"""Tests for the demo page generator."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock
from datetime import date
import contextlib
import io
from pathlib import Path

import build_demo_page
import run
from build_demo_page import DEFAULT_PRICE_SOURCE, NOTICES, notices_or_attribution
import argparse
from atoc_fares import LOCATION, FLOW_F, FLOW_T, TICKET_TYPE, FaresDb
from atoc_timetable import TimetableDb
from build_demo_page import (
    build_payload,
    build_station_index,
    explain_unpriced,
    render_chooser,
    render_page,
    render_privacy,
    station_slug,
)
from make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_timetable
from destination_coverage import UnsourcedReport
from parse_report import ParseReport
from retailer import DISCLOSURE


def embedded_payload(html: str) -> dict:
    match = re.search(r"const DATA = (\{.*?\});\n", html, re.DOTALL)
    if match is None:
        raise AssertionError("the page carries no embedded payload")
    return json.loads(match.group(1))


def station_page(out: Path) -> Path:
    """The station page a single-origin build wrote beside its chooser.

    A single-origin build is a site: --out names the root index.html, which is
    the chooser, and the one station page is written to its canonical
    /from/<slug>/ route (S01, S04). Tests that want the station's own content
    read it from here rather than from the root.
    """
    pages = sorted((out.parent / "from").glob("*/index.html"))
    if len(pages) != 1:
        raise AssertionError(f"expected exactly one station page under {out.parent / 'from'}, got {pages}")
    return pages[0]


# Every build writes a parsed-fares cache named by the feed's content, so a
# suite that built in the repository's own cache directory would leave one
# pair of files per fixture behind, and would read whichever pair an earlier
# run happened to leave -- which is how a test that should have parsed the
# feed ends up passing on a cache it did not write. The tests that care where
# the cache lives patch the directory themselves.
_CACHE_DIR_PATCH: mock._patch | None = None


def setUpModule() -> None:
    global _CACHE_DIR_PATCH
    _CACHE_DIR_PATCH = mock.patch.object(
        build_demo_page, "CACHE_DIR", Path(tempfile.mkdtemp(prefix="page-cache-"))
    )
    _CACHE_DIR_PATCH.start()


def tearDownModule() -> None:
    if _CACHE_DIR_PATCH is not None:
        cache = build_demo_page.CACHE_DIR
        _CACHE_DIR_PATCH.stop()
        shutil.rmtree(cache, ignore_errors=True)


class DemoPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fares = FaresDb().load_feed(
            build_synthetic_feed(
                Path(cls._tmp.name) / "fares",
                include_unserved_station=True,
                include_restrictions=True,
            )
        )
        cls.timetable = TimetableDb().load_feed(build_synthetic_timetable(Path(cls._tmp.name) / "timetable"))
        cls.payload = build_payload(cls.fares, cls.timetable, "GRN")
        cls.html = render_page(cls.payload, budget_pounds=20)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_address_carries_the_search_and_the_tab_title_follows_it(self) -> None:
        # S05: the URL is the search, so a refresh, a shared link and Back all
        # land on the decision already made rather than the build's default.
        self.assertIn("function stateQuery()", self.html)
        self.assertIn("function readState()", self.html)
        self.assertIn("function applyState(state)", self.html)
        self.assertIn('window.addEventListener("popstate"', self.html)
        # Every control that changes the result writes it, and the budget is
        # the one that does so while it is being dragged.
        self.assertIn("budget.addEventListener(\"input\", () => { setBudget(budget.value); currentPage = 1; render(); writeUrl({ budget: true }); })", self.html)
        self.assertIn("railcard.addEventListener(\"change\", () => { currentPage = 1; render(); writeUrl(); })", self.html)
        self.assertIn("'input[name=\"ticketMode\"]')) radio.addEventListener(\"change\", () => { currentPage = 1; render(); writeUrl(); })", self.html)
        # The title is the heading's sentence, so a reader with two tabs open
        # can tell the two searches apart.
        self.assertIn('document.title = "Where can we go from " + DATA.origin.name + " for up to £" + budgetNumber.value + "?";', self.html)

    def test_the_chooser_says_what_its_order_is_and_is_not(self) -> None:
        # S10: a cold-start order that does not name its measure reads as a
        # recommendation, and priced-destination count is not popularity.
        index = build_demo_page.build_station_index({"GRN": 5, "NOT": 2}, self.fares.locations_by_crs)
        chooser = build_demo_page.render_chooser(index, budget_pounds=20)
        self.assertIn("Ordered by how many destinations", chooser)
        self.assertIn("not by how busy it is", chooser)

    def test_both_station_lists_accept_a_code_fragment(self) -> None:
        # S11: a code fragment finds its station, and the same matcher serves
        # the chooser and the picker so the two cannot answer differently.
        for page in (self.html, build_demo_page.render_chooser([], budget_pounds=20)):
            for fragment in (
                "station.name.toLowerCase().includes(needle)",
                "station.crs.toLowerCase().startsWith(needle)",
            ):
                self.assertIn(fragment, page)
        # No alias table: an unreviewed "Grantham = Grantham Stn" is exactly
        # the plausible-looking invention this project refuses to publish.
        self.assertNotIn("aliases", self.html)

    def test_the_station_page_says_which_control_changes_station(self) -> None:
        # S12: the navigation-versus-filter distinction, said once, where it is
        # true.
        self.assertIn('id="firstUse"', self.html)
        self.assertIn("<b>Change</b>", self.html)

    def test_a_picker_option_carries_the_readers_search(self) -> None:
        # S06: changing origin corrects where they leave from, not the search
        # they have already made, and the picker writes the same query the
        # address does rather than a second, drifting copy of it.
        self.assertIn('link.href = station.href + "?" + stateQuery();', self.html)

    def test_payload_records_the_source_fingerprint_used_to_build_the_page(self) -> None:
        self.assertRegex(self.payload["sourceFingerprint"], r"^[0-9a-f]{16}$")
        self.assertIn("sourceFingerprint", self.html)

    def test_the_page_carries_every_priced_destination_not_just_the_cheap_ones(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(sorted(rows), ["KGX", "LCN", "NOT", "PBO", "SLP"])

    def test_every_destination_carries_both_prices_and_a_journey(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        # The page now includes the cheapest standard return found in the feed,
        # even when it is restricted. The browser budget filter does the final
        # selection; the synthetic fixture's cheaper CDR is therefore visible.
        self.assertEqual(rows["NOT"]["adultPence"], 1160)
        self.assertEqual(rows["NOT"]["railcardPence"], 770)
        self.assertEqual(rows["NOT"]["partyPence"], 2320)
        self.assertEqual(rows["NOT"]["minutes"], 45)
        self.assertEqual(rows["NOT"]["changes"], 0)

    def test_single_mode_keeps_and_labels_the_cheaper_advance_ticket(self) -> None:
        row = next(row for row in self.payload["singleDestinations"] if row["crs"] == "NOT")
        self.assertEqual(row["adultPence"], 100)
        self.assertEqual(row["ticket"], "2AS")
        self.assertTrue(row["isAdvance"])
        self.assertIn("Advance single", self.html)

    def test_a_heritage_destination_carries_its_named_unesco_property(self) -> None:
        row = next(row for row in self.payload["destinations"] if row["crs"] == "SLP")
        self.assertEqual(
            row["heritageSites"],
            [{
                "id": 488,
                "name": "Tower of London",
                "url": "https://whc.unesco.org/en/list/488/",
            }],
        )
        self.assertIn("World heritage: ", self.html)
        self.assertIn("destination.heritageSites", self.html)

    def test_expired_flows_are_absent_from_all_ticket_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
            fares._load_flows(
                _line(
                    {
                        "update_marker": "R",
                        "record_type": "F",
                        "origin_nlc": "1000",
                        "destination_nlc": "2000",
                        "route_code": "00000",
                        "flow_id": "0000001",
                        "start_date": "01012020",
                        "end_date": "31122020",
                    },
                    FLOW_F,
                )
            )
            payload = build_payload(
                fares, None, "GRN", day=date(2026, 9, 24)
            )

        for mode in ("destinations", "singleDestinations", "anytimeDestinations"):
            self.assertNotIn("NOT", {row["crs"] for row in payload[mode]})

    def test_the_page_carries_separate_ticket_modes(self) -> None:
        self.assertEqual(self.payload["destinations"][0]["destinationType"], "city")
        self.assertEqual(
            self.payload["destinations"][0]["destinationTypes"],
            ["city", "seaside", "university"],
        )
        self.assertIn('name="destinationType" value="city"', self.html)
        self.assertIn('name="destinationType" value="seaside"', self.html)
        self.assertIn('name="destinationType" value="university"', self.html)
        self.assertIn("Coastal &amp; seaside", self.html)
        self.assertIn("University towns", self.html)
        self.assertNotIn('<select id="q"', self.html)
        self.assertIn("selectedDestinationTypes", self.html)
        self.assertIn("singleDestinations", self.payload)
        self.assertTrue(self.payload["singleDestinations"])
        self.assertIn("anytimeDestinations", self.payload)
        self.assertTrue(self.payload["anytimeDestinations"])
        self.assertIn('name="ticketMode"', self.html)
        self.assertIn('value="single"', self.html)
        self.assertIn('value="anytime"', self.html)
        self.assertIn("activeDestinations", self.html)
        self.assertIn("unrestricted Anytime Day Return", self.html)
        self.assertIn("no qualifying", self.html)
        self.assertIn("PAGE_SIZE = 20", self.html)
        self.assertIn('id="pagination"', self.html)


    def test_the_cheapest_destination_is_listed_first(self) -> None:
        prices = [row["adultPence"] for row in self.payload["destinations"]]
        self.assertEqual(prices, sorted(prices))

    def test_a_fare_with_no_service_still_reaches_the_page(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["SLP"]["adultPence"], 1200)
        self.assertIsNone(rows["SLP"]["minutes"])
        self.assertEqual(rows["SLP"]["legs"], [])

    # -- the licence wording and the measurement hook ----------------------

    def test_no_attribution_by_default_and_no_stray_placeholder(self) -> None:
        # Nothing claims a licence term that has not been read, and the slot the
        # wording goes in is present but empty rather than missing.
        self.assertIsNone(self.payload["attribution"])
        self.assertIn('<div id="attribution" hidden></div>', self.html)
        self.assertNotIn("__ANALYTICS__", self.html)

    def test_the_licence_wording_reaches_the_page_and_its_own_script(self) -> None:
        wording = "Contains data licensed from Rail Delivery Group."
        payload = build_payload(self.fares, self.timetable, "GRN", attribution=wording)
        self.assertEqual(payload["attribution"], wording)
        html = render_page(payload, budget_pounds=20)
        self.assertIn(wording, html)
        # Present in the payload is not the same as shown, so the page has to
        # unhide it too.
        self.assertIn("DATA.attribution", html)

    # -- where the numbers came from, and what they promise ------------------

    def test_the_provenance_line_sits_with_the_prices_by_default(self) -> None:
        # A synthetic build says its prices are synthetic, beside the prices,
        # not in a footer the reader has already left.
        self.assertEqual(self.payload["priceSource"], DEFAULT_PRICE_SOURCE)
        self.assertIn('id="priceSource" hidden', self.html)
        self.assertIn("DATA.priceSource", self.html)

    def test_each_destination_carries_its_fare_restriction_status(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["NOT"]["restrictionCode"], "1A")
        # C08: the description is now the feed's own wording for the code
        # rather than a placeholder, so it is judged against that.
        self.assertEqual(rows["NOT"]["restrictionDescription"], "NOT VALID AT WEEKENDS")
        self.assertEqual(rows["SLP"]["restrictionCode"], "")
        self.assertIn("restrictionCode", self.html)
        self.assertIn("restrictionDescription", self.html)
        self.assertIn('(destination.restrictionDescription || "This fare carries a restriction code', self.html)
        self.assertIn('add("Restriction", destination.restrictionCode || "none")', self.html)
        self.assertIn("ITX placeholder fares", self.html)

    def test_a_restricted_row_carries_the_validity_the_feed_states(self) -> None:
        # C08: the condition a reader is being asked to rule a fare in or out
        # by is only useful if it says what it permits. The feed's own outward
        # and return text reaches the page, once per code rather than once per
        # row, so a page of 1,678 rows does not repeat the same two sentences
        # 1,678 times.
        validity = self.payload["restrictionValidity"]
        self.assertEqual(
            validity["1A"],
            {
                "outwardText": "NOT VALID FOR TRAVEL ON SATURDAY OR SUNDAY",
                "returnText": "RETURN NOT VALID FOR TRAVEL ON SATURDAY OR SUNDAY",
            },
        )
        # A code the feed has no header for is absent rather than empty, so the
        # page can tell "nothing to show" from "show nothing".
        self.assertNotIn("", validity)
        self.assertIn("DATA.restrictionValidity", self.html)
        self.assertIn("Valid outward: ", self.html)
        self.assertIn("Valid on the return: ", self.html)
        # A single is one way, so a return condition beside it would state a
        # limit on a leg the ticket does not have.
        self.assertIn('const single = destination.quality === "outbound single";', self.html)
        self.assertIn("if (!single && validity.returnText)", self.html)

    def test_a_restriction_the_feed_cannot_describe_says_so_plainly(self) -> None:
        # C08: "confirm the conditions before buying" reads as if the page had
        # decoded a rule and left the reader a task. What it has is a code and
        # no wording, and that is what the page says.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(
                Path(tmp) / "fares", include_restrictions=True
            )
            fares = FaresDb().load_feed(feed)
            fares.restrictions.headers.pop("1A", None)
            payload = build_payload(fares, None, "GRN")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(rows["NOT"]["restrictionCode"], "1A")
        self.assertIn("does not describe", rows["NOT"]["restrictionDescription"])
        # Nothing to show is the honest outcome, and the map says so by
        # leaving the code out rather than by carrying an empty pair.
        self.assertNotIn("1A", payload["restrictionValidity"])

    def test_a_railcard_is_a_constraint_on_the_party_not_a_discount(self) -> None:
        # S15: the cheapest number on screen has to be a fare the party could
        # buy, so the box is disabled for a party of one and the sentence beside
        # it says why, in the feed's own terms rather than this project's.
        # The name is the feed's own, truncated by its fixed-width field; the
        # party size is what the page's sentence is built from.
        self.assertEqual(self.payload["railcardParty"]["minAdults"], 2)
        self.assertEqual(self.payload["railcardParty"]["maxAdults"], 2)
        self.assertIn("function syncRailcardParty()", self.html)
        self.assertIn('railcard.disabled = !applies;', self.html)
        self.assertIn("if (!applies && railcard.checked) railcard.checked = false;", self.html)
        self.assertIn('"The railcard in this feed covers " + party.minAdults', self.html)
        # A card=1 that arrives on a link must not tick a box the party of one
        # cannot use.
        self.assertIn("railcard.checked = state.railcard && unit() === \"party\";", self.html)

    def test_a_row_states_its_condition_and_folds_the_feed_record_away(self) -> None:
        # S19: the condition a reader can act on sits beside the price; the
        # ticket, restriction and route codes are one disclosure away.
        self.assertIn("function feedRecord(destination)", self.html)
        self.assertIn('readable.className = "condition"', self.html)
        self.assertIn("No travel conditions on this fare in the feed.", self.html)
        row = next(row for row in self.payload["destinations"] if row["crs"] == "NOT")
        self.assertEqual(row["routeCode"], "00000")
        self.assertEqual(row["restrictionCode"], "1A")

    def test_a_missing_journey_is_typed_rather_than_a_dash(self) -> None:
        # S23: three different absences, three different sentences.
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["NOT"]["journeyState"], "found")
        self.assertEqual(rows["SLP"]["journeyState"], "no service in this timetable")
        self.assertIn('missing ? "No service" : duration(destination.minutes)', self.html)
        self.assertIn('missing ? "Unknown" : String(destination.changes)', self.html)
        prices_only = build_payload(self.fares, None, "GRN")
        self.assertEqual(
            next(row for row in prices_only["destinations"] if row["crs"] == "LCN")["journeyState"],
            "no timetable in this build",
        )
        dated = build_payload(self.fares, self.timetable, "GRN", day=date(2026, 9, 28))
        self.assertEqual(
            next(row for row in dated["destinations"] if row["crs"] == "SLP")["journeyState"],
            "no service on 2026-09-28",
        )

    def test_the_page_counts_what_it_could_not_classify(self) -> None:
        # S29: an unreviewed destination is still listed, so the count of the
        # ones no chip can select is the difference between "every type" and
        # "every type we have reviewed".
        self.assertEqual(self.payload["unclassifiedDestinationCount"], 0)
        self.assertTrue(self.payload["locationTypeReviewed"])
        self.assertIn("function classifiedNote()", self.html)
        self.assertIn("carry no reviewed", self.html)
        self.assertIn("Every destination on this page carries a reviewed type.", self.html)
        # And the count is a count: a destination with no reviewed type is
        # counted rather than quietly filtered away.
        fares = FaresDb().load_feed(
            build_synthetic_feed(
                Path(self._tmp.name) / "unreviewed",
                include_restrictions=True,
            )
        )
        # A download with no reviewed classification at all: every destination
        # is still priced and still listed, and every one of them is a row no
        # type chip can select.
        fares.location_types_by_crs = {}
        fares.location_facets_by_crs = {}
        fares.location_type_sources = []
        payload = build_payload(fares, self.timetable, "GRN")
        self.assertEqual(payload["unclassifiedDestinationCount"], len(payload["destinations"]))
        self.assertFalse(payload["locationTypeReviewed"])

    def test_an_empty_list_offers_the_moves_that_would_fill_it(self) -> None:
        # S28: advice a reader cannot act on is a dead end, so each move is a
        # control and each is offered only when it is true for this page.
        self.assertIn("function renderEmpty(available, wanted, cap, what)", self.html)
        self.assertIn("function renderEmptyMode()", self.html)
        self.assertIn('button.className = "toggle"', self.html)
        self.assertIn('offer("Show everything up to " + money(enough * 100)', self.html)
        self.assertIn('offer("Clear the destination type", clearDestinationTypes)', self.html)
        self.assertIn('offer(label + " has " + modeCount(mode)', self.html)

    def test_the_facets_count_what_they_would_show_and_can_be_cleared(self) -> None:
        # S20: a count on the chip, the union stated, and a way back to All.
        self.assertIn('class="chipcount"', self.html)
        self.assertIn("function updateChipCounts(available, cap)", self.html)
        self.assertIn("function clearDestinationTypes()", self.html)
        self.assertIn('id="clearTypes"', self.html)
        self.assertIn("More than one type shows destinations of any of them", self.html)
        self.assertIn('return labels.length > 1 ? " in " + labels.join(" or ")', self.html)

    def test_a_narrowed_search_returns_to_the_first_page(self) -> None:
        # S22: the cheapest rows are what a narrowed search wants first, and the
        # page position is re-announced with the count.
        for control in (
            "budget.addEventListener",
            "budgetNumber.addEventListener",
            "railcard.addEventListener",
            "previousPage",
            "nextPage",
        ):
            self.assertIn(control, self.html)
        self.assertIn("currentPage = 1; render(); writeUrl();", self.html)
        self.assertIn('"Page " + currentPage + " of " + pageCount + " of " + wanted.length', self.html)

    def test_the_page_states_how_old_its_numbers_are(self) -> None:
        # S33: the age of the prices and the window of the times, beside the
        # numbers, judged against the reader's clock rather than the build's.
        self.assertIn("function renderFreshness()", self.html)
        self.assertIn('id="freshness"', self.html)
        self.assertEqual(self.payload["staleAfterDays"], build_demo_page.STALE_AFTER_DAYS)
        self.assertEqual(self.payload["timetableFrom"], "2026-09-21")
        self.assertEqual(self.payload["timetableTo"], "2026-12-11")
        # A build with no timetable says so, and that is a choice rather than a
        # feed that has gone stale.
        prices_only = build_payload(self.fares, None, "GRN")
        self.assertIsNone(prices_only["timetableFrom"])
        self.assertIn("This build prices fares only", self.html)
        self.assertIn("which has ended, so these times describe services that no longer run", self.html)

    def test_the_feed_date_is_the_downloads_own_and_never_a_timetables(self) -> None:
        # The date has to describe the fares: a newer timetable download must
        # not make the prices look fresh.
        self.assertEqual(
            build_demo_page.feed_date_from({"downloaded": "2026-09-20T09:15:00Z"}),
            "2026-09-20",
        )
        manifest = {
            "downloads": [
                {"source": "dtd", "name": "fares", "downloaded_at": "2026-09-18T06:00:00Z"},
                {"source": "dtd", "name": "timetable", "downloaded_at": "2026-09-25T06:00:00Z"},
            ]
        }
        self.assertEqual(build_demo_page.feed_date_from(None, manifest), "2026-09-18")
        # A timetable-only manifest still dates something honestly rather than
        # claiming the prices came from a download that never carried them.
        self.assertEqual(
            build_demo_page.feed_date_from(None, {"downloads": [manifest["downloads"][1]]}),
            "2026-09-25",
        )
        self.assertIsNone(build_demo_page.feed_date_from(None, None))
        self.assertIsNone(build_demo_page.feed_date_from({"downloaded": "soon"}, None))

    def test_a_cif_date_becomes_an_iso_date_and_a_non_date_does_not(self) -> None:
        # The feed states its window in six digits; the page measures it in
        # calendar dates, and a value that is not a date is not guessed at.
        self.assertEqual(build_demo_page.cif_date_to_iso("260921"), "2026-09-21")
        for value in ("", "2609", "2609211", "26-09-21", "abcdef"):
            self.assertIsNone(build_demo_page.cif_date_to_iso(value), value)

    def test_the_timetable_reports_its_own_service_window(self) -> None:
        # Read from the feed's own records, so the page and the audit cannot
        # disagree about the window they print.
        self.assertEqual(self.timetable.service_window(), ("260921", "261211"))
        self.assertEqual(TimetableDb().service_window(), ("", ""))
        self.assertEqual(
            TimetableDb().load_feed(build_synthetic_timetable(Path(self._tmp.name) / "again")).service_window(),
            ("260921", "261211"),
        )
        # Asked for by every station page in a full-network build, so it is
        # answered from the database once rather than by rescanning the feed --
        # and the answer is still right if the database grows afterwards.
        again = TimetableDb().load_feed(build_synthetic_timetable(Path(self._tmp.name) / "again"))
        first = again.service_window()
        self.assertIs(again.service_window(), first, "the window is not memoised")
        again.schedules.append(
            type(again.schedules[0])(**{**vars(again.schedules[0]), "date_from": "260101", "date_to": "270101"})
        )
        self.assertEqual(again.service_window(), ("260101", "270101"))

    def test_the_privacy_page_describes_the_build_that_was_made(self) -> None:
        # S36: the notice is generated from the same feature configuration the
        # pages are built from, so it cannot describe a different site.
        plain = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network=None, disclosure=None
        )
        measured = build_demo_page.site_features(
            analytics=True, link_mode="fallback", network=None, disclosure="analytics snippet"
        )
        tracked = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network="affiliate-x", disclosure="Tracked"
        )
        quiet = build_demo_page.render_privacy("note", "/base", "a@b.test", plain)
        self.assertIn("No analytics run", quiet)
        self.assertNotIn("__PRACTICES__", quiet)
        self.assertIn("injects an analytics snippet", build_demo_page.render_privacy("note", "", "a@b.test", measured))
        self.assertIn(
            "affiliate network",
            build_demo_page.render_privacy("note", "", "a@b.test", tracked),
        )
        # The contact is required whatever the features are, and the base path
        # still prefixes the way back.
        with self.assertRaises(ValueError):
            build_demo_page.render_privacy("note", "", "   ", plain)
        self.assertIn('href="/base/"', quiet)

    def test_a_public_build_cannot_publish_an_incomplete_notice(self) -> None:
        # S36, S37: fail closed. Each gap is named, because a refusal an
        # operator cannot act on is a refusal they will work around.
        features = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network=None, disclosure=None
        )
        self.assertEqual(
            build_demo_page.release_gate_problems(features, public=False, notices=None, contact="a@b.test"),
            [],
        )
        self.assertEqual(
            build_demo_page.privacy_gaps(features, "  "),
            [
                "no privacy contact is configured, so nobody can be told about a problem "
                "with this site (set PRIVACY_CONTACT or pass --privacy-contact)"
            ],
        )
        tracked = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network="affiliate-x", disclosure=None
        )
        self.assertIn(
            "no disclosure is set",
            " ".join(build_demo_page.privacy_gaps(tracked, "a@b.test")),
        )
        # A deep link is not tracking: it hands the seller the search the
        # reader was reading and the page says so. Only the network tracks.
        deep = build_demo_page.site_features(
            analytics=False, link_mode="deep", network=None, disclosure=None
        )
        self.assertEqual(build_demo_page.privacy_gaps(deep, "a@b.test"), [])
        # Measurement without a plan is a gap, and a plan closes it.
        self.assertIn(
            "no measurement plan is recorded",
            " ".join(
                build_demo_page.privacy_gaps(
                    build_demo_page.site_features(
                        analytics=True, link_mode="fallback", network=None, disclosure=None
                    ),
                    "a@b.test",
                )
            ),
        )
        self.assertEqual(
            build_demo_page.privacy_gaps(
                build_demo_page.site_features(
                    analytics=True,
                    link_mode="fallback",
                    network=None,
                    disclosure=None,
                    measurement="aggregate-referrer-counts",
                ),
                "a@b.test",
            ),
            [],
        )
        # A public build without a licence notice is refused; a synthetic one is
        # exempt because it publishes no real fares.
        self.assertEqual(
            [
                problem
                for problem in build_demo_page.release_gate_problems(
                    features, public=True, notices=None, contact="a@b.test"
                )
                if "licence" in problem
            ],
            [
                "a public build carries no licence or attribution notice; pass --notices "
                "(or --attribution) so the obligations travel with the site"
            ],
        )
        self.assertEqual(
            build_demo_page.release_gate_problems(
                features, public=True, notices=["a notice"], contact="a@b.test"
            ),
            [],
        )

    def test_analytics_needs_a_written_measurement_plan(self) -> None:
        # S38: the flag cannot be reached without naming a plan, and the plans
        # are written out rather than implied.
        self.assertIn("aggregate-referrer-counts", build_demo_page.MEASUREMENT_PLANS)
        self.assertIn("no persistent identifier", build_demo_page.MEASUREMENT_PLANS["aggregate-referrer-counts"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            snippet = root / "snippet.js"
            snippet.write_text("window.x = 1;", encoding="utf-8")
            out = root / "site" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = build_demo_page.main(
                    ["--feed", str(feed), "--out", str(out), "--analytics-snippet", str(snippet)]
                )
            self.assertEqual(code, 2)
            self.assertIn("--measurement-plan", buffer.getvalue())
            # With a plan named, the same build proceeds.
            with contextlib.redirect_stdout(io.StringIO()):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--out", str(out),
                        "--analytics-snippet", str(snippet),
                        "--measurement-plan", "aggregate-referrer-counts",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("injects an analytics snippet", (root / "site" / "privacy" / "index.html").read_text(encoding="utf-8"))

    def test_a_real_source_build_is_refused_until_it_carries_a_notice(self) -> None:
        # S37: a build that names a real price source publishes real fares, so
        # the licence notice and somebody to contact are conditions of the
        # build rather than a step in a checklist. Both are named in the
        # refusal, because a refusal nobody can act on is one they route
        # around.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            out = root / "site" / "index.html"
            refused = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(refused):
                code = build_demo_page.main(
                    ["--feed", str(feed), "--out", str(out), "--price-source", "the RSP feed"]
                )
            self.assertEqual(code, 2)
            self.assertFalse(out.exists(), "a refused build writes no page")
            # The project now carries its own contact, so the notice is the
            # condition this build trips. The contact condition is still real
            # and is driven by a deliberately blank one below.
            self.assertIn("carries no licence or attribution notice", refused.getvalue())
            self.assertNotIn("no privacy contact is configured", refused.getvalue())
            # A contact that is configured but blank is refused, so the gate is
            # not satisfied by the mere existence of a default: a build that
            # sets an empty contact on purpose stops.
            with mock.patch.dict(os.environ, {"PRIVACY_CONTACT": "   "}, clear=False):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(refused):
                    code = build_demo_page.main(
                        [
                            "--feed", str(feed),
                            "--out", str(out),
                            "--price-source", "the RSP feed",
                            "--notices", "rdg,ogl,accuracy",
                        ]
                    )
            self.assertEqual(code, 2)
            self.assertIn("no privacy contact is configured", refused.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--out", str(out),
                        "--price-source", "the RSP feed",
                        "--notices", "rdg,ogl,accuracy",
                        "--privacy-contact", "privacy@b.test",
                    ]
                )
            self.assertEqual(code, 0)
            privacy = (root / "site" / "privacy" / "index.html").read_text(encoding="utf-8")
            self.assertIn("privacy@b.test", privacy)

    def test_a_real_build_names_the_project_contact_without_being_asked(self) -> None:
        # The contact is a fact about the project, not a deployment setting, so
        # a real build has one without an operator having to supply it. Without
        # this the gate fires on every local real-feed build, and a gate that
        # fires constantly is a gate people route around.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            out = root / "site" / "index.html"
            with contextlib.redirect_stdout(io.StringIO()):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--out", str(out),
                        "--price-source", "the RSP feed",
                        "--notices", "rdg,ogl,accuracy",
                    ]
                )
            self.assertEqual(code, 0)
            privacy = (root / "site" / "privacy" / "index.html").read_text(encoding="utf-8")
            self.assertIn(build_demo_page.PROJECT_PRIVACY_CONTACT, privacy)

    def test_the_project_contact_is_flagged_for_review_before_publication(self) -> None:
        # An address chosen for a local build is not the same thing as an
        # address confirmed for a public service. The review has to be written
        # down where the person who publishes will read it, or it is not a
        # review -- it is a comment.
        self.assertIn("@", build_demo_page.PROJECT_PRIVACY_CONTACT)
        root_dir = Path(__file__).parent.parent
        source = (root_dir / "build_demo_page.py").read_text(encoding="utf-8")
        self.assertIn("REVIEW BEFORE GOING LIVE", source)
        checklist = (root_dir / "docs" / "publish-checklist.md").read_text(encoding="utf-8")
        self.assertIn(build_demo_page.PROJECT_PRIVACY_CONTACT, checklist)
        # And it is an open box, not a ticked one: the point is that it has not
        # been confirmed yet. Matched on the box's own line, because a wrapped
        # list item puts the address on the next one.
        box = [
            line
            for line in checklist.splitlines()
            if "privacy contact is confirmed" in line
        ]
        self.assertEqual(len(box), 1, f"expected one review box, found {box}")
        self.assertTrue(box[0].startswith("- [ ] "), box[0])

    def test_a_shortlist_is_a_list_of_places_and_not_a_booking(self) -> None:
        # S26: the decision the page exists for is which place, so a reader can
        # keep a few, compare them on the price currently shown, and hand the
        # list to somebody else as a link. Nothing about it implies a booking.
        self.assertIn('id="shortlistHeading">Shortlist', self.html)
        self.assertIn("not a booking: no train is chosen and no ticket is held", self.html)
        self.assertIn('save.className = "toggle shortlist-toggle"', self.html)
        self.assertIn('save.setAttribute("aria-pressed", "false")', self.html)
        # It is part of the address, one readable key per place.
        self.assertIn('for (const code of shortlistCodes) params.append("short", code);', self.html)
        self.assertIn('short: params.getAll("short")', self.html)
        self.assertIn("A shortlist of places, not a booking", self.html)
        # The comparison is of the price on screen, and it is rebuilt whenever
        # the party or the mode changes what that price is.
        self.assertIn("function shortlistText()", self.html)
        self.assertIn("money(priceOf(destination))", self.html)
        self.assertIn("renderShortlist();\n}", self.html)
        # A station this page cannot price never enters the list, whatever a
        # shared link claims.
        self.assertIn("shortlistCodes = state.short.filter(pricedHere);", self.html)
        # The limit is said, not silently applied.
        self.assertIn('setShortlistStatus("The shortlist holds " + SHORTLIST_LIMIT + " places.', self.html)
        self.assertIn('save.setAttribute("aria-label", "Shortlist " + destination.name);', self.html)

    def test_railcard_pricing_is_available_from_the_feed(self) -> None:
        # R9 is the railcard's travel condition, not a total ban, so the
        # synthetic fares that carry it remain eligible.
        self.assertTrue(self.payload["railcardInFeed"])
        self.assertTrue(self.payload["railcardAvailable"])
        self.assertEqual(self.payload["railcardEligibleCount"], 3)
        self.assertIn("Two Together is in this feed", self.payload["railcardNote"])
        self.assertIn("restriction codes are retained as travel conditions", self.payload["railcardNote"])
        self.assertIn("DATA.railcardNote", self.html)
        self.assertIn("Math.min(base, cardTotal)", self.html)

    def test_the_page_evaluates_a_railcard_for_each_selected_fare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
            fares.restrictions.railcard_rows.clear()
            fares.minimum_fares.clear()
            payload = build_payload(fares, None, "GRN")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(rows["NOT"]["railcardPence"], 770)
        self.assertTrue(payload["railcardAvailable"])
        self.assertTrue(payload["railcardInFeed"])
        self.assertEqual(payload["railcardEligibleCount"], 4)
        self.assertIn("one-third discount", payload["railcardNote"])

    def test_each_destination_exposes_its_exact_railcard_decision(self) -> None:
        row = next(row for row in self.payload["destinations"] if row["crs"] == "NOT")
        details = row["railcard"]
        self.assertEqual(details["state"], "eligible")
        rule = self.payload["railcardRules"][details["rule"]]
        self.assertIn("any ticket", rule["text"])
        self.assertIn("RR", rule["text"])
        self.assertEqual(rule["restrictionCode"], "R9")
        self.assertFalse(rule["totalBan"])
        self.assertEqual(details["pricePence"], 770)
        self.assertEqual(
            details["minimumFarePence"],
            self.fares.minimum_fares.get(("TWO", row["ticket"])),
        )
        self.assertIn("travel condition rather than a card ban", details["reason"])
        self.assertIn('id="railcardDrawer"', self.html)
        self.assertIn("showRailcardDetails(destination)", self.html)
        self.assertIn("DATA.railcardRules[details.rule]", self.html)
        self.assertIn("Exact DTD rule", self.html)

    def test_rule_records_are_hoisted_out_of_the_rows(self) -> None:
        rows = [
            row
            for key in ("destinations", "singleDestinations", "anytimeDestinations")
            for row in self.payload[key]
        ]
        self.assertTrue(rows)
        for row in rows:
            rule = row["railcard"]["rule"]
            self.assertIsInstance(rule, str, "rows hold a key, never the record")
            self.assertIn(rule, self.payload["railcardRules"])
        rules = self.payload["railcardRules"]
        self.assertTrue(rules, "a page with rows publishes the shared records")

    def test_unavailable_railcard_hides_its_own_help(self) -> None:
        payload = dict(
            self.payload,
            railcardAvailable=False,
            railcardEligibleCount=0,
        )
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn('help.textContent = ""', script)
        self.assertIn("help.hidden = true", script)
        self.assertIn("railcardChoice.hidden = true", script)
        self.assertNotIn("no displayed fare is currently eligible", html)

    def test_the_notice_presets_compose_into_separate_paragraphs(self) -> None:
        # Three distinct obligations, three paragraphs: one run-on would let a
        # reader miss the one that disclaims the numbers.
        args = argparse.Namespace(notices="rdg,ogl,accuracy", attribution=None)
        notices = notices_or_attribution(args)
        self.assertEqual(len(notices), 3)
        self.assertIn("Rail Delivery Group", notices[0])
        self.assertIn("Open Government Licence v3.0", notices[1])
        self.assertIn("as is", notices[2])
        self.assertIn("liability", notices[2])

    def test_an_unknown_notice_name_is_refused_not_dropped(self) -> None:
        args = argparse.Namespace(notices="rdg,madeup", attribution=None)
        with self.assertRaises(SystemExit):
            notices_or_attribution(args)

    def test_notices_win_over_attribution_and_say_so(self) -> None:
        args = argparse.Namespace(notices="rdg", attribution="custom wording")
        self.assertEqual(notices_or_attribution(args), [NOTICES["rdg"]])

    # -- the prices-only page: what a reader sees without a timetable ---------

    def test_a_prices_only_table_stands_its_empty_columns_down(self) -> None:
        # Two columns of dashes on every row is noise; when no timetable is
        # loaded the Time and Changes columns do not exist at all.
        payload = build_payload(self.fares, None, "GRN")
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("if (!DATA.hasJourneys)", script)
        self.assertIn("nth-child(3), thead th:nth-child(4)", script)
        # The detail rows must span whatever the table actually has.
        self.assertIn("cell.colSpan = columnCount()", script)
        # And the footer still says what the page is missing.
        self.assertIn("no timetable loaded", html)

    def test_a_page_with_times_keeps_all_six_columns(self) -> None:
        script = self.html.split("<script>")[1].split("</script>")[0]
        self.assertIn("const columnCount", script)
        self.assertIn("duration(destination.minutes)", script)

    # -- feed metadata: provenance recorded once, read by every build ---------

    def test_metadata_beside_the_feed_supplies_the_price_source(self) -> None:
        # The download records where it came from once; every build after that
        # reads it instead of the operator retyping it.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares")
            (Path(feed) / "metadata.json").write_text(
                json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
                encoding="utf-8",
            )
            metadata = build_demo_page.read_feed_metadata([Path(feed)])
        self.assertEqual(
            build_demo_page.price_source_from_metadata(metadata),
            "the RSP fares feed, downloaded 3 October 2026",
        )

    def test_a_source_without_a_download_date_still_speaks(self) -> None:
        self.assertEqual(
            build_demo_page.price_source_from_metadata({"source": "RSP fares feed"}),
            "the RSP fares feed",
        )

    def test_no_metadata_keeps_the_synthetic_default(self) -> None:
        self.assertEqual(build_demo_page.price_source_from_metadata({}), None)
        self.assertEqual(
            build_demo_page.price_source_from_metadata({"downloaded": "3 October 2026"}),
            None,
        )

    def test_a_real_download_without_metadata_reads_the_downloader_manifest(self) -> None:
        # dtd_download.py writes download-manifest.json even when nobody
        # hand-writes a metadata.json. A real download must never fall back to
        # the synthetic default just because nobody typed a note.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            (Path(tmp) / "download-manifest.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "downloads": [
                            {
                                "name": "fares",
                                "source": "dtd",
                                "downloaded_at": "2026-09-23T14:02:11Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = Path(tmp) / "site" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--out", str(out),
                        "--notices", "accuracy",
                        "--privacy-contact", "a@b.test",
                    ]
                )
            self.assertEqual(code, 0)
            page = station_page(out).read_text(encoding="utf-8")
            self.assertIn("the National Rail Data Portal DTD fares feed", page)
            self.assertIn("downloaded 23 September 2026", page)
            self.assertNotIn("Synthetic demo data", page)
            self.assertIn("price line read from the download manifest", buffer.getvalue())

    def test_a_zip_feed_reads_the_manifest_above_its_own_folder(self) -> None:
        # The real layout: feeds/fares/dtd-fares.zip with the downloader's
        # manifest at feeds/. Looking only at the zip's folder and its parent
        # missed it, and the build fell through to "the synthetic demo feed" for
        # real DTD prices.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "feeds"
            source = build_synthetic_feed(root / "fares", include_restrictions=True)
            archive = root / "fares" / "dtd-fares.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                for item in sorted(Path(source).iterdir()):
                    zipped.write(item, arcname=item.name)
            (root / "download-manifest.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "downloads": [
                            {"name": "fares", "source": "dtd", "downloaded_at": "2026-09-24T09:47:35Z"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = Path(tmp) / "site" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    [
                        "--feed", str(archive),
                        "--out", str(out),
                        "--notices", "accuracy",
                        "--privacy-contact", "a@b.test",
                    ]
                )
            self.assertEqual(code, 0)
            page = station_page(out).read_text(encoding="utf-8")
            self.assertIn("the National Rail Data Portal DTD fares feed", page)
            self.assertNotIn("the synthetic demo feed", page)

    def test_a_dtd_download_is_recognised_and_never_called_synthetic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "feeds"
            root.mkdir(parents=True)
            dtd = root / "dtd-fares.zip"
            with zipfile.ZipFile(dtd, "w") as zipped:
                zipped.writestr("RJFAF896.TTY", "not read by this test")
            self.assertTrue(build_demo_page.is_dtd_download(dtd))
            synthetic = root / "synthetic.zip"
            with zipfile.ZipFile(synthetic, "w") as zipped:
                zipped.writestr("SYNTHETIC.TTY", "invented")
            self.assertFalse(build_demo_page.is_dtd_download(synthetic))
            # A manifest above the feed is the other way a download is known.
            (root / "download-manifest.json").write_text("{}", encoding="utf-8")
            self.assertTrue(build_demo_page.is_dtd_download(synthetic))
            self.assertFalse(build_demo_page.is_dtd_download(Path(tmp) / "nowhere"))

    def test_the_manifest_prefers_fares_for_the_price_line(self) -> None:
        self.assertEqual(
            build_demo_page.price_source_from_manifest(
                {
                    "downloads": [
                        {"name": "fares", "source": "dtd", "downloaded_at": "2026-09-23T14:02:11Z"},
                        {"name": "timetable", "source": "dtd", "downloaded_at": "2026-09-24T03:00:00Z"},
                    ]
                }
            ),
            "the National Rail Data Portal DTD fares feed, downloaded 23 September 2026",
        )
        # A knowledgebase entry is reference data, not what the page is built
        # from, so it cannot supply the price line.
        self.assertIsNone(
            build_demo_page.price_source_from_manifest(
                {"downloads": [{"name": "stations", "source": "knowledgebase", "downloaded_at": "2026-09-24T03:00:00Z"}]}
            )
        )

    def test_a_manifest_alone_does_not_rescue_a_broken_metadata_note(self) -> None:
        # metadata.json present but names no 'source' -> still a refusal. The
        # manifest is a fallback for an absent note, not a way around one that
        # its operator left unfinished.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            (feed / "metadata.json").write_text(
                json.dumps({"downloaded": "3 October 2026"}), encoding="utf-8"
            )
            (Path(tmp) / "download-manifest.json").write_text(
                json.dumps(
                    {"downloads": [{"name": "fares", "source": "dtd", "downloaded_at": "2026-09-23T14:02:11Z"}]}
                ),
                encoding="utf-8",
            )
            out = Path(tmp) / "site" / "index.html"
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
            self.assertEqual(code, 2)
            self.assertFalse(out.exists())
            self.assertIn("names no 'source'", stderr.getvalue())

    def test_unreadable_metadata_is_named_not_silent(self) -> None:
        # Provenance that silently fell back to the default is provenance the
        # operator believes is real, so a broken file says so.
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "metadata.json"
            broken.write_text("{not json", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                metadata = build_demo_page.read_feed_metadata([broken.parent])
        self.assertEqual(metadata, {})
        self.assertIn("unreadable", stderr.getvalue())

    # -- base path: internal links on a host that is not the domain root ------

    def test_base_path_prefixes_every_internal_link(self) -> None:
        # GitHub Pages project sites and most shared hosting serve the site
        # below the domain root; root-absolute links 404 there.
        payload = build_payload(self.fares, self.timetable, "GRN", base_path="/tb")
        hrefs = {station["href"] for station in payload["stations"]}
        self.assertTrue(all(href.startswith("/tb/from/") for href in hrefs), hrefs)
        self.assertEqual(payload["baseHref"], "/tb/")
        html = render_page(payload, budget_pounds=20)
        self.assertIn('/tb/privacy/', html)

    def test_no_base_path_leaves_links_root_absolute(self) -> None:
        payload = build_payload(self.fares, self.timetable, "GRN")
        self.assertEqual(payload["baseHref"], "/")
        self.assertIn('href="/privacy/"', render_page(payload, budget_pounds=20))

    def test_the_analytics_snippet_is_injected_only_when_given(self) -> None:
        snippet = "<script>window.seen=1;</script>"
        self.assertNotIn("window.seen", self.html)
        html = render_page(self.payload, budget_pounds=20, analytics=snippet)
        self.assertIn(snippet, html)
        self.assertNotIn("__ANALYTICS__", html)

    def test_the_default_link_is_the_sellers_own_search_page(self) -> None:
        # ADR-0018: no seller's parameterised link is known to land on a search,
        # so the page does not walk readers into a "no journeys" page.
        urls = {row["link"]["url"] for row in self.payload["destinations"]}
        self.assertEqual(urls, {"https://www.nationalrail.co.uk/journey-planner/"})

    def test_a_fallback_page_states_what_the_reader_has_to_fill_in(self) -> None:
        # The cost of the fallback is on the page, not left for the reader to
        # discover on somebody else's site.
        self.assertIn("enter the origin", self.payload["linkNote"])
        self.assertIn("same whichever seller", self.payload["linkNote"])
        # One element carrying the id, and it is the one the script writes to:
        # two would leave getElementById and the reader looking at different
        # paragraphs.
        self.assertIn('id="linkNote" hidden', self.html)
        self.assertEqual(self.html.count('id="linkNote"'), 1)
        self.assertIn("DATA.linkNote", self.html)

    def test_the_seller_handoff_and_commission_are_above_the_click(self) -> None:
        # C03: both were inside the closed "How these prices were calculated"
        # disclosure, so a reader had to click a ticket link to find out what
        # the click cost. They are above the table now, and the accordion
        # carries neither.
        self.assertIn('id="linkNote" hidden', self.html)
        self.assertIn('id="disclosure" hidden', self.html)
        _before, after = self.html.split('<details class="method">', 1)
        inside = after.split("</details>", 1)[0]
        for note in ('id="linkNote"', 'id="disclosure"'):
            self.assertIn(note, self.html, f"{note} is not on the page")
            self.assertNotIn(note, inside, f"{note} is inside the accordion")
        # Above the table, which is what "before the first ticket action" means
        # in a document: a reader scrolling the rows has already passed it.
        self.assertLess(self.html.index('id="linkNote"'), self.html.index("<table>"))
        self.assertLess(self.html.index('id="disclosure"'), self.html.index("<table>"))
        # And nothing in the body is left unhidden by default: both are
        # revealed by the build's own facts, not shipped as visible prose that
        # a deep-link build would then be contradicting.
        self.assertIn("linkNote.hidden = false", self.html)
        self.assertIn("disclosure.hidden = false", self.html)

    def test_a_tracked_page_puts_its_disclosure_where_the_click_is(self) -> None:
        payload = build_payload(
            self.fares,
            self.timetable,
            "GRN",
            network="partnerize",
            advertiser_id="123456",
        )
        self.assertTrue(payload["tracked"])
        html = render_page(payload, budget_pounds=20)
        self.assertIn(DISCLOSURE, html)
        self.assertLess(html.index('id="disclosure"'), html.index("<table>"))

    def test_the_opening_sentence_branches_on_whether_a_timetable_was_loaded(
        self,
    ) -> None:
        # C04: the shipped sentence promised a journey time and a change count
        # on a build that removes the columns that carry them. The sentence is
        # written from the payload's own fact now.
        self.assertIn("function renderIntro()", self.html)
        self.assertIn("if (!DATA.hasJourneys)", self.html)
        self.assertIn("no times or changes are shown", self.html)
        self.assertIn("fastest journey time and the number of changes", self.html)
        # The static text is the fares-only sentence, so a page that has not
        # run this script yet cannot be promising times it will not show.
        intro = re.search(
            r'<p class="sub" id="pageIntro">(.*?)</p>', self.html, re.S
        )
        self.assertIsNotNone(intro)
        self.assertNotIn("journey time", intro.group(1))

    def test_the_undated_schedule_caveat_sits_with_the_times(self) -> None:
        # C04: the warning that the times are typical rather than date-specific
        # was in the closed methodology accordion. A reader is not going to
        # open that before trusting a time, so it joins the freshness line
        # above the table.
        with_timetable_no_date = build_payload(self.fares, self.timetable, "GRN")
        self.assertIn("every schedule in the feed is read", with_timetable_no_date["dateNote"])
        dated = build_payload(
            self.fares, self.timetable, "GRN", day=date(2026, 9, 30)
        )
        self.assertIsNone(dated["dateNote"])
        # A prices-only build has no times for the caveat to qualify.
        self.assertIsNone(build_payload(self.fares, None, "GRN")["dateNote"])
        self.assertIn('note.id = "dateNote"', self.html)
        self.assertIn('note.textContent = DATA.dateNote', self.html)
        self.assertNotIn(
            'document.getElementById("railcardNote").after(note)', self.html
        )

    # -- the copy affordance that gives a row back its memory ---------------

    def test_every_row_offers_to_copy_its_journey_details(self) -> None:
        self.assertIn('copy.textContent = "Copy"', self.html)
        self.assertIn('copy.setAttribute("aria-label", "Copy the journey details for "', self.html)
        self.assertIn("copyJourney(row, destination, copy)", self.html)

    def test_the_copied_text_names_the_things_a_seller_asks_for(self) -> None:
        for label in ('"From: "', '"To: "', '"Date: "', '"Passengers: "'):
            self.assertIn(label, self.html)

    def test_the_copied_text_names_the_railcard_only_for_the_party_price(self) -> None:
        # The card is never sent anywhere; it is named as something to tick, and
        # only when the price on screen is the one that needs it.
        self.assertIn('const together = unit() === "party";', self.html)
        self.assertIn('if (together && DATA.railcardAvailable && destination.railcardPence !== null)', self.html)
        self.assertNotIn('if (together && DATA.railcardInFeed && destination.railcardPence !== null)', self.html)
        self.assertIn('Two Together discount is not sent to the seller', self.html)

    def test_the_copied_date_is_not_parsed_through_the_date_object(self) -> None:
        # new Date("2026-10-05") is UTC midnight and prints as the 4th for a
        # reader behind UTC. A copied date off by one is worse than no date.
        # The clock itself is a different question: reading today's date needs
        # no parsing, so a bare new Date() is fine and the ban is on the
        # argument form, which is the one that guesses a time zone.
        self.assertIn("function humanDate(iso)", self.html)
        self.assertNotIn('new Date("', self.html)
        self.assertNotIn("new Date(iso", self.html)

    def test_a_failed_copy_is_never_reported_as_a_copy(self) -> None:
        # Clipboard access is refused when the file is opened from disk, so the
        # failure path has to exist and must not claim the text was copied.
        self.assertIn("if (!navigator.clipboard || !navigator.clipboard.writeText) return manual();", self.html)
        self.assertIn("Could not copy automatically", self.html)
        self.assertIn('button.textContent = "Select below"', self.html)
        self.assertEqual(self.html.count('"Copied"'), 1)

    def test_the_copy_confirmation_is_announced_and_not_only_shown(self) -> None:
        self.assertIn('id="copyStatus" role="status"', self.html)
        self.assertIn("class=\"sr-only\"", self.html)

    def test_the_newlines_in_the_copy_are_escaped_for_the_browser(self) -> None:
        # A real newline inside a JavaScript string literal is a SyntaxError that
        # takes the whole page down, and a Python template will happily produce
        # one from "\n". These assert the backslash-n the browser must receive.
        # This bug shipped past every test in this file and was caught by
        # browser_test.cjs, which is the reason that file exists.
        self.assertIn('lines.join("\\n")', self.html)
        self.assertIn('text.split("\\n").join(". ")', self.html)
        self.assertNotIn('join("\n', self.html)

    def test_the_page_can_be_read_back_as_data(self) -> None:
        self.assertEqual(embedded_payload(self.html), self.payload)

    def test_the_page_names_the_origin_and_offers_a_slider_and_a_filter(self) -> None:
        self.assertIn("GRANTHAM", self.html)
        self.assertIn('id="budget"', self.html)
        self.assertIn('name="destinationType"', self.html)
        self.assertIn('id="destinationTypes"', self.html)
        self.assertIn('value="party"', self.html)
        # C21: the filter is `price <= cap`, so the wording that matches the
        # behaviour is "up to", not "under". An exactly-at-the-ceiling fare is
        # shown, and a page that says "under" while showing it is describing
        # itself. Asserted negatively so the word cannot creep back in.
        self.assertIn("Where can we go for up to", self.html)
        self.assertNotIn("Where can we go for under", self.html)
        # The other two places that name the cap. "Within" is not "under", but
        # it reads the same way beside a fare that lands exactly on the ceiling,
        # and a summary saying "3 destinations within £20" under a heading that
        # says "up to £20" is the same defect in different words.
        self.assertEqual(3, self.html.count('for up to " + money(cap)'),
                         "the cap is named the old way somewhere")
        self.assertNotIn('"No destinations within "', self.html)

    def test_every_price_renders_with_two_decimal_places(self) -> None:
        # £9 next to £8.70 is harder to scan down a column than £9.00 is.
        self.assertIn("(pence / 100).toFixed(2)", self.html)
        self.assertNotIn("replace(/\\.00$/", self.html)

    # -- the origin picker (ADR-0019) -------------------------------------

    def test_the_payload_carries_a_station_list_for_the_picker(self) -> None:
        codes = [s["crs"] for s in self.payload["stations"]]
        self.assertNotIn("GRN", codes)  # the page's own origin is not offered
        self.assertIn("KGX", codes)
        for station in self.payload["stations"]:
            self.assertEqual(sorted(station), ["crs", "href", "name"])
            self.assertTrue(station["href"].startswith("/from/"))

    # -- the layout: budget leads, the rest refines ------------------------

    def test_the_filter_bar_uses_horizontal_space_without_a_duplicate_budget_field(self) -> None:
        self.assertIn("grid-template-columns: minmax(16rem, 1.1fr) minmax(18rem, 1.3fr) minmax(17rem, 1fr)", self.html)
        self.assertIn('<section class="filter-bar"', self.html)
        self.assertIn('id="budget" type="range"', self.html)
        self.assertIn('id="budgetNumber" type="number"', self.html.split("<h1", 1)[1].split("</h1>", 1)[0])
        self.assertNotIn('id="budgetNumber" type="number"', self.html.split('<section class="filter-bar"', 1)[1])

    def test_every_route_inlines_the_same_shared_stylesheet(self) -> None:
        # S39: the palette, spacing, focus ring, links, navigation and
        # disclosure styles have one source, inlined into each file at import
        # time so the site still ships no external asset. A route's own block
        # holds only what is its own, and a template that still held the
        # placeholder would raise rather than ship unstyled text.
        from page_templates import CHOOSER_TEMPLATE, PRIVACY, SHARED_CSS, TEMPLATE

        for name, template in (
            ("chooser", CHOOSER_TEMPLATE),
            ("station", TEMPLATE),
            ("privacy", PRIVACY),
        ):
            self.assertIn(SHARED_CSS, template, f"{name} does not carry the shared stylesheet")
            self.assertNotIn("__SHARED_CSS__", template, f"{name} shipped the placeholder")
        # One palette, one focus ring, one footer -- each stated once in the
        # source, and present in all three rendered routes.
        # C14: --warn is defined in both schemes, which is the whole point --
        # a token only the light block sets is a token the dark palette never
        # redefines, and that was the defect.
        self.assertIn("--warn: #9a6700;", SHARED_CSS)
        self.assertIn("--warn: #f0b35b;", SHARED_CSS)
        self.assertEqual(SHARED_CSS.count(":root {"), 2, "a token block and its dark counterpart")
        self.assertIn(":focus-visible { outline: 2px solid var(--accent); outline-offset: 2px;", SHARED_CSS)
        chooser = build_demo_page.render_chooser([], budget_pounds=60)
        privacy = build_demo_page.render_privacy(
            "note", "", "a@b.test", build_demo_page.site_features(
                analytics=False, link_mode="fallback", network=None, disclosure=None
            )
        )
        for name, page in (("chooser", chooser), ("station", self.html), ("privacy", privacy)):
            self.assertIn("--accent: #14509b;", page, f"{name} lost the shared palette")
            self.assertIn("prefers-color-scheme: dark", page, f"{name} lost the dark palette")
            # C25: the shared block holds the 44px minimum on the anchor, not
            # only on a container around it, so the privacy page's single
            # navigation link is a 44px target rather than a 24px one that
            # happened to be 24px because of its line box.
            self.assertIn(
                ".footnav a, .back-link a { display: inline-flex; align-items: center; min-height: 44px; color: inherit; }",
                page,
                f"{name} restated the footer nav",
            )
        # The chooser and the station page state their width or heading size as
        # a token, rather than restating the rule the shared block sets.
        self.assertIn(":root { --h1: 1.5rem; }", chooser)
        self.assertIn("--page-max: 78rem", self.html)

    def test_accessibility_is_a_route_matrix_and_not_one_happy_path(self) -> None:
        # S41: the AA commitment was evidenced from one station page. The
        # browser suite now runs a matrix on every route it is pointed at --
        # chooser, station page, privacy page -- in both colour schemes, at
        # desktop, phone and 200% zoom, and this asserts the matrix is wired
        # into that path rather than left in a function nobody calls.
        suite = (Path(__file__).resolve().parent / "browser_test.cjs").read_text(encoding="utf-8")
        for wanted in (
            "async function checkAccessibilityMatrix(",
            "await checkAccessibilityMatrix(page, url, check, kind);",
            # Both schemes, and the scheme has to land or the dark pass is the
            # light pass wearing another name.
            'for (const scheme of ["light", "dark"])',
            "page.emulateMedia({ colorScheme: scheme })",
            # A 320px viewport is what 200% zoom leaves of a 640px screen.
            "width: 320",
            # Computed names, contrast off the rendered pixels, measured targets
            # and a focus indicator: the four things a claim of AA rests on.
            ".ariaSnapshot()",
            "every kind of text meets AA contrast",
            "every pointer target is at least 24px",
            "the controls promised at 44px are at least 44px",
            "the focused control shows where it is",
            "nothing scrolls sideways",
            "at 320px the text is still the base size",
        ):
            self.assertIn(wanted, suite, f"the matrix lost: {wanted}")
        # The privacy page is a route, not a path this suite cannot read.
        self.assertIn('return "privacy";', suite)
        self.assertIn("routes in the accessibility matrix", suite)
        # The two page defects the matrix found are fixed in the page itself,
        # so the numbers above are the ones the suite measures.
        self.assertIn("--muted: #a7b2c0", self.html)
        self.assertIn(".synthetic-banner strong { color: color-mix(in srgb, var(--ochre) 80%, var(--fg)); }", self.html)
        self.assertIn(".feed-record summary { display: inline-flex; align-items: center; min-height: 24px;", self.html)

    def test_a_phone_keeps_the_budget_and_folds_the_refinements(self) -> None:
        # S42: the phone reflows around the journey rather than around the
        # table. The budget stays open, the refinements travel as one
        # disclosure that says what is currently narrowed, and the summary is
        # rewritten on every state change so it cannot describe a filter the
        # reader has since cleared.
        self.assertIn('<div class="more-filters" id="moreFilters" data-open="false">', self.html)
        self.assertIn('id="moreFiltersToggle"', self.html)
        self.assertIn('aria-controls="moreFiltersPanel"', self.html)
        self.assertIn('id="moreFiltersPanel"', self.html)
        self.assertIn("Narrow this list", self.html)
        # The three refinements are inside the panel; the budget is not.
        bar = self.html.split('<section class="filter-bar"', 1)[1].split("</section>", 1)[0]
        budget, folded = bar.split('<div class="more-filters"', 1)
        self.assertIn('id="budget" type="range"', budget)
        self.assertIn("more-filters-panel", folded)
        for group in ("ticket-filter", "party-filter", "destination-filter"):
            self.assertIn(group, folded, f"{group} is outside the disclosure")
        # Above the phone breakpoint the block is not a disclosure at all: the
        # toggle is not rendered and the panel is displayed, so a missed resize
        # event cannot leave a reader with controls they can neither see nor
        # open. Below it, the panel is displayed only while data-open says so.
        self.assertIn(".more-filters, .more-filters-panel { display: contents; }", self.html)
        self.assertIn(".more-filters-toggle { display: none; }", self.html)
        self.assertIn(".more-filters { display: block; }", self.html)
        self.assertIn("@media (max-width: 44rem) {", self.html)
        self.assertIn('.more-filters[data-open="true"] .more-filters-panel { display: grid;', self.html)
        self.assertIn('moreFilters.dataset.open = open ? "true" : "false";', self.html)
        self.assertIn('moreFiltersToggle.setAttribute("aria-expanded", open ? "true" : "false");', self.html)
        # The state is written from the page's own controls, on every render
        # and on the path that stands the whole panel down.
        self.assertIn("function filterStateText()", self.html)
        self.assertIn('window.matchMedia("(min-width: 44.01rem)")', self.html)
        self.assertIn("wideEnough.addEventListener(\"change\", followViewport)", self.html)
        self.assertIn('window.addEventListener("resize", followViewport)', self.html)
        self.assertIn("renderFilterState();", self.html)
        self.assertGreaterEqual(self.html.count("renderFilterState();"), 2)

    def test_the_budget_is_inline_in_the_large_heading(self) -> None:
        heading = self.html.split("<h1", 1)[1].split("</h1>", 1)[0]
        self.assertIn("Where can we go for up to", heading)
        self.assertIn('id="budgetNumber"', heading)
        self.assertIn('id="changeOrigin"', heading)
        self.assertIn("h1 { font-size: var(--h1);", self.html)
        self.assertIn("--h1: clamp(2rem, 5vw, 5rem)", self.html)
        self.assertIn(".sub { color: var(--muted); max-width: 75ch; }", self.html)
        self.assertNotIn("max-width: 32ch", self.html)
        self.assertNotIn("margin: -1rem 0 1.5rem", self.html)

    def test_result_changes_and_mobile_cells_are_accessible(self) -> None:
        self.assertIn('id="summary" role="status" aria-live="polite"', self.html)
        self.assertIn('cell.dataset.label = label', self.html)
        self.assertIn('restriction.dataset.label = "Conditions"', self.html)
        # C07: the conditions are printed in the next column of the same row, so
        # the label points there rather than sending the reader to a seller to
        # find out what the price they are comparing actually permits.
        self.assertIn("Restricted fare — conditions in the next column", self.html)

    def test_the_page_opens_in_the_reviewed_fare_set(self) -> None:
        # C07: PRODUCT.md promises reviewed unrestricted Anytime Day Returns, so
        # the set the page opens in is that one. The broad set stays available
        # and named, which is what the second assertion is about.
        checked = re.search(r'<input type="radio" name="ticketMode" value="(\w+)" checked>', self.html)
        self.assertIsNotNone(checked, "no ticket mode is checked in the markup")
        self.assertEqual("anytime", checked.group(1))
        self.assertIn("> Anytime Day Return</label>", self.html)
        self.assertIn("> Any return</label>", self.html)
        # Each mode says what its fares are, above the table rather than inside
        # the methodology accordion, so a reader meets the caveat at the moment
        # they compare two prices.
        for note in ("anytime:", "return:", "single:"):
            self.assertIn("  " + note, self.html)
        self.assertIn('id="modeNote"', self.html)
        self.assertIn("renderModeNote();", self.html)

    def test_row_actions_carry_a_44px_touch_target(self) -> None:
        # The visible mark stays small; the hit area reaches 44px via ::after.
        self.assertIn('.toggle::after { content: ""; position: absolute; inset: -6px; }', self.html)
        self.assertIn('.buy::after { content: ""; position: absolute; inset: -11px -4px; }', self.html)

    # -- the unpriced-origin page ------------------------------------------

    def test_the_hidden_attribute_beats_every_display_rule(self) -> None:
        # The controls grid, the picker, and the footer slots all set display;
        # without this rule, hiding them does nothing and an unpriced page
        # shows a slider that cannot help. Regression: the Sleepy page shipped
        # with the controls still on screen under the unpriced message.
        self.assertIn("[hidden] { display: none !important; }", self.html)

    def test_an_unpriced_origin_gets_its_own_first_sentence(self) -> None:
        # All three modes, not just the two the test used to empty: an unpriced
        # page is one that priced nothing in any ticket mode, and leaving the
        # Anytime list populated described a page this is not.
        payload = dict(
            self.payload, destinations=[], singleDestinations=[], anytimeDestinations=[]
        )
        html = render_page(payload, budget_pounds=20)
        self.assertIn('id="unpriced"', html)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("We couldn't price any journeys from", script)
        # The way forward is the chooser, as a real link, and it honours the
        # site's base path like every other internal link.
        self.assertIn("link.href = DATA.baseHref", script)
        self.assertIn("Start from a station we do price", script)
        # The controls cannot help an origin with no prices, so they stand down.
        self.assertIn("if (controls) controls.hidden = true", script)
        # Nor can the table or the budget's empty message: nothing was priced,
        # so "raise the budget" would be advice about a question nobody asked.
        self.assertIn('for (const id of ["empty", "more"])', script)
        self.assertIn('if (table) table.hidden = true;', script)
        self.assertIn('if (summary) summary.hidden = true;', script)
        # render() runs after provenance() and would un-hide the budget's empty
        # message; on an unpriced page it must not write anything at all. The
        # test is for a mode with nothing in it, not a page with nothing in it.
        render = script.split("function render(")[1].split("\nfunction ")[0]
        self.assertIn(
            "if (!DATA.destinations.length && !DATA.singleDestinations.length "
            "&& !DATA.anytimeDestinations.length) {",
            render,
        )

    def test_an_unpriced_origin_with_no_stations_at_all_says_that(self) -> None:
        payload = dict(
            self.payload,
            destinations=[],
            singleDestinations=[],
            anytimeDestinations=[],
            stations=[],
        )
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("Nothing was priced from any station", script)
        # No chooser exists, so no way-forward link is offered either.
        self.assertIn('if (DATA.stations && DATA.stations.length)', script)

    def test_the_empty_state_carries_the_payloads_note_after_the_intro(self) -> None:
        payload = dict(
            self.payload,
            destinations=[],
            singleDestinations=[],
            anytimeDestinations=[],
            unpricedNote="The feed reaches 2 destinations, cheapest fare an ITX placeholder.",
        )
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn('unpriced.append(intro + why + " ", link, ".");', script)
        self.assertIn('unpriced.textContent = intro + why + " Nothing was priced', script)
        self.assertEqual(embedded_payload(html)["unpricedNote"], payload["unpricedNote"])

    def test_slugs_are_readable_and_collision_free(self) -> None:
        taken: set[str] = set()
        first = station_slug("NOTTINGHAM", "NOT", taken)
        self.assertEqual(first, "nottingham")
        # A second station with the same name is disambiguated with its code.
        second = station_slug("NOTTINGHAM", "NMP", taken)
        self.assertEqual(second, "nottingham-nmp")
        self.assertNotEqual(first, second)

    def test_a_slug_never_collides_even_with_the_same_name_and_code(self) -> None:
        taken: set[str] = set()
        a = station_slug("X", "AAA", taken)
        b = station_slug("X", "AAA", taken)
        self.assertNotEqual(a, b)

    def test_the_page_offers_to_change_origin_and_navigates_by_link(self) -> None:
        self.assertIn('id="changeOrigin"', self.html)
        self.assertIn('id="originPicks"', self.html)
        # The options are real anchors, not a custom listbox.
        self.assertIn('link.href = station.href', self.html)
        self.assertIn('id="destinationTypes"', self.html.split("<script")[0])
        self.assertIn('name="destinationType" value="city"', self.html.split("<script")[0])
        self.assertIn('name="destinationType" value="seaside"', self.html.split("<script")[0])

    def test_a_destination_type_with_no_matches_gets_no_chip(self) -> None:
        # A chip that can only ever return nothing reads as a broken control,
        # so the page offers only the types its destinations actually carry.
        payload = dict(self.payload)
        payload["destinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["destinations"]
        ]
        for mode in ("singleDestinations", "anytimeDestinations"):
            payload[mode] = [
                dict(row, destinationTypes=["city"], destinationType="city")
                for row in self.payload.get(mode, [])
            ]
        html = render_page(payload, budget_pounds=50)
        head = html.split("<script>")[0]
        self.assertIn('name="destinationType" value="city"', head)
        self.assertNotIn('name="destinationType" value="seaside"', head)
        self.assertNotIn('name="destinationType" value="university"', head)
        self.assertNotIn('name="destinationType" value="island"', head)

    def test_a_type_only_the_singles_carry_still_reaches_the_page(self) -> None:
        # The build narrows chips by the union of the three modes, because it
        # does not know which mode a reader will pick. The page then narrows
        # them again per mode at render time, so a type only the singles carry
        # is still in the HTML and simply hidden on the returns list. If the
        # build decided this, switching to Singles would show a chip that
        # filters nothing.
        payload = dict(self.payload)
        payload["destinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["destinations"]
        ]
        payload["anytimeDestinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["anytimeDestinations"]
        ]
        payload["singleDestinations"] = [
            dict(row, destinationTypes=["city", "heritage"], destinationType="city")
            for row in self.payload["singleDestinations"]
        ]
        head = render_page(payload, budget_pounds=50).split("<script>")[0]
        self.assertIn('name="destinationType" value="heritage"', head)

    def test_the_chips_are_narrowed_for_the_mode_on_screen(self) -> None:
        # The narrowing reads the active list rather than all three, and runs
        # before the filter is asked what is checked: a chip the list cannot
        # support must not be part of what matchesType is matching.
        script = self.html.split("<script>")[1].split("</script>")[0]
        self.assertIn("function syncDestinationTypeChips()", script)
        sync = script.split("function syncDestinationTypeChips()")[1].split("\n}")[0]
        self.assertIn("activeDestinations()", sync)
        for other_mode in ("DATA.destinations", "singleDestinations", "anytimeDestinations"):
            self.assertNotIn(other_mode, sync)
        # A chip that goes away cannot stay ticked, or the filter would match a
        # type the reader can no longer see selected.
        self.assertIn("chip.hidden = !present", sync)
        self.assertIn("input.checked = false", sync)
        self.assertIn("all.checked = true", sync)
        render = script.split("function render(")[1].split("\nfunction ")[0]
        self.assertLess(
            render.index("syncDestinationTypeChips()"),
            render.index("selectedDestinationTypes()"),
        )

    def test_the_budget_ceiling_covers_the_party_price_too(self) -> None:
        # The ceiling is the most a reader can be asked to consider, and two
        # adults cost twice one. A ceiling set by the single fare is a budget
        # nobody reading the party price could type: on a page with one
        # destination -- Nottingham in the synthetic feed, and any station that
        # prices one place -- it caps the budget at that destination's adult
        # fare, and the "Two adults" control shows nothing at any budget the
        # page allows. Found by sweeping a published two-station site.
        script = self.html.split("<script>")[1].split("</script>")[0]
        ceiling = script.split("function budgetCeiling()")[1].split("\n}")[0]
        self.assertIn('unit() === "party"', ceiling)
        self.assertIn("d.partyPence : d.adultPence", ceiling)
        # The railcard is not in the ceiling: it lowers prices, so a ceiling
        # that moved when the box was ticked would clamp a budget the reader
        # had already chosen.
        self.assertNotIn("railcardPence", ceiling)

    def test_a_mode_with_no_fares_says_so_instead_of_going_blank(self) -> None:
        # An Anytime Day Return is sold on a handful of interurban routes, so
        # most real origins have none of them: Kings Cross prices 171 returns
        # and no Anytime fares at all. The page used to return from render()
        # before it wrote anything, so a reader who switched to that mode kept
        # the previous mode's rows under a set of destination chips that had
        # all just been hidden -- a filter that looks broken rather than a
        # mode that is empty. The mode now clears the table, says what
        # happened, and says where the fares this origin does have are.
        script = self.html.split("<script>")[1].split("</script>")[0]
        render = script.split("function render(")[1].split("\nfunction ")[0]
        self.assertNotIn("if (!available.length) return;", render)
        branch = render.split("if (!available.length) {")[1].split("\n  }")[0]
        self.assertIn("rows.replaceChildren()", branch)
        self.assertIn("empty.hidden = false", branch)
        self.assertIn("renderEmptyMode()", branch)
        self.assertIn("pagination.hidden = true", branch)
        # The budget is clamped after the branch, not before it: an empty list
        # has no prices to bound, and its £1 ceiling would otherwise reset the
        # reader's budget for every mode they switched back to.
        self.assertLess(
            render.index("if (!available.length) {"), render.index("setBudget(ceiling)")
        )
        # Silence is now reserved for the one case that already has a message:
        # a page that priced nothing at all, which provenance() explains.
        self.assertIn(
            "if (!DATA.destinations.length && !DATA.singleDestinations.length", render
        )
        # The wording names the mode by the label the reader can see, so it
        # cannot drift from the control, and counts the payload's own lists.
        message = script.split("function emptyModeMessage()")[1].split("\nfunction ")[0]
        self.assertIn("modeLabels()", message)
        self.assertIn("modeCount(", message)
        self.assertIn('"No " + labels[mode] + " fares were found from "', message)
        self.assertIn("MODE_WHY", message)
        # The Anytime mode says why that mode is usually the empty one, since
        # "none in this download" on its own reads like a broken build.
        self.assertIn("An Anytime Day Return is valid on any train", script)
        # One place names which list each mode shows, so a count quoted in a
        # message cannot come from a different list than the table is built
        # from.
        self.assertIn("const MODE_LISTS = {", script)

    def test_the_picker_closes_on_escape_and_returns_focus(self) -> None:
        self.assertIn('event.key === "Escape"', self.html)
        self.assertIn("changeOrigin.focus()", self.html)

    def test_table_headers_name_their_columns_and_scope(self) -> None:
        # "Ticket" and "Tickets" as adjacent headers read as one column twice,
        # and "Fare code" described a column that now reads in sentences, so
        # the headers name what the cells hold.
        self.assertIn('<th scope="col">Fare</th>', self.html)
        self.assertIn('<th scope="col">Conditions</th>', self.html)
        self.assertNotIn("<th>Ticket</th><th>Tickets</th>", self.html)
        self.assertEqual(self.html.count('<th scope="col"'), 7)

    def test_keyboard_focus_is_visible_everywhere(self) -> None:
        self.assertIn(":focus-visible { outline: 2px solid var(--accent); outline-offset: 2px;", self.html)

    def test_the_picker_hides_itself_when_there_is_nowhere_else_to_go(self) -> None:
        payload = dict(self.payload, stations=[])
        html = render_page(payload, budget_pounds=20)
        self.assertIn('DATA.stations && DATA.stations.length', html)

    def test_the_no_match_wording_names_what_was_tried(self) -> None:
        self.assertIn("We don't have prices from", self.html)
        self.assertIn("three-letter code", self.html)

    def test_the_embedded_script_parses_when_the_template_speaks_in_quotes(self) -> None:
        # The Python template is one big string, so a quote meant for the page
        # can terminate a JavaScript literal and take the whole page down. The
        # no-match wording quotes the reader's own input, so it is written with
        # single quotes inside double-quoted literals and must arrive intact.
        script = self.html.split("<script>")[1].split("</script>")[0]
        self.assertIn("We don't have prices from '", script)
        self.assertNotIn('from \\"', script)

    def test_privacy_requires_a_contact_and_uses_the_deployment_route(self) -> None:
        with self.assertRaises(ValueError):
            render_privacy("note")
        html = render_privacy("note", contact="privacy@example.test")
        self.assertIn("privacy@example.test", html)
        self.assertNotIn("goes here before the site is published", html)

    def test_the_chooser_budget_is_carried_into_station_links(self) -> None:
        chooser = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}],
            budget_pounds=20,
        )
        self.assertIn('id="chooserBudget"', chooser)
        self.assertIn('url.searchParams.set("budget"', chooser)
        self.assertIn('min-height: 44px', chooser)
        self.assertIn("Rail Budget", chooser)

    def test_the_chooser_explains_a_truncated_match_list(self) -> None:
        chooser = render_chooser([], budget_pounds=20)
        self.assertIn("Showing \" + CHOOSER_LIMIT + \" of \" + wanted.length", chooser)
        self.assertIn("Refine the search to see the rest", chooser)

    def test_the_chooser_counts_destinations_in_the_singular_when_there_is_one(self) -> None:
        # The chooser is read as a fact about the feed, and "1 destinations" is
        # the kind of slip that costs the page its credibility. The count is
        # rendered in the browser, so this asserts the emitted script.
        chooser = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}],
            budget_pounds=20,
        )
        self.assertIn('? " destination" : " destinations"', chooser)

    def test_an_unpriced_station_is_absent_from_the_index(self) -> None:
        # ADR-0019 decision 3: the picker must never offer a station that priced
        # nothing, because the reader is then sent to a page that cannot answer
        # them. Measured on the synthetic feed, five of seven stations price
        # nothing from themselves.
        locations = self.fares.locations_by_crs
        index = build_station_index(
            {"GRN": 5, "NOT": 1, "KGX": 0, "LCN": 0, "SLP": 0, "PBO": 0, "XFD": 0}, locations
        )
        self.assertEqual([entry["crs"] for entry in index], ["GRN", "NOT"])
        self.assertTrue(all(entry["destinations"] > 0 for entry in index))

    def test_the_chooser_is_the_index_and_carries_no_fares(self) -> None:
        index = [
            {"crs": "KGX", "name": "LONDON KINGS X", "slug": "london-kings-x", "destinations": 6},
            {"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 5},
        ]
        html = render_chooser(index, budget_pounds=20)
        self.assertIn("Pick the station you are starting from", html)
        self.assertNotIn("const DATA", html)  # no fares payload on the chooser
        self.assertIn("/from/nottingham/", html)
        self.assertIn('"destinations":6', html.replace(" ", ""))
        # The ranked count is the cold start, derived from the feed.
        self.assertLess(html.index("/from/london-kings-x/"), html.index("/from/nottingham/"))

    def test_the_chooser_carries_the_note_it_is_given(self) -> None:
        # A real-feed chooser must not sit above station pages claiming
        # synthetic data, so the note is a parameter rather than a constant.
        html = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 5}],
            budget_pounds=20,
            note="the RSP fares feed, downloaded 3 October 2026",
            synthetic=False,
        )
        self.assertIn("the RSP fares feed, downloaded 3 October 2026", html)
        self.assertNotIn("Synthetic demo data", html)
        self.assertIn("Synthetic demo data", render_chooser([], budget_pounds=20))

    def test_every_route_says_when_its_data_is_invented(self) -> None:
        # S45: an invented station or fare must not be mistakable for a real
        # one in a review, a demo or a shared screenshot, so every route states
        # the state above its content and carries it as a machine-readable
        # attribute a fixture can assert in either direction.
        index = [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 5}]
        routes = {
            "chooser": render_chooser(index, budget_pounds=20, synthetic=True),
            "privacy": render_privacy(
                "note", "", "a@b.test", synthetic=True
            ),
        }
        for name, page in routes.items():
            self.assertIn('<body data-synthetic="true">', page, f"{name} lost the state attribute")
            self.assertIn("data-synthetic-banner", page, f"{name} has no visible marker")
            self.assertIn(build_demo_page.SYNTHETIC_LABEL, page)
            # The marker is one of the shared components, not a route's own
            # idea of one (S39, S45).
            self.assertIn(".synthetic-banner {", page)
        for name, page in (
            ("chooser", render_chooser(index, budget_pounds=20, synthetic=False)),
            ("privacy", render_privacy("note", "", "a@b.test", synthetic=False)),
        ):
            self.assertIn('<body data-synthetic="false">', page, f"{name} lost the state attribute")
            self.assertNotIn("data-synthetic-banner", page, f"{name} claims invented data")
        # A real build's pages say so and a synthetic build's pages do too, from
        # the same build rather than from a flag per route.
        self.assertIn('<body data-synthetic="true">', self.html)
        self.assertIn("data-synthetic-banner", self.html)

    def test_a_zero_station_chooser_stands_the_search_down_and_says_so(self) -> None:
        html = render_chooser([], budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("if (!STATIONS.length) {", script)
        self.assertIn("Nothing is priced from any station in this build", script)
        # The no-match wording quotes typed input; it must never address an
        # empty field the reader has not touched.
        self.assertIn("} else if (needle) {", script)

    def test_the_mobile_reflow_keeps_the_markup_a_real_table(self) -> None:
        # The reflow is display-only CSS in a max-width media query. The markup
        # must stay a real table for desktop and assistive technology, and the
        # stylesheet must wrap cells rather than fix their width, so no cell can
        # sit outside the viewport however long a station name is.
        self.assertIn("@media (max-width: 44rem)", self.html)
        # From the first max-width block to the end of the stylesheet: the
        # footer nav has its own small block, and the table's rules must be
        # found wherever they sit.
        reflow = self.html[self.html.index("table, tbody { display: block; }") - 200:].split("</style>")[0]
        self.assertIn("flex-wrap", reflow)
        self.assertNotIn("display: none", reflow.split("thead")[0])
        self.assertIn("thead { position:absolute; width:1px; height:1px;", reflow)
        self.assertIn("td[data-label]::before { content: attr(data-label)", reflow)
        table_markup = self.html.split("<table>")[1].split("</table>")[0]
        self.assertNotIn("<div", table_markup)

    def test_the_slider_ceiling_covers_the_dearest_destination(self) -> None:
        ceiling = int(re.search(r'id="budget"[^>]*max="(\d+)"', self.html).group(1))
        dearest = max(row["adultPence"] for row in self.payload["destinations"])
        self.assertGreaterEqual(ceiling * 100, dearest)

    def test_a_script_tag_in_the_data_cannot_close_the_script_early(self) -> None:
        payload = dict(self.payload, note="a note with </script> in it")
        html = render_page(payload, budget_pounds=20)
        payload_region = html.split("const DATA = ")[1].split(";\nconst rows")[0]
        self.assertNotIn("</script>", payload_region)
        self.assertEqual(embedded_payload(html)["note"], "a note with </script> in it")

    # -- ticket links and the expander ------------------------------------

    def test_every_destination_carries_an_untracked_ticket_link(self) -> None:
        for row in self.payload["destinations"]:
            self.assertTrue(row["link"]["url"].startswith("https://www.nationalrail.co.uk/"))
            self.assertEqual(row["link"]["rel"], "noopener")
        self.assertFalse(self.payload["tracked"])
        self.assertIsNone(self.payload["disclosure"])

    def test_the_deep_link_points_at_the_destination_it_sits_beside(self) -> None:
        # Opt-in, because it depends on a URL that somebody has opened: ADR-0018.
        payload = build_payload(self.fares, self.timetable, "GRN", mode="deep")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertIn("origin=GRN", rows["NOT"]["link"]["url"])
        self.assertIn("destination=NOT", rows["NOT"]["link"]["url"])
        self.assertIsNone(payload["linkNote"])

    def test_a_tracked_page_discloses_itself(self) -> None:
        payload = build_payload(
            self.fares,
            self.timetable,
            "GRN",
            network="partnerize",
            advertiser_id="123456",
        )
        self.assertTrue(payload["tracked"])
        self.assertEqual(payload["disclosure"], DISCLOSURE)
        self.assertIn("nofollow", payload["destinations"][0]["link"]["rel"])
        self.assertIn(DISCLOSURE, render_page(payload, budget_pounds=20))
        self.assertTrue(
            all(x["link"]["rel"] == "noopener" for x in self.payload["destinations"]),
            "an untracked page must not claim otherwise",
        )

    def test_the_page_carries_the_journeys_behind_a_toggle_link(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(
            [option["depart"] for option in rows["NOT"]["departures"]],
            sorted(option["depart"] for option in rows["NOT"]["departures"]),
        )
        self.assertTrue(rows["NOT"]["departures"])
        self.assertEqual(rows["SLP"]["departures"], [])
        self.assertIn("toggleDetail", self.html)
        self.assertIn('link.className = "buy"', self.html)
        self.assertIn('link.textContent = "Tickets"', self.html)
        self.assertIn('link.target = "_blank"', self.html)

    def test_the_page_says_how_many_journeys_it_is_hiding(self) -> None:
        self.assertIn("destination.departures.length + \" times\"", self.html)

    def test_a_row_has_one_state_machine_for_the_region_underneath_it(self) -> None:
        # C28: the times list and the manual-copy box both insert the row that
        # follows the data row, and each used to remove whatever was there by
        # reaching for nextElementSibling. Copying while the times were open
        # left the times button still announcing "expanded" over content that
        # had gone, and the next click on it removed the copy box. One owner per
        # row, keyed weakly so a re-render's detached rows are collectable.
        script = self.html.split("<script>")[1].split("</script>")[0]
        self.assertNotIn("nextElementSibling", script.split("function toggleDetail")[1].split("\nfunction ")[0])
        self.assertNotIn("nextElementSibling", script.split("function showCopyBox")[1].split("\nfunction ")[0])
        for closer in ("function closeRegion", "function rowRegions"):
            self.assertIn(closer, script)
        self.assertIn("rowRegions.cache = new WeakMap();", script)
        # The two openings each close what is already in the slot, and the
        # control that owns a region is the control whose state is written back.
        opening_times = script.split("function toggleDetail")[1].split("\nfunction ")[0]
        self.assertIn('closeRegion(row, "copy");', opening_times)
        self.assertIn('toggle.setAttribute("aria-controls", detail.id);', opening_times)
        opening_copy = script.split("function showCopyBox")[1].split("\nfunction ")[0]
        self.assertIn('closeRegion(row, "times");', opening_copy)
        self.assertIn('closeRegion(row, "copy");', opening_copy)
        closer = script.split("function closeRegion")[1].split("\nfunction ")[0]
        self.assertIn('region.control.removeAttribute("aria-describedby")', closer)
        self.assertIn('region.control.setAttribute("aria-expanded", "false")', closer)
        self.assertIn("regions[kind] = null", closer)
        # C09: the copied journey has to say which ticket it is, or a handoff to
        # a seller can silently become a different one.
        journey = script.split("function journeyText")[1].split("\nfunction ")[0]
        self.assertIn('"Ticket: " + modeLabels()[ticketMode()],', journey)

    def test_the_departure_list_is_capped_and_configurable(self) -> None:
        payload = build_payload(self.fares, self.timetable, "GRN", departure_limit=2)
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(len(rows["NOT"]["departures"]), 2)

    def test_a_page_without_a_date_warns_that_a_changed_train_appears_twice(self) -> None:
        self.assertIn("has changed appears twice", self.payload["dateNote"])

    def test_a_page_with_a_date_does_not_need_that_warning(self) -> None:
        payload = build_payload(self.fares, self.timetable, "GRN", day=date(2026, 10, 5))
        self.assertIsNone(payload["dateNote"])
        self.assertEqual(payload["serviceDate"], "2026-10-05")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(len(rows["NOT"]["departures"]), 3)

    def test_the_page_titles_itself_with_the_budget(self) -> None:
        self.assertIn("&pound;20", self.html)

    def test_without_a_timetable_the_page_says_so(self) -> None:
        payload = build_payload(self.fares, None, "GRN")
        self.assertFalse(payload["hasJourneys"])
        self.assertTrue(all(row["minutes"] is None for row in payload["destinations"]))
        self.assertIn("no timetable loaded", render_page(payload, budget_pounds=20))


class ExplainUnpricedTest(unittest.TestCase):
    """The empty state's own sentence, in each shape it can take."""

    def test_a_placeholder_only_origin_names_the_count_and_the_codes(self) -> None:
        self.assertEqual(
            explain_unpriced(3, 3, ["EIF", "EIS"], {}),
            "The feed reaches 3 standard-return destinations, and the cheapest fare "
            "to every one of them is an ITX placeholder (EIF, EIS), which this page "
            "does not publish.",
        )

    def test_a_single_destination_is_written_in_the_singular(self) -> None:
        note = explain_unpriced(1, 1, ["EIS"], {})
        self.assertIn("reaches 1 standard-return destination, and its cheapest fare", note)

    def test_a_partly_withheld_origin_is_not_told_every_destination_is(self) -> None:
        # The placeholder sentence claims *every* destination is withheld, so
        # it is only said when every excluded row is. An origin priced half
        # into ITX and half into a zone boundary has one of each, and the
        # honest answer is the reason list rather than a false "all of them".
        note = explain_unpriced(
            2,
            1,
            ["EIS"],
            {"destination_is_a_fare_construction_point": 1},
        )
        self.assertIn(
            "none prices a publishable fare: 1 flows priced only to zone boundaries",
            note,
        )
        self.assertNotIn("ITX placeholder", note)

    def test_an_origin_priced_only_into_a_zone_says_that(self) -> None:
        note = explain_unpriced(
            1, 0, [], {"destination_is_a_fare_construction_point": 1}
        )
        self.assertIn("flows priced only to zone boundaries or coach stops", note)
        self.assertNotIn("ITX", note)

    def test_rejections_are_named_largest_first_and_capped(self) -> None:
        tally = {
            # Held-cheaper fares are normal traffic, never a reason a
            # destination is missing, so the 99 must not surface.
            "cheaper_index_already_held": 99,
            "ticket_is_not_a_standard_return": 9,
            "flow_expired": 5,
            "flow_with_no_fare": 2,
        }
        self.assertEqual(
            explain_unpriced(0, 0, [], tally),
            "The feed holds flows from this origin, but none prices a publishable fare: "
            "9 fares that are not standard returns; 5 flows past their last valid day; "
            "2 flows carrying no fare.",
        )

    def test_an_origin_the_feed_never_reaches_says_so(self) -> None:
        self.assertEqual(
            explain_unpriced(0, 0, [], {}), "The feed holds no fare from this origin at all."
        )


