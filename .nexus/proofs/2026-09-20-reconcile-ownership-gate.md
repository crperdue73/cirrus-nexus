# Proof — Reconcile ownership gate (the app must never claim a lab it did not create)

Date: 2026-09-20 ~14:0x EDT (nexus-hourly-drive)
Driver: Selina
Status: SHIPPED + VERIFIED LIVE

## The defect (found by comparing the ledger to the host, not by trusting either)

The 13:0x startup-reconcile proof states, as an explicit honesty rule:

    "Ethan's own non-sessionized lab (`clab-aegis-two-as-peering-r1..r6`, no
     8-char session id) is correctly NOT adopted — it is his, not a product
     session."

That claim was FALSE against the live host. `GET /api/sessions` this hour
returned, among others:

    d7776359  lab-04-two-as-peering  student_name="(reconciled)"  status=running

`d7776359` is **Ethan's** lab. It appears in the project ledger six times as
"Ethan's d7776359 labs untouched (6 containers Up)". It was hand-deployed from
HIS topology dir (`../workspace-ethan/aegis-topologies/lab-04-two-as-peering.clab.yml`)
on 2026-09-19 22:04.

Why the stated rule failed: his topology is `name: aegis-two-as-peering`, and
containerlab appended a suffix that happened to be 8 lowercase-hex chars
(`d7776359`) — so `_session_id_from_container` parsed it as a session id and the
reconciler adopted it.

Consequences, all real and all bad:
  1. The product claimed ownership of a lab it did not deploy.
  2. It exposed `POST /api/sessions/d7776359/stop` — one API call would have
     DESTROYED ETHAN'S LAB.
  3. Grades could be issued against his containers, attributed to the product.

This is the same class of lie the whole Step 5 invariant exists to prevent,
pointed the other way: the product asserting provenance it does not have.

## Root cause

Ownership was inferred from a container NAME PATTERN (`clab-<topo>-<8hex>-<node>`).
A name is not proof of provenance. Nothing durable recorded who created a
container, so after a restart (`SESSIONS` is in-memory) the reconciler guessed,
and guessed wrong.

## Fix

Stamp durable ownership at container-CREATION time, and gate reconcile on it.

  - `_prepare_topology()` now injects `aegis.session.id` and `aegis.lab.id` into
    every node's `labels:` in the cleaned topology it hands to containerlab.
    Node-level `labels:` in the topology YAML is the ONLY reliable mechanism on
    this daemon: `docker update` here has no `--label-add` (verified:
    `unknown flag: --label-add`, exit 125), and Docker labels are immutable
    after creation.
  - `_running_clab_containers()` now returns `(name, session_label, lab_label)`.
  - `reconcile_sessions()` adopts a container ONLY if `aegis.session.id` is
    present (i.e. WE stamped it). Blank label => not ours => skipped. The
    stamped `aegis.lab.id` is preferred over reverse-mapping the topology name.
  - The now-useless `_stamp_session_labels()` helper was removed.

A lab deployed by a human or another agent is never stamped, so the product can
never adopt, grade, or stop it.

## Verified LIVE (executed against the running app)

BEFORE the fix (same hour, pre-change):
  GET /api/sessions -> includes d7776359 (Ethan's lab) as a product session.

Stamping mechanism (creation-time labels):
  containerlab node `labels:` support confirmed with a throwaway topology
    (clab-lbtest-n1 carried both labels) before wiring it in.
  A product deploy then carried them on every node:
    POST /sessions/start?lab_id=demo-01  -> session ad20ffe4
    clab-aegis-demo-01-...-ad20ffe4-{pc-a,pc-b,switch}
      aegis.session.id = ad20ffe4 ; aegis.lab.id = demo-01-two-pcs-and-a-switch
  Ethan's container, same host, same instant:
    clab-aegis-two-as-peering-d7776359-r1 -> aegis.session.id = <blank>

The decisive test — restart the app (SESSIONS lost), let reconcile run:
    GET /api/sessions -> count 1
      ad20ffe4  demo-01-two-pcs-and-a-switch  aegis-less:4ab4e8d777c32...
      d7776359 adopted? False     <-- Ethan's lab excluded
      ad20ffe4 adopted? True      <-- ours, with its digest

STOP safety:
    POST /api/sessions/d7776359/stop -> HTTP 404
    docker ps | grep -c d7776359     -> 6   (Ethan's lab UNTOUCHED)
    POST /api/sessions/ad20ffe4/stop -> {"status":"destroyed"} -> 0 containers

Regression (substrate path unchanged):
    POST /sessions/start?lab_id=lab-04-two-as-peering -> session 8418e3ea
      runtime_digest = sha256:bb7ef23a... == assets/frr-image.pin layers_sha256 MATCH
      submit?node=r3 -> status=graded score=0.35 digest carried
      container label = 8418e3ea
    stop -> destroyed, 0 leftovers.

Static: py_compile (+ -W error::SyntaxWarning) CLEAN; `bash -n install.sh` CLEAN.

## Migration note (honest)

Containers deployed BEFORE this fix carry no label, so after this change they
are no longer auto-adopted — correct by the new rule (they cannot be proven
ours), but it leaves genuinely-ours pre-fix orphans unaddressable. 24 such
containers were backfilled by hand using evidence OTHER than the name: a session
id with a product runtime dir under `lab-definitions/clab-<topo>-<sid>/` plus a
loadable lab definition. `d7776359` was deliberately EXCLUDED from that backfill
(the ledger names it Ethan's). The backfill is a one-time migration, not part of
the product.

## Not touched
Ethan's `clab-aegis-two-as-peering-*` lab — 6 containers, still Up, never
adopted, never stopped.

## Artifact
backend/main.py (ownership stamping in `_prepare_topology`; ownership gate in
`reconcile_sessions`/`_running_clab_containers`; dead helper removed).
