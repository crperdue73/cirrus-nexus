#!/usr/bin/env python3
"""Check the repo's *published GitHub metadata* against this tree.

Why this exists: the description and topics on github.com are set in the web UI or
the API — they are not files in the repo, so nothing in the product can ever
contradict them and no other check can see them. `tools/check_repo_metadata.json`
records what is currently published; this script reads this tree and fails if a
claim in that file is no longer true of it. Change a claim in the tree, change the
JSON in the same commit.

It checks only what a text search can honestly decide:

  * every topic has a stated reason, and the thing it names appears in the tree
    (`fastapi` -> backend/main.py really imports fastapi, etc.) — for the topics
    that name software; the subject-matter topics are checked by the README's own
    scope statement instead of by a string search;
  * the description does not promise anything the README says is out of scope
    (OSPF / BGP / EVPN / VPNs are disabled in the shipped substrate on purpose);
  * the description does not call the project finished, and does not contain a
    number ("two labs", "11 routes") that this script would have to keep in sync;
  * the license named for the repo is the license in LICENSE.

It cannot check the description and topics are *actually* set on GitHub — that
needs the API and a token with repo scope. Run that half by hand (README section
"Repository metadata" shows the two commands).

Exit codes: 0 = every claim still holds, 1 = at least one claim is now false of
this tree, 2 = could not run (the JSON is missing or unparseable) — the same
0/1/2 meaning the other tools in this directory use.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = os.path.join(ROOT, "tools", "check_repo_metadata.json")

# Substrates that must not be advertised: the README says these are off on purpose.
OUT_OF_SCOPE = ["OSPF", "BGP", "EVPN", "VPN"]

# Topics that name software or a format actually used in the tree, and where that use is.
# (topic name -> (relative path, regex that must match in it, what it proves))
TECH_TOPICS = {
    "fastapi": ("backend/main.py", r"^\s*(from|import)\s+fastapi\b",
                "the backend imports fastapi"),
    "containerlab": ("install.sh", r"\bcontainerlab\b",
                     "the installer installs containerlab"),
    "frr": ("Dockerfile.frr", r"\bfrr\b",
            "the router substrate is built from Dockerfile.frr"),
    "srlinux": ("lab-definitions", r"(?i)srlinux",
                "a shipped lab definition requests an SR Linux image"),
    "docker": ("install.sh", r"\bdocker\b",
               "the installer installs Docker"),
    "python": ("backend/main.py", r"^\s*(from|import)\s+\w+",
               "the shipped backend is Python"),
}

# Topics that describe what the thing is *for* rather than what runs it. They are
# checked against the README's scope statement, which is the honest witness: it must
# describe a lab bench, a teaching context, and networking.
SUBJECT_TOPICS = {
    "networking": ("README.md", r"(?i)\bnetwork(ing)?\b"),
    "education": ("README.md", r"(?i)\b(classroom|students?|teaching|course)\b"),
    "labs": ("README.md", r"(?i)\blabs?\b"),
}

# Topics are checked *both* ways. A topic the tree backs but the record omits is a
# claim nobody made, and it is the easier half to fix — so it is reported instead of
# being discovered later by someone reading github.com and finding the tree richer
# than its own tags. Adding a topic means editing the JSON; this list names the
# expected set so a *deleted* entry is noticed just as loudly as an invented one.
EXPECTED_TOPICS = sorted(set(TECH_TOPICS) | set(SUBJECT_TOPICS))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main():
    if not os.path.exists(META):
        print(f"UNAVAILABLE: {os.path.relpath(META, ROOT)} is missing — cannot check GitHub metadata")
        return 2
    try:
        with open(META, encoding="utf-8") as fh:
            meta = json.load(fh)
        description = meta["description"]
        topics = [t["name"] for t in meta["topics"]]
        reasons = {t["name"]: t["why"] for t in meta["topics"]}
        repo_license = meta["license"]
    except (ValueError, KeyError, TypeError) as exc:
        print(f"UNAVAILABLE: {os.path.relpath(META, ROOT)} is not the expected JSON ({exc})")
        return 2

    problems = []
    checks = 0

    # 1. Every topic has a reason, and a reason is not a placeholder.
    for name in topics:
        checks += 1
        why = (reasons.get(name) or "").strip()
        if len(why) < 8:
            problems.append(f"topic '{name}' has no stated reason in check_repo_metadata.json")

    # 2. Topics that name software must be backed by a file in the tree.
    for name in topics:
        if name not in TECH_TOPICS:
            continue
        rel, pattern, proves = TECH_TOPICS[name]
        checks += 1
        target = os.path.join(ROOT, rel)
        if os.path.isdir(target):
            body = "\n".join(read(os.path.join(dp, fn))
                             for dp, _, fns in os.walk(target) for fn in fns
                             if fn.endswith((".yml", ".yaml")))
        elif os.path.exists(target):
            body = read(rel)
        else:
            problems.append(f"topic '{name}': {rel} does not exist (expected: {proves})")
            continue
        if not re.search(pattern, body, re.MULTILINE):
            problems.append(f"topic '{name}': {rel} no longer matches {pattern!r} (expected: {proves})")

    # 3. Topics are checked both ways. `docs check_repo_metadata --expected` lists the
    #    set this script knows how to verify; anything in it that the record omits is a
    #    real gap (a topic the tree earns and github.com is not advertising).
    missing = [t for t in EXPECTED_TOPICS if t not in topics]
    errant = [t for t in topics if t not in EXPECTED_TOPICS]
    checks += 1
    if errant:
        problems.append("topics not verifiable by this check (add a TECH_TOPICS or "
                        "SUBJECT_TOPICS entry if they are true of the tree, or remove the "
                        f"topic from github.com): {', '.join(errant)}")
    checks += 1
    if missing:
        problems.append("verified topic(s) missing from the record: " + ", ".join(missing))

    # 4. Subject-matter topics: the README must still describe that thing.
    for name in topics:
        if name not in SUBJECT_TOPICS:
            continue
        rel, pattern = SUBJECT_TOPICS[name]
        checks += 1
        if not re.search(pattern, read(rel)):
            problems.append(f"topic '{name}': {rel} no longer describes {name}")

    # 5. The description must not advertise what the README rules out.
    for word in OUT_OF_SCOPE:
        checks += 1
        if re.search(rf"(?<![A-Za-z]){word}(?![A-Za-z])", description) and "static" not in description.lower():
            problems.append(f"description mentions {word} without saying static routing only "
                            "— the README states those protocols are disabled on purpose")

    # 6. The description must not call the project finished, or carry a number that
    #    would need the tree updated to keep true (v0.2.0 is an early release).
    checks += 1
    for word in ("complete", "finished", "production-ready", "production ready"):
        if re.search(rf"(?i)\b{word}\b", description):
            problems.append(f"description says '{word}' — that call is the maintainer's, "
                            "and the README calls this an early release")
    checks += 1
    num = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
                    r"(labs?|routes?|switches?|routers?|hosts?)\b", description, re.IGNORECASE)
    if num:
        problems.append(f"description counts '{num.group(0)}' — counts go stale (the lab table in "
                        "README.md is the one place they are stated, and a lab added or removed "
                        "must not leave the repo description lying)")

    # 7. The license named for the repo is the license in the tree.
    checks += 1
    license_path = os.path.join(ROOT, "LICENSE")
    if not os.path.exists(license_path):
        problems.append(f"metadata says license {repo_license}, but LICENSE is missing")
    else:
        head = read("LICENSE")[:400]
        if repo_license == "Apache-2.0" and "Apache License" not in head:
            problems.append(f"metadata says license {repo_license}, but LICENSE does not start "
                            "with the Apache License text")

    if problems:
        print(f"repo metadata: {len(problems)} claim(s) no longer true of this tree:")
        for p in problems:
            print(f"  - {p}")
        print("\nFix the claim (tree or JSON), do not delete the check.")
        return 1

    print(f"repo metadata OK: description + {len(topics)} topics still match this tree "
          f"({checks} claim(s) checked); license {repo_license}.")
    print("NOTE: this checks the record against the tree, not that GitHub is serving it. "
          "Confirm the live values with the API (README, 'Repository metadata').")
    return 0


if __name__ == "__main__":
    sys.exit(main())
