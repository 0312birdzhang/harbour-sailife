#!/bin/sh
# Route playback into a silent PulseAudio sink and expose 48 kHz stereo
# S16LE on the FIFO consumed by carlife_proto.py.
export XDG_RUNTIME_DIR=/run/user/100000

# wait for PulseAudio to be up
for i in 1 2 3 4 5 6 7 8 9 10; do
    pactl info >/dev/null 2>&1 && break
    sleep 0.5
done

module_id=$(pactl load-module module-null-sink \
    sink_name=sailife_cast rate=48000 \
    sink_properties=device.description=Sailife 2>/dev/null) || exit 1

# The null sink may come out as sailife_cast, sailife_cast.2, ... when an
# old instance was left behind by a crashed bridge. Resolve the ACTUAL
# monitor name — parec --device=sailife_cast.monitor would fail when the
# sink got a numeric suffix and fall back to the DEFAULT source (the
# microphone). Refuse to start if no sailife_cast monitor exists.
monitor=$(pactl list sources short 2>/dev/null |
    awk '$2 ~ /^sailife_cast/ {print $2; exit}')
if [ -z "$monitor" ]; then
    echo "no sailife_cast monitor" >&2
    pactl unload-module "$module_id" 2>/dev/null
    exit 1
fi

capture_pid=
cleanup()
{
    [ -n "$capture_pid" ] && kill "$capture_pid" 2>/dev/null
    pactl unload-module "$module_id" 2>/dev/null
}
trap cleanup EXIT INT TERM

# New playback defaults to the cast sink (tablet goes silent, head unit
# hears it); existing streams are moved in the loop below.
pactl set-default-sink sailife_cast 2>/dev/null

parec --device="$monitor" --format=s16le --rate=48000 \
    --channels=2 > /tmp/sailife-audio.pcm &
capture_pid=$!

while kill -0 "$capture_pid" 2>/dev/null; do
    pactl list short sink-inputs 2>/dev/null | while read -r input sink rest; do
        [ -n "$input" ] && pactl move-sink-input "$input" sailife_cast \
            >/dev/null 2>&1
    done
    sleep 1
done
wait "$capture_pid"