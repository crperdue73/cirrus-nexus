# Proof — Step 5: the digest gate was silently swallowed (found + fixed live)

Date: 2026-09-20 ~02:0x EDT (hour 02:00 nexus cron)
Driver: Selina
Status: ONE REAL BUG FOUND + FIXED + VERIFIED IN BOTH DIRECTIONS

## Why this hour, what was left
STATUS.md / the 01:09 composite proof named a first-grade race (runtime_digest
could read None right after start). That race was ALREADY patched earlier in
`resolve_runtime_digest` (bounded 10s retry, eager resolution at start). So this
hour I audited the grade path rather than re-patch it — and found the actual
residual defect, one layer up.

## THE BUG — the step-5 gate could not refuse
`grade_config()` (backend/main.py) called `_require_runtime_digest(session)`
INSIDE its `try: ... except Exception as e:` block. `_require_runtime_digest`
signals refusal by raising `HTTPException(409)` — but `HTTPException` is an
Exception, so the broad handler CAUGHT the refusal and returned a normal
`GraderResult(passed=False, score=0, feedback=["❌ Grader error: 409: ..."],
runtime_digest=<default "")`.

Effect: an unattributable session did NOT get a 409. It got an HTTP 200 carrying
a grade-shaped object with an EMPTY `runtime_digest`. The exact lie step 5 exists
to prevent — "a state cannot be cited without its digest" — was defeated: the
state was returned, citation field blank, caller free to ignore it.

Reproduced by control flow (pre-fix shape, executed):
    pre_fix_grade_config({"runtime_digest": ""}, "r1")
      -> returned HTTPException?  False
      -> returned grade object, runtime_digest = ''      <-- swallow confirmed
      -> feedback: "❌ Grader error: 409: unattributable"

## THE FIX
Moved the digest guard OUT of the try and ABOVE every grader path in
`grade_config`:
    digest = _require_runtime_digest(session)   # top-level; 409 propagates
    grader = _load_grader(...)
    if not grader: return _fallback_grade(...)  # already digest-guarded
    try: ... real grader ...
AST-verified: the `digest` assignment is now top-level in `grade_config`
(line 614), BEFORE the `Try` (line 621). `py_compile` clean.

## VERIFICATION (executed against the real function, both directions)
Harness: imported the real `backend/main.py` in-process; fabricated sessions in
the real `SESSIONS` store.

  UNATTRIBUTABLE session (runtime_digest=""):
    -> HTTP 409: "Session has no runtime digest; state is unattributable and
       cannot be graded. Re-deploy the lab to pin the substrate."   PASS

  ATTRIBUTABLE session (runtime_digest=bb7ef23a...):
    -> grade returned, grade.runtime_digest = sha256:bb7ef23a...   PASS

## LIVE END-TO-END (real topology, real substrate)
App started; deployed Ethan's topology via the product's own path:
    POST /api/sessions/start?lab_id=lab-04-two-as-peering&student_name=Selina
      -> session 00fe39a5, r1..r6 up
      -> session runtime_digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    POST /api/sessions/00fe39a5/submit?node=r1
      -> grade.runtime_digest = sha256:bb7ef23a...   == the install pin. Citable.
    POST /api/sessions/00fe39a5/stop -> destroyed.

Substrate cross-checked against the pin:
    aegis/frr:latest .Id         = sha256:acb8d8dc...  (daemon-local)
    layer chain                  = sha256:bb7ef23a...  (transport identity)
    assets/frr-image.pin         -> layers_sha256 = bb7ef23a...   == MATCH
    image label aegis.frr.dockerfile.sha256 = cce15a86...8f38cf   == MATCH

## ARTIFACT
backend/main.py — `grade_config` digest guard hoisted out of the broad
`except Exception`; the 409 refusal can no longer be swallowed. Edits on disk,
`py_compile` clean.

## NOT DONE / HONEST
- Did not touch Ethan's labs (clab-aegis-two-as-peering-d7776359-r1..r6 still
  Up — verified 6 containers after cleanup).
- The broader `except Exception` in `grade_config` still catches arbitrary grader
  faults and returns a 200 with passed=False. That is acceptable (a grader crash
  is not an attribution failure) but it means a grader bug and a refusal now
  differ only by HTTP code — worth a dedicated error field later. Flagged.
- Exit bar (cold-host install.sh + prototype on real topology + digest recorded)
  was already met; nothing regressed this hour. This hour's work HARDENED step 5
  so a state genuinely cannot be cited without its digest.

## NEXT (smallest real item)
Give `GraderResult` an explicit `error`/`refused` discriminator so a grader-side
failure is distinguishable in-band from a successful read (currently conflated at
the JSON layer when digest is present and grader crashed). Small, contained.
