"""Tests for the fare shapes a real feed has and a tidy invented one does not.

Three of these exist because of one risk: the go/no-go count is a number nobody
can check by hand, so anything the query drops must be dropped out loud.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atoc_fares import LOCATION, FaresDb
from make_synthetic_feed import _line, build_synthetic_feed


class RealShapeFareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_synthetic_feed(Path(cls._tmp.name) / "shapes", include_real_shapes=True)
        cls.db = FaresDb().load_feed(cls.feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def results(self, **kwargs) -> dict[str, object]:
        return {row.crs: row for row in self.db.destinations_within("GRN", 1_000_000, **kwargs)}

    # -- several route codes for one station pair ------------------------

    def test_a_cheaper_route_code_wins_over_the_direct_one(self) -> None:
        nottingham = self.results()["NOT"]
        self.assertEqual(nottingham.best_pence, 990)
        self.assertEqual(nottingham.ticket_code, "CDR")

    def test_a_dearer_route_code_leaves_the_answer_alone(self) -> None:
        self.assertEqual(self.db.flows["0000013"].route_code, "00002")
        self.assertEqual(self.results()["NOT"].best_pence, 990)

    def test_three_flows_still_produce_one_destination(self) -> None:
        flows_to_nottingham = [
            flow.flow_id for flow in self.db.flows.values() if flow.destination_nlc == "2000"
        ]
        self.assertEqual(len(flows_to_nottingham), 3)
        self.assertEqual(sum(1 for crs in self.results() if crs == "NOT"), 1)

    def test_the_party_price_follows_the_cheaper_route(self) -> None:
        rows = {
            row.crs: row
            for row in self.db.destinations_within(
                "GRN", 1_000_000, adults=2, railcard="Two Together", party_budget=True
            )
        }
        # A third off 990 rounds up to 660, and the 1200 minimum applies to SDR,
        # not to the off-peak CDR that won. So the party total is 1320.
        self.assertEqual(rows["NOT"].best_pence, 660)
        self.assertEqual(rows["NOT"].party_pence, 1320)

    # -- what the query refuses to guess ---------------------------------

    def test_a_destination_with_a_fare_and_no_station_code_is_counted(self) -> None:
        tally: dict[str, int] = {}
        results = self.db.destinations_within("GRN", 1_000_000, tally=tally)
        self.assertEqual(tally["destination_has_no_station_code"], 1)
        self.assertNotIn("LONDON ZONES", {row.station for row in results})

    def test_a_destination_with_no_location_record_is_counted(self) -> None:
        tally: dict[str, int] = {}
        self.db.destinations_within("GRN", 1_000_000, tally=tally)
        self.assertEqual(tally["destination_has_no_location_record"], 1)

    def test_the_union_selector_counts_the_unnameable_rows_once(self) -> None:
        # The three modes share the flow loop, so a tally riding on all three
        # would triple-count the rows the feed cannot name (audit A3). The
        # union also runs the publishable leg, which wants the .RST file.
        with tempfile.TemporaryDirectory() as tmp:
            db = FaresDb().load_feed(
                build_synthetic_feed(
                    Path(tmp) / "shapes",
                    include_real_shapes=True,
                    include_restrictions=True,
                )
            )
        tally: dict[str, int] = {}
        db.priced_destinations_within("GRN", 1_000_000, tally=tally)
        self.assertEqual(tally["destination_has_no_station_code"], 1)
        self.assertEqual(tally["destination_has_no_location_record"], 1)

    def test_a_flow_with_no_fare_is_counted(self) -> None:
        tally: dict[str, int] = {}
        results = self.db.destinations_within("GRN", 1_000_000, tally=tally)
        self.assertEqual(tally["flow_with_no_fare"], 1)
        self.assertEqual(results.count(self.results()["LCN"]), 1)

    def test_a_flow_to_another_code_for_the_origin_is_counted(self) -> None:
        tally: dict[str, int] = {}
        results = self.db.destinations_within("GRN", 1_000_000, tally=tally)
        self.assertEqual(tally["fare_to_the_origin_itself"], 1)
        self.assertNotIn("GRANTHAM STN", {row.station for row in results})

    # -- one station code, several location codes ------------------------

    def test_a_fare_departing_from_the_second_code_is_found(self) -> None:
        # Flow 0000016 leaves from 1500, the other Grantham code, and is the
        # cheapest way to Lincoln. A query that knew only one code would miss it
        # and, worse, would return nothing at all.
        results = self.results()
        self.assertEqual(results["LCN"].best_pence, 600)
        self.assertEqual(sorted(results), ["KGX", "LCN", "NOT", "PBO"])

    def test_a_deleted_code_stops_matching_without_taking_the_others(self) -> None:
        withdrawn = FaresDb().load_feed(self.feed)
        withdrawn._load_locations(
            _line(
                {"update_marker": "D", "record_type": "L", "nlc": "1500"},
                LOCATION,
            )
        )
        results = {row.crs: row for row in withdrawn.destinations_within("GRN", 1_000_000)}
        self.assertEqual(results["LCN"].best_pence, 870)
        self.assertEqual(len(results), 4)

    def test_a_losing_fare_is_counted_rather_than_silently_dropped(self) -> None:
        tally: dict[str, int] = {}
        self.db.destinations_within("GRN", 1_000_000, tally=tally)
        self.assertGreaterEqual(tally["cheaper_index_already_held"], 1)
        self.assertGreaterEqual(tally["ticket_is_not_a_standard_return"], 1)

    def test_fares_above_the_budget_are_counted(self) -> None:
        tally: dict[str, int] = {}
        self.db.destinations_within("GRN", 100, tally=tally)
        self.assertGreaterEqual(tally["fare_above_the_budget"], 1)

    def test_the_tally_is_optional_and_changes_nothing(self) -> None:
        tally: dict[str, int] = {}
        self.assertEqual(self.results(), self.results(tally=tally))

    # -- what the feed reports about itself ------------------------------

    def test_a_fare_with_no_flow_record_is_reported(self) -> None:
        self.assertEqual(self.db.stats()["fares_with_no_flow_record"], 1)

    def test_a_location_without_a_station_code_is_reported(self) -> None:
        self.assertEqual(self.db.stats()["locations_without_a_station_code"], 1)

    def test_a_second_location_code_for_one_station_is_reported(self) -> None:
        self.assertEqual(self.db.stats()["extra_location_codes_for_a_station"], 1)

    def test_the_clean_feed_reports_none_of_this(self) -> None:
        clean = FaresDb().load_feed(build_synthetic_feed(Path(self._tmp.name) / "clean"))
        self.assertEqual(clean.stats()["flows"], 6)
        self.assertEqual(clean.stats()["fares"], 10)
        self.assertEqual(clean.stats()["fares_with_no_flow_record"], 0)
        self.assertEqual(clean.stats()["locations_without_a_station_code"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
