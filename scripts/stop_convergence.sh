#!/bin/sh
pkill -f 'carui/carui /opt/carlife/carui/main.qml' 2>/dev/null || :
# A capture process blocked in a FIFO write does not exit on SIGTERM.
for pid in $(pgrep -f '^/opt/carlife/carlife-capture '); do
    kill -9 "$pid" 2>/dev/null || :
done
pkill -f '/opt/carlife/imira-comp --width' 2>/dev/null || :
pkill -f '/opt/carlife/audio_bridge.sh' 2>/dev/null || :
pkill -f '/opt/carlife/carlife_proto.py' 2>/dev/null || :
exit 0
