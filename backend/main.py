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

# Attributed-lab identity prefixes.
#
# `sha256:`      — the lab includes the pinned AEGIS substrate; the value is that
#                  substrate's transport-invariant layer-chain digest, comparable
#                  to install.sh's published `installed_layers_sha256`.
# `aegis-less:`  — the lab runs NO AEGIS substrate at all (e.g. the shipping
#                  two-PC demo: three alpine nodes, no FRR, no BGP). There is
#                  nothing pinned to verify, so the honest identity is a
#                  deterministic hash over the images the nodes ACTUALLY run.
#                  This is still an identity: it is derived off the running
#                  containers, is stable across a redeploy of the same lab, and
#                  changes if any node's image changes. It is NOT a refusal and
#                  NOT a pass — it is provenance for a lab that has no substrate.
#                  (Found 2026-09-20: the demo lab was refused outright because
#                  the guard conflated "no pinned substrate" with "unattributable",
#                  so the shipping demo could not start through the product.)
AEGIS_LESS_PREFIX = "aegis-less:"


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
    # FRR daemons this lab REQUIRES to be running on the substrate
    # (e.g. ["bgpd"]). Empty means "no dynamic-routing requirement" and keeps
    # historical behaviour. Enforced at deploy time against the substrate's
    # OWN /etc/frr/daemons so a lab can never be deployed onto a substrate that
    # can only grade it red forever (found 2026-09-20: lab-04 two-AS peering vs.
    # a `bgpd=no` image).
    requires_daemons: list[str] = []
    # The substrate image THIS lab's routers run. Defaults to the pinned base
    # substrate. A lab that requires a daemon the base disables (e.g. bgpd) must
    # name a substrate that enables it (aegis/frr-bgp:latest) — otherwise the
    # capability gate below will (correctly) refuse it. The gate reads the image
    # the lab actually deploys, not a global default, so capability and
    # deployability can never disagree.
    substrate_image: str = ""


class GraderResult(BaseModel):
    passed: bool
    score: float
    feedback: list[str]
    competencies: list[str]
    # Step 5 — runtime pin: a grade is only citable with the substrate it ran on.
    runtime_digest: str = ""
    # In-band discriminator. Three things can reach the client and they must
    # NOT look alike:
    #   "graded"  — the grader actually ran and judged the config. passed/score
    #               are meaningful.
    #   "error"   — the grader module raised. NOT a verdict on the student's
    #               config; the read is void and must not be shown as a fail.
    #   "refused" — no attributable substrate (no runtime digest). Rendered to
    #               the client as HTTP 409, but ALSO carried in-band here so any
    #               in-process caller (batch grader, CLI, export) sees the same
    #               three-state vocabulary instead of an exception it must catch.
    # Before this field, a crash and a wrong answer were both rendered as
    # "Not yet 0%", which told the student nothing and hid a broken grader.
    status: str = "graded"


# Refusal vocabulary. One shape for one state, everywhere it is observed.
# `grade_config` NEVER raises for a refused session: it returns a
# GraderResult(status="refused"). The HTTP route translates that to 409 so the
# wire contract is unchanged, but an in-process caller gets a value, not a
# traceback. (2026-09-20: the docstring claimed a `refused` status that no code
# path could actually produce — the 409 pre-empted every result construction.)
REFUSAL_FEEDBACK = [
    "⛔ Refused: this session has no runtime digest, so its state is "
    "unattributable and cannot be graded. Re-deploy the lab to pin the substrate."
]


def _refused_result() -> "GraderResult":
    """The single canonical refused-grade value (no digest, status='refused')."""
    return GraderResult(
        runtime_digest="",
        status="refused",
        passed=False,
        score=0.0,
        feedback=list(REFUSAL_FEEDBACK),
        competencies=[],
    )


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


