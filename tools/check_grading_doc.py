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

    # --- Claim 6: the per-lab score arithmetic the docs state as fact. GRADING-MODEL.md
    # names exact counts (Demo 2's pc-a is asked for three targets, not four) and exact
    # gate shapes (Demo 1 gates on pc-a+sw1 of three; Demo 2 on all five). Those numbers
    # rotted once already — the 2026-11-21 read found the doc saying "four (two across)"
    # and "Demo 2 omits r1" when the source said three and gated on r1 too. Derive both
    # from the frozen module instead of transcribing the prose.
    _check_grader_arithmetic()

    # --- Claim 6b: GRADING-MODEL.md must not re-assert that Demo 2 omits r1 — a claim
    # that was false of this tree and that a copy-paste could reintroduce while the
    # source checks above stayed green (they guard the code; this guards the prose).
    stale_gate = [m for m in ("omitting `r1`", "Demo 2 on four of five") if m in grading]
    check("GRADING-MODEL.md does not re-assert that Demo 2 omits r1 from its gate",
          not stale_gate,
          f"stale claim(s) present: {stale_gate} — the code gates on r1 too")

    _report()
    return 0 if not failures else 1


def _check_grader_arithmetic() -> None:
    """Derive the per-node target counts the docs state, from the graders themselves.

    GRADING-MODEL.md tells a reader exactly how many reachability targets Demo 2's
    pc-a is asked for (three) and which nodes each shipped lab's grade_all gates on
    (Demo 1: pc-a+sw1 of three; Demo 2: all five). Those are numbers a reader plans
    work against, and on 2026-11-21 they were found wrong of a tree that had passed
    every checker. So the doc numbers are now read from the source and compared.
    """
    import importlib.util
    import re as _re

    grading = read(GRADING)

    def load(name: str):
        path = ROOT / "lab-definitions" / f"{name}.py"
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:  # pragma: no cover - import-time side effect
            check(f"{name}.py imports for arithmetic check", False, str(exc))
            return None
        return mod

    g2 = load("grader_demo_02")
    if g2 is not None:
        end_to_end = getattr(g2, "END_TO_END", [])
        local = getattr(g2, "PC_A_LOCAL_TARGETS", [])
        pca = len(local) + len([t for s, t in end_to_end if s == "pc-a"])
        pcb = len([t for s, t in end_to_end if s == "pc-b"])
        # The doc line: "`pc-a` is asked for three (two local plus one across the
        # router), `pc-b` for one."
        word = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
                6: "six", 7: "seven", 8: "eight"}.get(pca, str(pca))
        claim = f"`pc-a` is asked for {word} ("
        check("GRADING-MODEL.md's Demo 2 pc-a target count matches the grader",
              pca <= 8 and claim in grading,
              f"the grader gives pc-a {pca} target(s) (word '{word}'); the doc does not "
              f"say \"{claim}...\" — the per-node count has rotted")
        pcb_claim = f"`pc-b`\n  for { {1:'one',2:'two',3:'three',4:'four'}.get(pcb, pcb) }."
        # tolerate the line wrap either way
        check("GRADING-MODEL.md's Demo 2 pc-b target count matches the grader",
              pcb <= 4 and (pcb_claim in grading or f"`pc-b` for { {1:'one',2:'two',3:'three',4:'four'}.get(pcb,pcb) }." in grading),
              f"the grader gives pc-b {pcb} target(s); the doc's 'pc-b for ...' sentence does not match")

    # Gate shape: Demo 2's grade_all must conjunct every node it grades (the doc now
    # says it gates on all five). Demo 1's must gate on pc-a and sw1 and omit pc-b.
    for mod_name, must_include, must_exclude in (
        ("grader_demo_02", {"pc-a", "pc-b", "sw1", "sw2", "r1"}, set()),
        ("grader_demo_01_srl", {"pc-a", "sw1"}, {"pc-b"}),
    ):
        mod = load(mod_name)
        if mod is None:
            continue
        src = (ROOT / "lab-definitions" / f"{mod_name}.py").read_text(encoding="utf-8")
        # the lab_passed = ... line's set of result[node] references
        m = _re.search(r"^\s*lab_passed\s*=\s*(.+)$", src, _re.M)
        gate_nodes = set(_re.findall(r'results\["([^"]+)"\]', m.group(1))) if m else set()
        # `e2e = results[...] and results[...]` aliases mean the gate line only names
        # e2e/real_switches/router_ok; resolve those aliases to their node sets.
        if m:
            aliases = dict(_re.findall(r'^\s*(\w+)\s*=\s*([^\n]+)$', src, _re.M))
            for ident in _re.findall(r'\b\w+\b', m.group(1)):
                if ident in aliases:
                    gate_nodes |= set(_re.findall(r'results\["([^"]+)"\]', aliases[ident]))
        ok_inc = must_include <= gate_nodes
        ok_exc = not (must_exclude & gate_nodes)
        check(f"{mod_name}: lab_passed gate shape matches GRADING-MODEL.md",
              ok_inc and ok_exc,
              f"gate resolves to {sorted(gate_nodes)}; expected include {sorted(must_include)} "
              f"and exclude {sorted(must_exclude)}")


def _report() -> None:
    print()
    print(f"{passes} PASS, {len(failures)} FAIL")
    if failures:
        print("\nFailed claims:")
        for f in failures:
            print(f"  - {f}")


if __name__ == "__main__":
    sys.exit(main())
