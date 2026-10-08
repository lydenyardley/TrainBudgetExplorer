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
is built from its own origin's slice of the timetable, about ten seconds of work
(ADR-0057). Two stations is a five-minute build when there is memory for the two
feeds. Measured on 7 October 2026 with 5.1 GB free against the 6.4 GB floor
`build_workers.ONE_WORKER_FLOOR` sets, the same two loads took 11 minutes under
paging and the build took 63 minutes end to end, writing both pages where the two
earlier runs had written none in 24. Measured again on 8 October 2026 with the
timetable slice in place and **2.1 GB free**: both pages, exit 0, in **20 min
53 s**, the first at 9.7 minutes and the second at 20.8. That floor is what the
script's memory warning is about: on the wrong side of it the two loads page their
way in and every page after the first is built with the machine short of memory,
which is the difference between five minutes and 21. A page is a slice of the
timetable now, so what a page holds is one origin's reach rather than the network.
The whole network is the same command without
`--only-stations`, and it is two hours on four workers or most of a working day on
one.

**What it costs with an index.** `--timetable-index` drops the timetable load
entirely: the fares feed plus one page's slice is the whole footprint, and no
process parses the national timetable -- not this one, and not a pool worker.
`python tools/build_timetable_index.py --timetable feeds/timetable --origins
GRA,NOT` writes those slices from a single parse, and every build after that
starts where the parse would have ended. Measured on 8 October 2026, this command
with the index on those two stations **finished, exit 0, in 3 min 44 s** with
4.7 GB free, so no national timetable was held at any point;
`docs/build-performance-findings.md` has the write, the read-back and that run.
The index is keyed to
the feed's bytes and to this source, so a new download needs a new index rather
than reusing an old one. A station the index has not got is built from the feed
when the feed is still there, and the build is refused before it starts when it
is not: a page published without times would say the station has no services.

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


def missing_feeds(
    fares: Path, timetable: Path, knowledgebase: Path, index: Path | None = None
) -> list[Path]:
    """The feed folders this build cannot run without, for the message below.

    A build given an index of slices does not read the timetable feed at all, so
    the feed is not asked for: the point of the index is a machine that does not
    have to hold the national timetable, and a feed folder it must keep anyway
    would be the same folder read by a different name.
    """
    wanted = [fares, knowledgebase] if index else [fares, timetable, knowledgebase]
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
        # network (ADR-0057); a handful of stations is not that. Given an index a
        # worker parses nothing and reads one page's slice instead, so its cost
        # is that station's reach -- but the pool is still not for two pages.
        "--workers", str(args.workers),
        "--out", str(args.out),
        # A directory of per-origin slices, when one has been written for these
        # stations: the builder then reads no timetable feed at all. Omitted
        # rather than passed empty, because the builder's default is no index.
        *(["--timetable-index", str(args.timetable_index)] if args.timetable_index else []),
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
                        help="1 by default; a pool worker re-parses the whole timetable, "
                             "unless --timetable-index is given, when it reads one page's slice")
    parser.add_argument("--date", default=None,
                        help="timetable service date as YYYY-MM-DD; defaults to today")
    parser.add_argument("--timetable-index", type=Path, default=None,
                        help="per-origin timetable slices to build from instead of the "
                             "timetable feed, written by tools/build_timetable_index.py")
    parser.add_argument("--port", type=int, default=PORT_DEFAULT)
    parser.add_argument("--no-serve", action="store_true",
                        help="build and stop instead of serving the result")
    args = parser.parse_args()

    codes = [code.strip().upper() for code in args.codes if code.strip()]
    if not codes:
        codes = list(DEFAULT_CODES)
    absent = missing_feeds(args.feed, args.timetable, args.knowledgebase, args.timetable_index)
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
    if args.timetable_index:
        print("Reading the fares feed now. Every page's timetable comes from its "
              "own slice in the index, so the national timetable is not read at "
              "all -- and a page costs what that station's reach costs.", flush=True)
    else:
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
