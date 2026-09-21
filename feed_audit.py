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
from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb

SAMPLE_LIMIT = 10


def audit(fares: FaresDb, timetable: TimetableDb) -> dict[str, object]:
    """Collect the coverage picture a first real run needs."""
    fare_crs = set(fares.locations_by_crs)
    timetable_crs = {station.crs for station in timetable.stations_by_tiploc.values() if station.crs}
    timetable_crs |= set(timetable.cif_crs_by_tiploc.values())

    used_tiplocs = {stop.tiploc for schedule in timetable.schedules for stop in schedule.stops}
    unresolved = sorted(tiploc for tiploc in used_tiplocs if timetable.crs_for_tiploc(tiploc) is None)

    stp_indicators: dict[str, int] = {}
    service_days: dict[str, int] = {}
    for schedule in timetable.schedules:
        stp = schedule.stp_indicator or "?"
        stp_indicators[stp] = stp_indicators.get(stp, 0) + 1
        days = schedule.days or "?"
        service_days[days] = service_days.get(days, 0) + 1

    date_starts = sorted(filter(None, (schedule.date_from for schedule in timetable.schedules)))
    date_ends = sorted(filter(None, (schedule.date_to for schedule in timetable.schedules)))

    return {
        "fares": fares.stats(),
        "timetable": timetable.stats(),
        "fares_report": fares.report.summary(),
        "timetable_report": timetable.report.summary(),
        "fares_files": sorted(fares.report.files_read),
        "timetable_files": sorted(timetable.report.files_read),
        "rejected_examples": fares.report.skipped_examples + timetable.report.skipped_examples,
        "stations_with_a_fare_and_no_timetable_entry": len(fare_crs - timetable_crs),
        "stations_with_a_train_and_no_fare_entry": len(timetable_crs - fare_crs),
        "sample_fare_only_stations": sorted(fare_crs - timetable_crs)[:SAMPLE_LIMIT],
        "sample_timetable_only_stations": sorted(timetable_crs - fare_crs)[:SAMPLE_LIMIT],
        "unresolved_tiplocs": len(unresolved),
        "sample_unresolved_tiplocs": unresolved[:SAMPLE_LIMIT],
        "schedule_dates_from": date_starts[0] if date_starts else "",
        "schedule_dates_to": date_ends[-1] if date_ends else "",
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
        f"  lines {fares_report['lines']}, handled {fares_report['parsed']}, "
        f"rejected {fares_report['skipped']}, encoding fallbacks {fares_report['encoding_fallbacks']}"
    )

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

    print("Coverage between the two feeds")
    print(f"  a fare and no timetable entry: {report['stations_with_a_fare_and_no_timetable_entry']}")
    print(f"  a train and no fare entry: {report['stations_with_a_train_and_no_fare_entry']}")
    print(f"  unresolved TIPLOC codes: {report['unresolved_tiplocs']}")
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


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Report what the feed parsers read.")
    parser.add_argument("--feed", required=True, help="fares feed folder or zip")
    parser.add_argument("--timetable", required=True, help="CIF timetable feed folder or zip")
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
