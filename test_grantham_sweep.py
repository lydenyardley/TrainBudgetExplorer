"""Tests for the fare and service merge in the sweep CLI."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
from grantham_sweep import enrich_with_journeys
from make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable


class SweepMergeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fares = FaresDb().load_feed(
            build_synthetic_feed(Path(cls._tmp.name) / "fares", include_unserved_station=True)
        )
        cls.timetable = TimetableDb().load_feed(build_synthetic_timetable(Path(cls._tmp.name) / "timetable"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_merge_keeps_fare_order_and_attaches_journeys(self) -> None:
        results = self.fares.destinations_within("GRN", 2000)
        rows = enrich_with_journeys(results, self.timetable, "GRN")
        self.assertEqual([reachable.crs for reachable, _ in rows], ["LCN", "NOT", "SLP"])
        by_crs = {reachable.crs: journey for reachable, journey in rows}
        self.assertEqual(by_crs["NOT"].duration, 45)
        self.assertEqual(by_crs["NOT"].changes, 0)
        self.assertEqual(by_crs["LCN"].duration, 50)

    def test_a_fare_with_no_service_gets_none(self) -> None:
        results = self.fares.destinations_within("GRN", 2000)
        by_crs = {
            reachable.crs: journey
            for reachable, journey in enrich_with_journeys(results, self.timetable, "GRN")
        }
        self.assertIsNone(by_crs["SLP"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
