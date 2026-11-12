#!/usr/bin/env python3
"""Check the lab-verdict rules in docs/GRADING-MODEL.md and docs/ADDING-A-LAB.md
against the code that actually enforces them.

Why this exists: both pages told a reader that coverage ("every declared
`gradeable_nodes` entry must appear in the verdict") was only consulted when the
grader reported `passed: true`, and that both shipped graders therefore violated
it. On 2026-11-12 that was measured false — `_lab_verdict_passed` computes
`_missing` unconditionally and returns `None`. Two reader-facing pages described
a backend that no longer exists, and nothing went red. This tool is that red.

The claims are checked against the *source*, read with the AST rather than by
grepping prose, because the sentence that broke was one that read as code.

Exit 0 = every claim holds. Exit 1 = at least one is false of this tree.

Run from the repo root:  python3 tools/check_grading_doc.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "backend" / "main.py"
GRADING = ROOT / "docs" / "GRADING-MODEL.md"
ADDING = ROOT / "docs" / "ADDING-A-LAB.md"

failures: list[str] = []
passes = 0


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def check(name: str, ok: bool, detail: str = "") -> None:
    global passes
    if ok:
        passes += 1
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}" + (f"\n        {detail}" if detail else ""))
        failures.append(name)


def _verdict_fn():
    """The `_lab_verdict_passed` FunctionDef node, or None."""
    tree = ast.parse(read(MAIN))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_lab_verdict_passed":
            return tree, node
    return tree, None


def main() -> int:
    src = read(MAIN)
    grading = read(GRADING)
    adding = read(ADDING)
    tree, fn = _verdict_fn()

    if fn is None:
        check("_lab_verdict_passed exists in backend/main.py", False,
              "the function these docs describe is gone; re-read both pages")
        _report()
        return 1
    check("_lab_verdict_passed exists in backend/main.py", True)

    # --- Claim 1: coverage is computed unconditionally (no `if _passed:` guard).
    # This is the exact claim both pages got wrong. We look for any If whose test
    # mentions _passed, because that is what "only checked on pass" looks like.
    guarded = []
    for node in ast.walk(fn):
        if isinstance(node, ast.If):
            seg = ast.get_source_segment(src, node.test) or ""
            if "_passed" in seg:
                guarded.append((node.lineno, seg.strip()))
    check("coverage check is not gated behind `if _passed:`", not guarded,
          f"found guard(s) at line(s): {guarded} — the docs say coverage runs "
          f"regardless of passed")

    # --- Claim 2: a shortfall returns None (uncomputable), not False (fail).
    # Find the `if _declared and _missing:` block and confirm it returns None.
    shortfall_returns_none = False
    shortfall_lineno = None
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and "_missing" in (ast.get_source_segment(src, node.test) or ""):
            shortfall_lineno = node.lineno
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Constant) \
                        and sub.value.value is None:
                    shortfall_returns_none = True
    check("a coverage shortfall returns None (uncomputable)", shortfall_returns_none,
          f"the `_missing` branch at line {shortfall_lineno} does not return None")

    # --- Claim 3: the docs still SAY both rules are enforced. A checker that only
    # reads code would pass happily after someone deleted the paragraphs — which is
    # the same silent rot in the other direction.
    check("GRADING-MODEL.md still states the coverage rule",
          "Coverage" in grading and "gradeable_nodes" in grading)
    check("GRADING-MODEL.md states that a failed check makes the verdict None",
          "None" in grading and ("uncomputable" in grading or "uncomputable" in grading.lower()))
    check("ADDING-A-LAB.md still states both rules",
          "cover every" in adding and "`node` field must match" in adding)
    check("ADDING-A-LAB.md says the coverage rule is not pass-gated",
          "regardless of whether your verdict says" in adding
          or "no \"only checked on pass\"" in adding
          or "not pass-gated" in adding)

    # --- Claim 4: neither page still carries the RETRACTED "only checked on pass"
    # assertion. Prose that asserts the old behaviour must not survive the fix.
    retracted_markers = [
        "only one of them is actually enforced",
        "checks coverage only when your verdict says",
        "does not fire on a real shortfall",
    ]
    stale = [m for m in retracted_markers if m in adding or m in grading]
    check("the retracted 'only-on-pass' claim is gone from both pages", not stale,
          f"still present: {stale}")

    # --- Claim 5: the shipped graders report on every declared node. The docs say
    # so; verify it rather than trust it. Parse each YAML's gradeable_nodes and each
    # grader's grade_all iterated node list.
    import re as _re
    labs = sorted(ROOT.glob("lab-definitions/*/*.yml")) + sorted(ROOT.glob("lab-definitions/*.yml"))
    saw_a_grader = False
    for yml in labs:
        text = read(yml)
        m_grad = _re.search(r"^\s*grader:\s*(\S+)", text, _re.M)
        if not m_grad:
            continue
        grader_mod = m_grad.group(1)
        gpath = ROOT / "lab-definitions" / f"{grader_mod}.py"
        if not gpath.is_file():
            continue  # graders in backend/graders/ are outside this check's scope
        saw_a_grader = True

        # declared nodes: inline list or block list
        declared: list[str] = []
        gr = _re.search(r"^\s*gradeable_nodes:\s*\[(.*?)\]", text, _re.M)
        if gr:
            declared = [x.strip().strip("'\"") for x in gr.group(1).split(",") if x.strip()]
        else:
            block = _re.search(r"^\s*gradeable_nodes:\s*\n((?:\s*-\s*\S+\n?)+)", text, _re.M)
            if block:
                declared = _re.findall(r"-\s*(\S+)", block.group(1))

        gtree = ast.parse(read(gpath))
        ga = None
        for node in ast.walk(gtree):
            if isinstance(node, ast.FunctionDef) and node.name == "grade_all":
                ga = node
        if ga is None:
            check(f"{grader_mod}: has grade_all", False, "no grade_all in the grader")
            continue

        iterated: list[str] = []
        for node in ast.walk(ga):
            if isinstance(node, ast.For) and isinstance(node.iter, (ast.List, ast.Tuple)):
                for el in node.iter.elts:
                    if isinstance(el, ast.Constant) and isinstance(el.value, str):
                        iterated.append(el.value)
        missing = set(declared) - set(iterated)
        check(f"{grader_mod}: grade_all iterates every declared node ({len(declared)})",
              bool(declared) and not missing,
              f"declared={sorted(declared)} iterated={sorted(iterated)} missing={sorted(missing)}")
    check("found at least one lab grader to cross-check", saw_a_grader,
          "no lab-definitions/*/*.yml named a grader present in lab-definitions/ — the "
          "shipped-grader claim is now unchecked")

    _report()
    return 0 if not failures else 1


def _report() -> None:
    print()
    print(f"{passes} PASS, {len(failures)} FAIL")
    if failures:
        print("\nFailed claims:")
        for f in failures:
            print(f"  - {f}")


if __name__ == "__main__":
    sys.exit(main())
