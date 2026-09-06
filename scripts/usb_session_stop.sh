#!/bin/sh
# Do not tear down an active AOA handshake on its brief USB reset. If the
# cable is genuinely gone, the timer stops the power-hungry chain after 8 s.
systemctl restart sailife-usb-stop.timer >/dev/null 2>&1 || :
exit 0
