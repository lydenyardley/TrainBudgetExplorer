"""Run the app locally: build the site fresh, serve it, open the browser.

    python run.py

Every run rebuilds from the current fares feed so the pages are never stale, then
serves the whole site on http://localhost:8741 and opens it. The default is a
fast single-origin page; use --with-timetable to opt into the large national
timetable feed, or pass --all-origins for every priced station (slow).

Other useful forms:

    python run.py --port 9000        different port
    python run.py --no-build         serve the existing _site/ untouched
    python run.py --feed feeds/fares  real fares, prices-only
    python run.py --with-timetable   include the large national timetable
    python run.py --with-single-timetable
                                     include the separate single-mode timetable cache
    python run.py --all-origins      one page per priced station

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
from build_demo_page import RELEASE_MANIFEST_NAME  # noqa: E402


def _feed_exists(path: Path) -> bool:
    """Accept either an extracted feed directory or a downloaded ZIP."""
    return path.is_file() and path.suffix.lower() == ".zip" or (
        path.is_dir() and any(path.iterdir())
    )


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
        cmd += ["--all-origins"]
    if args.base_path:
        cmd += ["--base-path", args.base_path]

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
    parser.add_argument("--no-build", action="store_true", help="serve _site/ as it is, without rebuilding")
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

    if args.all_origins and not args.i_know_this_is_slow:
        # Guard the default path: `python run.py` must never silently start a
        # hours-or-days build. The escape is one flag away (audit D1).
        print("--all-origins builds one page per priced station, which at network "
              "scale is a batch job measured in days (ADR-0024). Pass "
              "--i-know-this-is-slow to run it anyway, or drop --all-origins for "
              "the fast single-origin demo.", file=sys.stderr)
        return 2

    if not args.no_build:
        rc = build(args)
        if rc != 0:
            return rc
    elif not SITE.exists():
        print("No _site/ to serve -- drop --no-build or run a build first.", file=sys.stderr)
        return 1

    os.chdir(SITE)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt, *log_args):  # keep the terminal for the build, not request spam
            pass

    # Threaded: one reader, but browsers open parallel connections for
    # sub-resources and a second tab must not stall the first (audit B4).
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), Quiet) as httpd:
        url = f"http://localhost:{args.port}/"
        print(f"Serving {SITE.name} at {url}  (Ctrl+C to stop)")
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
