#!/bin/sh
pkill -f 'carui/carui /opt/carlife/carui/main.qml' 2>/dev/null || :
pkill -f 'carlife-capture --input shm' 2>/dev/null || :
pkill -f '/opt/carlife/imira-comp --width' 2>/dev/null || :
pkill -f '/opt/carlife/audio_bridge.sh' 2>/dev/null || :
pkill -f '/opt/carlife/carlife_proto.py' 2>/dev/null || :
exit 0
