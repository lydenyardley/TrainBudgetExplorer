"""Tests for the timetable parser and its journey queries.

Each assertion is a literal value, so a parser that returned nothing would fail.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from atoc_timetable import (
    CIF_INTERMEDIATE,
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

    def test_focused_load_is_narrower_and_reuses_its_cache(self) -> None:
        cache = Path(self._tmp.name) / "timetable-cache.pickle"
        focused = TimetableDb().load_feed(
            self.feed,
            focus_origin="GRN",
            focus_destinations={"LCN"},
            cache_path=cache,
        )
        self.assertLess(focused.stats()["schedules"], self.timetable.stats()["schedules"])
        self.assertIsNotNone(focused.best_journey("GRN", "NOT"))
        self.assertTrue(cache.is_file(), "a focused load leaves a cache for the next one")
        cached = TimetableDb().load_feed(
            self.feed,
            focus_origin="GRN",
            focus_destinations={"LCN"},
            cache_path=cache,
        )
        self.assertEqual(cached.stats(), focused.stats())
        self.assertEqual(cached.best_journey("GRN", "NOT").duration, 45)

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

    def test_departures_lists_each_departure_time_once(self) -> None:
        # One entry per departure time, earliest first, capped at the limit.
        # departures() is a second one-change search that runs per destination
        # on a real page, and it had no test of its own; the index it now reads
        # (_schedule_dest_stops) is exercised here through a change, which is
        # the only way this function reaches that index at all.
        rows = self.timetable.departures("GRN", "NOT", limit=5)
        self.assertEqual(
            [(row.departure, row.arrival, row.changes) for row in rows],
            [
                (7 * 60, 8 * 60 + 50, 0),
                (8 * 60, 8 * 60 + 55, 0),
                (9 * 60, 9 * 60 + 50, 0),
                (10 * 60, 10 * 60 + 45, 0),
                (10 * 60 + 30, 11 * 60 + 15, 0),
            ],
        )

    def test_departures_and_best_journey_agree_on_the_fastest_option(self) -> None:
        # The two one-change searches are twins reading the same indexes. They
        # answer different questions -- best_journey returns the shortest
        # journey, departures returns the next ways to leave, one per departure
        # time -- so they are not equal. But the shortest journey has to be one
        # of the ways to go, or the page would show a "minutes" figure its own
        # departure list contradicts.
        for destination in ("NOT", "LCN", "NWK"):
            best = self.timetable.best_journey("GRN", destination)
            options = self.timetable.departures("GRN", destination, limit=50)
            self.assertTrue(options, f"{destination} has no options")
            shown = {
                (row.departure, row.arrival, row.changes, tuple(leg.train_uid for leg in row.legs))
                for row in options
            }
            self.assertIn(
                (best.departure, best.arrival, best.changes, tuple(leg.train_uid for leg in best.legs)),
                shown,
                f"{destination}: the shortest journey is not among the ways to go",
            )

    def test_departures_finds_a_one_change_option_the_direct_search_misses(self) -> None:
        # Norwich has no single train from Grantham, so every option here is a
        # change. This is the path that regressed: the un-indexed twin scanned
        # every onward stop and this function had no test to catch it.
        rows = self.timetable.departures("GRN", "NWK", limit=5)
        self.assertEqual(
            [(row.departure, row.changes) for row in rows],
            [
                (7 * 60, 1),
                (8 * 60, 1),
                (9 * 60, 1),
                (10 * 60, 1),
                (12 * 60, 0),
            ],
        )
        for row in rows:
            self.assertEqual(len(row.legs), 1 + row.changes)

    def test_departures_for_an_unserved_station_is_empty(self) -> None:
        self.assertEqual(self.timetable.departures("GRN", "XFD", limit=5), [])

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


class PassingStopTest(unittest.TestCase):
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
            "\n".join(self._schedule("T90001", passing=True)) + "\n", encoding="utf-8"
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
            "\n".join(self._schedule("T90002", passing=False)) + "\n", encoding="utf-8"
        )
        timetable = TimetableDb().load_feed(self.feed)
        journey = timetable.best_journey("GRN", "LCN", day=MONDAY)
        self.assertIsNotNone(journey, "a train that calls at Grindleford is boardable")
        self.assertEqual(journey.duration, 75, "09:55 at Grindleford to 11:15 at Lincoln")

    def test_no_journey_departs_at_minute_zero(self) -> None:
        # The symptom in one assertion, over both services on the same feed.
        (self.feed / "both.mca").write_text(
            "\n".join(self._schedule("T90003", passing=True))
            + "\n"
            + "\n".join(self._schedule("T90004", passing=False))
            + "\n",
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


class TimetableFocusTest(unittest.TestCase):
    """The timetable index is scoped to the stations the page can show.

    It was scoped to the stations a return reaches, which is a narrower set:
    the outbound-single list reaches thirteen more on a real page. Those
    stations had no services in the index, so each was a row reading "No
    service" and "Unknown" -- a statement about the build wearing the voice of
    a statement about the network.

    This reads the wiring rather than driving the build. The behaviour needs
    the real feed and a station reachable only as an outbound single, which no
    synthetic fixture has; the behavioural guard is the browser check that no
    row claims no service for a destination the page's own payload times, and
    that check can only fail on a real page. This one runs everywhere.
    """

    def test_the_focus_set_covers_every_list_the_page_composes(self) -> None:
        source = Path(__file__).resolve().parent.parent / "build_demo_page.py"
        code = source.read_text(encoding="utf-8")
        start = code.index("focus_destinations: set[str] = set()")
        block = code[start:code.index("cache_path = (", start)]
        for query in (
            "page_destinations_within",
            "page_single_destinations_within",
            "publishable_destinations_within",
        ):
            self.assertIn(
                query, block,
                f"the timetable focus set does not include {query}, so one of the "
                f"three lists the page composes has no services in the index",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
