"""Tests for the unsourced-destination report.

The report exists to make a silent gap visible, so the tests are about what it
names, what it leaves out, and when it refuses a build. It reports and never
classifies: no test here expects a station to be given a band.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest import mock

import destination_coverage
from destination_coverage import UNSOURCED, UnsourcedReport


def row(crs: str, name: str, kind: str = "town") -> dict:
    return {"crs": crs, "name": name, "destinationType": kind}


class ReportTest(unittest.TestCase):
    def test_a_classified_destination_is_not_reported(self) -> None:
        report = UnsourcedReport()
        report.from_payload({"destinations": [row("LCN", "LINCOLN")]})
        self.assertEqual(len(report), 0)
        self.assertFalse(report)
        self.assertEqual(report.message(), "")

    def test_an_unsourced_destination_is_named_with_its_station(self) -> None:
        report = UnsourcedReport()
        report.from_payload(
            {"origin": {"crs": "GRA"}, "destinations": [row("DOR", "DORE & TOTLEY", UNSOURCED)]}
        )
        self.assertEqual(len(report), 1)
        self.assertIn("DOR DORE & TOTLEY", report.message())
        self.assertIn("1 priced station has no settlement class", report.message())

    def test_all_three_ticket_modes_are_read(self) -> None:
        # The page offers the same filters for each mode, so a station unsourced
        # in one of them is unsourced on the page.
        report = UnsourcedReport()
        report.from_payload(
            {
                "origin": {"crs": "GRA"},
                "destinations": [],
                "singleDestinations": [row("ELN", "ELTON", UNSOURCED)],
                "anytimeDestinations": [row("ELO", "ELTON & ORSTON", UNSOURCED)],
            }
        )
        self.assertEqual({code for code, _ in report.stations()}, {"ELN", "ELO"})

    def test_a_station_met_from_many_origins_is_named_once(self) -> None:
        report = UnsourcedReport()
        for origin in ("GRA", "NOT", "LCN", "LCN"):
            report.from_payload(
                {"origin": {"crs": origin}, "destinations": [row("DOR", "DORE & TOTLEY", UNSOURCED)]}
            )
        self.assertEqual(len(report), 1)
        self.assertIn("from 3 origins", report.message())

    def test_a_blank_code_is_dropped_rather_than_invented(self) -> None:
        report = UnsourcedReport()
        report.note("", "NOWHERE", "GRA")
        self.assertEqual(len(report), 0)

    def test_the_summary_is_bounded_and_says_how_many_it_left_out(self) -> None:
        report = UnsourcedReport()
        for number in range(destination_coverage.NAMED_LIMIT + 5):
            report.note(f"X{number:02d}", f"STATION {number}", "GRA")
        message = report.message()
        self.assertIn("and 5 more", message)
        self.assertIn("X00", message, "the first named station is still named")
        self.assertNotIn("X24", message, "the ones past the limit are counted, not listed")

    def test_a_malformed_payload_does_not_crash_the_report(self) -> None:
        report = UnsourcedReport()
        report.from_payload({"destinations": None, "singleDestinations": ["not a row"]})
        self.assertEqual(len(report), 0)

    def test_feed_rows_are_classified_by_the_feed(self) -> None:
        fares = mock.Mock()
        fares.destination_type.side_effect = lambda crs: "other" if crs == "DOR" else "town"
        rows = [mock.Mock(crs="DOR", station="DORE & TOTLEY"), mock.Mock(crs="LCN", station="LINCOLN")]
        report = UnsourcedReport()
        self.assertEqual(report.note_fares_rows(fares, rows, "GRA"), 1)
        self.assertEqual([code for code, _ in report.stations()], ["DOR"])


class ExitCodeTest(unittest.TestCase):
    def test_a_clean_build_continues(self) -> None:
        self.assertEqual(UnsourcedReport().exit_code(True), 0)

    def test_a_gap_is_a_warning_by_default(self) -> None:
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            report.report()
            self.assertEqual(report.exit_code(False), 0)
        self.assertIn("warning:", stderr.getvalue())
        self.assertIn("DOR", stderr.getvalue())

    def test_the_strict_flag_refuses_the_build_and_says_what_to_do(self) -> None:
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        report.note("RDF", "RADCLIFFE ON TRT")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(report.exit_code(True), 2)
        message = stderr.getvalue()
        self.assertIn("refusing to publish", message)
        self.assertIn("2 unsourced priced destinations", message)
        self.assertIn("REVIEWED_SETTLEMENT_FALLBACKS", message)

    def test_a_single_gap_is_not_written_in_the_plural(self) -> None:
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            report.exit_code(True)
        self.assertIn("1 unsourced priced destination ", stderr.getvalue())


class MainTest(unittest.TestCase):
    def test_an_origin_the_feed_does_not_carry_is_named(self) -> None:
        fares = mock.Mock()
        fares.locations_by_crs = {"GRA": mock.Mock()}
        with mock.patch.object(destination_coverage, "FaresDb") as db:
            db.return_value.load_feed.return_value = fares
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = destination_coverage.main(["--origin", "NOPE"])
        self.assertEqual(code, 2)
        self.assertIn("NOPE is not in this feed", stderr.getvalue())

    def test_a_run_over_a_clean_feed_says_nothing(self) -> None:
        fares = mock.Mock()
        fares.locations_by_crs = {"GRA": mock.Mock()}
        fares.publishable_destinations_within.return_value = [mock.Mock(crs="LCN", station="LINCOLN")]
        fares.destination_type.return_value = "town"
        with mock.patch.object(destination_coverage, "FaresDb") as db:
            db.return_value.load_feed.return_value = fares
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = destination_coverage.main(["--fail-on-unsourced"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
