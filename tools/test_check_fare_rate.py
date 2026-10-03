"""Tests for the price-per-minute gate.

The gate is only worth having if it fails on a bad fare and stays quiet on a
good one, so the tests build both and ask which happens. The feed is never
opened: every row here is constructed, so the suite stays fast and the numbers
in the assertions are the numbers under test rather than the feed's.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

import check_fare_rate
from check_fare_rate import (
    MIN_JOURNEY_MINUTES,
    RATE_CEILING_PENCE_PER_MINUTE,
    RATE_FLOOR_PENCE_PER_MINUTE,
    describe,
    main,
    outside_band,
)

DAY = date(2026, 10, 3)


def row(ticket: str, pence: int, minutes: int, name: str = "ANYTIME DAY S", origin="GRA", to="NOT"):
    return {
        "rate": pence / minutes,
        "pence": pence,
        "minutes": minutes,
        "from": origin,
        "to": to,
        "ticket": ticket,
        "name": name,
    }


class BandTest(unittest.TestCase):
    def test_an_ordinary_fare_is_inside_the_band(self) -> None:
        # GBP 8.00 over 40 minutes is 20 pence a minute, near the measured
        # median of 28.70. It must not be reported.
        rows = [row("SDS", 800, 40)]
        self.assertEqual(outside_band(rows), [])

    def test_a_fare_below_the_floor_is_an_offender(self) -> None:
        rows = [row("QQ1", 5, 145, "A NEW STAFF PASS")]
        self.assertEqual(len(outside_band(rows)), 1)

    def test_a_fare_above_the_ceiling_is_an_offender(self) -> None:
        rows = [row("QQ2", 999_800, 108, "A NEW SENTINEL")]
        self.assertEqual(len(outside_band(rows)), 1)

    def test_a_short_journey_is_not_measured_as_a_rate(self) -> None:
        # A GBP 14.00 minimum across one minute is 1,400 pence a minute and a
        # correct price. Measuring it as a rate would make it the loudest
        # offender in every run and the gate would be noise.
        rows = [row("SDR", 1400, 1, "ANYTIME DAY R")]
        self.assertEqual(outside_band(rows), [])
        # The exclusion is on duration, not on a ceiling the fare could clear,
        # and it ends at the threshold: five minutes is measured.
        self.assertEqual(len(outside_band([row("QQ4", 1, 5, "TOO CHEAP")])), 1)

    def test_the_excluded_rows_are_a_small_share_of_the_feed(self) -> None:
        # Recorded so the exclusion cannot quietly widen. The real feed holds
        # 10,274 such rows of 146,978 published.
        self.assertEqual(MIN_JOURNEY_MINUTES, 5)

    def test_there_is_no_exception_list_to_hide_behind(self) -> None:
        # The gate once carried five reviewed codes, which meant a family
        # reaching a page for an implausible rate was excused instead of
        # removed. Those five are excluded by the selectors now, so the gate
        # has nothing to excuse and a new family has nothing to hide behind.
        self.assertFalse(hasattr(check_fare_rate, "REVIEWED_RATE_EXCEPTIONS"))
        rows = [row("BJD", 5, 145, "AWC STAFF")]
        self.assertEqual(len(outside_band(rows)), 1)

    def test_every_fare_outside_the_band_is_an_offender(self) -> None:
        # The failure this replaced: an offender carrying a name that had been
        # accepted once. It now fails like any other.
        rows = [row("QQ3", 5, 145, "ANOTHER PASS"), row("DGA", 5, 145, "SALE ADVANCE")]
        self.assertEqual(len(outside_band(rows)), 2)

    def test_the_bounds_bracket_the_measured_distribution(self) -> None:
        # Guards a bounds edit that would either trip on ordinary fares or
        # catch nothing. The measured percentiles are in the tool's docstring.
        self.assertLess(RATE_FLOOR_PENCE_PER_MINUTE, 1.85)
        self.assertGreater(RATE_CEILING_PENCE_PER_MINUTE, 200)


class DescribeTest(unittest.TestCase):
    def test_the_report_names_the_code_the_price_and_the_journey(self) -> None:
        offenders = [row("QQ1", 5, 145, "A NEW STAFF PASS")]
        text = describe(offenders, 0.5, 600.0)
        self.assertIn("QQ1", text)
        self.assertIn("A NEW STAFF PASS", text)
        self.assertIn("0.03p/min", text)
        self.assertIn("GBP 0.05", text)
        self.assertIn("145 minutes", text)
        self.assertIn("below the band", text)

    def test_a_large_family_is_bounded_but_the_counts_are_not(self) -> None:
        offenders = [row("QQ1", 5, 100 + index, "BULK") for index in range(40)]
        text = describe(offenders, 0.5, 600.0)
        self.assertIn("40 rows", text)
        self.assertLessEqual(text.count("QQ1 GRA->NOT"), check_fare_rate.NAMED_LIMIT)


class FastestByPairTest(unittest.TestCase):
    """The pair table is built once, so it is worth a test of its two rules."""

    def _timetable(self):
        from types import SimpleNamespace

        schedule = SimpleNamespace(
            stops=[
                SimpleNamespace(alight=530),
                SimpleNamespace(alight=610),
                SimpleNamespace(alight=700),
            ]
        )
        table = mock.Mock()
        table.schedules = [schedule]
        table._schedule_crs = [["GRA", "LCN", "NOT"]]
        table._departures = {"GRA": [(540, 0, 0)]}
        table._ensure_indexes = mock.Mock()
        return table

    def test_a_journey_is_timed_from_its_departure_to_its_arrival(self) -> None:
        fastest = check_fare_rate.fastest_by_pair(self._timetable(), DAY)
        self.assertEqual(fastest[("GRA", "LCN")], 70)
        self.assertEqual(fastest[("GRA", "NOT")], 160)

    def test_the_table_holds_both_directions(self) -> None:
        # A return is priced for the journey either way, so one direction's
        # timing has to answer for both or half the rows go unmeasured.
        fastest = check_fare_rate.fastest_by_pair(self._timetable(), DAY)
        self.assertEqual(fastest[("NOT", "GRA")], fastest[("GRA", "NOT")])
        self.assertEqual(fastest[("LCN", "GRA")], fastest[("GRA", "LCN")])


class PublishedRowsTest(unittest.TestCase):
    def test_a_row_with_no_service_is_not_measured(self) -> None:
        # There is no journey to price it against, and inventing a duration
        # would invent a rate.
        fares = mock.Mock()
        fares.locations_by_crs = {"GRA": mock.Mock()}
        fares.nlcs_by_crs = {"GRA": {"1"}}
        fares.page_single_destinations_within.return_value = [mock.Mock(crs="XXX", best_pence=100, ticket_code="SDS", ticket_name="ANYTIME DAY S")]
        fares.page_destinations_within.return_value = []
        fares.publishable_destinations_within.return_value = []
        rows = check_fare_rate.published_rows(fares, {}, DAY)
        self.assertEqual(rows, [])

    def test_the_same_row_from_two_modes_is_counted_once(self) -> None:
        # The three modes overlap by design, and a row counted twice would
        # inflate the denominator the gate reports.
        same = mock.Mock(crs="NOT", best_pence=800, ticket_code="SDS", ticket_name="ANYTIME DAY S")
        fares = mock.Mock()
        fares.locations_by_crs = {"GRA": mock.Mock()}
        fares.nlcs_by_crs = {"GRA": {"1"}}
        fares.page_single_destinations_within.return_value = [same]
        fares.page_destinations_within.return_value = [same]
        fares.publishable_destinations_within.return_value = []
        rows = check_fare_rate.published_rows(fares, {("GRA", "NOT"): 40}, DAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rate"], 20.0)


class MainTest(unittest.TestCase):
    FEED_ARGS = ["--feed", "no-such-feed", "--timetable", "no-such-timetable"]

    def test_a_missing_feed_is_2_and_not_1(self) -> None:
        # A price being wrong and a feed being absent are different failures.
        # Reporting the second as the first would send a person to a fare.
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(self.FEED_ARGS)
        self.assertEqual(code, 2)
        self.assertIn("will not guess", stderr.getvalue())

    def test_a_clean_run_says_every_fare_is_plausible(self) -> None:
        # The success line names what was checked, so a green gate is not
        # silence that could mean the run measured nothing.
        fares = mock.Mock()
        fares.locations_by_crs = {"GRA": mock.Mock()}
        fares.nlcs_by_crs = {"GRA": {"1"}}
        fares.page_single_destinations_within.return_value = [
            mock.Mock(crs="NOT", best_pence=800, ticket_code="SDS", ticket_name="ANYTIME DAY S")
        ]
        fares.page_destinations_within.return_value = []
        fares.publishable_destinations_within.return_value = []
        db = mock.Mock()
        db.return_value.load_feed.return_value = fares
        timetable = mock.Mock()
        timetable.return_value.load_feed.return_value = self._timetable()
        with mock.patch.object(check_fare_rate, "FaresDb", db), mock.patch.object(
            check_fare_rate, "TimetableDb", timetable
        ), mock.patch.object(check_fare_rate, "fastest_by_pair", return_value={("GRA", "NOT"): 40}), \
            mock.patch.object(Path, "exists", return_value=True):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--feed", "f.zip", "--timetable", "tt"])
        self.assertEqual(code, 0)
        self.assertIn("every published fare is a plausible price", out.getvalue())

    def test_a_clean_run_exits_zero(self) -> None:
        fares = mock.Mock()
        fares.locations_by_crs = {"GRA": mock.Mock()}
        fares.nlcs_by_crs = {"GRA": {"1"}}
        fares.page_single_destinations_within.return_value = [
            mock.Mock(crs="NOT", best_pence=800, ticket_code="SDS", ticket_name="ANYTIME DAY S")
        ]
        fares.page_destinations_within.return_value = []
        fares.publishable_destinations_within.return_value = []
        db = mock.Mock()
        db.return_value.load_feed.return_value = fares
        timetable = mock.Mock()
        timetable.return_value.load_feed.return_value = self._timetable()
        with mock.patch.object(check_fare_rate, "FaresDb", db), mock.patch.object(
            check_fare_rate, "TimetableDb", timetable
        ), mock.patch.object(check_fare_rate, "fastest_by_pair", return_value={("GRA", "NOT"): 40}), \
            mock.patch.object(Path, "exists", return_value=True):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(["--feed", "f.zip", "--timetable", "tt"])
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")

    def test_a_bad_date_is_reported_before_the_feed_is_read(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(Path, "exists", return_value=True):
            with redirect_stderr(stderr):
                code = main(["--feed", "f.zip", "--timetable", "tt", "--day", "nonsense"])
        self.assertEqual(code, 2)
        self.assertIn("not a date", stderr.getvalue())

    def _timetable(self):
        from types import SimpleNamespace

        schedule = SimpleNamespace(
            stops=[SimpleNamespace(alight=530), SimpleNamespace(alight=610)]
        )
        table = mock.Mock()
        table.schedules = [schedule]
        table._schedule_crs = [["GRA", "NOT"]]
        table._departures = {"GRA": [(540, 0, 0)]}
        table._ensure_indexes = mock.Mock()
        return table


if __name__ == "__main__":
    unittest.main(verbosity=2)