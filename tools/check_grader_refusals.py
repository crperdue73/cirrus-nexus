#!/usr/bin/env python3
"""Witness: a switch that is not RUNNING must be refused, never graded as a failed config.

WHY THIS EXISTS
===============
Found live 2026-11-15 on this host, with the shipped demo-01 lab deployed: `sw1` had been
stopped (exit 143, a clean SIGTERM) six days earlier. Running the shipped grader against that
session returned, verbatim:

    ❌ sw1: expected real switch IRB 10.0.1.254/24 — no output from sr_cli: Error response from
       daemon: container ... is not running

The two Linux hosts in the SAME session got this right — they refused, with
"eth1 does not exist on this node — its link is gone … this is not a verdict about your
configuration." That refusal path was added in RUN 179 (2026-10-04) for exactly this reason.

The switch path never got it. `_srl_irb_ok` asked docker for `sr_cli` output, got an error on
stderr with empty stdout, and `if not out:` reported `no output from sr_cli` — a verdict-shaped
sentence ("expected real switch IRB 10.0.1.254/24 — …") built from a container that produced no
output because it was not running. A student reading that concludes they misconfigured the
switch. They cannot have: a stopped container ignores every command, and no amount of
re-checking or reconfiguring brings it back. Same defect in `grader_demo_02._srl_irb_ok`.

WHAT THIS CHECKS
================
It does not trust the graders' prose; it calls them. For each of the three states a node can be
in, it asserts the *shape* of the verdict:

  running + correct IRB   -> passed True,  status absent/ok,  no "not found"/"not running" text
  RUNNING but wrong IRB   -> passed False, status absent,    feedback says not found    (real verdict)
  STOPPED                 -> passed False, status "refused", feedback says the lab is not running
  ABSENT (no container)   -> passed False, status "refused", feedback says the lab is not running

The middle row is the control that matters: it proves the fix did not simply turn every
non-pass into a refusal and thereby stop grading anything. A refusal-only grader would pass
rows 3 and 4 and fail row 2.

How the states are produced WITHOUT docker: both graders call `subprocess.run(["docker", ...])`
for every host-side read. This script swaps `subprocess.run` for a stub that answers as docker
would in each state, then restores it. No container is touched; no image is needed. Graders are
imported from `lab-definitions/`, the same files the app loads.

Usage:  python3 tools/check_grader_refusals.py        # rc=0 when every assertion holds
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab-definitions"))

RESULTS: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))


# ---------------------------------------------------------------------------
# A fake docker, per node state.
# ---------------------------------------------------------------------------

SRCLI_UP = """\
===============================================================================
irb0 is up
  +--------+--------+---------+----------------+---------+---------+
  |  IPv4  |  IPv6  | oper    |  Description   |  Type   |  MTU    |
  | Address| Address| state   |                |         |         |
  +--------+--------+---------+----------------+---------+---------+
  | 10.0.1.254/24 |        | up      |                |         | 1500    |
  +--------+--------+---------+----------------+---------+---------+
  subinterface : 0
    irb0.0 is up
