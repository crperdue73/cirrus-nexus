# Proof — Refusal travels in-band: one state, one shape, both observers

Date: 2026-09-20 ~15:0x EDT (nexus-hourly-drive)
Driver: Selina
Status: SHIPPED + VERIFIED (in-process and over the wire)

## The defect (found by reading the code against its own docstring)

`GraderResult.status` (backend/main.py) documents three states that must not
look alike:

    "graded"  — the grader ran and judged the config.
    "error"   — the grader module raised; NOT a verdict on the student.
    "refused" — no attributable substrate (no runtime digest). The docstring
                states it is "mirrored here so any in-process caller sees the
                same vocabulary."

That last claim was FALSE. The only refusal path was

    _require_runtime_digest(session) -> raise HTTPException(409)

called at the top of `grade_config`. Raising pre-empted every `GraderResult`
construction, so **no code path in the repository could ever produce
`status="refused"`.** The frontend got the refusal state from the HTTP 409
*status code* (frontend/index.html line 652), not from the field. Result: the
same state had two different shapes depending on who observed it —

  - over the wire: HTTP 409 + a JSON `detail` string (no GraderResult at all);
  - in-process   : a raised exception.

Any future batch grader, CLI, or citation/export tool calling `grade_config()`
directly would have to catch HTTPException to see a refusal, and could not
produce a value whose `status` field matched the documented vocabulary. That is
exactly the "same state, different shape" failure the discriminator field was
added to prevent — it was only fixed for one of the two observers.

## Fix (backend/main.py)

Refusal is now a VALUE; the route renders it to 409 so the wire contract is
byte-for-byte unchanged.

  - `_session_runtime_digest(session) -> str` — pure read, never raises. The
    single source of truth for "does this session have an identity".
  - `_refused_result() -> GraderResult` — the one canonical refusal value:
    `status="refused"`, `runtime_digest=""`, passed=False, score=0.0, and a
    single REFUSAL_FEEDBACK line. One factory, so every caller's refusal is
    identical by construction.
  - `grade_config()` — returns `_refused_result()` when the session has no
    digest, instead of raising. Still outside the broad `except`, so the gate
    cannot be swallowed (2026-09-20 regression intact).
  - `submit_config()` (the HTTP route) — translates `grade.status == "refused"`
    to `HTTPException(409)`. Wire contract preserved.
  - `_require_runtime_digest()` kept as a documented deprecated shim for
    `_fallback_grade` and any legacy caller that wants hard-fail; new code uses
    the pure read + factory.

## Verified (executed)

In-process, importing `backend/main.py` directly:

    session "deadbeef" with runtime_digest="" ->
      grade_config(...) -> GraderResult  (type = GraderResult, NOT an exception)
        status         = 'refused'
        runtime_digest = ''
        passed/score   = False 0.0
        feedback[0]    = '⛔ Refused: this session has no runtime digest ...'
    _refused_result().model_dump() == grade_config refusal .model_dump()  -> OK

Wire, same digest-less session:

    submit_config("deadbeef", "r1") -> HTTPException 409   (contract unchanged)

Positive path, session WITH a digest:

    in-process grade_config -> status='graded', digest sha256:bb7ef23a... carried

Live end-to-end over HTTP (real deploy, real containers):

    POST /api/sessions/start?lab_id=lab-04-two-as-peering -> session 789dfcfb
      runtime_digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    POST /api/sessions/789dfcfb/submit?node=r1
      grade.status  = graded ; score 0.35 ; digest sha256:bb7ef23a... carried
    POST /api/sessions/789dfcfb/stop -> destroyed

Static: `py_compile` CLEAN, `py_compile -W error::SyntaxWarning` CLEAN,
`bash -n install.sh` CLEAN.

Cleanup: 0 containers left from proof sessions (789dfcfb, 52bd571c, db2479f9,
954d8aa4 all gone). Ethan's `clab-aegis-two-as-peering-d7776359-*` — 6 Up,
untouched.

## Note — the ledger's named NEXT item (first-grade digest race): CLOSED, not reproduced

The 2026-09-20 composite proof named the smallest open item: "after
/sessions/start, a submit immediately after can read runtime_digest=None before
resolution settles." That was chased this hour and did NOT reproduce.

    Three consecutive start-then-immediately-grade cycles against lab-04:
      session 52bd571c -> start digest sha256:bb7ef23a... ; grade digest present
      session db2479f9 -> start digest sha256:bb7ef23a... ; grade digest present
      session 954d8aa4 -> start digest sha256:bb7ef23a... ; grade digest present

Root cause of the original None was already fixed structurally: the digest is
resolved EAGERLY at `start_lab` (bounded 10s retry in `resolve_runtime_digest`),
so a well-formed session is stamped before start returns, and `grade_config`
now returns a refusal value rather than a digest-less pass-through. A
digest-less grade is no longer representable. The race is closed by
construction — recorded here so the ledger stops carrying it as "open".

## Artifact
backend/main.py — `_session_runtime_digest`, `_refused_result`, `REFUSAL_FEEDBACK`;
`grade_config` returns refusal in-band; `submit_config` translates to 409;
`_require_runtime_digest` retained as a documented shim.
