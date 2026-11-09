Canary pack for tools/lint_lab_pack.py. Not a real lab pack.
Expectations (each file is named <label>__<expected verdict>):
  demo2-shape__UNSOLVED.yml          nothing pre-applied                   -> UNSOLVED
  demo2-shape__PARTIAL.yml           pc-a + router fully pre-applied      -> PARTIAL 3/4
  demo2-shape__SOLVED.yml            every host + router pre-applied      -> SOLVED (RED FLAG)
  fake-switch__SOLVED.yml            as above, but sw1 is kind: linux     -> RED FLAG (fake switch)
  broken-grader__ERROR.yml           grader raises at import              -> ERROR, rc 2
  no-topology__NO-TOPOLOGY.yml       valid metadata, no topology: block   -> NO-TOPOLOGY, rc 2
                                     (added 2026-11-09; used to read UNSOLVED)
Run from the repo root:
  python3 tools/lint_lab_pack.py --labs-dir tools/canaries/lab-pack
Note: an SOLVED canary makes that run exit 1 (red flag) by design -- that is
the tool working. The measurement that matters is the per-lab verdict.
