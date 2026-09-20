#!/usr/bin/env bash
# =============================================================================
# AEGIS — Install Script
# Portable one-shot setup for a fresh Debian/Ubuntu machine.
# Run as root or with sudo.
#
# Usage:
#   chmod +x install.sh && sudo ./install.sh
#
# This will:
#   1. Install system dependencies (Docker, ContainerLab, ttyd, Python)
#   2. Copy the AEGIS project to /opt/aegis
#   3. Build the FRR Docker image for Tier 2+ labs
#   4. Install Python dependencies
#   5. Create a systemd service (optional)
# =============================================================================

set -euo pipefail

# --- Configuration -----------------------------------------------------------
AEGIS_DIR="/opt/aegis"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
SERVICE_USER="${SERVICE_USER:-aegis}"
LISTEN_PORT="${LISTEN_PORT:-8000}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[x]${NC} $1"; }

# --- Preflight ---------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (or with sudo)"
    exit 1
fi

log "AEGIS Installer — starting up"
log "Source: ${SCRIPT_DIR}"
log "Target: ${AEGIS_DIR}"

# --- Step 1: System Packages -------------------------------------------------
log "Step 1: Installing system packages..."

apt-get update -qq
apt-get install -y -qq \
    curl \
    git \
    make \
    cmake \
    build-essential \
    pkg-config \
    libwebsockets-dev \
    libjson-c-dev \
    libssl-dev \
    python3 \
    python3-pip \
    python3-venv \
    ca-certificates \
    gnupg \
    lsb-release

# --- Step 2: Docker ----------------------------------------------------------
log "Step 2: Installing Docker..."

if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian \
        $(lsb_release -cs) stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    # systemd may not be PID 1 (containers, WSL, minimal VMs). Bringing docker up
    # via systemctl must not abort a cold install on such hosts; fall back to
    # starting dockerd directly so the build/load steps below still work.
    if [[ -d /run/systemd/system ]]; then
        systemctl enable --now docker
        log "Docker installed (systemd)"
    else
        warn "systemd not PID 1 — starting dockerd directly"
        (dockerd >/var/log/dockerd.log 2>&1 &) || true
        for _ in $(seq 1 30); do
            docker info &>/dev/null && break
            sleep 1
        done
        docker info &>/dev/null && log "Docker installed (dockerd direct)" \
            || { err "Docker did not come up"; exit 1; }
    fi
else
    log "Docker already installed ($(docker --version))"
fi

# --- Step 3: ContainerLab ----------------------------------------------------
log "Step 3: Installing ContainerLab..."

if ! command -v containerlab &>/dev/null; then
    bash -c "$(curl -sL https://get.containerlab.dev)" -- -v 0.60.0
    log "ContainerLab installed"
else
    log "ContainerLab already installed ($(containerlab version 2>&1 | head -1))"
fi

# --- Step 4: ttyd ------------------------------------------------------------
log "Step 4: Installing ttyd..."

if ! command -v ttyd &>/dev/null; then
    # Try prebuilt binary first (fast path)
    TTYD_VERSION="1.7.4"
    ARCH="$(uname -m)"
    case "${ARCH}" in
        x86_64)  TTYD_ARCH="x86_64" ;;
        aarch64) TTYD_ARCH="aarch64" ;;
        armv7l)  TTYD_ARCH="arm" ;;
        *)
            warn "No prebuilt ttyd binary for ${ARCH}, building from source (slow)..."
            BUILD_TTYD=1
            ;;
    esac

    if [[ -z "${BUILD_TTYD:-}" ]]; then
        TTYD_URL="https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${TTYD_ARCH}"
        curl -fsSL "${TTYD_URL}" -o /usr/local/bin/ttyd
        chmod +x /usr/local/bin/ttyd
        log "ttyd binary downloaded"
    else
        # Build from source
        git clone --depth=1 -b "${TTYD_VERSION}" \
            https://github.com/tsl0922/ttyd.git /tmp/ttyd-src
        cd /tmp/ttyd-src
        mkdir build && cd build
        cmake .. && make -j"$(nproc)" && make install
        cd /
        rm -rf /tmp/ttyd-src
        log "ttyd built from source"
    fi
