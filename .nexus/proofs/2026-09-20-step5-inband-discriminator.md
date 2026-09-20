# Step 5 close-out — in-band GraderResult discriminator

**Date:** 2026-09-20 (hour of ~10:0x EDT)
**Commit:** c1746f8
**Item:** last named open product item in .nexus/STATUS.md
**Files:** backend/main.py, frontend/index.html

## What was actually wrong

Two defects, both client-visible. Neither was cosmetic.

**1. Digest drop on grader crash.** `grade_config()`'s `except Exception` branch
returned:

    GraderResult(passed=False, score=0, feedback=[f"❌ Grader error: {e}"], competencies=[])

No `runtime_digest`. That is an **unattributed grade emitted from the error path**
— the precise state the Step 5 invariant ("a state cannot be cited without its
digest") exists to forbid. The sibling leak on the 409 refusal path had been
fixed in the "gate-swallow" hour; this one was still open.

**2. No in-band discriminator.** A grader crash and a legitimately failing config
both rendered as `❌ Not yet 0%`. Three different meanings (grader ran / grader
broke / cannot grade at all) collapsed into one string. The operator could not
tell a broken grader from a bad student answer, and the student was told they
failed when the read was void.

## Fix

`GraderResult.status: str = "graded"` with three values:

| status    | meaning                                            | surfaced as |
|-----------|----------------------------------------------------|-------------|
| `graded`  | grader ran and judged; passed/score are meaningful  | 200 + grade |
| `error`   | grader module raised; read is VOID, not a verdict   | 200, no score, styled apart |
| `refused` | no attributable substrate (no digest)               | HTTP 409 |

- except-path now passes `runtime_digest=digest, status="error"`.
- frontend handles `resp.status === 409` explicitly (previously fell straight
  through to `data.grade` and would throw), and renders three distinct states.
- `.grade-result.error` / `.grade-result.refused` styles added.

## Verification (executed, not asserted)

- `python3 -W error::SyntaxWarning -m py_compile backend/main.py` → clean
- `node --check` on the extracted `<script>` blocks → clean
- LIVE HTTP deploy, lab `tier-02-router-basics`, session `26341b0a`:
  - start → `runtime_digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c`
    (== `assets/frr-image.pin` `layers_sha256`; == live-deployment record)
  - `POST /api/sessions/26341b0a/submit?node=r1` → **HTTP 200**,
    `status='graded'`, `score=0.35`, digest carried, real grader feedback
- refused: session with `runtime_digest=""` → `HTTPException 409`
- error  : synthetic grader raise → `status='error'`, digest **preserved**
- test session stopped + destroyed → **0 leftover containers**
- git staged exactly `backend/main.py` + `frontend/index.html`; guard confirmed
  no tarball / clab state / db / pin-artifact staged

Not touched: Ethan's lab containers.

## Step board after this hour

1. Build gate (Dockerfile-hash label) — DONE
2. Cold rebuild + running-container digest — DONE
3. Deploy against real topology — DONE
4. Cold-host install.sh landing current digest — DONE
5. Runtime pin wired into app + in-band discriminator — **DONE (this hour)**

All five exit-bar steps done. Remaining named items in STATUS.md: none blocking.
This closes the last one.
