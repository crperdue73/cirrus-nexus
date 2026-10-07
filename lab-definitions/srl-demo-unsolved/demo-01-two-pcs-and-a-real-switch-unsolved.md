# Demo (UNSOLVED) — Two PCs and a Real Switch (SR Linux) 🖥️🔀🖥️

## Objective
Two computers through a **real** switch. **The PCs ship unconfigured** — your
job is to address them and prove the path works. The switch (SR Linux) is real
and its IRB arrives pre-configured (that is deliberate: this lab is about host
addressing and reaching the switch, not about switch bring-up).

## Topology
```
pc-a ────────── sw1 (SR Linux) ────────── pc-b
10.0.1.1/24       10.0.1.254/24          10.0.1.2/24
```
- **sw1** (SR Linux): IRB `10.0.1.254/24` — **already configured**.
- **pc-a / pc-b**: you must address them.

## Instructions (this is the work)

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

## Verification
From **PC-A**, prove BOTH:
```
ping 10.0.1.254     # the switch (its management IRB)
ping 10.0.1.2       # PC-B
```
Both must reply. PC-to-PC alone does **not** count — the switch
itself must answer.

## How this lab is graded

| Node | Check | Full credit when |
|------|-------|------------------|
| pc-a | `10.0.1.1/24` on `eth1` AND pings the switch (`.254`) AND PC-B (`.2`) | all reply |
| pc-b | `10.0.1.2/24` on `eth1` | address present |
| sw1  | real SR Linux switch, `10.0.1.254/24` up on `irb0.0` | shipped pre-configured |

**The lab counts as passed when `pc-a` and `sw1` both pass.** PC-B is implied — PC-A cannot
earn credit without reaching it. *(Added 2026-10-04, run 196: LAB-B's guide states its lab-level
rule and this one did not, though the grader has always enforced `pc-a` AND `sw1`.)*

> Difference from the *shipped* demo-01 (SR Linux): there, the PCs arrive
> configured and the lab grades with no work. Here they do not, so a cold
> deploy **fails** until the student addresses PC-A and PC-B.

## Tips
- The switch check reads `irb0` via `sr_cli`, so a Linux bridge pretending to be
  a switch cannot pass — the switch is real.
- On sw1: `show interface irb0` should show the IRB in **both** `mac-vrf-1`
  (L2) and `ip-vrf-1` (L3).
