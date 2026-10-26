"""Tests for how the parsers behave when a feed arrives damaged.

Every test here answers one of two questions: did the damage change an answer it
should not have, or did it get swallowed in silence. A crash is a failure of
both.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.timetable.atoc_timetable import TimetableDb
from trainbudget.feeds.damage_feed import COSMETIC_DAMAGES, STRUCTURAL_DAMAGES, UnknownDamage, damage
from trainbudget.feeds.make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable


def fare_shape(db: FaresDb, origin: str = "GRN") -> list[tuple[str, int, int, str]]:
    """What matters in an answer: which stations, at what price, on what ticket."""
    return sorted(
        (row.crs, row.best_pence, row.party_pence, row.ticket_code)
        for row in db.destinations_within(origin, 1_000_000)
    )


class DamagedFaresFeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.clean = build_synthetic_feed(cls.root / "clean", include_unserved_station=True)
        cls.clean_db = FaresDb().load_feed(cls.clean)
        cls.clean_shape = fare_shape(cls.clean_db)
        cls.clean_stats = dict(cls.clean_db.stats())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def load(self, kind: str, **kwargs) -> FaresDb:
        target = kwargs.pop("target", "ffl")
        where = damage(self.clean, self.root / f"damaged-{kind}", kind, target=target)
        return FaresDb().load_feed(where)

    # -- cosmetic damage changes nothing ---------------------------------

    def test_cosmetic_damage_changes_no_answer(self) -> None:
        for kind in COSMETIC_DAMAGES:
            with self.subTest(kind=kind):
                target = "loc" if kind == "accented_name" else "ffl"
                db = self.load(kind, target=target)
                self.assertEqual(fare_shape(db), self.clean_shape)
                self.assertEqual(db.stats()["flows"], self.clean_stats["flows"])
                self.assertEqual(db.report.records_skipped, 0)

    def test_a_windows_line_ending_is_not_a_rejected_record(self) -> None:
        db = self.load("crlf")
        self.assertEqual(db.report.records_skipped, 0)
        self.assertEqual(db.report.lines_read, self.clean_db.report.lines_read)

    def test_an_accented_station_name_survives_the_encoding_fallback(self) -> None:
        db = self.load("accented_name", target="loc")
        self.assertEqual(db.report.encoding_fallback_lines, 1)
        names = {row.station for row in db.destinations_within("GRN", 1_000_000)}
        self.assertIn("NOTT CAF\u00c9", names)

    def test_a_repeated_record_does_not_double_a_fare(self) -> None:
        db = self.load("repeated_records")
        self.assertEqual(db.stats()["fares"], self.clean_stats["fares"])

    def test_a_byte_order_mark_does_not_become_part_of_the_first_record(self) -> None:
        db = self.load("byte_order_mark")
        self.assertEqual(db.stats()["flows"], self.clean_stats["flows"])

    def test_a_lowercase_record_type_still_reads(self) -> None:
        db = self.load("lowercase_record_types")
        self.assertEqual(db.stats()["fares"], self.clean_stats["fares"])

    def test_the_downloaded_archive_works_inside_its_own_folder(self) -> None:
        db = self.load("zip_in_folder")
        self.assertEqual(fare_shape(db), self.clean_shape)

    # -- structural damage is reported -----------------------------------

    def test_a_truncated_record_is_rejected_and_the_rest_still_loads(self) -> None:
        db = self.load("truncated_record")
        self.assertEqual(db.report.records_skipped, 1)
        self.assertTrue(db.report.skipped_examples)
        before = self.clean_stats["flows"] + self.clean_stats["fares"]
        self.assertEqual(db.stats()["flows"] + db.stats()["fares"], before - 1)
        self.assertEqual(db.stats()["stations"], self.clean_stats["stations"])

    def test_a_record_with_no_fields_left_is_rejected_rather_than_read(self) -> None:
        # The danger is not the crash. It is a cut off fare reading as zero, or a
        # cut off flow id becoming a flow keyed on nothing.
        db = self.load("stubbed_record")
        self.assertEqual(db.report.records_skipped, 1)
        self.assertNotIn("", db.flows)
        self.assertTrue(all(flow.origin_nlc and flow.destination_nlc for flow in db.flows.values()))
        self.assertTrue(all(fare.pence > 0 for bucket in db.fares_by_flow.values() for fare in bucket.values()))

    def test_an_empty_file_drops_records_out_loud(self) -> None:
        tally: dict[str, int] = {}
        db = self.load("empty_file", target="tty")
        results = db.destinations_within("GRN", 1_000_000, tally=tally)
        self.assertEqual(results, [])
        self.assertGreater(tally["fare_with_no_ticket_type"], 0)

    def test_a_stray_file_is_ignored_rather_than_read(self) -> None:
        db = self.load("unknown_file")
        self.assertEqual(db.stats()["flows"], self.clean_stats["flows"])
        self.assertEqual(db.stats()["stations"], self.clean_stats["stations"])

    def test_an_archive_inside_the_archive_is_named_not_decoded(self) -> None:
        db = self.load("nested_archive")
        self.assertEqual(fare_shape(db), self.clean_shape)
        # skipped_files is one channel for every whole-source decision the load
        # made, so its length is not what this test is about: a classification
        # cache under an older schema, or a curated name list this synthetic
        # feed cannot match, lands there too and would change the count for
        # reasons that have nothing to do with the damage. What matters is that
        # the archive inside the archive is named, and named once.
        named = [note for note in db.report.skipped_files if "extra.zip" in note]
        self.assertEqual(len(named), 1)
        self.assertIn("not opened", named[0])

    def test_a_path_that_does_not_exist_fails_loudly(self) -> None:
        # The policy is report or fail, never a quiet empty feed, because an
        # empty feed answers every question with "nowhere".
        with self.assertRaises(FileNotFoundError):
            FaresDb().load_feed(self.root / "no-such-feed")

    def test_an_unknown_damage_name_is_refused(self) -> None:
        with self.assertRaises(UnknownDamage):
            damage(self.clean, self.root / "nope", "shaken")
        with self.assertRaises(UnknownDamage):
            damage(self.clean, self.root / "nope", "truncated_record", target="msn")

    def test_every_named_damage_is_covered_by_this_file(self) -> None:
        # A damage nobody tests is a damage nobody has run.
        tested = set(COSMETIC_DAMAGES) | set(STRUCTURAL_DAMAGES)
        self.assertEqual(tested, set(COSMETIC_DAMAGES) | set(STRUCTURAL_DAMAGES))
        for kind in tested:
            damage(self.clean, self.root / f"all-{kind}", kind, target="loc" if kind == "accented_name" else "ffl")


class DamagedTimetableFeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.clean = build_synthetic_timetable(cls.root / "clean")
        cls.clean_db = TimetableDb().load_feed(cls.clean)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_cosmetic_damage_changes_no_journey(self) -> None:
        for kind in ("crlf", "blank_lines", "no_final_newline", "byte_order_mark", "repeated_records"):
            with self.subTest(kind=kind):
                where = damage(self.clean, self.root / f"mca-{kind}", kind, target="mca")
                db = TimetableDb().load_feed(where)
                self.assertEqual(
                    db.best_journey("GRN", "NOT").duration,
                    self.clean_db.best_journey("GRN", "NOT").duration,
                )
                self.assertEqual(db.report.records_skipped, 0)

    def test_half_removed_from_a_record_leaves_the_journeys_alone(self) -> None:
        # The fields carrying a journey sit early in a CIF record, so half a
        # record is all padding. The next test is the cut that is not.
        where = damage(self.clean, self.root / "mca-truncated", "truncated_record", target="mca")
        db = TimetableDb().load_feed(where)
        self.assertEqual(db.report.records_skipped, 0)
        self.assertEqual(db.stats(), self.clean_db.stats())
        self.assertEqual(
            db.best_journey("GRN", "NOT"),
            self.clean_db.best_journey("GRN", "NOT"),
        )

    def test_a_record_with_no_fields_left_takes_its_schedule_with_it(self) -> None:
        # A schedule is only a train if it has somewhere to start and somewhere
        # to end, so losing a calling point loses the whole train. That is the
        # honest outcome: the alternative is a train that stops once.
        where = damage(self.clean, self.root / "mca-stubbed", "stubbed_record", target="mca")
        db = TimetableDb().load_feed(where)
        self.assertGreaterEqual(db.report.records_skipped, 1)
        self.assertEqual(db.stats()["schedules"], self.clean_db.stats()["schedules"] - 1)
        self.assertTrue(
            all(len(schedule.stops) >= 2 for schedule in db.schedules),
            "a schedule with one stop is not a journey",
        )

    def test_a_stray_file_does_not_become_a_station(self) -> None:
        where = damage(self.clean, self.root / "msn-unknown", "unknown_file", target="msn")
        db = TimetableDb().load_feed(where)
        self.assertEqual(db.stats()["stations"], self.clean_db.stats()["stations"])

    def test_the_archive_inside_its_own_folder_still_loads(self) -> None:
        where = damage(self.clean, self.root / "msn-zipped", "zip_in_folder", target="msn")
        db = TimetableDb().load_feed(where)
        self.assertEqual(db.stats()["schedules"], self.clean_db.stats()["schedules"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
