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


ADVICE = (" Re-checking will NOT rebuild the link: restart the lab (End Lab, then Start Lab) "
          "and reconfigure.")


def _iface_missing(container, dev):
    """True if `dev` does not exist on the node at ALL (so nothing can be read from it).

    Found live 2026-10-04 (run 179). containerlab wires the hosts to the switch with veth
    pairs, so stopping a switch destroys its netns and takes the hosts' `eth1` with it. The
    address check then fell through to "<ip> not found on eth1" -- asserting a fact about a
    device that does not exist, which reads to a student as "you configured it wrong". A
    missing device cannot be caused by misconfiguring it (you cannot delete eth1 with `ip`),
    so it is never a verdict about their work. (The plain-output branch also swallows
    `ip addr show`'s error because of the `|| true`, so the error text had to be read.)
    """
    rc, out, err = _exec(container, f"ip link show {dev} 2>&1 || true")
    blob = f"{out} {err}".lower()
    if "does not exist" in blob or "can't find device" in blob or "cannot find device" in blob:
        return True
    return rc != 0 or not out


def _refuse_missing_link(node, detail):
    """A refused grade whose reason is a MISSING LINK, not a wrong configuration."""
    return {
        "passed": False,
        "score": 0,
        "status": "refused",
        "feedback": [f"\u26a0\ufe0f {node}: {detail}"],
        "competencies": [],
    }


def _node_ip_ok(container, ip, dev, prefixlen=24):
    """True if `ip/prefixlen` is configured on `dev` (linux node).

    Prefix length MATTERS. Before 2026-09-28 this compared only the address and
    threw the mask away (`split("/")[0]`), so a wrong mask (/32) was reported as
    /24 and scored full credit. Same defect fixed in the LAB-A grader the same
    day; both graders share this helper. A grader may not claim a mask it did
    not verify.

    BusyBox `ip` (the Alpine host image) does NOT support `-j`/JSON, so we
    try JSON first (iproute2 hosts), then fall back to a plain `ip addr show`
    and match the address string against the interface's parsed output.
    """
    # RUN 179: a MISSING interface is not a configuration verdict. Report it as a refusal
    # (the route renders refusals as 409 "Cannot grade") instead of "not found on <dev>".
    if _iface_missing(container, dev):
        return None, (f"{dev} does not exist on this node \u2014 its link is gone (a switch or "
                      f"peer was stopped, or the lab was torn down). Nothing can be read from "
                      f"it, so this is not a verdict about your configuration."
                      + ADVICE)
    want = f"{ip}/{prefixlen}"
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
                        got = addr.get("prefixlen")
                        if got == prefixlen:
                            return True, f"{dev} has {want}"
                        return False, f"{dev} has {ip}/{got}, expected {want}"
            return False, f"{ip} not found on {dev}"

    # Fallback: plain text output (BusyBox ip). Match the address INCLUDING mask.
    rc, out, err = _exec(container, f"ip addr show {dev} 2>&1 || true")
    if rc != 0 or not out:
        return False, f"could not read {dev} on {container}: {err or 'no output'}"
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("inet", "inet6"):
            spec = parts[1]
            if spec == want:
                return True, f"{dev} has {want}"
            if spec.split("/")[0] == ip:
                return False, f"{dev} has {spec}, expected {want}"
    return False, f"{ip} not found on {dev}"


def _ip_forward_ok(container):
    rc, out, err = _exec(container, "cat /proc/sys/net/ipv4/ip_forward")
    if rc != 0:
        return False, f"could not read ip_forward: {err}"
    return out.strip() == "1", f"ip_forward={out.strip()}"


def _ping_from(container, target):
    rc, out, err = _exec(container, f"ping -c 2 -W 2 {target}")
    return rc == 0, (out or err)


def _container_kind(container):
    """The containerlab node KIND label for `container` (host-side docker inspect).

    Identity, not output. A node's kind is stamped by containerlab at creation and cannot be
    changed from inside the container, so it distinguishes a real SR Linux switch from a plain
    container that merely *prints* switch-like text. (Added 2026-10-02: the switch check was
    output-only and could be satisfied by faking sr_cli output.)
    """
    try:
        r = subprocess.run(
            ["docker", "inspect", "-f", '{{ index .Config.Labels "clab-node-kind" }}', container],
            capture_output=True, text=True, timeout=15,
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _srl_irb_ok(container, ip):
    """True if `container` is a REAL SR Linux switch with `ip` on irb0.0.

    Uses sr_cli, so a Linux bridge masquerading as a switch cannot pass.
    Refuses (not a soft-fail) if sr_cli is missing — that means the node is
    not a real switch, which is exactly what we must report.
    """
    kind = _container_kind(container)
    if kind != "nokia_srlinux":
        return False, ("not a real SR Linux switch "
                       f"(clab-node-kind={kind or 'absent'})")
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
            if ok is None:
                return _refuse_missing_link(node, detail)
            if ok:
                feedback.append(f"✅ r1: {detail}")
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
    if ok is None:
        return _refuse_missing_link(node, detail)
    if ok:
        feedback.append(f"✅ {node}: {detail}")
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


# RUN 227 (2026-10-06): stamp every per-node result with the node that was ACTUALLY GRADED -- here, at
# the point of grading, not at the call site. Stamping at the call site would let a mislabelled caller
# stamp itself consistent; stamping the graded node means the caller (backend/main.py) can compare the
# name a result claims against the key it was filed under and refuse a mismatch.
def _self_identifying(fn):
    def _wrapped(session, node):
        res = fn(session, node)
        if isinstance(res, dict):
            res.setdefault("node", node)
        return res
    return _wrapped


grade = _self_identifying(grade)
