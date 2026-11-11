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
     comment says whether it is "in CI" or "local only", and that must match ci.yml — for every
     entry, not just the ones CI runs.
  5. The ORDER. The entries the block marks `— in CI` are listed in the order a reader should run
     them; ci.yml must run them in that same order. Labels and commands can both be right while the
     sequence drifts, and then the block no longer describes the workflow it claims to mirror
     (same failure as 2026-11-06 12:00, one axis over).

What it does NOT check: whether a step's command is any good, whether the workflow is valid
YAML Actions semantics, or whether CI passed — that last one is the API's word, not this tool's.
It reads the file. It does not run the workflow. Sub-claims inside a step (e.g. a version named in
prose) are only checked where a claim below names them.
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
    # Not a check — `uses:` only, no `run:` — and it used to be skipped by the NOT_A_CHECK prefix.
    # Anchoring it keeps it out of the check count while letting a claim below name its version, so a
    # `python-version` change in ci.yml breaks the sentence that quotes it.
    "Set up Python": ("actions/setup-python@", "setup-python"),
}
# Keys in `found` that are runner steps rather than checks: never counted, never listed as checks.
NON_CHECK_KEYS = {"setup-python"}
# The three step-list lines that are not claim checkers. Defined at module level because the order
# claim below needs it too — it used to be a local inside the step-list branch, which meant the order
# claim read a name defined in a sibling block and silently filtered nothing.
NON_CHECKERS = {"py_compile", "install.sh", "secrets-grep"}
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
        if not cmds and name.startswith(NOT_A_CHECK) and name not in ANCHORED_BY_COMMAND:
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


def ci_check_keys():
    """ci.yml's check keys, in workflow order — runner steps like setup-python excluded."""
    _, found = ci_checks()
    return [k for k, _ in found if k not in NON_CHECK_KEYS]


TOOLS = [
    "check_self_contained",
    "check_repo_metadata",
    "check_prerequisites",
    "check_install_narrative",
    "check_lab_assets",
    "check_operations_doc",
    "check_api_doc",
    "check_self_contained_doc",
    "check_pyc_staleness",
    "check_release_notes",
]

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}  # Twelve is far past what these sentences need; past it the doc should use digits,
   # and num() raising KeyError is the signal to stop spelling counts out.


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

# Every checker CONTRIBUTING and SECURITY say is NOT in the workflow, and where it is said.
#
# README used to be listed here too, name by name, and that is how its list drifted: on 2026-11-11 14:00
# the README paragraph enumerating the local-only checkers named ten of the eleven, silently omitting
# `check_repo_metadata.py`, and this tool passed 17/17 because the missing name was simply not on the
# hand-kept list it compared against. A list kept by the same hand that writes the prose cannot catch the
# prose. README's names are now DERIVED from the paragraph itself (see README_LOCAL_ONLY below) and
# checked against the tree in both directions, so a missing name and an invented name both fail.
LOCAL_ONLY = [
    (CONTRIBUTING, "check_prerequisites"), (CONTRIBUTING, "check_install_narrative"),
    (CONTRIBUTING, "check_lab_assets"), (CONTRIBUTING, "check_operations_doc"),
    (CONTRIBUTING, "check_api_doc"), (CONTRIBUTING, "check_repo_metadata"),
    (CONTRIBUTING, "check_self_contained_doc"), (CONTRIBUTING, "check_ci_doc"),
    (CONTRIBUTING, "check_pyc_staleness"), (CONTRIBUTING, "check_release_notes"),
    (CONTRIBUTING, "check_canary_pack"),
    (SECURITY, "check_prerequisites"), (SECURITY, "check_install_narrative"),
    (SECURITY, "check_lab_assets"), (SECURITY, "check_api_doc"),
    (SECURITY, "check_operations_doc"), (SECURITY, "check_repo_metadata"),
    (SECURITY, "check_self_contained_doc"), (SECURITY, "check_ci_doc"),
    (SECURITY, "check_pyc_staleness"), (SECURITY, "check_release_notes"),
    (SECURITY, "check_canary_pack"),
]

