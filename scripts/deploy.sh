#!/bin/sh
# Deploy to the tablet. Two modes:
#
# 1. Fast iteration — python proto + start script only (binaries untouched):
#      sh scripts/deploy.sh [user@host]
# 2. Full RPM install:
#      sh scripts/deploy.sh --rpm ../harbour-sailife-<ver>.aarch64.rpm [user@host]
#
# devel-su on this tablet only execs a SINGLE-WORD command (no shell
# metacharacters), so root work goes through a script scp'd to /tmp and run
# via:  echo asd | devel-su -c /tmp/root-job.sh
set -e
MODE="$1"; shift 2>/dev/null || true
case "$MODE" in
--rpm) RPMFILE="$1"; shift || true; TAB="${1:-defaultuser@192.168.3.224}" ;;
"")    TAB="${MODE:-defaultuser@192.168.3.224}" ;;
*)     TAB="$MODE" ;;
esac

if command -v sshpass >/dev/null 2>&1; then
    SCP="sshpass -p asd scp"; SSH="sshpass -p asd ssh"
else
    SCP="scp"; SSH="ssh"
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

case "$MODE" in
--rpm)
    [ -f "$RPMFILE" ] || { echo "usage: $0 --rpm <harbour-sailife-*.aarch64.rpm> [user@host]"; exit 1; }
    $SCP "$RPMFILE" "$TAB:/tmp/harbour-sailife.rpm"
    cat > "$TMP/root-job.sh" <<'EOF'
#!/bin/sh
rpm -Uvh --force /tmp/harbour-sailife.rpm
systemctl status carlife.service --no-pager | head -8
EOF
    ;;
*)
    $SCP carlife-proto/carlife_proto.py carlife-proto/aoa_manager.py "$TAB:/tmp/"
    $SCP scripts/start_convergence.sh "$TAB:/tmp/"
    cat > "$TMP/root-job.sh" <<'EOF'
#!/bin/sh
cp /tmp/carlife_proto.py /tmp/aoa_manager.py /opt/carlife/
cp /tmp/start_convergence.sh /opt/carlife/start_convergence.sh
sh /opt/carlife/start_convergence.sh
sleep 8
tail -n 15 /opt/carlife/proto.log
EOF
    ;;
esac

$SCP "$TMP/root-job.sh" "$TAB:/tmp/root-job.sh"
$SSH "$TAB" "chmod +x /tmp/root-job.sh && echo asd | devel-su -c /tmp/root-job.sh"
