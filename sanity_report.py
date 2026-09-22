"""Question a budget count before believing it.

The Stage 1 decision rests on one number: how many destinations are reachable
from Grantham for under £20. Nobody can check that by hand, so this report asks
the questions that decide whether the number is a finding or an artefact.

    python sanity_report.py --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20

It answers four things:

1. What the count is under each reading of the budget, because "under £20" means
   a different number of destinations to one adult and to two people with a
   Two Together Railcard, and the difference is the interesting part.
2. What the count left out, by reason, because every dropped record is a
   candidate reason the number is too low.
3. Which destinations sit close enough to the line that a small data error would
   move them, and how the count moves if the budget does.
4. What looks wrong with the fares themselves: values that are not multiples of
   five pence, values far below or above anything a day return costs.

None of this makes the number correct. It makes the number arguable.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

from atoc_fares import FaresDb, Reachable, format_pence
from atoc_timetable import TimetableDb
from feed_audit import audit

TWO_TOGETHER = "Two Together"
DEFAULT_MARGIN = 0.10
FARE_FLOOR_PENCE = 50
FARE_CEILING_PENCE = 50_000
ROUNDING_STEP_PENCE = 5
SAMPLE_LIMIT = 8

# The reasons a query can drop something, with the wording the report uses.
DROPPED_REASONS = (
    "destination_has_no_station_code",
    "destination_has_no_location_record",
    "flow_with_no_fare",
    "fare_with_no_ticket_type",
    "ticket_is_not_a_standard_return",
    "fare_to_the_origin_itself",
    "fare_above_the_budget",
    "cheaper_index_already_held",
)


def count_variants(
    fares: FaresDb,
    origin_crs: str,
    budget_pence: int,
    *,
    railcard: str | None = TWO_TOGETHER,
    adults: int = 2,
) -> dict[str, int]:
    """The count under each reading of what the budget covers."""
    variants = {
        "one adult, standard fare": dict(adults=1, railcard=None, party_budget=False),
        f"one adult, {railcard}": dict(adults=1, railcard=railcard, party_budget=False),
        f"{adults} adults, standard fares": dict(adults=adults, railcard=None, party_budget=True),
        f"{adults} adults, {railcard} (party total)": dict(
            adults=adults, railcard=railcard, party_budget=True
        ),
    }
    counts: dict[str, int] = {}
    for label, options in variants.items():
        try:
            counts[label] = len(fares.destinations_within(origin_crs, budget_pence, **options))
        except KeyError:
            counts[label] = 0
    return counts


def dropped_reasons(
    fares: FaresDb, origin_crs: str, budget_pence: int
) -> tuple[dict[str, int], dict[str, int]]:
    """Why the query dropped records. Returns the reasons and the feed's own counts."""
    tally: dict[str, int] = {}
    try:
        fares.destinations_within(origin_crs, budget_pence, tally=tally)
    except KeyError:
        pass
    stats = fares.stats()
    return tally, {
        "locations_without_a_station_code": stats["locations_without_a_station_code"],
        "extra_location_codes_for_a_station": stats["extra_location_codes_for_a_station"],
        "fares_with_no_flow_record": stats["fares_with_no_flow_record"],
    }


def inside_budget(fares: FaresDb, origin_crs: str, budget_pence: int) -> list[Reachable]:
    """The destinations under the budget, or nothing if the origin is not in the feed."""
    try:
        return fares.destinations_within(origin_crs, budget_pence)
    except KeyError:
        return []


def borderline(
    inside: list[Reachable], budget_pence: int, *, margin: float = DEFAULT_MARGIN
) -> list[Reachable]:
    """Destinations inside the budget and close to it, where an error would show."""
    limit = int(budget_pence * (1 - margin))
    return [row for row in inside if row.best_pence >= limit]


def sensitivity(
    fares: FaresDb,
    origin_crs: str,
    budget_pence: int,
    *,
    fraction: float = DEFAULT_MARGIN,
    adults: int = 1,
    railcard: str | None = None,
) -> dict[str, int]:
    """How the count moves when the budget does."""
    readings = {
        "at_10_percent_less": int(budget_pence * (1 - fraction)),
        "at_budget": budget_pence,
        "at_10_percent_more": int(budget_pence * (1 + fraction)),
    }
    return {
        label: len(
            inside_budget_adults(fares, origin_crs, value, adults=adults, railcard=railcard)
        )
        for label, value in readings.items()
    }


def inside_budget_adults(
    fares: FaresDb,
    origin_crs: str,
    budget_pence: int,
    *,
    adults: int,
    railcard: str | None,
) -> list[Reachable]:
    """As inside_budget, for a party reading of the budget."""
    try:
        return fares.destinations_within(
            origin_crs, budget_pence, adults=adults, railcard=railcard, party_budget=adults > 1
        )
    except KeyError:
        return []


def fare_smells(fares: FaresDb) -> dict[str, list[str]]:
    """Fare values that no real day return would have, with samples."""
    smells: dict[str, list[str]] = {
        "below_the_floor": [],
        "above_the_ceiling": [],
        "not_a_multiple_of_five_pence": [],
    }
    for flow_id, bucket in fares.fares_by_flow.items():
        for ticket_code, fare in bucket.items():
            label = f"{flow_id}/{ticket_code} {format_pence(fare.pence)}"
            if fare.pence < FARE_FLOOR_PENCE:
                smells["below_the_floor"].append(label)
            elif fare.pence > FARE_CEILING_PENCE:
                smells["above_the_ceiling"].append(label)
            elif fare.pence % ROUNDING_STEP_PENCE:
                smells["not_a_multiple_of_five_pence"].append(label)
    return smells


