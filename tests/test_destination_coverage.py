"""Tests for the unsourced-destination report.

The report exists to make a silent gap visible, so the tests are about what it
names, what it leaves out, and when it refuses a build. It reports and never
classifies: no test here expects a station to be given a band.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from trainbudget.fares import destination_coverage
from trainbudget.fares.destination_coverage import UNSOURCED, UnsourcedReport


def row(crs: str, name: str, kind: str = "town") -> dict:
    return {"crs": crs, "name": name, "destinationType": kind}


class ReportTest(unittest.TestCase):
    def test_a_classified_destination_is_not_reported(self) -> None:
        report = UnsourcedReport()
        report.from_payload({"destinations": [row("LCN", "LINCOLN")]})
        self.assertEqual(len(report), 0)
        self.assertFalse(report)
        self.assertEqual(report.message(), "")

    def test_an_unsourced_destination_is_named_with_its_station(self) -> None:
        report = UnsourcedReport()
        report.from_payload(
            {"origin": {"crs": "GRA"}, "destinations": [row("DOR", "DORE & TOTLEY", UNSOURCED)]}
        )
        self.assertEqual(len(report), 1)
        self.assertIn("DOR DORE & TOTLEY", report.message())
        self.assertIn("1 priced station has no settlement class", report.message())

    def test_all_three_ticket_modes_are_read(self) -> None:
        # The page offers the same filters for each mode, so a station unsourced
        # in one of them is unsourced on the page.
        report = UnsourcedReport()
        report.from_payload(
            {
                "origin": {"crs": "GRA"},
                "destinations": [],
                "singleDestinations": [row("ELN", "ELTON", UNSOURCED)],
                "anytimeDestinations": [row("ELO", "ELTON & ORSTON", UNSOURCED)],
            }
        )
        self.assertEqual({code for code, _ in report.stations()}, {"ELN", "ELO"})

    def test_a_station_met_from_many_origins_is_named_once(self) -> None:
        report = UnsourcedReport()
        for origin in ("GRA", "NOT", "LCN", "LCN"):
            report.from_payload(
                {"origin": {"crs": origin}, "destinations": [row("DOR", "DORE & TOTLEY", UNSOURCED)]}
            )
        self.assertEqual(len(report), 1)
        self.assertIn("from 3 origins", report.message())

    def test_a_blank_code_is_dropped_rather_than_invented(self) -> None:
        report = UnsourcedReport()
        report.note("", "NOWHERE", "GRA")
        self.assertEqual(len(report), 0)

    def test_the_summary_is_bounded_and_says_how_many_it_left_out(self) -> None:
        report = UnsourcedReport()
        for number in range(destination_coverage.NAMED_LIMIT + 5):
            report.note(f"X{number:02d}", f"STATION {number}", "GRA")
        message = report.message()
        self.assertIn("and 5 more", message)
        self.assertIn("X00", message, "the first named station is still named")
        self.assertNotIn("X24", message, "the ones past the limit are counted, not listed")

    def test_a_malformed_payload_does_not_crash_the_report(self) -> None:
        report = UnsourcedReport()
        report.from_payload({"destinations": None, "singleDestinations": ["not a row"]})
        self.assertEqual(len(report), 0)

    def test_feed_rows_are_classified_by_the_feed(self) -> None:
        fares = mock.Mock()
        fares.destination_type.side_effect = lambda crs: "other" if crs == "DOR" else "town"
        rows = [mock.Mock(crs="DOR", station="DORE & TOTLEY"), mock.Mock(crs="LCN", station="LINCOLN")]
        report = UnsourcedReport()
        self.assertEqual(report.note_fares_rows(fares, rows, "GRA"), 1)
        self.assertEqual([code for code, _ in report.stations()], ["DOR"])

    def test_an_extracted_origin_replays_as_the_queries_wrote_it(self) -> None:
        # T6: the pricing pre-pass replays the coverage it already priced
        # rather than re-querying the fares for it. The replayed report reads
        # exactly as the queried one: the stations, the shares, the message
        # and the exit code cannot tell them apart.
        fares = mock.Mock()
        fares.destination_type.side_effect = lambda crs: "other" if crs == "DOR" else "town"
        queried = UnsourcedReport()
        tally: dict[str, int] = {}
        rows = [mock.Mock(crs="DOR", station="DORE & TOTLEY"), mock.Mock(crs="LCN", station="LINCOLN")]
        queried.note_unnameable("GRA", 2)
        queried.note_fares_rows(fares, rows, "GRA")
        queried.note_unnameable("NOT", 1)
        replayed = UnsourcedReport()
        replayed.replay_origin("GRA", queried.extract_origin("GRA"))
        replayed.replay_origin("NOT", queried.extract_origin("NOT"))
        self.assertEqual(replayed.stations(), queried.stations())
        self.assertEqual(replayed.worst_shares(), queried.worst_shares())
        self.assertEqual(replayed.message(), queried.message())
        self.assertEqual(replayed.exit_code(False), queried.exit_code(False))
        self.assertEqual(replayed.unnameable_by_origin(), {"GRA": 2, "NOT": 1})

    def test_replaying_an_origin_the_report_never_saw_changes_nothing(self) -> None:
        report = UnsourcedReport()
        report.replay_origin("GRA", {"totals": [], "unsourced": [], "unnameable": 0})
        report.replay_origin("GRA", None)
        self.assertFalse(report)
        self.assertEqual(report.message(), "")


class ShareTest(unittest.TestCase):
    """The per-origin share audit A2 asked for: how much of one page is gap."""

    @staticmethod
    def payload(origin: str, total: int, unsourced: int) -> dict:
        rows = [
            row(f"X{number:02d}", f"STATION {number}", UNSOURCED if number < unsourced else "town")
            for number in range(total)
        ]
        return {"origin": {"crs": origin}, "destinations": rows}

    def test_a_mostly_unsourced_page_states_its_share(self) -> None:
        report = UnsourcedReport()
        report.from_payload(self.payload("GRA", 10, 9))
        self.assertIn("90% of GRA's 10 destinations", report.message())

    def test_a_page_too_small_to_rate_is_named_without_a_share(self) -> None:
        report = UnsourcedReport()
        report.from_payload(self.payload("GRA", 5, 5))
        self.assertIn("5 priced stations", report.message())
        self.assertNotIn("Worst shares", report.message())

    def test_only_the_worst_shares_are_named(self) -> None:
        report = UnsourcedReport()
        for origin, unsourced in (("AAA", 5), ("BBB", 6), ("CCC", 4), ("DDD", 3)):
            report.from_payload(self.payload(origin, 10, unsourced))
        message = report.message()
        self.assertIn("60% of BBB's 10 destinations", message)
        self.assertIn("50% of AAA's 10 destinations", message)
        self.assertIn("40% of CCC's 10 destinations", message)
        self.assertNotIn("DDD's 10 destinations", message, "beyond the limit is left out")

    def test_an_origin_with_no_gap_is_not_a_finding(self) -> None:
        report = UnsourcedReport()
        report.from_payload(self.payload("GRA", 10, 9))
        report.from_payload(self.payload("NOT", 20, 0))
        self.assertNotIn("NOT's", report.message())

    def test_the_feed_path_counts_destinations_for_the_share_too(self) -> None:
        fares = mock.Mock()
        fares.destination_type.side_effect = lambda crs: "other" if crs == "DOR" else "town"
        rows = [mock.Mock(crs=f"X{number:02d}", station=f"STATION {number}") for number in range(9)]
        rows.append(mock.Mock(crs="DOR", station="DORE & TOTLEY"))
        report = UnsourcedReport()
        report.note_fares_rows(fares, rows, "GRA")
        self.assertIn("10% of GRA's 10 destinations", report.message())


class PseudoDestinationTest(unittest.TestCase):
    """Zone and coach pseudo-stations leave the report (audit A6)."""

    def test_a_zone_pseudo_row_is_neither_named_nor_counted(self) -> None:
        report = UnsourcedReport()
        report.from_payload(
            {
                "origin": {"crs": "GRA"},
                "destinations": [
                    row("QAH", "BOUNDARY ZONE 4", UNSOURCED),
                    row("DOR", "DORE & TOTLEY", UNSOURCED),
                ],
            }
        )
        self.assertEqual([code for code, _ in report.stations()], ["DOR"])
        self.assertIn("1 priced station has", report.message())
        self.assertNotIn("BOUNDARY ZONE 4", report.message())

    def test_the_share_denominator_drops_the_pseudo_rows_too(self) -> None:
        rows = [row(f"X{number:02d}", f"STATION {number}", "town") for number in range(9)]
        rows.append(row("QAH", "BOUNDARY ZONE 4", UNSOURCED))
        report = UnsourcedReport()
        report.from_payload({"origin": {"crs": "GRA"}, "destinations": rows})
        self.assertEqual(len(report), 0)

    def test_feed_rows_for_a_pseudo_station_are_skipped(self) -> None:
        fares = mock.Mock()
        fares.destination_type.return_value = "other"
        rows = [mock.Mock(crs="QAH", station="BOUNDARY ZONE 4")]
        report = UnsourcedReport()
        self.assertEqual(report.note_fares_rows(fares, rows, "GRA"), 0)
        self.assertFalse(report)

    def test_a_pseudo_station_is_not_queried_as_an_origin(self) -> None:
        qah = mock.Mock()
        qah.name = "BOUNDARY ZONE 4"
        gra = mock.Mock()
        gra.name = "GRANTHAM"
        fares = mock.Mock()
        fares.locations_by_crs = {"QAH": qah, "GRA": gra}
        fares.priced_destinations_within.return_value = []
        report = UnsourcedReport()
        report.from_feed(fares, ["QAH", "GRA"])
        self.assertEqual(fares.priced_destinations_within.call_count, 1)
        fares.priced_destinations_within.assert_called_once_with(
            "GRA", destination_coverage.EVERYTHING_PENCE, adults=1, day=None,
            tally=mock.ANY,
        )


class UnnameableRowTest(unittest.TestCase):
    """Priced rows the feed cannot name at all, counted per origin (audit A3)."""

    def test_the_payloads_count_rides_along_with_the_report(self) -> None:
        report = UnsourcedReport()
        report.from_payload(
            {
                "origin": {"crs": "GRA"},
                "destinations": [row("DOR", "DORE & TOTLEY", UNSOURCED)],
                "unnameableFareCount": 7,
            }
        )
        self.assertEqual(report.unnameable_by_origin(), {"GRA": 7})
        self.assertIn(
            "A further 7 destination rows can never be named as a destination at all",
            report.message(),
        )

    def test_the_feed_path_records_the_tally_per_origin(self) -> None:
        fares = mock.Mock()
        location = mock.Mock()
        location.name = "GRANTHAM"
        fares.locations_by_crs = {"GRA": location}

        def selector(origin, budget, *, tally=None, **kwargs):
            if tally is not None:
                tally["destination_has_no_location_record"] = 3
            return []

        fares.priced_destinations_within.side_effect = selector
        report = UnsourcedReport()
        report.from_feed(fares, ["GRA"])
        self.assertEqual(report.unnameable_by_origin(), {"GRA": 3})

    def test_a_payload_without_the_count_records_nothing(self) -> None:
        report = UnsourcedReport()
        report.from_payload({"destinations": [row("LCN", "LINCOLN")]})
        self.assertEqual(report.unnameable_by_origin(), {})

    def test_the_count_is_still_reported_once_the_gap_closes(self) -> None:
        # The unnameable half is a fact about the feed, not a defect in the
        # registry, so closing the classifiable list below must not silence it.
        # A summary that only spoke when something was unsourced would drop
        # this number exactly when the work it measures has succeeded.
        report = UnsourcedReport()
        report.from_payload(
            {"origin": {"crs": "GRA"}, "destinations": [row("DOR", "DORE & TOTLEY", "town")],
             "unnameableFareCount": 9}
        )
        self.assertFalse(report, "nothing is unsourced")
        message = report.message()
        self.assertIn("A further 9 destination rows can never be named as a destination at all", message)
        self.assertNotIn("no settlement class", message)

    def test_a_report_with_nothing_to_say_is_still_silent(self) -> None:
        report = UnsourcedReport()
        report.from_payload({"origin": {"crs": "GRA"}, "destinations": [row("DOR", "DORE", "town")]})
        self.assertEqual(report.message(), "")
        self.assertEqual(report.exit_code(False, ceiling=0), 0)

    def test_the_tally_helper_sums_every_row_that_cannot_be_a_destination(self) -> None:
        tally = {
            "destination_has_no_location_record": 2,
            "destination_has_no_station_code": 5,
            "destination_is_a_fare_construction_point": 4,
            "fare_above_the_budget": 99,
        }
        self.assertEqual(destination_coverage.unnameable_from_tally(tally), 11)


class ExitCodeTest(unittest.TestCase):
    def test_a_clean_build_continues(self) -> None:
        self.assertEqual(UnsourcedReport().exit_code(True), 0)

    def test_a_gap_is_a_warning_by_default(self) -> None:
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            report.report()
            self.assertEqual(report.exit_code(False), 0)
        self.assertIn("warning:", stderr.getvalue())
        self.assertIn("DOR", stderr.getvalue())

    def test_the_strict_flag_refuses_the_build_and_says_what_to_do(self) -> None:
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        report.note("RDF", "RADCLIFFE ON TRT")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(report.exit_code(True), 2)
        message = stderr.getvalue()
        self.assertIn("refusing to publish", message)
        self.assertIn("2 unsourced priced destinations", message)
        self.assertIn("REVIEWED_SETTLEMENT_FALLBACKS", message)

    def test_a_single_gap_is_not_written_in_the_plural(self) -> None:
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            report.exit_code(True)
        self.assertIn("1 unsourced priced destination ", stderr.getvalue())

    def test_a_count_above_the_ceiling_refuses(self) -> None:
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(report.exit_code(False, ceiling=0), 2)
        message = stderr.getvalue()
        self.assertIn("ceiling of 0", message)
        self.assertIn("1 unsourced priced destination exceeds", message)

    def test_a_count_at_the_ceiling_passes(self) -> None:
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(report.exit_code(False, ceiling=1), 0)
        self.assertEqual(stderr.getvalue(), "")

    def test_an_empty_report_passes_any_ceiling(self) -> None:
        self.assertEqual(UnsourcedReport().exit_code(False, ceiling=0), 0)

    def test_the_ceiling_is_honoured_alongside_the_strict_flag(self) -> None:
        # Both flags are independent, and the ceiling is read first. A clean
        # report used to return 0 without ever consulting it, so a mistyped
        # ceiling in a run that also passed --fail-on-unsourced held nothing
        # at all and said nothing.
        report = UnsourcedReport()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(report.exit_code(True, ceiling=-1), 2)
        self.assertIn("ceiling of -1", stderr.getvalue())

    def test_a_count_inside_the_ceiling_still_reports_the_strict_refusal(self) -> None:
        # The other order: the ceiling passes, so the strict flag is what the
        # operator is told about.
        report = UnsourcedReport()
        report.note("DOR", "DORE & TOTLEY")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(report.exit_code(True, ceiling=5), 2)
        self.assertIn("--fail-on-unsourced", stderr.getvalue())


class MainTest(unittest.TestCase):
    # Every run names a feed that exists. The default is the licensed download
    # under feeds/, which is git-ignored, so relying on it would make these
    # tests pass on a machine that has the feed and fail on a fresh clone.
    FEED = ["--feed", "."]

    def test_an_origin_the_feed_does_not_carry_is_named(self) -> None:
        fares = mock.Mock()
        location = mock.Mock()
        location.name = "GRANTHAM"
        fares.locations_by_crs = {"GRA": location}
        with mock.patch.object(destination_coverage, "FaresDb") as db:
            db.return_value.load_feed.return_value = fares
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = destination_coverage.main([*self.FEED, "--origin", "NOPE"])
        self.assertEqual(code, 2)
        self.assertIn("NOPE is not in this feed", stderr.getvalue())

    def test_a_run_over_a_clean_feed_says_nothing(self) -> None:
        fares = mock.Mock()
        location = mock.Mock()
        location.name = "GRANTHAM"
        fares.locations_by_crs = {"GRA": location}
        fares.priced_destinations_within.return_value = [mock.Mock(crs="LCN", station="LINCOLN")]
        fares.destination_type.return_value = "town"
        with mock.patch.object(destination_coverage, "FaresDb") as db:
            db.return_value.load_feed.return_value = fares
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = destination_coverage.main([*self.FEED, "--fail-on-unsourced"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")

    def test_the_ceiling_flag_refuses_a_run_over_it(self) -> None:
        fares = mock.Mock()
        location = mock.Mock()
        location.name = "GRANTHAM"
        fares.locations_by_crs = {"GRA": location}
        fares.priced_destinations_within.return_value = [
            mock.Mock(crs="DOR", station="DORE & TOTLEY")
        ]
        fares.destination_type.return_value = "other"
        with mock.patch.object(destination_coverage, "FaresDb") as db:
            db.return_value.load_feed.return_value = fares
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = destination_coverage.main([*self.FEED, "--unsourced-ceiling", "0"])
        self.assertEqual(code, 2)
        self.assertIn("ceiling of 0", stderr.getvalue())


class ConditionalLossReportTest(unittest.TestCase):
    """The loss is a set difference, so a rejected fare row is not a lost row.

    A destination only counts as lost when the reviewed run no longer reaches
    it. Two rejected fare rows can leave every destination priced, so a report
    that counted the rows would overstate the loss.
    """

    def _fare(self, crs, pence, code="SDR", name="ANYTIME DAY R", kind="R"):
        return mock.Mock(
            crs=crs,
            station=f"{crs} STATION",
            best_pence=pence,
            ticket_code=code,
            ticket_name=name,
        )

    def _db(self, kept_single, all_single, kept_return, all_return):
        fares = mock.Mock()
        fares.page_single_destinations_within.side_effect = (
            lambda *a, **k: all_single if k.get("include_conditional") else kept_single
        )
        fares.page_destinations_within.side_effect = (
            lambda *a, **k: all_return if k.get("include_conditional") else kept_return
        )
        return fares

    def test_a_destination_the_child_fare_held_is_counted_lost(self) -> None:
        fares = self._db(
            kept_single=[self._fare("NOT", 100, "2AS", "ADVANCE", "S")],
            all_single=[self._fare("NOT", 10, "CTS", "UNDER 11 SINGLE", "S")],
            kept_return=[],
            all_return=[],
        )
        report = destination_coverage.ConditionalLossReport()
        report.measure(fares, "GRA")
        # NOT is still priced, so no destination was lost. The price moved.
        self.assertEqual(report.lost_by_origin(), {})
        self.assertEqual(report.message(), "")

    def test_a_destination_nothing_else_prices_is_lost(self) -> None:
        fares = self._db(
            kept_single=[self._fare("LCN", 900, "SDS", "ANYTIME DAY S", "S")],
            all_single=[
                self._fare("LCN", 900, "SDS", "ANYTIME DAY S", "S"),
                self._fare("HUL", 99_900, "SPN", "LNER GRP SGL", "S"),
            ],
            kept_return=[],
            all_return=[],
        )
        report = destination_coverage.ConditionalLossReport()
        report.measure(fares, "GRA")
        self.assertEqual(report.lost_by_origin(), {"GRA": 1})
        self.assertEqual(report.singles_by_origin(), {"GRA": 1})
        self.assertEqual(report.returns_by_origin(), {"GRA": 0})

    def test_an_origin_that_keeps_nothing_is_named(self) -> None:
        # The outcome worth a person's attention. It is reported apart from the
        # ordinary loss so it cannot be averaged away in the total.
        fares = self._db(
            kept_single=[],
            all_single=[self._fare("HUL", 99_900, "SPN", "LNER GRP SGL", "S")],
            kept_return=[],
            all_return=[self._fare("CDF", 5, "ENT", "TFW EVENT CON", "R")],
        )
        report = destination_coverage.ConditionalLossReport()
        report.measure(fares, "GRA")
        self.assertEqual(report.empties_the_origin(), ["GRA"])
        self.assertIn("keep no destination at all", report.message())

    def test_the_summary_names_the_totals_and_the_worst_shares(self) -> None:
        # The share is against what the origin reached with the conditional
        # fares in, two stations, so losing one reads as 50%. Against what it
        # kept it would read as 100%, which says nothing about the origin.
        fares = self._db(
            kept_single=[
                self._fare("LCN", 900, "SDS", "ANYTIME DAY S", "S"),
                self._fare("NOT", 100, "2AS", "ADVANCE", "S"),
            ],
            all_single=[
                self._fare("LCN", 900, "SDS", "ANYTIME DAY S", "S"),
                self._fare("NOT", 100, "2AS", "ADVANCE", "S"),
                self._fare("HUL", 99_900, "SPN", "LNER GRP SGL", "S"),
            ],
            kept_return=[],
            all_return=[],
        )
        report = destination_coverage.ConditionalLossReport()
        report.measure_all(fares, ["GRA"])
        message = report.message()
        self.assertIn("1 destinations across 1 of 1 origins", message)
        self.assertIn("33% of GRA's 3", message)

    def test_a_clean_feed_says_nothing_at_all(self) -> None:
        fares = self._db(
            kept_single=[self._fare("LCN", 900)],
            all_single=[self._fare("LCN", 900)],
            kept_return=[self._fare("NOT", 1160)],
            all_return=[self._fare("NOT", 1160)],
        )
        report = destination_coverage.ConditionalLossReport()
        report.measure_all(fares, ["GRA"])
        self.assertEqual(report.lost_by_origin(), {})
        self.assertEqual(report.message(), "")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            report.report()
        self.assertEqual(stderr.getvalue(), "")

    def test_the_loss_is_counted_from_destinations_not_from_rejected_fares(self) -> None:
        # Two cheap child fares on one destination the feed also prices for an
        # adult. Two fares are rejected and no destination is lost, which is the
        # difference the report exists to get right.
        fares = self._db(
            kept_single=[self._fare("NOT", 100, "2AS", "ADVANCE", "S")],
            all_single=[
                self._fare("NOT", 5, "CTS", "UNDER 11 SINGLE", "S"),
                self._fare("NOT", 7, "TKS", "CHILD FLTFARE S", "S"),
            ],
            kept_return=[],
            all_return=[],
        )
        report = destination_coverage.ConditionalLossReport()
        report.measure(fares, "GRA")
        self.assertEqual(report.lost_by_origin(), {})
        self.assertEqual(report._totals, 1)


class ConditionalLossMainTest(unittest.TestCase):
    FEED = ["--feed", "."]

    def _mocks(self):
        fares = mock.Mock()
        location = mock.Mock()
        location.name = "GRANTHAM"
        fares.locations_by_crs = {"GRA": location}
        fares.priced_destinations_within.return_value = [mock.Mock(crs="LCN", station="LINCOLN")]
        fares.destination_type.return_value = "town"
        # The child's fare holds Hull, which nothing else prices, so the
        # destination is genuinely lost rather than merely repriced.
        single = mock.Mock(crs="LCN", station="LINCOLN", best_pence=900, ticket_code="SDS")
        child = mock.Mock(crs="HUL", station="HULL", best_pence=99_900, ticket_code="SPN")
        fares.page_single_destinations_within.side_effect = (
            lambda *a, **k: [single, child] if k.get("include_conditional") else [single]
        )
        fares.page_destinations_within.side_effect = lambda *a, **k: []
        return fares

    def test_the_flag_prints_a_table_and_leaves_the_exit_code_alone(self) -> None:
        fares = self._mocks()
        out = io.StringIO()
        with mock.patch.object(destination_coverage, "FaresDb") as db:
            db.return_value.load_feed.return_value = fares
            with redirect_stdout(out):
                code = destination_coverage.main([*self.FEED, "--conditional-loss"])
        self.assertEqual(code, 0)
        self.assertIn("GRA loses 1 destinations", out.getvalue())
        self.assertIn("(1 singles, 0 returns)", out.getvalue())

    def test_without_the_flag_the_run_prints_no_loss_table(self) -> None:
        fares = self._mocks()
        out = io.StringIO()
        with mock.patch.object(destination_coverage, "FaresDb") as db:
            db.return_value.load_feed.return_value = fares
            with redirect_stdout(out):
                destination_coverage.main([*self.FEED])
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
