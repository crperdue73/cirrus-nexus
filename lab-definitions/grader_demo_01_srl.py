"""
AEGIS — DEMO Lab 01 Grader (REAL SWITCH): Two PCs and a Nokia SR Linux Switch
Lab: Demo — Two PCs and a Real Switch (SR Linux) 🖥️🔀🖥️

Dad's pass condition, verbatim:
  "when PC 1 can ping BOTH the switch and PC 2, then the lab works."
Dad's correction (2026-09-21): the switch must be a REAL switch, not a Linux
  PC running a bridge. PC-to-PC alone does NOT count.

Expected config:
  pc-a : 10.0.1.1/24   on eth1
  pc-b : 10.0.1.2/24   on eth1
  sw1  : REAL SR Linux switch — IRB 10.0.1.254/24 on irb0.0
         (member of BOTH mac-vrf-1 and ip-vrf-1)

Grading model (per node):
  pc-a : must have 10.0.1.1/24 up AND reach sw1 IRB (10.0.1.254) AND pc-b
         (10.0.1.2).
  pc-b : must have 10.0.1.2/24 up.
  sw1  : must be a REAL switch (sr_cli) with IRB 10.0.1.254/24 up.

Design rules:
  - NO fallback grading. If a check cannot run, it REFUSES (passed=False,
    feedback names the reason).
  - The switch check reads the IRB via `sr_cli`, so a Linux-PC fake cannot
    pass — Dad's explicit requirement.
  - BusyBox `ip` on the Alpine hosts has no JSON mode; parse plain output.
"""

import json
import subprocess


EXPECTED = {
    "pc-a": {"ip": "10.0.1.1", "dev": "eth1"},
    "pc-b": {"ip": "10.0.1.2", "dev": "eth1"},
}

# Real switch: node -> expected IRB address on irb0.0
SWITCH_IP = {"sw1": "10.0.1.254"}

# From pc-a the student must reach BOTH of these (Dad's pass condition).
PING_TARGETS = ["10.0.1.254", "10.0.1.2"]


def _exec(container, cmd, timeout=20):
    try:
        r = subprocess.run(
            ["docker", "exec", container, "sh", "-c", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", "docker not available"


def _node_ip_ok(container, ip, dev):
    """True if `ip` is configured (any prefixlen) on `dev` (linux node)."""
    rc, out, err = _exec(container, f"ip -j addr show {dev} 2>/dev/null || true")
    if rc == 0 and out and out.lstrip().startswith(("[", "{")):
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = None
        if data is not None:
            for iface in data:
                for addr in iface.get("addr_info", []):
                    if addr.get("local") == ip:
                        return True, f"{dev} has {ip}"
            return False, f"{ip} not found on {dev}"

    rc, out, err = _exec(container, f"ip addr show {dev} 2>&1 || true")
    if rc != 0 or not out:
        return False, f"could not read {dev} on {container}: {err or 'no output'}"
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("inet", "inet6"):
            if parts[1].split("/")[0] == ip:
                return True, f"{dev} has {ip}"
    return False, f"{ip} not found on {dev}"


def _ping_from(container, target):
    rc, out, err = _exec(container, f"ping -c 2 -W 2 {target}")
    return rc == 0, (out or err)


def _srl_irb_ok(container, ip):
    """True if `container` is a REAL SR Linux switch with `ip` on irb0.0."""
    rc, out, err = _exec(container, "sr_cli 'show interface irb0' 2>&1")
    if rc == 127:
        return False, "sr_cli not available — node is not an SR Linux switch"
    if not out:
        return False, f"no output from sr_cli: {err}"
    if "sr_cli: not found" in out or "command not found" in out:
        return False, "sr_cli not available — node is not an SR Linux switch"
    if ip in out and "irb0.0 is up" in out:
        return True, f"SR Linux irb0.0 up with {ip}"
    if ip in out:
        return False, f"{ip} present but irb0.0 not reported up"
    return False, f"{ip} not found on irb0.0"


def grade(session, node):
    nodes = session.get("nodes", {})
    container = nodes.get(node)

    if not container:
        return {
            "passed": False, "score": 0,
            "feedback": [f"❌ Node '{node}' not found in session."],
            "competencies": [],
        }

    # --- Real switch ------------------------------------------------------
    if node in SWITCH_IP:
        ip = SWITCH_IP[node]
        ok, detail = _srl_irb_ok(container, ip)
        return {
            "passed": ok,
            "score": 1.0 if ok else 0.0,
            "feedback": [
                f"✅ {node}: real SR Linux switch, {detail}" if ok
                else f"❌ {node}: expected real switch IRB {ip}/24 — {detail}"
            ],
            "competencies": ["Management IP on a real switch (IRB)",
                             "L2 bridging on a real switch"],
        }

    spec = EXPECTED.get(node)
    if not spec:
        return {
            "passed": False, "score": 0,
            "feedback": [f"❌ Unknown node '{node}' for this lab."],
            "competencies": [],
        }

    feedback = []
    score = 0.0
    ok, detail = _node_ip_ok(container, spec["ip"], spec["dev"])
    if ok:
        feedback.append(f"✅ {node}: {spec['ip']}/24 present on {spec['dev']}")
        score += 0.5
    else:
        feedback.append(
            f"❌ {node}: expected {spec['ip']}/24 on {spec['dev']} — {detail}"
        )

    passed = ok

    if node == "pc-a":
        reached = 0
        for target in PING_TARGETS:
            good, out = _ping_from(container, target)
            label = "the switch" if target == "10.0.1.254" else "PC-B"
            if good:
                feedback.append(f"✅ pc-a can ping {label} ({target})")
                reached += 1
            else:
                feedback.append(f"❌ pc-a cannot ping {label} ({target})")
        score += 0.5 * (reached / len(PING_TARGETS))
        passed = ok and reached == len(PING_TARGETS)

    return {
        "passed": passed,
        "score": round(score, 3),
        "feedback": feedback,
        "competencies": (
            ["IP addressing", "Ping verification"]
            if node == "pc-a"
            else ["IP addressing"]
        ),
    }


def grade_all(session):
    """Lab-level pass = Daddy's pass condition: pc-a reaches BOTH the real
    switch IRB and PC-B."""
    results = {}
    for node in ["pc-a", "pc-b", "sw1"]:
        results[node] = grade(session, node)
    lab_passed = results["pc-a"]["passed"] and results["sw1"]["passed"]
    return {
        "passed": lab_passed,
        "nodes": results,
        "summary": (
            "Demo lab 1 PASSES — pc-a reaches both the real switch and PC-B."
            if lab_passed
            else "Demo lab 1 is not yet complete — see per-node feedback."
        ),
    }


if __name__ == "__main__":
    import sys
    s = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(grade_all(s), indent=2))
