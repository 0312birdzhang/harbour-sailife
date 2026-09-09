#!/bin/sh
# Repair usb-moded's persistent Sailife selection at every boot. Package
# installation can race the daemon, and system settings can rewrite its state.

DEST=com.meego.usb_moded
PATH_OBJ=/com/meego/usb_moded
IFACE=com.meego.usb_moded
MODE=sailife_mode

call()
{
    method=$1
    shift
    dbus-send --system --print-reply --reply-timeout=3000 \
        --dest="$DEST" "$PATH_OBJ" "$IFACE.$method" "$@"
}

# usb-moded can be active before it has acquired its D-Bus name. Give slower
# boots up to 30 seconds; systemd retries the unit if the daemon stays absent.
attempt=0
while [ "$attempt" -lt 30 ]; do
    if call mode_request >/dev/null 2>&1; then
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
[ "$attempt" -lt 30 ] || exit 1

whitelist=$(call get_whitelisted_modes 2>/dev/null || :)
case "$whitelist" in
    *"$MODE"*) ;;
    *) call set_whitelisted string:"$MODE" boolean:true >/dev/null || exit 1 ;;
esac

configured=$(call get_config 2>/dev/null || :)
case "$configured" in
    *"\"$MODE\""*) ;;
    *) call set_config string:"$MODE" >/dev/null || exit 1 ;;
esac

# A successful D-Bus call only proves transport; verify both writes stuck.
call get_whitelisted_modes 2>/dev/null | grep -q "$MODE" || exit 1
call get_config 2>/dev/null | grep -q "\"$MODE\"" || exit 1
exit 0