# README's enumeration of the checkers it says are NOT CI steps. Anchored on the sentence's own
# opening and closing words so a reworded paragraph fails loudly instead of parsing as empty.
# The span is the parenthetical of "the ci.yml diff that adds it (and the other local-only claim
# checkers — `tools/check_x.py` for ..., and `tools/check_y.py` for ...) is written".
README_LOCAL_ONLY = re.compile(
    r"the `ci\.yml` diff that adds it \(\s*and\s+the\s+other\s+local-only\s+claim\s+checkers\s*—"
    r"(?P<body>.+?)\)\s+is\s+written",
    re.S,
)

# Checkers that run *in* CI rather than by hand. They must not appear in LOCAL_ONLY: that list is what
# the "not yet in the workflow" sentence counts, and a checker in both would make the docs contradict
# themselves while the tree stayed green.
#
# Empty as of 2026-11-10: check_release_notes.py was written to run in CI, but the push token lacks the
# `workflow` scope, so the ci.yml step could not be published. Until that scope is granted the checker is
# hand-run like the rest and stays in LOCAL_ONLY. Move it here in the same commit that adds the ci.yml
# step, and fix the four/five counts in README, CONTRIBUTING and SECURITY with it.
IN_CI_TOOLS = []

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
    r"^(python3 -m py_compile backend/main\.py|bash -n install\.sh|python3 tools/(\w+)\.py|#\s*\d+\.\s*no obvious secrets committed)"
)


