# Changelog

All notable changes to AEGIS are recorded here. This project ships two labs
(`demo-01-two-pcs-and-a-real-switch-unsolved`, `demo-02-two-switches-one-router-unsolved`).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — week of 2026-10-30

25 non-merge commits on `main` since `v0.2.0` (measure it: `git rev-list --count v0.2.0..HEAD` — a
number written here goes stale, which is why it is also written as a command). Tag state as measured
on 2026-10-30: `git describe --tags` → `v0.2.0-25-gf4b148a`. **No tag was cut and no GitHub Release
was published for this window** — notes are drafted in
[`docs/RELEASE-NOTES-v0.3.0-draft.md`](docs/RELEASE-NOTES-v0.3.0-draft.md) and awaiting the operator's call.

This window **removes files from the tree** (archived first, not discarded) and changes shipped
behaviour, so it is not a patch release if it is released at all.

### Fixed
- **`start_server.py` measured the wrong server and reported the result as fact.** Readiness probed a
  hardcoded `http://localhost:8000/api` while the backend honours `AEGIS_HOST`/`AEGIS_PORT`, so a
  server on any other port read as "failed to start" while it was up, and a foreign server on 8000 read
  as success. The probe also shelled out to `curl`, which `install.sh` never installs, and `curl -s`
  exits 0 printing nothing on a refused connection. `pkill` patterns were unescaped. The child is now
  proven to be ours and a dead one is reported as dead.
- **`install.sh` now says when the FRR pin no longer describes the shipped Dockerfile.** The pin named
  `Dockerfile.frr` as of `2868142` (2026-09-20); that file has not been in the tree since `0503bc5` the
  same day, which rewrote the daemon block because the old `sed` matched nothing on FRR 10.x. The pin
  was stale by one day and one entire class of bug for six weeks. Fields that could not be measured
  (`image_id`, `layers_sha256`, `tarball_sha256`, `built` — no working Docker daemon on this host, no
  tarball in any commit) are marked `UNPINNED` rather than guessed.
- **`install.sh` names the re-pinned Dockerfile that actually ships** (see above); `Dockerfile.frr-bgp`
  is gone from the tree (below).
- **`tools/plan_status.py` finds the worklog by pattern**, not one hardcoded filename.
- **`tools/check_self_contained.py` stopped reporting a doc link as an install failure** — the check's
  two claims (required files present / links resolve) are now reported separately.

### Added
- **`tools/check_repo_metadata.py`** plus `tools/check_repo_metadata.json`: records and checks the
  GitHub description, topics and license against what the repo declares.
- **`tools/plan_status.py`**: counts the backlog instead of requiring a human to scroll it.
- **`docs/API.md`**: the API table summarised 11 routes; every route is now documented, including the
  422 the old table never mentioned.
- **`.nexus/proofs/`**: the proof trail for the grader-default finding ships publicly; this box's
  addresses are redacted from it.

### Removed
- **`Dockerfile.frr-bgp`** — a second substrate image no code path built. `install.sh` Step 7b was
  removed 2026-09-20 (`0583677`) and lab-04, its only would-be consumer, is not in this tree;
  unreferenced for six weeks. Documented as "kept as static source" in `architecture.md` and
  `main.py`'s docstring, which was false and has been corrected.
- **`lab-definitions-quarantine-2026-09-30/`** (46 files) — archived out of the tree, not discarded:
  copied verbatim to `archive/quarantine-aegis-20261030/`, diff-verified identical, then `git rm -r`.
  The loader never read it.

### Documentation
- Real Python floor stated as **3.10**, not 3.9, and not 3.8 before it; README now also says that CI
  never tests that floor.
- README, `CONTRIBUTING.md`, `docs/ADDING-A-LAB.md`, `docs/OPERATIONS.md`, `.gitattributes` swept for
  claims that no longer match the tree.

### Known, not fixed
- **Cold install still serves zero labs unless per-lab assets are placed manually** where `install.sh`
  does not reach them. Documented; not claimed as solved.
- **The grader default is derived from `metadata.id` and does not resolve** for at least one lab;
  recorded in `docs/ADDING-A-LAB.md` and the worklog, with a proof file under `.nexus/proofs/`.
- **CI's Python matrix is written but not pushable** as configured — stated in the repo rather than
  claimed as coverage.

## [v0.2.0] — 2026-10-25

**Shipped.** The tag `v0.2.0` exists on `main` and on `origin`, and a GitHub Release was published from
[`docs/RELEASE-NOTES-v0.2.0.md`](docs/RELEASE-NOTES-v0.2.0.md) on 2026-10-25.

