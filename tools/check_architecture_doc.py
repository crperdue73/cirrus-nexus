#!/usr/bin/env python3
"""
check_architecture_doc.py -- the canary-pack row in docs/architecture.md against
the canary pack on disk.

WHY THIS EXISTS
    `docs/architecture.md` describes `tools/canaries/lab-pack/` in one table row.
    Until 2026-11-16 that row opened "eight files, one per verdict the linter can
    emit". Eight files is true; "one per verdict" is not. The pack carries seven
    distinct verdicts, because SOLVED has two files (demo2-shape__SOLVED and
    fake-switch__SOLVED -- the second is the lab that models a switch as a Linux
    PC). The row then contradicted its own opening clause further along ("two
    pre-solved on purpose"), so a careful reader could see the mismatch, and a
    fast reader took away a 1:1 mapping that does not exist.

    Nothing checked this row. `check_canary_pack.py` holds the pack's own
    README.txt to the pack, and `check_ci_doc.py` holds the checker counts -- but
    the prose in architecture.md was carried forward by hand. This is the
    self-citing failure named in the workspace rules: a sentence that described
    the pack when it was written and kept reading as authoritative because no
    tool ever re-read it.

WHAT IT CHECKS (all derived from disk, nothing transcribed here)
    1. every `*.yml` in the pack still has a `<label>__<VERDICT>` name, so the
       verdict multiset below is well defined;
    2. the row states the file count, and that count matches the pack;
    3. the row states the number of DISTINCT verdicts, and that number matches;
    4. if two files share a verdict, the row says so -- it must not claim a 1:1
       file-per-verdict mapping (the actual 2026-11-16 bug);
    5. every verdict the pack exercises is named in the row, and no verdict the
       linter cannot emit is named there.

WHAT IT DOES NOT CHECK
    It does not run the linter, and it does not re-derive the verdict for any
    canary -- that is `check_lint_canaries.sh`'s job (it executes the linter) and
    `check_canary_pack.py`'s (it holds the pack README to the file names). A
    green result here means architecture.md describes the pack's *shape*
    truthfully, not that the linter reads the labs correctly.

Exit 0 = the row and the pack agree. Exit 1 = they disagree (details printed).
Stdlib only, no dependencies.
"""

import os
import re
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACK = os.path.join(HERE, "canaries", "lab-pack")
DOC = os.path.join(ROOT, "docs", "architecture.md")

# Verdicts `lint_lab_pack.py` can print. Read from the tool's own docstring block
# rather than hardcoded, so adding a verdict there does not silently drift past
# this check.
LINTER = os.path.join(HERE, "lint_lab_pack.py")

# Words a row may use for a count. Kept small on purpose: a number written as an
# unusual word should fail loudly here rather than pass unread.
NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20,
}


def n2i(word):
    """'eight' -> 8, '8' -> 8, anything else -> None."""
    w = word.strip().lower()
    if w.isdigit():
        return int(w)
    return NUMBERS.get(w)


def linter_verdicts():
    """The verdict tokens lint_lab_pack.py assigns to result['status']."""
    try:
        with open(LINTER, encoding="utf-8") as fh:
            src = fh.read()
    except OSError:
        return None
    found = set(re.findall(r'result\["status"\]\s*=\s*"([A-Z][A-Z-]*)"', src))
    # UNKNOWN is an initial placeholder overwritten on every path, never a verdict.
    found.discard("UNKNOWN")
    return found


def pack_verdicts():
    """[(filename, verdict)] for every yml in the pack, sorted."""
    out = []
    for p in sorted(glob.glob(os.path.join(PACK, "*.yml"))):
        name = os.path.basename(p)
        stem = name[:-4]
        if "__" not in stem:
            out.append((name, None))
            continue
        out.append((name, stem.rsplit("__", 1)[1]))
    return out


def find_row(text):
    """The architecture.md table row describing the canary pack, or None."""
    for line in text.splitlines():
        if line.lstrip().startswith("|") and "canaries/lab-pack/" in line:
            return line
    return None


