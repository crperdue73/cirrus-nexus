# AEGIS — Networking Labs for the Classroom

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![status: v0.2.0 — early release](https://img.shields.io/badge/status-v0.2.0%20early%20release-yellow.svg)](#release-status)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
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

The other topologies are **not** part of this release and are **not in this tree**. They were pulled out
of `lab-definitions/` on 2026-09-30 and held in a sibling quarantine directory until 2026-10-30, when
that directory was archived out of the repository entirely. Nothing in this tree references them; see
the Archive section of [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for what remains (`10-archive/`).

---

## How it works

The full component breakdown and the lab lifecycle are in
[`docs/architecture.md`](docs/architecture.md). The diagram below is the component diagram from that
document, rendered straight out of its `mermaid` block — it is a build of the source diagram, not a
mock-up:

![AEGIS component diagram: student browser → FastAPI backend → containerlab, ttyd, and live lab
containers](docs/assets/architecture-components.png)

The same shape in text, for terminals and diffs:

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

**Prerequisites:** a clean Debian/Ubuntu host (a distro whose `apt` provides a `python3` of **3.10 or newer**
— Ubuntu 24.04 does; 22.04 ships 3.10 as well, and 25.04+ ship newer), `sudo`, internet access (to pull the
SR Linux image), and ~3 GB free disk. `install.sh` does not check the Python version it gets from `apt`;
the four notes below explain what is pinned and what is not, and the last one derives the 3.10 floor.
**No image ships in the repo:** the router image (`aegis/frr:latest`) is built locally from
`Dockerfile.frr`, and the switch image is pulled at install.

Four things you should know before you start, because they are **not pinned or checked in this tree**:

- **The base images are tags, not digests.** `Dockerfile.frr` is `FROM alpine:latest`; both shipped
  topologies bind `ghcr.io/nokia/srlinux:latest` for the switches and `alpine:latest` for the PCs;
  `install.sh` pre-pulls those same two names. All three are `git grep`-able in this tree, and none of
  them is pinned to a digest here — so a build today and a build next month are not guaranteed to be
  the same bits. "Latest" of a third-party image is a moving target; pin it if you need reproducibility.
  (The locally built router image *is* tracked: `assets/frr-image.pin` records a Dockerfile fingerprint
  and a rootfs layer-chain hash, and `install.sh` verifies both — see [Known
  limitations](#known-limitations-read-these-before-you-rely-on-it).)
- **The host architecture is assumed, not checked.** Nothing in `install.sh` tests the CPU architecture
  for the labs themselves. It *reads* `uname -m` for `ttyd` (Step 4: `x86_64`/`aarch64`/`armv7l` get a
  prebuilt binary, anything else builds a 4th package from source via `cmake`), and `Dockerfile.frr` is a
  plain `FROM alpine:latest` with no `--platform`, so Docker picks whatever the host is. But the switch
  nodes are `kind: nokia_srlinux` with **`ghcr.io/nokia/srlinux:latest`** and no architecture override in
  the topology. Nokia's own docs describe the SR Linux container image as ARM64-native *in preview* and
  unqualified, and upstream containerlab says arm64 gets selected automatically only from SR Linux 24.10.1
  onward — which a floating `:latest` does not guarantee. The FRR/Alpine images are multi-arch and fine
  either way. So: **x86-64 is the architecture this tree is built and checked on; on arm64 hosts, treat
  the switch nodes as untested here** (that is a statement about this repo's testing, not a claim about
  Nokia's image). See [Known
  limitations](#known-limitations-read-these-before-you-rely-on-it).
- **`requirements.txt` ships no version constraints.** It lists three packages — `fastapi`, `uvicorn`,
  `pyyaml` — and `install.sh` installs exactly those, unpinned (`pip3 install --break-system-packages
  fastapi uvicorn pyyaml`, with a plain `pip3 install` fallback) — not `pip install -r requirements.txt`.
  The backend also imports `pydantic`, but only for two `BaseModel` subclasses (no validators, no
  `Field`), and it is not named in either file. Nothing here fixes *which* FastAPI you get.
- **The Python floor is 3.10, and nothing here enforces it.** The `python-3.10+` badge above states it;
  `install.sh` installs whatever `python3` `apt` gives the host and never checks the version. The floor
  comes from *runtime* behaviour, not grammar: `backend/main.py` does **not** start with
  `from __future__ import annotations`, so CPython evaluates every function signature and class-body
  annotation at definition time, and FastAPI and pydantic then evaluate the pydantic model fields. Two
  forms in that file break on older interpreters, in that order:
  - **builtin generics (3.9+).** The pydantic models use `competencies: list[str]`, and there are return
    types like `list[tuple[str, str, str]]`, `set[str]` and `dict[str, bool]`. On 3.8 these raise
    `TypeError: 'type' object is not subscriptable` (PEP 585 landed in 3.9).
  - **`X | None` unions (3.10+).** Six annotations are written that way — `dict | None` (line 396),
    `LabDef | None` (674), `str | None` (822), `str | None` and `dict[str, bool] | None` (1243), and
    `str | None` (1288) — and PEP 604 landed in **3.10**. On 3.9 the import dies with
    `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`, before the app serves a request.

  Grammar is not a sufficient test: `ast.parse(..., feature_version=(3, 8))` accepts this file, and so
  does an `ast.parse(..., feature_version=(3, 9))`, because both forms are valid *syntax* there and fail
  only when evaluated. **How this was established:** by reading the annotations with `ast` and counting
  the sites above, and by evaluating each distinct annotation form against the versions that define it —
  **not** by running the backend on a 3.9 interpreter. No 3.9 or 3.8 interpreter exists on the machine
  this was checked on (it has 3.13), so 3.13 is the only version actually executed here, and 3.10 is
  stated as the floor those annotations require, not as a **tested** runtime — treat any specific 3.10
  patch release as unverified until someone runs the install on one.

Those are the requirements, not a tested matrix. **CI does not pin a Python version:**
`.github/workflows/ci.yml` asks
`actions/setup-python` for `python-version: "3.x"`, so each CI run uses whatever the newest 3.x on the
runner is. No Ubuntu version is pinned in `install.sh` either — it installs what `apt` offers.

**CI does not test the floor, either.** Because `"3.x"` resolves to the newest release, CI has never
run the `py_compile` check on 3.10 — the version this README calls the minimum. What the job actually
proves is that the file compiles under whatever 3.x was newest on that run, nothing about 3.10 or 3.11. A regression
that broke a 3.10 host while staying fine on the newest interpreter would pass all four checks. The
fix is a matrix (`3.10` alongside `3.x`) **written and ready to land but not yet pushed**: the
maintainer's automation token can write any other file in this repo and is refused on workflow paths,
so the change needs someone with `workflow` scope to apply it (see
[`CONTRIBUTING.md`](CONTRIBUTING.md#changing-ci)). Until that lands, treat 3.10 support as derived
from the annotations above rather than exercised by CI.

```bash
git clone https://github.com/crperdue73/cirrus-nexus.git aegis
cd aegis
sudo ./install.sh
```

`install.sh` installs Docker, ContainerLab, `ttyd`, and the Python deps
(`fastapi`, `uvicorn`, `pyyaml`), copies the app to `/opt/aegis`, builds the FRR router image from
`Dockerfile.frr` (this tree ships no prebuilt FRR tarball), pre-pulls the switch image, and installs a
systemd service.

Each lab's switch startup config lives in `lab-definitions/<lab>/assets/`, and both shipped topologies
reference it by a path inside their own directory (`startup-config: assets/sw1.cfg`). The installer
copies those per-lab `assets/` folders explicitly and then verifies that **every** `startup-config:` a
shipped topology names actually landed in `/opt/aegis`. If one is missing it says so by name at install
time — because the backend refuses a lab whose startup config it cannot find (the correct behaviour, but
it means one missing folder serves **zero** labs, with the UI coming up empty).

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
| `GET` | `/api` | — | service card: `{"service": "NEXUS", "version": "0.3.0", "labs_count"}` (the version is the API's own, not the release tag's — see [Release status](#release-status)) |
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

Per-route detail — parameters, response fields, the digest fields on a session, and the status-code
contract — is in [`docs/API.md`](docs/API.md). Example: start, grade, stop (the same three calls the UI
makes):

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
same three-outcome rule as the grading model above. Status codes, measured against this tree:

| code | when |
|------|------|
| `200` | the request was answered truthfully |
| `404` | an unknown lab, session, or **session record** — including `submit` on a session id that does not exist |
| `409` | a **refusal**: the system could not make a truthful statement. Covers a node the *lab* does not have (the detail carries the node list), a node that is not running, a substrate that changed since start, and no grader module |
| `422` | a required query parameter is missing (`lab_id` on `start`, `node` on `submit`). FastAPI's own validation, returned before any handler runs |
| `500` | a deploy failed, or a teardown could not complete (a failed teardown leaves the session listed and retryable, and says so in `detail`) |

The distinction that matters: a node the *lab* does not have is a `409`, not a `404`. You asked a
well-formed question and the answer is "that node isn't here" — which is a refusal, not a missing
record. A session id that does not exist *is* a `404`.

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

**v0.2.0 — early release.** The tree is a working, installable teaching platform for its two shipped
labs; it is not a finished product. What that means concretely:

- **`v0.2.0` is the release to install.** Tagged 2026-10-25 and published as a GitHub Release; see
  [`docs/RELEASE-NOTES-v0.2.0.md`](docs/RELEASE-NOTES-v0.2.0.md). `git checkout v0.2.0` before
  `./install.sh` — installing from `main` gives you whatever landed after the tag.
- **`v0.1.0` is not moved.** It was cut 2026-10-09 and is now behind the tip; it is left in place as
  a record of what shipped then rather than force-pushed forward. Four behaviour fixes landed
  between it and `v0.2.0` (`scripts/clab-reaper.sh` twice, `tools/lint_lab_pack.py`, `install.sh`,
  plus Demo 2's prerequisite id), so anyone installing from `v0.1.0` gets the older behaviour. Tag
  position is deliberately not given as a commit count here — a count goes stale with every push.
  Measure it with `git describe --tags`.
- **No screenshots in this README.** Every capture would have to come from a live install; none has
  been taken yet, and none is faked here.
- **Two labs only, static routing only** (see below).

## Known limitations (read these before you rely on it)

- **Static routing only** — see "what this is not," above.
- **A host reboot loses running labs.** Student containers are not restored on boot.
- **A missing lab asset fails the whole catalog, not one lab's switch.** The backend refuses a lab whose
  `startup-config` it cannot find, and that refusal is per-lab — but if every lab is refused the UI
  comes up with no labs at all. `install.sh` now verifies those files exist after installing and warns
  by name; it cannot repair a clone that never had them.
- **Binds to every interface, with no authentication.** The server listens on `0.0.0.0:8000`
  (`AEGIS_HOST` / `AEGIS_PORT` override that, and `install.sh` prints the LAN URL), and every route —
  including `start`, `stop`, and `/docs` — is unauthenticated. That is deliberate for a classroom's
  own network and is **not** safe exposed to the internet. The in-browser terminals (ttyd, ports
  `8765`–`9765`) are similarly open, which is why those ports ship bound to all interfaces too.
- **The SR Linux image is a ~2.35 GB pull**; each switch node runs a full instance of it. Keep to
  **one session per student per lab**; use *Reconnect* for a returning student rather than Start.
- **Architecture is not tested beyond x86-64.** The topologies request
  `ghcr.io/nokia/srlinux:latest` with no `--platform` override and `install.sh` never checks
  `uname -m` for the labs (it reads it only to choose a prebuilt `ttyd` binary). x86-64 is what this
  tree is built and checked on; arm64 switch nodes are untested here.
- **A known image-pin drift:** `Dockerfile.frr` hashes differently from `assets/frr-image.pin`. No
  pinned FRR image tarball ships in this tree (`assets/` tracks only `frr-image.pin`;
  `installed-image-id.txt` exists locally but is git-ignored, so it does not ship), so `install.sh`
  takes its build-from-source fallback and builds
  `aegis/frr:latest` locally from `Dockerfile.frr`. That build is self-consistent but will not match
  the pin's `layers_sha256`. Since 2026-10-27 `install.sh` also prints a warning whenever the pinned
  `dockerfile_sha256` disagrees with the shipped `Dockerfile.frr`, so the drift is stated at install
  time instead of being discovered later; it warns, it does not fail, because the build-from-source
  path is the correct one here. Details in [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

---

## Documentation

| doc | contents |
|-----|----------|
| [`docs/API.md`](docs/API.md) | all 11 routes with their parameters, the two ways people call them wrong, the status-code contract (`404` / `409` / `500`), a three-call walkthrough, exposure, and how to re-check the page against the app |
| [`docs/architecture.md`](docs/architecture.md) | components, diagrams, the lab lifecycle, the grading path, substrates, scope boundaries |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | stopping a session (what a failed stop means), bundle rebuild, runtime digests, concurrency, running without the service, substrate details, known drift |
| [`docs/ADDING-A-LAB.md`](docs/ADDING-A-LAB.md) | what a lab is, the metadata schema, the load-time validation the loader refuses by name, the grader interface |
| [`docs/GRADING-MODEL.md`](docs/GRADING-MODEL.md) | pass / fail / refused, per-node vs lab verdict, the digest gate, the refusal vocabulary |
| [`docs/SELF-CONTAINED.md`](docs/SELF-CONTAINED.md) | what "self-contained" means here, the CI check that enforces it, and exactly what a cold install pulls |
| [`docs/RELEASE-NOTES-v0.2.0.md`](docs/RELEASE-NOTES-v0.2.0.md) | release notes for the current release, `v0.2.0` — **published** |
| [`docs/RELEASE-NOTES-v0.1.0-draft.md`](docs/RELEASE-NOTES-v0.1.0-draft.md) | release notes for `v0.1.0` — **historical draft**; the tag exists, its GitHub Release was never published (see `v0.2.0`) |
| [`CONFERENCE.md`](CONFERENCE.md) | booth-operator cheat sheet (install, ports, troubleshooting, reset) — **draft / not maintained**; install & lab-catalog sections corrected to this tree |
| [`HANDOFF-2026-09-22.md`](HANDOFF-2026-09-22.md) | dated handoff note from a 2026-09-22 demo drive — **historical / not maintained**; counts and lab names in it describe a wider tree than this release (see the banner in the file) |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | the ground rules, and the checks to run before pushing (the same four CI runs) |
| [`SECURITY.md`](SECURITY.md) | how to report a vulnerability privately, the threat model (unauthenticated by design), what's in scope, and the automated checks that exist (four, and no more) |
| [`CHANGELOG.md`](CHANGELOG.md) | what changed, newest first |
| [`10-archive/SUMMARY-for-Dad.md`](10-archive/SUMMARY-for-Dad.md) | dated 2026-06-09 topology audit — **historical**, describes a pre-release layout (see `docs/OPERATIONS.md` → Archive) |
| [`lab-guides/lab-03-lock-it-down.md`](lab-guides/lab-03-lock-it-down.md) | a single student guide for `lab-03-lock-it-down` — **historical / not a shipping lab** (the only file in `lab-guides/`; its lab definition is quarantined); cited by `docs/OPERATIONS.md` as the in-tree source for the capstone's point numbers |
| [`10-archive/`](10-archive/) | an older archive (not the rest of it): `tier-03-bgp-simplified.yml` (an older BGP topology — **not shipped, not deployable here**, since BGP is disabled in the substrate), the two FRR configs it binds under `frr-configs/`, and `SUMMARY-for-Dad.md` (provenance, below) |
| [`docs/GITHUB-PLAN.md`](docs/GITHUB-PLAN.md) | internal, dated maintainer worklog of the repo's documentation-hardening passes — **not product documentation and not a reader's guide** (see below) |
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

The same reading rule applies to [`docs/GITHUB-PLAN.md`](docs/GITHUB-PLAN.md): it is the maintainer's
run-by-run record of what each documentation pass measured and changed. It sits in `docs/` because
that is where the trail lives, not because it describes how to use the product — nothing in the
install, lab, grading or operations path points into it, and it names internal hosts and dated
evidence that only make sense next to the proof files. Start from this README, not from that file.

---

## Contributing & changelog

The one rule that matters is that **everything in this repo must be true** — see
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the ground rules and the exact checks to run before pushing.
Notable changes are recorded in [`CHANGELOG.md`](CHANGELOG.md). CI (`.github/workflows/ci.yml`) runs
those checks on every push and pull request.

---

## Repository metadata

The description, the nine topics and the license shown on the repository's landing page are set in
GitHub's UI or API — they are not files in this repo, so nothing here can contradict them and nothing in
this repo could ever notice them going stale. They are written down in
[`tools/check_repo_metadata.json`](tools/check_repo_metadata.json) with a stated reason per topic, and
[`tools/check_repo_metadata.py`](tools/check_repo_metadata.py) reads this tree and reports every claim
in that record that is no longer true of it (a topic the tree doesn't back, a verified topic the record
has dropped, a description that re-adds OSPF/BGP/EVPN/VPNs the substrate disables, a description that
calls the project finished or carries a count that goes stale, or a license that isn't the one in
`LICENSE`):

```bash
python3 tools/check_repo_metadata.py    # 0 = every claim still holds, 1 = one is false, 2 = it couldn't run
```

The script checks the **record against the tree**, not what GitHub is serving today. To compare the
live values (no token needed for a public repo):

```bash
curl -s https://api.github.com/repos/crperdue73/cirrus-nexus | jq -r '.description'
curl -s -H 'Accept: application/vnd.github+json' \
  https://api.github.com/repos/crperdue73/cirrus-nexus/topics | jq -r '.names | join(", ")'
curl -s https://api.github.com/repos/crperdue73/cirrus-nexus | jq -r '.license.spdx_id'
```

Change a claim in the tree and change the JSON in the same commit. Like
`tools/check_self_contained.py` this tool is **not** wired into CI (CI runs four checks, listed in
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md)); it is a manual re-check for
whoever next touches the repo's front page.

---

## License

[Apache-2.0](LICENSE).
