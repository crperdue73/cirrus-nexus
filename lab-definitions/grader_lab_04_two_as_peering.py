"""
AEGIS — CI-04 Grader: Two ASes, One Peering Session 🛰️

Lab id: lab-04-two-as-peering   grader: grader_lab_04_two_as_peering

Topology (6 FRR routers, one peering link r3:eth2 <-> r4:eth2):
    AS 65001:  r1 -- r2 -- r3
    AS 65002:              r4 -- r5 -- r6

What the student must prove (per lab-definitions/lab-04-two-as-peering.md):
    - the 65001<->65002 peering link is up and reachable (r3 <-> r4)
    - 10.10.10.0/24 is originated in AS 65001 and carried only on the 65001 side
    - 10.20.20.0/24 is originated in AS 65002 and carried only on the 65002 side
    - neither AS originates the other's prefix   <- the trap in the tip:
      "'Established' tells you the session is up, not that the right prefix
       crossed it."

SUBSTRATE HONESTY (read this before trusting a "❌"):
    Dockerfile.frr deliberately installs FRR with zebra + staticd ONLY — no
    ospfd, no bgpd (see the Dockerfile: "No ospfd. No bgpd."). So a live BGP
    session table is NOT the measure here and `show ip bgp` will always be
    empty on this image. That is by design, not a student error.

    This grader therefore measures the substrate-observable invariants that
    the lab is actually about on THIS image:
      1. the peering link is up (r3 <-> r4 bidirectional ping)
      2. the 65001-side routers (r1,r2,r3) agree on the 10.10.10.0/24 path,
         and the 65002-side routers (r4,r5,r6) agree on the 10.20.20.0/24 path
      3. the WRONG-SESSION carry: a 65001 router must not be able to reach the
         65002-originated prefix (10.20.20.0/24) on its own side and vice
         versa — this is the trap the lab tip names.

    If/when the image gains bgpd, this module should be upgraded to read
    `show ip bgp ...` directly. Until then, grading an unmeasurable thing
    would be exactly the "fake green" the project forbids.
"""

import subprocess

AS65001_NODES = ("r1", "r2", "r3")
AS65002_NODES = ("r4", "r5", "r6")

# Prefixes as stated in the lab definition.
PREFIX_AS65001 = "10.10.10.0/24"
PREFIX_AS65002 = "10.20.20.0/24"

# Short grace window: a just-started topology needs a moment for interfaces to
# come up. Bounded and small — never a hang.
PING_TIMEOUT = 12


