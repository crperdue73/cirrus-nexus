# AEGIS — Conference Operator Cheat Sheet

*Give this to anyone running the booth.*

---

## Before the Conference

### Server Requirements
- Debian or Ubuntu VM / laptop
- 4 GB RAM minimum, 8 GB recommended
- 20 GB free disk
- Internet access for first-time install (docker pulls images)

### Install
```bash
tar xzf aegis-portable.tar.gz
cd aegis
sudo ./install.sh        # ~5 min, installs everything
sudo systemctl start aegis
sudo systemctl enable aegis  # auto-start on boot
```

Check it's alive:
```bash
curl http://localhost:8000/api
# → {"service":"AEGIS","version":"0.3.0","labs_count":4}
```

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
- Tier 1 (Foundation) is the best for walk-ups — 5 minutes, instant win
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

See README.md for full details on the YAML format and grader API.

---

## Important Notes
- **No authentication** — anyone on the network can start/stop labs. Fine for workshop LAN. Add nginx reverse proxy + auth for production.
- **Sessions are in-memory** — restarting the service kills all active labs.
- **Each "Start Lab" creates a new isolated deployment** — containers are named with a unique session ID, so multiple students can run the same lab without colliding.