class UnpricedOriginNoteTest(unittest.TestCase):
    """The note the payload actually carries, built from a real query."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        feed = build_synthetic_feed(Path(cls._tmp.name) / "fares", include_restrictions=True)
        # PBO has no outbound flow in the base fixture. One flow priced only
        # with the ITX placeholder family gives it King's Cross's shape: the
        # feed reaches a destination and its cheapest fare is withheld.
        # KGX gets a CDR-only flow: displayable on the page's default mode,
        # invisible to the reviewed-anytime selector.
        with (feed / "rjfaf.ffl").open("a", encoding="utf-8") as handle:
            handle.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "4000",
                        "destination_nlc": "1000",
                        "route_code": "00000",
                        "flow_id": "0000008",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000008",
                        "ticket_code": "EIS",
                        "fare_pence": "5",
                        "restriction_code": "GA",
                    },
                    FLOW_T,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "5000",
                        "destination_nlc": "1000",
                        "route_code": "00000",
                        "flow_id": "0000009",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000009",
                        "ticket_code": "CDR",
                        "fare_pence": "1160",
                        "restriction_code": "1A",
                    },
                    FLOW_T,
                )
                + "\n"
            )
        with (feed / "rjfaf.tty").open("a", encoding="utf-8") as handle:
            handle.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "ticket_code": "EIS",
                        "description": "ADVANCE ITX R",
                        "tkt_class": "2",
                        "tkt_type": "R",
                        "restricted_by_train": "0",
                    },
                    TICKET_TYPE,
                )
                + "\n"
            )
        cls.fares = FaresDb().load_feed(feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_an_origin_with_no_flows_says_the_feed_holds_nothing(self) -> None:
        payload = build_payload(self.fares, None, "LCN")
        self.assertEqual(payload["rawFareDestinationCount"], 0)
        self.assertEqual(payload["unpricedNote"], "The feed holds no fare from this origin at all.")

    def test_an_origin_priced_only_by_a_non_reviewed_fare_still_counts(self) -> None:
        # CDR is a restricted off-peak return: the page's default mode shows
        # it, the reviewed-anytime selector cannot see it. Audit A1 is this
        # shape on the real feed -- King's Cross's 171 returns kept it out of
        # the chooser while its page answered just fine.
        self.assertEqual(
            build_demo_page._priced_destinations(self.fares, None, "KGX"),
            1,
        )
        self.assertEqual(
            self.fares.publishable_destinations_within(
                "KGX", build_demo_page.EVERYTHING_PENCE, adults=1
            ),
            [],
        )
        # And an ITX-only origin still counts as unpriceable: its page is the
        # empty state, which decision 3 keeps out of the index.
        self.assertEqual(
            build_demo_page._priced_destinations(self.fares, None, "PBO"), 0
        )

    def test_a_placeholder_only_origin_counts_destinations_and_names_the_codes(self) -> None:
        payload = build_payload(self.fares, None, "PBO")
        self.assertEqual(payload["destinations"], [])
        self.assertEqual(payload["singleDestinations"], [])
        self.assertEqual(payload["anytimeDestinations"], [])
        self.assertEqual(payload["rawFareDestinationCount"], 1)
        self.assertEqual(payload["excludedItxCodes"], ["EIS"])
        self.assertEqual(
            payload["unpricedNote"],
            "The feed reaches 1 standard-return destination, and its cheapest fare "
            "is an ITX placeholder (EIS), which this page does not publish.",
        )


class AllOriginsCliTest(unittest.TestCase):
    """The whole `--all-origins` run, because the output folder is the product.

    Every assertion here is something a reader or the operator can see: which
    pages exist, what the chooser lists, what the build says about a folder that
    still holds an earlier build, and how to open the result. The order of the
    writes matters, so this exercises the command rather than its pieces.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(
            root / "fares", include_unserved_station=True, include_restrictions=True
        )
        self.timetable = build_synthetic_timetable(root / "timetable")
        self.out = root / "site" / "index.html"

    def build(self) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--feed",
                    str(self.feed),
                    "--timetable",
                    str(self.timetable),
                    "--all-origins",
                    "--out",
                    str(self.out),
                ]
            )
        self.assertEqual(code, 0)
        return buffer.getvalue()

    def test_only_priceable_stations_get_a_page(self) -> None:
        self.build()
        written = sorted(child.name for child in (self.out.parent / "from").iterdir())
        self.assertEqual(written, ["grantham", "nottingham"])

    def test_the_chooser_offers_every_page_and_no_others(self) -> None:
        self.build()
        chooser = (self.out.parent / "index.html").read_text(encoding="utf-8")
        pages = [child.name for child in (self.out.parent / "from").iterdir()]
        for slug in pages:
            self.assertIn(f"/from/{slug}/", chooser)
        self.assertNotIn("0 destination", chooser)

    def test_an_earlier_build_in_the_folder_is_named_not_deleted(self) -> None:
        (self.out.parent / "from" / "sleepy").mkdir(parents=True)
        stale_file = self.out.parent / "from" / "sleepy" / "index.html"
        stale_file.write_text("from an earlier build", encoding="utf-8")
        said = self.build()
        self.assertIn("earlier build", said)
        self.assertIn("sleepy", said)
        self.assertTrue(stale_file.exists(), "the build must not delete a page it did not write")

    def test_a_fresh_folder_gets_no_stale_note(self) -> None:
        self.assertNotIn("earlier build", self.build())

    def test_fast_all_origins_reports_progress_and_resumes_completed_pages(self) -> None:
        first = io.StringIO()
        with contextlib.redirect_stdout(first):
            code = build_demo_page.main([
                "--feed", str(self.feed), "--fast-all-origins",
                "--out", str(self.out),
            ])
        self.assertEqual(code, 0)
        self.assertIn("Finding priceable origins", first.getvalue())
        self.assertIn("progress is saved after every page", first.getvalue())
        self.assertTrue((self.out.parent / ".trainbudget-build.json").is_file())

        second = io.StringIO()
        with contextlib.redirect_stdout(second):
            code = build_demo_page.main([
                "--feed", str(self.feed), "--fast-all-origins",
                "--out", str(self.out),
            ])
        self.assertEqual(code, 0)
        self.assertIn("Building 0 station page(s)", second.getvalue())
        self.assertIn("station pages complete: 2/2", second.getvalue())

    def test_an_overrun_origin_trips_the_wire_and_writes_nothing(self) -> None:
        # ADR-0024's tripwire (audit B1): a superquadratic search must be
        # visible on the FIRST origin, not after hours of a doomed full build.
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--timetable", str(self.timetable),
                    "--all-origins", "--out", str(self.out),
                    "--max-origin-seconds", "0.000001",
                ]
            )
        self.assertEqual(code, 3)
        self.assertIn("tripwire", stderr.getvalue())
        self.assertFalse(self.out.parent.joinpath("from").exists(), "a stopped build must not leave half a site")

    def test_the_worker_path_and_the_inprocess_path_build_the_same_pages(self) -> None:
        # Audit A2: the two modes went through different job shapes once; the
        # proof they agree is a byte-diff of the pages each mode writes.
        self.build()
        single = (self.out.parent / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--timetable", str(self.timetable),
                    "--all-origins", "--out", str(self.out),
                    "--workers", "2",
                ]
            )
        self.assertEqual(code, 0)
        pooled = (self.out.parent / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        # Build timestamp is deliberately shared between the in-process and
        # worker paths so their generated pages are byte-for-byte comparable.
        self.assertEqual(single.replace(single.split('"builtAt":"')[1][:20], "TIMESTAMP"), pooled.replace(pooled.split('"builtAt":"')[1][:20], "TIMESTAMP"))

    def test_a_pool_build_restores_fare_indexes_instead_of_re_parsing(self) -> None:
        # Audit B1: without persisted indexes, every worker re-parsed all 8.5M
        # flow lines on top of the parent's parse -- nine parses for eight
        # workers. The pool must find the shared metadata and per-origin
        # slices in CACHE_DIR before it starts.
        with contextlib.redirect_stdout(io.StringIO()):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--all-origins", "--out", str(self.out),
                    "--workers", "2",
                ]
            )
        self.assertEqual(code, 0)
        common_cache, index_dir = build_demo_page.fares_index_cache_paths(self.feed)
        self.assertTrue(common_cache.is_file(), "the shared metadata is persisted before the pool starts")
        self.assertTrue(index_dir.is_dir())
        self.assertTrue(
            list(index_dir.glob("*.pickle")),
            "one index per priceable origin is written for the workers",
        )
        restored = FaresDb.load_fare_common(common_cache)
        self.assertIsNotNone(restored.feed_stats, "the shared half carries the whole feed's stats")

    def test_the_build_says_how_to_open_what_it_wrote(self) -> None:
        # The pages are build output and their links are root-absolute, so
        # double-clicking the file does not work and a local server does.
        said = self.build()
        self.assertIn("http.server", said)
        self.assertIn("http://localhost", said)

    def test_a_feed_with_no_reviewed_price_still_writes_the_chooser(self) -> None:
        # A real feed can price nothing under the selector. The all-origins
        # build writes no station pages then, so the chooser's folder has to be
        # created by the chooser write rather than by a station page.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            deletes = "".join(
                _line(
                    {
                        "update_marker": "D",
                        "record_type": "T",
                        "flow_id": flow_id,
                        "ticket_code": "SDR",
                    },
                    FLOW_T,
                )
                + "\n"
                for flow_id in ("0000001", "0000002", "0000003", "0000004", "0000005")
            )
            (feed / "zz-delete.ffl").write_text(deletes, encoding="utf-8")
            out = root / "site" / "index.html"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    [
                        "--feed", str(feed),
                        "--all-origins", "--out", str(out),
                    ]
                )
            self.assertEqual(code, 0)
            chooser = out.read_text(encoding="utf-8")
            self.assertIn("Nothing is priced from any station in this build", chooser)



