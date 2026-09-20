# Proof — Lab-04 REAL competency grader written + verified (closes the named remaining item)

Date: 2026-09-20 ~05:0x–05:3x EDT (hour 05:00 nexus cron)
Driver: Selina
Status: SHIPPED — lab-04 now grades with a real module, not the fallback.

## Why this hour
STATUS.md (03:0x and 04:0x) named the ONE remaining real product item, distinct
from the exit bar:

    "lab-04 real competency grader module does not exist (fallback grades today)."

The exit bar was already met 3x. This hour produced the missing artifact rather
than re-reproducing the bar a 4th time.

## Artifact
`lab-definitions/grader_lab_04_two_as_peering.py` (NEW, ~8 KB)

The lab definition (`lab-04-two-as-peering.md`) declares
`grader: grader_lab_04_two_as_peering`. The module did not exist, so
`_load_grader()` returned None and every lab-04 grade came from
`_fallback_grade()` (a generic "count non-loopback IPs" check that says nothing
about BGP, AS path, or origination — none of the lab's three competencies).

The new module implements the lab's three stated competencies against the
SUBSTRATE THAT ACTUALLY EXISTS.

## Substrate honesty (this is the crux)
`Dockerfile.frr` installs FRR with zebra + staticd ONLY — the file says in
plain English: "No ospfd. No bgpd." So `show ip bgp` is ALWAYS empty on this
image, by design. Grading a live BGP table would be grading an unmeasurable
thing — fake green. The module therefore measures the substrate-observable
invariants the lab is actually about:

  - BGP Peering      -> the r3<->r4 edge link is up and bidirectionally reachable
  - AS Path Reasoning-> an interior router reaches its own AS edge across in-AS links
  - Origin Attribution-> the AS's own prefix is carried on lab interfaces
  - THE TRAP         -> the OTHER AS's prefix must NOT be carried here
                        ("Established is not a measurement" — the lab tip)

The docstring records that this module must be upgraded to read `show ip bgp`
if/when the image gains bgpd. Disclosed, not hidden.

## The bug I found in my own first cut (and fixed)
First version used `ip route get <prefix>` to test reachability. Containerlab
attaches every node to a management network with a DEFAULT route
(`default via 172.20.20.1 dev eth0`), so `ip route get` resolved the other AS's
prefix on a completely unconfigured router.

    LIVE, corrected-by-hand evidence (r3, unconfigured, 6ba5d53a):
      ip route  -> default via 172.20.20.1 dev eth0 ; 172.20.20.0/24 dev eth0
      ip route get 10.20.20.1 -> via 172.20.20.1 dev eth0   (the OTHER AS prefix!)
      ip route get 10.10.10.1 -> via 172.20.20.1 dev eth0   (its OWN prefix!)

=> my grader reported a LEAK on an empty lab AND reported "own prefix resolves"
   as a pass. Both wrong; both reproduced live before the fix.

Fix: reachability is now computed from the real FIB, counting ONLY routes on
lab interfaces (`dev eth1|eth2`), never the mgmt default. Verified below.

Second bug found: r1 scored exactly 0.70 and would have PASSED while its own-AS
edge path was down — the leak-clearance bonus (0.35) masked a failed essential
check. Fixed with an `essential_ok` flag: a failed essential check blocks a pass
regardless of accumulated score. Correctness over accumulation.

## Verification (executed, both directions, live)
Deployed a throwaway session via the PRODUCT's own path (NOT Ethan's labs):

    POST /api/sessions/start?lab_id=lab-04-two-as-peering  -> session 6ba5d53a
      r1..r6 running; session digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c

Every grade below carries `runtime_digest = sha256:bb7ef23a...` (== the pin).

  UNCONFIGURED (as shipped — no addresses on eth1/eth2):
    r3 -> score 0.35  passed FALSE
      "Peering link unconfigured: no IP on r3 eth2 and r4 eth2"
      no false LEAK, no false "own prefix resolves"          PASS (correct refusal)

  CORRECTLY CONFIGURED (addresses + routes put on my own throwaway session):
    r3 -> score 1.00  passed TRUE   (link up / own prefix / no leak)   PASS
    r5 -> score 1.00  passed TRUE                                       PASS

  LEAK INJECTED (r3 given a real route to the OTHER AS prefix 10.20.20.0/24):
    r3 -> score 0.30  passed FALSE
      "❌ LEAK: r3 (AS 65001) can reach 10.20.20.0/24 ... 'Established' is not
       a measurement."                                                  PASS (caught)

  ESSENTIAL-FAILURE NO LONGER MASKED:
    r1 -> score 0.70  passed FALSE  ("cannot reach its own AS edge r3")
    r6 -> score 0.70  passed FALSE  ("cannot reach its own AS edge r4")
      -> the false pass is gone; score alone can no longer green-light it.

`python3 -m py_compile` clean; `/api/labs/reload` picked the module up; the app
loads it from `LABS_DIR/grader_lab_04_two_as_peering.py` (the loader's first
search path) — confirmed by the distinct grader feedback replacing the fallback's
"N non-loopback IPs" line.

## Cleanup
    POST /api/sessions/6ba5d53a/stop -> {"status":"destroyed"}
    Verified after: no 6ba5d53a containers remain.
    Ethan's labs UNTOUCHED and still Up:
      clab-aegis-two-as-peering-d7776359-r1..r6   (his own session)
      clab-aegis-two-as-peering-r1..r6            (his bare set)

## STEP BOARD
1,2,3,4,5 DONE. Composite DONE. First-grade race DONE. Gate-swallow fix DONE.
Exit bar reproduced 3x. lab-04 real grader SHIPPED (this hour).

REMAINING (real product work, NOT exit-bar blockers):
  - other labs referenced by .md but with no module (scan: lab-01, lab-2,
    lab-3 have .md guides; confirm each declared `grader:` resolves).
  - optional GraderResult refused/error discriminator (flagged 02:0x).

Not touched: ethan's lab containers.
