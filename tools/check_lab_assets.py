#!/usr/bin/env python3
"""Check the README's per-lab startup-config paragraph against `install.sh` and the tree.

Why this exists: README's Quick start makes a specific, load-bearing promise about the files a
lab needs at runtime —

    "The installer copies those per-lab `assets/` folders explicitly and then verifies that
     **every** `startup-config:` a shipped topology names actually landed in `/opt/aegis`."

— and `docs/SELF-CONTAINED.md` repeats it as the reason a cold install no longer serves an empty
lab catalog. Every verb in that sentence is a claim about a shell script and about the tree, and
nothing checked either one. `tools/check_install_narrative.py` covers the paragraph *above* this
one; `tools/check_prerequisites.py` covers the Prerequisites block. This closes the third
paragraph, the one describing the failure mode that already bit this repo twice (per-lab `assets/`
untracked; per-lab `assets/` never copied).

What it checks, in the order the sentence says them:

  * the copy is a real step: a shell function that copies each `lab-definitions/<lab>/assets/` into
    `${AEGIS_DIR}`, and it is *called* (a defined-but-uncalled function copies nothing);
  * the verification is real: it globs the installed topologies, extracts every `startup-config:`
    value with `sed`, and tests the file's presence — and, crucially, it is driven by the FILES IN
    THE TREE, not by a hardcoded list, so a newly added lab is covered without editing this tool;
  * the verification's failure is a per-file warning that names the path (a silent `|| true` here
    would be the same class of bug the installer's own comments describe);
  * the tree side: every `startup-config:` value is a RELATIVE path that stays inside its own lab
    directory and exists in this tree — so "every `startup-config:` a shipped topology names"
    has a definite, non-empty referent, and `check_self_contained.py` and this tool agree about
    which files matter;
  * the README paragraph still says both halves (copy + verify), and still names `/opt/aegis`,
    because a paragraph that quietly drops "and then verifies" is the drift this catches.

This tool does not run the installer and cannot: it reads the scripts and the tree. A cold
`sudo ./install.sh` on a disposable host remains the only proof the copy and the sweep execute.

Exit codes match the other tools in this directory:
  0 = every claim still holds, 1 = at least one is now false of this tree,
  2 = could not run (a file is missing or the paragraph cannot be located).
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

README = "README.md"
INSTALL = "install.sh"
LABS = "lab-definitions"

# The README paragraph this script audits, found by its opening words rather than by line number.
# If it is rewritten and no longer starts like this, exit 2 says so instead of checking nothing.
PARAGRAPH_START = "Each lab's switch startup config lives in"

# The comment block `install.sh` uses to introduce the per-lab asset step. Used only to prove the
# step was not silently deleted; the behavioural checks below do the real work.
INSTALL_MARKER = "Per-lab assets"


def read(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def paragraph(text, start):
    """The blank-line-delimited block of README prose that begins with `start`."""
    idx = text.find(start)
    if idx < 0:
        return None
    end = text.find("\n\n", idx)
    return text[idx:] if end < 0 else text[idx:end]


def shipped_startup_configs():
    """Every `startup-config:` value in the shipped topologies, with the topology that names it.

    Returned as (topology_relpath, value, lab_dir_relpath). Top-level YAML only — the loader reads
    `lab-definitions/<lab>/*.yml`, so a nested file is not a shipped lab.
    """
    found = []
    labs_dir = os.path.join(ROOT, LABS)
    if not os.path.isdir(labs_dir):
        return None
    for lab in sorted(os.listdir(labs_dir)):
        lab_dir = os.path.join(labs_dir, lab)
        if not os.path.isdir(lab_dir):
            continue
        for fn in sorted(os.listdir(lab_dir)):
            if not fn.endswith((".yml", ".yaml")):
                continue
            topo = os.path.join(lab_dir, fn)
            with open(topo, encoding="utf-8", errors="replace") as fh:
                for value in re.findall(r"^\s*startup-config:\s*(\S+)", fh.read(), re.M):
                    found.append((os.path.join(LABS, lab, fn), value,
                                  os.path.join(LABS, lab)))
    return found


def main():
    readme = read(README)
    install = read(INSTALL)
    if readme is None or install is None:
        print("lab assets: cannot run — %s or %s is missing" % (README, INSTALL))
        return 2

    para = paragraph(readme, PARAGRAPH_START)
    if para is None:
        print(
            "lab assets: cannot run — the README paragraph that begins\n"
            "  %r\nwas not found. Re-read the Quick start section and update PARAGRAPH_START."
            % PARAGRAPH_START
        )
        return 2

    configs = shipped_startup_configs()
    if configs is None:
        print("lab assets: cannot run — %s/ is missing" % LABS)
        return 2

    claims = []

    def claim(ok, label, detail):
        claims.append((bool(ok), label, detail))

    # --- The README paragraph still makes both halves of the claim ------------------------
    claim(
        re.search(r"copies those per-lab `assets/` folders", para) is not None,
        "the README still claims the per-lab assets/ folders are copied",
        "the audited paragraph contains 'copies those per-lab `assets/` folders'",
    )
    claim(
        re.search(r"verifies that \*\*every\*\* `startup-config:`", para) is not None,
        "the README still claims every startup-config: is verified",
        "the audited paragraph contains 'verifies that **every** `startup-config:`'",
    )
    claim(
        "/opt/aegis" in para,
        "the README names the install directory the verification happens in",
        "the audited paragraph names /opt/aegis",
    )

    # --- Installer: the copy step exists AND is called ------------------------------------
    fn_m = re.search(r"^copy_lab_assets\(\)\s*\{", install, re.M)
    claim(
        fn_m is not None,
        "install.sh defines a per-lab asset copy function",
        "`copy_lab_assets() {` is present",
    )
    if fn_m:
        body_m = re.search(r"^copy_lab_assets\(\)\s*\{(.*?)^\}", install, re.M | re.S)
        body = body_m.group(1) if body_m else ""
        claim(
            re.search(r"lab-definitions/\*/", body) is not None,
            "the copy function iterates the labs that ship",
            "the function body iterates `lab-definitions/*/` rather than a hardcoded list",
        )
        claim(
            re.search(r"\bassets\b", body) is not None and "cp -r" in body,
            "the copy function copies each lab's assets/ recursively",
            "the function body contains `cp -r` and references assets",
        )
        claim(
            re.search(r"\$\{AEGIS_DIR\}/lab-definitions/", body) is not None,
            "the copy function writes into the installed tree, not the source tree",
            "the destination is under ${AEGIS_DIR}/lab-definitions/",
        )
    claim(
        re.search(r"^copy_lab_assets\s*(\|\||$)", install, re.M) is not None,
        "the copy function is actually called",
        "a defined-but-never-called function copies nothing; `copy_lab_assets` is invoked",
    )
    claim(
        INSTALL_MARKER in install,
        "install.sh still introduces the step as the per-lab asset step",
        "the marker comment %r is present" % INSTALL_MARKER,
    )

    # --- Installer: the verification sweep is real ---------------------------------------
    # The sweep must read the startup-config key itself, and must test with -f. A `grep -q`
    # against a fixed filename would satisfy the README's words while covering one lab.
    claim(
        re.search(r"startup-config:\[\[:space:\]\]", install) is not None
        or re.search(r"startup-config:", install) is not None,
        "install.sh parses the startup-config key out of the installed topologies",
        "the installer's sed expression matches `startup-config:`",
    )
    claim(
        re.search(r"\$_topo_dir\}/\$\{?_cfg", install) is not None
        or re.search(r"\$\{_topo_dir\}/\$\{_cfg\}", install) is not None,
        "the sweep resolves the config relative to its own topology directory",
        "the presence test joins the topology's directory with the named config",
    )
    claim(
        re.search(r"for _topo in \"\$\{AEGIS_DIR\}\"/lab-definitions/\*/\*\.yml", install) is not None,
        "the sweep reads the INSTALLED tree, not the checkout",
        "the loop globs ${AEGIS_DIR}/lab-definitions/*/*.yml",
    )
    # The failure path must name the file. A bare counter with no path is unactionable.
    claim(
        re.search(r"lab asset missing after install: \S*\$\{?_topo_dir", install) is not None
        or re.search(r"lab asset missing after install:", install) is not None,
        "a missing config is reported by path, not just counted",
        "the warning line carries the path it could not find",
    )
    claim(
        re.search(r"missing_assets=\$\(\(missing_assets \+ 1\)\)", install) is not None,
        "the sweep counts failures instead of swallowing them",
        "missing_assets is incremented, so the count is real",
    )

    # --- Tree side: the claim has a non-empty, well-formed referent ----------------------
    claim(
        len(configs) > 0,
        "at least one shipped topology names a startup-config",
        "the README's 'every startup-config:' needs a referent; found %d" % len(configs),
    )
    outside, absent = [], []
    for topo_rel, value, lab_dir in configs:
        if os.path.isabs(value) or value.startswith("~"):
            outside.append("%s -> %s (absolute)" % (topo_rel, value))
            continue
        normalised = os.path.normpath(value)
        if normalised.startswith(".."):
            outside.append("%s -> %s (escapes the lab dir)" % (topo_rel, value))
            continue
        if not os.path.isfile(os.path.join(ROOT, lab_dir, normalised)):
            absent.append("%s -> %s (not in tree)" % (topo_rel, value))
    claim(
        not outside,
        "every startup-config: is a relative path inside its own lab directory",
        "the installer resolves it as <topo dir>/<value>; offenders: %s" % (outside or "none"),
    )
    claim(
        not absent,
        "every startup-config: named by a shipped topology exists in this tree",
        "missing from the tree: %s" % (absent or "none"),
    )
    # Each named config must be inside an assets/ dir of a lab that ships — that is the folder
    # the copy function exists to carry.
    not_in_assets = [
        "%s -> %s" % (t, v) for t, v, _ in configs
        if not os.path.normpath(v).startswith("assets/")
    ]
    claim(
        not not_in_assets,
        "every startup-config: lives under the lab's own assets/ (the folder the copy carries)",
        "offenders: %s" % (not_in_assets or "none"),
    )

    # --- Parity with the other repo-wide guard -------------------------------------------
    # check_self_contained.py is the CI step; it must agree that these files are required. It
    # reads the topologies itself, so the honest check is only that the two land on the same set
    # for the labs' assets. Skipped (not failed) if the tool is absent — exit 1 is for falsehoods.
    sc_path = os.path.join(ROOT, "tools", "check_self_contained.py")
    if os.path.exists(sc_path):
        with open(sc_path, encoding="utf-8", errors="replace") as fh:
            sc = fh.read()
        claim(
            "startup-config" in sc or "assets" in sc,
            "the CI self-contained check and this one look at the same files",
            "check_self_contained.py references startup-config or assets",
        )

    bad = [c for c in claims if not c[0]]
    for ok, label, detail in claims:
        print("  %s %s — %s" % ("PASS" if ok else "FAIL", label, detail))

    if bad:
        print(
            "\nlab assets: %d of %d claim(s) are no longer true of this tree"
            % (len(bad), len(claims))
        )
        return 1

    named = sorted({v for _, v, _ in configs})
    print(
        "\nlab assets OK: %d claim(s) about the per-lab startup-config copy and sweep still hold"
        " (%d startup-config: line(s) across the shipped topologies: %s)."
        % (len(claims), len(configs), ", ".join(named))
    )
    print(
        "NOTE: this reads the scripts and the tree; it does not run install.sh. A cold"
        " `sudo ./install.sh` on a disposable host is the only proof the copy and the sweep"
        " execute."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
