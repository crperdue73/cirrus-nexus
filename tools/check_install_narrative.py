#!/usr/bin/env python3
"""Check the README's narrative of what `install.sh` does against `install.sh` itself.

Why this exists: the README's Quick start tells a reader, in one sentence, what the installer
"installs, copies, builds, pre-pulls, and registers". Every verb in that sentence is a claim
about a shell script that changes without the README. `tools/check_prerequisites.py` already
covers the Prerequisites paragraph; this covers the sentence right after the install command,
which nothing checked. It was true when written and it is the kind of sentence that stays
grammatical for years after it stops being true.

So, for each step named in the README sentence, this script looks for that step in the
installer and checks the one thing the step claims:

  * system packages   -> `apt-get install` is present (Step 1);
  * Docker            -> the Docker apt repository or the docker-ce package is named;
  * ContainerLab      -> the pinned `get.containerlab.dev` install with a `-v` version;
  * ttyd              -> a ttyd install path exists;
  * Python deps       -> `pip3 install` names every module the README names;
  * copy to /opt/aegis-> `install.sh`'s AEGIS_DIR default is the path the README prints;
  * build the router  -> `Dockerfile.frr` is built and the README's image name is the tag used;
  * pre-pull images   -> `docker pull` names exactly the images the README lists for that step;
  * systemd service   -> the unit `install.sh` writes is the unit name the README tells you to
                         start (`systemctl start <name>` vs `/etc/systemd/system/<name>.service`).

A README sentence that stops naming a step, or names one the installer no longer performs,
fails here. That is the point: re-read the paragraph, re-measure, then update the patterns
below in the same commit as the prose.

Exit codes match the other tools in this directory:
  0 = every claim still holds, 1 = at least one claim is now false of this tree,
  2 = could not run (a file is missing or the paragraph could not be located).
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

README = "README.md"
INSTALL = "install.sh"

# The README paragraph this script audits, found by its opening words rather than by line
# number. If the paragraph is rewritten and no longer starts like this, exit 2 says so instead
# of silently checking nothing.
PARAGRAPH_START = "`install.sh` installs Docker, ContainerLab, `ttyd`, and the Python deps"

# The path the README tells the reader the app lands in. Checked against the installer's
# AEGIS_DIR default so a change on either side fails here.
README_INSTALL_DIR = "/opt/aegis"

# The systemd unit the README tells the reader to start, checked against the unit name the
# installer writes to /etc/systemd/system/.
README_SERVICE = "aegis"


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


def main():
    readme = read(README)
    install = read(INSTALL)
    if readme is None or install is None:
        print("install narrative: cannot run — %s or %s is missing" % (README, INSTALL))
        return 2

    para = paragraph(readme, PARAGRAPH_START)
    if para is None:
        print(
            "install narrative: cannot run — the README paragraph that begins\n"
            "  %r\nwas not found. Re-read the Quick start section and update PARAGRAPH_START."
            % PARAGRAPH_START
        )
        return 2

    claims = []

    def claim(ok, label, detail):
        claims.append((bool(ok), label, detail))

    # --- The five things the sentence says are installed --------------------------------
    claim(
        re.search(r"^apt-get install -y[^\n]*", install, re.M),
        "system packages are apt-installed",
        "`apt-get install -y ...` appears in install.sh",
    )
    claim(
        "download.docker.com/linux/debian" in install or "docker-ce" in install,
        "Docker is installed",
        "the Docker apt repository or the docker-ce package is named in install.sh",
    )
    claim(
        "get.containerlab.dev" in install and re.search(r"get\.containerlab\.dev.*?-v \S+", install),
        "ContainerLab is installed at a pinned version",
        "the get.containerlab.dev installer is invoked with `-v <version>`",
    )
    claim(
        "ttyd" in install and re.search(r"(curl -fsSL .*ttyd|build/make install|\bmake install\b)", install),
        "ttyd is installed",
        "a ttyd download or build path exists in install.sh",
    )

    # The Python deps the README names, in its own wording, must be the ones pip3 installs.
    deps_m = re.search(r"Python deps\s*\(([^)]*)\)", para)
    readme_deps = []
    if deps_m:
        readme_deps = [d.strip(" `") for d in deps_m.group(1).split(",") if d.strip(" `")]
    # The installer's first pip line ends in `|| pip3 install ...` as a fallback, so the
    # capture must stop at the `||` rather than swallowing the shell operator.
    pip_m = re.search(r"^pip3 install ([^\n|]*)", install, re.M)
    pip_line = pip_m.group(1) if pip_m else ""
    missing = [d for d in readme_deps if not re.search(r"\b%s\b" % re.escape(d), pip_line)]
    claim(
        readme_deps and not missing,
        "Python deps named in the README are the ones pip installs",
        "README names %s; pip3 line %r%s"
        % (readme_deps or "(none found)", pip_line.strip()[:90],
           "" if not missing else "; MISSING %s" % missing),
    )

    # --- Where it lands ------------------------------------------------------------------
    dir_m = re.search(r'^AEGIS_DIR="([^"]+)"', install, re.M)
    claim(
        dir_m and dir_m.group(1) == README_INSTALL_DIR,
        "install directory matches the README",
        "install.sh AEGIS_DIR=%r, README prints %r"
        % (dir_m.group(1) if dir_m else None, README_INSTALL_DIR),
    )
    claim(
        README_INSTALL_DIR in para,
        "the README actually mentions the install directory",
        "the audited paragraph names %r" % README_INSTALL_DIR,
    )

    # --- What it builds and pre-pulls ----------------------------------------------------
    # The build step reads `-f "${FRR_SRC}"` where FRR_SRC is the Dockerfile NAME assigned
    # earlier, so the filename appears in the assignment, not on the build line. Follow both.
    frr_src_m = re.search(r'^FRR_SRC="?([^"\n]+)"?', install, re.M)
    frr_src = (frr_src_m.group(1) if frr_src_m else "Dockerfile.frr").strip()
    claim(
        "docker build" in install and re.search(r'-f\s+"?\$\{?FRR_SRC\}?"?', install),
        "the router image is built from Dockerfile.frr",
        "install.sh runs `docker build -f ${FRR_SRC}` with FRR_SRC=%r" % frr_src,
    )
    # The image the README says is built must be the tag the build step produces.
    built_m = re.search(r"FRR router image", para)
    tag_m = re.search(r'-t\s+([\w./-]+:[\w.-]+)', install)
    claim(
        built_m is not None and tag_m is not None,
        "the README still names the router image it says is built, and the installer tags one",
        "README mentions the FRR router image; install.sh tags %r"
        % (tag_m.group(1) if tag_m else None),
    )
    # "pre-pulls the switch image" -> a docker pull that names the switch image. Match only
    # real pull commands: the installer also PRINTS a `docker pull ...` hint inside a warn,
    # and a bare `docker pull (\S+)` sweep picks that up as if it were a step.
    pull_imgs = sorted(set(re.findall(r"^\s*docker pull (\S+)\s*;?\s*$", install, re.M)))
    pull_loop_m = re.search(r"^for IMG in ([^;\n]+); do", install, re.M)
    pulled = pull_imgs + (
        [i.strip() for i in pull_loop_m.group(1).split()] if pull_loop_m else []
    )
    claim(
        any("srlinux" in i for i in pulled),
        "the switch image is pre-pulled",
        "pre-pull targets: %s" % (sorted(set(pulled)) or "(none)"),
    )
    claim(
        "pre-pulls" in para,
        "the README still says the switch image is pre-pulled",
        "the audited paragraph contains 'pre-pulls'",
    )

    # --- The service it registers --------------------------------------------------------
    unit_m = re.search(r"/etc/systemd/system/([A-Za-z0-9_.@-]+)\.service", install)
    start_m = re.search(r"systemctl start ([A-Za-z0-9_.@-]+)", readme)
    claim(
        unit_m and start_m and unit_m.group(1) == start_m.group(1) == README_SERVICE,
        "the service name in the README is the unit the installer writes",
        "install.sh writes %r, README says `systemctl start %s`, expected %r"
        % (unit_m.group(1) if unit_m else None,
           start_m.group(1) if start_m else "?",
           README_SERVICE),
    )

    bad = [c for c in claims if not c[0]]
    for ok, label, detail in claims:
        print("  %s %s — %s" % ("PASS" if ok else "FAIL", label, detail))

    if bad:
        print(
            "\ninstall narrative: %d of %d claim(s) are no longer true of this tree"
            % (len(bad), len(claims))
        )
        return 1

    print(
        "\ninstall narrative OK: %d claim(s) about what install.sh does still match install.sh."
        % len(claims)
    )
    print(
        "NOTE: this reads the scripts; it does not run them. A cold `sudo ./install.sh` is the"
        " only proof the steps execute."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
