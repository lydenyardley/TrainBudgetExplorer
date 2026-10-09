"""Run the app locally: build the site fresh, serve it, open the browser.

    python run.py

This serves what the last build wrote, on http://localhost:8741, and opens it. It
does not rebuild: a server that rebuilds on every start cannot say what it is
serving. On a clean checkout there is nothing to serve, so it builds once first.
The default build is a fast single-origin page; use --with-timetable to opt into
the large national timetable feed, or pass --all-origins for every priced station
(slow).

Other useful forms:

    python run.py --port 9000        different port
    python run.py --no-build         serve the existing _site/ untouched
    python run.py --feed feeds/fares  real fares, prices-only
    python run.py --with-timetable   include the large national timetable
    python run.py --with-single-timetable
                                     include the separate single-mode timetable cache
    python run.py --all-origins      one page per priced station

A build from the real fares feed is a public build, so it carries the licence
notices and somebody to contact, and the runner passes both without being asked:
a real feed gets every notice the builder knows, and the builder names the public issue tracker as the contact,
and --notices is there to *narrow* that, not to grant it. A page you previewed
without the notices is not the page that ships, and the builder refuses to build
one anyway, so `python run.py` used to fail outright once the feeds were
downloaded:

    python run.py --notices nre,ogl              a narrower set, if you know why
    python run.py --privacy-contact privacy@example.org

The server runs until you press Ctrl+C. Nothing is installed and nothing
outside this folder is touched.
"""

import argparse
from datetime import date
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
SITE = ROOT / "_site"
PORT_DEFAULT = 8741
# Written by the build beside the pages, naming the routes this release
# serves. Imported rather than repeated so the tidying step below and the
# build that precedes it cannot name the file differently. The path insert is
# for the "import run" case (a test), where the project root is not otherwise
# importable; running this file as a script already has it.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from build_demo_page import NOTICES, RELEASE_MANIFEST_NAME  # noqa: E402
from build_workers import free_memory_bytes, worker_budget  # noqa: E402


def _feed_exists(path: Path) -> bool:
    """Accept either an extracted feed directory or a downloaded ZIP."""
    return path.is_file() and path.suffix.lower() == ".zip" or (
        path.is_dir() and any(path.iterdir())
    )


def _is_synthetic(path: Path) -> bool:
    """Is this the project's own invented fares rather than a downloaded one?

    Resolved before comparing, because the same folder arrives as ``_demo_feed``
    on the command line and as an absolute path from the default, and the two
    must not take different sides of the question below. The answer decides
    whether the page credits NRE for prices NRE did not supply, which is false
    attribution rather than a missing one.
    """
    try:
        return path.resolve() == (ROOT / "_demo_feed").resolve()
    except OSError:
        return False


def build(args: argparse.Namespace) -> int:
    """Run the page build into _site/. Returns the exit code."""
    if not _feed_exists(args.feed):
        print(f"No feed at {args.feed} -- run `python make_synthetic_feed.py _demo_feed` "
              f"or download the real feeds with `python dtd_download.py`.", file=sys.stderr)
        return 1

    origin = args.origin
    if origin is None:
        origin = "GRA" if args.feed != ROOT / "_demo_feed" else "GRN"
    cmd = [sys.executable, "build_demo_page.py",
           "--feed", str(args.feed),
           "--origin", origin,
           "--out", "_site/index.html"]
    if args.timetable is not None:
        cmd += ["--timetable", str(args.timetable)]
    if args.with_single_timetable:
        cmd += ["--with-single-timetable"]
    # A date-specific timetable index is dramatically smaller than indexing
    # every schedule in the national feed. It also makes the default page mean
    # "today" rather than an unfiltered mixture of permanent and overlay plans.
    cmd += ["--date", args.date or date.today().isoformat()]
    if args.all_origins:
        # Each origin's page is independent and the work is CPU-bound, so the
        # worker count would be the core count if cores were the only thing
        # that mattered. They are not: every worker is handed the whole
        # national timetable, and min(8, cpu_count()) -- eight, here -- dies
        # with a MemoryError in the pool initialiser after five minutes,
        # reproducibly, having written no pages. The budget measures what a
        # worker costs and asks the machine what it has, and caps the answer at
        # the largest count measured to finish.
        #
        # Measured here, real feed, four workers: the feeds load in 145s, the
        # pool takes a further 83s, and the 2,712 pages then take 121 minutes at
        # 0.37 pages/s -- about two hours from a cold start. The first 239 pages
        # arrive at 0.77 pages/s, because the builder works through the origin
        # list and the early ones are priced for a handful of destinations; a
        # stopwatch over those is not a stopwatch over the work. One worker is
        # 2,712 / 0.093 -- most of a working day.
        # The free-memory figure is read once and named, because the count it
        # produces is the number a reader would ask about and "1 worker" on its
        # own does not say whether that was a choice or a shortage.
        free = free_memory_bytes()
        workers = worker_budget(free_bytes=free)
        print(f"Building the whole network on {workers} worker(s)"
              + (f", with {free / 1e9:.1f} GB free." if free is not None else "."))
        cmd += ["--all-origins", "--workers", str(workers)]
    if args.base_path:
        cmd += ["--base-path", args.base_path]
    # A real feed is a public build, and the builder refuses one that carries no
    # licence notice and no way to be told about a problem with the page. The
    # contact now defaults in the builder to the public issue tracker, so
    # --privacy-contact is for pointing the page somewhere else.
    #
    # The notices used to have to be passed by hand, and that was a lie about
    # the entry point: main() swaps the default feed for the downloaded one the
    # moment it exists, so `python run.py` produced a public build the runner
    # then refused to pass the notices for. The build died with "this build
    # cannot be published as configured" on the documented double-click path.
    # So a real feed carries every notice by default, read from the builder's
    # own table rather than repeated here: adding a notice there cannot leave
    # this list behind. --notices still wins, and it wins exactly, which is the
    # direction that matters -- a person can narrow what the page claims, never
    # widen it past what the builder offers. The default therefore applies only
    # when the flag is absent: `--notices ""` asks for no notice at all and is
    # handed on as such, so the builder's refusal is what answers it rather than
    # this line quietly supplying the set the person just declined.
    notices = args.notices
    if notices is None and not _is_synthetic(args.feed):
        notices = ",".join(NOTICES)
    if notices:
        cmd += ["--notices", notices]
    if args.privacy_contact:
        cmd += ["--privacy-contact", args.privacy_contact]

    print("Building the site ...")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode == 0 and not args.all_origins:
        remove_unwritten_station_pages()
    return result.returncode


