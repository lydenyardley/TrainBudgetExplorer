"""Build a short list of stations, fully, and serve them.

    python build_stations.py                    # Grantham and Nottingham
    python build_stations.py GRA NOT KGX        # any codes you like
    python build_stations.py --no-serve         # build and stop
    python build_stations.py --date 2026-10-04  # a service date other than today

"Fully" means the same thing the published release is: the downloaded fares
feed, the national timetable, the ticket-restrictions reference feed, every
licence notice and the project's own contact. The pages carry prices and journey
times, or the build says why they are missing. Nothing is dropped to make the
build quick.

**Why this is not two `--origin` runs.** A single-origin build writes its own
chooser at the root and its own release manifest, so the second run replaces the
first one's root and leaves its station page orphaned. `--only-stations` builds a
subset of the whole-network build instead: two stations come out as one site,
with one chooser offering exactly those two and nothing linking to a page that
was not written.

**What it costs.** The two feeds, not the number of stations. The fares feed and
the national timetable load once -- 727,315 flows and 419,589 schedules, 93
seconds measured on this machine when there is room -- and then each station page
costs about ten seconds (ADR-0057). Two stations is a five-minute build when there
is memory for the two feeds. Measured on 7 October 2026 with 5.1 GB free against
the 6.4 GB floor `build_workers.ONE_WORKER_FLOOR` sets, the same two loads took 11
minutes under paging and the build took 63 minutes end to end, writing both pages
where the two earlier runs had written none in 24. That floor is what the script's
memory warning is about, and it is the difference between five minutes and 63. The
whole network is the same command without `--only-stations`, and it is two hours on
four workers or most of a working day on one.

The output goes to `_stations/`, not `_site/`: the runner owns `_site/` and
removes station folders a build did not write, so sharing the folder would have
the two entry points tidy each other's work away.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
SITE = ROOT / "_stations"
PORT_DEFAULT = 8742
DEFAULT_CODES = ("GRA", "NOT")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from build_demo_page import NOTICES  # noqa: E402
# The floor is the measured cost of the feeds plus the reserve, not a guess: a
# machine short of it still builds, on one page at a time, with Windows paging.
# Said before the build starts rather than discovered halfway through it.
from build_workers import ONE_WORKER_FLOOR, free_memory_bytes  # noqa: E402
from run import serve  # noqa: E402


def missing_feeds(fares: Path, timetable: Path, knowledgebase: Path) -> list[Path]:
    """The feed folders this build cannot run without, for the message below."""
    wanted = [fares, timetable, knowledgebase]
    return [path for path in wanted if not (path.is_dir() and any(path.iterdir()))]


def build_command(args: argparse.Namespace, codes: list[str]) -> list[str]:
    """The builder invocation, assembled here so the script states what it runs."""
    return [
        sys.executable,
        "build_demo_page.py",
        "--feed", str(args.feed),
        "--timetable", str(args.timetable),
        "--knowledgebase", str(args.knowledgebase),
        "--date", args.date or date.today().isoformat(),
        "--all-origins",
        "--only-stations", ",".join(codes),
        # One worker on purpose. A pool worker parses the whole national
        # timetable for itself, which is 79 seconds and 2.2 GB each, to save the
        # ten seconds an extra station page takes. The pool is for the whole
        # network (ADR-0057); a handful of stations is not that.
        "--workers", str(args.workers),
        "--out", str(args.out),
        # Every notice, read from the builder's own table rather than a list
        # repeated here: adding one there cannot leave this list behind, and a
        # real feed's build carries the notices as a matter of course.
        "--notices", ",".join(NOTICES),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build named stations from the real feeds, then serve them.",
        epilog="Station codes are CRS codes: Grantham is GRA, Nottingham is NOT.",
    )
    parser.add_argument("codes", nargs="*", default=list(DEFAULT_CODES),
                        help="CRS codes to build; defaults to Grantham and Nottingham")
    parser.add_argument("--feed", type=Path, default=ROOT / "feeds" / "fares")
    parser.add_argument("--timetable", type=Path, default=ROOT / "feeds" / "timetable")
    parser.add_argument("--knowledgebase", type=Path,
                        default=ROOT / "feeds" / "knowledgebase")
    parser.add_argument("--out", type=Path, default=SITE / "index.html")
    parser.add_argument("--workers", type=int, default=1,
                        help="1 by default; a pool worker re-parses the whole timetable")
    parser.add_argument("--date", default=None,
                        help="timetable service date as YYYY-MM-DD; defaults to today")
    parser.add_argument("--port", type=int, default=PORT_DEFAULT)
    parser.add_argument("--no-serve", action="store_true",
                        help="build and stop instead of serving the result")
    args = parser.parse_args()

    codes = [code.strip().upper() for code in args.codes if code.strip()]
    if not codes:
        codes = list(DEFAULT_CODES)
    absent = missing_feeds(args.feed, args.timetable, args.knowledgebase)
    if absent:
        for path in absent:
            print(f"No feed at {path}", file=sys.stderr)
        print(
            "Download the real feeds first:  python dtd_download.py\n"
            "Or build the invented demo feed instead:\n"
            "  python build_stations.py --feed _demo_feed --timetable _demo_feed"
            " --knowledgebase _demo_kb",
            file=sys.stderr,
        )
        return 1

    free = free_memory_bytes()
    floor_gb = ONE_WORKER_FLOOR / 1e9
    # Flushed, because the builder below is a child process writing to the same
    # standard output. A line buffered here surfaces after the build it was
    # announcing, which reads as though the build had started before it was
    # asked to -- and the memory warning is the one line that has to arrive
    # first, since it is the one that changes what the operator should do.
    if free is not None and free < ONE_WORKER_FLOOR:
        print(
            f"Warning: {free / 1e9:.1f} GB of memory is free and this build wants "
            f"about {floor_gb:.1f} GB for the two feeds and one page at a time "
            "(ADR-0057). It will still run, slowly, by paging.",
            file=sys.stderr,
            flush=True,
        )
    elif free is not None:
        print(f"{free / 1e9:.1f} GB of memory free; this build wants about "
              f"{floor_gb:.1f} GB (ADR-0057).", flush=True)
    print(f"Building {len(codes)} station page(s): {', '.join(codes)}", flush=True)
    print("Reading the fares feed and the national timetable now. That is the "
          "whole cost of the build, and it does not grow with the number of "
          "stations: about 93 seconds with room, and minutes of paging when "
          "memory is short.", flush=True)
    result = subprocess.run(build_command(args, codes), cwd=ROOT)
    if result.returncode != 0:
        return result.returncode
    if args.no_serve:
        print(f"Wrote {args.out.parent}. To open it: "
              f"python -m http.server {args.port} --directory {args.out.parent}",
              flush=True)
        return 0
    return serve(args.out.parent, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