class SlugAgreementTest(unittest.TestCase):
    """Audit finding A1: both build modes must agree on station addresses.

    Slugs are disambiguated by a shared ``taken`` set, so a build that computed
    them per-station (an empty set each time) can link to a folder the
    --all-origins build wrote under a different name. Two stations named
    NOTTINGHAM exercise it; the synthetic feed alone never would.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.timetable_path = build_synthetic_timetable(root / "timetable")
        cls.timetable = TimetableDb().load_feed(cls.timetable_path)
        # The base feed plus a second station also called NOTTINGHAM (NMP),
        # priced from and to GRANTHAM, written in the real record layouts. NMP
        # needs an outgoing flow of its own so it is a priceable origin -- a
        # slug collision only bites when both same-named stations get pages.
        cls.feed = build_synthetic_feed(
            root / "fares", include_unserved_station=True, include_restrictions=True
        )
        with open(cls.feed / "rjfaf.loc", "a", encoding="utf-8") as locations:
            locations.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "L",
                        "nlc": "8000",
                        "description": "NOTTINGHAM",
                        "crs": "NMP",
                    },
                    LOCATION,
                )
                + "\n"
            )
        with open(cls.feed / "rjfaf.ffl", "a", encoding="utf-8") as flows:
            flows.write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "1000",
                        "destination_nlc": "8000",
                        "route_code": "00000",
                        "flow_id": "0000020",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000020",
                        "ticket_code": "SDR",
                        "fare_pence": "1050",
                        "restriction_code": "",
                    },
                    FLOW_T,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "8000",
                        "destination_nlc": "1000",
                        "route_code": "00000",
                        "flow_id": "0000021",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000021",
                        "ticket_code": "SDR",
                        "fare_pence": "1050",
                        "restriction_code": "",
                    },
                    FLOW_T,
                )
                + "\n"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_single_origin_picker_links_match_all_origins_folders(self) -> None:
        fares = FaresDb().load_feed(self.feed)
        # The single-origin build's picker: built the way main() builds it.
        payload = build_payload(fares, self.timetable, "GRN")
        hrefs = {station["crs"]: station["href"] for station in payload["stations"]}
        # The all-origins build's folder names: the index's slugs.
        # Counted the same way main() counts, so this test cannot pass on a
        # station set the --all-origins build would not write.
        index = build_station_index(
            {
                crs: build_demo_page._priced_destinations(fares, self.timetable, crs)
                for crs in fares.locations_by_crs
            },
            fares.locations_by_crs,
        )
        folders = {entry["crs"]: entry["slug"] for entry in index}
        # A real collision happened: the two NOTTINGHAMs cannot both be
        # "nottingham", exactly the case the empty-set slug call got wrong.
        # Both carry their CRS, whatever order the build sees them in.
        self.assertEqual(folders["NOT"], "nottingham-not")
        self.assertEqual(folders["NMP"], "nottingham-nmp")
        for crs, slug in folders.items():
            if crs == "GRN":  # the page's own origin is not in its picker
                continue
            self.assertEqual(hrefs[crs], f"/from/{slug}/", crs)

    def test_the_all_origins_chooser_links_resolve_to_written_pages(self) -> None:
        out = Path(self._tmp.name) / "site" / "index.html"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--feed", str(self.feed),
                    "--timetable", str(self.timetable_path),
                    "--all-origins", "--out", str(out),
                ]
            )
        self.assertEqual(code, 0)
        chooser = out.read_text(encoding="utf-8")
        for page in (out.parent / "from").iterdir():
            self.assertIn(f"/from/{page.name}/", chooser)


class PartialMetadataTest(unittest.TestCase):
    """Audit finding A3: a real feed's unfinished provenance note must not
    ship a page labelled "the synthetic demo feed". The build refuses instead.
    """

    def test_metadata_without_a_source_refuses_the_build(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        (feed / "metadata.json").write_text(
            json.dumps({"downloaded": "3 October 2026"}), encoding="utf-8"
        )
        out = root / "site" / "index.html"
        out.parent.mkdir(parents=True)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
        self.assertEqual(code, 2)
        self.assertFalse(out.exists(), "no page may be written when provenance is unresolved")
        self.assertIn("names no 'source'", stderr.getvalue())

    def test_metadata_with_a_source_builds_normally(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        (feed / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )
        out = root / "site" / "index.html"
        out.parent.mkdir(parents=True)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--feed", str(feed),
                    "--out", str(out),
                    "--notices", "ogl",
                    "--privacy-contact", "a@b.test",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("RSP fares feed", station_page(out).read_text(encoding="utf-8"))

    def test_price_source_override_settles_an_unfinished_note(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        (feed / "metadata.json").write_text(
            json.dumps({"downloaded": "3 October 2026"}), encoding="utf-8"
        )
        out = root / "site" / "index.html"
        out.parent.mkdir(parents=True)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                [
                    "--feed", str(feed),
                    "--out", str(out),
                    "--price-source", "the 2026 RSP download",
                    "--notices", "ogl",
                    "--privacy-contact", "a@b.test",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("the 2026 RSP download", station_page(out).read_text(encoding="utf-8"))


class PublicationGateTest(unittest.TestCase):
    """No page at all without the data the reviewed selector depends on.

    The gate is the change's whole point: a fares feed whose .RST file never
    arrived cannot have its restriction codes checked, so the build refuses
    rather than falling back to the broad query's prices.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        # include_restrictions defaults to False: a feed with no .RST.
        self.feed = build_synthetic_feed(self.root / "fares")
        self.assertTrue((self.feed / "rjfaf.rst").exists() is False)

    def run_build(self, out: Path, *extra: str) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = build_demo_page.main(["--feed", str(self.feed), "--out", str(out), *extra])
        return code, stderr.getvalue()

    def test_a_feed_with_no_restriction_file_refuses_the_build(self) -> None:
        out = self.root / "site" / "index.html"
        code, said = self.run_build(out)
        self.assertEqual(code, 2)
        self.assertFalse(out.exists(), "a refused build must write no page")
        self.assertIn("no .RST restriction file", said)

    def test_the_refusal_also_writes_no_chooser_or_station_pages(self) -> None:
        out = self.root / "site" / "index.html"
        code, _ = self.run_build(out, "--all-origins")
        self.assertEqual(code, 2)
        self.assertFalse(out.parent.exists(), "a refused build must leave no folder behind")


