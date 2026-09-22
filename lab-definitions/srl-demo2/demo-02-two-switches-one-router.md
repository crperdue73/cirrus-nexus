# Demo 2 — Two Switches and a Router 🖥️🔀📡🔀🖥️

## Objective
Two real switches joined by a real router. Each switch is an L2 bridge with an
IRB used as its subnet gateway; the router forwards between the two subnets.
Prove the path works end to end from PC-A to PC-B across the routed boundary.

## Topology
```
pc-a ── sw1 ── r1 ── sw2 ── pc-b
10.0.1.1   .254   .253|.253   .254   10.0.2.1
   LEFT 10.0.1.0/24     RIGHT 10.0.2.0/24
```
- **sw1** (SR Linux): IRB `10.0.1.254/24`; e1/1 → pc-a, e1/2 → r1.
- **r1** (FRR): `10.0.1.253/24` and `10.0.2.253/24`, IP forwarding on.
- **sw2** (SR Linux): IRB `10.0.2.254/24`; e1/1 → r1, e1/2 → pc-b.

## Instructions

1. **PC-A**:
   ```
   ip addr add 10.0.1.1/24 dev eth1
   ip link set eth1 up
   ip route add 10.0.2.0/24 via 10.0.1.253
   ```
2. **PC-B**:
   ```
   ip addr add 10.0.2.1/24 dev eth1
   ip link set eth1 up
   ip route add 10.0.1.0/24 via 10.0.2.253
   ```
3. **r1** — address both sides and forward:
   ```
   sysctl -w net.ipv4.ip_forward=1
   ip addr add 10.0.1.253/24 dev eth1
   ip link set eth1 up
   ip addr add 10.0.2.253/24 dev eth2
   ip link set eth2 up
   ```
4. **sw1 / sw2** — the IRB management addresses ship pre-configured.

## Verification
From **PC-A**:
```
ping 10.0.1.254     # sw1 (local switch) — must reply
ping 10.0.1.253     # r1 (the router)     — must reply
ping 10.0.2.1       # pc-b across the router — must reply
```
And back: from **PC-B**, `ping 10.0.1.1` must succeed.

```
traceroute -n 10.0.2.1
```
should show hop 1 = `10.0.1.253` (r1) and hop 2 = `10.0.2.1` (pc-b).

## How this lab is graded
Every one of the five nodes is graded, and the **lab passes only when the
whole path is real end-to-end**:

| Node | Check | Full credit when |
|------|-------|------------------|
| pc-a | `10.0.1.1/24` on `eth1` **and** pings `10.0.1.254` (sw1), `10.0.1.253` (r1), **and** `10.0.2.1` (PC-B across the router) | all three reply |
| pc-b | `10.0.2.1/24` on `eth1` **and** pings `10.0.1.1` (PC-A across the router) | address + ping reply |
| sw1  | **real SR Linux switch** with `10.0.1.254/24` up on `irb0.0` | `sr_cli` fingerprint matches |
| sw2  | **real SR Linux switch** with `10.0.2.254/24` up on `irb0.0` | `sr_cli` fingerprint matches |
| r1   | `10.0.1.253/24` on `eth1`, `10.0.2.253/24` on `eth2`, IP forwarding ON | both addressed + forwarding |

The lab verdict requires **pc-a AND pc-b end-to-end AND both real switches
AND the router** — a Linux PC standing in for a switch is refused, and a
working PC-to-PC path alone is not a pass.

## Tips
- A **far-segment switch IRB** (e.g. pc-a → `10.0.2.254`) does *not* answer:
  each switch is L2 plus its own subnet gateway only and does not route between
  subnets. Inter-subnet routing is the router's job. Same-segment IRB pings
  (pc-b → `10.0.2.254`) and router-side pings (r1 → `10.0.2.254`) do work.
- On sw1/sw2: `show interface irb0` confirms the IRB is in both `mac-vrf-1`
  and `ip-vrf-1`.
