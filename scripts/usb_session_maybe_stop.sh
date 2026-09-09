#!/bin/sh
# Guard behind sailife-usb-stop.service (fired 8s after usb-moded reports the
# Sailife mode leaving). The 4EE1->2D00 AOA re-enumeration looks like a mode
# leave: without this guard the timer kills sailife.service mid-handshake,
# the head unit shows "unsupported device", and the user must start the app
# by hand. While the link looks alive (UDC configured + proto running) defer
# by re-arming the timer instead of stopping. Deferrals are capped so a real
# unplug or a mode switch still terminates the chain; usb_session_start.sh
# resets the counter on every (re-)enter.
DEFER_FILE=/tmp/sailife-stop-defer
MAX_DEFER=7

udc_state()
{
    cat /sys/class/udc/*/state 2>/dev/null | head -1
}

count=$(cat "$DEFER_FILE" 2>/dev/null || echo 0)
case "$count" in
    ''|*[!0-9]*) count=0 ;;
esac

if [ "$(udc_state)" = "configured" ] && \
   pgrep -f '/opt/carlife/carlife_proto.py' >/dev/null 2>&1; then
    if [ "$count" -lt "$MAX_DEFER" ]; then
        echo $((count + 1)) > "$DEFER_FILE"
        systemctl restart sailife-usb-stop.timer >/dev/null 2>&1
        exit 0
    fi
fi

rm -f "$DEFER_FILE"
systemctl stop sailife.service >/dev/null 2>&1
exit 0
