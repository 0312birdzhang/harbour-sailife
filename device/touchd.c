/*
 * touchd - carlife touch injection daemon.
 * Reads "action x y" lines from stdin (action: 0=down 1=up 2=move),
 * injects MT-protocol touch events into a virtual uinput device.
 */
#include <linux/uinput.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>

#define MAX_X 1600
#define MAX_Y 2560
#define MAX_SLOTS 10

static int fd = -1;
static int cur_slot = -1;
static int tracking_id = -1;

static void emit(int type, int code, int val)
{
    struct input_event ev;
    memset(&ev, 0, sizeof(ev));
    ev.type = type;
    ev.code = code;
    ev.value = val;
    if (write(fd, &ev, sizeof(ev)) != sizeof(ev))
        fprintf(stderr, "touchd: write err %s\n", strerror(errno));
}

static int setup_device(void)
{
    fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (fd < 0) {
        fprintf(stderr, "touchd: open /dev/uinput: %s\n", strerror(errno));
        return -1;
    }
    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH);
    ioctl(fd, UI_SET_EVBIT, EV_ABS);
    ioctl(fd, UI_SET_ABSBIT, ABS_MT_SLOT);
    ioctl(fd, UI_SET_ABSBIT, ABS_MT_POSITION_X);
    ioctl(fd, UI_SET_ABSBIT, ABS_MT_POSITION_Y);
    ioctl(fd, UI_SET_ABSBIT, ABS_MT_TRACKING_ID);
    ioctl(fd, UI_SET_ABSBIT, ABS_X);
    ioctl(fd, UI_SET_ABSBIT, ABS_Y);

    struct uinput_user_dev udev;
    memset(&udev, 0, sizeof(udev));
    strncpy(udev.name, "carlife-touch", UINPUT_MAX_NAME_SIZE);
    udev.id.bustype = BUS_VIRTUAL;
    udev.id.vendor = 0x1234;
    udev.id.product = 0x5678;
    udev.id.version = 1;
    udev.absmax[ABS_MT_SLOT] = MAX_SLOTS - 1;
    udev.absmin[ABS_MT_SLOT] = 0;
    udev.absmax[ABS_MT_POSITION_X] = MAX_X;
    udev.absmin[ABS_MT_POSITION_X] = 0;
    udev.absmax[ABS_MT_POSITION_Y] = MAX_Y;
    udev.absmin[ABS_MT_POSITION_Y] = 0;
    udev.absmax[ABS_MT_TRACKING_ID] = MAX_SLOTS - 1;
    udev.absmin[ABS_MT_TRACKING_ID] = 0;
    udev.absmax[ABS_X] = MAX_X;
    udev.absmin[ABS_X] = 0;
    udev.absmax[ABS_Y] = MAX_Y;
    udev.absmin[ABS_Y] = 0;
    if (write(fd, &udev, sizeof(udev)) != sizeof(udev)) {
        fprintf(stderr, "touchd: write udev: %s\n", strerror(errno));
        return -1;
    }
    if (ioctl(fd, UI_DEV_CREATE) < 0) {
        fprintf(stderr, "touchd: UI_DEV_CREATE: %s\n", strerror(errno));
        return -1;
    }
    fprintf(stderr, "touchd: virtual touch device created (%dx%d)\n", MAX_X, MAX_Y);
    usleep(200000);
    return 0;
}

static void do_down(int x, int y)
{
    cur_slot = 0;
    tracking_id = 1;
    emit(EV_ABS, ABS_MT_SLOT, cur_slot);
    emit(EV_ABS, ABS_MT_TRACKING_ID, tracking_id);
    emit(EV_ABS, ABS_MT_POSITION_X, x);
    emit(EV_ABS, ABS_MT_POSITION_Y, y);
    emit(EV_ABS, ABS_X, x);
    emit(EV_ABS, ABS_Y, y);
    emit(EV_KEY, BTN_TOUCH, 1);
    emit(EV_SYN, SYN_REPORT, 0);
}

static void do_move(int x, int y)
{
    emit(EV_ABS, ABS_MT_SLOT, 0);
    emit(EV_ABS, ABS_MT_POSITION_X, x);
    emit(EV_ABS, ABS_MT_POSITION_Y, y);
    emit(EV_ABS, ABS_X, x);
    emit(EV_ABS, ABS_Y, y);
    emit(EV_SYN, SYN_REPORT, 0);
}

static void do_up(void)
{
    emit(EV_ABS, ABS_MT_SLOT, 0);
    emit(EV_ABS, ABS_MT_TRACKING_ID, -1);
    emit(EV_KEY, BTN_TOUCH, 0);
    emit(EV_SYN, SYN_REPORT, 0);
    tracking_id = -1;
}

int main(void)
{
    if (setup_device() < 0)
        return 1;
    char line[128];
    while (fgets(line, sizeof(line), stdin)) {
        int action, x, y;
        if (sscanf(line, "%d %d %d", &action, &x, &y) == 3) {
            if (action == 0) do_down(x, y);
            else if (action == 2) do_move(x, y);
            else if (action == 1) do_up();
        } else if (sscanf(line, "%d", &action) == 1 && action == 1) {
            do_up();
        }
    }
    ioctl(fd, UI_DEV_DESTROY);
    close(fd);
    return 0;
}