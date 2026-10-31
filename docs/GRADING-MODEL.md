# The grading model

A grade in AEGIS is a **verdict only when the node could actually be examined.**
That one sentence drives every rule below. It is also the invariant to keep if you
change anything here.

---

## Three outcomes, three appearances

| outcome | meaning | on the wire |
|---|---|---|
| **pass / fail** | the node was examined and the configuration met / didn't meet the lab's criteria | HTTP `200`, `passed` true/false, `score` in `[0, 1]` |
| **refused** | the system could not make a truthful statement (node down, lab has no such node, substrate changed since start, no grader, no runtime digest) | HTTP `409`, and in-band `status: "refused"` |
| **error** | the grader module itself raised | HTTP `200`, `status: "error"` — **not** a verdict on the student |

`status` is carried in the response body as well as on the wire, so an in-process
caller (batch grader, CLI, export) sees the same three-state vocabulary instead of
an exception to catch.

**Why refusals exist:** a submit racing a teardown used to return
`passed=false, "no output from sr_cli"` — the student was told "wrong" when the
truth was "nobody looked." A refusal says so, in words that name the cause.

---

## What `score` and `passed` actually mean here

Read this before you interpret a number. The two fields are **not** the same claim, and
only one of them is a pass condition.

- **`passed` is the node's verdict, and it is all-or-nothing.** It is true only when every
  check that node was asked succeeded — the shipped graders spell that out per node
  (Demo 1: `passed = ok and reached == len(PING_TARGETS)` for `pc-a`; Demo 2:
  `passed = ok and reached == len(targets)`). It is never derived from the score.
- **`score` is a completion fraction, not a grade.** It is the share of that node's graded
  checks that succeeded, in `[0, 1]`. Because `passed` does not depend on it, **a node can
  carry a positive score and still fail**: Demo 1's `pc-a` scores `0.5` when its address is
  correct and neither ping target answers. (Demo 1's `pc-b` is the sharpest case: it has one
  check, so its wrong address scores `0.0` and its right address also *passes*.)
- **The two shipped graders do not scale `score` the same way, and per-node credit is
  uneven inside a lab.** Demo 1 gives `pc-a` `0.5` for its address plus `0.5` for its two
  ping targets, but gives `pc-b` the full `1.0` for its single address check — a node with
  one check can be worth more than a node with three. Demo 2 gives every node `0.5` for its
  address plus `0.5` for its reachability targets, but *which* targets a node is asked about
  differs by node: `pc-a` is asked for four (two local plus two across the router), `pc-b`
  for one. The number is per-node, per-lab credit — do not compare it across nodes or across
  labs, and do not treat it as a percentage of the exercise.
- **The lab verdict does not read `score` at all.** A session becomes `submitted` only when
  the grader's `grade_all()` returns `passed: true`, and both shipped `grade_all()`s are
  built out of the per-node `passed` flags (`pc-a`/`pc-b`/`sw1` in Demo 1;
  `pc-a`/`pc-b`/`sw1`/`sw2`/`r1` in Demo 2 — see the Coverage section below for the one lab
  whose lab-level condition ignores a node it grades). A node at `score: 1.0` in one lab and
  `score: 0.5` in another can be equally "done".
- **A refusal or an error carries `score: 0.0`.** That zero is the absence of a
  measurement, not a measurement of zero — the same reason `status` exists. Never read it as
  "scored nothing".

If you are writing a grader, the same rule applies from the other side: express the pass
condition with `passed` and use `score` only as feedback about how far along the student is.

---

## Per-node grade vs lab verdict

- **`POST /api/sessions/{id}/submit?node=<node>`** grades **one node** and returns
  the `grade()` result (see [`ADDING-A-LAB.md`](ADDING-A-LAB.md)).
- The session's `status` is **`submitted` only when the grader's lab-level
  `grade_all()` passes** — not when a single node passes. A switch that ships
  pre-configured passes on its own, and that must not submit the lab.

The lab verdict is **tri-state**, and the three states are different facts:

| verdict | session status | meaning |
|---|---|---|
| `True` | `submitted` | the lab's own pass condition is met |
| `False` | `running` | the lab did not pass |
| `None` | `running` | the verdict **could not be computed** |

`None` is not `False`. When `grade_all` fails, or its result fails a consistency
check, the node result is still returned untouched — and the feedback gains a
line:

> ⚠️ The lab-level result could not be computed (&lt;reason&gt;). Your result above
> stands. This is a system fault, not something about your configuration.

A student should never see all-green nodes and a lab that never finishes, with no
explanation (`RUN 225`).

The session record also carries **`status_updated_at`** and **`last_graded_node`**,
so a reader can tell whether a `submitted` verdict is seconds or hours old rather
than being handed an undated claim (`RUN 229`).

---

## Consistency checks on a lab verdict

Before trusting `grade_all()["passed"]`, the backend checks:

1. **Coverage** — the verdict's `nodes` map must include every node the lab
   declares in `gradeable_nodes`. A grader that grades *fewer* nodes than the lab
   claims cannot pass the lab (`RUN 226`).

   > **Measured 2026-10-23: this rule does not fire on a real shortfall — not even
   > for the two shipped graders, which both violate it.** The backend only checks
   > coverage when the grader's returned dict has `passed: true`
   > (`backend/main.py`, `_lab_verdict_passed`). When a node *should* have passed and
   > the grader left it out — the only case where the shortfall can change the
   > verdict — the grader's own `passed` is `false`, so the check is skipped and the
   > mismatch is reported as an ordinary fail. Demo 2 ships exactly that: it declares
   > five `gradeable_nodes` but computes its verdict from four (`pc-a`, `pc-b`, `sw1`,
   > `sw2`) and returns `"nodes": results`, which also holds `r1` — so its map is a
   > **superset** here and the visible check never involved it at all. Reading the
   > code, the check catches a lab that declares *no* nodes (nothing to be short of)
   > or a grader that omits a declared node **and** still reports pass — and no
   > shipped grader does either.
   >
   > What this means for a contributor: **`grade_all()` is where a lab's pass
   > condition is expressed, and nothing below it will catch an omission you make
   > there.** `docs/ADDING-A-LAB.md` therefore states the rule for the grader you
   > write, and this page states the rule the backend actually enforces; they are not
   > the same guarantee. Do not read this section as "the backend has verified your
   > coverage."
2. **Identity** — each result's `node` field must equal the key it is filed under.
   A mislabelled result makes the verdict uncomputable (`RUN 227`).

If either fails, the verdict is `None` (see above). Both shipped graders pass both
checks because they iterate their own declared node list and stamp each result
with the node actually graded. This is why `ADDING-A-LAB.md` asks you to copy the
`_self_identifying` decorator.

---

## The digest gate — a grade is only citable with its substrate

Every session pins a `runtime_digest` at start, read off the running containers
(not a name or a tag — see [`OPERATIONS.md`](OPERATIONS.md)). Grading re-resolves
that digest against the live containers and **refuses if the substrate has changed
since start**:

```
HTTP 409 — The substrate under this session does not match the one it was pinned
to (expected sha256:…, found …), so a grade cannot be cited against it.
```

The session record and the Running-sessions panel carry the same comparison
(`runtime_digest`, `runtime_digest_live`, `runtime_digest_matches`), so a reader can
see *that* a session became unattributable and *what* it changed to.

---

## Refusal vocabulary (what a student can hit)

| situation | message shape |
|---|---|
| node the lab doesn't have | `This lab has no node 'r1' — nothing to grade. The nodes here are: …` |
| node stopped / torn down | `Node 'x' is not running, so it could not be examined — this is not a verdict about your configuration.` |
| node stopped *mid-grade* | `Node 'x' stopped while it was being graded, so the result could not be trusted …` |
| no grader module | `No grader module for this lab — this lab cannot be graded.` |
| substrate changed | `The substrate under this session does not match the one it was pinned to …` |
| no runtime digest | `Refused: this session has no runtime digest, so its state is unattributable …` |

Every refusal names the reason **and** states explicitly that it is not a judgment
of the student's work. Keep both halves when you add one.
