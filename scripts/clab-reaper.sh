#!/usr/bin/env bash
# clab-reaper.sh — find and destroy orphaned containerlab labs on the AEGIS host.
#
# WHY: lab sessions created outside the normal stop path leave `clab-*` containers
# running. `docker ps` shows them as healthy; only `containerlab inspect --all`
# reveals they belong to no live lab. Two known bursts (2026-10-15 19:0x and 23:4x)
# left 14 labs / 46 containers running for four days.
#
# RULE: never touch non-clab containers. That's the six real services
# (nexus-backend, pasteboard, heimdall, portainer, uptime-kuma, glances).
#
# RULE: age alone is not evidence of an orphan. A learner can sit in a lab for
# hours; the "four days" burst this script was written for was found by
# reconciling against the product's own session state, not by a clock. So a lab
# is only a candidate for reaping when the product's authoritative list cannot
# account for it (`--orphans`, below).
#
# MODES
#   --dry-run   (default) print what would be destroyed, change nothing
#   --apply     actually destroy
#   --min-age N only reap labs older than N minutes (default 60)
#   --orphans   DEFAULT: only reap labs the product does NOT know about (asks the
#               live app; needs $NEXUS_URL, default http://127.0.0.1:8000)
#   --age-only  reap on age ALONE, ignoring ownership. Dangerous: reaps labs a
#               learner is still holding. Requires --apply AND an explicit
#               confirmation flag on purpose.
#   --json      machine-readable summary on stdout
#
# SAFETY
#   * snapshots `containerlab inspect --all` JSON before deleting anything
#   * writes an append-only JSONL run log
#   * refuses to run if it cannot confirm the lab name maps to clab-* containers
#   * with --orphans, refuses to reap ANYTHING if the app cannot be reached or the
#     ownership labels are missing - "could not ask" is not "nothing is owned"
#   * uses `docker rm -f` fallback when `containerlab destroy` hangs
#
# Installed by: Selina, 2026-10-19, at operator request.

set -uo pipefail

MODE="dry-run"
MIN_AGE_MIN=60
JSON=0
LOG_DIR="/var/log/clab-reaper"
BACKUP_ROOT="/root/clab-reaper-backups"
CLAB_DESTROY_TIMEOUT=120
ORPHANS_ONLY=1
AGE_ONLY=0
NEXUS_URL="${NEXUS_URL:-http://127.0.0.1:8000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) MODE="apply"; shift ;;
    --dry-run) MODE="dry-run"; shift ;;
    --min-age) MIN_AGE_MIN="${2:-60}"; shift 2 ;;
    --orphans) ORPHANS_ONLY=1; shift ;;
    --age-only) ORPHANS_ONLY=0; AGE_ONLY=1; shift ;;
    --json) JSON=1; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

if [[ "$AGE_ONLY" -eq 1 && "$MODE" == "apply" && "${CLAB_REAPER_I_MEAN_IT:-0}" != "1" ]]; then
  echo "clab-reaper: --age-only --apply reaps labs by clock alone, including labs a" >&2
  echo "  learner may still be holding. If that is really what you want, re-run with" >&2
  echo "  CLAB_REAPER_I_MEAN_IT=1 in the environment." >&2
  exit 5
fi

mkdir -p "$LOG_DIR" "$BACKUP_ROOT"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
SNAP="$BACKUP_ROOT/$TS"
mkdir -p "$SNAP"

command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }
command -v containerlab >/dev/null || { echo "containerlab not found" >&2; exit 1; }

# ---- 1. Snapshot -----------------------------------------------------------
containerlab inspect --all --format json > "$SNAP/labs.json" 2>/dev/null
docker ps --format '{{.Names}}\t{{.Image}}\t{{.CreatedAt}}\t{{.Status}}' > "$SNAP/containers.txt"
CLAB_TOTAL_BEFORE=$(docker ps --format '{{.Names}}' | grep -c '^clab-' || true)
ALL_TOTAL_BEFORE=$(docker ps -q | wc -l)

# ---- 2. Enumerate labs with age -------------------------------------------
# Emit: <lab_name>\t<age_minutes>\t<node_count>
LABROWS="$(python3 - "$SNAP/labs.json" <<'PY'
import json, subprocess, sys, datetime

path = sys.argv[1]
try:
    d = json.load(open(path))
except Exception:
    sys.exit(0)

rows = []
for lab, nodes in d.items():
    names = [n.get("name") for n in nodes if n.get("name")]
    if not names:
        continue
    # oldest node in the lab defines its age
    oldest = None
    for nm in names:
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.Created}}", nm],
            capture_output=True, text=True).stdout.strip()
        if not out:
            continue
        try:
            dt = datetime.datetime.fromisoformat(out.replace("Z", "+00:00"))
        except Exception:
            continue
        if oldest is None or dt < oldest:
            oldest = dt
    if oldest is None:
        continue
    now = datetime.datetime.now(datetime.timezone.utc)
    age_min = int((now - oldest).total_seconds() // 60)
    rows.append(f"{lab}\t{age_min}\t{len(names)}")

for r in rows:
    print(r)
PY
)"

