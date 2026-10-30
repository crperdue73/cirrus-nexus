# AEGIS — Operations Notes

The detail behind the README: how to run, ship, and reason about the system, plus the known drift.
Everything here was measured on a live host; it is not aspirational.

---

## Running the server

**Installed, the server runs as a systemd service.**

```bash
systemctl start aegis        # start
systemctl enable aegis       # start at boot
systemctl status aegis       # check
journalctl -u aegis -f       # logs (also written to /var/log/aegis.log)
```

The installer sets `User=aegis`, `WorkingDirectory=/opt/aegis`, and
`ExecStart=python3 /opt/aegis/backend/main.py`.

### Running without the service

```bash
cd /opt/aegis
python3 start_server.py          # serves on :8000 (AEGIS_HOST/AEGIS_PORT honoured)
```

What it does, in order:

1. `pkill -f "ttyd.*docker exec"` — clears leftover terminals from previous runs.
2. `pkill -f` on **this tree's own absolute backend path** — stops only a server started from the
   same directory, never one installed at `/opt/aegis` from somewhere else.
3. Starts `backend/main.py` in the foreground-logged background (log: `/tmp/aegis-server.log`), then
   waits up to 15 s for `GET /api` — on `AEGIS_HOST`/`AEGIS_PORT` if you set them, else `127.0.0.1:8000`.
   It also fails fast if the child **exits**, printing the real log instead of an empty one.

> ⚠️ **If the systemd service is running, this script will not take over `:8000`.** It only kills a
> server launched from its own directory, so on an installed host the service keeps the port, the new
> process dies immediately, and the script now reports that failure (exit 1, with the log) instead of
> reporting the old server's answer as success. **Stop the service first:** `systemctl stop aegis`
> (or `nexus` on the pre-install layout).
>
> (Corrected 2026-10-30. This section previously said the kill pattern was `aegis.*main.py` and that
> it therefore matched the service — that was true of a 2026-09-28 build. The pattern was narrowed
> later the same week; the docs were not, so they described a hazard the tree no longer has and
> omitted the one it does have.)

`start_server.py` resolves `backend/` relative to its own location, so it works from any install
directory.

> **Note on unit names:** this repository's installer creates `aegis.service`. A **full host reboot
> still loses any running lab** — student containers are not restored on boot. (Tracked as an open
> lifecycle item.)

---

## Lab definitions are cached — reload after editing

Lab definitions are loaded from disk **once**, then **cached in memory** for the life of the server
process. Editing `lab-definitions/grader_*.py` (or a topology `.yml`) and re-grading a node **will
not pick up your change**.

**Reload without a restart:**

```bash
curl -X POST http://localhost:8000/api/labs/reload
# -> {"status":"reloaded","count":2}   (the labs on THIS host)
```

*Why this note exists:* verifying a grader fix without reloading looks like the fix did nothing.
Measured 2026-09-28: with the cache warm, an edited grader kept returning the old score until
`/api/labs/reload` was called; the same edit applied immediately in a fresh process.

---

## Release bundle (historical — not shipped in this tree)

**The current shipping model is a git clone.** The README quickstart and `docs/SELF-CONTAINED.md`
are the source of truth: a clean host clones this repo and runs `install.sh`. **No `nexus-release.tar.gz`
(or any other bundle tarball) is committed to this tree** — measured live 2026-10-11: `find . -name
'*.tar.gz'` returns nothing outside `.git/`.

The `nexus-release.tar.gz` bundle was the **older** shipping path. It is documented here because the
rebuild command in an earlier revision of this file implied the bundle was live; that is no longer
true. When the bundle *was* the shippable artifact it contained exactly the two shipping labs and the
source that runs them:

```
README.md  install.sh  start_server.py  Dockerfile.frr
backend/main.py  frontend/index.html
assets/                                   (frr-image.pin only — the tarball and installed-image-id.txt never ship)
lab-definitions/srl-demo-unsolved/        (demo-01 + its assets/)
lab-definitions/srl-demo2-unsolved/       (demo-02 + its assets/)
lab-definitions/grader_demo_01_srl.py
lab-definitions/grader_demo_02.py
```

Lessons from that era are kept because `tools/check_bundle_fresh.sh` still exists and will act **only
if a bundle is present** (it no-ops otherwise):

