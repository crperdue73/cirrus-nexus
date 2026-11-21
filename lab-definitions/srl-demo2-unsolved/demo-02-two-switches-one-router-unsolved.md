# Demo 2 (UNSOLVED) — Two Switches and a Router 🖥️🔀📡🔀🖥️

## Objective
Two real switches joined by a real router. **The PCs and the router ship
unconfigured** — your job is to address them so traffic crosses the routed
boundary end to end. Each switch's IRB is applied by that switch's own start-up
commit (that is deliberate: this lab is about the routed path, not about switch
bring-up).

> ⚠️ **Read this before you conclude you misconfigured something.** The IRBs are
> applied by each switch's own start-up commit, so they are only there if that
> commit succeeded. On some hosts the switches boot but reject every commit —
> including the start-up one — with `Unacceptable syslog configuration` /
> `Applications have failed: log_mgr`. When that happens `irb0` never gets
> `10.0.1.254` / `10.0.2.254` and no answer you give can pass. That is a host
> condition, not your config. See **startup commit** below.

## Topology
```
pc-a ── sw1 ── r1 ── sw2 ── pc-b
10.0.1.1   .254   .253|.253   .254   10.0.2.1
   LEFT 10.0.1.0/24     RIGHT 10.0.2.0/24
```
- **sw1** (SR Linux): IRB `10.0.1.254/24` — applied by the switch's **start-up commit**.
- **sw2** (SR Linux): IRB `10.0.2.254/24` — applied by the switch's **start-up commit**.
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
| sw1  | real SR Linux switch, `10.0.1.254/24` up on `irb0.0` | the switch's own start-up commit applied it |
| sw2  | real SR Linux switch, `10.0.2.254/24` up on `irb0.0` | the switch's own start-up commit applied it |
| r1   | both addresses + IP forwarding ON | student config |

> Difference from the *shipped* demo-02: there, the PCs and router arrive
> configured and the lab grades 5/5 with no work. Here they do not, so a cold
> deploy **fails** until the student configures PC-A, PC-B, and r1.

## The switches' start-up commit

The IRBs are not baked into the image. Each SR Linux switch applies its IRB as a
commit during boot, and `log_mgr` verifies rsyslogd before it will accept any
commit. That verification mounts `sysfs` inside the container's `srbase` network
namespace. If the runtime does not permit that mount, the commit fails and the
switch comes up healthy but with **no IRB address** — nothing answering on
`.254`.

How to tell it apart from a mistake of your own, on a switch (this is `sw1`; the
same one-line probe works on `sw2`):

```
set / interface ethernet-1/3 admin-state enable
commit now
```

- **`Commit failed` / `Unacceptable syslog configuration`** — the switch cannot
  commit at all. The lab is unpassable on this host. Nothing you type changes
  that. Tell your instructor; the fix is on the host, not in the lab.
- **commit succeeds** — the switch is fine and a missing `.254` is a real
  finding to work.

This was measured on 2026-11-15 on the reference build host: `ip netns exec
srbase mount -t sysfs sysfs /sys` returns *Operation not permitted*, and every
commit — including a one-line cosmetic one — is rejected by `log_mgr`.

## Tips
- A far-segment switch IRB (pc-a → `10.0.2.254`) does not answer; each switch
  is L2 plus its own subnet gateway. Inter-subnet routing is the router's job.
- On sw1/sw2: `show interface irb0` confirms the IRB is in both `mac-vrf-1`
  and `ip-vrf-1`.
