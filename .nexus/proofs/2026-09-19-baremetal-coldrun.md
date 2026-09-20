# Proof — Bare-Metal Cold Install (closes the Step 4 caveat)

Date: 2026-09-19 ~23:1x EDT (hour 23:00 nexus cron)
Host: fresh `debian:12` container, `--privileged`, NO docker, NO containerlab
Driver: Selina

## Why
STATUS.md flagged ONE open item across the project: every prior "cold host" run
(nexus-debhost) had docker + containerlab PRE-INSTALLED, so install.sh Steps 1-5
short-circuited with "already installed". The stated Step 4 bar ("cold on a clean
host, no hand steps") was therefore not fully exercised. This run exercises it
from bare metal.

## Bare state (verified before install)
    BARE-STATE docker:       NONE
    BARE-STATE containerlab: NONE

## Command
    docker run --rm --privileged -v <aegis>:/src:ro debian:12 bash -c '
      apt-get update -qq && apt-get install -y -qq curl ca-certificates gnupg \
        lsb-release python3 sudo
      cp -r /src /tmp/aegis-src && cd /tmp/aegis-src && bash install.sh'

## Result
    EXIT=0
    [+] Step 1: Installing system packages...
    [+] Step 2: Installing Docker...
    [+] Step 3: Installing ContainerLab...
    [+] Step 4: Installing ttyd...
    [+] Step 5: Installing Python dependencies...
    [+] Step 6: Installing AEGIS to /opt/aegis...
    [+] Step 7: Building FRR Docker image (aegis/frr:latest)...
    [+] Loading pinned FRR image from aegis-frr-image.tar.gz...
    [+] FRR image loaded and verified against pin
    [+]   verified on Dockerfile fingerprint cce15a8696ae045e... and
          layer-chain bb7ef23a07dcb6c6...
    [+] Step 8: Creating systemd service...
    [+] Step 9: Checking firewall...

NO "already installed" short-circuit on Steps 2 or 3 — both installed from
scratch. Steps 1-5 ran fully on a host with no docker and no containerlab.

## Digest landed
    layer-chain : sha256:bb7ef23a07dcb6c6b34e225dd77fa2eb592700975843ad1f1aa0105f49f9220c
    (== assets/frr-image.pin layer chain == the identity install.sh verifies)
    daemon-local image id: sha256:37b3ab8e3e631dec1e6e291a99e48ac9e90a2dd205b8a942d1206089e84f6e42
    (daemon-specific, correctly NOT treated as the pin key)

## Remaining honest caveat
The target still needed base `curl ca-certificates gnupg lsb-release python3 sudo`
present (installed by the harness before invoking install.sh; a stock debian:12
image). install.sh itself installs these in Step 1, but `apt-get` must exist. A
raw image with no apt at all is out of scope for a Debian/Ubuntu target.
