# Release notes — AEGIS v0.2.0

**Status: PUBLISHED.** Tagged `v0.2.0` on `main`, GitHub Release published from this file.

- **Tagged:** 2026-10-25.
- **Base:** `main` at the commit this tag points at — measure it with `git describe --tags`, not from
  a number written here (a count in a doc goes stale with every push; that mistake has been made in
  this repo before and is the reason this line reads as a command).
- **Previous tag:** `v0.1.0`, cut 2026-10-09. It is deliberately **not** moved or force-pushed: tags
  are records of what shipped, and rewriting one would make the record disagree with history.
  Anyone who wants the old behaviour can still check out `v0.1.0`.

## Why this is a minor bump, not a patch

`v0.1.0..v0.2.0` contains behaviour changes a learner or operator can hit — not documentation only.
`scripts/clab-reaper.sh` did not exist at `v0.1.0` and now ships and can destroy containers, so the
release changes what the software does. Nothing was removed, so the version goes `0.1` → `0.2`.

## What's in it

### Fixed — a reaper that could kill a live lab
`scripts/clab-reaper.sh` selected containers by age alone, so a `clab-*` container an active learner
was still working in was torn down the moment it crossed the threshold. It now checks the AEGIS
session record / `aegis.session.id` label before removing anything, and its `--orphans` default
refuses instead of guessing: exit 3 if the app is unreadable, exit 4 if a container cannot be
attributed. A companion `scripts/clab-reaper.cron` ships with it.

### Fixed — the reaper's follow-up bug
After the guard landed, a `python -c` one-liner read its input as a filename, so every run silently
saw "no sessions". Corrected; the reaper now reads the session list and acts on it.

### Fixed — `lint_lab_pack` no longer lies about failures
A tool that could not run printed one `ERROR` per lab, which reads as a lab failure. It now reports
the check as not-run, and `CONTRIBUTING.md` shows the output a contributor will actually see.

### Fixed — Demo 2's prerequisite
It linked to a Demo 1 id that is not in the repo. It now names
`demo-01-two-pcs-and-a-real-switch-unsolved`.

### Fixed — the installer verifies the lab assets it needs
`install.sh` now copies each lab's `assets/` explicitly and then verifies that every
`startup-config:` named by a shipped topology actually exists under the install directory, warning by
name and path when one does not. The failure it guards against is total: the backend refuses a lab
whose startup config is missing, so one absent folder serves zero labs.

## Verification done before this tag was cut

Measured on the release commit, not asserted:

| check | result |
|-------|--------|
| `python3 -m py_compile backend/main.py` | OK |
| `bash -n install.sh` | OK |
| `python3 tools/check_self_contained.py` | OK — 16 required files present, lab assets + graders resolve, no developer paths leak |
| `tools/lint_lab_pack.py` (with PyYAML available) | 2 labs scanned, `SOLVED (red flag): 0` |
| CI secret-scan pattern, run by hand over the tree | no hits |

Note on the last two: `lint_lab_pack.py` reports `UNAVAILABLE` on a host without PyYAML — that is a
not-run, not a pass, and it was installed into a throwaway venv to get a real answer. It is declared
in `requirements.txt`, but a check that did not execute is not evidence, so it was made to execute.

## Still open — stated, not solved

- **Cold-install ships the assets, but the UI is not smoke-tested end to end.** The installer now
  verifies startup configs; it does not drive a browser.
- **No screenshots in the README.** Every capture must come from a live install, and none has been
  taken on a host where that was possible. None is faked.
- **Static routing only, two labs only.** No OSPF, BGP, EVPN or VPNs; the other quarantined lab
  definitions do not ship.
- **Unpinned inputs.** `Dockerfile.frr` does not match `assets/frr-image.pin`, so `install.sh` builds
  the FRR image from source locally; the switch image is pulled as `nokia/srlinux:latest` with no
  per-arch pin, and only x86-64 is tested.
- **Unauthenticated by design.** The API, `/docs`, and the ttyd terminal ports bind to every
  interface with no login. Fine on a classroom LAN; not safe on the public internet.
- **No security contact address is published yet.** `SECURITY.md` states the process; the address is
  still an operator decision, so this release does not invent one.

This is **not a finished product**, and nothing here claims otherwise. Completeness is the
operator's call, not a cron's and not this file's.

## Install

```bash
git clone https://github.com/crperdue73/cirrus-nexus.git
cd cirrus-nexus
git checkout v0.2.0
./install.sh
```

`git checkout v0.2.0` is the line that matters: installing from `main` gives you whatever landed
after this tag.