def _substrate_image_for(topology_file: str) -> str:
    """Detect which AEGIS substrate a lab's routers run, from its topology.

    Scans node specs for the first `aegis/frr...` image. Falls back to the
    pinned base. This makes the topology the source of truth for capability:
    the gate reads exactly the image the lab will deploy, so a lab and its
    substrate cannot drift apart (lab-04 vs. a bgpd=no base was that drift).
    """
    try:
        with open(LABS_DIR / topology_file) as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return AEGIS_SUBSTRATE_IMAGE
    nodes = (data.get("topology") or {}).get("nodes") or {}
    if isinstance(nodes, dict):
        for spec in nodes.values():
            if not isinstance(spec, dict):
                continue
            image = spec.get("image")
            if isinstance(image, str) and image.startswith("aegis/frr"):
                return image
    return AEGIS_SUBSTRATE_IMAGE


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
            "requires_daemons": meta.get("requires_daemons", []),
            "substrate_image": _substrate_image_for(f.name),
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

SESSION_LABEL = "aegis.session.id"
LAB_LABEL = "aegis.lab.id"


def _running_clab_containers() -> list[tuple[str, str, str]]:
    """List `clab-*` containers as (name, session-label, lab-label).

    Labels are "" for containers the product did not deploy — those are
    someone else's (a hand-run lab, Ethan's labs) and must not be adopted.
    """
    out = subprocess.run(
        ["docker", "ps",
         "--format",
         f"{{{{.Names}}}}\t{{{{.Label \"{SESSION_LABEL}\"}}}}"
         f"\t{{{{.Label \"{LAB_LABEL}\"}}}}"],
        capture_output=True, text=True, timeout=15,
    )
    if out.returncode != 0:
        return []
    rows = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            parts += [""] * (3 - len(parts))
        name, session_label, lab_label = parts[0], parts[1], parts[2]
        if name.startswith("clab-"):
            rows.append((name, session_label.strip(), lab_label.strip()))
    return rows


def _session_id_from_container(name: str) -> str | None:
    """Extract the 8-char session id from `clab-<topo>-<sid>-<node>`.

    Session ids are `uuid4().hex[:8]` (lowercase hex). Node names may contain
    hyphens, and the session id is always an 8-char hex segment immediately
    followed by `-<node>`. We scan for the LAST 8-char hex segment so topologies
    whose base name itself contains hex-looking segments still parse right.
    """
    parts = name.split("-")
    for i in range(len(parts) - 2, 0, -1):
        seg = parts[i]
        if len(seg) == 8 and all(c in "0123456789abcdef" for c in seg):
            return seg
    return None


def reconcile_sessions() -> int:
    """Rebuild SESSIONS from running containers on startup.

    SESSIONS is in-memory, so a crash, restart, or systemd unit reload made the
    app forget every lab it had deployed while the containers kept running and
    consuming the host. `GET /api/sessions` then reported 0 sessions with dozens
    of live clab containers on the box — the product's view of reality and the
    host's actual state diverged, and the orphans were unaddressable (could not
    be listed, graded, or stopped by id).

    Reconcile by scanning `docker ps` for `clab-*` containers THAT CARRY OUR
    OWNERSHIP LABEL (`aegis.session.id`, stamped at deploy time by
    _stamp_session_labels). A container without the label was not deployed by
    this product — a hand-run lab, or another agent's (Ethan's) lab — and is
    deliberately NOT adopted: the product must never claim, grade, or offer to
    destroy a lab it did not create. (Before this gate, reconcile matched any
    `clab-<topo>-<8hex>-<node>` name, which swept in hand-deployed labs whose
    topology name happened to carry a hex-looking suffix — a real defect: it
    exposed a STOP route that would have torn down someone else's lab.)

    Group the adopted containers by the label's session id and rebuild each
    session the same way start_lab builds it — including resolving the runtime
    digest OFF THE RUNNING CONTAINERS, so a reconciled session still satisfies
    the Step 5 invariant (a state cannot be cited without its digest). Sessions
    whose digest cannot be resolved are NOT silently adopted with an empty
    digest; they are registered with runtime_digest="" and will refuse to grade,
    which is the honest outcome (they are visible and stoppable, but
    unattributable).

    Returns the number of sessions adopted.
    """
    names = _running_clab_containers()
    if not names:
        return 0

    grouped: dict[str, dict] = {}
    for name, owner_label, lab_label in names:
        # Ownership gate: only containers WE stamped. A blank label means the
        # product did not deploy this container (e.g. Ethan's lab) => not ours.
        if not owner_label:
            continue
        sid = owner_label
        # `clab-<topo>-<sid>-<node>` -> node is the remainder after the sid
        # segment. Split once on the sid boundary so hyphenated nodes survive.
        marker = f"-{sid}-"
        idx = name.find(marker)
        if idx != -1:
            node = name[idx + len(marker):]
            base = name[len("clab-"):idx]
        else:
            # Label present but the name does not embed the sid. Still adopt so
            # the containers stay addressable; node = trailing name segment.
            cut = name.rfind("-")
            if cut == -1:
                continue
            node = name[cut + 1:]
            base = name[len("clab-"):cut]
        entry = grouped.setdefault(
            sid, {"base": base, "lab_label": lab_label, "nodes": {}}
        )
        entry["nodes"][node] = name
        if lab_label:
            entry["lab_label"] = lab_label

    adopted = 0
    for sid, info in grouped.items():
        if sid in SESSIONS:
            continue
        # Prefer the lab id stamped at deploy (authoritative). Fall back to
        # reverse-mapping the topology name, then to the base name itself so a
        # renamed/removed lab is still addressable and stoppable.
        lab_id = info.get("lab_label") or ""
        if not lab_id:
            for lab in LABS:
                if _get_topology_name(lab.topology_file) == info["base"]:
                    lab_id = lab.id
                    break
        if not lab_id:
            lab_id = info["base"]

        try:
            digest = resolve_runtime_digest(info["nodes"]) if info["nodes"] else ""
        except Exception:
            digest = ""

        SESSIONS[sid] = {
            "lab_id": lab_id,
            "student_name": "(reconciled)",
            "status": "running",
            "created_at": time.time(),
            "nodes": info["nodes"],
            "ttyd_ports": [],
            "runtime_digest": digest,
            "reconciled": True,
        }
        adopted += 1
    return adopted


