# Release notes — AEGIS v0.3.0 (DRAFT — NOT PUBLISHED)

> **Status: DRAFT.** No tag has been created. No GitHub Release exists. Nothing has been pushed beyond
> `main`. This file is text for the operator's review.
>
> **Decision requested from Dad:** cut `v0.3.0`, cut `v0.2.1`, or hold. My recommendation is `v0.3.0`
> because this window **removes two things from the tree**, and a patch bump would understate that.
> The removals were his call on 2026-10-30 and both are archived, not destroyed.

- **Drafted:** 2026-10-30, Friday release run.
- **Window:** `v0.2.0..main` — 25 non-merge commits, 2026-10-25 → 2026-10-30.
- **Base:** `main` at the commit this would tag. Measured on 2026-10-30: `git describe --tags` →
  `v0.2.0-25-gf4b148a`. Written as a command on purpose; a hardcoded count drifts every week and has
  drifted before.

## Why a tag is warranted

Not documentation-only. A learner or operator can hit the behaviour changes:

1. `start_server.py` reported a live server as dead and a foreign server as healthy.
2. The FRR pin described a Dockerfile the tree has not contained since 2026-09-20.
3. Two files/directories left the tree. That is a change to what ships, and it must be in a numbered
   release rather than buried in `main`.

## Draft body (for the GitHub Release, once approved)

### AEGIS v0.3.0 — week of 2026-10-30

**Fixed — `start_server.py` measured the wrong server and then reported it as fact.** Readiness probed a
hardcoded `http://localhost:8000/api` while the backend honours `AEGIS_HOST`/`AEGIS_PORT`: a server on
any other port read as "failed to start" while it was running, and some unrelated server on 8000 read as
success. The probe shelled out to `curl`, which `install.sh` never installs — and `curl -s` exits 0
printing nothing when the connection is refused. `pkill` patterns were unescaped. The wrapper now proves
the child process is ours and reports a dead one as dead.

**Fixed — the FRR pin described a file that has not shipped since 2026-09-20.** The pin named
`Dockerfile.frr` as of `2868142`; `0503bc5` the same day rewrote the daemon block because the old `sed`
matched nothing on FRR 10.x (the build asserted nothing and looked configured anyway), and every commit
since has shipped that version. The pin is re-pointed, and the fields that could not be measured —
`image_id`, `layers_sha256`, `tarball_sha256`, `built` — are marked `UNPINNED`. There is no working
Docker daemon on this host and no tarball in any commit, so they are declared unknown rather than
invented.

**Added — a documented API.** `docs/API.md` documents every route; the previous table summarised 11 and
omitted the 422.

**Added — two repo tools.** `tools/check_repo_metadata.py` records and checks the GitHub description,
topics and license against the repo; `tools/plan_status.py` counts the backlog instead of asking a human
to scroll it, and finds the worklog by pattern rather than one hardcoded name.

**Added — `.nexus/proofs/`.** The proof trail behind the grader-default finding ships publicly, with this
box's addresses redacted.

**Removed — `Dockerfile.frr-bgp`.** A second substrate image no code path built: `install.sh` Step 7b was
removed 2026-09-20 and lab-04, its only would-be consumer, is not in this tree. Unreferenced for six
weeks, and falsely described as "kept as static source" in `architecture.md` and `main.py`'s docstring.
Both descriptions are corrected.

**Removed — `lab-definitions-quarantine-2026-09-30/` (46 files).** Archived out of the tree, not
discarded: copied verbatim to `archive/quarantine-aegis-20261030/`, diff-verified identical, then
removed. The loader never read it.

**Documentation.** The honesty sweep continues: the real Python floor (3.10, not 3.9, not 3.8), that CI
never tests that floor, README, `CONTRIBUTING.md`, `docs/ADDING-A-LAB.md`, `docs/OPERATIONS.md`,
`.gitattributes`.

**Still open, not claimed as solved:**
- A cold install serves zero labs unless per-lab assets are placed manually where `install.sh` does not
  reach them.
- The grader default is derived from `metadata.id` and does not resolve for at least one lab.
- CI's Python matrix is written but not pushable as configured.

## Verification run before drafting

Measured on the base commit, not asserted:

| check | result |
|-------|--------|
| `python3 -m py_compile backend/main.py` | OK |
| `python3 -m py_compile start_server.py` | OK |
| `bash -n install.sh` | OK |
| `python3 -m py_compile tools/*.py` | OK |
| `python3 tools/check_self_contained.py` | OK — 15 required files present, 2 linked doc assets present, lab assets + graders resolve, no developer paths leak |

Not run this week: `tools/lint_lab_pack.py` (needs PyYAML; not installed in a venv for this pass) and
any Docker build. Both are a *not-run*, not a pass, and neither is claimed here.

### Not published
No tag created, no tag pushed, no GitHub Release. Awaiting Dad's explicit OK.
