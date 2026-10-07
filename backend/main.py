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
import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import sys
import time
import traceback
import uuid
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request
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

# Serializes lab deployment. WHY (found 2026-09-27, cron run 10): containerlab
# creates a SHARED docker network named "clab" on first deploy. FastAPI runs sync
# route handlers in a threadpool, so two concurrent POST /api/sessions/start calls
# race: both check for "clab", both try to create it, and the loser gets
# "Error response from daemon: network with name clab already exists" -> HTTP 500.
# A second student starting at the same moment as the first simply failed.
# Deploys are heavy and rare; serializing them costs nothing and removes the race.
_DEPLOY_LOCK = threading.Lock()
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

try:
    os.makedirs(LABS_DIR, exist_ok=True)
except (FileExistsError, NotADirectoryError) as e:
    # RUN 242 (2026-10-06): measured, this fails LOUDLY and in the right place already -- with
    # lab-definitions replaced by a FILE the service refuses to start and the log names the exact call and
    # path (FileExistsError: [Errno 17] File exists: '.../lab-definitions'). That is correct behaviour, so
    # this is not a bug fix: it turns a traceback into a sentence an operator can act on, because a STARTUP
    # failure is the worst place to make someone read a stack (run 239's NameError presented as the unit
    # sitting in "activating" while the cause sat in a log). The process still exits -- it must.
    raise SystemExit(
        f"[startup] {LABS_DIR} exists but is not a directory ({e}).\n"
        f"[startup] The product cannot start without its lab-definitions directory. Move the file aside "
        f"or restore the directory."
    )


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
    # Does the lab's middle device have to be a REAL switch OS (not a Linux PC
    # running a software bridge)? Sourced from the lab's own metadata so the
    # lab declares its own contract; the per-lab audit
    # (.nexus/proofs/lab-authenticity-audit-20260922-2205.txt) is the evidence
    # behind each value. 2026-09-22: demo-01-plain PASSES with a plain Alpine
    # box in the middle -- it validates CONNECTIVITY ONLY. A student hitting a
    # green grade there is not looking at a real switch, and nothing in the API
    # said so. This field makes that honest on the wire, not just in a
    # markdown banner nobody in the UI reads.
    validates_switch_authenticity: bool = False
    # The substrate image THIS lab's routers run. Defaults to the pinned base
    # substrate. The capability gate below reads the image the lab ACTUALLY
    # deploys (not a global default), so capability and deployability can never
    # disagree: a lab that needs a daemon the substrate disables is (correctly)
    # refused rather than deployed onto an image that can only grade it red.
    substrate_image: str = ""


class GraderResult(BaseModel):
    passed: bool
    score: float
    feedback: list[str]
    competencies: list[str]
    # RUN 227: which node this result is ABOUT. The graders stamp it where the grading happens, so
    # the lab-verdict check can compare it against the key it was filed under.
    node: str = ""
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


def _refused_result_with(reason: str) -> "GraderResult":
    """A refusal that says WHY, in the same three-state vocabulary as _refused_result.

    Added 2026-10-04 (run 174, decision #7). A grader that could not examine a node must
    not answer "you failed" -- see grade_config. The refusal stays a VALUE, and the route
    still renders every refusal as HTTP 409, so the wire contract is unchanged.
    """
    return GraderResult(
        runtime_digest="",
        status="refused",
        passed=False,
        score=0.0,
        feedback=[reason],
        competencies=[],
    )


def _container_running(name: str) -> bool:
    """Host-side: is this node's container actually running? Fails SAFE (unreadable -> False).

    Deployments stop containers for real reasons, and a grader asked about a container
    that no longer exists produces no output -- which is indistinguishable from a wrong
    configuration unless we check first.
    """
    if not name or not isinstance(name, str):
        return False
    try:
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True, text=True, timeout=10,
        )
        return out.returncode == 0 and out.stdout.strip().lower() == "true"
    except Exception:
        return False


def _node_examinable(name: str) -> bool:
    """Can a grader actually LOOK at this node right now? Fails safe (unreadable -> False).

    `_container_running` is not enough: a container mid-teardown still reports
    State.Running=true for a moment while `docker exec` already refuses, which is how a
    submit racing a stop produced a confident FAIL ("no output from sr_cli") from a node
    nobody could examine (reproduced live 2026-10-04, twice). This asks the question the
    grader is really asking: can a command run in it?
    """
    if not name or not isinstance(name, str):
        return False
    try:
        out = subprocess.run(
            ["docker", "exec", name, "true"],
            capture_output=True, text=True, timeout=10,
        )
        return out.returncode == 0
    except Exception:
        return False


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

# RUN 240 (2026-10-06): files whose YAML does not parse at all, recorded by name. Declared ABOVE the
# module-level _reload_labs() call, like everything else that runs there (see run 239's NameError).
_LABS_UNPARSEABLE: list = []


