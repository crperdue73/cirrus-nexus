# AEGIS — Conference Operator Cheat Sheet

*Give this to anyone running the booth.*

> **Status: draft / not maintained.** This sheet predates the current tree. Some sections below
> describe an older release (a `tar xzf` bundle install, the `AEGIS` service name) that this tree no
> longer matches. Where this sheet and the shipped code disagree, **the code and [`README.md`](README.md)
> win.** The install and lab-catalog sections have been corrected to today's tree; the two walk-up
> labs below are the ones that actually ship.

---

## Before the Conference

### Server Requirements
- Debian or Ubuntu VM / laptop
- 4 GB RAM minimum, 8 GB recommended
- 20 GB free disk
- Internet access for first-time install (docker pulls images)

### Install

**No bundle ships in this tree.** The shipping model is a git clone plus `install.sh`
(`find . -name '*.tar.gz'` returns nothing outside `.git/`):

```bash
git clone https://github.com/crperdue73/cirrus-nexus.git aegis
cd aegis
sudo ./install.sh        # installs Docker, ContainerLab, ttyd, Python deps
sudo systemctl start aegis
sudo systemctl enable aegis  # auto-start on boot
```

Check it's alive:
```bash
curl http://localhost:8000/api
# → {"service":"NEXUS","version":"0.3.0","labs_count":<n>}
```
`labs_count` reflects whatever `lab-definitions/` currently holds; this release ships **two** labs
(demo-01, demo-02), so a fresh install reports `2`, not the older `4`. See
[`README.md`](README.md) → "The shipping labs".

### Firewall / Ports
- **8000** — AEGIS web portal (students open this in browser)
- **8765–9765** — ttyd terminals (one port per container per session)
- If there's a firewall between students and the server, both ranges need to be open.

### Test Before You Go
1. Open `http://<server-ip>:8000`
2. Enter your name, pick any lab
3. Verify terminals load (iframes aren't blank)
4. Run through the lab steps, click "Check" — verify it grades
5. Click "End Lab" — verify cleanup

---

## At the Conference

### Student Flow (60 seconds)
1. Open the URL (put it on a QR code on the booth)
2. Enter their name
3. Pick a lab
4. Terminals appear — they click in and start typing
5. Click "Check" — instant pass/fail feedback

### If Something Goes Wrong

| Symptom | Likely Fix |
|---------|-----------|
| Web page doesn't load | Server not running — `sudo systemctl restart aegis` |
| Terminals show blank/error | ttyd not installed — check `which ttyd` |
| Lab deploy fails | Docker not running — `sudo systemctl restart docker` |
| "Can't reach Docker daemon" | Service user not in docker group — `sudo usermod -aG docker aegis` then restart |
| Terminals load but are slow | Server is out of RAM — close unused sessions |
| Student finished, need next one | Click "End Lab" — frees containers and ports |
| "refused" from Check (HTTP 409) | The grader could not examine the node (down, or substrate changed since start) — this is **not** a failure (see [`docs/GRADING-MODEL.md`](docs/GRADING-MODEL.md)); restart the session |

### Reset Everything
```bash
sudo systemctl stop aegis
sudo pkill -f ttyd
sudo containerlab destroy --all --cleanup 2>/dev/null
sudo systemctl start aegis
```

### Booth Setup Tips
- Put the URL on a QR code + big text sign
- Have one tablet/laptop showing the lab catalog as a demo loop
- The two shipping labs are demo-01 (2 PCs + 1 SR Linux switch, bridged, ~25 min) and demo-02
  (2 switches + 1 router, routed, ~35 min) — demo-01 is the fastest walk-up
- Bring a "cheat sheet" handout with the IP commands for each lab

---

## Adding a New Lab (Quick Reference)

```bash
# 1. Create lab-definitions/my-lab.yml with:
#    - metadata section (id, name, description, instructions, grader)
#    - topology section (nodes, links)

# 2. Create lab-definitions/grader_my_lab.py with a grade() function

# 3. Reload without restart:
curl -X POST http://localhost:8000/api/labs/reload

# 4. Verify it appears:
curl http://localhost:8000/api/labs
```

The full lab schema, the load-time validation the loader refuses by name, and the grader interface
are in [`docs/ADDING-A-LAB.md`](docs/ADDING-A-LAB.md) — not the README.

---

## Important Notes
- **No authentication** — anyone on the network can start/stop labs. Fine for workshop LAN. Add nginx reverse proxy + auth for production.
- **Sessions are in-memory** — restarting the service kills all active labs.
- **Each "Start Lab" creates a new isolated deployment** — containers are named with a unique session ID, so multiple students can run the same lab without colliding.