@app.on_event("startup")
def _on_startup_reconcile():
    """Adopt labs already running on the host so the product sees reality."""
    try:
        n = reconcile_sessions()
        print(f"[reconcile] adopted {n} running session(s) from live containers")
    except Exception as e:
        print(f"[reconcile] failed: {e}")


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

    # Stamp durable ownership on every node, at container-CREATION time.
    # Docker labels are immutable after creation (`docker update` on this daemon
    # has no --label-add), so this is the only way to mark a container as ours.
    # A durable label is what lets `reconcile_sessions` tell OUR labs from a
    # hand-deployed lab (e.g. Ethan's) after a restart, when SESSIONS is gone.
    topo = data.get("topology")
    nodes = topo.get("nodes") if isinstance(topo, dict) else None
    if isinstance(nodes, dict):
        for _node, spec in nodes.items():
            if not isinstance(spec, dict):
                continue
            labels = spec.get("labels")
            if not isinstance(labels, dict):
                labels = {}
            labels[SESSION_LABEL] = session_id
            labels[LAB_LABEL] = lab.id
            spec["labels"] = labels

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

# FRR daemons that watchfrr starts even when `/etc/frr/daemons` does not carry
# an explicit `<name>=yes` line. Verified 2026-09-20 on aegis/frr:latest: the
# file has no `zebra=`/`staticd=` line at all, yet both run under watchfrr.
# Trusting the file alone would under-report capability and refuse good labs.
_FRR_IMPLICIT_ON = {"zebra", "staticd", "mgmtd"}


def _substrate_daemons(image: str | None = None) -> dict[str, bool] | None:
    """Read a substrate's enabled FRR daemons from a throwaway container.

    Source of truth is the substrate AS RUN — read by starting it and asking
    the file plus FRR's implicit watchfrr defaults. Not a build log, not a
    label. `image` selects which substrate to read; None means the pinned base.
    Returns None when the substrate cannot be read (no image, docker error);
    callers must treat None as "unknown", never as "capable".
    """
    image = image or AEGIS_SUBSTRATE_IMAGE
    try:
        proc = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "cat",
             image, "/etc/frr/daemons"],
            capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    daemons: dict[str, bool] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.endswith("_options"):
            continue
        daemons[name] = value.strip().lower() == "yes"
    if not daemons:
        return None
    # watchfrr starts its always-on core daemons regardless of an explicit
    # `<name>=yes` line (the file does not list zebra/staticd at all).
    for name in _FRR_IMPLICIT_ON:
        daemons.setdefault(name, True)
    return daemons


