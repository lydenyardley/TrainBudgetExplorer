"""Tests for the report that questions a budget count.

The numbers here are the fixture's, which is the point: the report is only worth
reading if each of its lines can be traced to a record in the feed.
"""

from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.timetable.atoc_timetable import TimetableDb
from trainbudget.feeds.make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable
from trainbudget.measure.sanity_report import (
    build_report,
    cheapest_and_dearest,
    count_variants,
    dropped_reasons,
    fare_smells,
    inside_budget,
    print_report,
    sensitivity,
)


class SanityReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.fares = FaresDb().load_feed(
            build_synthetic_feed(cls.root / "fares", include_unserved_station=True)
        )
        cls.timetable = TimetableDb().load_feed(build_synthetic_timetable(cls.root / "timetable"))
        cls.shapes = FaresDb().load_feed(
            build_synthetic_feed(cls.root / "shapes", include_real_shapes=True)
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # -- the count under each reading ------------------------------------

    def test_every_reading_of_the_budget_gets_its_own_count(self) -> None:
        counts = count_variants(self.fares, "GRN", 2000)
        self.assertEqual(len(counts), 4)
        self.assertEqual(counts["one adult, standard fare"], 3)
        self.assertEqual(counts["one adult, Two Together"], 4)
        # A budget read as the party total buys fewer destinations than the same
        # budget read per adult, which is the whole reason this section exists.
        self.assertLess(counts["2 adults, standard fares"], counts["one adult, standard fare"])

    def test_a_railcard_never_removes_a_destination(self) -> None:
        counts = count_variants(self.fares, "GRN", 2000)
        self.assertGreaterEqual(
            counts["one adult, Two Together"], counts["one adult, standard fare"]
        )
        self.assertGreaterEqual(
            counts["2 adults, Two Together (party total)"], counts["2 adults, standard fares"]
        )

    def test_an_origin_that_is_not_in_the_feed_gives_zeros_rather_than_an_error(self) -> None:
        counts = count_variants(self.fares, "XXX", 2000)
        self.assertEqual(set(counts.values()), {0})

    # -- what the count left out -----------------------------------------

    def test_the_reasons_a_record_was_dropped_are_counted(self) -> None:
        dropped, feed_counts = dropped_reasons(self.fares, "GRN", 2000)
        self.assertEqual(dropped["ticket_is_not_a_standard_return"], 4)
        self.assertEqual(dropped["fare_above_the_budget"], 2)
        self.assertEqual(feed_counts["fares_with_no_flow_record"], 0)

    def test_a_feed_shape_defect_reaches_the_report(self) -> None:
        _, feed_counts = dropped_reasons(self.shapes, "GRN", 2000)
        self.assertEqual(feed_counts["fares_with_no_flow_record"], 1)
        self.assertEqual(feed_counts["locations_without_a_station_code"], 1)
        self.assertEqual(feed_counts["extra_location_codes_for_a_station"], 1)

    # -- how close the count is to the line ------------------------------

    def test_the_borderline_destinations_are_the_ones_near_the_budget(self) -> None:
        inside = inside_budget(self.fares, "GRN", 1300)
        self.assertEqual([row.crs for row in inside], ["LCN", "NOT", "SLP"])
        report = build_report(self.fares, None, "GRN", 1300)
        # 1300 with a 10 percent margin is 1170, so the 1200 fare is close and the
        # 870 fare is not.
        self.assertEqual(report["borderline"], ["SLP"])

    def test_the_count_at_ten_percent_either_side_is_reported(self) -> None:
        self.assertEqual(
            sensitivity(self.fares, "GRN", 1300),
            {"at_10_percent_less": 2, "at_budget": 3, "at_10_percent_more": 3},
        )

    def test_the_cheapest_and_dearest_are_named(self) -> None:
        cheapest, dearest = cheapest_and_dearest(inside_budget(self.fares, "GRN", 2000))
        self.assertEqual(cheapest[0].crs, "LCN")
        self.assertEqual(cheapest[0].best_pence, 870)
        self.assertEqual(dearest[-1].crs, "SLP")

    # -- smells in the fares themselves ----------------------------------

    def test_the_clean_feed_smells_of_nothing(self) -> None:
        smells = fare_smells(self.fares)
        self.assertTrue(all(not samples for samples in smells.values()), smells)

    def test_a_fare_that_is_not_a_multiple_of_five_pence_is_flagged(self) -> None:
        smells = fare_smells(self.shapes)
        self.assertEqual(len(smells["not_a_multiple_of_five_pence"]), 1)
        self.assertIn("0000099/SDR", smells["not_a_multiple_of_five_pence"][0])

    # -- the report as a whole -------------------------------------------

    def test_the_report_says_what_it_read(self) -> None:
        report = build_report(self.fares, self.timetable, "GRN", 2000)
        self.assertIn("rjfaf.ffl", report["files"])
        self.assertEqual(report["counts"]["flows"], 7)

    def test_the_report_names_the_destinations_the_timetable_does_not_serve(self) -> None:
        report = build_report(self.fares, self.timetable, "GRN", 2000)
        self.assertEqual(report["unserved"], ["SLP"])
        self.assertEqual(report["served"], 2)

    def test_the_report_prints_without_a_timetable(self) -> None:
        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(build_report(self.fares, None, "GRN", 2000))
        text = buffer.getvalue()
        self.assertIn("Count sanity report", text)
        self.assertIn("What the count left out", text)
        self.assertNotIn("Where the two feeds disagree", text)

    def test_the_printed_report_carries_the_count_and_the_caveat(self) -> None:
        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(build_report(self.fares, None, "GRN", 2000))
        text = buffer.getvalue()
        self.assertIn("one adult, standard fare", text)
        self.assertIn("too low looks exactly like a count", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
