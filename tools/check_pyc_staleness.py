#!/usr/bin/env python3
"""check_pyc_staleness.py — reproduce the stale-`.pyc` case OPERATIONS.md documents.

Why this exists: `backend/main.py::_load_grader` imports a grader with
`importlib.util.spec_from_file_location(...).exec_module(...)`. Python's source loader
writes `__pycache__/<name>.<tag>.pyc` next to the module and, on a later import, reuses
that bytecode when the source's **size and whole-second mtime** both still match. So a
rewrite within the same second at the same byte length (a one-character fix such as
`THRESHOLD = 2` -> `THRESHOLD = 3`, or any scripted rewrite) serves the OLD value — and
because the `.pyc` is on disk, a fresh process serves it too. `docs/OPERATIONS.md` says
exactly that, and says `rm -rf __pycache__` is the remedy.

A doc reading a file cannot show any of this. This script executes it, with the same
import call the loader uses, on a throwaway copy in the system temp dir. It never
touches the repo's `lab-definitions/`.

Each case below is a claim in OPERATIONS.md. Change the loader, change Python's
behaviour, or change the doc's remedy, and one of them fails.

Exit 0 = every measured case still matches the doc. Exit 1 = at least one does not.
Exit 2 = could not run (no temp dir / no interpreter detail).

Run from anywhere:  python3 tools/check_pyc_staleness.py
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import time

SRC = "THRESHOLD = {v}\ndef score():\n    return THRESHOLD\n"
failures = []
passes = 0


def report(name, ok, detail=""):
    global passes
    if ok:
        passes += 1
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}" + (f"\n        {detail}" if detail else ""))
        failures.append(name)


def load(path, name):
    """The same two calls _load_grader makes, nothing more."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no loader for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.score()


def wait_for_fresh_second():
    """Sleep to the start of the next wall-clock second.

    Same-second is the whole point: it must be engineered, not hoped for.
    """
    now = time.time()
    time.sleep((1.0 - (now % 1.0)) + 0.02)


def main():
    try:
        work = tempfile.mkdtemp(prefix="pyc-witness-")
    except OSError as exc:
        print(f"[check_pyc_staleness] cannot run — no temp dir: {exc}")
        return 2
    try:
        grader = os.path.join(work, "grader_witness.py")
        cache_dir = os.path.join(work, "__pycache__")

        def write(value):
            with open(grader, "w", encoding="utf-8") as fh:
                fh.write(SRC.format(v=value))

        def clear_cache():
            if os.path.isdir(cache_dir):
                shutil.rmtree(cache_dir)

        def grade():
            # A unique module name per load: _GRADER_CACHE also keys by name, and this
            # script must measure the .pyc layer only, not any in-process cache.
            return load(grader, f"grader_witness_{time.time_ns()}")

        print(f"python {sys.version.split()[0]}  {sys.executable}")
        print(f"scratch tree {work}\n")

        # --- Case 1: same second, same size -> STALE ------------------------
        clear_cache()
        wait_for_fresh_second()
        write(2)
        first = grade()
        st_a = os.stat(grader)
        write(3)                     # one character, identical byte length
        st_b = os.stat(grader)
        same_sec = int(st_a.st_mtime) == int(st_b.st_mtime)
        same_size = st_a.st_size == st_b.st_size
        second = grade()
        report("same second + same size rewrite serves the OLD value (doc: 'the stale `.pyc` wins')",
               same_sec and same_size and first == 2 and second == 2,
               f"engineered same-second={same_sec} same-size={same_size}; "
               f"got first={first} second={second} (expected 2 then 2)")

        # --- Case 2: the .pyc is on disk -> a FRESH PROCESS is stale too ----
        # (still in the same second relative to the edit above, so re-establish it)
        clear_cache()
        wait_for_fresh_second()
        write(2)
        grade()
        write(3)
        stale_pyc = os.path.isdir(cache_dir) and any(
            f.endswith(".pyc") for f in os.listdir(cache_dir))
        report(".pyc is written next to the module (no PYTHONDONTWRITEBYTECODE needed)", stale_pyc,
               f"nothing in {cache_dir}" if os.path.isdir(cache_dir) else "no __pycache__ dir made")
        fresh = load(grader, "grader_witness_fresh_process")
        report("a fresh process in the same second also serves the OLD value (doc: 'a restart does not clear it')",
               fresh == 2, f"got {fresh} (expected 2)")

        # --- Case 3: time passing does NOT clear it ------------------------
        # Measured 2026-11-08 (twice): after a same-second, same-size rewrite the OLD value
        # is still served on the next second and several seconds later, in this process and
        # in a fresh one, with importlib.invalidate_caches() making no difference. The
        # .pyc header (timestamp mode, source mtime SECOND, source size) and the whole file
        # are byte-identical across those loads, so the loader reuses the bytecode.
        # docs/OPERATIONS.md said "next second -> fresh" until a witness run measured the
        # opposite; that was a harness that waited for a fresh second BEFORE the edit, i.e.
        # it ran a different experiment than the sentence described.
        clear_cache()
        wait_for_fresh_second()
        write(2)
        first = grade()
        write(3)                     # same second, same byte length -> stale
        same_second = grade()
        time.sleep(1.05)             # cross into the next second
        importlib.invalidate_caches()
        next_second = load(grader, f"grader_witness_next_second_{time.time_ns()}")
        time.sleep(3.0)              # and well past it
        importlib.invalidate_caches()
        later = load(grader, f"grader_witness_later_{time.time_ns()}")
        report("neither the next second nor a later wait clears the stale .pyc (doc: clears only on a "
               "size or mtime-second change)",
               first == 2 and same_second == 2 and next_second == 2 and later == 2,
               f"got same-second={same_second} next-second={next_second} +3s={later} (expected 2, 2, 2). "
               "If this now passes only because the value is fresh, the loader changed — re-measure the doc.")

        # --- Case 3b: a changed SIZE clears it ------------------------------
        write(33)                    # one byte longer, still within the same second
        importlib.invalidate_caches()
        size_changed = load(grader, f"grader_witness_size_{time.time_ns()}")
        report("a size change clears it (doc: 'clears when the source's size changes')",
               size_changed == 33, f"got {size_changed} (expected 33)")

        # --- Case 4: same second, different size -> FRESH -------------------
        clear_cache()
        wait_for_fresh_second()
        write(2)
        first = grade()
        write(33)                    # one byte longer
        fresh3 = grade()
        report("same second + different size serves the NEW value",
               first == 2 and fresh3 == 33, f"got first={first} second={fresh3} (expected 2 then 33)")

        # --- Case 5: the doc's remedy works ---------------------------------
        clear_cache()
        wait_for_fresh_second()
        write(2)
        grade()
        write(3)                     # stale condition established again
        stale = grade()
        # Exactly the command OPERATIONS.md prints, scoped to this scratch tree.
        clear_cache()
        fixed = grade()
        report("removing __pycache__ and re-importing serves the NEW value (doc's remedy)",
               stale == 2 and fixed == 3, f"got stale={stale} then after rm={fixed} (expected 2 then 3)")

        print()
        print(f"{passes} PASS, {len(failures)} FAIL")
        return 1 if failures else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
