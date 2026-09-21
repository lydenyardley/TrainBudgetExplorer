"""Tests for the feed audit and for parse robustness on damaged input."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
from feed_audit import audit
from make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable


class FeedAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fares = FaresDb().load_feed(
            build_synthetic_feed(Path(cls._tmp.name) / "fares", include_unserved_station=True)
        )
        cls.timetable = TimetableDb().load_feed(build_synthetic_timetable(Path(cls._tmp.name) / "timetable"))
        cls.report = audit(cls.fares, cls.timetable)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_counts_what_each_feed_contributed(self) -> None:
        self.assertEqual(
            self.report["fares_files"],
            ["rjfaf.ffl", "rjfaf.loc", "rjfaf.rcm", "rjfaf.rlc", "rjfaf.tty"],
        )
        self.assertEqual(self.report["timetable_files"], ["stations.msn", "timetable.mca"])
        self.assertEqual(self.report["fares_report"]["files"], 5)
        self.assertEqual(self.report["fares_report"]["skipped"], 0)
        self.assertEqual(self.report["timetable_report"]["skipped"], 0)

    def test_reports_the_timetable_contents(self) -> None:
        self.assertEqual(self.report["timetable"]["schedules"], 11)
        self.assertEqual(self.report["timetable"]["stations"], 5)

    def test_reports_coverage_gaps_between_the_feeds(self) -> None:
        self.assertEqual(self.report["stations_with_a_fare_and_no_timetable_entry"], 3)
        self.assertEqual(self.report["stations_with_a_train_and_no_fare_entry"], 2)
        self.assertEqual(self.report["sample_fare_only_stations"], ["KGX", "SLP", "XFD"])
        self.assertEqual(self.report["sample_timetable_only_stations"], ["NWK", "XXX"])

    def test_reports_no_unresolved_tiplocs(self) -> None:
        self.assertEqual(self.report["unresolved_tiplocs"], 0)

    def test_reports_the_stp_mix_days_and_date_span(self) -> None:
        self.assertEqual(self.report["stp_indicators"], {"P": 9, "O": 1, "C": 1})
        self.assertEqual(self.report["service_day_patterns"], {"1111110": 10, "0000001": 1})
        self.assertEqual(self.report["schedule_dates_from"], "260921")
        self.assertEqual(self.report["schedule_dates_to"], "261211")


class ParseRobustnessTest(unittest.TestCase):
    def test_a_truncated_record_is_rejected_rather_than_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = build_synthetic_timetable(Path(tmp))
            target = path / "timetable.mca"
            lines = target.read_text(encoding="utf-8").splitlines()
            origin_records = [index for index, line in enumerate(lines) if line.startswith("LO")]
            lines[origin_records[2]] = lines[origin_records[2]][:8]
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")

            db = TimetableDb().load_feed(path)
            self.assertEqual(db.report.records_skipped, 1)
            self.assertEqual(len(db.schedules), 10)
            self.assertEqual(len(db.report.skipped_examples), 1)
            self.assertIn("timetable.mca", db.report.skipped_examples[0])

    def test_a_latin1_station_name_still_parses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = build_synthetic_timetable(Path(tmp))
            target = path / "stations.msn"
            lines = target.read_text(encoding="utf-8").splitlines()
            lines[0] = lines[0][:5] + "CAFÉ".ljust(30) + lines[0][35:]
            target.write_bytes(("\n".join(lines) + "\n").encode("latin-1"))

            db = TimetableDb().load_feed(path)
            self.assertEqual(db.report.encoding_fallback_lines, 1)
            self.assertEqual(db.stations_by_tiploc["GRNT"].name, "CAFÉ")

    def test_the_timetable_loader_ignores_fares_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares_folder = build_synthetic_feed(Path(tmp) / "fares", include_unserved_station=True)
            timetable_folder = build_synthetic_timetable(Path(tmp) / "timetable")
            for child in timetable_folder.iterdir():
                child.rename(fares_folder / child.name)

            db = TimetableDb().load_feed(fares_folder)
            self.assertEqual(db.report.files_read, ["stations.msn", "timetable.mca"])
            self.assertEqual(len(db.stations_by_tiploc), 5)
            self.assertEqual(len(db.schedules), 11)

    def test_a_zip_feed_loads_the_same_as_a_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = build_synthetic_feed(Path(tmp) / "fares")
            archive = folder.with_suffix(".zip")
            import zipfile

            with zipfile.ZipFile(archive, "w") as handle:
                for child in folder.iterdir():
                    handle.write(child, child.name)

            from_folder = FaresDb().load_feed(folder)
            from_zip = FaresDb().load_feed(archive)
            self.assertEqual(from_zip.stats(), from_folder.stats())
            self.assertEqual(from_zip.destinations_within("GRN", 2000), from_folder.destinations_within("GRN", 2000))


if __name__ == "__main__":
    unittest.main(verbosity=2)