- **`--exclude='clab-*'` (added 2026-10-04):** containerlab writes a live instance directory inside
  the lab's own folder — `lab-definitions/<lab>/clab-<lab>-<session>-<node>/` — holding the switch's
  runtime config, `authorized_keys`, and TLS **private keys**. Because the archive command named the
  lab DIRECTORY rather than individual files, a rebuild done while a session is running swept all of
  it into the artifact (it happened once: the tarball grew +38 KB and carried a `ca.key`). The
  exclusion makes it impossible instead of merely unlikely.
- **`assets/` must be included** if a bundle is ever rebuilt: today the *tracked* contents are
  `frr-image.pin` (which *names* `aegis-frr-image.tar.gz`). An `installed-image-id.txt` may exist on a
  live host but it is git-ignored (`.gitignore`), so it does **not** ship. In the bundle era it also carried the
  ~20.7 MB pinned FRR tarball itself; that tarball does **not** ship in this tree, so a rebuild here
  would need to reproduce it first or fall back to a local `aegis/frr:latest` build.

---

## Node substrates: what ships, and what is pulled

The two shipped labs need three node images. **None ships as a tarball in this tree:**

| image | who needs it | shipped? |
|---|---|---|
| `aegis/frr:latest` | the router in Demo 2 (`demo-02-two-switches-one-router-unsolved`) | ❌ built locally by `install.sh` from `Dockerfile.frr` — the pin's tarball (`aegis-frr-image.tar.gz`) is *not* in this tree |
| `ghcr.io/nokia/srlinux:latest` | the REAL switch in both labs | ❌ pulled at deploy time — **~2.35 GB** |
| `alpine:latest` | the PCs | ❌ pulled at deploy time (small) |

`install.sh` (Step 7c) pre-pulls the two registry images **before** creating the service, so a blocked
registry fails early with a clear message. On a host with no internet, load them by hand first:

```bash
docker pull ghcr.io/nokia/srlinux:latest alpine:latest
```

---

## Runtime digests come in TWO forms

Every session carries a `runtime_digest`. It is **not** always `sha256:` — there are two schemes, and
both are honest identity:

| form | when | what it is |
|---|---|---|
| `sha256:<layers>` | the lab includes the **AEGIS substrate** (any `aegis/frr` node) | the pinned substrate's content-addressed layer chain |
| `aegis-less:<sha256>` | the lab runs **no AEGIS substrate** | a deterministic hash over each node's `name=layer-chain` pair |

For the shipping two labs: **demo-01 → `aegis-less:`** (no FRR node) and **demo-02 → `sha256:`**
(verified live 2026-10-02: demo-02's digest equals the pin's `layers_sha256`). A lab whose identity
cannot be read off the running containers at all returns `""` — a hard refusal, not a third style.

---

## Stopping a session

What a failed stop actually means, read off `backend/main.py` and `scripts/clab-reaper.sh`:

- **A failed stop leaves the session listed, on purpose.** `stop` tears the lab down *first* and only
  then removes the session and frees its `ttyd` ports (RUN 209, `POST /api/sessions/{id}/stop`). A
  teardown error surfaces as HTTP `500` with "the session is still listed and its containers may still
  be running — press End Lab again." So **press End Lab again**: that is the retry the code is asking
  for. Earlier versions popped the session first and swallowed the error, which reported
  `{"status": "destroyed"}` over containers that were still running.
- **`404` means the session id is unknown**, not that the lab is still up: the route looks up the
  session before touching anything, so a second stop on an already-forgotten id is a `404`. Check
  `GET /api/sessions` to see what is actually live.
- **The stop takes the deploy lock; a concurrent `start` waits on it.** Teardown and port release run
  inside the same lock `start` allocates ports under, so a start cannot grab a port a stop is about to
  free. Grading is deliberately *not* under that lock (a grade takes tens of seconds).
- **Sessions are in memory; the containers are the record.** On startup `reconcile_sessions()` rebuilds
  the session view from the `aegis.session.id` label the deployer stamps on every node, so a restart
  does not orphan a lab that carries its label. A `clab-*` container with **no** label can never be
  matched back to a session — `stop` cannot find it. That is what `scripts/clab-reaper.sh` is for: its
  default `--orphans` mode reaps only labs the running app does not claim, and it refuses to reap
  anything when `/api/sessions` cannot be read (exit 3) or when any `clab-*` container is unlabelled
  (exit 4) — "could not ask" is not "nothing is owned."

