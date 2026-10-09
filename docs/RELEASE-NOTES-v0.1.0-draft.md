# Release notes — AEGIS v0.1.0 (draft)

**Status: DRAFT — not published.** Per standing rule, no GitHub Release is created without Dad's
explicit OK. This file is the staged text for him to approve, edit, or discard.

- **Tag:** `v0.1.0` (annotated), points at the current `main` tip.
- **Scope:** the two-lab shipping set — `demo-01-two-pcs-and-a-real-switch-unsolved`,
  `demo-02-two-switches-one-router-unsolved`.
- **Date drafted:** 2026-10-09.

---

## AEGIS v0.1.0

First tagged snapshot of the AEGIS lab platform shipping set: a small, self-contained repo with two
graded containerlab labs, installable from a bare clone. Every claim here is backed by a proof under
`.nexus/proofs/`.

### Highlights
- **Two labs, verified end to end.** A student success path passes for both labs (LAB-A 3/3,
  LAB-B 5/5), served guides work when followed literally, and graders discriminate a subtly-wrong
  config rather than rubber-stamping.
- **Survives a restart.** A configured lab keeps grading a passing verdict across a server restart,
  including the full 5-node LAB-B path.
- **Refuses to lie.** A session without a resolvable runtime digest refuses to grade instead of
  emitting a false verdict.
- **Repo is small and self-contained.** 730 MB → 1.6 MB after purging stale bundle history; a bare
  clone installs; CI compiles the backend, syntax-checks `install.sh`, checks self-containment, and
  scans for secrets.
- **Docs + hygiene.** README for a public audience, `docs/` guides (architecture, adding-a-lab,
  grading model, self-contained, operations), `CONTRIBUTING.md`, `CITATION.cff`, issue/PR templates,
  Apache-2.0 `LICENSE`.

### Fixed
- Cold install could not deploy a lab: containerlab pin corrected 0.60.0 → 0.75.0 (the version the
  labs are verified against).
- A stale shippable bundle could be served; bundle freshness is now guarded.
- The session panel could name a substrate the lab does not run; the pinned substrate is now
  surfaced and live-derived.

### Known limitations (named, not hidden)
- `aegis/frr` image is local-only (never pushed to a registry), so cold-host deploy is not yet
  hand-step-free.
- The student browser UI is not smoke-tested end to end (browser policy blocks automated navigation;
  automated runs used the API).
- Static routing only — no BGP/OSPF/EVPN in the shipped labs.

### Not in this release (blocked, awaiting a ruling)
- CI hardening (byte-compile graders): needs a token with `workflow` scope.
- Screenshots: need a session on the host where AEGIS actually runs.

**What this is NOT:** not "complete" — that's Dad's call alone.

---

## Publish checklist (Dad)
1. Approve / edit the text above.
2. Say the word — I publish the GitHub Release from tag `v0.1.0` with this body.
3. Until then, the tag exists in the repo but **no Release is published**.