def check():
    failures = []
    notes = []

    if not os.path.isdir(PACK):
        return ["canary pack not found at %s" % PACK], notes
    if not os.path.isfile(DOC):
        return ["docs/architecture.md not found at %s" % DOC], notes

    pairs = pack_verdicts()
    unnamed = [n for n, v in pairs if v is None]
    if unnamed:
        failures.append(
            "canary file(s) with no __<VERDICT> suffix, so the verdict set is "
            "undefined: %s" % ", ".join(unnamed)
        )
        return failures, notes

    n_files = len(pairs)
    verdicts = sorted({v for _, v in pairs})
    n_verdicts = len(verdicts)

    # verdict -> [filenames], for the shared-verdict claim
    by_verdict = {}
    for name, verdict in pairs:
        by_verdict.setdefault(verdict, []).append(name)
    shared = {v: f for v, f in by_verdict.items() if len(f) > 1}

    with open(DOC, encoding="utf-8") as fh:
        text = fh.read()
    row = find_row(text)
    if row is None:
        return [
            "no table row mentioning `canaries/lab-pack/` in docs/architecture.md "
            "(the row was reworded or removed -- update this tool)"
        ], notes

    # 2. the file count, as a number word or digit, immediately before "file"
    m = re.search(r"\b([A-Za-z]+|\d+)\s+(?:canary\s+)?files?\b", row)
    if not m:
        failures.append(
            "the canary row states no file count (expected e.g. 'eight files'); "
            "the pack has %d" % n_files
        )
    else:
        claimed = n2i(m.group(1))
        if claimed is None:
            failures.append(
                "the canary row's file count %r is not a number this check reads; "
                "the pack has %d" % (m.group(1), n_files)
            )
        elif claimed != n_files:
            failures.append(
                "the canary row says %d file(s); the pack has %d (%s)"
                % (claimed, n_files, ", ".join(n for n, _ in pairs))
            )
        else:
            notes.append("file count %d holds" % claimed)

    # 3. the distinct-verdict count
    m = re.search(r"\b([A-Za-z]+|\d+)\s+(?:distinct\s+)?verdicts?\b", row)
    if not m:
        failures.append(
            "the canary row states no verdict count (expected e.g. 'seven verdicts'); "
            "the pack exercises %d in %d files" % (n_verdicts, n_files)
        )
    else:
        claimed = n2i(m.group(1))
        if claimed is None:
            failures.append(
                "the canary row's verdict count %r is not a number this check reads; "
                "the pack exercises %d" % (m.group(1), n_verdicts)
            )
        elif claimed != n_verdicts:
            failures.append(
                "the canary row says %d distinct verdict(s); the pack exercises %d (%s)"
                % (claimed, n_verdicts, ", ".join(verdicts))
            )
        else:
            notes.append("verdict count %d holds" % claimed)

    # 4. the actual bug: a 1:1 mapping claim when two files share a verdict.
    #    The corrected sentence negates the claim on purpose ("...seven verdicts
    #    the linter can emit, not one file per verdict: SOLVED carries two...").
    #    A regex for the bare phrase fires on that negation -- measured 2026-11-16
    #    against the fix itself, which is the only reason the negation guard is
    #    below rather than assumed unnecessary.
    ONE_PER = re.compile(r"\bone\s+(?:file\s+)?per\s+verdict\b", re.I)
    NEGATED = re.compile(r"\b(?:not|never|no)\s+$", re.I)
    claims_one_per = False
    for hit in ONE_PER.finditer(row):
        before = row[: hit.start()]
        # "not one per verdict" / "never one per verdict" -- explicitly denied.
        if NEGATED.search(before):
            continue
        claims_one_per = True
        break
    if claims_one_per and shared:
        failures.append(
            "the canary row claims 'one per verdict' but %d verdict(s) carry more "
            "than one file (%s), so %d files cover only %d verdicts"
            % (
                len(shared),
                "; ".join("%s -> %s" % (v, ", ".join(f)) for v, f in sorted(shared.items())),
                n_files,
                n_verdicts,
            )
        )
    elif claims_one_per:
        notes.append("'one per verdict' holds (no verdict is duplicated)")
    else:
        notes.append("no 1:1 file-per-verdict claim (negated or absent)")

    # 5a. every verdict the pack exercises is named
    missing = [v for v in verdicts if v not in row]
    if missing:
        failures.append(
            "the canary row never names verdict(s) the pack exercises: %s" % ", ".join(missing)
        )
    else:
        notes.append("all %d exercised verdicts named" % n_verdicts)

    # 5b. no verdict named that the linter cannot emit
    known = linter_verdicts()
    if known is None:
        notes.append("could not read lint_lab_pack.py -- skipped the emitted-verdict cross-check")
    else:
        named = {v for v in re.findall(r"\b[A-Z][A-Z-]{2,}\b", row) if v in known or v.isupper()}
        bogus = sorted(v for v in named if v not in known and v in {
            "SOLVED", "PARTIAL", "UNSOLVED", "ERROR", "NO-TOPOLOGY", "NO-GRADER",
            "NO-EXPECTED", "NO-GRADER", "UNKNOWN", "PASS", "FAIL", "SKIPPED",
        })
        if bogus:
            failures.append(
                "the canary row names verdict(s) lint_lab_pack.py cannot print: %s "
                "(it prints: %s)" % (", ".join(bogus), ", ".join(sorted(known)))
            )
        else:
            notes.append("no unemittable verdict named")

        # and the pack must actually cover every verdict the linter can print
        uncovered = sorted(known - set(verdicts))
        if uncovered:
            failures.append(
                "the linter can print verdict(s) with no canary in the pack: %s "
                "(the row's 'all seven' style claim would be false)"
                % ", ".join(uncovered)
            )
        else:
            notes.append("pack covers every verdict the linter can print")

    return failures, notes


def main():
    failures, notes = check()
    for n in notes:
        print("  note: %s" % n)
    if failures:
        for f in failures:
            print("  FAIL: %s" % f)
        print("[check_architecture_doc] FAILED -- %d problem(s)" % len(failures))
        return 1
    print(
        "[check_architecture_doc] OK -- docs/architecture.md describes the canary "
        "pack's file and verdict counts as the pack on disk actually is"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
