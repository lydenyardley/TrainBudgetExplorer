"""Answer the Stage 1 question for one origin: how many destinations fall under a budget?

Usage:
    python grantham_sweep.py --feed ~/Downloads/RJFAF464 --origin GRN --budget 20 --adults 2
    python grantham_sweep.py --feed feeds/fares --timetable feeds/timetable --origin GRN --budget 20
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from atoc_fares import FaresDb, Reachable, format_pence
from atoc_timetable import Journey, TimetableDb, format_minutes
from feeds_cli import add_feed_args, find_origin


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cheapest return reachable from an origin inside a budget.")
    add_feed_args(parser)
    parser.add_argument(
        "--origin",
        default="GRN",
        help="origin CRS code. Grantham's real code is GRA; the synthetic feed invents GRN",
    )
    parser.add_argument("--budget", type=float, default=20.0, help="budget in pounds")
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--railcard", default=None, help='railcard name, e.g. "Two Together"')
    parser.add_argument(
        "--party-budget",
        action="store_true",
        help="treat the budget as the total for the party rather than per adult",
    )
    parser.add_argument("--max-changes", type=int, default=1, help="changes to allow when planning a journey")
    parser.add_argument(
        "--date",
        default=None,
        help="service date as YYYY-MM-DD, applying each schedule's days and overlays",
    )
    parser.add_argument("--limit", type=int, default=15, help="rows to print")
    parser.add_argument("--csv", default=None, help="write the full result set to this path")
    return parser.parse_args(argv)


def enrich_with_journeys(
    results: list[Reachable],
    timetable: TimetableDb,
    origin_crs: str,
    *,
    max_changes: int = 1,
    day: date | None = None,
) -> list[tuple[Reachable, Journey | None]]:
    """Attach the best journey to each destination. None means no service in the feed."""
    return [
        (reachable, timetable.best_journey(origin_crs, reachable.crs, max_changes=max_changes, day=day))
        for reachable in results
    ]


def _journey_cells(journey: Journey | None) -> tuple[str, str]:
    if journey is None:
        return "-", "-"
    return format_minutes(journey.duration), str(journey.changes)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    budget_pence = round(args.budget * 100)
    db = FaresDb().load_feed(args.feed)
    stats = db.stats()

    origin = find_origin(db, args.origin)
    if origin is None:
        print(f"origin {args.origin!r} not found in feed. Files read: {db.files_read}", file=sys.stderr)
        return 2

    results = db.destinations_within(
        origin.crs,
        budget_pence,
        adults=args.adults,
        railcard=args.railcard,
        party_budget=args.party_budget,
    )

    day: date | None = None
    if args.date:
        try:
            day = date.fromisoformat(args.date)
        except ValueError:
            print(f"date {args.date!r} is not YYYY-MM-DD", file=sys.stderr)
            return 2

    timetable = TimetableDb().load_feed(args.timetable) if args.timetable else None
    rows = (
        enrich_with_journeys(results, timetable, origin.crs, max_changes=args.max_changes, day=day)
        if timetable
        else [(reachable, None) for reachable in results]
    )

    mode = "party total" if args.party_budget else "per adult"
    print(f"feed: {stats['stations']} stations, {stats['flows']} flows, {stats['fares']} fares")
    if timetable:
        timetable_stats = timetable.stats()
        print(f"timetable: {timetable_stats['schedules']} schedules, {timetable_stats['calling_points']} calling points")
    print(f"origin: {origin.crs} {origin.name}")
    print(f"budget: {format_pence(budget_pence)} {mode}, {args.adults} adult(s), railcard: {args.railcard or 'none'}")
    if timetable:
        print(f"services: {day.isoformat() if day else 'every schedule in the feed, dates ignored'}")
    print(f"destinations under budget: {len(rows)}")
    if timetable:
        served = sum(1 for _, journey in rows if journey is not None)
        print(f"with a service in the feed: {served}; with no service: {len(rows) - served}")
    print()

    if rows:
        header = f"{'CRS':<4}{'station':<22}{'per adult':>10}{'party':>9}"
        if timetable:
            header += f"{'time':>9}{'chg':>4}"
        print(f"{header}  ticket")
        for reachable, journey in rows[: args.limit]:
            duration, changes = _journey_cells(journey)
            line = (
                f"{reachable.crs:<4}{reachable.station[:21]:<22}"
                f"{format_pence(reachable.best_pence):>10}{format_pence(reachable.party_pence):>9}"
            )
            if timetable:
                line += f"{duration:>9}{changes:>4}"
            flag = " off-peak" if reachable.off_peak else ""
            note = "" if journey or not timetable else "  no service in the feed"
            print(f"{line}  {reachable.ticket_code}{flag}{note}")

    if args.csv:
        with Path(args.csv).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "crs",
                    "station",
                    "ticket_code",
                    "per_adult_pence",
                    "party_pence",
                    "off_peak",
                    "minutes",
                    "changes",
                    "legs",
                ]
            )
            for reachable, journey in rows:
                writer.writerow(
                    [
                        reachable.crs,
                        reachable.station,
                        reachable.ticket_code,
                        reachable.best_pence,
                        reachable.party_pence,
                        "yes" if reachable.off_peak else "no",
                        journey.duration if journey else "",
                        journey.changes if journey else "",
                        ">".join(leg.train_uid for leg in journey.legs) if journey else "",
                    ]
                )
        print(f"\nwrote {len(rows)} rows to {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
