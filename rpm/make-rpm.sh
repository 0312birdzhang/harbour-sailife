#!/bin/bash
# Pack the RPM from the (already cross-built) tree. Run INSIDE the SDK under
# the aarch64 target (the chroot's host-side rpm only knows x86 build archs):
#
#   sudo ./sdk-chroot -u <sdkuser> sb2 -t SailfishOS-latest-aarch64 bash \
#       /parentroot/mnt/d/code/sfos-carlife/harbour-sailife/rpm/make-rpm.sh
#
# Version here and Version: in the spec must match.
set -e
NAME=harbour-sailife
VERSION=0.1.0
REPO=/parentroot/mnt/d/code/sfos-carlife/harbour-sailife
WORK=/tmp/$NAME-build
STAGE=$WORK/$NAME-$VERSION

test -f "$REPO/rpm/payload/imira-comp" || { echo "run rpm/build-arm.sh first"; exit 1; }

rm -rf "$WORK"
mkdir -p "$STAGE/rpm/payload" "$STAGE/carlife-proto" "$STAGE/carui" "$STAGE/scripts"
# exactly the set the spec installs (plus the carui sources for reference)
cp "$REPO"/carlife-proto/carlife_proto.py "$REPO"/carlife-proto/aoa_manager.py "$STAGE/carlife-proto/"
cp "$REPO"/carui/main.cpp "$REPO"/carui/main.qml "$REPO"/carui/carui.pro "$REPO"/carui/carui-apps.conf "$STAGE/carui/"
cp "$REPO"/scripts/start_convergence.sh "$STAGE/scripts/"
cp "$REPO"/rpm/harbour-sailife.spec "$REPO"/rpm/carlife.service "$STAGE/rpm/"
cp "$REPO"/rpm/payload/imira-comp "$REPO"/rpm/payload/carui "$REPO"/rpm/payload/carlife-capture "$STAGE/rpm/payload/"

cd "$WORK"
tar cjf "$NAME-$VERSION.tar.bz2" "$NAME-$VERSION"

# __os_install_post nil: host-side strip/debuginfo must not touch aarch64 binaries
rpmbuild -ta --target aarch64 \
    --define "_buildhost reproducible-builder" \
    --define "debug_package %{nil}" \
    --define "__os_install_post %{nil}" \
    "$NAME-$VERSION.tar.bz2"

# deterministic name (a plain glob under sb2 mysteriously misses the file)
RPM="$HOME/rpmbuild/RPMS/aarch64/$NAME-$VERSION-1.aarch64.rpm"
test -f "$RPM" && echo "RPM_OK $RPM"
