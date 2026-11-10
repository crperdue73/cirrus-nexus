#!/usr/bin/env python3
"""
check_canary_pack.py -- does every canary lab the gate runs also appear in the
pack's own README, with the verdict the gate actually asserts?

WHY THIS EXISTS
    `tools/canaries/check_lint_canaries.sh` proves one thing well: every canary
    file `<label>__<EXPECTED>.yml` gets exactly EXPECTED back from the linter.
    It reads the expected verdict out of the FILE NAME. So the file name is a
    claim, and the gate trusts it without question.

    `tools/canaries/lab-pack/README.txt` is the pack's own description and it
    lists the same files, again as NAME -> verdict. Nothing compared the two.
    Measured 2026-11-10: `nogr__NO-GRADER.yml` and `noexp__NO-EXPECTED.yml`
    were added to the pack on 2026-11-09 (commit 0498da2, "canary gate 5 -> 7
    labs") and never added to README.txt. The gate still printed "canary gate
    OK" over eight files while the README listed six -- and the README's note
    ("an SOLVED canary makes that run exit 1") was stale the same way, because
    the pack has carried an ERROR lab and a NO-TOPOLOGY lab since 2026-11-08/09
    and the pack-level exit code is 2, not 1.

    This is the self-citing failure the workspace rules name: a document that
    described the pack at one point, was copied forward, and kept reading as
    authoritative because nothing ever re-read it.

WHAT IT CHECKS (pack = tools/canaries/lab-pack, override with --pack)
    1. Every `*.yml` in the pack has a row in README.txt naming the file.
    2. Every file named in README.txt exists in the pack.
    3. The verdict in the README row == the verdict in the file name, ...__<V>.
    4. That verdict is one the linter can actually print (VERDICTS below), so a
       typo in a file name cannot be enshrined as an expectation.
    5. If the README states the pack-level exit code ("exit code is N"), N
       equals the code the gate's own header says this pack produces. The gate
       does not assert that code -- it asserts the per-lab verdicts -- so this
       compares prose to prose; running the linter is what tests the gate's
       statement itself.

WHAT IT DOES NOT CHECK
    It does not run the linter. That is the gate's job and it stays the gate's
    job; this reads the pack's description against the pack. A green result here
    means the README is not lying about what is in the pack, not that the linter
    still reads the labs correctly. Both are needed; neither substitutes.

Exit 0 = README and pack agree. Exit 1 = they disagree (details printed).
Stdlib only, no dependencies.
"""

import argparse
import glob
import os
import re
import sys

# The verdicts tools/lint_lab_pack.py can emit as a per-lab status. Keep in the
# tool's own spelling; a new verdict added there must be added here too, which
# is intentional -- an unrecognised verdict in a file name is exactly how a
# canary ends up asserting nothing.
VERDICTS = (
    "SOLVED",
    "PARTIAL",
    "UNSOLVED",
    "ERROR",
    "NO-TOPOLOGY",
    "NO-GRADER",
    "NO-EXPECTED",
)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PACK = os.path.join(HERE, "canaries", "lab-pack")
GATE = os.path.join(HERE, "canaries", "check_lint_canaries.sh")


def split_name(filename):
    """`demo2-shape__PARTIAL.yml` -> ('demo2-shape', 'PARTIAL')."""
    stem = filename[:-4] if filename.endswith(".yml") else filename
    if "__" not in stem:
        return stem, None
    label, _, verdict = stem.rpartition("__")
    return label, verdict


def readme_rows(text):
    """Map filename -> verdict as described in the README, or raise ValueError.

    A row is expected to look like (leading whitespace and the -> arrow vary):
        demo2-shape__PARTIAL.yml   pc-a + router pre-applied   -> PARTIAL 3/4
    The verdict is the first line-token AFTER '->' that is a known verdict
    (VERDICTS), so a row may annotate -- "-> SOLVED (RED FLAG)", "-> SOLVED
    (RED FLAG, fake switch)" -- without the annotation being mistaken for the
    verdict. A row that names no known verdict is reported. A row for a .yml
    file with no '->' is a row that describes the file without saying what to
    expect; that is reported rather than guessed at.
    """
    rows = {}
    problems = []
    for line in text.splitlines():
        m = re.search(r"([A-Za-z0-9_.\-]+\.yml)", line)
        if not m:
            continue
        filename = m.group(1)
        rest = line[m.end():]
        if "->" not in rest:
            problems.append(
                "README row for %s states no verdict (no '->' on the line)" % filename
            )
            continue
        verdict = rest.split("->", 1)[1].strip().split()
        token = verdict[0] if verdict else ""
        # A row may annotate the verdict ("RED FLAG (fake switch)"); the
        # verdict is the first KNOWN token on the line, so the annotation does
        # not have to be stripped by hand every time someone edits the README.
        for word in verdict:
            if word.strip("(),") in VERDICTS:
                token = word.strip("(),")
                break
        rows[filename] = token
    return rows, problems


