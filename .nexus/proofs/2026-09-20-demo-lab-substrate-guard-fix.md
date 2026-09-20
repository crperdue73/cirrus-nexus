# 2026-09-20 — DEMO LAB UNBLOCKED: provenance-vs-gate conflation fixed

## The defect (reproduced live, before the fix)

Dad's new shipping spec (2026-09-20): a DEMO lab, 2 PCs + a switch, student
assigns IPs + a switch management IP, passes when pc-a can ping BOTH. It was
built and verified by hand last hour, but **could not start through the product**:

    POST /api/sessions/start?lab_id=demo-01-two-pcs-and-a-switch
    => 500 {
         "detail": "Could not resolve runtime digest from running containers;
                    refusing to start an unattributable session"
       }

ROOT CAUSE (backend/main.py): `resolve_runtime_digest` treated "no `aegis/frr`
substrate in the lab" as "unattributable". The demo lab is three `alpine:latest`
nodes — no FRR, no BGP, nothing pinned to verify — so it was refused outright.
The guard conflated **provenance** (which substrate is this?) with **gate**
(may I run this at all?). A lab with no substrate is not unattributable; it is a
legitimately unpinned lab.

## The fix (backend/main.py)

`_resolve_runtime_digest_once` now has three explicit outcomes:

1. **Substrate present, matches install record** -> cite the transport-invariant
   layer-chain `sha256:<...>` (unchanged; step-5 invariant intact).
2. **Substrate present but stale / multiple distinct AEGIS substrates** -> `""`
   hard refuse (unchanged; genuine ambiguity still refuses).
3. **No AEGIS substrate in the lab** -> NEW: attribute honestly as
   `aegis-less:<sha256>`, a deterministic identity over each node's
   `name=layer-chain` pair, read off the RUNNING containers (never a tag, never a
   build log).

`""` is now reserved for a lab whose identity genuinely cannot be read off the
running containers — that still refuses.

Step 5 is preserved: a state is still never cited WITHOUT an identity. The demo
lab gets a *real* identity instead of a blank one; an unresolvable lab still
gets none and still refuses to start.

## Verification (executed)

POSITIVE — demo lab now starts THROUGH the product:
    POST /sessions/start (demo-01) -> session b3bce69f, 3 nodes running
    runtime_digest = aegis-less:4ab4e8d777c320d221509dc1258e9c2b96b7f72b79acdc7f4b560e6e91baa24b
    unconfigured -> pc-a graded, passed=False score=0.0, digest cited
    student config applied (pc-a/b/switch per spec) -> pc-a ping 10.0.1.254 2/2
      and ping 10.0.1.2 2/2, 0% loss
    grade pc-a   -> passed=True score=1.0  digest cited
    grade pc-b   -> passed=True score=0.5  digest cited
    grade switch -> passed=True score=0.5  digest cited

DETERMINISM / REDEPLOY STABILITY:
    stop b3bce69f, redeploy demo-01 -> session 200405b8
    digest = aegis-less:4ab4e8d7...  == the first session  STABLE across redeploy
    (identity keys on node names, so it is stable per lab and changes only if a
     node's image changes.)

REGRESSION — substrate labs unchanged:
    lab-04-two-as-peering -> runtime_digest = sha256:bb7ef23a...  == assets pin  MATCH
    (the pinned-substrate path still cites the installer-verified identity.)

NEGATIVE — genuinely unresolvable still refuses (unit, against the real fn):
    resolve_runtime_digest({"ghost": "does-not-exist-xyz"}) -> ""  (refuse)
    resolve_runtime_digest({})                              -> ""  (refuse)

STATIC: `python3 -m py_compile backend/main.py` CLEAN; `bash -n install.sh` CLEAN.

CLEANUP: all my sessions stopped+destroyed; 0 leftover containers; my stray
demo labs removed. Ethan's lab `clab-aegis-two-as-peering-d7776359-*` untouched
(6 containers still Up).

ARTIFACT: backend/main.py (three-outcome resolver) + the demo lab files now
under version control (lab-definitions/demo-01-two-pcs-and-a-switch.yml,
lab-definitions/grader_demo_01.py).
