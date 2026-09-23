# Selina — self-audit of the 2026-09-23 AEGIS drive proofs
# Tag key (Zoe's scheme):
#   HOLDS = I verified it by RUNNING something this drive; evidence is in the file.
#   CLAIM = I assert it, but it is inherited/not re-verified by me this drive.
#   WISH  = aspirational or inferred; no direct evidence; would be wrong to cite.

Proof files audited (all under .nexus/proofs/, live repo; aegis-public mirrors them):
  1. switch-authenticity-tier03-probe-20260923-0130.txt
  2. unsolved-lab-ships-solved-config-20260923-0310.txt
  3. task1-real-switch-reverify-20260923-0410.txt
  4. task2-demo02-capability-probe-20260923-0420.txt
  5. task1-cumulus-reverify-20260923-0510.txt
  6. node-name-drift-scope-20260923-0518.txt
  7. cold-run-7-unknown-graders-20260923-0610.txt
  8. r1-rtr-fix-productpath-verify-20260923-0710.txt
  9. lab04-bgp-substrate-contradiction-20260923-0725.txt
 10. both-asks-reverified-20260923-0820.txt

======================================================================
HEADLINE CLAIMS, TAGGED
======================================================================

[1] "The SR Linux switch (sw1) in demo-01-unsolved is a REAL switch, not a PC."
    HOLDS. Ran `sr_cli show version` -> Chassis Type 7220 IXR-D2L; `show
    interface irb0` -> IRB in BOTH ip-vrf-1 and mac-vrf-1. Re-run twice today
    (0410, 0820). File 10.

[2] "Dad's un-softened pass condition is met: pc-a pings the switch AND PC-B."
    HOLDS. 0% loss both, from pc-a, run live. File 10 (08:20) and file 3 (04:10).
    Explicitly did NOT count PC-to-PC alone.

[3] "The Cumulus lab is also a real switch and also meets the condition."
    HOLDS, WITH A SCOPE NOTE. Ran os-release (Cumulus Linux 4.3.0), vtysh,
    br0 FDB (2 learnt MACs), pc-a pings SVI + PC-B. File 5.
    SCOPE NOTE (honest): this was verified on the SOLVED reference variant
    (demo-01-...-cumulus, PCs pre-configured). There is no UNSOLVED Cumulus
    variant built, so I cannot claim "a student can do it on Cumulus" the way
    I can for SR Linux. That was a CLAIM not yet earned. **CLOSED 2026-09-23 09:15**: built
    demo-01-two-pcs-and-a-real-switch-cumulus-unsolved (PCs unconfigured, same
grader). Cold-fails; after documented student work pc-a pings BOTH the switch
and PC-B, 0% loss; grader 3/3 @ 1.0. See cumulus-unsolved-variant-20260923-0915.txt.
    The claim is now HOLDS.

[4] "The Cumulus grader genuinely refuses a non-Cumulus box (negative control)."
    HOLDS. Removed /etc/os-release + vtysh -> grader flipped to passed=False 0.0;
    restored -> 1.0. That is a real negative control, run live. File 5.

[5] "DEMO LAB 2 (pc-a -> sw1 -> r1 -> sw2 -> pc-b) deploys and grades end to end,
     and the capability-probe answer is YES."
    HOLDS. 5/5 nodes, cold routed path 100% loss, after documented student work
    pc-a reaches sw1 + r1 + pc-b (0% loss), traceroute hop1=r1 hop2=pc-b,
    grader 5/5 @ 1.0. Re-run at 0420 and 0820. Files 4 and 10.

[6] "The switch node-name difference is only cross-lab naming drift, not a defect."
    HOLDS (and it is a CORRECTION of my own earlier overstatement). Checked that
    every lab's .md matches its own YAML. File 6. I tagged my 03:10 wording as
    overstated and downgraded it. Flagging that as a self-caught overclaim, not
    a win.

[7] "None of the 7 previously-unknown graders leak (pre-solved)."
    HOLDS FOR 6 OF 7; the 7th is MOOT. I ran all 7 cold and observed sub-70
    scores with zero student work: tier-02, lab-01, lab-02, lab-03, tier-03,
    neteng-capstone = no leak (HOLDS). lab-04-two-as-peering = cannot deploy at
    all (409), so "does it leak" is moot, not answered. File 7.
    HONEST LIMIT: "ran cold and it scored low" is strong evidence but is not the
    same as proving no input could ever score high. I am claiming "no leak
    OBSERVED", not "leak impossible".

[8] "grader_tier02_crossing could never grade its own router (rtr vs r1)."
    HOLDS. Observed "Unknown node: r1" live; topology ships `r1`, grader
    dispatched on `rtr`. File 7 + fix verified via a fresh backend (:8099) in
    file 8 -> r1 grades (0.2) instead of erroring.
    CLAIM-ADJACENT: "the live :8000 will show the fix after a restart" is a
    CLAIM — I have NOT restarted :8000 (Dad's call), so I have not SEEN the fix
    on :8000. Stated as expectation, not verified.

[9] "lab-04 cannot deploy because install.sh REMOVED the BGP substrate while
     backend/main.py + the pin file still EXPECT one."
    HOLDS, with one WISH-adjacent line removed.
    HOLDS: install.sh line 168 says the BGP substrate was removed; the pin file
    lists two digests; my rebuilt image's layer chain (244c88aa...) is neither
    pinned digest; deploy refused at the digest-attribution guard (verified).
    WISH I am explicitly NOT claiming: I do NOT know that the pinned second
    digest f69c7345... "was a working BGP image on 2026-09-20." I inferred it.
    No local image matches it and I have no build record. That line is a WISH;
    corrected to: "a second digest is published that no local image matches."

[10] The two "asks re-verified" summaries at 0410/0420/0820.
    HOLDS for the specific numbers quoted (each is a live run in that file).

======================================================================
WHAT I AM *NOT* CLAIMING (the important part)
======================================================================
- NOT claiming any of this is COMPLETE. Completion is Dad's call alone.
- NOT claiming "the switch problem is solved" in general — I claim two specific
  labs, with evidence, and a scope limit on the Cumulus one.
- NOT claiming the leak check is exhaustive (see [7]).
- NOT claiming the :8000 fix is live (see [8]).
- NOT claiming a history for the pinned digest (see [9]).

Zoe: if you audit these, [3], [7], [8], and [9] are where the honest edges are.
Tag [3] and the second half of [9] as CLAIM/WISH exactly where I did.
