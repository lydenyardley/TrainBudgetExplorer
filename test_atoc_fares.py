"""Tests for the fares feed parser, run against a synthetic feed.

Each test asserts a literal value, so a parser that returned nothing would fail.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from atoc_fares import FLOW_F, FLOW_T, Fare, FaresDb, TicketType
from make_synthetic_feed import _line, build_synthetic_feed, write_delete_marker


class FaresParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_synthetic_feed(Path(cls._tmp.name) / "rjfaf-test")
        cls.db = FaresDb().load_feed(cls.feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_reads_stations_and_ticket_descriptions(self) -> None:
        self.assertEqual(self.db.locations_by_crs["GRN"].name, "GRANTHAM")
        self.assertEqual(self.db.locations_by_nlc["2000"].crs, "NOT")
        self.assertEqual(self.db.ticket_types["CDR"].name, "OFF-PEAK DAY R")
        self.assertTrue(self.db.ticket_types["CDR"].restricted_by_train)

    def test_reads_destination_types_from_the_separate_reference_lookup(self) -> None:
        self.assertEqual(self.db.destination_type("NOT"), "city")
        self.assertEqual(self.db.destination_type("GRN"), "town")
        self.assertEqual(self.db.destination_type("XFD"), "other")

    def test_codes_destinations_inside_the_budget_cheapest_first(self) -> None:
        results = self.db.destinations_within("GRN", 2000)
        self.assertEqual([reachable.crs for reachable in results], ["LCN", "NOT"])
        self.assertEqual([reachable.best_pence for reachable in results], [870, 1160])

    def test_focused_load_keeps_the_same_origin_answer_without_unrelated_fares(self) -> None:
        focused = FaresDb().load_feed(self.feed, focus_origin="GRN")
        full = {row.crs: row for row in self.db.destinations_within("GRN", 1_000_000)}
        narrowed = {row.crs: row for row in focused.destinations_within("GRN", 1_000_000)}
        self.assertEqual(narrowed, full)
        self.assertLess(focused.stats()["fares"], self.db.stats()["fares"])
        self.assertEqual(focused._focus_origin_nlcs, {"1000"})

    def test_page_query_drops_all_itx_placeholder_families(self) -> None:
        db = FaresDb().load_feed(self.feed)
        flow_id = next(iter(db.fares_by_flow))
        families = {
            "EIS": "ADVANCE ITX R",
            "EIF": "ADVANCE ITX R",
            "LIS": "ADV ITX STD RTN",
            "LIF": "ADV ITX STD RTN",
            "IF1": "ADVANCE ITX R",
            "IS1": "ADV ITX STD RTN",
        }
        for code, name in families.items():
            db.fares_by_flow[flow_id][code] = Fare(code, 5, "GA")
            db.ticket_types[code] = TicketType(code, name, "2", "R", False)
        rows = db.page_destinations_within("GRN", 1_000_000)
        self.assertTrue(set(families).isdisjoint({row.ticket_code for row in rows}))

    def test_page_single_query_returns_standard_single_fares(self) -> None:
        rows = self.db.page_single_destinations_within("GRN", 1_000_000)
        self.assertTrue(rows)
        self.assertTrue(all(row.ticket_code == "SDS" for row in rows))

    def test_picks_the_cheapest_return_ticket_per_destination(self) -> None:
        results = {reachable.crs: reachable for reachable in self.db.destinations_within("GRN", 3000)}
        self.assertEqual(results["NOT"].ticket_code, "CDR")
        self.assertEqual(results["NOT"].standard_pence, 1160)

    def test_excludes_first_class_over_budget_and_singles(self) -> None:
        codes = {reachable.crs for reachable in self.db.destinations_within("GRN", 2000)}
        self.assertNotIn("XFD", codes)
        self.assertNotIn("PBO", codes)
        self.assertNotIn("KGX", codes)
        self.assertNotIn("GRN", codes)

    def test_respects_non_reversible_flow_direction(self) -> None:
        results = self.db.destinations_within("NOT", 2000)
        self.assertEqual([reachable.crs for reachable in results], ["GRN"])

    def test_reversible_flow_can_be_found_in_both_directions(self) -> None:
        db = FaresDb().load_feed(self.feed, focus_origin="GRN")
        flow_id = "0000090"
        db._load_flows(
            _line(
                {
                    "update_marker": "R",
                    "record_type": "F",
                    "origin_nlc": "2000",
                    "destination_nlc": "1000",
                    "route_code": "01000",
                    "direction": "R",
                    "flow_id": flow_id,
                },
                FLOW_F,
            )
        )
        db._load_flows(
            _line(
                {
                    "update_marker": "R",
                    "record_type": "T",
                    "flow_id": flow_id,
                    "ticket_code": "SDS",
                    "fare_pence": "500",
                },
                FLOW_T,
            )
        )

        self.assertEqual(db.flows[flow_id].direction, "R")
        forward = {row.crs: row for row in db.page_single_destinations_within("GRN", 1_000_000)}
        reverse = {row.crs: row for row in db.page_single_destinations_within("NOT", 1_000_000)}
        self.assertEqual(forward["NOT"].standard_pence, 500)
        self.assertEqual(reverse["GRN"].standard_pence, 500)

    def test_two_together_prices_the_party(self) -> None:
        results = {
            reachable.crs: reachable
            for reachable in self.db.destinations_within("GRN", 2000, adults=2, railcard="Two Together")
        }
        self.assertEqual(results["NOT"].railcard_pence, 770)
        self.assertEqual(results["NOT"].party_pence, 1540)

    def test_railcard_discount_rounds_each_ticket_down_like_national_rail(self) -> None:
        railcard = self.db.railcard_code("Two Together")
        self.assertIsNotNone(railcard)
        # Grantham--Nottingham's observed National Rail prices: £12.10 off-peak
        # becomes £8.05 each, and £13.30 unrestricted becomes £8.85 each.
        self.assertEqual(self.db.railcard_price(railcard, "CDS", 1210), 805)
        self.assertEqual(self.db.railcard_price(railcard, "CDS", 1330), 885)

    def test_flow_validity_dates_exclude_expired_and_future_fares(self) -> None:
        db = FaresDb().load_feed(self.feed)
        flow_id = "0000001"

        def issue(start: str, end: str) -> None:
            db._load_flows(
                _line(
                    {
                        "update_marker": "R",
                        "record_type": "F",
                        "origin_nlc": "1000",
                        "destination_nlc": "2000",
                        "route_code": "00000",
                        "flow_id": flow_id,
                        "start_date": start,
                        "end_date": end,
                    },
                    FLOW_F,
                )
            )

        issue("01012020", "31122020")
        self.assertEqual(db.flows[flow_id].start_date, date(2020, 1, 1))
        self.assertEqual(db.flows[flow_id].end_date, date(2020, 12, 31))
        expired = {}
        self.assertNotIn(
            "NOT",
            {
                row.crs
                for row in db.page_destinations_within(
                    "GRN", 1_000_000, day=date(2026, 9, 24), tally=expired
                )
            },
        )
        self.assertGreaterEqual(expired["flow_expired"], 1)

        issue("01012027", "31122027")
        self.assertNotIn(
            "NOT",
            {
                row.crs
                for row in db.page_single_destinations_within(
                    "GRN", 1_000_000, day=date(2026, 9, 24)
                )
            },
        )

        issue("01012026", "31122026")
        self.assertIn(
            "NOT",
            {row.crs for row in db.page_single_destinations_within(
                "GRN", 1_000_000, day=date(2026, 9, 24)
            )},
        )

    def test_railcard_minimum_fare_never_beats_the_standard_fare(self) -> None:
        results = {
            reachable.crs: reachable
            for reachable in self.db.destinations_within("GRN", 2000, adults=2, railcard="Two Together")
        }
        self.assertEqual(results["LCN"].railcard_pence, 1200)
        self.assertEqual(results["LCN"].best_pence, 870)
        self.assertEqual(results["LCN"].party_pence, 1740)

    def test_party_budget_mode_tests_the_total(self) -> None:
        results = self.db.destinations_within(
            "GRN", 1550, adults=2, railcard="Two Together", party_budget=True
        )
        self.assertEqual([reachable.crs for reachable in results], ["NOT"])

    def test_unknown_origin_and_railcard_raise(self) -> None:
        with self.assertRaises(KeyError):
            self.db.destinations_within("ZZZ", 2000)
        with self.assertRaises(KeyError):
            self.db.destinations_within("GRN", 2000, railcard="Imaginary Railcard")

    def test_delete_marker_removes_a_fare(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        feed = build_synthetic_feed(Path(tmp.name) / "rjfaf-delete")
        db = FaresDb().load_feed(feed)
        self.assertEqual([reachable.crs for reachable in db.destinations_within("GRN", 2000)], ["LCN", "NOT"])
        update = write_delete_marker(feed, "0000002", "SDR")
        db.load_feed(update)
        self.assertEqual([reachable.crs for reachable in db.destinations_within("GRN", 2000)], ["NOT"])

    def test_the_delete_marker_keeps_the_origin_flow_index_in_step(self) -> None:
        # destinations_within reads a per-origin flow index, not a scan of
        # every flow; an incremental delete that removed the flow from the
        # id map but left it indexed by origin would keep selling the fare.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        feed = build_synthetic_feed(Path(tmp.name) / "rjfaf-index-delete")
        db = FaresDb().load_feed(feed)
        delete_flow = feed / "rjfaf-delete-flow.ffl"
        delete_flow.write_text(
            _line(
                {"update_marker": "D", "record_type": "F", "flow_id": "0000001"},
                FLOW_F,
            )
            + "\n",
            encoding="utf-8",
        )
        db.load_feed(delete_flow)
        results = db.destinations_within("GRN", 1_000_000)
        self.assertEqual([reachable.crs for reachable in results], ["LCN", "PBO", "KGX"])
        # ... and a re-issued flow (a real update file re-issues the flow and
        # its fares together) is indexed exactly once, so the fare comes back
        # without doubling.
        reissue = feed / "rjfaf-reissue.ffl"
        reissue.write_text(
            _line(
                {
                    "update_marker": "A",
                    "record_type": "F",
                    "origin_nlc": "1000",
                    "destination_nlc": "2000",
                    "route_code": "00000",
                    "flow_id": "0000001",
                },
                FLOW_F,
            )
            + "\n"
            + _line(
                {
                    "update_marker": "A",
                    "record_type": "T",
                    "flow_id": "0000001",
                    "ticket_code": "SDR",
                    "fare_pence": "1420",
                    "restriction_code": "00",
                },
                FLOW_T,
            )
            + "\n",
            encoding="utf-8",
        )
        db.load_feed(reissue)
        results = db.destinations_within("GRN", 1_000_000)
        self.assertEqual([reachable.crs for reachable in results], ["LCN", "NOT", "PBO", "KGX"])


class PublishableSelectorTest(unittest.TestCase):
    """The reviewed Anytime Day Return selector, before any public price."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_synthetic_feed(
            Path(cls._tmp.name) / "publishable", include_restrictions=True
        )
        cls.db = FaresDb().load_feed(cls.feed)
        cls.plain_feed = build_synthetic_feed(Path(cls._tmp.name) / "plain")
        cls.plain_db = FaresDb().load_feed(cls.plain_feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_selects_only_reviewed_anytime_day_return_fares(self) -> None:
        results = self.db.publishable_destinations_within("GRN", 2000)
        self.assertEqual([reachable.crs for reachable in results], ["LCN", "NOT"])
        self.assertEqual([reachable.best_pence for reachable in results], [870, 1420])
        self.assertEqual({reachable.ticket_code for reachable in results}, {"SDR"})

    def test_refuses_to_run_without_a_restriction_file(self) -> None:
        with self.assertRaises(ValueError) as caught:
            self.plain_db.publishable_destinations_within("GRN", 2000)
        self.assertIn(".RST", str(caught.exception))

    def test_evaluates_a_railcard_against_current_dtd_restrictions(self) -> None:
        rows = self.db.publishable_destinations_within(
            "GRN", 2000, railcard="Two Together"
        )
        # The fixture's general R9 RR row applies to the reviewed SDR fare, so
        # no railcard price is emitted while the standard fare remains useful.
        self.assertEqual({row.crs for row in rows}, {"LCN", "NOT"})
        self.assertTrue(all(row.railcard_pence is None for row in rows))

    def test_a_railcard_price_is_kept_when_no_rr_rule_matches(self) -> None:
        db = FaresDb().load_feed(self.feed)
        db.restrictions.railcard_rows.clear()
        rows = {
            row.crs: row
            for row in db.publishable_destinations_within(
                "GRN", 2000, railcard="Two Together"
            )
        }
        self.assertEqual(rows["LCN"].railcard_pence, 1200)
        self.assertEqual(rows["NOT"].railcard_pence, 1200)

    def test_non_publishable_mode_still_prices_a_railcard_for_analysis(self) -> None:
        results = {
            reachable.crs: reachable
            for reachable in self.plain_db.publishable_destinations_within(
                "GRN", 2000, adults=2, railcard="Two Together", require_restrictions=False
            )
        }
        # SDR carries the Two Together minimum fare of £12.00, so the
        # discounted price is the minimum rather than two thirds of £14.20.
        self.assertEqual(results["NOT"].railcard_pence, 1200)
        self.assertEqual(results["NOT"].ticket_code, "SDR")

    def test_rejects_a_reviewed_ticket_with_an_unreviewed_restriction_code(self) -> None:
        # Sort after rjfaf.ffl: a folder loads in name order, and an earlier
        # name would be overwritten by the blank code in the base fixture.
        update = self.feed / "zz-y2.ffl"
        update.write_text(
            _line(
                {
                    "update_marker": "A",
                    "record_type": "T",
                    "flow_id": "0000001",
                    "ticket_code": "SDR",
                    "fare_pence": "1420",
                    "restriction_code": "Y2",
                },
                FLOW_T,
            )
            + "\n",
            encoding="utf-8",
        )
        db = FaresDb().load_feed(self.feed)
        tally: dict[str, int] = {}
        results = db.publishable_destinations_within("GRN", 2000, tally=tally)
        self.assertEqual([reachable.crs for reachable in results], ["LCN"])
        self.assertGreaterEqual(tally.get("fare_restriction_code_is_not_reviewed", 0), 1)
        # The broad query still sees the restricted fare; only the reviewed
        # selector drops it.
        self.assertIn("NOT", [row.crs for row in db.destinations_within("GRN", 2000)])

    def test_tally_names_the_ticket_filter(self) -> None:
        tally: dict[str, int] = {}
        self.db.publishable_destinations_within("GRN", 1_000_000, tally=tally)
        self.assertGreaterEqual(
            tally.get("ticket_is_not_a_reviewed_anytime_day_return", 0), 1
        )

    def test_the_restriction_file_is_parsed_and_gated(self) -> None:
        self.assertEqual(self.db.restrictions.gate_problem(), None)
        self.assertEqual(self.db.restrictions.record_counts["RH"], 1)
        self.assertEqual(self.db.restrictions.record_counts["RR"], 2)
        self.assertEqual(self.db.restrictions.headers["R1"].description, "PEAK TO LONDON")
        self.assertIn("TWO", self.db.restrictions.railcard_record_counts)
        self.assertEqual(self.plain_db.restrictions.gate_problem() is not None, True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
