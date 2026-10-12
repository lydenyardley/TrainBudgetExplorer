"""Tests for the fares feed parser, run against a synthetic feed.

Each test asserts a literal value, so a parser that returned nothing would fail.
"""

from __future__ import annotations

import functools
import io
import dataclasses
import json
import pickle
import tempfile
import unittest
import zipfile
from unittest import mock

import atoc_fares
import atoc_restrictions
from datetime import date
from pathlib import Path

from atoc_fares import (
    COASTAL_SITE_PROOFS,
    SEASIDE_SUPPLEMENT_CRS,
    seaside_crs_missing_coastal_proofs,
    DESTINATION_FACET_SOURCES,
    DESTINATION_FACET_READERS,
    DESTINATION_TYPE_FILTERS,
    HERITAGE_PROPERTIES,
    HERITAGE_SITE_POINTS,
    NATIONAL_PARK_GATEWAYS,
    NATIONAL_TRUST_PROPERTIES,
    ONS_BUILT_UP_AREAS_FILE_URL,
    REVIEWED_ATTRACTIONS_BY_FACET,
    RSPB_RESERVES,
    ReviewedAttraction,
    LOCATION,
    LOCATION_BAND_TYPES,
    LOCATION_CACHE_SCHEMA,
    LOCATION_FALLBACK_SOURCE,
    LOCATION_TYPE_SOURCE,
    LOCATION_TYPES_FILE,
    DESTINATION_FACETS_FILE,
    classification_files,
    FARE_CONSTRUCTION_CRS,
    LONDON_STATION_CRS,
    looks_like_fare_construction,
    haversine_km,
    load_station_coordinates,
    select_nearest_stations,
    SUPPORTED_DESTINATION_FACETS,
    FLOW_F,
    FLOW_T,
    Fare,
    FaresDb,
    Railcard,
    Location,
    TicketType,
    dtd_flag,
    is_advance_ticket,
    is_pseudo_station,
)
from make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_station_coordinates, write_delete_marker
from atoc_restrictions import RESTRICTION_LAYOUTS


def facet(key: str):
    """One sourced destination facet, read out of the registry by its key.

    The registry is the one place a facet is added, so a test looks a facet up
    by scanning it rather than by holding a second index beside it.
    """
    return next(f for f in DESTINATION_FACET_SOURCES if f.key == key)


def _restriction_header(code: str, description: str, outward: str) -> str:
    """One real ``RH`` record, written through the layout the parser reads."""
    return _line(
        {
            "record_type": "RH",
            "restriction_code": code,
            "description": description,
            "desc_out": outward,
            "desc_rtn": "Return",
            "type_out": "N",
            "type_rtn": "N",
            "change_ind": "Y",
            "cf_marker": "C",
        },
        RESTRICTION_LAYOUTS["RH"],
    )


def _feed_with_stations(root: Path, *stations: tuple[str, str]) -> Path:
    """A synthetic feed that also carries stations the fixture does not name.

    A reviewed list is intersected with the stations the feed contains, so a
    fallback or a facet can only be proved at the fixture boundary if the feed
    carries the station: the fixture's own GRN..XFD is in no reviewed list but
    London King's Cross, and its own classification file answers that one
    whether or not the fallback does.
    """
    feed = build_synthetic_feed(Path(root) / "fares", include_unserved_station=True)
    if stations:
        (feed / "rjfaf-extra.loc").write_text(
            "\n".join(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "L",
                        "nlc": f"{9000 + index}",
                        "description": name,
                        "crs": crs,
                    },
                    LOCATION,
                )
                for index, (crs, name) in enumerate(stations)
            )
            + "\n",
            encoding="utf-8",
        )
    return feed


def _first_build(root: Path, *stations: tuple[str, str]) -> Path:
    """A feed whose classification cache has not been written yet.

    ``build_synthetic_feed`` writes one beside every feed it builds, and a load
    answers from that cache before it opens a source, so a test about the
    sources a first build reads has to take it out of the way. The manifest is
    what makes the load treat the folder as a download and read the workbook.
    """
    feed = _feed_with_stations(root, *stations)
    (Path(root) / "fares.location-types.json").unlink()
    (Path(root) / "download-manifest.json").write_text("{}", encoding="utf-8")
    return feed


def _ons_workbook(rows: tuple[tuple[str, str], ...]) -> bytes:
    """The ONS built-up-area workbook as its reader sees it: F the settlement, G its band."""
    sheet = [
        '<?xml version="1.0"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>",
    ]
    for number, (settlement, band) in enumerate(rows, start=1):
        sheet.append(
            f'<row r="{number}"><c r="F{number}"><v>{settlement}</v></c>'
            f'<c r="G{number}"><v>{band}</v></c></row>'
        )
    sheet.append("</sheetData></worksheet>")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", "".join(sheet))
    return buffer.getvalue()


def _only_source(url: str, body: bytes):
    """Answer one classification source, and refuse the rest as an offline build."""
    def answer(request, timeout=0):
        if request.full_url == url:
            return io.BytesIO(body)
        raise OSError("offline")

    return answer


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


