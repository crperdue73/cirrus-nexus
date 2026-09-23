# STATUS — :8000 staleness (escalated by Zoe's independent audit, 2026-09-23 15:30)

**This is a fact for Dad's attention, not a claim of completion.**

## The measurement (live, re-verified)
- Running process: PID on `:8000`, started **Tue Sep 22 16:03:40 EDT 2026**.
- Age as of 15:30 EDT Sep 23: **23h26m** — a full day.
- `backend/main.py` mtime: **Tue Sep 22 23:03:45 EDT** → ~7h NEWER than the process.

## What the live server serves vs. what the tree has
| | live `:8000` | current tree code |
|---|---|---|
| labs | **14** | **16** |
| `demo-01-...-cumulus-unsolved` | absent | present |
| `demo-02-...-cumulus-unsolved` | absent | present |
| `validates_switch_authenticity` field | absent | present (`True` on 4 real-switch labs) |
| grader_tier02_crossing `rtr`/`r1` fix | not live | in tree (line 149) |

## The one-word correction (Zoe, adopted)
Not "a restart *would* surface the current code." **It WILL.** The trigger is
known, the outcome is fixed by code already in the tree. Nothing is in doubt —
only the moment Dad pulls it. This is a **permission**, not a mystery.

## Files
- `stale-8000-vs-fresh-code-20260923-1410.txt` (original proof, fresh :8017 diff)
- `.nexus/proofs/AUDIT-BY-ZOE-SELF-AUDIT-20260923.md` (independent re-check)

**NOT COMPLETE.** Restart is Dad's call. Not forced by me.
