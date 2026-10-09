# GITHUB-PLAN — making `crperdue73/cirrus-nexus` professional

**Source of truth:** this tree (`projects/aegis`). `origin` = `github.com/crperdue73/cirrus-nexus`.
The old public history is preserved on branch `legacy-orphan-tree` (the deprecated `aegis-public` fork).

**Rule:** everything in the README and docs must be *true of this tree*. No invented metrics, no
unverifiable claims, no screenshots of a build that isn't here.

---

## Backlog (one item per polish run)

- [x] Promote `projects/aegis` to the shipping tree; push to `origin/main` (2026-10-06)
- [x] Repo description + topics set (networking, containerlab, frr, srlinux, education, …)
- [x] Apache-2.0 `LICENSE` added
- [x] **README hardening** — badges (license, python, containerlab), a real feature list, a text
      architecture diagram, an honest lab table, the grading model (pass/fail/refused), and a
      "what this is / what this is NOT" section (static routing only; no BGP/OSPF/EVPN)
- [x] `docs/OPERATIONS.md` — bundle rebuild, digests, concurrency, running, drift moved out of the README
- [x] `docs/` — adding-a-lab + grading-model guides
      (`docs/ADDING-A-LAB.md`, `docs/GRADING-MODEL.md`, 2026-10-07)
- [x] `CONTRIBUTING.md`
- [x] `CITATION.cff` (2026-10-07)
- [x] `.github/ISSUE_TEMPLATE/` (`bug_report.md`, `lab_request.md`) + `PULL_REQUEST_TEMPLATE.md` (2026-10-07)
- [x] `docs/architecture.md` + diagrams committed as source (mermaid component + lifecycle) (2026-10-07)
- [x] CI: GitHub Actions (backend compile, `bash -n install.sh`, self-contained check, secret scan)
- [ ] CI hardening: extend the compile step to also byte-compile the shipped lab graders
      (`lab-definitions/grader_*.py`) — `backend/main.py` is the only file CI compiles today, so a
      syntax error in a grader would pass CI silently. **BLOCKED 2026-10-09:** the change is written
      and verified (simulated the exact step → STEP OK), but it edits `.github/workflows/ci.yml`, and
      **neither write token carries the `workflow` scope.** The `ghp_` token `origin` uses reports
      scopes `delete:packages, repo, write:discussion, write:packages` (no `workflow`), and GitHub
      rejects the push: *"refusing to allow a Personal Access Token to create or update workflow
      `.github/workflows/ci.yml` without `workflow` scope"*. Do NOT force it. **Dad's call:** mint a
      token with `workflow` scope (or grant `Workflows: write` on the fine-grained PAT), then push.
      The edit was reverted so the tree stays in sync with `origin/main`. — 2026-10-09
- [ ] Screenshots: the student UI + a terminal mid-lab (real captures only) — **BLOCKED, premise
      corrected 2026-10-09.** Original note blamed "no running AEGIS/docker on this box". Measured
      live today (2026-10-09 11:00 UTC on host `dept-dragon-tech`): the true reason is that the
      AEGIS/Nexus platform runs on a DIFFERENT host on a DIFFERENT subnet — this box is
      `192.168.111.40/16`, the recorded lab host is `192.168.1.110:8000` (log runs 16+), and NEITHER
      `127.0.0.1:8000` NOR `192.168.1.110:8000` is reachable from here (both `000`); `nexus.service`
      is not even a unit on this host. So "start it here and capture" was never possible on this
      machine; screenshots need a session on the host where AEGIS actually runs. A mock still
      violates the "everything must be true" rule — do NOT fake it. **Dad's call: either grant a
      route/session to the live host, or accept the item stays open.**
- [x] README hardening pass 2: link the orphaned `docs/SELF-CONTAINED.md` into the Documentation
      table (it existed but was unreachable from the README) — 2026-10-08
- [x] **Self-contained**: repo proven installable from a bare clone (`tools/check_self_contained.py`)
- [x] `CHANGELOG.md` seeded from history
- [x] README hardening pass 3: CI status badge (workflow exists → badge is truthful) + a Contributing
      & changelog section so `CONTRIBUTING.md` / `CHANGELOG.md` are no longer orphaned from the README
      — 2026-10-09

## Run 2026-10-09 11:00 UTC — plan file is here (path correction) + screenshots blocker re-scoped

The morning-plan cron referenced `docs/GITHUB-PLAN.md` relative to the workspace root, but the
file (and `logs/nexus-forward.log`) live under `projects/aegis/`. Recorded here so future runs
find it: **plan = `projects/aegis/docs/GITHUB-PLAN.md`; forward log = `projects/aegis/logs/nexus-forward.log`.**

Tree state measured live this run: `git status` clean except 3 pre-existing `.nexus/` files,
`HEAD..origin/main = 0 0` (nothing to push), CI workflow present, README already carries the CI
badge + Contributing/changelog section (pass 3 committed `1e4b584`). So the polish backlog's only
remaining item is Screenshots, and its blocker premise is corrected above. No in-scope code change
was appropriate today (everything else on this project is product-level and gated on Dad's rulings:
delete 14-vs-12 labs, the `/result` route, `aegis/frr` `ip_forward=1` default, per-lab locking,
restore-on-boot unit). One item, honestly assessed, no manufactured work.

## Rules for the polish runs

> **Push credentials (2026-10-08):** the token in `github.md` is **read-only** — pushes with it return
> `403 Permission denied`. The working write token is in `github2.md`. `origin` in the shipping tree
> is set to that one. If a push 403s, check which token `origin` carries.


1. One item per run — don't sprawl.
2. Commit with an honest, specific message; push `origin main`.
3. Never claim "complete"/"finished" about Nexus — that's Dad's word alone.
4. If an item needs a screenshot or a decision only Dad can make, note it here and move on.
