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
RELEASE=7
REPO=/parentroot/mnt/d/code/sfos-carlife/harbour-sailife
WORK=/tmp/$NAME-build
STAGE=$WORK/$NAME-$VERSION

test -f "$REPO/rpm/payload/imira-comp" || { echo "run rpm/build-arm.sh first"; exit 1; }

rm -rf "$WORK"
mkdir -p "$STAGE/rpm/payload" "$STAGE/carlife-proto" "$STAGE/carui" "$STAGE/scripts"
# exactly the set the spec installs (plus the carui sources for reference)
cp "$REPO"/carlife-proto/carlife_proto.py "$REPO"/carlife-proto/aoa_manager.py "$STAGE/carlife-proto/"
cp "$REPO"/carui/main.cpp "$REPO"/carui/main.qml "$REPO"/carui/mobile-settings.qml "$REPO"/carui/harbour-sailife.png "$REPO"/carui/carui.pro "$REPO"/carui/carui-apps.conf "$STAGE/carui/"
cp "$REPO"/scripts/start_convergence.sh "$REPO"/scripts/stop_convergence.sh "$REPO"/scripts/audio_bridge.sh "$REPO"/scripts/usb_session_start.sh "$REPO"/scripts/usb_session_stop.sh "$REPO"/scripts/usb_session_maybe_stop.sh "$REPO"/scripts/usb_mode_restore.sh "$STAGE/scripts/"
cp "$REPO"/rpm/harbour-sailife.spec "$REPO"/rpm/sailife.service "$REPO"/rpm/harbour-sailife.desktop "$REPO"/rpm/50-sailife.rules "$REPO"/rpm/sailife-xpolicy.conf "$REPO"/rpm/sailife-usb-mode.ini "$REPO"/rpm/sailife-usb-appsync.ini "$REPO"/rpm/90-sailife-usb.ini "$REPO"/rpm/sailife-usb-environment.conf "$REPO"/rpm/sailife-usb-session.service "$REPO"/rpm/sailife-usb-stop.service "$REPO"/rpm/sailife-usb-stop.timer "$REPO"/rpm/sailife-usb-restore.service "$REPO"/rpm/sailife-usb-restore.timer "$REPO"/rpm/sailife-usb-moded.conf "$STAGE/rpm/"
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
RPM="$HOME/rpmbuild/RPMS/aarch64/$NAME-$VERSION-$RELEASE.aarch64.rpm"
test -f "$RPM" || { echo "RPM missing: $RPM"; exit 1; }
echo "RPM_OK $RPM"
