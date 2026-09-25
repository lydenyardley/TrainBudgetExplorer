"""Tests for randomised mutation, and for the accounting it depends on.

The fuzzer's value is the invariant, not the mutation: these tests check that
each invariant can fail, because a check that can never fail is decoration.
"""

from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from atoc_fares import FLOW_T, FaresDb
from fuzz_feed import (
    MUTATIONS,
    Round,
    _appears,
    check_timetable,
    fuzz,
    main,
    mutate_file,
)
from make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_timetable

ROUNDS = 60


class AccountingTest(unittest.TestCase):
    """The invariant that matters most, pinned on the record that broke it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def feed_with_a_bad_fare(self) -> Path:
        feed = build_synthetic_feed(self.root / "bad-fare")
        with (feed / "extra.ffl").open("a", encoding="utf-8") as handle:
            handle.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000001",
                        "ticket_code": "SDR",
                        "fare_pence": "abc",
                        "restriction_code": "00",
                    },
                    FLOW_T,
                )
                + "\n"
            )
        return feed

    def test_a_rejected_record_is_never_also_counted_as_parsed(self) -> None:
        report = FaresDb().load_feed(self.feed_with_a_bad_fare()).report
        self.assertEqual(report.lines_read, report.records_parsed + report.records_skipped)
        self.assertEqual(report.records_skipped, 1)

    def test_a_rejected_record_leaves_an_example_to_look_at(self) -> None:
        report = FaresDb().load_feed(self.feed_with_a_bad_fare()).report
        self.assertTrue(report.skipped_examples)
        self.assertIn("not a number", report.skipped_examples[0])

    def test_the_clean_feed_accounts_for_every_line(self) -> None:
        report = FaresDb().load_feed(build_synthetic_feed(self.root / "clean")).report
        self.assertEqual(report.lines_read, report.records_parsed)
        self.assertEqual(report.records_skipped, 0)


class MutationTest(unittest.TestCase):
    def test_every_mutation_name_does_something(self) -> None:
        # A mutation that leaves the bytes alone means the fuzzer is testing the
        # clean feed over and over.
        import random

        content = b"AT0000001SDR      1420\nAT0000001CDR      1160\n"
        untouched = []
        for _ in range(400):
            mutated, kind = mutate_file(content, random.Random(_))
            if mutated == content and kind != "add_a_stray_file":
                untouched.append(kind)
        self.assertEqual(untouched, [], f"these mutations changed nothing: {set(untouched)}")

    def test_the_mutation_list_is_what_the_fuzzer_uses(self) -> None:
        import random

        seen = {mutate_file(b"AT0000001SDR      1420\n", random.Random(seed))[1] for seed in range(300)}
        self.assertEqual(seen - set(MUTATIONS), set())
        self.assertGreater(len(seen), 8)


class ProvenanceTest(unittest.TestCase):
    def test_a_value_from_the_file_is_found_whatever_its_case(self) -> None:
        self.assertTrue(_appears("SLP", b"a loc record with slp in it"))
        self.assertTrue(_appears("GRANTHAM", "GRANTHAM CAFÉ".encode("latin-1")))

    def test_a_value_that_was_never_in_the_file_is_not_found(self) -> None:
        self.assertFalse(_appears("ZZZ", b"a loc record with slp in it"))


class FuzzRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.feed = build_synthetic_feed(
            cls.root / "fares", include_unserved_station=True, include_real_shapes=True
        )
        cls.timetable = build_synthetic_timetable(cls.root / "timetable")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_no_round_violates_an_invariant(self) -> None:
        rounds = fuzz(self.feed, rounds=ROUNDS, seed=20260921, work=self.root / "scratch")
        self.assertEqual([result.describe() for result in rounds if not result.ok], [])

    def test_the_same_seed_gives_the_same_rounds(self) -> None:
        first = fuzz(self.feed, rounds=12, seed=5, work=self.root / "one")
        second = fuzz(self.feed, rounds=12, seed=5, work=self.root / "two")
        self.assertEqual(
            [(r.mutations, r.lines_read, r.destinations) for r in first],
            [(r.mutations, r.lines_read, r.destinations) for r in second],
        )

    def test_the_rounds_actually_damage_the_feed(self) -> None:
        rounds = fuzz(self.feed, rounds=ROUNDS, seed=20260921, work=self.root / "biting")
        self.assertTrue(any(result.rejected for result in rounds), "no round rejected a record")
        # And a round that reads a different number of lines than the clean feed
        # is proof the bytes changed, not just the counters.
        clean_lines = FaresDb().load_feed(self.feed).report.lines_read
        self.assertTrue(any(result.lines_read != clean_lines for result in rounds))

    def test_a_failure_names_the_round_the_seed_and_the_mutation(self) -> None:
        result = Round(number=7, seed=3, mutations=("flip_a_byte on rjfaf.ffl",))
        result.violations.append("lines are not accounted for")
        self.assertFalse(result.ok)
        self.assertIn("round 7", result.describe())
        self.assertIn("flip_a_byte", result.describe())

    def test_the_timetable_feed_passes_its_own_invariants(self) -> None:
        self.assertEqual(check_timetable(self.timetable), [])

    def test_a_schedule_with_one_stop_is_a_violation(self) -> None:
        # Build the failing state directly rather than hoping a mutation finds it.
        from atoc_timetable import CallingPoint, Schedule, TimetableDb

        db = TimetableDb()
        db.load_feed(self.timetable)
        db.schedules.append(
            Schedule(
                train_uid="BROKEN",
                stops=(CallingPoint("GRNT", None, 540, None, 540),),
                days="1111110",
                stp_indicator="P",
                date_from="260921",
                date_to="261211",
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken"
            path.mkdir()
            db.load_feed(path)
        violations = check_timetable(self.timetable)
        self.assertEqual(violations, [])


class FuzzCommandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_synthetic_feed(Path(cls._tmp.name) / "fares")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_command_reports_what_it_did(self) -> None:
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = main(["--feed", str(self.feed), "--rounds", "10", "--seed", "2"])
        self.assertEqual(code, 0)
        self.assertIn("10 rounds from seed 2", buffer.getvalue())

    def test_the_command_refuses_a_feed_that_is_not_there(self) -> None:
        self.assertEqual(main(["--feed", "no-such-feed", "--rounds", "1"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
