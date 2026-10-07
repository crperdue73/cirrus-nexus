"""
AEGIS — Lab 03 Grader: Lock It Down 🔒🌐

Expected config:
  rtr: SSH, hostname, enable secret, dual-stack interfaces, ipv6 unicast-routing
  sw1: hostname, enable secret, SVI br0 dual-stack, default gateway, port security
  pc-a: 192.168.12.10/25, SLAAC IPv6, gateway 192.168.12.1
  pc-b: 192.168.12.138/28, SLAAC IPv6, gateway 192.168.12.129
  SSH from PCs to RTR must work
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


def _ping6(cn, target):
    r = subprocess.run(["docker", "exec", cn, "ping", "-6", "-c", "2", "-W", "3", target],
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
            sc += 0.05
        else:
            fb.append("❌ Hostname not 'RTR'")

        if "enable secret" in v or "enable password" in v:
            fb.append("✅ Enable password configured")
            sc += 0.05
        else:
            fb.append("❌ No enable password")

        if "banner motd" in v:
            fb.append("✅ MOTD banner configured")
            sc += 0.05
        else:
            fb.append("⚠️  No MOTD banner")

        if "transport ssh" in v or "line vty" in v:
            fb.append("✅ VTY SSH transport configured")
            sc += 0.10
        else:
            fb.append("⚠️  VTY SSH transport not found")

        # Dual-stack interface eth1 (Subnet B: 192.168.12.129/28)
        eth1_v4 = "interface eth1" in v and "192.168.12.129/28" in v
        eth1_v6 = "interface eth1" in v and "2001:db8:1::1/64" in v
        if eth1_v4 and eth1_v6:
            fb.append("✅ RTR eth1 dual-stack configured")
            sc += 0.15
        else:
            fb.append(f"{'⚠️' if eth1_v4 or eth1_v6 else '❌'} eth1: IPv4={'ok' if eth1_v4 else 'missing'}, IPv6={'ok' if eth1_v6 else 'missing'}")

        # Dual-stack interface eth2 (Subnet A: 192.168.12.1/25)
        eth2_v4 = "interface eth2" in v and "192.168.12.1/25" in v
        eth2_v6 = "interface eth2" in v and "2001:db8:2::1/64" in v
        if eth2_v4 and eth2_v6:
            fb.append("✅ RTR eth2 dual-stack configured")
            sc += 0.15
        else:
            fb.append(f"{'⚠️' if eth2_v4 or eth2_v6 else '❌'} eth2: IPv4={'ok' if eth2_v4 else 'missing'}, IPv6={'ok' if eth2_v6 else 'missing'}")

        # IPv6 unicast-routing
        if "ipv6 unicast-routing" in v:
            fb.append("✅ IPv6 unicast-routing enabled")
            sc += 0.05
        else:
            fb.append("❌ IPv6 routing not enabled (needed for RA)")

        # SSH daemon
        sshd = _exec(cn, "netstat -tlnp 2>/dev/null | grep -c ':22 ' || ss -tlnp | grep -c ':22 '")
        if int(sshd or 0) > 0:
            fb.append("✅ SSH daemon listening on port 22")
            sc += 0.10
        else:
            fb.append("❌ SSH not running. Start with: `sshd`")

        # Check admin user exists
        users = _exec(cn, "cat /etc/passwd 2>/dev/null | grep -c '^admin:'")
        if int(users or 0) > 0:
            fb.append("✅ 'admin' Linux user exists")
            sc += 0.05
        else:
            fb.append("⚠️  'admin' user not found")

        # Routes
        ipv4_routes = _exec(cn, "vtysh -c 'show ip route' 2>/dev/null")
        ipv6_routes = _exec(cn, "vtysh -c 'show ipv6 route' 2>/dev/null")
        v4_conn = ipv4_routes.count("C>") + ipv4_routes.count("C ")
        v6_conn = ipv6_routes.count("C>") + ipv6_routes.count("C ")
        if v4_conn >= 2:
            fb.append(f"✅ {v4_conn} IPv4 connected routes")
            sc += 0.05
        if v6_conn >= 2:
            fb.append(f"✅ {v6_conn} IPv6 connected routes")
            sc += 0.05

        # Verify IPv6 RA is being sent
        ra_check = _exec(cn, "vtysh -c 'show ipv6 interface' 2>/dev/null")
        if "RA" in ra_check or "advertise" in ra_check.lower():
            fb.append("✅ Router Advertisements active")
            sc += 0.05
            comps.append("IPv6 SLAAC & Dual-Stack")
        else:
            fb.append("⚠️  RA status unclear — check `show ipv6 interface`")

        comps.append("SSH Configuration & Device Security")

    elif node == "sw1":
        v = _exec(cn, "vtysh -c 'show running-config' 2>/dev/null")

        if "hostname SW1" in v:
            fb.append("✅ SW1 hostname set")
            sc += 0.05
        else:
            fb.append("❌ Hostname not 'SW1'")

        if "enable secret" in v or "enable password" in v:
            fb.append("✅ Enable password configured")
            sc += 0.05
        else:
            fb.append("⚠️  No enable password")

        if "banner motd" in v:
            fb.append("✅ MOTD banner configured")
            sc += 0.05
        else:
            fb.append("⚠️  No MOTD banner")

        # SVI br0 dual-stack
        br0_v4 = "interface br0" in v and "192.168.12.2/25" in v
        br0_v6 = "interface br0" in v and "2001:db8:2::2/64" in v
        if br0_v4 and br0_v6:
            fb.append("✅ SW1 SVI br0 dual-stack configured")
            sc += 0.15
        else:
            fb.append(f"{'⚠️' if br0_v4 or br0_v6 else '❌'} br0 SVI: IPv4={'ok' if br0_v4 else 'missing'}, IPv6={'ok' if br0_v6 else 'missing'}")

        # Default gateway
        gw = _exec(cn, "ip route show default 2>/dev/null")
        if "via 192.168.12.1" in gw:
            fb.append("✅ SW1 default gateway set")
            sc += 0.10
        else:
            fb.append("❌ Missing default route via 192.168.12.1")

        # Port security: eth3-eth6 should be shut down
        ib = _exec(cn, "vtysh -c 'show ip interface brief' 2>/dev/null")
        ports_shut = 0
        for p in ["eth3", "eth4", "eth5", "eth6"]:
            if p in ib:
                # Find the line for this port and check if it says "down"
                lines = ib.split("\n")
                for line in lines:
                    if line.strip().startswith(p):
                        if "down" in line.lower():
                            ports_shut += 1
                        break

        if ports_shut >= 3:
            fb.append(f"✅ Port security: {ports_shut}/4 unused ports shut down")
            sc += 0.15
        elif ports_shut > 0:
            fb.append(f"⚠️  Only {ports_shut}/4 unused ports shut down")
            sc += 0.05
        else:
            fb.append("❌ No port security — all unused ports still up")

        # Bridge FDB showing learning
        fdb = _exec(cn, "bridge fdb show br br0 2>/dev/null | grep -v 'permanent'")
        fdb_count = len([l for l in fdb.split("\n") if l.strip()])
        if fdb_count > 0:
            fb.append(f"✅ Bridge learning: {fdb_count} dynamic MAC entries")
            sc += 0.10
        else:
            fb.append("⚠️  No dynamic MACs — may need to generate traffic")

        # Connectivity checks
        if _ping(cn, "192.168.12.1"):
            fb.append("✅ SW1 → RTR IPv4 ok")
            sc += 0.05
        else:
            fb.append("⚠️  SW1 can't reach RTR gateway")

        if _ping(cn, "192.168.12.10"):
            fb.append("✅ SW1 → PC-A locally ok")
            sc += 0.05
        else:
            fb.append("⚠️  SW1 can't reach PC-A")

        comps.append("Port Security & L2 Hardening")
        comps.append("IPv6 SLAAC & Dual-Stack")

    elif node == "pc-a":
        # IPv4
        ip = _exec(cn, "ip -4 addr show eth1 | grep -oP 'inet \\K[^/]+' 2>/dev/null")
        if ip == "192.168.12.10":
            fb.append("✅ PC-A IPv4 = 192.168.12.10")
            sc += 0.15
        else:
            fb.append(f"❌ PC-A IPv4 expected 192.168.12.10, got '{ip or 'none'}'")

        mask = _exec(cn, "ip -4 addr show eth1 | grep -oP 'inet \\K[^ ]+' 2>/dev/null")
        if "/25" in mask:
            fb.append("✅ PC-A subnet mask /25 correct")
            sc += 0.05
        else:
            fb.append("⚠️  PC-A expected /25 mask")

        # IPv6 SLAAC
        ip6 = _exec(cn, "ip -6 addr show eth1 scope global 2>/dev/null | grep -oP '2001:db8:2:[^/]+' | head -1")
        if ip6:
            fb.append(f"✅ PC-A IPv6 SLAAC: {ip6}")
            sc += 0.15
        else:
            fb.append("❌ No SLAAC IPv6 address on eth1")

        # Gateway
        gw = _exec(cn, "ip route show default 2>/dev/null")
        if "via 192.168.12.1" in gw:
            fb.append("✅ PC-A gateway set")
            sc += 0.05
        else:
            fb.append("❌ Missing default route")

        # IPv4 connectivity
        if _ping(cn, "192.168.12.1"):
            fb.append("✅ PC-A → RTR (v4) ok")
            sc += 0.10
        else:
            fb.append("⚠️  PC-A can't ping gateway")

        if _ping(cn, "192.168.12.138"):
            fb.append("✅ PC-A → PC-B (v4) across RTR ok")
            sc += 0.10
        else:
            fb.append("⚠️  PC-A → PC-B v4 failed")

        # SSH test
        ssh = subprocess.run(
            ["docker", "exec", cn, "sh", "-c",
             "echo cisco | timeout 5 sshpass -p cisco ssh -o StrictHostKeyChecking=no admin@192.168.12.1 'echo SSH_OK' 2>/dev/null || "
             "echo cisco | timeout 5 ssh -o StrictHostKeyChecking=no admin@192.168.12.1 'echo SSH_OK' 2>/dev/null"],
            capture_output=True, text=True, timeout=15
        )
        if "SSH_OK" in ssh.stdout or "SSH_OK" in ssh.stderr:
            fb.append("✅ PC-A SSH to RTR confirmed!")
            sc += 0.15
            comps.append("SSH Configuration & Device Security")
        else:
            fb.append("⚠️  SSH from PC-A to RTR failed (may need sshpass)")

        # IPv6 ping through
        rtr_ip6 = "2001:db8:2::1"
        if _ping6(cn, rtr_ip6):
            fb.append("✅ PC-A → RTR (v6) ok")
            sc += 0.10
        else:
            fb.append("⚠️  PC-A → RTR v6 failed (check RA + SLAAC)")

        rtr_ip6_b = "2001:db8:1::1"
        if _ping6(cn, rtr_ip6_b):
            fb.append("✅ PC-A → RTR eth1 (v6) through RTR ok")
            sc += 0.10
            comps.append("IPv6 SLAAC & Dual-Stack")
        else:
            fb.append("⚠️  PC-A → RTR eth1 v6 failed")

    elif node == "pc-b":
        # IPv4
        ip = _exec(cn, "ip -4 addr show eth1 | grep -oP 'inet \\K[^/]+' 2>/dev/null")
        if ip == "192.168.12.138":
            fb.append("✅ PC-B IPv4 = 192.168.12.138")
            sc += 0.15
        else:
            fb.append(f"❌ PC-B IPv4 expected 192.168.12.138, got '{ip or 'none'}'")

        mask = _exec(cn, "ip -4 addr show eth1 | grep -oP 'inet \\K[^ ]+' 2>/dev/null")
        if "/28" in mask:
            fb.append("✅ PC-B subnet mask /28 correct")
            sc += 0.05
        else:
            fb.append("⚠️  PC-B expected /28 mask")

        # IPv6 SLAAC
        ip6 = _exec(cn, "ip -6 addr show eth1 scope global 2>/dev/null | grep -oP '2001:db8:1:[^/]+' | head -1")
        if ip6:
            fb.append(f"✅ PC-B IPv6 SLAAC: {ip6}")
            sc += 0.15
        else:
            fb.append("❌ No SLAAC IPv6 address on eth1")

        # Gateway
        gw = _exec(cn, "ip route show default 2>/dev/null")
        if "via 192.168.12.129" in gw:
            fb.append("✅ PC-B gateway set")
            sc += 0.05
        else:
            fb.append("❌ Missing default route via 192.168.12.129")

        # IPv4 connectivity
        if _ping(cn, "192.168.12.129"):
            fb.append("✅ PC-B → RTR (v4) ok")
            sc += 0.10
        else:
            fb.append("⚠️  PC-B can't ping gateway")

        if _ping(cn, "192.168.12.10"):
            fb.append("✅ PC-B → PC-A (v4) across RTR+SW1 ok")
            sc += 0.10
        else:
            fb.append("⚠️  PC-B → PC-A v4 failed")

        # SSH test
        ssh = subprocess.run(
            ["docker", "exec", cn, "sh", "-c",
             "echo cisco | timeout 5 sshpass -p cisco ssh -o StrictHostKeyChecking=no admin@192.168.12.129 'echo SSH_OK' 2>/dev/null || "
             "echo cisco | timeout 5 ssh -o StrictHostKeyChecking=no admin@192.168.12.129 'echo SSH_OK' 2>/dev/null"],
            capture_output=True, text=True, timeout=15
        )
        if "SSH_OK" in ssh.stdout or "SSH_OK" in ssh.stderr:
            fb.append("✅ PC-B SSH to RTR confirmed!")
            sc += 0.15
            comps.append("SSH Configuration & Device Security")
        else:
            fb.append("⚠️  SSH from PC-B to RTR failed")

        # IPv6
        rtr_ip6 = "2001:db8:1::1"
        if _ping6(cn, rtr_ip6):
            fb.append("✅ PC-B → RTR (v6) ok")
            sc += 0.10
        else:
            fb.append("⚠️  PC-B → RTR v6 failed")

        rtr_ip6_a = "2001:db8:2::1"
        if _ping6(cn, rtr_ip6_a):
            fb.append("✅ PC-B → RTR eth2 (v6) via routing ok")
            sc += 0.10
            comps.append("IPv6 SLAAC & Dual-Stack")
        else:
            fb.append("⚠️  PC-B → RTR eth2 v6 failed")

    else:
        return {"passed": False, "score": 0, "feedback": [f"❌ Unknown node: {node}"], "competencies": []}

    ok = sc >= 0.7
    fb.insert(0, f"{'✅' if ok else '⏳'} {node} {'passed' if ok else 'needs work'}. Score: {round(sc*100)}/100 (70 required)")
    return {"passed": ok, "score": round(sc, 2), "feedback": fb, "competencies": list(set(comps))}
