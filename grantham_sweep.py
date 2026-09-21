"""Answer the Stage 1 question for one origin: how many destinations fall under a budget?

Usage:
    python grantham_sweep.py --feed ~/Downloads/RJFAF464 --origin GRN --budget 20 --adults 2
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from atoc_fares import FaresDb, format_pence


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cheapest return reachable from an origin inside a budget.")
    parser.add_argument("--feed", required=True, help="fares feed folder or zip")
    parser.add_argument("--origin", default="GRN", help="origin CRS code, e.g. GRN for Grantham")
    parser.add_argument("--budget", type=float, default=20.0, help="budget in pounds")
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--railcard", default=None, help='railcard name, e.g. "Two Together"')
    parser.add_argument(
        "--party-budget",
        action="store_true",
        help="treat the budget as the total for the party rather than per adult",
    )
    parser.add_argument("--limit", type=int, default=15, help="rows to print")
    parser.add_argument("--csv", default=None, help="write the full result set to this path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    budget_pence = round(args.budget * 100)
    db = FaresDb().load_feed(args.feed)
    stats = db.stats()

    try:
        origin = db.locations_by_crs[args.origin.strip().upper()]
    except KeyError:
        print(f"origin {args.origin!r} not found in feed. Files read: {db.files_read}", file=sys.stderr)
        return 2

    results = db.destinations_within(
        origin.crs,
        budget_pence,
        adults=args.adults,
        railcard=args.railcard,
        party_budget=args.party_budget,
    )

    mode = "party total" if args.party_budget else "per adult"
    print(f"feed: {stats['stations']} stations, {stats['flows']} flows, {stats['fares']} fares")
    print(f"origin: {origin.crs} {origin.name}")
    print(f"budget: {format_pence(budget_pence)} {mode}, {args.adults} adult(s), railcard: {args.railcard or 'none'}")
    print(f"destinations under budget: {len(results)}")
    print()
    if results:
        print(f"{'CRS':<4}{'station':<22}{'per adult':>10}{'party':>9}  ticket")
        for reachable in results[: args.limit]:
            flag = " off-peak" if reachable.off_peak else ""
            print(
                f"{reachable.crs:<4}{reachable.station[:21]:<22}"
                f"{format_pence(reachable.best_pence):>10}{format_pence(reachable.party_pence):>9}"
                f"  {reachable.ticket_code}{flag}"
            )

    if args.csv:
        with Path(args.csv).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["crs", "station", "ticket_code", "per_adult_pence", "party_pence", "off_peak"])
            for reachable in results:
                writer.writerow(
                    [
                        reachable.crs,
                        reachable.station,
                        reachable.ticket_code,
                        reachable.best_pence,
                        reachable.party_pence,
                        "yes" if reachable.off_peak else "no",
                    ]
                )
        print(f"\nwrote {len(results)} rows to {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
