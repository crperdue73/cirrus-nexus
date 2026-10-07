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

## What a cold install pulls from the network

Only third-party images the two labs need:

| image | why | size |
|---|---|---|
| `ghcr.io/nokia/srlinux:latest` | the real switch in both labs | ~2.35 GB |
| `alpine:latest` | the PCs | small |
| `aegis/frr:latest` | the router in LAB-B | **built locally** from `Dockerfile.frr` |

The FRR substrate is **built from source** (`Dockerfile.frr`, in this repo) when no pinned tarball is
shipped — so no binary blob is required to install. See
[`OPERATIONS.md`](OPERATIONS.md) for the image-pin notes.
