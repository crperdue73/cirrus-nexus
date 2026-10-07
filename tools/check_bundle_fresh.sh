#!/usr/bin/env bash
# Verify the shippable bundle matches the source tree.
#
# Guards against the failure the README records historically: the bundle sat un-rebuilt for 3.5
# months, shipping neither current lab nor current code, and was referenced by nothing so nothing
# flagged it. Run this after any edit to a bundled file. Exit 1 if the bundle is stale.
#
# The bundle is not committed (see .gitignore), so in CI this prints "no bundle present" and exits 0.
set -euo pipefail
cd "$(dirname "$0")/.."

B="frontend/nexus-release.tar.gz"
if [ ! -f "$B" ]; then
  echo "no bundle present at $B — nothing to check"
  exit 0
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tar xzf "$B" -C "$tmp" backend/main.py frontend/index.html 2>/dev/null || true

rc=0
for f in backend/main.py frontend/index.html; do
  if cmp -s "$f" "$tmp/$f"; then
    echo "OK    $f"
  else
    echo "STALE $f — bundle differs from the tree"
    rc=1
  fi
done

if [ "$rc" -eq 0 ]; then
  echo "bundle is in sync with the source"
else
  echo "BUNDLE STALE — rebuild it with the command in docs/OPERATIONS.md"
fi
exit "$rc"
