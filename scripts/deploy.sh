#!/bin/sh
# Push the Python proto files + start script to the tablet and restart the chain.
# Binaries (imira-comp / carui / carlife-capture) are NOT touched — rebuild and
# copy them separately when they change.
#
# Usage (from the repo root; needs ssh keys or will prompt for the tablet password):
#   sh scripts/deploy.sh [user@host]
set -e
TAB=${1:-defaultuser@192.168.3.224}

scp carlife-proto/carlife_proto.py carlife-proto/aoa_manager.py "$TAB:/tmp/"
scp scripts/start_convergence.sh "$TAB:/tmp/"

ssh "$TAB" "echo asd | devel-su -c 'cp /tmp/carlife_proto.py /tmp/aoa_manager.py /opt/carlife/ &&
    cp /tmp/start_convergence.sh /home/defaultuser/start_convergence.sh &&
    sh /home/defaultuser/start_convergence.sh'"

echo "--- proto.log ---"
ssh "$TAB" "tail -n 15 /opt/carlife/proto.log"
