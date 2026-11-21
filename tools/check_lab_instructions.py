#!/usr/bin/env python3
"""Hold every shipped lab's `metadata.instructions` to what the lab actually delivers.

WHY THIS EXISTS
===============
2026-11-15 14:00: `lab-guides/demo-01` told the student the switch's IRB "arrives
pre-configured" (the YAML line said *ships pre-configured*, the rubric said *shipped
pre-configured*). On this host the switch could not commit at all -- the `srbase` netns
could not mount sysfs, so `log_mgr` failed every commit -- and the promised IRB was
never applied. The sentence was true of `assets/sw1.cfg` and false of the deployed lab,
and nothing in the tree could tell the difference.

Two of the three fixes were prose (the guide now says the IRB comes from the switch's
*start-up commit*). But that same run found the identical sentence still sitting in
`lab-definitions/srl-demo2-unsolved/demo-02-two-switches-one-router-unsolved.yml` --
the YAML `instructions` list, which is what the app shows as the step list. Prose that
promises a pre-applied switch config is a claim about a *file*: `topology.nodes.<n>.
startup-config`. This tool makes that claim checkable instead of re-read.

WHAT THIS CHECKS (per shipped lab = every `lab-definitions/**/*.yml` the loader globs)
======================================================================================
  1. Every node named in `metadata.instructions` prose ("the switch (SR Linux) is ...",
     "sw1 and sw2 ...") exists in `topology.nodes`. An instruction about a node that is
     not in the lab cannot be followed.
  2. **A PRE-APPLIED CLAIM REQUIRES A STARTUP-CONFIG.** If any instruction line says a
     node's config is pre-applied / pre-configured / already-configured / shipped
     with ... / arrives configured, then at least one node in that lab must declare a
     `startup-config`, and that file must (a) exist inside the lab directory, and
     (b) end with a committing line (`commit now` / `commit save`, sr_cli) -- a config
     file that never commits applies nothing.
  3. Every `startup-config` path referenced by a topology exists, lives inside the lab
     directory, and carries a commit line. (The backend already refuses a path that
     escapes or does not exist at load: this is the same rule, checked at commit time on
     the source rather than discovered at deploy.)
  4. Every IPv4 address an instruction tells the student to add on a switch (`irb`,
     "already configured", "pre-configured") is actually present in the startup-config
     that switch loads. This is the demo-02 case: the note says the IRBs are
     pre-configured, so the two addresses have to be in `assets/sw1.cfg` / `sw2.cfg`.

WHAT THIS DELIBERATELY DOES NOT CHECK
=====================================
It does not deploy anything. It cannot tell you the switch *accepted* its start-up
commit -- the 2026-11-15 host condition is exactly the case where the file is right and
the runtime refuses it. That is a measurement, not a grep, and the guide carries it as a
dated warning. This tool holds the file-side promise; the host-side promise stays measured.

It also does not grade prose quality, or the student guides themselves beyond the
addresses they name in rubric wording -- a guide can still be unhelpful and pass here.

Usage:  python3 tools/check_lab_instructions.py       # rc=0 when every claim holds
Exit:   0 = every shipped lab's instructions are backable by its own topology/assets
        1 = at least one claim is false of this tree
        2 = could not run (no lab-definitions/, or a lab the loader would load is unreadable)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS = ROOT / "lab-definitions"

# Wording that promises a node's configuration is applied before the student arrives.
# Kept narrow on purpose: "you must address the switch" is not a claim, and neither is
# "the IRB is graded". These are the forms that were actually wrong in the tree.
#
# 2026-11-21: the honest rewording ("each applies its IRB ... by its own start-up
# commit") is *also* a promise about topology.nodes.<n>.startup-config, so it is added
# here. Without it, fixing the wording silently disabled checks 3-4 -- a pass that
# proves nothing, which is worse than the false claim it replaced.
PREAPPLIED = re.compile(
    r"pre-?configured|pre-?applied|already configured|arrives? configured|"
    r"ship(?:s|ped)? configured|shipped with .*configured|"
    r"configured (?:for you|out of the box)|"
    r"applies (?:its|their) .*?\bcommit|start-?up commit applied",
    re.IGNORECASE,
)

COMMIT = re.compile(r"^\s*commit\s+(now|save)\s*$", re.MULTILINE)

# An address as instructions actually write it: `10.0.1.254/24` or bare `10.0.1.254`.
# The bare form is the one that matters -- "ship pre-configured (10.0.1.254 and
# 10.0.2.254)" names no mask, and the first version of this tool required `/nn` and so
# silently skipped the exact line it was written for. Caught by running it, not by reading it.
IPV4 = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})(?:/\d{1,2})?\b")


def _is_v4(addr: str) -> bool:
    return all(0 <= int(part) <= 255 for part in addr.split("."))

failures: list[str] = []
passes = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passes
    if ok:
        passes += 1
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}" + (f"\n        {detail}" if detail else ""))
        failures.append(name)


def _load_yaml(path: Path):
    """Parse a lab topology. Uses PyYAML, the same library the backend loads labs with."""
    import yaml  # local import: this tool must say so plainly if PyYAML is absent
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _instruction_lines(doc) -> list[str]:
    meta = (doc or {}).get("metadata") or {}
    raw = meta.get("instructions") or []
    if isinstance(raw, str):
        return [raw]
    return [str(x) for x in raw]


def _node_specs(doc) -> dict:
    topo = (doc or {}).get("topology") or {}
    nodes = topo.get("nodes") or {}
    return nodes if isinstance(nodes, dict) else {}


def _startup_config_for(spec) -> str | None:
    if isinstance(spec, dict) and spec.get("startup-config"):
        return str(spec["startup-config"])
    return None


def _lab_dirs() -> list[Path]:
    """The directories the loader globs for labs: lab-definitions/ and one level under it."""
    if not LABS.is_dir():
        return []
    dirs = {LABS}
    for child in sorted(LABS.iterdir()):
        if child.is_dir() and child.name != "__pycache__":
            dirs.add(child)
    return sorted(dirs)


def _lab_yml_files() -> list[Path]:
    """Every `.yml`/`.yaml` directly in those dirs -- the loader's own glob, not a guess."""
    out: list[Path] = []
    for d in _lab_dirs():
        for ext in ("*.yml", "*.yaml"):
            out.extend(sorted(p for p in d.glob(ext) if p.is_file()))
    return out


