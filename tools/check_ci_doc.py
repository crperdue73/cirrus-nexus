#!/usr/bin/env python3
"""check_ci_doc.py — the three docs' count of CI steps, against the workflow itself and the
step list the docs point the reader at.

Why this exists: README.md, CONTRIBUTING.md and SECURITY.md all describe *how many* CI checks
`ci.yml` runs, and which of the checks a reader runs by hand are not in it. Every one of those
counts has been edited by hand and one of them was already wrong (README said "four run in CI,
three are claim checkers" while the same file listed five local-only checkers). A count in prose
about a file in the tree is exactly the kind of claim that drifts silently.

What it checks, in both directions:
  1. `ci.yml`'s step names. The two checks whose step name does not equal their command's tool
     name (the byte-compile and the secrets grep) are named here and verified by their commands;
     the other in-CI checks are anchored by tool file name, so a step that runs tool X under any
     name counts, and a doc claiming X is in CI while no step runs it fails.
  2. The NUMBER each doc states — "runs four checks", "the four checks CI actually enforces",
     "four of them" — against the number of checks found in ci.yml.
  3. The *complement*: every checker named in the docs' "local only" prose and in the
     CONTRIBUTING step list must NOT be run by the workflow; a checker promoted into CI while
     the docs still say "not yet in the workflow" fails.
  4. CONTRIBUTING's step list (the hand-run block) must agree with itself: each entry's own
     comment says whether it is "in CI" or "local only", and that must match ci.yml — for all
     ten entries, not just the ones CI runs.

What it does NOT check: whether a step's command is any good, whether the workflow is valid
YAML Actions semantics, or whether CI passed — that last one is the API's word, not this tool's.
It reads the file. It does not run the workflow.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI = os.path.join(ROOT, ".github", "workflows", "ci.yml")
README = os.path.join(ROOT, "README.md")
CONTRIBUTING = os.path.join(ROOT, "CONTRIBUTING.md")
SECURITY = os.path.join(ROOT, "SECURITY.md")

PASS, FAIL, INFO = "PASS", "FAIL", "info"
results = []


def ok(claim, detail=""):
    results.append((PASS, claim, detail))


def bad(claim, detail=""):
    results.append((FAIL, claim, detail))


def info(claim, detail=""):
    results.append((INFO, claim, detail))


def die(msg):
    print(f"[check_ci_doc] cannot run — {msg}")
    raise SystemExit(2)


# --- the workflow's own view --------------------------------------------------------------------
# Step names in ci.yml that are not simply the tool file name, mapped to the command they must run.
ANCHORED_BY_COMMAND = {
    "Backend compiles": ("py_compile backend/main.py", "py_compile"),
    "Installer is valid shell": ("bash -n install.sh", "install.sh"),
    "No obvious secrets committed": ("grep -rInE", "secrets-grep"),
}
# A step whose name starts with this is not a check (it is the runner setup).
NOT_A_CHECK = "Set up Python"


def ci_checks():
    """([(step name, [command lines])], [(tool or 'py_compile'|'grep', step name)])."""
    text = open(CI, encoding="utf-8").read()
    steps, cur = [], None
    in_run = False
    run_indent = 0
    in_block = False
    for raw in text.splitlines():
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        m = re.match(r"-\s+name:\s*(.+)$", stripped)
        if m and not in_run and not in_block:
            cur = [m.group(1).strip().strip("\"'"), []]
            steps.append(cur)
            in_block = False
            continue
        if in_run:
            if stripped and indent > run_indent:
                if not stripped.startswith("- name:"):
                    cur[1].append(stripped)
                continue
            in_run = in_block = False
        m = re.match(r"(?:-\s+)?run:\s*(.+)$", stripped)
        if m and cur is not None:
            body = m.group(1).strip()
            if body in ("|", ">", "|-", ">-"):
                in_run, run_indent, in_block = True, indent, True
            else:
                cur[1].append(body)

    found = []  # (key, step name)
    for name, cmds in steps:
        if not cmds and name.startswith(NOT_A_CHECK):
            continue
        blob = " ".join(cmds)
        key = None
        anchor = ANCHORED_BY_COMMAND.get(name)
        if anchor is not None:
            if anchor[0] in blob:
                key = anchor[1]
        else:
            for tool in TOOLS:
                if f"tools/{tool}.py" in blob:
                    key = tool
                    break
        if key is None:
            key = "unrecognised:" + name
        found.append((key, name))
    return steps, found


TOOLS = [
    "check_self_contained",
    "check_repo_metadata",
    "check_prerequisites",
    "check_install_narrative",
    "check_lab_assets",
    "check_operations_doc",
    "check_api_doc",
    "check_self_contained_doc",
]

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def num(word):
    if word.isdigit():
        return int(word)
    return NUMBER_WORDS[word.lower()]


# --- what each doc claims -----------------------------------------------------------------------
# (file, regex with one group naming the count, sentence the count is about, which CI check counts)
COUNTS = [
    (README, r"the checks to run before pushing \((\w+) run in CI", "README: CONTRIBUTING row, CI count"),
    (CONTRIBUTING, r"the same checks CI runs \(`\.github/workflows/ci\.yml` — (\w+) of them\)",
     "CONTRIBUTING: 'the same checks CI runs — N of them'"),
    (CONTRIBUTING, r"The (\w+) checks CI actually enforces are", "CONTRIBUTING: 'the N checks CI actually enforces'"),
    (SECURITY, r"runs (\w+) checks on every push", "SECURITY: 'CI runs N checks'"),
]

# Every checker the docs say is NOT in the workflow, and where it is said.
LOCAL_ONLY = [
    (README, "check_prerequisites"), (README, "check_install_narrative"),
    (README, "check_lab_assets"), (README, "check_api_doc"),
    (README, "check_operations_doc"), (README, "check_repo_metadata"),
    (CONTRIBUTING, "check_prerequisites"), (CONTRIBUTING, "check_install_narrative"),
    (CONTRIBUTING, "check_lab_assets"), (CONTRIBUTING, "check_operations_doc"),
    (CONTRIBUTING, "check_api_doc"), (CONTRIBUTING, "check_repo_metadata"),
    (SECURITY, "check_prerequisites"), (SECURITY, "check_install_narrative"),
    (SECURITY, "check_lab_assets"), (SECURITY, "check_api_doc"),
    (SECURITY, "check_operations_doc"), (SECURITY, "check_repo_metadata"),
]

# The complement sentence each doc uses to say "these are the rest, and they are not in CI".
# (file, regex, [(group index, what it counts)], label)
COMPLEMENTS = [
    (CONTRIBUTING,
     r"plus the (\w+) claim\s+checkers that are written and verified but \*\*not yet in the workflow\*\*",
     [(1, "the checkers not yet in the workflow")],
     "CONTRIBUTING: 'plus the N claim checkers ... not yet in the workflow'"),
    (README,
     r"the checks to run before pushing \((\w+) run in CI, (\w+) are claim checkers run by hand\)",
     [(1, "the checks in CI"), (2, "the checkers run by hand")],
     "README: 'N run in CI, M are claim checkers run by hand'"),
]

STEP_LIST = re.compile(
    r"^(python3 -m py_compile backend/main\.py|bash -n install\.sh|python3 tools/(\w+)\.py|#\s*10\.)"
)


def main():
    for path, label in ((CI, "ci.yml"), (README, "README.md"),
                        (CONTRIBUTING, "CONTRIBUTING.md"), (SECURITY, "SECURITY.md")):
        if not os.path.isfile(path):
            die(f"{label} is missing")

    steps, found = ci_checks()
    keys = [k for k, _ in found]
    n_ci = len(keys)
    if n_ci == 0:
        die("no checks parsed out of ci.yml — the parser or the file changed shape")
    ok("ci.yml's steps parse as checks", f"{n_ci}: {', '.join(n for _, n in found)}")

    # 1. nothing unrecognised — a new step the tool cannot classify means a doc count may be off.
    unknown = [n for k, n in found if k.startswith("unrecognised:")]
    if unknown:
        bad("every ci.yml check is one this tool can classify",
            "unclassified step(s): " + "; ".join(unknown))
    else:
        ok("every ci.yml check is one this tool can classify")

    # 2. each stated count == the workflow's count
    for path, pattern, label in COUNTS:
        text = open(path, encoding="utf-8").read()
        m = re.search(pattern, text)
        if not m:
            bad(f"{label} is still present", "sentence not found (it was reworded — update this tool)")
            continue
        try:
            claimed = num(m.group(1))
        except KeyError:
            bad(f"{label} is a number this tool can read", f"got {m.group(1)!r}")
            continue
        if claimed == n_ci:
            ok(f"{label} == ci.yml", f"{claimed}")
        else:
            bad(f"{label} == ci.yml", f"doc says {claimed}, ci.yml runs {n_ci}")

    # 3. checkers the docs call local-only must not be in the workflow
    wrong = [t for p, t in LOCAL_ONLY
             if t in keys and f"not yet in the workflow" in open(p, encoding="utf-8").read()]
    if not wrong:
        ok("no checker is called 'not yet in the workflow' while ci.yml runs it",
           f"{len(set(t for _, t in LOCAL_ONLY))} local-only tool(s) cross-checked")
    else:
        bad("no checker is called 'not yet in the workflow' while ci.yml runs it",
            "now in CI but docs say not: " + ", ".join(sorted(set(wrong))))

    # 3b. the complement: each doc's "N checkers are not in CI / M are" must match the tree
    local_tools = sorted(set(t for _, t in LOCAL_ONLY))
    not_in_ci = [t for t in local_tools if t not in keys]
    for path, pattern, groups, label in COMPLEMENTS:
        text = open(path, encoding="utf-8").read()
        m = re.search(pattern, text)
        if not m:
            bad(f"{label} is still present", "sentence not found (it was reworded — update this tool)")
            continue
        expected = {"the checkers not yet in the workflow": len(not_in_ci),
                    "the checks in CI": n_ci,
                    "the checkers run by hand": len(not_in_ci)}
        wrong = []
        for idx, what in groups:
            got = m.group(idx)
            if not got.isdigit():
                try:
                    got = num(got)
                except KeyError:
                    wrong.append(f"{what}: cannot read {m.group(idx)!r}")
                    continue
            if int(got) != expected[what]:
                wrong.append(f"{what}: doc says {got}, tree says {expected[what]}")
        if not wrong:
            ok(f"{label} == the tree", " · ".join(f"{w} {expected[w]}" for _, w in groups))
        else:
            bad(f"{label} == the tree", "; ".join(wrong))

    # 4. CONTRIBUTING's hand-run block against itself and against ci.yml
    lines = open(CONTRIBUTING, encoding="utf-8").read().splitlines()
    entries, in_block = [], False
    for line in lines:
        if line.startswith("```bash"):
            in_block = entries == []
            continue
        if line.startswith("```"):
            in_block = False
            continue
        if in_block and STEP_LIST.search(line.strip()):
            cmd = line.strip()
            tool = "py_compile" if cmd.startswith("python3 -m py_compile") else (
                "install.sh" if cmd.startswith("bash -n") else (
                    "secrets-grep" if re.match(r"#\s*10\.", cmd) else STEP_LIST.search(cmd).group(2)))
            claims_ci = "— in CI" in line
            entries.append((cmd, tool, claims_ci))
    if len(entries) < 5:
        bad("CONTRIBUTING's step list is still parseable", f"{len(entries)} entries found")
    else:
        mismatched = [(c, t, claims_ci) for c, t, claims_ci in entries
                      if t not in ("unrecognised",) and claims_ci != (t in keys)]
        if len(entries) != n_ci + len(not_in_ci):
            bad("CONTRIBUTING's step list has a line for every checker in this repo",
                f"{len(entries)} entries, but ci.yml has {n_ci} and {len(not_in_ci)} local-only "
                f"tool(s) are described elsewhere — a checker with no line here will never be run by hand")
        else:
            ok("CONTRIBUTING's step list has a line for every checker in this repo", f"{len(entries)}")
        if not mismatched:
            ok("every line of CONTRIBUTING's step list agrees with ci.yml",
               f"{len(entries)} entries, {sum(1 for _, t, _ in entries if t in keys)} in CI")
        else:
            bad("every line of CONTRIBUTING's step list agrees with ci.yml",
                "; ".join(f"{t}: doc says {'in CI' if c else 'local only'}, "
                          f"ci.yml says {'in CI' if t in keys else 'not in CI'}"
                          for _, t, c in mismatched))

    info("NOT checked here", "that CI passed (the API's word), and whether each step's command "
                             "is a good check — this tool reads the workflow, it does not run it")

    width = max(len(c) for _, c, _ in results)
    fails = 0
    for status, claim, detail in results:
        if status == FAIL:
            fails += 1
        line = f"[{status}] {claim.ljust(width)}"
        if detail:
            line += f"  — {detail}"
        print(line)
    checked = sum(1 for s, _, _ in results if s in (PASS, FAIL))
    print(f"\n[check_ci_doc] {checked - fails}/{checked} claims hold; "
          f"{sum(1 for s, _, _ in results if s == INFO)} surface(s) named as out of scope.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
