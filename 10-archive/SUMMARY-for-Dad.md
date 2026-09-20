# AEGIS Topology Audit — Summary for Dad 🐧💍

**From:** Selina & Ethan
**Date:** 2026-06-09
**What we did:** Full audit of all 6 ContainerLab topologies in `aegis-topologies/` — complexity, node count, config approach, audience fit.

---

## Overview

We inventoried every YAML, FRR config, grader script, and Dockerfile. The original tiers had ballooned in complexity — Tier 4 (EVPN-VXLAN) was CCNP-level, and several labs used fragile inline exec chains instead of proper config management.

## Changes Made

| Lab | Original | Revised | Why |
|-----|----------|---------|-----|
| **T1 Foundation** | 1a + 1b split | ✅ Kept as-is | Simple, Alpine-only, perfect for absolute beginners |
| **T1 Static Routing** | `tier-01b-static-routing.yml` | ✅ Renamed to `tier-01-static-routing.yml` | Clean naming; content unchanged |
| **T2 OSPF** | 76 lines, inline `sleep 2` exec chains | ⚠️ Split into bind-mounted FRR configs + health-check script | Inline exec is fragile; config binds are realistic and survive restarts |
| **T3 BGP** | 81 lines, 6 nodes, multi-AS iBGP+ eBGP | 🚩 Simplified to 51 lines, 4 nodes, single eBGP peer | First BGP lab shouldn't require understanding two ASes and iBGP |
| **T4 EVPN-VXLAN** | 156 lines, MP-BGP + VXLAN + route reflector | 🛑 Replaced with VLAN trunking + router-on-a-stick (70 lines) | EVPN is CCNP/DC level; replacement teaches 802.1q, PVID, subinterfaces |
| **Capstone** | 86 lines, FRR-as-switch | ⚠️ Pending your call | FRR simulates IOS CLI but confuses switch concepts; Alpine bridge is simpler |

## Pending Decision: Capstone Switch

**Two options:**

1. **FRR on SW1** — Keeps IOS-like CLI (vtysh). Students see familiar `show` commands. But FRR is a router — it doesn't behave like a switch (no MAC table, no spanning-tree).

2. **Alpine bridge-utils on SW1** — Correct L2 switch behavior. Simpler. But CLI is Linux-native, not Cisco-style.

**Our recommendation:** Option 2 (Alpine) for high school audiences. Option 1 (FRR) only if the audience specifically needs Cisco IOS simulation for certification prep.

---

## Files Changed

All files are in `aegis-topologies/` and `frr-configs/`:

- `tier-01-foundation.yml` — unchanged
- `tier-01-static-routing.yml` — renamed from 01b
- `tier-02-ospf.yml` — cleaned up, references bind-mounted configs
- `tier-03-bgp-simplified.yml` — new simplified version (old multi-AS kept as `tier-03-bgp-multi-as.yml`)
- `tier-04-vlan-routing.yml` — new replacement (old EVPN kept as `tier-04-evpn-vxlan.yml`)
- `tier-capstone-neteng.yml` — unchanged, pending decision
- `frr-configs/` — added r1-frr.conf, r2-frr.conf; updated per-router configs for T2/T4
- `scripts/` — added `wait-and-apply.sh` (FRR health-check + IP applier)

---

## Ready When You Are

We can walk through any lab in detail. The old EVPN and multi-AS BGP files are preserved as `*-archive/` for reference.

— Selina 🐧 & Ethan 🔧
