# Demo 2 (Cumulus, UNSOLVED) — Two Switches and a Router 🖥️🔀📡🔀🖥️

## Objective
Two computers sit on two **different subnets**, each behind its own **real
Cumulus Linux switch**, with a **router** in the middle joining the subnets.
Your job is to address the two PCs and the router, then prove the path works
**end to end** — PC-A all the way to PC-B across the routed boundary.

The two switches' bridge SVIs (`10.0.1.254` and `10.0.2.254`) ship
**pre-configured** on purpose — this lab is about the routed path, not switch
bring-up.

## Topology
```
pc-a ── sw1 (Cumulus) ── r1 (router) ── sw2 (Cumulus) ── pc-b
10.0.1.1/24   SVI .254     .253 | .253    SVI .254   10.0.2.1/24
   LEFT subnet 10.0.1.0/24        RIGHT subnet 10.0.2.0/24
```

## Instructions

1. **PC-A** — address, bring up, and route to the far subnet:
   ```
   ip addr add 10.0.1.1/24 dev eth1
   ip link set eth1 up
   ip route add 10.0.2.0/24 via 10.0.1.253
   ```
2. **PC-B** — same, mirrored:
   ```
   ip addr add 10.0.2.1/24 dev eth1
   ip link set eth1 up
   ip route add 10.0.1.0/24 via 10.0.2.253
   ```
3. **r1 (the router)** — an address on each side, and turn on forwarding:
   ```
   ip addr add 10.0.1.253/24 dev eth1
   ip link set eth1 up
   ip addr add 10.0.2.253/24 dev eth2
   ip link set eth2 up
   sysctl -w net.ipv4.ip_forward=1
   ```
4. **Prove it from PC-A** — all three must reply:
   ```
   ping 10.0.1.254     # sw1 (the local switch's SVI)
   ping 10.0.1.253     # r1 (the router)
   ping 10.0.2.1       # pc-b ACROSS the router
   traceroute -n 10.0.2.1   # hop 1 = r1, hop 2 = pc-b
   ```
5. **And back from PC-B:** `ping 10.0.1.1` must reply.

## Pass condition
| Node | Requirement |
|------|-------------|
| pc-a | `10.0.1.1/24` on `eth1` **and** pings sw1 SVI, r1, **and** PC-B across the router |
| pc-b | `10.0.2.1/24` on `eth1` **and** pings PC-A back across the router |
| r1   | `10.0.1.253/24` + `10.0.2.253/24` up, `ip_forward=1` |
| sw1  | **real Cumulus switch**, `10.0.1.254/24` on `br0` (SVI) |
| sw2  | **real Cumulus switch**, `10.0.2.254/24` on `br0` (SVI) |

Both switches must be **real**. The grader fingerprints Cumulus
(`/etc/os-release` + `vtysh`), so a plain Linux bridge replacing a switch
fails — and the lab verdict requires **all** nodes, not just the hosts.

## Why the switches are real
Same reasoning as demo-01 (Cumulus): the L3 address lives on the **bridge
device itself** (`br0`), the SVI — "L3 on the bridge", not on a sub-interface.
The switch also runs the real Cumulus userland (`/etc/os-release` +
`/usr/bin/vtysh`).
