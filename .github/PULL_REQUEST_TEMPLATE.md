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

## If this touches a served lab

- [ ] I reloaded lab definitions (`POST /api/labs/reload`) and re-ran the grader.

  ```bash
  curl -X POST http://localhost:8000/api/labs/reload
  ```

There is **no shippable bundle** in this tree: `frontend/nexus-release.tar.gz` does not ship, and a
clean host installs straight from the git clone + `install.sh` — which copies the project to
`/opt/aegis` and runs that copy as the `aegis` service. **Edit your clone; `/opt/aegis` is the deployed
copy, not a workspace.** You do not rebuild or commit a `nexus-release.tar.gz`. `tools/check_bundle_fresh.sh` still exists and is safe to
run, but it no-ops when no bundle is present — as it is here — so it is not a required check on this
repo.

## How it was verified

Paste the **real** command output you used to convince yourself this works.
