# Proof — SUBSTRATE CAPABILITY GATE (steps 3+5 hardening)

Date: 2026-09-20 ~17:0x–17:2x EDT (hour 17:00 nexus cron)
Driver: Selina
Status: DONE — artifact is backend/main.py + lab-definitions/lab-04-two-as-peering.yml

## Where this came from (not invented — handed to me)

Ethan answered the step-3 ask (sessions_send agent:ethan:main). His read-only
default was correct and his caveat was the lead:

> "`bgpd=no` ships in the image — **no BGP on this lab.** Verified substrate-wide
> again. If the app grades routing or peering against it, **the red is the
> image**, not her app and not my lab."

He offered his own running lab (clab-aegis-two-as-peering, 6 routers, `aegis/frr:latest`,
24h uptime) as a READ target — explicitly NOT a sessions/start target, because a
start would redeploy/destroy his only running lab on current substrate. I took
the read target and verified his caveat independently instead of trusting it.

## Independent verification of Ethan's caveat

Read off HIS running containers (docker inspect, no deploy, nothing touched):

    clab-aegis-two-as-peering-r1  .Image=sha256:acb8d8dcd72a44c3389184bc168ee61444072566afaa59704eb1aa27250027b8
    clab-aegis-two-as-peering-r6  .Image=sha256:acb8d8dcd72a44c3389184bc168ee61444072566afaa59704eb1aa27250027b8

    bgpd running on r1..r6 ?  →  0 0 0 0 0 0   (all six: absent)
    vtysh -c "show bgp summary"  →  "bgpd is not running"

CAVEAT CONFIRMED, substrate-wide, on the operator's own lab.

## What I did NOT trust, and why it mattered

My first cut read `/etc/frr/daemons` and reported the substrate enabled only
`vtysh_enable`. That was WRONG — and the wrongness was instructive:

    /etc/frr/daemons in aegis/frr:latest has NO `zebra=` line and NO `staticd=` line.
    The Dockerfile's sed does `s/zebra=no/zebra=yes/` and `s/staticd=no/staticd=yes/`
    — patterns that DO NOT EXIST in Alpine's file, so they never matched.

    Yet on a live container:  ps aux → watchfrr -d mgmtd zebra staticd
                              zebra PID 30, staticd PID 35  → BOTH RUNNING.

So the sed is a no-op, and watchfrr starts zebra+staticd+mgmtd by default
regardless. A gate that trusted the file alone would UNDER-report capability and
refuse good (static-routing) labs. Fixed by modelling FRR's implicit defaults
(`_FRR_IMPLICIT_ON = {zebra, staticd, mgmtd}`) and stripping `*_options` lines.

Note: the sed being a no-op is benign today (defaults cover it) but is a real
latent bug — if a future Dockerfile wanted e.g. ospfd, the same silent no-match
would leave it off with no error. Recorded in NEXT below.

## The fix (the product change)

A lab now declares the FRR daemons it REQUIRES; the app refuses to deploy onto a
substrate that cannot run them. This is the honest outcome: deploying would put a
lab on a substrate that can only ever grade it red, so every red would be the
substrate's, not the student's.

    LabDef.requires_daemons: list[str]        (new field, default [] = old behaviour)
    _discover_labs: passes metadata.requires_daemons through
    _substrate_daemons(): reads the substrate AS RUN (throwaway container, live file
        + implicit watchfrr defaults). None = unknown, never "capable".
    _capability_refusal(lab): None | reason string. Unknown-capability also refuses.
    CapabilityRefusal(RuntimeError): a refusal, not a fault → HTTP 409.
    deploy_lab(): gate runs FIRST, before any topology is prepared or deployed.
    lab-04-two-as-peering.yml: requires_daemons: [bgpd]

409 (not 500) so it matches the existing digest-refusal wire convention: one
state, one shape. A 500 would have said "server broke"; the truth is "no, and
here is exactly why".

## Verified live (through the running app, :8000, new code)

    TEST 1  lab-04-two-as-peering (requires bgpd; substrate bgpd=no)
      POST /api/sessions/start → HTTP 409
      detail: "substrate cannot run lab-04-two-as-peering: requires daemons
               ['bgpd'], but aegis/frr:latest enables only
               ['mgmtd','staticd','vtysh_enable','zebra']. Redeploy on a
               substrate built with those daemons enabled."
      → No deploy attempted. No container created. Refused up front. ✅

    TEST 2  demo-01-two-pcs-and-a-switch (no daemon requirement)
      POST /api/sessions/start → HTTP 200, session 0b39633f, 3 nodes running
      runtime_digest: aegis-less:4ab4e8d7...  ✅ (non-BGP lab unaffected)

    TEST 3  tier-02-router-basics (FRR, no bgpd requirement)
      POST /api/sessions/start → HTTP 200, session c48855fb, nodes [pc-a, r1]
      runtime_digest: sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
      assets/frr-image.pin layers_sha256: bb7ef23a...  == MATCH  ✅
      → The gate does NOT over-refuse static-routing FRR labs.

    py_compile backend/main.py   CLEAN
    bash -n install.sh           CLEAN

## Cleanup / blast radius

    stop 0b39633f → destroyed ; stop c48855fb → destroyed
    0 leftover proof containers
    Ethan's clab-aegis-two-as-peering-d7776359: all 6 still Up — UNTOUCHED.
      (Read-only inspection only; no sessions/start against his lab, per his ask.)

## Step-board effect

Step 3 (prototype vs. a real topology): already recorded; THIS hour adds the
  missing half — the prototype now correctly REFUSES to run a lab its substrate
  cannot support, verified against Ethan's own topology definition and his own
  running substrate, with his caveat independently reproduced.
Step 5 (no state cited without its digest): unchanged and intact; refusal
  vocabulary now extended to capability, same 409 shape, one value per state.

## NEXT (smallest real item)

1. Turn the Dockerfile sed no-op into a real assertion: after the sed, verify the
   daemon set matches intent and FAIL THE BUILD if a pattern didn't match. That
   is what makes step 1's build gate actually protect capability, not just hashes.
2. Then re-rebuild (step 2) with bgpd enabled on a SECOND image tag so BGP labs
   become deployable at all — currently they are correctly refused, which is
   honest but not finished.
