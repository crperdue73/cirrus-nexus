# Demo 1 — Two PCs and a Switch 🖥️🔀🖥️

## Objective
Two computers connected through a switch. Assign an IP on each PC and a
management address on the switch, then prove the lab works by pinging **both
the switch and the other PC** from PC-A.

No routing, no dynamic protocols. Three devices, three addresses, two pings.

## Topology
```
pc-a ────────── switch ────────── pc-b
10.0.1.1/24   10.0.1.254/24     10.0.1.2/24
```

## Instructions

1. **PC-A**:
   ```
   ip addr add 10.0.1.1/24 dev eth1
   ip link set eth1 up
   ```
2. **PC-B**:
   ```
   ip addr add 10.0.1.2/24 dev eth1
   ip link set eth1 up
   ```
3. **switch** — give it a management address on its bridge (`br0`):
   ```
   ip addr add 10.0.1.254/24 dev br0
   ip link set br0 up
   ```

## Verification
From **PC-A**, both must reply with 0% loss:
```
ping 10.0.1.254     # the switch itself
ping 10.0.1.2       # PC-B
```

## How this lab is graded
All three nodes must be correct:

| Node | Check | Full credit when |
|------|-------|------------------|
| pc-a | `10.0.1.1/24` on `eth1` **and** pings BOTH `10.0.1.254` (the switch) and `10.0.1.2` (PC-B) | both pings reply |
| pc-b | `10.0.1.2/24` on `eth1` | address present |
| switch | `10.0.1.254/24` on `br0` | management address present |

> **Note:** this is the *plain* demo. The middle device is a Linux PC running a
> software bridge, not a network OS. See **Demo — Two PCs and a Real Switch**
> for the version where the switch is a real SR Linux or Cumulus device.

## Tips
- `ip addr show eth1` on a PC to check its addressing.
- On the switch: `ip -br addr` shows the bridge address; `bridge fdb show`
  lists MACs learned in the bridge (both PC MACs should appear).
