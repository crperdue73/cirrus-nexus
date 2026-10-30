#!/usr/bin/env python3
"""Start the AEGIS demo server.
Portable — resolves the backend path relative to this script.
"""
import re
import subprocess
import sys
import os
import time
from pathlib import Path
from urllib.request import urlopen

BASE_DIR = Path(__file__).parent.resolve()
BACKEND = str(BASE_DIR / "backend" / "main.py")

# The port/host the backend will actually bind. backend/main.py reads the same two
# variables (defaults 0.0.0.0:8000), so honouring them here keeps this script from
# waiting on a port nothing is listening on. (Before 2026-10-30 this script ignored
# both and reported failures from an empty log — see docs/OPERATIONS.md.)
PORT = os.environ.get("AEGIS_PORT", "8000")
HOST = os.environ.get("AEGIS_HOST", "0.0.0.0")

# Probe address: the bound host is often 0.0.0.0, which is not a destination.
_PROBE_HOST = "127.0.0.1" if HOST in ("0.0.0.0", "", "::") else HOST
API_URL = f"http://{_PROBE_HOST}:{PORT}/api"

LOG_PATH = "/tmp/aegis-server.log"

# 1) Kill leftover ttyd terminals from previous runs.
subprocess.run(["pkill", "-f", "ttyd.*docker exec"], capture_output=True)

# 2) Stop a server started from THIS tree only.
# The pattern must be an absolute filesystem path, so BACKEND is escaped as-is
# (Path.resolve() already yields a leading "/"); it therefore cannot match a
# relative `python3 backend/main.py`. It used to be the bare, unescaped path, which does not
# match `python3 /opt/aegis/backend/main.py`: the installer's systemd unit kept
# running, the new process died on the occupied port, and the readiness loop then
# reported the OLD server's answer as success. (Fixed 2026-10-30.)
# Matching only this tree's absolute path is still deliberate: it must not kill a
# server installed elsewhere at /opt/aegis (found 2026-10-04).
subprocess.run(["pkill", "-f", re.escape(BACKEND)], capture_output=True)
# pkill is asynchronous; a dying server holds the port for a moment.
time.sleep(1)

# 3) Start the AEGIS server.
proc = subprocess.Popen(
    [sys.executable, BACKEND],
    stdout=open(LOG_PATH, "w"),
    stderr=subprocess.STDOUT,
    env={**os.environ},
)
print(f"AEGIS Server PID: {proc.pid}")
print(f"Backend: {BACKEND}")
print(f"Logs: {LOG_PATH}")

# 4) Readiness: require OUR process to still be alive AND the API to answer.
# curl was assumed but never checked for; it is not installed by install.sh
# (urllib is in the standard library). curl -s also prints nothing on a failed
# connection but exits 0, so the old loop could count a refusal as success.
for i in range(15):
    time.sleep(1)
    if proc.poll() is not None:
        print(f"AEGIS server exited with status {proc.returncode} before it served.")
        print("Check the log:")
        print(open(LOG_PATH).read() or "(log is empty)")
        sys.exit(1)
    try:
        with urlopen(API_URL, timeout=3) as resp:
            body = resp.read().decode("utf-8", "replace").strip()
    except Exception:
        continue
    if body:
        print(f"Server ready after {i + 1}s")
        print(f"Response: {body}")
        print(f"Open: http://localhost:{PORT}")
        sys.exit(0)

print(f"Server did not answer {API_URL} within 15s (process {proc.pid} still running).")
print("Check the log:")
print(open(LOG_PATH).read() or "(log is empty)")
sys.exit(1)
