"""The checks a change has to pass, in one command, on any platform.

An agent's cheapest loop in this repository was `python -m unittest
tests.<module>`, one file at a time: the page's tests take 156 s and the fares
parser's 200 s, and neither command runs the page's JavaScript. The suite that
does execute that JavaScript ran only in CI, after a feed download and a site
build, in a step of a hundred lines of bash inside the workflow, which a Windows
checkout cannot run at all (F5 of the 8 October 2026 agent-efficiency audit).
This is that entry point, written in Python so the same command covers a
developer's machine and the release.

    python tools/verify.py --fast      both unit suites minus the feed-scale tests, and the page's JavaScript parsed
    python tools/verify.py --full      every unit test, and the page's JavaScript parsed
    python tools/verify.py --browser   a synthetic feed, the demo and shape builds, then the browser suite
    python tools/verify.py --all       --full, then --browser

`--browser` drives the pages CI drives, built from the synthetic feed with the
same commands, and adds the pages a built site already has at `_site` when they
are there. It needs Playwright's chromium and downloads nothing itself.

Exit codes: 0 every step ran and passed, 1 a step ran and failed, 2 a step could
not run (node or Playwright missing, a build that wrote no page).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# `python tools/verify.py` puts tools/ on the path, not the directory this
# repository's modules live in, and every test module under tests/ imports those
# by bare name. Without this the whole suite loads as 16 failed imports.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: The tests that read the licensed national feed. Two of them are 58 s and 49 s
#: of the fares module's 200 s, measured on 8 October 2026 with `python -m
#: unittest --durations 15 tests.test_atoc_fares`, and they are the same file
#: read twice. `--fast` leaves them to `--full` rather than to every edit.
FEED_SCALE = (
    "test_atoc_fares.FaresParserTest.test_the_real_feed_marks_its_advance_tickets_train_restricted",
    "test_atoc_fares.FaresParserTest.test_real_gra_to_not_keeps_two_together_r9_price",
)

#: The page's own JavaScript, which no Python check can parse (audit C2). The
#: station route is one file per panel under a subdirectory, so the pattern has
#: to reach below the first level or the panels stop being checked.
JAVASCRIPT = "page/**/*.js"

#: The service date the demo and shape pages are built for. A build with no date
#: carries no week of days, so ten checks about the day the table reports -- the
#: control's options, the wording of every absence, the day in the address --
#: had nothing to read and were skipped on the two pages that have a timetable,
#: on every run. Monday 5 October 2026 is inside the synthetic feed's own window
#: (21 September to 11 December 2026) and is the date
#: `tests/test_build_demo_page.py` builds its own pages for. Fixed rather than
#: today's date, because the fixture's window is fixed: a build at today's date
#: stops carrying journeys once the window ends, and which weekday the fixture
#: shows should be a property of the fixture rather than of the run. The
#: workflow's own build reads this constant rather than naming a second date,
#: because two copies of a date is two chances for the suite and CI to drive
#: different days and for only one of them to be noticed.
SERVICE_DATE = "2026-10-05"
DEMO_FEED = "_demo_feed"
DEMO_KB = "_demo_kb"
DEMO_SITE = "_demo_site"
SHAPE_FEED = "_shape_feed"
SHAPE_SITE = "_shape_site"
SITE = "_site"


class Step:
    """One check, with what it costs and whether it ran."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.started = time.monotonic()
        self.ok: bool | None = None
        self.detail = ""

    def done(self, ok: bool | None, detail: str = "") -> "Step":
        self.ok, self.detail = ok, detail
        return self

    @property
    def seconds(self) -> float:
        return time.monotonic() - self.started

    def line(self) -> str:
        state = {True: "ok", False: "FAILED", None: "not run"}[self.ok]
        return f"{state:>7}  {self.name} ({self.seconds:.1f}s){': ' + self.detail if self.detail else ''}"


def _discover(directory: str) -> unittest.TestSuite:
    # The same discovery the CI and the README use, `discover -s <directory> -p
    # "test_*.py"` with its default top level, which puts that directory on the
    # path: a tools test imports its sibling by bare name, as
    # `test_build_timetable_index` imports `make_synthetic_feed`. Discovery from
    # the repository root, whatever directory the command was run from.
    return unittest.TestLoader().discover(directory, pattern="test_*.py")


def without(suite: unittest.TestSuite, excluded: frozenset[str]) -> unittest.TestSuite:
    """The same suite minus the named test ids, which is how --fast is defined."""
    kept = unittest.TestSuite()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            kept.addTest(without(item, excluded))
        elif item.id() not in excluded:
            kept.addTest(item)
    return kept


def unit(fast: bool) -> Step:
    step = Step("unit tests" + (" (fast)" if fast else ""))
    excluded = frozenset(FEED_SCALE) if fast else frozenset()
    suite = without(_discover("tests"), excluded)
    suite.addTest(without(_discover("tools"), excluded))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    ran = result.testsRun
    detail = f"{ran:,} tests"
    if not result.wasSuccessful():
        failed = len(result.failures) + len(result.errors)
        detail = f"{ran:,} tests, {failed} failing"
    return step.done(result.wasSuccessful(), detail)