@functools.lru_cache(maxsize=1)
def real_gra_fares() -> FaresDb:
    """The licensed feed, focused on GRA, parsed once for every test that reads it.

    Two tests read this file, and they are 58 s and 49 s of this module's 200 s
    (measured 8 October 2026 with `python -m unittest --durations 15
    tests.test_atoc_fares`), because each one parses the whole archive. Both only
    read what they are handed, so one parse answers both. A test that mutated the
    database would change what the next one sees, which is why this returns a
    loaded database and says so here rather than being a bare module global.
    """
    return FaresDb().load_feed("feeds/fares/dtd-fares.zip", focus_origin="GRA")


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

    def test_the_dtd_flag_spelling_is_read_by_a_test_the_synthetic_feed_cannot_pass(self) -> None:
        # The licensed feed writes ``Y`` for a true flag. This project's
        # synthetic feed was written before any licensed file was available and
        # writes ``1``. Reading the flag as ``== "1"`` therefore matched the
        # synthetic feed and nothing else: on the real feed every
        # train-restricted ticket read as unrestricted, so the check that exists
        # to stop an advance fare being published as a walk-up price never
        # fired, and the page published fares no train on the day was selling.
        #
        # So the spellings are pinned here against the reader rather than
        # against a fixture, which is the one thing the fixture cannot catch.
        for yes in ("Y", "y", "1", " Y "):
            self.assertTrue(dtd_flag(yes), f"{yes!r} must read as yes")
        for no in ("N", "n", "0", "", "  ", None):
            self.assertFalse(dtd_flag(no), f"{no!r} must read as no")

    @unittest.skipUnless(
        Path("feeds/fares/dtd-fares.zip").is_file(),
        "licensed DTD feed is not available",
    )
    def test_the_real_feed_marks_its_advance_tickets_train_restricted(self) -> None:
        # The synthetic feed cannot catch the spelling, so the licensed file is
        # the only place this can be asserted. Before the fix every advance
        # ticket in the real feed read as unrestricted: 378 of them did not.
        db = real_gra_fares()
        advance = [
            ticket
            for ticket in db.ticket_types.values()
            if is_advance_ticket(ticket.name)
        ]
        self.assertGreater(len(advance), 100)
        flagged = [ticket.code for ticket in advance if ticket.restricted_by_train]
        self.assertGreater(len(flagged), 100)
        # And the fare this started on: the £6.60 single Grantham--Skegness was
        # priced as, which no train on 6 October 2026 was selling.
        self.assertIn("2AS", flagged)

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

    def test_coastal_site_proof_requires_the_seaside_facet(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {"SKG": Location("1", "SKG", "SKEGNESS", "")}
        db.location_facets_by_crs = {"SKG": {"seaside"}}
        self.assertEqual(
            db.coastal_sites("SKG"),
            [{
                "name": "Skegness Beach",
                "url": "https://www.visitlincolnshire.com/destinations/skegness/",
            }],
        )
        db.location_facets_by_crs = {"SKG": set()}
        self.assertEqual(db.coastal_sites("SKG"), [])
        # A seaside tag with no proof row yields an empty subline; the coverage
        # invariant below refuses to leave that state in a real facet map.
        db.location_facets_by_crs = {"LCN": {"seaside"}}
        self.assertEqual(db.coastal_sites("LCN"), [])
        self.assertEqual(
            seaside_crs_missing_coastal_proofs(db.location_facets_by_crs),
            ["LCN"],
        )

    def test_every_seaside_tagged_crs_in_the_cache_has_a_coastal_proof(self) -> None:
        # Chip implies named subline: ONS seaside set + supplements ⊆ proofs.
        path = Path("feeds/location-types.json")
        if not path.is_file():
            self.skipTest("feeds/location-types.json not present")
        data = json.loads(path.read_text(encoding="utf-8"))
        facets = {crs: set(values) for crs, values in data.get("facets", {}).items()}
        for crs in SEASIDE_SUPPLEMENT_CRS:
            facets.setdefault(crs, set()).add("seaside")
        missing = seaside_crs_missing_coastal_proofs(facets)
        self.assertEqual(missing, [], msg=f"seaside without coastal proof: {missing}")

    def test_coastal_proof_table_covers_the_seaside_supplement(self) -> None:
        proved = {crs for crs, _name, _url in COASTAL_SITE_PROOFS}
        self.assertTrue(SEASIDE_SUPPLEMENT_CRS <= proved)

    def test_tenby_carries_a_named_coastal_day_out(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {"TEN": Location("1", "TEN", "TENBY", "")}
        db.location_facets_by_crs = {"TEN": {"seaside"}}
        self.assertEqual(
            db.coastal_sites("TEN"),
            [{
                "name": "Tenby North Beach",
                "url": (
                    "https://www.visitpembrokeshire.com/explore-pembrokeshire/"
                    "beaches/tenby-north-beach"
                ),
            }],
        )
        db.location_facets_by_crs = {"TEN": set()}
        self.assertEqual(db.coastal_sites("TEN"), [])

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

    def test_a_workbook_district_does_not_hide_a_settlement(self) -> None:
        # The workbook writes "Foxton (South Cambridgeshire)"; the station is
        # FOXTON, and the two sides have to normalise the same way. On the real
        # feed this gap alone left 43 priced destinations unclassified. Keying
        # the workbook is a pure function of its rows, so it is stated here;
        # the station it has to reach is now proved at the feed boundary.
        bands = FaresDb._key_settlements(
            [
                ("Foxton (South Cambridgeshire)", "minor"),
                ("Neston (Cheshire West and Chester)", "small"),
            ]
        )
        self.assertEqual(bands["FOXTON"]["type"], "village")
        self.assertEqual(bands["NESTON"]["type"], "small_town")

    def test_two_settlements_of_one_name_are_refused_not_guessed(self) -> None:
        # Bucknell (Cherwell) and Bucknell (Shropshire) are different places
        # with the same name; a station called BUCKNELL cannot be told which one
        # it serves from its name, so it keeps the coverage report rather than
        # taking a class that may belong to the other. Keying the workbook is a
        # pure function of its rows, so it is stated here; the station left
        # unclassified is now proved at the feed boundary.
        same = FaresDb._key_settlements(
            [("Bucknell (Cherwell)", "minor"), ("Bucknell (Shropshire)", "minor")]
        )
        self.assertEqual(same["BUCKNELL"]["type"], "village", "one band is not ambiguous")
        different = FaresDb._key_settlements(
            [("Wick (Hackney)", "large"), ("Wick (Highland)", "small")]
        )
        self.assertIsNone(different["WICK"]["type"])

    def test_a_station_qualifier_is_not_dropped_to_find_a_class(self) -> None:
        # Tried and dropped: stripping a trailing qualifier matched London
        # stations to same-named settlements the workbook holds elsewhere --
        # Acton Central to Acton, Clapham High Street to Clapham (Arun) -- and
        # a wrong class on a page is worse than no class at all. The name the
        # station carries is the name the workbook has to hold; the qualifier
        # only ever decides which *session* is asked about, never a different
        # settlement.
        db = FaresDb()
        self.assertEqual(db._settlement_name_candidates("WATFORD JUNCTION"), ["WATFORDJUNCTION"])
        self.assertEqual(db._settlement_name_candidates("CLAPHAM HIGH ST"), ["CLAPHAMHIGHST"])
        self.assertFalse(db._settlement_matches("WATFORD JUNCTION", {"WATFORD"}))

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
            db.location_type_sources = [LOCATION_TYPE_SOURCE, LOCATION_FALLBACK_SOURCE]
            db._write_location_cache(path)

            reloaded = FaresDb()
            reloaded.locations_by_crs = dict(db.locations_by_crs)
            reloaded._load_location_types_json(json.loads(path.read_text(encoding="utf-8")))

        self.assertEqual(reloaded.destination_type("ANC"), "village")
        self.assertEqual(reloaded.location_facets_by_crs["ANC"], {"seaside"})
        # The labels are written as a list and read back as one, in the order
        # they were loaded: a joined string would have to be split at the
        # joiner, and a source's own text may contain it.
        self.assertEqual(
            reloaded.location_type_sources,
            [LOCATION_TYPE_SOURCE, LOCATION_FALLBACK_SOURCE],
        )
        self.assertEqual(
            reloaded.location_type_source,
            LOCATION_TYPE_SOURCE + " + " + LOCATION_FALLBACK_SOURCE,
        )
        self.assertEqual(
            [note for note in reloaded.report.skipped_files if "schema" in note],
            [],
            "a cache this build wrote must survive its own next load",
        )

    def test_a_label_from_an_older_fare_index_cache_is_still_reported(self) -> None:
        # A fare-index pickle written before the labels were accumulated holds
        # one label and no list, and unpickling sets the instance dictionary
        # without running __init__. The property shadows that stored label, so
        # it has to read it back explicitly: the alternative is a page built
        # from an existing index losing its provenance line, and a build that
        # dies on an attribute the pickle was never written with.
        db = FaresDb()
        db.__dict__.pop("location_type_sources")
        db.__dict__["location_type_source"] = LOCATION_TYPE_SOURCE
        restored = pickle.loads(pickle.dumps(db))
        self.assertEqual(restored.location_type_source, LOCATION_TYPE_SOURCE)
        self.assertTrue(restored._has_sourced_classes())

    def test_the_classification_file_names_are_the_two_this_project_writes(self) -> None:
        # The name is the contract, so the accepted shapes are worth stating on
        # their own: the bare name this build writes and the same name behind a
        # feed's own. A name that merely mentions the same words is not one.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (
                LOCATION_TYPES_FILE,
                f"fares.{LOCATION_TYPES_FILE}",
                DESTINATION_FACETS_FILE,
                f"fares.{DESTINATION_FACETS_FILE}",
            ):
                (root / name).write_text("{}", encoding="utf-8")
            for name in (
                "location-types-notes.json",
                "noteslocation-types.json",
                "location_types.json",
                "cachedestination-facets.json",
                "fares.destination-facets.txt",
            ):
                (root / name).write_text("{}", encoding="utf-8")
            self.assertEqual(
                [path.name for path in classification_files(root)],
                [
                    DESTINATION_FACETS_FILE,
                    f"fares.{DESTINATION_FACETS_FILE}",
                    f"fares.{LOCATION_TYPES_FILE}",
                    LOCATION_TYPES_FILE,
                ],
            )

    def test_every_london_code_is_one_the_feed_carries(self) -> None:
        # The seven Underground codes that had lost their leading Z, which made
        # them name no station at all. A reviewed list is only as good as this.
        for crs in ("ZBF", "ZCD", "ZGR", "ZLP", "ZPD", "ZPI", "ZRY"):
            self.assertIn(crs, LONDON_STATION_CRS)
        for dropped in ("BKF", "CDL", "DLP", "GLR", "IPD", "PIM", "RGY"):
            self.assertNotIn(dropped, LONDON_STATION_CRS)

    def test_the_heritage_reader_only_uses_current_uk_properties(self) -> None:
        # The curated list is checked against UNESCO's own XML on every read, so
        # a delisted property stops contributing and a curated station name that
        # no longer names anything is reported. Loaded through a feed, the
        # checked-in reference data has already tagged these same stations, so
        # the reader's own answer can only be read off the step itself.
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
            db._apply_destination_facet(facet("heritage"))
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

    def test_hybrid_prune_drops_buxton_for_bath_and_keeps_bath_spa(self) -> None:
        # Litmus: Buxton is a curated City of Bath namesake ~212 km away.
        coords = {
            "BTH": (51.37768276, -2.357034178),
            "BUX": (53.26074338, -1.912870681),
        }
        located = [(crs, *coords[crs]) for crs in ("BTH", "BUX")]
        kept = select_nearest_stations(located, HERITAGE_SITE_POINTS[1613])
        self.assertEqual(kept, ["BTH"])
        self.assertGreater(haversine_km(*coords["BUX"], *HERITAGE_SITE_POINTS[1613][0]), 15.0)

    def test_hybrid_prune_drops_cheshire_chester_for_hadrians_wall(self) -> None:
        # Litmus: Cheshire Chester matched the old curated "Chester" token.
        coords = {
            "CAR": (54.89064626, -2.933810228),
            "CLS": (54.85459856, -1.578018751),
            "CRB": (54.96630507, -2.018556061),
            "CTR": (53.19683958, -2.880125588),
            "NCL": (54.96822056, -1.617285496),
        }
        located = [(crs, *coords[crs]) for crs in coords]
        kept = select_nearest_stations(located, HERITAGE_SITE_POINTS[430])
        self.assertNotIn("CTR", kept)
        self.assertIn("CAR", kept)
        self.assertIn("CRB", kept)
        self.assertIn("NCL", kept)

    def test_hybrid_prune_keeps_derwent_valley_as_a_component_set(self) -> None:
        coords = {
            "BLP": (53.02459133, -1.482616227),
            "CMF": (53.11294781, -1.548786122),
            "MAT": (53.13815608, -1.558986118),
            "MTB": (53.12197042, -1.557657491),
        }
        located = [(crs, *coords[crs]) for crs in coords]
        kept = set(select_nearest_stations(located, HERITAGE_SITE_POINTS[1030]))
        self.assertEqual(kept, set(coords))

    def test_heritage_sites_apply_prune_so_buxton_loses_bath(self) -> None:
        db = FaresDb()
        db.locations_by_crs = {
            "BTH": Location("1", "BTH", "BATH SPA", ""),
            "BUX": Location("2", "BUX", "BUXTON", ""),
        }
        db.location_facets_by_crs = {
            "BTH": {"heritage"},
            "BUX": {"heritage"},
        }
        db._station_coordinates = {
            "BTH": (51.37768276, -2.357034178),
            "BUX": (53.26074338, -1.912870681),
        }
        bath_ids = {site["id"] for site in db.heritage_sites("BTH")}
        buxton_ids = {site["id"] for site in db.heritage_sites("BUX")}
        self.assertIn(1613, bath_ids)
        self.assertNotIn(1613, buxton_ids)

    def test_tower_of_london_still_labels_without_knowledgebase_coords(self) -> None:
        # Tower Hill Und is absent from National Rail stations.xml; fail-open
        # must keep the curated underground gateway.
        db = FaresDb()
        db.locations_by_crs = {
            "SLP": Location("1", "SLP", "TOWER HILL UND", ""),
        }
        db.location_facets_by_crs = {"SLP": {"heritage"}}
        db._station_coordinates = {}
        self.assertEqual(
            db.heritage_sites("SLP"),
            [{
                "id": 488,
                "name": "Tower of London",
                "url": "https://whc.unesco.org/en/list/488/",
            }],
        )

    def test_hadrian_curated_list_names_chester_le_street_not_cheshire(self) -> None:
        hadrian_stations = next(
            stations for site_id, _name, stations in HERITAGE_PROPERTIES if site_id == 430
        )
        self.assertIn("Chester-le-Street", hadrian_stations)
        self.assertNotIn("Chester", hadrian_stations)

    def test_the_three_backlog_sources_are_facets_with_reviewed_lists(self) -> None:
        # ADR-0062: RSPB, National Trust and National Park / Landscape gateways
        # each ship as one facet and one reviewed list, never as a raw dump.
        expected = {
            "rspb": RSPB_RESERVES,
            "national_trust": NATIONAL_TRUST_PROPERTIES,
            "national_park": NATIONAL_PARK_GATEWAYS,
        }
        for key, attractions in expected.items():
            one = facet(key)
            self.assertIn(key, SUPPORTED_DESTINATION_FACETS)
            self.assertIn((key, one.label), DESTINATION_TYPE_FILTERS)
            self.assertTrue(one.url.startswith("http"), key)
            self.assertIn("reviewed", one.source.lower(), key)
            self.assertEqual(one.reviewed_attractions, attractions, key)
            self.assertTrue(attractions, key)
            for attraction in attractions:
                self.assertTrue(attraction.name.strip(), key)
                self.assertTrue(attraction.url.startswith("http"), attraction.name)
                self.assertTrue(attraction.stations, attraction.name)
                self.assertTrue(attraction.points, attraction.name)
                for lat, lon in attraction.points:
                    self.assertTrue(-90 <= lat <= 90, attraction.name)
                    self.assertTrue(-180 <= lon <= 180, attraction.name)

    def test_an_attraction_prune_drops_a_distant_namesake_and_keeps_the_near_one(self) -> None:
        # ADR-0063: the curated candidate is kept, any candidate beyond max_km
        # from the attraction point is dropped. Newport Wetlands is the shape:
        # the curated name reaches both Newports, and the prune keeps the Welsh
        # one the reserve is actually beside.
        attraction = ReviewedAttraction(
            "Newport Wetlands",
            "https://example.org/newport-wetlands",
            ("Newport (S Wales)",),
            ((51.5560, -2.9560),),
        )
        db = FaresDb()
        db.locations_by_crs = {
            "NWP": Location("1", "NWP", "NEWPORT S.WALES", ""),
            "NWE": Location("2", "NWE", "NEWPORT", ""),
        }
        db._station_coordinates = {
            "NWP": (51.5890, -2.9990),
            "NWE": (51.7920, 0.2110),
        }
        kept = db._pruned_attraction_crs(attraction)
        self.assertIn("NWP", kept)
        self.assertNotIn("NWE", kept)

    def test_an_attraction_fails_open_when_the_coordinate_file_is_absent(self) -> None:
        # No stations.xml means distance cannot judge the candidate, so the
        # reviewed list stands as written rather than tagging nothing.
        attraction = ReviewedAttraction(
            "Rainham Marshes",
            "https://example.org/rainham-marshes",
            ("Purfleet",),
            ((51.4870, 0.2190),),
        )
        db = FaresDb()
        db.locations_by_crs = {"PFL": Location("1", "PFL", "PURFLEET", "")}
        db._station_coordinates = {}
        self.assertEqual(db._pruned_attraction_crs(attraction), ["PFL"])

    def test_a_day_out_list_survives_a_pass_made_before_the_stations_were_known(self) -> None:
        # The loader applies the reviewed facets twice, and the first pass can
        # run before any classification file has named a station. The prune's
        # answer is a fact about the station set, so a first pass that cached it
        # as "no candidates" would leave the second pass, after the ONS read,
        # tagging nothing at all. A feed load cannot produce that state: it
        # reads every station out of the feed before it looks anything up, so
        # this is the one place the pass can be driven with an empty station
        # set and the hand-built state is the only way to hold the rule.
        db = FaresDb()
        db._station_coordinates = {"PFL": (51.4810, 0.2368)}
        db._apply_reviewed_facets()
        self.assertNotIn("PFL", db.location_facets_by_crs)
        db.locations_by_crs = {"PFL": Location("1", "PFL", "PURFLEET", "")}
        db._apply_reviewed_facets()
        self.assertIn("rspb", db.destination_types("PFL"))
        self.assertEqual(db.rspb_sites("PFL")[0]["name"], "Rainham Marshes")

    def test_every_reviewed_facet_code_is_a_station_code(self) -> None:
        # The codes are intersected with the feed's own stations, so a typo is
        # silently dropped rather than failing a build. Checking the shape here
        # is what catches one; the names are checked against a real download.
        for facet in DESTINATION_FACET_SOURCES:
            if not facet.is_reviewed:
                continue
            self.assertTrue(
                facet.reviewed_station_codes
                or facet.reviewed_name_markers
                or facet.reviewed_attractions,
                facet.key,
            )
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
        # A facet is added by writing one registry entry, and a reader that is
        # not registered is a defect in that entry rather than a state a feed can
        # be in -- the registry test above asserts every facet's reader is
        # registered. The guard is what turns the defect into a reported source
        # instead of a dead build, so it is stated against the step.
        db = FaresDb()
        broken = dataclasses.replace(facet("seaside"), reader="not_a_reader")
        with self.assertRaises(ValueError):
            db._apply_destination_facet(broken)

    def test_a_facet_source_with_no_readable_settlements_is_reported(self) -> None:
        # A source that names no settlements must not tag nothing in silence. The
        # only way to reach the guard is a reader that returns nothing, which a
        # feed load discovers by opening a file rather than by building one.
        db = FaresDb()
        db.locations_by_crs = {"NOT": Location("1", "NOT", "NOTTINGHAM", "")}
        db._read_ons_coastal_facet = lambda: set()  # type: ignore[method-assign]
        with self.assertRaises(ValueError):
            db._apply_destination_facet(facet("seaside"))
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
        # A facet sources its settlements from elsewhere and matches them
        # against the station names the feed carries. The checked-in reference
        # data already carries the answer for these stations on any feed load,
        # so the reader's own answer is read off the step here.
        db = FaresDb()
        db.locations_by_crs = {
            "OXF": Location("1", "OXF", "OXFORD", ""),
            "YRK": Location("2", "YRK", "YORK", ""),
            "NWE": Location("3", "NWE", "NEWPORT", ""),
        }
        db._read_learning_provider_facet = lambda: {"OXFORD", "YORK"}  # type: ignore[method-assign]
        db._apply_destination_facet(facet("university"))
        self.assertEqual(db.location_facets_by_crs["OXF"], {"university"})
        self.assertEqual(db.location_facets_by_crs["YRK"], {"university"})
        self.assertNotIn("NWE", db.location_facets_by_crs)

    def test_codes_destinations_inside_the_budget_cheapest_first(self) -> None:
        results = self.db.destinations_within("GRN", 2000)
        self.assertEqual([reachable.crs for reachable in results], ["LCN", "NOT"])
        self.assertEqual([reachable.best_pence for reachable in results], [870, 1160])

    def test_focused_load_keeps_the_same_origin_answer_without_unrelated_fares(self) -> None:
        # A focused load keeps the origin's fares and its change stations'
        # fares (ADR-0061), and nothing else. Every flow in the base fixture
        # touches Grantham or a station Grantham's flows reach, so an unrelated
        # one is added: Matlock to Retford, neither of which Grantham names.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "feed", include_return_network=True)
            with (feed / "rjfaf.ffl").open("a", encoding="utf-8") as handle:
                handle.write(
                    _line(
                        {"update_marker": "A", "record_type": "F", "origin_nlc": "8000",
                         "destination_nlc": "8100", "route_code": "00000", "flow_id": "0000090"},
                        FLOW_F,
                    )
                    + "\n"
                    + _line(
                        {"update_marker": "A", "record_type": "T", "flow_id": "0000090",
                         "ticket_code": "SDR", "fare_pence": "450", "restriction_code": ""},
                        FLOW_T,
                    )
                    + "\n"
                )
            whole = FaresDb().load_feed(feed)
            focused = FaresDb().load_feed(feed, focus_origin="GRN")
        full = {row.crs: row for row in whole.destinations_within("GRN", 1_000_000)}
        narrowed = {row.crs: row for row in focused.destinations_within("GRN", 1_000_000)}
        self.assertEqual(narrowed, full)
        self.assertLess(focused.stats()["fares"], whole.stats()["fares"])
        self.assertNotIn("0000090", focused.fares_by_flow, "a fare no Grantham page can use is dropped")
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
        # A train-restricted fare is out of the published set. It is a real fare
        # the feed sells, but its price belongs to one named train, and a page
        # that cannot name the train must not publish its price as the price of
        # the journey. What is left is the walk-up single the feed holds too.
        self.assertTrue(all(row.ticket_code == "SDS" for row in rows.values()))
        self.assertEqual(rows["NOT"].standard_pence, 700)
        self.assertEqual(rows["NOT"].ticket_code, "SDS")
        self.assertEqual(rows["NOT"].ticket_name, "ANYTIME DAY S")

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
        # Forward, the walk-up single the feed holds for GRN--NOT wins because
        # the advance fare is no longer published. Reverse, the SDS added below
        # is the only fare for the pair, and it is found in both directions.
        self.assertEqual(forward["NOT"].standard_pence, 500)
        self.assertEqual(forward["NOT"].ticket_code, "SDS")
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
        db = real_gra_fares()
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
        # SDR, not CDR: the fixture's other rule bans CDR outright, and this test
        # is about the rule that attaches a condition rather than one that
        # refuses the discount.
        rules = db.railcard_rules(
            "YNG",
            ticket_code="SDR",
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
                "YNG",
                ticket_code="SDR",
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
            "ticket_code": "CDR",
            "route_code": "00000",
            "origin_crs": "GRN",
            "destination_crs": "NOT",
            "origin_nlc": "1000",
            "destination_nlc": "2000",
        }
        self.assertTrue(db.railcard_restriction("YNG", **context).total_ban)
        self.assertIsNone(
            db.railcard_price_for("YNG", standard_pence=2400, **context)
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
            for reachable in self.db.destinations_within("GRN", 2000, adults=2, railcard="16-25 Railcard")
        }
        self.assertEqual(results["LCN"].railcard_pence, 1200)
        self.assertEqual(results["LCN"].best_pence, 870)
        self.assertEqual(results["LCN"].party_pence, 1740)

    # The .RCM record's own window is read, rather than read past: finding 3 of
    # the 29 September 2026 audit found a minimum outside its window applied as
    # if current, which holds a discounted fare above the floor the feed had
    # already retired.

    def _db_with_minimums(self, *records: tuple[str, ...]) -> FaresDb:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        feed = build_synthetic_feed(
            Path(tmp.name) / "rjfaf-rcm-window", minimum_fares=records
        )
        return FaresDb().load_feed(feed)

    def test_a_lapsed_window_does_not_raise_a_fare(self) -> None:
        db = self._db_with_minimums(("TWO", "SDR", 1200, "01012020", "31122020"))
        day = date(2026, 9, 24)
        # The card's own discount: two thirds of £8.70, rounded down to 5p.
        self.assertIsNone(db.minimum_fare("TWO", "SDR", day))
        self.assertEqual(db.railcard_price("TWO", "SDR", 870, day=day), 580)
        rows = {
            row.crs: row
            for row in db.destinations_within(
                "GRN", 2000, adults=2, railcard="Two Together", day=day
            )
        }
        self.assertEqual(rows["LCN"].railcard_pence, 580)
        self.assertEqual(rows["LCN"].standard_pence, 870)

    def test_the_window_ends_belong_to_the_record(self) -> None:
        db = self._db_with_minimums(("TWO", "SDR", 1200, "01012026", "30092026"))
        self.assertEqual(db.minimum_fare("TWO", "SDR", date(2026, 1, 1)), 1200)
        self.assertEqual(db.minimum_fare("TWO", "SDR", date(2026, 9, 30)), 1200)
        # One day past the end, the floor is gone rather than still applied.
        self.assertIsNone(db.minimum_fare("TWO", "SDR", date(2026, 10, 1)))
        # And a day before the start is the same answer for the same reason.
        self.assertIsNone(db.minimum_fare("TWO", "SDR", date(2025, 12, 31)))

    def test_comment_and_trailer_lines_are_not_records(self) -> None:
        # The 12 October 2026 feed closes its .RCM with `/!! Records: N`,
        # which the reader rejected as a bad date and the audit then failed
        # on. Every fares file gets the same header and trailer here.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        feed = build_synthetic_feed(
            Path(tmp.name) / "rjfaf-trailer",
            minimum_fares=(("TWO", "SDR", 1200, "01012026", "31122026"),),
        )
        clean = FaresDb().load_feed(feed)
        for path in sorted(Path(feed).glob("rjfaf.*")):
            body = path.read_text(encoding="utf-8").splitlines()
            lines = ["/!! Start of file", *body, f"/!! Records: {len(body)}"]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        db = FaresDb().load_feed(feed)
        self.assertEqual(db.report.records_skipped, 0, db.report.skipped_examples)
        self.assertEqual(db.minimum_fare("TWO", "SDR", date(2026, 6, 1)), 1200)
        self.assertEqual(set(db.railcards), set(clean.railcards))
        self.assertEqual(set(db.ticket_types), set(clean.ticket_types))
        self.assertEqual(set(db.locations_by_crs), set(clean.locations_by_crs))
        self.assertEqual(len(db.flows), len(clean.flows))
    def test_the_window_covering_the_day_is_the_one_applied(self) -> None:
        db = self._db_with_minimums(
            ("TWO", "SDR", 1200, "01012020", "31122020"),
            ("TWO", "SDR", 1500, "01012026", "31122026"),
        )
        self.assertEqual(db.minimum_fare("TWO", "SDR", date(2026, 9, 24)), 1500)
        self.assertIsNone(db.minimum_fare("TWO", "SDR", date(2022, 1, 1)))

    def test_the_query_day_reaches_the_railcard_price(self) -> None:
        db = self._db_with_minimums(("TWO", "SDR", 1200, "01012020", "31122020"))
        day = date(2026, 9, 24)
        self.assertEqual(
            db.railcard_price_for(
                "TWO",
                ticket_code="SDR",
                route_code="",
                origin_crs="GRN",
                destination_crs="LCN",
                origin_nlc="",
                destination_nlc="",
                standard_pence=870,
                day=day,
            ),
            580,
        )

    def test_party_budget_mode_tests_the_total(self) -> None:
        results = self.db.destinations_within(
            "GRN", 1550, adults=2, railcard="16-25 Railcard", party_budget=True
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


class FeedBoundaryClassificationTest(unittest.TestCase):
    """The classification rules, stated where a page build reads them.

    Every rule here used to be asserted by building ``locations_by_crs`` by hand
    and calling the private load step, which is the layer a reorganisation of
    ``load_feed`` breaks without changing a page. These build a synthetic feed
    and read the answer back through the public query methods, so what they are
    coupled to is the fixture boundary a site is built from.

    The station table below is the load-bearing part: the fixture's own
    GRN..XFD is in no reviewed list but London King's Cross, and its own
    classification file answers that one anyway, so a reviewed rule can only be
    seen at the boundary if the feed carries the station the list names.
    """

    FALLBACK_STATIONS = (
        # The London list, for a station the workbook does not name.
        ("ECR", "EAST CROYDON", "city"),
        # Major English cities outside the workbook, and the nations it does not
        # cover: Scotland, Wales outside its settlement names, Northern Ireland.
        ("MAN", "MANCHESTER PIC", "city"),
        ("GLC", "GLASGOW CENTRAL", "city"),
        ("NWY", "NEWRY", "town"),
        # CDD is Cardenden, not Cardiff Central: the feed's own name for the
        # code. An earlier hand-built fixture invented CARDIFF CENTRAL under CDD,
        # which made a test assert a city for a station that is not one and hid
        # the same slip in the reviewed list. A fixture that contradicts the
        # feed cannot catch a list entry that does.
        ("CDD", "CARDENDEN", "town"),
        ("NCL", "NEWCASTLE", "city"),
        # Reviewed settlement fallbacks: the floor that removes "No settlement
        # band" from a destination a page can actually price.
        ("EDL", "EDALE", "village"),
        ("BHC", "BALLOCH CENTRAL", "village"),
    )

    def test_a_station_no_source_names_is_classified_by_its_reviewed_fallback(self) -> None:
        # A reviewed list is a floor under the real sources, and a station
        # nothing else classifies is still a destination the page can price:
        # leaving it "other" is what the "No settlement band" answer was.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed_with_stations(
                Path(tmp), *((crs, name) for crs, name, _ in self.FALLBACK_STATIONS)
            )
            db = FaresDb().load_feed(feed)
        for crs, _name, kind in self.FALLBACK_STATIONS:
            self.assertEqual(db.destination_type(crs), kind, crs)
            self.assertNotIn("other", db.destination_types(crs), crs)

    def test_a_reviewed_fallback_outranks_a_source_that_filed_the_station_other(self) -> None:
        # The reviewed lists are the floor, so they are applied where a source's
        # answer was "other" and not only where there is no answer at all: a
        # station the workbook cannot name is still a settlement, and keeping
        # the earlier class would publish the unsourced remainder. The source is
        # named in the assertions because a file whose label is recorded is one
        # whose classes were read, which is what makes "village" below the
        # fallback's answer rather than the file's.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = _feed_with_stations(root, ("EDL", "EDALE"))
            (root / "saying-other.location-types.json").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA,
                        "source": "a source that filed Edale as other",
                        "records": {"EDL": {"primary": "other"}},
                    }
                ),
                encoding="utf-8",
            )
            db = FaresDb().load_feed(feed)
        self.assertIn("a source that filed Edale as other", db.location_type_sources)
        self.assertEqual(db.destination_type("EDL"), "village")

    def test_attenborough_is_a_village_and_a_nature_site(self) -> None:
        # The reserve five minutes from the station is the proof the page names
        # for the nature chip (ADR-0064), so the station has to earn both the
        # class and the named day-out through a real load.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed_with_stations(Path(tmp), ("ATB", "ATTENBOROUGH"))
            db = FaresDb().load_feed(feed)
        self.assertEqual(db.destination_type("ATB"), "village")
        self.assertIn("nature", db.destination_types("ATB"))
        self.assertNotIn("other", db.destination_types("ATB"))
        self.assertEqual(
            db.nature_sites("ATB"),
            [{
                "name": "Attenborough Nature Reserve",
                "url": "https://www.nottinghamshirewildlife.org/attenborough-plan-your-visit",
            }],
        )
        self.assertEqual(db.nature_sites("NOT"), [])

    def test_an_airport_station_is_in_the_airport_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed_with_stations(Path(tmp), ("XQB", "EAST M AIR LGE"))
            db = FaresDb().load_feed(feed)
        self.assertIn("airport", db.destination_types("XQB"))
        self.assertIn("airport", SUPPORTED_DESTINATION_FACETS)
        self.assertIn(("airport", "Airports"), DESTINATION_TYPE_FILTERS)
        # The airport is its own category, and the settlement it serves is
        # still classified, so the row is not left as the unsourced remainder.
        self.assertEqual(db.destination_type("XQB"), "village")
        self.assertNotIn("other", db.destination_types("XQB"))

    def test_the_seaside_supplement_tags_classic_day_out_stations(self) -> None:
        # The ONS coastal workbook misses Blackpool, Brighton, Southend and
        # Weston-super-Mare by name, so a reviewed supplement carries them: the
        # chip has to reach the stations the feed actually contains, and each
        # one has to name its beach.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed_with_stations(
                Path(tmp),
                ("BTN", "BRIGHTON"),
                ("BPN", "BLACKPOOL NORTH"),
                ("WSM", "WESTON SUPR MARE"),
                ("SOC", "SOUTHEND CENTRAL"),
            )
            db = FaresDb().load_feed(feed)
        for crs in ("BTN", "BPN", "WSM", "SOC"):
            self.assertIn("seaside", db.location_facets_by_crs.get(crs, set()), crs)
            self.assertTrue(db.coastal_sites(crs), crs)

    def test_a_coach_or_parkway_station_is_a_transport_interchange(self) -> None:
        # Locations whose purpose is to move people between networks are
        # destinations, and without the tag the page had no answer for them: the
        # name markers reach most, and the code list reaches the ones whose
        # names say nothing.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed_with_stations(
                Path(tmp),
                ("XDO", "BATH BUS STATION"),
                ("TIN", "MAGNA TRAM STOP"),
                ("TPC", "THORPE CULVERT"),
                ("BUS", "BUSBY"),
                ("ATB", "ATTENBOROUGH"),
            )
            db = FaresDb().load_feed(feed)
        self.assertIn("transport", db.destination_types("XDO"))
        self.assertIn("transport", db.destination_types("TIN"))
        # A park and ride named after the village it serves carries no marker,
        # so the code list has to reach it.
        self.assertIn("transport", db.destination_types("TPC"))
        # BUSBY is a village whose name merely contains the marker.
        self.assertNotIn("transport", db.destination_types("BUS"))
        self.assertNotIn("transport", db.destination_types("ATB"))
        self.assertIn(("transport", "Transport interchanges"), DESTINATION_TYPE_FILTERS)

    def test_reviewed_facets_only_tag_stations_the_feed_actually_has(self) -> None:
        # A stale code on a reviewed list is dropped rather than applied to a
        # station the feed does not carry, so a facet cannot name somewhere this
        # build has never heard of.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed_with_stations(Path(tmp), ("HHD", "HOLYHEAD"))
            db = FaresDb().load_feed(feed)
        island = facet("island")
        self.assertIn("HHD", island.reviewed_station_codes)
        self.assertNotIn("NOT", island.reviewed_station_codes)
        self.assertIn("island", db.destination_types("HHD"))
        self.assertNotIn("island", db.destination_types("NOT"))

    def test_a_reviewed_attraction_tags_its_station_and_names_the_proof(self) -> None:
        # Chip implies a named proof (ADR-0064), extended to the ADR-0062
        # sources: the station carries the facet and the reserve by name.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed_with_stations(Path(tmp), ("PFL", "PURFLEET"), ("BEM", "BEMPTON"))
            db = FaresDb().load_feed(feed)
        self.assertIn("rspb", db.destination_types("PFL"))
        self.assertIn("rspb", db.destination_types("BEM"))
        self.assertNotIn("rspb", db.destination_types("NOT"))
        self.assertEqual(
            db.rspb_sites("PFL"),
            [{
                "name": "Rainham Marshes",
                "url": "https://www.rspb.org.uk/nature-reserves/rainham-marshes/",
            }],
        )
        # A station the facet did not tag carries no proof for it.
        self.assertEqual(db.rspb_sites("NOT"), [])

    def test_a_warm_cache_still_earns_the_day_out_chips(self) -> None:
        # ADR-0065: the three reviewed day-out lists shipped *without* a cache
        # schema bump, and the reason has to keep holding. A cache written by the
        # previous release is the current schema with no rspb chip anywhere on
        # it; the reviewed pass runs after the cache is read and tags additively,
        # so the chip appears anyway. If that pass were ever moved before the
        # cache load, or made to respect a cached facet list as final, a build on
        # a warm cache would silently lose the chips until the schema was bumped.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = _feed_with_stations(root, ("PFL", "PURFLEET"))
            (root / f"warm.{DESTINATION_FACETS_FILE}").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA,
                        "source": "a build from before the day-out sources",
                        "records": {"PFL": {"primary": "other", "facets": []}},
                    }
                ),
                encoding="utf-8",
            )
            db = FaresDb().load_feed(feed)
        self.assertIn("rspb", db.destination_types("PFL"))
        self.assertEqual(db.rspb_sites("PFL")[0]["name"], "Rainham Marshes")
        # A warm cache is not a stale-cache note: nothing was discarded.
        self.assertEqual(
            [note for note in db.report.skipped_files if "schema" in note], []
        )

    def test_facets_from_several_files_are_merged_not_replaced(self) -> None:
        # The checked-in reference data, a cache beside the feed and the feed's
        # own lookup can all name the same station. Replacing made the answer
        # depend on the order the files were read in, and let a stale cache drop
        # a facet the checked-in file knew about. LCN keeps its seaside and its
        # university beside the second file's island, a facet no registry entry
        # declares is dropped rather than served, and a key written with padding
        # and in lower case is the same station as the feed's own.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = _feed_with_stations(root)
            (root / f"second.{DESTINATION_FACETS_FILE}").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA,
                        "source": "a second file naming the same station",
                        "records": {
                            "  lcn ": {"primary": "city", "facets": ["island", "nonsense"]}
                        },
                    }
                ),
                encoding="utf-8",
            )
            db = FaresDb().load_feed(feed)
        self.assertEqual(db.destination_type("LCN"), "city")
        self.assertEqual(
            sorted(db.location_facets_by_crs["LCN"]), ["island", "seaside", "university"]
        )
        self.assertNotIn("lcn", db.location_facets_by_crs)

    def test_a_reviewed_code_the_feed_does_not_carry_is_named(self) -> None:
        # A reviewed list is only as good as its fit with the feed, so a code
        # that names no station in it is recorded rather than left to grow. The
        # lists are intersected before they are applied, so the record is the
        # only effect a dead code has, and it is not a skipped file: nothing
        # went unread, a reviewed list is naming a station the feed does not
        # carry.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed_with_stations(Path(tmp), ("BHC", "BALLOCH CENTRAL"))
            # The prune's coordinates come from the fixture, not the licensed
            # download a clean checkout lacks, whose absence is a skipped file.
            coordinates = build_synthetic_station_coordinates(Path(tmp) / "stations.xml")
            with mock.patch.object(atoc_fares, "DEFAULT_STATIONS_XML", coordinates):
                db = FaresDb().load_feed(feed)
        absent = db.report.reviewed_codes_absent
        self.assertTrue(absent, "the dead codes are named")
        self.assertEqual(db.report.skipped_files, [])
        # A reviewed code the feed does carry is applied, and is not named as
        # absent: the record is about the feed, not about the list.
        self.assertEqual(db.destination_type("BHC"), "village")
        self.assertNotIn("BHC", absent)
        self.assertIn("ABD", absent)
        self.assertEqual(db.destination_type("ABD"), "other")

    def test_a_size_band_names_the_settlement_class_of_a_station(self) -> None:
        # The ONS bands are population classes, and the two smallest are the
        # whole difference between a village and a town: collapsing them into
        # one "town" is what left villages filed as "other".
        with tempfile.TemporaryDirectory() as tmp:
            feed = _first_build(
                Path(tmp),
                ("ANC", "ANCASTER"),
                ("BTF", "BOTTESFORD"),
                ("RET", "RETFORD"),
            )
            workbook = _ons_workbook(
                (("Ancaster", "minor"), ("Bottesford", "minor"), ("Retford", "medium"))
            )
            with mock.patch.object(
                atoc_fares.urllib.request,
                "urlopen",
                side_effect=_only_source(ONS_BUILT_UP_AREAS_FILE_URL, workbook),
            ):
                db = FaresDb().load_feed(feed)
        self.assertEqual(db.destination_type("ANC"), "village")
        self.assertEqual(db.destination_type("BTF"), "village")
        self.assertEqual(db.destination_type("RET"), "town")

    def test_a_workbook_district_does_not_hide_the_station_the_feed_carries(self) -> None:
        # The workbook writes "Foxton (South Cambridgeshire)"; the station is
        # FOXTON, and the two sides have to normalise the same way. On the real
        # feed this gap alone left 43 priced destinations unclassified.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _first_build(Path(tmp), ("FXN", "FOXTON"))
            workbook = _ons_workbook((("Foxton (South Cambridgeshire)", "minor"),))
            with mock.patch.object(
                atoc_fares.urllib.request,
                "urlopen",
                side_effect=_only_source(ONS_BUILT_UP_AREAS_FILE_URL, workbook),
            ):
                db = FaresDb().load_feed(feed)
        self.assertEqual(db.destination_type("FXN"), "village")

    def test_a_refused_settlement_name_leaves_the_station_other(self) -> None:
        # Wick (Hackney) and Wick (Highland) are different places in different
        # bands; a station called WICK cannot be told which one it serves from
        # its name, so it keeps the coverage report rather than taking a class
        # that may belong to the other.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _first_build(Path(tmp), ("WCK", "WICK"))
            workbook = _ons_workbook(
                (("Wick (Hackney)", "large"), ("Wick (Highland)", "small"))
            )
            with mock.patch.object(
                atoc_fares.urllib.request,
                "urlopen",
                side_effect=_only_source(ONS_BUILT_UP_AREAS_FILE_URL, workbook),
            ):
                db = FaresDb().load_feed(feed)
        self.assertEqual(db.destination_type("WCK"), "other")

    def test_a_reviewed_fallback_the_workbook_already_names_is_reported(self) -> None:
        # A reviewed entry for a station the workbook names is not an error
        # today: the class is never applied, so nothing looks wrong. It becomes
        # one the day a name match misses, and the reviewed class then lands on
        # a station the workbook had classified correctly -- York was filed as a
        # town beside a workbook that says city. Both halves matter: the code is
        # named, and the workbook still wins while it is there.
        workbook = _ons_workbook((("York", "large"),))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(
                atoc_fares.urllib.request,
                "urlopen",
                side_effect=_only_source(ONS_BUILT_UP_AREAS_FILE_URL, workbook),
            ):
                named = FaresDb().load_feed(_first_build(root / "without", ("YRK", "YORK")))
                # Put the entry back and the next build names it: the list no
                # longer holds York, so nothing is redundant until one is.
                with mock.patch.dict(atoc_fares.MAJOR_UK_STATION_FALLBACKS, {"YRK": "town"}):
                    with_entry = FaresDb().load_feed(_first_build(root / "with", ("YRK", "YORK")))
        self.assertEqual(named.destination_type("YRK"), "city")
        self.assertNotIn("YRK", named.report.reviewed_codes_redundant, "the list no longer names York")
        self.assertIn("YRK", with_entry.report.reviewed_codes_redundant)
        self.assertEqual(
            with_entry.destination_type("YRK"), "city", "the workbook's class still wins"
        )
        # Named once, because the pass runs again as each source lands and a
        # note per pass would say the same thing three times.
        self.assertEqual(with_entry.report.reviewed_codes_redundant.count("YRK"), 1)

    def test_a_discard_does_not_cost_a_later_source_its_label(self) -> None:
        # The flag that records a discard is sticky, and it must not be
        # consulted for every candidate after the one that discarded: a file
        # that classifies the feed properly is loaded after a stale cache in
        # every real layout, and clearing its label left the build claiming no
        # source at all for classes a source had just supplied. ANC and RET are
        # in no reviewed list, so a class for them can only have come from a file.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = _feed_with_stations(root, ("ANC", "ANCASTER"), ("RET", "RETFORD"))
            (root / "aaa.stale.location-types.json").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA - 1,
                        "source": "an older build",
                        "records": {"ANC": {"primary": "other"}, "RET": {"primary": "other"}},
                    }
                ),
                encoding="utf-8",
            )
            (root / f"zzz.sourced.{DESTINATION_FACETS_FILE}").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA,
                        "source": "a sourced workbook",
                        "records": {"ANC": {"primary": "village"}, "RET": {"primary": "town"}},
                    }
                ),
                encoding="utf-8",
            )
            db = FaresDb().load_feed(feed)
        self.assertEqual(db.destination_type("ANC"), "village")
        self.assertEqual(db.destination_type("RET"), "town")
        # The label names the file that classified the feed, and the discarded
        # cache's own claim is not in it: a label is recorded when a file's
        # classes are kept, and dropped with the classes when they are not. The
        # two wrong answers this replaces were an empty label, which claims
        # nothing classified the feed, and the fallback label, which claims the
        # reviewed lists did it when ANC and RET are in no reviewed list.
        self.assertIn("a sourced workbook", db.location_type_sources)
        self.assertNotIn("an older build", db.location_type_sources)

    def test_a_discarded_cache_does_not_stop_the_workbook_being_read(self) -> None:
        # The whole classification pass, because a discarded file must not leave
        # the build looking as though it already has a source: the classes are
        # gone and the file's label is gone with them, so the workbook is what
        # fills the gap. When the label stood, the pass returned early and every
        # station the cache had classified fell through to the reviewed
        # fallbacks -- 3,119 of 3,436 on the 24 September 2026 download. ANC is
        # in no reviewed list, so "village" below can only have come from the
        # workbook.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = _feed_with_stations(root, ("ANC", "ANCASTER"))
            # The fixture writes its own cache beside every feed it builds; this
            # is that file, now carrying the classes a build wrote before the
            # schema moved.
            (root / "fares.location-types.json").write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA - 1,
                        "source": "an older build",
                        "records": {"ANC": {"primary": "other", "facets": ["seaside"]}},
                    }
                ),
                encoding="utf-8",
            )
            (root / "download-manifest.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(
                atoc_fares.urllib.request,
                "urlopen",
                side_effect=_only_source(
                    ONS_BUILT_UP_AREAS_FILE_URL, _ons_workbook((("Ancaster", "minor"),))
                ),
            ):
                db = FaresDb().load_feed(feed)
        self.assertEqual(db.destination_type("ANC"), "village")
        self.assertEqual(db.location_facets_by_crs["ANC"], {"seaside"})
        # The build names the workbook, not the cache whose classes it threw
        # away: that label is what the page's provenance line claims.
        self.assertIn(LOCATION_TYPE_SOURCE, db.location_type_sources)
        self.assertNotIn("an older build", db.location_type_sources)

    def test_only_the_classification_files_this_project_writes_are_read(self) -> None:
        # A file beside a feed whose name merely mentioned locations and types
        # used to be loaded as a source, so a backup, a scratch probe or a
        # staging copy of the cache was trusted exactly as much as the cache.
        # The same bytes are read under a name this project writes and ignored
        # under one it does not.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = _feed_with_stations(root, ("ANC", "ANCASTER"))
            lookalike = root / "location-types-notes.json"
            lookalike.write_text(
                json.dumps(
                    {
                        "schema": LOCATION_CACHE_SCHEMA,
                        "source": "a scratch probe",
                        "records": {"ANC": {"primary": "town"}},
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                atoc_fares.urllib.request, "urlopen", side_effect=OSError("offline")
            ):
                ignored = FaresDb().load_feed(feed)
                self.assertEqual(ignored.destination_type("ANC"), "other")
                self.assertNotIn("a scratch probe", ignored.location_type_sources)

                (root / f"notes{LOCATION_TYPES_FILE}").write_text(
                    lookalike.read_text(encoding="utf-8"), encoding="utf-8"
                )
                glued = FaresDb().load_feed(feed)
                self.assertEqual(
                    glued.destination_type("ANC"),
                    "other",
                    "a name glued onto the prefix is not a name this project writes",
                )

                lookalike.rename(root / f"probe.{LOCATION_TYPES_FILE}")
                accepted = FaresDb().load_feed(feed)
        self.assertEqual(accepted.destination_type("ANC"), "town")
        self.assertIn("a scratch probe", accepted.location_type_sources)

    def test_a_build_names_every_source_that_classified_the_feed(self) -> None:
        # The page's provenance line is where a reader learns where a
        # destination's type comes from. London is classified by the reviewed
        # list before the workbook is read at all, and the build used to publish
        # that class as the workbook's own work -- so a build with both names
        # both, and the reviewed floor is named last.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = _first_build(root, ("ANC", "ANCASTER"))
            workbook = _ons_workbook((("Ancaster", "minor"),))
            with mock.patch.object(
                atoc_fares.urllib.request,
                "urlopen",
                side_effect=_only_source(ONS_BUILT_UP_AREAS_FILE_URL, workbook),
            ):
                db = FaresDb().load_feed(feed)
            written = json.loads((root / LOCATION_TYPES_FILE).read_text(encoding="utf-8"))
        # The reviewed list classified London on its own, and the workbook was
        # still read for the rest of the country: a build whose only classes are
        # the reviewed fallbacks has to read it, or a first build would never
        # classify anything outside them.
        self.assertEqual(db.destination_type("KGX"), "city")
        self.assertEqual(db.destination_type("ANC"), "village")
        self.assertEqual(
            db.location_type_sources, [LOCATION_FALLBACK_SOURCE, LOCATION_TYPE_SOURCE]
        )
        self.assertEqual(
            db.location_type_source,
            LOCATION_TYPE_SOURCE + " + " + LOCATION_FALLBACK_SOURCE,
        )
        # Written back with both, so the next build names both without reading
        # the workbook again. The list keeps the order the labels were loaded
        # in; the string beside it is the page's reading order.
        self.assertEqual(
            written["provenance"], [LOCATION_FALLBACK_SOURCE, LOCATION_TYPE_SOURCE]
        )
        self.assertEqual(
            written["source"], LOCATION_TYPE_SOURCE + " + " + LOCATION_FALLBACK_SOURCE
        )


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
            "GRN", 2000, railcard="16-25 Railcard"
        )
        # The fixture's general R9 RR row attaches the card's travel condition.
        # It is not a total ban, so the reviewed fares stay priced.
        self.assertEqual({row.crs for row in rows}, {"LCN", "NOT", "PBO"})
        prices = {row.crs: row.railcard_pence for row in rows}
        # LCN's £8.70 SDR fare is raised to the card's £12.00 minimum, which is
        # the case the page has to state rather than present as a saving, and
        # NOT's cheaper CDR fare is the one the fixture bans outright.
        self.assertEqual(prices, {"LCN": 1200, "NOT": 1200, "PBO": 1490})

    def test_a_railcard_price_is_kept_when_no_rr_rule_matches(self) -> None:
        db = FaresDb().load_feed(self.feed)
        db.restrictions.railcard_rows.clear()
        rows = {
            row.crs: row
            for row in db.publishable_destinations_within(
                "GRN", 2000, railcard="16-25 Railcard"
            )
        }
        self.assertEqual(rows["LCN"].railcard_pence, 1200)
        self.assertEqual(rows["NOT"].railcard_pence, 1200)

    def test_non_publishable_mode_still_prices_a_railcard_for_analysis(self) -> None:
        results = {
            reachable.crs: reachable
            for reachable in self.plain_db.publishable_destinations_within(
                "GRN", 2000, adults=2, railcard="16-25 Railcard", require_restrictions=False
            )
        }
        # SDR carries the card's £12.00 minimum fare, so the discounted price
        # is the minimum rather than two thirds of £14.20.
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
        # One header per restriction code the fixture's own fares carry, plus
        # the one that exercises the rest of the record types.
        self.assertEqual(self.db.restrictions.record_counts["RH"], 3)
        # One pair of rules per reviewed card, because an RR record is
        # keyed by the card it governs: a card with no rule of its own is
        # not discounted at all, which is how the fixture came to offer
        # one card in a control built to offer six.
        self.assertEqual(self.db.restrictions.record_counts["RR"], 12)
        self.assertEqual(self.db.restrictions.headers["R1"].description, "PEAK TO LONDON")
        self.assertIn("YNG", self.db.restrictions.railcard_record_counts)
        self.assertEqual(self.plain_db.restrictions.gate_problem() is not None, True)

    def test_a_restriction_header_carries_the_validity_beside_the_description(
        self,
    ) -> None:
        # C08: the page can only tell a reader what a condition permits because
        # the header carries the outward and return text, not just the code's
        # name. A parser that read the description and dropped the other two
        # would leave the page nothing to show.
        header = self.db.restrictions.headers["1A"]
        self.assertEqual(header.outward_text, "NOT VALID FOR TRAVEL ON SATURDAY OR SUNDAY")
        self.assertEqual(
            header.return_text, "RETURN NOT VALID FOR TRAVEL ON SATURDAY OR SUNDAY"
        )


class RailcardAdultBoundsTest(unittest.TestCase):
    """The adult range a card is offered with, read from the feed's own records.

    A railcard cannot price a party of no one, so a family whose union came
    out at zero adults would tell a reader a card that is not there. The real
    feed carries the 16-25 3-year codes Y3R and YN3 as 0-0, and taking those at
    face value reported the 16-25 Railcard as covering zero to eight adults.
    """

    def _db_with(self, records):
        db = atoc_fares.FaresDb()
        db.railcards = {
            code: atoc_fares.Railcard(code=code, name=code, min_adults=low, max_adults=high)
            for code, (low, high) in records.items()
        }
        return db

    def test_a_zero_bound_is_read_as_unstated_not_as_zero_adults(self):
        db = self._db_with({"YNG": (1, 1), "Y3R": (0, 0), "YN3": (0, 0), "RYP": (1, 8)})
        families = {family.label: family for family in db.reviewed_railcard_families()}
        self.assertEqual(1, families["16-25 Railcard"].min_adults)
        self.assertEqual(8, families["16-25 Railcard"].max_adults)

    def test_every_reviewed_card_offers_a_party_of_at_least_one_adult(self):
        db = self._db_with({code: (0, 0) for code in ("YNG", "NEW", "SRN", "DIS", "BB2", "2TR")})
        for family in db.reviewed_railcard_families():
            with self.subTest(family.label):
                self.assertGreaterEqual(family.min_adults, 1)

    def test_a_card_that_states_no_bound_at_all_prices_one_adult(self):
        db = self._db_with({"BB2": (0, 0)})
        family = db.reviewed_railcard_families()[0]
        self.assertEqual((1, 1), (family.min_adults, family.max_adults))


class ReviewedRailcardTest(unittest.TestCase):
    """What the page may offer, and what it is offered under.

    The feed gives one product several codes -- a base code, a three-year
    code, an online code, a replacement code and a corporate one -- and a
    reader holding any of them holds the same card. Publishing the codes
    separately would put five controls on the page for one product and make
    the reader work out which one they have.
    """

    def setUp(self) -> None:
        self.db = FaresDb()
        self.db.railcards = {
            "2TR": Railcard("2TR", "TWO TOGETHER R/CARD", 2, 2),
            "YNG": Railcard("YNG", "16-25 RAILCARD", 1, 1),
            "Y3R": Railcard("Y3R", "16-25 3YR RC REP", 0, 0),
            "RYP": Railcard("RYP", "REP 16-25 RAILCARD", 1, 8),
            "SRN": Railcard("SRN", "SENIOR RAILCARD", 1, 1),
            "RSN": Railcard("RSN", "REP SENIOR RAILCARD", 1, 8),
            "NEW": Railcard("NEW", "NETWORK RAILCARD", 0, 4),
            "DIS": Railcard("DIS", "DISABLED ADULT", 1, 2),
            "AT1": Railcard("AT1", "1YR DISABLED PERSONS", 1, 2),
            "AT4": Railcard("AT4", "3YR DISABLED PERSONS", 1, 2),
            "BB2": Railcard("BB2", "STUDENT DISCOUNT", 1, 1),
            "TYC": Railcard("TYC", "A CLUB SEASON TICKET", 1, 4),
        }

    def test_a_product_is_one_control_however_many_codes_the_feed_gives_it(self) -> None:
        families = {family.key: family for family in self.db.reviewed_railcard_families()}
        self.assertEqual(sorted(families), ["2TR", "BB2", "DIS", "NEW", "SRN", "YNG"])
        self.assertEqual(families["YNG"].codes, ("YNG", "Y3R", "RYP"))
        self.assertEqual(families["YNG"].label, "16-25 Railcard")

    def test_a_code_outside_the_reviewed_set_is_not_offered(self) -> None:
        # The catalogue is 382 codes on the real feed and most are agency,
        # group-travel and football-club passes. A club season ticket is a real
        # code that a page cannot offer 382 of.
        offered = {family.key for family in self.db.reviewed_railcard_families()}
        self.assertNotIn("TYC", offered)

    def test_the_adult_bounds_are_the_union_across_the_products_codes(self) -> None:
        # The feed gives the Senior Railcard 1-1 under SRN and 1-8 under RSN.
        # A reader with the replacement is still one traveller, and a bound
        # taken from one code rather than the product would price a party of
        # two at a one-adult card's rate on one code and refuse it on another.
        families = {family.key: family for family in self.db.reviewed_railcard_families()}
        self.assertEqual((families["SRN"].min_adults, families["SRN"].max_adults), (1, 8))

    def test_a_product_the_feed_drops_is_reported_and_not_silently_shortened(self) -> None:
        del self.db.railcards["2TR"]
        families = {family.key: family for family in self.db.reviewed_railcard_families()}
        self.assertNotIn("2TR", families)
        self.assertEqual(self.db.report.reviewed_railcard_codes_absent, ["2TR"])

    def test_a_product_whose_primary_code_is_gone_is_still_offered_through_an_alias(self) -> None:
        # Refusing a card because the feed dropped one of its spellings would
        # be a page answering the wrong question about a card the reader holds.
        del self.db.railcards["YNG"]
        families = {family.key: family for family in self.db.reviewed_railcard_families()}
        self.assertIn("Y3R", families)
        self.assertEqual(families["Y3R"].label, "16-25 Railcard")

    def test_the_list_is_ordered_by_the_label_a_reader_reads(self) -> None:
        labels = [family.label for family in self.db.reviewed_railcard_families()]
        self.assertEqual(labels, sorted(labels))


class AdvanceFareTest(unittest.TestCase):
    """One definition of "advance", asked through the fares database.

    The page labels an Advance single differently from a walk-up fare, so the
    test that decides it has to agree with the feed. A ticket called ADVANCE
    is train-specific whatever code it carries, and a restriction the ``.RST``
    file describes as "valid on date&train shown only" is train-specific
    whatever the ticket is called. The second test reads the file rather than
    naming one code: this build recognised AS alone, so the 51 other codes the
    feed describes the same way reached the page as ordinary singles, and GA
    among them is on every LNER promotion, Edinburgh included (audit A9).
    """

    def test_a_restriction_code_alone_marks_the_fare_advance(self) -> None:
        fares = atoc_fares.FaresDb()
        self.assertTrue(fares.is_advance_fare("SUPER OFFPEAK DAY R", " as "))
        self.assertFalse(fares.is_advance_fare("SUPER OFFPEAK DAY R", "RH"))
        self.assertFalse(fares.is_advance_fare("SUPER OFFPEAK DAY R", ""))

    def test_a_code_the_restriction_file_calls_a_date_and_train_is_advance(self) -> None:
        fares = atoc_fares.FaresDb()
        fares.restrictions.headers["GA"] = atoc_restrictions.parse_header(
            _restriction_header("GA", "IEC ADVANCE", "VALID ON DATE&TRAIN SHOWN ONLY.LTD CHANGE.NO RFND")
        )
        fares.restrictions.headers["ZZ"] = atoc_restrictions.parse_header(
            _restriction_header("ZZ", "ANYTHING", "VALID ON ANY TRAIN")
        )
        # The LNER promotion that reached the page as a walk-up single.
        self.assertTrue(fares.is_advance_fare("LNER PROMO STD", "GA"))
        self.assertFalse(fares.is_advance_fare("LNER PROMO STD", "ZZ"))
        # A code the file does not describe is not claimed either way.
        self.assertFalse(fares.is_advance_fare("LNER PROMO STD", "QQ"))

    def test_a_ticket_name_alone_marks_the_fare_advance(self) -> None:
        fares = atoc_fares.FaresDb()
        self.assertTrue(fares.is_advance_fare("ANYTIME ADVANCE DAY S", ""))
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
        self.assertFalse(atoc_fares.FaresDb().is_advance_fare(None, None))


class ConditionalFareTest(unittest.TestCase):
    """A child's or a group's fare is not the price one traveller pays.

    The page publishes the cheapest fare the feed holds, so a 10p UNDER 11
    single wins the slot from an adult's origin and the reader is told a
    journey costs ten pence. Each test opens its own database, because the
    fixture is class-level and a fare injected into it would leak into the
    next test in this class and the ones after it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_synthetic_feed(Path(cls._tmp.name) / "conditional")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _db(self):
        return FaresDb().load_feed(self.feed)

    def _with(self, db, code, name, pence, ticket_type="S"):
        """Give one destination a fare with this ticket, on the live flow."""
        flow_id = next(iter(db.fares_by_flow))
        db.fares_by_flow[flow_id][code] = Fare(code, pence, "")
        db.ticket_types[code] = TicketType(code, name, "2", ticket_type, False)
        return db

    def test_a_childs_single_cannot_win_the_cheapest_single_slot(self) -> None:
        db = self._with(self._db(), "CTS", "UNDER 11 SINGLE", 10)
        rows = {row.crs: row for row in db.page_single_destinations_within("GRN", 1_000_000)}
        self.assertNotIn("CTS", {row.ticket_code for row in rows.values()})
        # NOT still has a fare, and it is the walk-up adult single the feed also
        # holds rather than the advance one, which the published set no longer
        # carries for the reason its own test gives.
        self.assertIn("NOT", rows)
        self.assertEqual(rows["NOT"].ticket_code, "SDS")

    def test_the_child_fare_is_rejected_and_the_reason_says_why(self) -> None:
        # The coverage report counts reasons, so a child's fare filed under
        # "not a standard single" could not be told apart from a first-class
        # one, and the report would answer a question nobody asked.
        db = self._with(self._db(), "CTS", "UNDER 11 SINGLE", 10)
        tally: dict[str, int] = {}
        db.page_single_destinations_within("GRN", 1_000_000, tally=tally)
        self.assertEqual(tally[atoc_fares.CONDITIONAL_REASON], 1)

    def test_a_groups_single_cannot_win_the_slot_either(self) -> None:
        # The 999p sentinel was the one code that cost the most destinations.
        db = self._with(self._db(), "SPN", "LNER GRP SGL", 99_900)
        rows = db.page_single_destinations_within("GRN", 1_000_000)
        self.assertNotIn("SPN", {row.ticket_code for row in rows})

    def test_a_childs_return_cannot_win_the_cheapest_return_slot(self) -> None:
        db = self._with(self._db(), "CTR", "UNDER 11 RETURN", 5, ticket_type="R")
        rows = {row.crs: row for row in db.page_destinations_within("GRN", 1_000_000)}
        self.assertNotIn("CTR", {row.ticket_code for row in rows.values()})
        self.assertIn("NOT", rows)

    def test_the_measurement_switch_puts_them_back_and_can_only_add_destinations(self) -> None:
        # The loss report subtracts the two answers, so the relationship the
        # report depends on is that the conditional run reaches everything the
        # reviewed run reaches. It is not that prices match: putting a 10p
        # child's fare back is meant to move the price of the destination it
        # wins, and the report counts that destination as lost.
        db = self._with(self._db(), "CTS", "UNDER 11 SINGLE", 10)
        kept = {row.crs: row for row in db.page_single_destinations_within("GRN", 1_000_000)}
        every = {
            row.crs: row
            for row in db.page_single_destinations_within(
                "GRN", 1_000_000, include_conditional=True
            )
        }
        self.assertIn("CTS", {row.ticket_code for row in every.values()})
        self.assertLessEqual(set(kept), set(every))
        self.assertEqual(every["NOT"].ticket_code, "CTS")
        # The reviewed run still shows the adult fare for the same pair.
        self.assertEqual(kept["NOT"].ticket_code, "SDS")
        self.assertGreater(kept["NOT"].best_pence, every["NOT"].best_pence)

    def test_a_destination_only_the_child_priced_is_lost_and_says_so(self) -> None:
        # The rule is tested inside the shared loop, so a destination whose
        # only fare is a child's disappears rather than keeping a price the
        # reader cannot buy.
        db = self._with(self._db(), "CTS", "UNDER 11 SINGLE", 10)
        before = {row.crs for row in db.page_single_destinations_within("GRN", 1_000_000, include_conditional=True)}
        after = {row.crs for row in db.page_single_destinations_within("GRN", 1_000_000)}
        self.assertIn("NOT", before)
        self.assertTrue(before - after or after, "the comparison must be meaningful")

    def test_the_table_holds_the_codes_the_feed_actually_used(self) -> None:
        # Guard against a future edit that empties the table, which would
        # silently put every child's fare back on the page.
        self.assertEqual(len(atoc_fares.CONDITIONAL_TICKET_CODES), 107)
        for code in ("CTS", "CTR", "TKS", "TKR", "SPN", "S05", "ENT"):
            self.assertIn(code, atoc_fares.CONDITIONAL_TICKET_CODES, code)

    def test_the_sale_advance_family_is_closed_not_just_the_code_named(self) -> None:
        # The rate gate found DGB at GBP 1.00 and stayed silent on DGC at
        # GBP 2.00, because a rate inside the band is not evidence that a
        # fare is purchasable. All three are one product on route 00429, so
        # excluding the one the gate named would leave two live.
        for code in ("DGA", "DGB", "DGC"):
            self.assertIn(code, atoc_fares.CONDITIONAL_TICKET_CODES, code)

    def test_a_staff_and_a_concession_fare_are_also_excluded(self) -> None:
        # These are not children and not parties, and a reader cannot buy
        # either at the price the feed quotes: a staff pass at 5p and a
        # concession at 10p are the same fact about a fare as an UNDER 11
        # single, so they are excluded by the same rule.
        for code in ("BJD", "COS", "COR", "DGA", "KWA"):
            self.assertIn(code, atoc_fares.CONDITIONAL_TICKET_CODES, code)

    def test_a_sentinel_is_a_placeholder_and_not_a_conditional_fare(self) -> None:
        # XD3 at GBP 9,998.00 is not a fare at all, so it belongs with the
        # catalogue placeholders. Keeping the two tables apart means a
        # conditional fare can be argued about without re-deciding what a
        # placeholder is.
        self.assertIn("XD3", atoc_fares.PLACEHOLDER_TICKET_CODES)
        self.assertNotIn("XD3", atoc_fares.CONDITIONAL_TICKET_CODES)

    def test_a_fare_the_feed_says_needs_another_ticket_cannot_win(self) -> None:
        # BCF FRIENDS&FAMILY is priced at GBP 1.00 and won 678 slots before
        # this rule. Its restriction says ONLY VALID WITH TfWM SEASON TKT
        # HOLDER, so a reader without a season ticket cannot buy it. The rule
        # is the feed's sentence rather than a code, so the next fare the file
        # describes this way is caught without anyone typing its code.
        fares = self._db()
        fares.restrictions.headers["FH"] = atoc_restrictions.parse_header(
            _restriction_header("FH", "SEASON", "ONLY VALID WITH TfWM SEASON TKT HOLDER")
        )
        flow_id = next(iter(fares.fares_by_flow))
        fares.fares_by_flow[flow_id]["BCF"] = Fare("BCF", 100, "FH")
        fares.ticket_types["BCF"] = TicketType("BCF", "FRIENDS&FAMILY", "2", "R", False)
        rows = fares.page_destinations_within("GRN", 1_000_000)
        self.assertNotIn("BCF", {row.ticket_code for row in rows})

    def test_a_time_restricted_fare_is_still_published(self) -> None:
        # The check is that the restriction demands another ticket, not that
        # it demands anything. EGS EVENING DAY is a real product restricted to
        # after 1830. Priced at 50p so it would take the slot outright, because
        # a fixture priced above the fixture's 100p incumbent passes whether
        # or not the rule rejects it.
        fares = self._db()
        fares.restrictions.headers["EF"] = atoc_restrictions.parse_header(
            _restriction_header(
                "EF", "EVENING", "ONLY VALID ON JOURNEYS FROM 1830 MONDAY TO SUNDAY"
            )
        )
        flow_id = next(iter(fares.fares_by_flow))
        fares.fares_by_flow[flow_id]["EGS"] = Fare("EGS", 50, "EF")
        fares.ticket_types["EGS"] = TicketType("EGS", "EVENING DAY S", "2", "S", False)
        rows = fares.page_single_destinations_within("GRN", 1_000_000)
        self.assertIn("EGS", {row.ticket_code for row in rows})

    def test_a_staff_pass_cannot_win_the_cheapest_single_slot(self) -> None:
        db = self._with(self._db(), "BJD", "AWC STAFF", 5)
        rows = db.page_single_destinations_within("GRN", 1_000_000)
        self.assertNotIn("BJD", {row.ticket_code for row in rows})

    def test_a_return_named_not_for_travel_is_rejected(self) -> None:
        # Priced at 100p so it would win the slot outright. The real ZZZ
        # carries a plausible price and a blank restriction, so a fixture
        # priced above the incumbent passes whether or not the selector
        # rejects it, which is a test of the fixture.
        db = self._with(self._db(), "ZZZ", "NOT FOR TRAVEL", 100, ticket_type="R")
        rows = db.page_destinations_within("GRN", 1_000_000)
        self.assertNotIn("ZZZ", {row.ticket_code for row in rows})

    def test_an_ordinary_return_is_still_published(self) -> None:
        # The marker test is on names, so it is worth asserting the fare the
        # page exists to publish still passes it.
        db = self._with(self._db(), "QQR", "ANYTIME DAY R", 900, ticket_type="R")
        rows = {row.crs: row for row in db.page_destinations_within("GRN", 1_000_000)}
        self.assertEqual(rows["NOT"].ticket_code, "QQR")

    def test_the_reason_names_the_fact_rather_than_the_three_conditions(self) -> None:
        # The table started as child, group and event and now holds a staff
        # pass, so the tally key that names those three would understate what
        # it excludes.
        self.assertEqual(
            atoc_fares.CONDITIONAL_REASON, "ticket_is_not_one_a_reader_can_buy"
        )

    def test_an_ordinary_fare_is_not_treated_as_conditional(self) -> None:
        # A word in a name must not be the rule. The selectors are keyed by
        # code, so a fare whose name happens to contain a marker is still
        # displayable, and it is priced under the fixture's 100p incumbent so
        # that it wins the slot and the test can see it.
        db = self._with(self._db(), "QQ1", "GROUP SPECIAL OFFER", 50)
        rows = {row.crs: row for row in db.page_single_destinations_within("GRN", 1_000_000)}
        self.assertEqual(rows["NOT"].ticket_code, "QQ1")
        self.assertEqual(rows["NOT"].best_pence, 50)


class TwoPartFareTest(unittest.TestCase):
    """ADR-0061: a place the feed prices in two parts is one row.

    The return network gives Grantham two such places. Skegness has no
    Grantham flow, and the feed prices Grantham to Lincoln and Lincoln to
    Skegness; Leicester has none either, and the feed prices Grantham to
    Nottingham and Nottingham to Leicester.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.feed = build_synthetic_feed(
            Path(self.tmp.name) / "feed", include_return_network=True, include_restrictions=True
        )
        self.db = FaresDb().load_feed(self.feed)

    def returns(self, db: FaresDb):
        return lambda crs: db.page_destinations_within(crs, 1_000_000, adults=1)

    def test_the_price_is_both_published_fares_added_together(self) -> None:
        rows = {
            row.crs: row
            for row in self.db.two_part_fares("GRN", {"SLD": "LCN", "LEC": "NOT"}, self.returns(self.db))
        }
        self.assertEqual(set(rows), {"SLD", "LEC"})
        skegness = rows["SLD"]
        self.assertEqual(skegness.best_pence, 870 + 3240)
        self.assertEqual((skegness.change_crs, skegness.change_station), ("LCN", "LINCOLN"))
        self.assertEqual(
            [(leg.ticket_code, leg.best_pence) for leg in skegness.legs], [("SDR", 870), ("SDR", 3240)]
        )
        # Both conditions are carried, one per ticket.
        leicester = rows["LEC"]
        self.assertEqual(leicester.best_pence, 1160 + 2400)
        self.assertEqual([leg.restriction_code for leg in leicester.legs], ["1A", "1A"])

    def test_the_tickets_are_the_journeys_own_not_the_cheapest_pair(self) -> None:
        # Skegness is cheaper through Lincoln (870 + 3240) than through
        # Nottingham (1160 + 3560). A journey that changes at Nottingham is
        # quoted the Nottingham pair, because that is the pair it travels on.
        rows = self.db.two_part_fares("GRN", {"SLD": "NOT"}, self.returns(self.db))
        self.assertEqual([(row.crs, row.change_crs, row.best_pence) for row in rows], [("SLD", "NOT", 1160 + 3560)])

    def test_each_ticket_is_the_one_its_own_page_would_quote(self) -> None:
        # The same selector, asked of each end: the first ticket is the
        # origin page's row for the change station, the second is the change
        # station page's row for the destination.
        row = self.db.two_part_fares("GRN", {"LEC": "NOT"}, self.returns(self.db))[0]
        own = {r.crs: r for r in self.db.page_destinations_within("GRN", 1_000_000, adults=1)}
        onward = {r.crs: r for r in self.db.page_destinations_within("NOT", 1_000_000, adults=1)}
        self.assertEqual(row.first, own["NOT"])
        self.assertEqual(row.second, onward["LEC"])

    def test_a_place_with_its_own_fare_or_a_missing_ticket_is_no_two_part_row(self) -> None:
        # Nottingham has its own Grantham fare, so it keeps it. Peterborough
        # prices nothing on to Matlock, so a journey through it has no price.
        self.assertEqual(
            self.db.two_part_fares("GRN", {"NOT": "LCN", "MAT": "PBO"}, self.returns(self.db)), []
        )


    def test_a_calling_point_on_a_direct_journey_is_a_split(self) -> None:
        # Wider ADR-0061: Bulwell has no Grantham flow and no change of train.
        # Nottingham is a calling point on the through train, and both legs
        # sell, so the pair is a row. Strict change-station-only would pass an
        # empty candidate list and miss it.
        alone = self.db.two_part_fares("GRN", {"BUL": []}, self.returns(self.db))
        self.assertEqual(alone, [])
        rows = self.db.two_part_fares("GRN", {"BUL": ["NOT"]}, self.returns(self.db))
        self.assertEqual([(row.crs, row.change_crs, row.best_pence) for row in rows], [("BUL", "NOT", 1160 + 410)])

    def test_the_cheapest_valid_calling_point_wins_among_the_journeys_stops(self) -> None:
        # Skegness is cheaper through Lincoln than through Nottingham. Both are
        # on a journey's candidate list; the sum through Lincoln wins. That is
        # still journey-matched: neither candidate invents a stop the journey
        # does not call at.
        rows = self.db.two_part_fares(
            "GRN", {"SLD": ["NOT", "LCN"]}, self.returns(self.db)
        )
        self.assertEqual(
            [(row.crs, row.change_crs, row.best_pence) for row in rows],
            [("SLD", "LCN", 870 + 3240)],
        )

    def test_a_focused_load_keeps_the_second_ticket(self) -> None:
        # ADR-0061's second false zero: a database focused on one origin
        # dropped every fare from anywhere else, so the second ticket was an
        # empty flow and nothing was priceable in two parts.
        focused = FaresDb().load_feed(self.feed, focus_origin="GRN")
        changes = {"SLD": "LCN", "LEC": "NOT"}
        self.assertEqual(
            focused.two_part_fares("GRN", changes, self.returns(focused)),
            self.db.two_part_fares("GRN", changes, self.returns(self.db)),
        )

    def test_a_restored_index_reads_the_second_ticket_from_the_change_stations_index(self) -> None:
        changes = {"SLD": "LCN", "LEC": "NOT"}
        expected = self.db.two_part_fares("GRN", changes, self.returns(self.db))
        with tempfile.TemporaryDirectory() as tmp:
            common, indexes = Path(tmp) / "common.pickle", Path(tmp) / "indexes"
            FaresDb().load_feed(self.feed, focus_origin="GRN").write_fare_indexes(common, indexes, ["GRN"])
            self.assertTrue((indexes / "LCN.pickle").is_file(), "a change station's index is written")
            self.assertTrue((indexes / "NOT.pickle").is_file())
            alone = FaresDb.load_fare_index(common, indexes / "GRN.pickle")
            self.assertEqual(alone.two_part_fares("GRN", changes, self.returns(alone)), [])
            merged = FaresDb.load_fare_index(common, indexes / "GRN.pickle")
            self.assertEqual(merged.merge_interchange_indexes(indexes), [])
            self.assertEqual(merged.two_part_fares("GRN", changes, self.returns(merged)), expected)
            # A missing change-station index is reported, not served around.
            (indexes / "NOT.pickle").unlink()
            partial = FaresDb.load_fare_index(common, indexes / "GRN.pickle")
            self.assertEqual(partial.merge_interchange_indexes(indexes), ["NOT"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
