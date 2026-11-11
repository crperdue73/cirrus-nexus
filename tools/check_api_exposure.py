#!/usr/bin/env python3
"""Check the parts of `docs/API.md` that the OpenAPI document does not carry.

`tools/check_api_doc.py` reads the route table and the status-code table against the app. Its own
`[info]` line has named three claims as out of scope since 2026-11-10:

  * the ttyd port range (`8765`-`9765`) and the "allocator never wraps onto a live port" claim;
  * the `/docs` / `/redoc` exposure notes and the `0.0.0.0` bind;
  * the `graded` / `error` / `refused` sub-status vocabulary.

An `[info]` line is honest but it is not a witness: nothing would have gone red if any of those had
rotted. This tool is the separate read, so they can be checked rather than disclaimed.

What it measures, all against `backend/main.py` and `docs/API.md` in this tree:

  1. **Port range.** `TTYD_PORT_BASE` / `TTYD_PORT_MAX` as the code defines them, plus the inclusive
     span (MAX-BASE+1), against the range the page prints. The page also says the allocator raises
     rather than wrapping onto a port still in use; the check requires `_allocate_port` to contain a
     raise carrying the range, so the sentence has a site.
  2. **Bind + exposure.** `AEGIS_HOST` default in `run()`, and whether the page names that default and
     the env override. `/docs`, `/redoc` and `/openapi.json` must exist in the app's own OpenAPI
     document, not merely be named in prose; and since the page calls the API unauthenticated, it
     must not contain a `Depends(` / auth dependency on any route (a page that claims no auth while
     the app mounted an auth dependency would be the worst kind of stale).
  3. **Sub-status vocabulary.** The three literals the code can put in `GraderResult.status` —
     read off the construction sites, not off the comment that describes them — against the three the
     page names. A fourth value added in code without the page fails here; a value in the page that
     no site constructs fails too.
  4. **ttyd URL honesty.** The page says the response carries a per-node `ttyd` URL. The code builds
     that URL from the *request's Host header* when there is one, and only falls back to the derived
     host otherwise. That is what makes the URL reachable from whichever address the browser used,
     so the page claiming "the URL a client gets works from where the client is" has a site.

Out of scope, stated rather than scored: whether these pages are *reachable* on a live host (that
needs a running server, and the repo has no fixture for one). Nothing here starts uvicorn.

Exit 0 = every claim holds, 1 = at least one is now false of this tree, 2 = could not run.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DOC = os.path.join(ROOT, "docs", "API.md")
BACKEND = os.path.join(ROOT, "backend", "main.py")

PASS, FAIL, INFO = "PASS", "FAIL", "info"
results = []


def ok(claim, detail=""):
    results.append((PASS, claim, detail))


def bad(claim, detail=""):
    results.append((FAIL, claim, detail))


def info(claim, detail=""):
    results.append((INFO, claim, detail))


def die(msg):
    print(f"[check_api_exposure] cannot run — {msg}")
    raise SystemExit(2)


def live_lines(source):
    """Source with comment-only lines dropped, so a commented-out site cannot satisfy a check."""
    return "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))


def handler_body(source, name):
    """The body of a top-level function, up to the next top-level def/class/decorator."""
    m = re.search(r"\ndef\s+%s\s*\(" % re.escape(name), source)
    if not m:
        return ""
    nxt = re.compile(r"\n(?:@|def |class )").search(source, m.start() + 1)
    return source[m.start(): nxt.start() if nxt else len(source)]


# --- claim 1: the ttyd port range -------------------------------------------------------------

def check_port_range(text, source):
    base = re.search(r"^TTYD_PORT_BASE\s*=\s*(\d+)", source, re.M)
    maxtop = re.search(r"^TTYD_PORT_MAX\s*=\s*(\d+)", source, re.M)
    if not base or not maxtop:
        bad("the ttyd port range is declared in backend/main.py",
            "TTYD_PORT_BASE / TTYD_PORT_MAX not found at module level")
        return
    lo, hi = int(base.group(1)), int(maxtop.group(1))
    span = hi - lo + 1
    printed = re.search(r"=?\s*(\d{4})\s*[–-]\s*(\d{4})", text)
    if not printed:
        bad("the page prints a ttyd port range", "no NNNN-NNNN range found in docs/API.md")
        return
    p_lo, p_hi = int(printed.group(1)), int(printed.group(2))
    if (p_lo, p_hi) == (lo, hi):
        ok("the page's ttyd port range matches the code", f"{lo}-{hi} ({span} ports)")
    else:
        bad("the page's ttyd port range matches the code",
            f"page says {p_lo}-{p_hi}, code says {lo}-{hi}")

    alloc = handler_body(source, "_allocate_port")
    if not alloc:
        bad("the allocator exists", "_allocate_port not found")
        return
    alloc_live = live_lines(alloc)
    raises_range = re.search(r"raise\s+\w+\([^)]*TTYD_PORT_BASE", alloc_live, re.S) or \
        re.search(r"raise\s+\S*\(?[^)]*\{TTYD_PORT_BASE\}", alloc_live, re.S) or \
        "TTYD_PORT_MAX" in alloc_live and "raise" in alloc_live
    if raises_range:
        ok("the allocator refuses rather than wrapping (raise site carries the range)")
    else:
        bad("the allocator refuses rather than wrapping (raise site carries the range)",
            "no raise mentioning the range in _allocate_port")
    # the path the page says is skipped: ports already in use must be consulted
    if "TTYD_PROCS" in alloc_live and "ttyd" in alloc_live:
        ok("the allocator consults in-use ports before handing one out",
            "reads TTYD_PROCS and live-session ttyd maps")
    else:
        bad("the allocator consults in-use ports before handing one out",
            "_allocate_port does not read TTYD_PROCS / session ttyd maps")


# --- claim 2: bind + exposure -----------------------------------------------------------------

def check_bind_and_docs(text, source, doc_urls):
    m = re.search(r'os\.environ\.get\(\s*"AEGIS_HOST"\s*,\s*"([^"]+)"\s*\)', source)
    if not m:
        bad("the server's bind address has an env default the page can name",
            'no os.environ.get("AEGIS_HOST", …) in backend/main.py')
        host = None
    else:
        host = m.group(1)
        if host in text and "AEGIS_HOST" in text:
            ok("the page names the real bind default and its env override", f"AEGIS_HOST default {host}")
        else:
            bad("the page names the real bind default and its env override",
                f"code default is {host!r}; page does not state it with AEGIS_HOST")

    # The doc pages are Starlette's, not the app's own routes: measured on this tree, they are NOT in
    # `openapi()["paths"]` (which carries the 11 /api routes only). Read them off the app object, which
    # is where uvicorn gets them from. A `None` there means the page was switched off and the doc lies.
    wanted = {"/docs": doc_urls.get("docs"), "/redoc": doc_urls.get("redoc"),
              "/openapi.json": doc_urls.get("openapi")}
    off = sorted(p for p, v in wanted.items() if not v)
    if not off:
        ok("the three doc pages the page promises really exist in the app",
            "docs_url, redoc_url, openapi_url all set")
    else:
        bad("the three doc pages the page promises really exist in the app",
            "app has these switched off (url is None): " + ", ".join(off))

    # "The API has no authentication" — check the claim against mounted dependencies
    auth_tokens = ("Depends(", "APIKey", "HTTPBasic", "OAuth2", "Security(")
    hits = [t for t in auth_tokens if t in live_lines(source)]
    if not hits:
        ok("the 'no authentication' claim has no contradicting dependency in the app")
    else:
        bad("the 'no authentication' claim has no contradicting dependency in the app",
            "backend/main.py mentions " + ", ".join(hits) + " — the page says there is no auth")

    # and the page must still say it, because it is the claim a deployer acts on
    if "The API has no authentication" in text:
        ok("the page still makes the no-authentication claim")
    else:
        bad("the page still makes the no-authentication claim",
            "the sentence 'The API has no authentication' is gone from docs/API.md")


# --- claim 3: the sub-status vocabulary -------------------------------------------------------

def check_substatus(text, source):
    """Which statuses can this tree actually construct?"""
    live = live_lines(source)
    built = set()
    for m in re.finditer(r"GraderResult\((?:[^()]|\([^()]*\))*?status\s*=\s*[\"'](\w+)[\"']", live, re.S):
        built.add(m.group(1))
    # the default on the model is a construction site too: nothing passing status= gets it
    default = re.search(r"status:\s*str\s*=\s*[\"'](\w+)[\"']", live)
    if default:
        built.add(default.group(1))
    if not built:
        bad("the sub-status values are constructible in code", "no GraderResult(status=…) site found")
        return

    # Named means NAMED AS A VALUE: backticked or quoted. A bare `\berror\b` matches the English word
    # in any paragraph, which is how the first draft of this check passed while the page had dropped
    # `refused` entirely — measured 2026-11-11 on a mutated copy. Prose counts for nothing here.
    named = set()
    for token in ("graded", "error", "refused"):
        if re.search(r"`%s`|\"%s\"|\x27%s\x27" % (token, token, token), text):
            named.add(token)

    undocumented = sorted(built - named)
    phantom = sorted(named - built)
    if not undocumented and not phantom:
        ok("the page's three-state vocabulary matches the statuses the code constructs",
            ", ".join(sorted(built)))
    if undocumented:
        bad("every sub-status the code can produce is named in the page",
            "code constructs: " + ", ".join(undocumented))
    if phantom:
        bad("every sub-status the page names can actually be produced",
            "page names, code never constructs: " + ", ".join(phantom))

    # the distinguishing claim: a raise is not an HTTP error
    err = re.search(r"GraderResult\((?:[^()]|\([^()]*\))*?status\s*=\s*[\"']error[\"']", live, re.S)
    if err:
        ok("status='error' is returned as a value, not raised",
            "grader crash path builds a result")
    else:
        info("status='error' construction site", "not found — re-read the page's error paragraph")

    if "grade.status == \"error\"" in text or 'grade.status == "error"' in text or '"error"' in text:
        pass  # prose-level; the vocabulary check above is the real one


# --- claim 4: the ttyd URL a client receives --------------------------------------------------

def check_ttyd_url(text, source):
    live = live_lines(source)
    rewrite = handler_body(live, "_rewrite_ttyd_urls")
    if not rewrite:
        bad("the ttyd URL is built from the request's Host header",
            "_rewrite_ttyd_urls not found")
        return
    if "headers.get(\"host\")" in rewrite or "headers.get('host')" in rewrite:
        ok("the ttyd URL follows the Host the browser used", "host header read, host swapped")
    else:
        bad("the ttyd URL follows the Host the browser used",
            "_rewrite_ttyd_urls no longer reads the Host header")
    if "request" in handler_body(live, "start_lab") and "_rewrite_ttyd_urls" in handler_body(live, "start_lab"):
        ok("start returns the rewritten URLs, not the derived ones")
    else:
        bad("start returns the rewritten URLs, not the derived ones",
            "start_lab does not call _rewrite_ttyd_urls on the ttyd map")


# --- main --------------------------------------------------------------------------------------

def main():
    if not os.path.isfile(API_DOC):
        die("docs/API.md is missing")
    if not os.path.isfile(BACKEND):
        die("backend/main.py is missing")
    text = open(API_DOC, encoding="utf-8").read()
    source = open(BACKEND, encoding="utf-8").read()

    # the app's own view of what it serves, for the /docs existence check
    import subprocess
    src = (
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "import main\n"
        "print(json.dumps({'docs': main.app.docs_url, 'redoc': main.app.redoc_url,\n"
        "                  'openapi': main.app.openapi_url}))\n" % os.path.join(ROOT, "backend")
    )
    proc = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        die("importing backend/main.py failed (needs fastapi/uvicorn/pyyaml). Last line: "
            + (tail[-1] if tail else "(no output)"))
    import json
    doc_urls = json.loads(proc.stdout)

    check_port_range(text, source)
    check_bind_and_docs(text, source, doc_urls)
    check_substatus(text, source)
    check_ttyd_url(text, source)

    info("NOT checked here (needs a live server, not this tree)",
         "whether /docs, /redoc and the ttyd ports are reachable through a real bind — "
         "that is an OPERATIONS/live-host question, not a doc-versus-source one")

    width = max(len(c) for _, c, _ in results)
    fails = sum(1 for s, _, _ in results if s == FAIL)
    for status, claim, detail in results:
        line = f"[{status}] {claim.ljust(width)}"
        if detail:
            line += f"  — {detail}"
        print(line)
    checked = sum(1 for s, _, _ in results if s in (PASS, FAIL))
    print(f"\n[check_api_exposure] {checked - fails}/{checked} claims hold; "
          f"{sum(1 for s, _, _ in results if s == INFO)} surface(s) named as out of scope.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
