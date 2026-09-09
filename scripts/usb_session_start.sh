#!/bin/sh
# AOA changes USB identity once during negotiation. Cancel a pending stop
# when usb-moded sees the Sailife mode return after that re-enumeration.
systemctl stop sailife-usb-stop.timer >/dev/null 2>&1 || :
systemctl reset-failed sailife-usb-stop.timer sailife-usb-stop.service >/dev/null 2>&1 || :
rm -f /tmp/sailife-stop-defer
systemctl start sailife.service
exit $?
