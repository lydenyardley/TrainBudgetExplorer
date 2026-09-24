"""Tests for the fares feed parser, run against a synthetic feed.

Each test asserts a literal value, so a parser that returned nothing would fail.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atoc_fares import FLOW_F, FLOW_T, FaresDb
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

    def test_codes_destinations_inside_the_budget_cheapest_first(self) -> None:
        results = self.db.destinations_within("GRN", 2000)
        self.assertEqual([reachable.crs for reachable in results], ["LCN", "NOT"])
        self.assertEqual([reachable.best_pence for reachable in results], [870, 1160])

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

    def test_respects_flow_direction(self) -> None:
        results = self.db.destinations_within("NOT", 2000)
        self.assertEqual([reachable.crs for reachable in results], ["GRN"])

    def test_two_together_prices_the_party(self) -> None:
        results = {
            reachable.crs: reachable
            for reachable in self.db.destinations_within("GRN", 2000, adults=2, railcard="Two Together")
        }
        self.assertEqual(results["NOT"].railcard_pence, 775)
        self.assertEqual(results["NOT"].party_pence, 1550)

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

    def test_refuses_a_railcard_while_the_railcard_records_are_unevaluated(self) -> None:
        with self.assertRaises(ValueError) as caught:
            self.db.publishable_destinations_within("GRN", 2000, railcard="Two Together")
        self.assertIn("railcard", str(caught.exception).lower())

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
