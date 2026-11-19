#!/bin/bash
# AEGIS host-compat patch for ghcr.io/nokia/srlinux
#
# WHY THIS EXISTS (2026-11-16):
#   `sr_log_mgr` validates the syslog config before every commit by running
#   `rsyslogd -N2` inside the `srbase` network namespace:
#       /usr/sbin/ip netns exec srbase ... rsyslogd ... -N2
#   `ip netns exec` tries to mount a FRESH sysfs into the netns. Under an LXC
#   parent that exports /sys read-only (our host: systemd-detect-virt -> lxc,
#   /sys mounted ro at the container root), that mount fails:
#       "mount of /sys failed: Operation not permitted"
#   log_mgr therefore reports "Unacceptable syslog configuration", the config
#   commit is rejected, and a student cannot change ANY switch setting. Every
#   SR Linux lab is unusable.
#
# THE FIX:
#   Replace `ip netns exec` with `nsenter --net=<path>`, which enters the SAME
#   network namespace without attempting a sysfs remount. rsyslogd -N2 only
#   needs the net namespace, so verification passes (verified rc=0) and commits
#   succeed.
set -euo pipefail
F=/opt/srlinux/bin/logmgr_set_env.sh
cp -p "$F" "$F.orig-aegis-patch"
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = '    [[ -n $g_network_instance ]] && cmd+="/usr/sbin/ip netns exec $(printf "%q" "$g_network_instance") "\n'
new = (
    '    # AEGIS PATCH 2026-11-16: ip netns exec remounts sysfs and fails under an\n'
    '    # LXC parent with read-only /sys, breaking rsyslogd -N2 and rejecting every\n'
    '    # commit. nsenter enters the same netns without the remount. See\n'
    '    # docker/srlinux-logmgr-netns.patch.sh for the full write-up.\n'
    '    if [[ -n $g_network_instance ]]; then\n'
    '        cmd+="/usr/bin/nsenter --net=/run/netns/$g_network_instance -- "\n'
    '    fi\n'
)
if old not in s:
    sys.exit("patch anchor not found -- srlinux script changed upstream")
open(p, "w").write(s.replace(old, new, 1))
PY
bash -n "$F"
echo "patched: $F"
