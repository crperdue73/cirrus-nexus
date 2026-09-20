"""
AEGIS — Tier 1 Grader: Foundation
Lab: Make Two Computers Talk 🖥️🖥️

Expected config:
  pc-a: 10.0.1.1/24 on eth1
  pc-b: 10.0.1.2/24 on eth1
  Both should be able to ping each other.
"""

import json
import subprocess


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
    passed = False
    competencies = []

    # Define expected IPs
    ips = {"pc-a": "10.0.1.1", "pc-b": "10.0.1.2"}
    partner_ips = {"pc-a": "10.0.1.2", "pc-b": "10.0.1.1"}

    expected_ip = ips.get(node)
    partner_ip = partner_ips.get(node)

    if not expected_ip:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Unknown node: {node}"],
            "competencies": [],
        }

    # Step 1: Check IP assignment on eth1
    result = subprocess.run(
        ["docker", "exec", container_name, "sh", "-c",
         "ip -j addr show eth1 2>/dev/null || ip addr show eth1"],
        capture_output=True, text=True, timeout=10
    )
    config_text = result.stdout.strip()

    if expected_ip in config_text:
        feedback.append(f"✅ {node} has IP {expected_ip} assigned on eth1")
        score += 0.4

        # Check prefix length
        try:
            data = json.loads(config_text)
            for iface in data:
                for addr in iface.get("addr_info", []):
                    if addr.get("local") == expected_ip:
                        prefix = addr.get("prefixlen")
                        if prefix == 24:
                            feedback.append(f"✅ Subnet mask /24 is correct")
                            score += 0.2
                        else:
                            feedback.append(f"⚠️  Prefix is /{prefix}, expected /24")
        except json.JSONDecodeError:
            # Fallback: regex
            import re
            match = re.search(rf"{re.escape(expected_ip)}/(\d+)", config_text)
            if match and match.group(1) == "24":
                feedback.append(f"✅ Subnet mask /24 is correct")
                score += 0.2

        # Step 2: Check interface is up
        up_check = subprocess.run(
            ["docker", "exec", container_name, "sh", "-c",
             "cat /sys/class/net/eth1/operstate 2>/dev/null"],
            capture_output=True, text=True, timeout=5
        )
        if up_check.stdout.strip() == "up":
            feedback.append(f"✅ Interface eth1 is up")
            score += 0.1

        # Step 3: Ping partner
        ping = subprocess.run(
            ["docker", "exec", container_name, "ping", "-c", "2", "-W", "3", partner_ip],
            capture_output=True, text=True, timeout=10
        )
        if ping.returncode == 0:
            feedback.append(f"✅ Ping to {partner_ip} successful — they can talk!")
            score += 0.3
            competencies.append("Networking Basics — Ethernet & IP Addressing")
        else:
            feedback.append(f"⚠️  IP is set but can't reach {partner_ip}. Is the other computer configured?")
    else:
        current = config_text.replace("\n", "; ")[:150]
        feedback.append(f"❌ {node} doesn't have {expected_ip}. Current config: {current}")
        feedback.append(f"💡  Try: `ip addr add {expected_ip}/24 dev eth1 && ip link set eth1 up`")

    passed = score >= 0.8
    return {
        "passed": passed,
        "score": round(score, 2),
        "feedback": feedback,
        "competencies": competencies,
    }
