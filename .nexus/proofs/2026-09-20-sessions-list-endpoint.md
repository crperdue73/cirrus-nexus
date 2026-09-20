# Proof — GET /api/sessions (live-session enumeration)

Date: 2026-09-20 ~12:1x EDT (nexus-hourly-drive)
Driver: Selina
Status: SHIPPED + VERIFIED LIVE

## Why (the earliest genuinely un-done item)
Prior hour (11:0x) named the remaining ergonomics gap:
  `GET /api/sessions` -> 404; stopping a session required already knowing its id.

Confirmed absent on the running app before touching anything:
    curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/sessions
    -> 404

## What was also re-checked first (no fake green)
The composite proof's named NEXT item — "first-grade race: submit immediately
after start can read runtime_digest=None" — was RE-TESTED before being called
done:
    substrate-less path (demo-01): 3/3 runs -> first grade digest = aegis-less:4ab4e8d7...  status=graded
    frr-substrate path (lab-04):   3/3 runs -> start digest AND first grade = sha256:bb7ef23a... status=graded
6/6 clean. The bounded retry in resolve_runtime_digest() closes it on both paths.
No code change needed; the named race is genuinely closed.

## Change (backend/main.py)
Added `GET /api/sessions` BEFORE the `{session_id}` route (ordering matters;
route registered at line 845, `{session_id}` at 872 — verified).

Returns every live session with: session_id, lab_id, student_name, status,
created_at, node names, and runtime_digest. Sorted newest-first. Count included.

`GET /api/sessions/{session_id}` was already per-session; this is the missing
collection read. Session lifecycle is now fully addressable:
    start -> list -> get -> submit -> stop

## Change (frontend/index.html)
Live-sessions panel (#live-sessions):
  - loads `/api/sessions` on DOMContentLoaded and after start/stop
  - renders each running session with lab, student, node count, id, digest
  - per-row Stop button calls the existing stop path by id (stopSessionById)
  - state is server truth, not this tab's memory — a session started in another
    tab/host is visible and stoppable here

## Verified LIVE (executed against the running app)
    GET  /api/sessions  (empty)              -> {"sessions":[],"count":0}
    POST /api/sessions/start?lab_id=demo-01  -> session b36b8902
    GET  /api/sessions                       -> count 1, digest aegis-less:4ab4e8d7...
    POST /api/sessions/b36b8902/stop         -> destroyed
    GET  /api/sessions                       -> count 0

    Served page contains loadLiveSessions x4 (panel wired into served HTML).

    frr substrate path:
    POST /api/sessions/start?lab_id=lab-04-two-as-peering -> session 8404047e
    GET  /api/sessions -> 8404047e  digest sha256:bb7ef23a...
       (== assets/frr-image.pin layers_sha256 — MATCH)
    stop -> count 0

    py_compile (with -W error::SyntaxWarning) -> CLEAN
    node --check on extracted script             -> CLEAN

Cleanup: both test sessions destroyed; 0 leftovers from this hour.
Ethan's lab containers untouched.

## Step board
Steps 1,2,3,4,5 DONE. Composite DONE. Race DONE (re-verified this hour).
Gate-swallow DONE. In-band discriminator DONE. Demo lab UNBLOCKED.
Sessions-list endpoint: DONE (this hour).

## NEXT (smallest real item)
The panel lists and stops, but does not auto-refresh while idle — a session
started elsewhere appears only on next action or reload. Optional: poll every
~10s, or add a manual Refresh button. Minor.
