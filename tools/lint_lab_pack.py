#!/usr/bin/env python3
"""
AEGIS lab-pack lint — detect labs that ship PRE-SOLVED.

Why this exists (2026-09-22): the four demo labs all deployed and graded, but
a cold deploy of demo-02 graded 5/5 with ZERO student work — every value the
grader checks was baked into the topology `exec` blocks. A lab pack built from
those would ship the answer key. This lint catches that statically, before a
deploy, so "shipped solved" can't slip through unnoticed.

Method (static, no containers):
  1. For each lab YAML, find its grader module (metadata.grader).
  2. Import the grader and read its EXPECTED map (node -> {ip, dev}) plus any
     switch-IRB / router expectations the module exposes.
  3. Scan the lab's topology YAML for those IPs appearing in node `exec:` or
     `startup-config` files.
  4. Classify each lab.

Classification: a lab's PC/router addresses are the *student's* work. The
switch management IP is deliberately pre-seeded by design, so it is NOT counted
when deciding "solved".

  SOLVED  — every PC (and router, if any) address is pre-applied in the topology
  PARTIAL — some PC/router addresses pre-applied, some left to the student
  UNSOLVED— no PC/router addresses pre-applied (the student does the work)

Usage:  python3 tools/lint_lab_pack.py [--json]
Exit code 1 if any lab is SOLVED (a lab-pack red flag), else 0.
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LABS_DIR = BASE / "lab-definitions"


def load_grader(module_name: str):
    path = LABS_DIR / f"{module_name}.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"_lint_{module_name}", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # pragma: no cover - defensive
        print(f"  ! could not import {module_name}: {e}", file=sys.stderr)
        return None
    return mod


def parse_metadata(yml_path: Path) -> dict:
    """Read just the `metadata:` block (no yaml dep assumed)."""
    text = yml_path.read_text()
    m = re.search(r"^metadata:\n((?:[ \t].*\n|\n)*)", text, re.M)
    if not m:
        return {}
    block = m.group(1)
    meta = {}
    for line in block.split("\n"):
        km = re.match(r"\s*([a-z_]+):\s*(.*)$", line)
        if km:
            meta[km.group(1)] = km.group(2).strip()
    return meta


def switch_ips_from_grader(mod) -> dict:
    """Collect switch-IRB expectations a grader may expose."""
    out = {}
    for attr in ("IRB_EXPECTED", "SWITCH_EXPECTED", "SW_EXPECTED"):
        v = getattr(mod, attr, None)
        if isinstance(v, dict):
            out.update({k: vv for k, vv in v.items()})
    return out


def student_values(mod) -> dict:
    """node -> list of IPs the STUDENT is expected to apply.

    PCs come from EXPECTED. A router's addresses (if the grader exposes a
    ROUTER_EXPECTED map of node -> [(dev, ip), ...]) are also student work.
    Switch IRBs are deliberately seeded and excluded.
    """
    vals = {}
    exp = getattr(mod, "EXPECTED", {}) or {}
    for node, spec in exp.items():
        if isinstance(spec, dict) and spec.get("ip"):
            # 'switch' node in the plains lab is the switch mgmt IP: it IS
            # student work there (no separate switch grader map). Keep it.
            vals.setdefault(node, []).append(spec["ip"])
    rt = getattr(mod, "ROUTER_EXPECTED", {}) or {}
    for node, pairs in rt.items():
        for _dev, ip in pairs:
            vals.setdefault(node, []).append(ip)
    return vals


def _ipv4(s: str) -> bool:
    parts = s.split(".")
    if len(parts) != 4:
        return False
    return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def ast_student_values(mod) -> dict:
    """AST fallback for graders that expose no EXPECTED map.

    Legacy tier/lab graders build their expectations inline, e.g.
        ips = {"pc-a": "10.0.1.1", "pc-b": "10.0.1.2"}
    Walk the module AST for dict literals mapping a STRING key that looks like
    a node name to a STRING value that parses as IPv4. This is deliberately
    conservative -- only literal string->IPv4 pairs, only keys that look like
    node names -- so networks/masks/localhost are not mistaken for student IPs
    (a regex sweep over raw source over-matched exactly those; that is why
    this is AST-based). Returns node -> [ip, ...], same shape as
    student_values().
    """
    import ast, inspect
    try:
        src = inspect.getsource(mod)
        tree = ast.parse(src)
    except Exception:
        return {}
    nodeish = re.compile(r"^(pc|sw|switch|host|r[0-9]|router|node)[-\w]*$")
    vals: dict[str, list] = {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            if not nodeish.match(k.value.lower()):
                continue
            if isinstance(v, ast.Constant) and isinstance(v.value, str) and _ipv4(v.value):
                vals.setdefault(k.value, [])
                if v.value not in vals[k.value]:
                    vals[k.value].append(v.value)
    return vals


def preapplied_in_topology(yml_path: Path, ips: list) -> set:
    """Which of `ips` appear in the topology's *executable* config text.

    Only real config counts: node `exec:` commands and referenced
    `startup-config` files. The `instructions:` list and header comments quote
    the same commands but do not apply them, and scanning those produced false
    SOLVED verdicts for labs that actually fail cold (verified by running them:
    plains demo-01 and demo-02-unsolved both FAIL with zero student config, yet
    an earlier version of this lint flagged them SOLVED).
    """
    import yaml
    doc = yaml.safe_load(yml_path.read_text()) or {}
    topo = doc.get("topology") or {}
    chunks = []
    for node, spec in (topo.get("nodes") or {}).items():
        if not isinstance(spec, dict):
            continue
        for cmd in (spec.get("exec") or []):
            chunks.append(str(cmd))
        sc = spec.get("startup-config")
        if sc:
            scp = (yml_path.parent / sc)
            if scp.exists():
                chunks.append(scp.read_text())
    blob = "\n".join(chunks)
    found = set()
    for ip in ips:
        if re.search(re.escape(ip) + r"/", blob):
            found.add(ip)
    return found


REAL_SWITCH_KINDS = {"nokia_srlinux", "srlinux", "cumulus_cx", "cumulus"}
# A `kind: linux` node is still a REAL switch when it runs a real switch OS
# image. networkop/cx ships the Cumulus Linux userland (verified: os-release
# NAME="Cumulus Linux" VERSION_ID=4.3.0, /usr/bin/vtysh present), so the image,
# not the kind, is what makes it authentic. Without this the lint would
# false-positive the Cumulus demo -- the exact cry-wolf failure rejected before.
REAL_SWITCH_IMAGE_MARKERS = ("cumulus", "networkop/cx", "/cx", "srlinux")


def switch_authenticity(yml_path: Path) -> dict:
    """Flag labs that model a switch as a Linux PC.

    Dad's rule (2026-09-21): the switch must be a REAL switch, not a Linux PC
    running a bridge. A node whose name looks like a switch but whose kind is
    `linux` (and whose image is NOT a real switch OS) is the fake-switch
    pattern. This is independent of the SOLVED check and applies to EVERY lab,
    including legacy ones that expose no EXPECTED map.
    """
    import yaml
    doc = yaml.safe_load(yml_path.read_text()) or {}
    nodes = (doc.get("topology") or {}).get("nodes") or {}
    fake = []
    real = []
    for name, spec in nodes.items():
        if not isinstance(spec, dict):
            continue
        n = name.lower()
        if not (n.startswith("sw") or "switch" in n):
            continue
        kind = str(spec.get("kind", "")).lower()
        image = str(spec.get("image", "")).lower()
        real_image = any(m in image for m in REAL_SWITCH_IMAGE_MARKERS)
        if kind in REAL_SWITCH_KINDS or real_image:
            real.append(name)
        else:
            fake.append(f"{name}({kind or 'linux'}:{image or 'no-image'})")
    return {"fake_switches": fake, "real_switches": real}


def classify(lab_dir: Path, yml_path: Path) -> dict:
    meta = parse_metadata(yml_path)
    grader_name = meta.get("grader") or f"grader_{meta.get('id','')}"
    mod = load_grader(grader_name)
    result = {
        "lab": meta.get("id", yml_path.stem),
        "topology": str(yml_path.relative_to(BASE)),
        "switch_auth": switch_authenticity(yml_path),
        "grader": grader_name,
        "status": "UNKNOWN",
        "student_nodes": {},
    }
    if mod is None:
        result["status"] = "NO-GRADER"
        return result

    sv = student_values(mod)
    source = "EXPECTED"
    if not sv:
        sv = ast_student_values(mod)
        source = "AST"
    if not sv:
        result["status"] = "NO-EXPECTED"
        return result
    result["expect_source"] = source

    total, seeded = 0, 0
    for node, ips in sv.items():
        got = preapplied_in_topology(yml_path, ips)
        total += len(ips)
        seeded += len(got)
        result["student_nodes"][node] = {
            "expected": ips,
            "seeded_in_topology": sorted(got),
        }

    if seeded == 0:
        result["status"] = "UNSOLVED"
    elif seeded == total:
        result["status"] = "SOLVED"
    else:
        result["status"] = "PARTIAL"
    result["seeded_ratio"] = f"{seeded}/{total}"
    return result


def discover_labs() -> list:
    out = []
    cands = list(LABS_DIR.glob("*.yml"))
    for sub in sorted(p for p in LABS_DIR.iterdir() if p.is_dir()):
        cands.extend(sorted(sub.glob("*.yml")))
    for yml in sorted(cands):
        # only real labs: a metadata block with an id
        meta = parse_metadata(yml)
        if meta.get("id"):
            out.append(yml)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = []
    for yml in discover_labs():
        try:
            results.append(classify(yml.parent, yml))
        except Exception as e:
            results.append({"lab": yml.stem, "status": "ERROR", "error": str(e)})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"{'STATUS':<9} {'SEEDED':<8} LAB")
        print("-" * 70)
        for r in results:
            if r["status"] in ("SOLVED", "PARTIAL", "UNSOLVED"):
                print(f"{r['status']:<9} {r.get('seeded_ratio',''):<8} {r['lab']}")
            else:
                print(f"{r['status']:<9} {'-':<8} {r['lab']}  ({r.get('error', r['status'])})")
        solved = [r for r in results if r["status"] == "SOLVED"]
        fake = [r for r in results if (r.get("switch_auth") or {}).get("fake_switches")]
        print("-" * 70)
        print(f"labs scanned: {len(results)}   SOLVED (red flag): {len(solved)}")
        if solved:
            print("RED FLAG — these labs grade with zero student work:")
            for r in solved:
                print(f"   {r['lab']}  (grader {r['grader']})")
        if fake:
            print(f"RED FLAG — these labs model a switch as a Linux PC ({len(fake)}):")
            for r in fake:
                print(f"   {r['lab']}  -> {', '.join(r['switch_auth']['fake_switches'])}")

    red = any(r["status"] == "SOLVED" for r in results) or any(
        (r.get("switch_auth") or {}).get("fake_switches") for r in results
    )
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
