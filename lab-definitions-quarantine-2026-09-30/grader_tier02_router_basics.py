"""
AEGIS — Tier 2 Grader: Router Basics
Lab: Configure Your First Router 🖥️🔧

Expected config:
  r1: hostname set, enable password configured, eth1 IP 10.0.1.1/24
  pc-a: 10.0.1.10/24 on eth1, default gateway 10.0.1.1
  pc-a should be able to ping r1 (10.0.1.1)
"""

import subprocess


def _exec(container_name, cmd):
    result = subprocess.run(
        ["docker", "exec", container_name, "sh", "-c", cmd],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


def _check_ip_on_iface(container_name, interface, expected_ip):
    output = _exec(container_name, f"ip -j addr show {interface} 2>/dev/null || ip addr show {interface}")
    return expected_ip in output


def _ping(container_name, target_ip):
    result = subprocess.run(
        ["docker", "exec", container_name, "ping", "-c", "2", "-W", "3", target_ip],
        capture_output=True, text=True, timeout=10
    )
    return result.returncode == 0


def grade(session, node):
    container_name = session["nodes"].get(node)
    if not container_name:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Node '{node}' not found in session."],
            "competencies": [],
        }

    feedback = []
    score = 0.0
    competencies = []

    if node == "r1":
        vtysh_out = _exec(container_name, "vtysh -c 'show running-config' 2>/dev/null")

        if "hostname" in vtysh_out and "hostname" not in _exec(container_name, "echo $HOSTNAME"):
            feedback.append("✅ Router hostname configured")
            score += 0.20
        else:
            feedback.append("❌ No hostname found. Use: `hostname R1` in vtysh configure terminal")

        if "enable secret" in vtysh_out or "enable password" in vtysh_out:
            feedback.append("✅ Enable password configured")
            score += 0.20
        else:
            feedback.append("❌ No enable password set. Use: `enable secret cisco` in vtysh config")

        if "interface eth1" in vtysh_out or "10.0.1.1/24" in vtysh_out:
            feedback.append("✅ Interface eth1 configured with IP")
            score += 0.25
        else:
            feedback.append("❌ eth1 not configured. Use: `interface eth1` then `ip address 10.0.1.1/24`")

        route_out = _exec(container_name, "vtysh -c 'show ip route' 2>/dev/null")
        if "C>" in route_out or "C " in route_out:
            feedback.append("✅ Connected routes present — interface is up")
            score += 0.15
        else:
            feedback.append("⚠️  No connected routes. Check interface is not shutdown")

        iface_check = _exec(container_name, "vtysh -c 'show ip interface brief' 2>/dev/null")
        if "eth1" in iface_check and "up" in iface_check.split("eth1")[-1][:15]:
            feedback.append("✅ eth1 status is 'up'")
            score += 0.10
        else:
            feedback.append("⚠️  eth1 may be down. Check `no shutdown` was applied")

    elif node == "pc-a":
        if _check_ip_on_iface(container_name, "eth1", "10.0.1.10"):
            feedback.append("✅ PC-A has IP 10.0.1.10 on eth1")
            score += 0.30
        else:
            feedback.append("❌ PC-A missing 10.0.1.10 on eth1")

        route_out = _exec(container_name, "ip route show default 2>/dev/null")
        if "via 10.0.1.1" in route_out:
            feedback.append("✅ Default gateway set to 10.0.1.1")
            score += 0.25
        else:
            feedback.append("❌ Missing default route via 10.0.1.1")

        if _ping(container_name, "10.0.1.1"):
            feedback.append("✅ PC-A → R1 ping successful!")
            score += 0.35
            competencies.append("Interface Configuration & Connectivity Verification")
        else:
            feedback.append("⚠️  PC-A can't reach R1 (10.0.1.1). Check R1 eth1 config.")

    else:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Unknown node: {node}"],
            "competencies": [],
        }

    passed = score >= 0.7
    status = "passed" if passed else "needs work"
    feedback.insert(0, f"{'✅' if passed else '⏳'} {node} {status}. Score: {round(score * 100)}/100 (70 required)")

    return {
        "passed": passed,
        "score": round(score, 2),
        "feedback": feedback,
        "competencies": list(set(competencies)),
    }
