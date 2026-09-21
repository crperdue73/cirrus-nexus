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

## Running a Lab

```bash
# Deploy (from the repo root, or /opt/aegis after install)
sudo containerlab deploy --topo lab-definitions/demo-01-two-pcs-and-a-switch.yml

# Access a node
docker exec -it clab-<lab-name>-<node> bash

# Tear down
sudo containerlab destroy --topo lab-definitions/demo-01-two-pcs-and-a-switch.yml
```

## Running the Server

```bash
cd /opt/aegis
python3 start_server.py          # serves on :8000
```

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
