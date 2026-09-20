#!/usr/bin/env bash
# Nexus exit-bar independent reproduction — 2026-09-20 04:01 EDT hour.
# Fresh bare debian:12, no docker, no containerlab. Cold install then deploy.
set -u
echo "=== BARE BEFORE ==="
command -v docker >/dev/null && echo "docker=PRESENT" || echo "docker=NONE"
command -v containerlab >/dev/null && echo "containerlab=PRESENT" || echo "containerlab=NONE"

echo "=== apt prep ==="
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq curl ca-certificates gnupg lsb-release python3 python3-pip sudo >/dev/null 2>&1
echo "apt prep rc=$?"

mkdir -p /etc/docker
echo '{"storage-driver":"vfs"}' > /etc/docker/daemon.json

echo "=== copy source ==="
cp -r /src /tmp/aegis-src
cd /tmp/aegis-src || exit 9

echo "=== install.sh ==="
bash install.sh
echo "INSTALL EXIT=$?"

echo "=== install record ==="
cat /opt/aegis/assets/installed-image-id.txt 2>&1
echo "=== pin ==="
grep -E 'layers_sha256|dockerfile_sha256' /opt/aegis/assets/frr-image.pin

echo "=== app deps ==="
pip3 install --quiet fastapi uvicorn python-multipart 2>&1 | tail -2

echo "=== start app ==="
cd /opt/aegis || exit 9
nohup python3 backend/main.py >/tmp/app.log 2>&1 &
APP_PID=$!
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:8000/api/labs >/dev/null 2>&1 && break
  sleep 1
done
echo "app up after ${i}s (pid ${APP_PID})"
echo "LABS:"; curl -s http://127.0.0.1:8000/api/labs | head -c 400; echo

echo "=== deploy lab-04 (Ethan's topology) ==="
START=$(curl -s -X POST "http://127.0.0.1:8000/api/sessions/start?lab_id=lab-04-two-as-peering&student_name=Selina")
echo "$START" | head -c 900; echo
SID=$(echo "$START" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("session_id",""))' 2>/dev/null)
echo "SESSION=$SID"

echo "=== grade r1 (exit-bar assertion: digest must be cited) ==="
GRADE=$(curl -s -X POST "http://127.0.0.1:8000/api/sessions/${SID}/submit?node=r1")
echo "$GRADE" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("runtime_digest =",repr(d.get("runtime_digest")));print("passed =",d.get("passed"))' 2>&1

echo "=== stop session ==="
curl -s -X POST "http://127.0.0.1:8000/api/sessions/${SID}/stop"; echo
kill $APP_PID 2>/dev/null
echo "=== DONE ==="
