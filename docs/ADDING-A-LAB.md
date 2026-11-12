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
  grader_demo_01_srl.py                              # the grader (flat, NOT inside the lab folder)
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
- **`grader`** defaults to `grader_<id>` when omitted, where `<id>` is the lab's **`metadata.id`**
  (e.g. `grader_demo-01-two-pcs-and-a-real-switch-unsolved`), *not* its folder or file name. Because a
  shipping lab id is usually a sentence, the default almost never resolves — `_load_grader` looks for
  `<name>.py` in `lab-definitions/` and `backend/graders/`, and a missing module silently falls back to
  the built-in IP/ping grade. Both shipped labs set `grader:` explicitly, and so should you.
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
| a `startup-config` resolves **outside the lab's own directory** | `startup-config for sw1 resolves outside the lab directory (../../x.cfg)` |
| a `startup-config` names a **file that does not exist** | `startup-config for sw1 names a file that does not exist: assets/sw1.cfg` |
| `gradeable_nodes` names nodes the topology does **not** define | `gradeable_nodes names nodes the topology does not define: ghost1` |
| a `LabDef` field has the wrong type | `1 validation error for LabDef` |
| the YAML does not parse at all | `while parsing a flow sequence` (reported for the *file*) |

### …and one row that is NOT true yet

This table used to list **`topology unreadable: <file>`** as a refusal. It is
not one — the guard is **effectively unreachable**. `backend/main.py:632` raises
that string when `_topology_node_names()` returns `None`; but the loader stores
a lab's `topology_file` as **the lab file's own path**, so `None` requires the
lab *file* to be unreadable — and those are already dropped by the earlier
unparseable-YAML guard (`RUN 240`), before this check runs.

**Measured 2026-11-09** against a copy of `lab-definitions` (three shapes):

| shape | measured result |
|---|---|
| topology parses, no `metadata:` block | never discovered — guard never runs |
| lab file itself unreadable | refused by `RUN 240` (`UNPARSEABLE`), not by this guard |
| `topology.nodes` is a **list** of mappings | refused by the `gradeable_nodes` guard instead |
| `topology:` is a **list**, not a mapping | **`AttributeError` in `_substrate_image_for` (main.py:444) — discovery crashes** |

The last row is a real product bug, and fixing loader behaviour is the
operator's call, not a docs run's. Use the linter in the meantime: it now
answers `NO-TOPOLOGY` (exit 2) for a lab whose own topology is missing,
unparseable, or defines no nodes, instead of the green `UNSOLVED` it used to
print for exactly those labs:

```sh
python3 tools/lint_lab_pack.py --labs-dir lab-definitions   # NO-TOPOLOGY = nothing was examined
```

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
    "score": float,           # 0.0 … 1.0 — SHARE OF THIS NODE'S CHECKS, not a grade;
                              #   `passed` must not be derived from it (see GRADING-MODEL.md)
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

The backend uses this for the session's `submitted` status. `_lab_verdict_passed()`
enforces two rules on the result, and **both are hard today** (`RUN 226` / `227`,
re-read against the source 2026-11-12):

- **`nodes` must cover every `gradeable_nodes` entry.** A lab cannot pass while a
  declared node was never checked. A missing node makes the verdict
  **uncomputable** — `None`, not a fail: the session stays `running` and the
  student's node result comes back with a note that the lab-level result could not
  be computed and that this is a system fault, not their configuration. See
  [`GRADING-MODEL.md`](GRADING-MODEL.md) → *Consistency checks on a lab verdict*.
- **each result's `node` field must match the key it is filed under.** A result
  filed under the wrong name makes the verdict *uncomputable*, not passing.

Both checks run on the returned `nodes` map regardless of whether your verdict says
`passed: true` — there is no "only checked on pass" shortcut left. Neither is a
substitute for your own verdict, though: coverage says every declared node was
*reported on*, not that passing required it. **`grade_all()` is where the lab's pass
condition lives**, and nothing below it reads your intent.

Both shipped graders wrap `grade` with a `_self_identifying` decorator that stamps
`result["node"] = node` at the point of grading; copy that pattern.

---

## What the pre-solved linter can see

`tools/lint_lab_pack.py` judges a lab by comparing **the IPs your grader expects the
student to apply** against **the IPs already in the topology's `exec:` lines**. That
makes the grader's expectation map a contract with the linter, not just with the
backend:

| The linter reads | Shape | Notes |
|---|---|---|
| `EXPECTED` | `{node: {"ip": ..., "dev": ...}}` or `{node: ip}` | legacy/PC expectations |
| `ROUTER_EXPECTED`, `ROUTERS`, `ROUTER`, `ROUTER_IPS` (first that exists) | `{node: [(dev, ip), ...]}` | router interface addresses, also student work |
| module AST fallback | string→IPv4 dict literals | used only when no map above is found |

Switch-management addresses are **not** read: a switch ships with its IRB seeded by
design, and counting it would manufacture false red flags.

Two consequences worth knowing:

- A grader that keeps its expectations in some other shape is judged by the AST
  fallback or not at all. The tool does not guess: an unreadable grader is reported
  as such. **Until 2026-11-08 it looked for `ROUTER_EXPECTED` alone** — a name no
grader in this tree uses — so Demo 2's router was never examined, and a lab with the
router's whole answer key pre-applied read as `PARTIAL`, never as the red flag.
- The linter is regression-tested against canary labs in
  `tools/canaries/lab-pack/`: `sh tools/canaries/check_lint_canaries.sh` asserts one
expected verdict per canary. Add a canary when you find a shape the tool misreads —
a passing run over the real tree alone cannot tell you the tool still reads anything.
- The pack's own list (`tools/canaries/lab-pack/README.txt`) is checked against the pack by
`python3 tools/check_canary_pack.py`: every canary file must have a row there whose verdict matches
the file name. That check exists because the list fell two labs behind the pack and nothing noticed.

---

## After you edit a lab: reload

Lab definitions and graders are **cached in memory for the life of the process**.
Editing a `.yml` or a grader module does nothing until you reload (a grader may be named
anything — `grader_*.py` is the convention, not a loader rule):

```bash
curl -X POST http://localhost:8000/api/labs/reload
```

Then verify the honest way: start the lab, follow your own guide through the
terminals, and confirm every node you declared grades and that the session reaches
`submitted`. See [`GRADING-MODEL.md`](GRADING-MODEL.md) for the verdict rules your
grader must honor, and [`OPERATIONS.md`](OPERATIONS.md) for the cache, the bundle, and the
reload command.
