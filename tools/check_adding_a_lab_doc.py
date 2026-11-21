#!/usr/bin/env python3
"""
check_adding_a_lab_doc.py -- hold docs/ADDING-A-LAB.md's CONTRACT claims to the
source and to the shipped graders, derived rather than transcribed.

WHY THIS EXISTS
    `docs/ADDING-A-LAB.md` is the document a lab author follows to write a grader.
    It makes hard, falsifiable promises: a grader exports exactly two functions
    (`grade` and `grade_all`); `grade()` returns a dict with the keys passed,
    score, feedback and competencies; the loader skips files whose name starts
    with "." or contains .bak/.stale/.orig; a grader module is looked up flat in
    `lab-definitions/` and `backend/graders/`. Until 2026-11-21 NOTHING checked
    any of this. Every other reader-facing doc (README, SECURITY, architecture,
    grading model, operations, API, install) had a checker; this one was carried
    by hand. That is the self-citing failure named in the workspace rules: a page
    that described the code when it was written and kept reading as authoritative
    because no tool ever re-read it.

WHAT IT CHECKS (all derived from source/live files, nothing transcribed here)
    1. `grade` and `grade_all` are documented as the two exported functions, and
       every shipped grader in lab-definitions/ actually defines both.
    2. The four result keys `grade()` returns are named in the doc, and the
       shipped graders actually return exactly those keys from `grade()`.
    3. The loader's skip rules (leading ".", or .bak/.stale/.orig in the name)
       are both present in backend/main.py AND described in the doc.
    4. The grader lookup directories named in the doc (`lab-definitions/` and
       `backend/graders/`) are the ones `_load_grader` actually searches.

WHAT IT DOES NOT CHECK
    It does not run a lab or a grader. It does not verify the prose around these
    claims (why the contract exists, the RUN 226/227 narrative). A green result
    means the doc's contract claims match the code and the shipped graders on
    disk -- not that any particular lab starts and grades clean.

Exit 0 = doc and source agree. Exit 1 = they disagree (details printed).
Stdlib only.
"""

import os
import re
import sys
import glob
import ast

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOC = os.path.join(ROOT, "docs", "ADDING-A-LAB.md")
MAIN = os.path.join(ROOT, "backend", "main.py")
LABDIR = os.path.join(ROOT, "lab-definitions")

REQUIRED_RESULT_KEYS = {"passed", "score", "feedback", "competencies"}


def _grade_result_block(doc):
    """The code block that documents grade()'s return dict.

    Located by scanning fenced blocks line-by-line and returning the one that holds
    both `"passed": bool` and `"score"`. Line scanning avoids a `.*?` regex tripping
    over an earlier fence that the doc left open or nested.
    """
    lines = doc.splitlines()
    in_fence = False
    buf = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_fence:
                block = "\n".join(buf)
                if '"passed": bool' in block and '"score"' in block:
                    return block
                in_fence = False
                buf = []
            else:
                in_fence = True
                buf = []
            continue
        if in_fence:
            buf.append(line)
    return None


def _doc_names_key(doc, key):
    """True only if the grade() RESULT block names `key` as a field.

    A doc-wide substring test is too loose: 'status' also appears as a key in the
    reload-response JSON (`{"status":"reloaded with skips"...}`) and as prose about
    the session's status. Both passed a whole-document search while the result-dict
    contract key was missing. So the key must appear inside the result block itself.
    """
    block = _grade_result_block(doc)
    if block is None:
        return False
    pat = re.compile(r'["\']' + re.escape(key) + r'["\']\s*:')
    return bool(pat.search(block))


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def shipped_graders():
    """[(path, ast.Module)] for every grader_*.py in lab-definitions/ (flat)."""
    out = []
    for p in sorted(glob.glob(os.path.join(LABDIR, "grader_*.py"))):
        try:
            out.append((p, ast.parse(_read(p), filename=p)))
        except SyntaxError as e:
            out.append((p, e))
    return out


def top_level_funcs(tree):
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def dict_keys_returned_by(tree, func_name):
    """The set of string-literal keys in any dict return inside func_name."""
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict):
                    for k in inner.value.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
    return keys


def doc_loader_skip_rules(doc):
    """Which skip rules the doc names: returns set of tokens it mentions."""
    found = set()
    if re.search(r'starts? with\s*`?\.`?|\._prefix_|leading\s*`?\.`?', doc) or 'starts with' in doc.lower() and '`.`' in doc:
        found.add("dot")
    for tok in (".bak", ".stale", ".orig"):
        if tok in doc:
            found.add(tok)
    return found


