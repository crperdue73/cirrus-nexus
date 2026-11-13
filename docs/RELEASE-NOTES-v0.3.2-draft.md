# Release notes — AEGIS v0.3.2 (DRAFT — NOT PUBLISHED)

> **Status: DRAFT.** No tag has been created. No GitHub Release exists. Nothing has been pushed beyond
> `main`. This file is text for the operator's review.
>
> **Decision requested from Dad:** cut `v0.3.2`, cut something else (see the stacked-windows problem
> below), or cut nothing. **My recommendation is still to hold** — but this week is a closer call than
> the last two, because the linter's *verdicts* changed, not just its prose.
> If you want a tag cut, say so and I will tag and push; the notes below are ready.

- **Drafted:** 2026-11-13, 22:00 UTC (Friday release run).
- **Window:** `v0.2.0..main` — 32 non-merge commits, 2026-11-07 → 2026-11-13.
- **Base:** `main` at the commit this *would* tag. Measured on 2026-11-13:

  ```
  git describe --tags                     → v0.2.0-88-g8a4120c
  git rev-list --count v0.2.0..HEAD       → 88
  git diff --stat 110b4ec..HEAD           → 57 files changed, 4666 insertions(+), 141 deletions(-)
  python3 tools/lint_lab_pack.py          → rc=0   (both labs UNSOLVED, 0 solved)
  ```

  Written as commands on purpose. A hardcoded count drifts every week, and has drifted before.

- **Release state:** local tags `v0.1.0`, `v0.2.0` only. `v0.2.0` remains the sole published release.

## The stacking problem (read this before deciding)

There are now **two unreleased windows underneath this one**:

| Window | Draft | Content |
|---|---|---|
| week of 2026-10-30 | `docs/RELEASE-NOTES-v0.3.0-draft.md` | removes files from the tree; **contains real fixes** (`start_server.py` measuring the wrong server, the FRR pin) |
| week of 2026-11-06 | `docs/RELEASE-NOTES-v0.3.1-draft.md` | documentation only |
| week of 2026-11-13 | this file | linter verdict fixes |

Cutting `v0.3.2` now tags *this* week while three windows' worth of commits sit unterminated. Either the
older windows get their own tags first (clean history, more tags than Dad may want), or one tag covers
all three (fewer tags, but the version number stops meaning "one week"). **I am not making that call.**

## What changed this week

**No learner-facing behaviour changed.** The product code paths are untouched. What changed is
`tools/lint_lab_pack.py` — a local audit tool — and it changed in the direction of *admitting less*:

1. **An unclassifiable lab exited 0.** Fixed. It now fails.
2. **A grader that raised on import read as `NO-GRADER`, rc 0.** Fixed. A crash was wearing the costume
   of a benign verdict.
3. **`NO-TOPOLOGY` was reported as `UNSOLVED`.** Fixed. Unreadable is not the same claim as unsolved,
   and the tool should not assert the stronger one.

Everything else is what the last two weeks have been about: documentation measured against the tree,
and checkers added so it stays measured. 14 `check_*.py` tools exist; the ones not in CI are named in the
README rather than implied.

## Draft body (for the GitHub Release, once approved)

### AEGIS v0.3.2 — week of 2026-11-13

**An audit-tool release. No change to either lab, the loader, the grader path, or the API.**

The lab linter stopped giving confident answers it had not earned. Three verdicts were wrong in the
most dangerous direction — saying "fine" when the tool had actually failed to look:

- A lab the linter could not classify was reported as passing. It now reports the failure.
- A grader that raised on import was read as "this lab has no grader" and exited 0. A crash is not an
  absence.
- A lab whose topology could not be read was reported as `UNSOLVED` — asserting the learner hadn't
  solved it. `NO-TOPOLOGY` is now its own verdict.

Alongside that, the week's documentation corrections: the OpenAPI document does not carry response
schemas and the README said it did; `SELF-CONTAINED.md` said its checker pins 16 claims when it pins 19,
and the count is now derived rather than typed; the "non-colliding ttyd ports" claim is scoped to what
the allocator can actually see. The journald claim was false — the journal is empty, the log is
`/var/log/aegis.log` — and the checker now reads the unit instead of the sentence.

Two things are measured and **deliberately not fixed**, because they are behaviour calls, not bugs to
change quietly: `install.sh`'s Step 6 re-install nests the app tree (not idempotent), and a
topology-as-list crashes lab reload. Repro for the second is in the tree.

Still blocked on a human: the CI workflow patch. This token is refused on `.github/workflows/`, so what
CI runs today is unchanged. Write ≠ step.

**Known limitation:** nothing here is a learner-visible improvement. If you are installing AEGIS for the
labs, v0.2.0 and this are the same product.
