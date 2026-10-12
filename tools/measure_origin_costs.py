"""Time the per-origin phases of a page build, and print the distribution.

The build's own measured average is 10.75 s per page on one worker, but three
sampled origins cost 1.17 s, 7.20 s and 28.48 s for the timetable half alone
(12 October 2026 audit, T8): a mean taken over that spread cannot say whether
the tail or the middle dominates, and which of the two it is decides whether
the work goes into the search or into splitting the origin list. So this times
the phases -- the slice cut, the day index, the reachability search -- per
origin, through the functions the build calls, and prints the shape rather
than the mean.

    python tools/measure_origin_costs.py --origins AAT,ABA,AAP
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atoc_timetable import TimetableDb  # noqa: E402

#: The service week the build searches, as days past the service date. Eight
#: days, because the build walks SERVICE_WEEK_HORIZON + 1 past its day, and a
#: tool that searched fewer would time a different week than the pages carry.
SERVICE_WEEK_DAYS = 8


def time_origin(timetable: TimetableDb, origin: str, days: list[date], max_changes: int) -> dict:
    """The timetable half of one origin's page, phase by phase.

    The slice cut first, then one day index and one reachability search per
    day of the week -- the same calls build_payload makes, in the same order.
    The index is timed apart from the search it serves because amortising the
    index is a different change than speeding the search (T2): one number for
    both cannot tell them apart.
    """
    start = time.perf_counter()
    focused = timetable.focused(origin)
    cut = time.perf_counter() - start
    index_total = 0.0
    search_total = 0.0
    reached = 0
    for day in days:
        start = time.perf_counter()
        focused._ensure_indexes(day)
        index_total += time.perf_counter() - start
        start = time.perf_counter()
        found = focused.journeys_from(origin, max_changes=max_changes, day=day)
        search_total += time.perf_counter() - start
        reached = max(reached, len(found))
    return {
        "origin": origin,
        "schedules": len(focused.schedules),
        "destinations": reached,
        "cut": cut,
        "index_per_day": index_total / len(days),
        "search_per_day": search_total / len(days),
        "total": cut + index_total + search_total,
    }


def distribution(rows: list[dict]) -> dict:
    """Mean, median, ninetieth percentile and maximum of the per-origin totals."""
    totals = sorted(row["total"] for row in rows)
    ninetieth = totals[min(len(totals) - 1, int(len(totals) * 0.9))]
    return {
        "origins": len(totals),
        "mean": statistics.fmean(totals),
        "median": statistics.median(totals),
        "p90": ninetieth,
        "max": totals[-1],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed", default=None, type=Path,
                        help="timetable feed folder; defaults to feeds/timetable")
    parser.add_argument("--origins", default="AAT,ABA,AAP",
                        help="comma-separated CRS codes. The default is the three "
                             "origins the 12 October 2026 audit sampled, so a run "
                             "reproduces its table before extending it.")
    parser.add_argument("--date", default=None,
                        help="service date as YYYY-MM-DD; the week starts here. "
                             "Defaults to today.")
    parser.add_argument("--max-changes", type=int, default=1,
                        help="the journey search's change limit, as the build takes it")
    args = parser.parse_args(argv)

    feed = args.feed or (ROOT / "feeds" / "timetable")
    if not feed.is_dir() or not any(feed.iterdir()):
        print(f"no timetable feed at {feed}", file=sys.stderr)
        return 2
    origins = [code.strip().upper() for code in args.origins.split(",") if code.strip()]
    if not origins:
        print("error: --origins named no code", file=sys.stderr)
        return 2
    day = date.fromisoformat(args.date) if args.date else date.today()
    days = [day + timedelta(days=offset) for offset in range(SERVICE_WEEK_DAYS)]

    print(f"Loading timetable feed from {feed} ...", flush=True)
    started = time.perf_counter()
    timetable = TimetableDb().load_feed(feed)
    print(f"Loaded {len(timetable.schedules):,} schedules "
          f"in {time.perf_counter() - started:.1f}s", flush=True)

    rows = []
    for origin in origins:
        row = time_origin(timetable, origin, days, args.max_changes)
        rows.append(row)
        print(f"  {row['origin']}: {row['schedules']:,} slice schedules, "
              f"cut {row['cut']:.2f}s, index {row['index_per_day']:.2f}s/day, "
              f"search {row['search_per_day']:.2f}s/day, "
              f"total {row['total']:.2f}s", flush=True)

    shape = distribution(rows)
    print(f"\n{shape['origins']} origin(s): mean {shape['mean']:.2f}s, "
          f"median {shape['median']:.2f}s, p90 {shape['p90']:.2f}s, "
          f"max {shape['max']:.2f}s per origin for the timetable half")
    print(f"the most expensive origin costs "
          f"{shape['max'] / max(shape['mean'], 1e-9):.1f}x the mean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