def check():
    failures = []
    notes = []

    if not os.path.isfile(DOC):
        return ["docs/ADDING-A-LAB.md not found at %s" % DOC], notes
    if not os.path.isfile(MAIN):
        return ["backend/main.py not found at %s" % MAIN], notes

    doc = _read(DOC)
    main_src = _read(MAIN)

    # 1. the two exported functions
    if "grade_all" not in doc or not re.search(r'`grade\(', doc):
        failures.append(
            "docs/ADDING-A-LAB.md no longer documents both `grade` and `grade_all`"
        )
    else:
        notes.append("doc names grade() and grade_all()")

    graders = shipped_graders()
    if not graders:
        failures.append("no grader_*.py found in lab-definitions/ -- cannot verify the contract")
    for path, tree in graders:
        name = os.path.basename(path)
        if isinstance(tree, SyntaxError):
            failures.append("%s does not parse: %s" % (name, tree))
            continue
        funcs = top_level_funcs(tree)
        missing = {"grade", "grade_all"} - funcs
        if missing:
            failures.append(
                "%s does not define %s -- the doc promises a grader exports both"
                % (name, " and ".join(sorted(missing)))
            )
        else:
            notes.append("%s defines grade() and grade_all()" % name)

        # 2. the four result keys
        keys = dict_keys_returned_by(tree, "grade")
        if keys:
            absent = REQUIRED_RESULT_KEYS - keys
            extra = keys - REQUIRED_RESULT_KEYS
            if absent:
                failures.append(
                    "%s grade() never returns documented key(s): %s (returns: %s)"
                    % (name, ", ".join(sorted(absent)), ", ".join(sorted(keys)))
                )
            elif extra:
                # Extra keys are allowed, but if a shipped grader returns a key the
                # doc does not name, that is a contract the author cannot see. 2026-11-21:
                # grader_demo_02.py returned `status` (a real GraderResult field, three-state
                # graded/error/refused) that ADDING-A-LAB.md never listed. Treat any returned
                # key missing from the doc as a failure -- an undocumented contract is the bug.
                undocumented = sorted(k for k in extra if not _doc_names_key(doc, k))
                if undocumented:
                    failures.append(
                        "%s grade() returns key(s) the doc never names: %s -- a lab author "
                        "following the doc would not know to emit them"
                        % (name, ", ".join(undocumented))
                    )
                else:
                    notes.append("%s grade() also returns documented extra key(s): %s"
                                 % (name, ", ".join(sorted(extra))))
            else:
                notes.append("%s grade() returns exactly the four documented keys" % name)

    for k in sorted(REQUIRED_RESULT_KEYS):
        if k not in doc:
            failures.append(
                "docs/ADDING-A-LAB.md never names the `%s` result key the graders return" % k
            )

    # 3. loader skip rules: present in source AND described in doc
    src_has = {
        "dot": bool(re.search(r'startswith\("\."\)', main_src)),
        ".bak": '".bak"' in main_src or "'.bak'" in main_src,
        ".stale": '".stale"' in main_src or "'.stale'" in main_src,
        ".orig": '".orig"' in main_src or "'.orig'" in main_src,
    }
    doc_has = doc_loader_skip_rules(doc)
    for rule, in_src in src_has.items():
        label = 'leading "."' if rule == "dot" else rule
        if in_src and rule not in doc_has:
            failures.append(
                "backend/main.py skips %s but docs/ADDING-A-LAB.md never says so "
                "(a backup could load as a lab and the author would not know)" % label
            )
        elif not in_src and rule in doc_has:
            failures.append(
                "docs/ADDING-A-LAB.md says the loader skips %s but backend/main.py "
                "has no such rule -- the doc describes a filter the code lacks" % label
            )
    if all(src_has.values()) and all(r in doc_has for r in src_has):
        notes.append("loader skip rules (.dot/.bak/.stale/.orig) match on both sides")

    # 4. grader lookup directories
    look_in_doc = []
    if "lab-definitions/" in doc:
        look_in_doc.append("lab-definitions")
    if "backend/graders/" in doc:
        look_in_doc.append("backend/graders")
    src_dirs = "LABS_DIR, BASE_DIR" in main_src or "BASE_DIR / \"backend\" / \"graders\"" in main_src
    if "backend/graders/" in doc and 'BASE_DIR / "backend" / "graders"' not in main_src:
        failures.append(
            "docs/ADDING-A-LAB.md says graders are looked up in backend/graders/, but "
            "_load_grader in backend/main.py does not search that directory"
        )
    elif "lab-definitions/" in doc and not src_dirs:
        failures.append(
            "docs/ADDING-A-LAB.md says graders live in lab-definitions/, but "
            "_load_grader does not search LABS_DIR"
        )
    else:
        notes.append("grader lookup dirs in the doc match _load_grader (both %s)" % ", ".join(look_in_doc))

    return failures, notes


def main():
    failures, notes = check()
    for n in notes:
        print("  note: %s" % n)
    if failures:
        for f in failures:
            print("  FAIL: %s" % f)
        print("[check_adding_a_lab_doc] FAILED -- %d problem(s)" % len(failures))
        return 1
    print(
        "[check_adding_a_lab_doc] OK -- docs/ADDING-A-LAB.md's contract claims (the two "
        "functions, the four result keys, the loader skip rules, the lookup dirs) match "
        "the source and the shipped graders"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
