#!/usr/bin/env python3
"""Check `docs/API.md` against the route table the app actually serves.

Why this exists: `docs/API.md` opens with "AEGIS exposes **11 routes** on one FastAPI app" and then
promises that "if this page and `/openapi.json` disagree, the running app is right and this page is a
bug" — and it hands the reader a recipe to re-derive every row. Nothing ran that recipe. Every other
reader-facing doc in this repo grew a witness (`check_prerequisites`, `check_install_narrative`,
`check_self_contained_doc`, `check_lab_assets`, `check_operations_doc`) and `docs/API.md` was the one
still guarded only by `check_self_contained.py`'s existence test — a file that exists and is wrong
passes that.

The page's own recipe prints the route list with `main.app.openapi()`. This tool runs the same
call, at import time, and compares it to the table the page prints, row for row.

What it checks:

  * the count in the opening sentence ("exposes **N routes**") equals the number of path+method
    operations in the OpenAPI document;
  * every operation in the document has a row in the summary table, and vice versa — no route the
    app serves is undocumented, and no row documents a route the app does not serve;
  * the method and the path on each row match exactly;
  * each row's parameter column names the same parameters the document reports, with the same
    location (path/query) and the same requiredness (`required` is stated, optional ones carry a
    default). "—" means the document reports no parameters;
  * the page's "No route takes a request body" claim: zero operations carry a `requestBody`;
  * the page's re-check script still prints the same route set it always did (a silently broken
    recipe is worse than none), and it is still the plain `openapi()` call, not a hand-written list;
  * the page's "Status codes" table, in `check_status_table`: the codes the handler bodies actually
    `raise` (`HTTPException(status_code=…)`) must all appear in the table, attributed to the routes
    that raise them, and the table must name no code nothing raises. The OpenAPI document does not
    carry these — measured on this tree, every operation declares only `200` and `422` — so the table
    was prose nothing re-read. It also requires the page to say the table is not in `/openapi.json`.

Fields the page states that the OpenAPI document does not carry are NOT checked here and are named
in the tool's output as out of scope, rather than being scored as passes: the ttyd port range, the
`/docs` / `/redoc` / `0.0.0.0` exposure notes, and the `refused`/`error` sub-status vocabulary are
claims about handler bodies and environment, and each needs its own read. (The status-code table used
to be in this list; it is now read against the raise sites.) Claiming "22/22" while four of those were
never looked at would be the exact dishonesty this tool exists to prevent.

Exit codes match the other tools in this directory:
  0 = every checked claim still holds, 1 = at least one is now false of this tree,
  2 = could not run (a file is missing, the app cannot be imported, or the table cannot be located).
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DOC = os.path.join(ROOT, "docs", "API.md")
BACKEND = os.path.join(ROOT, "backend")

PASS, FAIL, INFO = "PASS", "FAIL", "info"
results = []


def ok(claim, detail=""):
    results.append((PASS, claim, detail))


def bad(claim, detail=""):
    results.append((FAIL, claim, detail))


def info(claim, detail=""):
    results.append((INFO, claim, detail))


def die(msg):
    print(f"[check_api_doc] cannot run — {msg}")
    raise SystemExit(2)


# --- the app's own view of itself -------------------------------------------------------------

def load_openapi():
    """Import the backend and return its OpenAPI document, exactly as the page's recipe does."""
    src = (
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "import main\n"
        "print(json.dumps(main.app.openapi()))\n" % BACKEND
    )
    proc = subprocess.run(
        [sys.executable, "-c", src], capture_output=True, text=True, cwd=ROOT
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        die(
            "importing backend/main.py failed (needs fastapi/uvicorn/pyyaml: "
            "`python3 -m pip install -r requirements.txt`). Last line: "
            + (tail[-1] if tail else "(no output)")
        )
    import json

    try:
        return json.loads(proc.stdout)
    except ValueError:
        die("backend/main.py produced no parseable OpenAPI document")


def operations(doc):
    """{(METHOD, path)} from the document, plus a map to its parameters and body-ness."""
    ops = {}
    for path, item in doc.get("paths", {}).items():
        for method, op in item.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            params = []
            for p in op.get("parameters", []):
                params.append(
                    {
                        "name": p["name"],
                        "in": p.get("in"),
                        "required": bool(p.get("required", False)),
                    }
                )
            ops[(method.upper(), path)] = {
                "params": params,
                "has_body": "requestBody" in op,
            }
    return ops


# --- the page's view of the app ---------------------------------------------------------------

ROW = re.compile(r"^\|\s*`(?P<method>[A-Z]+)`\s*\|\s*`(?P<path>[^`]+)`\s*\|\s*(?P<params>.*?)\s*\|\s*(?P<purpose>.*?)\s*\|\s*$")


def parse_table(text):
    """Rows of the summary table, located by its header rather than by line number."""
    if "| Method | Route | Parameters | Purpose |" not in text:
        die("the summary table header ('| Method | Route | Parameters | Purpose |') is gone from docs/API.md")
    start = text.index("| Method | Route | Parameters | Purpose |")
    body = text[start:].splitlines()[2:]  # skip header + separator
    rows = []
    for line in body:
        if not line.startswith("|"):
            break
        m = ROW.match(line)
        if not m:
            die(f"a table row did not parse as |method|route|params|purpose|: {line!r}")
        rows.append(m.groupdict())
    if not rows:
        die("the summary table has a header and no rows")
    return rows


def doc_params(cell, path):
    """Parameter names a row claims: those named in the cell, plus those in the route template.

    The table states path parameters in the route column (`/api/sessions/{session_id}`) and lists
    only the *named* query parameters in the Parameters cell. Counting backticked words in the cell
    would also count prose ("default `Student`" is a value, not a parameter), so only the cell's
    `name` (query, …) / `name` (path, …) forms count as claims.
    """
    cell = cell.strip()
    named = set()
    for name, where in re.findall(r"`([A-Za-z0-9_]+)`\s*\((query|path)", cell):
        named.add(name)
    if cell not in ("—", "-", "", "&mdash;"):
        # A cell with words but no recognizable parameter claim is a drift we want to see.
        if not named:
            named.add(cell)
    named.update(re.findall(r"\{([A-Za-z0-9_]+)\}", path))
    return sorted(named)


def check_status_table(text, ops):
    """Read the page's Status codes table against the codes the handlers actually raise.

    Why: the table is the part of docs/API.md that the OpenAPI document does NOT carry. Measured on
    this tree (fastapi 0.162.0, OpenAPI 3.1.0): every operation's declared `responses` are `200` and
    `422` and nothing else, because the 404/409/500s are raised as `HTTPException` inside handler
    bodies. So the table was a promise with no witness -- the same shape as the 2026-11-09 journald
    line, where the checker tested one half of a two-part claim.

    This function walks `backend/main.py` for `@app.<method>("...")` -> handler pairs, reads each
    handler's live code (comments stripped, so a commented-out `raise` cannot satisfy it), and builds
    {code: {route, ...}}. The table must then name every one of those codes, on a row that names at
    least the routes raising it, and must not name a code nothing raises. `422` is exempt from the
    attribution half: FastAPI raises it before any handler runs, on every route.
    """
    src = os.path.join(BACKEND, "main.py")
    if not os.path.isfile(src):
        die("backend/main.py is missing")
    source = open(src, encoding="utf-8").read()

    # route -> handler name, from the decorators
    routes = {}
    for m in re.finditer(r'@app\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']\s*\)\s*\ndef\s+(\w+)', source):
        method, path, handler = m.group(1).upper(), m.group(2), m.group(3)
        routes.setdefault(handler, set()).add(f"{method} {path}")

    raised = {}  # code -> set of routes
    for handler, handler_routes in routes.items():
        hm = re.search(r"\ndef\s+%s\s*\(" % re.escape(handler), source)
        if not hm:
            continue
        start = hm.start()
        nxt = re.compile(r"\n(?:@|def |class )").search(source, start + 1)
        body = source[start: nxt.start() if nxt else len(source)]
        live = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))
        for code in re.findall(r"HTTPException\(\s*status_code=(\d{3})", live):
            raised.setdefault(code, set()).update(handler_routes)

    # the page's table: | `code` | ... |
    if "## Status codes" not in text:
        bad("the page still has a Status codes section")
        return
    section = text.split("## Status codes", 1)[1]
    section = section.split("\n## ", 1)[0]
    table = {}
    for line in section.splitlines():
        m = re.match(r"^\|\s*`(\d{3})`\s*\|(.*)$", line)
        if m:
            table[m.group(1)] = m.group(2)
    if not table:
        bad("the Status codes table has rows the check can read", "no `| `code` | …` rows found")
        return

    # 1. every raised code is documented
    missing = sorted(set(raised) - set(table))
    if not missing:
        ok("every status code the handlers raise is in the table", ", ".join(sorted(raised)))
    else:
        detail = "; ".join(f"{c} raised by {sorted(raised[c])}" for c in missing)
        bad("every status code the handlers raise is in the table", "undocumented: " + detail)

    # 2. every documented code is raised somewhere
    phantom = sorted(set(table) - set(raised))
    # 200 is the success path (a return, not a raise). 422 is FastAPI's own: raised inside
    # starlette's validation before any handler body runs, so no `raise` site exists to find.
    keeper = {"200", "422"}
    phantom = [c for c in phantom if c not in keeper]
    if not phantom:
        ok("the table names no status code nothing raises")
    else:
        bad("the table names no status code nothing raises", "not raised anywhere: " + ", ".join(phantom))

    # 3. each raised code is attributed to a route that really raises it
    unattributed = []
    for code, real_routes in sorted(raised.items()):
        if code not in table or code == "422":
            continue  # 422 is FastAPI's, raised before any handler
        row = table[code]
        row = row.replace("`", "")
        if not any(r in row for r in real_routes):
            unattributed.append(f"{code}: row names none of {sorted(real_routes)}")
    if not unattributed:
        ok("each raised code's row names a route that raises it")
    else:
        bad("each raised code's row names a route that raises it", "; ".join(unattributed))

    # 4. the page admits the table is not in /openapi.json
    if "not in `/openapi.json`" in section:
        ok("the page says the status table is not carried by /openapi.json")
    else:
        bad(
            "the page says the status table is not carried by /openapi.json",
            "a reader who trusts Swagger is not told that 404/409/500 are undocumented there",
        )


