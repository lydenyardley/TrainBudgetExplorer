"""Write the per-origin timetable slices a build can be built from.

A page's timetable is a slice of the feed: the schedules that call its origin,
and the schedules that call anywhere those call. `TimetableDb.focused` cuts that
slice out of a database already in memory, which is nearly free -- a quarter of
a second once one pass has indexed the feed -- but the database it is cut from
is the whole national timetable, parsed and held at 56.7 s and 1.87 GB in every
process that builds a page.

This tool cuts the slices once and leaves them on disk. A build given the
directory answers each page from its own slice and never reads the feed at all
(`build_demo_page.py --timetable-index`), which is what a machine without the
memory for the national index needs: no parse, no 1.87 GB held beside the fares
feed, and the same pages, because the slice is the same slice the feed would
have been cut down to.

    python tools/build_timetable_index.py --timetable feeds/timetable \\
        --origins GRA,NOT
    python tools/build_timetable_index.py --timetable feeds/timetable \\
        --origins GRA,NOT --root _cache/timetable-index

Exit codes: 0 every named origin is in the index now, 1 some could not be
written, 2 the request could not be served at all (no feed, no origins named, a
code the feed cannot be asked about). A code the feed does not know is exit 2
rather than a silent skip, because the caller asked for it by name.

**What this costs.** One file per origin, and a slice is as large as that
origin's reach: about a quarter of the feed for a main-line station, and the
schedules are the bytes. The index is for the origins a build actually writes --
a station subset, or one station -- and `--all-origins` is refused without
`--max-bytes`, because indexing all 3,400 priced stations means writing the
network out 3,400 times and the file system would be the first thing to say so.

**What this does not do.** It does not read the index it writes -- a build does
that, and `SliceIndex.save` reads each file back before this reports it written,
so a slice that cannot be restored fails here rather than in the next build. It
does not prune: an index cut from an older feed or an older parser is a
different directory, and deleting the old one is a decision with a size attached,
so it is left for a person to make.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

# Reach the project root whether run as `python tools/build_timetable_index.py`
# (the README's way) or imported as tools.build_timetable_index (the tests' way).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atoc_timetable import SLICE_INDEX_SCHEMA, SliceIndex, TimetableDb  # noqa: E402
from build_demo_page import (  # noqa: E402
    TIMETABLE_INDEX_ROOT,
    timetable_index_location,
)

MEGABYTE = 1_000_000


def askable_origins(db: TimetableDb) -> set[str]:
    """Every station code this feed can be asked about.

    Both maps, because a station the CIF inserts name is one a page can be
    about even though the station names file does not list it.
    """
    codes = {station.crs for station in db.stations_by_tiploc.values() if station.crs}
    codes.update(crs for crs in db.cif_crs_by_tiploc.values() if crs)
    return codes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timetable", type=Path, required=True, help="CIF timetable feed folder or zip")
    parser.add_argument("--origins", default=None, help="comma-separated station codes to index")
    parser.add_argument("--all-origins", action="store_true", help="every station in the feed; needs --max-bytes")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help=f"where the index lives (default: {TIMETABLE_INDEX_ROOT}, one directory per feed and parser)",
    )
    parser.add_argument("--max-bytes", type=int, default=None, help="stop before writing more than this much")
    parser.add_argument("--refresh", action="store_true", help="rewrite a slice this index already holds")
    args = parser.parse_args(argv)

    if not args.timetable.exists():
        print(f"no timetable feed at {args.timetable}", file=sys.stderr)
        return 2
    named = [code.strip().upper() for code in (args.origins or "").split(",") if code.strip()]
    if not named and not args.all_origins:
        print("name the origins to index with --origins, or ask for --all-origins", file=sys.stderr)
        return 2
    if args.all_origins and args.max_bytes is None:
        print(
            "--all-origins writes one slice per station and a slice is a quarter of the "
            "feed for a main-line station; pass --max-bytes to say how much room it may use",
            file=sys.stderr,
        )
        return 2

    root = args.root if args.root is not None else TIMETABLE_INDEX_ROOT
    started = time.monotonic()
    print(f"Loading timetable feed from {args.timetable} ...", flush=True)
    db = TimetableDb().load_feed(args.timetable)
    print(
        f"Loaded timetable: {db.stats()['schedules']:,} schedules, "
        f"{db.stats()['calling_points']:,} calling points in {time.monotonic() - started:.1f}s",
        flush=True,
    )

    known = askable_origins(db)
    unknown = [code for code in named if code not in known]
    if unknown:
        print(
            f"this feed cannot be asked about {', '.join(sorted(unknown))}: "
            "no station record and no CIF insert names a code",
            file=sys.stderr,
        )
        return 2
    origins = named or sorted(known)
    directory, identity = timetable_index_location(root, args.timetable)
    index = SliceIndex(
        directory,
        identity=identity,
        source={"feed": str(args.timetable), "schema": SLICE_INDEX_SCHEMA},
    )
    print(f"{len(origins):,} origin(s) to index into {index.directory}", flush=True)
    free = shutil.disk_usage(index.directory.parent if index.directory.parent.exists() else Path.cwd()).free
    print(f"{free / MEGABYTE / 1000:.1f} GB free on this volume", flush=True)

    already = index.totals()["bytes"]
    written = 0
    written_bytes = 0
    failed: list[str] = []
    kept = [origin for origin in origins if index.has(origin)]
    if kept and not args.refresh:
        print(f"{len(kept):,} origin(s) are already here and are being left alone", flush=True)
    for origin in origins:
        if index.has(origin) and not args.refresh:
            continue
        slice_db = db.focused(origin)
        try:
            path = index.save(origin, slice_db)
        except OSError as error:
            failed.append(origin)
            print(f"{origin}: FAILED {error}", file=sys.stderr, flush=True)
            continue
        written += 1
        entry = index.manifest()["origins"][origin]
        written_bytes += entry["bytes"]
        print(
            f"{origin}: {entry['schedules']:,} of {entry['feed_schedules']:,} schedules, "
            f"{entry['calling_points']:,} calling points, "
            f"{entry['bytes'] / MEGABYTE:.1f} MB -> {path.name}"
            + (f" in {time.monotonic() - started:.0f}s" if written % 10 == 0 else ""),
            flush=True,
        )
        if args.max_bytes is not None and already + written_bytes > args.max_bytes:
            print(
                f"stopping: the index is now {(already + written_bytes) / MEGABYTE:.1f} MB, "
                f"past the {args.max_bytes / MEGABYTE:.1f} MB it was allowed",
                flush=True,
            )
            break
        # The slice is a list of references into the feed's schedules, so letting
        # it go costs nothing and keeps one origin's cut from being held while
        # the next one is made.
        del slice_db

    print(f"Timetable index: {index.describe()}", flush=True)
    if failed:
        print(f"{len(failed)} origin(s) could not be written: {', '.join(failed)}", file=sys.stderr)
        return 1
    # A bounded run is meant to stop, so what it left out is not a failure. An
    # unbounded one either wrote everything it was asked for or did not, and the
    # caller needs to know which: a script that indexes two stations and goes on
    # to build them is a build that finds out later.
    outstanding = [origin for origin in origins if not index.has(origin)]
    if outstanding and args.max_bytes is None:
        print(
            f"{len(outstanding):,} origin(s) were asked for and are not in the index: "
            f"{', '.join(outstanding[:12])}",
            file=sys.stderr,
        )
        return 2
    if written:
        print(
            f"{written:,} slice(s) written in {time.monotonic() - started:.0f}s; a build can now be "
            f"given --timetable-index {root} with no timetable feed",
            flush=True,
        )
    else:
        print(
            f"every origin asked for was already in the index ({len(kept):,} left alone); "
            "nothing to write",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