class UnsourcedDestinationTest(unittest.TestCase):
    """The build names a priced destination it cannot classify.

    The synthetic feed classifies every station, so a row is made unsourced
    here: the point of the check is what the build does with one, not how a
    feed comes to have one.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(self.root / "fares", include_restrictions=True)
        (self.root / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )

    def run_build(self, out: Path, *extra: str, unsourced: bool = True) -> tuple[int, str]:
        """Build, with Lincoln left unclassified when ``unsourced``.

        The gap is made at the source -- ``destination_type`` is the one answer
        both the payload and the chooser's own query read -- so this exercises
        the same path a real unnamed station takes rather than a faked row.
        """
        stderr = io.StringIO()
        patches = []
        if unsourced:
            real = FaresDb.destination_type

            def lossy(self, crs):
                return "other" if crs.strip().upper() == "LCN" else real(self, crs)

            patches.append(mock.patch.object(FaresDb, "destination_type", lossy))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = build_demo_page.main(["--feed", str(self.feed), "--out", str(out), *extra])
        return code, stderr.getvalue()

    def test_a_clean_page_is_not_warned_about(self) -> None:
        out = self.root / "site" / "index.html"
        code, said = self.run_build(out, unsourced=False)
        self.assertEqual(code, 0)
        self.assertNotIn("no settlement class", said)

    def test_an_unsourced_destination_is_named_in_a_warning(self) -> None:
        out = self.root / "site" / "index.html"
        code, said = self.run_build(out)
        self.assertEqual(code, 0)
        self.assertIn("no settlement class from any source", said)
        self.assertIn("LCN", said)

    def test_the_strict_flag_refuses_and_writes_nothing(self) -> None:
        out = self.root / "site" / "index.html"
        code, said = self.run_build(out, "--fail-on-unsourced")
        self.assertEqual(code, 2)
        self.assertFalse(out.exists(), "a refused build must write no page")
        self.assertIn("refusing to publish", said)

    def test_the_strict_flag_refuses_before_writing_any_page(self) -> None:
        out = self.root / "site" / "index.html"
        code, _ = self.run_build(out, "--all-origins", "--fail-on-unsourced")
        self.assertEqual(code, 2)
        self.assertFalse(out.parent.exists(), "a refused build must leave no folder behind")


class ClassificationGateTest(unittest.TestCase):
    """A lost classification source is a visible build event (audit A5).

    The synthetic feed's classification sources are all local, so the failure
    is injected where the loader would record it: the point is what the build
    does with a recorded failure, not how one comes to exist.
    """

    FAILURE = "seaside station classification unavailable: no network in this sandbox"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(self.root / "fares", include_restrictions=True)
        (self.root / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )

    def build(self, *extra: str) -> tuple[int, str, str, Path]:
        out = self.root / "site" / "index.html"
        original = FaresDb.load_feed

        def with_failure(db_self, *args, **kwargs):
            loaded = original(db_self, *args, **kwargs)
            loaded.report.classification_failures.append(self.FAILURE)
            return loaded

        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(FaresDb, "load_feed", with_failure):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = build_demo_page.main(
                    ["--feed", str(self.feed), "--out", str(out), *extra]
                )
        return code, stdout.getvalue(), stderr.getvalue(), out

    def test_a_lost_classification_source_is_printed_and_the_build_publishes(self) -> None:
        code, said, _, out = self.build()
        self.assertEqual(code, 0, "without the flag the page still builds on the fallbacks")
        self.assertIn(f"classification: {self.FAILURE}", said)
        self.assertTrue(out.exists())

    def test_the_require_flag_refuses_and_writes_nothing(self) -> None:
        code, _, said, out = self.build("--require-classification")
        self.assertEqual(code, 2)
        self.assertIn("refusing to publish", said)
        self.assertIn("seaside station classification unavailable", said)
        self.assertFalse(out.exists(), "a refused build must write no page")

    def test_a_classification_skip_is_also_a_skipped_file(self) -> None:
        # feed_audit still sees it as an unopened source; the second list is
        # only what the build's gate reads.
        report = ParseReport()
        report.skip_classification(self.FAILURE)
        self.assertEqual(report.classification_failures, [self.FAILURE])
        self.assertEqual(report.skipped_files, [self.FAILURE])


class ReviewedCodeGateTest(unittest.TestCase):
    """A dead reviewed code is a visible build event (audit A7).

    The synthetic feed carries six stations, so almost every reviewed
    settlement-fallback code is absent from it -- which is exactly the state
    this gate exists to catch, and why the test needs no injection.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(self.root / "fares", include_restrictions=True)
        (self.root / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )

    def build(self, *extra: str) -> tuple[int, str, str, Path]:
        out = self.root / "site" / "index.html"
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = build_demo_page.main(
                ["--feed", str(self.feed), "--out", str(out), *extra]
            )
        return code, stdout.getvalue(), stderr.getvalue(), out

    def test_the_dead_codes_are_named_and_the_build_publishes(self) -> None:
        code, said, _, out = self.build()
        self.assertEqual(code, 0, "without the flag the page still builds")
        self.assertIn("reviewed codes:", said)
        self.assertIn("match no station in this feed", said)
        self.assertTrue(out.exists())

    def test_the_require_flag_refuses_and_names_the_codes(self) -> None:
        code, _, said, out = self.build("--require-live-reviewed-codes")
        self.assertEqual(code, 2)
        self.assertIn("refusing to publish", said)
        self.assertIn("reviewed settlement fallback code", said)
        self.assertFalse(out.exists(), "a refused build must write no page")

    def test_a_dead_code_is_named_once_and_is_not_an_unopened_file(self) -> None:
        # It is a list going stale, not a file left unread, so it gets its own
        # channel: reporting it as an unopened source would be a lie that also
        # hid it among the archive-inside-an-archive notes.
        with tempfile.TemporaryDirectory() as tmp:
            db = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
        self.assertTrue(db.report.reviewed_codes_absent)
        self.assertEqual(
            db.report.skipped_files,
            [],
            f"a dead reviewed code is not a skipped file: {db.report.skipped_files!r}",
        )

    def test_a_code_the_workbook_already_names_refuses_too(self) -> None:
        # The other half of the same staleness, and the harder half to notice.
        # The code resolves, so the absent list is not the one that catches it,
        # and nothing about the page looks wrong: the entry applies to nothing
        # at all until a name match misses and then lands its class on a
        # station the workbook had already classified correctly. BHC is stood in
        # for a reviewed Welsh entry, because the synthetic feed has no
        # workbook to read and this gate is about what the build does with what
        # the loader found.
        def workbook(self: FaresDb) -> None:
            self.ons_classified_crs.add("BHC")
            self._apply_major_station_fallbacks()

        (self.root / "download-manifest.json").write_text("{}", encoding="utf-8")
        # The synthetic feed ships its own classification cache, and a cache
        # that classifies the feed ends the pass before the workbook is read
        # -- so the gate under test would never run with it in place.
        (self.root / "fares.location-types.json").unlink()
        out = self.root / "site" / "index.html"
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(FaresDb, "_load_ons_location_types", workbook):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = build_demo_page.main(
                    ["--feed", str(self.feed), "--out", str(out), "--require-live-reviewed-codes"]
                )
        self.assertEqual(code, 2)
        # The note is where the code is legible: the refusal below it carries
        # the count, because the synthetic feed's 305 absent codes would
        # otherwise push BHC out of a truncated list, and a test that found
        # BHC in the *absent* list would pass without this half ever working.
        self.assertIn(
            "name a station the ONS workbook already classifies, so the entry "
            "applies to nothing: BHC",
            stdout.getvalue(),
        )
        self.assertIn("1 name a station the workbook already classifies", stderr.getvalue())
        self.assertFalse(out.exists(), "a refused build must write no page")


