# Demo — Two PCs and a Real Switch (Cumulus) 🖥️🔀🖥️

## Objective
Assign IP addresses to two computers connected through a **real switch**, give
the switch its own management address, then prove the lab works by pinging
**both the switch and the other PC** from PC-A.

This is the same job as the plain demo, but the middle device is a real
network OS (Cumulus Linux), not a Linux PC running a bridge. PC-to-PC working
is not enough — the switch must answer too.

## Topology
```
pc-a ──────── sw1 (Cumulus) ──────── pc-b
10.0.1.1/24      10.0.1.254/24        10.0.1.2/24
```

## Instructions

1. **PC-A** — assign its address and bring the link up:
   ```
   ip addr add 10.0.1.1/24 dev eth1
   ip link set eth1 up
   ```
2. **PC-B** — same:
   ```
   ip addr add 10.0.1.2/24 dev eth1
   ip link set eth1 up
   ```
3. **sw1** — give the switch a management address on its bridge SVI. In
   Cumulus's standard model, the L3 address goes **on the bridge device
   itself** (`br0`), not on a VLAN sub-interface:
   ```
   ip addr add 10.0.1.254/24 dev br0
   ip link set br0 up
   ```
   (The lab ships this pre-configured so the demo is about the pings.)

## Verification
From **PC-A**:
```
ping 10.0.1.254     # the switch itself — must reply
ping 10.0.1.2       # PC-B — must reply
```

Both must succeed, 0% loss. And from **PC-B**:
```
ping 10.0.1.254     # the switch — must reply
ping 10.0.1.1       # PC-A — must reply
```

## How this lab is graded
Every node is graded, and the **lab passes only when the real-switch check
passes too**:

| Node | Check | Full credit when |
|------|-------|------------------|
| pc-a | `10.0.1.1/24` on `eth1` **and** pings BOTH `10.0.1.254` (the switch) and `10.0.1.2` (PC-B) | both pings reply, 0% loss |
| pc-b | `10.0.1.2/24` on `eth1` | address present |
| sw1  | **real Cumulus switch** (`/etc/os-release` names Cumulus Linux AND `vtysh` present) with `10.0.1.254/24` on its bridge | switch fingerprint matches AND SVI up |

A Linux PC running a bridge **cannot** pass as `sw1` — the grader fingerprints
the OS and refuses. PC-to-PC alone is not a pass.

## Tips
- `ip addr show eth1` on a PC to check its addressing.
- On sw1: `ip -br addr` shows the bridge's address; `bridge fdb show` lists the
  MACs learned in the bridge (both PC MACs should appear).
- If PC-B answers but the switch does not, the L3 address is probably on a VLAN
  sub-interface instead of on the bridge device — move it to `br0`.
- Cumulus ships `vtysh` (FRR); `vtysh -c 'show interface'` is available, though
  this demo is pure L2 + a management SVI and needs no routing config.
