# Demo — Two PCs and a Real Switch (Cumulus, UNSOLVED) 🖥️🔀🖥️

## Objective
Two computers are connected through a **real Cumulus Linux switch**. The PCs
arrive **unconfigured** — your job is to address them and then prove the lab
works by pinging **both the switch and the other PC** from PC-A.

PC-to-PC working is **not** enough. The switch itself must answer (10.0.1.254).

> This is the unsolved student variant. The switch's bridge SVI
> (`10.0.1.254/24`) ships **pre-configured** on purpose — this lab is about host
> addressing and reaching the switch, not switch bring-up. The PCs start with
> no IPv4 address at all.

## Topology
```
pc-a ──────── sw1 (Cumulus) ──────── pc-b
10.0.1.1/24      10.0.1.254/24        10.0.1.2/24
```
The switch SVI ships pre-configured. The PC addresses do not — that is your work.

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
3. **Prove it from PC-A** — both must reply with **0% loss**:
   ```
   ping 10.0.1.254     # the switch (its bridge SVI)
   ping 10.0.1.2       # PC-B
   ```

## Pass condition
| Node | Requirement | Evidence |
|------|-------------|----------|
| pc-a | `10.0.1.1/24` on `eth1` **and** pings BOTH `10.0.1.254` (switch) and `10.0.1.2` (PC-B) | both pings reply, 0% loss |
| pc-b | `10.0.1.2/24` on `eth1` | address present |
| sw1  | real Cumulus switch, `10.0.1.254/24` on `br0` | shipped pre-configured, real NOS |

**PC-to-PC alone does not count.** The switch must answer its own address.

## Why the switch is real
The grader fingerprints the switch as a real Cumulus Linux system
(`/etc/os-release` NAME="Cumulus Linux" + `/usr/bin/vtysh`), so a plain Linux
bridge pretending to be a switch cannot pass.

- On the switch: `bridge fdb show br br0` should show both PC MACs learnt on
  `eth1`/`eth2` (vlan 1).
- The L3 address lives on the **bridge device itself** (`br0`), not on a
  sub-interface — "L3 on the bridge". That is the SVI.
