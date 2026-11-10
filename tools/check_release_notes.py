#!/usr/bin/env python3
"""Release notes may not claim a limitation the tree no longer has.

WHY THIS EXISTS
---------------
`docs/RELEASE-NOTES-*-draft.md` and `CHANGELOG.md` carried one sentence forward for five weeks:

    "A cold install still serves zero labs unless per-lab assets are placed manually."

It was true when first written. It stopped being true on 2026-10-24, when commit `0c86d13` made
`install.sh` copy each lab's `assets/` directory and verify that every `startup-config:` a shipped
topology names actually landed. Nobody re-ran it, because nothing measured it: the wording is prose,
the claim is about behaviour, and every other checker in this repo reads code or a doc about code.

So the false sentence was copied from draft to draft, and each copy made the next one look sourced.
That is exactly the failure the workspace rules call out -- a self-citing entry is a rumour, not a
record. This checker is the measurement that was missing: it reads the claim, then reads the tree,
and refuses to let the two disagree.

WHAT IT CHECKS
--------------
1. The cold-install claim is absent or explicitly struck/withdrawn in every release-notes draft and
   in CHANGELOG.md. A bare assertion of it fails.
2. The underlying behaviour is still true: `install.sh` still copies per-lab assets and still
   verifies each `startup-config:`. If someone rips that out, the *struck* wording becomes wrong in
   the other direction, so this fails too and the prose must be revisited.
3. The grader-default claim is absent or struck. Both shipping labs name `grader:` explicitly, so
   "does not resolve for at least one lab" is false of this tree. The weak *default* stays legal to
   describe -- it is a real property of `metadata.id`-derived names.

This checks prose against source. It does not run the installer; a cold `sudo ./install.sh` on a
disposable host remains the only proof the steps execute.

Exit 0 = every claim holds. Exit 1 = a claim and the tree disagree.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
LABS = ROOT / "lab-definitions"

# Files that render as the record of a release, plus the changelog.
PROSE_GLOBS = [
    "CHANGELOG.md",
    "docs/RELEASE-NOTES-*.md",
]

# --- claim 1: cold install serves zero labs ----------------------------------
COLD_RE = re.compile(
    r"(cold[- ]install|install\.sh)[^.\n]{0,120}?"
    r"(zero labs|no labs|placed manually|does not copy them|does not reach them)",
    re.IGNORECASE,
)

# A claim counts as withdrawn when the line (or the block it opens) is struck, or an adjacent line
# says so in words. Strikethrough is what the 2026-11-10 correction actually used.
WITHDRAWN_RE = re.compile(
    r"(~~|\bwithdrawn\b|\bstruck\b|\bno longer true\b|\bfalse of this tree\b)",
    re.IGNORECASE,
)

# --- claim 2: the behaviour the struck note now describes --------------------
ASSET_COPY_MARKERS = [
    ("copies per-lab assets", re.compile(r"copy_lab_assets|labdir\}assets|labdir.*assets")),
    ("verifies startup-config presence", re.compile(r"startup-config:")),
]


def prose_files() -> list[Path]:
    out: list[Path] = []
    for pat in PROSE_GLOBS:
        out.extend(sorted(ROOT.glob(pat)))
    return [p for p in out if p.is_file()]


def claim_blocks(text: str) -> list[tuple[int, str]]:
    """Yield (line_number, surrounding_text) for every mention of the cold-install claim.

    The surrounding text is the hit's own paragraph *plus* up to two lines either side, because a
    strike on a wrapped bullet may sit one line above the words that match.
    """
    lines = text.splitlines()
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if not COLD_RE.search(line):
            continue
        lo, hi = max(0, i - 2), min(len(lines), i + 3)
        hits.append((i + 1, "\n".join(lines[lo:hi])))
    return hits


def check_cold_install(say) -> None:
    files = prose_files()
    if not files:
        say("FAIL", "no release-notes or CHANGELOG files found — nothing measured")
        return

    for path in files:
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        for lineno, block in claim_blocks(text):
            if WITHDRAWN_RE.search(block):
                say("PASS", f"{rel}:{lineno}: cold-install claim is marked withdrawn")
            else:
                say(
                    "FAIL",
                    f"{rel}:{lineno}: asserts the cold-install limitation as current, but "
                    "install.sh copies per-lab assets and verifies startup-configs "
                    "(0c86d13, 2026-10-24) — strike it or measure it again",
                )


def check_behaviour_holds(say) -> None:
    """If the installer ever stops copying assets, the withdrawal becomes the false statement."""
    if not INSTALL.is_file():
        say("FAIL", "install.sh not found — cannot confirm the withdrawal is still correct")
        return
    src = INSTALL.read_text(encoding="utf-8")
    for label, rx in ASSET_COPY_MARKERS:
        if rx.search(src):
            say("PASS", f"install.sh still {label}")
        else:
            say(
                "FAIL",
                f"install.sh no longer {label} — the withdrawn cold-install claim is now stale in "
                "the other direction; reinstate it honestly with a measurement",
            )


def check_grader_claim(say) -> None:
    rx = re.compile(
        r"grader[^.\n]{0,80}?(does not resolve|doesn't resolve)[^.\n]{0,40}?(at least one|one lab)",
        re.IGNORECASE,
    )
    for path in prose_files():
        rel = path.relative_to(ROOT)
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not rx.search(line):
                continue
            lo, hi = max(0, i - 2), min(len(lines), i + 3)
            if WITHDRAWN_RE.search("\n".join(lines[lo:hi])):
                say("PASS", f"{rel}:{i + 1}: grader-default claim is marked withdrawn")
            else:
                say(
                    "FAIL",
                    f"{rel}:{i + 1}: asserts a shipping lab's grader does not resolve; both shipped "
                    "labs name `grader:` explicitly and both load — strike or re-measure",
                )


def check_shipped_labs_name_a_grader(say) -> None:
    """The fact that makes the struck claim true must itself stay true."""
    if not LABS.is_dir():
        say("FAIL", "lab-definitions/ not found")
        return
    tops = sorted(LABS.glob("*/*.yml"))
    if not tops:
        say("FAIL", "no shipped lab topologies found")
        return
    for topo in tops:
        text = topo.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*grader:\s*\S", text, re.MULTILINE):
            say("PASS", f"{topo.relative_to(ROOT)} names grader: explicitly")
        else:
            say(
                "FAIL",
                f"{topo.relative_to(ROOT)} omits grader: and falls back to grader_<metadata.id>, "
                "which typically does not resolve — the struck claim is false again",
            )


def main() -> int:
    failures = 0

    def say(tag: str, msg: str) -> None:
        nonlocal failures
        if tag == "FAIL":
            failures += 1
        print(f"[{tag}] {msg}")

    print("[check_release_notes] prose vs. tree")
    check_cold_install(say)
    check_behaviour_holds(say)
    check_grader_claim(say)
    check_shipped_labs_name_a_grader(say)

    print()
    print(
        "[check_release_notes] NOTE: this reads install.sh and the lab YAMLs; it does not run the "
        "installer. A cold `sudo ./install.sh` on a disposable host is the only proof the steps "
        "execute."
    )
    if failures:
        print(f"[check_release_notes] {failures} claim(s) disagree with the tree")
        return 1
    print("[check_release_notes] OK — release notes make no withdrawn limitation as current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