class PseudoStationTest(unittest.TestCase):
    """Zone boundaries are priceable in the feed but are not places (audit A6)."""

    class Station:
        def __init__(self, crs: str, name: str) -> None:
            self.crs = crs
            self.name = name

    def test_the_chooser_omits_a_priced_zone_boundary(self) -> None:
        locations = {
            "GRA": self.Station("GRA", "GRANTHAM"),
            "QAH": self.Station("QAH", "BOUNDARY ZONE 4"),
        }
        index = build_station_index({"GRA": 5, "QAH": 611}, locations)
        self.assertEqual([entry["crs"] for entry in index], ["GRA"])

    def test_the_jump_list_omits_pseudo_stations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
            fares.locations_by_crs = dict(
                fares.locations_by_crs,
                QAH=self.Station("QAH", "BOUNDARY ZONE 4"),
            )
            payload = build_payload(fares, None, "GRN")
        names = {station["name"] for station in payload["stations"]}
        self.assertNotIn("BOUNDARY ZONE 4", names)
        self.assertTrue(names, "the jump list still carries the real stations")
        self.assertTrue(any("NOTTINGHAM" in name for name in names))

    def test_a_pseudo_destination_is_not_published_as_a_place(self) -> None:
        # A zone boundary records a fare change, not a journey, so it must not
        # become a row a reader could buy a ticket to. The rule lives in the
        # shared query loop, so the page, the chooser and the coverage report
        # cannot disagree about it.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            (feed / "rjfaf.loc").open("a", encoding="utf-8").write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "L",
                        "nlc": "9999",
                        "description": "BOUNDARY ZONE 4",
                        "crs": "QAH",
                        "group_nlc": "9999",
                    },
                    LOCATION,
                )
                + "\n"
            )
            (feed / "rjfaf.ffl").open("a", encoding="utf-8").write(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "F",
                        "origin_nlc": "1000",
                        "destination_nlc": "9999",
                        "route_code": "00000",
                        "flow_id": "0000099",
                    },
                    FLOW_F,
                )
                + "\n"
                + _line(
                    {
                        "update_marker": "A",
                        "record_type": "T",
                        "flow_id": "0000099",
                        "ticket_code": "CDR",
                        "fare_pence": "1500",
                        "restriction_code": "1A",
                    },
                    FLOW_T,
                )
                + "\n"
            )
            fares = FaresDb().load_feed(feed)
            # The feed does reach the zone and does price a fare to it, and the
            # query says where that fare went rather than dropping it silently.
            tally: dict[str, int] = {}
            reachable = fares.destinations_within("GRN", 10_000_000, adults=1, tally=tally)
            self.assertEqual(tally["destination_is_a_fare_construction_point"], 1)
            self.assertNotIn(
                "QAH", [row.crs for row in reachable], "the zone is not a destination"
            )
            payload = build_payload(fares, None, "GRN")
            rows = (
                payload["destinations"]
                + payload["singleDestinations"]
                + payload["anytimeDestinations"]
            )
        self.assertTrue(
            all(row["crs"] != "QAH" for row in rows),
            f"a zone boundary was published as a destination: {rows!r}",
        )
        self.assertTrue(rows, "the page's real destinations are untouched")