class CapabilityRefusal(RuntimeError):
    """The substrate cannot run the lab's required daemons. A refusal, not an
    error: the request is well-formed and the answer is 'no', with a reason.
    Rendered to the wire as 409, matching the digest-refusal convention."""


def _capability_refusal(lab: LabDef) -> str | None:
    """Return a refusal reason when the substrate cannot run the lab's daemons.

    A refusal here is the honest outcome: deploying would put a lab on a
    substrate that can only ever grade it red, so every red would be the
    substrate's, not the student's. Better to refuse with a reason than to
    emit a green-looking deploy and an unexplained failure.
    """
    required = [d for d in (lab.requires_daemons or []) if d]
    if not required:
        return None
    image = lab.substrate_image or AEGIS_SUBSTRATE_IMAGE
    daemons = _substrate_daemons(image)
    if daemons is None:
        return ("substrate capability unknown: could not read /etc/frr/daemons "
                f"from {image}; refusing to deploy "
                f"{lab.id} which requires {required}")
    missing = [d for d in required if not daemons.get(d, False)]
    if not missing:
        return None
    return (f"substrate cannot run {lab.id}: requires daemons {missing}, "
            f"but {image} enables only "
            f"{sorted(d for d, on in daemons.items() if on)}. "
            "Redeploy on a substrate built with those daemons enabled.")


def deploy_lab(lab: LabDef, session_id: str) -> dict:
    """Deploy a ContainerLab topology with a session-unique name, return node info."""
    if not (LABS_DIR / lab.topology_file).exists():
        raise FileNotFoundError(f"Topology file not found: {lab.topology_file}")

    # Capability gate: never deploy a lab the pinned substrate cannot run.
    refusal = _capability_refusal(lab)
    if refusal:
        raise CapabilityRefusal(refusal)

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

    # Ownership is stamped at CREATION time by _prepare_topology (docker
    # labels are immutable after creation on this daemon), so nothing to do
    # here. reconcile_sessions reads the label to decide what is ours.
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

    A lab running NO AEGIS substrate at all (e.g. the shipping two-PC demo: three
    alpine nodes, no FRR) is not ambiguous — it is a legitimate unpinned lab. It
    is attributed with `aegis-less:<sha256>`, a deterministic identity over the
    node images actually in use, rather than refused. Only a lab whose identity
    cannot be read off the running containers returns "" (hard refusal).

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
        # No node runs the pinned AEGIS substrate. This is NOT automatically
        # unattributable: a legitimate lab may run no substrate at all (the
        # shipping two-PC demo is three alpines with no routing protocol).
        # Attribute it honestly instead of refusing: a deterministic identity
        # over the node images actually in use. Blank is reserved for a lab we
        # truly cannot resolve (see below).
        return _aegis_less_identity(containers)
    if len(substrate_digests) != 1:
        # Two different AEGIS substrates in one lab: genuinely ambiguous.
        return ""
    live = substrate_digests.pop()

    pin = _installed_pin()
    expected = _pinned_substrate_digests(pin)
    if not expected:
        # No installer-published identity on this host: unattributable.
        return ""
    if live not in expected:
        # Live substrate is not one the installer verified.
        return ""
    return live


def _pinned_substrate_digests(pin: dict) -> set[str]:
    """The set of substrate layer-chain digests the installer verified.

    AEGIS ships more than one substrate: the base (static routing) and the
    BGP variant (bgpd enabled, for lab-04). Each is a legitimate, install-verified
    substrate with its OWN transport-invariant layer chain, so the install record
    publishes a SET of accepted digests. A grade on any of them is citable.

    Reads `installed_substrate_digests` (space-separated) when present, and
    always folds in the legacy single `installed_layers_sha256` for
    backward-compatibility with records written by older installers.
    """
    digests: set[str] = set()
    multi = pin.get("installed_substrate_digests", "").split()
    for d in multi:
        digests.add(d if d.startswith("sha256:") else f"sha256:{d}")
    legacy = pin.get("installed_layers_sha256", "")
    if legacy:
        digests.add(legacy if legacy.startswith("sha256:") else f"sha256:{legacy}")
    return digests


