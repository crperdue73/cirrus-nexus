#!/bin/sh
# Canary gate for tools/lint_lab_pack.py (2026-11-08).
# Each canary lab is named <label>__<EXPECTED VERDICT>. The gate requires the
# tool to produce exactly that verdict for each one -- a per-lab assertion, so
# "the tool still reads router maps the way the shipped graders expose them"
# is checkable in one command. The pack carries a deliberately SOLVED and a
# deliberately broken lab, so the pack-level exit code is 2 (see the tool's own
# ordering note); the gate reads the per-lab rows, not the exit code.
set -u
# Resolve both paths from this script's location: the script lives in
# tools/canaries/, while the tool and the pack are one level up. (Measured
# 2026-11-08: `cd $(dirname $0)/..` lands in tools/, so a pack path relative to
# the repo root was checked one directory too high and the gate declared its
# own full pack empty.)
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
root=$(CDPATH= cd -- "$here/../.." && pwd) || exit 1
pack="${1:-$here/lab-pack}"
cd "$root" || exit 1
out=$(python3 tools/lint_lab_pack.py --json --labs-dir "$pack" 2>/dev/null); rc=$?
# 0 clean, 1 red flag, 2 an unexaminable lab: all three still print per-lab rows,
# and this pack is built to produce 2. Anything else means the tool itself failed.
case "$rc" in
  0|1|2) ;;
  *) echo "canary gate: lint could not run on $pack (rc=$rc)"; exit 2 ;;
esac
fail=0
# Collect first so an empty pack says so instead of becoming a lab named "*.yml".
# (Measured 2026-11-08: a helper loop guarded with `[ -f "$y" ] && labs=...`
# is the LAST command of that loop body, so the loop's exit status was 1, and
# `dash -e`-free or not, the follow-on test then read as failure. Use if/then.)
labs=$(ls "$pack"/*.yml 2>/dev/null)
[ -n "$labs" ] || { echo "canary gate: no canary labs in $pack"; exit 2; }
# shellcheck disable=SC2086  # word splitting is intended: no canary name has a space
for yml in $labs; do
  name=$(basename "$yml" .yml)
  want=${name#*__}
  # Match on the file, not the metadata id: ids differ from file names by
  # punctuation (id demo2-shape vs file demo2-shape__UNSOLVED) and comparing on
  # the id silently made every row read ABSENT (measured 2026-11-08).
  topo="$pack/$name.yml"
  got=$(printf '%s' "$out" | python3 -c '
import json, os, sys
want = os.path.realpath(sys.argv[1])
for r in json.load(sys.stdin):
    t = r.get("topology") or ""
    if t and os.path.realpath(t) == want:
        print(r.get("status", ""))
        break
else:
    print("ABSENT")
' "$topo")
  [ "$got" = "$want" ] && status=ok || { status=FAIL; fail=1; }
  echo "  $status  $name: expected $want, got $got"
done
[ "$fail" -eq 0 ] && echo "canary gate OK: every canary lab got its expected verdict." \
  || echo "canary gate FAILED: at least one canary lab read wrong."
exit "$fail"
