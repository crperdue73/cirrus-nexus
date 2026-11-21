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


# --- the Python floor, derived from the code that has to run ------------------------------- #
#
# The floor is set by the NEWEST language feature an annotation actually uses, because
# backend/main.py carries no `from __future__ import annotations`: every annotation in a `def`
# signature or a class body is evaluated when the module is imported, so a form the interpreter
# does not know is not a style problem, it is an ImportError-and-dead-service problem.
#
# Forms considered, and the version that first evaluates them (PEP numbers as the authority):
#   PEP 585 builtin generics  `list[str]`  -> 3.9   (3.8: TypeError, 'type' not subscriptable)
#   PEP 604 unions            `X | None`  -> 3.10  (3.9: TypeError on the `|`)
#   PEP 634 match statement   `match x:`  -> 3.10  (3.9: SyntaxError)
# `from __future__ import annotations` would defer all of the annotation forms and lower the floor;
# it is checked because a file that adopts it changes the answer, and a derived floor that ignored
# it would start overstating the requirement.
FLOOR_FOR = (("pep604", "3.10"), ("match", "3.10"), ("pep585", "3.9"))


def _floor_sources():
    """Every Python file whose import an installed host would execute.

    backend/main.py plus the graders that the backend imports by path from lab-definitions/.
    Deliberately NOT tools/: this is the floor for a *user's* install, and the checkers never run
    on that host.
    """
    out = []
    backend = os.path.join(ROOT, "backend")
    for root, _dirs, files in os.walk(backend):
        if "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    labs = os.path.join(ROOT, "lab-definitions")
    if os.path.isdir(labs):
        for root, _dirs, files in os.walk(labs):
            if "__pycache__" in root:
                continue
            for f in files:
                if f.endswith(".py"):
                    out.append(os.path.join(root, f))
    return sorted(out)


def derived_floor():
    """The oldest Python that can import this tree, by reading the annotations. None if unreadable."""
    import ast

    needed = {"pep585": None, "pep604": None, "match": None}
    parsed = 0
    for path in _floor_sources():
        try:
            src = read(path)
            tree = ast.parse(src)
        except (SyntaxError, ValueError):
            continue
        parsed += 1
        deferred = "from __future__ import annotations" in src

        def note(form, lineno):
            if needed[form] is None:
                needed[form] = (os.path.relpath(path, ROOT), lineno)

        def annotations_of(node):
            out = [node.annotation for node in node.args.posonlyargs + node.args.args
                   + node.args.kwonlyargs if node.annotation]
            for opt in (node.args.vararg, node.args.kwarg):
                if opt is not None and opt.annotation:
                    out.append(opt.annotation)
            if node.returns:
                out.append(node.returns)
            return out

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                anns = annotations_of(node)
            elif isinstance(node, ast.AnnAssign):
                anns = [node.annotation]
            else:
                anns = []
            if not deferred:
                for ann in anns:
                    for sub in ast.walk(ann):
                        if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr):
                            note("pep604", node.lineno)
                        elif (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name)
                              and sub.value.id in ("list", "dict", "set", "tuple", "frozenset", "type")):
                            note("pep585", node.lineno)
            if isinstance(node, getattr(ast, "Match", ())):
                note("match", node.lineno)

    if not parsed:
        return None
    floor = "3.7"
    for form, version in FLOOR_FOR:
        if needed[form] is not None:
            where, lineno = needed[form]
            print(f"  floor: {form} used at {where}:{lineno}")
            floor = max(floor, version, key=lambda v: tuple(int(p) for p in v.split(".")))
    return floor


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
        # The floor is a promise about what the code uses, so DERIVE it from the code each run.
        # Earlier versions of this check compared the badge to the string "3.10" and then asked a
        # regex whether *some* 3.10 syntax exists — i.e. it was held by a note, and it looked only
        # at backend/main.py, never at the graders the backend loads. Both are fixed here.
        floor_found = derived_floor()
        if floor_found is None:
            fail(
                "README: the Python floor could not be derived from the tree — no Python under "
                "backend/ or lab-definitions/ could be parsed; re-measure before trusting the badge"
            )
        elif floor_found != floor:
            fail(
                f"README: python badge says {floor}+, but the newest annotation form in the "
                f"backend and graders needs {floor_found}+ — one of the two is wrong"
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
