# Self-contained by design

**Requirement:** a clean host that clones this repo must be able to install and run AEGIS using
**only what is in this repository** (plus the public container registries it pulls from). Nothing may
depend on a developer's machine, a private path, or an out-of-band file that isn't shipped.

## How that is enforced

`tools/check_self_contained.py` runs in CI on every push and PR. It fails if:

- a required file (installer, backend, frontend, lab definitions, graders, pin) is missing;
- a lab's `startup-config` asset or `grader` module doesn't resolve inside the repo;
- a developer's absolute path (`/home/<user>/.openclaw`, `/Users/<user>/.openclaw`) appears in any
  shipped source file.

**What it does not check: the install step.** It proves the *repository* is complete; it does not
prove that `install.sh` carries those files to `/opt/aegis`. It could not: the installer needs root,
Docker and network, and CI runs none of it. The check also cannot notice a file that was deleted
before commit. See the *Known gap* note in the README's Quick start for the one place where this
boundary is currently visible — the per-lab `assets/` folders are in the repo but are not copied by
the installer, so a fresh install serves an empty catalog until they are copied by hand.

## What a cold install pulls from the network

Only third-party images the two labs (`demo-01-two-pcs-and-a-real-switch-unsolved`,
`demo-02-two-switches-one-router-unsolved`) need:

| image | why | size |
|---|---|---|
| `ghcr.io/nokia/srlinux:latest` | the real switch in both labs | ~2.35 GB |
| `alpine:latest` | the PCs | small |
| `aegis/frr:latest` | the router in Demo 2 (`demo-02-two-switches-one-router-unsolved`) | **built locally** from `Dockerfile.frr` |

The FRR substrate is **built from source** (`Dockerfile.frr`, in this repo) when no pinned tarball is
shipped — so no binary blob is required to install. See
[`OPERATIONS.md`](OPERATIONS.md) for the image-pin notes.