def cheapest_and_dearest(inside: list[Reachable]) -> tuple[list[Reachable], list[Reachable]]:
    """The five cheapest destinations, and the dearest inside the budget."""
    return inside[:5], inside[-5:]


def build_report(
    fares: FaresDb,
    timetable: TimetableDb | None,
    origin_crs: str,
    budget_pence: int,
    *,
    adults: int = 2,
) -> dict[str, object]:
    """Everything the report prints, as data, so the tests can check it."""
    origin = fares.locations_by_crs.get(origin_crs.strip().upper())
    tally, feed_counts = dropped_reasons(fares, origin_crs, budget_pence)
    priced = inside_budget(fares, origin_crs, budget_pence)
    cheapest, dearest = cheapest_and_dearest(priced)

    served: int | None = None
    unserved: list[str] = []
    if timetable is not None and origin is not None:
        for row in priced:
            if timetable.best_journey(origin.crs, row.crs) is None:
                unserved.append(row.crs)
        served = len(priced) - len(unserved)

    agreement = audit(fares, timetable) if timetable is not None else None
    return {
        "origin": origin.crs if origin else origin_crs,
        "origin_name": origin.name if origin else "",
        "budget_pence": budget_pence,
        "variants": count_variants(fares, origin_crs, budget_pence, adults=adults),
        "dropped": tally,
        "feed_counts": feed_counts,
        "borderline": [row.crs for row in borderline(priced, budget_pence)],
        "sensitivity": sensitivity(fares, origin_crs, budget_pence),
        "smells": fare_smells(fares),
        "cheapest": [(row.crs, row.station, row.best_pence) for row in cheapest],
        "dearest_inside": [(row.crs, row.station, row.best_pence) for row in dearest],
        "priced": len(priced),
        "served": served,
        "unserved": unserved,
        "agreement": agreement,
        "files": fares.report.files_read,
        "counts": fares.stats(),
    }


def print_report(data: dict[str, object], limit: int = SAMPLE_LIMIT) -> None:
    budget = format_pence(int(data["budget_pence"]))
    print("Count sanity report")
    print(f"  origin {data['origin']} {data['origin_name']}, budget {budget}")
    counts = data["counts"]
    print(
        f"  read {len(data['files'])} file(s), {counts['stations']} stations, "
        f"{counts['flows']} flows, {counts['fares']} fares, {counts['ticket_types']} ticket types"
    )
    print(f"  {', '.join(data['files']) or 'nothing'}")

    print(f"The count under each reading of {budget}")
    for label, count in data["variants"].items():
        print(f"  {label:<44}{count:>5}")

    print("What the count left out")
    dropped = data["dropped"]
    for reason in DROPPED_REASONS:
        if dropped.get(reason):
            print(f"  {reason:<44}{dropped[reason]:>5}")
    for label, value in data["feed_counts"].items():
        if value:
            print(f"  {label:<44}{value:>5}")
    if not any(dropped.values()):
        print("  nothing")

    print("The numbers closest to the line")
    close = data["borderline"]
    print(f"  inside the budget and within 10% of it      {len(close):>5} {close[:limit]}")
    for label, count in data["sensitivity"].items():
        print(f"  {label:<44}{count:>5}")

    print("The fares themselves")
    cheapest = data["cheapest"]
    dearest = data["dearest_inside"]
    if cheapest:
        print(f"  cheapest  {cheapest[0][0]:<4}{cheapest[0][1]:<22}{format_pence(cheapest[0][2]):>9}")
    if dearest:
        print(
            f"  dearest inside the budget  {dearest[-1][0]:<4}{dearest[-1][1]:<22}"
            f"{format_pence(dearest[-1][2]):>9}"
        )
    for label, samples in data["smells"].items():
        print(f"  {label:<44}{len(samples):>5} {samples[:3]}")

    if data["served"] is not None:
        print("Where the two feeds disagree")
        print(f"  priced with a service in the timetable      {data['served']:>5}")
        print(f"  priced with no service in the timetable     {len(data['unserved']):>5} {data['unserved'][:limit]}")
        agreement = data["agreement"]
        print(f"  a fare and no timetable entry               {agreement['stations_with_a_fare_and_no_timetable_entry']:>5}")
        print(f"  a train and no fare entry                   {agreement['stations_with_a_train_and_no_fare_entry']:>5}")
        print(f"  unresolved TIPLOC codes                     {agreement['unresolved_tiplocs']:>5}")

    print("Read the dropped reasons and the file list before the count. A count that")
    print("is too low looks exactly like a count, and this report is the only thing that")
    print("tells the difference.")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Question a budget count before believing it.")
    parser.add_argument("--feed", required=True, help="fares feed folder or zip")
    parser.add_argument("--timetable", default=None, help="CIF timetable feed folder or zip")
    parser.add_argument(
        "--origin",
        default="GRN",
        help="origin CRS code. Grantham's real code is GRA; the synthetic feed invents GRN",
    )
    parser.add_argument("--budget", type=float, default=20.0, help="budget in pounds")
    parser.add_argument("--adults", type=int, default=2, help="party size for the party readings")
    arguments = parser.parse_args(argv)

    for label, path in (("fares", arguments.feed), ("timetable", arguments.timetable)):
        if path and not Path(path).exists():
            print(f"{label} path {path!r} does not exist", file=sys.stderr)
            return 2

    fares = FaresDb().load_feed(arguments.feed)
    timetable = TimetableDb().load_feed(arguments.timetable) if arguments.timetable else None
    if arguments.origin.strip().upper() not in fares.locations_by_crs:
        print(
            f"origin {arguments.origin!r} not found. Files read: {fares.report.files_read}",
            file=sys.stderr,
        )
        return 2

    data = build_report(
        fares, timetable, arguments.origin, round(arguments.budget * 100), adults=arguments.adults
    )
    print_report(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
