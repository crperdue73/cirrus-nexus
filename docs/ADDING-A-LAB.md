# Adding a lab

A lab is **two files**: a YAML topology with a `metadata:` section, and a Python
grader. `backend/main.py` discovers the YAML, validates it, and serves it through
the API; the grader is imported on demand and must implement a two-function
interface.

This page documents the contract the loader **actually enforces**. Every rule
below was added because a lab that broke it shipped quietly — the `RUN nnn`
references point at the measurement in `.nexus/proofs/`.

---

## Where the files live

```
lab-definitions/
  srl-demo-unsolved/
    demo-01-two-pcs-and-a-real-switch-unsolved.yml   # topology + metadata
    demo-01-two-pcs-and-a-real-switch-unsolved.md    # student guide (optional)
    assets/
      sw1.cfg                                        # a startup-config the YAML names
  grader_demo_01_srl.py                              # the grader
```

- The loader scans `lab-definitions/*.yml` **and one level of subdirectories**
  (`lab-definitions/*/*.yml`), so a lab can keep its topology, its guide, and its
  `assets/` together in one folder.
- A file is skipped if its name starts with `.`, or contains `.bak`, `.stale`, or
  `.orig`. Backups never load as labs.
- `topology_file` is stored **relative to `lab-definitions/`**, so the deploy copy
  resolves, and containerlab resolves a node's `startup-config` relative to the
  topology file's own directory.
- A lab's **guide** is found in this order: the `_GUIDE_MAP` table, then
  `lab-definitions/<id>.md`, then `lab-definitions/<topology-dir>/<id>.md`. A lab
  with no guide still works — it just warns at load (see below).

---

## The metadata section

```yaml
metadata:
  id: demo-01-two-pcs-and-a-real-switch-unsolved   # REQUIRED — the lab id, unique
  name: "Demo 1 — Two PCs and a Real Switch"
  description: >
    One or two sentences a student sees in the catalog.
  difficulty: Beginner
  duration_min: 25                                  # integer, minutes
  course: CI-DEMO
  competencies:
    - IP addressing on a host
    - L2 bridging vs L3 gateway on a switch
  instructions:                                     # per-step strings shown to the student
    - "Assign an IP: ip addr add 10.0.1.1/24 dev eth1"
    - "Bring the interface up: ip link set eth1 up"
  tip: ""
  gradeable_nodes: [pc-a, pc-b, sw1]                # must be a subset of the topology's nodes
  grader: grader_demo_01_srl                        # module name, NO .py
  requires_daemons: []                              # FRR daemons the substrate must run, e.g. [bgpd]
  validates_switch_authenticity: true               # the middle device must be a real switch OS
```

Field notes:

- **`id`** is the only strictly required key. A YAML with no `metadata:` (or no
  `id`) is skipped silently — it simply isn't a lab.
- **`duration_min` must be a number.** A wrong type (e.g. `soon`) used to crash the
  whole service at import; it no longer does, but the lab is still refused.
- **`gradeable_nodes`** is the set of nodes the UI offers a *Check* button for. It
  may name only nodes the topology defines.
- **`grader`** defaults to `grader_<id>` when omitted — always ship it explicitly.
- **`requires_daemons`** is enforced at deploy time against the substrate's own
  `/etc/frr/daemons`, so a lab can never be deployed onto a substrate that could
  only ever grade it red.
- **`validates_switch_authenticity`** makes the deployed switch's *identity* a
  graded requirement (the grader uses `sr_cli`), so a Linux PC running a software
  bridge cannot pass as a switch.

---

## What the loader REFUSES — by name

`_reload_labs()` runs at import and on `POST /api/labs/reload`. It validates
**each lab on its own**: a bad definition is **refused by name, logged, and
skipped**, and the valid labs keep serving. One bad file can no longer take the
product down (it used to — `RUN 222`).

A lab is refused when:

| condition | example error |
|---|---|
| the topology file cannot be read | `topology unreadable: <file>` |
| a `startup-config` resolves **outside the lab's own directory** | `startup-config for sw1 resolves outside the lab directory (../../x.cfg)` |
| a `startup-config` names a **file that does not exist** | `startup-config for sw1 names a file that does not exist: assets/sw1.cfg` |
| `gradeable_nodes` names nodes the topology does **not** define | `gradeable_nodes names nodes the topology does not define: ghost1` |
| a `LabDef` field has the wrong type | `1 validation error for LabDef` |
| the YAML does not parse at all | `while parsing a flow sequence` (reported for the *file*) |

The refusal is visible in the reload response:

```json
{"status":"reloaded with skips","count":1,
 "skipped":[{"id":"demo-02-…","error":"gradeable_nodes names nodes the topology does not define: ghost1"}]}
```

…and in the operator log (`[labs] REFUSED malformed lab definition …`).

A **missing guide is a warning, not a refusal** — a lab with no `.md` still
starts, still grades, and can still be submitted; only the *Lab Guide* button
404s. The log says so by name so a student never has to discover it.

---

## The grader module

The grader is a Python module in `lab-definitions/` (or `backend/graders/`). The
loader imports it **by resolved path, required to sit inside one of those two
directories** — a `grader:` value containing `..` is refused, because a lab
definition is *data* and must not be able to execute code from anywhere on the
filesystem (`RUN 236`).

A grader exports two functions.

### `grade(session, node) -> dict`

Grades **one node**. `session` is the live session dict; `session["nodes"]` is the
`{node: container_name}` map. Return:

```python
{
    "passed": bool,
    "score": float,           # 0.0 … 1.0
    "feedback": [str, ...],   # one line per check; shown to the student verbatim
    "competencies": [str, ...],
}
```

If a check cannot run at all (device unreachable, interface missing), **refuse** —
return `passed=False` with feedback that names the reason, or raise. The backend
turns an unexaminable node into a refusal, never a silent fail. Do not invent a
fallback grade: a wrong answer and "nobody looked" must not look alike.

### `grade_all(session) -> dict`

The **lab-level verdict** — the product's real success condition.

```python
{
    "passed": bool,
    "nodes": {node: <grade(session, node) result>, ...},   # must cover gradeable_nodes
    "summary": "one line",
}
```

The backend uses this for the session's `submitted` status, and enforces two rules
on the result (`RUN 226` / `227`):

- **`nodes` must cover every `gradeable_nodes` entry.** A lab cannot pass while a
  declared node was never checked.
- **each result's `node` field must match the key it is filed under.** A result
  filed under the wrong name makes the verdict *uncomputable*, not passing.

Both shipped graders wrap `grade` with a `_self_identifying` decorator that stamps
`result["node"] = node` at the point of grading; copy that pattern.

---

## After you edit a lab: reload

Lab definitions and graders are **cached in memory for the life of the process**.
Editing a `.yml` or a `grader_*.py` does nothing until you reload:

```bash
curl -X POST http://localhost:8000/api/labs/reload
```

Then verify the honest way: start the lab, follow your own guide through the
terminals, and confirm every node you declared grades and that the session reaches
`submitted`. See [`GRADING-MODEL.md`](GRADING-MODEL.md) for the verdict rules your
grader must honor, and [`OPERATIONS.md`](OPERATIONS.md) for the cache, the bundle, and the
reload command.
