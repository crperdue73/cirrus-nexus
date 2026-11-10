Canary pack for tools/lint_lab_pack.py. Not a real lab pack.
Eight canary labs, each a shape the linter has been wrong about or must not be
wrong about. Each file is named <label>__<EXPECTED VERDICT> and the expected
verdict is what tools/canaries/check_lint_canaries.sh asserts for it:

  demo2-shape__UNSOLVED.yml          nothing pre-applied                   -> UNSOLVED
  demo2-shape__PARTIAL.yml           pc-a + router fully pre-applied      -> PARTIAL (3/4)
  demo2-shape__SOLVED.yml            every host + router pre-applied      -> SOLVED (RED FLAG)
  fake-switch__SOLVED.yml            as above, but sw1 is kind: linux     -> SOLVED (RED FLAG, fake switch)
  broken-grader__ERROR.yml           grader raises at import              -> ERROR
  no-topology__NO-TOPOLOGY.yml       valid metadata, no topology: block   -> NO-TOPOLOGY
  nogr__NO-GRADER.yml                names a grader the pack does not ship -> NO-GRADER
  noexp__NO-EXPECTED.yml             grader ships no EXPECTED map         -> NO-EXPECTED

Added 2026-11-09 (nogr, noexp; commit 0498da2) and 2026-11-08/09 (ERROR,
NO-TOPOLOGY). This list is checked against the pack by tools/check_canary_pack.py
-- a canary missing from here, or a verdict here that disagrees with the file
name, fails that check. That is what makes the list a record rather than a note.

NO-GRADER and NO-EXPECTED say nothing about pre-solved status -- the linter
could not examine those labs, which is not the same as examining them and
finding them clean.

Run from the repo root:
  sh tools/canaries/check_lint_canaries.sh
  python3 tools/lint_lab_pack.py --labs-dir tools/canaries/lab-pack

Note: two SOLVED canaries (one of them the fake switch) make that run exit 1
(red flag) by design -- that is the tool working. The gate reads the per-lab
rows, not the exit code, and the pack's exit code is 2 because it also carries
an ERROR and a NO-TOPOLOGY lab (an unexaminable lab outranks a red flag, see
the ordering note in the tool).
