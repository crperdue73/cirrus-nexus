# AEGIS — Networking Labs for the Classroom

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![status: v0.1.0 — early release](https://img.shields.io/badge/status-v0.1.0%20early%20release-yellow.svg)](#release-status)
![Python 3](https://img.shields.io/badge/python-3.x-blue.svg)
![Powered by ContainerLab](https://img.shields.io/badge/powered%20by-containerlab-orange.svg)
![API: FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)
[![CI](https://github.com/crperdue73/cirrus-nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/crperdue73/cirrus-nexus/actions/workflows/ci.yml)

**AEGIS** turns a single Linux host into a small, self-contained networking lab bench. Students get
**real** routers and switches — the same FRR and Nokia SR Linux images a network engineer would
touch — in a browser tab, with an **automated grader** that scores their configuration against the
live devices.

Built for **high school Cisco Networking (Net Eng I)**. No cloud account, no per-seat service, one
install command.

---

## What this is — and what it is **not**

**It is:** a static-routing and L2-switching teaching lab. IPv4/IPv6 addressing, interface bring-up,
L2 bridging, switch IRB/SVI gateways, static routes, end-to-end ping and traceroute, and basic device
security — graded automatically.

**It is not:** a dynamic-routing platform. **No OSPF. No BGP. No EVPN. No VPNs.** Those daemons are
disabled in the shipped substrate on purpose. If you need them, this isn't the tool.

---

## The shipping labs

This release ships exactly **two** labs. Both use **Nokia SR Linux** switches.

| Lab | ID | Topology | Difficulty | Time | Guide |
|-----|----|----------|-----------|------|-------|
| **Demo 1 — Two PCs and a Real Switch** | `demo-01-two-pcs-and-a-real-switch-unsolved` | 2 Alpine PCs + 1 SR Linux switch, bridged | Beginner | 25 min | [guide](lab-definitions/srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.md) |
| **Demo 2 — Two Switches and One Router** | `demo-02-two-switches-one-router-unsolved` | 2 Alpine PCs + 2 SR Linux switches + 1 FRR router, routed | Intermediate | 35 min | [guide](lab-definitions/srl-demo2-unsolved/demo-02-two-switches-one-router-unsolved.md) |

Each lab is a YAML topology plus a Markdown **student guide** (objective, topology, step-by-step
instructions) in the same directory, alongside its Python grader. The guides linked above are the ones
shipped in this tree.

> **Reading a guide in the browser:** the **Lab Guide** button opens the served copy at
> `/api/labs/{id}/guide`. That endpoint answers `Content-Type: text/markdown`, which browsers display
> inconsistently (Firefox renders it; Chrome and Safari typically download it instead). Open the
> downloaded file in a text editor or Markdown viewer, or read the linked file on GitHub. This release
> ships **no in-app Markdown renderer** — the frontend is a single `fetch()`-driven page (`frontend/index.html`)
> and the guide opens in a new tab.

The other topologies are retained for reference and are **not** part of this release; they live in the
sibling directory `lab-definitions-quarantine-2026-09-30/` (outside `lab-definitions/`, so the loader
does not see them). That is a different place from `10-archive/` — see the Archive section of
[`docs/OPERATIONS.md`](docs/OPERATIONS.md) for what is in each.

---

## How it works

The full component breakdown and the lab lifecycle are in
[`docs/architecture.md`](docs/architecture.md); the sketch below is the essential shape.

```
        student browser
              │  HTTP  (:8000)
              ▼
   ┌─────────────────────────┐
   │  backend/main.py        │   FastAPI + uvicorn
   │  • lab catalog + guides │   loads lab-definitions/*.yml once, caches them
   │  • session lifecycle    │
   │  • grader runner        │──────────────┐
   └───────────┬─────────────┘              │ docker exec / vtysh / sr_cli
               │ containerlab deploy/destroy │
               ▼                             ▼
   ┌─────────────────────────┐   ┌──────────────────────────────────┐
   │  containerlab topology  │   │  live lab containers             │
   │  (lab-definitions/*.yml)│   │  alpine · aegis/frr · srlinux    │
   └─────────────────────────┘   └──────────────────────────────────┘
               │ ttyd
               ▼
   in-browser terminals per node (frontend/index.html)
```

- **Backend:** a single FastAPI app (`backend/main.py`) — lab catalog, session start/stop, terminal
  wiring, and the grader runner.
- **Frontend:** one static page (`frontend/index.html`) that talks to the API and embeds a `ttyd`
  terminal per node.
- **Lab definitions** are plain YAML (`lab-definitions/**/*.yml`) plus a Python grader
  (`lab-definitions/grader_*.py`) per lab. Adding a lab is adding a YAML file and a grader.
- **Substrate:** `aegis/frr:latest` — Alpine + FRR with only `zebra` and `staticd` enabled.

---

## Quick start

**Prerequisites:** a clean Debian/Ubuntu host, `sudo`, internet access (to pull the SR Linux image),
and ~3 GB free disk. **No image ships in the repo:** the router image (`aegis/frr:latest`) is built
locally from `Dockerfile.frr`, and the switch image is pulled at install.

```bash
git clone https://github.com/crperdue73/cirrus-nexus.git aegis
cd aegis
sudo ./install.sh
```

`install.sh` installs Docker, ContainerLab, `ttyd`, and the Python deps
(`fastapi`, `uvicorn`, `pyyaml`), copies the app to `/opt/aegis`, builds the FRR router image from
`Dockerfile.frr` (this tree ships no prebuilt FRR tarball), pre-pulls the switch image, and installs a
systemd service.

```bash
sudo systemctl start aegis     # start the server
sudo systemctl enable aegis    # start on boot
sudo systemctl status aegis    # check
```

The UI is at `http://localhost:8000/`; the API at `http://localhost:8000/api`.

> **Service names:** the installer registers **`aegis.service`**. The *product* is named NEXUS —
> the API's own health card says `"service": "NEXUS"` — so you will see both names in the product,
> the docs, and this repository (which is `cirrus-nexus`). Everything you type is `aegis`.

---

## Grading — three honest outcomes

A grade is a **verdict only when the node could actually be examined.** The grader returns one of:

| outcome | meaning |
|---------|---------|
| **pass / fail** | the node was examined and the configuration met / didn't meet the lab's criteria |
| **refused** | the system could not make a truthful statement (node down, substrate changed since start, no grader) — returned as HTTP `409`, **never** as a silent pass |

The last case matters: a student should never be told "wrong" when the truth is "nobody looked."

---

## API

The table below is the complete route set exposed by `backend/main.py` (11 routes). Parameters are
**query parameters** — the `start` and `submit` handlers read them from the query string, which is
exactly how the shipped UI calls them.

| Method | Route | Parameters | Purpose |
|--------|-------|------------|---------|
| `GET` | `/api` | — | service card: `{"service": "NEXUS", "version", "labs_count"}` |
| `GET` | `/api/labs` | — | the served lab catalog |
| `GET` | `/api/labs/{id}` | — | one lab's definition |
| `GET` | `/api/labs/{id}/guide` | — | the lab's Markdown student guide (served raw) |
| `GET` | `/api/labs/{id}/topology` | — | the lab's rendered topology diagram |
| `POST` | `/api/labs/reload` | — | re-read lab definitions and clear the grader cache |
| `POST` | `/api/sessions/start` | `lab_id` (required), `student_name` (default `Student`) | deploy a lab and open a session |
| `GET` | `/api/sessions` | — | running sessions, newest first |
| `GET` | `/api/sessions/{id}` | — | one session's status (used by *Reconnect*) |
| `POST` | `/api/sessions/{id}/submit` | `node` (required) | grade one node |
| `POST` | `/api/sessions/{id}/stop` | — | tear down a session |

Example — start, grade, stop (the same three calls the UI makes):

```bash
# 1. deploy a lab; the response carries session_id and a per-node ttyd URL
curl -X POST 'http://localhost:8000/api/sessions/start?lab_id=demo-01-two-pcs-and-a-real-switch-unsolved&student_name=Ada'

# 2. grade one node
curl -X POST 'http://localhost:8000/api/sessions/<session_id>/submit?node=sw1'

# 3. tear it down
curl -X POST 'http://localhost:8000/api/sessions/<session_id>/stop'
```

### Interactive API docs

FastAPI generates these three pages from the routes above — they are served by the app itself, not
written by hand, so they cannot drift from the code:

| page | what it is |
|------|------------|
| `/docs` | Swagger UI — every route, its parameters, and a *Try it out* button |
| `/redoc` | the same schema as reference documentation |
| `/openapi.json` | the raw OpenAPI 3 document, for codegen or an external client |

```
http://localhost:8000/docs
```

They are **only readable from where the server is reachable.** Unlike the student UI, the API has no
login and no per-session token (see *Binds to every interface* below), so on a shared network `/docs`
is open to anyone who can hit port 8000 — bind the server to localhost (or put it behind your own
auth) if that is not what you want.

**Responses.** A grade returns `{session_id, node, grade}` where `grade` carries `passed`, `score`,
`feedback`, `competencies`, the in-band `status` (`graded` / `error` / `refused`) and the
`runtime_digest` it was taken against. A **refusal** is HTTP `409` with the reason in `detail` — the
same three-outcome rule as the grading model above. An unknown lab, session or node is `404` (a node
that the *lab* does not have is a `409` refusal with the node list, since that is a question, not a
missing record); a failed deploy is `500`.

---

## Development

**Lab definitions are cached in memory.** Editing a grader or topology will not take effect until you
reload:

```bash
curl -X POST http://localhost:8000/api/labs/reload
```

**The shipping model is a git clone plus `install.sh`** — no prebuilt bundle is committed to this
tree (`find . -name '*.tar.gz'` returns nothing outside `.git/`). Earlier revisions of
[`docs/OPERATIONS.md`](docs/OPERATIONS.md) described rebuilding a `frontend/nexus-release.tar.gz`
bundle; that path is kept there as *historical* because a `nexus-release.tar.gz` no longer ships.

---

## Release status

**v0.1.0 — early release.** The tree is a working, installable teaching platform for its two shipped
labs; it is not a finished product. What that means concretely:

- **No published release.** A `v0.1.0` git tag exists, but it points at an older commit than the tip
  of `main` — every commit since the tag is documentation or CI, with no change to how a lab runs
  (see the sweep in [`CHANGELOG.md`](CHANGELOG.md)) — and **no GitHub Release has been published**
  for it. Tag position is deliberately not given as a commit count here: a count goes stale with every
  push. Measure it yourself with `git describe --tags` — see
  [`docs/RELEASE-NOTES-v0.1.0-draft.md`](docs/RELEASE-NOTES-v0.1.0-draft.md) for the tag's full
  history.
- **No screenshots in this README.** Every capture would have to come from a live install; none has
  been taken yet, and none is faked here.
- **Two labs only, static routing only** (see below).

## Known limitations (read these before you rely on it)

- **Static routing only** — see "what this is not," above.
- **A host reboot loses running labs.** Student containers are not restored on boot.
- **Binds to every interface, with no authentication.** The server listens on `0.0.0.0:8000`
  (`AEGIS_HOST` / `AEGIS_PORT` override that, and `install.sh` prints the LAN URL), and every route —
  including `start`, `stop`, and `/docs` — is unauthenticated. That is deliberate for a classroom's
  own network and is **not** safe exposed to the internet. The in-browser terminals (ttyd, ports
  `8765`–`9765`) are similarly open, which is why those ports ship bound to all interfaces too.
- **The SR Linux image is a ~2.35 GB pull**; each switch node runs a full instance of it. Keep to
  **one session per student per lab**; use *Reconnect* for a returning student rather than Start.
- **A known image-pin drift:** `Dockerfile.frr` hashes differently from `assets/frr-image.pin`. No
  pinned FRR image tarball ships in this tree (`assets/` tracks only `frr-image.pin`;
  `installed-image-id.txt` exists locally but is git-ignored, so it does not ship), so `install.sh`
  takes its build-from-source fallback and builds
  `aegis/frr:latest` locally from `Dockerfile.frr`. That build is self-consistent but will not match
  the pin's `layers_sha256`. Details in [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

---

## Documentation

| doc | contents |
|-----|----------|
| [`docs/architecture.md`](docs/architecture.md) | components, diagrams, the lab lifecycle, the grading path, substrates, scope boundaries |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | bundle rebuild, runtime digests, concurrency, running without the service, substrate details, known drift |
| [`docs/ADDING-A-LAB.md`](docs/ADDING-A-LAB.md) | what a lab is, the metadata schema, the load-time validation the loader refuses by name, the grader interface |
| [`docs/GRADING-MODEL.md`](docs/GRADING-MODEL.md) | pass / fail / refused, per-node vs lab verdict, the digest gate, the refusal vocabulary |
| [`docs/SELF-CONTAINED.md`](docs/SELF-CONTAINED.md) | what "self-contained" means here, the CI check that enforces it, and exactly what a cold install pulls |
| [`docs/GITHUB-PLAN.md`](docs/GITHUB-PLAN.md) | repo-hardening backlog |
| [`docs/RELEASE-NOTES-v0.1.0-draft.md`](docs/RELEASE-NOTES-v0.1.0-draft.md) | staged release notes for v0.1.0 — **draft, not published** (no GitHub Release exists yet) |
| [`CONFERENCE.md`](CONFERENCE.md) | booth-operator cheat sheet (install, ports, troubleshooting, reset) — **draft / not maintained**; install & lab-catalog sections corrected to this tree |
| [`HANDOFF-2026-09-22.md`](HANDOFF-2026-09-22.md) | dated handoff note from a 2026-09-22 demo drive — **historical / not maintained**; counts and lab names in it describe a wider tree than this release (see the banner in the file) |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | the ground rules, and the checks to run before pushing (the same four CI runs) |
| [`SECURITY.md`](SECURITY.md) | how to report a vulnerability privately, the threat model (unauthenticated by design), what's in scope, and the automated checks that exist (four, and no more) |
| [`CHANGELOG.md`](CHANGELOG.md) | what changed, newest first |
| [`10-archive/SUMMARY-for-Dad.md`](10-archive/SUMMARY-for-Dad.md) | dated 2026-06-09 topology audit — **historical**, describes a pre-release layout (see `docs/OPERATIONS.md` → Archive) |
| [`lab-guides/lab-03-lock-it-down.md`](lab-guides/lab-03-lock-it-down.md) | a single student guide for `lab-03-lock-it-down` — **historical / not a shipping lab** (the only file in `lab-guides/`; its lab definition is quarantined); cited by `docs/OPERATIONS.md` as the in-tree source for the capstone's point numbers |
| [`10-archive/`](10-archive/) | an older archive (not the rest of it): `tier-03-bgp-simplified.yml` (an older BGP topology — **not shipped, not deployable here**, since BGP is disabled in the substrate), the two FRR configs it binds under `frr-configs/`, and `SUMMARY-for-Dad.md` (provenance, below) |
| [`.nexus/`](.nexus/) | internal engineering audit trail — **not required to install or run AEGIS**, and not product documentation (see below) |

### About `.nexus/`

`.nexus/` is this project's **internal working record**, committed here rather than kept private. It is
**not** part of the product and nothing in it is needed to install, run, or grade a lab: a cold clone
installs and runs from `install.sh` and the shipped source alone. Its contents are:

- `.nexus/proofs/` — dated evidence files (cold-install runs, reproductions, audit notes) that several
  documents cite by name (e.g. [`CHANGELOG.md`](CHANGELOG.md) and [`docs/ADDING-A-LAB.md`](docs/ADDING-A-LAB.md)
  point at `.nexus/proofs/`);
- dated status and decision notes (`STATUS.md`, `DECISION-NEEDED-*.md`), which are **historical** — they
  record what was true on their date, not the current state;
- `.nexus/deck-view/` — rendered slide images used while making a deck, kept here for reference.

Read it as a lab notebook: entries are dated, some are superseded, and a stale entry is not a claim
about today. Where a `.nexus/` note and the shipped code disagree, **the code and the docs above win.**

---

## Contributing & changelog

The one rule that matters is that **everything in this repo must be true** — see
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the ground rules and the exact checks to run before pushing.
Notable changes are recorded in [`CHANGELOG.md`](CHANGELOG.md). CI (`.github/workflows/ci.yml`) runs
those checks on every push and pull request.

---

## License

[Apache-2.0](LICENSE).
