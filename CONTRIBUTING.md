# Contributing

Thanks for helping with AEGIS. This is a small, honest codebase — a few ground rules keep it that way.

## The one rule that matters

**Everything in this repo must be true.** No invented benchmarks, no "supports X" when it doesn't,
no screenshot of a build that isn't here. If you can't point at the code or a live measurement, don't
write the claim.

## Before you push

Run the same checks CI runs (`.github/workflows/ci.yml` — all four):

```bash
python3 -m py_compile backend/main.py     # 1. backend compiles
bash -n install.sh                        # 2. installer is valid shell
python3 tools/check_self_contained.py     # 3. a bare clone is installable
# 4. no obvious secrets committed — CI greps the tree for token/key patterns
```

`check_self_contained.py` (step 3) is the important one: it fails if a required file is missing, a
lab's `startup-config` or `grader` doesn't resolve, a shipped grader fails to byte-compile, or a
developer's absolute path leaked into source.

The four checks above are exactly what CI enforces on every push and PR. Two further tools exist
for lab authors and are **not** part of CI:

```bash
sudo pip install pyyaml                   # lint_lab_pack.py reads YAML (CI does not install deps)
python3 tools/lint_lab_pack.py            # flags a lab that ships PRE-SOLVED (the answer key)
bash tools/check_bundle_fresh.sh          # served bundle vs. source (no-ops if no bundle present)
```

`lint_lab_pack.py` guards the one failure that has bitten this repo before — a lab whose grader
passes with **zero** student work because the expected values were baked into the topology. It is
not wired into CI (it needs `pyyaml`, which CI does not install, and CI cannot be changed from a
token without `workflow` scope), so **run it by hand when you add or edit a lab.** Both are also
listed in the pull-request checklist.

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
