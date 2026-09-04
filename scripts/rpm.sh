#!/bin/sh
# One-shot RPM build from Windows/Git Bash: cross-compiles the ARM binaries
# in the WSL SailfishOS SDK (sb2) and then packs the RPM (rpmbuild).
#   sh scripts/rpm.sh
set -e
SDK=/srv/sailfishos/sdks/sfossdk
REPO=/parentroot/mnt/d/code/sfos-carlife/harbour-sailife

wsl.exe -u root -e bash -c "cd $SDK &&
    ./sdk-chroot -u pc sb2 -t SailfishOS-latest-aarch64 bash $REPO/rpm/build-arm.sh &&
    ./sdk-chroot -u pc sb2 -t SailfishOS-latest-aarch64 bash $REPO/rpm/make-rpm.sh"

# copy the fresh RPM out to the workspace (WSL side; outside the SDK sandbox)
cp -v /home/pc/rpmbuild/RPMS/aarch64/harbour-sailife-*.aarch64.rpm /mnt/d/code/sfos-carlife/
