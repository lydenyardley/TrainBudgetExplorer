"""N11: the test for a train that passes a station without stopping.

Written before the fix, and it fails without it.

The real feed records a passing call by putting the train's pass-through time
in the CIF's `scheduled_pass` field and leaving both public time fields as
`0000`. The parser never reads `scheduled_pass`, and it read `0000` as
midnight, so `CallingPoint.board` returned 0 rather than None, the departure
index registered a departure from that station at minute 0, and every service
that merely passed through became an outbound service leaving at midnight.

Measured on the real Grindleford page, where the parser had produced journeys
like these:

    GRNDLFD board=0 -> MNCRPIC alight=365   11 minutes
    GRNDLFD board=0 -> LVRPLSH alight=7      7 minutes
    GRNDLFD board=0 -> EDGH alight=0        0 minutes

and the same station, on the one service that genuinely calls there, gave the
real answer: GRNDLFD dep=591 -> SHEFFLD arr=604, 13 minutes.

The test asserts the behaviour a reader depends on rather than the string in
the parser: a train that does not stop cannot be boarded, so no journey is
found from that station on it. The control in the same test is the service
that does stop, which must still be found and must still report its real
duration -- a parser that simply returned nothing everywhere would pass a test
that only asked for the absence.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD_IMPORT = """from atoc_timetable import (
    CIF_ORIGIN,
    CIF_SCHEDULE,
    CIF_TERMINUS,
    CIF_TIPLOC_DELETE,
    CIF_TIPLOC_INSERT,
    MSN_STATION,
    TimetableDb,
    format_minutes,
)"""

NEW_IMPORT = """from atoc_timetable import (
    CIF_INTERMEDIATE,
    CIF_ORIGIN,
    CIF_SCHEDULE,
    CIF_TERMINUS,
    CIF_TIPLOC_DELETE,
    CIF_TIPLOC_INSERT,
    MSN_STATION,
    TimetableDb,
    format_minutes,
)"""

OLD_TAIL = """if __name__ == "__main__":
    unittest.main(verbosity=2)"""

NEW_TAIL = '''class PassingStopTest(unittest.TestCase):
    """A train that passes a station is not a journey from it.

    The CIF has a field for the pass-through time and the feed uses it: the
    public arrival and departure are left as `0000`, which is not midnight
    because the format has no midnight -- a time after midnight is written
    2400 to 2949. Read as a clock time, `0000` manufactured a departure from
    every station on the network at minute zero.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feed = build_synthetic_timetable(self.root / "timetable")
        # The stations file carries the TIPLOC-to-CRS mapping and is what this
        # test needs from the synthetic feed. Its timetable is not: it has a
        # Grindleford to Lincoln service of its own that is quicker than the one
        # written below, so it would be the journey found either way and the
        # test would pass without ever exercising a passing stop.
        (self.feed / "timetable.mca").unlink()

    def _schedule(self, uid: str, passing: bool) -> list[str]:
        """NOT to LCN, calling at GRN or passing through it."""
        schedule = [
            _line(
                {
                    "record_type": "BS",
                    "transaction_type": "N",
                    "train_uid": uid,
                    "date_runs_from": "260921",
                    "date_runs_to": "261211",
                    "days": "1111110",
                },
                CIF_SCHEDULE,
            ),
            _line(
                {"record_type": "LO", "location": "NOTT   ", "scheduled_departure": "0900",
                 "public_departure": "0900"},
                CIF_ORIGIN,
            ),
        ]
        if passing:
            # The feed's own shape: the pass-through time is recorded, and both
            # public times are the absent marker.
            schedule.append(
                _line(
                    {"record_type": "LI", "location": "GRNT   ", "scheduled_pass": "1000",
                     "public_arrival": "0000", "public_departure": "0000"},
                    CIF_INTERMEDIATE,
                )
            )
        else:
            schedule.append(
                _line(
                    {"record_type": "LI", "location": "GRNT   ", "scheduled_arrival": "0955",
                     "scheduled_departure": "1000", "public_arrival": "0955",
                     "public_departure": "1000"},
                    CIF_INTERMEDIATE,
                )
            )
        schedule.append(
            _line(
                {"record_type": "LT", "location": "LINC   ", "scheduled_arrival": "1115",
                 "public_arrival": "1115"},
                CIF_TERMINUS,
            )
        )
        return schedule

    def test_a_train_that_passes_a_station_is_not_boardable_there(self) -> None:
        (self.feed / "pass.mca").write_text(
            "\\n".join(self._schedule("T90001", passing=True)) + "\\n", encoding="utf-8"
        )
        timetable = TimetableDb().load_feed(self.feed)
        self.assertEqual(timetable.crs_for_tiploc("GRNT"), "GRN")
        # The stop is in the schedule and the station is known, so this is not a
        # parse failure: the service is there and simply does not call.
        schedule = next(s for s in timetable.schedules if s.train_uid == "T90001")
        self.assertIn("GRNT", [s.tiploc for s in schedule.stops])
        self.assertIsNone(
            timetable.best_journey("GRN", "LCN", day=MONDAY),
            "a train that does not stop at Grindleford cannot be boarded there",
        )

    def test_a_train_that_does_call_is_still_boardable_and_timed(self) -> None:
        # The control. Without it a parser that found nothing at all would pass.
        (self.feed / "call.mca").write_text(
            "\\n".join(self._schedule("T90002", passing=False)) + "\\n", encoding="utf-8"
        )
        timetable = TimetableDb().load_feed(self.feed)
        journey = timetable.best_journey("GRN", "LCN", day=MONDAY)
        self.assertIsNotNone(journey, "a train that calls at Grindleford is boardable")
        self.assertEqual(journey.duration, 75, "09:55 at Grindleford to 11:15 at Lincoln")

    def test_no_journey_departs_at_minute_zero(self) -> None:
        # The symptom in one assertion, over both services on the same feed.
        (self.feed / "both.mca").write_text(
            "\\n".join(self._schedule("T90003", passing=True))
            + "\\n"
            + "\\n".join(self._schedule("T90004", passing=False))
            + "\\n",
            encoding="utf-8",
        )
        timetable = TimetableDb().load_feed(self.feed)
        for destination in ("LCN", "NOT"):
            journey = timetable.best_journey("GRN", destination, day=MONDAY)
            if journey is None:
                continue
            self.assertGreater(
                journey.duration, 0,
                f"GRN to {destination} was timed as {journey.duration} minutes",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)'''

if __name__ == "__main__":
    patch(
        "tests/test_atoc_timetable.py",
        [(OLD_IMPORT, NEW_IMPORT), (OLD_TAIL, NEW_TAIL)],
    )