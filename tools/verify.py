"""The checks a change has to pass, in one command, on any platform.

An agent's cheapest loop in this repository was `python -m unittest
tests.<module>`, one file at a time: the page's tests take 156 s and the fares
parser's 200 s, and neither command runs the page's JavaScript. The suite that
does execute that JavaScript ran only in CI, after a feed download and a site
build, in a step of a hundred lines of bash inside the workflow, which a Windows
checkout cannot run at all (F5 of the 8 October 2026 agent-efficiency audit).
This is that entry point, written in Python so the same command covers a
developer's machine and the release.

    python -m tools.verify --fast      the page, payload and chooser modules, the page's JavaScript parsed as files and as each route's script, and actionlint over the workflows
    python -m tools.verify --full      every unit test, the type check, and the same two parses
    python -m tools.verify --browser   a synthetic feed, the demo and shape builds, then the browser suite
    python -m tools.verify --all       --full, then --browser

`--browser --require-site` is the release's own browser step: the site at
`_site` must be there, with its privacy page, or the run fails rather than
driving the demo pages alone.

`--browser` drives the pages CI drives, built from the synthetic feed with the
same commands, and adds the pages a built site already has at `_site` when they
are there. It needs Playwright's chromium and downloads nothing itself.

Exit codes: 0 every step ran and passed, 1 a step ran and failed, 2 a step could
not run (node, Playwright or actionlint missing, a build that wrote no page).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Callable, Sequence
from pathlib import Path

from trainbudget.build import page_templates

ROOT = Path(__file__).resolve().parents[1]

#: What `--fast` runs: the modules that hold the page, the payload it is built
#: from, the chooser, and the checks that speak for the build. `--full` runs
#: every module, including the feed-scale ones that read the licensed national
#: download. Until this list existed, `--fast` was every test minus two, which is
#: 1,137 tests in 21 minutes -- not a loop a change can be checked with while it
#: is being written (A5 of the 20 October 2026 poteto audit).
FAST_MODULES = (
    "tests.test_build_demo_page",
    "tests.test_build_fares",
    "tests.test_build_chooser",
    "tests.test_build_provenance",
    "tests.test_build_links",
    "tests.test_page_assets",
    "tests.test_workflows",
    "tests.test_test_suite_shape",
    "tools.test_verify",
    "tools.test_release",
    "tools.test_commit_hook",
    # The release's own fare gate, which is what stands between a wrong price and
    # a reader. It runs here because it did not: its rows priced a place ADR-0076
    # stopped listing, they went red on 24 October 2026, and nothing ran them
    # until the release did. It costs 25-32 s rather than the 3 s of a read site,
    # because a row's absence means what the page left out, and that is three
    # builds of the synthetic site: with the week, capped, and fares only
    # (measured 25 October 2026).
    "tools.test_check_known_fares",
)

#: The wall clock `--fast`'s unit step may take before the command fails naming
#: it. This is the five minutes A5 of the 20 October 2026 audit asked for, and
#: `tools/test_verify.py` holds it there; headroom for a slower machine rather
#: than a target, and a module added to the list is the usual thing that breaks
#: it. How much is left depends on the machine as much as on the suite: the same
#: 300 tests took 72.6, 80.2 and 93.9 s on 24 October 2026, before the fare gate
#: built its fixture three ways, and 137, 158, 180 and 182 s on 25 October once
#: it did. The gate is about 25 s of that and the rest is the desktop. At the
#: slowest run this leaves about two minutes, which is one more fixture-building
#: module and no more; a trip with nothing added means the machine, so measure
#: again before raising the number.
FAST_CEILING = 300.0

#: The page's own JavaScript, which no Python check can parse (audit C2). The
#: station route is one file per panel under a subdirectory, so the pattern has
#: to reach below the first level or the panels stop being checked.
JAVASCRIPT = "page/**/*.js"

#: The one file that names the browser the suite launches. CI installs that
#: version, this command asks npx for it, and `tests/test_workflows.py` fails
#: when either path names another. Before this, CI pinned 1.63.0 while a local
#: run took whatever `npx --package playwright` resolved to that day, so a green
#: run here was not the same command as a green run there (A7 of the 20 October
#: 2026 poteto audit).
PLAYWRIGHT_VERSION = Path("tests/browser/playwright-version")


def playwright_package() -> str:
    """`playwright@<the pinned version>`, as npx and the workflow both ask for it."""
    version = (ROOT / PLAYWRIGHT_VERSION).read_text(encoding="utf-8").strip()
    return f"playwright@{version}"

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


def unit(fast: bool) -> Step:
    step = Step("unit tests" + (" (fast)" if fast else ""))
    if fast:
        suite = unittest.TestLoader().loadTestsFromNames(FAST_MODULES)
    else:
        suite = _discover("tests")
        suite.addTest(_discover("tools"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    ran = result.testsRun
    detail = f"{ran:,} tests"
    if not result.wasSuccessful():
        failed = len(result.failures) + len(result.errors)
        detail = f"{ran:,} tests, {failed} failing"
    if fast and step.seconds > FAST_CEILING:
        return step.done(
            False,
            f"{detail} in {step.seconds:.0f}s, over the {FAST_CEILING:.0f}s ceiling for "
            "--fast: move a module to --full, or fix what got slower",
        )
    return step.done(result.wasSuccessful(), detail)


def _parse(node: str, source: str, scratch: Path) -> subprocess.CompletedProcess[str]:
    """`node --check` over a string, through a file, because that is what it reads."""
    path = scratch / "route.js"
    path.write_text(source, encoding="utf-8")
    return subprocess.run([node, "--check", str(path)], capture_output=True, text=True, cwd=ROOT)


def first_unparsed(
    parts: Sequence[str], build: Callable[[tuple[str, ...]], str], parses: Callable[[str], bool]
) -> str:
    """The first part whose addition stops a route's concatenated script parsing.

    A panel is parsed on its own and the artifact is not: two panels may each
    declare `const total`, and that is a SyntaxError where neither file is one.
    Parsing the prefixes names the panel that broke the artifact instead of
    reporting that "the script" does not parse (A4 of the 20 October 2026
    poteto audit). An empty answer means every prefix parses, which is the
    caller's cue that nothing shorter than the whole artifact is at fault.
    """
    for index, part in enumerate(parts, 1):
        if not parses(build(tuple(parts[:index]))):
            return part
    return ""


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

    # The station route ships one script built from STATION_SCRIPT_PARTS, so the
    # concatenation is what a reader's browser parses and no per-file check can
    # see a name two panels both declare. The artifact is checked as one string
    # here, and a failure names the panel whose addition broke it.
    with tempfile.TemporaryDirectory() as scratch:
        route = Path(scratch)

        def parses(source: str) -> bool:
            return _parse(node, source, route).returncode == 0

        artifact = page_templates.STATION_SCRIPT
        if not parses(artifact):
            print(_parse(node, artifact, route).stderr.strip(), file=sys.stderr)
            offender = first_unparsed(
                page_templates.STATION_SCRIPT_PARTS, page_templates.station_script, parses
            )
            return step.done(
                False,
                f"the station route's script does not parse: "
                + (f"{offender} is the panel that breaks it" if offender else "the whole artifact is at fault"),
            )
        if not parses(page_templates.CHOOSER_SCRIPT):
            print(_parse(node, page_templates.CHOOSER_SCRIPT, route).stderr.strip(), file=sys.stderr)
            return step.done(False, "the chooser route's script does not parse")
    return step.done(True, f"{len(files)} file(s) and 2 route artifacts")


def workflows() -> Step:
    """actionlint over `.github/`, so a YAML or expression error fails on the desk.

    A workflow mistake used to cost a push and a run to find (task 1 of the 21
    October 2026 re-architecture audit). It is a binary rather than a Python
    module, so a machine without it reports `not run` and the run exits 2.
    """
    step = Step("workflows lint")
    actionlint = shutil.which("actionlint")
    if actionlint is None:
        return step.done(None, "actionlint is not on PATH: python -m pip install actionlint-py")
    result = subprocess.run([actionlint], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        print((result.stdout + result.stderr).strip(), file=sys.stderr)
        return step.done(False, "actionlint found a workflow error")
    return step.done(True, f"{len(list((ROOT / '.github' / 'workflows').glob('*.yml')))} workflow(s)")


def types() -> Step:
    """The type-check ratchet (item 4 of the 14 October 2026 engineering audit).

    Run with `--full` and not with `--fast`: it needs mypy installed, and a
    developer's fast loop should not stop on a dependency they have not
    installed. CI installs it for the full run and for the check itself.
    """
    step = Step("types")
    result = subprocess.run(
        [sys.executable, "-m", "tools.check_types"], cwd=ROOT, capture_output=True, text=True
    )
    detail = (result.stdout + result.stderr).strip().splitlines()
    if result.returncode == 2:
        return step.done(None, detail[-1] if detail else "mypy is not installed")
    return step.done(result.returncode == 0, detail[-1] if detail else "")


def page_state() -> Step:
    """The page-state read ratchet (R5 of the 18 October 2026 plan).

    In `--full` only, beside the type ratchet: it reads the page's sources and
    needs nothing installed, but it is a size over sixteen files rather than a
    check of one, so it is not in the fast loop.
    """
    step = Step("page state")
    result = subprocess.run(
        [sys.executable, "-m", "tools.check_page_state"], cwd=ROOT, capture_output=True, text=True
    )
    detail = (result.stdout + result.stderr).strip().splitlines()
    if result.returncode == 2:
        return step.done(None, detail[-1] if detail else "no page to read")
    return step.done(result.returncode == 0, detail[-1] if detail else "")


def _run(command: list[str], what: str) -> bool:
    print(f"  $ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        print(f"  {what} exited {result.returncode}", file=sys.stderr)
    return result.returncode == 0


# The browser suite's own last word on a run, which harness.cjs prints once:
# "1 of 31 page(s) failed: ..." or "5 of 5 page(s) checked, ...".
SUITE_SUMMARY = re.compile(r"^(\d+) of (\d+) page\(s\) (failed|checked)\b")


def suite_verdict(ok: bool, lines: Sequence[str], targets: int) -> str:
    """What the browser step reports, in the suite's own page counts.

    The suite is handed page files and directories it sweeps, so the number of
    arguments is not the number of pages: run 39772120392 gave it 8 targets,
    the suite drove 31 pages and one failed, and the step said it "failed on 8
    page(s)". The suite counts its pages and says which failed, so the step
    repeats that rather than counting something else.
    """
    found = None
    for line in lines:
        match = SUITE_SUMMARY.match(line.strip())
        if match:
            found = match
    if found is None:
        if ok:
            return f"{targets} page target(s), and the suite printed no summary"
        return f"the browser suite failed before it summarised its pages ({targets} page target(s))"
    count, total, verb = int(found.group(1)), int(found.group(2)), found.group(3)
    if ok:
        return f"{total} page(s)"
    if verb == "failed":
        return f"the browser suite failed on {count} of {total} page(s)"
    return f"the browser suite failed after checking {count} of {total} page(s)"


def _run_suite(command: list[str]) -> tuple[bool, list[str]]:
    """Run the suite with its output shown as it runs and kept for the verdict."""
    print(f"  $ {' '.join(command)}", flush=True)
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        sys.stdout.write(line)
        lines.append(line)
    code = process.wait()
    if code:
        print(f"  the browser suite exited {code}", file=sys.stderr)
    return code == 0, lines


def browser(require_site: bool = False) -> Step:
    """The pages the browser suite drives, built here, then the suite itself."""
    step = Step("browser suite")
    if shutil.which("node") is None:
        return step.done(None, "node is not on PATH")
    if not (ROOT / PLAYWRIGHT_VERSION).is_file():
        return step.done(None, f"{PLAYWRIGHT_VERSION} names no browser version")
    # Every page the suite drives has to be written by this run. A build that
    # writes no page used to leave the folder as it found it, so the suite drove
    # yesterday's page -- and, on 24 October 2026, a script this tree no longer
    # writes: the reviewed-name shape priced nothing once a place no journey
    # reaches stopped being listed (ADR-0076), and its checks kept passing
    # against the stale page. Cleared here, so that inner check fails instead.
    for folder in (DEMO_SITE, SHAPE_SITE):
        shutil.rmtree(Path(ROOT, folder), ignore_errors=True)
    steps = [
        # --long-list is what gives the driven station page a second page: the
        # table shows twenty rows before it offers a pager, so a fixture whose
        # every origin prices fewer cannot exercise page two or the n/p keys.
        (["python", "-m", "trainbudget.feeds.make_synthetic_feed", DEMO_FEED, "--unserved-station", "--third-origin", "--return-network", "--long-list", "--knowledgebase", DEMO_KB], "the demo feed"),
        (["python", "-m", "trainbudget.build.build_demo_page", "--feed", DEMO_FEED, "--timetable", DEMO_FEED, "--knowledgebase", DEMO_KB, "--all-origins", "--date", SERVICE_DATE, "--out", f"{DEMO_SITE}/index.html"], "the demo site"),
        # --third-origin and --return-network for the same reason the demo feed
        # takes them: without them this feed's secondary origins are priced to
        # one station each, and a page with one row cannot exercise its own
        # controls -- no shortlist of two, no second destination type, no
        # heritage row, nothing for the dock to hold. The shape this build is
        # for is the list that fits on one page (ADR-0058); the number of rows
        # was never the point, and the six to eight the feed now prices against
        # each origin still fit.
        # --reviewed-origin adds fares from London Kings Cross for the
        # reviewed-name page below, and nothing to the pages built before it.
        (["python", "-m", "trainbudget.feeds.make_synthetic_feed", SHAPE_FEED, "--unserved-station", "--third-origin", "--return-network", "--reviewed-origin"], "the shape feed"),
        # No --timetable, so the page prices fares only, and no --date for the
        # same reason: a build with no times has no day to report, and a page
        # carrying a date it cannot report times for would be claiming one.
        (["python", "-m", "trainbudget.build.build_demo_page", "--feed", SHAPE_FEED, "--origin", "GRN", "--out", f"{SHAPE_SITE}/prices-only/index.html"], "the prices-only page"),
        (["python", "-m", "trainbudget.build.build_demo_page", "--feed", SHAPE_FEED, "--timetable", SHAPE_FEED, "--all-origins", "--date", SERVICE_DATE, "--out", f"{SHAPE_SITE}/one-page/index.html"], "the one-page shape"),
        # Two shapes no other fixture page has, both found by the deploy sweep
        # of run 39818671598 rather than by this suite: an origin whose name
        # is the reviewed "London Kings Cross" rather than the feed's
        # upper-case CIF name (Harwich International's heading), and a page
        # whose card-priced rows all cost more for two than the one-adult
        # ceiling the page opens on (Farnborough (Main)'s railcard note). With
        # the timetable, because a prices-only page skips the times half of
        # the suite and its skips count against the budget for pages like it.
        (["python", "-m", "trainbudget.build.build_demo_page", "--feed", SHAPE_FEED, "--timetable", SHAPE_FEED, "--date", SERVICE_DATE, "--origin", "KGX", "--out", f"{SHAPE_SITE}/reviewed-name/index.html"], "the reviewed-name page"),
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
        Path(ROOT, SHAPE_SITE, "reviewed-name/from/london-kings-x/index.html"),
    ]
    missing = [page for page in pages if not page.is_file() or not page.stat().st_size]
    if missing:
        return step.done(False, "a build wrote no page at " + ", ".join(str(page) for page in missing))

    # The site the release would publish, when it is on disk: CI drives it, and a
    # local run that has just built one should drive it too.
    sweep: list[str] = []
    site_pages = [Path(ROOT, SITE, "index.html"), Path(ROOT, SITE, "privacy/index.html")]
    if require_site or site_pages[0].is_file():
        missing = [page for page in site_pages if not page.is_file() or not page.stat().st_size]
        if missing:
            return step.done(False, "the site that ships has no page at " + ", ".join(str(page) for page in missing))
        pages += site_pages
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
        playwright_package(),
        "node",
        "tests/browser_test.cjs",
    ]
    command += [str(page.relative_to(ROOT)).replace("\\", "/") for page in pages]
    command += sweep
    ok, lines = _run_suite(command)
    return step.done(ok, suite_verdict(ok, lines, len(pages)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="the page, payload and chooser modules, under a five-minute ceiling")
    parser.add_argument("--full", action="store_true", help="every unit test, and the type check")
    parser.add_argument("--browser", action="store_true", help="the demo and shape builds, then the browser suite")
    parser.add_argument("--all", action="store_true", help="--full, then --browser")
    parser.add_argument("--require-site", action="store_true", help="with --browser: fail when _site holds no page to drive")
    args = parser.parse_args(argv)
    if not (args.fast or args.full or args.browser or args.all):
        parser.print_help()
        return 2
    os.chdir(ROOT)

    steps: list[Step] = []
    if args.fast or args.full or args.all:
        steps.append(unit(fast=args.fast and not (args.full or args.all)))
        steps.append(javascript())
        steps.append(workflows())
        if not (args.fast and not (args.full or args.all)):
            steps.append(types())
            steps.append(page_state())
    if args.browser or args.all:
        steps.append(browser(require_site=args.require_site))
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