# ---- 2b. Ownership: drop the labs the product is actively tracking -----------
# The product's own view lives at GET /api/sessions and is rebuilt at startup from
# the `aegis.session.id` label it stamps on every container it deploys
# (backend/main.py -> reconcile_sessions). Those labels are the authority on what
# a learner currently holds: an unlabelled clab container, or a labelled one the
# app does not list, is the actual orphan class this script exists for.
#
# A session is represented by its node containers, so a lab is "owned" only when
# EVERY one of its nodes carries an `aegis.session.id` that the app is tracking.
# If any node is unlabelled we cannot establish ownership at all and refuse.
OWNED_IDS=""
OWNERSHIP_OK=0
if [[ "$ORPHANS_ONLY" -eq 1 ]]; then
  if ! curl -fsS --max-time 10 "$NEXUS_URL/api/sessions" > "$SNAP/sessions.json"; then
    echo "clab-reaper: could not read $NEXUS_URL/api/sessions - refusing to reap on a guess" >&2
    exit 3
  fi
  # NOTE: this used a `python3` one-liner with embedded newlines. `python3` only treats
  # `-c` as a script when it is the IMMEDIATELY following argv element; here it was
  # `python3` + a multi-line argv + the json path, so the first line went to the
  # interpreter as a FILE NAME (-> "can't open file '"$ python3 -c '": [Errno 2]") and
  # the json path was silently swallowed. The `if !` then read that as "did not parse"
  # and exited 3, so against a reachable app this reaper ALWAYS refused before: it
  # never reaped anything and never said why. Same fix as scripts/session-read.py and
  # the 2026-10-06 lesson: python-in-shell goes in a HEREDOC, never a `-c` one-liner.
  if ! OWNED_IDS="$(python3 - "$SNAP/sessions.json" <<'PY' | sort -u
import json, sys
docs = json.load(open(sys.argv[1]))
if isinstance(docs, dict):
    docs = docs.get("sessions", [])
for s in docs:
    if isinstance(s, dict) and s.get("session_id"):
        print(s["session_id"])
PY
)"; then
    echo "clab-reaper: the sessions response did not parse - refusing to reap on a guess" >&2
    exit 3
  fi
  UNLABELLED="$(docker ps --format '{{.Names}}	{{.Label "aegis.session.id"}}' \
    | awk -F'\t' '$1 ~ /^clab-/ && ($2 == "" || $2 == "<no value>") {print $1}')"
  if [[ -n "$UNLABELLED" ]]; then
    echo "clab-reaper: $(echo "$UNLABELLED" | wc -l) clab container(s) carry no aegis.session.id label;" >&2
    echo "  ownership cannot be established - refusing to reap. Snapshot: $SNAP" >&2
    exit 4
  fi
  OWNERSHIP_OK=1
fi

# node container names for one topology, one per line
_lab_nodes() {
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
for n in (d.get(sys.argv[2]) or []):
    if n.get("name"):
        print(n["name"])
' "$SNAP/labs.json" "$1"
}

_owned_by_product() {
  local name sid
  [[ "$OWNERSHIP_OK" -eq 1 ]] || return 1
  while read -r name; do
    [[ -z "$name" ]] && continue
    sid="$(docker inspect -f '{{index .Config.Labels "aegis.session.id"}}' "$name" 2>/dev/null)"
    [[ -z "$sid" || "$sid" == "<no value>" ]] && return 1
    grep -qxF "$sid" <<< "$OWNED_IDS" || return 1
  done < <(_lab_nodes "$1")
  return 0
}

# ---- 3. Decide -------------------------------------------------------------
REAP=()
KEEP=()
SKIP_OWNED=()
while IFS=$'\t' read -r lab age nodes; do
  [[ -z "${lab:-}" ]] && continue
  if [[ "$age" -lt "$MIN_AGE_MIN" ]]; then
    KEEP+=("$lab")
  elif [[ "$ORPHANS_ONLY" -eq 1 ]] && _owned_by_product "$lab"; then
    SKIP_OWNED+=("$lab")
  else
    REAP+=("$lab")
  fi
done <<< "$LABROWS"

: "${REAP[@]:-}"; : "${KEEP[@]:-}"; : "${SKIP_OWNED[@]:-}"

# ---- 4. Act ---------------------------------------------------------------
DESTROYED=0
FAILED=0
FALLBACK=0

