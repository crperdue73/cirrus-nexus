#!/usr/bin/env python3
"""Check the README's badge block against this tree and against GitHub.

Why this exists: `README.md` opens with seven badges. Six are shipped to every visitor before any
prose, and each one states something checkable:

    status: v0.2.0 — early release      -> the newest numbered tag in this tree
    release notes: v0.3.0 not published -> "no release after v0.2.0", and the v0.3.0 notes are a draft
    python 3.10+                        -> the Python floor the backend actually needs
    powered by containerlab             -> containerlab is really what deploys the labs
    API: FastAPI                        -> the backend really is FastAPI
    CI: .../ci.yml/badge.svg            -> the workflow path exists here, and CI really serves it
    license: Apache 2.0                 -> LICENSE really is Apache 2.0

Nothing in `tools/` read that block. `tools/check_repo_metadata.py` covers the GitHub-side
description, topics and license, but it starts at the repository landing page, not the README — so a
badge that went stale (a new tag created and the status badge left at v0.2.0) was green everywhere.
That is the 2026-11-10 architecture.md failure again: prose-shaped metadata held by nothing.

What it does NOT do: it does not fetch the badge SVG from GitHub (that is a network call in a checker
that must pass offline; the shields.io service answers "passing"/"failing" for the CI badge and this
tool cannot know when it last rebuilt). Instead it checks the half that lives in this tree — that the
badges agree with the tag list, with the draft notes, with the code — and prints, without failing,
what a human should confirm on the web. The CI badge's *live* colour is the one thing here that needs
a browser, and is stated as such rather than asserted.

Exit codes: 0 = every badge still true of this tree, 1 = at least one badge is now false, 2 = could
not run (README or a file it is checked against is missing) — the same 0/1/2 meaning the other tools
in this directory use.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
CI = os.path.join(ROOT, ".github", "workflows", "ci.yml")

failures = []


def fail(msg):
    failures.append(msg)


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        print(f"could not run: {path}: {exc}")
        sys.exit(2)


def tags():
    """Numbered tags in this tree. None if git could not answer.

    git refusing is NOT the same as "no tags": a git that will not read the repository (dubious
    ownership, not a repo, git absent) used to fall through to the empty list and quietly disable
    the two tag checks below. Measured: a scratch copy at /tmp is refused for dubious ownership and
    a stale status badge passed as OK. So a non-zero git exit is `None`, never `[]`.
    """
    try:
        res = subprocess.run(
            ["git", "-C", ROOT, "tag", "-l", "v*"],
            capture_output=True, text=True,
        )
    except OSError:
        return None
    if res.returncode != 0:
        if res.stderr.strip():
            print(f"note: git could not list tags ({res.stderr.strip().splitlines()[0]})")
        return None
    return [t.strip() for t in res.stdout.splitlines() if t.strip()]


def vkey(tag):
    return tuple(int(p) for p in re.findall(r"\d+", tag))


def main():
    readme = read(README)
    ci = read(CI) if os.path.exists(CI) else None

    # --- 1. the status badge names the newest tag, and calls it early release ---------------- #
    m = re.search(r"badge/status-v((?:[0-9]+\.){2}[0-9]+)%20early", readme)
    if not m:
        fail("README: no 'status: vX.Y.Z early release' badge found (reworded? then update this tool)")
    else:
        claimed = "v" + m.group(1)
        all_tags = tags()
        if all_tags is None:
            # Not a pass. This is the one badge that states which release the tree is; if the tag
            # list cannot be read there is nothing holding it, and saying OK would be a lie.
            fail(
                "README: status badge names a release, but git could not list this tree's tags — "
                "the badge is unverified (run this from a git checkout with a readable tag list)"
            )
        elif not all_tags:
            fail("README: status badge names a tag but this tree has no tags")
        else:
            newest = sorted(all_tags, key=vkey)[-1]
            if claimed != newest:
                fail(
                    f"README: status badge says {claimed} is the release, but the newest tag here is "
                    f"{newest} — a tag was cut and the badge was not updated"
                )

    # --- 2. the release-notes badge says the next version is unpublished, and it is --------- #
    m = re.search(r"badge/release%20notes-v((?:[0-9]+\.){2}[0-9]+)%20draft%2C%20unpublished", readme)
    if not m:
        fail("README: no 'release notes: vX.Y.Z draft, unpublished' badge found")
    else:
        draft = m.group(1)
        notes = os.path.join(ROOT, "docs", f"RELEASE-NOTES-v{draft}-draft.md")
        if not os.path.exists(notes):
            fail(
                f"README: badge says the v{draft} notes are a draft, but docs/RELEASE-NOTES-v{draft}-draft.md "
                f"is not in this tree"
            )
        all_tags = tags()
        if all_tags and f"v{draft}" in all_tags:
            fail(
                f"README: badge says v{draft} is unpublished, but v{draft} is a tag in this tree — "
                f"publishing it means fixing this badge and the Release status section together"
            )

    # --- 3. the Python floor is the one the backend needs ---------------------------------- #
    m = re.search(r"badge/python-([0-9]+\.[0-9]+)%2B", readme)
    if not m:
        fail("README: no 'python X.Y+' badge found")
    else:
        floor = m.group(1)
        # The floor is a promise about what the code uses. Match it against real syntax usage:
        # 3.10+ is what the `X | Y` union type and match statements need. Look for those.
        backend = read(os.path.join(ROOT, "backend", "main.py"))
        uses_union = re.search(r":\s*\w+\s*\|\s*None\b|\bmatch\s+\w+:", backend) is not None
        if floor != "3.10":
            fail(
                f"README: python badge says {floor}+, but the tree's floor was recorded as 3.10 on "
                f"2026-11-16 — re-measure the floor before changing this badge"
            )
        elif not uses_union:
            fail(
                "README: python badge says 3.10+, but backend/main.py shows no 3.10-only syntax "
                "(PEP 604 unions / match) — the floor looks lower than advertised; re-measure"
            )

    # --- 4. 'powered by containerlab' and 'API: FastAPI' are true of the backend ------------ #
    if not re.search(r"badge/powered%20by-containerlab-", readme):
        fail("README: no 'powered by containerlab' badge found")
    else:
        backend = read(os.path.join(ROOT, "backend", "main.py"))
        if "containerlab" not in backend.lower():
            fail("README: badge says 'powered by containerlab', but backend/main.py never names it")

    if not re.search(r"badge/API-FastAPI-", readme):
        fail("README: no 'API: FastAPI' badge found")
    else:
        backend = read(os.path.join(ROOT, "backend", "main.py"))
        if not re.search(r"^\s*(import fastapi|from fastapi import)", backend, re.M):
            fail("README: badge says 'API: FastAPI', but backend/main.py does not import fastapi")

    # --- 5. the CI badge points at a workflow that exists here ----------------------------- #
    m = re.search(r"actions/workflows/([A-Za-z0-9_.-]+\.ya?ml)/badge\.svg", readme)
    if not m:
        fail("README: no CI badge pointing at a workflow file found")
    else:
        wf = m.group(1)
        path = os.path.join(ROOT, ".github", "workflows", wf)
        if not os.path.exists(path):
            fail(f"README: CI badge points at .github/workflows/{wf}, which is not in this tree")
        if ci is None:
            fail(f"README: CI badge points at {wf}, but no workflow file could be read")

    # --- 6. the license badge matches LICENSE ---------------------------------------------- #
    if not re.search(r"badge/license-Apache--2\.0-", readme):
        fail("README: no 'Apache 2.0' license badge found")
    else:
        lic = read(os.path.join(ROOT, "LICENSE"))
        if "Apache License" not in lic or "Version 2.0" not in lic:
            fail("README: license badge says Apache 2.0, but LICENSE is not the Apache 2.0 text")

    # --- what a human still has to confirm -------------------------------------------------- #
    print("Checked against this tree (7 badges):")
    print("  status / release-notes / python / containerlab / FastAPI / CI path / license")
    print("NOT checked here, confirm on the web:")
    print("  * the CI badge's live colour (shields.io) — it answers for the last workflow run")
    print("  * that the tag named in the status badge was actually published as a GitHub Release")

    if failures:
        print()
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print()
    print(f"OK: every badge still holds ({7} badges read)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
