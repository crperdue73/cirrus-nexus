README badge block held by a checker — 2026-11-19 11:06Z

PROBLEM: README lines 3-9 ship seven badges. Six state checkable facts (release = v0.2.0;
release notes v0.3.0 draft,unpublished; python 3.10+; powered by containerlab; API FastAPI;
CI workflow path; license Apache-2.0). Nothing in tools/ read them. check_repo_metadata.py
covers GitHub's description/topics/license, which start at the landing page, not the README.
So a future tag v0.3.0 would have left 'status: v0.2.0' green forever.

NEW: tools/check_readme_badges.py — 7 claims, 0/1/2 exit codes like its neighbours.

TREE SIDE (real repo): rc=0, 'every badge still holds (7 badges read)'

WITNESS — 8 mutated copies under /tmp/bw2 (control C = untouched):

--- C rc=0
    OK: every badge still holds (7 badges read)

--- S1 rc=1
    FAIL: README: status badge says v0.1.0 is the release, but the newest tag here is v0.2.0 — a tag was cut and the badge was not updated

--- S2 rc=1
    FAIL: README: status badge says v0.2.0 is the release, but the newest tag here is v0.3.0 — a tag was cut and the badge was not updated
    FAIL: README: badge says v0.3.0 is unpublished, but v0.3.0 is a tag in this tree — publishing it means fixing this badge and the Release status section together

--- S3 rc=1
    FAIL: README: badge says the v0.3.0 notes are a draft, but docs/RELEASE-NOTES-v0.3.0-draft.md is not in this tree

--- S4 rc=1
    FAIL: README: no 'API: FastAPI' badge found

--- S5 rc=1
    FAIL: README: CI badge points at .github/workflows/nope.yml, which is not in this tree

--- S6 rc=1
    FAIL: README: python badge says 3.13+, but the tree's floor was recorded as 3.10 on 2026-11-16 — re-measure the floor before changing this badge

--- S7 rc=1
    FAIL: README: no 'Apache 2.0' license badge found

--- S8 rc=1
    FAIL: README: status badge names a release, but git could not list this tree's tags — the badge is unverified (run this from a git checkout with a readable tag list)

S8 has .git removed: git refuses -> rc=1, not a silent OK. That hole was found by writing
this witness: the first version caught git's failure and returned an empty tag list, so a stale
status badge in a /tmp copy passed rc=0. tags() now treats any non-zero git exit as None and
claim 1 fails closed.

ALSO: check_ci_doc.py gained LOCAL_ONLY entries + NUMBER_WORDS sixteen/seventeen; SECURITY.md
16->17, README CONTRIBUTING row 16->17, CONTRIBUTING line 13 16->17, both enumerations name
check_readme_badges, CONTRIBUTING step block gained line 20 and 'steps 4-18' -> '4-20'.

AFTER: all 18 tools/check_*.py rc=0; py_compile rc=0; bash -n install.sh rc=0.
