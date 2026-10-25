# Security policy

AEGIS is a classroom lab bench: it deploys real routers and switches on one host and grades students'
configurations. This file says how to report a problem, and what this project already knows about
itself so you don't spend a weekend rediscovering it.

## Reporting a vulnerability

**Do not open a public issue for a vulnerability.** No proof-of-concept, no exploit output, no
affected-host details in a public thread.

Contact the maintainer privately, [@crperdue73](https://github.com/crperdue73), through GitHub
(reach out via his profile / a private channel) rather than posting the details publicly. There is
**no security mailing list, no PGP key, and no bug bounty** for this project, and this policy makes
no promise about response times — say what you found, how to reproduce it, and what you think the
impact is, and you'll get a straight answer.

## The threat model, stated up front

AEGIS is designed for **one trusted host on a classroom's own network**. It is *not* designed to be
exposed to the internet, and several of its properties would be vulnerabilities in a different threat
model. These are **known design boundaries, not undisclosed flaws** — reports about them will be
answered as such:

- **The API is unauthenticated.** `backend/main.py` binds to `0.0.0.0:8000` by default
  (`AEGIS_HOST` / `AEGIS_PORT` override that), there is no auth layer on any route, and
  `/docs`, `/redoc`, and `/openapi.json` are served to anyone who can reach the port. Every route —
  including `start`, `stop`, and `/api/sessions/{id}/submit` — is open to the network.
- **The in-browser terminals are unauthenticated.** Each node's terminal is a `ttyd` process on a
  port in the range `8765`–`9765` (see `TTYD_PORT_BASE` / `TTYD_PORT_MAX` in `backend/main.py`),
  bound to the same interfaces, with no per-session secret. Anyone who can reach that port can type
  into that device.
- **Labs run containers as the service user.** A student has root inside a lab node by design — that
  is the point of a lab. The isolation boundary between a student's lab and the host is the
  container, not the shell.
- **There is no multi-tenancy.** Sessions are keyed by student name, not by an authenticated
  identity; one student can act on another's session if they know its id.

If you need a deployment that faces untrusted networks, put it behind something that authenticates —
a reverse proxy with auth, a VPN, or a firewall that restricts `8000` and `8765–9765` to the lab
subnet. That is a deployment decision this project does not make for you.

## What *is* in scope

Problems that break the design above rather than restating it. Examples:

- A lab grader that **passes with zero student work** — this repo has a documented history of
  pre-solved labs, and `tools/lint_lab_pack.py` exists to catch it. A grader that can be fooled into a
  wrong *pass* is a correctness bug we care about.
- A grading path that returns a verdict (`pass` / `fail`) when the node could not actually be
  examined. The invariant is that the system must **refuse** instead — see
  [`docs/GRADING-MODEL.md`](docs/GRADING-MODEL.md).
- A lab definition or grader that escapes its container, writes outside the lab directory, or reads
  host files.
- A secret or credential committed to this repository.
- Bugs in `install.sh` that would let a hostile or corrupted artifact into the host it installs on.

## What this project checks today

CI (`.github/workflows/ci.yml`) runs four checks on every push and pull request: the backend
byte-compiles, `install.sh` is valid shell, the tree is self-contained (a bare clone is installable,
every shipped grader byte-compiles, no absolute developer paths), and a grep for obvious committed
secrets. That is the whole automated surface — there is **no dependency scanning, no SAST, and no
fuzzing**. Don't assume those exist.

## Supported versions

There is one line of development, `main`. This is an early release (`v0.2.0`, published 2026-10-25 —
see the README's *Release status*), so fixes land on `main` and nowhere else.
Older commits do not get backported patches. `v0.1.0` is superseded and receives nothing.

## Disclosure

There is no formal disclosure timeline. If a report is valid, the fix and the credit for it go into
`CHANGELOG.md` when it lands, unless you ask not to be credited.
