# Pull Request

## What this changes

One or two sentences on *what* and *why*. One change per PR.

## Type

- [ ] Bug fix
- [ ] New or edited lab (definition + grader)
- [ ] Docs
- [ ] Tooling / CI
- [ ] Other:

## Truth check (required)

AEGIS keeps one rule: **everything in the repo must be true.** Confirm:

- [ ] No invented benchmarks, metrics, or "supports X" claims that aren't in this tree.
- [ ] Any screenshot or diagram here is a **real** capture of this tree, not a mock.
- [ ] Nothing claims the project is "complete" or "finished" — that's the maintainer's call.
- [ ] No `*.bak*`, `clab-*/`, `._clean_*`, secrets, bundled images, or tarballs added.

## Ran before pushing

The same checks CI runs:

- [ ] `python3 -m py_compile backend/main.py`
- [ ] `bash -n install.sh`
- [ ] `python3 tools/check_self_contained.py`
- [ ] `python3 tools/lint_lab_pack.py`  (if labs changed)

## If this touches a served lab or the bundle

- [ ] I reloaded lab definitions (`POST /api/labs/reload`) and re-ran the grader.

  ```bash
  curl -X POST http://localhost:8000/api/labs/reload
  ```

- [ ] If shipping files changed, I rebuilt `frontend/nexus-release.tar.gz`
      (see `docs/OPERATIONS.md`) — it is a snapshot, not a symlink.
- [ ] The served frontend, source, and bundle still agree (`tools/check_bundle_fresh.sh`).

## How it was verified

Paste the **real** command output you used to convince yourself this works.
