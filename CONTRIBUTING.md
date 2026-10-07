# Contributing

Thanks for helping with AEGIS. This is a small, honest codebase — a few ground rules keep it that way.

## The one rule that matters

**Everything in this repo must be true.** No invented benchmarks, no "supports X" when it doesn't,
no screenshot of a build that isn't here. If you can't point at the code or a live measurement, don't
write the claim.

## Before you push

Run the same checks CI runs:

```bash
python3 -m py_compile backend/main.py     # backend compiles
bash -n install.sh                        # installer is valid shell
python3 tools/check_self_contained.py     # a bare clone is installable
```

`check_self_contained.py` is the important one: it fails if a required file is missing, a lab's
`startup-config` or `grader` doesn't resolve, or a developer's absolute path leaked into source.

## Adding or editing a lab

The full contract — file layout, the metadata schema, the load-time validation the
loader refuses by name, and the grader interface — is in
[`docs/ADDING-A-LAB.md`](docs/ADDING-A-LAB.md). The short version:

- A lab is a YAML topology (`lab-definitions/<name>.yml`) plus a grader
  (`lab-definitions/grader_<name>.py`). Ship both.
- Lab definitions are cached in memory — after editing, `POST /api/labs/reload` (see
  [`docs/OPERATIONS.md`](docs/OPERATIONS.md)).
- Don't commit `*.bak*`, `clab-*/`, `._clean_*`, secrets, or bundled images/tarballs.

## Grading philosophy

A grade is a verdict **only if the node was actually examined.** If the system can't make a truthful
statement (node down, substrate changed, no grader), it must **refuse** — never pass, never silently
fail. Keep that invariant.

## Commits

One change per commit, message says *what* and *why*. Never write "complete" or "finished" about the
project in a commit or doc — release readiness is the maintainer's call, not the code's.
