"""AEGIS — Demo Lab 02 (CUMULUS) grader: two real Cumulus switches + one router.

Shape:  pc-a --- sw1(Cumulus) --- r1(FRR) --- sw2(Cumulus) --- pc-b
        10.0.1.0/24        .254   .253|.253   .254       10.0.2.0/24

What each node must show:
  pc-a : 10.0.1.1/24 up AND reach sw1 SVI (10.0.1.254), r1 (10.0.1.253),
         and pc-b (10.0.2.1) ACROSS the routed boundary.
  pc-b : 10.0.2.1/24 up AND reach pc-a (10.0.1.1) back across the router.
  r1   : 10.0.1.253/24 + 10.0.2.253/24 up, ip_forward=1.
  sw1  : REAL Cumulus switch (os-release Cumulus + vtysh present) with
         10.0.1.254/24 up on the bridge device br0 (the SVI).
  sw2  : REAL Cumulus switch with 10.0.2.254/24 up on br0.

The switch check fingerprints a REAL Cumulus Linux system, so a plain Linux
bridge masquerading as a switch cannot pass (Dad's explicit requirement). It
reads the SVI via `ip -j addr show br0`, but ALSO requires the Cumulus
fingerprint, so the address alone is never sufficient.

Lab-level pass requires ALL of: both hosts end-to-end, BOTH switches real with
their SVI up, AND the router forwarding.
"""

import json
import subprocess

EXPECTED = {
    "pc-a": {"ip": "10.0.1.1", "dev": "eth1"},
    "pc-b": {"ip": "10.0.2.1", "dev": "eth1"},
}

# Cumulus switches: node -> expected SVI address on the bridge device br0
SWITCHES = {
    "sw1": "10.0.1.254",
    "sw2": "10.0.2.254",
}

ROUTERS = {
    "r1": [("eth1", "10.0.1.253"), ("eth2", "10.0.2.253")],
}

# (source node, target) — each must be reachable for the lab to pass.
END_TO_END = [
    ("pc-a", "10.0.2.1"),   # pc-a -> pc-b across the routed boundary
    ("pc-b", "10.0.1.1"),   # and back
]

# From pc-a, the student must also reach its local switch SVI and the router.
PC_A_LOCAL_TARGETS = ["10.0.1.254", "10.0.1.253"]


def _exec(container, cmd, timeout=20):
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

    # Fallback: plain text output (BusyBox ip).
    rc, out, err = _exec(container, f"ip addr show {dev} 2>&1 || true")
    if rc != 0 or not out:
        return False, f"could not read {dev} on {container}: {err or 'no output'}"
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("inet", "inet6"):
            if parts[1].split("/")[0] == ip:
                return True, f"{dev} has {ip}"
    return False, f"{ip} not found on {dev}"


def _ip_forward_ok(container):
    rc, out, err = _exec(container, "cat /proc/sys/net/ipv4/ip_forward")
    if rc != 0:
        return False, f"could not read ip_forward: {err}"
    return out.strip() == "1", f"ip_forward={out.strip()}"


def _ping_from(container, target):
    rc, out, err = _exec(container, f"ping -c 2 -W 2 {target}")
    return rc == 0, (out or err)


def _cumulus_fingerprint(container):
    """True if `container` looks like a REAL Cumulus Linux system.

    Two independent signals, both required:
      - /etc/os-release names Cumulus Linux
      - the Cumulus/FRR CLI `vtysh` exists
    A plain Linux bridge has neither, so it cannot pass.
    """
    rc, out, err = _exec(container, "cat /etc/os-release 2>&1")
    if rc != 0 or "Cumulus" not in out:
        return False, "os-release not Cumulus"
    rc2, out2, _ = _exec(container, "command -v vtysh 2>/dev/null || echo MISSING")
    if "vtysh" not in out2 or out2.strip() == "MISSING":
        return False, "vtysh missing"
    return True, "Cumulus Linux (os-release + vtysh)"


