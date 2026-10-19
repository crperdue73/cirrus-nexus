# Release notes — AEGIS v0.1.0 (draft)

**Status: DRAFT — not published.** Per standing rule, no GitHub Release is created without Dad's
explicit OK. This file is the staged text for him to approve, edit, or discard.

- **Tag:** `v0.1.0` (annotated) — **cut and pushed 2026-10-09**, pointing at commit `35e271d`. It does
  **not** point at the current `main` tip: `main` has moved on since. **The commit count is deliberately
  not written here** — earlier revisions published it and it drifted every polish run (37, then 40, then
  43, then 48), so it is measured rather than recited: `git rev-list --count v0.1.0..HEAD`, and
  `git describe --tags` to see how far `main` is past the tag.
  **CORRECTION (2026-10-18):** earlier revisions of this file said those commits were documentation-only
  "so the tagged tree and `main` differ in docs, not in what ships." Measured false by name, not by
  category count — `git diff --numstat v0.1.0..HEAD` shows every non-`.md` path changed in that range:
  `backend/main.py` (+31/−12, **comments and docstrings only** — verified diff read line by line),
  `lab-definitions/grader_demo_02.py` (+3/−3, **docstring only**), `tools/check_self_contained.py`
  (**+11, a new CI guard**), `.gitignore` (+7), and four lab-definition moves into
  `lab-definitions-quarantine-2026-09-30/` (content unchanged, 0/0). So the accurate statement is:
  **`main` adds no runtime behaviour the tag lacks, but it does add a shipped CI guard and moves four
  lab definitions.** The tag remains a true snapshot of the product; it is not byte-identical to what
  CI validates today.
- **How this was checked:** `git show v0.1.0:backend/main.py` compiles (`py_compile`, doraise), so the
  tagged tree is runnable, and the warning paths cited in the "Fixed" section below (frontend mount,
  missing install record, guide-less lab) are all present in the tag at lines 655/2307/2328/2337 — i.e.
  the tag's behaviour was not retroactively falsified by later docs.
- **GitHub Release:** none exists (`GET /repos/crperdue73/cirrus-nexus/releases` → `[]`, measured
  2026-10-17). The tag exists on `origin`; the Release does not.
- **Scope:** the two-lab shipping set — `demo-01-two-pcs-and-a-real-switch-unsolved`,
  `demo-02-two-switches-one-router-unsolved`.
- **Date drafted:** 2026-10-09. **Updated:** 2026-10-17 (tag-pointer statement corrected to the measured
  tag; see below).

---

## AEGIS v0.1.0

First tagged snapshot of the AEGIS lab platform shipping set: a small, self-contained repo with two
graded containerlab labs, installable from a bare clone. Every claim here is backed by a proof under
`.nexus/proofs/`.

### Highlights
- **Two labs, verified end to end.** A student success path passes for both labs (Demo 1 3/3,
  Demo 2 5/5), served guides work when followed literally, and graders discriminate a subtly-wrong
  config rather than rubber-stamping.
- **Survives a restart.** A configured lab keeps grading a passing verdict across a server restart,
  including the full 5-node Demo 2 path.
- **Refuses to lie.** A session without a resolvable runtime digest refuses to grade instead of
  emitting a false verdict.
- **Repo is small and self-contained.** Stale bundle history was purged (the `730 MB → 1.6 MB`
  reduction was measured at that 2026-09 purge, before this history; measured 2026-10-16 the
  `.git` is ~21 MB packed / ~24 MB on disk and the working tree ~4 MB); a bare clone installs; CI
  compiles the backend, syntax-checks `install.sh`, checks self-containment, and scans for secrets.
- **Docs + hygiene.** README for a public audience, `docs/` guides (architecture, adding-a-lab,
  grading model, self-contained, operations), `CONTRIBUTING.md`, `CITATION.cff`, issue/PR templates,
  Apache-2.0 `LICENSE`.

### Fixed
- Cold install could not deploy a lab: containerlab pin corrected 0.60.0 → 0.75.0 (the version the
  labs are verified against).
- A stale shippable bundle could be served (back when a bundle shipped); `tools/check_bundle_fresh.sh`
  guarded it. **Note:** the guard is vestigial in the current tree — no `nexus-release.tar.gz` is
  committed, so the check no-ops ("no bundle present"). The shipping model is now a git clone +
  `install.sh`.
