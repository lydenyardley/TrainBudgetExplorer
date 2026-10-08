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
    parse_shard,
    sampled_legs,
    save_progress,
    shard_origins,
    shard_progress_path,
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

    def _run(self, argv: list[str]) -> tuple[int, str]:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(argv)
        return code, stream.getvalue()


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


class ParseShardTest(unittest.TestCase):
    def test_a_share_reads_as_an_index_and_a_count(self) -> None:
        self.assertEqual(parse_shard("3/8"), (3, 8))
        self.assertEqual(parse_shard("1/1"), (1, 1))

    def test_what_is_not_a_share_is_refused(self) -> None:
        # Including 0/4 and 5/4: a shard that is not one of the M is a request
        # for a share of the work that does not exist, and a run that compared
        # nothing would report the request as unwitnessed rather than wrong.
        for text in ("3", "0/4", "5/4", "x/y", "/3", "3/", "-1/4"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_shard(text)


class ShardOriginsTest(unittest.TestCase):
    def test_the_shares_are_disjoint_and_together_the_request(self) -> None:
        origins = [f"S{index:03d}" for index in range(10)]
        shares = [shard_origins(origins, index, 4) for index in range(1, 5)]
        seen = [origin for share in shares for origin in share]
        self.assertEqual(sorted(seen), origins)
        self.assertEqual(len(seen), len(set(seen)), "a shard repeated another shard's origin")
        self.assertEqual([len(share) for share in shares], [3, 3, 2, 2])

    def test_a_share_is_the_same_list_however_the_others_are_ordered(self) -> None:
        origins = [f"S{index:03d}" for index in range(10)]
        self.assertEqual(shard_origins(origins, 2, 3), ["S001", "S004", "S007"])

    def test_a_share_of_a_larger_run_is_empty_rather_than_the_whole_list(self) -> None:
        # parse_shard refuses N > M, and this is what the slice would answer if
        # it were ever called with one: an empty share, never the request.
        self.assertEqual(shard_origins(["GRA", "NOT"], 5, 4), [])

    def test_the_checkpoint_a_shard_owns_is_named_for_it(self) -> None:
        base = Path("_cache/slice-equivalence.json")
        self.assertEqual(
            shard_progress_path(base, 2, 8).name, "slice-equivalence.shard-2-of-8.json"
        )
        # Beside the base file, so M shards write M files and none of them is
        # the base one a single-process sweep resumes from.
        self.assertEqual(shard_progress_path(base, 2, 8).parent, base.parent)
        self.assertEqual(shard_progress_path(Path("progress"), 1, 2).name, "progress.shard-1-of-2.json")


class MergeTest(Fixture):
    """The partition behind a merged verdict, which is what a merge has to check."""

    def _base(self, tmp: str) -> Path:
        return Path(tmp) / "slice-equivalence.json"

    def _argv(self, progress: Path, *extra: str) -> list[str]:
        return [
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
            *extra,
        ]

    def test_disjoint_shards_merge_into_the_one_verdict_a_single_run_prints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = self._base(tmp)
            origins = feed_origins(self.db)
            total = 0
            for index in (1, 2, 3):
                code, output = self._run(self._argv(base, "--shard", f"{index}/3"))
                self.assertEqual(code, 0, output)
                self.assertIn(f"shard {index} of 3:", output)
                written = json.loads(
                    shard_progress_path(base, index, 3).read_text(encoding="utf-8")
                )
                # A shard's own file holds its own origin-days and the request
                # they are a share of, and nothing else.
                self.assertEqual(written["origins"], shard_origins(origins, index, 3))
                self.assertEqual(written["request_origins"], origins)
                self.assertEqual(len(written["pairs"]), len(written["origins"]))
                total += len(written["pairs"])
            self.assertEqual(total, len(origins))
            # The shards share no state: the base checkpoint is not theirs.
            self.assertFalse(base.exists())

            code, output = self._run(self._argv(base, "--merge", "3"))
            self.assertEqual(code, 0, output)
            self.assertIn("merged shard checkpoint(s)", output)
            self.assertIn("every origin-day asked for agreed", output)
            # Each shard's own coverage, so a merge that is short says which
            # shell to run again rather than which file to go and read.
            for index in (1, 2, 3):
                self.assertIn(f"shard {index} of 3: ", output)
            merged = json.loads(base.read_text(encoding="utf-8"))
            self.assertEqual(len(merged["pairs"]), len(origins))
            self.assertTrue(all(value == "ok" for value in merged["pairs"].values()))
            self.assertEqual(len(merged["merged_from"]), 3)

    def test_a_missing_shard_is_a_reason_rather_than_a_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = self._base(tmp)
            code, output = self._run(self._argv(base, "--shard", "1/3"))
            self.assertEqual(code, 0, output)
            code, output = self._run(self._argv(base, "--merge", "3"))
            self.assertEqual(code, 2, output)
            self.assertIn("shard 2 of 3 has no checkpoint", output)
            self.assertNotIn("every origin-day asked for agreed", output)
            self.assertFalse(base.exists(), "a refused merge writes no verdict")

    def test_shards_asked_different_questions_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = self._base(tmp)
            code, output = self._run(self._argv(base, "--shard", "1/2"))
            self.assertEqual(code, 0, output)
            # The same shard index, a different request: two days instead of one.
            code, output = self._run(
                [
                    "--timetable",
                    str(self.feed),
                    "--date",
                    MONDAY.isoformat(),
                    "--days",
                    "2",
                    "--max-legs",
                    "2",
                    "--progress",
                    str(base),
                    "--shard",
                    "2/2",
                ]
            )
            self.assertEqual(code, 0, output)
            code, output = self._run(self._argv(base, "--merge", "2"))
            self.assertEqual(code, 2, output)
            self.assertIn("was made against another request", output)

    def test_shards_that_overlap_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = self._base(tmp)
            code, output = self._run(self._argv(base, "--shard", "1/2"))
            self.assertEqual(code, 0, output)
            # A shard file copied over the other one's: the same origins twice,
            # and the ones the second share should have held in no shard at all.
            shard_progress_path(base, 2, 2).write_bytes(
                shard_progress_path(base, 1, 2).read_bytes()
            )
            code, output = self._run(self._argv(base, "--merge", "2"))
            self.assertEqual(code, 2, output)
            self.assertIn("so the shards overlap", output)
            self.assertIn("are in no shard", output)

    def test_a_checkpoint_holding_pairs_it_does_not_record_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = self._base(tmp)
            code, output = self._run(self._argv(base, "--shard", "1/1"))
            self.assertEqual(code, 0, output)
            path = shard_progress_path(base, 1, 1)
            written = json.loads(path.read_text(encoding="utf-8"))
            written["pairs"]["ZZZ|2026-10-07"] = "ok"
            path.write_text(json.dumps(written), encoding="utf-8")
            code, output = self._run(self._argv(base, "--merge", "1"))
            self.assertEqual(code, 2, output)
            self.assertIn("not one of the origin-days it records", output)

    def test_a_shard_that_did_not_agree_merges_into_exit_one(self) -> None:
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
            base = self._base(tmp)
            origins = feed_origins(self.db)
            # One origin per shard, so the shard that carries the origin this
            # damage shows on is known rather than hoped for: a damaged slice
            # does not move every origin's answers.
            with mock.patch.object(TimetableDb, "focused", damaged):
                sensitive = [origin for origin in origins if compare_origin(self.db, origin, MONDAY)]
            self.assertTrue(sensitive, "this damage shows on no origin at all")
            count = len(origins)
            for index in range(1, count + 1):
                share = f"{index}/{count}"
                expected = 1 if origins[index - 1] in sensitive else 0
                patcher = mock.patch.object(TimetableDb, "focused", damaged)
                if expected:
                    patcher.start()
                try:
                    code, output = self._run(self._argv(base, "--shard", share))
                finally:
                    if expected:
                        patcher.stop()
                self.assertEqual(code, expected, output)
            code, output = self._run(self._argv(base, "--merge", str(count)))
            self.assertEqual(code, 1, output)
            self.assertIn("did not agree or could not be compared", output)
            merged = json.loads(base.read_text(encoding="utf-8"))
            self.assertTrue(merged["differences"], "the merge keeps what differed")

    def test_a_shard_with_origin_days_still_to_compare_merges_to_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = self._base(tmp)
            for index in (1, 2):
                code, output = self._run(self._argv(base, "--shard", f"{index}/2"))
                self.assertEqual(code, 0, output)
            path = shard_progress_path(base, 1, 2)
            written = json.loads(path.read_text(encoding="utf-8"))
            written["pairs"].pop(sorted(written["pairs"])[0])
            path.write_text(json.dumps(written), encoding="utf-8")
            code, output = self._run(self._argv(base, "--merge", "2"))
            self.assertEqual(code, 2, output)
            self.assertIn("still to compare", output)

    def test_a_shard_holding_an_origin_this_request_never_asked_for_is_refused(self) -> None:
        # The other direction of the coverage check: a file that claims an origin
        # outside the merge's own list. Its pair is inside the origin-days it
        # records, so nothing else here would catch it.
        with tempfile.TemporaryDirectory() as tmp:
            base = self._base(tmp)
            code, output = self._run(self._argv(base, "--shard", "1/1"))
            self.assertEqual(code, 0, output)
            path = shard_progress_path(base, 1, 1)
            written = json.loads(path.read_text(encoding="utf-8"))
            written["origins"].append("ZZZ")
            written["pairs"]["ZZZ|2026-10-07"] = "ok"
            path.write_text(json.dumps(written), encoding="utf-8")
            code, output = self._run(self._argv(base, "--merge", "1"))
            self.assertEqual(code, 2, output)
            self.assertIn("are in a shard and not in this request", output)

    def test_a_shard_and_a_merge_together_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = self._base(tmp)
            code, output = self._run(self._argv(base, "--shard", "1/2", "--merge", "2"))
            self.assertEqual(code, 2, output)
            self.assertIn("give one", output)

    def test_a_share_that_is_not_a_share_is_refused_before_the_feed_is_read(self) -> None:
        code, output = self._run(self._argv(Path("_cache/unused.json"), "--shard", "3/2"))
        self.assertEqual(code, 2)
        self.assertIn("--shard '3/2' is not a share of a run", output)


if __name__ == "__main__":
    unittest.main()
