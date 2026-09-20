"""
AEGIS — Grader: Net Eng I Capstone
Cisco Networking Engineering Technology I — Performance-Based Measurement

Scoring (100 pts total, proficiency at 70+):
  Component 1: Subnetting (27 pts) — checked via form/worksheet
  Component 2: Device Config (67 pts)
    - RTR router:         33 pts
    - SW1 switch:         30 pts
    - PCA / PCB:           4 pts
  Component 3: Connectivity (6 pts)
"""

import json
import re
import subprocess


def _exec(container, cmd):
    """Run a command in a container and return stdout."""
    result = subprocess.run(
        ["docker", "exec", container, "sh", "-c", cmd],
        capture_output=True, text=True, timeout=15
    )
    return result.stdout.strip(), result.returncode


# ─── SHOW-RUN PARSERS ───────────────────────────────────────────────────────

def _has_config_line(show_run, pattern):
    """Check if a pattern appears in show run output."""
    return bool(re.search(pattern, show_run, re.IGNORECASE))


def _get_hostname(show_run):
    m = re.search(r'^hostname\s+(\S+)', show_run, re.MULTILINE)
    return m.group(1) if m else None


# ─── COMPONENT 2a: RTR (33 pts) ────────────────────────────────────────────

def grade_rtr(container):
    """Grade RTR configuration. Returns (score, feedback, competencies)."""
    score = 0.0
    feedback = []
    competencies = set()

    stdout, rc = _exec(container, "vtysh -c 'show run' 2>/dev/null || cat /etc/frr/frr.conf 2>/dev/null || echo 'NO_CONFIG'")
    if rc != 0 or stdout == 'NO_CONFIG':
        feedback.append("❌ Cannot read RTR configuration. Is FRR running?")
        return score, feedback, competencies

    show_run = stdout
    hostname = _get_hostname(show_run)

    # 1. Hostname = RTR (3 pts)
    if hostname and hostname.upper() == "RTR":
        feedback.append("✅ Hostname set to RTR")
        score += 3
    elif hostname:
        feedback.append(f"⚠️  Hostname is '{hostname}', expected 'RTR'")
    else:
        feedback.append("❌ Hostname not set")

    # 2. MOTD Banner (3 pts)
    if r'banner\s+motd' in show_run.lower() or 'banner motd' in show_run.lower():
        if 'Unauthorized Access Prohibited' in show_run or re.search(r'Unauthorized.*Prohibited', show_run):
            feedback.append("✅ MOTD banner set correctly")
            score += 3
        else:
            feedback.append("⚠️  MOTD banner found but text doesn't match expected")
    else:
        feedback.append("❌ MOTD banner not configured")

    # 3. Console + VTY passwords (3 pts)
    if _has_config_line(show_run, r'password\s+ncconskills'):
        feedback.append("✅ Console/VTY password set")
        score += 3
    else:
        feedback.append("❌ Console/VTY password 'ncconskills' not found")

    # 4. Enable secret (3 pts)
    if _has_config_line(show_run, r'enable\s+secret') or _has_config_line(show_run, r'enable secret'):
        if 'ncenskills' in show_run:
            feedback.append("✅ Enable secret set")
            score += 3
        else:
            feedback.append("⚠️  Enable secret configured but value doesn't match 'ncenskills'")
    else:
        feedback.append("❌ Enable secret not configured")

    # 5. Password encryption (3 pts)
    if _has_config_line(show_run, r'service\s+password-encryption'):
        feedback.append("✅ Service password-encryption enabled")
        score += 3
    else:
        feedback.append("❌ Password encryption not enabled")

    # 6. IPv6 routing enabled (3 pts)
    if _has_config_line(show_run, r'ipv6\s+unicast-routing'):
        feedback.append("✅ IPv6 unicast routing enabled")
        score += 3
        competencies.add("IPv6 Routing Configuration")
    else:
        feedback.append("❌ IPv6 unicast routing not enabled")

    # 7. IPv4 interface addressing (3 pts)
    stdout4, _ = _exec(container, "vtysh -c 'show ip int brief' 2>/dev/null || ip -4 addr show 2>/dev/null")
    has_subnet_a = '192.168.12.1' in stdout4  # RTR G0/0/1 (Subnet A)
    has_subnet_b = '192.168.12.129' in stdout4  # RTR G0/0/0 (Subnet B)
    if has_subnet_a and has_subnet_b:
        feedback.append("✅ Both IPv4 interfaces configured correctly")
        score += 3
    elif has_subnet_a or has_subnet_b:
        feedback.append("⚠️  Only one IPv4 interface configured")
    else:
        feedback.append("❌ IPv4 interfaces not configured")

    # 8. IPv6 interface addressing (3 pts)
    stdout6, _ = _exec(container, "vtysh -c 'show ipv6 int brief' 2>/dev/null || ip -6 addr show 2>/dev/null")
    has_ipv6_subnet = '2001:db8:bbad' in stdout6
    has_linklocal = 'fe80::1' in stdout6.lower()
    if has_ipv6_subnet:
        feedback.append("✅ IPv6 interfaces configured with subnet addresses")
        score += 2
        if has_linklocal:
            feedback.append("✅ Link-local address FE80::1 configured")
            score += 1
        else:
            feedback.append("⚠️  Link-local address FE80::1 not found on interfaces")
    else:
        feedback.append("❌ IPv6 interface addresses not configured")

    # 9. SSH config (3 pts) — checking key parts
    ssh_ok = True
    if not _has_config_line(show_run, r'username\s+ncadmin'):
        feedback.append("❌ Username 'ncadmin' not configured for SSH")
        ssh_ok = False
    if not _has_config_line(show_run, r'ip\s+domain-name\s+ncdpi\.com') and \
       not _has_config_line(show_run, r'domain.name.*ncdpi'):
        feedback.append("❌ Domain name 'ncdpi.com' not set (required for SSH key)")
        ssh_ok = False
    if _has_config_line(show_run, r'transport\s+input\s+ssh'):
        feedback.append("✅ VTY transport set to SSH only")
    elif _has_config_line(show_run, r'transport\s+input'):
        feedback.append("⚠️  VTY transport set but not restricted to SSH")
    else:
        feedback.append("⚠️  VTY transport not restricted to SSH (telnet still allowed)")
    if ssh_ok:
        score += 2
    # 3rd SSH point — try actual SSH handshake
    ssh_test, _ = _exec(container, "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 ncadmin@127.0.0.1 2>&1 || true")
    if 'authentication failed' in ssh_test.lower() or 'password' in ssh_test.lower():
        feedback.append("✅ SSH server responding on localhost")
        score += 1
    else:
        feedback.append("⚠️  SSH not responding — check SSH config and keys")
    competencies.add("SSH Configuration")

    # 10. Password min length (3 pts)
    if _has_config_line(show_run, r'security\s+passwords\s+min-length\s+'):
        m = re.search(r'security\s+passwords\s+min-length\s+(\d+)', show_run)
        length = int(m.group(1)) if m else 0
        if length >= 8:
            feedback.append(f"✅ Password minimum length set to {length} (≥ 8)")
            score += 3
        else:
            feedback.append(f"⚠️  Password min-length is {length}, expected ≥ 8")
    else:
        feedback.append("❌ Password minimum length not configured")

    # 11. DNS lookup disabled (3 pts)
    if _has_config_line(show_run, r'no\s+ip\s+domain-lookup') or \
       _has_config_line(show_run, r'no ip domain.lookup'):
        feedback.append("✅ DNS lookup disabled")
        score += 3
    else:
        feedback.append("❌ DNS lookup still enabled (will cause delays on mistyped commands)")

    return score, feedback, competencies


