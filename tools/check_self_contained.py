#!/usr/bin/env python3
"""Self-contained check: can this repo be installed from a bare clone?

Run from the repo root (or anywhere — it resolves the root from its own path).
Exits non-zero and prints every problem found, so CI and a human see the same list.

This is the guard for the rule: **a clone of this repo on a clean host must contain
everything the product needs.** If something is missing here, an install from GitHub
will fail — so this runs in CI on every push.
"""
from __future__ import annotations

import py_compile
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files/dirs the installer and the running product require.
REQUIRED = [
    "install.sh",
    "start_server.py",
    "Dockerfile.frr",
    "README.md",
    "LICENSE",
    "backend/main.py",
    "frontend/index.html",
    "assets/frr-image.pin",
    "lab-definitions/grader_demo_01_srl.py",
    "lab-definitions/grader_demo_02.py",
    "lab-definitions/srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.yml",
    "lab-definitions/srl-demo-unsolved/assets/sw1.cfg",
    "lab-definitions/srl-demo2-unsolved/demo-02-two-switches-one-router-unsolved.yml",
    "lab-definitions/srl-demo2-unsolved/assets/sw1.cfg",
    "lab-definitions/srl-demo2-unsolved/assets/sw2.cfg",
]

# A developer's absolute path must never ship. (These records legitimately mention
# historic paths and are excluded by design.)
PATH_ALLOWLIST = (
    ".nexus/",           # engineering audit trail (records historic paths on purpose)
    "docs/SELF-CONTAINED.md",
    "tools/check_self_contained.py",
)
PATH_PATTERN = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/.openclaw")
TEXT_EXT = {".py", ".sh", ".yml", ".yaml", ".md", ".html", ".json", ".cfg", ".txt"}


def main() -> int:
    problems: list[str] = []

    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            problems.append(f"missing required file: {rel}")

    # Every lab YAML's startup-config must exist beside it, and its grader must exist.
    for yml in (ROOT / "lab-definitions").rglob("*.yml"):
        text = yml.read_text(errors="replace")
        for ref in re.findall(r"startup-config:\s*(\S+)", text):
            if not (yml.parent / ref).exists():
                problems.append(f"{yml.relative_to(ROOT)}: startup-config missing -> {ref}")
        m = re.search(r"^\s*grader:\s*(\S+)", text, re.M)
        if m:
            name = m.group(1)
            cands = [ROOT / "lab-definitions" / f"{name}.py",
                     ROOT / "backend" / "graders" / f"{name}.py"]
            if not any(c.exists() for c in cands):
                problems.append(f"{yml.relative_to(ROOT)}: grader module missing -> {name}.py")

    # Every shipped grader must byte-compile. backend/main.py is compiled by its own CI
    # step, but a syntax error in a lab grader would otherwise pass CI silently.
    for gr in sorted((ROOT / "lab-definitions").glob("grader_*.py")):
        try:
            with tempfile.NamedTemporaryFile(suffix=".pyc", delete=True) as tmp:
                py_compile.compile(str(gr), cfile=tmp.name, doraise=True)
        except py_compile.PyCompileError as exc:
            problems.append(f"{gr.relative_to(ROOT)}: does not compile -> {exc.msg.splitlines()[0]}")

    # No shipped source may reference a developer's absolute path.
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_EXT:
            continue
        rel = str(path.relative_to(ROOT))
        if any(rel.startswith(a) or rel == a for a in PATH_ALLOWLIST):
            continue
        if ".git/" in rel:
            continue
        if PATH_PATTERN.search(path.read_text(errors="replace")):
            problems.append(f"{rel}: contains an absolute developer path")

    if problems:
        print("repo is NOT self-contained:\n  " + "\n  ".join(problems))
        return 1
    print(f"self-contained OK: {len(REQUIRED)} required files present, "
          f"lab assets + graders resolve, no developer paths leak.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
