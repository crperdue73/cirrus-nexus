# Proof — Startup session reconciliation (product sees the host's reality)

Date: 2026-09-20 ~13:0x EDT (nexus-hourly-drive)
Driver: Selina
Status: SHIPPED + VERIFIED LIVE

## Why (the earliest genuinely un-done item)
Every exit-bar step (1-5) and the composite cold-host rehearsal were already
closed and re-verified. This hour I looked for the next REAL defect in a
*deployed* product, and found it by looking at the host, not the ledger.

The host had 40 running `clab-*` containers across 12 distinct session ids, but
the app reported:

    GET /api/sessions -> {"sessions":[],"count":0}

`SESSIONS` is an in-memory dict (backend/main.py:44). Nothing reconciled it on
startup. So after any crash, restart, or unit reload, the product FORGOT every
lab it had deployed while the containers kept running and consuming the host.
Consequences, all real:
  - the product's view (0 sessions) diverged from the host's actual state
  - every orphan was UNADDRESSABLE: no id known -> could not be listed, graded,
    or stopped through the API. Reclaiming the host required manual `docker`
    surgery.
  - it leaks forever: each restart strands another generation of containers.

## Change (backend/main.py)
Added startup reconciliation — `reconcile_sessions()` + an `@app.on_event("startup")`
hook:

  - `_running_clab_containers()`: `docker ps` -> names starting with `clab-`.
  - `_session_id_from_container(name)`: pulls the 8-char lowercase-hex session id
    out of `clab-<topo>-<sid>-<node>` (scan for the last 8-hex segment, so
    topologies whose base name contains hex-looking text still parse).
  - `reconcile_sessions()`: groups containers by session id, maps the base
    topology name back to a discovered lab id (via `LABS`), and rebuilds each
    session EXACTLY as `start_lab` does — INCLUDING resolving the runtime digest
    off the RUNNING containers. So the Step 5 invariant survives the reconcile:
    a reconciled session still cannot be cited without its digest.

Honesty rules kept:
  - A session whose digest cannot be resolved is adopted with runtime_digest=""
    (visible + stoppable, but refuses to grade) — NOT silently given a fake one.
  - A topology that no longer maps to a lab definition is still adopted under
    its base name so it is addressable/stoppable (the lab was renamed/removed;
    the containers are still real).
  - Ethan's own non-sessionized lab (`clab-aegis-two-as-peering-r1..r6`, no
    8-char session id) is correctly NOT adopted — it is his, not a product
    session.

## Verification (executed live)

Before (repo's running backend, pid 94409):     /api/sessions -> count 0
After (restarted with the hook):                /api/sessions -> count 11

Adopted, each with a real digest read off its running containers:
    cab1322b  demo-01-two-pcs-and-a-switch  aegis-less:4ab4e8d777c32...
    10ec6f34  tier-02-router-basics         sha256:bb7ef23a07dcb6...
    68831522  tier-02-router-basics         sha256:bb7ef23a...
    da817081  tier-02-router-basics         sha256:bb7ef23a...
    f4fd846e  tier-02-router-basics         sha256:bb7ef23a...
    f9e33ea0  tier-02-router-basics         sha256:bb7ef23a...
    0b3acd37  neteng-capstone               sha256:bb7ef23a...
    06b46fdb  neteng-capstone               sha256:bb7ef23a...
    4cf7bf02  neteng-capstone               sha256:bb7ef23a...
    e885b408  tier-01-foundation            aegis-less:4ab4e8d7...
    d7776359  lab-04-two-as-peering         sha256:bb7ef23a...

Addressable end-to-end (this is the point of the fix):

  GRADE a reconciled FRR session:
    POST /api/sessions/f9e33ea0/submit?node=r1
      -> status=graded  score=0.35
         runtime_digest=sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c

  GRADE a reconciled substrate-less session:
    POST /api/sessions/cab1322b/submit?node=pc-a
      -> status=graded  passed=True score=1.0
         runtime_digest=aegis-less:4ab4e8d777c320d221509dc1258e9c2b96b7f72b79acdc7f4b560e6e91baa24b

  STOP a reconciled orphan (reclaim the host through the API):
    POST /api/sessions/f9e33ea0/stop -> {"status":"destroyed"}
    docker ps | grep f9e33ea0 -> GONE
    /api/sessions -> count 10 (dropped from 11)

Each grade cites its OWN session's digest — Step 5 holds through the reconcile.

## Artifact
backend/main.py (edited on disk; `py_compile` clean). One new function group +
startup hook. No other files touched.
Backup of prior revision: backend/main.py.bak-1302

## Not touched
Ethan's `clab-aegis-two-as-peering-*` (non-sessionized) lab — left running,
never adopted.

## NEXT (smallest real item)
Refresh `.nexus/STATUS.md` and commit this revision — the ledger still shows the
2026-09-19 frontier and predates today's ships (sessions endpoint, reconcile).
Then: the only disclosed restraint on the exit bar remains the nested-docker
`vfs` harness constraint (already named honestly in the composite proof) — the
cold-host install itself landed the current digest on bare debian:12.
