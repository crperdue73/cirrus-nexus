"""
AEGIS — Tier 3 Grader: Router, Switch, and a PC 🖥️🔗🖧

Expected config:
  rtr: hostname RTR, enable secret, eth1 10.0.1.1/24
  sw1: hostname SW1, enable secret, SVI br0 10.0.1.2/24, default gateway 10.0.1.1
  pc-a: 10.0.1.10/24, default gateway 10.0.1.1
  pc-a should ping rtr (10.0.1.1) through the switch
"""

import subprocess


def _exec(container, cmd):
    r = subprocess.run(["docker", "exec", container, "sh", "-c", cmd],
                       capture_output=True, text=True, timeout=10)
    return r.stdout.strip()


def _ping(container, target):
    r = subprocess.run(["docker", "exec", container, "ping", "-c", "2", "-W", "3", target],
                       capture_output=True, text=True, timeout=10)
    return r.returncode == 0


def grade(session, node):
    cn = session["nodes"].get(node)
    if not cn:
        return {"passed": False, "score": 0, "feedback": [f"❌ Node '{node}' not found."], "competencies": []}

    fb = []
    sc = 0.0
    comps = []

    if node == "rtr":
        v = _exec(cn, "vtysh -c 'show running-config' 2>/dev/null")

        if "hostname RTR" in v:
            fb.append("✅ RTR hostname set")
            sc += 0.15
        else:
            fb.append("❌ Hostname not 'RTR'. Set via `hostname RTR` in vtysh config")

        if "enable secret" in v or "enable password" in v:
            fb.append("✅ Enable password configured")
            sc += 0.15
        else:
            fb.append("❌ No enable password. Use `enable secret cisco`")

        if "interface eth1" in v and "10.0.1.1/24" in v:
            fb.append("✅ RTR eth1 = 10.0.1.1/24")
            sc += 0.30
        else:
            fb.append("❌ RTR eth1 not configured. Set `ip address 10.0.1.1/24`")

        routes = _exec(cn, "vtysh -c 'show ip route' 2>/dev/null")
        if "C>" in routes or "C " in routes:
            fb.append("✅ Connected routes present — interface is up")
            sc += 0.15
        else:
            fb.append("⚠️  No connected routes. Check `no shutdown` on eth1")

        if _ping(cn, "10.0.1.2"):
            fb.append("✅ RTR can reach SW1 SVI (10.0.1.2)")
            sc += 0.15
        else:
            fb.append("⚠️  RTR can't reach SW1. Is SW1 configured?")

        if _ping(cn, "10.0.1.10"):
            fb.append("✅ RTR can reach PC-A through switch!")
            sc += 0.10
            comps.append("L2 Forwarding")
        else:
            fb.append("⚠️  RTR can't reach PC-A. Check PC-A config.")

    elif node == "sw1":
        v = _exec(cn, "vtysh -c 'show running-config' 2>/dev/null")

        if "hostname SW1" in v:
            fb.append("✅ SW1 hostname set")
            sc += 0.10
        else:
            fb.append("❌ Hostname not 'SW1'. Set via `hostname SW1`")

        if "enable secret" in v or "enable password" in v:
            fb.append("✅ Enable password configured")
            sc += 0.10
        else:
            fb.append("❌ No enable password. Use `enable secret cisco`")

        if "interface br0" in v and "10.0.1.2/24" in v:
            fb.append("✅ SW1 SVI br0 = 10.0.1.2/24")
            sc += 0.25
        else:
            fb.append("❌ SVI br0 not configured. Set `interface br0` then `ip address 10.0.1.2/24`")

        gw = _exec(cn, "ip route show default 2>/dev/null")
        if "via 10.0.1.1" in gw:
            fb.append("✅ SW1 default gateway set to 10.0.1.1")
            sc += 0.15
        else:
            fb.append("❌ SW1 missing default route. Run `ip route add default via 10.0.1.1`")

        bridge = _exec(cn, "bridge fdb show 2>/dev/null | head -5")
        if bridge:
            fb.append("✅ Bridge forwarding table populated")
            sc += 0.10
        else:
            fb.append("⚠️  Empty FDB — may indicate no traffic yet")

        if _ping(cn, "10.0.1.1"):
            fb.append("✅ SW1 can reach RTR gateway")
            sc += 0.20
            comps.append("SVI & L3 Forwarding")
        else:
            fb.append("⚠️  SW1 can't reach RTR. Check RTR eth1 config.")

    elif node == "pc-a":
        ip = _exec(cn, "ip addr show eth1 | grep -oP 'inet \\K[^/]+' 2>/dev/null")
        if ip == "10.0.1.10":
            fb.append(f"✅ PC-A has IP {ip} on eth1")
            sc += 0.30
        else:
            fb.append(f"❌ PC-A expected 10.0.1.10, got '{ip or 'none'}'")

        gw = _exec(cn, "ip route show default 2>/dev/null")
        if "via 10.0.1.1" in gw:
            fb.append("✅ PC-A default gateway = 10.0.1.1")
            sc += 0.25
        else:
            fb.append("❌ Missing default route via 10.0.1.1")

        if _ping(cn, "10.0.1.2"):
            fb.append("✅ PC-A → SW1 SVI ping ok")
            sc += 0.15
        else:
            fb.append("⚠️  PC-A can't reach SW1 SVI")

        if _ping(cn, "10.0.1.1"):
            fb.append("✅ PC-A → RTR through switch = success!")
            sc += 0.30
            comps.append("End-to-End L2/L3 Forwarding")
        else:
            fb.append("⚠️  PC-A can't reach RTR. Check SW1 bridging + RTR config.")

    else:
        return {"passed": False, "score": 0, "feedback": [f"❌ Unknown node: {node}"], "competencies": []}

    ok = sc >= 0.7
    fb.insert(0, f"{'✅' if ok else '⏳'} {node} {'passed' if ok else 'needs work'}. Score: {round(sc*100)}/100 (70 required)")
    return {"passed": ok, "score": round(sc, 2), "feedback": fb, "competencies": list(set(comps))}
