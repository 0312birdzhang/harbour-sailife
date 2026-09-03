import socket, os, select, time, subprocess, sys

GADGET = '/sys/kernel/config/usb_gadget'
UDC = 'a600000.dwc3'
DEV = '/dev/usb/usb_accessory'

def run(cmd):
    subprocess.run(cmd, shell=True)

def switch_to_accessory():
    print('SWITCH idProduct -> 0x2d00', flush=True)
    run("echo '' > %s/g1/UDC" % GADGET)
    time.sleep(0.1)
    run("echo 0x2d00 > %s/g1/idProduct" % GADGET)
    time.sleep(0.1)
    run("echo %s > %s/g1/UDC" % (UDC, GADGET))
    time.sleep(0.1)
    st = open('/sys/class/udc/%s/state' % UDC).read().strip()
    pid = open('%s/g1/idProduct' % GADGET).read().strip()
    print('after switch: UDC=%s PID=%s' % (st, pid), flush=True)

# open accessory data channel early (works whenever function is bound)
try:
    fd = os.open(DEV, os.O_RDWR | os.O_NONBLOCK)
    print('OPEN accessory fd=%d' % fd, flush=True)
except OSError as e:
    print('OPEN FAIL:', e, flush=True)
    fd = None

# netlink kobject uevent listener
NETLINK_KOBJECT_UEVENT = getattr(socket, 'NETLINK_KOBJECT_UEVENT', 15)
sock = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_KOBJECT_UEVENT)
sock.bind((0, 1))
print('listening for ACCESSORY=START (netlink) ...', flush=True)

t0 = time.time()
started = False
polls = [sock]
if fd is not None:
    polls.append(fd)
total = 0

while time.time() - t0 < 120:
    r, w, x = select.select(polls, [], [], 2)
    for s in r:
        if s is sock:
            data = s.recv(65536)
            fields = data.split(b'\x00')
            if b'ACCESSORY=START' in fields:
                print('>>> ACCESSORY=START uevent received!', flush=True)
                started = True
                switch_to_accessory()
        elif fd is not None and s is fd:
            try:
                data = os.read(fd, 16384)
                if data:
                    total += len(data)
                    print('READ %d bytes (total %d): %s' % (len(data), total, data[:64].hex()), flush=True)
            except BlockingIOError:
                pass
            except OSError as e:
                print('READ ERR:', e, flush=True)
    if started and total > 0 and time.time() - t0 > 40:
        print('got data, stopping early', flush=True)
        break

print('DONE started=%s total_bytes=%d' % (started, total), flush=True)
if fd is not None:
    os.close(fd)