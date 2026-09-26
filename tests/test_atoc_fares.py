"""Tests for the fares feed parser, run against a synthetic feed.

Each test asserts a literal value, so a parser that returned nothing would fail.
"""

from __future__ import annotations

import io
import dataclasses
import json
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
    LOCATION_BAND_TYPES,
    LOCATION_CACHE_SCHEMA,
    LOCATION_FALLBACK_SOURCE,
    LOCATION_TYPE_SOURCE,
    FARE_CONSTRUCTION_CRS,
    LONDON_STATION_CRS,
    looks_like_fare_construction,
    SUPPORTED_DESTINATION_FACETS,
    FLOW_F,
    FLOW_T,
    Fare,
    FaresDb,
    Location,
    TicketType,
    is_pseudo_station,
)
from make_synthetic_feed import _line, build_synthetic_feed, write_delete_marker


class PseudoStationTest(unittest.TestCase):
    """Zone boundaries and named coach stops are not places (audit A6).

    The list is reviewed and keyed by CRS, not matched on the name, so these
    tests are about the codes the 24 September 2026 download actually
    carried and the names recorded beside them.
    """

    def test_every_reviewed_code_is_a_fare_construction_point(self) -> None:
        self.assertEqual(len(FARE_CONSTRUCTION_CRS), 12)
        for crs in sorted(FARE_CONSTRUCTION_CRS):
            self.assertTrue(is_pseudo_station(crs), crs)

    def test_the_list_is_the_name_markers_exactly_on_this_feed(self) -> None:
        # The proposer prints what the markers catch; on the stations the 24
        # September 2026 download carried, that is the whole list, which is
        # why splitting the evidence from the judgement has cost nothing yet.
        feed = {
            "QAG": "BOUNDARY ZONE 3", "QAH": "BOUNDARY ZONE 4",
            "QAI": "BOUNDARY ZONE 5", "QAJ": "BOUNDARY ZONE 6",
            "QAK": "BOUNDARY ZONE 2", "QBU": "BRIGHTON UNIZONE",
            "QWU": "WORTHING UNIZONE", "QMZ": "METRO T&W ZONE A",
            "KLB": "KINGS LYNN COACH", "QDM": "DEREHAM (COACH)",
            "SWB": "SWAFFHAM (COACH)", "WIS": "WISBECH (COACH)",
            "GRN": "GRANTHAM", "KGX": "LONDON KINGS X", "ZBF": "BLACKFRIARS UND",
            "WKF": "WAKEFIELD WESTGT", "BCH": "BIRCHINGTON",
        }
        self.assertEqual(
            sorted(crs for crs, name in feed.items() if looks_like_fare_construction(name)),
            sorted(FARE_CONSTRUCTION_CRS),
        )

    def test_a_real_station_is_not_pseudo(self) -> None:
        for crs in ("GRN", "KGX", "ZBF", "NOT", "LCN", "EDE", "ABD", "WKF", "BCH"):
            self.assertFalse(is_pseudo_station(crs), crs)

    def test_the_predicate_ignores_a_station_that_merely_sounds_like_one(self) -> None:
        # The point of a CRS list over a substring test: a future station
        # called Coach House cannot be dropped from the chooser by accident.
        self.assertTrue(looks_like_fare_construction("COACH HOUSE HALT"))
        self.assertFalse(is_pseudo_station("BCH"), "Birchington is a place")

    def test_the_predicate_normalises_what_it_is_given(self) -> None:
        self.assertTrue(is_pseudo_station(" qah "))
        self.assertFalse(is_pseudo_station(""))


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
        self.assertEqual(self.db.destination_type("XFD"), "village")
        self.assertEqual(self.db.destination_types("NOT"), ["city", "university"])
        self.assertEqual(self.db.destination_types("LCN"), ["city", "seaside", "university"])
        self.assertEqual(self.db.destination_types("XFD"), ["village", "island"])
        self.assertEqual(self.db.destination_types("PBO"), ["small_town", "university"])
        self.assertEqual(self.db.destination_types("SLP"), ["other", "heritage"])
        self.assertIn("synthetic", self.db.location_type_source or "")

    def test_heritage_details_come_from_the_curated_station_to_site_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_unserved_station=True)
            )
        self.assertEqual(db.destination_types("SLP"), ["other", "heritage"])
        self.assertEqual(
            db.heritage_sites("SLP"),
            [{
                "id": 488,
                "name": "Tower of London",
                "url": "https://whc.unesco.org/en/list/488/",
            }],
        )
        self.assertEqual(db.heritage_sites("NOT"), [])

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
            "ECR": Location("2000", "ECR", "EAST CROYDON", ""),
            "MAN": Location("3000", "MAN", "MANCHESTER PIC", ""),
            "GLC": Location("4000", "GLC", "GLASGOW CENTRAL", ""),
            "CDD": Location("5000", "CDD", "CARDENDEN", ""),
        }
        db._apply_major_station_fallbacks()
        self.assertEqual(db.destination_type("KGX"), "city")
        self.assertEqual(db.destination_type("ECR"), "city")
        self.assertEqual(db.destination_type("MAN"), "city")
        self.assertEqual(db.destination_type("GLC"), "city")
        # CDD is Cardenden, not Cardiff Central: the feed's own name for the
        # code. The fixture used to invent CARDIFF CENTRAL under CDD, which
        # made the test assert a city for a station that is not one, and hid
        # the same slip in the reviewed list. A fixture that contradicts the
        # feed cannot catch a list entry that does.
        self.assertEqual(db.destination_type("CDD"), "town")
        self.assertIn("London", db.location_type_source or "")

    def test_the_size_bands_name_what_they_are(self) -> None:
        # The ONS bands are population classes, and collapsing the two smallest
        # into one "town" is what left villages filed as "other". The "other"
        # remainder keeps its payload class but is no longer offered as a
        # filter: "No settlement band" read as a gap, not a choice.
        self.assertEqual(LOCATION_BAND_TYPES["major"], "city")
        self.assertEqual(LOCATION_BAND_TYPES["large"], "city")
        self.assertEqual(LOCATION_BAND_TYPES["medium"], "town")
        self.assertEqual(LOCATION_BAND_TYPES["small"], "small_town")
        self.assertEqual(LOCATION_BAND_TYPES["minor"], "village")
        self.assertEqual(
            [key for key, _ in DESTINATION_TYPE_FILTERS[:4]],
            ["city", "town", "small_town", "village"],
        )
        self.assertNotIn("other", [key for key, _ in DESTINATION_TYPE_FILTERS])
        self.assertNotIn("No settlement band", [label for _, label in DESTINATION_TYPE_FILTERS])

    def test_a_major_city_is_not_filed_as_other(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {
            "NCL": Location("1", "NCL", "NEWCASTLE", ""),
            "EDL": Location("2", "EDL", "EDALE", ""),
        }
        db._apply_major_station_fallbacks()
        self.assertEqual(db.destination_type("NCL"), "city")
        self.assertEqual(db.destination_type("EDL"), "village")
        self.assertNotIn("other", db.destination_types("NCL"))
        self.assertNotIn("other", db.destination_types("EDL"))

    def test_attenborough_is_a_village_and_a_nature_site(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {"ATB": Location("1", "ATB", "ATTENBOROUGH", "")}
        db._apply_major_station_fallbacks()
        db._apply_reviewed_facets()
        self.assertEqual(db.destination_type("ATB"), "village")
        self.assertIn("nature", db.destination_types("ATB"))
        self.assertNotIn("other", db.destination_types("ATB"))

    def test_an_airport_station_is_in_the_airport_category(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {"XQB": Location("1", "XQB", "EAST M AIR LGE", "")}
        db._apply_major_station_fallbacks()
        db._apply_reviewed_facets()
        self.assertIn("airport", db.destination_types("XQB"))
        self.assertIn("airport", SUPPORTED_DESTINATION_FACETS)
        self.assertIn(("airport", "Airports"), DESTINATION_TYPE_FILTERS)
        # The airport is its own category, and the settlement it serves is
        # still classified, so the row is not left as the unsourced remainder.
        self.assertEqual(db.destination_type("XQB"), "village")
        self.assertNotIn("other", db.destination_types("XQB"))

    def test_a_station_settlement_band_becomes_a_village_not_other(self) -> None:
        db = FaresDb()
        db._read_ons_built_up_areas = lambda data: {  # type: ignore[method-assign]
            "ANCASTER": {"name": "Ancaster", "type": "village", "band": "minor"},
            "BOTTESFORD": {"name": "Bottesford", "type": "village", "band": "minor"},
            "RETFORD": {"name": "Retford", "type": "town", "band": "medium"},
        }
        db.locations_by_crs = {
            "ANC": Location("1", "ANC", "ANCASTER", ""),
            "BTF": Location("2", "BTF", "BOTTESFORD", ""),
            "RET": Location("3", "RET", "RETFORD", ""),
        }
        with mock.patch.object(atoc_fares.urllib.request, "urlopen", return_value=io.BytesIO(b"xlsx")):
            db._load_ons_location_types()
        self.assertEqual(db.destination_type("ANC"), "village")
        self.assertEqual(db.destination_type("BTF"), "village")
        self.assertEqual(db.destination_type("RET"), "town")

    def test_a_bracketed_county_does_not_hide_a_settlement(self) -> None:
        db = FaresDb()
        self.assertEqual(db._settlement_name_candidates("Ascot (Berks)"), ["ASCOTBERKS", "ASCOT"])
        self.assertEqual(db._settlement_name_candidates("ADLINGTON CHES"), ["ADLINGTONCHES"])
        self.assertEqual(db._settlement_name_candidates("(Berks)"), ["BERKS"])
        areas = {"ASCOT"}
        self.assertTrue(db._settlement_matches("Ascot (Berks)", areas))
        self.assertFalse(db._settlement_matches("Adlington Ches", areas))

    def test_matching_is_never_a_prefix_match(self) -> None:
        # "starts with" would let Bathgate claim Bath and Bradford-on-Avon
        # claim Bradford, so a curated list has to name stations as the feed
        # writes them instead.
        db = FaresDb()
        settled = {"BATH", "BRADFORD", "CHESTER"}
        self.assertFalse(db._settlement_matches("BATHGATE", settled))
        self.assertFalse(db._settlement_matches("BRADFORD ON AVON", settled))
        self.assertFalse(db._settlement_matches("CHESTER ROAD", settled))
        self.assertTrue(db._settlement_matches("BATH", settled))

    def test_an_older_cache_cannot_keep_calling_villages_other(self) -> None:
        db = FaresDb()
        db._load_location_types_json(
            {
                "schema": LOCATION_CACHE_SCHEMA - 1,
                "source": "an older build",
                "records": {"ANC": {"primary": "other", "facets": ["seaside"]}},
            }
        )
        self.assertNotIn("ANC", db.location_types_by_crs)
        # The facets in an older file are still good, and they are additive.
        self.assertEqual(db.location_facets_by_crs["ANC"], {"seaside"})
        self.assertTrue(any("schema" in note for note in db.report.skipped_files))
        # The source label cannot be cleared here: the loader reads it straight
        # back out of the same discarded data. The pass is what has to notice,
        # and the next test drives the pass.

    def test_a_cache_this_build_writes_is_a_cache_the_next_build_keeps(self) -> None:
        # The round trip, because the writer once named its own schema as a
        # literal while the reader moved on: every build then wrote a cache
        # whose classes the next build was required to throw away and re-derive
        # from the workbook, so the cache never once saved the work it exists
        # to save. Writing and re-reading is the only thing that catches it.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "location-types.json"
            db = FaresDb()
            db.locations_by_crs = {"ANC": Location("1", "ANC", "ANCASTER", "")}
            db.location_types_by_crs = {"ANC": "village"}
            db.location_facets_by_crs = {"ANC": {"seaside"}}
            db._write_location_cache(path)

            reloaded = FaresDb()
            reloaded.locations_by_crs = dict(db.locations_by_crs)
            reloaded._load_location_types_json(json.loads(path.read_text(encoding="utf-8")))

        self.assertEqual(reloaded.destination_type("ANC"), "village")
        self.assertEqual(reloaded.location_facets_by_crs["ANC"], {"seaside"})
        self.assertEqual(
            [note for note in reloaded.report.skipped_files if "schema" in note],
            [],
            "a cache this build wrote must survive its own next load",
        )

    def test_a_discard_does_not_cost_a_later_source_its_label(self) -> None:
        # The flag that records a discard is sticky, and it must not be
        # consulted for every candidate after the one that discarded: a file
        # that classifies the feed properly is loaded after a stale cache in
        # every real layout, and clearing its label left the build claiming no
        # source at all for classes a source had just supplied. ANC and RET are
        # in no reviewed list, so nothing else can label this build.
        with tempfile.TemporaryDirectory() as tmp:
            feed = Path(tmp) / "fares"
            feed.mkdir()
            (feed / "stale.location-types.json").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA - 1,
                        "source": "an older build",
                        "records": {"ANC": {"primary": "other"}, "RET": {"primary": "other"}},
                    }
                ),
                encoding="utf-8",
            )
            (Path(tmp) / "cachedestination-facets.json").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA,
                        "source": "a sourced workbook",
                        "records": {
                            "ANC": {"primary": "village"},
                            "RET": {"primary": "town"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            db = FaresDb()
            db.locations_by_crs = {
                "ANC": Location("1", "ANC", "ANCASTER", ""),
                "RET": Location("2", "RET", "RETFORD", ""),
            }
            db._load_location_lookup(feed)
        self.assertEqual(db.destination_type("ANC"), "village")
        self.assertEqual(db.destination_type("RET"), "town")
        # A source label, and specifically not the two wrong answers: empty,
        # which claims nothing classified the feed, and the fallback label,
        # which claims the reviewed lists did it. Which source label wins when
        # several files are loaded is a pre-existing question this test does
        # not settle; what it settles is that a discard does not erase one.
        self.assertNotEqual(db.location_type_source, "")
        self.assertNotEqual(db.location_type_source, LOCATION_FALLBACK_SOURCE)

    def test_a_discarded_cache_does_not_stop_the_workbook_being_read(self) -> None:
        # The whole classification pass, because the label above is read back
        # out of the same data: it is the pass that has to notice. When it did
        # not, the pass believed the workbook had already been applied, returned
        # early, and every station the cache had classified fell through to the
        # reviewed fallbacks -- 3,119 of 3,436 on the 24 September 2026
        # download. ANC is in no reviewed list, so "village" below can only have
        # come from the workbook.
        with tempfile.TemporaryDirectory() as tmp:
            feeds = Path(tmp) / "feeds"
            (feeds / "fares").mkdir(parents=True)
            (feeds / "download-manifest.json").write_text("{}", encoding="utf-8")
            (feeds / "location-types.json").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA - 1,
                        "source": "reviewed synthetic station types",
                        "records": {"ANC": {"primary": "other", "facets": ["seaside"]}},
                    }
                ),
                encoding="utf-8",
            )
            db = FaresDb()
            db._read_ons_built_up_areas = lambda data: {  # type: ignore[method-assign]
                "ANCASTER": {"name": "Ancaster", "type": "village", "band": "minor"},
            }
            db.locations_by_crs = {"ANC": Location("1", "ANC", "ANCASTER", "")}
            with mock.patch.object(
                atoc_fares.urllib.request, "urlopen", return_value=io.BytesIO(b"xlsx")
            ):
                db._load_location_lookup(feeds / "fares")
        self.assertEqual(db.destination_type("ANC"), "village")
        self.assertEqual(db.location_facets_by_crs["ANC"], {"seaside"})
        # The build names the workbook, not the cache whose classes it threw
        # away: that label is what the page's provenance line claims.
        self.assertEqual(db.location_type_source, LOCATION_TYPE_SOURCE)

    def test_a_reviewed_fallback_the_workbook_already_names_is_reported(self) -> None:
        # A reviewed entry for a station the workbook names is not an error
        # today: the class is never applied, so nothing looks wrong. It becomes
        # one the day a name match misses, and the reviewed class then lands on
        # a station the workbook had classified correctly -- York was filed as a
        # town beside a workbook that says city. Both halves matter: the code is
        # named, and the workbook still wins while it is there.
        def workbook() -> dict:
            return {"YORK": {"name": "York", "type": "city", "band": "large"}}

        db = FaresDb()
        db._read_ons_built_up_areas = lambda data: workbook()  # type: ignore[method-assign]
        db.locations_by_crs = {"YRK": Location("1", "YRK", "YORK", "")}
        with mock.patch.object(atoc_fares.urllib.request, "urlopen", return_value=io.BytesIO(b"xlsx")):
            db._load_ons_location_types()
        db._apply_major_station_fallbacks()
        self.assertIn("YRK", db.ons_classified_crs)
        self.assertNotIn("YRK", db.report.reviewed_codes_redundant, "the list no longer names York")
        self.assertEqual(db.destination_type("YRK"), "city")
        # Put the entry back and it is named as redundant on the next pass.
        with mock.patch.dict(atoc_fares.MAJOR_UK_STATION_FALLBACKS, {"YRK": "town"}):
            db._apply_major_station_fallbacks()
            self.assertIn("YRK", db.report.reviewed_codes_redundant)
            self.assertEqual(db.destination_type("YRK"), "city", "the workbook's class still wins")
            # Named once, because the pass runs again as each source lands and
            # a note per pass would say the same thing three times.
            recorded = list(db.report.reviewed_codes_redundant)
            db._apply_major_station_fallbacks()
            self.assertEqual(db.report.reviewed_codes_redundant, recorded)

    def test_a_reviewed_code_the_feed_does_not_carry_is_named(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {
            "GRN": Location("1", "GRN", "GRINDELFORD", ""),
            "GRA": Location("2", "GRA", "GRANTHAM", ""),
            "BHC": Location("3", "BHC", "BALLOCH CENTRAL", ""),
        }
        db._apply_major_station_fallbacks()
        absent = db.report.reviewed_codes_absent
        self.assertTrue(absent, "the dead codes are named")
        # The lists are still intersected before they are applied, so the
        # record is the only effect a dead code has. It is not a skipped file:
        # nothing went unread, a reviewed list is naming a station the feed
        # does not carry.
        self.assertNotIn("ABD", db.location_types_by_crs)
        self.assertEqual(db.report.skipped_files, [])
        # A reviewed code the feed does carry is applied, and is not named as
        # absent: the record is about the feed, not about the list.
        self.assertEqual(db.destination_type("BHC"), "village")
        self.assertNotIn("BHC", absent)
        self.assertIn("ABD", absent)
        # Re-running the pass must not restate it: the classification pass runs
        # again as each source lands.
        db._apply_major_station_fallbacks()
        self.assertEqual(db.report.reviewed_codes_absent, absent)

    def test_every_london_code_is_one_the_feed_carries(self) -> None:
        # The seven Underground codes that had lost their leading Z, which made
        # them name no station at all. A reviewed list is only as good as this.
        for crs in ("ZBF", "ZCD", "ZGR", "ZLP", "ZPD", "ZPI", "ZRY"):
            self.assertIn(crs, LONDON_STATION_CRS)
        for dropped in ("BKF", "CDL", "DLP", "GLR", "IPD", "PIM", "RGY"):
            self.assertNotIn(dropped, LONDON_STATION_CRS)

    def test_the_heritage_reader_only_uses_current_uk_properties(self) -> None:
        body = (
            '<?xml version="1.0"?><query>'
            "<row><id_number>428</id_number><states>United Kingdom of Great Britain "
            "and Northern Ireland</states><category>Cultural</category></row>"
            "<row><id_number>371</id_number><states>United Kingdom of Great Britain "
            "and Northern Ireland</states><category>Cultural</category></row>"
            "<row><id_number>1613</id_number><states>Germany,United Kingdom</states>"
            "</row>"
            "<row><id_number>1133</id_number><states>Austria</states></row>"
            "</query>"
        )
        db = FaresDb()
        db.locations_by_crs = {
            "BTH": Location("1", "BTH", "BATH SPA", ""),
            "BGX": Location("2", "BGX", "BATHGATE", ""),
        }
        with mock.patch.object(
            atoc_fares.urllib.request, "urlopen", return_value=io.BytesIO(body.encode())
        ):
            db._apply_destination_facet(DESTINATION_FACETS_BY_KEY["heritage"])
        self.assertEqual(db.location_facets_by_crs["BTH"], {"heritage"})
        # Bathgate is a different place that merely starts with the same word.
        self.assertNotIn("BGX", db.location_facets_by_crs)
        # The rest of the curated list names stations this feed does not carry,
        # and that is reported rather than left looking current.
        self.assertTrue(
            any("curated station names match no station" in note for note in db.report.skipped_files)
        )

    def test_a_delisted_heritage_site_stops_tagging_destinations(self) -> None:
        body = (
            '<?xml version="1.0"?><query><row><id_number>9999</id_number>'
            "<states>United Kingdom</states></row></query>"
        )
        db = FaresDb()
        db.locations_by_crs = {"BTH": Location("1", "BTH", "BATH SPA", "")}
        with mock.patch.object(
            atoc_fares.urllib.request, "urlopen", return_value=io.BytesIO(body.encode())
        ):
            with self.assertRaises(ValueError):
                db._read_unesco_heritage_facet()
        self.assertTrue(any("not a current UK World Heritage" in note for note in db.report.skipped_files))

    def test_a_coach_or_parkway_station_is_a_transport_interchange(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {
            "XDO": Location("1", "XDO", "BATH BUS STATION", ""),
            "TIN": Location("2", "TIN", "MAGNA TRAM STOP", ""),
            "TPC": Location("3", "TPC", "THORPE CULVERT", ""),
            "BUS": Location("4", "BUS", "BUSBY", ""),
            "ATB": Location("5", "ATB", "ATTENBOROUGH", ""),
        }
        db._apply_reviewed_facets()
        self.assertIn("transport", db.destination_types("XDO"))
        self.assertIn("transport", db.destination_types("TIN"))
        # A park and ride named after the village it serves carries no marker,
        # so the code list has to reach it.
        self.assertIn("transport", db.destination_types("TPC"))
        # BUSBY is a village whose name merely contains the marker.
        self.assertNotIn("transport", db.destination_types("BUS"))
        self.assertNotIn("transport", db.destination_types("ATB"))
        self.assertIn(("transport", "Transport interchanges"), DESTINATION_TYPE_FILTERS)

    def test_every_reviewed_facet_code_is_a_station_code(self) -> None:
        # The codes are intersected with the feed's own stations, so a typo is
        # silently dropped rather than failing a build. Checking the shape here
        # is what catches one; the names are checked against a real download.
        for facet in DESTINATION_FACET_SOURCES:
            if not facet.is_reviewed:
                continue
            self.assertTrue(facet.reviewed_station_codes or facet.reviewed_name_markers, facet.key)
            for crs in facet.reviewed_station_codes:
                self.assertRegex(crs, r"^[A-Z]{3}$", facet.key)
            for marker in facet.reviewed_name_markers:
                self.assertEqual(marker, marker.upper(), facet.key)

    def test_every_facet_declares_a_readable_source_and_reaches_the_filter(self) -> None:
        for facet in DESTINATION_FACET_SOURCES:
            self.assertIn(facet.key, SUPPORTED_DESTINATION_FACETS)
            self.assertIn((facet.key, facet.label), DESTINATION_TYPE_FILTERS)
            self.assertTrue(facet.source.strip(), facet.key)
            self.assertTrue(facet.coverage.strip(), facet.key)
            if facet.is_reviewed:
                # A reviewed facet has to say so, or the page reads as if an
                # official list produced it.
                self.assertIn("reviewed", facet.source.lower())
            else:
                self.assertTrue(facet.url.startswith("http"), facet.key)
                self.assertIn(facet.reader, DESTINATION_FACET_READERS)
            for crs in facet.excluded_station_codes:
                self.assertNotIn(crs, facet.reviewed_station_codes, facet.key)
        # The primary classes come first, and the facets follow in registry
        # order, so the filter reads settlements first and character last.
        self.assertEqual(
            [key for key, _ in DESTINATION_TYPE_FILTERS],
            ["city", "town", "small_town", "village"]
            + [facet.key for facet in DESTINATION_FACET_SOURCES],
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
            self.assertEqual(
                grantham.stats(),
                self.db.stats(),
                "a restored index reports the whole feed's stats, not its slice",
            )

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
        rows = {
            row.crs: row
            for row in self.db.page_single_destinations_within("GRN", 1_000_000)
        }
        self.assertTrue(rows)
        self.assertTrue(all(row.ticket_code in {"SDS", "2AS"} for row in rows.values()))
        # Advance is a valid fare. The page keeps the cheaper one and labels it
        # train-specific rather than silently replacing it with a walk-up fare.
        self.assertEqual(rows["NOT"].standard_pence, 100)
        self.assertEqual(rows["NOT"].ticket_code, "2AS")
        self.assertEqual(rows["NOT"].ticket_name, "ADVANCE")

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
        self.assertEqual(forward["NOT"].standard_pence, 100)
        self.assertEqual(forward["NOT"].ticket_code, "2AS")
        self.assertEqual(reverse["GRN"].standard_pence, 500)
        self.assertEqual(reverse["GRN"].ticket_code, "SDS")

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


class AdvanceFareTest(unittest.TestCase):
    """One definition of "advance", asked two ways.

    The page labels an Advance single differently from a walk-up fare, so the
    test that decides it has to agree with the ticket catalogue. A fare the DTD
    marks with restriction code AS is train-specific whatever the ticket is
    called, and a ticket called ADVANCE is train-specific whatever code it
    carries.
    """

    def test_a_restriction_code_alone_marks_the_fare_advance(self) -> None:
        self.assertTrue(atoc_fares.is_advance_fare("SUPER OFFPEAK DAY R", " as "))
        self.assertFalse(atoc_fares.is_advance_fare("SUPER OFFPEAK DAY R", "RH"))
        self.assertFalse(atoc_fares.is_advance_fare("SUPER OFFPEAK DAY R", ""))

    def test_a_ticket_name_alone_marks_the_fare_advance(self) -> None:
        self.assertTrue(atoc_fares.is_advance_fare("ANYTIME ADVANCE DAY S", ""))
        self.assertTrue(
            atoc_fares.TicketType("2AS", "ADVANCE", "2", "S", True).is_advance
        )
        self.assertFalse(
            atoc_fares.TicketType("CDR", "OFF-PEAK DAY R", "2", "R", False).is_advance
        )

    def test_a_nameless_fare_is_not_advance(self) -> None:
        # An empty ticket name must not be read as containing the word: this is
        # the shape the feed gives an unnamed catalogue record.
        self.assertFalse(atoc_fares.is_advance_ticket(None))
        self.assertFalse(atoc_fares.is_advance_ticket(""))
        self.assertFalse(atoc_fares.is_advance_fare(None, None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
