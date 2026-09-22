# Demo 2 (UNSOLVED) — Two Switches and a Router 🖥️🔀📡🔀🖥️

## Objective
Two real switches joined by a real router. **The PCs and the router ship
unconfigured** — your job is to address them so traffic crosses the routed
boundary end to end. The two switches' IRBs arrive pre-configured (that is
deliberate: this lab is about the routed path, not about switch bring-up).

## Topology
```
pc-a ── sw1 ── r1 ── sw2 ── pc-b
10.0.1.1   .254   .253|.253   .254   10.0.2.1
   LEFT 10.0.1.0/24     RIGHT 10.0.2.0/24
```
- **sw1** (SR Linux): IRB `10.0.1.254/24` — **already configured**.
- **sw2** (SR Linux): IRB `10.0.2.254/24` — **already configured**.
- **r1** (FRR): you must address both sides and enable forwarding.
- **pc-a / pc-b**: you must address them and add the cross-subnet route.

## Instructions (this is the work)

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

## Verification
From **PC-A**:
```
ping 10.0.1.254     # sw1 (local switch)
ping 10.0.1.253     # r1 (the router)
ping 10.0.2.1       # pc-b across the router
```
And from **PC-B**, `ping 10.0.1.1` must succeed. `traceroute -n 10.0.2.1`
should show hop 1 = `10.0.1.253` (r1), hop 2 = `10.0.2.1` (pc-b).

## How this lab is graded
All five nodes are graded; the lab passes only when the whole path works:

| Node | Check | Full credit when |
|------|-------|------------------|
| pc-a | `10.0.1.1/24` on `eth1` AND pings sw1, r1, and PC-B | all three reply |
| pc-b | `10.0.2.1/24` on `eth1` AND pings PC-A | address + ping reply |
| sw1  | real SR Linux switch, `10.0.1.254/24` up on `irb0.0` | shipped pre-configured |
| sw2  | real SR Linux switch, `10.0.2.254/24` up on `irb0.0` | shipped pre-configured |
| r1   | both addresses + IP forwarding ON | student config |

> Difference from the *shipped* demo-02: there, the PCs and router arrive
> configured and the lab grades 5/5 with no work. Here they do not, so a cold
> deploy **fails** until the student configures PC-A, PC-B, and r1.

## Tips
- A far-segment switch IRB (pc-a → `10.0.2.254`) does not answer; each switch
  is L2 plus its own subnet gateway. Inter-subnet routing is the router's job.
- On sw1/sw2: `show interface irb0` confirms the IRB is in both `mac-vrf-1`
  and `ip-vrf-1`.