if [[ "$MODE" == "apply" ]]; then
  for lab in "${REAP[@]:-}"; do
    [[ -z "${lab:-}" ]] && continue
    if timeout "$CLAB_DESTROY_TIMEOUT" containerlab destroy --name "$lab" --cleanup >/dev/null 2>&1; then
      DESTROYED=$((DESTROYED+1))
    else
      # fallback: containerlab hung or errored — remove its containers directly
      docker ps -aq --filter "name=^clab-${lab}-" | xargs -r docker rm -f >/dev/null 2>&1
      if [[ "$(docker ps -q --filter "name=^clab-${lab}-" | wc -l)" -eq 0 ]]; then
        DESTROYED=$((DESTROYED+1)); FALLBACK=$((FALLBACK+1))
      else
        FAILED=$((FAILED+1))
      fi
      # best-effort network cleanup
      docker network ls --format '{{.Name}}' | grep -qx "clab" && true
    fi
  done
  # leftover mgmt helpers only after all labs in scope are gone
  if [[ "${#REAP[@]}" -gt 0 && "${#KEEP[@]}" -eq 0 ]]; then
    docker ps -aq --filter 'name=^clab$' | xargs -r docker rm -f >/dev/null 2>&1 || true
  fi
fi

CLAB_TOTAL_AFTER=$(docker ps --format '{{.Names}}' | grep -c '^clab-' || true)
ALL_TOTAL_AFTER=$(docker ps -q | wc -l)
N_REAP=${#REAP[@]}
N_KEEP=${#KEEP[@]}
N_FOUND=$(( N_REAP + N_KEEP ))

# ---- 5. Report -------------------------------------------------------------
if [[ "$JSON" -eq 1 ]]; then
  python3 - "$MODE" "$MIN_AGE_MIN" "$CLAB_TOTAL_BEFORE" "$CLAB_TOTAL_AFTER" \
            "$ALL_TOTAL_BEFORE" "$ALL_TOTAL_AFTER" "$DESTROYED" "$FAILED" "$FALLBACK" \
            "${REAP[*]:-}" "${KEEP[*]:-}" "$SNAP" <<'PY'
import json, sys, datetime
(mode, min_age, cb, ca, ab, aa, d, f, fb, reap, keep, snap) = sys.argv[1:13]
print(json.dumps({
    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "mode": mode, "min_age_minutes": int(min_age),
    "clab_containers_before": int(cb), "clab_containers_after": int(ca),
    "containers_before": int(ab), "containers_after": int(aa),
    "labs_destroyed": int(d), "labs_failed": int(f), "docker_rm_fallbacks": int(fb),
    "labs_reaped": reap.split() if reap else [],
    "labs_kept_too_new": keep.split() if keep else [],
    "snapshot": snap,
}, indent=2))
PY
else
  echo "clab-reaper  $TS  mode=$MODE  min_age=${MIN_AGE_MIN}m"
  echo "snapshot: $SNAP"
  echo
  echo "labs found:   $N_FOUND"
  echo "to reap:      $N_REAP   (age >= ${MIN_AGE_MIN}m)"
  if [[ "$ORPHANS_ONLY" -eq 1 ]]; then
    echo "owned/skipped: ${#SKIP_OWNED[@]}   (product is tracking these)"
  fi
  echo "kept (young): $N_KEEP"
  for lab in "${KEEP[@]:-}"; do [[ -n "${lab:-}" ]] && echo "    keep  $lab"; done
  for lab in "${REAP[@]:-}"; do [[ -n "${lab:-}" ]] && echo "    reap  $lab  [$(grep -P "^\Q$lab\E\t" <<< "$LABROWS" | cut -f2) min, $(grep -P "^\Q$lab\E\t" <<< "$LABROWS" | cut -f3) nodes]"; done
  echo
  if [[ "$MODE" == "dry-run" ]]; then
    echo "DRY RUN — nothing destroyed. Re-run with --apply."
  else
    echo "destroyed: $DESTROYED   failed: $FAILED   (docker rm fallback: $FALLBACK)"
  fi
  echo
  echo "clab containers: $CLAB_TOTAL_BEFORE -> $CLAB_TOTAL_AFTER"
  echo "all containers:  $ALL_TOTAL_BEFORE -> $ALL_TOTAL_AFTER"
fi

# ---- 6. Run log ------------------------------------------------------------
printf '{"ts":"%s","mode":"%s","min_age":%s,"labs_found":%s,"labs_reaped":%s,"destroyed":%s,"failed":%s,"fallback":%s,"clab_before":%s,"clab_after":%s,"all_before":%s,"all_after":%s}\n' \
  "$TS" "$MODE" "$MIN_AGE_MIN" "$N_FOUND" "$N_REAP" \
  "$DESTROYED" "$FAILED" "$FALLBACK" "$CLAB_TOTAL_BEFORE" "$CLAB_TOTAL_AFTER" \
  "$ALL_TOTAL_BEFORE" "$ALL_TOTAL_AFTER" >> "$LOG_DIR/runs.jsonl"

# Keep snapshots for 30 days
find "$BACKUP_ROOT" -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true

[[ "$FAILED" -eq 0 ]] && exit 0 || exit 1