def check(pack):
    failures = []
    notes = []

    readme_path = os.path.join(pack, "README.txt")
    if not os.path.isfile(readme_path):
        return ["missing %s -- the pack has no description to check" % readme_path], notes
    with open(readme_path, encoding="utf-8") as fh:
        readme_text = fh.read()

    rows, row_problems = readme_rows(readme_text)
    failures.extend(row_problems)

    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(pack, "*.yml")))

    # 1. every canary file is described, with a verdict
    for filename in files:
        if filename not in rows:
            failures.append(
                "%s is in the pack but not in README.txt (a canary no reader can find, "
                "and no described purpose)" % filename
            )

    # 2. every described file is in the pack
    for filename in sorted(rows):
        if filename not in files:
            failures.append(
                "README.txt describes %s, which is not in the pack (deleted canary still "
                "reading as coverage)" % filename
            )

    # 3. file-name verdict == README verdict, and both are real verdicts
    for filename in files:
        _label, name_verdict = split_name(filename)
        if name_verdict is None:
            failures.append(
                "%s has no __<VERDICT> suffix, so the gate has nothing to assert for it"
                % filename
            )
            continue
        if name_verdict not in VERDICTS:
            failures.append(
                "%s asserts %r, which lint_lab_pack.py cannot print (known: %s)"
                % (filename, name_verdict, ", ".join(VERDICTS))
            )
        described = rows.get(filename)
        if described is not None and described != name_verdict:
            failures.append(
                "%s: README says %s, the file name says %s -- the gate asserts the file "
                "name, so the README is describing a different test"
                % (filename, described, name_verdict)
            )

    # 4. the pack-level exit code, where the README states one.
    #
    # Read the code out of the gate's comment block ("this pack is built to
    # produce 2"), NOT out of its `case` statement: the case lists every code
    # the gate tolerates (0|1|2), which is a different question. The first
    # version of this check read the case statement and passed a README that was
    # wrong by one -- recorded here so it is not rebuilt the same way.
    #
    # Scope, stated plainly: the gate asserts per-lab VERDICTS, not the
    # pack-level code. What the pack exits with is a property of the linter's
    # ordering rules and is measured by running it. This check holds the README
    # to what the gate says the pack produces; the run tests the gate's
    # statement itself.
    codes_in_readme = set(re.findall(r"exit code is\D{0,3}([012])\b", readme_text))
    expected_code = None
    if os.path.isfile(GATE):
        with open(GATE, encoding="utf-8") as fh:
            gate_text = fh.read()
        m = re.search(r"this pack is built to produce ([012])", gate_text)
        if m:
            expected_code = m.group(1)
    if expected_code is not None:
        if codes_in_readme and expected_code not in codes_in_readme:
            failures.append(
                "README.txt says the pack exits %s, but the gate documents this pack as "
                "producing exit %s (the linter's code changed; the description did not)"
                % ("/".join(sorted(codes_in_readme)), expected_code)
            )
        elif not codes_in_readme:
            notes.append(
                "README.txt does not state the pack-level exit code (the gate expects %s); "
                "not required, but it is the first thing a reader trips over" % expected_code
            )

    notes.append(
        "pack: %d canary file(s), %d README row(s); verdicts %s"
        % (len(files), len(rows), ", ".join(sorted({split_name(f)[1] or "?" for f in files})))
    )
    return failures, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1].strip())
    ap.add_argument("--pack", default=DEFAULT_PACK, help="canary pack directory")
    args = ap.parse_args()

    if not os.path.isdir(args.pack):
        print("[check_canary_pack] no pack at %s" % args.pack)
        return 2

    failures, notes = check(args.pack)
    for note in notes:
        print("  note: %s" % note)
    if failures:
        for failure in failures:
            print("  FAIL: %s" % failure)
        print("[check_canary_pack] %d disagreement(s) between README.txt and the pack" % len(failures))
        return 1
    print("[check_canary_pack] OK -- README.txt describes every canary in the pack, with the "
          "verdict the gate asserts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
