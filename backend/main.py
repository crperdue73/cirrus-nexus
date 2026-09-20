"""
NEXUS — Network Education & User Simulation
Refactored backend with dynamic lab discovery, pluggable graders,
dynamic node parsing, and port allocation.

FastAPI application that orchestrates ContainerLab topologies,
provides web terminal access via ttyd, and grades student configs.
"""

import hashlib
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import signal

# --- Setup ---

app = FastAPI(title="NEXUS", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent.parent
LABS_DIR = BASE_DIR / "lab-definitions"
SESSIONS: dict = {}
TTYD_PROCS: dict = {}  # port -> subprocess.Popen

# The pinned AEGIS substrate. install.sh builds/loads THIS image and publishes
# its transport-invariant identity as `installed_layers_sha256`. Auxiliary lab
# images (e.g. alpine PCs) are deliberately NOT part of the substrate identity.
AEGIS_SUBSTRATE_IMAGE = "aegis/frr:latest"


# --- No-cache middleware (prevents browser caching during dev) ---


@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
TTYD_PORT_BASE = 8765
TTYD_PORT_MAX = 9765

os.makedirs(LABS_DIR, exist_ok=True)


# --- Models ---

class LabDef(BaseModel):
    id: str
    name: str
    description: str
    difficulty: str
    duration_min: int
    competencies: list[str]
    course: str = ""
    topology_file: str
    grader_module: str
    instructions: list[str] = []
    tip: str = ""
    gradeable_nodes: list[str] = []


class GraderResult(BaseModel):
    passed: bool
    score: float
    feedback: list[str]
    competencies: list[str]
    # Step 5 — runtime pin: a grade is only citable with the substrate it ran on.
    runtime_digest: str = ""


# --- Step 5: Runtime digest pin -------------------------------------------
#
# A lab state is meaningless without the substrate it ran on. The FRR image
# behind a container is the substrate; its digest is the identity. A grade
# produced against a stale image must never be citable as if it came from the
# current one. We therefore resolve the digest OFF THE RUNNING CONTAINER (not
# the build log, not the tag) at deploy time, stamp it into the session, and
# refuse to grade/cite without it.


def _image_layers_sha(image_ref: str) -> str:
    """Transport-invariant content identity of a local image.

    sha256 over the ordered rootfs layer digests. Survives `docker save |
    docker load` unchanged (the config digest does NOT — it is recomputed on
    load, so the image ID changes across transport for byte-identical content).

    Mirrors install.sh EXACTLY: capture to a var, then `printf '%s'` (no
    trailing newline). A pipeline here would append a newline and produce a
    hash that disagrees with the installer's for the same image — the bug that
    made the published identity fail its own re-verification.
    """
    try:
        layers = subprocess.run(
            ["docker", "image", "inspect", image_ref,
             "--format", "{{range .RootFS.Layers}}{{.}} {{end}}"],
            capture_output=True, text=True, timeout=10,
        )
        if layers.returncode != 0:
            return ""
        # Match install.sh byte-for-byte. install.sh computes:
        #   layers=$(docker image inspect ... --format '{{range .RootFS.Layers}}{{.}} {{end}}' | tr -d ' ')
        #   printf '%s' "$layers" | sha256sum
        # Two subtleties, both verified by execution here:
        #   1. `tr -d ' '` deletes SPACES ONLY, leaving the daemon's trailing
        #      newline.
        #   2. command substitution `$(...)` STRIPS trailing newlines, so `$layers`
        #      has NO trailing newline by the time `printf '%s'` hashes it.
        # Net effect: hash of the space-stripped chain with trailing newlines
        # removed. Reproduce exactly (`rstrip('\n')`, NOT `strip()` — an interior
        # whitespace nuance would otherwise silently change the value).
        chain = layers.stdout.replace(" ", "").rstrip("\n")
        if not chain:
            return ""
        h = hashlib.sha256(chain.encode()).hexdigest()
        return h
    except Exception:
        return ""


def _installed_pin() -> dict:
    """Read the substrate identity install.sh PUBLISHED on this host.

    `/opt/aegis/assets/installed-image-id.txt` is written by install.sh after it
    verifies the loaded image against the shipped pin. The value that matters is
    `installed_layers_sha256` — the transport-invariant content identity, i.e.
    what the substrate IS. `installed_local_image_id` is daemon-specific and is
    NOT an identity across transport, so it is read for diagnostics only.

    Returns {} when absent/unreadable -> the caller must treat the substrate as
    unattributable rather than assume it is current.
    """
    candidates = [
        BASE_DIR / "assets" / "installed-image-id.txt",
        Path("/opt/aegis/assets/installed-image-id.txt"),
    ]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            pin = {}
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                pin[k.strip()] = v.strip()
            if pin:
                pin["_source"] = str(path)
                return pin
        except Exception:
            continue
    return {}


def _resolve_container_digest(container: str) -> str:
    """Resolve the substrate identity of a RUNNING container.

    Identity is the transport-invariant LAYER-CHAIN hash of the image actually in
    use — the same value install.sh publishes as `installed_layers_sha256`. This
    is what makes an app-cited digest comparable to the installer's verified
    digest.

    A registry RepoDigest is preferred when one exists (it is a stronger, signed
    identity), but this image is local-only (RepoDigests: []) so in practice we
    fall back to the layer chain. Never parses a build log. Returns "" when it
    cannot be determined — callers must treat that as unattributable, not a pass.
    """
    try:
        inspect = subprocess.run(
            ["docker", "inspect", container, "--format", "{{.Image}}"],
            capture_output=True, text=True, timeout=10,
        )
        if inspect.returncode != 0:
            return ""
        image_id = inspect.stdout.strip()
        if not image_id:
            return ""

        # Prefer a registry digest for the same image when one exists.
        repo = subprocess.run(
            ["docker", "image", "inspect", image_id,
             "--format", "{{index .RepoDigests 0}}"],
            capture_output=True, text=True, timeout=10,
        )
        repo_digest = repo.stdout.strip() if repo.returncode == 0 else ""
        if repo_digest and repo_digest not in ("<no value>", "[]"):
            return repo_digest

        # Local-only image: cite the transport-invariant layer chain.
        layers_sha = _image_layers_sha(image_id)
        if layers_sha:
            return f"sha256:{layers_sha}"
        return ""
    except Exception:
        return ""


# --- Dynamic Lab Discovery ---

def _parse_yaml_metadata(path: Path) -> dict | None:
    """Parse the metadata section from a topology YAML."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            if data and "metadata" in data:
                return data["metadata"]
    except (yaml.YAMLError, OSError):
        pass
    return None


def _discover_labs() -> list[dict]:
    """Scan lab-definitions/ for YAML files with metadata sections."""
    labs = []
    seen_ids = set()
    for f in sorted(LABS_DIR.glob("*.yml")):
        meta = _parse_yaml_metadata(f)
        if not meta or "id" not in meta:
            continue
        lab_id = meta["id"]
        if lab_id in seen_ids:
            continue
        seen_ids.add(lab_id)
        labs.append({
            "id": lab_id,
            "name": meta.get("name", lab_id),
            "description": meta.get("description", ""),
            "difficulty": meta.get("difficulty", "Beginner"),
            "duration_min": meta.get("duration_min", 45),
            "competencies": meta.get("competencies", []),
            "course": meta.get("course", ""),
            "topology_file": f.name,
            "grader_module": meta.get("grader", f"grader_{lab_id}"),
            "instructions": meta.get("instructions", []),
            "tip": meta.get("tip", ""),
            "gradeable_nodes": meta.get("gradeable_nodes", []),
        })
    return labs


LABS: list[LabDef] = []


def _reload_labs():
    global LABS
    discovered = _discover_labs()
    LABS = [LabDef(**d) for d in discovered]


_reload_labs()


def _get_lab(lab_id: str) -> LabDef | None:
    for lab in LABS:
        if lab.id == lab_id:
            return lab
    return None


# --- Dynamic Grader Loading ---

_GRADER_CACHE: dict = {}


def _load_grader(module_name: str):
    """Import a grader module by name. Caches after first load."""
    if module_name in _GRADER_CACHE:
        return _GRADER_CACHE[module_name]

    # Try: lab-definitions/<module>.py
    module_path = LABS_DIR / f"{module_name}.py"
    if module_path.exists():
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
            _GRADER_CACHE[module_name] = mod
            return mod

    # Try: backend/graders/<module>.py (fallback)
    backend_graders = BASE_DIR / "backend" / "graders"
    alt_path = backend_graders / f"{module_name}.py"
    if alt_path.exists():
        spec = importlib.util.spec_from_file_location(module_name, alt_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
            _GRADER_CACHE[module_name] = mod
            return mod

    return None


# --- Topology helpers ---

def _parse_topology_nodes(topology_file: str) -> list[str]:
    """Extract node names from a Containerlab YAML topology."""
    topo_path = LABS_DIR / topology_file
    if not topo_path.exists():
        raise FileNotFoundError(f"Topology file not found: {topo_path}")
    with open(topo_path) as f:
        data = yaml.safe_load(f)
    nodes = []
    topo = data.get("topology", {})
    for node_name in topo.get("nodes", {}):
        nodes.append(node_name)
    return nodes


def _get_topology_name(topology_file: str) -> str:
    """Get the base topology name from a clab YAML."""
    topo_path = LABS_DIR / topology_file
    if not topo_path.exists():
        return Path(topology_file).stem
    with open(topo_path) as f:
        data = yaml.safe_load(f)
    return data.get("name", Path(topology_file).stem)


def _prepare_topology(lab: LabDef, session_id: str) -> tuple[Path, str]:
    """
    Load topology YAML, strip metadata, inject a session-unique name,
    and write to a session-specific temp file.
    
    Returns: (path_to_cleaned_yaml, unique_topo_name)
    """
    topo_path = LABS_DIR / lab.topology_file
    if not topo_path.exists():
        raise FileNotFoundError(f"Topology file not found: {topo_path}")

    with open(topo_path) as f:
        data = yaml.safe_load(f)

    # Strip metadata so containerlab doesn't choke on unknown keys
    if "metadata" in data:
        del data["metadata"]

    # Inject a unique name so multiple sessions don't collide on container names
    base_name = data.get("name", Path(lab.topology_file).stem)
    unique_name = f"{base_name}-{session_id}"
    data["name"] = unique_name

    clean_path = LABS_DIR / f"._clean_{lab.topology_file}_{session_id}.yml"
    with open(clean_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    return clean_path, unique_name


def _remove_clean_copy(topology_file: str, session_id: str):
    """Remove the session-specific cleaned temp YAML."""
    clean_path = LABS_DIR / f"._clean_{topology_file}_{session_id}.yml"
    if clean_path.exists():
        clean_path.unlink()


# --- Port Allocator ---

_PORT_ALLOC = {"next": TTYD_PORT_BASE}


def _allocate_port() -> int:
    """Allocate the next available ttyd port (simple sequential)."""
    port = _PORT_ALLOC["next"]
    _PORT_ALLOC["next"] += 1
    if _PORT_ALLOC["next"] > TTYD_PORT_MAX:
        _PORT_ALLOC["next"] = TTYD_PORT_BASE
    return port


# --- Core Functions ---

def deploy_lab(lab: LabDef, session_id: str) -> dict:
    """Deploy a ContainerLab topology with a session-unique name, return node info."""
    if not (LABS_DIR / lab.topology_file).exists():
        raise FileNotFoundError(f"Topology file not found: {lab.topology_file}")

    nodes = _parse_topology_nodes(lab.topology_file)
    clean_path, unique_name = _prepare_topology(lab, session_id)

    try:
        result = subprocess.run(
            ["containerlab", "deploy", "-t", str(clean_path), "--reconfigure"],
            capture_output=True, text=True, timeout=60
        )
    finally:
        _remove_clean_copy(lab.topology_file, session_id)

    if result.returncode != 0:
        raise RuntimeError(f"ContainerLab deploy failed: {result.stderr}")

    # Extract container names dynamically using the unique topology name.
    #
    # A single post-deploy status check is a race: nodes that bootstrap in
    # their exec commands (e.g. FRR's `/usr/lib/frr/frrinit.sh start; sleep 3`)
    # are not yet `running` the instant `containerlab deploy` returns. A one-
    # shot check silently drops those nodes from the node set, which then
    # makes the runtime-digest resolution fail and the session refuse to
    # start. Poll with a bounded wait so a healthy deploy is not mistaken for
    # a broken one.
    deploy_deadline = time.time() + 60
    containers = {}
    node_names = sorted(nodes)
    while True:
        containers = {}
        for node_name in node_names:
            container_name = f"clab-{unique_name}-{node_name}"
            inspect = subprocess.run(
                ["docker", "inspect", container_name, "--format", "{{.State.Status}}"],
                capture_output=True, text=True, timeout=10
            )
            if inspect.returncode == 0 and inspect.stdout.strip() == "running":
                containers[node_name] = container_name

        if len(containers) == len(node_names):
            break
        if time.time() >= deploy_deadline:
            missing = [n for n in node_names if n not in containers]
            raise RuntimeError(
                "ContainerLab deploy did not bring up all nodes within 60s; "
                f"missing or not-running: {missing}"
            )
        time.sleep(1)

    # Install iproute2 for alpine-based nodes (idempotent)
    for container_name in containers.values():
        subprocess.run(
            ["docker", "exec", container_name, "sh", "-c",
             "apk add iproute2 iputils -q 2>/dev/null"],
            capture_output=True, timeout=15
        )

    return containers


def resolve_runtime_digest(containers: dict) -> str:
    """Resolve the runtime substrate digest for a deployed lab's node set.

    The AEGIS substrate is the `aegis/frr` image — the thing install.sh pins and
    verifies. Labs legitimately mix substrates: a router node runs the pinned
    `aegis/frr` image while a student PC runs stock `alpine:latest` (see
    tier-02-router-basics.yml, lab-04, etc.). Requiring EVERY node image to be
    identical therefore made any mixed lab permanently unresolvable — the pin
    refused to cite a perfectly well-pinned substrate because an auxiliary PC
    image differed. (Found live 2026-09-19: lab-04 resolved, tier-02 refused.)

    Correct rule: identify the node(s) running the pinned substrate and pin THAT
    identity. If multiple distinct AEGIS-substrate images are live in one lab,
    the session is genuinely mixed and we refuse ("") — that is a real ambiguity,
    unlike an alpine PC.

    Additionally cross-check the live substrate against the identity install.sh
    PUBLISHED for this host (`installed_layers_sha256`). A grade may only cite a
    substrate that is the one the installer verified. If the host publishes a
    different identity than the substrate actually in use — stale image after a
    rebuild, or a session against an image the installer never landed — the
    substrate is unattributable and we refuse (""), rather than cite a digest
    that would not survive re-verification. An absent install record is also
    unattributable: we do not assume "probably current".
    """
    # A freshly-deployed lab has containers in `docker ps` before every FRR
    # node has finished settling; a single pass can therefore see NO substrate
    # node yet and refuse a perfectly good session (observed live 2026-09-20:
    # session 20490067 graded with runtime_digest=None immediately after start,
    # then resolved cleanly on re-run). Retry briefly. Bounded, and only the
    # empty/ambiguous outcome is retried — a DEFINITE refusal (install-record
    # mismatch) still returns immediately on the first pass.
    _deadline = time.time() + 10.0
    while True:
        result = _resolve_runtime_digest_once(containers)
        if result or time.time() >= _deadline:
            return result
        time.sleep(0.5)


def _resolve_runtime_digest_once(containers: dict) -> str:
    """Single-pass substrate resolution. See resolve_runtime_digest()."""
    substrate_tag = AEGIS_SUBSTRATE_IMAGE
    substrate_digests = set()
    for container in containers.values():
        image_ref = _container_image(container)
        if not image_ref:
            continue
        tags = _image_tags(image_ref)
        # Only the pinned AEGIS substrate participates in the identity.
        if substrate_tag not in tags and not _is_aegis_substrate(image_ref):
            continue
        d = _resolve_container_digest(container)
        if not d:
            return ""
        substrate_digests.add(d)

    if not substrate_digests:
        # No node runs the pinned substrate — nothing to attribute.
        return ""
    if len(substrate_digests) != 1:
        # Two different AEGIS substrates in one lab: genuinely ambiguous.
        return ""
    live = substrate_digests.pop()

    pin = _installed_pin()
    expected = pin.get("installed_layers_sha256", "")
    if not expected:
        # No installer-published identity on this host: unattributable.
        return ""
    if live != f"sha256:{expected}":
        # Live substrate is not the one the installer verified.
        return ""
    return live


def _container_image(container: str) -> str:
    """Image id (`.Image`) of a container, or "" if undeterminable."""
    try:
        r = subprocess.run(
            ["docker", "inspect", container, "--format", "{{.Image}}"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _image_tags(image_ref: str) -> set:
    """Repo tags of a local image, as a set. Empty when untagged/unknown."""
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", image_ref,
             "--format", "{{json .RepoTags}}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return set()
        return set(json.loads(r.stdout.strip() or "null") or [])
    except Exception:
        return set()


def _is_aegis_substrate(image_ref: str) -> bool:
    """True when the image carries the installer's Dockerfile fingerprint label.

    This catches a substrate loaded under a different tag: the label is stamped
    by install.sh and survives save/load, so it identifies the AEGIS substrate
    even when RepoTags is empty.
    """
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", image_ref,
             "--format", '{{index .Config.Labels "aegis.frr.dockerfile.sha256"}}'],
            capture_output=True, text=True, timeout=10,
        )
        label = r.stdout.strip() if r.returncode == 0 else ""
        return bool(label) and label != "<no value>"
    except Exception:
        return False


def destroy_lab(lab: LabDef, session_id: str):
    """Destroy a session-specific ContainerLab topology."""
    clean_path, _ = _prepare_topology(lab, session_id)
    try:
        subprocess.run(
            ["containerlab", "destroy", "-t", str(clean_path), "--cleanup"],
            capture_output=True, timeout=30
        )
    finally:
        _remove_clean_copy(lab.topology_file, session_id)


def grade_config(session_id: str, lab_id: str, node: str) -> GraderResult:
    """Grade a student's configuration using the lab's grader module."""
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    lab = _get_lab(lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")

    # Step 5 invariant is enforced BEFORE any grader path and OUTSIDE the broad
    # except below. `_require_runtime_digest` signals refusal with
    # HTTPException(409); the previous layout called it INSIDE the try, so the
    # `except Exception` swallowed the refusal and returned a 200 with an EMPTY
    # runtime_digest instead. That silently defeated the gate: an unattributable
    # session produced a citable-looking grade carrying no identity. (Found live
    # 2026-09-20.) Resolve/refuse here so the 409 propagates untouched.
    digest = _require_runtime_digest(session)

    grader = _load_grader(lab.grader_module)
    if not grader:
        # Fallback: basic IP/ping check (already digest-guarded).
        return _fallback_grade(session, node)

    try:
        result = grader.grade(session, node)
        if isinstance(result, dict):
            if result.get("passed"):
                session["status"] = "submitted"
            return GraderResult(runtime_digest=digest, **result)
        return GraderResult(
            runtime_digest=digest,
            passed=result.passed,
            score=result.score,
            feedback=result.feedback,
            competencies=result.competencies,
        )
    except Exception as e:
        return GraderResult(
            passed=False, score=0,
            feedback=[f"❌ Grader error: {str(e)}"],
            competencies=[],
        )


def _require_runtime_digest(session: dict) -> str:
    """Return the session's runtime digest, or refuse to produce a grade.

    Step 5 invariant: a state cannot be cited without its digest. If a session
    has no resolved substrate identity, grading is refusable — no unattributed
    reads, ever.
    """
    digest = session.get("runtime_digest") or ""
    if not digest:
        raise HTTPException(
            status_code=409,
            detail=(
                "Session has no runtime digest; state is unattributable and "
                "cannot be graded. Re-deploy the lab to pin the substrate."
            ),
        )
    return digest


def _fallback_grade(session: dict, node: str) -> GraderResult:
    """Basic fallback grader when no module is available."""
    digest = _require_runtime_digest(session)
    container = session["nodes"].get(node)
    if not container:
        return GraderResult(runtime_digest=digest, passed=False, score=0,
                            feedback=[f"Node '{node}' not found."],
                            competencies=[])
    result = subprocess.run(
        ["docker", "exec", container, "sh", "-c",
         "ip -4 addr show | grep -c 'inet '"],
        capture_output=True, text=True, timeout=10
    )
    ip_count = int(result.stdout.strip() or 0)
    total = max(ip_count - 1, 0)  # exclude loopback
    return GraderResult(
        runtime_digest=digest,
        passed=total > 0,
        score=min(total * 0.3, 1.0),
        feedback=[f"ℹ️  {node} has {total} non-loopback IPs configured"],
        competencies=[],
    )


# --- API Routes ---

@app.get("/api")
def root():
    return {"service": "NEXUS", "version": "0.3.0", "labs_count": len(LABS)}


@app.get("/api/labs")
def list_labs():
    return {"labs": LABS}


@app.get("/api/labs/{lab_id}")
def get_lab(lab_id: str):
    lab = _get_lab(lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


@app.post("/api/labs/reload")
def reload_labs():
    """Reload lab definitions from disk (admin endpoint)."""
    _reload_labs()
    _GRADER_CACHE.clear()
    return {"status": "reloaded", "count": len(LABS)}


@app.post("/api/sessions/start")
def start_lab(lab_id: str, student_name: str = "Student"):
    lab = _get_lab(lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")

    session_id = str(uuid.uuid4())[:8]

    try:
        containers = deploy_lab(lab, session_id)

        # Step 5 — pin the real substrate. Resolve OFF THE RUNNING CONTAINERS.
        runtime_digest = resolve_runtime_digest(containers)
        if not runtime_digest:
            # Do not silently deploy an unattributable lab.
            raise RuntimeError(
                "Could not resolve runtime digest from running containers; "
                "refusing to start an unattributable session"
            )

        # Start ttyd for each node
        ttyd_info = {}
        ttyd_ports = []
        for node_name in containers:
            port = _allocate_port()
            ttyd_ports.append(port)
            ttyd_info[node_name] = start_ttyd_process(
                port, containers[node_name]
            )

        SESSIONS[session_id] = {
            "lab_id": lab_id,
            "student_name": student_name,
            "status": "running",
            "created_at": time.time(),
            "nodes": containers,
            "ttyd_ports": ttyd_ports,
            "runtime_digest": runtime_digest,
        }

        return {
            "session_id": session_id,
            "lab": lab,
            "nodes": containers,
            "ttyd": ttyd_info,
            "runtime_digest": runtime_digest,
            "status": "running",
            "message": f"Lab '{lab.name}' is ready! Open the terminal below to start.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/submit")
def submit_config(session_id: str, node: str):
    grade = grade_config(session_id, SESSIONS.get(session_id, {}).get("lab_id", ""), node)
    return {"session_id": session_id, "node": node, "grade": grade}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "lab_id": session["lab_id"],
        "student_name": session["student_name"],
        "status": session["status"],
        "created_at": session["created_at"],
        "nodes": list(session["nodes"].keys()),
        "runtime_digest": session.get("runtime_digest", ""),
    }


@app.post("/api/sessions/{session_id}/stop")
def stop_session(session_id: str):
    session = SESSIONS.pop(session_id, None)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Clean up ttyd processes for THIS session only
    for port in session.get("ttyd_ports", []):
        proc = TTYD_PROCS.pop(port, None)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    # Destroy lab with session-specific topology
    lab = _get_lab(session["lab_id"])
    if lab:
        try:
            destroy_lab(lab, session_id)
        except Exception:
            pass

    return {"status": "destroyed", "session_id": session_id}


# --- ttyd Management ---

def start_ttyd_process(port: int, container: str) -> dict:
    """Start a ttyd process for a running container."""
    # Clean up existing on this port
    if port in TTYD_PROCS:
        old = TTYD_PROCS.pop(port)
        try:
            old.terminate()
            old.wait(timeout=5)
        except Exception:
            try:
                old.kill()
            except Exception:
                pass

    cmd = [
        "ttyd",
        "-p", str(port),
        "-W",
        "-i", "0.0.0.0",
        "-t", "fontSize=14",
        "-t", 'theme={"background":"#0f1117","foreground":"#e1e3eb"}',
        "docker", "exec", "-it", container, "sh",
    ]

    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    TTYD_PROCS[port] = proc

    # Use the actual routable IP, preferring the LAN IP
    host = "localhost"
    try:
        ip_output = subprocess.run(
            ["hostname", "-I"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().split()
        # Prefer a LAN (192.168.x.x) or routable IP that isn't Docker
        for candidate in ip_output:
            if candidate.startswith("192.168.") or candidate.startswith("10."):
                host = candidate
                break
        # Fallback: skip Docker bridge IPs and loopback
        if host == "localhost":
            for candidate in ip_output:
                if not candidate.startswith("172.") and candidate != "127.0.0.1":
                    host = candidate
                    break
        if host == "localhost":
            host = ip_output[0] if ip_output else "localhost"
    except Exception:
        pass

    return {
        "port": port,
        "container": container,
        "url": f"http://{host}:{port}",
        "pid": proc.pid,
    }


@app.on_event("shutdown")
def cleanup_all():
    for proc in TTYD_PROCS.values():
        try:
            proc.terminate()
        except Exception:
            pass


# --- Topology Endpoint ---

_ASCII_GLYPHS = {
    "pc": "[PC]",
    "switch": "[SW]",
    "router": "[RTR]",
    "firewall": "[FW]",
    "server": "[SRV]",
}


def _node_kind(node_name: str) -> str:
    """Classify a topology node by NAME (read the object, not the label)."""
    n = (node_name or "").strip().lower()
    if n.startswith("pc") or n.endswith("pc") or "pc-" in n:
        return "pc"
    if n.startswith("sw") or "switch" in n:
        return "switch"
    if n.startswith("fw") or "firewall" in n:
        return "firewall"
    if n.startswith("srv") or "server" in n:
        return "server"
    if n.startswith("r") and n[1:2].isdigit() or "router" in n or "rtr" in n:
        return "router"
    return "other"


def _node_glyph(kind: str) -> str:
    """Return a plain-ASCII kind marker. No emoji, no hardcoded PC."""
    return _ASCII_GLYPHS.get(kind, "[?]")


@app.get("/api/labs/{lab_id}/topology")
def get_lab_topology(lab_id: str):
    """Render a simple topology diagram for a lab."""
    lab = _get_lab(lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")

    topo_path = LABS_DIR / lab.topology_file
    if not topo_path.exists():
        raise HTTPException(status_code=404, detail="Topology file not found")

    with open(topo_path) as f:
        data = yaml.safe_load(f)

    nodes = list(data.get("topology", {}).get("nodes", {}).keys())
    links = data.get("topology", {}).get("links", [])

    node_badges = ""
    for n in nodes:
        kind = _node_kind(n)
        node_badges += f'<div class="topo-node topo-{kind}">{_node_glyph(kind)} {n}</div>'

    link_list = ""
    for link in links:
        if isinstance(link, list) and len(link) >= 2:
            a = link[0].split(":")[0]
            b = link[1].split(":")[0]
            link_list += f'<div class="topo-link">{a}  \u2500\u2500\u2500  {b}</div>'
        elif isinstance(link, dict):
            eps = link.get("endpoints", [])
            if len(eps) >= 2:
                a = eps[0].split(":")[0]
                b = eps[1].split(":")[0]
                link_list += f'<div class="topo-link">{a}  \u2500\u2500\u2500  {b}</div>'

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head><meta charset="UTF-8">
<title>Topology \u2014 {lab.name}</title>
<style>
    body {{ font-family: 'SF Mono', monospace; background: #0f1117; color: #e1e3eb; padding: 32px; }}
    h1 {{ font-size: 20px; margin-bottom: 4px; color: #00d4aa; }}
    .lab-id {{ font-size: 13px; color: #8b8fa3; margin-bottom: 24px; }}
    .topo-nodes {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }}
    .topo-node {{ background: #1a1d27; border: 1px solid #2d3145; border-radius: 8px; padding: 12px 20px; font-size: 14px; }}
    .topo-glyph {{ color: #00d4aa; margin-right: 6px; }}
    .topo-link {{ background: #242738; border-radius: 6px; padding: 8px 16px; margin: 4px 0; font-size: 13px; color: #8b8fa3; font-family: 'SF Mono', monospace; }}
    h3 {{ font-size: 14px; color: #8b8fa3; margin-bottom: 12px; }}
</style></head>
<body>
<h1>\U0001f5fa  {lab.name}</h1>
<div class="lab-id">{lab.id}</div>
<h3>Devices</h3>
<div class="topo-nodes">
{node_badges}
</div>
<h3>Connections</h3>
<div>
{link_list}
</div>
</body>
</html>"""
    return HTMLResponse(html)


# --- Lab Guide Endpoint ---

@app.get("/api/labs/{lab_id}/guide")
def get_lab_guide(lab_id: str):
    """Serve a lab's markdown guide file if it exists."""
    # Map lab IDs to likely guide filenames
    # Map lab IDs to guide markdown files
    guide_map = {
        "tier-01-foundation": "tier-01-foundation.md",
        "tier-02-router-basics": "tier-02-router-basics.md",
        "lab-01-crossing-subnets": "lab-2-crossing-subnets.md",
        "lab-02-switch-in-the-middle": "lab-2-switch-in-middle.md",
        "tier-03-router-switch-pc": "tier-03-router-switch-pc.md",
        "lab-03-lock-it-down": "lab-3-lock-it-down.md",
        "neteng-capstone": "neteng-capstone.md",
    }
    guide_file = guide_map.get(lab_id)
    if guide_file and guide_file.endswith(".md"):
        guide_path = LABS_DIR / guide_file
        if guide_path.exists():
            content = guide_path.read_text()
            return PlainTextResponse(content, media_type="text/markdown")

    # Fallback: try <lab-id>.md
    fallback = LABS_DIR / f"{lab_id}.md"
    if fallback.exists():
        return PlainTextResponse(fallback.read_text(), media_type="text/markdown")

    raise HTTPException(status_code=404, detail="No guide available for this lab")


# --- Serve Frontend ---

FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
