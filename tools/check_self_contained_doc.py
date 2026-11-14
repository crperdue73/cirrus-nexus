#!/usr/bin/env python3
"""Check `docs/SELF-CONTAINED.md` against the tool it describes.

Why this exists: that doc's job is to state the **boundary** of
`tools/check_self_contained.py` — what it proves and, at least as important, what it
does not. Both halves are claims about Python source that changes without the prose.
The "what it fails on" bullets are the easy half: delete a rule from the tool and the
sentence keeps reading as a coverage guarantee. The "what it does not check" paragraphs
are the half that actually protects a reader, and they are *negative* claims — nothing
notices the day a limitation stops being true.

So every statement the doc makes is pinned here in both directions:

  * a check the doc says the tool performs must still exist in the tool (by name);
  * a limitation the doc says the tool has must still be true of the tool (measured,
    where a measurement exists: which files the path rule scans, which suffix set, the
    list of things a cold install pulls);
  * the counts the doc quotes (the success-line numbers) must match what the tool
    computes from the tree -- including the number of anchors pinned in this file, which
    the doc states in prose and which is read from `len(DOC_ANCHORS)` rather than typed,
    and the number of claims this file makes, read from the claim list it builds (claim 7).

Two measured boundary facts are asserted here because the doc draws conclusions from
them and nothing else in the tree ties them down:
  * `docs/SELF-CONTAINED.md` and `install.sh` are exempt from the tool's own path rule
    (both are allowlisted / not applicable), so a path in either proves nothing;
  * `install.sh` derives the invoking user via `SUDO_USER` — calling `./install.sh`
    with a bare `sudo` gets `SUDO_USER=root`, which skips the caller group-fix — and the
    systemd unit it writes hard-codes `User=aegis`, while the service user is
    configurable (`SERVICE_USER`). Both are real gaps; the doc says the check does not
    read shell logic, and these are the concrete cases.
  * the doc's *remedy* for the `SUDO_USER` gap is a shell snippet, so it is checked the
    same way as the rule it describes: the invocation parser is lifted out of
    `install.sh` and run against simulated environments. A bare `sudo ./install.sh` must
    resolve to the invoking human; `sudo -E` from a `root` login must too; a login with
    neither variable must resolve to nothing (the group step is then skipped, as stated).

Exit codes match the other tools in this directory:
  0 = every claim still holds, 1 = at least one claim is now false of this tree,
  2 = could not run (the doc or the tool is missing, or a claim's anchor text is gone).
"""

import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOC = "docs/SELF-CONTAINED.md"
TOOL = "tools/check_self_contained.py"
INSTALL = "install.sh"

# Claim 8: the page groups itself with two other local-only checkers by name, so their
# targets are read out of their own sources rather than assumed. `\"README.md\"` is the
# module constant each of those tools sets; PREREQ_LIMIT is the sentence that makes the
# page's old "checked the same way" comparison false -- check_prerequisites.py reads
# patterns of README.md, it does not read this page or run any Markdown parser.
PREREQ_TOOL = "tools/check_prerequisites.py"
METADATA_TOOL = "tools/check_repo_metadata.py"
PREREQ_TOOL_NAME = "check_prerequisites.py"
METADATA_TOOL_NAME = "check_repo_metadata.py"
PREREQ_TARGET = 'README = "README.md"'
METADATA_TARGET = '"README.md"'
PREREQ_LIMIT = "does not parse Markdown prose"
CI_WORKFLOW = ".github/workflows/ci.yml"


