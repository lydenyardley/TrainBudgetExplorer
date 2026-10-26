"""Time the per-origin phases of a page build, and print the distribution.

The build's own measured average is 10.75 s per page on one worker, but three
sampled origins cost 1.17 s, 7.20 s and 28.48 s for the timetable half alone
(12 October 2026 audit, T8): a mean taken over that spread cannot say whether
the tail or the middle dominates, and which of the two it is decides whether
the work goes into the search or into splitting the origin list. So this times
the phases -- the slice cut, the day index, the reachability search -- per
origin, through the functions the build calls, and prints the shape rather
than the mean.

    python -m tools.measure_origin_costs --origins AAT,ABA,AAP

With ``--priced-count`` it also builds one origin's page and prints the two
numbers beside each other: the places the fare selectors price, which is the
question the index pass asks (``_priced_destinations``), and the places the page
carries, which is the number the chooser shows (``places_in_payload``). The gap
between them is the places the feed prices as two fares (ADR-0061), and the page
time is what closing that gap in the index pass would cost -- it does not, and
this is the measurement behind that.

    python -m tools.measure_origin_costs --origins GRA,KGX,MAN --priced-count
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from trainbudget.build import build_demo_page
from trainbudget.timetable.atoc_timetable import TimetableDb

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


def time_count(fares, timetable, origin: str, day: date, max_changes: int) -> dict:
    """The two numbers one origin has, and what each of them costs.

    The index pass asks ``_priced_destinations`` -- the fare selectors' union --
    to decide whether an origin can answer at all (ADR-0019 decision 3), and the
    page the build writes carries more places than that: a place the feed prices
    in two fares is a row the page has and no selector sees (ADR-0061). The
    number the chooser shows is therefore read off the page
    (``places_in_payload``), and this times the page to show what that reading
    costs when it is done as a second pass instead. Measured 15 October 2026,
    real feed: Grantham's union was **50** places and its page **334**, King's
    Cross 206 and 535, Manchester Piccadilly 287 and 427 -- and the walk that
    closes the gap costs 3.0s, 12.9s and 15.9s per origin, against a release
    share of about 450 origins that already takes 87 to 114 minutes inside a
    150-minute timeout. That is why the count comes from the page.
    """
    start = time.perf_counter()
    union = fares.priced_destinations_within(
        origin, build_demo_page.EVERYTHING_PENCE, adults=1, day=day
    )
    union_seconds = time.perf_counter() - start
    start = time.perf_counter()
    payload = build_demo_page.build_payload(
        fares, timetable, origin, max_changes=max_changes, day=day
    )
    return {
        "origin": origin,
        "union": len(union),
        "places": build_demo_page.places_in_payload(payload),
        "union_seconds": union_seconds,
        "page_seconds": time.perf_counter() - start,
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
    parser.add_argument("--priced-count", action="store_true",
                        help="also build one page per origin, and print the places "
                             "the selectors price beside the places the page carries")
    parser.add_argument("--fares", default=None, type=Path,
                        help="fares feed folder, for --priced-count; defaults to feeds/fares")
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

    if args.priced_count:
        fares_folder = args.fares or (ROOT / "feeds" / "fares")
        if not fares_folder.exists():
            print(f"no fares feed at {fares_folder}", file=sys.stderr)
            return 2
        print("", flush=True)
        for origin in origins:
            # Loaded outside the timings: a page build loads the feed once for
            # the whole run, so a load inside the timer would report a cost the
            # index pass does not pay.
            started = time.perf_counter()
            fares = build_demo_page.load_page_fares(fares_folder, origin).fares
            loaded = time.perf_counter() - started
            row = time_count(fares, timetable, origin, day, args.max_changes)
            print(f"  {row['origin']}: {row['union']} places from the selectors, "
                  f"{row['places']} the page carries, "
                  f"union {row['union_seconds']:.2f}s, "
                  f"page {row['page_seconds']:.2f}s "
                  f"(fares loaded in {loaded:.1f}s, outside the timings)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
