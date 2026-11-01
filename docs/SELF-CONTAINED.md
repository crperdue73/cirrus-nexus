# Self-contained by design

**Requirement:** a clean host that clones this repo must be able to install and run AEGIS using
**only what is in this repository** (plus the public container registries it pulls from). Nothing may
depend on a developer's machine, a private path, or an out-of-band file that isn't shipped.

## How that is enforced

`tools/check_self_contained.py` runs in CI on every push and PR. It fails if:

- a required file (installer, backend, frontend, lab definitions, graders, pin) is missing.
  This list is measured against the installer's own copy block, so it holds exactly what
  `install.sh` carries to `/opt/aegis` — no more;
- a repository file that `install.sh` does *not* carry is missing (`LICENSE`). That is a
  licensing problem, not an install failure, and it is reported under its own message so the
  two claims never share one number;
- a lab's `startup-config` asset or `grader` module doesn't resolve inside the repo;
- a shipped grader (`lab-definitions/grader_*.py`) does not byte-compile;
- a developer's absolute path (`/home/<user>/.openclaw`, `/Users/<user>/.openclaw`) appears in any
  shipped source file.

**What it does not check: the install step.** It proves the *repository* is complete; it does not
prove that `install.sh` carries those files to `/opt/aegis`. It could not: the installer needs root,
Docker and network, and CI runs none of it. Two limits are worth stating plainly, because a guard
that is trusted beyond its reach is worse than no guard:

- **It cannot notice a file that was deleted before commit.** It reads the working tree, so a file
  missing from a clone is missing here too — but only if it is in a list above or referenced by a
  shipped topology. A file that ships, that nothing needs, and that someone has since deleted, is
  invisible to it.
- **It cannot notice an untracked file on the machine that ran it.** The mirror image of the same
  blind spot, and it has bitten this repo: until 2026-10-24 the per-lab `assets/` folders existed on
  the development host but were never copied by the installer, so a cold install served an empty lab
  catalog while every local run looked healthy. `install.sh` now copies them explicitly and verifies
  every `startup-config:` a shipped topology names exists under `/opt/aegis`, warning by name if one
  does not — the verification the CI check cannot perform lives in the installer instead.

The one path this guard does not exercise at all is the pinned-tarball restore in `install.sh`:
`assets/frr-image.pin` ships its re-pinned Dockerfile fingerprint with `layers_sha256` and `tarball`
set to `UNPINNED`, and no tarball ships. So a cold install always takes the build-from-source path,
and the load-and-verify branch is unproven by any check or by any recent install. It is recorded here
rather than in the tool's success line, because a check that cannot run that branch must not appear to
have passed it.

## What a cold install pulls from the network

Only third-party images the two labs (`demo-01-two-pcs-and-a-real-switch-unsolved`,
`demo-02-two-switches-one-router-unsolved`) need:

| image | why | size |
|---|---|---|
| `ghcr.io/nokia/srlinux:latest` | the real switch in both labs | ~0.75 GB compressed, single layer (measured from its registry manifest 2026-10-31) |
| `alpine:latest` | the PCs — and the base of `Dockerfile.frr` | small |
| `aegis/frr:latest` | the router in Demo 2 (`demo-02-two-switches-one-router-unsolved`) | **built locally** from `Dockerfile.frr` |

The FRR substrate is **built from source** (`Dockerfile.frr`, in this repo, `FROM alpine:latest`). No
pinned image tarball ships — the pin records `tarball=` empty and `UNPINNED` for the layer chain and
build time — so the installer's build-from-source path is the only one a cold host takes, and no binary
blob is required to install. See [`OPERATIONS.md`](OPERATIONS.md) for the image-pin notes.
