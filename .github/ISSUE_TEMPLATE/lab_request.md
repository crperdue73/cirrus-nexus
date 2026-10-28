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

- Uses only: Alpine hosts / `aegis/frr` / Nokia SR Linux switches (`kind: nokia_srlinux`)
  (yes / no — explain)
- Any new image required? (name + source)
- Static routing or L2 only? (yes / no — if no, out of scope)

## Where the files go

Prefer the shipped layout — a folder per lab under `lab-definitions/`, with the topology,
its guide, and its `assets/` together:

```
lab-definitions/<lab-dir>/<lab-id>.yml   # topology + metadata
lab-definitions/<lab-dir>/<lab-id>.md    # student guide
lab-definitions/<lab-dir>/assets/sw1.cfg # a startup-config the YAML names
```

The loader scans `lab-definitions/*.yml` **and one level of subdirectories**
(`lab-definitions/*/*.yml`), so both layouts load. Graders are **not** nested: put
`grader.py` flat in `lab-definitions/` (both shipped graders do) or in
`backend/graders/`, and name it in the lab's `metadata: grader:` as a bare module name
with no `.py`.

## Definition of done

Per `docs/ADDING-A-LAB.md`, a lab is:

- [ ] the topology YAML (with its `metadata:` block) under `lab-definitions/`
- [ ] a `grade()` grader module, named by the YAML's `grader:` key, plus `grade_all()`
      for the lab-level verdict
- [ ] `python3 tools/check_self_contained.py` exits **0** (it resolves every
      `startup-config:` and every named grader, and byte-compiles the shipped graders)
- [ ] `python3 tools/lint_lab_pack.py` exits **0**, or **2** with a stated reason —
      **2 means PyYAML was missing and nothing was examined, so it is not a pass**
      (exit 1 is the red flag: a lab that grades with zero student work)
- [ ] you started it on a real host, followed your own guide, and confirmed the session
      reaches `submitted`