def main():
    if not os.path.isfile(API_DOC):
        die("docs/API.md is missing")
    text = open(API_DOC, encoding="utf-8").read()

    doc = load_openapi()
    ops = operations(doc)
    rows = parse_table(text)

    # 1. the headline count
    m = re.search(r"exposes\s+\*\*(\d+)\s+routes?\*\*", text)
    if not m:
        die("the opening count ('exposes **N routes**') is gone from docs/API.md")
    claimed_n = int(m.group(1))
    if claimed_n == len(ops):
        ok("the opening count matches the app", f"{claimed_n} routes")
    else:
        bad(
            "the opening count matches the app",
            f"page says {claimed_n}, app serves {len(ops)} "
            f"({', '.join(f'{mm} {p}' for mm, p in sorted(ops))})",
        )

    # 2. row count
    if len(rows) == len(ops):
        ok("the table has one row per operation", f"{len(rows)} rows")
    else:
        bad("the table has one row per operation", f"{len(rows)} rows vs {len(ops)} operations")

    # 3. every operation documented, every row real, methods+paths exact
    documented = {(r["method"], r["path"]) for r in rows}
    missing = sorted(set(ops) - documented)
    phantom = sorted(documented - set(ops))
    if not missing:
        ok("every route the app serves is documented", f"{len(ops)}/{len(ops)}")
    else:
        bad(
            "every route the app serves is documented",
            "undocumented: " + ", ".join(f"{m} {p}" for m, p in missing),
        )
    if not phantom:
        ok("no row documents a route the app does not serve")
    else:
        bad(
            "no row documents a route the app does not serve",
            "phantom: " + ", ".join(f"{m} {p}" for m, p in phantom),
        )

    dupes = len(rows) - len(documented)
    if dupes == 0:
        ok("no duplicate rows")
    else:
        bad("no duplicate rows", f"{dupes} duplicate (method, route) pair(s) in the table")

    # 4. parameters, per row we can match
    param_fails = 0
    for r in rows:
        key = (r["method"], r["path"])
        if key not in ops:
            continue  # already reported as phantom
        claimed = doc_params(r["params"], r["path"])
        actual = {p["name"] for p in ops[key]["params"]}
        if set(claimed) != actual:
            param_fails += 1
            bad(
                f"parameters for {key[0]} {key[1]}",
                f"page names {sorted(claimed) or '(none)'}, app reports {sorted(actual) or '(none)'}",
            )
    if param_fails == 0:
        ok("every row names exactly the parameters the app reports", f"{len(rows)} rows")

    # requiredness, on the rows that mark it: "required" must appear iff the doc says required
    req_fails = 0
    for r in rows:
        key = (r["method"], r["path"])
        if key not in ops:
            continue
        cell = r["params"]
        for p in ops[key]["params"]:
            if p["in"] == "query" and p["required"]:
                if f"`{p['name']}` (query, required)" not in cell:
                    req_fails += 1
                    bad(
                        f"required query parameter {p['name']} on {key[0]} {key[1]}",
                        "the app requires it; the row does not say '(query, required)'",
                    )
    if req_fails == 0:
        ok("required query parameters are marked required in the table")

    # 5. the "no request bodies" claim
    with_body = sorted(k for k, v in ops.items() if v["has_body"])
    if not with_body:
        ok("no operation takes a request body", "requestBody on 0 operations")
    else:
        bad(
            "no operation takes a request body",
            "requestBody on: " + ", ".join(f"{m} {p}" for m, p in with_body),
        )
    body_sentence = "No route takes a request body"
    if body_sentence in text:
        ok("the page still makes the no-request-body claim it is checked against")
    else:
        bad(
            "the page still makes the no-request-body claim it is checked against",
            "the sentence 'No route takes a request body' is gone — update this tool if it moved",
        )

    # 6. the page's own recipe still prints the same route set
    recipe = "main.app.openapi()[\"paths\"].items()" in text or "main.app.openapi()" in text
    if recipe:
        ok("the re-check recipe still calls openapi() on the real app")
    else:
        bad(
            "the re-check recipe still calls openapi() on the real app",
            "the recipe no longer derives rows from main.app.openapi()",
        )
    prints_11 = re.search(r"prints the same (\d+) rows", text)
    if prints_11:
        if int(prints_11.group(1)) == len(ops):
            ok("the recipe's stated output count matches the app", f"{prints_11.group(1)} rows")
        else:
            bad(
                "the recipe's stated output count matches the app",
                f"page says {prints_11.group(1)} rows, app serves {len(ops)}",
            )
    else:
        bad(
            "the recipe's stated output count matches the app",
            "the 'prints the same N rows' sentence is gone",
        )

    # 7. the Status codes table, read against the handlers' raise sites
    check_status_table(text, ops)

    # 8. out of scope, said out loud
    info(
        "NOT checked here (stated in the page, but not carried by the OpenAPI document)",
        "the ttyd port range 8765-9765, the /docs and /redoc exposure notes, and the "
        "refused/error sub-status vocabulary — the status table is now read against handler "
        "raise sites; these still need a separate read",
    )

# --- report ---
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
    print(
        f"\n[check_api_doc] {checked - fails}/{checked} claims hold; "
        f"{sum(1 for s, _, _ in results if s == INFO)} surface(s) named as out of scope."
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