def read(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def section(text, start, end=None):
    """The slice of `text` from `start` up to `end` (or end of text)."""
    idx = text.find(start)
    if idx < 0:
        return None
    if end is None:
        return text[idx:]
    end_idx = text.find(end, idx + len(start))
    return text[idx:] if end_idx < 0 else text[idx:end_idx]


# Text the doc must still contain, one anchor per claim. A moved or reworded sentence
# fails here on purpose: re-read it, re-measure, update this list in the same commit.
DOC_ANCHORS = [
    "runs on every push and PR **in CI**",
    "a required file (installer, backend, frontend, lab definitions, graders, pin) is missing",
    "measured against the installer's own copy block",
    "no more",
    "does *not* carry is missing (`LICENSE`)",
    "licensing problem, not an install failure",
    "lab's `startup-config` asset or `grader` module doesn't resolve inside the repo",
    "does not byte-compile",
    "developer's absolute path",
    "What it does not check: the install step",
    "cannot notice a file that was deleted before commit",
    "cannot notice an untracked file on the machine that ran it",
    "does not exercise at all is the pinned-tarball restore",
    "`UNPINNED`",
    "no tarball ships",
    # The remedy for the SUDO_USER gap. Until 2026-11-03 the doc named `sudo -E` as the
    # default fix for a bare `sudo`, and `sudo -E` is the one invocation that cannot fix it:
    # `env_reset` still sets SUDO_USER=root and sudo re-sets USER=root from the target
    # passwd entry. Measured, then corrected -- claim 6 below now runs the parser instead
    # of trusting the sentence.
    "Use a plain `sudo ./install.sh` from your",
    "`sudo -E` is only for the case where you are already `root`",
    "always add yourself to the `docker` (and `clab_admins`) group afterwards",
    "re-login before the new group membership applies",
    # Claim 9. Until 2026-11-14 the doc described the installer's `startup-config` verify
    # block as evidence -- "copies them explicitly and verifies ..." -- and nothing read it.
    # Measured, the block checks `<lab dir>/<path>`, the directory holding the topology, while
    # the copy it is verifying puts assets in `<lab dir>/assets/`; the page's own "what it does
    # not check" section says no claim here reads shell logic, so the block sat outside every
    # guard while being cited as one. Claim 9 lifts it out of install.sh and runs it.
    "it\n  verifies every `startup-config:` a shipped topology names",
    "the lab's own directory, not against an `assets/` subdirectory",
    "the check and the copy disagree",
    "the intact tree passes partly because `cp -r lab-definitions`",
]


def main():
    doc = read(DOC)
    tool = read(TOOL)
    install = read(INSTALL)
    if doc is None or tool is None or install is None:
        print("self-contained doc check: cannot run — %s, %s or %s is missing"
              % (DOC, TOOL, INSTALL))
        return 2

    claims = []

    def claim(ok, label, detail):
        claims.append((bool(ok), label, detail))

    # --- 1. The doc still says what this script thinks it says --------------------------
    absent = [a for a in DOC_ANCHORS if a not in doc]
    claim(not absent,
          "every anchored statement is still in %s" % DOC,
          "all %d anchors found" % len(DOC_ANCHORS) if not absent
          else "anchor(s) gone (re-read the doc, then this list): %s" % "; ".join(absent))

    # --- 1b. The page's own count of these anchors is derived, not typed -----------------
    #             Until 2026-11-13 the page said "pins 16" while this list held 19, and
    #             nothing read the number. A count in prose that no code derives goes stale
    #             in silence -- the exact defect this tool exists to catch, on the page that
    #             governs it. So the number is read out of this source (len(DOC_ANCHORS)) and
    #             the page is required to state it. Adding or removing an anchor without
    #             updating the page now fails here.
    n_anchors = len(DOC_ANCHORS)
    m = re.search(r"pins (\d+) of them", doc)
    claim(m is not None and int(m.group(1)) == n_anchors,
          "the page states the number of anchors this tool holds (derived from DOC_ANCHORS)",
          "DOC_ANCHORS has %d entries; page says %r"
          % (n_anchors, m.group(1) if m else "<no 'pins N of them' sentence>"))

    # --- 1c. The page's count of *claims* is derived too ---------------------------------
    #             Added 2026-11-14. The "measured against" section used to enumerate which
    #             rules the tool pins, and that enumeration was unchecked prose: it named
    #             coverage that no claim reads, and omitted claim 1b and the pin-state claim,
    #             while the tool reported 18 claims. The enumeration is gone (see the table it
    #             was replaced with), but it is now replaced by a number, and a number in prose
    #             is the same defect -- so this compares it to len(claims) AFTER the last claim
    #             is appended. It is evaluated below, at the end, not here; the append loop above
    #             simply defines the helper. See clause 7.

    # --- 2. The checks the doc says are run still exist in the tool ---------------------
    for label, pattern in [
        ("required-file check", r"for rel in REQUIRED"),
        ("repo-only (LICENSE) check reported separately", r"for rel in NOT_COPIED"),
        ("README-linked doc-asset check", r"for rel in DOCS_READER_FACING"),
        ("startup-config resolution", r"startup-config:\\s\*\(\\S\+\)"),
        ("grader-module resolution", r"grader:\\s\*\(\\S\+\)"),
        ("grader byte-compile", r"py_compile\.compile"),
        ("developer-path rule", r"/\(\?:home\|Users\)/"),
    ]:
        claim(re.search(pattern, tool),
              "tool still performs the %s" % label,
              "found" if re.search(pattern, tool) else "rule is gone from %s" % TOOL)

    # --- 3. The separate counts the doc promises are still separate --------------------
    #             The doc: the two lists are reported "under its own message so the two
    #             claims never share one number". The tool keeps that as two lists and a
    #             success line that prints both counts.
    claim(re.search(r"REQUIRED = \[", tool) and re.search(r"NOT_COPIED = \[", tool)
          and "len(REQUIRED)" in tool and "len(NOT_COPIED)" in tool,
          "install set and repo-only set are still separate lists with separate counts",
          "REQUIRED / NOT_COPIED / both counts present in the success line")

    # --- 4. The limitations the doc states are still true, measured --------------------
    # (a) The path rule scans one suffix set. Re-derive it from the tool rather than
    #     trusting the doc, then assert the doc's consequence: files outside it are not
    #     scanned (10-archive/*.conf is the tree's live example).
    m = re.search(r"TEXT_EXT = \{([^}]*)\}", tool)
    ext = ({e.strip().strip('"\'') for e in m.group(1).split(",") if e.strip()} if m else set())
    claim(".conf" not in ext and ".log" not in ext and ".bak" not in ext,
          "the path rule still skips suffixes the tree contains",
          "TEXT_EXT = %s" % ", ".join(sorted(ext)))

    allow = re.search(r"PATH_ALLOWLIST = \((.*?)\n\)", tool, re.S)
    allowed = set(re.findall(r'"([^"]+)"', allow.group(1))) if allow else set()
    claim(DOC in allowed,
          "the doc itself is still exempt from the path rule it describes",
          "PATH_ALLOWLIST = %s" % ", ".join(sorted(allowed)))

    # (b) The doc's claim that the tool reads the working tree — not the index — is what
    #     makes "a file deleted before commit" invisible. Assert it walks paths on disk.
    claim("ROOT.rglob" in tool and not re.search(r"\bgit (?:ls-files|diff|show)\b", tool),
          "the tool still reads the working tree and never consults git",
          "walk is pathlib rglob over ROOT; no git call before the path rule")

    # (c) The pin/tarball state the doc states. Read the pin the doc names, rather than
    #     trusting the sentence.
    pin = ""
    try:
        with open(os.path.join(ROOT, "assets", "frr-image.pin"), encoding="utf-8",
                  errors="replace") as fh:
            pin = fh.read()
    except OSError:
        pass
    tarball = re.findall(r"^tarball=(.*)$", pin, re.M)
    layers = re.findall(r"^layers_sha256=(.*)$", pin, re.M)
    # The pin keeps the 2026-09-19 record above the 2026-10-30 re-pin (it is a true record
    # of that date), so the CURRENT value is the last occurrence, not the first -- and a
    # first-occurrence read is exactly what would report a shipped tarball here.
    claim(tarball and not tarball[-1].strip()
          and layers and layers[-1].strip() == "UNPINNED",
          "no tarball ships and the layer chain is the UNPINNED placeholder",
          "current tarball=%r, current layers_sha256=%r"
          % (tarball[-1].strip() if tarball else "<no key>",
             layers[-1].strip() if layers else "<no key>"))

    # --- 5. The network table matches what install.sh pulls ------------------------------
    #          The doc's table lists the images a cold install pulls. The installer's
    #          pre-pull loop is the source of truth for that set.
    loop = re.search(r"for IMG in ([^;]+);", install)
    pulled = sorted(loop.group(1).split()) if loop else []
    table = section(doc, "## What a cold install pulls from the network")
    tabled = sorted(set(re.findall(r"`(ghcr\.io/[^`]+|alpine:[^`]+)`", table))) if table else []
    claim(pulled == tabled,
          "the pull table lists exactly the images install.sh pre-pulls",
          "install.sh: %s | doc: %s" % (pulled, tabled))

    # --- 6. The two concrete gaps the boundary paragraph stands on ----------------------
    claim("SUDO_USER" in install,
          "the invoking user is derived from SUDO_USER (bare `sudo` -> root -> group fix skipped)",
          "install.sh reads ${SUDO_USER} for CALLER_USER")

    # The doc's remedy, executed rather than read. The parser is lifted out of install.sh,
    # so this breaks the day someone edits it, and it is run against the environments the
    # doc makes a promise about. This is the rule that catches the doc's old advice: `sudo -E`
    # preserves the caller's USER but sudo still sets SUDO_USER=root for the target account,
    # so it resolved to root and the group step was skipped anyway.
    parser = re.search(r'^(CALLER_USER=.*)$', install, re.M)
    if parser is None:
        claim(False, "the doc's remedy for the SUDO_USER gap still works",
              "CALLER_USER assignment is gone from %s" % INSTALL)
    else:
        line = parser.group(1)
        # sudo(8) with env_reset (the Debian/Ubuntu default), as three simulated shells.
        envs = {
            "plain `sudo ./install.sh` from a normal login":
                {"SUDO_USER": "alice", "USER": "root"},
            "`sudo -E ./install.sh` from a `root` login":
                {"SUDO_USER": "root", "USER": "root"},
            "a login carrying neither variable":
                {},
        }
        got = {}
        for label, env in envs.items():
            try:
                out = subprocess.run(
                    ["env", "-i", "-u", "SUDO_USER", "-u", "USER"]
                    + ["%s=%s" % kv for kv in env.items()]
                    + ["sh", "-c", line + '; printf %s "$CALLER_USER"'],
                    capture_output=True, text=True, timeout=10)
                got[label] = out.stdout
            except (OSError, subprocess.SubprocessError) as exc:
                got[label] = "<could not run: %s>" % exc
        keys = list(envs)
        claim(got[keys[0]] == "alice" and got[keys[1]] == "root" and got[keys[2]] == "",
              "the doc's remedy for the SUDO_USER gap still works (parser executed)",
              "plain sudo -> %r (want 'alice'); sudo -E as root -> %r (want 'root', i.e. skipped "
              "as the doc says); neither var -> %r (want '')"
              % (got[keys[0]], got[keys[1]], got[keys[2]]))
    unit = section(install, "cat > /etc/systemd/system/aegis.service", "SERVICE\n")
    claim(unit is not None and "User=aegis" in unit and "SERVICE_USER" in install,
          "the unit hard-codes User=aegis while SERVICE_USER is configurable",
          "unit has User=aegis; installer sets SERVICE_USER default 'aegis'")

    # --- 8. The page's "checked the same way" sentence, held in both directions --------
    #          Added 2026-11-14. The page said these two sections "are checked the same way
    #          README's Prerequisites are" -- and nothing held that: claim 2 reads THIS tool's
    #          source and nothing else, so the sentence is a claim about *other* checkers'
    #          methods. Measured before writing the claim (not assumed):
    #            - tools/check_prerequisites.py targets README.md, and its own docstring says
    #              it "does not parse Markdown prose"; both are read out of that file here, so
    #              the sentence is rewritten to name what those two tools actually read rather
    #              than to compare methods.
    #            - the "not wired into CI" sentence names exactly those two tools; the workflow
    #              is parsed here and every check it runs must be some other tools/check_*.py,
    #              so adding check_prerequisites.py to CI fails here instead of silently making
    #              the page wrong about three tools at once.
    #          One source per direction: the first reads those two tools' sources, the second
    #          reads ci.yml. Neither trusts this page.
    prereq = read(PREREQ_TOOL) or ""
    meta = read(METADATA_TOOL) or ""
    claim(PREREQ_TARGET in prereq and PREREQ_LIMIT in prereq
          and METADATA_TARGET in meta,
          "the two tools the page groups itself with still read what the page says they read",
          "check_prerequisites.py: %s; its 'does not parse Markdown prose' sentence: %s; "
          "check_repo_metadata.py: %s"
          % ("reads %s" % PREREQ_TARGET if PREREQ_TARGET in prereq else "does NOT read %s" % PREREQ_TARGET,
             "present" if PREREQ_LIMIT in prereq else "GONE",
             "reads %s" % METADATA_TARGET if METADATA_TARGET in meta else "does NOT read %s" % METADATA_TARGET))
    ci = read(CI_WORKFLOW)
    ci_tools = re.findall(r"tools/(check_[a-z0-9_]+\.py)", ci) if ci is not None else []
    claim(ci is not None and ci_tools and not (
              {PREREQ_TOOL_NAME, METADATA_TOOL_NAME} & set(ci_tools)),
          "CI runs none of the three tools the page calls local-only by name",
          "%s is missing" % CI_WORKFLOW if ci is None
          else "ci.yml runs %d checker(s): %s; the page names %s and %s as local-only"
               % (len(ci_tools), ", ".join(sorted(set(ci_tools))) or "none",
                  PREREQ_TOOL_NAME, METADATA_TOOL_NAME))

    # --- 9. The installer's `startup-config` verify block, EXECUTED ----------------------
    #          Added 2026-11-14. The page cited this block as the reason the untracked-asset bug
    #          cannot recur, while also saying (correctly) that nothing here reads shell logic.
    #          Both cannot stand. The block's body is extracted from install.sh verbatim -- no
    #          copy lives in this file, so the claim breaks the day someone edits it -- and run
    #          against a temporary tree built from the labs this repo ships. `lab-definitions/`
    #          is copied in first, exactly as Step 6 does, so the fixtures are this tree's real
    #          files and not hand-written ones. The mutation is the bug itself: remove one asset
    #          and the block must name that lab and must not report success.
    block = re.search(
        r"# Verify, rather than assume, that the configs the shipped topologies name.*?\n"
        r"(?P<body>(?:[ \t]*#.*\n|[ \t]*\n|[ \t]*[^#\n].*\n)+?)"
        r"(?=# start_server\.py resolves its own path)", install)
    if block is None:
        claim(False, "the installer's startup-config verify block still runs (executed)",
              "the verify block is gone from %s" % INSTALL)
    else:
        prelude = 'log()  { echo "LOG   $1"; }; warn() { echo "WARN  $1"; }\n'
        result = {}
        try:
            with tempfile.TemporaryDirectory(prefix="aegis-claim9-") as tmp:
                labs = os.path.join(tmp, "lab-definitions")
                subprocess.run(["cp", "-r", os.path.join(ROOT, "lab-definitions"), tmp],
                               check=True, capture_output=True, timeout=60)
                script = os.path.join(tmp, "verify-block.sh")
                with open(script, "w", encoding="utf-8") as fh:
                    fh.write("#!/usr/bin/env bash\nset -uo pipefail\n" + prelude + block.group("body"))

                def run_tree():
                    env = {"PATH": "/usr/bin:/bin", "AEGIS_DIR": tmp}
                    out = subprocess.run(["bash", script], capture_output=True, text=True,
                                         env=env, timeout=120)
                    return (out.stdout + out.stderr).strip()

                clean = run_tree()
                # What the shipped topologies name, read from the tree (not from the doc).
                named = []
                for lab in sorted(os.listdir(labs)):
                    labdir = os.path.join(labs, lab)
                    if not os.path.isdir(labdir):
                        continue
                    for f in sorted(os.listdir(labdir)):
                        if f.endswith(".yml"):
                            for p in re.findall(r"^\s*startup-config:\s*(\S+)",
                                                read(os.path.join("lab-definitions", lab, f)) or "", re.M):
                                named.append((labdir, p))
                victim = next(((labdir, p) for labdir, p in named
                               if os.path.isfile(os.path.join(labdir, p))), None)
                if victim is None:
                    claim(False, "the installer's startup-config verify block still runs (executed)",
                          "no asset named by a shipped topology exists at its named path — "
                          "the fixture is not the tree Step 6 copies")
                else:
                    target = os.path.join(victim[0], victim[1])
                    held = target + ".held"
                    os.rename(target, held)
                    mutated = run_tree()
                    os.rename(held, target)
                    result.update(clean=clean, mutated=mutated, named=named,
                                  victim="%s/%s" % (os.path.basename(victim[0]), victim[1]))
        except (OSError, subprocess.SubprocessError) as exc:
            claim(False, "the installer's startup-config verify block still runs (executed)",
                  "could not run it: %s" % exc)
        if result:
            # The intact tree must log success and warn about nothing; the mutated one must
            # warn by name about the asset that was removed and must not log success. A block
            # that warned unconditionally would satisfy the second half alone, so both halves
            # are required.
            ok = ("LOG" in result["clean"] and "WARN" not in result["clean"]
                  and "WARN" in result["mutated"] and result["victim"] in result["mutated"]
                  and "LOG" not in result["mutated"])
            claim(ok, "the installer's startup-config verify block still runs (executed)",
                  "intact tree -> %s; %s removed -> %s (%d startup-config path(s) named by "
                  "shipped topologies)"
                  % (result["clean"].replace("\n", " | ") or "<no output>",
                     result["victim"],
                     result["mutated"].replace("\n", " | ") or "<no output>",
                     len(result["named"])))

    # --- 7. The page's stated number of claims == the number this tool makes -------------
    #          Evaluated last, so `claims` is complete. Reads the count out of the page's
    #          "holds **N claims**" sentence; one source of truth, one direction each way.
    n_claims = len(claims)
    mc = re.search(r"holds \*\*(\d+) claims\*\*", doc)
    claim(mc is not None and int(mc.group(1)) == n_claims,
          "the page states the number of claims this tool makes (derived from the claim list)",
          "this tool made %d claim(s); page says %r"
          % (n_claims, mc.group(1) if mc else "<no 'holds **N claims**' sentence>"))

    bad = [c for c in claims if not c[0]]
    for ok, label, detail in claims:
        print("  %s %s — %s" % ("PASS" if ok else "FAIL", label, detail))

    if bad:
        print("\nself-contained doc check: %d of %d claim(s) are no longer true of this tree"
              % (len(bad), len(claims)))
        return 1

    print("\nself-contained doc OK: %d claim(s) in %s still match %s and the tree."
          % (len(claims), DOC, TOOL))
    print("  %d anchors pinned; the page states that number, so neither can drift alone."
          % n_anchors)
    print("NOTE: this checks the doc against the tool's source, not the tool's behaviour;"
          " neither of them installs anything. A cold `sudo ./install.sh` remains the only"
          " proof the install path works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
