#!/usr/bin/env python3
"""Check docs/OPERATIONS.md against the tree it describes.

Every claim in OPERATIONS.md is supposed to be measurable. This script measures
the ones that can be measured by reading files, and prints PASS/FAIL per claim.
It is deliberately dumb and explicit: each check names the file and the token it
looks for, so a FAIL tells you where to look.

Exit 0 = all claims hold. Exit 1 = at least one claim is false of this tree.

Why this exists: OPERATIONS.md is the doc operators trust when something is on
fire, and it has been wrong before in ways that mattered (see the 2026-10-30
exit-1 note in the start_server section). A doc that says "everything here was
measured" needs a thing that re-measures it.

Run from the repo root:  python3 tools/check_operations_doc.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPS = ROOT / "docs" / "OPERATIONS.md"

failures: list[str] = []
passes = 0


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def check(name: str, ok: bool, detail: str = "") -> None:
    global passes
    if ok:
        passes += 1
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}" + (f"\n        {detail}" if detail else ""))
        failures.append(name)


def main() -> int:
    if not OPS.exists():
        print(f"FAIL  docs/OPERATIONS.md missing at {OPS}")
        return 1
    ops = OPS.read_text(encoding="utf-8", errors="replace")

    # ---- Section: running the server (systemd unit) -------------------------
    install = read("install.sh")
    check("unit is aegis.service", "aegis.service" in install)
    check("User=aegis in the unit", "User=aegis" in install)
    check("WorkingDirectory=/opt/aegis", "WorkingDirectory=/opt/aegis" in install)
    check(
        "ExecStart matches the doc (python3 /opt/aegis/backend/main.py)",
        re.search(r"ExecStart=\S*python3 /opt/aegis/backend/main\.py", install) is not None,
        "the doc prints ExecStart=python3 /opt/aegis/backend/main.py; the unit must agree on the path",
    )
    check("journald + append:/var/log/aegis.log both true", "append:/var/log/aegis.log" in install)

    # ---- start_server.py behaviour -----------------------------------------
    ss = read("start_server.py")
    check("start_server kills ttyd leftovers", "pkill" in ss and "ttyd" in ss)
    check("start_server honours AEGIS_HOST", "AEGIS_HOST" in ss)
    check("start_server honours AEGIS_PORT", "AEGIS_PORT" in ss)
    check("start_server waits 15s for /api", re.search(r"range\(15\)", ss) is not None)
    check("start_server logs to /tmp/aegis-server.log", "/tmp/aegis-server.log" in ss)
    check("start_server fails fast on child exit", "exited with status" in ss)

    # ---- Step 7c pre-pull --------------------------------------------------
    check("install.sh Step 7c pre-pulls srlinux + alpine",
          "Step 7c" in install and "ghcr.io/nokia/srlinux:latest" in install and "alpine:latest" in install)

    # ---- Node substrates table ---------------------------------------------
    d1 = read("lab-definitions/srl-demo-unsolved/demo-01-two-pcs-and-a-real-switch-unsolved.yml")
    d2 = read("lab-definitions/srl-demo2-unsolved/demo-02-two-switches-one-router-unsolved.yml")
    check("demo-01 uses alpine PCs", "image: alpine:latest" in d1)
    check("demo-01 has no aegis/frr node", "aegis/frr" not in d1)
    check("demo-02 uses aegis/frr router", "image: aegis/frr:latest" in d2)
    check("doc's 'none ships as a tarball' holds",
          not list(ROOT.glob("*.tar.gz")) and not list((ROOT / "assets").glob("*.tar.gz")))

    # ---- Runtime digest schemes -------------------------------------------
    main_py = read("backend/main.py")
    check("code has the aegis-less: prefix", 'AEGIS_LESS_PREFIX = "aegis-less:"' in main_py)
    check("code returns \"\" as the refusal", 'return ""' in main_py)

    # ---- Stop semantics ----------------------------------------------------
    check("stop holds the deploy lock", "_DEPLOY_LOCK" in main_py)
    check("failed stop reports 'still listed'", "still listed" in main_py)
    check("404 is a lookup miss", "Session not found" in main_py)
    check("reconcile_sessions exists", "def reconcile_sessions" in main_py)
    check("session label is aegis.session.id", 'SESSION_LABEL = "aegis.session.id"' in main_py)

    reaper = read("scripts/clab-reaper.sh")
    check("reaper defaults to --orphans", "--orphans" in reaper)
    check("reaper exits 3 when it cannot ask", re.search(r"exit 3", reaper) is not None)
    check("reaper exits 4 on an unlabelled clab container", re.search(r"exit 4", reaper) is not None)

    # ---- Image pin ---------------------------------------------------------
    pin = read("assets/frr-image.pin")
    check("pin names the shipped Dockerfile hash", "dockerfile_sha256=b3046a70" in pin)
    check("pin marks image facts UNPINNED", "image_id=UNPINNED" in pin and "layers_sha256=UNPINNED" in pin)
    check("pin keeps the 2026-09-19 record", "cce15a86" in pin)
    dfr = read("Dockerfile.frr")
    actual = subprocess.run(["sha256sum", str(ROOT / "Dockerfile.frr")],
                            capture_output=True, text=True).stdout.split()[0]
    check("pin's dockerfile_sha256 matches the on-disk Dockerfile",
          pin.count(f"dockerfile_sha256={actual}") >= 1,
          f"on-disk sha256 is {actual}; the re-pin section names a different one")
    check("Dockerfile.frr asserts ospfd=no / bgpd=no at build time",
          "require ospfd no;" in dfr and "require bgpd no;" in dfr)
    check("installer treats UNPINNED as unusable",
          '"${dockerfile_sha256}" == "UNPINNED"' in install)
    check("installer stamps the Dockerfile fingerprint label",
          'aegis.frr.dockerfile.sha256' in install)
    check("pin's tarball field is empty (nothing ships)", re.search(r"^tarball=\s*$", pin, re.M) is not None)

    # ---- Capstone (Net Eng I PBM) -----------------------------------------
    # The doc states a 27 / 67 / 6 point split and says those numbers are read
    # directly from lab-guides/lab-03-lock-it-down.md. They must therefore
    # appear in that guide, summed from its own rubric table.
    guide = read("lab-guides/lab-03-lock-it-down.md")
    check("lab-03 guide says 'Auto-graded (100 pts)' or has a 100 pts rubric",
          "100 pts" in guide)
    check("lab-03 guide names 192.168.12.0/24", "192.168.12.0/24" in guide)
    check("lab-03 guide states the 70% pass mark", "70%" in guide)

    # Sum the guide's own rubric table.
    rubric = re.findall(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|", guide, re.M)
    pts = {name.strip(): int(v) for name, v in rubric}
    total = sum(pts.values())
    check("lab-03 rubric sums to 100", total == 100,
          f"rubric table sums to {total}: {pts}")

    group = {
        "Subnetting": "Subnetting",
        "Device Config": {"RTR SSH Config", "RTR Interface Config", "SW1 SVI",
                          "SW1 Port Security", "PC Config"},
        "Connectivity": "Connectivity",
    }
    for label, members in group.items():
        if isinstance(members, str):
            got = pts.get(members)
        else:
            got = sum(v for k, v in pts.items() if k in members) if all(m in pts for m in members) else None
        check(f"capstone '{label}' figure is derivable from the guide",
              got is not None,
              f"the guide has no rows for {sorted(members)} "
              f"(it has {sorted(pts)})" if got is None else "")
        if got is not None:
            # The doc must quote this number, not a number of its own.
            check(f"OPERATIONS quotes {label} = {got}",
                  re.search(rf"{label}[^.\n]*?\b{got}\b", ops) is not None,
                  f"the guide's own rows give {label} = {got}")

    # ---- Reload / cache section --------------------------------------------
    # These tie the doc's cache narrative to the code that implements it. Each
    # token below is a thing main.py must actually do, not a paraphrase. Added
    # 2026-11-08 after the doc claimed a restart always clears a stale grader
    # and the measured loader wrote/reused a .pyc that a restart does not clear;
    # the behavioural part (same-second + same-size -> stale) is reproduced by
    # tools/check_pyc_staleness.py, because reading files cannot prove it.
    main_py_src = read("backend/main.py")
    check("main.py keeps a module-level _GRADER_CACHE dict",
          re.search(r"^_GRADER_CACHE\s*(?::\s*dict)?\s*=\s*\{\}", main_py_src, re.M) is not None)
    check("main.py caches a loaded grader in _GRADER_CACHE",
          re.search(r"_GRADER_CACHE\[module_name\]\s*=\s*mod", main_py_src) is not None)
    check("main.py has a top-level LABS cache the doc promises",
          re.search(r"^LABS\b\s*(?::[^=]+)?=", main_py_src, re.M) is not None)
    reload_m = re.search(r"_GRADER_CACHE\.clear\(\)", main_py_src)
    check("main.py clears _GRADER_CACHE (the doc's 'cleared by reload')", reload_m is not None)
    check("main.py loads graders through importlib's loader (writes a .pyc)",
          "importlib.util.spec_from_file_location" in main_py_src)
    check("install.sh does NOT set PYTHONDONTWRITEBYTECODE (the .pyc is written by default)",
          "PYTHONDONTWRITEBYTECODE" not in install)
    check(".gitignore ignores __pycache__/ (none of it ships)",
          re.search(r"^__pycache__/", read(".gitignore"), re.M) is not None)
    check("OPERATIONS names both caches",
          "`LABS`" in ops and "`_GRADER_CACHE`" in ops)
    check("OPERATIONS says a restart does not clear the .pyc",
          re.search(r"restart does not clear it", ops) is not None)
    check("OPERATIONS gives a remedy that removes __pycache__",
          re.search(r"-name __pycache__ -type d -exec rm -rf", ops) is not None)
    pyc_tool = ROOT / "tools" / "check_pyc_staleness.py"
    check("the witness tools/check_pyc_staleness.py exists (the behaviour claim has a witness)",
          pyc_tool.exists())
    if pyc_tool.exists():
        got = subprocess.run([sys.executable, str(pyc_tool)], capture_output=True, text=True)
        check("check_pyc_staleness.py passes (stale case still reproduces)", got.returncode == 0,
              (got.stdout + got.stderr).strip()[-600:])

    # ---- Archive -----------------------------------------------------------
    arch = ROOT / "10-archive"
    check("10-archive exists", arch.is_dir())
    check("10-archive holds tier-03-bgp-simplified.yml", (arch / "tier-03-bgp-simplified.yml").exists())
    check("10-archive holds the two frr-configs",
          (arch / "frr-configs" / "r1-frr.conf").exists() and (arch / "frr-configs" / "r2-frr.conf").exists())
    check("10-archive holds topology-audit-2026-06-09.md", (arch / "topology-audit-2026-06-09.md").exists())
    check("quarantine dir really is gone from the tree",
          not (ROOT / "lab-definitions-quarantine-2026-09-30").exists())
    check("loader globs lab-definitions/**/*.yml only",
          "lab-definitions" in main_py and "*.yml" in main_py)

    print()
    print(f"{passes} PASS, {len(failures)} FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