def main():
    for path, label in ((CI, "ci.yml"), (README, "README.md"),
                        (CONTRIBUTING, "CONTRIBUTING.md"), (SECURITY, "SECURITY.md")):
        if not os.path.isfile(path):
            die(f"{label} is missing")

    steps, found = ci_checks()
    keys = ci_check_keys()
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
            # the leading "N." of the line is the step number the prose talks about
            m_num = re.match(r"(?:python3|bash|#)\s.*?#\s*(\d+)\.", cmd)
            step_no = int(m_num.group(1)) if m_num else None
            tool = "py_compile" if cmd.startswith("python3 -m py_compile") else (
                "install.sh" if cmd.startswith("bash -n") else (
                    "secrets-grep" if re.search(r"#\s*\d+\.\s*no obvious secrets committed", cmd)
                    else STEP_LIST.search(cmd).group(2)))
            claims_ci = "— in CI" in line
            entries.append((cmd, tool, claims_ci, step_no))
    if len(entries) < 5:
        bad("CONTRIBUTING's step list is still parseable", f"{len(entries)} entries found")
    else:
        mismatched = [(c, t, claims_ci) for c, t, claims_ci, _ in entries
                      if t not in ("unrecognised",) and claims_ci != (t in keys)]
        # The block has one line per tool plus the py_compile / shell-lint / secrets-grep lines, so the
        # count to agree with is the *tools* (ci.yml's checker steps + every checker not in it), not
        # ci.yml's total step count — the two differ by the three lines that are not checkers. This
        # comparison had been `n_ci + len(not_in_ci)`, which only equalled the block's length while the
        # secrets-grep line failed to parse (see STEP_LIST): 11 lines vs. 10 could never have passed.
        checker_lines = [t for _, t, _, _ in entries if t not in NON_CHECKERS]
        # every checker this repo has = every tools/check_*.py, read from the tree, not from a list here
        repo_checkers = sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "tools"))
                               if f.startswith("check_") and f.endswith(".py"))
        if sorted(set(checker_lines)) != repo_checkers:
            bad("CONTRIBUTING's step list has a line for every checker in this repo",
                f"block lines {sorted(set(checker_lines))} vs. tools/check_*.py {repo_checkers}; "
                f"differing: {sorted(set(checker_lines) ^ set(repo_checkers))}")
        else:
            ok("CONTRIBUTING's step list has a line for every checker in this repo",
               f"{len(repo_checkers)} checker(s), {len(entries)} entries incl. 3 non-checker steps")
        # and the docs that name local-only checkers must name all of the ones ci.yml does not run
        named_local = {t for _, t in LOCAL_ONLY}
        unnamed = [t for t in repo_checkers if t not in keys and t not in named_local]
        if unnamed:
            bad("every checker not in ci.yml is named as local-only in the docs",
                f"never mentioned as local-only: {unnamed}")
        else:
            ok("every checker not in ci.yml is named as local-only in the docs",
               f"{len([t for t in repo_checkers if t not in keys])} local-only tool(s)")

        # 4b. README's own enumerated list, DERIVED rather than transcribed. Both directions:
        #     every checker ci.yml does not run must be in the paragraph, and every name in the
        #     paragraph must be a checker that exists and that ci.yml does not run. The hand-kept
        #     list this replaces (`(README, "check_x")` rows above) could only ever prove that the
        #     names it already knew about were still absent from ci.yml — a name missing from both
        #     the list and the README was invisible, which is exactly what happened to
        #     check_repo_metadata.py until 2026-11-11 14:00.
        readme_text = open(README, encoding="utf-8").read()
        m_ro = README_LOCAL_ONLY.search(readme_text)
        expected_local = [t for t in repo_checkers if t not in keys]
        if not m_ro:
            bad("README enumerates the checkers it says are not CI steps",
                "paragraph not found (it was reworded — update this tool)")
        else:
            body = m_ro.group("body")
            readme_names = set(re.findall(r"`tools/(check_[a-z_]+)\.py`", body))
            missing = [t for t in expected_local if t not in readme_names]
            not_a_checker = sorted(
                t for t in readme_names
                if not os.path.isfile(os.path.join(ROOT, "tools", t + ".py")))
            already_ci = sorted(t for t in readme_names if t in keys)
            problems = []
            if missing:
                problems.append(f"README omits {missing}")
            if not_a_checker:
                problems.append(f"README names checker(s) not in tools/: {not_a_checker}")
            if already_ci:
                problems.append(f"README calls these 'local only' but ci.yml runs them: {already_ci}")
            if problems:
                bad("README's local-only list == the tree, both ways",
                    "; ".join(problems) + f" (tree: {expected_local})")
            else:
                ok("README's local-only list == the tree, both ways",
                   f"{len(readme_names)} name(s), derived from the paragraph not a list here")
        if not mismatched:
            ok("every line of CONTRIBUTING's step list agrees with ci.yml",
               f"{len(entries)} entries, {sum(1 for e in entries if e[1] in keys)} in CI")
        else:
            bad("every line of CONTRIBUTING's step list agrees with ci.yml",
                "; ".join(f"{t}: doc says {'in CI' if c else 'local only'}, "
                          f"ci.yml says {'in CI' if t in keys else 'not in CI'}"
                          for _, t, c in mismatched))

    # 5. the *second* statement of which steps are in CI must agree with the block's own markers.
    #    The block above carries the truth (one `— in CI` marker per line, already cross-checked
    #    against ci.yml in step 4). Later prose restates it in words, and until 2026-11-06 two
    #    sentences contradicted each other about the same fact while both doc and tree stayed green:
    #    "CI does not run steps 4–7, 9 or 10" and "The four checks CI actually enforces are steps
    #    1–3 and 8" — the second naming step 8, which is check_operations_doc, a local-only line.
    #    A number is not a name; the prose now names the checks, and this checks the names.
    in_ci_steps = {no for _, _, c, no in entries if c and no is not None}
    ck_tools_all = {t for _, t, _, _ in entries}
    ck_tools_in_ci = {t for _, t, c, _ in entries if c}
    prose = open(CONTRIBUTING, encoding="utf-8").read()
    m = re.search(r"The (?:\w+) checks CI actually enforces are (.{0,400}?)\.\s", prose, re.S)
    if not m:
        bad("CONTRIBUTING's 'what CI actually enforces' sentence is still present",
            "sentence not found (it was reworded — update this tool)")
    else:
        sentence = re.sub(r"\s+", " ", m.group(1))
        named = {n[:-3] for n in re.findall(r"`(check_[a-z_]+\.py)`", sentence)}
        block_tools = ck_tools_in_ci - {"py_compile", "install.sh", "secrets-grep"}
        if named != block_tools:
            bad("CONTRIBUTING's prose names exactly the checkers the block marks in CI",
                f"prose names {sorted(named) or 'none'}, block marks {sorted(block_tools)}")
        else:
            ok("CONTRIBUTING's prose names exactly the checkers the block marks in CI",
               f"{len(named)} checker(s): " + (", ".join(sorted(named)) or "— the block marks none"))
        # any "step N" the sentence offers must be a step the block marks in CI
        cited = {int(n) for n in re.findall(r"steps? (\d+)", sentence)}
        cited |= {int(n) for n in re.findall(r"step (\d+)", sentence)}
        stray = sorted(n for n in cited if n not in in_ci_steps)
        if stray:
            bad("CONTRIBUTING's prose cites no step number the block marks local-only",
                f"cited step(s) {stray} are not marked `— in CI`")
        else:
            ok("CONTRIBUTING's prose cites no step number the block marks local-only",
               f"{'no bare step numbers' if not cited else sorted(cited)}; block's in-CI steps "
               f"{sorted(in_ci_steps)}")

    # 6. the ORDER of the in-CI block entries == the order ci.yml runs them in. Only the entries the
    #    block marks `— in CI` are ordered against the workflow: the local-only lines are interleaved
    #    for reading, and their position says nothing about CI. A block reordered by hand, or a
    #    ci.yml step moved, now fails here even though every label and command is still correct.
    #
    #    NOTE (three bugs, each found by mutating and reading the PASS/FAIL detail):
    #    1. the first version compared `keys` filtered BY `block_ci_order`'s own membership — a
    #       tautology that could only detect a duplicate, never a reordering;
    #    2. the second filtered the ci.yml side by NON_CHECKERS, the *block's* labels for its three
    #       non-checker lines. Applied to ci.yml's keys that deleted three of the four real steps, so
    #       a one-element list was compared to another and nearly anything passed;
    #    3. the third compared `block_ci_order` (block keys, which by construction EXCLUDE those
    #       three names) to the full ci.yml key list, so the honest tree failed with
    #       "block: check_self_contained | ci.yml: py_compile → install.sh → ...".
    #    The two sides use different vocabularies and neither is a subset of the other, so this now
    #    compares positions: every entry the block marks `— in CI` must appear in ci.yml in the same
    #    relative order as it appears in the block. That is exactly the drift this claim exists for.
    block_in_ci = [t for _, t, c, _ in entries if c]
    ci_pos = {k: i for i, k in enumerate(keys)}
    misplaced = [t for t in block_in_ci if t not in ci_pos]
    block_ci_order = [t for t in block_in_ci if t in ci_pos]
    if misplaced:
        bad("CONTRIBUTING's in-CI step order == ci.yml's order",
            f"block marks {misplaced} `— in CI` but ci.yml has no such step")
    elif block_ci_order != sorted(block_ci_order, key=ci_pos.get):
        ci_seq = sorted(block_ci_order, key=ci_pos.get)
        bad("CONTRIBUTING's in-CI step order == ci.yml's order",
            f"block: {' → '.join(block_ci_order)} | ci.yml runs them: {' → '.join(ci_seq)}")
    else:
        ok("CONTRIBUTING's in-CI step order == ci.yml's order",
           f"{' → '.join(block_ci_order)}" if block_ci_order else "— the block marks no check in CI")

    # 7. the one place CONTRIBUTING quotes a value *inside* a ci.yml step: the `python-version`
    #    floor the parked workflow patch would add. The sentence names it, so the workflow must still
    #    be below it — the day someone bumps ci.yml to the floor, the sentence becomes a no-op promise
    #    and nothing else here would notice.
    m = re.search(r"`python-version` floor of `([\d.]+)`", prose)
    m_ver = re.search(r"python-version:\s*[\"']?([\d.x]+)", open(CI, encoding="utf-8").read())
    if not m:
        bad("CONTRIBUTING's `python-version` floor sentence is still present",
            "sentence not found (it was reworded — update this tool)")
    elif not m_ver:
        bad("ci.yml still sets a python-version this tool can read", "no `python-version:` in ci.yml")
    else:
        doc_floor, ci_ver = m.group(1), m_ver.group(1)
        try:
            ci_tuple = tuple(int(x) for x in ci_ver.split("."))
            floor_tuple = tuple(int(x) for x in doc_floor.split("."))
        except ValueError:
            ok("CONTRIBUTING's `python-version` floor is consistent with ci.yml",
               f"ci.yml sets {ci_ver!r} (not a numeric version — compared at ref time, not here)")
        else:
            if ci_tuple < floor_tuple:
                ok("CONTRIBUTING's `python-version` floor is consistent with ci.yml",
                   f"ci.yml sets {ci_ver}, doc says the patch floors it at {doc_floor} — true")
            else:
                bad("CONTRIBUTING's `python-version` floor is consistent with ci.yml",
                    f"ci.yml already sets {ci_ver} ≥ the {doc_floor} floor the doc says it would add")

    # 8. prose paragraphs that say "Step N checks ..." must agree with the block's number for the
    #    checker the sentence is about. That checker is the FIRST tool named after the step number,
    #    not every tool in the paragraph: "Step 5 reads the README's Prerequisites block ... It reads
    #    the installer and the tree" mentions install.sh as an object, not as the step's subject, and
    #    a first draft of this claim flagged it as "install.sh: prose says step 6, block says 2".
    #    This is the drift the 2026-11-05 20:00 run recorded and left in place: the startup-config
    #    paragraph began "Step 7 checks ..." while the block lists the checker it describes at 8,
    #    because the list gained an entry and the prose numbers were never re-read.
    tool_step = {t: n for _, t, _, n in entries if n is not None}
    prose_steps, offenders = [], []
    for para in re.split(r"\n\s*\n", prose):
        m_s = re.search(r"\b[Ss]teps? (\d+)\b", para)
        if not m_s:
            continue
        # The subject is the checker the paragraph names, if it names one; a bare `install.sh` is
        # only the subject when no checker is named at all (e.g. "install.sh copies the project
        # into /opt/aegis (Step 6)"). Two paragraphs here are *about* check_install_narrative and
        # check_lab_assets and merely use install.sh as the thing under test — matching install.sh
        # first flagged both, which is how that distinction got made explicit.
        after = para[m_s.end():]
        subject = re.search(r"`(check_[a-z_]+\.py)`", after) or re.search(r"`(install\.sh)`", after)
        if not subject:
            continue
        t = subject.group(1)
        t = t[:-3] if t.startswith("check_") else t
        if t not in tool_step:
            continue
        n = int(m_s.group(1))
        prose_steps.append((t, n))
        if tool_step[t] != n:
            offenders.append(f"{t}: prose says step {n}, the block lists it as step {tool_step[t]}")
    if offenders:
        bad("CONTRIBUTING's prose step numbers agree with the block's numbering",
            "; ".join(offenders))
    else:
        ok("CONTRIBUTING's prose step numbers agree with the block's numbering",
           f"{len(prose_steps)} citation(s) checked, all matching: "
           + (", ".join(f"{t}=step {n}" for t, n in prose_steps)
              if prose_steps else "no single-tool step citations to compare"))

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