- The session panel could name a substrate the lab does not run; the pinned substrate is now
  surfaced and live-derived.

### Known limitations (named, not hidden)
- `aegis/frr` image is local-only (never pushed to a registry), so cold-host deploy is not yet
  hand-step-free.
- The student browser UI is not smoke-tested end to end (browser policy blocks automated navigation;
  automated runs used the API).
- Static routing only — no BGP/OSPF/EVPN in the shipped labs.

### Not in this release (blocked, awaiting a ruling)
- Screenshots: need a session on the host where AEGIS actually runs (this box is not that host).
- Cosmetic `ci.yml` step: needs a token with `workflow` scope.

**What this is NOT:** not "complete" — that's Dad's call alone.

---

## Weekly roll-up — week of 2026-10-10 → 2026-10-16

**No new version is proposed this week.** The 35 commits since the `v0.1.0` tag contain no product
change: every one is a documentation/provenance correction (retracting stale-bundle claims, replacing
unresolvable `LAB-A`/`LAB-B` nicknames, dropping a pre-history `.git` size, adding historical
disclaimers) plus a single additive CI check. A SemVer/CalVer tag should mark a change to what ships;
there is none to mark here, so drawing one would overstate the week. The week's corrections are
recorded under `[Unreleased]` in `CHANGELOG.md` instead.

Contents, for the record:
- **Stale-bundle claims retracted** on every surface (README, OPERATIONS, CONTRIBUTING, PR template,
  CONFERENCE, CHANGELOG); the guard `tools/check_bundle_fresh.sh` is now labelled vestigial — no bundle
  ships in-tree, the shipping model is a git clone + `install.sh`.
- **`LAB-A`/`LAB-B` retired** in shipped docs *and* source in favour of the real lab names.
- **Pre-history `.git` size (`730 MB → 1.6 MB`) dropped** in favour of the measured current size
  (~21 MB packed / ~24 MB on disk / ~4 MB tree, 2026-10-16).
- **README API table completed** (4 routes); Demo 2 lab-table node count corrected (3 → 5); `.nexus/`
  labelled; quarantined-topology path fixed.
- **CI now byte-compiles shipped lab graders** (`tools/check_self_contained.py`) — a grader syntax error
  fails CI. *(This supersedes the older "blocked on `workflow` scope" note above.)*
- **Hygiene:** orphan root lab YAMLs moved to the quarantine dir; stray BGP-revert backup moved out of
  the shipping lab dir.

### Tag decision (needs Dad)
**A tag already exists:** `v0.1.0` (annotated), cut and pushed 2026-10-09 at `35e271d`. No *new* tag is
proposed from this window, and no GitHub Release has been published for the existing one. Two open calls:

- **Does the existing `v0.1.0` tag stand as the release point?** It is **behind** `main` (all
  non-behavioural, but *not* all documentation — see the tag correction at the top of this file:
  `main` adds a shipped CI guard and moves four lab definitions). Either it stands as-is (the tagged *tree* is the release; later doc
  corrections are not part of v0.1.0), or it is re-pointed / a fresh tag is drawn from current `main`.
- **Marker tag for the honesty sweep, if wanted:** say the word and I'll cut an **annotated,
  non-release** tag (suggestion: `honesty-sweep-2026-10-16`, not a version number) and push it.

Absent a ruling, nothing new is tagged and no Release is published.

---

## Publish checklist (Dad)
1. Decide: keep `v0.1.0` as the release point where it stands, re-point it, cut the non-release marker
   tag above, or name a new version. (No *new* tag is created this week absent your say-so.)
2. Approve / edit the text above.
3. Say the word — I publish the GitHub Release for `v0.1.0` with this body.
4. Until then, **no Release is published** and no new tag is pushed.

> **Correction (2026-10-17):** an earlier revision of this draft said the tag "points at the current
> `main` tip" and implied no tag existed. Measured live: `v0.1.0` exists on `origin` at `35e271d`
> (`git rev-parse v0.1.0`), `main` is ahead of it (`git describe --tags` — the count is quoted with its
> measurement date, or not at all: it has been 37, 40, 43 and 48 across successive runs, which is exactly
> why this file no longer publishes a bare number), and no GitHub Release exists (releases API → `[]`).
> Corrected in place.
