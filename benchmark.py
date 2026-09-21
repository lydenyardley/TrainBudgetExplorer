"""Measure the journey search on a large invented feed.

Time alone is not a decision. Each onward departure cap is compared against an
uncapped search over the same feed, so the cap is chosen with its cost visible.

The feed is invented and uniform, so the times bound the work the search does.
They do not predict a real network.

Usage:
    python benchmark.py
    python benchmark.py --schedules 4000 --stations 300 --queries 100
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import time
from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import MAX_ONWARD_DEPARTURES, TimetableDb
from make_synthetic_feed import build_large_synthetic_feed

UNLIMITED = 0
DEFAULT_CAPS = (UNLIMITED, 20, 60, 200)
EVERYTHING_PENCE = 100_000


def rank(journey) -> tuple[int, int] | None:
    """What a journey is judged on: duration first, then changes."""
    return None if journey is None else (journey.duration, journey.changes)


def measure(timetable: TimetableDb, targets: list[tuple[str, str]], *, max_onward: int | None):
    """Run every query and return per-query seconds plus the journeys found."""
    timings: list[float] = []
    journeys: dict[tuple[str, str], tuple[int, int] | None] = {}
    for target in targets:
        started = time.perf_counter()
        journey = timetable.best_journey(target[0], target[1], max_onward=max_onward)
        timings.append(time.perf_counter() - started)
        journeys[target] = rank(journey)
    return timings, journeys


def percentile(timings: list[float], fraction: float) -> float:
    if not timings:
        return 0.0
    ordered = sorted(timings)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return ordered[index]


def build_targets(
    fares: FaresDb,
    origins: list[str],
    per_origin: int,
    *,
    timetable: TimetableDb | None = None,
    transfer_only: bool = False,
) -> list[tuple[str, str]]:
    """Priced destinations per origin.

    With transfer_only, keep the pairs whose only route needs a change. That is
    where a cap on the onward search can cost a journey, and where a cap that
    never bites proves nothing.
    """
    targets: list[tuple[str, str]] = []
    for origin in origins:
        priced = fares.destinations_within(origin, EVERYTHING_PENCE, adults=1)
        picked: list[tuple[str, str]] = []
        for reachable in priced:
            if transfer_only:
                if timetable is None:
                    raise ValueError("transfer_only needs a timetable to test for a direct train")
                if timetable.best_journey(origin, reachable.crs, max_changes=0) is not None:
                    continue
            picked.append((origin, reachable.crs))
            if len(picked) >= per_origin:
                break
        targets.extend(picked)
    return targets


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Measure the journey search against a cap.")
    parser.add_argument("--stations", type=int, default=120)
    parser.add_argument("--schedules", type=int, default=1000)
    parser.add_argument(
        "--shape",
        choices=("uniform", "hub_spoke"),
        default="uniform",
        help="uniform randomises stops; hub_spoke forces a change past the hub",
    )
    parser.add_argument("--origins", type=int, default=2, help="how many invented origins to query from")
    parser.add_argument(
        "--origin",
        action="append",
        default=None,
        help="query this station code instead; repeat to measure several",
    )
    parser.add_argument("--queries", type=int, default=40, help="priced destinations per origin")
    parser.add_argument("--caps", default=",".join(str(cap) for cap in DEFAULT_CAPS))
    parser.add_argument("--keep", default=None, help="write the invented feed here and keep it")
    parser.add_argument(
        "--feed",
        default=None,
        help="measure an existing feed folder instead of building an invented one",
    )
    parser.add_argument(
        "--transfer-only",
        action="store_true",
        help="measure only the pairs whose route needs a change",
    )
    arguments = parser.parse_args(argv)

    caps = [int(value) for value in arguments.caps.split(",")]
    context = tempfile.TemporaryDirectory() if arguments.keep is None else None
    if arguments.feed:
        feed = Path(arguments.feed)
        if not feed.is_dir():
            print(f"not a feed folder: {feed}", file=sys.stderr)
            return 2
    else:
        feed = Path(arguments.keep) if arguments.keep else Path(context.name)
        build_large_synthetic_feed(
            feed,
            stations=arguments.stations,
            schedules=arguments.schedules,
            shape=arguments.shape,
        )

    started = time.perf_counter()
    fares = FaresDb().load_feed(feed)
    fares_seconds = time.perf_counter() - started
    started = time.perf_counter()
    timetable = TimetableDb().load_feed(feed)
    timetable_seconds = time.perf_counter() - started

    if arguments.origin:
        origins = list(arguments.origin)
    else:
        origins = [
            fares.locations_by_nlc[str(1000 + index)].crs for index in range(arguments.origins)
        ]
    targets = build_targets(
        fares,
        origins,
        arguments.queries,
        timetable=timetable,
        transfer_only=arguments.transfer_only,
    )

    if arguments.feed:
        print(f"feed: {feed} (existing)")
    else:
        print(
            f"feed: {arguments.stations} stations, {arguments.schedules} schedules,"
            f" {arguments.shape} shape (invented)"
        )
    print(f"parse: fares {fares_seconds:.2f}s, timetable {timetable_seconds:.2f}s")
    print(f"queries: {len(targets)} target pairs across {len(origins)} origin(s)")
    print(f"origins: {', '.join(origins)}")
    print("the first query includes the station index build")
    print()
    if not targets:
        print("no priced destinations found, so there is nothing to measure", file=sys.stderr)
        return 2
    header = f"{'cap':>10}{'total s':>10}{'median ms':>12}{'p95 ms':>10}{'worse than uncapped':>22}"
    print(header)

    reference: dict[tuple[str, str], tuple[int, int] | None] | None = None
    uncapped_total = 0.0
    for cap in sorted(caps, key=lambda value: (value != UNLIMITED, value)):
        timings, journeys = measure(timetable, targets, max_onward=None if cap == UNLIMITED else cap)
        if cap == UNLIMITED:
            reference = journeys
            uncapped_total = sum(timings)
        worse = ""
        if reference is not None and cap != UNLIMITED:
            worse = str(
                sum(
                    1
                    for key, reference_rank in reference.items()
                    if reference_rank is not None
                    and (journeys[key] is None or journeys[key] > reference_rank)
                )
            )
        label = "uncapped" if cap == UNLIMITED else str(cap)
        print(
            f"{label:>10}{sum(timings):>10.2f}"
            f"{statistics.median(timings) * 1000:>12.1f}"
            f"{percentile(timings, 0.95) * 1000:>10.1f}{worse:>22}"
        )

    if uncapped_total:
        print()
        print(f"the shipped cap is {MAX_ONWARD_DEPARTURES}; read the table above for its price")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
