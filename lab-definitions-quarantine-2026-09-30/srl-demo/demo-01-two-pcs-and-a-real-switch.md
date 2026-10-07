# Demo — Two PCs and a Real Switch (SR Linux) 🖥️🔀🖥️

## Objective
Assign IP addresses to two computers connected through a **real switch**, give
the switch its own management address, then prove the lab works by pinging
**both the switch and the other PC** from PC-A.

This is the same job as the plain demo, but the middle device is a real
network OS (Nokia SR Linux), not a Linux PC running a bridge. PC-to-PC working
is not enough — the switch must answer too.

## Topology
```
pc-a ──────── sw1 (SR Linux) ──────── pc-b
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
3. **sw1** — give the switch a management address on its IRB. Open the SR
   Linux CLI (`sr_cli`) and commit:
   ```
   enter candidate
   set / interface irb0 subinterface 0 ipv4 address 10.0.1.254/24
   commit now
   ```
   (The lab ships this pre-configured so the demo is about the pings.)

## Verification
From **PC-A**:
```
ping 10.0.1.254     # the switch itself — must reply
ping 10.0.1.2       # PC-B — must reply
```

Both must succeed, 0% loss. If PC-B answers but the switch does not, the
switch's L2 bridge and its L3 gateway are in different network instances —
the IRB is not a member of the bridge domain.

## How this lab is graded
Every node is graded, and the **lab passes only when the real-switch check
passes too**:

| Node | Check | Full credit when |
|------|-------|------------------|
| pc-a | `10.0.1.1/24` on `eth1` **and** pings BOTH `10.0.1.254` (the switch) and `10.0.1.2` (PC-B) | both pings reply, 0% loss |
| pc-b | `10.0.1.2/24` on `eth1` | address present |
| sw1  | **real SR Linux switch** with `10.0.1.254/24` up on `irb0.0` | `sr_cli` reads the IRB up with the address |

A Linux PC running a bridge **cannot** pass as `sw1` — the grader reads the IRB
through `sr_cli` and refuses. PC-to-PC alone is not a pass.

## Tips
- `ip addr show eth1` on a PC to check its addressing.
- On sw1: `show interface irb0` shows the IRB address and its network-instance
  membership. A working IRB is listed under **both** `mac-vrf-1` (L2) and
  `ip-vrf-1` (L3).
- `show network-instance mac-vrf-1 bridge-table mac-table all` on sw1 should
  list the IRB MAC *and* both PC MACs.