# ─── COMPONENT 2b: SW1 (30 pts) ────────────────────────────────────────────

def grade_sw1(container):
    """Grade SW1 configuration. Returns (score, feedback, competencies)."""
    score = 0.0
    feedback = []
    competencies = set()

    stdout, rc = _exec(container, "vtysh -c 'show run' 2>/dev/null || cat /etc/frr/frr.conf 2>/dev/null || echo 'NO_CONFIG'")
    if rc != 0 or stdout == 'NO_CONFIG':
        feedback.append("❌ Cannot read SW1 configuration")
        return score, feedback, competencies

    show_run = stdout
    hostname = _get_hostname(show_run)
    running_config = show_run

    # 1. Telnet works (3 pts) — check if telnet/SSH listener is up
    telnet_test, _ = _exec(container, "ss -tlnp 2>/dev/null | grep -E ':(23|22)\s' || netstat -tlnp 2>/dev/null | grep -E ':(23|22)\s' || true")
    if '23' in telnet_test or '22' in telnet_test:
        feedback.append("✅ Management access (telnet/SSH) is listening")
        score += 3
    else:
        feedback.append("⚠️  No telnet/SSH listener detected — check VTY lines")

    # 2. MOTD Banner (3 pts)
    if 'Unauthorized Access Prohibited' in running_config or \
       re.search(r'Unauthorized.*Prohibited', running_config):
        feedback.append("✅ MOTD banner set correctly")
        score += 3
    else:
        feedback.append("❌ MOTD banner not configured or text doesn't match")

    # 3. Hostname = SW1 (3 pts)
    if hostname and hostname.upper() == "SW1":
        feedback.append("✅ Hostname set to SW1")
        score += 3
    elif hostname:
        feedback.append(f"⚠️  Hostname is '{hostname}', expected 'SW1'")
    else:
        feedback.append("❌ Hostname not set")

    # 4. Console + VTY passwords (3 pts)
    if 'ncconskills' in running_config and \
       ('password' in running_config or 'login' in running_config):
        feedback.append("✅ Console and VTY passwords configured")
        score += 3
    else:
        feedback.append("❌ Console/VTY passwords not found in config")

    # 5. Enable secret (3 pts)
    if 'ncenskills' in running_config and \
       ('enable secret' in running_config or 'enable' in running_config):
        feedback.append("✅ Enable secret set")
        score += 3
    else:
        feedback.append("❌ Enable secret not configured or value doesn't match")

    # 6. Password encryption (3 pts)
    if 'service password-encryption' in running_config:
        feedback.append("✅ Service password-encryption enabled")
        score += 3
    else:
        feedback.append("❌ Password encryption not enabled")

    # 7. SVI interface IP (3 pts) — VLAN 1 with Subnet A IP
    stdout_ip, _ = _exec(container, "ip -4 addr show 2>/dev/null")
    if '192.168.12.2' in stdout_ip:
        feedback.append("✅ SVI VLAN 1 IP address (192.168.12.2) configured")
        score += 3
    else:
        feedback.append("❌ SVI IP 192.168.12.2 not found on any interface")

    # 8. Default gateway (3 pts)
    if '192.168.12.1' in running_config and \
       ('default-gateway' in running_config or 'default gateway' in running_config.lower() or
        'ip route' in running_config):
        feedback.append("✅ Default gateway configured (192.168.12.1 → RTR)")
        score += 3
    else:
        feedback.append("❌ Default gateway not configured")
    competencies.add("Switch Configuration (SVI, Default Gateway)")

    # 9. Unused ports shutdown (3 pts)
    # Check eth3-eth6 (simulated unused ports)
    ports_down = 0
    for port in ['eth3', 'eth4', 'eth5', 'eth6']:
        state, _ = _exec(container, f"cat /sys/class/net/{port}/operstate 2>/dev/null || echo 'missing'")
        if state.strip() == 'down':
            ports_down += 1
    if ports_down >= 4:
        feedback.append("✅ All 4 unused ports administratively shutdown")
        score += 3
    elif ports_down > 0:
        feedback.append(f"⚠️  {ports_down}/4 unused ports shutdown")
    else:
        feedback.append("❌ Unused ports still up — use 'shutdown' in interface config")

    # 10. Domain name (3 pts)
    if 'ncdpi.com' in running_config and 'domain-name' in running_config:
        feedback.append("✅ Domain name 'ncdpi.com' configured")
        score += 3
    elif 'ncdpi.com' in running_config:
        feedback.append("⚠️  Domain name 'ncdpi.com' found but may not be in correct config context")
    else:
        feedback.append("❌ Domain name 'ncdpi.com' not configured")

    return score, feedback, competencies


