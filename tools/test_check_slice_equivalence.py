"""Tests for the slice equivalence sweep.

The tool's whole product is a verdict about two sets of answers, so the tests
that matter are the two directions of it: a slice the feed agrees with is
reported as agreeing, and a slice with one schedule missing is reported as
differing and names what changed. A sweep that cannot see a damaged slice would
be a green light with nothing behind it.

The feeds are synthetic, so the comparison is over a fixture whose slice is a
strict subset of the feed rather than over the whole national download.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from atoc_timetable import TimetableDb
from make_synthetic_feed import build_synthetic_timetable
from tools.check_slice_equivalence import (
    DEFAULT_MAX_LEGS,
    compare_origin,
    compared_counts,
    coverage,
    feed_origins,
    load_progress,
    main,
    sampled_legs,
    save_progress,
    week_days,
)

MONDAY = date(2026, 10, 7)


class Fixture(unittest.TestCase):
    """One synthetic timetable, loaded once for the class."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_synthetic_timetable(Path(cls._tmp.name) / "timetable")
        cls.db = TimetableDb().load_feed(cls.feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()


class WeekDaysTest(unittest.TestCase):
    def test_the_week_is_seven_consecutive_days(self) -> None:
        days = week_days(MONDAY, 7)
        self.assertEqual(len(days), 7)
        self.assertEqual(days[0], MONDAY)
        self.assertEqual(days[-1], date(2026, 10, 13))

    def test_a_shorter_window_stops_where_it_was_told(self) -> None:
        self.assertEqual(week_days(MONDAY, 2), [MONDAY, date(2026, 10, 8)])


class SampledLegsTest(unittest.TestCase):
    def test_no_sample_is_no_legs(self) -> None:
        self.assertEqual(sampled_legs(["A", "B"], {}, 0), [])

    def test_the_default_is_every_leg_of_every_journey(self) -> None:
        self.assertIsNone(DEFAULT_MAX_LEGS, "the whole question is the default")

        class _Leg:
            def __init__(self, uid: str) -> None:
                self.train_uid = uid
                self.origin_crs = "ORG"
                self.destination_crs = "DST"

        class _Journey:
            def __init__(self, uid: str) -> None:
                self.legs = (_Leg(uid), _Leg(uid + "B"))

        destinations = [f"D{index:03d}" for index in range(50)]
        reached = {crs: _Journey(crs) for crs in destinations}
        legs = sampled_legs(destinations, reached, None)
        self.assertEqual(len(legs), 100, "two legs each, for every destination")

    def test_the_sample_spreads_over_the_whole_list(self) -> None:
        class _Leg:
            def __init__(self, uid: str) -> None:
                self.train_uid = uid
                self.origin_crs = "ORG"
                self.destination_crs = "DST"

        class _Journey:
            def __init__(self, uid: str) -> None:
                self.legs = (_Leg(uid),)

        destinations = [f"D{index:03d}" for index in range(100)]
        reached = {crs: _Journey(crs) for crs in destinations}
        legs = sampled_legs(destinations, reached, 10)
        # Every tenth destination, not the first ten: the sample is the whole
        # list rather than its alphabetical head.
        self.assertEqual(len(legs), 10)
        self.assertEqual(legs[0][0], "D000")
        self.assertEqual(legs[-1][0], "D090")

    def test_the_sample_is_the_same_every_run(self) -> None:
        class _Leg:
            train_uid = "T1"
            origin_crs = "ORG"
            destination_crs = "DST"

        class _Journey:
            legs = (_Leg(),)

        destinations = [f"D{index:03d}" for index in range(7)]
        reached = {crs: _Journey() for crs in destinations}
        self.assertEqual(
            sampled_legs(destinations, reached, 3),
            sampled_legs(destinations, reached, 3),
        )


class CompareOriginTest(Fixture):
    def test_every_origin_agrees_with_the_whole_feed(self) -> None:
        origins = feed_origins(self.db)
        self.assertGreater(len(origins), 1)
        for origin in origins:
            for day in week_days(MONDAY, 2):
                with self.subTest(origin=origin, day=day):
                    self.assertEqual(compare_origin(self.db, origin, day), [])

    def test_a_slice_missing_a_schedule_is_named(self) -> None:
        original = TimetableDb.focused

        def damaged(self, origin_crs):
            slice_db = original(self, origin_crs)
            if slice_db is self or not slice_db.schedules:
                return slice_db
            thinner = copy.copy(slice_db)
            thinner.schedules = slice_db.schedules[:-1]
            thinner._invalidate_indexes()
            return thinner

        with mock.patch.object(TimetableDb, "focused", damaged):
            found = [
                (origin, compare_origin(self.db, origin, MONDAY))
                for origin in feed_origins(self.db)
            ]
        differing = [item for item in found if item[1]]
        self.assertTrue(differing, "a slice with a schedule missing was reported as agreeing")
        # The difference names the destination and both answers, so a reader of
        # the failure can tell which page moved and how.
        origin, differences = differing[0]
        self.assertTrue(differences[0].startswith(f"{origin}") or ":" in differences[0])
        self.assertIn("whole=", differences[0])
        self.assertIn("slice=", differences[0])

    def test_the_counts_the_page_reports_are_compared(self) -> None:
        origin = feed_origins(self.db)[0]
        self.assertEqual(
            compare_origin(self.db, origin, MONDAY),
            [],
            "stats and the service window are part of the page's answers",
        )


class ProgressTest(unittest.TestCase):
    def test_a_missing_checkpoint_is_empty_rather_than_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = load_progress(Path(tmp) / "absent.json")
        self.assertEqual(progress["pairs"], {})

    def test_a_checkpoint_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "progress.json"
            save_progress(path, {"pairs": {"GRA|2026-10-07": "ok"}, "differences": {}})
            self.assertEqual(
                load_progress(path)["pairs"], {"GRA|2026-10-07": "ok"}
            )

    def test_a_corrupt_checkpoint_is_started_again_rather_than_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            path.write_text("{ not json", encoding="utf-8")
            self.assertEqual(load_progress(path)["pairs"], {})

    def test_coverage_counts_a_partly_compared_origin_as_incomplete(self) -> None:
        origins = ["GRA", "NOT"]
        days = week_days(MONDAY, 2)
        progress = {
            "pairs": {
                "GRA|2026-10-07": "ok",
                "GRA|2026-10-08": "ok",
                "NOT|2026-10-07": "ok",
            }
        }
        line = coverage(progress, origins, days)
        self.assertIn("3 of 4 origin-days compared", line)
        self.assertIn("1 of 2 origins complete", line)

    def test_coverage_counts_the_request_and_not_every_pair_in_the_file(self) -> None:
        # A checkpoint outlives the request that wrote it: an earlier --limit,
        # --origins or single day leaves pairs this run was not asked about. A
        # line that counted them would report more compared than there is to
        # compare, which is the one direction a proof cannot be wrong in.
        origins = ["GRA", "NOT"]
        days = week_days(MONDAY, 1)
        progress = {"pairs": {"GRA|2026-10-07": "ok", "ZZZ|2020-01-01": "differs"}}
        line = coverage(progress, origins, days)
        self.assertIn("1 of 2 origin-days compared", line)
        self.assertIn("0 differing", line)
        # And the same count is what the run estimates its remaining work from,
        # so a request run after a wider one does not read its file's pairs as
        # its own and report itself finished.
        self.assertEqual(compared_counts(progress, origins, days), (1, 0))


class CliTest(Fixture):
    def _run(self, argv: list[str]) -> tuple[int, str]:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(argv)
        return code, stream.getvalue()

    def test_a_missing_feed_is_exit_two(self) -> None:
        code, output = self._run(["--timetable", str(Path(self._tmp.name) / "absent")])
        self.assertEqual(code, 2)
        self.assertIn("no timetable feed", output)

    def test_a_sweep_writes_its_checkpoint_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            argv = [
                "--timetable",
                str(self.feed),
                "--date",
                MONDAY.isoformat(),
                "--days",
                "1",
                "--max-legs",
                "2",
                "--progress",
                str(progress),
            ]
            code, output = self._run(argv)
            self.assertEqual(code, 0, output)
            written = json.loads(progress.read_text(encoding="utf-8"))
            origins = feed_origins(self.db)
            self.assertEqual(len(written["pairs"]), len(origins))
            self.assertTrue(all(value == "ok" for value in written["pairs"].values()))

            before = progress.read_text(encoding="utf-8")
            code, second = self._run(argv)
            self.assertEqual(code, 0, second)
            # A resumed run reports the same coverage and does not rewrite what
            # it has already compared.
            self.assertEqual(progress.read_text(encoding="utf-8"), before)
            self.assertIn("of", second)

    def test_a_checkpoint_compared_with_other_legs_is_not_carried_over(self) -> None:
        # `--max-legs` bounds which calling points were compared, so pairs
        # compared under one bound are not evidence about another. Without this
        # a quick sampled run would leave a checkpoint behind that a full sweep
        # resumes from and reports as every origin-day agreed.
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            base = [
                "--timetable",
                str(self.feed),
                "--date",
                MONDAY.isoformat(),
                "--days",
                "1",
                "--progress",
                str(progress),
            ]
            code, output = self._run([*base, "--max-legs", "1"])
            self.assertEqual(code, 0, output)
            self.assertEqual(json.loads(progress.read_text(encoding="utf-8"))["max_legs"], 1)

            code, output = self._run([*base, "--max-legs", "0"])
            self.assertEqual(code, 0, output)
            self.assertIn("not carried over", output)
            written = json.loads(progress.read_text(encoding="utf-8"))
            self.assertEqual(written["max_legs"], 0)
            self.assertTrue(all(value == "ok" for value in written["pairs"].values()))

    def test_a_differing_pair_is_exit_one_and_kept(self) -> None:
        original = TimetableDb.focused

        def damaged(self, origin_crs):
            slice_db = original(self, origin_crs)
            if slice_db is self or not slice_db.schedules:
                return slice_db
            thinner = copy.copy(slice_db)
            thinner.schedules = slice_db.schedules[:-1]
            thinner._invalidate_indexes()
            return thinner

        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            argv = [
                "--timetable",
                str(self.feed),
                "--date",
                MONDAY.isoformat(),
                "--days",
                "1",
                "--progress",
                str(progress),
            ]
            with mock.patch.object(TimetableDb, "focused", damaged):
                code, output = self._run(argv)
            self.assertEqual(code, 1, output)
            written = json.loads(progress.read_text(encoding="utf-8"))
            self.assertIn("differs", written["pairs"].values())
            self.assertTrue(written["differences"])

    def test_a_limited_sweep_only_compares_the_origins_it_was_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            code, output = self._run(
                [
                    "--timetable",
                    str(self.feed),
                    "--origins",
                    "GRN",
                    "--days",
                    "1",
                    "--progress",
                    str(progress),
                ]
            )
            self.assertEqual(code, 0, output)
            self.assertEqual(list(json.loads(progress.read_text(encoding="utf-8"))["pairs"]), ["GRN|2026-10-07"])

    def test_a_probe_times_origins_and_writes_nothing(self) -> None:
        code, output = self._run(
            ["--timetable", str(self.feed), "--probe", "2", "--days", "1", "--max-legs", "1"]
        )
        self.assertEqual(code, 0, output)
        self.assertIn("projects to", output)


if __name__ == "__main__":
    unittest.main()
