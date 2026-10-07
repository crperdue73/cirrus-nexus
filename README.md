# AEGIS — Networking Fundamentals Labs

> **Audience:** High school — Cisco Net Eng I
> **Scope:** Static routing, L2 switching, IPv4/IPv6, device security
> **No dynamic routing.** No BGP. No OSPF. No EVPN. No VPNs.

---

## Quick Start

```bash
git clone <repo-url> aegis && cd aegis
sudo ./install.sh
```

`install.sh` is a one-shot setup for a clean Debian/Ubuntu host. It installs
Docker, ContainerLab, ttyd, and the Python dependencies, copies the app to
`/opt/aegis`, loads the pinned FRR image, and verifies it against the shipped
pin file. Run it as root (or with `sudo`).

Then start the server per **Running the Server** below.

---

## Lab Progression

| # | Lab | Devices | Core Skills | Duration |
|---|-----|---------|-------------|----------|
| 0 | **Foundation** | 2x Alpine + bridge | `ip addr`, `ping`, Ethernet basics | 30 min |
| 1 | **Day 1 Router** | FRR router + Alpine | vtysh CLI, hostname, passwords, interface config | 45 min |
| 2 | **Crossing Subnets** | FRR router + 2x Alpine | Default gateway, traceroute, connected routes | 60 min |
| 3 | **Switch in the Middle** | FRR router + FRR switch + 2x Alpine | L2 vs L3, SVI, MAC learning, full path | 75 min |
| 4 | **Lock It Down** | Same + SSH | SSH, port security, IPv6/SLAAC, subnetting | 90 min |
| 5 | **Capstone** | Same topology | Comprehensive PBM — see below | 90 min |

## Topology Files

Everything needed to run a lab ships in this repository:

- Lab topologies: `lab-definitions/*.yml`
- Graders: `lab-definitions/grader_*.py`

No external directories are required.

## The Shipping Labs

This release ships exactly **two** labs:

| Lab | ID | Topology | Grader |
|-----|----|----------|--------|
| Demo 1 — Two PCs and a Real Switch | `demo-01-two-pcs-and-a-real-switch-unsolved` | `lab-definitions/srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.yml` | `grader_demo_01_srl.py` |
| Demo 2 — Two Switches and One Router | `demo-02-two-switches-one-router-unsolved` | `lab-definitions/srl-demo2-unsolved/demo-02-two-switches-one-router-unsolved.yml` | `grader_demo_02.py` |

Both use **SR Linux** switches (`srlinux` image). The other topologies under
`lab-definitions/` are retained for reference and are not part of this release.

### Editing a grader or topology (important)

Lab definitions are loaded from disk **once**, then **cached in memory** for the
life of the server process. Editing `lab-definitions/grader_*.py` (or a topology
`.yml`) and re-grading a node **will not pick up your change** — grading keeps
using the copy it loaded the first time that lab was graded.

**To make an edit take effect, reload without a restart:**

```bash
curl -X POST http://localhost:8000/api/labs/reload
# -> {"status":"reloaded","count":2}   (the labs on THIS host — a shipped install carries 2)
```

This re-reads the lab definitions and clears the grader cache. Restarting the
service (`systemctl restart aegis`) works too but drops all running labs.

*Why this note exists:* verifying a grader fix without reloading looks like the
fix did nothing. Measured 2026-09-28: with the cache warm, an edited grader kept
returning the old score until `/api/labs/reload` was called; the same edit
applied immediately in a fresh process.

## Release Bundle

`frontend/nexus-release.tar.gz` is the shippable artifact — the product a fresh
host unpacks and installs. It contains exactly the two shipping labs and the
source that runs them:

```
README.md  install.sh  start_server.py  Dockerfile.frr
backend/main.py  frontend/index.html
assets/                                   (aegis-frr-image.tar.gz + frr-image.pin + installed-image-id.txt)
lab-definitions/srl-demo-unsolved/        (demo-01 + its assets/)
lab-definitions/srl-demo2-unsolved/       (demo-02 + its assets/)
lab-definitions/grader_demo_01_srl.py
lab-definitions/grader_demo_02.py
```

**Rebuild it whenever shipping files change** (it is a snapshot, not a symlink to
the tree):

```bash
tar czf frontend/nexus-release.tar.gz \
      --exclude='*.bak*' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='clab-*' \
      README.md install.sh start_server.py Dockerfile.frr \
      backend/main.py frontend/index.html \
      assets/ \
      lab-definitions/srl-demo-unsolved/ lab-definitions/srl-demo2-unsolved/ \
      lab-definitions/grader_demo_01_srl.py lab-definitions/grader_demo_02.py
```

