# 2026-09-20 06:0x EDT — Grader dispatch verified + exit bar re-verified (4th independent run)

Hour: NEXUS-HOURLY-DRIVE. Did NOT add features. Verified claims by execution per
cron RULES. Closed the one real product item STATUS.md named outstanding
("audit remaining labs whose declared `grader:` may not resolve").

## 1. Declared-grader audit — 8/8 RESOLVE (executed)

Parsed `metadata.grader` from every lab-definition and loaded each through the
**app's own loader path** (`LABS_DIR/<module>.py`, exactly as
`backend/main.py::_load_grader` does), then asserted a callable `grade`:

    lab file                        grader module                    result
    01-foundation.yml               grader_tier01                    IMPORT OK
    02-router-basics.yml            grader_tier02_router_basics      IMPORT OK
    03-crossing-subnets.yml         grader_tier02_crossing           IMPORT OK
    04-switch-in-the-middle.yml     grader_lab_02_switch_in_the_middle IMPORT OK
    05-router-switch-pc.yml         grader_tier03_switch             IMPORT OK
    06-lock-it-down.yml             grader_lab_03_lock_it_down       IMPORT OK
    07-capstone.yml                 grader_neteng_capstone           IMPORT OK
    lab-04-two-as-peering.yml       grader_lab_04_two_as_peering     IMPORT OK

    RESOLVABLE: 8/8   PROBLEMS: none

Note: `metadata.grader` is nested under `metadata:`, not top-level. A naive
top-level lookup reports all 8 as "none declared" — recorded so this is not
mistaken for a missing grader.
Benign: grader_neteng_capstone.py emits a SyntaxWarning (invalid escape `\s` at
line 201). Import still succeeds; cosmetic.

## 2. Lab-04 REAL grader actually DISPATCHES (not the fallback) — LIVE

Every prior entry asserted the lab-04 grader was "shipped". This hour proved it
is the module the app USES at grade time, by distinguishing its output from the
generic fallback's.

    session start (product path): POST /api/sessions/start?lab_id=lab-04-two-as-peering
      -> session d17868a6 ; nodes r1..r6 = clab-aegis-two-as-peering-d17868a6-*
    session.runtime_digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c

    FIRST grade (fired immediately, tests the first-grade race fix):
      POST /api/sessions/d17868a6/submit?node=r3
      grade.runtime_digest = sha256:bb7ef23a...   (cites on FIRST read) PASS
      grade.passed = False ; grade.score = 0.35
      feedback:
        "r3 needs work. Score: 35/100 (70 required)"
        "Peering link unconfigured: no IP on r3 eth2 and r4 eth2 ..."
        "r3 cannot resolve 10.10.10.0/24, which AS 65001 must originate ..."
        "No leak: r3 (AS 65001) does NOT carry 10.20.20.0/24. The wrong-session carry test passes."

    DISPATCH PROOF: fallback `_fallback_grade` only counts non-loopback IPs
      (grep -c 'inet '). It has no notion of eth2, AS 65001, prefixes, or the
      leak trap. The feedback above uses lab-04's own vocabulary
      ("wrong-session carry test"), which exists ONLY in
      lab-definitions/grader_lab_04_two_as_peering.py (3 matches for
      LEAK|wrong-session|Established-is-not-a-measurement; 0 in the fallback).
      => the real grader ran.

## 3. Substrate identity — four-way agreement (executed)

    session d17868a6 running containers r1..r6 (docker inspect .Image ->
      image RootFS.Layers -> sha256)            = bb7ef23a...  (6/6 identical)
    first-grade runtime_digest                   = bb7ef23a...
    assets/frr-image.pin layers_sha256           = bb7ef23a...
    install.sh gate Dockerfile fingerprint label = cce15a86... == on-disk
                                                   Dockerfile.frr sha256

    Transient-daemon-local `.Image` id (acb8d8dc...) correctly NOT the pin key.

## 4. Static integrity

    python3 -m py_compile backend/main.py   -> clean
    bash -n install.sh                      -> clean
    install.sh gate (L255-284) keys on Dockerfile-SHA LABEL, not tag presence.

## 5. Cleanup / non-interference

    session d17868a6 -> stop -> {"status":"destroyed"}; 0 of its containers remain.
    Ethan's lab clab-aegis-two-as-peering-d7776359-r1..r6 -> still Up (8h). Untouched.

## ARTIFACT
This file. No product code changed this hour.

## STEP BOARD
1,2,3,4,5 DONE. Composite DONE. First-grade race DONE. Gate-swallow fix DONE.
Exit bar re-verified this hour (4th independent run). Grader-dispatch audit DONE.

REMAINING open product work (NOT exit-bar blockers):
  - optional GraderResult refused/error in-band discriminator (flagged 02:0x).
  - grader_neteng_capstone.py SyntaxWarning (cosmetic).

EXIT BAR: cold-host install.sh lands the current digest (DONE, bare-metal run
2026-09-19), prototype running against a real topology (DONE, this hour),
digest pasted and recorded (DONE above), state cannot be cited without its
digest (first grade carried it). => cron RETIREABLE by the stated definition.