> Correction, recorded because the wrong text sat here for a day: until 2026-10-26 this entry said
> "not yet tagged and not yet published" and claimed `git tag -l` showed only `v0.1.0`. That was
> written before the cut and never refreshed afterwards. Re-measured against the remote rather than the
> local clone — `git ls-remote --tags origin` lists `refs/tags/v0.2.0`, and the GitHub releases API returns it with
> `"draft": false, "prerelease": false, "published_at": "2026-10-25T12:30:44Z"`. The claim in the
> README, `SECURITY.md` and the release notes was right; this file was the one that had gone stale.

Cut as a minor bump because behaviour changed (the reaper in this window can destroy containers); nothing was
removed, and `v0.1.0` was left where it is rather than moved.

Thirty-odd commits since `v0.1.0`. Unlike the two preceding weeks, **this window contains shipped
behaviour**: fixes to tooling/scripts, the installer, and a shipped lab definition. The rest is the
ongoing documentation sweep.

### Fixed
- **`scripts/clab-reaper.sh` destroyed labs a learner was still holding.** The reaper decided by age
  alone: any `clab-*` container older than the threshold was torn down, with no check for a live AEGIS
  session, and that is precisely the container an active learner is sitting in. The reaper now consults
  the app (`aegis.session.id` label / session record) before removing anything, and its `--orphans`
  default refuses rather than guesses — exit 3 on an unreadable app, exit 4 on containers it cannot
  attribute. A cron file (`scripts/clab-reaper.cron`) ships alongside it. The file did not exist in the
  `v0.1.0` tag; this window is where it arrived.
- **`scripts/clab-reaper.sh` then reaped nothing at all.** The `python -c` one-liner that reads the app's
  session list parsed its input as a filename, so it took the first line of stdin as a path and failed;
  the reaper treated that failure as "no sessions" and, depending on the guard, either skipped every
  candidate or removed by age. Fixed by feeding the request body through stdin correctly.
- **`tools/lint_lab_pack.py` printed `ERROR` for labs it had never checked.** When the tool could not run
  (missing dependency / unparseable input) it emitted one `ERROR` line per lab, which reads as "this lab
  failed" when the truth is "the check did not execute". It now reports the check itself as not-run.
  `CONTRIBUTING.md` was updated to match the real output.
- **`lab-definitions/srl-demo2-unsolved/demo-02-two-switches-one-router-unsolved.yml`: the prerequisite
  pointed at a Demo 1 id that does not ship.** A learner following the prerequisite link landed on
  nothing. It now names the id that is actually in the tree
  (`demo-01-two-pcs-and-a-real-switch-unsolved`). One line.

### Changed
- **Documentation sweep, continued** (the bulk of the window): README corrections for the lab-guide
  button's real response type, the API card's real version string, the install script's refusal to copy
  per-lab assets, and a rendered component diagram in place of the ASCII sketch; a `SECURITY.md`; a
  `CONTRIBUTING.md` that states the CI secret-scan grep instead of naming it; `.gitattributes` pinning
  YAML/source text to LF and images to binary; and the internal worklog relabelled as internal wherever
  it was being advertised as public documentation.

## [Unreleased] — honesty sweep, week of 2026-10-20
### Added
- **`docs/OPERATIONS.md`: a "Stopping a session" section.** The failure mode with the worst
  operator-facing consequences — a stop that reports failure while the lab is still up, and a
  `clab-*` container that no session can claim — was documented nowhere, so the only way to learn it
  was to hit it. The section states, from the code: a failed teardown is HTTP `500` and leaves the
  session listed (`POST /api/sessions/{id}/stop`, RUN 209) so **End Lab again** is the retry; a stop on
  an unknown id is `404`, not a live lab; teardown and ttyd-port release happen inside the deploy lock
  a `start` also takes; and `reconcile_sessions()` adopts only containers carrying the
  `aegis.session.id` label, which is why `scripts/clab-reaper.sh`'s default `--orphans` mode refuses
  (exit 3 unreadable app / exit 4 unlabelled containers) instead of guessing. Documentation only; no
  behaviour change.

### Changed
- **`CONTRIBUTING.md`: the four checks a contributor is told to run are now three commands and one
  pattern.** "Run the same checks CI runs" listed steps 1–3 as copy-paste commands and step 4 as a
  comment — the secret scan is a shell `grep` that lives inline in `.github/workflows/ci.yml`, so a
  contributor had nothing to run for it and no way to know what the pass looked like. The grep is now
  written out, and it says to use `grep`, not `git grep`: `git grep` reads only tracked files, so it
  misses a secret in an untracked file — measured, a seeded `ghp_…` token in an unstaged file is
  *missed* by `git grep` and *found* by the CI `grep -rInE` form. The section also no longer implies
  step 3 can catch a deleted or never-added file: `check_self_contained.py` runs inside a clone and
  checks only what is present, and resolves its root from its own path. Documentation only.