def remove_unwritten_station_pages() -> list[str]:
    """Delete the station page folders this build did not write.

    A single-origin build is a site too, so it writes its one station at
    /from/<slug>/ beside the chooser, and that page must survive to be served.
    What genuinely needs removing is the *other* station folders: a previous
    --all-origins run leaves a browsable /from/<origin>/ tree, and serving one
    of those pages under a chooser that does not offer it is the same
    contract the build's own link crawl refuses to publish.

    The set of folders to keep is read from the release manifest the build
    just wrote, rather than guessed, so this cannot disagree with the release
    it is tidying. An unreadable or absent manifest removes nothing: the worst
    case is a stale folder left on disk, which the build already names in its
    output, and deleting pages on a guess is the worse failure.
    """
    import shutil

    from_dir = SITE / "from"
    if not from_dir.is_dir():
        return []
    manifest_path = SITE / RELEASE_MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"note: {manifest_path.name} is not there, so no station page folder was removed.")
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"note: {manifest_path.name} could not be read, so no station page folder was removed.")
        return []
    # A manifest this function cannot read the way the builder writes one is
    # treated the same as an unreadable one: remove nothing. Iterating a string
    # where a list of routes belongs, or asking a list for "routes", would both
    # leave the keep-set empty, and an empty keep-set means deleting every
    # station folder including the one the build just wrote.
    if not isinstance(manifest, dict):
        print(f"note: {manifest_path.name} is not a release manifest, so no station page folder was removed.")
        return []
    routes = manifest.get("routes")
    if not isinstance(routes, list):
        print(f"note: {manifest_path.name} names no route list, so no station page folder was removed.")
        return []
    # A build served from a subpath writes its routes prefixed with that path,
    # so the prefix has to come off before the station segment is read. Taking
    # it from the manifest rather than from argv keeps this correct for
    # --base-path without run.py having to agree with the builder about it:
    # reading "/app/from/grantham/" as a station route without stripping "/app"
    # would match nothing and delete the page the build just wrote.
    base_path = manifest.get("basePath") or ""
    if not isinstance(base_path, str):
        base_path = ""
    prefix = "/" + base_path.strip("/") + "/" if base_path.strip("/") else "/"
    station_prefix = prefix + "from/"
    written = {
        segment
        for route in routes
        if isinstance(route, str) and route.startswith(station_prefix) and route.endswith("/")
        for segment in [route[len(station_prefix):-1]]
        if "/" not in segment
    }
    removed: list[str] = []
    for child in sorted(from_dir.iterdir()):
        if not child.is_dir() or child.name in written:
            continue
        shutil.rmtree(child, ignore_errors=True)
        removed.append(child.name)
    if removed:
        print(f"removed {len(removed)} station page folder(s) this build did not write: {', '.join(removed)}")
    return removed


# The files whose mtime decides whether _site/ is out of date. A build is a
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


