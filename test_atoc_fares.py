"""Tests for the fares feed parser, run against a synthetic feed.

Each test asserts a literal value, so a parser that returned nothing would fail.
"""

from __future__ import annotations

import io
import dataclasses
import tempfile
import unittest
from unittest import mock

import atoc_fares
from datetime import date
from pathlib import Path

from atoc_fares import (
    DESTINATION_FACET_SOURCES,
    DESTINATION_FACETS_BY_KEY,
    DESTINATION_FACET_READERS,
    DESTINATION_TYPE_FILTERS,
    SUPPORTED_DESTINATION_FACETS,
    FLOW_F,
    FLOW_T,
    Fare,
    FaresDb,
    Location,
    TicketType,
)
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
        self.assertEqual(self.db.destination_types("NOT"), ["city", "university"])
        self.assertEqual(self.db.destination_types("LCN"), ["city", "seaside", "university"])
        self.assertEqual(self.db.destination_types("XFD"), ["other", "island"])
        self.assertIn("synthetic", self.db.location_type_source or "")

    def test_facets_from_several_files_are_merged_not_replaced(self) -> None:
        # The checked-in reference data, a cache beside the feed and the feed's
        # own lookup can all name the same station. Replacing made the answer
        # depend on the order the files were read in, and let a stale cache
        # drop a facet the checked-in file knew about.
        db = FaresDb()
        db._merge_location_facets("LCN", ["seaside"])
        db._merge_location_facets("LCN", ["university"])
        db._merge_location_facets("LCN", ["island", "nonsense"])
        self.assertEqual(db.location_facets_by_crs["LCN"], {"island", "seaside", "university"})
        db._merge_location_facets("  lcn ", "university")
        self.assertEqual(db.location_facets_by_crs["LCN"], {"island", "seaside", "university"})
        self.assertNotIn("lcn", db.location_facets_by_crs)

    def test_major_london_and_non_england_wales_stations_have_a_fallback(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {
            "KGX": Location("1000", "KGX", "LONDON KINGS X", ""),
            "GLC": Location("2000", "GLC", "GLASGOW CENTRAL", ""),
            "CDD": Location("3000", "CDD", "CARDIFF CENTRAL", ""),
        }
        db._apply_major_station_fallbacks()
        self.assertEqual(db.destination_type("KGX"), "city")
        self.assertEqual(db.destination_type("GLC"), "city")
        self.assertEqual(db.destination_type("CDD"), "city")
        self.assertIn("London", db.location_type_source or "")

    def test_every_facet_declares_a_readable_source_and_reaches_the_filter(self) -> None:
        for facet in DESTINATION_FACET_SOURCES:
            self.assertIn(facet.key, SUPPORTED_DESTINATION_FACETS)
            self.assertIn((facet.key, facet.label), DESTINATION_TYPE_FILTERS)
            self.assertTrue(facet.source.strip(), facet.key)
            self.assertTrue(facet.coverage.strip(), facet.key)
            if facet.reviewed_station_codes:
                # A reviewed facet has to say so, or the page reads as if an
                # official list produced it.
                self.assertIn("reviewed", facet.source.lower())
            else:
                self.assertTrue(facet.url.startswith("http"), facet.key)
                self.assertIn(facet.reader, DESTINATION_FACET_READERS)
        # The primary classes come first, and the facets follow in registry
        # order, so the filter reads settlements first and character last.
        self.assertEqual(
            [key for key, _ in DESTINATION_TYPE_FILTERS],
            ["city", "town", "other"] + [facet.key for facet in DESTINATION_FACET_SOURCES],
        )

    def test_a_facet_with_no_registered_reader_is_reported_not_raised_as_keyerror(self) -> None:
        db = FaresDb()
        broken = dataclasses.replace(DESTINATION_FACETS_BY_KEY["seaside"], reader="not_a_reader")
        with self.assertRaises(ValueError):
            db._apply_destination_facet(broken)

    def test_a_facet_source_with_no_readable_settlements_is_reported(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {"NOT": Location("1", "NOT", "NOTTINGHAM", "")}
        db._read_ons_coastal_facet = lambda: set()  # type: ignore[method-assign]
        with self.assertRaises(ValueError):
            db._apply_destination_facet(DESTINATION_FACETS_BY_KEY["seaside"])
        self.assertEqual(db.location_facets_by_crs, {})

    def test_learning_provider_reader_reads_the_town_column_by_name(self) -> None:
        body = (
            "UKPRN\tPROVIDER_NAME\tPOSTCODE\tTOWN\r\n"
            "10007774\tUNIVERSITY OF OXFORD\tOX1 2JD\tOxford\r\n"
            "10007775\tUNIVERSITY OF YORK\tYO1 9DD\tYork\r\n"
            "10007776\tA COLLEGE WITH NO TOWN\t\t\r\n"
        )
        db = FaresDb()
        with mock.patch.object(atoc_fares.urllib.request, "urlopen", return_value=io.BytesIO(body.encode())):
            names = db._read_learning_provider_facet()
        self.assertEqual(names, {"OXFORD", "YORK"})
        with mock.patch.object(
            atoc_fares.urllib.request,
            "urlopen",
            return_value=io.BytesIO(b"UKPRN\tPROVIDER_NAME\r\n10007774\tOXFORD\r\n"),
        ):
            with self.assertRaises(ValueError):
                db._read_learning_provider_facet()

    def test_a_facet_source_applies_by_settlement_name(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {
            "OXF": Location("1", "OXF", "OXFORD", ""),
            "YRK": Location("2", "YRK", "YORK", ""),
            "NWE": Location("3", "NWE", "NEWPORT", ""),
        }
        db._read_learning_provider_facet = lambda: {"OXFORD", "YORK"}  # type: ignore[method-assign]
        db._apply_destination_facet(DESTINATION_FACETS_BY_KEY["university"])
        self.assertEqual(db.location_facets_by_crs["OXF"], {"university"})
        self.assertEqual(db.location_facets_by_crs["YRK"], {"university"})
        self.assertNotIn("NWE", db.location_facets_by_crs)

    def test_reviewed_facets_only_tag_stations_the_feed_actually_has(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {
            "HHD": Location("1", "HHD", "HOLYHEAD", ""),
            "NOT": Location("2", "NOT", "NOTTINGHAM", ""),
        }
        island = DESTINATION_FACETS_BY_KEY["island"]
        self.assertIn("HHD", island.reviewed_station_codes)
        self.assertNotIn("NOT", island.reviewed_station_codes)
        db._apply_reviewed_facets()
        self.assertEqual(db.location_facets_by_crs["HHD"], {"island"})
        self.assertNotIn("NOT", db.location_facets_by_crs)

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

    def test_persisted_origin_indexes_are_isolated_and_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            common, indexes = root / "common.pickle", root / "indexes"
            self.db.write_fare_indexes(common, indexes, ["GRN", "LCN"])

            grantham = FaresDb.load_fare_index(common, indexes / "GRN.pickle")
            lincoln = FaresDb.load_fare_index(common, indexes / "LCN.pickle")
            self.assertEqual(grantham._cache_origin, "GRN")
            self.assertEqual(lincoln._cache_origin, "LCN")
            self.assertEqual(
                {row.crs for row in grantham.destinations_within("GRN", 2000)},
                {"LCN", "NOT"},
            )
            self.assertEqual(
                [row.crs for row in lincoln.destinations_within("LCN", 2000)],
                [],
            )
            self.assertLess(grantham.stats()["fares"], self.db.stats()["fares"])

            # The persisted index is usable without reopening the source feed.
            source_backup = root / "feed-copy"
            source_backup.mkdir()
            for item in self.feed.iterdir():
                source_backup.joinpath(item.name).write_bytes(item.read_bytes())
            for item in source_backup.iterdir():
                item.unlink()
            reopened = FaresDb.load_fare_index(common, indexes / "GRN.pickle")
            self.assertEqual(
                [row.crs for row in reopened.destinations_within("GRN", 2000)],
                ["LCN", "NOT"],
            )

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

    @unittest.skipUnless(
        Path("feeds/fares/dtd-fares.zip").is_file(),
        "licensed DTD feed is not available",
    )
    def test_real_gra_to_not_keeps_two_together_r9_price(self) -> None:
        db = FaresDb().load_feed("feeds/fares/dtd-fares.zip", focus_origin="GRA")
        row = next(
            row
            for row in db.page_destinations_within("GRA", 1_000_000)
            if row.crs == "NOT"
        )
        code = db.railcard_code("Two Together")
        rules = db.railcard_rules(
            code,
            ticket_code=row.ticket_code,
            route_code=row.route_code,
            origin_crs="GRA",
            destination_crs=row.crs,
            origin_nlc=row.origin_nlc,
            destination_nlc=row.destination_nlc,
        )
        self.assertEqual([rule.restriction_code for rule in rules], ["R9"])
        self.assertFalse(any(rule.total_ban for rule in rules))
        self.assertEqual(
            db.railcard_price_for(
                code,
                ticket_code=row.ticket_code,
                route_code=row.route_code,
                origin_crs="GRA",
                destination_crs=row.crs,
                origin_nlc=row.origin_nlc,
                destination_nlc=row.destination_nlc,
                standard_pence=row.standard_pence,
            ),
            db.railcard_price(code, row.ticket_code, row.standard_pence),
        )

    def test_rr_restriction_code_is_a_condition_not_a_railcard_ban(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
        rules = db.railcard_rules(
            "TWO",
            ticket_code="CDR",
            route_code="00000",
            origin_crs="GRN",
            destination_crs="NOT",
            origin_nlc="1000",
            destination_nlc="2000",
        )
        self.assertEqual([rule.restriction_code for rule in rules], ["R9"])
        self.assertFalse(any(rule.total_ban for rule in rules))
        self.assertIsNone(
            db.railcard_restriction(
                "TWO",
                ticket_code="CDR",
                route_code="00000",
                origin_crs="GRN",
                destination_crs="NOT",
                origin_nlc="1000",
                destination_nlc="2000",
            )
        )

    def test_rr_total_ban_still_removes_the_discount(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
        context = {
            "ticket_code": "SDR",
            "route_code": "00002",
            "origin_crs": "GRN",
            "destination_crs": "NOT",
            "origin_nlc": "1000",
            "destination_nlc": "2000",
        }
        self.assertTrue(db.railcard_restriction("TWO", **context).total_ban)
        self.assertIsNone(
            db.railcard_price_for("TWO", standard_pence=2400, **context)
        )

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
        # The fixture's general R9 RR row attaches the Two Together travel
        # condition. It is not a total ban, so the reviewed fares stay priced.
        self.assertEqual({row.crs for row in rows}, {"LCN", "NOT", "PBO"})
        prices = {row.crs: row.railcard_pence for row in rows}
        self.assertEqual(prices, {"LCN": 1200, "NOT": 1200, "PBO": 1490})

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
