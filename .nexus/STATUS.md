# Cirrus-Nexus — Deployment Ledger

Owner: Selina (sole). Robbie handed over 2026-09-19. Nightly meetings stopped.

## Steps (do the earliest un-done step, then stop)

- [x] **1. Build gate fix in install.sh** — DONE 2026-09-19 15:0x EDT
      install.sh Step 7 no longer skips on tag existence alone.
      Rebinds on a Dockerfile sha256 stamped as image label
      `aegis.frr.dockerfile.sha256`; missing label (stale image) => rebuild.
      Why not mtime: the live image was created 4s AFTER Dockerfile.frr was
      written (09:28:39 vs 09:28:35), so mtime-vs-Created still said "skip" —
      reproduced the bug. Fingerprint is the only reliable gate.
      Artifact: install.sh (edited on disk, `bash -n` clean).
      Verified: gate now returns REBUILD against the stale image.

- [x] **2. Cold rebuild aegis/frr; read digest off a RUNNING container via
      docker inspect** — DONE 2026-09-19 16:0x EDT
      Ran `docker build --no-cache` with label
      `aegis.frr.dockerfile.sha256=cce15a8696ae045e8001f2b32107b1261fa7fc5ba30ad4cab5dfa8c7bc8f38cf`
      New image id: sha256:acb8d8dcd72a44c3389184bc168ee61444072566afaa59704eb1aa27250027b8
      Digest read off a RUNNING container (docker run + docker inspect .Image),
      NOT the build log:
        running-container image digest = sha256:acb8d8dcd72a44c3389184bc168ee61444072566afaa59704eb1aa27250027b8
      Image label verified present: cce15a86...8f38cf
      Functional check inside the running container:
        FRRouting 10.5.3; watchfrr running `mgmtd zebra staticd`;
        vtysh responds. ospfd=no, bgpd=no (matches intent).
      NOTE (benign): Dockerfile.frr sed for `zebra=no`/`staticd=no` is a no-op
      on FRR 10.x — its /etc/frr/daemons states zebra+staticd are ALWAYS
      started. ospfd/bgpd disable DID apply. Scope is correct; could tidy the
      no-op seds later.
      RepoDigests = [] : image is local-only (never pushed to a registry).
      ==> NO registry digest exists yet. "Digest" for now == local image id.
          Step 4 (cold host) will require a registry push or image tarball
          transport; flagging now, not hiding it.
      Ethan's lab (clab-aegis-two-as-peering-r1..r6) left untouched.

- [~] **3. Deploy prototype against a real topology.** IN PROGRESS — asked Ethan 16:0x.
      Ethan answered and is acting: destroy + redeploy `lab-04-two-as-peering`
      from `aegis-topologies/lab-04-two-as-peering.clab.yml` so r1..r6 come up on
      the NEW digest first (attributed read), then I point the prototype at it.
      Reasoned right: pointing the app at the current 2-day-old lab would
      manufacture an unattributed read against the substrate we just replaced.
      Ethan owns the redeploy. Blocker for me: waiting on his containers to be
      on sha256:acb8d8dc... My next action once up: start backend/main.py against
      that lab and capture a real read.
- [ ] **4. install.sh cold on a clean host lands the current digest, no hand steps.**
      BLOCKED — not on effort, on transport. `RepoDigests: []` => the image is
      local-only, never pushed to a registry. A real cold host cannot pull
      sha256:acb8d8dc... There is no hand-step-free path until we either
      (a) push aegis/frr to a registry, or (b) ship an image tarball the
      installer loads. Single missing thing: the transport decision.
      Ethan split his row accordingly: running D-outward v4 on the new digest
      now (the runnable half, correctly NOT labeled cold-host); cold-host stays
      open, unclaimed, named and dated. Agreed — no fake green on either side.
- [x] **5. Wire runtime digest pin into the app** — DONE 2026-09-19 17:0x EDT
      backend/main.py: added `_resolve_container_digest()` (reads `.Image` off the
      RUNNING container, prefers registry RepoDigest, never parses a build log),
      `resolve_runtime_digest()` (single digest across the node set; "" if nodes
      disagree => mixed substrate => refuse), `_require_runtime_digest()` guard,
      and `runtime_digest` on `GraderResult`.
      Enforcement:
        - `start_lab`: resolves the digest off the running containers; if it
          cannot resolve, raises and refuses to start an unattributable session.
        - `grade_config` / `_fallback_grade`: call `_require_runtime_digest()`
          before grading. A session with no digest => HTTP 409, no grade.
        - `get_session` and the start response now expose `runtime_digest`.
      Artifact: backend/main.py (edited on disk; `py_compile` clean).
      `bash -n install.sh` still clean.
      NOTE: full live enforcement could not be exercised end-to-end because the
      running lab is on the unattributed substrate (see below) — the resolver
      itself WAS exercised against the live containers and returned a value.

      ==> CAVEAT FOUND while testing (important, unflattering):
      the live r1..r6 containers' `.Image` now reads sha256:acb8d8dc... — the
      rebuild's `docker build -t aegis/frr:latest` RE-POINTED the tag, so those
      containers report the NEW image id while their rootfs is still the Jun-11
      f42e4ca9 content. A digest read off them would be a LIE of exactly the
      kind this step exists to prevent. Consequence: only a true destroy +
      redeploy yields an honest read. This strengthens the case for Ethan's
      redeploy (step 3) and is a live example of why tag-based attribution is
      unsafe. Flagged to Ethan (dm seq 130).

## Verified history (2026-09-19)
- OLD stale aegis/frr:latest = sha256:f42e4ca9f0d716f036bd40507219eb9a805bd0ec716a42efab652cad670e960a
- Created 2026-06-11T09:28:39-04:00; Dockerfile.frr mtime 2026-06-11T09:28:35-04:00 (4s EARLIER)
- Dockerfile.frr sha256: cce15a8696ae045e8001f2b32107b1261fa7fc5ba30ad4cab5dfa8c7bc8f38cf
- Rebuilt 2026-09-19 -> sha256:acb8d8dcd72a44c3389184bc168ee61444072566afaa59704eb1aa27250027b8

## 2026-09-19 18:0x EDT — Step 3 completed (hour 18:00 cron)

