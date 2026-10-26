"""Tests for the feed-change report.

The report is read by a person deciding whether a new download goes out, so
almost every test here is about a way it could lie. A move that clears neither
bar is not a finding. A fare the feed renumbered between downloads is not a
removal. A fare with no flow record cannot be compared to anything, so it is
counted rather than quietly dropped -- dropped, it would appear as a removal
that never happened. A figure that did not move must not be reported as having
moved, because "moved from £1.00 to £1.00" is the sentence that teaches a
reader to stop believing the rest of the report.

The fixtures are written by hand rather than by the synthetic-feed generator, so
a change to that generator cannot quietly change what these tests claim. The
record layouts come from the reader that has to read them: a 73-column LOC, a
49-column flow and a 22-column fare.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from trainbudget.fares.atoc_fares import Fare, Flow, FaresDb, Location, TicketType
from trainbudget.timetable.atoc_timetable import TimetableDb
from tools.feed_change_report import (
    ChangeReport,
    _is_material,
    compare,
    coverage_by_origin,
    fare_lines,
    freshness,
    main,
    render,
)

LOC_WIDTH = 73
FLOW_WIDTH = 49
TICKET_WIDTH = 22
CRLF = "\r\n"


def _pad(value: str, width: int) -> str:
    if len(value) > width:
        raise ValueError(f"{value!r} does not fit in {width} columns")
    return value.ljust(width)


def _location(nlc: str, name: str, crs: str) -> str:
    """One LOC record, the layout ``atoc_fares`` slices."""
    return (
        "A"  # update marker
        "L"  # record type
        + _pad("0000000", 7)  # uic code
        + _pad("", 8)  # end date
        + _pad("", 8)  # start date
        + _pad("", 8)  # quote date
        + _pad("", 3)  # admin area code
        + _pad(nlc, 4)  # nlc
        + _pad(name, 16)  # description
        + _pad(crs, 3)  # crs
        + _pad("", 10)  # location attributes
        + _pad("", 4)  # group nlc
    )


def _flow(flow_id: str, origin: str, destination: str, route: str = "ROUTE") -> str:
    """One flow record, the layout ``atoc_fares`` slices."""
    return (
        "A"  # update marker
        "F"  # record type
        + _pad(origin, 4)  # origin nlc
        + _pad(destination, 4)  # destination nlc
        + _pad(route, 5)  # route code
        + _pad("", 3)  # status code
        + " "  # usage code
        + " "  # direction
        + _pad("", 8)  # end date
        + _pad("", 8)  # start date
        + _pad("", 3)  # toc
        + " "  # cross london
        + " "  # non standard discount
        + " "  # publication indicator
        + _pad(flow_id, 7)  # flow id
    )


def _fare(flow_id: str, ticket: str, pence: int, restriction: str = "00") -> str:
    """One fare record, the layout ``atoc_fares`` slices."""
    return (
        "A"  # update marker
        "T"  # record type
        + _pad(flow_id, 7)
        + _pad(ticket, 3)
        + _pad(str(pence), 8)
        + _pad(restriction, 2)
    )


def write_feed(folder: Path, locations: list[tuple[str, str, str]], records: list[str]) -> Path:
    """Write the two files a fares feed needs, plus the cache a real one has.

    The cache is copied rather than written because without it the reader looks
    for a classification source over the network: a two-line fixture took twenty
    seconds to load and the wait was all timeout. A real feed folder carries
    this file, so a fixture that does not is not the thing under test.
    """
    folder.mkdir(parents=True, exist_ok=True)
    cache = Path(__file__).resolve().parent.parent / "feeds" / "location-types.json"
    if cache.is_file():
        shutil.copy(cache, folder / "location-types.json")
    (folder / "rjtest.loc").write_bytes(
        (CRLF.join(_location(*row) for row in locations) + CRLF).encode("utf-8")
    )
    (folder / "rjtest.ffl").write_bytes((CRLF.join(records) + CRLF).encode("utf-8"))
    return folder


def snapshot(
    fares: dict[str, int], *, restriction: str = "00", flow_id: str = "FLOW001"
) -> FaresDb:
    """A fares database with one origin, one destination and the fares given.

    Built directly rather than read from a file, so a test says exactly what it
    is about. ``flow_id`` is the seam the key-stability test pulls apart.
    """
    db = FaresDb()
    db.locations_by_nlc["1000"] = Location("1000", "AAA", "ALPHA", "")
    db.locations_by_crs["AAA"] = db.locations_by_nlc["1000"]
    db.locations_by_nlc["2000"] = Location("2000", "BBB", "BRAVO", "")
    db.locations_by_crs["BBB"] = db.locations_by_nlc["2000"]
    db.flows[flow_id] = Flow(
        flow_id=flow_id,
        origin_nlc="1000",
        destination_nlc="2000",
        route_code="ROUTE",
        direction="",
        start_date=None,
        end_date=None,
    )
    bucket = db.fares_by_flow.setdefault(flow_id, {})
    for ticket, pence in fares.items():
        db.ticket_types[ticket] = TicketType(ticket, f"fare {ticket}", "2", "R", True)
        bucket[ticket] = Fare(ticket, pence, restriction)
    return db


class MaterialityTest(unittest.TestCase):
    def test_a_move_needs_both_bars_not_either(self) -> None:
        # A fifty percent rise on a fifty-pence fare is arithmetic, not news, and
        # a six percent fall on a five-pound fare is thirty pence. Either one
        # alone would call a routine download a set of findings.
        self.assertEqual(_is_material(50, 75, pct=5.0, pence=100)[0], False)
        self.assertEqual(_is_material(500, 470, pct=5.0, pence=100)[0], False)
        self.assertEqual(_is_material(5000, 5300, pct=5.0, pence=100)[0], True)

    def test_the_percentage_is_signed_so_a_fall_reads_as_a_fall(self) -> None:
        material, change = _is_material(1000, 800, pct=5.0, pence=100)
        self.assertTrue(material)
        self.assertAlmostEqual(change, -20.0)

    def test_a_fare_that_was_free_and_now_is_not_is_reported(self) -> None:
        # A percentage of zero is not a way to say a fare appeared, and a free
        # fare becoming a priced one is a change a reader would see.
        self.assertEqual(_is_material(0, 100, pct=5.0, pence=100)[0], True)


class CompareTest(unittest.TestCase):
    def compare(self, before: FaresDb, after: FaresDb) -> ChangeReport:
        return compare(before, after, previous_label="old", current_label="new")

    def test_a_price_move_is_reported_with_both_prices_and_its_percentage(self) -> None:
        report = self.compare(snapshot({"AAA": 1000}), snapshot({"AAA": 1500}))
        self.assertEqual(len(report.moves), 1)
        move = report.moves[0]
        self.assertEqual((move.before.pence, move.after.pence), (1000, 1500))
        self.assertEqual(move.delta, 500)
        self.assertAlmostEqual(move.percent, 50.0)
        self.assertEqual(move.after.origin, "ALPHA (AAA)")
        self.assertEqual(move.after.fare, "fare AAA")

    def test_a_renumbered_flow_id_is_not_a_removal_and_an_addition(self) -> None:
        # The flow id is the feed's own record key and a publisher may renumber
        # it. Keyed on it, the whole catalogue would read as gone and new.
        report = self.compare(
            snapshot({"AAA": 1000}, flow_id="FLOW001"),
            snapshot({"AAA": 1000}, flow_id="FLOW999"),
        )
        self.assertEqual(report.removed, [])
        self.assertEqual(report.added, [])
        self.assertEqual(report.moves, [])

    def test_a_fare_that_left_and_one_that_arrived_are_both_named(self) -> None:
        report = self.compare(snapshot({"AAA": 1000, "BBB": 2000}), snapshot({"AAA": 1000, "CCC": 3000}))
        self.assertEqual([fare.fare for fare in report.removed], ["fare BBB"])
        self.assertEqual([fare.fare for fare in report.added], ["fare CCC"])

    def test_a_restriction_that_changed_at_the_same_price_is_reported(self) -> None:
        # The price column looks identical, so this is the change a reader is
        # least likely to notice and the report most needs to name.
        report = self.compare(snapshot({"AAA": 1000}, restriction="00"), snapshot({"AAA": 1000}, restriction="RB"))
        self.assertEqual(report.moves, [])
        self.assertEqual(len(report.restrictions), 1)
        change = report.restrictions[0]
        self.assertEqual((change.before.restriction, change.after.restriction), ("00", "RB"))

    def test_a_fare_with_no_flow_record_is_counted_not_compared(self) -> None:
        # The orphan cannot be matched to anything, so it is counted in its own
        # line and left out of the comparison rather than being matched on
        # price. What that costs is stated rather than hidden: the same fare in
        # the other snapshot now reads as added, because on the evidence the
        # report has, it is one.
        orphan = snapshot({})
        orphan.fares_by_flow["NOSUCH"] = {"AAA": Fare("AAA", 1000, "00")}
        report = self.compare(orphan, snapshot({"AAA": 1000}))
        self.assertEqual(report.unattributed_previous, 1)
        self.assertEqual(report.unattributed_current, 0)
        self.assertEqual(report.removed, [])
        self.assertEqual([fare.fare for fare in report.added], ["fare AAA"])
        self.assertIn("no flow record", render(report))

    def test_moves_are_ordered_by_size_not_by_the_order_the_feed_kept_them_in(self) -> None:
        report = self.compare(
            snapshot({"AAA": 10000, "BBB": 10000, "CCC": 10000}),
            snapshot({"AAA": 10500, "BBB": 12000, "CCC": 11100}),
        )
        self.assertEqual([move.after.fare for move in report.moves], ["fare BBB", "fare CCC", "fare AAA"])

    def test_the_cheapest_and_dearest_are_read_from_the_whole_feed(self) -> None:
        report = self.compare(snapshot({"AAA": 1000, "BBB": 9000}), snapshot({"AAA": 800, "BBB": 9000}))
        self.assertEqual(report.current_cheapest, ("ALPHA (AAA) to BRAVO (BBB)", 800))
        self.assertEqual(report.current_dearest, ("ALPHA (AAA) to BRAVO (BBB)", 9000))


class CoverageTest(unittest.TestCase):
    def test_a_station_that_lost_a_destination_is_reported_as_coverage(self) -> None:
        before = snapshot({"AAA": 1000})
        after = snapshot({})
        report = compare(before, after, previous_label="old", current_label="new")
        self.assertEqual(len(report.coverage), 1)
        change = report.coverage[0]
        self.assertEqual(change.origin, "ALPHA (AAA)")
        self.assertEqual(change.lost, ("BBB",))
        self.assertEqual(change.gained, ())

    def test_a_station_that_priced_the_same_destinations_is_not_reported(self) -> None:
        report = compare(snapshot({"AAA": 1000}), snapshot({"AAA": 1000}), previous_label="old", current_label="new")
        self.assertEqual(report.coverage, [])

    def test_the_coverage_key_is_the_station_code_where_the_feed_carries_one(self) -> None:
        db = snapshot({"AAA": 1000})
        self.assertEqual(set(coverage_by_origin(db)), {"AAA"})


class RenderTest(unittest.TestCase):
    def test_a_figure_that_did_not_move_is_never_reported_as_having_moved(self) -> None:
        report = compare(snapshot({"AAA": 1000}), snapshot({"AAA": 1000}), previous_label="old", current_label="new")
        text = render(report)
        self.assertIn("held at £10.00", text)
        self.assertNotIn("moved from £10.00 to £10.00", text)

    def test_the_move_column_reads_as_a_percentage_and_not_as_pounds(self) -> None:
        # It printed the difference in pounds under a percent sign: £5.00 of
        # rise on a £10.00 fare read as "+5.0%", which is a tenth of the truth.
        report = compare(snapshot({"AAA": 1000}), snapshot({"AAA": 1500}), previous_label="old", current_label="new")
        self.assertIn("+50.0%", render(report))
        self.assertNotIn("+5.0%", render(report))

    def test_a_single_move_does_not_announce_a_ranking_of_one(self) -> None:
        report = compare(snapshot({"AAA": 1000}), snapshot({"AAA": 1500}), previous_label="old", current_label="new")
        self.assertNotIn("largest of 1", render(report))

    def test_the_report_names_what_it_read(self) -> None:
        # A comparison that silently skipped a file is a report about half a
        # feed, and the reader cannot see that from the counts.
        report = compare(snapshot({"AAA": 1000}), snapshot({"AAA": 1500}), previous_label="old", current_label="new")
        self.assertIn("old: 0 file(s)", render(report))

    def test_an_unattributed_fare_is_named_in_the_report(self) -> None:
        orphan = snapshot({})
        orphan.fares_by_flow["NOSUCH"] = {"AAA": Fare("AAA", 1000, "00")}
        text = render(compare(orphan, snapshot({"AAA": 1000}), previous_label="old", current_label="new"))
        self.assertIn("no flow record", text)
        self.assertIn("1 from old", text)


class FreshnessTest(unittest.TestCase):
    def test_the_window_is_the_earliest_and_latest_date_a_schedule_states(self) -> None:
        from trainbudget.timetable.atoc_timetable import Schedule

        timetable = TimetableDb()
        timetable.schedules = [
            Schedule("A", (), date_from="2026-10-01", date_to="2026-12-20"),
            Schedule("B", (), date_from="2026-09-01", date_to="2026-11-02"),
        ]
        item = freshness("new", timetable)
        self.assertEqual((item.earliest, item.latest), ("2026-09-01", "2026-12-20"))
        self.assertEqual(item.schedules, 2)

    def test_a_snapshot_with_no_dated_schedule_says_so_rather_than_blank(self) -> None:
        item = freshness("new", TimetableDb())
        self.assertEqual(item.earliest, "")
        self.assertIn("no schedule in this snapshot carries a validity window", item.note)


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.addCleanup(self.folder.cleanup)

    def feed(self, name: str, pence: int) -> Path:
        return write_feed(
            self.root / name,
            [("1000", "ALPHA", "AAA"), ("2000", "BRAVO", "BBB")],
            [
                _flow("FLOW001", "1000", "2000"),
                _fare("FLOW001", "AAA", pence),
            ],
        )

    def run_main(self, *arguments: str) -> tuple[int, str, str]:
        import contextlib
        import io

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(arguments))
        return code, out.getvalue(), err.getvalue()

    def test_a_snapshot_that_is_not_there_is_refused_before_anything_is_read(self) -> None:
        code, _, err = self.run_main("--feed", str(self.feed("new", 1000)), "--previous-feed", str(self.root / "gone"))
        self.assertEqual(code, 2)
        self.assertIn("gone", err)

    def test_the_two_snapshots_are_compared_and_printed(self) -> None:
        code, out, _ = self.run_main(
            "--previous-feed", str(self.feed("old", 1000)), "--feed", str(self.feed("new", 1500))
        )
        self.assertEqual(code, 0)
        self.assertIn("# Feed change report", out)
        self.assertIn("+50.0%", out)

    def test_the_refusal_is_opt_in_and_only_fires_on_a_material_move(self) -> None:
        quiet = self.run_main(
            "--previous-feed", str(self.feed("old", 1000)),
            "--feed", str(self.feed("new", 1001)),
            "--fail-on-material",
        )
        self.assertEqual(quiet[0], 0)
        loud = self.run_main(
            "--previous-feed", str(self.feed("old", 1000)),
            "--feed", str(self.feed("new", 1500)),
            "--fail-on-material",
        )
        self.assertEqual(loud[0], 1)
        self.assertIn("1 fare(s) moved", loud[2])

    def test_the_json_written_is_the_report_the_run_printed(self) -> None:
        target = self.root / "change.json"
        code, _, _ = self.run_main(
            "--previous-feed", str(self.feed("old", 1000)),
            "--feed", str(self.feed("new", 1500)),
            "--json", str(target),
        )
        self.assertEqual(code, 0)
        written = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(written["current"], str(self.root / "new"))
        self.assertEqual(len(written["moves"]), 1)
        self.assertEqual(written["moves"][0]["now"], 1500)


class KeyTest(unittest.TestCase):
    def test_every_fare_in_the_database_is_keyed_by_what_identifies_it(self) -> None:
        lines, unattributed = fare_lines(snapshot({"AAA": 1000, "BBB": 2000}))
        self.assertEqual(unattributed, 0)
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            {line.fare for line in lines.values()}, {"fare AAA", "fare BBB"}
        )


if __name__ == "__main__":
    unittest.main()
