"""
AEGIS — DEMO Lab 01 Grader (REAL SWITCH): Two PCs and a Nokia SR Linux Switch
Lab: Demo — Two PCs and a Real Switch (SR Linux) 🖥️🔀🖥️

Dad's pass condition, verbatim:
  "when PC 1 can ping BOTH the switch and PC 2, then the lab works."
Dad's correction (2026-09-21): the switch must be a REAL switch, not a Linux
  PC running a bridge. PC-to-PC alone does NOT count.

Expected config:
  pc-a : 10.0.1.1/24   on eth1
  pc-b : 10.0.1.2/24   on eth1
  sw1  : REAL SR Linux switch — IRB 10.0.1.254/24 on irb0.0
         (member of BOTH mac-vrf-1 and ip-vrf-1)

Grading model (per node):
  pc-a : must have 10.0.1.1/24 up AND reach sw1 IRB (10.0.1.254) AND pc-b
         (10.0.1.2).
  pc-b : must have 10.0.1.2/24 up.
  sw1  : must be a REAL switch (sr_cli) with IRB 10.0.1.254/24 up.

Design rules:
  - NO fallback grading. If a check cannot run, it REFUSES (passed=False,
    feedback names the reason).
  - The switch check reads the IRB via `sr_cli`, so a Linux-PC fake cannot
    pass — Dad's explicit requirement.
  - BusyBox `ip` on the Alpine hosts has no JSON mode; parse plain output.
"""

import json
import subprocess


EXPECTED = {
    "pc-a": {"ip": "10.0.1.1", "dev": "eth1"},
    "pc-b": {"ip": "10.0.1.2", "dev": "eth1"},
}

# Real switch: node -> expected IRB address on irb0.0
SWITCH_IP = {"sw1": "10.0.1.254"}

# From pc-a the student must reach BOTH of these (Dad's pass condition).
PING_TARGETS = ["10.0.1.254", "10.0.1.2"]


def _exec(container, cmd, timeout=20):
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
    threw the mask away (`split("/")[0]`), so a student who typed
    10.0.1.2/32 - a wrong mask that breaks reachability - was told
    "10.0.1.2/24 present on eth1" and scored a full 1.0. The grader printed a
    mask the student never entered and credited a broken config. Live-caught
    2026-09-28 (run 49). A grader may not claim a mask it did not verify.
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
    """True if `container` is a REAL SR Linux switch with `ip` on irb0.0."""
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
    nodes = session.get("nodes", {})
    container = nodes.get(node)

    if not container:
        return {
            "passed": False, "score": 0,
            "feedback": [f"❌ Node '{node}' not found in session."],
            "competencies": [],
        }

    # --- Real switch ------------------------------------------------------
    if node in SWITCH_IP:
        ip = SWITCH_IP[node]
        ok, detail = _srl_irb_ok(container, ip)
        return {
            "passed": ok,
            "score": 1.0 if ok else 0.0,
            "feedback": [
                f"✅ {node}: real SR Linux switch, {detail}" if ok
                else f"❌ {node}: expected real switch IRB {ip}/24 — {detail}"
            ],
            "competencies": ["Management IP on a real switch (IRB)",
                             "L2 bridging on a real switch"],
        }

    spec = EXPECTED.get(node)
    if not spec:
        return {
            "passed": False, "score": 0,
            "feedback": [f"❌ Unknown node '{node}' for this lab."],
            "competencies": [],
        }

    feedback = []
    score = 0.0
    ok, detail = _node_ip_ok(container, spec["ip"], spec["dev"])
    if ok is None:
        return _refuse_missing_link(node, detail)
    if ok:
        feedback.append(f"✅ {node}: {detail}")
        # pc-a has TWO graded parts (address + reachability), so its address check
        # is worth 0.5 and the pings make up the other 0.5. pc-b has only ONE
        # graded part, so a correct pc-b is worth its FULL 1.0, not 0.5. Before
        # 2026-09-28 both nodes credited 0.5 for the address, which meant a
        # student who configured pc-b exactly as the guide says saw
        # "✅ Passed! 50%" - a correct node reading as a half-finished one.
        # The credit MUST stay inside this `if ok:` branch: awarding it
        # unconditionally gives a failing pc-b a score of 1.0 (caught live
        # 2026-09-28 on the first attempt at this fix).
        if node == "pc-a":
            score += 0.5
        else:
            score += 1.0
    else:
        feedback.append(
            f"❌ {node}: expected {spec['ip']}/24 on {spec['dev']} — {detail}"
        )

    passed = ok

    if node == "pc-a":
        reached = 0
        for target in PING_TARGETS:
            good, out = _ping_from(container, target)
            label = "the switch" if target == "10.0.1.254" else "PC-B"
            if good:
                feedback.append(f"✅ pc-a can ping {label} ({target})")
                reached += 1
            else:
                feedback.append(f"❌ pc-a cannot ping {label} ({target})")
        score += 0.5 * (reached / len(PING_TARGETS))
        passed = ok and reached == len(PING_TARGETS)

    return {
        "passed": passed,
        "score": round(score, 3),
        "feedback": feedback,
        "competencies": (
            ["IP addressing", "Ping verification"]
            if node == "pc-a"
            else ["IP addressing"]
        ),
    }


def grade_all(session):
    """Lab-level pass = Daddy's pass condition: pc-a reaches BOTH the real
    switch IRB and PC-B."""
    results = {}
    for node in ["pc-a", "pc-b", "sw1"]:
        results[node] = grade(session, node)
    lab_passed = results["pc-a"]["passed"] and results["sw1"]["passed"]
    return {
        "passed": lab_passed,
        "nodes": results,
        "summary": (
            "Demo lab 1 PASSES — pc-a reaches both the real switch and PC-B."
            if lab_passed
            else "Demo lab 1 is not yet complete — see per-node feedback."
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