# ─── COMPONENT 2c: PCA / PCB (4 pts) ──────────────────────────────────────

def grade_pc(container, expected_ip, expected_gateway, subnet_mask="255.255.255.128"):
    """Grade a PC configuration. Returns (score, feedback)."""
    score = 0.0
    feedback = []

    # Check IPv4 config
    stdout, rc = _exec(container, "ip -4 addr show eth1 2>/dev/null")
    if rc != 0 or not stdout:
        feedback.append("❌ eth1 not found or no IPv4 configured")
        return score, feedback

    if expected_ip in stdout:
        feedback.append(f"✅ IPv4 address {expected_ip} configured")
        score += 1

        # Check prefix
        for line in stdout.split('\n'):
            if expected_ip in line:
                m = re.search(r'/(\d+)', line)
                if m:
                    feedback.append(f"✅ Prefix length /{m.group(1)}")
                    score += 0.5
                break
    else:
        feedback.append(f"❌ Expected IP {expected_ip} not found on eth1")

    # Check gateway
    stdout_gw, _ = _exec(container, "ip route show default 2>/dev/null")
    if expected_gateway in stdout_gw:
        feedback.append(f"✅ Default gateway {expected_gateway} configured")
        score += 0.5
    else:
        feedback.append(f"⚠️  Default gateway not set to {expected_gateway}")

    return score, feedback