else
    log "ttyd already installed"
fi

# --- Step 5: Python Dependencies ---------------------------------------------
log "Step 5: Installing Python dependencies..."

pip3 install --quiet --break-system-packages fastapi uvicorn pyyaml 2>/dev/null \
    || pip3 install --quiet fastapi uvicorn pyyaml

log "Python deps installed (fastapi, uvicorn, pyyaml)"

# --- Step 6: Copy AEGIS to install location ----------------------------------
log "Step 6: Installing AEGIS to ${AEGIS_DIR}..."

mkdir -p "${AEGIS_DIR}"
cp -r "${SCRIPT_DIR}/backend"     "${AEGIS_DIR}/backend"
cp -r "${SCRIPT_DIR}/frontend"    "${AEGIS_DIR}/frontend"
cp -r "${SCRIPT_DIR}/lab-definitions" "${AEGIS_DIR}/lab-definitions"
cp    "${SCRIPT_DIR}/Dockerfile.frr"  "${AEGIS_DIR}/Dockerfile.frr"
cp    "${SCRIPT_DIR}/README.md"       "${AEGIS_DIR}/README.md"

# Ship the pinned FRR image tarball + its pin file (step-4 transport).
# The image is local-only (RepoDigests: []), so a cold host cannot pull it;
# the installer loads the tarball instead and verifies the resulting IMAGE ID
# against the pin. No registry required.
ASSETS_SRC="${SCRIPT_DIR}/assets"
ASSETS_DST="${AEGIS_DIR}/assets"
if [[ -d "${ASSETS_SRC}" ]]; then
    mkdir -p "${ASSETS_DST}"
    cp -r "${ASSETS_SRC}/." "${ASSETS_DST}/"
    log "Shipped FRR image assets to ${ASSETS_DST}"
else
    warn "No assets/ dir found — FRR image must be built from source instead"
fi

# Fix the start_server.py path if it references the old workspace
sed -i 's|/home/student/.openclaw/workspace-selina/projects/aegis|'"${AEGIS_DIR}"'|g' \
    "${AEGIS_DIR}/start_server.py" 2>/dev/null || true

# Create a service user if it doesn't exist
if ! id "${SERVICE_USER}" &>/dev/null; then
    useradd -r -s /bin/false -d "${AEGIS_DIR}" "${SERVICE_USER}"
    log "Created system user: ${SERVICE_USER}"
fi

# Group membership. TWO users need this, not one:
#   - SERVICE_USER: the systemd service account runs docker exec + containerlab
#   - the INVOKING user (sudo caller): the manual/operator path. Without this,
#     `docker inspect` inside a hand-run backend is permission-denied, so the
#     app sees zero running containers and cannot resolve a runtime digest.
#     (Found live 2026-09-19 — was a real install.sh gap.)
DOCKER_GROUPS="docker"

# containerlab does NOT create clab_admins; it only *uses* it, and when the
# group is absent it prints "Containerlab admin group 'clab_admins' does not
# exist, skipping group membership check" and then refuses admin operations
# ("user '%v' is not part of containerlab admin group 'clab_admins'").
# On a cold host install.sh runs BEFORE the first `containerlab deploy`, so the
# group does not exist yet and the check silently no-ops -> the invoking user is
# never granted it -> app sees no containers (the gap found live 2026-09-19).
# Create it here when containerlab is present (or will be), so membership can be
# granted in the same run and no manual groupedit is needed.
if ! getent group clab_admins &>/dev/null && command -v containerlab &>/dev/null; then
    groupadd -r clab_admins 2>/dev/null && log "Created containerlab admin group: clab_admins"
fi
if getent group clab_admins &>/dev/null; then
    DOCKER_GROUPS="docker,clab_admins"
fi

