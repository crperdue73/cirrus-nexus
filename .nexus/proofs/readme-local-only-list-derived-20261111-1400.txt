2026-11-11 14:00 UTC — check_ci_doc.py: README's local-only list now derived, not hand-kept

MEASURED BEFORE: git clean vs origin/main; check_ci_doc 17/17 rc=0; all 12 tools/check_*.py rc=0; py_compile backend/main.py rc=0; bash -n install.sh rc=0.

DEFECT (live, not hypothesized): README.md's paragraph enumerating the local-only checkers named 10 of the 11 in the tree — it omitted tools/check_repo_metadata.py — while check_ci_doc.py reported 17/17 PASS. Cause: the tool's required-name set was the hand-written LOCAL_ONLY list, which also omitted check_repo_metadata, so the tool compared the prose against the same forgetful hand that wrote it. A name absent from BOTH the list and the README was invisible.

FIX (tool): removed (README, ...) rows from LOCAL_ONLY; added README_LOCAL_ONLY regex anchoring the paragraph ('the ci.yml diff that adds it (and the other local-only claim checkers — ...' through ') is written'), whitespace-tolerant because README is hard-wrapped. New claim 4b derives readme_names from the paragraph and checks BOTH ways vs repo_checkers - ci.yml keys: (a) every non-CI checker named, (b) every named checker exists in tools/, (c) no named checker is one ci.yml runs. A reworded paragraph fails loudly (rc=1, 'paragraph not found') rather than parsing as empty.

FIX (doc): README.md paragraph now names tools/check_repo_metadata.py with its subject (the GitHub-side description, topics and license).

NEGATIVE CONTROLS, run on a scratch copy (/tmp/negctl), each observed to FAIL:
  A drop the check_repo_metadata name -> rc=1 'README omits [check_repo_metadata]'
  B name a nonexistent tools/check_ghost_tool.py -> rc=1 'names checker(s) not in tools/: [check_ghost_tool]'
  C call in-CI check_self_contained local-only -> rc=1 'ci.yml runs them: [check_self_contained]'
  D reword the anchor sentence -> rc=1 'paragraph not found (it was reworded - update this tool)'

AFTER: check_ci_doc.py 18/18 rc=0. All 12 checkers rc=0 (check_api_doc 15/15, check_repo_metadata 27 claims, check_prerequisites 36, check_lab_assets 19, check_self_contained_doc 17, check_operations_doc 62 PASS, check_pyc_staleness 7 PASS). py_compile backend/main.py rc=0, tools/check_ci_doc.py rc=0, bash -n install.sh rc=0.

SCOPE: one tool + one README paragraph. No backend, installer, topology, grader or ci.yml change. README's '4 in CI, 11 run by hand' counts unchanged and still true; README's live-README enumeration now matches the tree. check_repo_metadata.py remains hand-run only (ci.yml patch still blocked on the workflow scope).
