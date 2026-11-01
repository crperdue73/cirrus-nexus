#!/usr/bin/env python3
"""Check the README's Prerequisites against what `install.sh` actually does.

Why this exists: the README's Prerequisites block is the one paragraph a reader plans
a machine from, and `install.sh` is the program that will run on that machine. Nothing
in this tree connected the two, so a note in the README could drift away from the
installer and stay green — including a note that says, truthfully today, that the
installer does NOT check something. That kind of note is the most fragile claim in
the repo: the day someone adds the check, the README starts warning about a hazard
that no longer exists, and nothing fails.

So this script makes both directions fail loudly. For each claim it runs exactly one
targeted search and reports pass/fail. It does not parse Markdown prose (that would
invent a second, worse parser for English). If a sentence moves, the search misses and
this fails — which is the point: re-read the README, re-measure, then update the
pattern below in the same commit.

Exit codes are the same 0/1/2 the other tools in this directory use:
  0 = every claim still holds, 1 = at least one claim is now false of this tree,
  2 = could not run (a file is missing).
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

README = "README.md"
INSTALL = "install.sh"


def read(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main():
    readme = read(README)
    install = read(INSTALL)
    requirements = read("requirements.txt")
    if requirements is None:
        print("UNAVAILABLE: requirements.txt is missing — cannot check the package claims")
        return 2
    for rel, body in ((README, readme), (INSTALL, install)):
        if body is None:
            print(f"UNAVAILABLE: {rel} is missing — cannot check prerequisites")
            return 2

    problems = []
    checks = 0

    def claim(ok, fail):
        """Record one claim: a single search, one expected state."""
        nonlocal checks
        checks += 1
        if not ok:
            problems.append(fail)

    def readme_has(pattern, what):
        claim(re.search(pattern, readme) is not None,
              f"README.md no longer says {what} — re-check the claim against install.sh "
              "and update the pattern in tools/check_prerequisites.py")

    def install_has(pattern, what):
        claim(re.search(pattern, install) is not None,
              f"install.sh no longer has {what} — the README says it does")

    def install_lacks(pattern, what):
        claim(re.search(pattern, install) is None,
              f"install.sh now has {what} — the README says it does not. Either the note is "
              "stale (retract it) or the change should be reverted")

    # -- 1. Packages. The README lists what Step 1 apt-installs; the installer must
    #       really contain that list, and the README must not omit an obvious one.
    step1 = re.search(r"apt-get install -y -qq \\\n(.*?)\n\n", install, re.S)
    claim(step1 is not None, "install.sh no longer has a multi-line `apt-get install` block "
                             "at Step 1 — the README's package list has lost its witness")
    pkgs = []
    if step1:
        pkgs = [p.strip().rstrip("\\").strip() for p in step1.group(1).split("\n")]
        pkgs = [p for p in pkgs if p and not p.startswith("#")]
    for pkg in ("curl", "git", "cmake", "build-essential", "python3", "python3-pip",
                "python3-venv", "lsb-release"):
        claim(pkg in pkgs, f"install.sh Step 1 no longer installs {pkg} "
                           "(sanity: the block itself was found)")
    # python3 must be installed yet never version-checked — that pair is the README's note.
    claim("python3" in pkgs, "install.sh Step 1 no longer installs python3 — the README "
                                  "says it does")
    install_lacks(r"python3\s+(-V|--version)|sys\.version_info|PYTHON_VERSION",
                  "a Python version check")

    # -- 2. Docker repository. README: Debian repo only, suite from lsb_release, and no
    #       ID / ID_LIKE / VERSION_ID guard. Three separate claims, three searches.
    install_has(r"download\.docker\.com/linux/debian", "the Debian Docker apt repository")
    install_lacks(r"download\.docker\.com/linux/ubuntu", "the Ubuntu Docker apt repository")
    install_has(r"lsb_release -cs", "`lsb_release -cs` as the Docker suite name")
    install_lacks(r"VERSION_ID|ID_LIKE|/etc/os-release", "an /etc/os-release or VERSION_ID check")

    # -- 3. Containerlab is pinned, and Docker is skipped when already present.
    install_has(r"--\s*-v\s*0\.75\.0\b", "a pinned containerlab version (0.75.0)")
    install_has(r"if ! command -v docker &>/dev/null", "the `docker` already-installed guard")

    # -- 4. Base images. README: three tags, no digests; two of them pre-pulled.
    dockerfile = read("Dockerfile.frr")
    claim(dockerfile is not None, "Dockerfile.frr is missing — the FRR image claim has no witness")
    if dockerfile is not None:
        claim(re.search(r"^FROM\s+alpine:latest\s*$", dockerfile, re.M) is not None,
              "Dockerfile.frr no longer starts `FROM alpine:latest`")
        claim(re.search(r"^FROM\s+\S+@sha256:", dockerfile, re.M) is None,
              "Dockerfile.frr now pins a base image by digest — the README says it does not")
    install_has(r"for IMG in ghcr\.io/nokia/srlinux:latest alpine:latest", "the two pre-pulled image tags")
    lab_images = []
    for dirpath, _, files in os.walk(os.path.join(ROOT, "lab-definitions")):
        for fn in files:
            if fn.endswith((".yml", ".yaml")):
                with open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace") as fh:
                    lab_images += re.findall(r"^\s*image:\s*(\S+)", fh.read(), re.M)
    claim(sorted(set(lab_images)) == ["aegis/frr:latest", "alpine:latest",
                                      "ghcr.io/nokia/srlinux:latest"],
          "the shipped lab topologies no longer use exactly alpine:latest + "
          f"ghcr.io/nokia/srlinux:latest + aegis/frr:latest — found {sorted(set(lab_images))}. "
          "The README's 'the base images are tags, not digests' note names them")
    claim(not any("@sha256:" in img for img in lab_images),
          "a shipped topology now pins an image by digest — the README says it does not")

    # -- 5. Architecture. README: `uname -m` is read for ttyd only, Dockerfile has no
    #       --platform, topologies carry no architecture override.
    install_has(r"uname -m", "`uname -m` for the ttyd binary")
    # (Not checked: `dpkg --print-architecture` on the apt source line. It selects package
    #  architecture for the Docker repo; it is not a check that the labs will run here.)
    if dockerfile is not None:
        claim("--platform" not in dockerfile,
              "Dockerfile.frr now sets --platform — the README says the host architecture is assumed")
    claim(not re.search(r"^\s*(platform|arch):", "\n".join(
        open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
        for dp, _, fns in os.walk(os.path.join(ROOT, "lab-definitions"))
        for fn in fns if fn.endswith((".yml", ".yaml"))), re.M),
          "a shipped topology now sets a `platform:`/`arch:` override — the README says "
          "the topology has no architecture override")

    # -- 6. Python packages. README: three names, unpinned, installed by name to pip3;
    #       `requirements.txt` is NOT what install.sh reads.
    install_has(r"pip3 install --quiet --break-system-packages fastapi uvicorn pyyaml",
                "the unpinned `pip3 install … fastapi uvicorn pyyaml` line")
    install_lacks(r"pip3? install[^\n]*-r\s+\S*requirements", "a `pip3 install -r requirements.txt`")
    # requirements.txt is read by name, comments stripped — its own header lines are prose.
    req = [ln.strip() for ln in requirements.splitlines()
           if ln.strip() and not ln.strip().startswith("#")]
    claim(req == ["fastapi", "uvicorn", "pyyaml"],
          "requirements.txt no longer lists exactly fastapi, uvicorn, pyyaml "
          f"(found {req}) — the README names all three")
    claim(not re.search(r"[<>=~!]", " ".join(req)),
          "requirements.txt now carries version constraints — the README says it ships none")
    main_py = read("backend/main.py") or ""
    claim(re.search(r"^\s*from pydantic import", main_py, re.M) is not None
          or re.search(r"^\s*import pydantic\b", main_py, re.M) is not None,
          "backend/main.py no longer imports pydantic — the README says it does, unnamed in any manifest")
    claim(not re.search(r"^\s*pydantic\s*$", install, re.M) and "pydantic" not in req,
          "pydantic is now declared somewhere — the README says it is not named in either manifest")

    # -- 7. Doc links the README points a reader at for the details.
    for rel in ("assets/frr-image.pin", "docs/OPERATIONS.md", "docs/SELF-CONTAINED.md",
                "docs/architecture.md"):
        claim(os.path.exists(os.path.join(ROOT, rel)), f"README links {rel}, which does not exist")

    if problems:
        print(f"prerequisites: {len(problems)} claim(s) no longer true of this tree:")
        for p in problems:
            print(f"  - {p}")
        print("\nFix the claim (README or installer), do not delete the check.")
        return 1

    print(f"prerequisites OK: {checks} claim(s) in README's Prerequisites still match install.sh "
          "and the tree.")
    print("NOTE: this reads the scripts, it does not install anything — a cold `sudo ./install.sh` "
          "is the only proof that the steps run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
