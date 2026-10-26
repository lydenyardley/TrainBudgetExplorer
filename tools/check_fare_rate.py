"""Refuse a published fare whose price per minute of journey is not plausible.

A page publishes the cheapest fare the feed holds, so a price means nothing on
its own. What a reader can act on is the price beside the journey it buys. A
fare that works out at half a penny a minute across two hours, or at nine
thousand, is not a price, and it is not a symptom anybody is watching for
while a build runs over 2,500 pages.

This asks the page's own three selectors for every origin, prices each
destination's row against the fastest timetable journey for that pair, and
refuses the build when a rate falls outside the reviewed band. The selectors
are the page's, so a fare this tool calls publishable is a fare a page would
show, and one it does not is one no page carries.

Usage:
    python -m tools.check_fare_rate --feed feeds/fares/dtd-fares.zip \\
        --timetable feeds/timetable
    python -m tools.check_fare_rate ... --report

Exits 0 when every rate is inside the band, 1 with the offenders named, and 2
when the feeds could not be read at all, which is a different failure from a
price being wrong and must not read as one.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.timetable.atoc_timetable import TimetableDb

# The sentinel budget: what every origin can reach, so nothing is dropped for
# price before the rate is measured.
EVERYTHING_PENCE = 10**12

# The reviewed band, in pence per minute of journey.
#
# Measured against the 24 September 2026 download rather than chosen. Of the
# 136,704 published rows on a journey of five minutes or more, 99.4% fall
# between 1 and 100 pence a minute, the median is 34, and the 1st and 99th
# percentiles are 1.85 and 200. The bounds are set outside those percentiles
# with room to spare, so ordinary fare restructuring does not trip the gate and
# a price that is not a price does.
RATE_FLOOR_PENCE_PER_MINUTE = 0.5
RATE_CEILING_PENCE_PER_MINUTE = 600.0

# A journey shorter than this is priced at a floor rather than at a rate, so
# dividing by its minutes measures the floor and not the fare. The real feed
# holds 10,274 such rows, the dearest of them an ordinary GBP 14.00 Anytime
# Day Return across one minute at 1,400 pence a minute, which is a correct
# price and would be the loudest offender in the run. The count of excluded
# rows is printed so this is never a silent narrowing.
MIN_JOURNEY_MINUTES = 5

# Above this many offenders the run prints the codes and counts rather than
# every row, because a gate that fails on every fare is not telling anyone
# anything new. The families are always printed in full.
NAMED_LIMIT = 20


def fastest_by_pair(timetable: TimetableDb, day: date) -> dict[tuple[str, str], int]:
    """The fastest journey in either direction for every connected pair.

    Built from the departure index rather than by asking for a journey per
    fare, because the feed holds 420,884 publishable fare rows and one search
    per row would dominate the run. A pair with no service at all is absent
    from the result and its fares are not measured: there is no journey to
    price them against, and inventing a duration would invent a rate.
    """
    timetable._ensure_indexes(day)
    fastest: dict[tuple[str, str], int] = {}
    for origin_crs, entries in timetable._departures.items():
        for departure, schedule_index, stop_index in entries:
            schedule = timetable.schedules[schedule_index]
            chain = timetable._schedule_crs[schedule_index]
            for later in range(stop_index + 1, len(chain)):
                destination = chain[later]
                if destination is None or destination == origin_crs:
                    continue
                arrival = schedule.stops[later].alight
                if arrival is None:
                    continue
                duration = arrival + (1440 if arrival < departure else 0) - departure
                if duration <= 0:
                    continue
                # A return is timed as well as an outward, and a fare quoted
                # for a return buys the journey either way.
                for pair in ((origin_crs, destination), (destination, origin_crs)):
                    if duration < fastest.get(pair, 10**9):
                        fastest[pair] = duration
    return fastest


def published_rows(
    fares: FaresDb, fastest: dict[tuple[str, str], int], day: date
) -> list[dict[str, object]]:
    """Every row the page would publish that has a journey to measure against."""
    rows: list[dict[str, object]] = []
    queries = (
        fares.page_single_destinations_within,
        fares.page_destinations_within,
        fares.publishable_destinations_within,
    )
    for origin in sorted(fares.locations_by_crs):
        if origin not in fares.nlcs_by_crs:
            continue
        seen: set[tuple[str, str, str]] = set()
        for query in queries:
            try:
                found = query(origin, EVERYTHING_PENCE, adults=1, day=day)
            except ValueError:
                # The publishable selector refuses to run without a clean
                # restriction file. Its rows are covered by the other two, and
                # a missing restriction file is the feed audit's finding.
                continue
            for row in found:
                minutes = fastest.get((origin, row.crs))
                if not minutes or row.best_pence <= 0:
                    continue
                key = (origin, row.crs, row.ticket_code)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "rate": row.best_pence / minutes,
                        "pence": row.best_pence,
                        "minutes": minutes,
                        "from": origin,
                        "to": row.crs,
                        "ticket": row.ticket_code,
                        "name": row.ticket_name,
                    }
                )
    return rows


def outside_band(
    rows: list[dict[str, object]],
    *,
    floor: float = RATE_FLOOR_PENCE_PER_MINUTE,
    ceiling: float = RATE_CEILING_PENCE_PER_MINUTE,
) -> list[dict[str, object]]:
    """The rows outside the band.

    No exception list, and that is the point. This gate once carried five
    reviewed codes, which meant a family that reached a page for an implausible
    rate was excused rather than removed. Those five are now excluded by the
    page selectors instead, so none of them is published, so none reaches here
    and nothing needs excusing. A baseline that cannot fire is a loophole the
    next family would hide behind.
    """
    return [
        row
        for row in rows
        if row["minutes"] >= MIN_JOURNEY_MINUTES
        and not (floor <= float(row["rate"]) <= ceiling)
    ]


def describe(offenders: list[dict[str, object]], floor: float, ceiling: float) -> str:
    """A bounded, readable report: the families in full, then sample rows."""
    families: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in offenders:
        families[str(row["ticket"])].append(row)
    lines = [
        f"{len(offenders):,} published fares fall outside the reviewed band of "
        f"{floor} to {ceiling} pence per minute, in {len(families)} ticket codes."
    ]
    for code, group in sorted(families.items(), key=lambda item: -len(item[1])):
        sample = group[0]
        side = "below" if float(sample["rate"]) < floor else "above"
        lines.append(f"  {code} {sample['name']!r}, {len(group):,} rows, {side} the band")
        lines.append(
            f"    measured {float(sample['rate']):.2f}p/min for "
            f"GBP {int(sample['pence']) / 100:.2f} over {sample['minutes']} minutes"
            f" ({sample['from']} to {sample['to']})"
        )
    for code, group in sorted(families.items(), key=lambda item: -len(item[1])):
        if len(group) <= NAMED_LIMIT:
            continue
        for row in group[:NAMED_LIMIT]:
            lines.append(
                f"    {code} {row['from']}->{row['to']} "
                f"{float(row['rate']):.2f}p/min GBP {int(row['pence']) / 100:.2f}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed", type=Path, default=ROOT / "feeds" / "fares" / "dtd-fares.zip")
    parser.add_argument("--timetable", type=Path, default=ROOT / "feeds" / "timetable")
    parser.add_argument("--day", default="2026-10-03", help="the date the rates are measured on")
    parser.add_argument(
        "--report",
        action="store_true",
        help="print every rate outside the band, which is also what a failure prints",
    )
    parser.add_argument("--floor", type=float, default=RATE_FLOOR_PENCE_PER_MINUTE)
    parser.add_argument("--ceiling", type=float, default=RATE_CEILING_PENCE_PER_MINUTE)
    args = parser.parse_args(argv)

    if not args.feed.exists() or not args.timetable.exists():
        print(
            f"error: no feed at {args.feed} or no timetable at {args.timetable}; "
            "this check needs both and will not guess",
            file=sys.stderr,
        )
        return 2
    try:
        day = date.fromisoformat(args.day)
    except ValueError as error:
        print(f"error: --day {args.day!r} is not a date: {error}", file=sys.stderr)
        return 2

    fares = FaresDb().load_feed(args.feed)
    timetable = TimetableDb().load_feed(args.timetable)
    fastest = fastest_by_pair(timetable, day)
    rows = published_rows(fares, fastest, day)

    measured = [row for row in rows if row["minutes"] >= MIN_JOURNEY_MINUTES]
    print(
        f"published rows with a journey {len(rows):,}, of which measured against "
        f"the band {len(measured):,}; {len(rows) - len(measured):,} pairs are under "
        f"{MIN_JOURNEY_MINUTES} minutes and are excluded"
    )
    if measured:
        rates = sorted(float(row["rate"]) for row in measured)
        middle = rates[len(rates) // 2]
        print(f"  median {middle:.2f} pence per minute, from {rates[0]:.2f} to {rates[-1]:.2f}")

    offenders = outside_band(rows, floor=args.floor, ceiling=args.ceiling)
    if args.report:
        print(describe(offenders, args.floor, args.ceiling) if offenders else "no fare is outside the band")
    if not offenders:
        print("every published fare is a plausible price for its journey")
        return 0

    print(describe(offenders, args.floor, args.ceiling), file=sys.stderr)
    print(
        "error: refusing to publish with a fare whose price per minute of journey is "
        "not a price. Add a reviewed code to atoc_fares, or investigate the fare.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())