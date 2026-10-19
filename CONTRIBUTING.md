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

- A lab is a YAML topology plus a grader. Ship both.
- **Where they go:** the loader scans `lab-definitions/*.yml` **and one level of
  subdirectories** (`lab-definitions/*/*.yml`), so the shipped labs keep the topology,
  the student guide, and `assets/` together in a folder — e.g.
  `lab-definitions/srl-demo-unsolved/` holding `demo-01-two-pcs-and-a-real-switch-unsolved.yml`,
  its `.md` guide, and `assets/sw1.cfg`. Graders are **not** nested: both shipped graders
  sit flat at `lab-definitions/grader_demo_01_srl.py` and `lab-definitions/grader_demo_02.py`,
  and the lab's YAML names its grader as a bare module name (`grader: grader_demo_01_srl`).
- A file is skipped — never loaded as a lab — if its name starts with `.` or contains
  `.bak`, `.stale`, or `.orig`.
- Lab definitions are cached in memory — after editing, `POST /api/labs/reload` (see
  [`docs/OPERATIONS.md`](docs/OPERATIONS.md)).
- Don't commit `*.bak*`, `clab-*/`, `._clean_*`, secrets, or bundled images/tarballs.

## Grading philosophy

A grade is a verdict **only if the node was actually examined.** If the system can't make a truthful
statement (node down, substrate changed, no grader), it must **refuse** — never pass, never silently
fail. Keep that invariant.

## What `lint_lab_pack.py` answers

If you run it (see above), read the output as **green means "no pre-solved lab was detected"**, not
"this lab is correct". It flags exactly one class of failure: a lab whose expected values are already
present in the topology, so the grader would pass with zero student work. Exit status is `0` when nothing
was flagged and `1` when at least one lab was — its final line is the verdict, not the per-lab rows.

## Commits

One change per commit, message says *what* and *why*. Never write "complete" or "finished" about the
project in a commit or doc — release readiness is the maintainer's call, not the code's.

## How a change gets in

This project has no mailing list, no CLA, and no bot that will re-run CI for you. The path is a fork and
a pull request:

1. **Fork** `crperdue73/cirrus-nexus` on GitHub and push your branch to your fork — not to this repo.
   Direct pushes to `main` here are the maintainer's, not a contributor's.
2. **Branch** off `main` with one change on it. `main` is the only active branch; `legacy-orphan-tree`
   is preserved history from the old public tree and is not the place for new work.
3. **Run the four checks** in *Before you push* above. Paste the real output into the PR's
   *How it was verified* section — a summary is not evidence.
4. **Open the pull request** using
   [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md). CI runs on the PR.
5. **Expect a conversation, not an auto-merge.** Small, honest, single-purpose changes land fastest;
   a PR that changes behaviour *and* rewrites the README is hard to check and will usually be split.

If your change is a **new lab**, it is much more likely to be reviewable if it says up front which node
the grader examines, what the exact expected output is, and how you confirmed the lab does **not** pass
before the student does anything.

## Reporting instead of fixing

A precise bug report is as useful as a patch. Use the issue templates (`.github/ISSUE_TEMPLATE/`):
`bug_report.md` asks for the commit, host OS, Docker and containerlab versions, and the exact
`POST /api/sessions/{id}/submit` response, because a grading problem is only diagnosable if we can see
whether it was a pass, a fail, or a **refusal**. `lab_request.md` is for proposing a new lab.

Two things that will be closed as working-as-intended, not bugs: OSPF/BGP/EVPN/VPN being *missing* (the
shipped substrate disables those daemons on purpose), and a lab refusing to grade (a refusal is the
grading model working — see [`docs/GRADING-MODEL.md`](docs/GRADING-MODEL.md)).

## Security

Do not open a public issue for a vulnerability. Read [`SECURITY.md`](SECURITY.md) first — it carries the
reporting route (**contact the maintainer privately**, [@crperdue73](https://github.com/crperdue73),
no public proof-of-concept), the threat model, what is in scope, and what this project checks today.
Note the threat model before you dig: this runs on a single trusted host with no authentication on the
API or the terminals, so "the API has no auth" is a known design boundary, not an undisclosed flaw.
