"""Tests for the timetable parser and its journey queries.

Each assertion is a literal value, so a parser that returned nothing would fail.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atoc_timetable import TimetableDb, format_minutes
from make_synthetic_feed import build_synthetic_timetable


class TimetableParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_synthetic_timetable(Path(cls._tmp.name) / "timetable")
        cls.timetable = TimetableDb().load_feed(cls.feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_reads_stations_schedules_and_change_times(self) -> None:
        self.assertEqual(self.timetable.station_for_tiploc("GRNT").name, "GRANTHAM")
        self.assertEqual(self.timetable.stats()["schedules"], 11)
        self.assertEqual(self.timetable.connection_minutes_at("NOT"), 10)

    def test_station_names_file_wins_over_a_tiploc_insert(self) -> None:
        self.assertEqual(self.timetable.cif_crs_by_tiploc["NOTT"], "XXX")
        self.assertEqual(self.timetable.crs_for_tiploc("NOTT"), "NOT")

    def test_fastest_direct_train_wins_with_no_changes(self) -> None:
        journey = self.timetable.best_journey("GRN", "NOT")
        self.assertEqual(journey.duration, 45)
        self.assertEqual(journey.changes, 0)
        self.assertEqual(journey.departure, 10 * 60)
        self.assertEqual([leg.train_uid for leg in journey.legs], ["T10004"])

    def test_reads_an_intermediate_calling_point(self) -> None:
        journey = self.timetable.best_journey("GRN", "LCN")
        self.assertEqual(journey.duration, 50)
        self.assertEqual(journey.departure, 9 * 60 + 15)

    def test_one_change_beats_a_slower_direct_train(self) -> None:
        journey = self.timetable.best_journey("GRN", "NWK")
        self.assertEqual(journey.changes, 1)
        self.assertEqual(journey.departure, 10 * 60)
        self.assertEqual(journey.arrival, 11 * 60 + 30)
        self.assertEqual(journey.duration, 90)
        self.assertEqual([leg.train_uid for leg in journey.legs], ["T10004", "T10005"])

    def test_minimum_connection_time_rejects_a_five_minute_change(self) -> None:
        journey = self.timetable.best_journey("GRN", "NWK")
        self.assertNotIn("T10006", [leg.train_uid for leg in journey.legs])

    def test_max_changes_zero_falls_back_to_the_direct_train(self) -> None:
        journey = self.timetable.best_journey("GRN", "NWK", max_changes=0)
        self.assertEqual(journey.changes, 0)
        self.assertEqual(journey.duration, 120)
        self.assertEqual([leg.train_uid for leg in journey.legs], ["T10007"])

    def test_unserved_station_returns_none(self) -> None:
        self.assertIsNone(self.timetable.best_journey("GRN", "XFD"))

    def test_formats_a_duration(self) -> None:
        self.assertEqual(format_minutes(50), "50m")
        self.assertEqual(format_minutes(60), "1h")
        self.assertEqual(format_minutes(95), "1h35")


if __name__ == "__main__":
    unittest.main(verbosity=2)
