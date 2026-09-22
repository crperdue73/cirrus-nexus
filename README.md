# AEGIS

**A hands-on networking lab platform for the classroom.**

AEGIS runs real network devices — not a simulator — in disposable containers
on a single Linux host. A student opens a browser, gets a live terminal on
every device in the topology, configures it, and presses one button to have
their work graded automatically.

Ships with **one demo lab**. Additional curriculum ships separately as
**lab packs** (see [Lab Packs](#lab-packs)).

> **Product family:** Cirrus · **engine:** AEGIS · **platform:** Cirrus-Nexus
> **License:** Apache-2.0 · **Copyright 2026 CRPerdue Technologies, LLC**

---

## What makes it different

- **Real devices, real commands.** Students type actual Linux and FRR commands
  against actual network stacks. Nothing is mocked.
- **Automatic grading.** Each lab ships a grader that inspects live device
  state and answers a precise question: did the student achieve the goal?
- **Zero student setup.** No VM, no GNS3, no image downloads. The browser is
  the whole client.
- **Disposable by design.** Every session is containers on a throwaway
  bridge. Break it, close it, start again.
- **One-command install.** `sudo ./install.sh` on a clean Debian or Ubuntu
  host. That is the entire setup.

---

## Screenshots

> **TODO:** capture from a running instance and commit to `docs/screenshots/`.
>
> - `01-catalog.png` — the lab catalog
> - `02-terminal.png` — a live lab, three device terminals
> - `03-expanded-terminal.png` — the fullscreen terminal view
> - `04-graded.png` — a passing grade with per-check feedback

---

## Requirements

- Linux host — Debian 12/13 or Ubuntu 22.04/24.04, x86_64
- Root or `sudo`
- Docker (the installer installs it if missing)
- ~2 GB free disk
- One free TCP port for the web UI (default `8000`) and ports `8765+` for
  device terminals

---

## Quick start

```bash
git clone https://github.com/crperdue73/cirrus-nexus.git aegis
cd aegis
sudo ./install.sh
```

`install.sh` installs Docker, ContainerLab, and ttyd, copies the application
to `/opt/aegis`, loads the pinned FRR image, and **verifies it against
`assets/frr-image.pin`** before trusting it. Run it as root, or with `sudo`.

Then:

```bash
sudo python3 /opt/aegis/start_server.py
```

Open **http://127.0.0.1:8000**, pick the demo lab, deploy it, and work in the
terminals.

The installer is idempotent — re-run it to repair an installation or to pick
up a rebuilt FRR image.

---

## Running a lab

1. Open the web UI and choose a lab from the catalog.
2. Press **Deploy**. The topology comes up as containers; a terminal opens for
   each device.
3. Configure the devices per the lab guide.
4. Press **Check My Work**. The grader reports each check and the pass/fail
   result.
5. Press **Close** when finished — the containers are torn down.

**Small screen?** Every terminal has an **⛶ Expand** button. It blows that one
terminal up to fill the screen; press it again or hit **Escape** to return.
Your session is preserved either way.

---

## The demo lab

`lab-definitions/demo-01-two-pcs-and-a-switch.yml`

Two PCs and a switch, all Linux, no routing:

```
   pc-a ────────── switch ────────── pc-b
 10.0.1.1/24   10.0.1.254/24      10.0.1.2/24
```

The student assigns an IP to each PC and a management IP to the switch, then
proves it works by pinging the switch and the other PC from PC-A.

**Pass condition:** both pings from PC-A succeed.

It exercises IP addressing, interface bring-up, L2 forwarding, and ping
verification — with no routing protocol to hide behind. Full walkthrough in
`lab-definitions/demo-01-two-pcs-and-a-switch.md`.

---

## Lab packs

A lab is a **YAML topology** plus a **Python grader**. Both drop into
`lab-definitions/` and are discovered automatically at startup — there is no
registry to edit.

```
lab-definitions/
  my-lab.yml          # topology + metadata
  grader_my_lab.py    # pass/fail logic against live devices
  my-lab.md           # optional student guide, served at /api/labs/<id>/guide
```

A lab's YAML declares its own metadata — course, difficulty, duration,
competencies, gradeable nodes, and required FRR daemons — and the platform
enforces those declarations at deploy time. A lab that requires a daemon the
substrate does not run is refused rather than deployed.

Write a lab, drop in the files, restart the server. Curriculum packs for
Cisco Net Eng I and beyond are distributed separately.

---

## Architecture

```
Browser ──HTTP──▶ FastAPI backend ──docker exec──▶ lab containers
   │                    │
   │                    └── containerlab ──▶ topology deploy/destroy
   │
   └──ttyd (websocket)──▶ one terminal per device
```

- **Backend** — FastAPI (`backend/main.py`). Deploys topologies with
  ContainerLab, serves the catalog, runs graders, manages sessions.
- **Frontend** — a single static page (`frontend/index.html`). No build step,
  no framework, no toolchain.
- **Terminals** — [ttyd](https://github.com/tsl0922/ttyd) attaches to each
  container and streams a real shell into an iframe.
- **Substrate** — `aegis/frr:latest`, Alpine + FRR with zebra and staticd.
  Shipped as a pinned tarball and verified on a transport-invariant
  layer-chain digest before use.

### Ownership and safety

The backend stamps every container it creates with a session label at
creation time. On restart it reconciles only containers bearing that label —
a lab deployed by hand, or by another tool, is **never** adopted, graded, or
torn down by AEGIS. Two labs can run side by side without interfering.

---

## The FRR substrate image

The lab routers run `aegis/frr:latest`: Alpine + FRR, with **only** `zebra` and
`staticd` enabled. No dynamic routing daemons.

The image is **local-only** — it is never pushed to a registry. It ships as
`assets/aegis-frr-image.tar.gz` alongside `assets/frr-image.pin`, which records
its content-addressed layer-chain digest. `install.sh` loads the tarball,
verifies it against the pin, and refuses to proceed on a mismatch. If the
tarball is absent, the installer falls back to building from `Dockerfile.frr`.

Rebuild it yourself with:

```bash
docker build -f Dockerfile.frr -t aegis/frr:latest .
```

---

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `AEGIS_DIR` | `/opt/aegis` | Install location |
| `SERVICE_USER` | `aegis` | Service account |
| `LISTEN_PORT` | `8000` | Web UI port |
| `PYTHON` | `python3` | Interpreter used to run the backend |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `This script must be run as root` | not root | `sudo ./install.sh` |
| Containers are created but the UI shows zero devices | the invoking user is not in the `docker` group | the installer adds both the service user and the invoking sudo user; log out and back in |
| ContainerLab reports no admins | `clab_admins` group missing | the installer creates it; re-run `install.sh` |
| A terminal shows `about:blank` | ttyd failed to attach | check `docker ps`, then restart the session |
| Grading fails with a digest error | image drifted from the pin | re-run `install.sh` to reload and re-verify |
| Port already in use | another server on `8000` | set `LISTEN_PORT` |

---

## Development

There is no build step. Edit `frontend/index.html` or `backend/main.py` and
restart the server.

```bash
python3 backend/main.py            # run directly
sudo python3 start_server.py       # run with ttyd wiring
```

The backend requires `fastapi`, `uvicorn`, and `pyyaml`.

---

## License

Apache License 2.0. See [LICENSE](LICENSE).

Copyright 2026 CRPerdue Technologies, LLC.
