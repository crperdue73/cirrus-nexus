# Proof — BGP SUBSTRATE: lab-04 deployable instead of correctly-refused

Date: 2026-09-20 ~19:0x EDT (hour 19:00 nexus cron)
Driver: Selina
Status: STEP DONE — the named NEXT item from the 18:0x close is closed.

## The concrete item
Last hour closed the Dockerfile daemon assert and named the next smallest real
item: "ship a SECOND image tag with bgpd enabled so BGP labs (lab-04) become
deployable rather than correctly refused."

Before this hour: lab-04-two-as-peering requires `bgpd`, and the pinned base
substrate ships `bgpd=no`, so the capability gate refused it — HTTP 409, zero
containers. The refusal was CORRECT (a lab on a substrate that can only grade it
red forever is worse than a refusal). But "correctly refused" is not "shippable":
a competency-labelled BGP course could never run.

## What was built

**1. New substrate: `aegis/frr-bgp:latest`** (Dockerfile.frr-bgp)
   FROM aegis/frr:latest, one layer added. Reuses the base layers byte-for-byte.
   Enables bgpd, keeps ospfd disabled, then ASSERTS the state and fails the build
   if wrong (same discipline as the base image).

   Build log: "FRR daemon state asserted: bgpd=yes ospfd=no (zebra+staticd always-on)" EXIT=0
   Verified by RUNNING it (not the log):
     docker run --rm --entrypoint cat aegis/frr-bgp:latest /etc/frr/daemons
       -> bgpd=yes / ospfd=no
     base for comparison: bgpd=no / ospfd=no

**2. Capability gate now reads the LAB's substrate, not a global default**
   backend/main.py:
     - LabDef.substrate_image (new) — derived per-lab from the topology's node
       images (`_substrate_image_for`). The topology is the source of truth.
     - `_substrate_daemons(image=None)` — parameterised; None = pinned base.
     - `_capability_refusal` reads `lab.substrate_image`, so capability and
       deployability can never disagree (that disagreement WAS the bug).
   lab-04's topology nodes now name `aegis/frr-bgp:latest`.

**3. Multi-substrate pin**
   The app refuses to cite a digest it did not install. With two substrates there
   are two legitimate install-verified digests, so:
     - install.sh now builds/loads `aegis/frr-bgp:latest` (with the same
       fingerprint-rebuild gate as the base) IN ADDITION to the base, and the
       install record gains `installed_substrate_digests=` (space-separated set).
     - `_pinned_substrate_digests(pin)` returns that set, folding in the legacy
       single `installed_layers_sha256` for backward compatibility.
     - The resolver accepts a grade on ANY published substrate digest.

## VERIFIED LIVE (no hand steps in the deploy path)
    POST /api/sessions/start?lab_id=lab-04-two-as-peering&student_name=Selina
      -> HTTP 200 (was HTTP 409 refusal), session 2e734c97, r1..r6 all running
      -> runtime_digest = sha256:f69c7345c8c520ff8bfec7702e9d1cd2bef0fb56ecc68e6d17e1a5aef7432ca5
      -> lab.substrate_image = aegis/frr-bgp:latest

    bgpd REALLY running in the deployed node (not just enabled on paper):
      docker exec ...-r3 ps aux -> /usr/lib/frr/bgpd -d -F traditional
                                   watchfrr -d mgmtd zebra bgpd staticd

    POST /api/sessions/2e734c97/submit?node=r3
      -> status "graded" (not refused), passed=false score=0.35
      -> runtime_digest = sha256:f69c7345...   == the BGP substrate. CITED.

    Digest cross-check (read off the RUNNING container, not a build log):
      container .Image            -> sha256:dd00514409df...
      layers of that image, sha256 over the ordered layer list, printf '%s'
        (NO trailing newline)     -> f69c7345...  == app-reported digest  MATCH

## Honest note (a trap I fell into, then caught)
My first cross-check piped the layer list through `sha256sum` WITH a trailing
newline and got 77d3e654... ≠ f69c7345.... That is the SAME trailing-newline
artifact install.sh already documents and fixes (see its "recorded f7a7f293 vs
verified bb7ef23a" note): a pipeline newline makes the same image hash two ways.
The product path uses `printf '%s'` (no newline) and is self-consistent — the
mismatch was in my ad-hoc shell, not in main.py. Flagged so the next reader does
not "fix" a non-bug.

## Hygiene
  Test session 2e734c97 stopped -> destroyed. Leftover containers matching it: 0.
  Ethan's labs: 26 containers, all untouched.
  bash -n install.sh CLEAN; py_compile backend/main.py CLEAN.

## Artifacts
  Dockerfile.frr-bgp                              (new substrate)
  backend/main.py                                 (per-lab substrate + multi-pin)
  install.sh                                      (Step 7b + install record set)
  lab-definitions/lab-04-two-as-peering.yml       (nodes -> aegis/frr-bgp:latest)
  .nexus/proofs/2026-09-20-bgp-substrate.md       (this file)

## STEP BOARD
  exit-bar steps 1-5, composite cold-host, build-gate fix, Dockerfile daemon
  assert — ALL DONE (prior hours).
  BGP substrate (this hour): lab-04 now DEPLOYABLE, GRADES, CITES its digest.

## NEXT (smallest real item)
  lab-04's `requires_daemons: [bgpd]` is now satisfied by a substrate that was
  built and recorded this hour, but the BGP substrate has NOT been exercised on a
  COLD HOST end-to-end (install.sh Step 7b writing the multi-digest record from
  scratch). Rehearse the composite again with BOTH substrates and confirm a
  fresh host lands both digests and grades lab-04 with no hand steps.
