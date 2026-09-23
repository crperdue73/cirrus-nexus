# DECISION NEEDED — lab-04 BGP substrate contradiction (1 page)
**From:** Selina 🐧 · **Date:** 2026-09-23 ~13:10 EDT · **Status:** NOT complete; needs Dad's call

## The contradiction
The product currently ships **two truths that disagree**. Reproduced live today
against the running `:8000`:

```
POST /api/sessions/start?lab_id=lab-04-two-as-peering
-> HTTP 409
   "substrate cannot run lab-04-two-as-peering: requires daemons ['bgpd'],
    but aegis/frr:latest enables only ['mgmtd','staticd','vtysh_enable','zebra'].
    Redeploy on a substrate built with those daemons"
```

- **`install.sh` says the BGP substrate was removed.** Line 168:
  `# (Dockerfile.frr-bgp removed 2026-09-20 — that substrate is not part of this product.)`
  and line 379: "Step 7b removed 2026-09-20 — it built a substrate the product does not ship."
- **`backend/main.py` and the pin file still expect one.** main.py lines 103-107,
  321, 859-862, 944 all reference "the BGP variant (bgpd enabled, for lab-04)";
  `assets/installed-image-id.txt` carries a second substrate digest.
- **`lab-04-two-as-peering.yml` requires it** (`requires_daemons: [bgpd]`).

Result: lab-04 **cannot deploy at all**. It is not a grading bug — the substrate
guard is *correctly* refusing a mismatch. The product is internally inconsistent.

## Blast radius (already measured)
- **lab-04 is the ONLY lab that declares `requires_daemons`.** Nothing else needs
  `bgpd`. The other 14 labs are unaffected either way.
- lab-04 is referenced only by its own files (`lab-04-two-as-peering.yml`,
  `grader_lab_04_two_as_peering.py`) plus internal docs (backend, HANDOFF,
  10-archive). **No lab pack manifest lists it**, so neither option churns a pack.

## Option A — RESTORE the BGP substrate (build + re-pin)
Make the product ship what it says it ships.
- I already built and *tested* a staged `Dockerfile.frr-bgp` (bgpd=yes asserted,
  in the same spirit as the base image). It builds; its layer-chain is
  `244c88aa…`.
- Work required: (1) re-add `Dockerfile.frr-bgp` to `install.sh` (undo line 168 /
  Step 7b); (2) build the image; (3) **re-publish the pin file**
  (`assets/installed-image-id.txt`) with the new substrate's real digest
  (`244c88aa…` + tarball ID). Until step 3, the digest-attribution guard refuses
  to start sessions (verified: `500 "Could not resolve runtime digest … refusing
  to start an unattributable session"`).
- Cost: touches install.sh + an asset the installer verifies. **Install-path
  change → your call.** Est. ~20-30 min once approved.
- Pinned 2nd digest `f69c7345…` currently matches **no local image** (its history
  is unknown to me — I inferred it; see my self-audit WISH entry).

## Option B — DROP lab-04 from the product
Accept that the fundamentals substrate is the product, and lab-04 is future work.
- Work required: remove/retire `lab-04-two-as-peering.yml` +
  `grader_lab_04_two_as_peering.py`; drop the "BGP variant" references from
  `backend/main.py` (lines 103-107, 321, 859-862, 944) and the 2nd pin digest.
- Cost: no substrate rebuild, no new asset. But it **deletes a shipped lab** —
  also your call. Est. ~15 min.

## My recommendation
**Option A if labs are meant to include BGP** (the code clearly *intended* it,
and the substrate is already written + tested). **Option B if the product scope is
deliberately fundamentals-only** — then the backend/pin references should be
cleaned so the contradiction stops existing. Either way the fix is one direction:
today the two halves disagree, and guard-correctness means the lab stays dead
until we pick one.

## What I did NOT do
I did not touch `install.sh`, the pin file, or any shipped lab — those are your
call. The staged `Dockerfile.frr-bgp` is in the tree but **NOT wired in**.

— Selina 🐧 (proof: `.nexus/proofs/lab04-bgp-substrate-contradiction-20260923-0725.txt`)
