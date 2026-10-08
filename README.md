# AEGIS — Networking Labs for the Classroom

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3](https://img.shields.io/badge/python-3.x-blue.svg)
![Powered by ContainerLab](https://img.shields.io/badge/powered%20by-containerlab-orange.svg)
![API: FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)

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

| Lab | ID | Topology | Difficulty | Time |
|-----|----|----------|-----------|------|
| **Demo 1 — Two PCs and a Real Switch** | `demo-01-two-pcs-and-a-real-switch-unsolved` | 2 Alpine PCs + 1 SR Linux switch, bridged | Beginner | 25 min |
| **Demo 2 — Two Switches and One Router** | `demo-02-two-switches-one-router-unsolved` | 2 SR Linux switches + 1 FRR router, routed | Intermediate | 35 min |

The other topologies under `lab-definitions/` are retained for reference and are **not** part of this
release (see `lab-definitions-quarantine-2026-09-30/`).

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
and ~3 GB free disk. Only **one** image travels in the repo; the switch image is pulled at install.

```bash
git clone https://github.com/crperdue73/cirrus-nexus.git aegis
cd aegis
sudo ./install.sh
```

`install.sh` installs Docker, ContainerLab, `ttyd`, and the Python deps
(`fastapi`, `uvicorn`, `pyyaml`), copies the app to `/opt/aegis`, loads the pinned FRR image and
**verifies it against the shipped pin**, pre-pulls the switch image, and installs a systemd service.

```bash
sudo systemctl start aegis     # start the server
sudo systemctl enable aegis    # start on boot
sudo systemctl status aegis    # check
```

The UI is at `http://localhost:8000/`; the API at `http://localhost:8000/api`.

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

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/labs` | the served lab catalog |
| `GET` | `/api/labs/{id}` | one lab's definition |
| `POST` | `/api/labs/reload` | re-read lab definitions and clear the grader cache |
| `POST` | `/api/sessions/start` | deploy a lab and open a session |
| `POST` | `/api/sessions/{id}/submit` | grade a node |
| `GET` | `/api/sessions` | running sessions |
| `POST` | `/api/sessions/{id}/stop` | tear down a session |

---

## Development

**Lab definitions are cached in memory.** Editing a grader or topology will not take effect until you
reload:

```bash
curl -X POST http://localhost:8000/api/labs/reload
```

**Rebuild the release bundle** (`frontend/nexus-release.tar.gz`) whenever shipping files change — it
is a snapshot, not a symlink. The exact command, and the reasons behind each exclusion, are in
[`docs/OPERATIONS.md`](docs/OPERATIONS.md).

---

## Known limitations (read these before you rely on it)

- **Static routing only** — see "what this is not," above.
- **A host reboot loses running labs.** Student containers are not restored on boot.
- **The SR Linux image is a ~2.35 GB pull**; each switch node runs a full instance of it. Keep to
  **one session per student per lab**; use *Reconnect* for a returning student rather than Start.
- **A known image-pin drift:** `Dockerfile.frr` hashes differently from `assets/frr-image.pin`. The
  shipped tarball matches the pin, so installs are unaffected; only a rebuild-from-source would
  diverge. Details in [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

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

---

## License

[Apache-2.0](LICENSE).
