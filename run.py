"""Run the app locally: build the site fresh, serve it, open the browser.

    python run.py

Every run rebuilds from the current feed so the pages are never stale, then
serves the whole site on http://localhost:8741 and opens it. The build is the
single-origin demo page set plus the chooser; pass --all-origins for every
priced station (slow on a network-sized feed, see ADR-0024).

Other useful forms:

    python run.py --port 9000        different port
    python run.py --no-build         serve the existing _site/ untouched
    python run.py --feed feeds/fares --timetable feeds/timetable
                                     real licensed feeds instead of the demo
    python run.py --all-origins      one page per priced station

The server runs until you press Ctrl+C. Nothing is installed and nothing
outside this folder is touched.
"""

import argparse
import http.server
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


def build(args: argparse.Namespace) -> int:
    """Run the page build into _site/. Returns the exit code."""
    if not (args.feed / "stations.msn").exists():
        print(f"No feed at {args.feed} -- run `python make_synthetic_feed.py _demo_feed` "
              f"or point --feed at a real one.", file=sys.stderr)
        return 1

    cmd = [sys.executable, "build_demo_page.py",
           "--feed", str(args.feed),
           "--out", "_site/index.html"]
    if args.timetable is not None:
        cmd += ["--timetable", str(args.timetable)]
    if args.all_origins:
        cmd += ["--all-origins"]
    if args.base_path:
        cmd += ["--base-path", args.base_path]

    print("Building the site ...")
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the site and serve it at http://localhost:<port>")
    parser.add_argument("--port", type=int, default=PORT_DEFAULT)
    parser.add_argument("--feed", type=Path, default=ROOT / "_demo_feed")
    parser.add_argument("--timetable", type=Path, nargs="?", default=ROOT / "_demo_feed",
                        const=None,
                        help="timetable feed folder; --timetable with no value skips it")
    parser.add_argument("--all-origins", action="store_true",
                        help="one page per priced station (slow at network scale)")
    parser.add_argument("--i-know-this-is-slow", action="store_true",
                        help="required with --all-origins: at network scale the "
                        "build is a batch job measured in days (ADR-0024)")
    parser.add_argument("--base-path", default=None,
                        help="path prefix if the site will not sit at the domain root")
    parser.add_argument("--no-build", action="store_true",
                        help="serve _site/ as it is, without rebuilding")
    args = parser.parse_args()

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
