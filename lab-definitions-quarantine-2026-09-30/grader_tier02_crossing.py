"""
AEGIS — Tier 2 Grader: Crossing Subnets
Lab: Two Networks, One Router 🖥️🔀🖥️

Expected config:
  rtr:  eth1 (10.0.1.1/24), eth2 (10.0.2.1/24)
  pc-a: 10.0.1.10/24 on eth1, default gateway 10.0.1.1
  pc-b: 10.0.2.10/24 on eth1, default gateway 10.0.2.1
  pc-a should be able to ping pc-b (10.0.2.10)
  pc-b should be able to ping pc-a (10.0.1.10)
"""

import json
import re
import subprocess


def _exec(container_name, cmd):
    """Run a command inside a container and return stdout."""
    result = subprocess.run(
        ["docker", "exec", container_name, "sh", "-c", cmd],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


def _check_ip_on_interface(container_name, interface, expected_ip, expected_prefix):
    """Check if an IP with a given prefix is assigned to an interface."""
    output = _exec(container_name, f"ip -j addr show {interface} 2>/dev/null || ip addr show {interface}")
    try:
        data = json.loads(output)
        for iface in data:
            for addr in iface.get("addr_info", []):
                if addr.get("local") == expected_ip and addr.get("prefixlen") == expected_prefix:
                    return True
    except (json.JSONDecodeError, KeyError):
        # Fallback regex
        if re.search(rf"{re.escape(expected_ip)}/{expected_prefix}", output):
            return True
    return False


def _check_interface_up(container_name, interface):
    """Check if an interface is operationally up."""
    state = _exec(container_name, f"cat /sys/class/net/{interface}/operstate 2>/dev/null")
    return state == "up"


def _ping(container_name, target_ip):
    """Ping a target and return True if successful."""
    result = subprocess.run(
        ["docker", "exec", container_name, "ping", "-c", "2", "-W", "3", target_ip],
        capture_output=True, text=True, timeout=10
    )
    return result.returncode == 0


def grade(session, node):
    """Grade a student's configuration for a given node."""
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

    if node == "pc-a":
        # PC-A: 10.0.1.10/24 on eth1, default gateway 10.0.1.1
        if _check_ip_on_interface(container_name, "eth1", "10.0.1.10", 24):
            feedback.append("✅ PC-A has IP 10.0.1.10/24 on eth1")
            score += 0.25
        else:
            feedback.append("❌ PC-A missing 10.0.1.10/24 on eth1")

        if _check_interface_up(container_name, "eth1"):
            feedback.append("✅ PC-A eth1 is up")
            score += 0.10
        else:
            feedback.append("❌ PC-A eth1 is not up")

        # Check default gateway
        route_output = _exec(container_name, "ip route show default 2>/dev/null")
        if "via 10.0.1.1" in route_output:
            feedback.append("✅ PC-A default gateway set to 10.0.1.1")
            score += 0.15
        else:
            feedback.append("❌ PC-A missing default route via 10.0.1.1")

        # Ping PC-B through router
        if _ping(container_name, "10.0.2.10"):
            feedback.append("✅ PC-A → PC-B ping successful — traffic crossed subnets!")
            score += 0.30
            competencies.append("Multi-Interface Router Configuration")
            competencies.append("Default Gateway & Connected Routes")
        else:
            feedback.append("⚠️  PC-A can't reach PC-B (10.0.2.10). Check RTR config and PC-B's setup.")

        # Ping RTR's interface on this subnet
        if _ping(container_name, "10.0.1.1"):
            feedback.append("✅ PC-A can reach RTR gateway (10.0.1.1)")
            score += 0.10
        else:
            feedback.append("⚠️  PC-A can't reach its default gateway. Check RTR eth1 config.")

    elif node == "pc-b":
        # PC-B: 10.0.2.10/24 on eth1, default gateway 10.0.2.1
        if _check_ip_on_interface(container_name, "eth1", "10.0.2.10", 24):
            feedback.append("✅ PC-B has IP 10.0.2.10/24 on eth1")
            score += 0.25
        else:
            feedback.append("❌ PC-B missing 10.0.2.10/24 on eth1")

        if _check_interface_up(container_name, "eth1"):
            feedback.append("✅ PC-B eth1 is up")
            score += 0.10
        else:
            feedback.append("❌ PC-B eth1 is not up")

        # Check default gateway
        route_output = _exec(container_name, "ip route show default 2>/dev/null")
        if "via 10.0.2.1" in route_output:
            feedback.append("✅ PC-B default gateway set to 10.0.2.1")
            score += 0.15
        else:
            feedback.append("❌ PC-B missing default route via 10.0.2.1")

        # Ping PC-A through router
        if _ping(container_name, "10.0.1.10"):
            feedback.append("✅ PC-B → PC-A ping successful — traffic crossed subnets!")
            score += 0.30
            competencies.append("Multi-Interface Router Configuration")
            competencies.append("Default Gateway & Connected Routes")
        else:
            feedback.append("⚠️  PC-B can't reach PC-A (10.0.1.10). Check RTR config and PC-A's setup.")

        # Ping RTR's interface on this subnet
        if _ping(container_name, "10.0.2.1"):
            feedback.append("✅ PC-B can reach RTR gateway (10.0.2.1)")
            score += 0.10
        else:
            feedback.append("⚠️  PC-B can't reach its default gateway. Check RTR eth2 config.")

    elif node in ("rtr", "r1"):
        # RTR: check hostname, eth1 and eth2 configs via vtysh.
        # NOTE (2026-09-23): 03-crossing-subnets.yml ships this node as `r1`,
        # but this grader only dispatched on `rtr`, so the router could never
        # be graded ("Unknown node: r1"). Accept BOTH names so the shipped
        # topology and any `rtr` variant both grade. Siblings already use `r1`.
        vtysh_output = _exec(container_name, "vtysh -c 'show running-config' 2>/dev/null")

        if "hostname RTR" in vtysh_output:
            feedback.append("✅ Router hostname set to RTR")
            score += 0.10
        else:
            feedback.append("❌ Router hostname not set to RTR")

        if "enable secret" in vtysh_output or "enable password" in vtysh_output:
            feedback.append("✅ Enable password configured")
            score += 0.10
        else:
            feedback.append("⚠️  No enable password found (enable secret recommended)")

        if "interface eth1" in vtysh_output and "10.0.1.1/24" in vtysh_output:
            feedback.append("✅ RTR eth1 configured with 10.0.1.1/24")
            score += 0.20
        else:
            feedback.append("❌ RTR eth1 not properly configured (expected 10.0.1.1/24)")

        if "interface eth2" in vtysh_output and "10.0.2.1/24" in vtysh_output:
            feedback.append("✅ RTR eth2 configured with 10.0.2.1/24")
            score += 0.20
        else:
            feedback.append("❌ RTR eth2 not properly configured (expected 10.0.2.1/24)")

        # Check connected routes via show ip route
        route_output = _exec(container_name, "vtysh -c 'show ip route' 2>/dev/null")
        connected_count = route_output.count("C>") + route_output.count("C ")
        if connected_count >= 2:
            feedback.append(f"✅ RTR has {connected_count} connected routes (eth1 + eth2)")
            score += 0.20
            competencies.append("Default Gateway & Connected Routes")
        else:
            feedback.append(f"⚠️  RTR shows {connected_count} connected routes, expected 2")

        # Check interfaces are up via show ip interface brief
        brief = _exec(container_name, "vtysh -c 'show ip interface brief' 2>/dev/null")
        # Count interfaces that are "up" (not "down" or "administratively down")
        if "eth1" in brief and "eth2" in brief:
            feedback.append("✅ Both interfaces (eth1, eth2) present")
            score += 0.10
        else:
            feedback.append("⚠️  Missing one or more interface configs")

    else:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Unknown node: {node}"],
            "competencies": [],
        }

    # Determine pass/fail
    passed = score >= 0.7
    if passed:
        feedback.insert(0, f"✅ {node} passed! Score: {round(score * 100)}/100")
    else:
        feedback.insert(0, f"⏳ {node} needs work. Score: {round(score * 100)}/100 (70 required)")

    return {
        "passed": passed,
        "score": round(score, 2),
        "feedback": feedback,
        "competencies": list(set(competencies)),
    }