def _parse_yaml_metadata(path: Path) -> dict | None:
    """Parse the metadata section from a topology YAML.

    RUN 240: a YAML SYNTAX error used to be caught by the same `except` as "no metadata section" -- both
    returned None, and the discover loop then dropped the file silently. Measured: appending an unclosed
    flow sequence to LAB-B's definition removed the lab from the catalog and the reload answered a plain
    {"status":"reloaded","count":1} with NOTHING naming the file. An operator watching the count would see
    2 become 1 and have no way to know why. Unreadable files are now recorded and reported by name.
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            if data and "metadata" in data:
                return data["metadata"]
    except yaml.YAMLError as e:
        _LABS_UNPARSEABLE.append({"file": path.name, "error": str(e).splitlines()[0][:200]})
        print(f"[labs] UNPARSEABLE {path.name}: {str(e).splitlines()[0][:160]}", file=sys.stderr)
    except OSError:
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
    """Scan lab-definitions/ for YAML files with metadata sections.

    Scans the top level AND one level of subdirectories, so a lab can keep
    its topology plus its `assets/` (e.g. switch startup configs) together in
    its own folder. `topology_file` is stored as a path RELATIVE to
    LABS_DIR so every `LABS_DIR / topology_file` join still resolves, and
    containerlab resolves in-YAML `startup-config` paths relative to the
    topology file's own directory.
    """
    labs = []
    seen_ids = set()
    candidates = list(LABS_DIR.glob("*.yml"))
    for sub in sorted(p for p in LABS_DIR.iterdir() if p.is_dir()):
        candidates.extend(sorted(sub.glob("*.yml")))
    # Backups must never load as labs. `X.yml.bak-<date>` never matched the glob, but a
    # file named `X.bak.yml` WOULD have (it ends in .yml and can carry valid metadata) —
    # the only thing stopping that today is the naming convention. Made structural
    # 2026-10-04 rather than left to convention.
    candidates = [f for f in candidates
                  if not f.name.startswith(".")
                  and ".bak" not in f.name
                  and ".stale" not in f.name
                  and ".orig" not in f.name]
    for f in sorted(candidates):
        meta = _parse_yaml_metadata(f)
        if not meta or "id" not in meta:
            continue
        lab_id = meta["id"]
        if lab_id in seen_ids:
            continue
        seen_ids.add(lab_id)
        rel = f.relative_to(LABS_DIR)
        labs.append({
            "id": lab_id,
            "name": meta.get("name", lab_id),
            "description": meta.get("description", ""),
            "difficulty": meta.get("difficulty", "Beginner"),
            "duration_min": meta.get("duration_min", 45),
            "competencies": meta.get("competencies", []),
            "course": meta.get("course", ""),
            "topology_file": str(rel),
            "grader_module": meta.get("grader", f"grader_{lab_id}"),
            "instructions": meta.get("instructions", []),
            "tip": meta.get("tip", ""),
            "gradeable_nodes": meta.get("gradeable_nodes", []),
            "requires_daemons": meta.get("requires_daemons", []),
            "validates_switch_authenticity": bool(
                meta.get("validates_switch_authenticity", False)
            ),
            "substrate_image": _substrate_image_for(str(rel)),
        })
    return labs


LABS: list[LabDef] = []


def _startup_config_paths(topology_file):
    """{node: startup-config value} for a topology, or {} if it cannot be read.

    RUN 237 (2026-10-06): these values are consumed by containerlab at deploy time, resolved relative to
    the topology file -- so a `../` here asks containerlab to copy a file from elsewhere on the host into
    the lab's container. Same containment rule as run 236's graders: a lab definition may only reference
    files inside its own directory.
    """
    try:
        with open(LABS_DIR / topology_file) as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}
    nodes = (data.get("topology") or {}).get("nodes") or {}
    out = {}
    if isinstance(nodes, dict):
        for name, spec in nodes.items():
            if isinstance(spec, dict) and spec.get("startup-config"):
                out[name] = spec["startup-config"]
    return out


def _topology_node_names(topology_file):
    """The node names a lab's topology ACTUALLY defines; None when it cannot be read.

    RUN 224 (2026-10-06): nothing cross-checked a lab's declared gradeable_nodes against its own
    topology. Measured: adding `ghost1` to LAB-B's gradeable_nodes loaded cleanly, the catalog
    advertised it, and grading it answered "This lab has no node 'ghost1'" -- the contradiction was
    only discovered by a student pressing a button that should never have been offered.
    """
    if not topology_file:
        return None
    try:
        with open(LABS_DIR / topology_file) as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return None
    nodes = (data.get("topology") or {}).get("nodes")
    if isinstance(nodes, dict):
        return set(nodes.keys())
    if isinstance(nodes, list):
        return set(n for n in nodes if isinstance(n, str))
    return None


LABS_REJECTED: list = []


_GUIDE_MAP = {
    "tier-01-foundation": "tier-01-foundation.md",
    "tier-02-router-basics": "tier-02-router-basics.md",
    "lab-01-crossing-subnets": "lab-2-crossing-subnets.md",
    "lab-02-switch-in-the-middle": "lab-2-switch-in-middle.md",
    "tier-03-router-switch-pc": "tier-03-router-switch-pc.md",
    "lab-03-lock-it-down": "lab-3-lock-it-down.md",
    "neteng-capstone": "neteng-capstone.md",
}


def _guide_path_for(lab_id, lab=None):
    """Where this lab's guide lives, or None if it ships none.

    RUN 239 (2026-10-06): this resolution lived inline in the route and nowhere else, so a lab whose guide
    was missing got served SILENTLY -- a student only found out by pressing "Lab Guide" and getting a 404 in
    a new tab (measured in run 215). One source of truth now, so the loader can name it at load.
    A WARNING, deliberately not a refusal: measured, a lab with no guide still starts, still carries its 9
    instruction lines, still grades and still reaches "submitted" -- refusing it would take a WORKING lab
    offline to fix a reading problem.

    Defined ABOVE _reload_labs on purpose: _reload_labs runs at module level, so everything it calls must
    already exist. (My first attempt got this wrong and the service failed to start -- NameError.)
    The loader passes `lab` so this works before _get_lab is defined; the route omits it.
    """
    guide_file = _GUIDE_MAP.get(lab_id)
    if guide_file and guide_file.endswith(".md"):
        p = LABS_DIR / guide_file
        if p.exists():
            return p
    p = LABS_DIR / f"{lab_id}.md"
    if p.exists():
        return p
    if lab is None:
        lab = _get_lab(lab_id)
    if lab:
        p = LABS_DIR / Path(lab.topology_file).parent / f"{lab_id}.md"
        if p.exists():
            return p
    return None


def _reload_labs() -> list:
    """Rebuild LABS from disk, REFUSING individual malformed labs instead of dying.

    RUN 222 (2026-10-05): this used to be `LABS = [LabDef(**d) for d in discovered]` with no guard,
    and it runs at MODULE level. One lab definition with a wrong-typed field (measured live with
    `duration_min: soon`) therefore raised pydantic ValidationError during import: the service did
    not start at all (`nexus.service: Failed with result 'exit-code'`, no API), and the reload
    endpoint answered a bare 500. One bad metadata file must not be able to take the product down.
    Each lab is now validated on its own; a malformed one is refused BY NAME, logged, and skipped,
    and the labs that do validate keep serving.
    """
    global LABS, LABS_REJECTED
    _LABS_UNPARSEABLE.clear()
    discovered = _discover_labs()
    labs, rejected = [], []
    for d in discovered:
        try:
            # RUN 224: a lab that VALIDATES can still contradict its own topology.
            _topo = _topology_node_names(d.get("topology_file"))
            if _topo is None:
                raise ValueError("topology unreadable: %s" % d.get("topology_file"))
            _declared = set(d.get("gradeable_nodes") or [])
            _lab_dir = (LABS_DIR / d.get("topology_file", "")).parent.resolve()
            for _dev, _sp in _startup_config_paths(d.get("topology_file", "")).items():
                _cand = (Path(_sp) if os.path.isabs(_sp) else (_lab_dir / _sp)).resolve()
                try:
                    _cand.relative_to(_lab_dir)
                except ValueError:
                    raise ValueError(
                        "startup-config for %s resolves outside the lab directory (%s)" % (_dev, _sp)
                    )
                # RUN 238: containment is not existence. Measured: a lab whose startup-config named a
                # file that was never shipped was served happily and only failed at DEPLOY time -- a 500
                # carrying a wall of containerlab output instead of a sentence at load. If the product
                # ships a lab, the files that lab names must be there.
                if not _cand.is_file():
                    raise ValueError(
                        "startup-config for %s names a file that does not exist: %s" % (_dev, _sp)
                    )
            if not _declared <= _topo:
                raise ValueError(
                    "gradeable_nodes names nodes the topology does not define: "
                    + ", ".join(sorted(_declared - _topo))
                )
            labs.append(LabDef(**d))
        except Exception as e:
            rejected.append({"id": d.get("id"), "error": str(e).splitlines()[0][:200]})
            print(f"[labs] REFUSED malformed lab definition {d.get('id')!r}: {e}", file=sys.stderr)
    LABS = labs
    LABS_REJECTED = rejected + list(_LABS_UNPARSEABLE)   # RUN 240: name the files that did not parse
    # RUN 239: say it out loud when a shipped lab has no guide, instead of letting a student discover it.
    for _lab in LABS:
        if _guide_path_for(_lab.id, lab=_lab) is None:
            print(f"[labs] WARNING: lab {_lab.id!r} ships no guide -- 'Lab Guide' will 404 for students",
                  file=sys.stderr)
    if LABS_REJECTED:
        print(f"[labs] {len(LABS_REJECTED)} definition(s) skipped; serving {len(labs)}", file=sys.stderr)
    return LABS_REJECTED   # RUN 240: includes the files that did not PARSE, not just those that failed checks


_reload_labs()


def _get_lab(lab_id: str) -> LabDef | None:
    for lab in LABS:
        if lab.id == lab_id:
            return lab
    return None


# --- Dynamic Grader Loading ---

_GRADER_CACHE: dict = {}


_LAB_VERDICT_ERROR: str = ""   # why the last lab-verdict computation failed


def _lab_verdict_passed(grader, session) -> bool:
    """True only if the grader's own LAB-LEVEL verdict passes.

    A grader may expose grade_all(session) -> {"passed": bool, ...}. That is the
    product's real success condition (e.g. demo-01: pc-a.passed AND sw1.passed;
    demo-02: end-to-end AND both switches real AND router). Session status must
    reflect THAT, not whether one node happened to pass.

    Never raises: if a grader has no grade_all, or it errors, return False so
    status stays "running". A failed verdict check must not become a new
    grading failure — the per-node grade is still returned untouched.
    """
    # RUN 225 (2026-10-06): tri-state. This used to swallow a grade_all failure into False. Measured
    # live: a grader whose lab-level check named a node the lab does not have (results["ghost1"]) left
    # every node green and the lab permanently "running", with the only trace a log line -- the student
    # saw all-green with no explanation. False means "the lab did not pass"; None means "we could not
    # compute it". Those are different facts and must not be conflated.
    global _LAB_VERDICT_ERROR
    fn = getattr(grader, "grade_all", None)
    if not callable(fn):
        _LAB_VERDICT_ERROR = "the grader defines no grade_all()"
        return None
    try:
        verdict = fn(session)
        _LAB_VERDICT_ERROR = ""
        if isinstance(verdict, dict):
            _passed = bool(verdict.get("passed"))
            # RUN 226 (2026-10-06): COVERAGE IS PART OF THE CLAIM. A grader that grades FEWER nodes
            # than the lab declares can report "passed" while a declared node was never checked.
            # Measured live: with sw2 dropped from LAB-B's grade_all, an unsound sw2 (its IRB address
            # removed, path still working) ended in a session marked "submitted". So before trusting
            # "passed", check that the nodes the grader says it graded cover the nodes the lab declares.
            _lab = _get_lab(session.get("lab_id", ""))
            _declared = set(getattr(_lab, "gradeable_nodes", None) or [])
            _graded = set((verdict.get("nodes") or {}).keys())
            _missing = _declared - _graded
            _mislabelled = [k for k, v in (verdict.get("nodes") or {}).items()
                            if isinstance(v, dict) and v.get("node") and v.get("node") != k]
            if _mislabelled:
                _LAB_VERDICT_ERROR = ("a result was filed under the wrong node name: "
                                      + ", ".join(sorted(_mislabelled)))
                print(f"[lab-verdict] MISLABELLED RESULT for {session.get('lab_id')!r}: "
                      f"{_LAB_VERDICT_ERROR}", file=sys.stderr)
                return None
            if _declared and _missing:
                _LAB_VERDICT_ERROR = ("the grader did not grade declared node(s): "
                                      + ", ".join(sorted(_missing)))
                print(f"[lab-verdict] COVERAGE SHORTFALL for {session.get('lab_id')!r}: "
                      f"{_LAB_VERDICT_ERROR}", file=sys.stderr)
                return None
            return _passed
        # A grader that returns a non-dict verdict reports no node breakdown, so its coverage cannot be
        # verified here. Left as-is deliberately (both shipped graders return dicts); noted in run 226.
        return bool(getattr(verdict, "passed", False))
    except Exception as e:
        _LAB_VERDICT_ERROR = f"{type(e).__name__}: {e}"
        print(f"[lab-verdict] grade_all FAILED ({getattr(grader, '__name__', 'grader')}); the lab "
              f"result cannot be computed: {_LAB_VERDICT_ERROR}", file=sys.stderr)
        return None


def _load_grader(module_name: str):
    """Import a grader module by name, from WITHIN the product's own grader directories.

    RUN 236 (2026-10-06): the two lookups used to be `LABS_DIR / f"{module_name}.py"` and
    `BASE_DIR/"backend"/"graders" / f"{module_name}.py"` with NO containment check. `..` walks straight
    out of both. Measured: setting a lab's `grader:` to `../OUTSIDE-canary-r236` resolved and EXECUTED a
    module one directory above the lab tree -- the grade came back passed=true 1.0 with feedback
    "OUTSIDE module executed". A lab definition is DATA; it must not be able to run code from anywhere on
    the filesystem. Each candidate is now resolved and required to sit under its permitted directory, and
    a refusal is logged by name instead of being silent.
    """
    if module_name in _GRADER_CACHE:
        return _GRADER_CACHE[module_name]

    for base in (LABS_DIR, BASE_DIR / "backend" / "graders"):
        try:
            candidate = (base / f"{module_name}.py").resolve()
            base_resolved = base.resolve()
            candidate.relative_to(base_resolved)          # containment: raises ValueError if it escapes
        except ValueError:
            print(f"[grader] REFUSED {module_name!r}: resolves outside {base}", file=sys.stderr)
            continue
        except Exception:
            continue
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location(module_name, candidate)
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

        # Restore terminals for the adopted session (added 2026-09-29, cron run 70).
        # WHY: the service restart that runs this reconcile KILLS the previous
        # process's ttyd children (they are in its systemd cgroup), so the lab came
        # back with containers and grading intact but NO terminals -- GET
        # /api/sessions advertised ttyd: {} and a student had no way to get a shell
        # back except stopping and re-starting the lab. Re-start one ttyd per node
        # so an adopted session looks like a running lab again. This runs at most
        # once per session: reconcile skips ids already in SESSIONS
        # (`if sid in SESSIONS: continue`), including its periodic ghost-reap calls.
        ttyd_info = {}
        ttyd_ports = []
        try:
            for node_name, container in info["nodes"].items():
                port = _allocate_port()
                ttyd_ports.append(port)
                ttyd_info[node_name] = start_ttyd_process(port, container)
        except Exception as e:
            print(f"[reconcile] ttyd restore failed for {sid}: {e}")

        SESSIONS[sid] = {
            "lab_id": lab_id,
            "student_name": "(reconciled)",
            "status": "running",
            "created_at": time.time(),
            "nodes": info["nodes"],
            "ttyd_ports": ttyd_ports,
            "ttyd": ttyd_info,
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


# --- Ghost reaper (added 2026-09-27 by Selina, cron-driven) -----------------
# WHY: reconcile_sessions() is correct but was only called ONCE, at startup.
# Any session whose containers die underneath the process (manual docker rm,
# containerlab destroy by hand, a crashed containerlab) stayed registered as
# "running" forever -> GET /api/sessions lied, and ttyd terminals leaked.
# This reaps ghosts on a timer so the registry matches the host. It calls the
# SAME reconcile_sessions() the startup hook uses; no new semantics.
#
# SWITCHABLE: set NEXUS_GHOST_REAP=0 in the environment to disable entirely.
# Any failure is swallowed and logged -- the reaper must never take the app down.
GHOST_REAP_SECONDS = int(os.environ.get("NEXUS_GHOST_REAP_SECONDS", "120"))
GHOST_REAP_ENABLED = os.environ.get("NEXUS_GHOST_REAP", "1") not in ("0", "false", "False")


async def _ghost_reap_loop():
    while True:
        try:
            await asyncio.sleep(GHOST_REAP_SECONDS)
            before = len(SESSIONS)
            # reconcile_sessions ADOPTS live labelled containers; ghosts are
            # sessions it does NOT adopt and that have no containers -> drop them.
            live = set()
            try:
                r = subprocess.run(
                    ["docker", "ps", "-a", "--format", "{{.Names}}"],
                    capture_output=True, text=True, timeout=20,
                )
                live = set(r.stdout.split())
            except Exception as e:
                print(f"[ghost-reap] docker ps failed, skipping: {e}")
                continue

            dropped = []
            for sid in list(SESSIONS.keys()):
                mine = [n for n in live if f"-{sid}-" in n]
                if not mine:
                    dropped.append(sid)
            for sid in dropped:
                session = SESSIONS.pop(sid, None)
                # best-effort: release any ttyd ports the ghost still held
                try:
                    for port in (session or {}).get("ttyd_ports", []) or []:
                        subprocess.run(["pkill", "-f", f"ttyd -p {port}"],
                                       capture_output=True, timeout=10)
                except Exception:
                    pass
            if dropped:
                print(f"[ghost-reap] dropped {len(dropped)} ghost session(s): {dropped} "
                      f"(registry {before} -> {len(SESSIONS)})")
        except Exception as e:
            print(f"[ghost-reap] error (non-fatal): {e}")


@app.on_event("startup")
def _on_startup_ghost_reaper():
    """Start the periodic ghost reaper (disable with NEXUS_GHOST_REAP=0)."""
    if not GHOST_REAP_ENABLED:
        print("[ghost-reap] disabled by NEXUS_GHOST_REAP")
        return
    try:
        asyncio.get_event_loop().create_task(_ghost_reap_loop())
        print(f"[ghost-reap] enabled, every {GHOST_REAP_SECONDS}s")
    except Exception as e:
        print(f"[ghost-reap] could not start: {e}")


# --- Orphaned topology-dir sweep (added 2026-09-28 by Selina, cron run 40) ----
# WHY: containerlab writes its runtime directory (`clab-<topology-name>/`) NEXT TO
# the topology file it is given. We hand it a session copy inside the lab's own
# folder (so in-YAML `assets/` still resolve), so the runtime dir lands inside
# lab-definitions/. `containerlab destroy -t <path>` removes the containers AND
# its own dir, so a clean start/stop leaves nothing. But a session torn down by
# anything OTHER than our stop path (process kill, host reboot, crashed clab)
# strands the dir permanently. Measured 2026-09-28: 13 orphaned dirs / 4.3M, five
# of them inside the two shipping lab folders - runtime junk that would ship with
# the lab definitions. Stop-time cleanup alone cannot cover a killed process, so
# this sweeps at startup, when the answer to "is anything using this dir?" is
# knowable: it removes only dirs with NO matching live container.
#
# SAFETY: never touches a dir whose topology name matches a running container.
# Runs once, before reconcile adopts live labs; any failure is logged, never fatal.
# Disable with NEXUS_SWEEP_ORPHAN_DIRS=0.
SWEEP_ORPHAN_DIRS = os.environ.get("NEXUS_SWEEP_ORPHAN_DIRS", "1") not in ("0", "false", "False")


def _sweep_orphaned_topology_dirs() -> int:
    """Remove clab-* runtime dirs that have no matching live container."""
    try:
        r = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=20,
        )
        live = set(r.stdout.split())
    except Exception as e:
        print(f"[dir-sweep] docker ps failed, skipping: {e}")
        return 0

    removed = 0
    for d in LABS_DIR.rglob("clab-*"):
        if not d.is_dir():
            continue
        # containerlab names containers `clab-<topology-name>-<node>`; the dir is
        # `clab-<topology-name>`. Anything live under this dir's name means keep.
        name = d.name
        if any(c == name or c.startswith(name + "-") for c in live):
            continue
        try:
            shutil.rmtree(d)
            removed += 1
        except Exception as e:
            print(f"[dir-sweep] could not remove {d}: {e}")
    if removed:
        print(f"[dir-sweep] removed {removed} orphaned topology dir(s)")
    return removed


@app.on_event("startup")
def _on_startup_dir_sweep():
    """Sweep orphaned containerlab runtime dirs (disable with NEXUS_SWEEP_ORPHAN_DIRS=0)."""
    if not SWEEP_ORPHAN_DIRS:
        print("[dir-sweep] disabled by NEXUS_SWEEP_ORPHAN_DIRS")
        return
    try:
        _sweep_orphaned_topology_dirs()
    except Exception as e:
        print(f"[dir-sweep] failed (non-fatal): {e}")


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
    # For labs in a subdirectory (lab.topology_file contains a '/'), write the
    # session copy INTO that same subdirectory so containerlab still resolves
    # the lab's `assets/` (e.g. switch startup-configs) relative to the copy.
    # Flatten the filename so we never depend on a nested temp dir existing.
    clean_path = LABS_DIR / Path(lab.topology_file).parent / (
        f"._clean_{Path(lab.topology_file).name}_{session_id}.yml"
    )
    # FIX 2026-09-26 (Selina): lab-definitions/ is root-owned in places, so the
    # service user (student) cannot write the temp copy there -> EACCES -> all
    # sessions for that lab 500. Fail with a CLEAR error instead of crashing the
    # request path, and try to create/repair the dir first.
    try:
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        with open(clean_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
    except PermissionError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"cannot write session topology copy to {clean_path.parent}: {exc}. "
                "The lab-definitions directory must be writable by the service user "
                f"(uid={os.getuid()}). Fix: chown/chmod that lab directory."
            ),
        )

    return clean_path, unique_name


def _remove_clean_copy(topology_file: str, session_id: str):
    """Remove the session-specific cleaned temp YAML."""
    clean_path = LABS_DIR / Path(topology_file).parent / (
        f"._clean_{Path(topology_file).name}_{session_id}.yml"
    )
    if clean_path.exists():
        clean_path.unlink()


# --- Port Allocator ---

_PORT_ALLOC = {"next": TTYD_PORT_BASE}


def _allocate_port() -> int:
    """Allocate a ttyd port that is not currently in use.

    RUN 212 (2026-10-05): this was a pure rotating counter over 8765..9765 with a wrap. The docstring
    claimed "next available" but nothing checked availability, so once the counter came round -- after
    about 333 LAB-A sessions, sooner with LAB-B -- it could hand out a port a LIVE session's ttyd was
    still bound to. Measured across three start/stop cycles: 8776-8778, then 8779-8781, then 8782-8784,
    with nothing released back and no check that the next port was free.

    It now skips ports held by live sessions or tracked ttyd processes, and REFUSES loudly rather than
    looping forever if the range is exhausted. Two terminals on one socket is worse than an error.
    """
    in_use = set()
    for _s in SESSIONS.values():
        for _v in (_s.get("ttyd") or {}).values():
            if _v.get("port"):
                in_use.add(int(_v["port"]))
    in_use.update(int(k) for k in TTYD_PROCS.keys())
    span = TTYD_PORT_MAX - TTYD_PORT_BASE + 1
    for _ in range(span):
        port = _PORT_ALLOC["next"]
        _PORT_ALLOC["next"] += 1
        if _PORT_ALLOC["next"] > TTYD_PORT_MAX:
            _PORT_ALLOC["next"] = TTYD_PORT_BASE
        if port not in in_use:
            return port
    raise RuntimeError(
        f"no free ttyd port in {TTYD_PORT_BASE}-{TTYD_PORT_MAX}: every port in the range is in use"
    )


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

    # RUN 230 (2026-10-06): the digest is PINNED at start and was never re-checked, so a grade could cite
    # an identity the session no longer has. Measured live: replacing r1 with an alpine container under
    # the same name left a sibling's grade citing the original substrate digest (sha256:bb7ef23a...) while
    # the session's composition had changed. The Step-5 invariant says a state cannot be cited without its
    # digest; this makes the citation TRUE OF WHAT WAS EXAMINED rather than true of what once was.
    _live_digest = resolve_runtime_digest(session.get("nodes") or {})
    if not _live_digest or _live_digest != digest:
        return _refused_result_with(
            "The substrate under this session does not match the one it was pinned to (expected %s, "
            "found %s), so a grade cannot be cited against it. This is a system fault, not something "
            "about your configuration." % (digest[:24], (_live_digest or "(unreadable)")[:24])
        )

    # RUN 174 (decision #7): a grade is a VERDICT only if the node could be examined.
    # Reproduced live 2026-10-04 -- a submit racing a stop returned
    # `passed=false, "no output from sr_cli"`, i.e. the student was told their config was
    # wrong when the truth was that the container had already been torn down and NOBODY
    # LOOKED. The same shape appears on a restart mid-grade. Refuse instead.
    # A node this lab does not have is a different thing from a node that is down (run 201).
    # Asking LAB-A about "r1" used to answer "Node 'r1' is not running ... restart the lab", which is
    # advice that can never work: LAB-A has no r1. Say what is true instead.
    if node not in (session.get("nodes") or {}):
        return _refused_result_with(
            "This lab has no node '%s' — nothing to grade. The nodes here are: %s."
            % (node, ", ".join(sorted((session.get("nodes") or {}).keys())))
        )

    container = (session.get("nodes") or {}).get(node)
    if not _container_running(container):
        return _refused_result_with(
            "Node '%s' is not running, so it could not be examined — this is not a verdict "
            "about your configuration. It usually means the lab was stopped, or the service "
            "restarted, while this request was in flight. Restarting a single container does NOT "
            "rebuild containerlab's links, so restart the lab (End Lab, then Start Lab) and "
            "reconfigure."
            % node
        )

    grader = _load_grader(lab.grader_module)
    if not grader:
        # Fallback: basic IP/ping check (already digest-guarded).
        return _fallback_grade(session, node)

    try:
        result = grader.grade(session, node)
        # RUN 174 (decision #7, the half I missed on the first attempt): checking the
        # container BEFORE grading is not enough — a teardown lands DURING a grade, so the
        # check passed and the grader then reported "no output from sr_cli" as a FAIL. When
        # the grader says FAIL, ask whether the node was still there when it finished. If it
        # was gone, that is absence of evidence, not evidence of a wrong configuration.
        if (isinstance(result, dict) and result.get("passed") is False
                and not _node_examinable(container)):
            return _refused_result_with(
                "Node '%s' stopped while it was being graded, so the result could not be "
                "trusted — this is not a verdict about your configuration. It usually means "
                "the lab was stopped, or the service restarted, mid-grade. Restart the lab "
                "(End Lab, then Start Lab) and reconfigure." % node
            )
        if isinstance(result, dict):
            # "submitted" must mean the LAB passed, not that ONE node did.
            # DEFECT FIXED 2026-09-27: this used to set status="submitted" the
            # moment any single node passed. Grading only sw1 (which ships
            # pre-configured) marked a session submitted while pc-a was still
            # 0.0 and the lab had NOT passed. Consult the grader's own lab-level
            # verdict (grade_all) instead of a per-node boolean. Falls back to
            # the per-node result if a grader has no grade_all, so this never
            # becomes a new failure mode.
            _verdict = _lab_verdict_passed(grader, session)
            if _verdict is None:
                # RUN 225: the lab-level result could not be computed. The node result above is real and
                # is returned untouched, but leaving a student with "every node green and the lab never
                # finishes", and no reason, is not honest. Say it on the result, and say whose fault it
                # is not.
                result = dict(result)
                result["feedback"] = list(result.get("feedback") or []) + [
                    "\u26a0\ufe0f The lab-level result could not be computed (%s). Your result above "
                    "stands. This is a system fault, not something about your configuration."
                    % (_LAB_VERDICT_ERROR or "unknown reason")
                ]
                session["status"] = "running"
                # RUN 229: record WHEN the status was computed, and by which node's grade. Without it a
                # reader of "submitted" cannot tell whether that verdict is seconds or hours old -- the
                # record only carried created_at (the session's birth), never the verdict's time.
                session["status_updated_at"] = time.time()
                session["last_graded_node"] = node
            else:
                session["status"] = "submitted" if _verdict else "running"
                session["status_updated_at"] = time.time()
                session["last_graded_node"] = node
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
    """REFUSE when no grader module is available (was: a lenient pseudo-grade).

    WHY THIS CHANGED (2026-10-03): the old fallback returned
        passed = (non-loopback IP count > 0),  score = min(count * 0.3, 1.0)
    so a missing/unloadable grader module made an UNSOLVED node report passed=True
    (e.g. pc-a addressed but pinging nothing -> "✅ Passed! 60%"). The lab could not submit
    (the lab verdict is only computed on the real-grader path), but the NODE feedback claimed
    a pass the system had not verified -- the same class as the run-49 mask claim and the
    run-144 output-only switch check: a grader must not claim a value it did not verify.
    A lab with no grader cannot be graded, so say exactly that.
    """
    digest = _require_runtime_digest(session)
    return GraderResult(
        runtime_digest=digest,
        passed=False,
        score=0.0,
        feedback=[
            "No grader module for this lab — this lab cannot be graded. "
            "Nothing here is a verdict about your configuration."
        ],
        competencies=[],
        status="refused",
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
    rejected = _reload_labs()
    _GRADER_CACHE.clear()
    out = {"status": "reloaded", "count": len(LABS)}
    if rejected:
        # Surface WHICH definition was refused and why, instead of a bare 500 (run 222).
        out["status"] = "reloaded with skips"
        out["skipped"] = rejected
    return out


def _teardown_failed_start(lab, session_id: str, state: dict) -> None:
    """Best-effort cleanup for a start that failed AFTER deploy_lab.

    WHY: before 2026-10-01, start_lab had no failure path. If resolve_runtime_digest (or a ttyd
    start) raised after the deploy, the containers were created and then abandoned — running, with
    no session and nothing in the log. This tears the lab back down instead.

    NEVER raises: the original error must reach the client unchanged. Skips destroy_lab when the
    session IS registered (that is a live session, not a failed start).
    """
    try:
        for port in state.get("ttyd_ports", []) or []:
            proc = TTYD_PROCS.pop(port, None)
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
        if state.get("attempted") and session_id not in SESSIONS:
            try:
                destroy_lab(lab, session_id)
            except Exception:
                pass
    except Exception:
        pass


@app.post("/api/sessions/start")
def start_lab(lab_id: str, student_name: str = "Student", request: Request = None):
    lab = _get_lab(lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")

    session_id = str(uuid.uuid4())[:8]

    # Track what a FAILED start has already created so it cannot leak. (Found 2026-10-01: a
    # transient digest-resolution failure deployed 5 containers, raised, and abandoned them with
    # no session and no traceback. See findings/2026-10-01-failed-start-leaks-containers.md.)
    _start_state = {"attempted": False, "ttyd_ports": []}

    try:
        _start_state["attempted"] = True
        with _DEPLOY_LOCK:
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
            _start_state["ttyd_ports"].append(port)
            ttyd_info[node_name] = start_ttyd_process(
                port, containers[node_name]
            )

        # RUN 174 (decision #6): session registration takes the same lock as teardown, so a
        # stop cannot pop a session while it is being registered.
        with _DEPLOY_LOCK:
            SESSIONS[session_id] = {
                "lab_id": lab_id,
                "student_name": student_name,
                "status": "running",
                "created_at": time.time(),
                "nodes": containers,
                "ttyd_ports": ttyd_ports,
                # node -> {port, container, url, pid}. Kept so a page reload can offer
                # a student their running terminals back instead of only a Stop button
                # (2026-09-28). Before this, the map existed only in the start response
                # and was thrown away, so after a refresh the only in-app action on a
                # running lab was to kill it.
                "ttyd": ttyd_info,
                "runtime_digest": runtime_digest,
            }

        return {
            "session_id": session_id,
            "lab": lab,
            "nodes": containers,
            "ttyd": _rewrite_ttyd_urls(_ttyd_entries_live(ttyd_info), request),
            "runtime_digest": runtime_digest,
            "status": "running",
            "message": f"Lab '{lab.name}' is ready! Open the terminal below to start.",
        }
    except CapabilityRefusal as e:
        _teardown_failed_start(lab, session_id, _start_state)
        # A refusal, not a server fault: 409 with a reason the operator can act on.
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        _teardown_failed_start(lab, session_id, _start_state)
        # Without this a 500 was OPAQUE: the only reason lived in the HTTP body (2026-10-01).
        traceback.print_exc()
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
def list_sessions(request: Request = None):
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
            # node -> ttyd {url,...}. Included so a page reload can offer a student
            # their running terminals back rather than only a Stop button. The URL
            # host is rewritten to THIS request's Host header (run 50) so a
            # reconnect from a different address than the original start still
            # gets a terminal URL that resolves.
            "ttyd": _rewrite_ttyd_urls(
                _ttyd_entries_live(s.get("ttyd", {}) or {}), request
            ),
            "runtime_digest": s.get("runtime_digest", ""),
            # RUN 232: the LIST is what the UI panel renders. It published the pinned digest with no
            # indication of whether it still describes the session -- measured: after a node's substrate
            # was substituted, the panel still showed the old digest as plain fact beside a Reconnect
            # button, for a session whose grades now refuse. Same single-pass resolver as the record.
            "runtime_digest_live": _resolve_runtime_digest_once(s.get("nodes") or {}),
            "runtime_digest_matches": bool(s.get("runtime_digest"))
                                     and s.get("runtime_digest") == _resolve_runtime_digest_once(s.get("nodes") or {}),
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
        # RUN 229: a verdict is a claim about a moment. Say which moment.
        "status_updated_at": session.get("status_updated_at"),
        "last_graded_node": session.get("last_graded_node", ""),
        # RUN 231: the record cited a digest pinned at START with nothing to say whether it still
        # describes the running session. Measured: substituting pc-a's container left the record citing
        # aegis-less:0d40ee2f... while the session's live identity was aegis-less:fb852c02... -- the
        # record and the grades disagreed about the same session, and only the grades were honest.
        # A reader now gets both: what it was pinned to, what it is now, and whether they agree.
        "runtime_digest_live": _resolve_runtime_digest_once(session.get("nodes") or {}),
        "runtime_digest_matches": bool(session.get("runtime_digest"))
                                 and session.get("runtime_digest") == _resolve_runtime_digest_once(session.get("nodes") or {}),
    }


@app.post("/api/sessions/{session_id}/stop")
def stop_session(session_id: str):
    # RUN 174 (decision #6): teardown runs INSIDE the deploy lock. It frees ttyd ports and destroys
    # containers, and `start` allocates ports inside the same lock -- unlocked, a start could allocate
    # a port this stop was about to release. Registration takes the same lock, so a stop can no longer
    # interleave with a start.
    #
    # Deliberately NOT holding it across grading in submit_config: a grade takes tens of seconds, and
    # serialising learners behind each other's grades is a real cost for a race that is already handled
    # honestly (a container that vanishes mid-grade reports a real error -- run 159).
    #
    # RUN 209: this used to pop the session FIRST and wrap the teardown in `except Exception: pass`,
    # and to SKIP the teardown entirely when the lab definition was missing. Both produced the same
    # false success: HTTP 200 {"status": "destroyed"} while the containers kept running -- measured
    # live with 3 containers left behind, the session already gone, so nothing could touch them any
    # more. Now the lab is torn down FIRST, a failure is reported instead of swallowed, and the
    # session is removed only once the lab is really gone -- so a failed stop stays retryable.
    with _DEPLOY_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        lab = _get_lab(session["lab_id"])
        try:
            if lab:
                destroy_lab(lab, session_id)
            else:
                # No definition to work from, but the session knows its own containers: take them
                # down by name rather than skipping the teardown silently.
                _names = [n for n in (session.get("nodes") or {}).values() if n]
                if _names:
                    _r = subprocess.run(["docker", "rm", "-f"] + _names,
                                        capture_output=True, text=True, timeout=120)
                    if _r.returncode != 0:
                        raise RuntimeError("no lab definition, and the name-based teardown failed: "
                                           + (_r.stderr or "").strip()[:200])
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=("The lab could not be torn down: %s. The session is still listed and its "
                        "containers may still be running \u2014 press End Lab again." % e),
            )

        # The lab is gone: now take the session down and release its terminals.
        SESSIONS.pop(session_id, None)
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

    return {"status": "destroyed", "session_id": session_id}


# --- ttyd Management ---

# START 2026-09-29 (run 66): a session's stored ttyd map is a CLAIM -- "this
# terminal is running". If ttyd died (crash / OOM / killed), that claim is false
# and the advertised URL points at a dead port; live-caught on run 66 where a
# killed ttyd stayed in GET /api/sessions while :8851 refused everything. We only
# DROP an entry when we can POSITIVELY prove the process ended (port known AND
# poll() is not None, which also reaps the zombie). An unknown port is left
# alone, so a terminal we cannot judge is never hidden.
def _ttyd_entries_live(ttyd_map: dict) -> dict:
    if not ttyd_map:
        return ttyd_map or {}
    live = {}
    for node, info in ttyd_map.items():
        port = info.get("port") if isinstance(info, dict) else None
        proc = TTYD_PROCS.get(port) if port is not None else None
        if proc is not None and proc.poll() is not None:
            continue  # provably dead -> do not advertise
        live[node] = info
    return live

     # START 2026-09-28 (run 50): the terminal URL must match how the BROWSER
# reached this box. The old code advertised a single guessed LAN IP, so a
# browser that loaded the frontend at the box's OTHER address (or by hostname
# or over a tunnel) got a terminal URL on the wrong host and ttyd - bound to
# one interface - refused the connection. See _rewrite_ttyd_urls().
def _rewrite_ttyd_urls(ttyd_info: dict, request) -> dict:
    """Return ttyd_info with each url's HOST replaced by the request's Host header.

    Live-caught 2026-09-28 (run 50): the host has two LAN addresses
    (192.168.1.110 and 192.168.1.188). ttyd bound only on 192.168.1.110, and the
    API advertised http://192.168.1.110:<port> to every client. A student on
    .188 - or on localhost, or behind a tunnel - loaded the frontend fine but
    every terminal URL was refused. Follow the origin the browser actually used.
    The URL SHAPE (http://<host>:<port>) is unchanged; only the host is swapped.
    """
    if not ttyd_info:
        return ttyd_info
    try:
        netloc = (request.headers.get("host") if request else "") or ""
    except Exception:
        netloc = ""
    if not netloc:
        return ttyd_info  # no basis to rewrite; leave the derived URL alone
    req_host = netloc.split(":")[0]
    out = {}
    for node, info in ttyd_info.items():
        info = dict(info)
        port = info.get("port")
        if port:
            info["url"] = f"http://{req_host}:{port}"
        out[node] = info
    return out


def _detect_ttyd_host() -> str:
    """Pick the host IP the student's browser should use to reach ttyd.

    Derived, never hardcoded. Prefers a LAN (192.168.x.x) or routable 10.x
    address, skips Docker bridge IPs (172.x) and loopback. Returns "localhost"
    if nothing better is found.
    """
    host = "localhost"
    try:
        ip_output = subprocess.run(
            ["hostname", "-I"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().split()
        for candidate in ip_output:
            if candidate.startswith("192.168.") or candidate.startswith("10."):
                host = candidate
                break
        if host == "localhost":
            for candidate in ip_output:
                if not candidate.startswith("172.") and candidate != "127.0.0.1":
                    host = candidate
                    break
        if host == "localhost":
            host = ip_output[0] if ip_output else "localhost"
    except Exception:
        pass
    return host


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

    # Resolve the host ONCE, then both bind ttyd to it and advertise it, so the
    # bound interface and the URL never disagree. (Before 2026-09-28 ttyd bound
    # -i 0.0.0.0 on every interface while the URL advertised the LAN IP: the
    # student's lab shell was reachable from any host on the network, including
    # ones with no business touching it.)
    host = _detect_ttyd_host()
    # Bind on ALL interfaces the host actually has (0.0.0.0) so whichever
    # address the browser used can reach the terminal. The URL returned to the
    # client is no longer this guess - it is rewritten to the request's Host
    # header (see _rewrite_ttyd_urls), so a narrower bind here would only break
    # valid clients. Access control, if needed, belongs at the proxy/firewall.
    bind = "0.0.0.0"

    cmd = [
        "ttyd",
        "-p", str(port),
        "-W",
        "-i", bind,
        "-t", "fontSize=14",
        "-t", 'theme={"background":"#0f1117","foreground":"#e1e3eb"}',
        "docker", "exec", "-it", container, "sh",
    ]

    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    TTYD_PROCS[port] = proc

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
    """Serve a lab's markdown guide file if it exists (RUN 239: via the shared resolver)."""
    guide_path = _guide_path_for(lab_id)
    if guide_path:
        return PlainTextResponse(guide_path.read_text(), media_type="text/markdown")
    raise HTTPException(status_code=404, detail="No guide available for this lab")


# --- Serve Frontend ---

FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
    if not (FRONTEND_DIR / "index.html").is_file():
        # RUN 243 (2026-10-06): run 241 warned when the frontend DIRECTORY was missing -- measured, that is
        # not the same condition. With frontend/ present but index.html gone the service reports healthy in
        # every respect, "/" returns 404, and run 241's check passes because it only looked at the directory.
        # The directory existing is not the UI existing.
        print(f"[frontend] WARNING: {FRONTEND_DIR / 'index.html'} is missing -- the web UI is NOT served "
              f"and '/' will return 404. The API under /api is unaffected.", file=sys.stderr)
else:
    # RUN 241 (2026-10-06): this branch had no else. Measured: with frontend/ absent the service starts
    # normally, /api answers 200, and "/" returns a bare 404 with NOTHING anywhere naming the cause -- an
    # operator sees a healthy service and a dead entry point, and a student sees a 404 on the product's front
    # door. Warn by name, deliberately not refuse: the API is genuinely usable without the UI (integrators
    # call it directly), and taking a working API offline to fix a missing page would trade a real capability
    # for a cosmetic one.
    print(f"[frontend] WARNING: {FRONTEND_DIR} does not exist -- the web UI is NOT served and '/' will "
          f"return 404. The API under /api is unaffected.", file=sys.stderr)

if __name__ == "__main__":
    import uvicorn
    # Bind address/port are overridable (2026-10-04, run 190). They were hardcoded, which meant a
    # deployer whose 8000 is already in use could not move the product without editing the source --
    # and it made it impossible to run a second instance from an installed tree for testing.
    # Defaults are unchanged, so the systemd unit needs no edit.
    _host = os.environ.get("AEGIS_HOST", "0.0.0.0")
    _raw_port = os.environ.get("AEGIS_PORT", "8000")
    try:
        _port = int(_raw_port)
    except ValueError:
        # A wrong value must fail with a sentence, not a traceback (found 2026-10-04, run 191:
        # AEGIS_PORT=not-a-number produced a raw ValueError from int()). Same principle as the
        # grader refusals -- name the problem in words the reader can act on, and exit non-zero.
        raise SystemExit(
            f"[aegis] AEGIS_PORT must be a whole number, got {_raw_port!r}. "
            f"Unset AEGIS_PORT to use the default 8000."
        )
    if not (1 <= _port <= 65535):
        raise SystemExit(
            f"[aegis] AEGIS_PORT must be between 1 and 65535, got {_port}."
        )
    print(f"[aegis] serving on {_host}:{_port} (AEGIS_HOST/AEGIS_PORT overridable)")
    uvicorn.run(app, host=_host, port=_port)