---

## Concurrent sessions

**More than one session of the SAME lab may run at once, and they are fully isolated** (verified
2026-10-05 with two concurrent Demo 1 (`demo-01-two-pcs-and-a-real-switch-unsolved`) sessions:
distinct container names, non-colliding ttyd ports,
and each grade reading its own session's containers). No policy refuses a duplicate start; the UI
avoids them by accident rather than by rule.

**What this costs:** every session consumes its lab's full container set (Demo 1 = 3 nodes, Demo 2 = 5), and each
switch is a ~2.35 GB image. Nothing caps it — treat "one session per student per lab" as the
operational convention.

---

## Known drift: `Dockerfile.frr` vs the image pin

`assets/frr-image.pin` names the substrate `install.sh` *would* prefer to load:
`dockerfile_sha256=cce15a86…`, `layers_sha256=bb7ef23a…`, `tarball=aegis-frr-image.tar.gz`.

The shipped `Dockerfile.frr` now hashes to `b3046a70…` — changed by commit `0503bc5` (2026-09-20)
whose message said *"Pin/image id unchanged."* The image file was not rebuilt, so **the pin and the
Dockerfile disagree.**

- **The pinned path is not taken here.** `install.sh` loads the tarball *only if* it is present; the
  pin's `tarball=aegis-frr-image.tar.gz` is **not in this tree** (measured live 2026-10-11; the tracked
  contents of `assets/` are only `frr-image.pin` — `installed-image-id.txt` is git-ignored and does not
  ship). So a cold clone falls to the
  build-from-source fallback below.
- **The fallback builds a different substrate.** With no tarball, `install.sh` runs
  `docker build` from `Dockerfile.frr` (`b3046a70…`), which installs and self-heals normally but does
  **not** reproduce the pin's `layers_sha256` (`bb7ef23a…`). That is expected, not a failure.
- **The installer now says so itself (added 2026-10-27).** Step 7 reads the pin and compares its
  `dockerfile_sha256` with the sha256 of the `Dockerfile.frr` it is about to build. On this tree they
  disagree, so the install prints a four-line warning naming both values and stating that building
  from the current source is the correct path and a pinned-tarball restore would not be. It **warns,
  it does not fail**: the fallback is legitimate and a hard stop would turn a documented drift into a
  broken install. When the pin is brought back in line with the Dockerfile the warning disappears
  with no installer change. Verified both directions on 2026-10-27 (stale pin → four warnings;
  pin rewritten to the current hash → silent).

Not "fixed" on purpose: choosing which substrate is authoritative is a product decision, not a
lab-local edit. Recorded so the next operator sees both values.

---

## Capstone — Net Eng I PBM (curriculum context, not a shipped lab)

The course outline describes a **performance-based measure** (PBM) out of 100 points, **70 = proficient**:

- **Subnetting (27 pts)** — a /24 into /25 + /28
- **Device Config (67 pts)** — RTR, SW1, PC-A, PC-B
- **Connectivity (6 pts)** — end-to-end IPv4 + IPv6

The three sub-scores above sum to **100**, and the only in-tree artifact that carries them is
`lab-guides/lab-03-lock-it-down.md`, which cross-references the capstone (it names 192.168.12.0/24,
"Auto-graded (100 pts)", and "70% = pass"). **Those numbers are read directly from that shipped guide;
the capstone itself is not one of the two labs in this tree and is not auto-graded by either shipping
grader.**

---

## Archive

Anything removed from the active lab set is retained for reference, not deployed, in **two separate
places — neither is inside `10-archive/`**:

- `lab-definitions-quarantine-2026-09-30/` — the topologies, guides and graders pulled from
  `lab-definitions/` on 2026-09-30 (46 tracked files; the file list is its `MANIFEST.txt`).
- `10-archive/` — an older, smaller archive: `tier-03-bgp-simplified.yml`, the two FRR configs it
  binds (`10-archive/frr-configs/`), and `SUMMARY-for-Dad.md`.

Neither directory is read by the loader (it globs `lab-definitions/**/*.yml` only).

Provenance for the older layout is in [`10-archive/SUMMARY-for-Dad.md`](../10-archive/SUMMARY-for-Dad.md),
a dated 2026-06-09 topology audit. It describes a tree that predates this release (its
`aegis-topologies/` paths do not exist here) — read it as history, not as the shipping tree.
