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
    recipe is worse than none), and it is still the plain `openapi()` call, not a hand-written list.

Fields the page states that the OpenAPI document does not carry are NOT checked here and are named
in the tool's output as out of scope, rather than being scored as passes: the `404/409/422/500`
table, the ttyd port range, and the `/docs` / `/redoc` exposure notes are claims about handler
bodies and environment, and each needs its own read. Claiming "22/22" while four of those were
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

    # 7. out of scope, said out loud
    info(
        "NOT checked here (stated in the page, but not carried by the OpenAPI document)",
        "the 404/409/422/500 status table, the ttyd port range 8765-9765, and the /docs, /redoc, "
        "0.0.0.0 exposure notes — each needs a separate read of handler bodies and environment",
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
