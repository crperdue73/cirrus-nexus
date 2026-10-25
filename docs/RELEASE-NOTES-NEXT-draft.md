# Release notes — AEGIS NEXT (draft)

> **SUPERSEDED on 2026-10-25.** The release was cut and published as **`v0.2.0`**; the shipped notes
> are [`RELEASE-NOTES-v0.2.0.md`](RELEASE-NOTES-v0.2.0.md). This file is kept as the drafting record,
> including the decision it asked for. Where the two disagree, the published notes win.

**Status: DRAFT — superseded.** Published as `v0.2.0` on 2026-10-25 after the operator approved the
cut. `v0.2.0` was the recommended option below (behaviour changed, nothing removed).

- **Drafted:** 2026-10-23, Friday release run.
- **Window:** 2026-10-17 → 2026-10-23 (`git log --since="7 days ago"`), 30 non-merge commits.
- **Base:** `main` at `8ee31c0`.
- **Tag state (measured, not recited):** `git describe --tags` → `v0.1.0-67-g8ee31c0`. The only tag in the
  repo is still `v0.1.0`, cut 2026-10-09. Commit distance is written as a command, not a number, because
  earlier drafts published it and it drifted every week.

## Why a tag is now warranted (unlike the last two weeks)

The last two windows were documentation-only, and the honest call was no tag. **This one is not.** It
contains the first runtime/tooling behaviour changes since `v0.1.0`:

1. `scripts/clab-reaper.sh` — destructive fix (was tearing down live learners' labs by age alone), plus a
   second fix for the "reaped nothing" regression in the same script, plus a shipped cron file.
2. `tools/lint_lab_pack.py` — false `ERROR` output when the check had not run.
3. `lab-definitions/srl-demo2-unsolved/demo-02-...yml` — a shipped lab's prerequisite pointed at an id
   that does not exist in the tree.

A learner or operator can hit all three. That is a product change, and a tag should mark it.

**Decision requested from Dad:** `v0.2.0` (recommended — behaviour changed, nothing removed) vs `v0.1.1`.
I have not created either. Say the word and I cut the annotated tag, push it, and confirm here.

---

## Draft body (for the GitHub Release, once approved)

### AEGIS — unreleased rollup, week of 2026-10-23

**Fixed — a reaper that could kill a live lab.** `scripts/clab-reaper.sh` selected containers by age
alone, so a `clab-*` container an active learner was still working in was torn down the moment it crossed
the threshold. It now checks the AEGIS session record / `aegis.session.id` label before removing
anything, and its `--orphans` default refuses instead of guessing: exit 3 if the app is unreadable, exit 4
if a container cannot be attributed. A companion `scripts/clab-reaper.cron` is included.

**Fixed — the reaper's follow-up bug.** After the guard landed, a `python -c` one-liner read its input as
a filename, so every run silently saw "no sessions". Corrected; the reaper now reads the session list and
acts on it.

**Fixed — `lint_lab_pack` no longer lies about failures.** A tool that could not run printed one `ERROR`
per lab, which reads as a lab failure. It now reports the check as not-run, and `CONTRIBUTING.md` shows
the output a contributor will actually see.

**Fixed — Demo 2's prerequisite.** It linked to a Demo 1 id that is not in the repo. It now names
`demo-01-two-pcs-and-a-real-switch-unsolved`.

**Documentation.** The honesty sweep continues: README (lab-guide button response type, real version
string, install script's per-lab asset behaviour, rendered architecture diagram), `SECURITY.md`,
`CONTRIBUTING.md`, `.gitattributes` (LF/binaries pinned), and the internal worklog relabelled as internal
where it had been presented as public docs.

**Still open, same as last week:** cold-install serves zero labs unless per-lab assets are placed
manually (`install.sh` does not copy them). Documented, not fixed. Not claimed as solved here.

### Not published
No GitHub Release exists or has been created. No tag pushed. This is text for review.
