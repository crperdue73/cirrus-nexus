---
name: Lab request
about: Propose a new teaching lab for the AEGIS bench
title: "[lab] "
labels: enhancement
assignees: ""
---

<!--
AEGIS is a static-routing and L2-switching teaching lab. A proposal is in scope
only if it can be built on the shipped substrate: Alpine hosts, `aegis/frr`
(zebra + staticd only), and Nokia SR Linux switches. Dynamic routing (OSPF/BGP/
EVPN) and VPN labs are out of scope by design.
-->

## The lab

- **Working title:**
- **What the student learns** (one or two sentences):
- **Difficulty / target time:**

## Topology

Nodes and links (text is fine — a small ASCII sketch helps):

```
e.g.  PC1 --- SW1 --- R1 --- SW2 --- PC2
```

## Gradeable outcomes

What must a student's configuration satisfy for a node to **pass**? Each node the
grader examines needs a concrete, checkable criterion. (The grader may also
**refuse** when it cannot make a truthful statement — see `docs/GRADING-MODEL.md`.)

- Node:
  - pass when:

## Substrate check

- Uses only: Alpine hosts / `aegis/frr` / `srlinux`  (yes / no — explain)
- Any new image required? (name + source)
- Static routing or L2 only? (yes / no — if no, out of scope)

## Definition of done

Per `docs/ADDING-A-LAB.md`, a lab is:

- [ ] `lab-definitions/<name>.yml` (topology + metadata)
- [ ] `lab-definitions/grader_<name>.py` (grader interface)
- [ ] passes `python3 tools/lint_lab_pack.py` and `tools/check_self_contained.py`
