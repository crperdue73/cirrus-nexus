# Changelog

All notable changes to AEGIS are recorded here. This project ships two labs
(`demo-01-two-pcs-and-a-real-switch-unsolved`, `demo-02-two-switches-one-router-unsolved`).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2026-10-09

First tagged snapshot of the two-lab shipping set. Every claim below is backed by a proof
under `.nexus/proofs/`; nothing here is asserted without a checkable artifact.

### Fixed
- **Cold install could not deploy a lab.** `install.sh` pinned containerlab 0.60.0, which rejects the
  labs' `type: ixr-d2l` node; a fresh host served the UI but `POST /api/sessions/start` returned 500.
  Pinned to **0.75.0** (the version the labs are verified against). Found by an end-to-end cold-install
  test in a blank container — see `.nexus/proofs/cold-install-verified-and-containerlab-pin-fixed-20261007.txt`.
- **A stale shippable bundle could be served.** Added `tools/check_bundle_fresh.sh` as a guard; the
  bundle is rebuilt and the freshness check fails a deploy if source and bundle disagree
  (runs 258/260).
- **The start/session panel could name a substrate the lab does not run.** The pinned substrate is
  now surfaced where a human reads it, with a live-derived, aegis-less identity that includes the
  switch (runs 246–248).

### Changed
- **Repo is now self-contained and small.** Removed 82 stale ~20 MB bundle snapshots from
  `.nexus/bundle-archive/` and purged them from history (`.git`: 730 MB → 1.6 MB; a cold
  clone is now <1 s). `.gitignore` tightened so a future run can't re-commit them.
- README rewritten for a public audience; operational detail moved to `docs/OPERATIONS.md`.
- Added Apache-2.0 `LICENSE`, `CONTRIBUTING.md`, `requirements.txt`, and CI.
- Removed the last hard-coded developer path from `install.sh`.

### Added
- `tools/check_self_contained.py` (+ CI job): fails if a bare clone isn't installable.
- **Verification evidence for both labs**, each with a proof file: a student success path end to
  end (LAB-A 3/3 run 252; LAB-B 5/5 run 253), served guides followed literally (runs 261/262), and
  graders that reject a wrong answer and discriminate a subtly-wrong config (runs 263/264).
- **Resilience proofs:** a configured lab keeps grading a passing verdict across a server restart
  for both labs, including full 5-node LAB-B (runs 269/270/271).
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
