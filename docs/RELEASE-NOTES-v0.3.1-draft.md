# Release notes — AEGIS v0.3.1 (DRAFT — NOT PUBLISHED)

> **Status: DRAFT.** No tag has been created. No GitHub Release exists. Nothing has been pushed beyond
> `main`. This file is text for the operator's review.
>
> **Decision requested from Dad:** cut `v0.3.1`, cut nothing (let this window fold into the next release
> with real behaviour changes), or something else. **My recommendation is to hold, not to cut.** See
> "Why a tag is *not* clearly warranted" below. If you want it cut anyway, say so and I will tag and push
> — the notes below are ready, the only thing missing is your word.

- **Drafted:** 2026-11-06, 22:00 UTC (Friday release run).
- **Window:** `v0.2.0..main` — 28 non-merge commits in the week, 2026-11-01 → 2026-11-06.
- **Base:** `main` at the commit this *would* tag. Measured on 2026-11-06:

  ```
  git describe --tags                → v0.2.0-56-gc80c99d
  git rev-list --count v0.2.0..HEAD  → 56
  git diff --stat v0.2.0..HEAD       → 99 files changed, 5311 insertions(+), 6108 deletions(-)
  ```

  Written as commands on purpose. A hardcoded count drifts every week, and has drifted before.

- **Release state as measured against the live GitHub API on 2026-11-06:** one published release,
  `v0.2.0` (2026-10-25T12:30:44Z). Remote tags: `v0.1.0`, `v0.2.0`. Nothing unpublished, nothing waiting.

## Why a tag is *not* clearly warranted

Under `v0.2.0`'s own standard — this window does **not** meet it:

1. **No shipped behaviour changed.** Every code path a learner or operator runs is byte-identical to
   `v0.2.0`'s. The only additions to `tools/` are claim checkers: local audit tools, not the product.
2. **The removals already happened in the previous window** and are waiting in the still-untagged
   `v0.3.0` draft. This week removed nothing from the tree.
3. **There is already an unreleased window stacked underneath this one.** `docs/RELEASE-NOTES-v0.3.0-draft.md`
   covers the week of 2026-10-30 and its window contains real fixes (`start_server.py` measuring the wrong
   server, the FRR pin). Cut this week as a patch and you would either drop those or brand them `0.3.1`,
   which is a lie about the ordering.

If a tag is cut anyway, `v0.3.1` is the right number and it should be cut **as a documentation release only**,
with this stated in the first paragraph rather than buried.

## Draft body (for the GitHub Release, once approved)

### AEGIS v0.3.1 — week of 2026-11-06

**A documentation release. No shipped behaviour changed.** The only thing added is a way to keep the
documents honest.

Two claim checkers were added to the set that runs against reader-facing docs. They found that two of those
docs had drifted from the tree, and that one of the existing checkers had silently dropped out of the list
of checks anyone ran.

**Added — `tools/check_api_doc.py`.** `docs/API.md` claimed 11 routes, printed a table, and told the
reader to trust `/openapi.json` over itself, with nothing running that recipe. The tool imports
`backend/main.py` and compares the page against `main.app.openapi()`: headline count, one row per operation
in both directions, each row's method, path and parameters, zero request bodies, and that the page still
makes the claims it is checked against. Verified 11/11 claims hold. Ten hand mutations all caught,
including adding a real route to `main.py`. The status-code table, ttyd port range and `/docs` exposure
notes are not carried by the OpenAPI document; the tool prints them as out of scope rather than scoring
them as passes.

**Added — `tools/check_ci_doc.py`.** README, CONTRIBUTING and SECURITY each state in words how many checks
`ci.yml` runs and how many claim checkers it does not. Every one of those numbers was typed by hand, and
two were wrong. The tool parses `ci.yml` and cross-checks the counts, the complement sentences, and
CONTRIBUTING's hand-run block line by line. 17/17 claims hold. It reads the workflow; it does not run it,
and does not claim CI passed.

**Fixed — CONTRIBUTING's step numbering contradicted itself, and a checker had silently dropped out of it.**
A checker that is no longer in the hand-run block is a checker nobody runs. Corrected, and held by the new
checker: four step citations verified against the block.

**Fixed — the "not yet in CI" notes now say what actually blocks them: the write, not the step.** The
workflow patch (Python 3.10 floor plus seven steps) applies cleanly and is parked at
`.nexus/WORKFLOW-PATCH-2026-11-06-1200.patch`. It cannot be pushed by this repo's automation token, which
is refused on `.github/workflows/` — re-measured 2026-11-03: a root-level `*.yml` on the same branch is
accepted, a workflow path is `404`. It needs a human with `workflow` scope, and it must land together with
the prose, not before it.

**Fixed — docs measured against the tree instead of against memory.** `docs/architecture.md` (grading path
described as three-state, a deleted file out of Components, pin row corrected), `docs/OPERATIONS.md` (now
guarded by `tools/check_operations_doc.py`), and the README's two re-install traps: re-running
`install.sh` nests the app tree, and the SR Linux image is 3.2 GB on disk against 0.75 GB compressed.

**Known, not fixed** — unchanged from `v0.2.0`, carried forward honestly:

- The CI workflow patch is not applied. CI still runs four checks.
- ~~A cold install still serves zero labs unless per-lab assets are placed manually.~~ **Withdrawn
  2026-11-10 as false of this tree.** It was carried forward from before 2026-10-24 and never re-measured.
  `install.sh` has copied each lab's `assets/` and verified every `startup-config:` it names since
  `0c86d13` (2026-10-24). Measured 2026-11-10 by running Step 6's copy block against a clean tree and
  then loading the result with the real `_reload_labs()`: both shipping labs load, none rejected. The
  limitation that *is* real is narrower and is in the README: a clone that never had the asset files
  cannot be repaired by the installer, which only warns by name.
- ~~The grader default derived from `metadata.id` still does not resolve for at least one lab.~~
  **Withdrawn 2026-11-10 as false of this tree.** Both shipping labs name `grader:` explicitly in their
  YAML (`grader_demo_01_srl`, `grader_demo_02`) and both resolve through `_load_grader`. What is true is
  the *default*: a lab that omits `grader:` gets `grader_<metadata.id>`, which for a sentence-shaped id
  almost never resolves — still documented in `docs/ADDING-A-LAB.md`. No shipping lab relies on it.

## Verification run before drafting

Measured on the base commit (`c80c99d`), not asserted:

| check | result |
|-------|--------|
| `python3 -m py_compile backend/main.py start_server.py tools/*.py` | OK |
| `bash -n install.sh` | OK |
| `tools/check_*.py` — all nine | rc=0 |
| `tools/check_ci_doc.py` | 17/17 claims hold |
| `patch --dry-run < .nexus/WORKFLOW-PATCH-2026-11-06-1200.patch` | applies cleanly |

Not run this week: any Docker build, and `tools/lint_lab_pack.py` (needs PyYAML; no venv for it this pass).
Both are a *not-run*, not a pass, and neither is claimed here.

### Not published
No tag created, no tag pushed, no GitHub Release. Awaiting Dad's explicit OK.
