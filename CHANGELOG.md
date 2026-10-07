# Changelog

All notable changes to AEGIS are recorded here. This project ships two labs
(`demo-01-two-pcs-and-a-real-switch-unsolved`, `demo-02-two-switches-one-router-unsolved`).

## [Unreleased]

### Fixed
- **Cold install could not deploy a lab.** `install.sh` pinned containerlab 0.60.0, which rejects the
  labs' `type: ixr-d2l` node; a fresh host served the UI but `POST /api/sessions/start` returned 500.
  Pinned to **0.75.0** (the version the labs are verified against). Found by an end-to-end cold-install
  test in a blank container — see `.nexus/proofs/cold-install-verified-and-containerlab-pin-fixed-20261007.txt`.

### Changed
- **Repo is now self-contained and small.** Removed 82 stale ~20 MB bundle snapshots from
  `.nexus/bundle-archive/` and purged them from history (`.git`: 730 MB → 1.6 MB; a cold
  clone is now <1 s). `.gitignore` tightened so a future run can't re-commit them.
- README rewritten for a public audience; operational detail moved to `docs/OPERATIONS.md`.
- Added Apache-2.0 `LICENSE`, `CONTRIBUTING.md`, `requirements.txt`, and CI.
- Removed the last hard-coded developer path from `install.sh`.

### Added
- `tools/check_self_contained.py` (+ CI job): fails if a bare clone isn't installable.

## Notes on history

This repository was reduced to the two-lab shipping set on 2026-10-06. The pre-cleanup public
history remains available on the `legacy-orphan-tree` branch.
