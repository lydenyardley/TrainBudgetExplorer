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


class ServiceWeekPayloadTest(unittest.TestCase):
    """The reader picks the day the times are for, so the build sends the week.

    The control on the page reads one table of answers per day and one row's
    index into it. Three things have to hold for that to be honest. Day zero is
    the build's own day, so its table must say exactly what the rows already
    said, and a reader who touches nothing must not see a single cell move. A
    day named by nextService must be a day the table answers that station on, so
    the sentence the row already carried and the answer the control reads are
    the same fact. And a station the week never reaches must stay absent from
    every day's table rather than be given an empty answer, because the page
    reads an absent station as "no service that day".
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.fares = FaresDb().load_feed(
            make_synthetic_feed.build_synthetic_feed(
                root / "fares",
                include_unserved_station=True,
                include_restrictions=True,
            )
        )
        cls.timetable = TimetableDb().load_feed(
            make_synthetic_feed.build_synthetic_timetable(root / "timetable")
        )
        cls.sunday = build_payload(cls.fares, cls.timetable, "GRN", day=SUNDAY)
        cls.undated = build_payload(cls.fares, cls.timetable, "GRN")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def rows(self, payload: dict) -> list:
        return [row for key in LISTS for row in payload[key]]

    def test_the_build_sends_one_day_per_offset_from_its_own_day(self) -> None:
        days = self.sunday["serviceDays"]
        self.assertEqual(len(days), SERVICE_WEEK_HORIZON + 1, "one day per offset, plus the build's own")
        self.assertEqual(days[0], self.sunday["serviceDate"], "day zero is the build's own day")
        for earlier, later in zip(days, days[1:]):
            step = date.fromisoformat(later) - date.fromisoformat(earlier)
            self.assertEqual(step, timedelta(days=1), f"{earlier} to {later} is not the next day")

    def test_every_table_is_a_week_of_days_keyed_by_station(self) -> None:
        week = self.sunday["serviceWeek"]
        self.assertGreaterEqual(len(week), 1, "at least one timetable's week must be sent")
        for position, per_day in enumerate(week):
            self.assertEqual(len(per_day), SERVICE_WEEK_HORIZON + 1, f"table {position}")
            for offset, table in enumerate(per_day):
                self.assertIsInstance(table, dict, f"table {position} day {offset}")
                for crs, answer in table.items():
                    self.assertIsInstance(crs, str, f"table {position} day {offset}")
                    self.assertIsInstance(answer, list, f"{crs} on day {offset}")
                    self.assertEqual(len(answer), 2, f"{crs} on day {offset} is a pair")
                    self.assertIsInstance(answer[0], int, f"{crs} minutes on day {offset}")
                    self.assertIsInstance(answer[1], int, f"{crs} changes on day {offset}")

    def test_day_zero_says_exactly_what_the_rows_already_said(self) -> None:
        # The invariant that makes the control cost nothing on arrival. If the
        # day-zero table disagreed with a row's own answer, a reader who never
        # touched the select would be shown a different journey from the one the
        # build spent its own effort proving.
        checked = 0
        for row in self.rows(self.sunday):
            index = row["serviceWeekIndex"]
            self.assertIsInstance(index, int, f"{row['crs']} names no table")
            day_zero = self.sunday["serviceWeek"][index][0].get(row["crs"])
            if row["journeyState"] == "found":
                self.assertIsNotNone(day_zero, f"{row['crs']} was found but day zero says no service")
                self.assertEqual(day_zero, [row["minutes"], row["changes"]], row["crs"])
            else:
                self.assertIsNone(day_zero, f"{row['crs']} was absent but day zero gives it a journey")
            checked += 1
        self.assertGreater(checked, 0, "no rows to check")

    def test_the_day_a_row_names_is_a_day_the_table_answers_it_on(self) -> None:
        # nextService and the week table are two readings of one sweep. If they
        # could disagree, the page would tell a reader "runs Monday" and then
        # show them nothing on Monday.
        named = 0
        for row in self.rows(self.sunday):
            if "nextService" not in row:
                continue
            index = row["serviceWeekIndex"]
            offset = self.sunday["serviceDays"].index(row["nextService"])
            answer = self.sunday["serviceWeek"][index][offset].get(row["crs"])
            self.assertIsNotNone(answer, f"{row['crs']} is promised {row['nextService']} and not given it")
            named += 1
        self.assertGreater(named, 0, "a Sunday build of a weekday-only feed should name a day")

    def test_a_station_the_week_never_reaches_is_absent_from_every_day(self) -> None:
        # Tower Hill has a fare and no train on any day of the synthetic week.
        # It must be absent rather than present-and-empty, because the page
        # reads a station missing from a day's table as no service on that day
        # and would otherwise print a journey of no minutes.
        for row in self.rows(self.sunday):
            if row["crs"] != "SLP":
                continue
            index = row["serviceWeekIndex"]
            present = [offset for offset, table in enumerate(self.sunday["serviceWeek"][index])
                       if row["crs"] in table]
            self.assertEqual(present, [], "a station with no train is in the week")
            self.assertNotIn("nextService", row)
            return
        self.fail("the unserved station should be priced here")

    def test_a_build_with_no_day_sends_no_week_and_names_no_table(self) -> None:
        # A build made without a date has nothing to walk the week from, so it
        # sends no days and every row says it has no table. The page then shows
        # no control at all rather than an empty one.
        self.assertEqual(self.undated["serviceDays"], [])
        self.assertEqual(self.undated["serviceWeek"], [])
        self.assertIsNone(self.undated["serviceDate"])
        rows = self.rows(self.undated)
        self.assertGreater(len(rows), 0, "no rows to check")
        for row in rows:
            self.assertIsNone(row["serviceWeekIndex"], row["crs"])


if __name__ == "__main__":
    unittest.main()