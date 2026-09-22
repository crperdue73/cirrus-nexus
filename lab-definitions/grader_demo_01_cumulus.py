"""
AEGIS — DEMO Lab 01 Grader (REAL SWITCH, CUMULUS)
Lab: Demo — Two PCs and a Real Switch (Cumulus) 🖥️🔀🖥️

Dad's pass condition, verbatim:
  "when PC 1 can ping BOTH the switch and PC 2, then the lab works."
Dad's correction (2026-09-21): the switch must be a REAL switch, not a Linux
  PC running a bridge. PC-to-PC alone does NOT count.

Expected config:
  pc-a : 10.0.1.1/24   on eth1
  pc-b : 10.0.1.2/24   on eth1
  sw1  : REAL Cumulus Linux switch — bridge br0 (SVI) with 10.0.1.254/24
         ("L3 on the bridge")

Grading model (per node):
  pc-a : must have 10.0.1.1/24 up AND reach sw1 (10.0.1.254) AND pc-b
         (10.0.1.2).
  pc-b : must have 10.0.1.2/24 up.
  sw1  : must be a REAL Cumulus switch (fingerprint: real /etc/os-release
         naming Cumulus Linux AND vtysh present) with 10.0.1.254/24 on the
         bridge.

Design rules:
  - NO fallback grading. If a check cannot run, it REFUSES (passed=False,
    feedback names the reason).
  - The switch check fingerprints Cumulus (/etc/os-release + vtysh), so a
    plain Linux PC running a bridge cannot pass — Dad's explicit requirement.
  - BusyBox `ip` on the Alpine hosts has no JSON mode; parse plain output.
"""

import json
import subprocess


EXPECTED = {
    "pc-a": {"ip": "10.0.1.1", "dev": "eth1"},
    "pc-b": {"ip": "10.0.1.2", "dev": "eth1"},
}

# Real switch: node -> expected SVI address on the bridge device.
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


def _node_ip_ok(container, ip, dev=None):
    """True if `ip` is configured on `dev` (or any dev when dev is None)."""
    target = dev if dev else "-o"
    rc, out, err = _exec(container, f"ip -j addr show {target} 2>/dev/null || true")
    if rc == 0 and out and out.lstrip().startswith(("[", "{")):
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = None
        if data is not None:
            for iface in data:
                for addr in iface.get("addr_info", []):
                    if addr.get("local") == ip:
                        name = iface.get("ifname", dev)
                        return True, f"{name} has {ip}"
            return False, f"{ip} not found on {dev or 'any iface'}"

    rc, out, err = _exec(container, f"ip addr show {dev or ''} 2>&1 || true")
    if rc != 0 or not out:
        return False, f"could not read {dev or 'interfaces'} on {container}: {err or 'no output'}"
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("inet", "inet6"):
            if parts[1].split("/")[0] == ip:
                return True, f"{dev or 'iface'} has {ip}"
    return False, f"{ip} not found on {dev or 'any iface'}"


def _ping_from(container, target):
    rc, out, err = _exec(container, f"ping -c 2 -W 2 {target}")
    return rc == 0, (out or err)


def _cumulus_switch_ok(container, ip):
    """True if `container` is a REAL Cumulus switch with `ip` on its bridge.

    Fingerprint: a real Cumulus image reports Cumulus Linux in /etc/os-release
    AND ships vtysh. A plain Linux PC running a bridge fails both.
    """
    rc, osrel, _ = _exec(container, "cat /etc/os-release 2>/dev/null || true")
    is_cumulus = "cumulus" in (osrel or "").lower()

    rc2, vtysh, _ = _exec(container, "command -v vtysh 2>/dev/null || true")
    has_vtysh = bool(vtysh)

    if not is_cumulus or not has_vtysh:
        return False, (
            "node is not a real Cumulus switch "
            f"(os-release cumulus={is_cumulus}, vtysh={has_vtysh})"
        )

    ok, detail = _node_ip_ok(container, ip, None)
    if not ok:
        return False, f"{ip} not configured on the bridge/SVI"
    return True, f"Cumulus switch, {detail}"


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
        ok, detail = _cumulus_switch_ok(container, ip)
        return {
            "passed": ok,
            "score": 1.0 if ok else 0.0,
            "feedback": [
                f"✅ {node}: real Cumulus switch, {detail}" if ok
                else f"❌ {node}: expected real switch SVI {ip}/24 — {detail}"
            ],
            "competencies": ["Management IP on a real switch (SVI)",
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
    ok_ip, detail = _node_ip_ok(container, spec["ip"], spec["dev"])
    feedback.append(
        f"✅ {node}: {spec['ip']}/24 present on {spec['dev']}" if ok_ip
        else f"❌ {node}: {detail}"
    )

    passed = ok_ip

    if node == "pc-a":
        for tgt in PING_TARGETS:
            label = "sw1 (the switch)" if tgt == SWITCH_IP["sw1"] else "pc-b"
            ok, out = _ping_from(container, tgt)
            feedback.append(
                f"✅ {node} can ping {label} ({tgt})" if ok
                else f"❌ {node} cannot ping {label} ({tgt})"
            )
            passed = passed and ok

    competencies = []
    if ok_ip:
        competencies.append("IP addressing on a host")
    if node == "pc-a" and passed:
        competencies.append("Ping verification (host-to-switch, host-to-host)")

    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "feedback": feedback,
        "competencies": competencies,
    }


def grade_all(session):
    """Lab-level pass = Dad's pass condition: pc-a reaches BOTH the real
    Cumulus switch (SVI) and PC-B, AND the switch fingerprint confirms a real
    switch (so a Linux-PC fake cannot carry the lab).

    NOTE (2026-09-21): this function was MISSING from this grader while every
    sibling grader had one. Added so the Cumulus lab has the same lab-level
    verdict contract as grader_demo_01_srl / grader_demo_02, and so the
    real-switch requirement gates the LAB verdict, not just the node score.
    """
    results = {}
    for node in ["pc-a", "pc-b", "sw1"]:
        results[node] = grade(session, node)

    lab_passed = results["pc-a"]["passed"] and results["sw1"]["passed"]
    return {
        "passed": lab_passed,
        "nodes": results,
        "summary": (
            "Demo lab 1 (Cumulus) PASSES — pc-a reaches both the real switch "
            "and PC-B."
            if lab_passed
            else "Demo lab 1 (Cumulus) is not yet complete — see per-node feedback."
        ),
    }


if __name__ == "__main__":
    import sys
    s = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(grade_all(s), indent=2))
