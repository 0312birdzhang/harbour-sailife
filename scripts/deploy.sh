#!/bin/sh
# Two modes:
#
# 1. Deploy the Python proto files + start script and restart the chain
#    (binaries untouched — fast iteration):
#      sh scripts/deploy.sh [user@host]
#
# 2. Install the built RPM (systemd service + all binaries):
#      sh scripts/deploy.sh --rpm ../harbour-sailife-<ver>.aarch64.rpm [user@host]
set -e
TAB=${2:-defaultuser@192.168.3.224}

if [ "$1" = "--rpm" ]; then
    RPM=$(ls "$1" 2>/dev/null || true)
    [ -n "$RPM" ] || { echo "usage: $0 --rpm <harbour-sailife-*.aarch64.rpm> [user@host]"; exit 1; }
    scp "$RPM" "$TAB:/tmp/harbour-sailife.rpm"
    ssh "$TAB" "echo asd | devel-su -c 'rpm -Uvh --force /tmp/harbour-sailife.rpm &&
        systemctl status carlife.service --no-pager | head -8'"
    exit 0
fi

scp carlife-proto/carlife_proto.py carlife-proto/aoa_manager.py "$TAB:/tmp/"
scp scripts/start_convergence.sh "$TAB:/tmp/"

ssh "$TAB" "echo asd | devel-su -c 'cp /tmp/carlife_proto.py /tmp/aoa_manager.py /opt/carlife/ &&
    cp /tmp/start_convergence.sh /home/defaultuser/start_convergence.sh &&
    sh /home/defaultuser/start_convergence.sh'"

echo "--- proto.log ---"
ssh "$TAB" "tail -n 15 /opt/carlife/proto.log"