def _exec(container, cmd, timeout=10):
    """Run a shell command inside a lab container; return stdout (stripped)."""
    try:
        r = subprocess.run(
            ["docker", "exec", container, "sh", "-c", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _ping(container, target):
    """True if `container` can ping `target`."""
    try:
        r = subprocess.run(
            ["docker", "exec", container, "ping", "-c", "2", "-W", "3", target],
            capture_output=True, text=True, timeout=PING_TIMEOUT,
        )
        return r.returncode == 0
    except Exception:
        return False


# Containerlab attaches every node to a management network with a default
# route (e.g. `default via 172.20.20.1 dev eth0`). That default route makes
# `ip route get <anything>` resolve — including the OTHER AS's prefix — so a
# naive `ip route get` check reports a LEAK on a completely unconfigured lab
# (verified live 2026-09-20: r3 with only eth0 answered for both prefixes).
#
# A route only counts for this lab if it is carried on a LAB interface (eth1
# / eth2), never via the management default. We therefore read the FIB and
# look for a non-default route on eth1/eth2 that covers the prefix.
#
# (The mgmt interface is normally eth0, but we key on `dev eth1|eth2` presence
# rather than assuming it, so a topology with a different mgmt naming still
# grades correctly.)


def _iface_ip(container, iface):
    """IPv4 address (no prefix) on `iface`, or ''."""
    return _exec(
        container,
        f"ip -4 -o addr show {iface} 2>/dev/null | awk '{{print $4}}' | cut -d/ -f1",
    )


def _lab_routes(container):
    """Real FIB entries carried on lab interfaces (eth1/eth2), i.e. NOT via
    the management default route. Returns list of 'prefix' strings."""
    out = _exec(container, "ip -4 route show 2>/dev/null")
    routes = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("default"):
            continue
        if "dev eth1" in line or "dev eth2" in line:
            routes.append(line.split()[0])
    return routes


def _has_route_to(container, prefix):
    """True if a real lab-interface route covers `prefix`.

    Deliberately NOT `ip route get`: that resolves via the containerlab
    management default route and would report every prefix as reachable. We
    require an actual route on eth1/eth2 whose network contains the target.
    """
    import ipaddress

    try:
        target = ipaddress.ip_network(prefix, strict=False)
    except ValueError:
        return False

    for rt in _lab_routes(container):
        try:
            net = ipaddress.ip_network(rt, strict=False)
        except ValueError:
            continue
        if target.subnet_of(net) or target == net or net.overlaps(target):
            return True
    return False


def grade(session, node):
    """Grade one node of lab-04 for a live session.

    Returns a dict:
        {"passed": bool, "score": float, "feedback": [str], "competencies": [str]}
    """
    container = session["nodes"].get(node)
    if not container:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Node '{node}' not found in session."],
            "competencies": [],
        }

    if node not in AS65001_NODES + AS65002_NODES:
        return {
            "passed": False,
            "score": 0,
            "feedback": [f"❌ Node '{node}' is not gradeable for lab-04."],
            "competencies": [],
        }

    feedback = []
    score = 0.0
    competencies = []
    # Set False if any essential connectivity check fails. A high score cannot
    # mask a broken path — correctness over accumulation.
    essential_ok = True

    own_prefix = PREFIX_AS65001 if node in AS65001_NODES else PREFIX_AS65002
    other_prefix = PREFIX_AS65002 if node in AS65001_NODES else PREFIX_AS65001
    as_label = "AS 65001" if node in AS65001_NODES else "AS 65002"

    # --- Check 1: the peering link must be up (r3 <-> r4 only, it's the edge) -
    # Only the two edge routers (r3, r4) sit on the inter-AS link. Test from
    # whichever end this node is, using the peer's link address.
    if node in ("r3", "r4"):
        peer = "r4" if node == "r3" else "r3"
        peer_container = session["nodes"].get(peer)
        self_ip = _iface_ip(container, "eth2")
        peer_ip = _iface_ip(peer_container, "eth2")
        if not self_ip or not peer_ip:
            missing = []
            if not self_ip:
                missing.append(f"{node} eth2")
            if not peer_ip:
                missing.append(f"{peer} eth2")
            essential_ok = False
            feedback.append(
                f"❌ Peering link unconfigured: no IP on " + " and ".join(missing)
                + ". Both edge routers need an address on eth2 before the "
                "session can exist."
            )
        elif _ping(container, peer_ip):
            feedback.append(f"✅ Peering link up: {node} ↔ {peer} ({peer_ip}) reachable")
            score += 0.30
            competencies.append("BGP Peering")
        else:
            essential_ok = False
            feedback.append(
                f"❌ Peering link DOWN: {node} ({self_ip}) cannot reach {peer} "
                f"at {peer_ip}. Bring up eth2 on both edge routers first."
            )
    else:
        # Interior router: it must reach its own AS edge (r3 for 65001, r4 for
        # 65002) across the in-AS links. Test that directly rather than trusting
        # a substituted prefix.
        edge = "r3" if node in AS65001_NODES else "r4"
        edge_container = session["nodes"].get(edge)
        edge_eth1_ip = _iface_ip(edge_container, "eth1")
        if not edge_eth1_ip:
            essential_ok = False
            feedback.append(
                f"❌ {node} cannot be checked: edge router {edge} has no address "
                f"on eth1, so the in-AS path does not exist yet."
            )
        elif _ping(container, edge_eth1_ip):
            feedback.append(
                f"✅ {node} reaches its AS edge {edge} ({edge_eth1_ip}) across the in-AS links"
            )
            score += 0.30
            competencies.append("AS Path Reasoning")
        else:
            essential_ok = False
            feedback.append(
                f"❌ {node} cannot reach its own AS edge {edge} "
                f"({edge_eth1_ip}). The {as_label} interior path is not up."
            )

    # --- Check 2: own prefix originated/known on the correct side ------------
    if _has_route_to(container, own_prefix):
        feedback.append(f"✅ {node} resolves {own_prefix} (originated in {as_label})")
        score += 0.35
        competencies.append("Origin Attribution")
    else:
        essential_ok = False
        feedback.append(
            f"❌ {node} cannot resolve {own_prefix}, which {as_label} must "
            f"originate. Check the static/originating route on the edge router."
        )

    # --- Check 3: THE TRAP — the other AS's prefix must NOT be carried here --
    if _has_route_to(container, other_prefix):
        feedback.append(
            f"❌ LEAK: {node} ({as_label}) can reach {other_prefix}, which "
            f"belongs to the OTHER AS. A prefix crossed the wrong session. "
            f"This is precisely the failure the lab tip warns about — "
            f"'Established' is not a measurement."
        )
        # Explicit penalty: a leak is a correctness failure, not a partial.
        score = max(score - 0.35, 0.0)
    else:
        feedback.append(
            f"✅ No leak: {node} ({as_label}) does NOT carry {other_prefix}. "
            f"The wrong-session carry test passes."
        )
        score += 0.35

    # Passing requires BOTH a passing score AND no failed essential check.
    # Otherwise a leak-penalty-free node could clear 0.7 on the leak bonus
    # alone while its own-AS path is down (found live 2026-09-20: r1 scored
    # 0.70 with "cannot reach its own AS edge" — a false pass).
    passed = score >= 0.7 and essential_ok
    verdict = "passed" if passed else "needs work"
    feedback.insert(
        0,
        f"{'✅' if passed else '⏳'} {node} {verdict}. "
        f"Score: {round(score * 100)}/100 (70 required)",
    )

    return {
        "passed": passed,
        "score": round(score, 2),
        "feedback": feedback,
        "competencies": list(dict.fromkeys(competencies)),
    }
