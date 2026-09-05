#!/bin/sh
# Route playback into a silent PulseAudio sink and expose 48 kHz stereo
# S16LE on the FIFO consumed by carlife_proto.py.
export XDG_RUNTIME_DIR=/run/user/100000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/100000/dbus/user_bus_socket

module_id=$(pactl load-module module-null-sink \
    sink_name=sailife_cast rate=48000 \
    sink_properties=device.description=Sailife 2>/dev/null) || exit 1

capture_pid=
cleanup()
{
    [ -n "$capture_pid" ] && kill "$capture_pid" 2>/dev/null
    pactl unload-module "$module_id" 2>/dev/null
}
trap cleanup EXIT INT TERM

parec --device=sailife_cast.monitor --format=s16le --rate=48000 \
    --channels=2 --property=application.name=sailife-audio \
    > /tmp/sailife-audio.pcm &
capture_pid=$!

while kill -0 "$capture_pid" 2>/dev/null; do
    pactl list short sink-inputs 2>/dev/null | while read -r input sink rest; do
        [ -n "$input" ] && pactl move-sink-input "$input" sailife_cast \
            >/dev/null 2>&1
    done
    sleep 1
done
wait "$capture_pid"
