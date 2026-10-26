"""Report what the parsers actually read, so the first real run is diagnosable.

Usage:
    python feed_audit.py --feed feeds/fares --timetable feeds/timetable

The first run against the real feeds happens once. This command turns that run
into a report instead of a guess: what each file contributed, what was rejected,
and where the two feeds disagree about the network.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.timetable.atoc_timetable import TimetableDb
from trainbudget.feeds.feeds_cli import add_feed_args

SAMPLE_LIMIT = 10


def audit(
    fares: FaresDb, timetable: TimetableDb, *, day: date | None = None
) -> dict[str, object]:
    """Collect the coverage picture a first real run needs."""
    fare_crs = set(fares.locations_by_crs)
    timetable_crs = {station.crs for station in timetable.stations_by_tiploc.values() if station.crs}
    timetable_crs |= set(timetable.cif_crs_by_tiploc.values())

    used_tiplocs = timetable.used_tiplocs()
    unresolved = sorted(
        tiploc for tiploc in used_tiplocs if timetable.crs_for_tiploc(tiploc) is None
    )
    unresolved_categories = Counter(timetable.tiploc_resolution(tiploc) for tiploc in unresolved)
    normalized_samples = [
        f"{canonical} <- {sorted(raws)[0]!r}"
        for canonical, raws in sorted(timetable.tiploc_variants.items())[:SAMPLE_LIMIT]
    ]

    stp_indicators: dict[str, int] = {}
    service_days: dict[str, int] = {}
    for schedule in timetable.schedules:
        stp = schedule.stp_indicator or "?"
        stp_indicators[stp] = stp_indicators.get(stp, 0) + 1
        days = schedule.days or "?"
        service_days[days] = service_days.get(days, 0) + 1

    window = timetable.service_window()

    return {
        "fares": fares.stats(),
        "fare_coverage": fares.fare_coverage_audit(day=day),
        "timetable": timetable.stats(),
        "fares_report": fares.report.summary(),
        "timetable_report": timetable.report.summary(),
        "fares_files": sorted(fares.report.files_read),
        "timetable_files": sorted(timetable.report.files_read),
        "rejected_examples": fares.report.skipped_examples + timetable.report.skipped_examples,
        "unopened_files": fares.report.skipped_files + timetable.report.skipped_files,
        # A reviewed settlement-fallback code the feed does not carry: a list
        # going stale, not a file left unread, so it is reported beside the
        # unopened files rather than inside them.
        "reviewed_codes_absent": fares.report.reviewed_codes_absent,
        "reviewed_codes_redundant": fares.report.reviewed_codes_redundant,
        "stations_with_a_fare_and_no_timetable_entry": len(fare_crs - timetable_crs),
        "stations_with_a_train_and_no_fare_entry": len(timetable_crs - fare_crs),
        "sample_fare_only_stations": sorted(fare_crs - timetable_crs)[:SAMPLE_LIMIT],
        "sample_timetable_only_stations": sorted(timetable_crs - fare_crs)[:SAMPLE_LIMIT],
        "used_tiplocs": len(used_tiplocs),
        "unresolved_tiplocs": len(unresolved),
        "unresolved_tiploc_categories": dict(sorted(unresolved_categories.items())),
        "sample_unresolved_tiplocs": unresolved[:SAMPLE_LIMIT],
        "normalized_tiplocs": timetable.normalized_tiploc_count(),
        "sample_tiploc_normalizations": normalized_samples,
        "restrictions": fares.restrictions.summary(),
        "schedule_dates_from": window[0],
        "schedule_dates_to": window[1],
        "stp_indicators": stp_indicators,
        "service_day_patterns": service_days,
    }


def print_audit(report: dict[str, object], limit: int = SAMPLE_LIMIT) -> None:
    fares = report["fares"]
    timetable = report["timetable"]
    fares_report = report["fares_report"]
    timetable_report = report["timetable_report"]

    print("Fares feed")
    print(f"  files {fares_report['files']}: {', '.join(report['fares_files']) or 'none'}")
    print(
        f"  stations {fares['stations']}, flows {fares['flows']}, fares {fares['fares']}, "
        f"ticket types {fares['ticket_types']}, railcards {fares['railcards']}"
    )
    print(
        f"  location codes with no station code {fares['locations_without_a_station_code']}, "
        f"extra codes for one station {fares['extra_location_codes_for_a_station']}, "
        f"fares with no flow {fares['fares_with_no_flow_record']}"
    )
    print(
        f"  lines {fares_report['lines']}, handled {fares_report['parsed']}, "
        f"rejected {fares_report['skipped']}, encoding fallbacks {fares_report['encoding_fallbacks']}"
    )
    restrictions = report["restrictions"]
    print(
        f"  restrictions: files {restrictions['files']}, records {restrictions['records']}, "
        f"codes {restrictions['restriction_codes']}, railcard codes {restrictions['railcard_codes']}, "
        f"rejected {restrictions['rejected']}"
    )
    if restrictions["unknown_types"]:
        print(f"  unknown restriction record types: {restrictions['unknown_types']}")

    print("Timetable feed")
    print(f"  files {timetable_report['files']}: {', '.join(report['timetable_files']) or 'none'}")
    print(
        f"  stations {timetable['stations']}, schedules {timetable['schedules']}, "
        f"calling points {timetable['calling_points']}"
    )
    print(
        f"  lines {timetable_report['lines']}, handled {timetable_report['parsed']}, "
        f"rejected {timetable_report['skipped']}, encoding fallbacks {timetable_report['encoding_fallbacks']}"
    )
    print(
        f"  dates {report['schedule_dates_from'] or 'unknown'} to {report['schedule_dates_to'] or 'unknown'}, "
        f"stp {report['stp_indicators']}, days {report['service_day_patterns']}"
    )

    coverage = report["fare_coverage"]
    print("Fare location coverage")
    print(
        f"  fare groups read {coverage['groupCodes']}, "
        f"group fare flows {coverage['groupFareFlows']}, "
        f"stations priced only through a group {coverage['stationsPricedOnlyThroughGroup']}, "
        f"London Terminals flows left unpriced {coverage['unexpandedGroupFareFlows']}"
    )
    print(
        f"  station clusters read {coverage['clusterCodes']}, "
        f"cluster memberships {coverage['clusterMemberships']}, "
        f"stations in clusters {coverage['stationsInClusters']}, "
        f"cluster fare flows {coverage['clusterFareFlows']}"
    )
    print(
        f"  stations with multiple location codes {coverage['stationsWithMultipleLocationCodes']}, "
        f"fare flows with missing locations {coverage['fareFlowsWithMissingLocation']}, "
        f"with no station code {coverage['fareFlowsWithNoStationCode']}"
    )
    for sample in coverage["sampleStationsPricedOnlyThroughGroup"][:limit]:
        print(
            f"  group {sample['groupNlc']} prices {sample['crs']} "
            f"{sample['name']} ({sample['flowCount']} flows)"
        )
    for sample in coverage["sampleStationsWithMultipleLocationCodes"][:limit]:
        print(
            f"  location aliases for {sample['crs']} {sample['name']}: "
            f"{', '.join(sample['nlcs'])}"
        )
    for sample in coverage["sampleFareFlowsWithUnmappedDestinations"][:limit]:
        print(
            f"  unmapped fare flow {sample['flowId']} -> "
            f"{sample['destinationNlc']} ({sample['label']})"
        )

    print("Coverage between the two feeds")
    print(f"  a fare and no timetable entry: {report['stations_with_a_fare_and_no_timetable_entry']}")
    print(f"  a train and no fare entry: {report['stations_with_a_train_and_no_fare_entry']}")
    print(f"  used TIPLOC codes: {report['used_tiplocs']}")
    print(f"  unresolved TIPLOC codes: {report['unresolved_tiplocs']}")
    categories = report["unresolved_tiploc_categories"]
    if categories:
        detail = ", ".join(f"{name} {count}" for name, count in categories.items())
        print(f"  unresolved TIPLOC categories: {detail}")
    print(f"  TIPLOCs normalised from a padded raw value: {report['normalized_tiplocs']}")
    for sample in report["sample_tiploc_normalizations"]:
        print(f"  normalised TIPLOC: {sample}")
    for label in (
        "sample_fare_only_stations",
        "sample_timetable_only_stations",
        "sample_unresolved_tiplocs",
    ):
        sample = report[label][:limit]
        if sample:
            print(f"  {label}: {', '.join(str(item) for item in sample)}")

    examples = report["rejected_examples"]
    if examples:
        print("Rejected records")
        for example in examples:
            print(f"  {example}")

    unopened = report["unopened_files"]
    if unopened:
        print("Files not opened")
        for entry in unopened:
            print(f"  {entry}")

    dead_codes = report["reviewed_codes_absent"]
    if dead_codes:
        print(
            f"Reviewed settlement codes matching no station ({len(dead_codes)}); "
            "each is a class that will not be applied to anything:"
        )
        for crs in dead_codes[:limit]:
            print(f"  {crs}")
        if len(dead_codes) > limit:
            print(f"  ... and {len(dead_codes) - limit} more")

    redundant_codes = report["reviewed_codes_redundant"]
    if redundant_codes:
        print(
            f"Reviewed settlement codes the workbook already covers "
            f"({len(redundant_codes)}); each is a fallback for a station nothing "
            "was missing, and would apply only if the name match ever missed:"
        )
        for crs in redundant_codes[:limit]:
            print(f"  {crs}")
        if len(redundant_codes) > limit:
            print(f"  ... and {len(redundant_codes) - limit} more")

    print("Read the rejected count and the unopened files before the totals: a record")
    print("that never loaded is a destination that never appears.")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Report what the feed parsers read.")
    add_feed_args(parser, timetable_required=True)
    arguments = parser.parse_args(argv)

    for label, path in (("fares", arguments.feed), ("timetable", arguments.timetable)):
        if not Path(path).exists():
            print(f"{label} path {path!r} does not exist", file=sys.stderr)
            return 2

    fares = FaresDb().load_feed(arguments.feed)
    timetable = TimetableDb().load_feed(arguments.timetable)
    print_audit(audit(fares, timetable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