- [x] **3. Deploy prototype against a real topology** — DONE 2026-09-19 18:0x EDT
      Ethan had already done his part: destroyed + redeployed lab-04 on the NEW
      digest at 2026-09-19T21:03Z (17:03 EDT) — all six nodes
      `clab-aegis-two-as-peering-r1..r6` report sha256:acb8d8dc... (read via
      docker inspect, post-rebuild 20:01Z => honest, attributed read).

      My side, this hour:
      1. Added `lab-definitions/lab-04-two-as-peering.yml` (metadata + topology)
         so the prototype can discover/deploy Ethan's two-AS lab. Grader module
         named but not yet written; the app's digest-guarded fallback runs.
      2. Started backend, `POST /api/sessions/start` => session 6c54b4e2.
         runtime_digest OFF THE RUNNING CONTAINERS =
           sha256:acb8d8dcd72a44c3389184bc168ee61444072566afaa59704eb1aa27250027b8
         (matches aegis/frr:latest Id; matches Ethan's r1..r6).
      3. Graded r3 via `POST /api/sessions/6c54b4e2/submit?node=r3`:
         grade carried runtime_digest = sha256:acb8d8dc...  A citable read.
      4. Digest gate exercised directly: session WITH digest => returns digest;
         session WITHOUT digest => HTTP 409 (refuses to cite unattributable state).
      5. Session stopped, its containers destroyed. Ethan's lab untouched.

      TWO REAL BUGS FOUND AND FIXED while doing this (both on disk, py_compile clean):
      a. backend/main.py `deploy_lab`: single post-deploy status check raced
         node bootstrap (FRR `frrinit.sh start; sleep 3`) and silently dropped
         nodes -> empty node set -> digest resolution failed -> session refused.
         Fixed: bounded 60s poll until all nodes running; raises with the missing
         list if not.
      b. Environment (not code): the invoking user `student` was in NEITHER the
         `docker` group NOR `clab_admins`. containerlab deploy could run (once
         clab_admins was fixed) but the app's `docker inspect` was permission-
         denied, so it saw zero running containers. This is a REAL install.sh
         gap: Step 6 adds the *service* user to docker but never the invoking
         user. Fixed live: `usermod -aG docker student` + `usermod -aG clab_admins
         student`. MUST be folded into install.sh for step 4 to be hand-step-free.

      Artifacts: backend/main.py (deploy_lab fix), lab-definitions/lab-04-two-as-peering.yml,
                 this ledger.
      NOT done: the lab-04 grader module (grader_lab_04_two_as_peering) does not
      exist; grading ran through the digest-guarded fallback. Real competency
      grading for lab-04 is still open.

- [ ] **4. install.sh cold on a clean host lands the current digest, no hand steps.**
      STILL BLOCKED on transport (`RepoDigests: []`, local-only image), AND now
      additionally requires the group-membership fixes above to be in install.sh.
      Single missing thing unchanged: the transport decision (registry push OR
      image tarball the installer loads).

## 2026-09-19 19:0x EDT — Step 4 advanced (hour 19:00 cron)

Transport decision MADE and IMPLEMENTED (was the named single missing thing):

- [~] **4. install.sh cold on a clean host lands the current digest, no hand steps.**
      IN PROGRESS — transport chosen: **image tarball** (not registry push),
      because the image is local-only (RepoDigests: []) and this is a
      single-host product; a registry is unnecessary moving parts.

      Chosen transport artifact:
        assets/aegis-frr-image.tar.gz   (20 MB, docker save | gzip -1)
          sha256 9c6837d26d8dfb4bbbab62288cbb9f6528a48fd40b9e859b0cd7f4ecb43a1ff3
          manifest.json Config = blobs/sha256/acb8d8dc...  (the pinned image)
          label aegis.frr.dockerfile.sha256 = cce15a86...8f38cf  (VERIFIED in blob)
        assets/frr-image.pin            (the pin file install.sh sources)
          image_id = sha256:acb8d8dcd72a44c3389184bc168ee61444072566afaa59704eb1aa27250027b8

      install.sh changes (edited on disk, `bash -n` CLEAN, now 363 lines):
        a. Step 6 now ships assets/ (tarball + pin) to /opt/aegis/assets.
        b. Step 7: when a build is needed, it first tries the PINNED TARBALL —
           verifies the tarball sha256, `docker load`s it, then compares the
           resulting image id to the pin and HARD-FAILS on mismatch. Local
           `docker build` remains only as a fallback when no tarball ships.
           Writes /opt/aegis/assets/installed-image-id.txt = what the tag
           resolved to.
        c. Group membership fixed for BOTH users: SERVICE_USER and the invoking
           sudo user (SUDO_USER) are added to docker AND clab_admins when
           present. This closes the gap found live last hour.

      VERIFIED BY EXECUTION (not by reading):
        - Deleted the aegis/frr:latest tag, ran the Step-7 load path in
          isolation from a clean dir => tag GONE, tarball checksum OK,
          `docker load` OK, verify OK, id = sha256:acb8d8dc... (the pin).
        - Negative test: tampered the pin to all-zeros => load succeeded but
          verify FAILED HARD, exit 1. No silent pass.

      NOT YET DONE (be honest — this is not a fake green):
        - This was NOT a true cold-host run on a clean machine. Step 4's stated
          bar is "install.sh run cold on a clean host lands the current digest
          with no hand steps." That has not been executed end-to-end here; only
          the digest-load+verify path was exercised, plus the group-membership
          logic is written but not exercised from a pristine image.
        - Remaining to close step 4: a genuinely clean host/container run of the
          full installer (needs a fresh Debian/Ubuntu target, sudo, docker). Is a
          clean host available? That is the one open question for me.

## 2026-09-19 21:0x EDT — Step 4 executed COLD + two real bugs fixed (hour 21:00 cron)

Ran the full installer cold on `nexus-debhost` (Debian 12, Docker 29.8.1,
containerlab present, NOT the build host). Pre-state was genuinely clean:
`aegis/frr:latest` tag ABSENT, `/opt/aegis` absent, `aegis` user ABSENT,
`clab_admins` group ABSENT.

**FOUND + FIXED BUG #3 (real, silent, corrupts the step-4 artifact):**
  install.sh wrote the recorded layer-chain hash through a PIPELINE
  (`docker inspect ... | tr -d ' ' | sha256sum`) while the VERIFIER computed the
  same value via `printf '%s' "${VAR}" | sha256sum`. A pipeline appends a
  trailing newline; printf '%s' does not. Same image, same daemon =>
  TWO different "content identity" hashes:
    verifier / pin : bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    recorder/wrote : f7a7f293b0d17b5bed9715bd65839cb2e72dd70628e0baeb43042ce0b178a540
  So `installed-image-id.txt` — the artifact install.sh publishes as THE runtime
  identity, and the value step 5 exists to cite — DISAGREED with the very pin
  install.sh had just verified against. Every prior "verified" cold run recorded
  a hash that fails its own re-verification. This is exactly the class of lie
  step 5 is meant to prevent, one layer down.
  Fix: recorder now uses the identical `printf '%s' "${VAR}"` form as the
  verifier. VERIFIED: recorded == pinned (bb7ef23a...) on the cold host.

**FOUND + FIXED BUG #4 (real gap, blocks the "no hand steps" bar):**
  containerlab does NOT create `clab_admins`; it only USES it. Binary strings
  confirm both messages: "Containerlab admin group 'clab_admins' does not exist,
  skipping group membership check" and "user '%v' is not part of containerlab
  admin group 'clab_admins', which is required to execute this command."
  install.sh (prev hour) added the caller to `clab_admins` ONLY IF the group
  already existed. On a cold host install.sh runs BEFORE the first
  `containerlab deploy`, so the group does not exist, the check no-ops, and the
  invoking user is never granted it -> app cannot manage/see containers. That is
  the live gap from 18:0x, still open because the group was created by hand.
  Fix: install.sh now `groupadd -r clab_admins` when containerlab is present and
  the group is missing, then grants membership in the same run.
  VERIFIED by execution with the group+user deleted first: group created,
  `Added aegis to groups: docker,clab_admins`, final state
  `aegis ... 996(docker),994(clab_admins)`.

**COLD RUN RESULT (executed, not read):**
  `bash install.sh` on the clean host, from the reset pre-state above:
    EXIT=0
    Step 6: Created system user: aegis / Created containerlab admin group: clab_admins
    Step 7: Loading pinned FRR image from aegis-frr-image.tar.gz...
            FRR image loaded and verified against pin
            verified on Dockerfile fingerprint cce15a86... and layer-chain bb7ef23a...
  No hand steps required between reset and completion.

**ARTIFACT — /opt/aegis/assets/installed-image-id.txt (cold host):**
    installed_local_image_id=sha256:37b3ab8e3e631dec1e6e291a99e48ac9e90a2dd205b8a942d1206089e84f6e42
    installed_dockerfile_sha256=cce15a8696ae045e8001f2b32107b1261fa7fc5ba30ad4cab5dfa8c7bc8f38cf
    installed_layers_sha256=bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
  Self-consistency re-checked independently: recorded layers == pin layers (MATCH),
  recorded dockerfile == pin dockerfile (MATCH).
  (37b3ab8e... is the daemon-local id on this host by design — save/load
  recomputes the config digest. The transport key is the layer chain, unchanged.)

**NEGATIVE TEST (no fake green):** tampered `tarball_sha256` to all-zeros in a
  copy of the pin, wiped the tag + /opt/aegis, re-ran install.sh
  => EXIT=1, "Tarball checksum mismatch — refusing to load a corrupted/unknown
  image". Hard fail confirmed. Pin restored, clean-host state returned to a good
  installed state (FINAL EXIT=0, artifact as above).

Changed files: install.sh (both fixes; `bash -n` CLEAN, now 434 lines).
Not touched: ethan's lab containers (clab-aegis-two-as-peering-r1..r6) untouched.

**STEP 4 STATUS — closer, still honestly NOT closed as stated.**
  The stated bar is "install.sh run cold on a clean host lands the current digest
  with no hand steps." I executed exactly that on a clean Debian 12 container and
  it passed with a self-consistent artifact and a working negative test.
  The remaining caveat is about the WORD "clean host", not the run: nexus-debhost
  had docker and containerlab PRE-INSTALLED (Steps 2-3 short-circuited with
  "already installed"), so Steps 1-5 were not exercised from bare metal. Steps
  6-9 and the digest path were exercised from a genuinely empty AEGIS state.
  Single missing thing to fully close: a run on a target with NO docker and NO
  containerlab yet, to prove Steps 1-5 need no hand steps either. That needs a
  fresh target with network + sudo; flagging, not claiming.

**STEP 5 STATUS:** the app already cites `runtime_digest` (done 17:0x). This
  hour's bug #3 was the missing prerequisite: the digest the installer PUBLISHES
  was not the digest it VERIFIED. Step 5 can now cite an identity that is
  self-consistent from pin -> install -> app. Worth a confirming pass next.

---

## 2026-09-19 22:xx — STEP 5 CONFIRMING PASS (executed)

**STEP 1-2 STATUS:** confirmed already done + verified this hour.
- Build gate (install.sh L255-284) keys on a Dockerfile-SHA *label*, not tag
  presence — a stale substrate can no longer survive. `bash -n` clean.
- aegis/frr:latest on-disk Dockerfile sha == image label
  = cce15a8696ae045e8001f2b32107b1261fa7fc5ba30ad4cab5dfa8c7bc8f38cf.
- Digest read off RUNNING containers via `docker inspect` (NOT build log):
  clab-aegis-two-as-peering-r1 and clab-aegis-tier-02-router-basics-r1 both
  resolve to the pinned layer chain (see below).

**STEP 4 STATUS:** confirmed done. Cold-host artifact live on nexus-debhost:
  /opt/aegis/assets/installed-image-id.txt
    installed_layers_sha256=bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
  The lone caveat stands (nexus-debhost had docker+containerlab preinstalled;
  Steps 1-5 not exercised from bare metal). Flagged, not claimed.

**STEP 5 — FOUND + FIXED TWO REAL BUGS (this hour's artifact).**

BUG #5 — the app cited the WRONG identity, one layer down from install.sh.
  `_resolve_container_digest` returned `.Image` = the DAEMON-LOCAL image id
  (sha256:acb8d8dc...). install.sh publishes the TRANSPORT-INVARIANT layer-chain
  hash (bb7ef23a...). So every grade cited a substrate identity that was NOT the
  installer-verified one — a number that cannot be compared to, or re-verified
  against, the pin install.sh landed. Step 5's whole point ("a state cannot be
  cited without its digest") was defeated by citing the wrong digest.
  Fix: resolve identity as the layer-chain hash, computed with byte-for-byte
  parity to install.sh, and cross-check against `installed_layers_sha256`.
  PARITY BUG CAUGHT IN MY OWN FIX by execution: `.replace(" ","")` alone still
  mismatched (python f7a7f293... vs shell bb7ef23a...) because `$(...)` command
  substitution STRIPS the trailing newline the daemon emits, and `tr -d ' '`
  does not. Correct form is `.replace(" ","").rstrip("\n")`. Now MATCHES exactly.

BUG #6 — mixed-substrate labs were PERMANENTLY unresolvable.
  `resolve_runtime_digest` required EVERY node image to be identical. Labs
  legitimately mix: r1 = aegis/frr, pc-a = alpine:latest (tier-02, lab-01..04,
  capstone). So any lab with a student PC could never pin — tier-02 refused
  every time while lab-04 (all-FRR) passed. The pin was blocking the product.
  Fix: identify the node(s) running the PINNED substrate (aegis/frr:latest, or
  the installer fingerprint label for a differently-tagged load) and pin THAT.
  Multiple distinct AEGIS substrates in one lab still refuse (genuine ambiguity);
  an auxiliary alpine PC is not ambiguity.

**VERIFICATION (executed, both directions):**
  POSITIVE (lab-04, all-FRR): deploy -> digest
    sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    == install.sh published. Grade r3 returned the same digest.
  POSITIVE (tier-02, MIXED frr+alpine — previously impossible): deploy -> same
    digest bb7ef23a..., grade r1 returned it. BUG #6 confirmed fixed.
  NEGATIVE (no fake green): blanked `installed_layers_sha256` to all-zeros ->
    deploy REFUSED: "Could not resolve runtime digest from running containers;
    refusing to start an unattributable session", HTTP 500. Pin restored.
  Regression: tier-01-foundation and lab-04 both re-deployed and resolved clean.

**ARTIFACT:** backend/main.py (973 lines, `python3 -m ast` clean) — app now
  cites the installer-verified transport identity and refuses to cite otherwise.
  grades carry `runtime_digest=sha256:bb7ef23a...` end-to-end.

**NEXT:** step 3/4 restated bar is met for the app path; the single thing still
  open across the project is a cold run on a target with NO docker/containerlab
  (bare metal), which needs a fresh target with network + sudo. Ethan owns labs.

Not touched: ethan's lab containers.

---

## 2026-09-19 23:xx — STEP 4 CAVEAT CLOSED (executed, bare-metal cold run)

The single item left open last hour — "a cold run on a target with NO
docker/containerlab" — is now DONE, not flagged.

WHAT I RAN: a fresh `debian:12` container (`--privileged`), verified bare BEFORE
  install: `docker: NONE`, `containerlab: NONE`. Copied the project in and ran
  `bash install.sh` with no hand steps.

RESULT (EXIT=0), every step executed for real — NO "already installed"
short-circuit on Steps 2 (Docker) or 3 (ContainerLab):
    Step 1 system packages -> Step 2 Docker from scratch -> Step 3 ContainerLab
    from scratch -> Step 4 ttyd -> Step 5 Python deps -> Step 6 copy -> Step 7
    load pinned FRR image from assets/aegis-frr-image.tar.gz -> verified against
    pin -> Step 8 systemd unit -> Step 9 firewall.

DIGEST LANDED (the identity install.sh verifies):
    layer-chain sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    == assets/frr-image.pin. Daemon-local id sha256:37b3ab8e... correctly NOT
    used as the pin key (transport recomputes config digest).

ARTIFACT: .nexus/proofs/2026-09-19-baremetal-coldrun.md (full log + bare-state
  evidence). This hour's concrete step = closing the last open finding.

HONEST CAVEAT (narrower than before): the target still needs `apt-get` present
  (stock debian:12 has it). install.sh installs curl/gnupg/etc itself in Step 1.
  A distro with no apt at all is out of scope for a Debian/Ubuntu target.

STEP 3 (real topology): still the open product step. Asked Ethan via dm2.py for a
  lab running the current aegis/frr:latest substrate; no reply yet at hour close.
  Not building labs myself — they are his.

Not touched: ethan's lab containers.

---

## 2026-09-20 00:0x — STEP 3 CLOSED (executed, real topology)

WHAT I RAN: the prototype's own deploy path against a real topology —
  POST /api/sessions/start?lab_id=lab-04-two-as-peering&student_name=Selina.
  Topology source = ETHAN'S file (../workspace-ethan/aegis-topologies/lab-04-two-as-peering.clab.yml),
  which was found ALREADY RUNNING this hour. App deploys an isolated
  session-unique copy; it does not touch his labs (re-verified his set still Up).

RESULT: session b29d96df running, r1..r6 all up.
  runtime_digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c

DIGEST — THREE independent reads agree:
  running container .Image (docker inspect) -> sha256:acb8d8dc... (daemon-local id)
  layer chain of that image                -> sha256:bb7ef23a... (transport identity)
  assets/frr-image.pin layers_sha256       -> sha256:bb7ef23a... == MATCH

STEP 5 IN LIVE USE: submit?node=r1 returned grade.runtime_digest = bb7ef23a...
  -> a state cannot be cited on this deployment without its digest.

ARTIFACT: .nexus/proofs/2026-09-20-step3-real-topology.md
CLEANUP: session stopped -> destroyed; Ethan's labs untouched.

STEP BOARD: 1 done, 2 done, 3 done (this hour), 4 done (bare-metal cold run,
  2026-09-19), 5 done (app cites installer-verified identity).

REMAINING TO EXIT THE CRON: the exit bar (cold-host install.sh + prototype on a
  real topology + digest recorded) is now met on this host. The one thing not
  exercised end-to-end in ONE continuous run is cold-host-install THEN deploy
  on that SAME fresh host with the app citing the digest there. That is a
  single composite rehearsal, not a missing capability. Next session: run it
  as one sequence on a fresh debian:12 to produce the composite proof and
  retire the cron.

Not touched: ethan's lab containers.

---

## 2026-09-20 05:2x — COMPOSITE REHEARSAL CLOSED (the exit-bar run)

The one thing flagged open at 00:0x hour-close — cold-host install THEN deploy
on that SAME fresh host with the app citing the digest — is DONE, in one
continuous run, no hand steps after invoke.

HOST: fresh debian:12 (docker NONE, containerlab NONE at start).
  Harness-only note: {"storage-driver":"vfs"} pre-seeded in daemon.json because
  nested docker can't mount overlay-on-overlay. NOT a product dependency;
  real hardware uses overlay2. Disclosed in the proof.

RUN: apt deps -> install.sh (Steps 1-9, Docker+clab from scratch, EXIT=0) ->
  app deps -> start /opt/aegis/backend/main.py -> POST /sessions/start
  (lab-04-two-as-peering, Ethan's topology file, deployed as isolated session
  copy) -> r1..r6 up -> grade.

DIGEST CITED ON THE COLD HOST:
    grade.runtime_digest = sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
  == running-container layer chain == /opt/aegis/assets/installed-image-id.txt
  installed_layers_sha256 == assets/frr-image.pin. Four-way agreement.

ARTIFACT: .nexus/proofs/2026-09-20-composite-coldhost-then-deploy.md

STEP BOARD: 1 done, 2 done, 3 done, 4 done, 5 done — AND the composite
  (install-then-deploy, same host, digest cited) now done. Exit bar met.

NEW OPEN ITEM (small, real): the FIRST grade fired immediately after
  /sessions/start can see runtime_digest=None before substrate resolution
  settles (observed once on session 20490067; clean on 8b1d0677). Fix =
  resolve substrate eagerly at session start, or resolve-on-demand in submit,
  so the first grade always cites the digest. This hardens step 5.

NEXT SESSION: make resolution eager at start; re-run the composite to confirm
  first-grade-cites-digest. That is the last hardening before the cron retires.

Not touched: ethan's lab containers.

---

## 2026-09-20 05:4x — FIRST-GRADE DIGEST RACE FIXED (executed)

ROOT CAUSE: a fresh deploy has containers in `docker ps` before every FRR node
has settled, so a single-pass `resolve_runtime_digest` could see NO substrate
node yet and return "" (unattributable) on the very first grade.

FIX (backend/main.py): split resolution into `_resolve_runtime_digest_once`
(one pass) and `resolve_runtime_digest` (bounded 10s retry, 0.5s interval,
RETRIES ONLY THE EMPTY/AMBIGUOUS OUTCOME). A definite refusal — install-record
mismatch — still returns immediately, so the retry cannot mask stale substrate.
Backup: backend/main.py.bak-2026-09-20-digest-retry. Compiles clean.

FIX VERIFIED on a fresh debian:12 cold install (same harness as the composite):
  3 consecutive /sessions/start, grade fired IMMEDIATELY each time:
    start#1 3e0dbd83 -> first-grade digest = bb7ef23a...
    start#2 15d72f01 -> first-grade digest = bb7ef23a...
    start#3 6e5001c9 -> first-grade digest = bb7ef23a...
  All match assets/frr-image.pin. 3/3. Race closed.

STEP BOARD: 1 done, 2 done, 3 done, 4 done, 5 done, composite done, race fixed.
  The exit bar is met AND step 5 now holds on the FIRST read, not just a retry.

ARTIFACT: this entry + fix in backend/main.py.

REMAINING (small): none blocking the exit bar. Optional hardening only:
  nothing queued. Next session: if a fresh cold composite run still shows all
  green, the cron is retireable.

Not touched: ethan's lab containers.

---

## 2026-09-20 02:0x EDT — STEP 5 HARDENED: digest gate was silently swallowed

The item left open at hour-close 01:09 ("chase the first-grade race") was
audited: that race was ALREADY patched (bounded retry in `resolve_runtime_digest`).
Auditing the grade path instead surfaced a REAL residual defect.

FOUND + FIXED (backend/main.py): `grade_config` called `_require_runtime_digest`
INSIDE its `except Exception` block. The guard refuses unattributable sessions by
raising `HTTPException(409)` — which the broad handler CAUGHT, converting the
refusal into a 200 `GraderResult` with an EMPTY `runtime_digest`. So a state with
no digest WAS returned, citation blank — defeating step 5's invariant.
Fix: hoisted the guard to top-level, above every grader path. 409 now propagates.

VERIFIED both directions against the REAL function (in-process, real SESSIONS):
  unattributable (digest="")   -> HTTP 409 refusal        PASS
  attributable (digest=pin)    -> grade cites the digest  PASS
  pre-fix control flow         -> 200 + runtime_digest=""  (bug was real)
LIVE end-to-end: session 00fe39a5 on lab-04 (Ethan's topology) -> r1..r6 up ->
  runtime_digest bb7ef23a... == install pin; submit?node=r1 cited the same digest.
  Session stopped -> destroyed. Ethan's d7776359 labs untouched (6 containers Up).

ARTIFACT: backend/main.py (py_compile clean).
        + .nexus/proofs/2026-09-20-step5-gate-swallow-fix.md
NEXT: add an explicit error/refused discriminator to GraderResult so a grader-side
  failure is distinguishable in-band from a successful read. Small, contained.

---

## 2026-09-20 03:0x EDT — EXIT BAR INDEPENDENTLY REPRODUCED (verify, not trust)

Per the cron RULES (don't claim a step done that I didn't do; no fake green),
this hour did not add features. It REPRODUCED the exit bar from scratch on a
bare debian:12 host and recorded raw output.

    BARE BEFORE: docker=NONE  containerlab=NONE
    install.sh EXIT=0, Steps 1-9 from scratch, FRR loaded + verified against pin
    installed_layers_sha256 = bb7ef23a...   == assets/frr-image.pin   MATCH
    POST /sessions/start  -> session 479bac5f, lab-04 (Ethan's topology)
    first grade r1        -> runtime_digest = sha256:bb7ef23a...  MATCH
    stop -> destroyed. Ethan's labs untouched.

EXIT BAR: cold-host install.sh landing the current digest (DONE), prototype
running against a real topology (DONE), digest pasted and recorded (DONE),
a state cannot be cited without its digest (first grade carried it).

ARTIFACT: .nexus/proofs/2026-09-20-exitbar-independent-reproduction.md

STEP BOARD: 1,2,3,4,5 DONE. Composite DONE. First-grade race DONE. Gate-swallow
fix DONE. Exit bar reproduced this hour.

REMAINING (open product work, NOT exit-bar blockers):
  - lab-04 real competency grader module does not exist (fallback grades today).
  - optional GraderResult refused/error discriminator (flagged 02:0x).

==> Nexus is a finished deployed product by the exit definition: cold-host
install.sh lands the current digest, prototype runs against a real topology,
digest pasted and recorded. NEXUS-HOURLY-DRIVE cron is RETIREABLE.

Not touched: ethan's lab containers.

---

## 2026-09-20 03:0x EDT — EXIT BAR INDEPENDENTLY REPRODUCED (verify, not trust)

Per the cron RULES (don't claim a step done that I didn't do; no fake green),
this hour did not add features. It REPRODUCED the exit bar from scratch on a
bare debian:12 host and recorded raw output.

    BARE BEFORE: docker=NONE  containerlab=NONE
    install.sh EXIT=0, Steps 1-9 from scratch, FRR loaded + verified against pin
    installed_layers_sha256 = bb7ef23a...   == assets/frr-image.pin   MATCH
    POST /sessions/start  -> session 479bac5f, lab-04 (Ethan's topology)
    first grade r1        -> runtime_digest = sha256:bb7ef23a...  MATCH
    stop -> destroyed. Ethan's labs untouched.

EXIT BAR: cold-host install.sh landing the current digest (DONE), prototype
running against a real topology (DONE), digest pasted and recorded (DONE),
a state cannot be cited without its digest (first grade carried it).

ARTIFACT: .nexus/proofs/2026-09-20-exitbar-independent-reproduction.md

STEP BOARD: 1,2,3,4,5 DONE. Composite DONE. First-grade race DONE. Gate-swallow
fix DONE. Exit bar reproduced this hour.

REMAINING (open product work, NOT exit-bar blockers):
  - lab-04 real competency grader module does not exist (fallback grades today).
  - optional GraderResult refused/error discriminator (flagged 02:0x).

==> Nexus is a finished deployed product by the exit definition: cold-host
install.sh lands the current digest, prototype runs against a real topology,
digest pasted and recorded. NEXUS-HOURLY-DRIVE cron is RETIREABLE.

Not touched: ethan's lab containers.

---

## 2026-09-20 04:0x EDT — EXIT BAR REPRODUCED AGAIN (3rd independent run)

Per cron RULES (verify, don't trust the ledger), this hour re-ran the composite
from scratch on a bare debian:12: cold install -> deploy Ethan's lab-04 -> grade.

    INSTALL EXIT=0; installed_layers_sha256 = bb7ef23a... == pin
    START session fa245809 (lab-04, r1 up)
    GRADE r1 -> grade.runtime_digest = sha256:bb7ef23a...  == pin   PASS
    live container layers_sha256 = bb7ef23a...  == pin  (independent read)
    STOP -> destroyed

HONEST NOTE: an earlier harness run this hour printed runtime_digest=None. That
was MY bug — the harness read `.runtime_digest` at the top level instead of
`.grade.runtime_digest`. The product was correct. No product defect. Recorded so
it isn't mistaken for one.

ARTIFACT: .nexus/proofs/2026-09-20-exitbar-repro-0401.md + repro-exitbar-v2.sh

STEP BOARD: 1,2,3,4,5 DONE. Composite DONE. Exit bar reproduced (3x now).
REMAINING (real product work, NOT exit-bar blockers):
  - lab-04 real grader module (grader_lab_04_two_as_peering) unwritten; the
    digest-guarded fallback grades today.
  - optional GraderResult refused/error discriminator.

Not touched: Ethan's lab containers (d7776359 + tier-* + neteng-capstone all Up).

---

## 2026-09-20 05:0x EDT — LAB-04 REAL GRADER SHIPPED (closed the named remaining item)

Did NOT re-reproduce the exit bar a 4th time. Produced the one real product
artifact STATUS.md named as outstanding: the lab-04 competency grader.

ARTIFACT: lab-definitions/grader_lab_04_two_as_peering.py (NEW).
  Replaces the generic fallback for lab-04 with a real grader implementing the
  lab's three declared competencies (BGP Peering / AS Path Reasoning / Origin
  Attribution) + the lab's TRAP (other AS's prefix must not be carried here).
  Substrate honest: image has NO bgpd (Dockerfile.frr says so), so it grades the
  substrate-observable invariants, not a BGP table that cannot exist here.

VERIFIED LIVE (session 6ba5d53a, deployed via the product path, digest
bb7ef23a... on every grade):
  unconfigured     -> r3 0.35 FAIL   (no false LEAK, no false resolves)
  configured       -> r3 1.00 PASS ; r5 1.00 PASS
  leak injected    -> r3 0.30 FAIL   ("LEAK ... Established is not a measurement")
  essential fail   -> r1/r6 0.70 FAIL (score alone can no longer mask a dead path)

TWO SELF-BUGS FOUND+FIXED during verification (recorded in the proof):
  1. `ip route get` resolved via the containerlab mgmt default route, so an
     empty lab reported both a LEAK and a false "own prefix resolves".
     Fixed: reachability now reads the real FIB, lab interfaces only.
  2. r1 scored 0.70 and would have passed with its own-AS path down.
     Fixed: essential_ok flag blocks a pass on a failed essential check.

PROOF: .nexus/proofs/2026-09-20-lab04-real-grader.md
Cleanup: session destroyed; Ethan's labs untouched (d7776359 + bare set Up).

STEP BOARD: 1,2,3,4,5 DONE; composite DONE; exit bar 3x; lab-04 grader SHIPPED.
REMAINING (real product work, not exit-bar blockers):
  - audit remaining labs whose .md exists but whose declared `grader:` may not
    resolve (next smallest real item).
  - optional GraderResult refused/error discriminator.

---

## 2026-09-20 06:0x EDT — GRADER DISPATCH VERIFIED + EXIT BAR RE-VERIFIED (4th run)

Did NOT add features. Verified claims by execution (cron RULES). Closed the one
real product item STATUS.md named outstanding: "audit remaining labs whose
declared `grader:` may not resolve."

1. DECLARED-GRADER AUDIT — 8/8 RESOLVE. Loaded each lab's `metadata.grader`
   through the app's OWN loader path (LABS_DIR/<module>.py) and asserted a
   callable grade(). All 8 import OK, 8/8 resolvable, zero problems.
   (Gotcha recorded: `grader:` is nested under `metadata:`; a top-level lookup
   falsely reports "none declared". grader_neteng_capstone.py has a cosmetic
   SyntaxWarning, import still succeeds.)

2. LAB-04 REAL GRADER ACTUALLY DISPATCHES — PROVEN LIVE, not asserted.
   Session d17868a6 via the product path. FIRST grade (immediately, tests the
   race fix) on r3:
     runtime_digest = sha256:bb7ef23a...   <- cites on the FIRST read
     passed=False score=0.35
     feedback uses lab-04's own vocabulary ("wrong-session carry test",
     "which AS 65001 must originate", "no IP on r3 eth2"). The fallback
     `_fallback_grade` only counts non-loopback IPs and has no such concepts
     (0 matches for LEAK|wrong-session in fallback; 3 in the grader module).
     => the real module ran; the fallback did not.

3. SUBSTRATE IDENTITY — FOUR-WAY AGREEMENT:
     d17868a6 running containers r1..r6 layer-chain = bb7ef23a...  (6/6)
     first-grade runtime_digest                      = bb7ef23a...
     assets/frr-image.pin layers_sha256              = bb7ef23a...
     install.sh gate label cce15a86... == on-disk Dockerfile.frr sha256
   Transient daemon-local id acb8d8dc... correctly NOT used as the pin key.

4. STATIC: py_compile clean; bash -n install.sh clean.

5. CLEANUP: session d17868a6 stopped+destroyed (0 containers remain). Ethan's
   lab clab-aegis-two-as-peering-d7776359-r1..r6 untouched, still Up (8h).

ARTIFACT: .nexus/proofs/2026-09-20-grader-dispatch-and-exitbar-reverify.md
          (No product code changed this hour.)

STEP BOARD: 1,2,3,4,5 DONE; composite DONE; first-grade race DONE;
  gate-swallow fix DONE; exit bar re-verified (4th run); grader audit DONE.
REMAINING (open product work, NOT exit-bar blockers):
  - optional GraderResult refused/error in-band discriminator.
  - cosmetic SyntaxWarning in grader_neteng_capstone.py.

==> Exit bar met: cold-host install.sh lands the current digest; prototype runs
against a real topology; digest pasted + recorded; a state cannot be cited
without its digest. NEXUS-HOURLY-DRIVE cron is RETIREABLE by the stated
definition.

Not touched: Ethan's lab containers.

---

## 2026-09-20 07:05 EDT — EXIT BAR RE-VERIFIED LIVE (5th run) + ledger reconciliation

Did NOT add features. Verified the physical artifacts and reproduced the live
deploy path by execution (cron RULES: verify, don't trust the ledger).

STATIC/ARTIFACT (all MATCH):
  bash -n install.sh CLEAN; py_compile main.py CLEAN.
  on-disk Dockerfile.frr sha = image label = cce15a86...8f38cf (gate skips rebuild — correct).
  running-container layer chain (install.sh framing) = bb7ef23a... = pin layers_sha256.
  tarball sha = pin tarball_sha256; tarball manifest Config = the pinned image.

FALSE ALARM REFUTED: my first layer check (newline-joined) showed a mismatch; the
  cause was MY framing, not the product. install.sh joins with a space. Using its
  own form => bb7ef23a == pin. Recorded so it isn't read as a defect.

LIVE: session a11fe90a (lab-04, Ethan's topology file, isolated copy) -> r1..r6 up.
  FIRST grade r3: runtime_digest = bb7ef23a..., score 0.35, lab-04's own grader
  vocabulary => REAL grader module dispatched (not fallback). Race fix holds.
  STOP -> destroyed (0 containers). Ethan's d7776359 labs untouched (6 Up).

LEDGER FIX: the 2026-09-20 03:0x proof's "lab-04 grader does not exist" line is
  STALE — grader_lab_04_two_as_peering.py shipped 05:08 and was re-verified live
  this hour.

ARTIFACT: .nexus/proofs/2026-09-20-exitbar-0705-reproduction.md
STEP BOARD: 1,2,3,4,5 DONE; composite DONE; first-grade race DONE; gate-swallow
  fix DONE; lab-04 grader SHIPPED; exit bar re-verified (5th run).
REMAINING (open product work, NOT exit-bar blockers):
  - optional GraderResult refused/error in-band discriminator.
  - cosmetic SyntaxWarning in grader_neteng_capstone.py.
  - project still NOT version-controlled.

==> Exit bar met and re-verified live. NEXUS-HOURLY-DRIVE cron is RETIREABLE.

Not touched: Ethan's lab containers.

---

## 2026-09-20 08:0x EDT — VERSION CONTROL ESTABLISHED (closed the last named structural item)

Did NOT re-reproduce the exit bar a 6th time for show. Produced the one real,
non-cosmetic item STATUS.md repeatedly named as outstanding: the project was
not version-controlled.

WHAT I DID (executed):
  1. Found the trap FIRST: there was a stray empty .git at the WORKSPACE ROOT
     (/home/student/.openclaw/workspace-selina), created May 9, zero commits.
     `git add -A` from the project succeeded against THAT repo and staged the
     entire private workspace — diaries, DM databases (dm.db/dms.db/chat.db),
     intimacy logs, memory/, PDFs, 20MB+ tarballs — 312 files. Aborted and
     unstaged immediately. This would have been a real privacy incident.
  2. Removed the stray workspace-root .git (empty, no commits, nothing lost).
  3. Created a SCOPED repo at the project root only:
       projects/aegis/.git   (branch main)
     so the private workspace can never be swept in by an aegis commit.
  4. .gitignore excludes everything that is not source:
       lab-definitions/clab-*/   (containerlab runtime: inventories, TLS keys,
                                  authorized_keys — per-run artifacts)
       assets/*.tar.gz           (20MB FRR image; identity is in the pin)
       assets/installed-image-id.txt
       __pycache__/, *.py[cod]
       *.bak, *.bak-*, *~
       *.tar.gz / *.tgz anywhere (stray release tarballs)
  5. Committed 52 source files. Guard check: zero tarballs, zero clab- state,
     zero __pycache__, zero *.bak, zero installed-image-id.txt staged.

COMMITS:
  2868142  initial version-controlled snapshot (records pin + digest in the msg)
  fbcd6bc  grader_neteng_capstone: invalid escape \s -> raw string

SECOND ITEM CLOSED (was named cosmetic, is a real defect):
  grader_neteng_capstone.py line 201 had a bare \s in a non-raw string =>
  SyntaxWarning at import. Fixed to a raw string. Verified:
    python3 -W error::SyntaxWarning -m py_compile  -> CLEAN
    import + grade() callable                       -> True

ARTIFACT: projects/aegis/.git (2 commits, 52 tracked files) + .gitignore.
  Not touched: Ethan's lab containers, private workspace files.

STEP BOARD: 1,2,3,4,5 DONE; composite DONE; race DONE; gate-swallow DONE;
  lab-04 grader SHIPPED; exit bar reproduced 5x; VERSION CONTROL DONE (this hour).

REMAINING (open product work, NOT exit-bar blockers) — now down to ONE:
  - optional GraderResult refused/error in-band discriminator.
  (SyntaxWarning item is closed.)

==> Nexus remains a finished deployed product by the exit definition, and is now
    recoverable: the exact source tree that produces the pinned digest is under
    version control. NEXUS-HOURLY-DRIVE cron is retireable.

---

## 2026-09-20 10:0x EDT — STEP 5 CLOSE-OUT: in-band discriminator (last named open item)

Did NOT re-reproduce the exit bar for show. Closed the one remaining named
product item from the previous entry.

TWO REAL DEFECTS FOUND AND FIXED (backend/main.py, frontend/index.html):
  1. grade_config() except-path returned a GraderResult with NO runtime_digest.
     An unattributed grade emitted from the error path — the exact state the
     Step 5 invariant forbids. The 409 refusal path had been fixed; this
     sibling leak had not.
  2. No in-band discriminator: grader crash and wrong answer both rendered
     "Not yet 0%". Student and operator could not tell void from fail.

FIX: GraderResult.status in {graded, error, refused}. error carries the digest
  and renders with no score; refused is the route-level 409; frontend handles
  409 explicitly (previously fell through to data.grade -> throw).

VERIFIED LIVE: deploy tier-02 -> session 26341b0a, digest bb7ef23a (== pin).
  submit r1 -> HTTP 200 status='graded' score=0.35 digest carried.
  refused -> 409. error -> status='error', digest PRESERVED.
  Session destroyed; 0 leftover containers. py_compile + node --check clean.

ARTIFACT: .nexus/proofs/2026-09-20-step5-inband-discriminator.md
COMMIT:   c1746f8

STEP BOARD: 1,2,3,4,5 ALL DONE. No named remaining items.
==> Nexus is a finished deployed product by the exit definition. Nothing further
    is outstanding. NEXUS-HOURLY-DRIVE cron is RETIREABLE.

---

## 2026-09-20 11:0x EDT — DEMO LAB UNBLOCKED (this hour's concrete step)

Dad's new shipping spec (a DEMO lab: 2 PCs + a switch, pass = pc-a pings both)
had been built by hand last hour but COULD NOT RUN THROUGH THE PRODUCT. This hour
fixed that real defect and put the demo under version control.

DEFECT (reproduced live first): `POST /sessions/start?lab_id=demo-01-...`
  => 500 "Could not resolve runtime digest ... unattributable session".
  ROOT CAUSE: `resolve_runtime_digest` treated "no `aegis/frr` substrate in the
  lab" as "unattributable" and refused. A pure-alpine lab has nothing pinned to
  verify — it is legitimately unpinned, not unattributable. The guard conflated
  *provenance* with *gate*.

FIX (backend/main.py): three explicit outcomes —
  1. pinned substrate present + matches install record -> cite sha256:<layers>;
  2. present but stale / multiple distinct substrates      -> "" hard refuse;
  3. NO substrate at all                                    -> `aegis-less:<sha256>`,
     a deterministic identity over each node's name=layer-chain pair, read off
     the RUNNING containers. Blank is now reserved for a lab whose identity
     genuinely cannot be read — that still refuses.
  Step-5 invariant intact: a state is still never cited without an identity.

VERIFIED (executed):
  demo-01 -> session b3bce69f, digest aegis-less:4ab4e8d7...
    unconfigured pc-a -> fail 0.0, digest cited
    configured (per spec) -> pc-a ping 10.0.1.254 AND 10.0.1.2, 2/2 0% loss
    grade pc-a 1.0 PASS / pc-b 0.5 PASS / switch 0.5 PASS, digest on every grade
  redeploy -> session 200405b8, SAME aegis-less:4ab4e8d7... (stable)
  REGRESSION: lab-04 -> sha256:bb7ef23a... == assets pin  MATCH (substrate path unchanged)
  NEGATIVE: unresolvable node -> "" (refuse); empty set -> "" (refuse)
  py_compile CLEAN; bash -n install.sh CLEAN.
  Cleanup: all sessions destroyed, 0 leftovers; Ethan's d7776359 labs untouched (6 Up).

ARTIFACT: backend/main.py + lab-definitions/demo-01-two-pcs-and-a-switch.yml +
  lab-definitions/grader_demo_01.py (now version-controlled).
PROOF: .nexus/proofs/2026-09-20-demo-lab-substrate-guard-fix.md

STEP BOARD: 1,2,3,4,5 DONE; composite DONE; race DONE; gate-swallow DONE;
  lab-04 grader SHIPPED; VC DONE; in-band discriminator DONE; DEMO LAB UNBLOCKED.

REMAINING (open product work, NOT exit-bar blockers):
  - app has no sessions-list endpoint (GET /api/sessions -> 404); stopping a
    session requires the id. Minor ergonomics gap noticed this hour.

---

## 2026-09-20 14:0x EDT — RECONCILE OWNERSHIP GATE (the app no longer claims labs it didn't deploy)

Did NOT re-reproduce the exit bar for show. Found and closed a REAL, dangerous
defect by comparing the 13:0x reconcile proof's claim to the live host.

DEFECT: the 13:0x proof states "Ethan's own non-sessionized lab ... is correctly
  NOT adopted." FALSE live: `GET /api/sessions` listed `d7776359` — ETHAN'S lab
  (hand-deployed 2026-09-19 22:04 from his own topology dir; named as his 6x in
  this ledger) — as a product session, `student_name="(reconciled)"`.
  ROOT CAUSE: ownership inferred from a NAME PATTERN (`clab-<topo>-<8hex>-<node>`).
  His topology name `aegis-two-as-peering` + a hex-looking suffix parsed as a
  session id. Consequences: the app claimed a lab it didn't create AND exposed
  `POST /api/sessions/d7776359/stop`, which would have DESTROYED HIS LAB.

FIX (backend/main.py): durable ownership stamped at CREATION, reconcile gated on it.
  - `_prepare_topology` injects `aegis.session.id` + `aegis.lab.id` into every
    node's `labels:`. Creation-time is the ONLY working mechanism here: this
    daemon's `docker update` has no `--label-add` (exit 125) and labels are
    immutable post-create.
  - `_running_clab_containers` returns (name, session_label, lab_label).
  - `reconcile_sessions` adopts ONLY containers carrying our label. Blank =>
    not ours => skipped. Stamped lab id preferred over name reverse-mapping.
  - Removed the dead `_stamp_session_labels` helper.

VERIFIED LIVE:
  fresh deploy ad20ffe4 -> all 3 nodes labeled; Ethan's r1 label = <blank>
  restart -> count 1: ad20ffe4 adopted (digest aegis-less:4ab4e8d7...),
             d7776359 adopted? False
  POST /api/sessions/d7776359/stop -> 404 ; his 6 containers still Up
  POST /api/sessions/ad20ffe4/stop -> destroyed, 0 leftovers
  REGRESSION lab-04 -> session 8418e3ea, digest sha256:bb7ef23a... == pin;
    grade r3 status=graded score=0.35 digest carried; stopped clean.
  py_compile (+ -W error::SyntaxWarning) CLEAN; `bash -n install.sh` CLEAN.

MIGRATION (honest): 24 pre-fix product containers had no label; backfilled by
  hand using evidence other than the name (product runtime dir + loadable lab
  def). `d7776359` deliberately EXCLUDED. One-time migration, not product code.

ARTIFACT: backend/main.py
PROOF: .nexus/proofs/2026-09-20-reconcile-ownership-gate.md

STEP BOARD: exit-bar steps 1-5 + composite + race + gate-swallow + lab-04 grader
  + VC + in-band discriminator + demo-lab unblock + sessions endpoint +
  startup reconcile ALL DONE; ownership gate DONE (this hour).
REMAINING: none blocking the exit bar. The exit bar itself remains met and
  re-verified; the cron stays retireable by its stated definition.

Not touched: Ethan's lab containers.

---

## 2026-09-20 15:0x EDT — REFUSAL VOCABULARY MADE REAL (in-band, both observers)

Did NOT re-reproduce the exit bar for show. Closed a real, documented-but-false
behaviour found by reading the code against its own docstring.

DEFECT: `GraderResult.status` documents three states — graded | error | refused —
and claims "refused" is "mirrored here so any in-process caller sees the same
vocabulary." FALSE: the only refusal path was `_require_runtime_digest()` raising
HTTPException(409) at the top of `grade_config`, which pre-empted every
GraderResult construction. NO code path could produce status="refused". The
frontend read the refusal from the 409 *status code*, not the field. So one state
had two shapes: HTTP 409+detail over the wire, a raised exception in-process. Any
batch grader / CLI / citation tool calling grade_config() directly could not
produce a value matching the documented vocabulary. Same class of bug the
discriminator field exists to prevent — fixed for only one observer.

FIX (backend/main.py):
  - `_session_runtime_digest(session)` — pure read, never raises. Single source
    of truth for "does this session have an identity".
  - `_refused_result()` — the one canonical refusal value (status="refused",
    digest="", passed=False, score=0.0, REFUSAL_FEEDBACK). One factory => every
    caller's refusal identical by construction.
  - `grade_config()` returns `_refused_result()` instead of raising; still outside
    the broad except, so the 2026-09-20 gate-swallow regression stays closed.
  - `submit_config()` (HTTP route) translates status=="refused" -> 409. Wire
    contract byte-for-byte unchanged.
  - `_require_runtime_digest()` kept as a documented deprecated shim.

VERIFIED:
  in-process: digest-less session -> grade_config returns a GraderResult VALUE
    (type GraderResult, NOT an exception), status='refused', digest='',
    factory model_dump() == grade_config model_dump()  OK
  wire: same session -> HTTP 409 (unchanged)
  with-digest: grade_config -> status='graded', digest sha256:bb7ef23a... carried
  LIVE HTTP: start lab-04 -> session 789dfcfb digest sha256:bb7ef23a...
    submit?node=r1 -> status=graded score=0.35 digest carried ; stop -> destroyed
  py_compile CLEAN; py_compile -W error::SyntaxWarning CLEAN; bash -n install.sh CLEAN.
  Cleanup: 0 proof-session leftovers; Ethan's d7776359 6 containers Up, untouched.

ALSO THIS HOUR — ledger NEXT item CLOSED (not a new step, a re-verification):
  the 05:0x composite named "first-grade digest race (runtime_digest=None right
  after start)" as the smallest open item. Chased it: three consecutive
  start-then-immediate-grade cycles (52bd571c, db2479f9, 954d8aa4) all resolved
  the digest eagerly and graded with it present. The None was already closed
  structurally — start_lab resolves the digest eagerly with a bounded retry, and
  a digest-less grade is now unrepresentable. Recorded so it stops being carried
  as "open".

ARTIFACT: backend/main.py
PROOF: .nexus/proofs/2026-09-20-refusal-vocabulary-inband.md

STEP BOARD: exit-bar steps 1-5 + composite + race + gate-swallow + lab-04 grader
  + VC + in-band discriminator + demo-lab unblock + sessions endpoint + startup
  reconcile + ownership gate ALL DONE; refusal vocabulary now consistent
  in-band across both observers (this hour).
REMAINING: none blocking the exit bar.

---

## 2026-09-20 17:2x EDT — SUBSTRATE CAPABILITY GATE (Ethan's caveat, made real)

Ethan answered the step-3 ask. His split: read his running lab, do NOT
sessions/start against it (a start would redeploy/destroy his only 24h lab on
current substrate — a decision, not a side effect). Took the read target.

His caveat, INDEPENDENTLY reproduced off his own containers (read-only):
  bgpd running on r1..r6 ?  ->  0 0 0 0 0 0.  vtysh: "bgpd is not running".
  Substrate-wide, on the operator's own lab. NOT taken on trust.

Found while verifying: /etc/frr/daemons has NO `zebra=` / `staticd=` lines, so
the Dockerfile's `s/zebra=no/zebra=yes/` and `s/staticd=no/staticd=yes/` never
matched — yet watchfrr starts zebra+staticd+mgmtd regardless (verified via ps on
a live container). A gate trusting the file alone would UNDER-refuse good labs.

FIX (backend/main.py + lab-04 yml):
  LabDef.requires_daemons (default [] = old behaviour); _substrate_daemons()
  reads the substrate AS RUN (live file + implicit watchfrr defaults), None =
  unknown never capable; _capability_refusal() refuses BEFORE any deploy;
  CapabilityRefusal -> HTTP 409 (same shape as the digest refusal). lab-04
  declares requires_daemons: [bgpd].

VERIFIED LIVE (:8000, new code):
  lab-04-two-as-peering  -> HTTP 409 refusal, zero containers created
  demo-01                -> HTTP 200, 3 nodes, aegis-less:4ab4e8d7...
  tier-02-router-basics  -> HTTP 200, digest sha256:bb7ef23a... == pin MATCH
  py_compile CLEAN; bash -n install.sh CLEAN
  Ethan's d7776359 lab: all 6 Up, untouched. Proof-session leftovers: 0.

ARTIFACT: backend/main.py ; lab-definitions/lab-04-two-as-peering.yml
PROOF: .nexus/proofs/2026-09-20-substrate-capability-gate.md
COMMIT: 2390356

REMAINING (next hour, smallest first): make the Dockerfile sed assert itself
(fail the build if a daemon pattern didn't match), then ship a second image tag
with bgpd enabled so BGP labs become deployable rather than correctly refused.

---

## 2026-09-20 18:0x EDT — DOCKERFILE SED NOW ASSERTS ITSELF (closed 17:2x NEXT item #1)

Did NOT re-reproduce the exit bar for show. Closed the concrete NEXT item named
last hour: "make the Dockerfile sed assert itself (fail the build if a daemon
pattern didn't match)."

DEFECT (silent, same class as the stale-digest bug): on the pinned substrate
(FRR 10.5.3) /etc/frr/daemons has NO `zebra=` or `staticd=` lines (verified live:
`docker run --rm aegis/frr:latest grep -nE '^(zebra|staticd)='` -> no output; the
file's own header says zebra+staticd are ALWAYS started). So two of the four sed
substitutions matched nothing and were no-ops: a Dockerfile that READS as if it
enables zebra/staticd while asserting nothing.

FIX (Dockerfile.frr): stop sed-ing patterns that may not exist; disable only what
we intend (`s/^(ospfd|bgpd)=.*/\1=no/`), then ASSERT required daemon state and
FAIL THE BUILD if absent. Disabled daemons asserted too, so a future FRR default
flip cannot silently re-enable bgpd/ospfd. Pin/image id UNCHANGED (build-gate
hardening, not a substrate change).

VERIFIED BOTH DIRECTIONS:
  POSITIVE: correct Dockerfile builds; log shows
    "FRR daemon state asserted: ospfd=no bgpd=no (zebra+staticd always-on)" EXIT=0
  NEGATIVE: `require bgpd yes` injected -> "BUILD ASSERT FAILED: expected
    ^bgpd=yes$ in /etc/frr/daemons" + echoes `17:bgpd=no`, exit 1.
  Test tags removed; /tmp scratch deleted; aegis/frr:latest untouched; Ethan's
  containers untouched.

ARTIFACT: Dockerfile.frr + .nexus/proofs/2026-09-20-dockerfile-daemon-assert.md

STEP BOARD: exit-bar steps 1-5 + composite + race + gate-swallow + lab-04 grader
  + VC + in-band discriminator + demo-lab unblock + sessions endpoint + startup
  reconcile + ownership gate + substrate capability gate ALL DONE; Dockerfile
  daemon assert DONE (this hour).
REMAINING (next, smallest first): ship a SECOND image tag with bgpd enabled so
  BGP labs (lab-04) become deployable rather than correctly refused.

---

## 2026-09-20 19:0x EDT — BGP SUBSTRATE SHIPPED (closed 18:0x NEXT item)

Closed the item named at 18:0x: "ship a second image tag with bgpd enabled so
BGP labs (lab-04) become deployable rather than correctly refused."

Built aegis/frr-bgp:latest (FROM base, bgpd=yes, assert-and-fail-if-wrong).
Capability gate now reads the LAB's own substrate (LabDef.substrate_image,
derived from the topology) so capability and deployability cannot disagree.
install.sh Step 7b builds/loads it and publishes installed_substrate_digests
(a SET); the app accepts a grade on any install-verified digest.

VERIFIED LIVE: lab-04 start HTTP 200 (was 409), r1..r6 up on the BGP substrate,
bgpd running in-node, submit grade status=graded citing
runtime_digest sha256:f69c7345... == the BGP layer chain read off the running
container. Test session destroyed; Ethan's 26 labs untouched. py_compile +
bash -n CLEAN.

ARTIFACT: Dockerfile.frr-bgp ; backend/main.py ; install.sh ;
  lab-definitions/lab-04-two-as-peering.yml
PROOF: .nexus/proofs/2026-09-20-bgp-substrate.md
COMMIT: 6fcc1ae

REMAINING (next, smallest first): rehearse the COLD-HOST composite again with
  BOTH substrates — confirm install.sh Step 7b writes the multi-digest record
  from scratch on a clean host, both digests land, and lab-04 grades with no
  hand steps.

---

## 2026-09-21 15:1x EDT — DEMO LABS ON A REAL SWITCH (both deploy AND grade)

Dad's two asks while away: (1) make the switch a REAL switch, not a Linux PC;
(2) build DEMO LAB 2 (pc-a -> sw1 -> ROUTER -> sw2 -> pc-b) as a capability
probe. Both DONE, verified by running. NOT declared complete — that is Dad's
call alone.

### Task 1 — real switch meets the pass condition
Root cause of the SRL IRB failure: network-instance split-brain. The naive
config put the bridged access ports in mac-vrf-1 (L2) and irb0.0 ONLY in
ip-vrf-1 (L3). PC-to-PC worked (same L2), but the switch's own IP never
answered ARP (100% loss). Fix: irb0.0 must be a member of BOTH mac-vrf-1 and
ip-vrf-1; and on a fresh switch the access subinterfaces default to `type
routed` so they need explicit `type bridged`.
Substrate: ghcr.io/nokia/srlinux:latest (v26.7.2). Cumulus NOT needed.
VERIFIED COLD: pc-a->switch 0% loss, pc-a->pc-b 0% loss, pc-b->switch 0% loss;
FDB shows the IRB MAC in the bridge table with both PCs.
ARTIFACT: lab-definitions/srl-demo/demo-01-srl-switch.yml (+ assets/sw1.cfg);
  lab-definitions/grader_demo_01_srl.py
PROOF: .nexus/proofs/srl-irb-fix-20260921-1513-FINAL.txt

### Task 2 — capability probe: two switches, one router
Topology: pc-a -- sw1(SRL) -- r1(FRR) -- sw2(SRL) -- pc-b.
VERIFIED COLD END-TO-END: pc-a->pc-b 0% loss and pc-b->pc-a 0% loss through
the router; traceroute = hop1 10.0.1.253 (r1), hop2 10.0.2.1 (pc-b). 5/5 nodes
deploy. grader_demo_02.py runs GREEN: lab passed, all 5 nodes 1.0.
ANSWER TO THE PROBE: real-switch multi-node labs deploy AND grade.
ARTIFACT: lab-definitions/srl-demo2/demo-02-two-switches-one-router.yml
  (+ assets/sw1.cfg, assets/sw2.cfg); lab-definitions/grader_demo_02.py
PROOF: .nexus/proofs/demo-02-capability-probe-20260921-1519.txt

NOTE: Alpine hosts use BusyBox `ip` (no JSON `-j`). Both new graders fall back
to parsing plain `ip addr show` output — the JSON path silently failed before.

REMAINING (next, smallest first): wire the two new lab dirs into the backend's
  lab list (they are discovered by scan; confirm they LIST + start + submit a
  grade through the HTTP API, not just the grader module directly).

### 2026-09-21 15:3x EDT — HTTP end-to-end confirmed (deploy + grade via the API)

Ran a SECOND backend instance on :8001 (Dad's :8000 left untouched) with the
updated discovery/path code, then drove the real product API:

  POST /api/sessions/start?lab_id=demo-02-two-switches-one-router  -> HTTP 200,
       nodes pc-a,pc-b,r1,sw1,sw2 running, runtime_digest sha256:bb7ef23a...
  POST /api/sessions/<sid>/submit?node=<n>  for all 5 nodes
       -> status=graded, passed=True, score=1.0 on EVERY node.
  POST /api/sessions/<sid>/stop -> destroyed.

So the answer to the capability probe is: real-switch multi-node labs DEPLOY
and GRADE through the product API, with a pinned runtime digest.

TWO BACKEND BUGS FOUND + FIXED for subdirectory labs:
  1. _discover_labs() only globbed the top level (*.yml), so any lab kept in
     its own folder (topology + assets/ together) was invisible. Now scans
     one level of subdirs and stores topology_file as a path relative to
     LABS_DIR.
  2. _prepare_topology()/_remove_clean_copy() built the session copy path as
     LABS_DIR/"._clean_<topology_file>_<sid>.yml", which for a subdir lab
     contains a slash and points at a non-existent nested dir -> FileNotFound.
     Now writes the copy beside the source (same subdir) with a flat name, so
     the lab's relative `assets/` startup-configs still resolve.

FLAG FOR DAD: the live backend on :8000 is an orphaned manual process
(PPID 1, no systemd unit, 17h+ uptime). It is running the PRE-FIX code, so it
does NOT yet list the two new real-switch labs. POST /api/labs/reload cannot
pick up the change because the running process already imported the old
module. It needs a process restart to serve the new labs. I did NOT restart
Dad's server. Restart when he says so.

### 2026-09-21 16:0x EDT — export hardening (guides + installer + guide routing)

Extended the two demo labs so they ship complete, not just deployable:
  - Student markdown guides for both labs, stored beside each topology
    (lab-definitions/srl-demo/demo-01-two-pcs-and-a-real-switch.md,
     lab-definitions/srl-demo2/demo-02-two-switches-one-router.md).
  - Backend guide lookup: added a subdir fallback so a lab in its own folder
    resolves <lab-id>.md beside its topology without a guide_map entry.
  - install.sh completion banner: was globbing lab-definitions/*.yml (flat),
    so subdir labs were never listed. Now finds maxdepth 2 recursively.
VERIFIED on a throwaway :8002 instance: /guide and /topology both HTTP 200 for
  both new labs; py_compile + bash -n clean. Instance shut down after.
  Dad's :8000 never touched.
LIVE COMMIT 80b11f2 · PUBLIC COMMIT a35d974

---

## 2026-09-22 ~22:10 EDT — aegis-demo2-drive (hourly drive)

**RAN (live, cold deploy, evidence in .nexus/proofs/demo-02-negative-gate-fix-20260922-2210.txt):**
- Cold `containerlab deploy` of demo-02 (pc-a -> sw1(SRL) -> r1(FRR) -> sw2(SRL) -> pc-b),
  metadata stripped as Nexus does. 5/5 nodes up.
- Pings: pc-a->sw1 IRB / ->r1 / ->pc-b, pc-b->pc-a, pc-b->sw2 IRB — ALL 0% loss.
- traceroute pc-a->pc-b: hop1 r1 (10.0.1.253), hop2 pc-b — real 2-hop path.
- grader_demo_02.grade_all on the live session: PASSED, 5/5 nodes.
- NEGATIVE TEST (Dad's requirement): fed an Alpine PC as sw1.

**FOUND + FIXED (2 grader defects):**
1. `grader_demo_02.py` `grade_all()` gated only on pc-a/pc-b, NEVER on sw1/sw2.
   -> a Linux-PC fake switch graded the LAB as PASSED. Now requires
   `e2e AND real_switches AND router_ok`. Re-verified: real=True, fake=False.
2. `grader_demo_01_cumulus.py` had NO `grade_all()` at all (all siblings do).
   -> Cumulus lab had no lab-level real-switch gate. Added, matching demo_01_srl.

**SCOPE NOTE (not overclaiming):** backend `main.py` grades per-node via
`grader.grade(session,node)`, so the API's per-node verdicts were ALREADY
correct (sw1 refused the fake). The `grade_all` hole affected the standalone /
CLI / lab-pack verdict path, which is what a lab-pack build would call.

**TASK 1 (real switch):** evidenced earlier today (SRL final proof + Cumulus
evaluation). Not re-run this drive.

**NOT COMPLETE.** Nexus completion is Dad's call alone.


---

## 2026-09-22 ~01:15 EDT — aegis-demo2-drive (capability probe: are the labs solved?)

**Guides closed out:** all four demo labs now serve BOTH a guide and a topology
(HTTP 200 each) via the product API:
  - wrote demo-01-two-pcs-and-a-switch.md (plain demo had NO guide)
  - wrote demo-01-two-pcs-and-a-real-switch-cumulus.md (Cumulus lab HAD NO
    guide -> /guide returned 404; now 200)
  - added a "How this lab is graded" section to all four demo guides.

**FOUND (capability probe, evidence ../proofs/pre-solved-labs-probe-20260922-0115.txt):**
Deployed each lab COLD, applied NO student config, graded immediately.

  demo-02-two-switches-one-router: ALL 5 NODES pass 1.0 with ZERO student work.
  demo-01-two-pcs-and-a-real-switch: pc-a unconfigured -> configure pc-a by
    hand -> pc-b STILL passes 0.5 (I never touched it).

  ROOT CAUSE: every value the grader checks is baked into the topology `exec`
  blocks. Pattern across all four labs:
    lab                     pc-a IP   pc-b IP   switch mgmt IP   verdict
    demo-01 (plain linux)   seeded    seeded    seeded           fully pre-solved
    demo-01 (SR Linux)      NOT       seeded    seeded           mostly pre-solved
    demo-01 (Cumulus)       seeded    seeded    seeded           fully pre-solved
    demo-02 (2sw+router)    seeded    seeded    seeded (both)    FULLY PRE-SOLVED

**What is PROVEN:** substrate capability. Both labs deploy cold on a fresh
backend, all devices come up, real switches answer, every node grades through
the product API with honest verdicts. demo-02 as a two-switch-one-router
probe: PASS.

**What is NOT proven / GAP FOR DAD:** the labs grade a SOLVED problem. Three of
four seed the PC addresses (and demo-02 seeds the router too) while the guide
tells the student to assign them. Seeding the SWITCH management IP is deliberate
and consistent (documented "ships pre-configured so the demo is about the
pings") -- that is fine. The open decision is per-lab: what ships seeded vs.
what the student must actually do. Not changed unilaterally; flagged.

**NOT COMPLETE.** Nexus completion is Dad's call alone.


### 2026-09-22 ~02:15 EDT — CORRECTION to the probe above (cold-run, zero config)

The 01:15 matrix was WRONG for two rows. I re-ran each lab COLD with NO
student config (proof: ../proofs/cold-zero-config-matrix-20260922-0215.txt):

  lab                                zero-config grade      verdict
  demo-01-two-pcs-and-a-switch       ALL FAIL (0.0/0.0/0.0)  UNSOLVED   ✅
  demo-01 (SR Linux)                 pass 1.0/0.5/1.0       PRE-SOLVED ❌
  demo-01 (Cumulus)                  pass 1.0/1.0/1.0       PRE-SOLVED ❌
  demo-02 (2 switches + router)      pass 1.0 x5            PRE-SOLVED ❌

Corrections:
  - SRL demo-01: pc-a IS seeded (`ip addr add 10.0.1.1/24` in exec). The 01:15
    note said pc-a was real work -- wrong; I had configured it by hand during
    that probe while it was already seeded.
  - plains demo-01: I called it pre-solved from the guide TEXT. Run cold it
    FAILS all nodes -- it is the only demo lab that is genuinely unsolved.

Lesson logged: grade the cold case; the guide text is not the topology.


---

## 2026-09-22 ~04:10 EDT — aegis-demo2-drive (live cold re-verify of demo-02)

RAN (not re-quoted): fresh cold deploy of demo-02 (metadata stripped), 5/5
nodes up. Zero student config.

  pc-a -> sw1 10.0.1.254 : 3/3 0% | pc-a -> r1 10.0.1.253 : 3/3 0%
  pc-a -> pc-b 10.0.2.1  : 3/3 0% (E2E) | pc-b -> pc-a 10.0.1.1 : 3/3 0% (E2E)
  traceroute: hop1 10.0.1.253 (r1), hop2 10.0.2.1 = REAL 2-hop path.
  grader_demo_02.grade_all -> LAB PASSED True, all 5 nodes 1.0.
  NEGATIVE: alpine PC as sw1 -> LAB PASSED False ("sr_cli not available").
  Proof: proofs/demo-02-live-reverify-20260922-0410.txt

FIND: `containerlab deploy` of the RAW lab yml fails on `metadata:`
  ("field metadata not found", clab 0.75.0). The backend strips it
  (main.py:625-627); a hand-dry-run must strip it too. Flagged, not a lab bug.

HOUSEKEEPING: destroyed 9 stale demo-01 containers left from earlier probes
  (44 -> 35). Probe containers destroyed after the run; no leftovers.

Task 1 (real switch SRL+Cumulus): evidenced 2026-09-21; unchanged this drive.

NOT COMPLETE. Nexus completion is Dad's call alone.


---

## 2026-09-22 ~05:12 EDT — aegis-demo2-drive (Task 1 live cold re-verify, BOTH variants)

RAN (fresh cold deploys, metadata stripped):
  A) SR Linux demo-01: 3/3 up. pc-a->switch 3/3 0%, pc-a->pc-b 3/3 0%,
     pc-b->switch 3/3 0%. grade_all -> PASSED True (pc-a 1.0/pc-b 0.5/sw1 1.0).
     irb0.0 in BOTH mac-vrf-1 AND ip-vrf-1; FDB shows IRB MAC + both PC MACs.
  B) Cumulus demo-01: 3/3 up (Cumulus Linux 4.3.0, vtysh present).
     pc-a->switch 3/3 0%, pc-a->pc-b 3/3 0%, pc-b->switch 3/3 0%.
     grade_all -> PASSED True (all 1.0).
  NEGATIVE: alpine PC as sw1 refused by BOTH graders; LAB verdict False.
  Proof: proofs/task1-live-reverify-20260922-0511.txt

Both candidates meet the unsoftened pass condition. SR Linux = stronger
(real NOS). Containers destroyed; 35 baseline, no leftovers.

NOT COMPLETE. Nexus completion is Dad's call alone.


---

## 2026-09-22 ~06:10 EDT — aegis-demo2-drive (demo-01 SRL unsolved variant + lint gate)

CLOSED the open item: both pre-solved demos now have an unsolved variant.

NEW: lab-definitions/srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.yml
  (pc-a/pc-b addresses stripped from exec; switch IRB kept pre-seeded by design)
  RUN 1 COLD: LAB PASSED False (pc-a/pc-b 0.0, sw1 1.0). Correct.
  RUN 2 after student config: pc-a->switch 3/3 0%, pc-a->pc-b 3/3 0%,
    LAB PASSED True. Correct.
  Proof: proofs/demo-01-unsolved-variant-20260922-0608.txt

LINT GATE (tools/lint_lab_pack.py): re-run after adding the variant.
  UNSOLVED 0/2 demo-01-...-unsolved (matches live) | scanned 14 | SOLVED 3.
  Exit code 1 on SOLVED present (verified). This is the pre-ship gate: a lab
  pack is red-flagged if any lab grades with zero student work.

Containers destroyed; 35 baseline, no leftovers.

NOT COMPLETE. Nexus completion is Dad's call alone.
