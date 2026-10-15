"""Run mypy over the tree and fail on a type error in a file that is clean today.

Nothing read the annotations, so nothing held them: on 15 October 2026, mypy's
default settings reported **350 errors across 29 of the 70 modules** at the root
and under `tools/` in **7 seconds** (measured here, dated, in
`docs/build-performance-findings.md`), and 132 more of them in those same modules
under `--strict`. The largest cause is one pattern, not 350 mistakes:
`atoc_fares_loader.FaresLoader` sets the attributes its subclass `FaresDb` reads,
so mypy sees 108 "has no attribute" errors in the mixin. Fixing all of it is a
typing project with its own measurement.

What this tool does instead is hold the line where the line already holds. The
list below is every module and tool that reported **no error of its own** on that
measurement, so the check is green the day it lands and fails the day a change
adds an error to one of them. A module joins the list when its own errors are
gone and never leaves it without a reason written in the same commit.

    python -m tools.check_types                # the listed files
    python -m tools.check_types --all          # every root module and tool, for the census

Exit codes: 0 every listed file is clean, 1 a listed file has an error (each is
printed), 2 mypy is not installed, or reported nothing this could read, or the
tree lost a file the list names. The third code is not a pass: a check that could
not run says so.

**What it does not do.** It does not fix anything, and it does not fail on an
error in a file that is not on the list -- a file with pre-existing errors is not
made worse by being read. `--all` prints the whole census without failing, which
is how the list is grown.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Every Python file at the root or under `tools/` whose own type errors are zero
#: (measured 15 October 2026, mypy 2.4.0, default settings). A file that is clean
#: and not here is a file nobody has looked at yet; the list grows, never shrinks.
CLEAN = (
    "atoc_fare_declarations.py",
    "atoc_knowledgebase.py",
    "build_demo_page.py",
    "build_release.py",
    "build_render.py",
    "build_stations.py",
    "build_workers.py",
    "damage_feed.py",
    "destination_coverage.py",
    "feeds_cli.py",
    "fuzz_feed.py",
    "page_templates.py",
    "retailer.py",
    "run.py",
    "tools/build_inputs.py",
    "tools/build_timetable_index.py",
    "tools/check_commit_message.py",
    "tools/check_facet_reference.py",
    "tools/check_links.py",
    "tools/check_release_clearance.py",
    "tools/easy_fares_check.py",
    "tools/measure_build_memory.py",
    "tools/measure_origin_costs.py",
    "tools/measure_worker_pages.py",
    "tools/page_bytes.py",
    "tools/propose_fare_construction_stations.py",
    "tools/verify.py",
)

#: The directories a build or a test run writes. mypy is pointed at source only.
GENERATED = ("_site", "_demo_site", "_shape_site", "_cache", "_probe_feed", "_zz_feed",
             "_demo_feed", "_demo_kb", "_shape_feed", "_stations", "__pycache__")

ERROR = re.compile(r"^(?P<file>[^:]+):\d+: error:")


def sources(root: Path) -> list[str]:
    """Every Python source at the root and under `tools/`, as mypy wants them."""
    return sorted(
        path.relative_to(root).as_posix()
        for path in (*root.glob("*.py"), *(root / "tools").glob("*.py"))
        if path.is_file()
    )


def run_mypy(root: Path, files: list[str]) -> tuple[int, str] | None:
    """mypy's exit code and its report, or None when mypy is not installed."""
    try:
        done = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-incremental", *files],
            cwd=root,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if "No module named mypy" in done.stderr or "No module named 'mypy'" in done.stderr:
        return None
    return done.returncode, done.stdout + done.stderr


def errors_in(report: str) -> dict[str, list[str]]:
    """Every error, keyed by the file mypy attributed it to."""
    found: dict[str, list[str]] = {}
    for line in report.splitlines():
        match = ERROR.match(line.strip())
        if match is None:
            continue
        name = match.group("file").replace("\\", "/").lstrip("./")
        found.setdefault(name, []).append(line.strip())
    return found


def check(root: Path, everywhere: bool) -> int:
    files = sources(root)
    if not files:
        print("error: no Python source found to check", file=sys.stderr)
        return 2
    missing = [name for name in CLEAN if not (root / name).is_file()]
    if missing:
        print(
            f"error: the clean list names {len(missing)} file(s) that are not there: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 2
    result = run_mypy(root, files if everywhere else list(CLEAN))
    if result is None:
        print("error: mypy is not installed (python -m pip install mypy)", file=sys.stderr)
        return 2
    _, report = result
    found = errors_in(report)
    if not found and not everywhere:
        # A mypy that reported nothing at all, on a list of files that are known
        # to be checked, is a mypy that did not read them.
        print("error: mypy reported nothing, so it read nothing", file=sys.stderr)
        return 2
    watched = set(files) if everywhere else set(CLEAN)
    failing = {name: lines for name, lines in found.items() if name in watched}
    if everywhere:
        for name in sorted(failing):
            print(f"{name}: {len(failing[name])} error(s)")
        print(
            f"{len(failing)} file(s) with errors of their own, "
            f"{len(found)} file(s) reported in all"
        )
        return 0
    if failing:
        for name in sorted(failing):
            for line in failing[name]:
                print(line)
        print(
            f"{sum(len(lines) for lines in failing.values())} error(s) in "
            f"{len(failing)} file(s) that were clean: fix them, or move the file "
            "off the clean list with the reason in the same commit",
            file=sys.stderr,
        )
        return 1
    print(f"{len(CLEAN)} clean file(s), no type error of their own")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--all",
        action="store_true",
        help="print the census over every root module and tool, and fail on nothing",
    )
    args = parser.parse_args(argv)
    return check(ROOT, args.all)


if __name__ == "__main__":
    raise SystemExit(main())
