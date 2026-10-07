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
- [ ] `CITATION.cff`
- [ ] `CITATION.cff` + `.github/ISSUE_TEMPLATE/` + `PULL_REQUEST_TEMPLATE.md`
- [ ] `architecture.md` + a diagram committed as source (mermaid or SVG)
- [x] CI: GitHub Actions (backend compile, `bash -n install.sh`, self-contained check, secret scan)
- [ ] Screenshots: the student UI + a terminal mid-lab (real captures only)
- [x] **Self-contained**: repo proven installable from a bare clone (`tools/check_self_contained.py`)
- [x] `CHANGELOG.md` seeded from history

## Rules for the polish runs

1. One item per run — don't sprawl.
2. Commit with an honest, specific message; push `origin main`.
3. Never claim "complete"/"finished" about Nexus — that's Dad's word alone.
4. If an item needs a screenshot or a decision only Dad can make, note it here and move on.