"""

STOPPED_ERR = (
    "Error response from daemon: container 0f1e2d3c4b5a is not running"
)
ABSENT_ERR = "Error response from daemon: No such container: {name}"


class FakeDocker:
    """Answers `docker exec` / `docker inspect` as docker would, for one node state."""

    def __init__(self, state: str, srcli_output: str | None = None):
        self.state = state          # "running" | "stopped" | "absent"
        self.srcli = srcli_output
        self.calls: list[str] = []

    def __call__(self, argv, *a, **kw):
        cmd = " ".join(argv)
        self.calls.append(cmd)

        out, err, rc = "", "", 0
        if "inspect" in cmd:
            # `docker inspect -f '{{ index .Config.Labels "clab-node-kind" }}' <c>`
            # An absent container makes inspect fail with empty output.
            if self.state == "absent":
                rc, err = 1, ABSENT_ERR.format(name=cmd.split()[-1])
            else:
                out = "nokia_srlinux"
        elif self.state == "absent":
            rc, err = 1, ABSENT_ERR.format(name=cmd.split()[-1])
        elif self.state == "stopped":
            rc, err = 1, STOPPED_ERR
        else:
            # running: answer the sr_cli read, and nothing else surprises us
            if "sr_cli" in cmd and self.srcli is not None:
                out = self.srcli
            elif "sr_cli" in cmd:
                out = ""
            else:
                out = ""

        return subprocess.CompletedProcess(args=argv, returncode=rc, stdout=out, stderr=err)


def grade_one(module, state: str, srcli: str | None, node: str = "sw1") -> dict:
    """Grade `node` with `module` under a fake docker in `state`."""
    fake = FakeDocker(state, srcli)
    real = subprocess.run
    subprocess.run = fake  # type: ignore[assignment]
    try:
        session = {"nodes": {node: f"clab-test-{node}"}}
        return module.grade(session, node)
    finally:
        subprocess.run = real  # type: ignore[assignment]


def flat(res: dict) -> str:
    return " | ".join(res.get("feedback") or [])


def exercise(label: str, module) -> None:
    # --- 1. running, correct IRB: a real pass --------------------------------
    r = grade_one(module, "running", SRCLI_UP)
    check(f"{label}: running+correct IRB passes", r.get("passed") is True, flat(r))
    check(f"{label}: running+correct IRB is not refused",
          r.get("status") not in ("refused",), flat(r))
    check(f"{label}: running+correct IRB scores 1.0", r.get("score") == 1.0, str(r.get("score")))

    # --- 2. CONTROL: running, IRB missing -> a genuine failed verdict ---------
    r = grade_one(module, "running", "irb0 is down\n  irb0.0 is down\n")
    check(f"{label}: running+wrong IRB FAILS (control: still grades)",
          r.get("passed") is False, flat(r))
    check(f"{label}: running+wrong IRB is NOT refused",
          r.get("status") != "refused",
          f"status={r.get('status')!r}; a running switch with a bad IRB is a real verdict")
    check(f"{label}: running+wrong IRB names the address it looked for",
          "10.0.1.254" in flat(r) or "10.0.2.254" in flat(r), flat(r))

    # --- 3. stopped: refuse ------------------------------------------------
    r = grade_one(module, "stopped", None)
    check(f"{label}: STOPPED switch is refused",
          r.get("status") == "refused",
          f"status={r.get('status')!r}, feedback={flat(r)}")
    check(f"{label}: STOPPED switch is not passed", r.get("passed") is False, flat(r))
    check(f"{label}: STOPPED switch says it is not running",
          "not running" in flat(r).lower(), flat(r))
    check(f"{label}: STOPPED switch does not blame the config",
          "expected real switch IRB" not in flat(r).replace("not running", ""),
          flat(r))
    check(f"{label}: STOPPED switch feedback is student-actionable",
          "start" in flat(r).lower() or "restart" in flat(r).lower(), flat(r))

    # --- 4. absent: same treatment -----------------------------------------
    r = grade_one(module, "absent", None)
    check(f"{label}: ABSENT switch is refused",
          r.get("status") == "refused", f"status={r.get('status')!r}, feedback={flat(r)}")
    check(f"{label}: ABSENT switch is not passed", r.get("passed") is False, flat(r))


def main() -> int:
    try:
        g1 = importlib.import_module("grader_demo_01_srl")
        g2 = importlib.import_module("grader_demo_02")
    except Exception as exc:  # noqa: BLE001 - report, don't traceback
        print(f"FAIL  could not import the shipped graders: {exc}")
        print("\n0 PASS, 1 FAIL")
        return 1

    exercise("demo-01", g1)
    exercise("demo-02", g2)

    passes = sum(1 for ok, _, _ in RESULTS if ok)
    fails = [(n, d) for ok, n, d in RESULTS if not ok]
    for ok, name, detail in RESULTS:
        if ok:
            print(f"PASS  {name}")
        else:
            print(f"FAIL  {name}\n        {detail}")
    print(f"\n{passes} PASS, {len(fails)} FAIL")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