# ─── COMPONENT 3: Connectivity (6 pts) ─────────────────────────────────────

def grade_connectivity(session):
    """Test IPv4 and IPv6 ping connectivity. Returns (score, feedback, competencies)."""
    score = 0.0
    feedback = []
    competencies = set()

    pc_a = session["nodes"].get("pc-a")
    pc_b = session["nodes"].get("pc-b")
    rtr = session["nodes"].get("rtr")

    if not all([pc_a, pc_b, rtr]):
        feedback.append("❌ Missing containers for connectivity tests")
        return score, feedback, competencies

    # 1. Ping PCA → RTR G0/0/0 (Subnet B IP)
    ping1, _ = _exec(pc_a, "ping -c 2 -W 3 192.168.12.129 2>/dev/null || echo 'FAIL'")
    if '100% packet loss' not in ping1 and 'FAIL' not in ping1:
        feedback.append("✅ PCA → RTR G0/0/0 (IPv4): Success")
        score += 1
    else:
        feedback.append("❌ PCA → RTR G0/0/0 (IPv4): Failed")

    # 2. Ping PCA → PCB (cross-subnet)
    ping2, _ = _exec(pc_a, "ping -c 2 -W 3 192.168.12.142 2>/dev/null || echo 'FAIL'")
    if '100% packet loss' not in ping2 and 'FAIL' not in ping2:
        feedback.append("✅ PCA → PCB (IPv4 cross-subnet): Success")
        score += 1
    else:
        feedback.append("❌ PCA → PCB (IPv4 cross-subnet): Failed")

    # 3. Ping PCB → SW1
    ping3, _ = _exec(pc_b, "ping -c 2 -W 3 192.168.12.2 2>/dev/null || echo 'FAIL'")
    if '100% packet loss' not in ping3 and 'FAIL' not in ping3:
        feedback.append("✅ PCB → SW1 (IPv4): Success")
        score += 1
    else:
        feedback.append("❌ PCB → SW1 (IPv4): Failed")

    # 4. Ping PCB → RTR G0/0/1 (Subnet A IP)
    ping4, _ = _exec(pc_b, "ping -c 2 -W 3 192.168.12.1 2>/dev/null || echo 'FAIL'")
    if '100% packet loss' not in ping4 and 'FAIL' not in ping4:
        feedback.append("✅ PCB → RTR G0/0/1 (IPv4): Success")
        score += 1
    else:
        feedback.append("❌ PCB → RTR G0/0/1 (IPv4): Failed")

    # 5. PCA IPv6 → RTR G0/0/0
    ping6_1, _ = _exec(pc_a, "ping -6 -c 2 -W 3 2001:db8:bbad::1 2>/dev/null || echo 'FAIL'")
    if '100% packet loss' not in ping6_1 and 'FAIL' not in ping6_1:
        feedback.append("✅ PCA → RTR G0/0/0 (IPv6): Success")
        score += 1
    else:
        feedback.append("❌ PCA → RTR G0/0/0 (IPv6): Failed — check SLAAC and IPv6 routing")

    # 6. PCB IPv6 → RTR G0/0/1
    ping6_2, _ = _exec(pc_b, "ping -6 -c 2 -W 3 2001:db8:bbad:1::1 2>/dev/null || echo 'FAIL'")
    if '100% packet loss' not in ping6_2 and 'FAIL' not in ping6_2:
        feedback.append("✅ PCB → RTR G0/0/1 (IPv6): Success")
        score += 1
    else:
        feedback.append("❌ PCB → RTR G0/0/1 (IPv6): Failed — check SLAAC and IPv6 routing")

    if score >= 4:
        competencies.add("End-to-End Connectivity (IPv4 & IPv6)")

    return score, feedback, competencies