def _aegis_less_identity(containers: dict) -> str:
    """Content identity for a lab that runs NO pinned AEGIS substrate.

    Returns "" when it cannot be computed from the RUNNING containers (an
    unresolvable image => genuinely unattributable => refuse). Otherwise returns
    `aegis-less:<sha256>`, a deterministic hash over each node's sorted
    `name=layer-chain` pair. Derived off the same running-container reads as the
    substrate path (never a build log, never a tag), so it survives a redeploy
    of the same lab and changes the moment any node's image changes.
    """
    node_layers = []
    for name, container in sorted(containers.items()):
        image_ref = _container_image(container)
        if not image_ref:
            return ""
        layers = _image_layers_sha(image_ref)
        if not layers:
            return ""
        node_layers.append(f"{name}={layers}")
    if not node_layers:
        return ""
    h = hashlib.sha256("\n".join(node_layers).encode()).hexdigest()
    return f"{AEGIS_LESS_PREFIX}{h}"


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
    # except below. Refusal is returned as a value (GraderResult(status="refused")),
    # NOT raised, so in-process callers see the same three-state vocabulary the
    # route does. The route then translates status="refused" to HTTP 409, keeping
    # the wire contract identical. (Earlier layout raised inside the try, so
    # `except Exception` swallowed the refusal and returned a 200 with an EMPTY
    # runtime_digest — silently defeating the gate. Found live 2026-09-20.)
    digest = _session_runtime_digest(session)
    if not digest:
        return _refused_result()

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
        # Carry the digest. A grader crash is still an attributable read: we know
        # the substrate it was attempted against. Dropping the digest here (as
        # the previous revision did) produced an unattributed grade from the
        # error path — the exact state Step 5 forbids. status="error" keeps this
        # from being read as a verdict on the student's configuration.
        return GraderResult(
            runtime_digest=digest,
            status="error",
            passed=False, score=0,
            feedback=[f"❌ Grader error: {str(e)}"],
            competencies=[],
        )


def _session_runtime_digest(session: dict) -> str:
    """The session's runtime digest, or "" when the session is unattributable.

    Step 5 invariant: a state cannot be cited without its digest. This is a pure
    read — it does NOT raise. Callers decide the shape of the refusal:
      - grade_config   -> returns GraderResult(status="refused")
      - the HTTP route -> translates that to 409
    Keeping the read pure is what lets the in-process and over-the-wire callers
    observe the SAME refusal state instead of two different ones.
    """
    return session.get("runtime_digest") or ""


def _require_runtime_digest(session: dict) -> str:
    """Deprecated shim: digest or HTTPException(409).

    Retained for the few call sites that still want the hard-fail behaviour
    (`_fallback_grade`, and any pre-existing external caller). New code should
    prefer `_session_runtime_digest` + `_refused_result` so refusals travel as
    values rather than exceptions.
    """
    digest = _session_runtime_digest(session)
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
    except CapabilityRefusal as e:
        # A refusal, not a server fault: 409 with a reason the operator can act on.
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/submit")
def submit_config(session_id: str, node: str):
    grade = grade_config(session_id, SESSIONS.get(session_id, {}).get("lab_id", ""), node)
    # Refusal travels in-band as a value; render it to the wire as 409 so the
    # HTTP contract is unchanged. One state, one shape, both observers.
    if grade.status == "refused":
        raise HTTPException(
            status_code=409,
            detail=grade.feedback[0] if grade.feedback else "Refused: no runtime digest",
        )
    return {"session_id": session_id, "node": node, "grade": grade}


@app.get("/api/sessions")
def list_sessions():
    """Enumerate live sessions.

    Without this, the only way to stop or grade a session was to already know
    its id. An operator looking at running containers (the "who is on this host"
    question) had no in-app path to the id. This is the read side of the session
    lifecycle: start -> list -> get -> submit -> stop.

    Each entry carries the session's runtime_digest (may be "" only if a session
    is mid-teardown); a state is never cited without its identity.
    """
    sessions = []
    for sid, s in SESSIONS.items():
        sessions.append({
            "session_id": sid,
            "lab_id": s.get("lab_id", ""),
            "student_name": s.get("student_name", ""),
            "status": s.get("status", ""),
            "created_at": s.get("created_at", 0),
            "nodes": list(s.get("nodes", {}).keys()),
            "runtime_digest": s.get("runtime_digest", ""),
        })
    sessions.sort(key=lambda x: x["created_at"], reverse=True)
    return {"sessions": sessions, "count": len(sessions)}


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