def javascript() -> Step:
    step = Step("page JavaScript parses")
    node = shutil.which("node")
    if node is None:
        return step.done(None, "node is not on PATH")
    files = sorted(Path(ROOT).glob(JAVASCRIPT))
    if not files:
        return step.done(None, f"no files match {JAVASCRIPT}")
    for path in files:
        checked = subprocess.run(
            [node, "--check", str(path)], capture_output=True, text=True, cwd=ROOT
        )
        if checked.returncode:
            print(checked.stderr.strip(), file=sys.stderr)
            return step.done(False, f"{path.name} does not parse")
    return step.done(True, f"{len(files)} file(s)")


def _run(command: list[str], what: str) -> bool:
    print(f"  $ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        print(f"  {what} exited {result.returncode}", file=sys.stderr)
    return result.returncode == 0


def browser() -> Step:
    """The pages the browser suite drives, built here, then the suite itself."""
    step = Step("browser suite")
    if shutil.which("node") is None:
        return step.done(None, "node is not on PATH")
    steps = [
        (["python", "make_synthetic_feed.py", DEMO_FEED, "--unserved-station", "--third-origin", "--return-network", "--knowledgebase", DEMO_KB], "the demo feed"),
        (["python", "build_demo_page.py", "--feed", DEMO_FEED, "--timetable", DEMO_FEED, "--knowledgebase", DEMO_KB, "--all-origins", "--date", SERVICE_DATE, "--out", f"{DEMO_SITE}/index.html"], "the demo site"),
        # --third-origin and --return-network for the same reason the demo feed
        # takes them: without them this feed's secondary origins are priced to
        # one station each, and a page with one row cannot exercise its own
        # controls -- no shortlist of two, no second destination type, no
        # heritage row, nothing for the dock to hold. The shape this build is
        # for is the list that fits on one page (ADR-0058); the number of rows
        # was never the point, and the six to eight the feed now prices against
        # each origin still fit.
        (["python", "make_synthetic_feed.py", SHAPE_FEED, "--unserved-station", "--third-origin", "--return-network"], "the shape feed"),
        # No --timetable, so the page prices fares only, and no --date for the
        # same reason: a build with no times has no day to report, and a page
        # carrying a date it cannot report times for would be claiming one.
        (["python", "build_demo_page.py", "--feed", SHAPE_FEED, "--origin", "GRN", "--out", f"{SHAPE_SITE}/prices-only/index.html"], "the prices-only page"),
        (["python", "build_demo_page.py", "--feed", SHAPE_FEED, "--timetable", SHAPE_FEED, "--all-origins", "--date", SERVICE_DATE, "--out", f"{SHAPE_SITE}/one-page/index.html"], "the one-page shape"),
    ]
    for command, what in steps:
        if not _run(command, what):
            return step.done(None, f"{what} did not build")

    station = sorted(Path(ROOT, DEMO_SITE).glob("from/*/index.html"))
    one_page = sorted(Path(ROOT, SHAPE_SITE).glob("one-page/from/*/index.html"))
    pages = [
        *station[:1],
        Path(ROOT, DEMO_SITE, "index.html"),
        Path(ROOT, DEMO_SITE, "privacy/index.html"),
        *one_page[-1:],
        Path(ROOT, SHAPE_SITE, "prices-only/from/grantham/index.html"),
    ]
    missing = [page for page in pages if not page.is_file() or not page.stat().st_size]
    if missing:
        return step.done(False, "a build wrote no page at " + ", ".join(str(page) for page in missing))

    # The site the release would publish, when it is on disk: CI drives it, and a
    # local run that has just built one should drive it too.
    sweep: list[str] = []
    if Path(ROOT, SITE, "index.html").is_file():
        pages += [Path(ROOT, SITE, "index.html"), Path(ROOT, SITE, "privacy/index.html")]
        if Path(ROOT, SITE, "from").is_dir():
            pages.append(Path(ROOT, SITE, "from"))
            sweep = ["--sweep", "--max", "24"]

    # `shutil.which` rather than the bare name: on Windows the launcher is
    # npx.cmd, and CreateProcess does not resolve a batch file, so the
    # documented `--browser` command died on WinError 2 before it ran a check.
    command = [
        shutil.which("npx") or "npx",
        "--yes",
        "--package",
        "playwright",
        "node",
        "tests/browser_test.cjs",
    ]
    command += [str(page.relative_to(ROOT)).replace("\\", "/") for page in pages]
    command += sweep
    if not _run(command, "the browser suite"):
        return step.done(False, f"the browser suite failed on {len(pages)} page(s)")
    return step.done(True, f"{len(pages)} page(s)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="the unit suites minus the feed-scale tests")
    parser.add_argument("--full", action="store_true", help="every unit test")
    parser.add_argument("--browser", action="store_true", help="the demo and shape builds, then the browser suite")
    parser.add_argument("--all", action="store_true", help="--full, then --browser")
    args = parser.parse_args(argv)
    if not (args.fast or args.full or args.browser or args.all):
        parser.print_help()
        return 2
    os.chdir(ROOT)

    steps: list[Step] = []
    if args.fast or args.full or args.all:
        steps.append(unit(fast=args.fast and not (args.full or args.all)))
        steps.append(javascript())
    if args.browser or args.all:
        steps.append(browser())
    for step in steps:
        print(step.line(), flush=True)
    if any(step.ok is None for step in steps):
        print("a step could not run, so nothing here says the change is good", flush=True)
        return 2
    if not all(step.ok for step in steps):
        return 1
    print("all steps passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