# ─── COMPONENT 1: Subnetting (27 pts) — FORM CHECK ─────────────────────────

def grade_subnetting(answers: dict) -> tuple:
    """
    Grade subnetting worksheet answers.
    Expected answers dict format:
    {
        "subnet_a_network": "192.168.12.0/25",
        "subnet_a_mask": "255.255.255.128",
        "subnet_a_hosts": "126",
        "subnet_a_first": "192.168.12.1",
        "subnet_a_last": "192.168.12.126",
        "subnet_b_network": "192.168.12.128/28",
        "subnet_b_mask": "255.255.255.240",
        "subnet_b_hosts": "14",
        "subnet_b_first": "192.168.12.129",
        "subnet_b_last": "192.168.12.142",
        "pc_a_ip": "192.168.12.126",
        "pc_b_ip": "192.168.12.142",
        "rtr_g000": "192.168.12.129",
        "rtr_g001": "192.168.12.1",
        "sw1_ip": "192.168.12.2",
        "ipv6_subnet_a": "2001:db8:bbad::/64",
        "ipv6_subnet_b": "2001:db8:bbad:1::/64",
    }
    """
    expected = {
        "subnet_a_network":  ("192.168.12.0/25", "192.168.12.0"),
        "subnet_a_mask":     ("255.255.255.128", "/25", "255.255.255.128"),
        "subnet_a_hosts":    ("126",),
        "subnet_a_first":    ("192.168.12.1",),
        "subnet_a_last":     ("192.168.12.126", "192.168.12.126"),
        "subnet_b_network":  ("192.168.12.128/28", "192.168.12.128"),
        "subnet_b_mask":     ("255.255.255.240", "/28", "255.255.255.240"),
        "subnet_b_hosts":    ("14",),
        "subnet_b_first":    ("192.168.12.129",),
        "subnet_b_last":     ("192.168.12.142",),
        "pc_a_ip":           ("192.168.12.126",),
        "pc_b_ip":           ("192.168.12.142",),
        "rtr_g000":          ("192.168.12.129",),
        "rtr_g001":          ("192.168.12.1",),
        "sw1_ip":            ("192.168.12.2",),
        "ipv6_subnet_a":     ("2001:db8:bbad::/64", "2001:db8:bbad:0::/64"),
        "ipv6_subnet_b":     ("2001:db8:bbad:1::/64",),
    }

    score = 0.0
    feedback = []
    point_values = {
        "subnet_a_network": 2, "subnet_a_mask": 2, "subnet_a_hosts": 2,
        "subnet_a_first": 2, "subnet_a_last": 2,
        "subnet_b_network": 2, "subnet_b_mask": 2, "subnet_b_hosts": 2,
        "subnet_b_first": 2, "subnet_b_last": 2,
        "pc_a_ip": 1, "pc_b_ip": 1, "rtr_g000": 1, "rtr_g001": 1, "sw1_ip": 1,
        "ipv6_subnet_a": 1, "ipv6_subnet_b": 1,
    }
    total_possible = sum(point_values.values())

    for key, pv in point_values.items():
        student_answer = answers.get(key, "").strip()
        if student_answer in expected[key]:
            score += pv
            feedback.append(f"✅ {key}: {student_answer} ({pv} pt)")
        else:
            feedback.append(f"❌ {key}: '{student_answer}' — expected one of {expected[key]}")

    return score, total_possible, feedback


# ─── MAIN GRADE FUNCTION ────────────────────────────────────────────────────

