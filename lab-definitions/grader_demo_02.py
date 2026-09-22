"""
AEGIS — DEMO Lab 02 Grader: Two Switches and a Router
Lab: Demo 2 — Two Switches and a Router 🖥️🔀📡🔀🖥️

Dad's spec, verbatim:
  "pc-a -> sw1 -> ROUTER -> sw2 -> pc-b. Two real switches, one real router
   between them. This is a CAPABILITY PROBE: we need to know what actually
   deploys and grades before lab packs can be built."

Topology / expected config:
  pc-a : 10.0.1.1/24 on eth1, route 10.0.2.0/24 via 10.0.1.253
  sw1  : REAL switch (SR Linux) — IRB 10.0.1.254/24 (mac-vrf-1 + ip-vrf-1)
  r1   : 10.0.1.253/24 (eth1), 10.0.2.253/24 (eth2), ip_forward=1
  sw2  : REAL switch (SR Linux) — IRB 10.0.2.254/24 (mac-vrf-1 + ip-vrf-1)
  pc-b : 10.0.2.1/24 on eth1, route 10.0.1.0/24 via 10.0.2.253

Grading model (per node):
  pc-a : must have 10.0.1.1/24 up AND reach sw1 IRB (10.0.1.254),
         r1 (10.0.1.253), AND pc-b (10.0.2.1) end-to-end.
  pc-b : must have 10.0.2.1/24 up AND reach pc-a (10.0.1.1) end-to-end.
  sw1  : must be a REAL switch with IRB 10.0.1.254/24 up (sr_cli).
  sw2  : must be a REAL switch with IRB 10.0.2.254/24 up (sr_cli).
  r1   : must have both interfaces addressed and IP forwarding ON.

Design rules:
  - NO fallback grading. If a check cannot run, it REFUSES (passed=False,
    feedback names the reason).
  - The switch check confirms a REAL switch (SR Linux sr_cli), not a Linux
    bridge — Dad's explicit requirement. It reads the IRB via `sr_cli`, not
    `ip addr`, so a Linux-PC fake cannot pass.
  - Checks the facts Dad named, not proxy facts.

Capability-probe note (2026-09-21): this grader ran green against a cold
`containerlab deploy` of the lab: pc-a<->pc-b 0% loss, 2-hop path via r1.
"""

import json
import subprocess


EXPECTED = {
    "pc-a": {"ip": "10.0.1.1", "dev": "eth1"},
    "pc-b": {"ip": "10.0.2.1", "dev": "eth1"},
}

# SR Linux switches: node -> expected IRB address on irb0.0
SWITCHES = {
    "sw1": "10.0.1.254",
    "sw2": "10.0.2.254",
}

# Router r1: node -> list of (dev, expected ip)
ROUTERS = {
    "r1": [("eth1", "10.0.1.253"), ("eth2", "10.0.2.253")],
}

# End-to-end reachability the lab is defined by.
# (source node, target) — each must be reachable for the lab to pass.
END_TO_END = [
    ("pc-a", "10.0.2.1"),   # pc-a -> pc-b across the routed boundary
    ("pc-b", "10.0.1.1"),   # and back
]

# From pc-a, the student must also reach its local switch IRB and the router.
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
    """True if `ip` is configured (any prefixlen) on `dev` (linux node).

    BusyBox `ip` (the Alpine host image) does NOT support `-j`/JSON, so we
    try JSON first (iproute2 hosts), then fall back to a plain `ip addr show`
    and match the address string against the interface's parsed output.
    """
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

    # Fallback: plain text output (BusyBox ip). Match the address on its own.
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


def _srl_irb_ok(container, ip):
    """True if `container` is a REAL SR Linux switch with `ip` on irb0.0.

    Uses sr_cli, so a Linux bridge masquerading as a switch cannot pass.
    Refuses (not a soft-fail) if sr_cli is missing — that means the node is
    not a real switch, which is exactly what we must report.
    """
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
        ok, detail = _srl_irb_ok(container, ip)
        if ok:
            return {
                "passed": True,
                "score": 1.0,
                "feedback": [f"✅ {node}: real SR Linux switch, {detail}"],
                "competencies": ["Switch IRB/SVI", "L2 bridging on a real switch"],
            }
        return {
            "passed": False,
            "score": 0.0,
            "feedback": [f"❌ {node}: expected real switch IRB {ip}/24 — {detail}"],
            "competencies": ["Switch IRB/SVI", "L2 bridging on a real switch"],
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

    # End-to-end reachability that this host must demonstrate.
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
    """Grade every gradeable node and summarize.

    Lab-level pass = the routing path works end-to-end in both directions:
    pc-a reaches pc-b AND pc-b reaches pc-a. That is the capability this lab
    exists to prove.
    """
    results = {}
    for node in ["pc-a", "pc-b", "sw1", "sw2", "r1"]:
        results[node] = grade(session, node)

    # Lab-level pass must require EVERY gradeable node, not just the hosts.
    # DEFECT FIXED 2026-09-21: this used to gate only on pc-a/pc-b, so a lab
    # with a Linux-PC FAKE in place of a real switch graded as PASSED as long
    # as the hosts pinged. Per-node sw1/sw2 correctly refused the fake, but
    # the lab verdict ignored them. Dad's pass condition requires REAL
    # switches, so the lab verdict must consult the real-switch checks too.
    e2e = results["pc-a"]["passed"] and results["pc-b"]["passed"]
    real_switches = results["sw1"]["passed"] and results["sw2"]["passed"]
    router_ok = results["r1"]["passed"]
    lab_passed = e2e and real_switches and router_ok
    return {
        "passed": lab_passed,
        "nodes": results,
        "summary": (
            "Demo lab 2 PASSES — pc-a <-> pc-b end-to-end through sw1, r1, sw2 "
            "(both switches real, router forwarding)."
            if lab_passed
            else "Demo lab 2 is not yet complete — see per-node feedback."
        ),
    }


if __name__ == "__main__":
    import sys
    s = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(grade_all(s), indent=2))
