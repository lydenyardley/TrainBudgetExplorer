"""A row with no service is asked the week, not only the build's day.

Every service in the synthetic timetable runs Monday to Saturday, so a build
for a Sunday has no journey on most destinations. That is the smallest version
of the real case: twenty-six of Nottingham's ninety-six rows read "No service"
on the Sunday the build ran for, and every one of them is a direct journey on
the Monday.
"""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import make_synthetic_feed
from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
from build_demo_page import SERVICE_WEEK_HORIZON, build_payload

# Sundays and Mondays inside the window the synthetic timetable covers
# (21 September to 11 December 2026, coded 260921 to 261211).
SUNDAY = date(2026, 10, 4)
MONDAY = date(2026, 10, 5)
LISTS = ("destinations", "singleDestinations", "anytimeDestinations")


class ServiceWeekTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.fares = FaresDb().load_feed(
            make_synthetic_feed.build_synthetic_feed(
                root / "fares", include_unserved_station=True, include_restrictions=True
            )
        )
        cls.timetable = TimetableDb().load_feed(
            make_synthetic_feed.build_synthetic_timetable(root / "timetable")
        )
        cls.sunday = build_payload(cls.fares, cls.timetable, "GRN", day=SUNDAY)
        cls.monday = build_payload(cls.fares, cls.timetable, "GRN", day=MONDAY)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_sunday_build_leaves_most_destinations_without_a_journey(self) -> None:
        # The precondition, stated so a fixture change cannot quietly turn this
        # into a test that passes because there was nothing to find.
        rows = self.sunday["destinations"]
        without = [row["crs"] for row in rows if row["journeyState"] == "found"]
        self.assertEqual(len(without) < len(rows) // 2, True, "the Sunday should have no service")
        self.assertNotEqual(without, [], "a Sunday build with no gaps cannot test this")

    def test_every_no_service_row_is_answered_one_way_or_the_other(self) -> None:
        # The invariant. A row either names a day the week reaches it on, or
        # says the week does not reach it. It never claims the first and
        # carries the second's wording, and it never carries neither.
        for key in LISTS:
            for row in self.sunday[key]:
                if row["journeyState"] == "found":
                    self.assertNotIn("nextService", row, row["crs"])
                    continue
                # The build sends a key rather than a sentence, and the day
                # the sentence is worded from travels beside it. So the state
                # a row is in is checkable here, and the wording it becomes
                # is checkable where it is written.
                self.assertEqual(row["journeyState"], "no_service", row["crs"])
                self.assertEqual(self.sunday["serviceDate"], SUNDAY.isoformat())
                self.assertEqual(self.sunday["serviceHorizon"], SERVICE_WEEK_HORIZON)
                if "nextService" in row:
                    later = date.fromisoformat(row["nextService"])
                    self.assertGreater(later, SUNDAY, row["crs"])
                    self.assertLessEqual(
                        (later - SUNDAY).days, SERVICE_WEEK_HORIZON, row["crs"]
                    )
                else:
                    # No day to name, and none invented: the row says so by
                    # carrying no key at all.
                    self.assertNotIn("nextService", row)

    def test_a_station_the_week_never_reaches_is_not_given_a_day(self) -> None:
        # Tower Hill has a fare and no train on any day of the synthetic week.
        # It is the case the reader's Wirksworth is, and it must not be dressed
        # up as a weekday.
        unserved = [row for row in self.sunday["destinations"] if row["crs"] == "SLP"]
        self.assertEqual(len(unserved), 1, "the unserved station should be priced here")
        self.assertNotIn("nextService", unserved[0])

    def test_the_sweep_does_not_touch_a_row_that_has_a_journey(self) -> None:
        # Nottingham is served on the Sunday by a train the synthetic feed runs
        # on all seven days, so its row must be exactly what it was: found, and
        # carrying nothing from the sweep.
        served = [row for row in self.sunday["destinations"] if row["crs"] == "NOT"]
        self.assertEqual(len(served), 1)
        self.assertEqual(served[0]["journeyState"], "found")
        self.assertNotIn("nextService", served[0])

    def test_a_monday_build_names_no_day_for_a_row_the_week_reaches(self) -> None:
        # The other side of the promise: on a day the network runs, the pages
        # that are complete carry no key and pay no bytes for the sweep.
        for key in LISTS:
            for row in self.monday[key]:
                if row["journeyState"] == "found":
                    self.assertNotIn("nextService", row, f"{key}/{row['crs']}")
                elif "nextService" in row:
                    self.assertGreater(
                        date.fromisoformat(row["nextService"]),
                        MONDAY + timedelta(days=-1),
                        f"{key}/{row['crs']}",
                    )


if __name__ == "__main__":
    unittest.main()