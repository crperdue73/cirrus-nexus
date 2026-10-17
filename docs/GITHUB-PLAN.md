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
- [x] CI hardening: byte-compile the shipped lab graders (`lab-definitions/grader_*.py`). **CLOSED via an
      unblocked route 2026-10-10:** `backend/main.py` is the only file CI compiles today, so a syntax
      error in a grader would pass CI silently — moved the guarantee into `tools/check_self_contained.py`
      (already a CI step), which now byte-compiles every `lab-definitions/grader_*.py` and fails by name.
      Proven both ways (clean → rc=0; injected syntax error → rc=1 naming the file/line). Push accepted,
      no `workflow` scope required. Residual slice — *also* adding the explicit step to `ci.yml` — stays
      blocked on the `workflow`-scoped token (Dad's call) and is now cosmetic, not load-bearing.
- [x] `CONFERENCE.md` truth pass: it was orphaned and its install step named a bundle that does not
      ship (`tar xzf aegis-portable.tar.gz`) plus a stale API response shape; corrected to the real
      clone+install flow and linked from the README — 2026-10-14
- [x] README hardening pass 6 (2026-10-17): **release-status badge + section** (v0.1.0, early release,
      no GitHub Release published, no screenshots) and a **service-name note** (`aegis.service` vs the
      product name NEXUS). Both gaps were real: the front page had no maturity signal at all, and the
      repo/README/product use three different names with nothing telling a reader they are one thing.
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
- [x] README hardening pass 4: link the orphaned `docs/RELEASE-NOTES-v0.1.0-draft.md` into the
      Documentation table, labelled honestly as a draft / not published (it existed but was reachable
      from nowhere) — 2026-10-10
- [x] README hardening pass 5: link the two shipped labs' **student guides**
      (`lab-definitions/srl-demo-unsolved/demo-01-...-unsolved.md`, `.../srl-demo2-unsolved/demo-02-...-unsolved.md`)
      from the "shipping labs" table via a new Guide column. Both guides shipped in-tree and were
      referenced from **nowhere** — a reader saw the lab named but could not reach its walkthrough — 2026-10-10
- [x] `docs/OPERATIONS.md` truth pass: removed two stale/unverifiable claims found by grepping the tree.
      (1) The "Release bundle" section described `frontend/nexus-release.tar.gz` as *the* shippable
      artifact, but **no bundle ships in this tree** — measured live 2026-10-11, `find . -name '*.tar.gz'`
      returns nothing outside `.git/`; the shipping path is a git clone + `install.sh`. Reframed as
      historical and hardened the leftover `check_bundle_fresh.sh` lesson. (2) The "Capstone" section
      was undated and asserted an unmeasured switch detail ("Alpine bridge-utils"); replaced with the
      numbers that actually trace to a shipped file (`lab-guides/lab-03-lock-it-down.md` — 100 pts,
      70 = pass) and labelled it curriculum context, not a shipped lab — 2026-10-11

## Run 2026-10-14 01:00 UTC — orphaned `CONFERENCE.md` shipped an install step for a bundle that does not exist

Measured live: `git status` clean, `HEAD...origin/main = 0 0`; `origin` token scopes `delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (cosmetic `ci.yml` step stays Dad-gated) and Screenshots still needs a session on the live AEGIS host.

Both blocked backlog items re-confirmed blocked, so I swept for a real, in-scope honesty gap. `CONFERENCE.md` (5.5 KB, tracked at repo root) was **referenced by nothing** — `git grep -l CONFERENCE.md` returned only `docs/GITHUB-PLAN.md`'s own orphan-list note — and it began by telling a booth operator to run `tar xzf aegis-portable.tar.gz`. Measured false: `find . -name '*.tar*'` returns **nothing** outside `.git/`, and `git grep aegis-portable` matches only CONFERENCE.md itself. It also printed an API response `{"service":"AEGIS",...,"labs_count":4}` where `backend/main.py:1764` actually returns `{"service":"NEXUS",...,"labs_count":len(LABS)}` (two labs ship). A stranger following the file's first instruction would have failed immediately.

Fixed by making it true of this tree, not by deleting it: replaced the `tar xzf` install with the real git-clone + `install.sh` flow, corrected the API example to the shape `main.py` returns (with an honest note that `labs_count` is whatever ships), updated the walk-up tips to name the two shipping labs instead of the legacy "Tier 1", pointed the "Adding a New Lab" footer at `docs/ADDING-A-LAB.md` (the README does not carry the full schema), added a `refused`/HTTP-409 row to the troubleshooting table, and stamped the whole file **draft / not maintained** with the same "code wins" rule used for `.nexus/`. Linked it from the README Documentation table so it is no longer orphaned. Backed up `CONFERENCE.md` and `README.md` via `scripts/safe-backup.sh` (label `conference-truth-pass-2026-10-14`, out of the served tree). No behaviour change. All four CI checks re-run green.

## Run 2026-10-13 19:00 UTC — `.nexus/` ships publicly and the README never said what it is

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). All four CI checks pass on the tree before the change(`py_compile`,
`bash -n install.sh`, `check_self_contained.py` rc=0, secret scan clean).

The 2026-10-12 13:00 run recorded a **Dad-gated** item: `.nexus/` (189 tracked files) ships publicly
but the README never mentions it. That note named the *unblocked half* explicitly — *"keep it public
(and label it clearly in the README as an internal audit trail)"* — so that half is in scope for a
polish run; only the structural choice (keep / split / prune) is Dad's.

Measured the gap before acting: `grep -n '\.nexus' README.md` → **no match**; `git ls-files .nexus/`
→ 189 files; the only *public* docs that reference it are `CHANGELOG.md`, `docs/ADDING-A-LAB.md`, and
`docs/RELEASE-NOTES-v0.1.0-draft.md` — all pointing at `.nexus/proofs/`. A reader therefore saw a
Documentation table listing every doc, then 189 unexplained files in the tree: an 87 KB `.nexus/STATUS.md`,
`DECISION-NEEDED-*.md`, audit notes, and — measured, not assumed — **28 slide images** under
`.nexus/deck-view/` (PNG/JPG) that **no tracked document references at all** (`git grep -l deck-view`
→ none). The tree was internally consistent but the README gave a stranger no way to know what any of
it was or that it is not product material.

Fixed by labelling, not by moving anything (moving/pruning is the Dad-gated half): added a
`.nexus/` row to the Documentation table and a short **About `.nexus/`** section that states what is
actually there (`proofs/` = dated evidence files; dated status/decision notes; `deck-view/` = rendered
slide images), that it is **not required to install or run AEGIS** (a cold clone installs from
`install.sh` + shipped source alone — consistent with `SELF-CONTAINED.md`), and that the dated entries
are **historical**: where a `.nexus/` note and the shipped code disagree, the code wins. No claim added
that the tree does not bear out. Backed up `README.md` via `scripts/safe-backup.sh` (label
`nexus-doc-labeling-2026-10-13`, out of the served tree). All four CI checks re-run green. Committed
`6137fae`, pushed `origin/main`. No behaviour change.

### Still Dad-gated (unchanged) — the `.nexus/` structural decision

The labelling above makes `.nexus/` *explained*; it does not decide whether it should be public. That
remains a policy call: keep it public (now labelled), split it to a private repo, or prune it. The
`deck-view/` images in particular look like they may simply be cruft (28 slide renders referenced
nowhere) — a prune candidate when Dad rules. Not acted on.

## Run 2026-10-13 13:00 UTC — README + OPERATIONS claimed `assets/` holds a file that does not ship

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). All four CI checks pass on the tree before the change (`py_compile`,
`bash -n install.sh`, `check_self_contained.py` rc=0, secret scan clean).

The README's Known-limitations section closed the pin-drift bullet with: *"`assets/` holds only
`frr-image.pin` and `installed-image-id.txt`."* Measured false of this tree. **`installed-image-id.txt`
does not ship**: `git ls-files assets/` returns only `assets/frr-image.pin`, and `git check-ignore -v
assets/installed-image-id.txt` confirms it is excluded by `.gitignore:13`. The file exists in my
working copy, but a reader who clones the repo gets **one** file in `assets/`, not two — the README
told them to expect a file that is not there. `docs/OPERATIONS.md` carried the same claim in two spots:
the bundle-contents block (line ~82, which also listed the `aegis-frr-image.tar.gz` that never ships)
and the Known-drift paragraph (line ~164).

Fixed all three to be true of this tree: README now says `assets/` *tracks* only `frr-image.pin` and
explicitly notes `installed-image-id.txt` exists locally but is git-ignored; OPERATIONS' bundle-contents
line reads `frr-image.pin only — the tarball and installed-image-id.txt never ship`; the bundle-rebuild
note and the Known-drift paragraph say `installed-image-id.txt` is git-ignored and does not ship. No
behaviour change; docs now agree with each other and with the tracked tree. Backed up `README.md` and
`docs/OPERATIONS.md` via `scripts/safe-backup.sh` (label `assets-holds-claim-2026-10-13`, out of the
served tree). All four CI checks re-run green.

## Run 2026-10-13 01:00 UTC — architecture.md still claimed install.sh verifies the substrate against the pin

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). All four CI checks pass on the tree before the change (`py_compile`,
`bash -n install.sh`, `check_self_contained.py` rc=0, secret scan clean).

The last run fixed the README's "one image travels" claim, but `docs/architecture.md` still carried an
unqualified version of the same false premise in its Components table: *"`assets/frr-image.pin` —
Content-addressed pin (layer chain + tarball sha256) that `install.sh` **verifies the loaded substrate
against**."*

Measured false of this tree. `install.sh` (lines 302–357) only reaches the verify branch **if** the
pinned tarball is present (`if [[ -n "${PIN_TARBALL}" && -f "${PIN_TARBALL}" ]]`). The pin names
`tarball=aegis-frr-image.tar.gz`, and `find . -path ./.git -prune -o -name '*.tar*' -print` returns
**nothing** — no tarball ships. So a cold clone never enters that branch; `install.sh` logs *"No pinned
image tarball found — building locally from Dockerfile"* and builds `aegis/frr:latest` from source
(line 363). The build is self-consistent but does **not** reproduce the pin's `layers_sha256`. README,
`OPERATIONS.md`, and `SELF-CONTAINED.md` were all already corrected to say exactly this; architecture.md
was the lone hold-out telling readers the pin is enforced at install.

Fixed: the row now reads that the pin names the substrate `install.sh` *would* load and verify **if the
pinned tarball were present**, states plainly that **no tarball ships in this tree** so the verify
branch is never taken, and points to `OPERATIONS.md` → "Known drift". No behaviour change; docs now
agree with each other and with the tree. Backed up `docs/architecture.md` via `scripts/safe-backup.sh`
(label `pin-verify-claim-2026-10-13`, out of the served tree). All four CI checks re-run green.

## Run 2026-10-12 19:00 UTC — README claimed an image ships in the repo (none does)

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). All four CI checks pass on the tree before the change.

The README Quick-start prerequisites closed with: *"Only **one** image travels in the repo; the switch
image is pulled at install."* Measured false. `find . -path ./.git -prune -o -name '*.tar*' -print`
(and `*.tgz`/`*.img`) returns **nothing**; `git ls-files assets/` returns only `assets/frr-image.pin`;
`install.sh` itself says *"No pinned image tarball found — building locally from Dockerfile"* and
builds `aegis/frr:latest` from `Dockerfile.frr`. So **zero** images travel in the tree, not one: the
router image is built locally and the switch image is pulled. The "one image travels" line contradicted
both the tree and the paragraph below it (the pin-drift section already says the FRR image is built
from source).

Fixed: the prerequisite now reads "**No image ships in the repo:** the router image (`aegis/frr:latest`)
is built locally from `Dockerfile.frr`, and the switch image is pulled at install." Backed up
`README.md` via `scripts/safe-backup.sh` (label `no-image-travels-claim`, out of the served tree). All
four CI checks re-run green. No behaviour change.

## Run 2026-10-12 11:00 UTC — README sent readers to the wrong directory for the quarantined topologies

Measured live: `git status` clean, `HEAD...origin/main = 0 0`; all four CI checks pass on the tree
(`py_compile`, `bash -n install.sh`, `check_self_contained.py` rc=0, secret scan clean). The two backlog
items stay blocked (Screenshots needs a session on the live AEGIS host; the cosmetic `ci.yml` step needs
a `workflow`-scoped token).

One real, in-scope, unblocked honesty gap: the README **shipping-labs** section closed with "The other
topologies under `lab-definitions/` are retained for reference … (see
`lab-definitions-quarantine-2026-09-30/`)." Measured: the quarantine dir is a **top-level sibling of
`lab-definitions/`**, not inside it — the 2026-09-30 quarantine `git mv`'d the non-release topologies
out. So a reader taking the sentence literally would list `lab-definitions/` and find **only the two
shipping labs** (plus three empty dirs `srl-demo/`, `srl-demo2/`, `cumulus-demo/`), not the retained
set the sentence promises.

Fixed: `README.md` now says the retained topologies live in the sibling
`lab-definitions-quarantine-2026-09-30/` (outside `lab-definitions/`, so the loader never sees them).
Backed up via `scripts/safe-backup.sh` (out of the served tree). All four CI checks re-run green.
Committed `0343bd1`, pushed `origin/main` (README is not a workflow file). No behaviour change.

## Run 2026-10-11 11:00 UTC — README still told readers to rebuild a bundle that does not ship

Measured live: `git status` clean, `HEAD...origin/main = 0 0`; all four CI checks pass on the tree
(`py_compile`, `bash -n install.sh`, `check_self_contained.py` rc=0, secret scan). The two backlog
items stay blocked (Screenshots needs a session on the live AEGIS host; the cosmetic `ci.yml` step
needs a `workflow`-scoped token).

Found the one real, in-scope, unblocked gap: the **2026-10-11 01:00 run corrected `docs/OPERATIONS.md`**
to state that no `nexus-release.tar.gz` ships in this tree — but it did **not** fix the **README**,
which is the primary doc. README (~line 145) still instructed the reader to *"Rebuild the release
bundle (`frontend/nexus-release.tar.gz`) whenever shipping files change — it is a snapshot, not a
symlink."* Verified the premise false: `find . -path ./.git -prune -o -name '*.tar.gz' -print`
returns **nothing**. So the front page told users to rebuild a bundle that does not exist.

Fixed: replaced the instruction with the true shipping model (**git clone + `install.sh`**; no
prebuilt bundle in-tree) and a pointer to the *historical* note in OPERATIONS.md. No behaviour change.
Backed up `README.md` via `scripts/safe-backup.sh` (out of the served tree). Re-ran all four CI checks
→ OK. Committed `6ec66f2`, pushed `origin/main` (accepted — README is not a workflow file).

## Run 2026-10-11 01:00 UTC — OPERATIONS.md truth pass (two stale claims corrected)

Measured live: `git status` clean, `HEAD...origin/main = 0 0`, CI workflow present, all four CI checks
pass on the tree (`py_compile`, `bash -n install.sh`, `check_self_contained.py` OK, secret scan clean).
The polish backlog's only open items remain **Screenshots** (blocked — needs a session on the live
AEGIS host) and the **cosmetic `ci.yml` step** (blocked — the `origin` token still lacks `workflow`
scope). Neither is Dad's call to infringe on, so this run took the one in-scope honesty fix available:
OPERATIONS.md carried a bundle command block implying a tarball ships (it doesn't) and an undated,
unmeasured Capstone claim. Both corrected; no invented content, only removal/citation.

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

## Run 2026-10-10 13:00 UTC — CONTRIBUTING pre-push list made truthful (it disagreed with CI)

Measured live: tree clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope**, so the
cosmetic `ci.yml` step stays blocked and Screenshots still needs a session on the live host.

One real, in-scope, unblocked item: `CONTRIBUTING.md` said "Run the same checks CI runs" and then
listed **three** commands — but `.github/workflows/ci.yml` runs **four** (the secret-scan was
omitted), and the README already claims "the same four CI runs". The two docs disagreed; a
contributor following CONTRIBUTING would skip the secret-scan. Fixed:

- Listed all four CI checks (backend compile, installer shell-syntax, self-contained, secret-scan) so
  the text matches the workflow exactly.
- Added the two lab-author tools the PR template references but CONTRIBUTING never mentioned:
  `tools/lint_lab_pack.py` and `tools/check_bundle_fresh.sh` — **verified both exist**, and labelled
  them honestly as **not** in CI (`lint_lab_pack.py` needs `pyyaml`; CI installs no deps — confirmed
  `grep -c 'pip install' ci.yml` = 0).
- Noted the grader byte-compile now covered by the self-contained check.

No behaviour change; docs now match the workflow. Committed `73720e0`, pushed `origin/main`.

## Run 2026-10-10 11:00 UTC — CI grader-compile gap CLOSED without the blocked workflow-scope token

Measured live: tree clean, `HEAD...origin/main = 0 0`. Re-confirmed the `origin` token scopes
(`delete:packages, repo, write:discussion, write:packages` — still no `workflow`).

Found the unblocked path for the highest-value backlog item. The gap the blocked CI item describes is
real: `backend/main.py` is the only thing CI compiles, so a syntax error in a shipped
`lab-definitions/grader_*.py` passes CI silently. But `tools/check_self_contained.py` already runs in CI
and is **not** a workflow file — so I moved the guarantee there instead of into `ci.yml`:

- Added a byte-compile loop over `lab-definitions/grader_*.py` to `tools/check_self_contained.py`.
- **Proven both ways:** clean tree → `rc=0`; injected syntax error in `grader_demo_02.py` → check
exits `1`, naming the file and line. Restored the grader, re-ran, `rc=0`.
- Committed `3e6610d`, pushed `origin/main` — **accepted, no `workflow` scope required.**

So the CI item is now *satisfied through an unblocked route*; the only residual slice is the cosmetic
one of also adding the explicit step to `ci.yml`, which stays blocked on the `workflow` token —
optional now, not load-bearing. Screenshots remain blocked (no session on the live AEGIS host, this box
is `192.168.111.40/16`).

## Run 2026-10-10 01:00 UTC — one real doc item (orphaned release notes linked), then blocked items stand

Measured live: `git status` clean, `HEAD...origin/main = 0 0`. Re-confirmed the `origin` token scopes:
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope**, so the CI
item stays blocked. Screenshots still need a session on the live AEGIS host (not this box).

Did ONE in-scope, unblocked item this run: swept `docs/*.md` + root `*.md` for files not referenced
anywhere, and found `docs/RELEASE-NOTES-v0.1.0-draft.md` orphaned (link-checked: no README mention, no
other doc references it). Linked it into the README Documentation table, labelled as a **draft / not
published** so the entry stays true. `CONFERENCE.md` and `HANDOFF-2026-09-22.md` are also unreferenced
but are historical/legacy artifacts, not repo documentation — left alone deliberately (link-or-archive
is Dad's call, not mine to invent).

## Run 2026-10-09 19:00 UTC — both open items re-verified blocked; no manufactured work

Measured live this run: `git status` clean, `HEAD...origin/main = 0 0` (nothing to push). README
headings checked against the task's hardening list — badges, what-this-is/is-not (features), the
architecture sketch, **Quick start** + install, the honest lab table, the grading model, the
documentation table, and License are all present. The loader glob (`lab-definitions/**/*.yml`) still
resolves to **exactly the two** labs the README table names, so the "ships exactly two labs" claim
remains true of this tree.

The only backlog items left are the two already marked blocked:

1. **CI hardening** (also byte-compile `lab-definitions/grader_*.py`) — re-tested the `origin` token
   live this run: `x-oauth-scopes: delete:packages, repo, write:discussion, write:packages`. **No
   `workflow` scope**, so any push touching `.github/workflows/ci.yml` is rejected. The edit already
   verified clean (simulated STEP OK). **Dad's call:** mint a token with `workflow` scope.
2. **Screenshots** — real captures require a session on the host where AEGIS actually runs (this box
   is `192.168.111.40/16`; the lab host is on another subnet and unreachable here). **Dad's call:**
   grant a route/session, or the item stays open.

No in-scope code change was appropriate today (remaining product work is gated on Dad's rulings). One
item honestly assessed, no phantom work.

## Run 2026-10-10 19:00 UTC — the two shipped labs' own student guides were unlinked

Measured live: tree clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays blocked), and Screenshots still needs a session on the live AEGIS host (this box is
`192.168.111.40/16`).

Swept every tracked `*.md`/`*.cff` for inbound links and found the highest-value unlinked pair: the
**student guides for the two labs the README advertises**. `lab-definitions/srl-demo-unsolved/
demo-01-two-pcs-and-a-real-switch-unsolved.md` and `lab-definitions/srl-demo2-unsolved/
demo-02-two-switches-one-router-unsolved.md` each had **zero** references anywhere — the README named
both labs by ID and linked their YAML nowhere and their walkthrough nowhere, so a reader could not
reach the actual instructions for either shipped lab.

Verified before linking: the loader glob (`lab-definitions/**/*.yml`) still resolves to **exactly two**
files (the two shipped labs), and both `.md` targets exist at the exact relative paths used. Added a
**Guide** column to the "shipping labs" table linking each lab's guide, plus one honest sentence
(YAML topology + Markdown guide + Python grader per lab, same directory) — all true of this tree.
Checks re-run: backend compile OK, `bash -n install.sh` OK, `check_self_contained.py` rc=0.

## Run 2026-10-12 01:00 UTC — a stray BGP-revert backup was committed inside the shipping lab dir

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). The CI-hardening gap is already satisfied via `tools/check_self_contained.py`
(byte-compiles `lab-definitions/grader_*.py`; runs in CI) — re-confirmed this run.

Found a real repo-cleanliness bug: `lab-definitions/lab-04-two-as-peering.yml.bgp-revert-bak` — a **1917-byte
pre-revert snapshot** — was committed *inside the shipping `lab-definitions/` directory*, visible on GitHub.
It is a **BGP** lab (BGP is explicitly out of scope for this release), it references `aegis/frr-bgp:latest`
and a grader (`grader_lab_04_two_as_peering`) that **does not exist** in this tree, and it is referenced by
nothing (`grep` → no hits outside `.git/`). A reader browsing the shipping lab dir sees a broken, ungraded BGP
artifact. The loader already refuses to load `*.bak` (structural guard at `backend/main.py` ~L469), so it was
inert at runtime — purely visual clutter.

Fixed, reversibly: `git mv` it into `lab-definitions-quarantine-2026-09-30/` (where its reverted sibling
`lab-04-two-as-peering.yml` + the real grader already live), and added a `.gitignore` guard
(`*-revert-bak`, `*.yml.bak-*`, `*.yml.orig`) so a future reverting snapshot cannot be committed into the
shipping dir. Backed up via `scripts/safe-backup.sh` (label `stray-bak-sweep`, out of the served tree).
Swept for other strays: `git ls-files | grep -E '\.bak|\.orig|-bak$'` → only this one.

Checks re-run, all four green: backend compile OK, `bash -n install.sh` OK, `check_self_contained.py` rc=0
(15 required files present), secret scan clean.

## Run 2026-10-11 13:00 UTC — the "shipped FRR image tarball" claims were false; corrected in three docs

Measured live: `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`).

Found a real honesty bug beyond the two blocked items. `README.md`, `docs/OPERATIONS.md`, and
`docs/architecture.md` all asserted that `aegis/frr:latest` **ships as `assets/aegis-frr-image.tar.gz`**
("the shipped tarball matches the pin"). It does not: `git ls-files | grep -E '\.tar|\.gz|\.tgz'`
returns nothing, and `find . -name '*.tar.gz'` (excluding `.git/`) is empty. `assets/` holds only
`frr-image.pin` and `installed-image-id.txt`, both tracked. `install.sh` loads a tarball **only if
present** (`if [[ -f $PIN_TARBALL ]]`); the pin *names* `aegis-frr-image.tar.gz` but that file is not in
this tree, so a cold clone takes the **build-from-source fallback** (`docker build` from
`Dockerfile.frr`) — which is self-consistent but does **not** reproduce the pin's `layers_sha256`.

Corrected four spots to be true of this tree: the README quickstart line ("loads the pinned image and
verifies it against the shipped pin" → builds locally), the README pin-drift bullet, the
OPERATIONS substrate table ("✅ shipped as…" → "❌ built locally"), the OPERATIONS bundle-contents
note, and the OPERATIONS pin-drift paragraph ("the pinned path installs cleanly" → "the pinned path is
not taken here"), plus the architecture.md substrate row. Backups via `safe-backup.sh`
(label `frr-tarball-truth`). Checks re-run: backend compile OK, `bash -n install.sh` OK,
`check_self_contained.py` rc=0 (15 required files present).

## Run 2026-10-12 13:00 UTC — README API table was missing 4 of the 11 routes

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). The CI-hardening gap stays satisfied via `tools/check_self_contained.py`.

Found a real, in-scope honesty gap: the README **API** section listed **7** routes, but
`backend/main.py` exposes **11** (`grep -oE '@app\.(get|post|put|delete)\("[^"]+"' backend/main.py`).
The four undocumented routes are all user-facing and functional:
`GET /api` (health/version card), `GET /api/labs/{id}/guide` (serves the student guide — the very
links the labs table points at), `GET /api/labs/{id}/topology` (renders the topology diagram),
and `GET /api/sessions/{id}` (one session's status — backs *Reconnect*).

Fixed: completed the table so it matches `main.py` name-for-name (`{id}` shorthand, as the table
already used). Added one sentence: "the complete route set exposed by `backend/main.py`." Backed up
`README.md` via `scripts/safe-backup.sh` (label `api-table-completeness`, out of the served tree).
All four CI checks re-run green (backend compile, `bash -n install.sh`, `check_self_contained.py`
rc=0, exact secret-scan command → clean). Committed `2b13a19`, pushed `origin/main`. No behaviour change.

### New Dad-gated item — the internal `.nexus/` engineering trail ships publicly

Not acted on (structural/policy decision, not mine). `.nexus/` is **tracked** — 189 files — and public
on GitHub. It is referenced from `CHANGELOG.md`, `docs/ADDING-A-LAB.md`, and the release-notes draft as
the evidence trail, and `tools/check_self_contained.py` lists `.nexus/` as an allowed reference target —
so it is *deliberate*, not junk, and deleting it would break those citations. But it also contains
material that is not repo documentation: `STATUS.md` (a dated deployment ledger naming colleagues),
`DECISION-NEEDED-lab04-bgp-20260923.md` ("From: Selina … Status: NOT complete; needs Dad's call"),
`AUDIT-BY-ZOE-*`, proof files whose names describe failures ("unsolved-lab-ships-solved-config"). None of
the six public docs (README, CONTRIBUTING, architecture, OPERATIONS, GRADING-MODEL, SELF-CONTAINED)
link into `.nexus/`. **Dad's call:** keep it public (and label it clearly in the README as an internal
audit trail), split it to a private repo, or prune it. Not invented work — recorded so it is not lost.

## Rules for the polish runs

> **Push credentials (2026-10-08):** the token in `github.md` is **read-only** — pushes with it return
> `403 Permission denied`. The working write token is in `github2.md`. `origin` in the shipping tree
> is set to that one. If a push 403s, check which token `origin` carries.


1. One item per run — don't sprawl.
2. Commit with an honest, specific message; push `origin main`.
3. Never claim "complete"/"finished" about Nexus — that's Dad's word alone.
4. If an item needs a screenshot or a decision only Dad can make, note it here and move on.

## Run 2026-10-14 13:00 UTC — root-level `HANDOFF-2026-09-22.md` was orphaned and asserted labs/counts this tree does not ship

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token
scopes `delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope**
(the cosmetic `ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live
AEGIS host (this box is `192.168.111.40/16`). All four CI checks pass on the tree before the change.

Both blocked backlog items re-confirmed blocked, so I swept for a real, in-scope honesty gap. The
prior run's own note (line ~304) had already flagged `HANDOFF-2026-09-22.md` as **unreferenced**
next to `CONFERENCE.md`; last run fixed `CONFERENCE.md` but explicitly left HANDOFF as "Dad's call."
On review it is squarely the same class of gap as the `CONFERENCE.md` and `10-archive/SUMMARY-for-Dad.md`
fixes — a **root-level tracked file a stranger sees, referenced by no public doc, asserting things
false of this tree** — so it is in scope for an honesty pass, not a structural decision.

Measured before acting: `git grep -n HANDOFF-2026-09-22 -- '*.md' ':!docs/GITHUB-PLAN.md' ':!.nexus/'`
returns **nothing** — no doc a reader sees links it. It ships at repo root, so GitHub shows it. Then
measured its claims against the tree:
- It says the server **"serves 14 labs."** False: `find lab-definitions -name '*.yml'` + the loader
glob (`LABS_DIR.glob('*.yml')` + one level of subdirs, `backend/main.py:466-468`) discover **exactly 2**
(`demo-01-two-pcs-and-a-real-switch-unsolved`, `demo-02-two-switches-one-router-unsolved`).
- It says the Cumulus lab **"ships as its own lab."** False: `git ls-files | grep -i cumulus` puts it
only under `lab-definitions-quarantine-2026-09-30/`, outside the loader's `lab-definitions/` root.
- It names `tier-01…03`, `lab-01…04`, `neteng-capstone`, `lab-04-two-as-peering` as live — none ship.
- It points at `projects/aegis-public` (the deprecated fork) and out-of-band `.nexus/proofs/*.txt`.

Fixed by making it true, not by deleting it (it is Dad's handoff — keep the value, mark it historical):
added a **HISTORICAL — not a description of the shipping tree** banner at the top listing the three
specific false-of-this-tree claims and the "code + README win" rule; corrected in place the "14 labs"
line, the Cumulus "ships as its own lab" line (→ retained under quarantine, does not ship), the §4
HEAD line (→ "as of 2026-09-22; tree has moved on"), the §3 grader list (→ noted those graders are
not in this release), and the §4 lint red-flags note (→ those labs do not ship). Linked it from the
README Documentation table as **historical / not maintained** so it is no longer orphaned. Backed up
via `scripts/safe-backup.sh` (label `handoff-truth-pass-2026-10-14`, out of the served tree). All four
CI checks re-run green. No behaviour change. NOT COMPLETE — Dad's word alone. | proof=none (docs) |
next=run: least-recently-moved in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs
live-host session), cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public
policy call.

## Run 2026-10-14 19:00 UTC — the README lab table counted Demo 1's nodes but not Demo 2's

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). All four CI checks pass on the tree before the change.

Checked the README lab table against the two shipped topologies line by line. Demo 1's Topology cell
read *"2 Alpine PCs + 1 SR Linux switch, bridged"* — matches `demo-01-...yml` exactly (nodes
`pc-a`, `pc-b` = `alpine:latest`, `sw1` = `nokia_srlinux`). Demo 2's cell read *"2 SR Linux switches +
1 FRR router, routed"* — but `demo-02-...yml` defines **five** nodes: two `alpine:latest` PCs (`pc-a`,
`pc-b`) plus two `nokia_srlinux` switches (`sw1`, `sw2`) plus one `aegis/frr:latest` router (`r1`), wired
`pc-a—sw1—r1—sw2—pc-b`. The row named only 3 of the 5 nodes and omitted both PCs, while its sibling row
counted every node. Not a falsehood, but an inconsistent convention inside the same table: a reader
scanning rows would under-count Demo 2 and would not know it also ends in two Alpine PCs.

Fixed by making the Demo 2 cell name all five nodes in the same order/convention as Demo 1:
*"2 Alpine PCs + 2 SR Linux switches + 1 FRR router, routed"* — true of `demo-02-...yml` as measured.
One-line, no behaviour change. Backed up `README.md` via `scripts/safe-backup.sh` (label
`demo02-row-2026-10-14`, out of the served tree). All four CI checks re-run green. NOT COMPLETE —
Dad's word alone. | proof=none (docs) | next=LAB least-recently-moved -> next in-scope honesty item;
STILL BLOCKED ON DAD: Screenshots (needs live-host session), cosmetic `ci.yml` step (needs
workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-14 11:00 UTC — the PR template required contributors to rebuild a bundle that does not ship

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). All four CI checks pass on the tree before the change.

Both blocked backlog items re-confirmed blocked, so I swept for a real, in-scope honesty gap — this
time the doc **every contributor reads first**: `.github/PULL_REQUEST_TEMPLATE.md`. Its truth-check
section required, under "If this touches a served lab or the bundle":

- *"If shipping files changed, I rebuilt `frontend/nexus-release.tar.gz` (see `docs/OPERATIONS.md`) —
  it is a snapshot, not a symlink."*
- *"The served frontend, source, and bundle still agree (`tools/check_bundle_fresh.sh`)."*

Both are false of this tree. Measured: `find . -name 'nexus-release.tar.gz'` returns **nothing** outside
`.git/`/`.nexus/` — no bundle ships, and it is git-ignored. `tools/check_bundle_fresh.sh` itself prints
*"no bundle present ... nothing to check"* and exits 0, so the required check is a permanent no-op
here. The README (line 156) and `docs/OPERATIONS.md` (lines 70–74) were corrected to say the shipping
path is a **git clone + `install.sh`, not a bundle** in the 2026-10-10/11 runs — the earlier
2026-10-11 OPERATIONS pass even flagged this exact false premise in the README but missed the PR
template. So a contributor following their own repo's checklist was told to rebuild and commit a
non-existent artifact.

Fixed by making the template true of this tree, not by deleting the section: the "or the bundle" branch
is gone; "If this touches a served lab" now keeps only the reload+regrade step (a real check), and a
short note states plainly that **no shippable bundle exists** (`frontend/nexus-release.tar.gz` does not
ship, a clean host installs from the clone + `install.sh`), that contributors must **not** rebuild or
commit one, and that `check_bundle_fresh.sh` still exists but **no-ops when no bundle is present — as it
is here — so it is not a required check on this repo.** Backed up via `scripts/safe-backup.sh` (label
`pr-template-bundle-truth-2026-10-14`, out of the served tree). Re-ran all four CI checks green;
`check_bundle_fresh.sh` no-ops with rc=0 as documented. Committed `808d9af`→this commit, pushed
`origin/main`, local==origin 0/0. NOT COMPLETE — Dad's word alone. | proof=none (docs) | next=run:
LAB least-recently-moved -> next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs
live-host session), cosmetic ci.yml step (needs workflow-scoped token), and the `.nexus/` public
policy call.

## Run 2026-10-15 11:00 UTC — five shipped docs referred to the labs as "LAB-A"/"LAB-B", a nickname no reader can resolve

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; `origin` token scopes
`delete:packages, repo, write:discussion, write:packages` — still **no `workflow` scope** (the cosmetic
`ci.yml` step stays Dad-gated), and Screenshots still needs a session on the live AEGIS host (this box
is `192.168.111.40/16`). All four CI checks pass on the tree before the change.

Both blocked backlog items re-confirmed blocked, so I swept for a real, in-scope honesty gap. The
README names the two shipping labs `demo-01-two-pcs-and-a-real-switch-unsolved` and
`demo-02-two-switches-one-router-unsolved`. But **five shipped public docs refer to them as `LAB-A` /
`LAB-B`** — an internal run-log nickname that is defined **nowhere** in the tree. Measured:
`grep -rn 'LAB-A\|LAB-B'` outside `GITHUB-PLAN.md` hits `CHANGELOG.md` (×2), `docs/OPERATIONS.md`
(×3), `docs/SELF-CONTAINED.md` (×1), and `docs/RELEASE-NOTES-v0.1.0-draft.md` (×3). A reader who
clones the repo sees "the router in LAB-B" (SELF-CONTAINED.md:24, OPERATIONS.md:112) and has no way to
learn that LAB-B = Demo 2, or that LAB-A = 3 nodes / LAB-B = 5. The docs are the product surface; this
is the same class of gap as the earlier orphaned-doc and bundle-truth passes.

Fixed by naming the real labs, not by deleting context. Mapping verified against the shipped YAMLs:
`LAB-A` = `demo-01-two-pcs-and-a-real-switch-unsolved` (nodes pc-a, pc-b, sw1 = **3**), `LAB-B` =
`demo-02-two-switches-one-router-unsolved` (nodes pc-a, pc-b, sw1, sw2, r1 = **5**). In each file the
first use now carries the real id (`Demo 1 (demo-01-…)` / `Demo 2 (demo-02-…)`) and later uses read
`Demo 1`/`Demo 2`; the node counts stay attached ("Demo 1 = 3 nodes, Demo 2 = 5"). SELF-CONTAINED.md's
"the two labs" now names both ids. No claim added or removed — only the identifier a reader can resolve.
Backed up `CHANGELOG.md`, `docs/OPERATIONS.md`, `docs/SELF-CONTAINED.md`, `docs/RELEASE-NOTES-v0.1.0-draft.md`
via `scripts/safe-backup.sh` (label `labab-truth-2026-10-15`, out of the served tree). All four CI
checks re-run green. No behaviour change. NOT COMPLETE — Dad's word alone. | proof=none (docs) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-15 13:00 UTC — the 11:00 sweep missed two shipped source files: the code still called the labs "LAB-A"/"LAB-B"

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; all four CI checks
(`check_self_contained.py`, `lint_lab_pack.py`, `check_bundle_fresh.sh`, byte-compile) pass on the tree
before the change. `origin` token scopes unchanged — still **no `workflow` scope** and no live host for
Screenshots, so both remain Dad-blocked (re-confirmed, not re-litigated).

The 11:00 run named the four *docs* that said `LAB-A`/`LAB-B`, but its sweep was doc-scoped and missed
**two shipped source files**, one of them student-facing:
- `lab-definitions/srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.md` — the served Demo 1
  student guide, line 48: *"…run 196: LAB-B's guide states its lab-level rule…"*. A student reading
  Demo 1's own guide cannot resolve "LAB-B".
- `lab-definitions/grader_demo_02.py` — the shipped grader's docstring: *"Same defect fixed in the
  LAB-A grader…"*.
- `backend/main.py` — **seven** more comments across the shipped API (`:401 :538 :709 :1199 :1608
  :1609 :2298`) that describe measured behaviour in terms of `LAB-A`/`LAB-B`.

Same gap, same fix: name the real labs, add no claim. Mapping unchanged and verified against the shipped
YAMLs — `LAB-A` = `demo-01-two-pcs-and-a-real-switch-unsolved` (3 nodes: pc-a, pc-b, sw1), `LAB-B` =
`demo-02-two-switches-one-router-unsolved` (5 nodes: pc-a, pc-b, sw1, sw2, r1). Each comment's measured
content is preserved verbatim; only the identifier changes to the resolvable one (`Demo 1 (demo-01-…)` /
`Demo 2 (demo-02-…)`, later uses `Demo 1`/`Demo 2`). `backend/main.py` still byte-compiles,
`grader_demo_02.py` still byte-compiles, `check_self_contained.py` green. `LAB-A`/`LAB-B` now survive
**only** in `.nexus/proofs/*` — signed, dated measurement records that are evidence and must not be
rewritten. Backed up via `scripts/safe-backup.sh` (label `labab-code-2026-10-15`, out of the served
tree). No behaviour change. NOT COMPLETE — Dad's word alone. | proof=none (docs/comments) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-15 19:00 UTC — two lab topologies were tracked at the REPO ROOT and referenced by nothing

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; all CI checks
(`check_self_contained.py`, `lint_lab_pack.py`, `check_bundle_fresh.sh`, byte-compile) green on the
tree before the change. `origin` token scopes unchanged — still **no `workflow` scope** (cosmetic
`ci.yml` step stays Dad-gated) and no live host for Screenshots (this box is `192.168.111.40/16`).
Both blocked items re-confirmed blocked, so I swept for a real, in-scope honesty gap.

An orphan sweep (every tracked `*.md`/`*.html`/`*.yml` that no other file names) returned exactly two
files, both at the **repo root**:
- `lab-day1-router.yml` — a FRR single-router lab ("Day 1 Router Configuration"), 88 lines.
- `tier-03-router-switch-pc.yml` — 116 lines.

Both were introduced in the initial snapshot (`2868142`) and touched by no commit since. Neither is
referenced anywhere in the shipping tree: `git grep` finds `tier-03-router-switch-pc` only in
historical notes (`HANDOFF-2026-09-22.md`) and `.nexus/` records, and `lab-day1-router` **nowhere**
outside the file itself. Meanwhile the README's "shipping labs" section says the release ships exactly
**two** labs and that "the other topologies ... live in the sibling directory
`lab-definitions-quarantine-2026-09-30/`". So root placement contradicted the README: a stranger
cloning the repo sees two `.yml` files named as labs sitting *beside the README*, not in the
quarantine dir the README points them to.

Two measured facts made this worse than a filing error:
1. `lab-day1-router.yml` carries **no `metadata:` section**. `backend/main.py:396 _parse_yaml_metadata`
   returns `None` for it and the discover loop (`:467`) `continue`s — so it is not merely quarantined,
   it was **never serveable** (`git grep -c 'metadata:'` → 0 in that file). Dead weight with a
   shipping-sounding name.
2. `tier-03-router-switch-pc.yml` is a duplicate of the already-quarantined
   `lab-definitions-quarantine-2026-09-30/05-router-switch-pc.yml`, minus that copy's two honesty
   annotations (`course: CI-01`, `validates_switch_authenticity: false`). The quarantined copy is the
   more complete record.

Fixed by moving both into `lab-definitions-quarantine-2026-09-30/` (git mv, history preserved) — the
directory the README already names — and appending a dated note to that directory's `MANIFEST.txt`
recording what each is and why it moved. No claim added or removed; the README's "exactly two labs"
statement is now true of the repo root too. Verified the loader is unaffected (it scans
`lab-definitions/` and one level of subdirs only, `main.py:456`) and re-ran all CI checks green.
Backed up both files via `scripts/safe-backup.sh` (label `orphan-yml-2026-10-15`, out of the served
tree). No behaviour change. NOT COMPLETE — Dad's word alone. | proof=none (docs/tree layout) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-16 01:00 UTC — `10-archive/SUMMARY-for-Dad.md` cited a provenance link that did not exist

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run
(`85d9f7d`); all four CI checks green on the tree before the change (backend `py_compile`,
`bash -n install.sh`, `tools/check_self_contained.py` rc=0, secret scan clean). `origin` token scopes
unchanged — still **no `workflow` scope** (cosmetic `ci.yml` step stays Dad-gated) and no live host for
Screenshots (this box is `192.168.111.40/16`). Both blocked items re-confirmed blocked, so I swept for
a real, in-scope honesty gap.

`10-archive/SUMMARY-for-Dad.md` opened with a banner whose last substantive sentence was:
*"Kept only because `docs/OPERATIONS.md` (Archive section) points readers here for provenance."*
Measured false of this tree: `git grep 'SUMMARY-for-Dad' -- . ':!.nexus'` matched **nothing** in any
doc outside `.nexus/` and this plan — including `docs/OPERATIONS.md`. That file's Archive section
(`docs/OPERATIONS.md:194`) named only the *directory* (`10-archive/`) and the sibling quarantine dir;
it never named this file. And the file was **unreachable from the README** (`grep -n '10-archive\|SUMMARY' README.md` → no match) while every other doc is in the Documentation table. So the file's
stated reason for existing was untrue, and a reader had no path to it anyway.

Fixed so the claim is true rather than by deleting the claim: (1) `docs/OPERATIONS.md` Archive section
now names `10-archive/SUMMARY-for-Dad.md` as the provenance source for the older layout, with the same
"read it as history, not the shipping tree" caveat; (2) added it to the README Documentation table;
(3) tightened the file's own banner — it previously said the `tier-01*`…`tier-04*` YAMLs do not exist,
but `10-archive/tier-03-bgp-simplified.yml` **does** ship (`git ls-files` confirms it) and the file's
own "Files Changed" note says so, so the banner now names `tier-01*`/`tier-02*`/`tier-04*` and calls out
the one survivor explicitly. No claim added that the tree does not bear out. Backed up all three files
via `scripts/safe-backup.sh` (label `provenance-claim-2026-10-16`, out of the served tree). No
behaviour change. NOT COMPLETE — Dad's word alone. | proof=none (docs) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-16 11:00 UTC — `_GUIDE_MAP` was an unlabelled fossil and `lab-guides/lab-03-lock-it-down.md` was an unlisted orphan

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; all CI checks green
(`py_compile`, `bash -n install.sh`, `tools/check_self_contained.py` rc=0, `tools/lint_lab_pack.py`,
secret scan clean). `origin` token scopes unchanged — still **no `workflow` scope** (cosmetic `ci.yml`
step stays Dad-gated) and no live host for Screenshots. Both blocked items re-confirmed blocked.

Host note (recorded, not acted on): `nexus.service` does **not** exist on this box (`dept-dragon-tech`,
`192.168.111.40/16`), and neither does `/srv` (so `AGENTS.md`'s `/srv/canon/README.md` reference is not
satisfiable here). The live-product verification legs of earlier runs were run against the Nexus host;
the work this host can honestly do is the tree/docs/CI lane, which is what this run stayed in.

Two in-scope honesty gaps, both measured, both fixed without behaviour change:

1. **`backend/main.py` `_GUIDE_MAP`** (7 entries) is a fossil of the pre-release layout. Measured: all
   seven target filenames are **absent** from `lab-definitions/` (`test -e lab-definitions/<t>` → 7 of 7
   missing), and all seven ids (`tier-01-foundation`, `tier-02-router-basics`, `lab-01-crossing-subnets`,
   `lab-02-switch-in-the-middle`, `tier-03-router-switch-pc`, `lab-03-lock-it-down`, `neteng-capstone`)
   are quarantined labs. `_GUIDE_MAP.get()` therefore returns `None` for **both shipping labs**
   (`demo-01`/`demo-02`) and resolution falls through to the topology-relative branch — which is where the
   shipped demo guides actually live and are served. So the map is inert, not live routing; the gap was
   that it sat in unlabelled **module-level** source, which is exactly how a fossil gets read as live
   (run 239's lesson: this module executes at import).
2. **`lab-guides/lab-03-lock-it-down.md`** is a guide for `lab-03-lock-it-down`, which this release does
   **not** ship (README: "ships exactly two labs"). It was unlisted in the README Documentation table and
   referenced only by `docs/OPERATIONS.md:187` as the in-tree source for the Net Eng I capstone's point
   numbers. Its lab definition is quarantined (`lab-definitions-quarantine-2026-09-30/06-lock-it-down.yml`,
   id `lab-03-lock-it-down`), outside `lab-definitions/`, so the loader never serves it.

Fix (no behaviour change): a comment naming `_GUIDE_MAP` **inert for the shipping tree** with the 7/7
measurement; a **historical banner** on the orphan guide naming its quarantined definition; and a README
Documentation-table row so the file has a discoverable path (same reachability medicine as the 01:00
SUMMARY-for-Dad run). Backed up both files via `scripts/safe-backup.sh` (label `guide-map-truth-2026-10-16`,
out of the served tree). Re-ran all CI checks green; committed `b9e10d3`, pushed `origin/main`, local==origin
`0 0`. NOT COMPLETE — Dad's word alone. | proof=none (source/doc note) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-16 13:00 UTC — CHANGELOG named the bundle-freshness guard as a live deploy gate, but it ships vestigial

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; all CI checks green
(`py_compile`, `bash -n install.sh`, `tools/check_self_contained.py` rc=0, `tools/lint_lab_pack.py`,
secret scan clean). `origin` token scopes unchanged — still **no `workflow` scope** (cosmetic `ci.yml`
step stays Dad-gated) and no live host for Screenshots (this box is `192.168.111.40/16`). Both blocked
items re-confirmed blocked.

One in-scope honesty gap, measured and fixed without behaviour change. The `[0.1.0]` **Fixed** bullet
in `CHANGELOG.md` read: *"Added `tools/check_bundle_fresh.sh` as a guard; the bundle is rebuilt and the
freshness check fails a deploy if source and bundle disagree (runs 258/260)."* That phrasing states a
**live rebuild-and-deploy gate** — false of this tree. Measured: `find . -name '*.tar.gz'` returns
nothing outside `.git/` (no bundle ships); the shipping model is clone + `install.sh`; and
`tools/check_bundle_fresh.sh` **no-ops** with `"no bundle present at frontend/nexus-release.tar.gz —
nothing to check"` (it exits 0 early when the file is absent). So the CHANGELOG claimed the repo carries
a deploy gate it does not run — a reader would believe a stale-bundle class of bug is guarded here,
when the guard is inert. This is the same drift README + `docs/OPERATIONS.md` were already corrected
for ("Release bundle (historical — not shipped in this tree)"); the CHANGELOG was the last un-swept
surface still telling the old story.

Fixed by making the bullet true of this tree, not by deleting it: kept the historical fact (the guard
was added, runs 258/260) and appended an honest **Note** that the guard is vestigial here — no bundle is
committed, the guard no-ops, and the current shipping model is a git clone + `install.sh`, pointing at
the README quickstart and `docs/OPERATIONS.md` → "Release bundle (historical)". No claim added that the
tree does not bear out. Backed up `CHANGELOG.md` via `scripts/safe-backup.sh` (label
`changelog-bundle-guard-truth-2026-10-16`; the script's backup landed under `.nexus/bundle-archive/`,
which is git-ignored at `.gitignore:48` and therefore does not ship — verified with `git status`, which
showed only `CHANGELOG.md` modified). All four CI checks re-run green; committed `dd76cbc`, pushed
`origin/main`, local==origin `0 0`. No behaviour change. NOT COMPLETE — Dad's word alone. | proof=none
(docs) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-16 19:00 UTC — CHANGELOG + RELEASE-NOTES still quoted a pre-history `.git` size (730 MB → 1.6 MB) that no longer describes this tree

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; CI checks green
(`py_compile` OK, `bash -n install.sh` OK, `tools/check_self_contained.py` rc=0, secret scan clean).
`tools/lint_lab_pack.py` cannot run **here** — this box has no PyYAML (`import yaml` → ModuleNotFoundError);
that is a pre-existing local-env gap, not a regression (this run touched no code, and the lint runs in CI
where deps install). `origin` token scopes unchanged — still **no `workflow` scope** (cosmetic `ci.yml`
step stays Dad-gated) and no live host for Screenshots (this box is `192.168.111.40/16`). Both blocked
items re-confirmed blocked.

One in-scope honesty gap, measured and fixed without behaviour change. Two surfaces carried the same
number: `CHANGELOG.md` ("Changed" → *"`.git`: 730 MB → 1.6 MB"*) and
`docs/RELEASE-NOTES-v0.1.0-draft.md` ("Highlights" → *"730 MB → 1.6 MB after purging stale bundle history"*).
That reduction was measured at the **2026-09 purge**, which **predates this git history** (earliest commit
here is `2868142`, 2026-09-20) — it is not a fact about the tree a reader clones today. Measured live:
`.git` is **~21 MB packed / ~24 MB on disk** (`git count-objects -vH` → size-pack 21.08 MiB; `du -sh .git`
→ 24M) and the working tree is **~4 MB**. So the present-tense framing ("Repo is now … 1.6 MB") was false
of this tree: a cloner sees ~21–24 MB, ~15× the quoted figure. No shipped proof carries the 730/1.6 numbers
either (`git grep '730\|1\.6 MB'` → only these two docs), so they were inherited, not evidenced here. Same
class as the 13:00 run's vestigial-bundle-guard drift: a surface still telling a pre-release story.

Fixed by making each line true of this tree, not by deleting the history: kept the purge fact, dropped the
unbacked current-tense number and **named the measured current size** (~21 MB packed / ~24 MB on disk /
~4 MB tree, 2026-10-16), stating plainly that 730→1.6 was the 2026-09 purge figure and predates this
history. Also corrected the adjacent RELEASE-NOTES "Fixed" bullet that still read *"bundle freshness is now
guarded"* — same vestigial-guard correction the 13:00 run applied to the CHANGELOG: no `nexus-release.tar.gz`
is committed, so `tools/check_bundle_fresh.sh` no-ops; the shipping model is git clone + `install.sh`. No
claim added that the tree does not bear out. Backed up both files via `scripts/safe-backup.sh` (label
`git-repo-size-truth-2026-10-16`; backups landed under `.nexus/bundle-archive/`, git-ignored, do not ship —
`git status` showed only the two files modified). CI checks re-run green as above; committed, pushed
`origin/main`, local==origin `0 0`. No behaviour change. NOT COMPLETE — Dad's word alone. | proof=none
(docs) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-17 01:00 UTC — release-notes draft said the `v0.1.0` tag "points at the current `main` tip" — it does not (37 commits behind)

Measured live: `git status` clean, `HEAD...origin/main = 0 0` before this run; CI checks green
(`python3 -m py_compile backend/main.py` OK, `bash -n install.sh` OK, `tools/check_self_contained.py`
rc=0 — "15 required files present, lab assets + graders resolve, no developer paths leak"). `origin`
token scopes unchanged — still **no `workflow` scope** (cosmetic `ci.yml` step stays Dad-gated) and no
live host for Screenshots (this box is `192.168.111.40/16`). Both blocked backlog items re-confirmed
blocked.

One in-scope honesty gap, measured and fixed without behaviour change. The prior (19:00) run swept the
`.git`-size claim in `docs/RELEASE-NOTES-v0.1.0-draft.md`; reading the same file end to end this run,
its **second bullet** was also false: *"Tag: `v0.1.0` (annotated), points at the current `main` tip."*

Measured before acting: `git tag -l` → `v0.1.0` **exists**; `git cat-file -t v0.1.0` → `tag` (annotated);
`git rev-parse v0.1.0` → **`26053ef…`** (tag object) / `35e271d` (commit it points at);
`git describe` → **`v0.1.0-37-g4a37ea9`**, i.e. `main`'s tip (`4a37ea9`) is **37 commits past** the tagged
commit. So the tag exists and is on `origin` (`git ls-remote --tags origin` lists it), but it pointed at a
commit that is *not* the current `main` tip and never was after the following 37 doc-only commits landed.
The same file's §Tag-decision also read as though **no tag existed at all** ("No tag is created from this
window … nothing is tagged"), which a reader could only read as "there is no `v0.1.0` tag" — contradicted
by `git tag -l`.

Separately verified the one claim in that file that *could* have been false but is **true**: no GitHub
Release exists — `GET /repos/crperdue73/cirrus-nexus/releases` with the repo's own write token returns
**`[]`**. So the tag ships without a Release; the README's "no GitHub Release exists yet" line is correct
and was left alone.

Fixed by making the draft true of this tree, not by deleting it: the **Tag** bullet now names the actual
tagged commit (`35e271d`), states plainly that it is **37 commits behind** `main` (and that those commits
are doc-only, so the tagged *tree* and `main` differ only in docs), and adds a **GitHub Release: none
exists** line with the measured evidence. The **Tag decision** section now says the tag *exists* and
frames the real open call for Dad (does the existing `v0.1.0` stand as the release point where it sits,
or get re-pointed / re-cut) instead of implying nothing was tagged; the publish checklist and a dated
correction note were updated to match. Added a matching bullet under `[Unreleased] → Changed` in
`CHANGELOG.md` so the sweep's own record stays complete. No claim added that the tree does not bear out.
Backed up both files via `scripts/safe-backup.sh` (label `tag-pointer-truth-2026-10-17`; backups landed
under `.nexus/bundle-archive/`, git-ignored at `.gitignore:48`, do not ship — `git status` confirmed only
`docs/RELEASE-NOTES-v0.1.0-draft.md` and `CHANGELOG.md` modified). CI checks re-run green as above;
committed, pushed `origin/main`, local==origin `0 0`. No behaviour change. NOT COMPLETE — Dad's word
alone. | proof=none (docs) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), and the `.nexus/` public policy call.

## Run 2026-10-17 11:00 UTC — backend told readers "the install record publishes a SET" of substrate digests; it publishes one

Measured live before acting: `git status` clean, `HEAD...origin/main = 0 0`; CI checks green
(`python3 -m py_compile backend/main.py` OK, `bash -n install.sh` OK, `tools/check_self_contained.py`
rc=0 — "15 required files present, lab assets + graders resolve, no developer paths leak", CI's secret
scan regex clean). `origin` token still has **no `workflow` scope** (cosmetic `ci.yml` step stays
Dad-gated) and this box is `192.168.111.40/16` with no route to the live host (Screenshots stays
blocked). Both blocked items re-confirmed blocked.

Swept for a fresh honesty gap: orphan check found **0** (every `.md`/`.py`/`.sh` in the tree is named
somewhere), and every backticked path in `README.md` + `docs/*.md` resolves except placeholder/ellipsis
names and `installed-image-id.txt`, which is deliberately git-ignored and documented as such. So the
gap was not in the docs — it was in a **docstring**, which is where a reader trusts what the code says
about itself.

`backend/main.py::_pinned_substrate_digests` claimed: *"AEGIS ships more than one substrate: the base
(static routing) and the BGP variant (bgpd enabled, for lab-04) ... so the install record publishes a
SET of accepted digests."* Measured false, in four places:

- `install.sh` writes the install record at **one** site (line 393) and emits **only**
  `installed_layers_sha256`; `git grep installed_substrate_digests` matches **no** `.sh` file. So
  `pin.get("installed_substrate_digests", "").split()` is always `[]` — the set half is inert.
- The multi-substrate era was removed **2026-09-20** in commit `0583677`, which deleted installer
  Step 7b ("Step 7b removed 2026-09-20 — it built a substrate the product does not ship").
- `Dockerfile.frr-bgp` is **tracked but built by nothing** — no `docker build`/`load`/`push` reference
  anywhere outside `.nexus/` proof files. A tracked Dockerfile with no consumer reads as a shipping
  substrate.
- Its only consumer, `lab-04-two-as-peering.yml`, is **quarantined** (`lab-definitions-quarantine-2026-09-30/`),
  and `lab-definitions/` contains no `.yml` for it — so "for lab-04" describes a lab this release does not ship.

This is the same class as the 10-16 `_GUIDE_MAP` fossil and the 2026-10-08 `DEMO-LAB` fix: a
pre-release story surviving in unexamined code. It is worse in one way — the docstring was the only
place a reader could learn what the install record contains, and it was wrong about the installer's
contract while the code it described still ran.

Fixed (no behaviour change, no code path altered): the docstring now states that only
`installed_layers_sha256` is written today (with the file:line), that the set-reading branch is
**inert for this release and retained deliberately** (it keeps an older installer's record citable),
and it no longer implies lab-04 or a BGP substrate ships. `docs/architecture.md` corrected in two
places that called `Dockerfile.frr-bgp` a "tested option" / "tested option for future labs": it is now
labelled as built by nothing since Step 7b's removal, kept as static source. Deliberately **not**
deleted — removing a tracked Dockerfile is Dad's call, not a docs sweep's, and the file is harmless
where it sits once labelled honestly.

Backed up all three files via `scripts/safe-backup.sh` (label `substrate-set-truth-2026-10-17`; landed
under `.nexus/bundle-archive/`, git-ignored at `.gitignore:48`, do not ship — `git status` showed only
the three files modified). CI checks re-run green as above; committed `bd4a883`, pushed `origin/main`,
local==origin `0 0`. NOT COMPLETE — Dad's word alone. | proof=none (docstring/docs) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), the `.nexus/` public policy call, and now also
DELETE-OR-KEEP `Dockerfile.frr-bgp` / `lab-definitions-quarantine-2026-09-30/` (both tracked, both
outside the product — his call whether they stay in a public tree).

## Run 2026-10-17 13:00 UTC — README had no maturity signal, and never explained the three names

Measured live before acting: `git status` clean, `HEAD...origin/main = 0 0`; CI checks green
(`py_compile`, `bash -n install.sh`, `check_self_contained.py` rc=0, secret scan clean). `origin` token
still `delete:packages, repo, write:discussion, write:packages` — **no `workflow` scope** (cosmetic
`ci.yml` step stays Dad-gated). Backlog's last unchecked *true* item is Screenshots, still blocked.

Scanned the hardening list against the README (badges, features, architecture diagram, quickstart,
install, screenshots, lab table, grading model, license) and found the README **satisfied nine of ten**.
Two honest gaps were left, both in-scope and unblocked:

1. **No maturity signal.** The badge row said license / python / containerlab / FastAPI / CI — all true,
   but nothing told a visitor that this is a **v0.1.0 early release**. Measured: `git describe --tags`
   → **`v0.1.0-40-g82c8f25`**; the GitHub API returns **`[]`** for `/releases` (no Release published).
   Added a **`status: v0.1.0 — early release`** badge anchored to a new **Release status** section that
   states those two facts with their evidence, plus "no screenshots in this README, none faked".
2. **Three names, no explanation.** The repo is `cirrus-nexus`, the README/product is **AEGIS**, and
   `backend/main.py`'s health card returns `"service": "NEXUS"`; the installer writes
   **`aegis.service`** (`install.sh:436`). Nothing in the README said these are one thing, so a reader
   told to `curl /api` and see "NEXUS" would reasonably wonder what they installed. Added a short
   **Service names** note under Quick start. No behaviour change and no new claim beyond the measured.

Also corrected while measuring: the previous run's plan entry recorded the tag as **37** commits behind
`main`; it is now **40** (`82c8f25` vs `35e271d`). The README states the live figure, not the remembered one.

Backed up `README.md` via `scripts/safe-backup.sh` (label `readme-release-status-2026-10-17`; landed in
`.nexus/bundle-archive/`, git-ignored at `.gitignore:48`, does not ship). All four CI checks re-run green.
NOT COMPLETE — Dad's word alone. | proof=none (docs) |
next=run: next in-scope honesty item; STILL BLOCKED ON DAD: Screenshots (needs live-host session),
cosmetic `ci.yml` step (needs workflow-scoped token), the `.nexus/` public policy call,
DELETE-OR-KEEP `Dockerfile.frr-bgp` / `lab-definitions-quarantine-2026-09-30/`, and the `v0.1.0` tag
re-point/re-cut decision.
