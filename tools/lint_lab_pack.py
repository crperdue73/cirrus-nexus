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
     switch-IRB / router expectations the module exposes. (Router maps were
     read under one assumed attribute name until 2026-11-08, so Demo 2's
     router was never examined -- see student_values().)
  3. Scan the lab's topology YAML for those IPs appearing in node `exec:` or
     `startup-config` files.
  4. Classify each lab.

Classification: a lab's PC/router addresses are the *student's* work. The
switch management IP is deliberately pre-seeded by design, so it is NOT counted
when deciding "solved".

  SOLVED  — every PC (and router, if any) address is pre-applied in the topology
  PARTIAL — some PC/router addresses pre-applied, some left to the student
  UNSOLVED— no PC/router addresses pre-applied (the student does the work)

Non-verdicts (nothing was actually examined — never read these as a pass):
  NO-GRADER   — the lab names a grader module that does not exist. This is a
                property of the lab and still exits 0 (the run completed).
  NO-EXPECTED — grader exposes no EXPECTED/literal node->IP map to read. Also
                exits 0, but prints its own NOT CHECKED line. LIMIT, named on
                purpose: a pack made only of such labs reports
                `labs scanned: N, SOLVED: 0` rc=0 having read no expectation at
                all. Making it fatal would retroactively flag the two shipped
                demo labs' profile, so that call is Dad's, not a polish run's.
  ERROR       — the lab could not be classified at all (unparseable topology,
                or a grader that raised on import — fixed 2026-11-07, which
                used to print as NO-GRADER). The reason is printed. Exits 2.
  UNAVAILABLE — PyYAML is missing, so the topology could not be parsed at all

UNAVAILABLE is a hard stop, not a per-lab finding: it is checked once, up
front, and exits 2 with one message on stderr. Before 2026-10-21 the missing
import surfaced inside the per-lab loop instead, so a box without PyYAML got
one `ERROR` row per lab under a header called STATUS and never saw the
NOT CHECKED line below — a worker following the PR-template checklist could
read that as a completed run.

ERROR rows had the same hole and were left open (found 2026-11-07): a lab with
an unparseable topology classified as ERROR, printed under STATUS, and the run
still exited **0** — green, with no NOT CHECKED line, in a run where that lab
was never examined. Only SOLVED (exit 1) and UNAVAILABLE (exit 2) were
counted. Now any ERROR row also exits 2: the run did not complete. A lab
nobody could classify is not evidence that the pack is clean.

Usage:  python3 tools/lint_lab_pack.py [--json]
Exit code 1 if any lab is SOLVED or models a switch as a Linux PC (a lab-pack
red flag), 2 if the run could not complete (PyYAML missing, or any lab ERROR),
else 0. A red flag outranks an incomplete run: a tree with both exits 1.
NO-GRADER and NO-EXPECTED rows exist but do not by themselves make the run
incomplete — see the LIMIT note above. This is NOT a CI step; run it by hand.
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LABS_DIR = BASE / "lab-definitions"


def _require_yaml() -> bool:
    """Fail once, loudly, if PyYAML is absent — before any lab is classified.

    The topology parse is the whole method, so without yaml there is no partial
    result worth printing. Checked up front so the message names the real
    problem instead of surfacing as a per-lab ERROR row.
    """
    try:
        import yaml  # noqa: F401
    except ImportError:
        print(
            "UNAVAILABLE: PyYAML is not installed, so no lab was examined "
            "(this is not a pass).\n"
            "Install it, then re-run:\n"
            "    python3 -m pip install pyyaml\n"
            "(pyyaml is already declared in requirements.txt.)",
            file=sys.stderr,
        )
        return False
    return True