if ! id -nG "${SERVICE_USER}" 2>/dev/null | tr ' ' '\n' | grep -qx docker; then
    usermod -aG "${DOCKER_GROUPS}" "${SERVICE_USER}"
    log "Added ${SERVICE_USER} to groups: ${DOCKER_GROUPS}"
fi

CALLER_USER="${SUDO_USER:-${USER:-}}"
if [[ -n "${CALLER_USER}" && "${CALLER_USER}" != "root" ]] && id "${CALLER_USER}" &>/dev/null; then
    ADDED=""
    for grp in ${DOCKER_GROUPS//,/ }; do
        getent group "${grp}" &>/dev/null || continue
        if ! id -nG "${CALLER_USER}" | tr ' ' '\n' | grep -qx "${grp}"; then
            usermod -aG "${grp}" "${CALLER_USER}"
            ADDED="${ADDED} ${grp}"
        fi
    done
    if [[ -n "${ADDED}" ]]; then
        log "Added invoking user ${CALLER_USER} to:${ADDED}"
        warn "${CALLER_USER} must re-login for group changes to take effect"
    fi
fi

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${AEGIS_DIR}"

log "AEGIS files installed to ${AEGIS_DIR}"

# --- Step 7: Build FRR Docker Image -----------------------------------------
log "Step 7: Building FRR Docker image (aegis/frr:latest)..."

# Rebuild when the source no longer matches what the tag was built from.
#
# A bare `docker image inspect` existence check lets a stale substrate survive
# forever: if the tag exists at all, the image is never rebuilt, so a Dockerfile
# change can never self-heal.
#
# An mtime-vs-`.Created` comparison is NOT sufficient either. The live image was
# created 4s AFTER Dockerfile.frr was written (09:28:39 vs 09:28:35), so mtime
# says "source is older, skip" — exactly the stale-substrate bug we're fixing.
# We therefore stamp a fingerprint of the Dockerfile into the image as a label
# and rebuild whenever the on-disk Dockerfile hashes differently. Absent label
# (any pre-existing image, e.g. the stale one) counts as a mismatch -> rebuild.
FRR_SRC="${AEGIS_DIR}/Dockerfile.frr"
NEED_FRR_BUILD=1

if docker image inspect aegis/frr:latest &>/dev/null; then
    FRR_SRC_SHA=$(sha256sum "${FRR_SRC}" 2>/dev/null | awk '{print $1}')
    FRR_IMG_SHA=$(docker image inspect aegis/frr:latest \
        --format '{{index .Config.Labels "aegis.frr.dockerfile.sha256"}}' 2>/dev/null)
    FRR_IMG_ID=$(docker image inspect aegis/frr:latest --format '{{.Id}}' 2>/dev/null)

    if [[ -n "${FRR_SRC_SHA}" && "${FRR_SRC_SHA}" == "${FRR_IMG_SHA}" ]]; then
        log "FRR image is up to date (Dockerfile hash matches label), skipping build"
        NEED_FRR_BUILD=0
    else
        warn "aegis/frr:latest does not match the current Dockerfile — rebuilding"
        warn "  source sha256: ${FRR_SRC_SHA:-<unreadable>}"
        warn "  image  sha256: ${FRR_IMG_SHA:-<no fingerprint label (stale image)>}"
        warn "  image  id:     ${FRR_IMG_ID}"
    fi
fi

if [[ "${NEED_FRR_BUILD}" -eq 1 ]]; then
    FRR_SRC_SHA=$(sha256sum "${FRR_SRC}" | awk '{print $1}')

    # Preferred path: load the shipped, pinned tarball. This is the only
    # hand-step-free path on a cold host, since the image is local-only.
    PIN_FILE="${ASSETS_DST}/frr-image.pin"
    PIN_TARBALL=""
    PIN_IMAGE_ID=""
    if [[ -f "${PIN_FILE}" ]]; then
        # shellcheck disable=SC1090
        source "${PIN_FILE}"
        PIN_TARBALL="${ASSETS_DST}/${tarball:-}"
        PIN_IMAGE_ID="${image_id:-}"
    fi

    if [[ -n "${PIN_TARBALL}" && -f "${PIN_TARBALL}" ]]; then
        log "Loading pinned FRR image from $(basename "${PIN_TARBALL}")..."
        ACTUAL_TARBALL_SHA=$(sha256sum "${PIN_TARBALL}" | awk '{print $1}')
        if [[ -n "${tarball_sha256:-}" && "${ACTUAL_TARBALL_SHA}" != "${tarball_sha256}" ]]; then
            err "Tarball checksum mismatch — refusing to load a corrupted/unknown image"
            err "  expected: ${tarball_sha256}"
            err "  actual:   ${ACTUAL_TARBALL_SHA}"
            exit 1
        fi
        docker load -i "${PIN_TARBALL}" \
            || { err "docker load FAILED"; exit 1; }

        # Verify the loaded image against the pin.
        #
        # We must NOT verify on the image ID. `docker save | docker load`
        # recomputes the image config digest on the target daemon (the config
        # JSON's `created` field differs), so the ID legitimately changes across
        # transport even when the content is byte-identical. Pinning on the ID
        # guarantees a cold host fails (found live 2026-09-19: source
        # acb8d8dc... loaded as 37b3ab8e... with identical rootfs).
        #
        # The transport-invariant identity is TWO things, both of which survive
        # save/load:
        #   1. the Dockerfile fingerprint label (what the image was BUILT from)
        #   2. the content-addressed rootfs layer chain (what the image IS)
        # Verify both. Either mismatch => refuse to continue.
        LOADED_ID=$(docker image inspect aegis/frr:latest --format '{{.Id}}')
        LOADED_LABEL=$(docker image inspect aegis/frr:latest \
            --format '{{index .Config.Labels "aegis.frr.dockerfile.sha256"}}' 2>/dev/null)
        LOADED_LAYERS=$(docker image inspect aegis/frr:latest \
            --format '{{range .RootFS.Layers}}{{.}} {{end}}' 2>/dev/null | tr -d ' ')
        LOADED_LAYERS_SHA=$(printf '%s' "${LOADED_LAYERS}" | sha256sum | awk '{print $1}')

        if [[ -n "${dockerfile_sha256:-}" && "${LOADED_LABEL}" != "${dockerfile_sha256}" ]]; then
            err "Loaded image was not built from the pinned Dockerfile — refusing"
            err "  expected fingerprint: ${dockerfile_sha256}"
            err "  loaded fingerprint:   ${LOADED_LABEL:-<none>}"
            exit 1
        fi
        if [[ -n "${layers_sha256:-}" && "${LOADED_LAYERS_SHA}" != "${layers_sha256}" ]]; then
            err "Loaded image content does not match the pin — refusing"
            err "  expected layer-chain sha256: ${layers_sha256}"
            err "  loaded layer-chain sha256:   ${LOADED_LAYERS_SHA}"
            exit 1
        fi
        log "FRR image loaded and verified against pin"
        log "  verified on Dockerfile fingerprint ${LOADED_LABEL:0:16}... and layer-chain ${LOADED_LAYERS_SHA:0:16}..."
        log "  local image id (daemon-specific, NOT the pin key): ${LOADED_ID}"
    else
        # Fallback: no pinned tarball shipped. Build locally with the
        # Dockerfile fingerprint label so a later run can still self-heal.
        warn "No pinned image tarball found — building locally from Dockerfile"
        docker build --no-cache \
            --label "aegis.frr.dockerfile.sha256=${FRR_SRC_SHA}" \
            -f "${FRR_SRC}" -t aegis/frr:latest "${AEGIS_DIR}" \
            || { warn "FRR image build FAILED"; exit 1; }
        log "FRR image built (fingerprint ${FRR_SRC_SHA:0:16}...)"
        log "FRR image id: $(docker image inspect aegis/frr:latest --format '{{.Id}}' | cut -c1-19)..."
    fi

    # Record what the tag resolved to, for operators and for the app.
    # We record BOTH the daemon-local id (what `docker inspect` returns here)
    # and the transport-invariant layer-chain hash (the real identity).
    #
    # CRITICAL: compute the layer-chain hash EXACTLY as the verifier above does
    # -- capture to a variable, then `printf '%s'` (no trailing newline).
    # A pipeline (`... | tr -d ' ' | sha256sum`) appends a trailing newline, so
    # the recorded hash differed from the verified hash for the SAME image
    # (recorded f7a7f293... vs verified bb7ef23a... on 2026-09-19). That made
    # the artifact install.sh publishes disagree with the pin it just checked,
    # so any consumer citing installed_layers_sha256 would cite a value that
    # fails its own re-verification. Verified-state must be self-consistent.
    INSTALLED_IMAGE_ID=$(docker image inspect aegis/frr:latest --format '{{.Id}}' 2>/dev/null)
    INSTALLED_LABEL=$(docker image inspect aegis/frr:latest \
        --format '{{index .Config.Labels "aegis.frr.dockerfile.sha256"}}' 2>/dev/null)
    INSTALLED_LAYERS=$(docker image inspect aegis/frr:latest \
        --format '{{range .RootFS.Layers}}{{.}} {{end}}' 2>/dev/null | tr -d ' ')
    INSTALLED_LAYERS_SHA=$(printf '%s' "${INSTALLED_LAYERS}" | sha256sum | awk '{print $1}')
    {
        echo "installed_local_image_id=${INSTALLED_IMAGE_ID}"
        echo "installed_dockerfile_sha256=${INSTALLED_LABEL}"
        echo "installed_layers_sha256=${INSTALLED_LAYERS_SHA}"
    } > "${AEGIS_DIR}/assets/installed-image-id.txt" 2>/dev/null || true
fi

# --- Step 8: Systemd Service (optional) --------------------------------------
log "Step 8: Creating systemd service..."

cat > /etc/systemd/system/aegis.service << 'SERVICE'
[Unit]
Description=AEGIS — Academic Educational Grading & Infrastructure System
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=simple
User=aegis
Group=aegis
WorkingDirectory=/opt/aegis
ExecStart=/usr/bin/python3 /opt/aegis/backend/main.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/aegis.log
StandardError=append:/var/log/aegis.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

if [[ -d /run/systemd/system ]]; then
    systemctl daemon-reload
    log "systemd service created (aegis.service)"
else
    warn "systemd not PID 1 — aegis.service written but not registered."
    warn "Start manually: python3 ${AEGIS_DIR}/backend/main.py"
fi

# --- Step 9: Firewall --------------------------------------------------------
log "Step 9: Checking firewall..."

if command -v ufw &>/dev/null; then
    ufw allow "${LISTEN_PORT}/tcp" 2>/dev/null && \
        log "UFW: allowed port ${LISTEN_PORT}" || \
        warn "UFW: couldn't add rule (may need manual config)"
fi

# --- Done --------------------------------------------------------------------
echo ""
log "═══════════════════════════════════════════════════════════"
log "Installation complete!"
log ""
log "  Start AEGIS:    systemctl start aegis"
log "  Enable at boot: systemctl enable aegis"
log "  View logs:      journalctl -u aegis -f"
log "  Open browser:   http://$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i!~/^(172\.|10\.|192\.168\.|127\.)/){print $i;exit}}'):${LISTEN_PORT}"
log ""
log "  OR run manually: python3 ${AEGIS_DIR}/backend/main.py"
log ""
log "  Default labs auto-discovered:"
for f in "${AEGIS_DIR}"/lab-definitions/*.yml; do
    if [[ -f "$f" ]]; then
        name=$(grep -m1 'name:' "$f" 2>/dev/null | head -1 | sed 's/name: *//')
        id=$(grep -m1 'id:' "$f" 2>/dev/null | head -1 | sed 's/id: *//')
        [[ -n "$id" ]] && echo "    - ${id}: ${name}"
    fi
done
log "═══════════════════════════════════════════════════════════"
