"""C8: the double-click path builds the thing the product is.

`python run.py` built one station's page, which is honest about itself and
useless for the thing a reader does first -- change station. The heading's
station name was plain text on that build, not because the control was broken
but because there was nowhere for it to go, and the railcard control was a
single card because the synthetic fixture prices one.

Two changes, and the second is the one that matters most:

* the default is the whole network, so every station the feed prices has a
  page and the station name in the heading is the control it was always drawn
  to be. The build is a one-off; every later run serves it.
* a build that is older than the sources is rebuilt rather than served. The
  runner's rule was that it never rebuilds on start, because a server that
  rebuilds every time cannot say what it is serving (ADR-0051). That still
  holds: it rebuilds only when what it would serve is out of date, and it says
  which of the two it did. The alternative is what actually happened -- nine
  hours of committed work, a double-clicked runner, and a page from before it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patch as patcher  # noqa: E402

OLD_GUARD = '''    if args.all_origins and not args.i_know_this_is_slow:
        # Guard the default path: `python run.py` must never silently start a
        # build that takes the machine for an hour and a half. Measured on the
        # real feed: 2,718 priced stations, and at roughly 0.28 pages/s per
        # worker an eight-core machine finishes in about 20 minutes while a
        # two-core one takes about 81. ADR-0024 projected days from an invented
        # uniform feed and the real network is far kinder than that shape; the
        # number here is the measured one. The escape is still one flag away
        # (audit D1), because asking for it should be a decision.
        print("--all-origins builds one page per priced station: 2,718 pages "
              "against the real feed, measured at about 81 minutes on two cores "
              "(ADR-0024, re-measured 1 October 2026; ADR-0050). Pass "
              "--i-know-this-is-slow to run it anyway, or drop "
              "--all-origins for the fast single-origin demo.", file=sys.stderr)
        return 2

'''

NEW_GUARD = '''    # The default is now the whole network, and this says what that costs
    # before it starts rather than after it has finished. Measured on the real
    # feed: 2,718 priced stations at roughly 0.28 pages/s per worker, so about
    # 20 minutes on eight cores and 81 on two (ADR-0024, re-measured 1 October
    # 2026; ADR-0050). The fast single-origin page is still one flag away,
    # because a build of one station is the right tool for working on one
    # station and the wrong thing to double-click.
    if not args.all_origins and args.origin is None and not args.no_build:
        args.all_origins = True
        args.i_know_this_is_slow = True
        print("Building one page per priced station. This is a one-off: the "
              "next `python run.py` serves what this writes and starts "
              "immediately. Pass --origin GRA for the fast single-station "
              "page instead.")

'''

OLD_DECISION = '''    if args.no_build:
        if not SITE.exists():
            print("No _site/ to serve and --no-build was given. Run a build first.",
                  file=sys.stderr)
            return 1
        print("Serving the existing _site/ untouched, as asked.")
    elif args.rebuild or not SITE.exists():
        if args.rebuild:
            print("Rebuilding _site/ before serving, as asked.")
        rc = build(args)
        if rc != 0:
            return rc
    else:
        print("Serving the existing _site/ without rebuilding it. Pass --rebuild to"
              " build again first.")'''

NEW_DECISION = '''    if args.no_build:
        if not SITE.exists():
            print("No _site/ to serve and --no-build was given. Run a build first.",
                  file=sys.stderr)
            return 1
        print("Serving the existing _site/ untouched, as asked.")
    elif args.rebuild or not SITE.exists() or sources_are_newer():
        if args.rebuild:
            print("Rebuilding _site/ before serving, as asked.")
        elif not SITE.exists():
            print("There is nothing in _site/ yet, so building it.")
        else:
            # The one case that made this runner quietly wrong. A build written
            # before the last commit is a page from before the last commit, and
            # nothing on the page says so -- which is how a review happens
            # against yesterday's fares, or a railcard fix appears not to work.
            print("The sources are newer than _site/, so rebuilding rather than "
                  "serving a page that is out of date.")
        rc = build(args)
        if rc != 0:
            return rc
    else:
        print("Serving the existing _site/ without rebuilding it. Pass --rebuild to"
              " build again first.")'''

OLD_MAIN_END = '''def main() -> int:'''

NEW_MAIN_END = '''# The files whose mtime decides whether _site/ is out of date. A build is a
# function of the builder and its template, so those two decide it; the modules
# they import decide it too, and a change to the fare maths that never reaches
# the page is still a change to the page's numbers.
BUILD_SOURCES = (
    "build_demo_page.py",
    "page_templates.py",
    "atoc_fares.py",
    "atoc_restrictions.py",
    "atoc_timetable.py",
    "retailer.py",
)


def sources_are_newer() -> bool:
    """Is any source newer than the build this runner is about to serve?

    Compared against the manifest rather than a page, because the manifest is
    written last and is therefore the build's own completion stamp. A manifest
    that is missing or unreadable answers no: an unreadable answer must never
    be the one that starts an hour-long build, and a stale build is fixed by
    --rebuild.
    """
    manifest = SITE / RELEASE_MANIFEST_NAME
    try:
        built = manifest.stat().st_mtime
    except OSError:
        return False
    for name in BUILD_SOURCES:
        source = ROOT / name
        try:
            if source.stat().st_mtime > built:
                return True
        except OSError:
            continue
    return False


def main() -> int:'''

patcher.patch("run.py", [(OLD_GUARD, NEW_GUARD), (OLD_DECISION, NEW_DECISION),
                         (OLD_MAIN_END, NEW_MAIN_END)])
