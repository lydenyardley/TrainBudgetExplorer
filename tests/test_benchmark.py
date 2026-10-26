"""Tests for the large feed generator and the benchmark measurement."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.timetable.atoc_timetable import MAX_ONWARD_DEPARTURES, TimetableDb
from trainbudget.measure.benchmark import build_targets, measure, rank
from trainbudget.feeds.make_synthetic_feed import build_large_synthetic_feed

STATIONS = 40
SCHEDULES = 60


class LargeFeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_large_synthetic_feed(
            Path(cls._tmp.name) / "large",
            stations=STATIONS,
            schedules=SCHEDULES,
            seed=3,
        )
        cls.fares = FaresDb().load_feed(cls.feed)
        cls.timetable = TimetableDb().load_feed(cls.feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_both_halves_load_without_rejections(self) -> None:
        self.assertEqual(self.fares.stats()["stations"], STATIONS)
        self.assertEqual(self.timetable.stats()["schedules"], SCHEDULES)
        self.assertEqual(self.fares.report.records_skipped, 0)
        self.assertEqual(self.timetable.report.records_skipped, 0)

    def test_every_other_station_is_priced_from_the_first(self) -> None:
        results = self.fares.destinations_within("A00", 100_000)
        self.assertEqual(len(results), STATIONS - 1)

    def test_the_same_seed_builds_the_same_feed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            again = build_large_synthetic_feed(Path(tmp) / "large", stations=STATIONS, schedules=SCHEDULES, seed=3)
            first = (self.feed / "large.mca").read_text(encoding="utf-8")
            second = (again / "large.mca").read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_measurement_covers_every_target_and_ranks_a_journey(self) -> None:
        targets = build_targets(self.fares, ["A00"], STATIONS)
        self.assertEqual(len(targets), STATIONS - 1)
        timings, journeys = measure(self.timetable, targets, max_onward=5)
        self.assertEqual(len(timings), STATIONS - 1)
        self.assertEqual(len(journeys), STATIONS - 1)
        found = [value for value in journeys.values() if value is not None]
        self.assertTrue(found)
        self.assertTrue(all(value[0] > 0 for value in found))

    def test_rank_of_a_missing_journey_is_none(self) -> None:
        self.assertIsNone(rank(None))

    def test_the_shipped_cap_is_the_value_the_benchmark_chose(self) -> None:
        self.assertEqual(MAX_ONWARD_DEPARTURES, 200)


class HubSpokeFeedTest(unittest.TestCase):
    """The shape where the cap has a price to show."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_large_synthetic_feed(
            Path(cls._tmp.name) / "hub",
            stations=STATIONS,
            schedules=SCHEDULES,
            seed=3,
            shape="hub_spoke",
        )
        cls.fares = FaresDb().load_feed(cls.feed)
        cls.timetable = TimetableDb().load_feed(cls.feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_origin_reaches_only_the_hub_without_a_change(self) -> None:
        outer = [f"A{index:02d}" for index in range(2, STATIONS)]
        for crs in outer:
            self.assertIsNone(
                self.timetable.best_journey("A00", crs, max_changes=0),
                f"{crs} should need a change",
            )

    def test_a_change_reaches_a_destination_the_origin_cannot_reach_directly(self) -> None:
        journey = self.timetable.best_journey("A00", "A03")
        self.assertIsNotNone(journey)
        self.assertEqual(journey.changes, 1)

    def test_a_small_cap_loses_a_journey_that_uncapped_finds(self) -> None:
        targets = build_targets(self.fares, ["A00"], 8, timetable=self.timetable, transfer_only=True)
        self.assertTrue(targets, "the invented hub feed should offer transfer-only pairs")
        lost = 0
        for origin, destination in targets:
            uncapped = self.timetable.best_journey(origin, destination, max_onward=None)
            capped = self.timetable.best_journey(origin, destination, max_onward=1)
            if uncapped is not None and (capped is None or rank(capped) > rank(uncapped)):
                lost += 1
        self.assertGreater(lost, 0, "cap 1 should cost at least one journey")

    def test_unknown_shape_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_large_synthetic_feed(Path(tmp) / "bad", shape="hub_and_spoke")


if __name__ == "__main__":
    unittest.main(verbosity=2)