def _cumulus_svi_ok(container, ip):
    """True if `container` is a REAL Cumulus switch with `ip` up on br0 (SVI).

    Requires the Cumulus fingerprint FIRST (refuses if absent — that means the
    node is not a real switch, which is exactly what must be reported), then
    the SVI address on the bridge device.
    """
    real, fp_detail = _cumulus_fingerprint(container)
    if not real:
        return False, f"node is not a real Cumulus switch ({fp_detail})"

    ok, detail = _node_ip_ok(container, ip, "br0")
    if not ok:
        return False, f"{ip} not configured on the bridge SVI (br0) — {detail}"

    # Confirm br0 is actually up (an SVI that is down is not usable).
    rc, out, _ = _exec(container, "ip -br link show br0 2>&1 || true")
    if "UP" not in out:
        return False, f"br0 present with {ip} but bridge is not UP ({out})"
    return True, f"real Cumulus switch, {ip}/24 on br0 (SVI), bridge UP"


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

    # --- Real switches ---------------------------------------------------
    if node in SWITCHES:
        ip = SWITCHES[node]
        ok, detail = _cumulus_svi_ok(container, ip)
        if ok:
            return {
                "passed": True,
                "score": 1.0,
                "feedback": [f"✅ {node}: {detail}"],
                "competencies": ["Switch SVI/L3-on-bridge", "L2 bridging on a real switch"],
            }
        return {
            "passed": False,
            "score": 0.0,
            "feedback": [f"❌ {node}: expected real Cumulus switch with SVI {ip}/24 — {detail}"],
            "competencies": ["Switch SVI/L3-on-bridge", "L2 bridging on a real switch"],
        }

    # --- Router ----------------------------------------------------------
    if node in ROUTERS:
        score = 0.0
        passed = True
        for dev, ip in ROUTERS[node]:
            ok, detail = _node_ip_ok(container, ip, dev)
            if ok:
                feedback.append(f"✅ r1: {ip}/24 present on {dev}")
                score += 0.4
            else:
                feedback.append(f"❌ r1: expected {ip}/24 on {dev} — {detail}")
                passed = False
        fwd_ok, fwd_detail = _ip_forward_ok(container)
        if fwd_ok:
            feedback.append(f"✅ r1: IP forwarding ON ({fwd_detail})")
            score += 0.2
        else:
            feedback.append(f"❌ r1: IP forwarding OFF ({fwd_detail})")
            passed = False
        return {
            "passed": passed,
            "score": round(score, 3),
            "feedback": feedback,
            "competencies": ["Router interface addressing", "IP forwarding"],
        }

    # --- Hosts -----------------------------------------------------------
    spec = EXPECTED.get(node)
    if not spec:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Unknown node '{node}' for this lab."],
            "competencies": [],
        }

    score = 0.0
    ok, detail = _node_ip_ok(container, spec["ip"], spec["dev"])
    if ok:
        feedback.append(f"✅ {node}: {spec['ip']}/24 present on {spec['dev']}")
        score += 0.5
    else:
        feedback.append(
            f"❌ {node}: expected {spec['ip']}/24 on {spec['dev']} — {detail}"
        )

    targets = []
    for src, tgt in END_TO_END:
        if src == node:
            targets.append(tgt)
    if node == "pc-a":
        targets = PC_A_LOCAL_TARGETS + targets

    reached = 0
    for target in targets:
        good, out = _ping_from(container, target)
        label = {
            "10.0.1.254": "sw1 (the left switch)",
            "10.0.1.253": "r1 (the router)",
            "10.0.2.1": "pc-b (across the router)",
            "10.0.1.1": "pc-a (across the router)",
        }.get(target, target)
        if good:
            feedback.append(f"✅ {node} can ping {label} ({target})")
            reached += 1
        else:
            feedback.append(f"❌ {node} cannot ping {label} ({target})")

    if targets:
        score += 0.5 * (reached / len(targets))
        passed = ok and reached == len(targets)
    else:
        passed = ok

    return {
        "passed": passed,
        "score": round(score, 3),
        "feedback": feedback,
        "competencies": ["IP addressing", "Static routing", "Ping verification"],
    }


def grade_all(session):
    """Grade every gradeable node and summarize."""
    results = {}
    for node in ["pc-a", "pc-b", "sw1", "sw2", "r1"]:
        results[node] = grade(session, node)

    e2e = results["pc-a"]["passed"] and results["pc-b"]["passed"]
    real_switches = results["sw1"]["passed"] and results["sw2"]["passed"]
    router_ok = results["r1"]["passed"]
    lab_passed = e2e and real_switches and router_ok
    return {
        "passed": lab_passed,
        "nodes": results,
        "summary": (
            "Demo lab 2 (Cumulus) PASSES — pc-a <-> pc-b end-to-end through "
            "sw1, r1, sw2 (both switches real Cumulus, router forwarding)."
            if lab_passed
            else "Demo lab 2 (Cumulus) is not yet complete — see per-node feedback."
        ),
    }


if __name__ == "__main__":
    import sys
    s = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(grade_all(s), indent=2))