*`--exclude='clab-*'` (added 2026-10-04, run 196):* containerlab writes a LIVE instance directory
inside the lab's own folder — `lab-definitions/<lab>/clab-<lab>-<session>-<node>/` — holding the
switch's runtime config, `authorized_keys`, and TLS **private keys** (`.tls/ca/ca.key`,
`.tls/sw1/sw1.key`, `config/tls/__default__.key.pem`). Because the command names the lab DIRECTORY
rather than individual files, a rebuild done while a session is running sweeps all of it into the
shippable artifact — which is exactly what happened: the tarball grew +38 KB and carried a `ca.key`.
The exclusion makes it impossible instead of merely unlikely. (The product deletes the directory on
stop, so an idle tree never showed this.)

*Assets note (added 2026-09-30):* `assets/` MUST be included — it carries the
~20.7 MB pinned FRR image (`assets/aegis-frr-image.tar.gz`) plus `frr-image.pin`
and `installed-image-id.txt`. The earlier command block omitted it, so a rebuild
would have produced a bundle with **no substrate image** (a cold host could not
install). The shipping bundle has always contained `assets/`; the command did not.

*Why this note exists:* the bundle sat un-rebuilt from 2026-06-13 to 2026-09-28 —
3.5 months stale. It shipped **neither** shipping lab, none of the frontend/backend
fixes, and referenced no current file. It was also referenced by nothing, so
nothing would ever have flagged it. Measured 2026-09-28: the old bundle contained
the old 7-lab set and a June-13 `main.py`/`index.html`.

### Node substrates: what ships, and what is pulled

The two shipped labs need three node images. **Only one of them travels in the bundle:**

| image | who needs it | shipped? |
|---|---|---|
| `aegis/frr:latest` | the router in LAB-B | ✅ shipped as `assets/aegis-frr-image.tar.gz` (52.3 MB), pinned by `assets/frr-image.pin` |
| `ghcr.io/nokia/srlinux:latest` | the REAL switch in both labs | ❌ pulled at deploy time — **~2.35 GB** |
| `alpine:latest` | the PCs | ❌ pulled at deploy time (small) |

`install.sh` (Step 7c) pre-pulls the two registry images **before** creating the service, so a
blocked registry or a slow link fails early with a clear message rather than as a cryptic
containerlab error mid-deploy. On a host with no internet, load them by hand first:

```bash
docker pull ghcr.io/nokia/srlinux:latest alpine:latest
```

**Known drift (latent, documented 2026-10-04):** the on-disk `Dockerfile.frr` hashes
`b3046a70…` while `assets/frr-image.pin` records `cce15a86…`. The shipped **tarball matches the
pin**, so installs are unaffected — this only bites if the tarball is missing AND a host rebuilds
from source, in which case the rebuilt image will differ from the pinned one. Decided 2026-10-04:
leave the shipped artifact alone (rebuilding it risks the thing that currently works) and make the
drift visible here instead.

## Concurrent sessions (verified 2026-10-05, run 203)

**More than one session of the SAME lab may run at once, and they are fully isolated.** Measured
live with two concurrent LAB-A sessions:

| | session 1 | session 2 |
|---|---|---|
| containers | 3 | 3 (distinct names; the session id is in every container name) |
| ttyd ports | 8776-8778 | 8779-8781 — **no collision** |
| grading `pc-a` | `passed=True` (its pc-a was configured) | `passed=False` (its pc-a was untouched) |

Each grade read its own session's container, and stopping one session left the other running with all
its containers. No policy refuses a duplicate start; the UI avoids them by accident rather than by
rule (`Start` replaces the catalog with a deploying notice, and returning students get **Reconnect**
instead of a second Start).

**What this costs:** every session consumes its lab's full container set — LAB-A 3, LAB-B 5 — and each
switch is a ~2.35 GB SR Linux image. Concurrent duplicates multiply that. Nothing caps it, so treat
"one session per student per lab" as the operational convention, and use Reconnect for a returning
student rather than a second Start.

## Runtime digests come in TWO forms (so nothing is compared apples-to-oranges)

Every session carries a `runtime_digest`. It is **not** always `sha256:` — there are two
schemes, and both are honest identity, not a fallback:

| form | when | what it is |
|---|---|---|
| `sha256:<layers>` | the lab includes the **AEGIS substrate** (any `aegis/frr` node) | the pinned substrate's content-addressed layer chain — the same value the FRR pin verifies |
| `aegis-less:<sha256>` | the lab runs **no AEGIS substrate** (e.g. the two-PC demo: alpine + an SR Linux switch, no FRR) | a deterministic hash over each node's `name=layer-chain` pair — there is nothing pinned to verify, so the identity is read off the images the nodes actually run |