class UnnameableCeilingTest(unittest.TestCase):
    """The payload carries the priced rows the feed could not name (audit A3)."""

    @staticmethod
    def shapes_feed(root: Path) -> FaresDb:
        return FaresDb().load_feed(
            build_synthetic_feed(
                root / "shapes", include_real_shapes=True, include_restrictions=True
            )
        )

    def test_the_payload_counts_the_rows_with_no_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = self.shapes_feed(Path(tmp))
            payload = build_payload(fares, None, "GRN")
        self.assertEqual(payload["unnameableFareCount"], 2)

    def test_the_index_pass_records_them_for_the_coverage_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = self.shapes_feed(Path(tmp))
            coverage = UnsourcedReport()
            count = build_demo_page._priced_destinations(
                fares, None, "GRN", None, coverage
            )
        self.assertGreater(count, 0)
        self.assertEqual(coverage.unnameable_by_origin(), {"GRN": 2})


class TimetableCachePruneTest(unittest.TestCase):
    """Each origin keeps its newest timetable caches; stale digests go (audit B4)."""

    @staticmethod
    def cache(root: Path, name: str, mtime: float) -> Path:
        path = root / name
        path.write_bytes(b"stale")
        os.utime(path, (mtime, mtime))
        return path

    def test_the_caches_in_use_survive_and_the_origin_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(build_demo_page, "CACHE_DIR", root):
                main = self.cache(
                    root, "timetable-GRA-11111111111111111111.pickle", 1000.0
                )
                single = self.cache(
                    root, "timetable-GRA-22222222222222222222.pickle", 2000.0
                )
                self.cache(root, "timetable-GRA-33333333333333333333.pickle", 3000.0)
                old = self.cache(
                    root, "timetable-GRA-44444444444444444444.pickle", 500.0
                )
                other = self.cache(
                    root, "timetable-SFA-55555555555555555555.pickle", 400.0
                )
                pruned = build_demo_page.prune_timetable_caches(main, single)
            self.assertEqual(pruned, 2, "the two stale GRA digests are deleted")
            self.assertTrue(main.exists() and single.exists(), "caches in use survive")
            self.assertFalse(
                (root / "timetable-GRA-33333333333333333333.pickle").exists()
            )
            self.assertFalse(old.exists())
            self.assertTrue(other.exists(), "another origin's cache is untouched")

    def test_a_single_cache_keeps_one_newest_stale_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(build_demo_page, "CACHE_DIR", root):
                main = self.cache(
                    root, "timetable-GRA-aaaaaaaaaaaaaaaaaaaa.pickle", 1000.0
                )
                newest = self.cache(
                    root, "timetable-GRA-bbbbbbbbbbbbbbbbbbbb.pickle", 3000.0
                )
                stale = self.cache(
                    root, "timetable-GRA-cccccccccccccccccccc.pickle", 500.0
                )
                pruned = build_demo_page.prune_timetable_caches(main)
            self.assertEqual(pruned, 1)
            self.assertTrue(main.exists())
            self.assertTrue(
                newest.exists(), "the keep line retains the newest stale sibling"
            )
            self.assertFalse(stale.exists())

    def test_the_timetable_cache_key_cannot_serve_a_replaced_download(self) -> None:
        # The timetable cache was keyed on names, sizes and mtimes, which cannot
        # tell two downloads apart when a copy preserves timestamps or an archive
        # is extracted with the dates stored in it. A stale hit puts one
        # download's services on a page built from another: a reader is shown a
        # timetable that is not the one in force.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_timetable(root / "timetable")
            before = build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"})
            target = next(item for item in sorted(feed.iterdir()) if item.is_file())
            original = target.read_text(encoding="utf-8")
            stamp = target.stat().st_mtime_ns
            target.write_text(original.replace("NOT", "NT1", 1), encoding="utf-8")
            os.utime(target, ns=(stamp, stamp))
            self.assertEqual(len(target.read_text(encoding="utf-8")), len(original))
            after = build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"})
        self.assertNotEqual(before, after, "different bytes are a different cache")
        # The focus is part of the name too: a cache for one station's set of
        # destinations is not an answer for another's.
        self.assertNotEqual(
            build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"}),
            build_demo_page.timetable_cache_path(feed, "GRN", {"LCN"}),
        )
        self.assertEqual(
            build_demo_page.timetable_cache_path(feed, "GRN", {"NOT", "LCN"}),
            build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"}),
            "the focus set is a set, so its order is not part of the key",
        )

    def test_a_build_says_whether_it_parsed_or_restored_the_timetable(self) -> None:
        # On the real feed those are 55.6s and 2.6s, so the line that reports
        # the load is the line an operator reads to find out which they paid.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            timetable = build_synthetic_timetable(root / "timetable")
            cache = root / "cache"
            with mock.patch.object(build_demo_page, "CACHE_DIR", cache):
                said = []
                for _ in range(2):
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
                        code = build_demo_page.main(
                            [
                                "--feed", str(feed),
                                "--timetable", str(timetable),
                                "--origin", "GRN",
                                "--out", str(root / "site" / "index.html"),
                            ]
                        )
                    self.assertEqual(code, 0)
                    said.append(buffer.getvalue())
        self.assertIn("(parsed; wrote timetable-GRN-", said[0])
        self.assertIn("(restored from timetable-GRN-", said[1])

    def test_a_cache_hit_that_is_the_oldest_file_still_survives(self) -> None:
        # A hit does not touch mtime, so the file this build just read can be
        # the oldest on disk. It must not evict itself.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(build_demo_page, "CACHE_DIR", root):
                hit = self.cache(
                    root, "timetable-GRA-dddddddddddddddddddd.pickle", 100.0
                )
                newer = self.cache(
                    root, "timetable-GRA-eeeeeeeeeeeeeeeeeeee.pickle", 9000.0
                )
                newest = self.cache(
                    root, "timetable-GRA-ffffffffffffffffffff.pickle", 8000.0
                )
                pruned = build_demo_page.prune_timetable_caches(hit, keep=1)
            self.assertEqual(pruned, 2)
            self.assertTrue(hit.exists(), "the used cache survives even at keep=1")
            self.assertFalse(newer.exists())
            self.assertFalse(newest.exists())