def load_grader(module_name: str, problems: dict | None = None,
                lab_dir: Path | None = None, grader_search: list | None = None):
    """Import a lab's grader module, or None if it is missing / will not import.

    `problems` (optional) records WHICH of the two happened. Since 2026-11-07
    that distinction matters: a grader file that exists but raises on import is
    a lab nobody could examine (`ERROR`, exit 2), while a grader file that is
    simply absent is a property of that lab (`NO-GRADER`, exit 0). Before this,
    both collapsed into NO-GRADER, so a broken grader was reported as a missing
    one and the run exited 0 — measured with a canary whose module raised
    ZeroDivisionError at import: `NO-GRADER - canary-raise`, rc=0, with the only
    trace on stderr. The docstring above already listed "a grader that raised on
    import" as an ERROR case; it was not true of the code.
    """
    # The grader may sit next to its lab YAML OR at lab-definitions/ root: that is
    # where both shipped graders live, and a sub-directory lab names them by bare
    # module name. Searching the lab's own directory alone is why every lab in
    # this tree read NO-GRADER on 2026-11-08 (measured: 2/2 labs NO-GRADER,
    # rc 0) -- the lint reported that it had examined no expectation at all.
    candidates = [((lab_dir or LABS_DIR) / f"{module_name}.py")]
    if lab_dir is not None and Path(lab_dir).resolve() != LABS_DIR.resolve():
        candidates.append(LABS_DIR / f"{module_name}.py")
    for extra in (grader_search or []):
        candidates.append(Path(extra) / f"{module_name}.py")
    path = next((c for c in candidates if c.exists()), candidates[0])
    if not path.exists():
        if problems is not None:
            problems["missing"] = True
        return None
    spec = importlib.util.spec_from_file_location(f"_lint_{module_name}", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # pragma: no cover - defensive
        if problems is not None:
            problems["raised"] = f"{type(e).__name__}: {e}"
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


# Node->[(dev, ip), ...] maps a grader may expose for a ROUTER's interfaces.
# Demo 2 uses ROUTERS; the plural ROUTER_EXPECTED is kept first only as an alias
# because this function used to look for that name alone (see the note below).
ROUTER_MAPS = ("ROUTER_EXPECTED", "ROUTERS", "ROUTER", "ROUTER_IPS")


def student_values(mod) -> dict:
    """node -> list of IPs the STUDENT is expected to apply.

    PCs come from EXPECTED. A router's addresses (from any map in ROUTER_MAPS,
    in the node -> [(dev, ip), ...] shape Demo 2 actually uses) are also student
    work. Switch IRBs are deliberately seeded and excluded.
    """
    vals = {}
    exp = getattr(mod, "EXPECTED", {}) or {}
    for node, spec in exp.items():
        if isinstance(spec, dict) and spec.get("ip"):
            # 'switch' node in the plains lab is the switch mgmt IP: it IS
            # student work there (no separate switch grader map). Keep it.
            vals.setdefault(node, []).append(spec["ip"])
    # Router expectations are read from EVERY map a shipped grader actually uses,
    # because no shipped grader calls it ROUTER_EXPECTED. Found 2026-11-08 by
    # measuring a canary that copies Demo 2's real shape (`ROUTERS = {"r1":
    # [(dev, ip), ...]}`): the lint reported PARTIAL 1/4 for a lab whose router
    # link had 10.0.1.253 pre-applied in node `exec:`, and PARTIAL 2/4 for one
    # that pre-applied BOTH addresses -- i.e. a lab whose entire answer key was
    # baked in read as a partial, never as SOLVED, and the run stayed rc 0. The
    # attr name this code looked for appears in no grader in this tree; it was
    # an assumption about a convention, not a measurement of the code.
    # Demo 2 exposes ROUTERS (node -> [(dev, ip), ...]); IRB/mgmt maps are
    # deliberately NOT read here, since a switch's management IP ships seeded
    # by design and counting it would manufacture false red flags.
    for attr in ROUTER_MAPS:
        rt = getattr(mod, attr, {}) or {}
        if not isinstance(rt, dict):
            continue
        for node, pairs in rt.items():
            for item in pairs if isinstance(pairs, (list, tuple)) else []:
                # ("eth1", "10.0.1.253") or, tolerantly, a bare address string.
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    ip = item[1]
                elif isinstance(item, str):
                    ip = item
                else:
                    continue
                if isinstance(ip, str) and _ipv4(ip) and ip not in vals.get(node, []):
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


def _rel_or_abs(path: Path) -> Path:
    """`path` relative to BASE when it is inside the tree, else as given."""
    try:
        return path.resolve().relative_to(BASE)
    except ValueError:
        return path


def classify(lab_dir: Path, yml_path: Path, grader_search: list | None = None) -> dict:
    meta = parse_metadata(yml_path)
    grader_name = meta.get("grader") or f"grader_{meta.get('id','')}"
    problems: dict = {}
    mod = load_grader(grader_name, problems, lab_dir, grader_search)
    result = {
        "lab": meta.get("id", yml_path.stem),
        # A lab outside this tree (a canary in /tmp) has no path relative to
        # BASE; reporting its absolute path is the truthful label, and printing
        # it beats raising before the lab is classified at all (2026-11-08).
        "topology": str(_rel_or_abs(yml_path)),
        "switch_auth": switch_authenticity(yml_path),
        "grader": grader_name,
        "status": "UNKNOWN",
        "student_nodes": {},
    }
    if mod is None:
        if "raised" in problems:
            # The module is there and broken: a lab this run could not
            # examine, i.e. ERROR (exit 2), not a lab without a grader.
            result["status"] = "ERROR"
            result["error"] = f"grader {grader_name} raised on import: {problems['raised']}"
        else:
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


def discover_labs(labs_dir: Path | None = None) -> list:
    """Lab YAMLs to examine. `labs_dir` defaults to this tree's lab-definitions.

    The argument exists so the lint can be measured against canary labs in /tmp
    without a copy of the whole tool -- and so a caller cannot silently measure
    a different directory: LABS_DIR is only the default.
    """
    out = []
    root = labs_dir or LABS_DIR
    cands = list(root.glob("*.yml"))
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
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
    ap.add_argument("--labs-dir", type=Path, default=None,
                    help="lab-definitions directory to examine (default: this tree's)")
    args = ap.parse_args()

    if not _require_yaml():
        return 2

    lancet = args.labs_dir
    grader_search = None
    if lancet is not None:
        # Measuring a canary pack: its own directory is searched for graders
        # FIRST, this tree's lab-definitions second, so a canary can supply a
        # deliberately broken module without shadowing the shipped ones.
        grader_search = [str(lancet), str(LABS_DIR)]

    results = []
    for yml in discover_labs(lancet):
        try:
            results.append(classify(yml.parent, yml, grader_search))
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
                why = r.get("error") or r["status"]
                print(f"{r['status']:<9} {'-':<8} {r['lab']}  ({why})")
        solved = [r for r in results if r["status"] == "SOLVED"]
        fake = [r for r in results if (r.get("switch_auth") or {}).get("fake_switches")]
        unchecked = [r for r in results if r["status"] == "NO-EXPECTED"]
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
        errored = [r for r in results if r["status"] == "ERROR"]
        if errored:
            # Added 2026-11-07. These ran under STATUS like a verdict and the
            # run exited 0 anyway; measured on a canary with a truncated
            # topology YAML: one ERROR row, rc=0, no line saying anything was
            # skipped. Exit 2 now, but also say it out loud here.
            print(f"NOT CHECKED — {len(errored)} lab(s) could not be classified at all"
                  " (see the ERROR rows above; this is not a pass):")
            for r in errored:
                print(f"   {r['lab']}")
        if unchecked:
            # Honesty line: NO-EXPECTED means the pre-solved check could not
            # read this grader's expectations (they are not a literal
            # node->IP map). That is NOT a clean bill — do not let silence
            # read as a pass. A call-arg AST extractor was attempted and
            # reverted: it cross-attributed IPs between node branches and
            # counted neteng's subnet masks, i.e. it manufactured false
            # verdicts. "Not checked" is the truthful status until a grader
            # exposes a real EXPECTED map.
            print(f"NOT CHECKED — pre-solved status UNKNOWN for {len(unchecked)} lab(s)"
                  " (grader exposes no EXPECTED map; this is not a pass):")
            for r in unchecked:
                print(f"   {r['lab']}  (grader {r['grader']})")

    # A lab this run could NOT examine is an incomplete run, not a verdict about
    # anything -- so it outranks the red flag. Measured 2026-11-08 on the canary
    # pack: a SOLVED canary beside a grader that raises at import exited 1, which
    # reads as "I found the answer key" while the ERROR row (the one thing that
    # says part of the run never happened) was the lower-priority signal. Order
    # now: ERROR (2) > red flag (1) > clean (0).
    if any(r["status"] == "ERROR" for r in results):
        return 2
    red = any(r["status"] == "SOLVED" for r in results) or any(
        (r.get("switch_auth") or {}).get("fake_switches") for r in results
    )
    if red:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
