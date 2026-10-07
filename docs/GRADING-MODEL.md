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