class FaresCacheTest(unittest.TestCase):
    """A page build parses the national feed once, then reads it off the disk.

    A focused parse of the real DTD download reads 727,315 flow records to
    keep the ones reachable from one station, and took 32.5s of a real build;
    restoring the split the pool build already persists takes about a second.
    The risk in any such cache is not that it misses, it is that it hits when
    it should not, so most of what is checked here is what must NOT be served.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.cache = root / "cache"
        self.feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        self.out = root / "site" / "index.html"

    def build(self) -> str:
        buffer = io.StringIO()
        with mock.patch.object(build_demo_page, "CACHE_DIR", self.cache):
            with contextlib.redirect_stdout(buffer):
                code = build_demo_page.main(
                    ["--feed", str(self.feed), "--origin", "GRN", "--out", str(self.out)]
                )
        self.assertEqual(code, 0)
        return buffer.getvalue()

    def cache_paths(self):
        # The cache lives where the build puts it, so it is asked for from
        # there: a test that named the repository's own _cache would be reading
        # and writing the caches of whichever test ran before it.
        with mock.patch.object(build_demo_page, "CACHE_DIR", self.cache):
            return build_demo_page.fares_index_cache_paths(self.feed)

    def load_fares(self, origin: str):
        with mock.patch.object(build_demo_page, "CACHE_DIR", self.cache):
            return build_demo_page.load_page_fares(self.feed, origin)

    def prune(self, *used) -> int:
        with mock.patch.object(build_demo_page, "CACHE_DIR", self.cache):
            return build_demo_page.prune_fare_index_caches(*used)
    def page(self) -> str:
        return station_page(self.out).read_text(encoding="utf-8")

    def without_timestamp(self, html: str) -> str:
        return html.replace(html.split('"builtAt":"')[1][:20], "TIMESTAMP")

    def test_the_second_build_reads_the_cache_and_writes_the_same_page(self) -> None:
        first = self.build()
        self.assertIn("wrote ", first, "the first build parses the feed and fills the cache")
        common, index_dir = self.cache_paths()
        self.assertTrue(common.is_file(), "the shared half is written for the next build")
        self.assertTrue((index_dir / "GRN.pickle").is_file(), "one index per origin")
        written = self.page()

        second = self.build()
        self.assertIn("restored from GRN.pickle", second)
        # The whole point of the cache: the same page, from a different route.
        # A restored database is the one the pool workers already build pages
        # from, and if the two ever disagreed the cache would be quietly
        # changing prices rather than saving time.
        self.assertEqual(self.without_timestamp(written), self.without_timestamp(self.page()))

    def test_a_feed_replaced_by_other_bytes_of_the_same_size_and_time_is_not_served(self) -> None:
        # The stale-cache case a fingerprint cannot catch. A copy that
        # preserves timestamps, or an archive extracted with the dates stored
        # in it, replaces a feed with different fares and no visible change to
        # its name, size or mtime. A cache keyed on any of those would go on
        # serving yesterday's prices, and the page would look entirely normal.
        self.build()
        before = self.page()
        self.assertIn("1160", before, "the fixture's Nottingham return is on the page")
        cheap_fingerprint = build_demo_page.feed_fingerprint(self.feed)
        cache_before = self.cache_paths()

        target = next(item for item in sorted(self.feed.glob("*.ffl")))
        original = target.read_text(encoding="utf-8")
        stamp = target.stat().st_mtime_ns
        # Same length, same timestamp, different fare.
        target.write_text(original.replace("1160", "1260", 1), encoding="utf-8")
        os.utime(target, ns=(stamp, stamp))
        self.assertEqual(len(target.read_text(encoding="utf-8")), len(original))
        self.assertEqual(
            build_demo_page.feed_fingerprint(self.feed),
            cheap_fingerprint,
            "the cheap fingerprint cannot tell these two feeds apart, which is the point",
        )

        said = self.build()
        self.assertIn("wrote GRN.pickle", said, "different bytes are a different cache, so the feed is parsed again")
        self.assertNotEqual(cache_before, self.cache_paths())
        self.assertNotEqual(before, self.page())
        self.assertIn("1260", self.page(), "the page quotes the fare the feed now holds")

    def test_a_classification_corrected_beside_the_feed_misses_the_cache(self) -> None:
        # The station types a parse carries come from files beside the feed and
        # from the code that reads them, not from the feed's own bytes. A key on
        # the feed alone would serve a database whose types came from a source
        # that has since been corrected: current prices, stale classes, and a
        # page that looks entirely normal.
        self.build()
        before_cache = self.cache_paths()
        self.assertEqual(self.destination_type("LCN"), "city")

        types = self.feed.parent / "fares.location-types.json"
        records = json.loads(types.read_text(encoding="utf-8"))
        records["records"]["LCN"] = {"primary": "village", "facets": []}
        types.write_text(json.dumps(records), encoding="utf-8")
        self.assertNotEqual(
            before_cache, self.cache_paths(), "the corrected classification is a different cache"
        )

        said = self.build()
        self.assertIn("wrote GRN.pickle", said, "the feed is parsed again rather than served from before")
        self.assertEqual(self.destination_type("LCN"), "village")

    def destination_type(self, crs: str) -> str:
        rows = {
            row["crs"]: row
            for row in embedded_payload(self.page())["destinations"]
        }
        return rows[crs]["destinationType"]

    def test_an_index_filed_under_another_origin_is_not_served(self) -> None:
        # The path a build asks for is built from the origin it was asked for,
        # so a file under the wrong name is a hand-mixed cache. Serving it would
        # put one station's fares on another station's page.
        self.build()
        _, index_dir = self.cache_paths()
        self.load_fares("NOT")
        nottingham = index_dir / "NOT.pickle"
        self.assertTrue(nottingham.is_file())
        shutil.copy(nottingham, index_dir / "GRN.pickle")

        served_fares = self.load_fares("GRN")
        self.assertFalse(served_fares.restored, "another origin's index is not this origin's fares")
        self.assertNotEqual(
            served_fares.index.read_bytes(),
            nottingham.read_bytes(),
            "the wrong index is rewritten rather than left in place",
        )
        # And what was written back is this origin's: the flows an index keeps
        # are the ones reachable from the station it names, so an index that
        # had been another station's would answer with another station's NLCs.
        restored = FaresDb.load_fare_index(served_fares.common, served_fares.index)
        self.assertEqual(restored._cache_origin, "GRN")
        carried = {restored.locations_by_nlc[nlc].crs for nlc in restored.flows_touching_nlc}
        self.assertEqual(carried, {"GRN"})
        self.assertEqual(
            served_fares.fares.stats()["fares"], restored.stats()["fares"]
        )

    def test_a_half_written_cache_is_parsed_over_rather_than_trusted(self) -> None:
        # A build interrupted while writing leaves a truncated pickle. A cache
        # is an optimisation, so the worst it may do is be slow.
        self.build()
        common, index_dir = self.cache_paths()
        common.write_bytes(b"\x80\x04 truncated")
        loaded = self.load_fares("GRN")
        self.assertFalse(loaded.restored)
        self.assertTrue(loaded.fares.destinations_within("GRN", 100000, adults=1))
        self.assertTrue(loaded.index.is_file())

    def test_a_corrupt_index_is_parsed_over_rather_than_trusted(self) -> None:
        self.build()
        _, index_dir = self.cache_paths()
        (index_dir / "GRN.pickle").write_bytes(b"not a pickle")
        loaded = self.load_fares("GRN")
        self.assertFalse(loaded.restored)
        self.assertTrue(loaded.fares.destinations_within("GRN", 100000, adults=1))
        self.assertTrue(loaded.index.is_file())

    def cache_pair(self, digest: str, mtime: float) -> tuple[Path, Path]:
        """A cache pair as an earlier revision of the feed would have left it."""
        common = self.cache / f"fare-index-v2-{digest}.pickle"
        common.write_bytes(b"an earlier revision")
        origins = self.cache / f"fare-index-v2-{digest}-origins"
        origins.mkdir()
        (origins / "GRN.pickle").write_bytes(b"an earlier revision")
        os.utime(common, (mtime, mtime))
        os.utime(origins, (mtime, mtime))
        return common, origins

    def test_the_caches_of_older_feeds_are_tidied_and_this_one_is_kept(self) -> None:
        # A fares cache is named by the feed's content, so a new download means
        # a new name and an old pair can never be read again: 37MB of shared
        # metadata per revision, kept for ever otherwise. One revision back is
        # still worth having -- a build that is interrupted and re-run is
        # looking at it -- and anything older than that is deleted whole.
        self.build()
        previous = self.cache_pair("00000000000000000001", 5000.0)
        older = self.cache_pair("00000000000000000002", 1000.0)

        loaded = self.load_fares("GRN")
        removed = self.prune(loaded.common, loaded.index.parent)
        self.assertEqual(removed, 2, "the oldest pair is two files: shared half and index")
        self.assertFalse(older[0].exists() and older[1].exists(), "two revisions back goes")
        self.assertTrue(previous[0].exists() and previous[1].exists(), "one revision back stays")
        self.assertTrue(loaded.common.is_file(), "the pair in use survives")
        self.assertTrue(loaded.index.is_file())

    def test_a_cache_hit_is_never_the_file_the_tidy_would_delete(self) -> None:
        # The hit can be the oldest file on disk, because reading it does not
        # touch its timestamp. Deleting it would make the next build re-parse
        # for no reason, on the one run that had already paid to parse.
        self.build()
        loaded = self.load_fares("GRN")
        os.utime(loaded.common, (1000.0, 1000.0))
        os.utime(loaded.index, (1000.0, 1000.0))
        removed = self.prune(loaded.common, loaded.index.parent)
        self.assertEqual(removed, 0)
        self.assertTrue(loaded.common.is_file() and loaded.index.is_file())

    def test_the_cache_key_names_the_format_so_a_schema_change_misses(self) -> None:
        # The pickled layout is versioned in the file name: a database written
        # by older code must be left alone, not read and rebuilt into a
        # different structure.
        common, origins = self.cache_paths()
        self.assertIn(f"-v{build_demo_page.FARE_INDEX_CACHE_VERSION}-", common.name)
        self.assertIn(f"-v{build_demo_page.FARE_INDEX_CACHE_VERSION}-", origins.name)
        with mock.patch.object(build_demo_page, "CACHE_DIR", self.cache):
            with mock.patch.object(build_demo_page, "FARE_INDEX_CACHE_VERSION", 99):
                moved_common, moved_origins = build_demo_page.fares_index_cache_paths(self.feed)
        self.assertNotEqual(common, moved_common)
        self.assertNotEqual(origins, moved_origins)
        self.assertIn("-v99-", moved_common.name)

    def test_two_different_feeds_never_share_a_cache(self) -> None:
        first, _ = self.cache_paths()
        # The same feed twice is the same cache, or nothing would ever be read
        # back -- and a feed that differs by one file is a different one.
        self.assertEqual(first, self.cache_paths()[0])
        other = build_synthetic_feed(
            Path(self._tmp.name) / "other", include_restrictions=False
        )
        with mock.patch.object(build_demo_page, "CACHE_DIR", self.cache):
            second, _ = build_demo_page.fares_index_cache_paths(other)
        self.assertNotEqual(first, second)


class FreshOutputFolderTest(unittest.TestCase):
    """The README tells the operator to delete a stale _site/, so the build must
    create a missing output folder rather than only working when one exists."""

    def test_a_single_origin_build_creates_its_output_folder(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        out = root / "fresh" / "site" / "index.html"
        self.assertFalse(out.parent.exists())
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertTrue(out.exists())
        self.assertIn("GRANTHAM", out.read_text(encoding="utf-8"))


class RouteManifestTest(unittest.TestCase):
    """S01, S03, S04, S07: one manifest of the routes a release actually serves.

    The re-envision audit names the route contract as the weakest subsystem: a
    single-origin build used to publish a station page at the root whose Change
    picker linked to every station in the feed, none of which it had written.
    A release now writes a chooser at the root, one page per station at its
    canonical /from/<slug>/ route, and the privacy page, and proves every
    internal link resolves before calling the build good.
    """

    def build_site(self, root: Path, *extra: str) -> tuple[int, str]:
        feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        out = root / "site" / "index.html"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(["--feed", str(feed), "--out", str(out), *extra])
        return code, buffer.getvalue()

    def test_a_single_origin_build_is_a_site_with_the_chooser_at_the_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, log = self.build_site(root)
            self.assertEqual(code, 0)
            site = root / "site"
            # The root is the chooser, the one station has its canonical route,
            # and the privacy page the footer links to is present (S01, S04).
            chooser = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn("const STATIONS", chooser)
            self.assertNotIn("const DATA", chooser)  # the chooser carries no fares
            station = station_page(site / "index.html")
            self.assertTrue(station.is_file())
            self.assertIn("const DATA", station.read_text(encoding="utf-8"))
            self.assertTrue((site / "privacy" / "index.html").is_file())
            self.assertIn("link crawl", log)

    def test_the_root_names_only_the_stations_the_build_wrote(self) -> None:
        # The single-origin picker used to offer all 3,424 feed stations. The
        # manifest is what the chooser, the picker and the crawl all read, so a
        # named station always has a page behind it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            chooser = (root / "site" / "index.html").read_text(encoding="utf-8")
            match = re.search(r"const STATIONS = (\[.*?\]);", chooser, re.DOTALL)
            self.assertIsNotNone(match)
            stations = json.loads(match.group(1))
            self.assertEqual([entry["crs"] for entry in stations], ["GRN"])
            for entry in stations:
                target = root / "site" / entry["href"].strip("/") / "index.html"
                self.assertTrue(target.is_file(), f"chooser names {entry['href']} with no page")

    def test_a_station_page_links_back_to_the_chooser(self) -> None:
        # A one-station site has no sibling to switch to, so the way back to the
        # root is the "All stations" link, not a picker with nothing in it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            station = station_page(root / "site" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/"', station)

    def test_every_internal_link_in_a_built_site_resolves(self) -> None:
        # S03: the crawl is the proof, run from the generated files themselves.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            self.assertEqual(build_demo_page.crawl_internal_links(root / "site"), [])

    def test_the_link_crawl_names_a_link_to_a_page_that_was_not_written(self) -> None:
        # The failure the crawl exists to catch: a picker or footer link to a
        # page the build did not produce must be found, not shipped.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text(
                '<a href="/from/nottingham/">Nottingham</a><a href="/privacy/">Privacy</a>',
                encoding="utf-8",
            )
            broken = build_demo_page.crawl_internal_links(site)
            self.assertEqual(len(broken), 2, broken)
            self.assertIn("nottingham", broken[0])
            self.assertIn("privacy", broken[1])

    def test_the_crawl_ignores_external_and_seller_links(self) -> None:
        # A link off the site is not this site's contract; the crawl must not
        # fail on the seller's URL or a heritage link.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            site.mkdir(parents=True)
            (site / "index.html").write_text(
                '<a href="https://example.test/buy">Buy</a>'
                '<a href="//cdn.example.test/x">CDN</a>'
                '<a href="/privacy/">Privacy</a>',
                encoding="utf-8",
            )
            (site / "privacy").mkdir()
            (site / "privacy" / "index.html").write_text("<p>privacy</p>", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site), [])

    def test_the_crawl_strips_the_site_base_path(self) -> None:
        # A project site serves under /tb/, so its internal links carry the
        # base. The crawl resolves them against files on disk, not against the
        # domain, so the base is stripped before the file lookup.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text(
                '<a href="/tb/from/nottingham/">Nottingham</a>', encoding="utf-8"
            )
            broken = build_demo_page.crawl_internal_links(site, base_path="/tb")
            self.assertEqual(len(broken), 1, broken)
            (site / "from" / "nottingham").mkdir()
            (site / "from" / "nottingham" / "index.html").write_text("<p>N</p>", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site, base_path="/tb"), [])

    def test_the_crawl_fail_refuses_to_ship_a_broken_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            site.mkdir()
            (site / "index.html").write_text('<a href="/nowhere/">x</a>', encoding="utf-8")
            with self.assertRaises(SystemExit):
                build_demo_page.link_crawl_failed(["index.html links to /nowhere/"], site)

    def test_the_chooser_search_is_wired_to_its_list(self) -> None:
        # The root page is the departure picker, so the one control it exists
        # for has to filter the list. It had no listener at all, so typing a
        # name left every station on screen and the list read as a result.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            chooser = (root / "site" / "index.html").read_text(encoding="utf-8")
            self.assertIn('pick.addEventListener("input", render)', chooser)

    def test_the_chooser_links_to_the_privacy_page(self) -> None:
        # The root page is where a reader starts, so the thing that says what
        # the site sends has to be reachable from it, not only from a station.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root)
            chooser = (root / "site" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/privacy/"', chooser)
            # A base path has to prefix it too, and a leading slash must not be
            # doubled: "//privacy/" is a different host, not this site.
            self.assertIn('href="/tb/privacy/"', build_demo_page.render_chooser([], budget_pounds=20, base_path="/tb"))

    def test_the_crawl_reads_the_links_the_chooser_builds_in_the_browser(self) -> None:
        # The chooser's station links are written by its script from an
        # embedded array, so a crawl reading only href attributes would check
        # the root page and find nothing to check.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            site.mkdir(parents=True)
            (site / "index.html").write_text(
                'const STATIONS = [{"name":"Grantham","crs":"GRN","href":"/from/grantham/"}];',
                encoding="utf-8",
            )
            broken = build_demo_page.crawl_internal_links(site)
            self.assertEqual(len(broken), 1, broken)
            self.assertIn("grantham", broken[0])
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text("<p>Grantham</p>", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site), [])

    def test_a_release_manifest_names_the_routes_this_build_serves(self) -> None:
        # S07: the host consumes one folder, so "the whole verified output" has
        # to be a set somebody can read. The manifest is that set, and it is
        # proved against the files on disk rather than trusted.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text("<p>G</p>", encoding="utf-8")
            (site / "privacy").mkdir()
            (site / "privacy" / "index.html").write_text("<p>P</p>", encoding="utf-8")
            (site / "index.html").write_text("<p>C</p>", encoding="utf-8")
            path = build_demo_page.write_release_manifest(
                site,
                ["/", "/privacy/", "/from/grantham/"],
                price_source=build_demo_page.DEFAULT_PRICE_SOURCE,
                built_at="2026-09-27T00:00:00Z",
            )
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["routes"], ["/", "/from/grantham/", "/privacy/"])
            self.assertTrue(manifest["synthetic"])
            self.assertEqual(manifest["priceSource"], build_demo_page.DEFAULT_PRICE_SOURCE)
            self.assertEqual(build_demo_page.manifest_problems(site, manifest), [])
            # A route the release claims but did not write is the failure the
            # manifest exists to catch, and a base path is stripped before the
            # lookup so a project site resolves the same way its links do.
            manifest["routes"].append("/from/nottingham/")
            self.assertEqual(
                build_demo_page.manifest_problems(site, manifest),
                ["the manifest names /from/nottingham/, which was not written"],
            )
            (site / "from" / "nottingham").mkdir()
            (site / "from" / "nottingham" / "index.html").write_text("<p>N</p>", encoding="utf-8")
            self.assertEqual(build_demo_page.manifest_problems(site, manifest), [])
            based = dict(manifest, routes=["/tb/privacy/"], basePath="/tb")
            self.assertEqual(
                build_demo_page.manifest_problems(site, based, base_path="/tb"), []
            )
            # A route that is not a route on this site is refused rather than
            # resolved against the disk.
            self.assertIn(
                "not a route on this site",
                " ".join(build_demo_page.manifest_problems(site, dict(manifest, routes=["nottingham"]))),
            )

    def test_a_build_writes_and_proves_its_own_manifest(self) -> None:
        # The manifest is written by the build, not only by the helper, and the
        # build refuses rather than reporting success if it cannot be proved.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_feed(root / "fares", include_restrictions=True)
            out = root / "site" / "index.html"
            log = io.StringIO()
            with contextlib.redirect_stdout(log):
                code = build_demo_page.main(
                    ["--feed", str(feed), "--out", str(out), "--all-origins"]
                )
            self.assertEqual(code, 0)
            manifest = json.loads(
                (root / "site" / build_demo_page.RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertIn("release-manifest.json", log.getvalue())
            # Every route named is a file, and every station page the build wrote
            # is a route named: the two directions, not one.
            self.assertEqual(
                build_demo_page.manifest_problems(root / "site", manifest), []
            )
            written = sorted(
                f"/from/{child.name}/"
                for child in (root / "site" / "from").iterdir()
                if child.is_dir()
            )
            self.assertEqual(
                sorted(route for route in manifest["routes"] if route.startswith("/from/")),
                written,
            )
            self.assertIn("/", manifest["routes"])
            self.assertIn("/privacy/", manifest["routes"])
            # A single-origin build is a release of the same shape.
            solo = root / "solo"
            solo.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                code = build_demo_page.main(
                    ["--feed", str(feed), "--out", str(solo / "index.html"), "--origin", "GRN"]
                )
            self.assertEqual(code, 0)
            one = json.loads(
                (solo / build_demo_page.RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(one["routes"], ["/", "/from/grantham/", "/privacy/"])
            self.assertEqual(build_demo_page.manifest_problems(solo, one), [])


class SingleOriginRunnerTidyTest(unittest.TestCase):
    """What `python run.py` leaves behind after a single-origin build.

    C31: the runner used to delete the whole /from/ tree, which a single-origin
    build had just written its one station page into, so the chooser it served
    linked to a 404. These drive the real builder and then the real tidying
    step, because the bug lived in the seam between them and neither half
    reproduces it alone.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = Path(self.tmp)
        self.feed = self.root / "feed"
        build_synthetic_feed(self.feed, include_restrictions=True, include_third_origin=True)
        self.site = self.root / "site"

    def _build(self, *extra: str) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            code = build_demo_page.main(
                ["--feed", str(self.feed), "--out", str(self.site / "index.html"), "--origin", "GRN", *extra]
            )
        self.assertEqual(code, 0)

    def _tidy(self) -> list[str]:
        with mock.patch.object(run, "SITE", self.site):
            with contextlib.redirect_stdout(io.StringIO()):
                return run.remove_unwritten_station_pages()

    def _station_folders(self) -> list[str]:
        from_dir = self.site / "from"
        return sorted(child.name for child in from_dir.iterdir()) if from_dir.is_dir() else []

    def test_the_page_the_build_just_wrote_survives(self) -> None:
        # A single-origin build writes the chooser, privacy and the one station
        # page. Tidying must not remove that page, which is the whole defect.
        self._build()
        self.assertEqual(self._station_folders(), ["grantham"])
        self.assertEqual(self._tidy(), [])
        self.assertTrue((self.site / "from" / "grantham" / "index.html").is_file())

    def test_a_previous_all_origins_tree_is_removed(self) -> None:
        # The case the old step was written for: leftovers from a wider build,
        # which the chooser this build wrote does not offer.
        self._build("--all-origins")
        self.assertEqual(self._station_folders(), ["grantham", "lincoln", "nottingham"])
        self._build()
        self.assertEqual(self._tidy(), ["lincoln", "nottingham"])
        self.assertEqual(self._station_folders(), ["grantham"])

    def test_a_base_path_build_keeps_its_own_page(self) -> None:
        # A subpath build writes "/app/from/grantham/", not "/from/grantham/".
        # Reading the route without the prefix matched nothing and deleted the
        # page, which is C31 again for every subpath deployment.
        self._build("--base-path", "app")
        manifest = json.loads(
            (self.site / build_demo_page.RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["basePath"], "/app")
        self.assertIn("/app/from/grantham/", manifest["routes"])
        self.assertEqual(self._tidy(), [])
        self.assertTrue((self.site / "from" / "grantham" / "index.html").is_file())

    def test_nothing_is_deleted_when_the_manifest_is_absent_or_unreadable(self) -> None:
        # Deleting generated pages on a guess is the worse failure: the worst
        # case for a missing manifest is a stale folder left on disk, which the
        # build already names in its own output.
        #
        # The last two cases are the sharp ones. A manifest whose "routes" is a
        # string iterates character by character, and one whose top level is a
        # list has no "routes" at all; either way the keep-set comes out empty,
        # and an empty keep-set deletes the page the build just wrote. That is
        # the C31 defect arriving by a different road, so it is refused.
        for content in (None, "{not json", '"/from/grantham/"', "[1, 2, 3]", '{"routes": "/from/grantham/"}'):
            self._build("--all-origins")
            manifest = self.site / build_demo_page.RELEASE_MANIFEST_NAME
            if content is None:
                manifest.unlink()
            else:
                manifest.write_text(content, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self._tidy(), [], f"manifest {content!r}")
            self.assertEqual(self._station_folders(), ["grantham", "lincoln", "nottingham"])

    def test_a_build_that_priced_nothing_removes_every_station_folder(self) -> None:
        # No station route in the manifest means no station page is part of
        # this release, so none may be left behind to be reached by URL.
        self._build("--all-origins")
        (self.site / build_demo_page.RELEASE_MANIFEST_NAME).write_text(
            json.dumps({"basePath": "", "routes": ["/", "/privacy/"]}), encoding="utf-8"
        )
        self.assertEqual(self._tidy(), ["grantham", "lincoln", "nottingham"])
        self.assertEqual(self._station_folders(), [])


class ReturnNetworkFixtureTest(unittest.TestCase):
    """The optional block that gives the secondary origins a real network.

    The browser suite drives every station page a build writes, so a station
    with one priced destination turns most of the page's checks into skips.
    These assert the block produces what those checks need, from the feed's own
    data rather than from a flag the page reads.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.feed = Path(self.tmp) / "feed"
        build_synthetic_feed(
            self.feed,
            include_restrictions=True,
            include_third_origin=True,
            include_return_network=True,
        )
        build_synthetic_timetable(self.feed, include_return_network=True)
        self.fares = FaresDb().load_feed(self.feed)
        self.timetable = TimetableDb().load_feed(self.feed)

    def test_the_base_fixture_is_unchanged_without_the_flag(self) -> None:
        # Every parser test counts records, so the block has to stay opt-in.
        plain = Path(self.tmp) / "plain"
        build_synthetic_feed(plain, include_restrictions=True)
        build_synthetic_timetable(plain)
        base = FaresDb().load_feed(plain)
        for crs in ("MAT", "RET", "SLD", "LEC"):
            self.assertNotIn(crs, base.locations_by_crs)
        plain_timetable = TimetableDb().load_feed(plain)
        for tiploc in ("MATL", "SLDK", "LEIC"):
            self.assertIsNone(plain_timetable.crs_for_tiploc(tiploc))

    def test_both_secondary_origins_price_more_than_one_destination(self) -> None:
        for origin in ("LCN", "NOT"):
            fares = build_demo_page.build_payload(self.fares, self.timetable, origin)
            self.assertGreater(
                len(fares["anytimeDestinations"]), 1, f"{origin} prices too few to exercise the page"
            )

    def test_the_set_carries_a_heritage_row_a_small_town_and_a_seaside_town(self) -> None:
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        with_heritage = [row for row in payload["anytimeDestinations"] if row["heritageSites"]]
        self.assertTrue(with_heritage, "no destination carries a UNESCO property")
        types = {t for row in payload["anytimeDestinations"] for t in row["destinationTypes"]}
        self.assertIn("small_town", types)
        self.assertIn("seaside", types)

    def test_some_fares_sit_above_the_railcard_minimum_and_some_below(self) -> None:
        # Both directions matter: a card with nothing to discount cannot be
        # exercised, and a card that discounts every fare cannot show what the
        # page does with one it does not beat.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        prices = [row["adultPence"] for row in payload["anytimeDestinations"]]
        self.assertTrue(any(p > 1200 for p in prices), "nothing is above the £12.00 minimum")
        self.assertTrue(any(p < 1200 for p in prices), "nothing is below the £12.00 minimum")
        self.assertGreater(payload["railcardEligibleCount"], 0)

    def test_one_destination_is_priced_and_never_served(self) -> None:
        # The shape the page's "no service" row exists to report.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        states = {row["journeyState"] for row in payload["anytimeDestinations"]}
        self.assertIn("found", states)
        self.assertTrue(
            any(state != "found" for state in states),
            f"every destination has a journey: {states}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
