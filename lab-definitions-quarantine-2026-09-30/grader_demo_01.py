"""
AEGIS — DEMO Lab 01 Grader: Two PCs and a Switch
Lab: Demo — Two PCs and a Switch 🖥️🔀🖥️

Dad's pass condition, verbatim:
  "when PC 1 can ping BOTH the switch and PC 2, then the lab works."

Expected config:
  pc-a  : 10.0.1.1/24   on eth1
  pc-b  : 10.0.1.2/24   on eth1
  switch: 10.0.1.254/24 on br0  (management IP)

Grading model (per node):
  pc-a  -> must have 10.0.1.1/24 up AND reach 10.0.1.254 AND 10.0.1.2
  pc-b  -> must have 10.0.1.2/24 up
  switch-> must have 10.0.1.254/24 up on br0

Design rules:
  - NO fallback grading. If the check cannot run, it REFUSES (passed=False,
    feedback names the reason). A grade that is real, attributed, and
    meaningless is the failure mode this avoids.
  - Checks the facts Dad named, not proxy facts (no counting interfaces).
"""

import json
import subprocess


EXPECTED = {
    "pc-a":   {"ip": "10.0.1.1",   "dev": "eth1"},
    "pc-b":   {"ip": "10.0.1.2",   "dev": "eth1"},
    "switch": {"ip": "10.0.1.254", "dev": "br0"},
}

# From pc-a the student must reach both of these.
PING_TARGETS = ["10.0.1.254", "10.0.1.2"]


def _exec(container, cmd, timeout=15):
    """Run a shell command in a container. Returns (rc, stdout, stderr)."""
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
    """True if `ip` is configured (any prefixlen) on `dev`."""
    rc, out, err = _exec(container, f"ip -j addr show {dev} 2>/dev/null || true")
    if rc != 0 or not out:
        return False, f"could not read {dev} on {container}"
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return f"{ip}" in out, "raw parse"
    for iface in data:
        for addr in iface.get("addr_info", []):
            if addr.get("local") == ip:
                return True, f"{dev} has {ip}"
    return False, f"{ip} not found on {dev}"


def _ping_from(container, target):
    rc, out, err = _exec(container, f"ping -c 2 -W 2 {target}")
    return rc == 0, (out or err)


def grade(session, node):
    """Grade one node's configuration."""
    nodes = session.get("nodes", {})
    container = nodes.get(node)

    if not container:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Node '{node}' not found in session."],
            "competencies": [],
        }

    feedback = []
    score = 0.0

    spec = EXPECTED.get(node)
    if not spec:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Unknown node '{node}' for this lab."],
            "competencies": [],
        }

    # --- 1. Address on the right interface -------------------------------
    ok, detail = _node_ip_ok(container, spec["ip"], spec["dev"])
    if ok:
        feedback.append(f"✅ {node}: {spec['ip']}/24 present on {spec['dev']}")
        score += 0.5
    else:
        feedback.append(
            f"❌ {node}: expected {spec['ip']}/24 on {spec['dev']} — {detail}"
        )

    # pc-b and switch have exactly one requirement: their address is up.
    # Their per-node pass must reflect that, not a fraction of a two-part check.
    passed = ok

    # --- 2. pc-a must reach the switch AND pc-b (Dad's pass condition) ----
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
        # pc-a passes only if it has the address AND reaches BOTH targets.
        passed = ok and reached == len(PING_TARGETS)

    return {
        "passed": passed,
        "score": round(score, 3),
        "feedback": feedback,
        "competencies": (
            ["IP addressing", "Ping verification"]
            if node == "pc-a"
            else (["Management IP on switch"] if node == "switch" else ["IP addressing"])
        ),
    }


def grade_all(session):
    """Grade every gradeable node and summarize.

    Lab-level pass = Dad's pass condition: pc-a reaches BOTH the switch and
    PC-B. That is the definition of "the lab works." Per-node `passed`
    reflects each node's own completeness.
    """
    results = {}
    for node in EXPECTED:
        results[node] = grade(session, node)
    lab_passed = results["pc-a"]["passed"]
    return {
        "passed": lab_passed,
        "nodes": results,
        "summary": (
            "Demo lab PASSES — pc-a reaches both the switch and PC-B."
            if lab_passed
            else "Demo lab is not yet complete — see per-node feedback."
        ),
    }


if __name__ == "__main__":
    import sys
    s = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(grade_all(s), indent=2))