For the shipping two labs: **demo-01 (two PCs + a switch, no FRR) → `aegis-less:`** and
**demo-02 (which includes the FRR router) → `sha256:`**. (Verified live 2026-10-02: demo-02's
digest equals the pin's `layers_sha256`.)

**Why this note exists:** the two prefixes are documented in `backend/main.py` comments, but a
consumer comparing digests across labs could reasonably assume they are all `sha256:` and be
misled by the mismatch. Both forms are deterministic and survive a redeploy of the same lab; the
digest changes the moment any node's image changes. A lab whose identity cannot be read off the
running containers at all returns `""` — that is a hard refusal, not a third style.

### FRR image pin vs Dockerfile.frr (known drift, 2026-09-20)

`assets/frr-image.pin` records the substrate `install.sh` loads:
`dockerfile_sha256=cce15a86…`, `layers_sha256=bb7ef23a…`, `tarball=aegis-frr-image.tar.gz`.

The shipped `Dockerfile.frr` now hashes to `b3046a70…` — it was changed by commit
`0503bc5` (2026-09-20, build-time daemon assertions) whose message says
*"Pin/image id unchanged."* The image file was not rebuilt, so **the pin and the
Dockerfile disagree.**

What this means in practice (verified):
- **The pinned path installs cleanly.** `install.sh` loads the shipped tarball and
  verifies against the pin on the loaded image's *label* and *layer chain* — both
  MATCH (`cce15a86…` / `bb7ef23a…`). Tarball sha256 also matches.
- **The rebuild-from-source fallback would produce a different substrate.** A
  `docker build` of the current `Dockerfile.frr` labels the image `b3046a70…`,
  which does not equal the pin's `cce15a86…`.

Not "fixed" here on purpose: choosing which substrate is authoritative (regenerate
the pin? rebuild the image? accept the drift?) is a product decision, not a
reversible lab-local edit. Recorded so the next operator sees both values.

## Running a Lab

```bash
# Deploy (from the repo root, or /opt/aegis after install)
sudo containerlab deploy --topo lab-definitions/srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.yml

# Access a node
docker exec -it clab-<lab-name>-<node> bash

# Tear down
sudo containerlab destroy --topo lab-definitions/srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.yml
```

> Normal operation does not require manual `containerlab deploy` — the server
> deploys and destroys lab topologies for you when a student starts/stops a
> session. The commands above are for troubleshooting a single lab by hand.

## Running the Server

**After `install.sh`, the server runs as a systemd service named `aegis`:**

```bash
systemctl start aegis        # start
systemctl enable aegis       # start at boot
systemctl status aegis       # check
journalctl -u aegis -f       # logs (also written to /var/log/aegis.log)
```

The installer sets `User=aegis`, `WorkingDirectory=/opt/aegis`, and
`ExecStart=python3 /opt/aegis/backend/main.py`, so the service is the supported
way to run the server.

### Running without the service

```bash
cd /opt/aegis
python3 start_server.py          # serves on :8000
```

`start_server.py` is a convenience wrapper: it runs
`pkill -f "ttyd.*docker exec"` and `pkill -f "aegis.*main.py"` before starting
`backend/main.py` in the foreground.

> ⚠️ **The second pattern also matches the running service.** The service process
> is `/usr/bin/python3 .../aegis/backend/main.py`, which `aegis.*main.py` matches
> (verified live 2026-09-28: `pgrep -f 'aegis.*main.py'` returns the service PID).
> Running this script on a host where the service is already up **kills it** — and
> because the service is `Restart=on-failure`, systemd may immediately start a
> *second* server, after which :8000 is contested. **Stop the service first:**
> `systemctl stop aegis` (or `nexus` on the pre-install layout), then run this.
> Use it for troubleshooting or a quick manual start; use the service for anything
> long-lived.

`start_server.py` is portable — it resolves `backend/` relative to its own
location, so it works from any install directory (no path rewriting needed).

> **Note on unit names:** this repository's installer creates `aegis.service`.
> A **full host reboot still loses any running lab** — student lab containers are
> not restored on boot. (Tracked as an open lifecycle item.)

The API is at `http://localhost:8000/api`; the UI is at `http://localhost:8000/`.

## FRR Image

`aegis/frr:latest` — Alpine + FRR with **only** zebra and staticd enabled.
- No OSPF, no BGP — those daemons are disabled in `/etc/frr/daemons`.
- Students configure routers via `vtysh` (Cisco IOS-like CLI).
- Source: `Dockerfile.frr`
- The pinned image ships as `assets/aegis-frr-image.tar.gz` with its pin in
  `assets/frr-image.pin`. The installer loads and verifies it; a cold host does
  not need a registry.

## Capstone — Net Eng I PBM

Performance-based measurement out of 100 points (70 = proficient):

- **Subnetting (27 pts)** — 192.168.12.0/24 → /25 + /28
- **Device Config (67 pts)** — RTR, SW1, PC-A, PC-B
- **Connectivity (6 pts)** — End-to-end IPv4 + IPv6

The Capstone switch uses **Alpine bridge-utils** (not FRR-as-switch). Cleaner L2 behavior, no pretending a router is a switch.

## Scratch / Archive

Anything removed from the active lab set is in `10-archive/` — old FRR configs
and retired topologies. Kept for reference, not deployed and not installed.
