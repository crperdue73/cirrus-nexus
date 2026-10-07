"""
AEGIS — Lab 02 Grader: The Switch in the Middle 🖧

Expected config (4 nodes):
  pc-a: 10.0.1.10/24 on eth1, gateway 10.0.1.1
  sw1: hostname SW1, enable secret, SVI br0 10.0.1.2/24, gateway 10.0.1.1
  r1: hostname R1, enable secret, eth1 10.0.2.1/24, eth2 10.0.1.1/24
  pc-b: 10.0.2.10/24 on eth1, gateway 10.0.2.1
  Full path: pc-a → sw1 → r1 → pc-b (ping across subnets through a switch)
"""

import subprocess


def _exec(cn, cmd):
    r = subprocess.run(["docker", "exec", cn, "sh", "-c", cmd],
                       capture_output=True, text=True, timeout=10)
    return r.stdout.strip()


def _ping(cn, target):
    r = subprocess.run(["docker", "exec", cn, "ping", "-c", "2", "-W", "3", target],
                       capture_output=True, text=True, timeout=10)
    return r.returncode == 0


def _check_ip(cn, iface, expected):
    out = _exec(cn, f"ip -j addr show {iface} 2>/dev/null || ip addr show {iface}")
    return expected in out


def grade(session, node):
    cn = session["nodes"].get(node)
    if not cn:
        return {"passed": False, "score": 0, "feedback": [f"❌ Node '{node}' not found."], "competencies": []}

    fb = []
    sc = 0.0
    comps = []

    if node == "pc-a":
        if _check_ip(cn, "eth1", "10.0.1.10/24"):
            fb.append("✅ PC-A = 10.0.1.10/24")
            sc += 0.25
        else:
            fb.append("❌ Missing 10.0.1.10/24 on eth1")

        gw = _exec(cn, "ip route show default 2>/dev/null")
        if "via 10.0.1.1" in gw:
            fb.append("✅ PC-A gateway = 10.0.1.1")
            sc += 0.15
        else:
            fb.append("❌ Missing default route")

        if _ping(cn, "10.0.1.2"):
            fb.append("✅ PC-A → SW1 SVI ok")
            sc += 0.15
        else:
            fb.append("⚠️  Can't reach SW1 (10.0.1.2)")

        if _ping(cn, "10.0.1.1"):
            fb.append("✅ PC-A → R1 through switch ok")
            sc += 0.15
        else:
            fb.append("⚠️  Can't reach R1 (10.0.1.1)")

        if _ping(cn, "10.0.2.10"):
            fb.append("✅ PC-A → PC-B across subnet + switch = success!")
            sc += 0.30
            comps.append("End-to-End L2/L3 Forwarding")
        else:
            fb.append("⚠️  Can't reach PC-B (10.0.2.10). Check R1 + PC-B config.")

    elif node == "pc-b":
        if _check_ip(cn, "eth1", "10.0.2.10/24"):
            fb.append("✅ PC-B = 10.0.2.10/24")
            sc += 0.25
        else:
            fb.append("❌ Missing 10.0.2.10/24 on eth1")

        gw = _exec(cn, "ip route show default 2>/dev/null")
        if "via 10.0.2.1" in gw:
            fb.append("✅ PC-B gateway = 10.0.2.1")
            sc += 0.15
        else:
            fb.append("❌ Missing default route")

        if _ping(cn, "10.0.2.1"):
            fb.append("✅ PC-B → R1 ok")
            sc += 0.15
        else:
            fb.append("⚠️  Can't reach R1 (10.0.2.1)")

        if _ping(cn, "10.0.1.10"):
            fb.append("✅ PC-B → PC-A across subnet + switch = success!")
            sc += 0.35
            comps.append("End-to-End L2/L3 Forwarding")
        else:
            fb.append("⚠️  Can't reach PC-A (10.0.1.10). Check R1 + SW1 + PC-A config.")

    elif node == "r1":
        v = _exec(cn, "vtysh -c 'show running-config' 2>/dev/null")

        if "hostname R1" in v:
            fb.append("✅ R1 hostname set")
            sc += 0.10
        else:
            fb.append("❌ Hostname not 'R1'")

        if "enable secret" in v or "enable password" in v:
            fb.append("✅ Enable password configured")
            sc += 0.10
        else:
            fb.append("⚠️  No enable password")

        eth1_ok = "interface eth1" in v and "10.0.2.1/24" in v
        eth2_ok = "interface eth2" in v and "10.0.1.1/24" in v

        if eth1_ok:
            fb.append("✅ R1 eth1 = 10.0.2.1/24")
            sc += 0.20
        else:
            fb.append("❌ eth1 expected 10.0.2.1/24")

        if eth2_ok:
            fb.append("✅ R1 eth2 = 10.0.1.1/24")
            sc += 0.20
        else:
            fb.append("❌ eth2 expected 10.0.1.1/24")

        routes = _exec(cn, "vtysh -c 'show ip route' 2>/dev/null")
        conns = routes.count("C>") + routes.count("C ")
        if conns >= 2:
            fb.append(f"✅ {conns} connected routes")
            sc += 0.15
            comps.append("Multi-Interface Router Configuration")
        else:
            fb.append(f"⚠️  Only {conns} connected routes, expected 2")

        if _ping(cn, "10.0.1.10") and _ping(cn, "10.0.2.10"):
            fb.append("✅ R1 can reach both PCs")
            sc += 0.15
        else:
            fb.append("⚠️  R1 can't reach one or both PCs")

    elif node == "sw1":
        v = _exec(cn, "vtysh -c 'show running-config' 2>/dev/null")

        if "hostname SW1" in v:
            fb.append("✅ SW1 hostname set")
            sc += 0.10
        else:
            fb.append("❌ Hostname not 'SW1'")

        if "enable secret" in v or "enable password" in v:
            fb.append("✅ Enable password configured")
            sc += 0.10
        else:
            fb.append("⚠️  No enable password")

        if "interface br0" in v and "10.0.1.2/24" in v:
            fb.append("✅ SW1 SVI br0 = 10.0.1.2/24")
            sc += 0.20
        else:
            fb.append("❌ SVI br0 not configured (expected 10.0.1.2/24)")

        gw = _exec(cn, "ip route show default 2>/dev/null")
        if "via 10.0.1.1" in gw:
            fb.append("✅ SW1 gateway = 10.0.1.1")
            sc += 0.15
        else:
            fb.append("❌ Missing default route via 10.0.1.1")

        fdb = _exec(cn, "bridge fdb show 2>/dev/null | wc -l")
        if int(fdb) > 2:
            fb.append(f"✅ Bridge has {fdb} FDB entries — MACs learning")
            sc += 0.10
        else:
            fb.append("⚠️  Low FDB count — may need to generate traffic")

        if _ping(cn, "10.0.1.1"):
            fb.append("✅ SW1 → R1 reachable")
            sc += 0.15
        else:
            fb.append("⚠️  SW1 can't reach R1")

        if _ping(cn, "10.0.1.10"):
            fb.append("✅ SW1 → PC-A reachable")
            sc += 0.10
            comps.append("L2 Switching & SVI Configuration")
        else:
            fb.append("⚠️  SW1 can't reach PC-A on local subnet")

    else:
        return {"passed": False, "score": 0, "feedback": [f"❌ Unknown node: {node}"], "competencies": []}

    ok = sc >= 0.7
    fb.insert(0, f"{'✅' if ok else '⏳'} {node} {'passed' if ok else 'needs work'}. Score: {round(sc*100)}/100 (70 required)")
    return {"passed": ok, "score": round(sc, 2), "feedback": fb, "competencies": list(set(comps))}