def grade(session, node):
    """
    Grade entry point called by AEGIS backend.
    'node' parameter indicates which device/componoent to grade:
      "rtr"     — Grade RTR router (Component 2a)
      "sw1"     — Grade SW1 switch (Component 2b)
      "pc-a"    — Grade PC-A (Component 2c)
      "pc-b"    — Grade PC-B (Component 2c)
      "connect" — Grade connectivity (Component 3)
      "subnet"  — Grade subnetting (Component 1) — requires answers in request
    """
    container_name = session["nodes"].get(node)
    if not container_name and node not in ("connect", "subnet"):
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Node '{node}' not found in session."],
            "competencies": [],
        }

    all_feedback = []
    all_competencies = set()
    total_score = 0.0

    COMPONENT_WEIGHTS = {
        "rtr": {"max": 33, "weight": 0.33},
        "sw1": {"max": 30, "weight": 0.30},
        "pc-a": {"max": 2, "weight": 0.02},
        "pc-b": {"max": 2, "weight": 0.02},
        "connect": {"max": 6, "weight": 0.06},
        "subnet": {"max": 27, "weight": 0.27},
    }

    if node in ("rtr",):
        s, fb, comps = grade_rtr(container_name)
        total_score += s
        all_feedback.append(f"— RTR Router ({s:.0f}/{COMPONENT_WEIGHTS['rtr']['max']} pts) —")
        all_feedback.extend(fb)
        all_competencies.update(comps)

    elif node in ("sw1",):
        s, fb, comps = grade_sw1(container_name)
        total_score += s
        all_feedback.append(f"— SW1 Switch ({s:.0f}/{COMPONENT_WEIGHTS['sw1']['max']} pts) —")
        all_feedback.extend(fb)
        all_competencies.update(comps)

    elif node == "pc-a":
        s, fb = grade_pc(container_name, "192.168.12.126", "192.168.12.1")
        total_score += s * 2  # Scale to 4 pts total for both PCs
        all_feedback.append(f"— PC-A ({s*2:.0f}/{COMPONENT_WEIGHTS['pc-a']['max']*2} pts) —")
        all_feedback.extend(fb)
        all_competencies.add("PC Configuration (IPv4 + SLAAC IPv6)")

    elif node == "pc-b":
        s, fb = grade_pc(container_name, "192.168.12.142", "192.168.12.129",
                         subnet_mask="255.255.255.240")
        total_score += s * 2
        all_feedback.append(f"— PC-B ({s*2:.0f}/{COMPONENT_WEIGHTS['pc-b']['max']*2} pts) —")
        all_feedback.extend(fb)
        all_competencies.add("PC Configuration (IPv4 + SLAAC IPv6)")

    elif node == "connect":
        s, fb, comps = grade_connectivity(session)
        total_score += s
        all_feedback.append(f"— Connectivity ({s:.0f}/{COMPONENT_WEIGHTS['connect']['max']} pts) —")
        all_feedback.extend(fb)
        all_competencies.update(comps)

    elif node == "subnet":
        # Subnetting requires answers dict passed via the submit request body
        # For now, return instructions
        return {
            "passed": False,
            "score": 0,
            "feedback": [
                "📋 Subnetting is graded via worksheet.",
                "Use the IP Addressing Worksheet to calculate:",
                "  • Subnet A: 192.168.12.0/24 → /25 (63 hosts)",
                "  • Subnet B: 192.168.12.0/24 → /28 (10 hosts)",
                "  • IPv6: 2001:db8:bbad::/48 → two /64 subnets",
                "",
                "Then grade individual devices (rtr, sw1, pc-a, pc-b, connect)",
                "to verify your addressing was applied correctly."
            ],
            "competencies": ["IPv4 Subnetting", "IPv6 Addressing"],
        }

    else:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Unknown grading target: {node}"],
            "competencies": [],
        }

    # Calculate percentage against full 100-pt rubric
    # Individual components have different denominators
    weight_map = {
        "rtr": 33, "sw1": 30, "pc-a": 2, "pc-b": 2, "connect": 6
    }
    denominator = weight_map.get(node, 1)
    percentage = (total_score / denominator) * 100 if denominator > 0 else 0
    passed = percentage >= 70

    all_feedback.append("")
    all_feedback.append(f"📊 Score: {total_score:.0f}/{denominator} ({percentage:.0f}%)")
    all_feedback.append(f"{'✅ PASSED' if passed else '❌ NOT YET'} — proficiency requires 70%")

    return {
        "passed": passed,
        "score": round(percentage / 100, 2),
        "feedback": all_feedback,
        "competencies": list(all_competencies),
    }
