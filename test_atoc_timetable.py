"""Tests for the timetable parser and its journey queries.

Each assertion is a literal value, so a parser that returned nothing would fail.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from atoc_timetable import (
    CIF_ORIGIN,
    CIF_SCHEDULE,
    CIF_TERMINUS,
    CIF_TIPLOC_DELETE,
    CIF_TIPLOC_INSERT,
    MSN_STATION,
    TimetableDb,
    format_minutes,
)
from make_synthetic_feed import _line, build_synthetic_timetable

SUNDAY = date(2026, 9, 27)
MONDAY = date(2026, 9, 28)


class TimetableParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_synthetic_timetable(Path(cls._tmp.name) / "timetable")
        cls.timetable = TimetableDb().load_feed(cls.feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_reads_stations_schedules_and_change_times(self) -> None:
        self.assertEqual(self.timetable.station_for_tiploc("GRNT").name, "GRANTHAM")
        self.assertEqual(self.timetable.stats()["schedules"], 11)
        self.assertEqual(self.timetable.connection_minutes_at("NOT"), 10)

    def test_station_names_file_wins_over_a_tiploc_insert(self) -> None:
        self.assertEqual(self.timetable.cif_crs_by_tiploc["NOTT"], "XXX")
        self.assertEqual(self.timetable.crs_for_tiploc("NOTT"), "NOT")

    def test_fastest_direct_train_wins_with_no_changes(self) -> None:
        journey = self.timetable.best_journey("GRN", "NOT")
        self.assertEqual(journey.duration, 45)
        self.assertEqual(journey.changes, 0)
        self.assertEqual(journey.departure, 10 * 60)
        self.assertEqual([leg.train_uid for leg in journey.legs], ["T10004"])

    def test_reads_an_intermediate_calling_point(self) -> None:
        journey = self.timetable.best_journey("GRN", "LCN")
        self.assertEqual(journey.duration, 50)
        self.assertEqual(journey.departure, 9 * 60 + 15)

    def test_one_change_beats_a_slower_direct_train(self) -> None:
        journey = self.timetable.best_journey("GRN", "NWK")
        self.assertEqual(journey.changes, 1)
        self.assertEqual(journey.departure, 10 * 60)
        self.assertEqual(journey.arrival, 11 * 60 + 30)
        self.assertEqual(journey.duration, 90)
        self.assertEqual([leg.train_uid for leg in journey.legs], ["T10004", "T10005"])

    def test_minimum_connection_time_rejects_a_five_minute_change(self) -> None:
        journey = self.timetable.best_journey("GRN", "NWK")
        self.assertNotIn("T10006", [leg.train_uid for leg in journey.legs])

    def test_max_changes_zero_falls_back_to_the_direct_train(self) -> None:
        journey = self.timetable.best_journey("GRN", "NWK", max_changes=0)
        self.assertEqual(journey.changes, 0)
        self.assertEqual(journey.duration, 120)
        self.assertEqual([leg.train_uid for leg in journey.legs], ["T10007"])

    def test_unserved_station_returns_none(self) -> None:
        self.assertIsNone(self.timetable.best_journey("GRN", "XFD"))

    def test_a_weekday_query_applies_the_overlay(self) -> None:
        self.assertEqual(len(self.timetable.active_schedules(MONDAY)), 7)
        journey = self.timetable.best_journey("GRN", "NOT", day=MONDAY)
        self.assertEqual(journey.departure, 10 * 60 + 30)
        self.assertEqual(journey.duration, 45)
        self.assertEqual([leg.train_uid for leg in journey.legs], ["T10004"])

    def test_a_weekday_query_excludes_the_sunday_train(self) -> None:
        journey = self.timetable.best_journey("GRN", "NOT", day=MONDAY)
        self.assertNotIn("T10009", [leg.train_uid for leg in journey.legs])

    def test_a_cancellation_removes_a_destination_on_that_date(self) -> None:
        self.assertIsNone(self.timetable.best_journey("GRN", "PBO", day=MONDAY))
        self.assertEqual(self.timetable.best_journey("GRN", "PBO").duration, 30)

    def test_a_sunday_query_uses_only_the_sunday_train(self) -> None:
        self.assertEqual(len(self.timetable.active_schedules(SUNDAY)), 1)
        journey = self.timetable.best_journey("GRN", "NOT", day=SUNDAY)
        self.assertEqual(journey.duration, 55)
        self.assertEqual([leg.train_uid for leg in journey.legs], ["T10009"])
        self.assertIsNone(self.timetable.best_journey("GRN", "LCN", day=SUNDAY))

    def test_formats_a_duration(self) -> None:
        self.assertEqual(format_minutes(50), "50m")
        self.assertEqual(format_minutes(60), "1h")
        self.assertEqual(format_minutes(95), "1h35")


class TiplocNormalizationTest(unittest.TestCase):
    """Unresolved TIPLOCs are normalised and classified, not just counted."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _schedule(self, uid: str, location: str) -> list[str]:
        return [
            _line(
                {
                    "record_type": "BS",
                    "transaction_type": "N",
                    "train_uid": uid,
                    "date_runs_from": "260921",
                    "date_runs_to": "261211",
                    "days": "1111110",
                    "stp_indicator": "P",
                },
                CIF_SCHEDULE,
            ),
            _line(
                {"record_type": "LO", "location": location, "scheduled_departure": "0900", "public_departure": "0900"},
                CIF_ORIGIN,
            ),
            _line(
                {"record_type": "LT", "location": "GRNT", "scheduled_arrival": "1000", "public_arrival": "1000"},
                CIF_TERMINUS,
            ),
        ]

    def test_a_padded_location_field_normalises_to_one_key(self) -> None:
        feed = build_synthetic_timetable(self.root / "timetable")
        # Eight-character location field whose eighth character is a path flag,
        # so only the first seven characters are the TIPLOC. The old parser took
        # the stripped whole field and sliced it, leaving a trailing space.
        (feed / "padded.mca").write_text(
            "\n".join(self._schedule("T10999", "NOTT   2")) + "\n", encoding="utf-8"
        )
        timetable = TimetableDb().load_feed(feed)
        self.assertIn("NOTT", timetable.used_tiplocs())
        self.assertNotIn("NOTT   ", timetable.used_tiplocs())
        self.assertEqual(timetable.crs_for_tiploc("NOTT"), "NOT")
        self.assertEqual(timetable.crs_for_tiploc(" nott   "), "NOT")
        self.assertIn("NOTT   ", timetable.tiploc_variants["NOTT"])
        self.assertGreaterEqual(timetable.normalized_tiploc_count(), 1)

    def test_a_station_names_header_is_not_read_as_a_station(self) -> None:
        feed = build_synthetic_timetable(self.root / "timetable")
        header = _line(
            {
                "record_type": "A",
                "name": "FILE-SPEC=05 1.00 22/09/26 18.00",
                "category": "S",
                "tiploc": "PEC=05",
                "crs": "2/0",
            },
            MSN_STATION,
        )
        stations = (feed / "stations.msn").read_text(encoding="utf-8")
        (feed / "stations.msn").write_text(header + "\n" + stations, encoding="utf-8")
        timetable = TimetableDb().load_feed(feed)
        self.assertIsNone(timetable.station_for_tiploc("PEC=05"))
        self.assertNotIn("2/0", timetable.crs_by_tiploc.values())
        self.assertEqual(timetable.stats()["stations"], 5)

    def test_a_location_with_no_crs_is_known_not_missing(self) -> None:
        feed = build_synthetic_timetable(self.root / "timetable")
        lines = [
            _line(
                {"record_type": "TI", "tiploc": "OPERTN", "crs": "", "description": "OPERATIONAL LOCATION"},
                CIF_TIPLOC_INSERT,
            )
        ]
        lines.extend(self._schedule("T10998", "OPERTN"))
        (feed / "operational.mca").write_text("\n".join(lines) + "\n", encoding="utf-8")
        timetable = TimetableDb().load_feed(feed)
        self.assertIsNone(timetable.crs_for_tiploc("OPERTN"))
        self.assertEqual(timetable.tiploc_resolution("OPERTN"), "location_record_without_crs")
        self.assertEqual(timetable.tiploc_resolution("NOPE"), "no_record")

    def test_a_tiploc_delete_keeps_the_station_names_entry(self) -> None:
        feed = build_synthetic_timetable(self.root / "timetable")
        # NOTT has an MSN station record (NOT) and a CIF insert (XXX). Deleting
        # the CIF insert must not delete the station names entry.
        # Sort after timetable.mca, or the TI insert in that file re-adds it.
        (feed / "zz-delete.mca").write_text(
            _line({"record_type": "TD", "tiploc": "NOTT"}, CIF_TIPLOC_DELETE) + "\n",
            encoding="utf-8",
        )
        timetable = TimetableDb().load_feed(feed)
        self.assertEqual(timetable.crs_for_tiploc("NOTT"), "NOT")
        self.assertIsNotNone(timetable.station_for_tiploc("NOTT"))
        self.assertNotIn("NOTT", timetable.cif_crs_by_tiploc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
