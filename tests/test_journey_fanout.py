"""journeys_from() must answer exactly what best_journey() answers.

best_journey() walks the origin's departures, their interchanges and their
onward windows once per destination. journeys_from() walks them once and
answers every destination out of the one walk, which measured 48% cheaper than
asking each destination separately over a seven-day window on the built Cameron
Bridge page. A faster search that answers a different question is not a faster
search, so this asserts they agree, in both directions: every destination the
fan-out returns must rank the same, and every destination it omits must be one
best_journey also cannot reach.
"""
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from atoc_timetable import TimetableDb, _rank  # noqa: E402
from make_synthetic_feed import build_synthetic_timetable  # noqa: E402


def _rank_or_none(journey):
    return None if journey is None else _rank(journey)


class JourneyFanOutMatchesBestJourneyTest(unittest.TestCase):
    """The two searches must be interchangeable, which is what buys the speed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        feed = build_synthetic_timetable(Path(cls._tmp.name) / "timetable")
        cls.db = TimetableDb().load_feed(feed)
        # Every station the fixture knows, so a destination the fan-out drops
        # is caught rather than only the ones it happens to keep.
        cls.stations = sorted({s.crs for s in cls.db.stations_by_tiploc.values() if s.crs})
        cls.days = [date(2026, 9, 28) + timedelta(days=offset) for offset in range(7)]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_both_searches_agree_on_every_station_and_day(self) -> None:
        for origin in self.stations[:6]:
            for day in self.days:
                table = self.db.journeys_from(origin, max_changes=1, day=day)
                for destination in self.stations:
                    with self.subTest(origin=origin, day=day.isoformat(), destination=destination):
                        self.assertEqual(
                            _rank_or_none(self.db.best_journey(origin, destination, max_changes=1, day=day)),
                            _rank_or_none(table.get(destination)),
                            "the two searches disagree about "
                            f"{origin} to {destination} on {day.isoformat()}",
                        )

    def test_a_fan_out_that_found_nothing_would_still_pass_the_test_above(self) -> None:
        # The agreement above is only worth anything if the fan-out returns
        # journeys at all, so this states that on its own: a fixture that
        # cannot be reached yields nothing, and one that can yields something.
        day = self.days[0]
        reachable = [c for c in self.stations if self.db.journeys_from(c, max_changes=1, day=day)]
        self.assertTrue(reachable, "the synthetic fixture reaches nothing at all")
        for origin in reachable[:3]:
            table = self.db.journeys_from(origin, max_changes=1, day=day)
            self.assertIn(origin, set(reachable))
            self.assertTrue(table, f"the fan-out returned nothing from {origin}")
            found = [c for c in self.stations if self.db.best_journey(origin, c, max_changes=1, day=day)]
            self.assertEqual(sorted(table), sorted(found), f"from {origin} the two differ on which stations are reachable")

    def test_direct_only_matches_direct_only(self) -> None:
        # max_changes=0 must not walk the one-change pass, or the fan-out would
        # answer a different question whenever a caller asks for a direct fare.
        day = self.days[0]
        for origin in self.stations[:6]:
            table = self.db.journeys_from(origin, max_changes=0, day=day)
            for destination in self.stations:
                with self.subTest(origin=origin, destination=destination):
                    self.assertEqual(
                        _rank_or_none(self.db.best_journey(origin, destination, max_changes=0, day=day)),
                        _rank_or_none(table.get(destination)),
                    )



class AStationCalledTwiceTest(unittest.TestCase):
    """An onward train that calls a station twice keeps the earlier call.

    Far North trains call at Georgemas Junction, run to Thurso, and call at
    Georgemas again on the way to Wick. The fan-out read the best journey it
    held once per onward train, so the second call was compared against the
    stale answer and replaced the first: Edinburgh's page timed GGJ at 513
    minutes in the row and 540 in its own week table.
    """

    def test_the_fan_out_keeps_the_first_call(self) -> None:
        import make_synthetic_feed as feed

        trains = (
            ("T20001", ("GRNT", "0900"), (), ("PETE", "0930"), "1111111", "P"),
            ("T20002", ("PETE", "0945"), (("LINC", "1000", "1002"), ("NWRK", "1020", "1025")), ("LINC", "1045"), "1111111", "P"),
        )
        kept = feed.TIMETABLE_TRAINS
        feed.TIMETABLE_TRAINS = trains
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db = TimetableDb().load_feed(build_synthetic_timetable(Path(tmp) / "timetable"))
                day = date(2026, 9, 28)
                best = db.best_journey("GRN", "LCN", max_changes=1, day=day)
                table = db.journeys_from("GRN", max_changes=1, day=day)
        finally:
            feed.TIMETABLE_TRAINS = kept
        self.assertIsNotNone(best)
        self.assertEqual(best.duration, 60)
        self.assertEqual(_rank_or_none(table.get("LCN")), _rank(best))

if __name__ == "__main__":
    unittest.main()
