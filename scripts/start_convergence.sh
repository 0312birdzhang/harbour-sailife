#!/bin/sh
pkill -f carlife_proto 2>/dev/null
pkill -f carlife-capture 2>/dev/null
pkill -f imira-comp 2>/dev/null
pkill -f 'carui/carui' 2>/dev/null
sleep 0.5
mkfifo /tmp/cast.h264 2>/dev/null
chmod 666 /tmp/cast.h264
mkfifo /tmp/carui-touch 2>/dev/null
chmod 666 /tmp/carui-touch
su defaultuser -s /bin/sh -c "XDG_RUNTIME_DIR=/run/user/100000 WAYLAND_DISPLAY=../../display/wayland-0 /opt/carlife/imira-comp --width 1920 --height 720 > /home/defaultuser/comp.log 2>&1" < /dev/null > /dev/null 2>&1 &
sleep 2
su defaultuser -s /bin/sh -c "XDG_RUNTIME_DIR=/run/user/100000 QT_QPA_PLATFORM=wayland WAYLAND_DISPLAY=imira-comp-0 /opt/carlife/carui/carui /opt/carlife/carui/main.qml > /home/defaultuser/carui.log 2>&1" < /dev/null > /dev/null 2>&1 &
su defaultuser -s /bin/sh -c "XDG_RUNTIME_DIR=/run/user/100000 /opt/carlife/carlife-capture --input shm --out /tmp/cast.h264 --width 1920 --height 720 --fps 30 --bitrate 4000000 > /home/defaultuser/capture.log 2>&1" < /dev/null > /dev/null 2>&1 &
nohup python3 /opt/carlife/carlife_proto.py > /opt/carlife/proto.log 2>&1 < /dev/null &
sleep 2
pgrep -f imira-comp >/dev/null && echo "comp: OK" || echo "comp: FAIL"
pgrep -f 'carui/carui' >/dev/null && echo "carui: OK" || echo "carui: FAIL"
pgrep -f 'input shm' >/dev/null && echo "capture: OK" || echo "capture: FAIL"
pgrep -f carlife_proto >/dev/null && echo "proto: OK" || echo "proto: FAIL"
exit 0