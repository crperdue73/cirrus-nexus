#!/usr/bin/env python3
"""Start the AEGIS demo server.
Portable — resolves the backend path relative to this script.
"""
import subprocess
import sys
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

# Kill any existing ttyd procs from previous runs
subprocess.run(["pkill", "-f", "ttyd.*docker exec"], capture_output=True)

# Kill any existing aegis server on port 8000
subprocess.run(["pkill", "-f", "aegis.*main.py"], capture_output=True)

# Start the AEGIS server
backend_path = BASE_DIR / "backend" / "main.py"
log_path = "/tmp/aegis-server.log"

proc = subprocess.Popen(
    [sys.executable, str(backend_path)],
    stdout=open(log_path, "w"),
    stderr=subprocess.STDOUT,
    env={**os.environ}
)
print(f"AEGIS Server PID: {proc.pid}")
print(f"Backend: {backend_path}")
print(f"Logs: {log_path}")

# Wait for it to be ready
for i in range(15):
    time.sleep(1)
    result = subprocess.run(
        ["curl", "-s", "http://localhost:8000/api"],
        capture_output=True, text=True
    )
    if result.returncode == 0 and result.stdout:
        print(f"Server ready after {i+1}s")
        print(f"Response: {result.stdout.strip()}")
        print(f"Open: http://localhost:8000")
        sys.exit(0)

print("Server failed to start — check the log:")
print(open(log_path).read())
sys.exit(1)
