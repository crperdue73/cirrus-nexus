# AEGIS — Networking Fundamentals Labs

> **Audience:** High school — Cisco Net Eng I
> **Scope:** Static routing, L2 switching, IPv4/IPv6, device security
> **No dynamic routing.** No BGP. No OSPF. No EVPN. No VPNs.

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

Topologies live in Ethan's workspace at `/home/student/.openclaw/workspace-ethan/aegis-topologies/`.

Lab definitions and graders in Selina's workspace at `projects/aegis/lab-definitions/`.

## Running a Lab

```bash
# Deploy
sudo containerlab deploy --topo /path/to/lab-XX-name.yml

# Access a node
docker exec -it clab-<lab-name>-<node> bash

# Tear down
sudo containerlab destroy --topo /path/to/lab-XX-name.yml
```

## FRR Image

`aegis/frr:latest` — Alpine + FRR with **only** zebra and staticd enabled.
- No OSPF, no BGP — those daemons are disabled in `/etc/frr/daemons`.
- Students configure routers via `vtysh` (Cisco IOS-like CLI).
- Source: `Dockerfile.frr`

## Capstone — Net Eng I PBM

Performance-based measurement out of 100 points (70 = proficient):

- **Subnetting (27 pts)** — 192.168.12.0/24 → /25 + /28
- **Device Config (67 pts)** — RTR, SW1, PC-A, PC-B
- **Connectivity (6 pts)** — End-to-end IPv4 + IPv6

The Capstone switch uses **Alpine bridge-utils** (not FRR-as-switch). Cleaner L2 behavior, no pretending a router is a switch.

## Scratch / Archive

Anything removed from the active lab set is in `10-archive/` — BGP configs, EVPN topologies, and old FRR configs with dynamic routing. Kept for reference, not deployed.