- **README: how a lab guide actually opens.** The "Lab Guide" button points at
  `/api/labs/{id}/guide`, and `backend/main.py` answers that route with
  `PlainTextResponse(..., media_type="text/markdown")` — verified by calling the route against the
  shipped tree (HTTP 200, `text/markdown; charset=utf-8`, 2140 / 2649 bytes for the two guides).
  Browsers display that type inconsistently (Firefox renders it; Chrome/Safari commonly download it),
  and the frontend ships **no** Markdown renderer (`frontend/index.html` contains no `marked`/Markdown
  code — the handler is one `window.open()`). The README's lab table linked the files but said nothing
  about what a student would see, so the note is now stated next to the table. Documentation only; the
  endpoint behaviour is unchanged.

## [Unreleased] — honesty sweep, week of 2026-10-10 → 2026-10-16

No shipped behaviour changed this week. Thirty-five commits, all documentation/provenance corrections with
one additive CI check; no new feature and no fix to a defect a user could hit. Recorded here because the
claims below changed, even though the product did not. **No version tag drawn from this window** — a release
tag should mark a product change, and there is none to mark (see the release-notes draft for the reasoning).

### Added
- **`SECURITY.md`.** The repo had no security policy; `CONTRIBUTING.md` said so in as many words. The new
  file states a reporting route (contact the maintainer privately, no public proof-of-concept), the threat
  model it is assessed against (single trusted host, unauthenticated API on `0.0.0.0:8000`, unauthenticated
  `ttyd` terminals on `8765`–`9765`, labs run as a non-login `aegis` service user with docker access — i.e.
  container isolation, not shell isolation), what is actually in scope (wrong-`pass` graders, verdicts
  returned when a node was never examined, container escapes, committed secrets, installer integrity), and
  what this project does **not** do (no dependency scanning, SAST, fuzzing, or bug bounty). No code change.

### Changed
- **Stale-bundle claims retracted across every surface.** README, `docs/OPERATIONS.md`, `CONTRIBUTING.md`,
  the PR template, `CONFERENCE.md`, the CHANGELOG and the release-notes draft all told the old
  "rebuild-and-deploy a release bundle" story. No bundle ships in this tree (`find . -name '*.tar.gz'`
  returns nothing outside `.git/`), and `tools/check_bundle_fresh.sh` **no-ops** ("no bundle present").
  Each surface now names the shipping model as a git clone + `install.sh` and labels the guard vestigial.
- **Pre-history `.git` size dropped.** The "730 MB → 1.6 MB" figure was measured at the 2026-09 purge,
  which predates this git history; measured 2026-10-16 the `.git` is ~21 MB packed / ~24 MB on disk and
  the working tree ~4 MB. Current figures now stated in place of the inherited number.
- **Unresolvable `LAB-A`/`LAB-B` nicknames replaced with real lab names** in shipped docs *and* shipped
  source (`backend/main.py` comments, `grader_demo_02.py` docstring). The nicknames resolved to nothing
  in this tree; the labs are `demo-01-two-pcs-and-a-real-switch-unsolved` and
  `demo-02-two-switches-one-router-unsolved`.
- **README corrections:** Demo 2 lab-table row now counts all 5 nodes (was 3 of 5); the API table is
  complete (4 undocumented routes added); `.nexus/` labelled (ships publicly but was unexplained);
  quarantined topologies' path corrected.
- **Historical disclaimers added** to `10-archive/SUMMARY-for-Dad.md`, `HANDOFF-2026-09-22.md`, and the
  orphan `lab-guides/lab-03-lock-it-down.md` — each named paths or a provenance link false of this tree.
- **Inert `_GUIDE_MAP` labelled.** All seven of its target filenames are absent from `lab-definitions/`;
  it is a fossil of the pre-release layout, kept (not deleted) and now explicitly marked inert in source.
- **Release-notes draft tag-pointer statement corrected.** It claimed the `v0.1.0` tag "points at the
  current `main` tip." Measured live 2026-10-17: the tag exists on `origin` at `35e271d` and `main` was
  **37 commits ahead** (`git describe` → `v0.1.0-37-g4a37ea9`; 43 as of 2026-10-18); no GitHub Release exists (releases API
  → `[]`). The draft now states the measured tag commit, the drift, and that only the tag (not a
  Release) exists.

### Added
- **CI: shipped lab graders are byte-compiled** in `tools/check_self_contained.py`, so a syntax error in
  a `grader_*.py` now fails CI instead of passing silently.
- Repo hygiene: two orphaned root lab YAMLs moved into the quarantine dir the README names; a stray
  BGP-revert backup moved out of the shipping lab dir.

