#!/bin/sh
pkill -f carlife_proto 2>/dev/null
# A capture process blocked in a FIFO write does not exit on SIGTERM.
for pid in $(pgrep -f '^/opt/carlife/carlife-capture '); do
    kill -9 "$pid" 2>/dev/null || :
done
pkill -f imira-comp 2>/dev/null
pkill -f audio_bridge.sh 2>/dev/null
# Only stop the projected launcher. The Sailife phone UI uses the same
# executable with mobile-settings.qml and must survive starting this service.
pkill -f 'carui/carui /opt/carlife/carui/main.qml' 2>/dev/null
sleep 0.5
mkfifo /tmp/cast.h264 2>/dev/null
chmod 666 /tmp/cast.h264
mkfifo /tmp/sailife-audio.pcm 2>/dev/null
chmod 666 /tmp/sailife-audio.pcm
# stale H/S commands in the compositor's FIFO would replay on its next
# start (the poller starts at offset 0) — start from a clean slate
: > /tmp/imira-touch
chmod 666 /tmp/imira-touch
# proto first: it creates the uinput mouse, which the compositor's
# InputHandler scans for at startup (it never rescans afterwards).
nohup python3 /opt/carlife/carlife_proto.py > /opt/carlife/proto.log 2>&1 < /dev/null &
su defaultuser -s /bin/sh -c "/opt/carlife/audio_bridge.sh > /home/defaultuser/audio.log 2>&1" < /dev/null > /dev/null 2>&1 &
sleep 1
# At boot systemd may run us before lipstick is up; the compositor needs
# its Wayland display, so wait for the socket (max 30s) and carry on.
# NOTE: WAYLAND_DISPLAY=../../display/wayland-0 normalises to /run/display —
# lipstick's socket lives there, NOT under /run/user/100000.
n=0
while [ ! -S /run/display/wayland-0 ] && [ $n -lt 60 ]; do
    sleep 0.5
    n=$((n+1))
done
su defaultuser -s /bin/sh -c "XDG_RUNTIME_DIR=/run/user/100000 WAYLAND_DISPLAY=../../display/wayland-0 /opt/carlife/imira-comp --width 1920 --height 720 > /home/defaultuser/comp.log 2>&1" < /dev/null > /dev/null 2>&1 &
sleep 2
su defaultuser -s /bin/sh -c "XDG_RUNTIME_DIR=/run/user/100000 QT_QPA_PLATFORM=wayland WAYLAND_DISPLAY=imira-comp-0 /opt/carlife/carui/carui /opt/carlife/carui/main.qml > /home/defaultuser/carui.log 2>&1" < /dev/null > /dev/null 2>&1 &
su defaultuser -s /bin/sh -c "XDG_RUNTIME_DIR=/run/user/100000 /opt/carlife/carlife-capture --input shm --out /tmp/cast.h264 --width 1920 --height 720 --fps 30 --bitrate 4000000 > /home/defaultuser/capture.log 2>&1" < /dev/null > /dev/null 2>&1 &
sleep 2
pgrep -f imira-comp >/dev/null && echo "comp: OK" || echo "comp: FAIL"
pgrep -f 'carui/carui /opt/carlife/carui/main.qml' >/dev/null && echo "carui: OK" || echo "carui: FAIL"
pgrep -f 'input shm' >/dev/null && echo "capture: OK" || echo "capture: FAIL"
pgrep -f carlife_proto >/dev/null && echo "proto: OK" || echo "proto: FAIL"
pgrep -f audio_bridge.sh >/dev/null && echo "audio: OK" || echo "audio: FAIL"
exit 0