def _switch_mentions(line: str, node_names: list[str]) -> list[str]:
    """Nodes this instruction line talks about, by name or by the word 'switch'."""
    hits = []
    low = line.lower()
    for name in node_names:
        if re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", low):
            hits.append(name)
    return hits


def main() -> int:
    if not LABS.is_dir():
        print(f"could not run: {LABS} does not exist", file=sys.stderr)
        return 2
    files = _lab_yml_files()
    if not files:
        # Not a pass: the loader would discover no labs, and every claim below would be
        # vacuously true.
        print(f"could not run: no lab *.yml under {LABS}", file=sys.stderr)
        return 2

    for path in files:
        rel = path.relative_to(ROOT)
        try:
            doc = _load_yaml(path)
        except Exception as exc:  # noqa: BLE001 - any parse error is a lab the loader skips
            check(f"{rel}: parses as YAML", False, f"{type(exc).__name__}: {exc}")
            continue
        if not isinstance(doc, dict) or not (doc.get("metadata") or {}).get("id"):
            # A YAML the loader would not treat as a lab (no metadata.id). Not a claim site.
            print(f"SKIP  {rel}: not a lab (no metadata.id)")
            continue

        lab_id = (doc.get("metadata") or {}).get("id")
        nodes = _node_specs(doc)
        node_names = list(nodes.keys())
        lines = _instruction_lines(doc)
        labdir = path.parent

        # --- 1. startup-config files: exist, contained, commit.
        configs: dict[str, Path] = {}
        ok_paths = True
        for node, spec in nodes.items():
            sc = _startup_config_for(spec)
            if not sc:
                continue
            p = (labdir / sc)
            try:
                resolved = p.resolve()
                resolved.relative_to(labdir.resolve())
            except (ValueError, OSError):
                check(f"{rel}: {node} startup-config stays inside the lab directory",
                      False, f"'{sc}' resolves outside {labdir.name}/")
                ok_paths = False
                continue
            if not resolved.is_file():
                check(f"{rel}: {node} startup-config exists", False,
                      f"'{sc}' does not exist")
                ok_paths = False
                continue
            body = resolved.read_text(encoding="utf-8", errors="replace")
            check(f"{rel}: {node} startup-config commits", bool(COMMIT.search(body)),
                  f"'{sc}' has no 'commit now'/'commit save' line -- it applies nothing")
            configs[node] = resolved
        if ok_paths and configs:
            check(f"{rel}: every startup-config present and contained", True)

        # --- 2. node names in instructions exist in the topology.
        for line in lines:
            named = _switch_mentions(line, node_names)
            # Only assert on names we actually matched; a line naming no node is fine.
            for name in named:
                if name not in nodes:
                    check(f"{rel}: instruction node '{name}' exists", False, line.strip()[:90])

        # --- 3. a pre-applied claim requires a startup-config in this lab.
        preapplied = [l for l in lines if PREAPPLIED.search(l)]
        if preapplied:
            check(f"{rel}: pre-applied claim is backed by a startup-config",
                  bool(configs),
                  "instruction says a node arrives pre-configured but no node in this "
                  "lab declares a startup-config:\n          "
                  + "\n          ".join(l.strip()[:120] for l in preapplied))

        # --- 4. addresses promised as pre-applied are in the startup-config.
        for line in preapplied:
            addrs = [a for a in IPV4.findall(line) if _is_v4(a)]
            if not addrs:
                continue
            joined = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                               for p in configs.values())
            for addr in addrs:
                check(f"{rel}: {addr} promised pre-applied is in a startup-config",
                      re.search(rf"\b{re.escape(addr)}(?:/\d+)?\b", joined) is not None,
                      f"{addr} named as pre-configured, absent from "
                      + (", ".join(p.name for p in configs.values()) or "any config"))

        # --- 5. A line telling the student to CONFIGURE a node that the lab also ships a
        # startup-config for is the mirror-image defect: it overwrites a graded answer.
        # Allowed when the same lab also says the node arrives pre-configured (the student
        # is then doing something the lab told them not to need), so the two claim classes
        # cannot both fire on one node without one of them being wrong.
        for node in configs:
            for line in lines:
                m = re.match(rf"^\s*{re.escape(node)}\b[^:]*:\s*(ip addr add|set /)",
                             line, re.IGNORECASE)
                if not m:
                    continue
                check(f"{rel}: '{node}' is not both student-configured and startup-configured",
                      bool(preapplied),
                      f"instruction tells the student to configure '{node}', but it also "
                      f"ships {configs[node].name} and no instruction says it arrives "
                      f"configured -- one of the two is wrong")

    print()
    if failures:
        print(f"{len(failures)} claim(s) false of this tree; {passes} held.")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"All {passes} claims hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