### Known limitations (unchanged, still named)
- `aegis/frr` image is local-only (never pushed to a registry); cold-host deploy is not hand-step-free.
- Student browser UI is not smoke-tested end to end (browser policy blocks automated navigation).
- Static routing only — no BGP/OSPF/EVPN in the shipped labs.

## [0.1.0] — 2026-10-09

First tagged snapshot of the two-lab shipping set. Every claim below is backed by a proof
under `.nexus/proofs/`; nothing here is asserted without a checkable artifact.

### Fixed
- **Cold install could not deploy a lab.** `install.sh` pinned containerlab 0.60.0, which rejects the
  labs' `type: ixr-d2l` node; a fresh host served the UI but `POST /api/sessions/start` returned 500.
  Pinned to **0.75.0** (the version the labs are verified against). Found by an end-to-end cold-install
  test in a blank container — see `.nexus/proofs/cold-install-verified-and-containerlab-pin-fixed-20261007.txt`.
- **A stale shippable bundle could be served.** Added `tools/check_bundle_fresh.sh` as a guard; the
  freshness check fails if source and bundle disagree (runs 258/260). **Note:** this guard is
  vestigial in the shipping tree — the `nexus-release.tar.gz` bundle is the *older* shipping path and
  **no bundle is committed** (`find . -name '*.tar.gz'` returns nothing outside `.git/`), so the guard
  no-ops with "no bundle present". The current shipping model is a git clone + `install.sh`; see the
  README quickstart and `docs/OPERATIONS.md` → "Release bundle (historical)".
- **The start/session panel could name a substrate the lab does not run.** The pinned substrate is
  now surfaced where a human reads it, with a live-derived, aegis-less identity that includes the
  switch (runs 246–248).

### Changed
- **Repo is now self-contained and small.** Removed 82 stale ~20 MB bundle snapshots from
  `.nexus/bundle-archive/` and purged them from history; `.gitignore` tightened so a future run
  can't re-commit them. **Note:** the `730 MB → 1.6 MB` figure that stood here was the size at the
  2026-09 purge moment and predates this history — it is no longer the shipped size. Measured now
  (2026-10-16): `.git` is ~21 MB packed / ~24 MB on disk, the working tree ~4 MB. Still small, and
  a cold clone is fast; the old number is kept out because a cloner does not see 1.6 MB.
- README rewritten for a public audience; operational detail moved to `docs/OPERATIONS.md`.
- Added Apache-2.0 `LICENSE`, `CONTRIBUTING.md`, `requirements.txt`, and CI.
- Removed the last hard-coded developer path from `install.sh`.

### Added
- `tools/check_self_contained.py` (+ CI job): fails if a bare clone isn't installable.
- **Verification evidence for both labs**, each with a proof file: a student success path end to
  end (Demo 1 3/3 run 252; Demo 2 5/5 run 253), served guides followed literally (runs 261/262), and
  graders that reject a wrong answer and discriminate a subtly-wrong config (runs 263/264).
- **Resilience proofs:** a configured lab keeps grading a passing verdict across a server restart
  for both labs, including the full 5-node Demo 2 (runs 269/270/271).
- **Refusal safety:** a session with no resolvable runtime digest refuses to grade rather than emit
  a false verdict (runs 251/256).
- Documentation: `docs/architecture.md` (component + lifecycle diagrams), `docs/ADDING-A-LAB.md`,
  `docs/GRADING-MODEL.md`, `docs/SELF-CONTAINED.md`, `docs/OPERATIONS.md`.
- Repo hygiene: `.github/ISSUE_TEMPLATE/` (`bug_report.md`, `lab_request.md`),
  `PULL_REQUEST_TEMPLATE.md`, `CITATION.cff`, CI status badge in the README.

### Known limitations (named, not hidden)
- **`aegis/frr` image is local-only.** It has never been pushed to a registry (`RepoDigests: []`),
  so `install.sh` cold-host deployment is not yet hand-step-free — that needs a transport decision.
- **Student browser UI is not smoke-tested.** The browser tool refuses to navigate to the served UI
  (policy), so every automated run drove the API with curl; the rendered page/JS remains unverified
  end to end (run 272). Named as a real verification limit, not a product defect.
- **Static routing only.** No BGP/OSPF/EVPN in the shipped labs.

### Not released (blocked, awaiting Dad's ruling)
- CI hardening — byte-compile the shipped lab graders (`lab-definitions/grader_*.py`). The change is
  written and verified but edits `.github/workflows/ci.yml`, and neither write token carries the
  `workflow` scope; pushed rejected. Not forced.
- Screenshots of the student UI — require a session on the host where AEGIS actually runs (this box
  is on a different subnet; the lab host is unreachable from here).

## Notes on history

This repository was reduced to the two-lab shipping set on 2026-10-06. The pre-cleanup public
history remains available on the `legacy-orphan-tree` branch.
