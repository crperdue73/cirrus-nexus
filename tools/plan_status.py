#!/usr/bin/env python3
"""
AEGIS backlog status — count the checkboxes in docs/GITHUB-PLAN.md.

Why this exists (2026-10-25): the worklog's header calls the file "the
maintainer's dated worklog of polish runs", and every run appends a new entry
at the top of the `## Backlog` list, each tagged `[x]` or `[ ]`. Nothing in the
tree ever counted them, so the one line a reader actually wants from a backlog
— "how much of this is still open?" — could only be answered by scrolling a
100 KB file. This prints it.

What it counts, exactly:
  * fenced code blocks are skipped (a checklist example inside ``` is not an item);
  * `## Backlog` starts the region, the next `## ` heading ends it;
  * inside it, a top-level `- [ ]` / `- [x]` line is one item, and any
    indented `- [ ]` line that follows is a *sub*checkbox of it, reported apart
    so a partly-checked item does not read as done or as not-started.

What it does NOT do: judge whether an item is finished. `[x]` here means the
maintainer ticked it; the last word on the project is the operator's, not a
checkbox (see CONTRIBUTING.md, "Commits").

Usage:  python3 tools/plan_status.py [--json]
Exit code 0 always — this reports, it does not gate CI. A missing plan file is
an error (exit 2), not an empty backlog.
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PLAN = BASE / "docs" / "GITHUB-PLAN.md"

TOP_ITEM = re.compile(r"^- \[( |x|X)\]\s")
SUB_ITEM = re.compile(r"^[ \t]+- \[( |x|X)\]\s")


def backlog_lines(path: Path):
    """Yield (lineno, text) for the `## Backlog` region, code fences removed."""
    in_backlog = False
    in_fence = False
    for lineno, text in enumerate(path.read_text().splitlines(), start=1):
        if text.startswith("```"):
            in_fence = not in_fence
            yield lineno, None
            continue
        if in_fence:
            yield lineno, None
            continue
        if text.startswith("## "):
            in_backlog = text.strip() == "## Backlog (one item per polish run)" or text.strip().startswith(
                "## Backlog"
            )
            yield lineno, None
            continue
        if in_backlog:
            yield lineno, text


def summarize(path: Path) -> dict:
    items = []
    current = None
    for lineno, text in backlog_lines(path):
        if text is None:
            continue
        if TOP_ITEM.match(text):
            current = {
                "line": lineno,
                "done": TOP_ITEM.match(text).group(1).lower() == "x",
                "title": _title(text),
                "sub_open": 0,
                "sub_done": 0,
            }
            items.append(current)
        elif SUB_ITEM.match(text) and current is not None:
            if SUB_ITEM.match(text).group(1).lower() == "x":
                current["sub_done"] += 1
            else:
                current["sub_open"] += 1
    done = sum(1 for i in items if i["done"])
    open_items = [i for i in items if not i["done"]]
    return {
        "file": str(path.relative_to(BASE)),
        "items": len(items),
        "done": done,
        "open": len(open_items),
        "open_titles": [i["title"] for i in open_items],
        "sub_open_total": sum(i["sub_open"] for i in items),
        "first_item_line": items[0]["line"] if items else None,
    }


def _title(text: str) -> str:
    """The item's opening clause, markdown emphasis stripped, for a listing."""
    t = text[6:].strip()
    t = re.sub(r"\*\*|\*|`", "", t)
    t = t.split(" (2026-", 1)[0]
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 110:
        t = t[:107].rstrip() + "..."
    return t


def main() -> int:
    if not PLAN.exists():
        print(f"NO PLAN FILE: {PLAN} does not exist (this is not an empty backlog).", file=sys.stderr)
        return 2
    if "--json" in sys.argv[1:]:
        print(json.dumps(summarize(PLAN), indent=2))
        return 0
    s = summarize(PLAN)
    print(f"{s['file']}: {s['items']} backlog item(s) — {s['done']} ticked, {s['open']} open")
    if s["sub_open_total"]:
        print(f"  ({s['sub_open_total']} open sub-checkbox(es) inside ticked items — read those entries, not the tick)")
    for t in s["open_titles"]:
        print(f"   [ ] {t}")
    print("A tick means the maintainer ticked it. It is not a statement that the project is done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