def serve(site: Path, port: int, *, open_browser: bool = True) -> int:
    """Serve `site` on 127.0.0.1:`port` until Ctrl+C.

    A function rather than a block inside `main()` because two entry points now
    need it and neither should own a second copy of a local HTTP server: the
    runner serves `_site/`, and `build_stations.py` serves a subset build. The
    handler is defined in here for the same reason -- the quiet one is this
    project's server, and the only one a reader's browser should meet.

    Returns a process exit code, so a caller can `return serve(...)`.
    """

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt, *log_args):  # keep the terminal for the build, not request spam
            pass

    # Threaded: one reader, but browsers open parallel connections for
    # sub-resources and a second tab must not stall the first (audit B4).
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    where_we_were = Path.cwd()
    os.chdir(site)
    try:
        with socketserver.ThreadingTCPServer(("127.0.0.1", port), Quiet) as httpd:
            url = f"http://localhost:{port}/"
            print(f"Serving {site.name} at {url}  (Ctrl+C to stop)")
            if open_browser:
                threading.Timer(0.8, webbrowser.open, args=(url,)).start()
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nStopped.")
    finally:
        os.chdir(where_we_were)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the site and serve it at http://localhost:<port>")
    parser.add_argument("--port", type=int, default=PORT_DEFAULT)
    parser.add_argument("--feed", type=Path, default=ROOT / "_demo_feed")
    parser.add_argument("--timetable", type=Path, nargs="?", default=None,
                        const=None,
                        help="optional timetable feed folder; omit it for a fast prices-only build")
    parser.add_argument("--with-timetable", action="store_true",
                        help="use the downloaded national timetable when available (slow)")
    parser.add_argument("--with-single-timetable", action="store_true",
                        help="also load the separate outbound-single timetable cache")
    parser.add_argument("--all-origins", action="store_true",
                        help="one page per priced station (slow at network scale)")
    parser.add_argument("--i-know-this-is-slow", action="store_true",
                        help="required with --all-origins: at network scale the "
                        "build is a batch job measured in days (ADR-0024)")
    parser.add_argument("--base-path", default=None,
                        help="path prefix if the site will not sit at the domain root")
    parser.add_argument("--notices", default=None,
                        help="which licence and attribution notices to carry; a real-feed "
                             "build takes all of them by default, and this narrows the set")
    parser.add_argument("--privacy-contact", default=None,
                        help="who to contact about a problem with the page; overrides "
                             "the issue-tracker route in build_demo_page.py")
    parser.add_argument("--rebuild", action="store_true",
                        help="build _site/ again before serving it (the default builds only when there is nothing to serve)")
    parser.add_argument("--no-build", action="store_true",
                        help="serve _site/ as it is and fail if it is not there")
    parser.add_argument("--origin", default=None, help="origin CRS code; defaults to GRA for real feeds and GRN for the demo")
    parser.add_argument("--date", default=None, help="timetable service date as YYYY-MM-DD; defaults to today")
    args = parser.parse_args()
    # Use downloaded fares automatically, but do not silently load the much
    # larger timetable feed: a real feed is never relabelled as demo data.
    if args.feed == ROOT / "_demo_feed" and (ROOT / "feeds" / "fares").exists():
        args.feed = ROOT / "feeds" / "fares"

    # The national timetable is a multi-million-record feed. Loading it is an
    # explicit opt-in: the double-click path stays fast and useful with real
    # fares, while --with-timetable opts into journey times.
    if (args.with_timetable or args.with_single_timetable) and args.timetable is None:
        real_timetable = ROOT / "feeds" / "timetable"
        args.timetable = real_timetable if real_timetable.exists() else ROOT / "_demo_feed"

    # Resolve the timetable default by existence rather than clever argparse:
    # a missing demo timetable folder means a prices-only build, which is honest.
    if args.timetable is not None and not args.timetable.exists():
        args.timetable = None

    # The default is now the whole network, and this says what that costs
    # before it starts rather than after it has finished. Measured on the real
    # feed with the national timetable, 2 October 2026, on this machine, by a
    # whole-network build rather than by a stopwatch over its first minutes:
    # 2,712 priced stations in 121 minutes of page building at 0.093 pages/s
    # per worker, so about two hours from a cold start on the four workers the
    # budget below chooses, and most of a working day on one.
    #
    # The figure this replaces was itself wrong twice over -- "20 minutes on
    # eight cores" came from a feed without the national timetable, and the 63
    # minutes that followed came from the first nine minutes of a build, which
    # are the cheapest stations in the set. A rate taken from the first tenth of
    # the work is not a rate for the work. Both are withdrawn rather than
    # qualified (ADR-0024, ADR-0050, ADR-0055, ADR-0057). The fast
    # single-origin page is still one flag away, because a build of one station
    # is the right tool for working on one station and the wrong thing to
    # double-click.
    if not args.all_origins and args.origin is None and not args.no_build:
        args.all_origins = True
        args.i_know_this_is_slow = True
        print("Building one page per priced station. This is a one-off: the "
              "next `python run.py` serves what this writes and starts "
              "immediately. Pass --origin GRA for the fast single-station "
              "page instead.")

    # The build and the serve are separate decisions. A runner that rebuilds
    # every time cannot answer "is this the build I made?", and a stale
    # answer to that question is how a page gets reviewed against yesterday's
    # fares. So it builds when there is nothing to serve, serves what is there
    # otherwise, and says which of the two it did.
    if args.no_build:
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
              " build again first.")

    return serve(SITE, args.port)


if __name__ == "__main__":
    sys.exit(main())
