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
python3 start_server.py          # serves on :8000
```

`start_server.py` runs `pkill -f "ttyd.*docker exec"` and `pkill -f "aegis.*main.py"` before starting
`backend/main.py` in the foreground.

> ⚠️ **The second pattern also matches the running service.** The service process is
> `/usr/bin/python3 .../aegis/backend/main.py`, which `aegis.*main.py` matches (verified live
> 2026-09-28: `pgrep -f 'aegis.*main.py'` returns the service PID). Running this script on a host
> where the service is already up **kills it** — and because the service is `Restart=on-failure`,
> systemd may immediately start a *second* server, after which `:8000` is contested.
> **Stop the service first:** `systemctl stop aegis` (or `nexus` on the pre-install layout).

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

## Release bundle

`frontend/nexus-release.tar.gz` is the shippable artifact. It contains exactly the two shipping labs
and the source that runs them:

```
README.md  install.sh  start_server.py  Dockerfile.frr
backend/main.py  frontend/index.html
assets/                                   (aegis-frr-image.tar.gz + frr-image.pin + installed-image-id.txt)
lab-definitions/srl-demo-unsolved/        (demo-01 + its assets/)
lab-definitions/srl-demo2-unsolved/       (demo-02 + its assets/)
lab-definitions/grader_demo_01_srl.py
lab-definitions/grader_demo_02.py
```

**Rebuild it whenever shipping files change** (it is a snapshot, not a symlink to the tree):

```bash
tar czf frontend/nexus-release.tar.gz \
      --exclude='*.bak*' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='clab-*' \
      README.md install.sh start_server.py Dockerfile.frr \
      backend/main.py frontend/index.html \
      assets/ \
      lab-definitions/srl-demo-unsolved/ lab-definitions/srl-demo2-unsolved/ \
      lab-definitions/grader_demo_01_srl.py lab-definitions/grader_demo_02.py
```

- **`--exclude='clab-*'` (added 2026-10-04):** containerlab writes a live instance directory inside
  the lab's own folder — `lab-definitions/<lab>/clab-<lab>-<session>-<node>/` — holding the switch's
  runtime config, `authorized_keys`, and TLS **private keys**. Because the command names the lab
  DIRECTORY rather than individual files, a rebuild done while a session is running sweeps all of it
  into the shippable artifact (it happened once: the tarball grew +38 KB and carried a `ca.key`). The
  exclusion makes it impossible instead of merely unlikely.
- **`assets/` MUST be included:** it carries the ~20.7 MB pinned FRR image plus `frr-image.pin` and
  `installed-image-id.txt`. An earlier command block omitted it, which would have produced a bundle
  with **no substrate image**.

*Historical:* the bundle sat un-rebuilt from 2026-06-13 to 2026-09-28 (3.5 months), shipping neither
current lab nor current code, and was referenced by nothing so nothing flagged it.

---

## Node substrates: what ships, and what is pulled

The two shipped labs need three node images. **Only one travels in the bundle:**

| image | who needs it | shipped? |
|---|---|---|
| `aegis/frr:latest` | the router in LAB-B | ✅ shipped as `assets/aegis-frr-image.tar.gz`, pinned by `assets/frr-image.pin` |
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

## Concurrent sessions

**More than one session of the SAME lab may run at once, and they are fully isolated** (verified
2026-10-05 with two concurrent LAB-A sessions: distinct container names, non-colliding ttyd ports,
and each grade reading its own session's containers). No policy refuses a duplicate start; the UI
avoids them by accident rather than by rule.

**What this costs:** every session consumes its lab's full container set (LAB-A 3, LAB-B 5), and each
switch is a ~2.35 GB image. Nothing caps it — treat "one session per student per lab" as the
operational convention.

---

## Known drift: `Dockerfile.frr` vs the image pin

`assets/frr-image.pin` records the substrate `install.sh` loads:
`dockerfile_sha256=cce15a86…`, `layers_sha256=bb7ef23a…`, `tarball=aegis-frr-image.tar.gz`.

The shipped `Dockerfile.frr` now hashes to `b3046a70…` — changed by commit `0503bc5` (2026-09-20)
whose message said *"Pin/image id unchanged."* The image file was not rebuilt, so **the pin and the
Dockerfile disagree.**

- **The pinned path installs cleanly.** `install.sh` loads the shipped tarball and verifies it against
  the pin on the loaded image's *label* and *layer chain* — both match.
- **A rebuild-from-source would produce a different substrate** (`b3046a70…` ≠ the pin).

Not "fixed" on purpose: choosing which substrate is authoritative is a product decision, not a
lab-local edit. Recorded so the next operator sees both values.

---

## Capstone — Net Eng I PBM

Performance-based measurement out of 100 points (**70 = proficient**):

- **Subnetting (27 pts)** — 192.168.12.0/24 → /25 + /28
- **Device Config (67 pts)** — RTR, SW1, PC-A, PC-B
- **Connectivity (6 pts)** — End-to-end IPv4 + IPv6

The Capstone switch uses **Alpine bridge-utils** (not FRR-as-switch) — cleaner L2 behavior.

---

## Archive

Anything removed from the active lab set is in `10-archive/` and
`lab-definitions-quarantine-2026-09-30/` — retained for reference, not deployed.
