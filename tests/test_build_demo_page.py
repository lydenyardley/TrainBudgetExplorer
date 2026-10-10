"""Tests for the demo page generator: its content, its payload and its prose.

The runner, the publication gates, the caches and the files a build writes have
modules of their own beside this one (F6 of the 8 October 2026 agent-efficiency
audit); this file holds what the page says."""

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
import argparse

import build_demo_page
from build_demo_page import DEFAULT_PRICE_SOURCE, NOTICES, notices_or_attribution
from atoc_fares import FLOW_F, FLOW_T, TICKET_TYPE, FaresDb
from atoc_timetable import TimetableDb
from build_demo_page import nre_attribution, wants_nre_credit, build_payload, build_station_index, explain_unpriced, render_chooser, render_page, render_privacy, station_slug
from make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_timetable
from retailer import DISCLOSURE

from tests.page_harness import embedded_payload, page_markup, page_script, serialised_callback_lines, setUpModule, station_page, tearDownModule


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
        self.assertIn('railcardSelect.addEventListener("change", () => {', self.html)
        self.assertIn("'input[name=\"ticketMode\"]')) radio.addEventListener(\"change\", () => { currentPage = 1; render(); writeUrl(); })", self.html)
        # The title is the heading's sentence, so a reader with two tabs open
        # can tell the two searches apart.
        self.assertIn('document.title = "Train fares up to £" + budgetNumber.value + " from " + DATA.origin.name;', self.html)

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
        self.assertIn("<b>station name</b>", self.html)
        # The note is half of the opening sentence rather than a
        # paragraph of its own: the page's promise and the one thing a
        # reader cannot guess are read together, not two blocks apart.
        self.assertLess(
            self.html.index('id="pageIntro"'),
            self.html.index('id="firstUse"'),
        )
        self.assertIn("</span></p>", self.html)

    def test_a_picker_option_carries_the_readers_search(self) -> None:
        # S06: changing origin corrects where they leave from, not the search
        # they have already made, and the picker writes the same query the
        # address does rather than a second, drifting copy of it.
        self.assertIn('link.href = station.href + "?" + stateQuery();', self.html)

    def test_the_page_states_where_a_split_ticket_would_split(self) -> None:
        # The other half of Q2: the sentence that states the possibility, in
        # the panel where the fare's condition already sits, and no price for
        # either half. The browser suite drives the live row.
        self.assertIn("function splitNote(destination)", self.html)
        self.assertIn("destination.changeStations || []", self.html)
        self.assertIn('note.className = "split"', self.html)
        # The station itself is named in the Changes column now, so the
        # panel says only what is still worth saying and is nowhere else.
        self.assertIn("one ticket to the station above", self.html)
        self.assertIn('line.className = "interchange"', self.html)
        self.assertIn('"via " + stations.map((station) => station.name)', self.html)
        self.assertIn("can sometimes cost less than this through fare", self.html)
        self.assertIn("This page prices the through fare only.", self.html)

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
        # NOT's CDR fare is the one the fixture's RR 0001 bans for this card,
        # so it carries a state and no price.
        self.assertEqual(rows["NOT"]["railcards"]["YNG"]["state"], "blocked")
        self.assertIsNone(rows["NOT"]["railcards"]["YNG"]["pricePence"])
        self.assertEqual(rows["PBO"]["railcards"]["YNG"]["pricePence"], 1490)
        self.assertEqual(rows["NOT"]["partyPence"], 2320)
        self.assertEqual(rows["NOT"]["minutes"], 45)
        self.assertEqual(rows["NOT"]["changes"], 0)

    def test_single_mode_prices_the_walk_up_single_not_the_advance_ticket(self) -> None:
        # The single list used to lead with a 100p advance fare because it was
        # the cheapest number in the feed, which told a reader Grantham to
        # Nottingham cost £1.00 when that price belonged to one named train.
        # The list now prices the walk-up single, and says so.
        row = next(row for row in self.payload["singleDestinations"] if row["crs"] == "NOT")
        self.assertEqual(row["adultPence"], 700)
        self.assertEqual(row["ticket"], "SDS")
        self.assertFalse(row["isAdvance"])
        self.assertEqual(row["quality"], "outbound single")

    def test_no_published_row_is_priced_as_a_train_specific_advance_fare(self) -> None:
        # The rule is about every row on every page, not one fixture's one
        # destination: a train-restricted fare reaching any published list is
        # the failure, whatever it is called and whatever it costs.
        for key in ("destinations", "singleDestinations", "anytimeDestinations"):
            for row in self.payload[key]:
                self.assertFalse(
                    row["isAdvance"],
                    f'{key} publishes {row["crs"]} as an advance fare at {row["adultPence"]}p',
                )

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

    def test_a_nature_destination_carries_its_named_reserve(self) -> None:
        # The synthetic GRN page has no ATB row; the builder still stamps the
        # field on every destination, and the page template names the proof.
        from atoc_fares import FaresDb, Location

        for row in self.payload["destinations"]:
            self.assertIn("natureSites", row)
            self.assertEqual(row["natureSites"], [])
        self.assertIn("Nature sites: ", self.html)
        self.assertIn("destination.natureSites", self.html)
        db = FaresDb()
        db.locations_by_crs = {"ATB": Location("7100", "ATB", "ATTENBOROUGH", "")}
        db.location_facets_by_crs = {"ATB": {"nature"}}
        self.assertEqual(
            db.nature_sites("ATB"),
            [{
                "name": "Attenborough Nature Reserve",
                "url": "https://www.nottinghamshirewildlife.org/attenborough-plan-your-visit",
            }],
        )

    def test_a_coastal_destination_carries_its_named_day_out(self) -> None:
        from atoc_fares import FaresDb, Location

        for row in self.payload["destinations"]:
            self.assertIn("coastalSites", row)
        self.assertIn("Coastal & seaside: ", self.html)
        self.assertIn("destination.coastalSites", self.html)
        db = FaresDb()
        db.locations_by_crs = {"SKG": Location("8200", "SKG", "SKEGNESS", "")}
        db.location_facets_by_crs = {"SKG": {"seaside"}}
        self.assertEqual(
            db.coastal_sites("SKG"),
            [{
                "name": "Skegness Beach",
                "url": "https://www.visitlincolnshire.com/destinations/skegness/",
            }],
        )
        # LCN is not a coastal proof CRS; without the seaside facet it stays empty.
        self.assertEqual(self.fares.coastal_sites("LCN"), [])

    def test_the_three_day_out_chips_name_their_own_proof(self) -> None:
        # ADR-0064's rule, applied to the sources ADR-0065 shipped: the chip is
        # only honest if the row can name the place behind it. Two halves, and
        # both are checked here because either alone looks like it works -- a
        # payload field with no reader renders no proof, and a reader with no
        # field renders an undefined one.
        for label, key in (
            ("RSPB reserves: ", "destination.rspbSites"),
            ("National Trust: ", "destination.nationalTrustSites"),
            ("National parks and landscapes: ", "destination.nationalParkSites"),
        ):
            self.assertIn(label, self.html)
            self.assertIn(key, self.html)


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


    def test_the_page_opens_on_the_cheapest_fare_of_any_type(self) -> None:
        # Q4: the list that opens is the cheapest fare of any ticket type, and
        # the three named sets survive as filters beside it. The checked radio
        # is what a reader arrives in, which is the part PRODUCT.md promises,
        # so the checked one is asserted rather than only present.
        self.assertIn('<input type="radio" name="ticketMode" value="cheapest" checked>', self.html)
        for other in ("anytime", "return", "single"):
            self.assertIn('<input type="radio" name="ticketMode" value="%s">' % other, self.html)
            self.assertNotIn('value="%s" checked' % other, self.html)
        script = page_script(self.html)
        self.assertIn('const CHEAPEST_MODE = "cheapest";', script)
        # Composed in the page, so it costs no payload bytes, and one row per
        # destination: the cheaper of the fares that destination is priced at.
        composition = script.split("function cheapestDestinations()")[1].split("\nfunction ")[0]
        self.assertIn("new Map()", composition)
        self.assertIn("for (const key of Object.values(MODE_LISTS))", composition)
        self.assertIn("cheapest.set(destination.crs, destination)", composition)
        # What decides a row is the price for this reader, card included, and
        # an equal price is broken on the fare's own standard. Both halves are
        # asserted rather than one literal comparison, because the comparison
        # moved into a helper and the rule is what has to hold.
        self.assertIn("isCheaperThan(destination, held)", composition)
        ranker = script.split("function isCheaperThan(")[1].split("\nfunction ")[0]
        self.assertIn("priceOf(candidate)", ranker)
        self.assertIn("priceOf(held)", ranker)
        self.assertIn("return price < other;", ranker)
        self.assertIn("standardPrice(candidate) < standardPrice(held)", ranker)
        # Without the tie-break, a card that made two fares equal swapped the
        # row and the cell named a standard fare the reader had not been shown.
        standard = script.split("function standardPrice(")[1].split("\nfunction ")[0]
        self.assertIn('unit() === "party" ? destination.partyPence : destination.adultPence', standard)
        active = script.split("function activeDestinations()")[1].split("\nfunction ")[0]
        self.assertIn("if (mode === CHEAPEST_MODE) return cheapestDestinations();", active)
        counted = script.split("function modeCount(")[1].split("\nfunction ")[0]
        self.assertIn("if (mode === CHEAPEST_MODE) return cheapestDestinations().length;", counted)
        # Which row is cheapest depends on the card, so the list is composed
        # after the card is settled -- the card arriving a line later would
        # leave one render showing a list of the wrong rows.
        order = script.split("function render(")[1].split("\nfunction ")[0]
        self.assertLess(order.index("syncRailcardParty();"), order.index("const available = activeDestinations();"))

    def test_the_count_line_names_the_mix_and_what_the_party_is_two_of(self) -> None:
        script = page_script(self.html)
        words = script.split("const MIX_WORDS = {")[1].split("};")[0]
        self.assertIn('"outbound single": "single"', words)
        self.assertIn('"unrestricted Anytime Day Return": "Anytime Day Return"', words)
        mix = script.split("function mixPhrase(")[1].split("\nfunction ")[0]
        self.assertIn("MIX_WORDS[destination.quality] || \"return\"", mix)
        # Named even when the list is one kind of fare, which is the case it
        # exists for: a list of nothing but singles says so.
        self.assertIn('if (!counts.size) return "";', mix)
        summary = script.split("const what = unit()")[1].split("\nfunction ")[0]
        self.assertIn('"for the two of us, two of the fare each row names"', summary)
        self.assertIn('const mix = ticketMode() === CHEAPEST_MODE ? mixPhrase(wanted) : "";', summary)
        self.assertIn("+ order + mix", summary)
        # A row in this list names its own fare, and every place a price is
        # carried off the page reads the same answer: the handoff to a
        # seller, the shortlist row, and the copied list. One helper, because
        # a shortlist that named a different fare from the count line beside
        # it would be the page disagreeing with itself.
        self.assertIn("function ticketName(destination)", script)
        fare = script.split("function fareName(")[1].split("\nfunction ")[0]
        self.assertIn(
            "ticketMode() === CHEAPEST_MODE ? ticketName(destination) : modeLabels()[ticketMode()]",
            fare,
        )
        journey = script.split("function journeyText")[1].split("\nfunction ")[0]
        self.assertIn('"Ticket: " + fareName(destination)', journey)
        # A price with no ticket beside it is the one thing a reader holding
        # the list cannot act on, so the shortlist names the fare on the row
        # and on every copied line, beside the price rather than in a footer.
        # The chip carries the name and the price -- the reason the place is
        # there -- and the fare name travels in the copied text and on the
        # row itself rather than making every chip three lines tall.
        row = script.split("function dockRow(")[1].split("\nfunction ")[0]
        self.assertIn('price.textContent = money(priceOf(destination));', row)
        self.assertNotIn("fareName(destination)", row)
        copied = script.split("function shortlistText()")[1].split("\nfunction ")[0]
        self.assertIn(r'" " + what + ", " + fareName(destination) + ", " + time', copied)
        # The set names itself above the table, in the coverage line and in the
        # provenance line, so no sentence on the page counts the wrong fares.
        self.assertIn('cheapest: "Each row is the cheapest fare of any ticket type', script)
        self.assertIn("each on the cheapest fare of any ticket type the feed prices for it", script)
        self.assertIn('cheapest: "destinations, each on its cheapest fare of any ticket type, in the feed"', script)

    def test_the_warn_token_clears_aa_where_the_cheapest_rows_put_it(self) -> None:
        # The cheapest list leads with restricted and advance fares, whose words
        # and marks are the warn token on the row panel's tint, and the browser
        # matrix holds every kind of text to 4.5:1. The token this replaced came
        # to 4.36:1 there -- measured here rather than asserted, so the number in
        # the stylesheet comment and the number in the test cannot drift apart.
        import re

        def channel(value: float) -> float:
            v = value / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        def luminance(rgb) -> float:
            r, g, b = rgb
            return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

        warn_hex = re.search(r"--warn: (#[0-9a-f]{6});", self.stylesheet)
        self.assertIsNotNone(warn_hex, "no light --warn token in the shared block")
        tint = re.search(r"--best:\s*rgba\((\d+), (\d+), (\d+), (\.\d+)\)", self.stylesheet)
        self.assertIsNotNone(tint, "no --best tint in the shared block")
        self.assertIn("tr.detail td { background: var(--best);", self.stylesheet)
        warn = tuple(int(warn_hex.group(1)[i:i + 2], 16) for i in (1, 3, 5))
        alpha = float(tint.group(4))
        panel = tuple(int(part) * alpha + 255 * (1 - alpha) for part in tint.groups()[:3])
        lighter, darker = sorted((luminance(warn), luminance(panel)), reverse=True)
        ratio = (lighter + 0.05) / (darker + 0.05)
        self.assertGreaterEqual(ratio, 4.5, "%s on the row panel is %.2f:1" % (warn_hex.group(1), ratio))

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
        self.assertIn('readable.textContent = destination.restrictionDescription ||', self.html)
        self.assertIn('if (restricted) {', self.html)
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
        # buy, so a card whose own feed record does not cover the party on
        # screen is taken out of the list rather than left there to be picked.
        # The bounds come from the feed, not from this project.
        card = self.payload["railcards"][0]
        # The bounds are each card's own, measured on the real feed on
        # 1 October 2026, so the party filter has something to take out.
        bounds = {c["key"]: (c["minAdults"], c["maxAdults"]) for c in self.payload["railcards"]}
        self.assertEqual(bounds["YNG"], (1, 8))
        self.assertEqual(bounds["2TR"], (2, 2))
        self.assertEqual(bounds["BB2"], (1, 1))
        self.assertIn("function syncRailcardParty()", self.html)
        self.assertIn("function cardCoversParty(card)", self.html)
        self.assertIn("return card.minAdults <= adults && adults <= card.maxAdults;", self.html)
        self.assertIn("railcardSelect.disabled = offered.length === 0;", self.html)
        self.assertIn('"The " + chosen.label + " in this feed covers "', self.html)
        # A card code arriving on a link is applied only when this page prices
        # it, so a link naming a card this origin has no fares for does not
        # read as a card the reader holds.
        self.assertIn('const wanted = state.railcard && railcards[state.railcard] ? state.railcard : "";',
                      self.html)

    def test_a_row_states_its_condition_and_folds_the_feed_record_away(self) -> None:
        # S19: the condition a reader can act on sits beside the price; the
        # ticket, restriction and route codes are one disclosure away.
        self.assertIn("function feedRecord(destination)", self.html)
        self.assertIn('readable.className = "condition"', self.html)
        # An unrestricted fare used to open with a second paragraph saying
        # there was nothing to read, which is the same information as
        # silence said in a line.
        self.assertIn("with no conditions in the feed.", self.html)
        self.assertNotIn("No travel conditions on this fare in the feed.", self.html)
        row = next(row for row in self.payload["destinations"] if row["crs"] == "NOT")
        self.assertEqual(row["routeCode"], "00000")
        self.assertEqual(row["restrictionCode"], "1A")

    def test_a_missing_journey_is_typed_rather_than_a_dash(self) -> None:
        # S23: three different absences, three different sentences.
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["NOT"]["journeyState"], "found")
        self.assertEqual(rows["SLP"]["journeyState"], "no_service")
        # The cell reads the chosen day, not the build's own answer: the Time
        # and Changes columns report whichever day the reader picked, so the
        # absence beside them has to be worded for that day too.
        self.assertIn(
            "cell.textContent = missing ? dayAbsenceText(destination, true) : duration(journey.minutes);",
            self.html,
        )
        # Every absence is worded in one table on the page, from the key, the
        # day the build asked about and the day the row next runs. There is no
        # other place an absence can be worded, so there is no sentence that
        # can name no day: a bare "No service" beside a station the network
        # serves reads as a fact about the station.
        self.assertIn("const JOURNEY_ABSENCE = {", self.html)
        for key in ("no_timetable", "no_service"):
            self.assertIn(f"  {key}: (day, later) => ({{", self.html)
        self.assertIn("function absenceText(destination, brief) {", self.html)
        # A row this build holds no week for keeps the build's own wording, so
        # the brief form is still reachable from the day-aware reader rather
        # than only from the long one.
        self.assertIn("if (answer === undefined) return absenceText(destination, brief);", self.html)
        # And the wording has no branch that leaves the day out.
        self.assertNotIn('return "No service";', self.html)
        # The change count is a word rather than a digit, and the station it
        # changes at sits under it in the column whose header says Changes.
        self.assertIn("function changeCount(changes)", self.html)
        self.assertIn('if (changes === 0) return "Direct";', self.html)
        self.assertIn(
            'return changes === 1 ? "1 change" : changes + " changes";', self.html
        )
        self.assertIn('count.textContent = missing ? "Unknown" : changeCount(journey.changes);', self.html)
        prices_only = build_payload(self.fares, None, "GRN")
        self.assertEqual(
            next(row for row in prices_only["destinations"] if row["crs"] == "LCN")["journeyState"],
            "no_timetable",
        )
        dated = build_payload(self.fares, self.timetable, "GRN", day=date(2026, 9, 28))
        # Tower Hill has a fare and no train, so the row names the week the build
        # asked as well as the day: a reader who cannot reach either date is
        # owed that, and the old sentence stopped at the day.
        unserved = next(row for row in dated["destinations"] if row["crs"] == "SLP")
        self.assertEqual(unserved["journeyState"], "no_service")
        self.assertEqual(dated["serviceDate"], "2026-09-28")
        self.assertEqual(dated["serviceHorizon"], 7)
        self.assertNotIn("nextService", unserved)

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
            "railcardSelect.addEventListener",
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

    def test_no_page_callback_carries_a_doubled_escape(self) -> None:
        # A regex literal inside a page.evaluate callback is parsed twice, and
        # a doubled escape survives the second parse as a literal backslash:
        # the word boundary the suite wrote becomes a backslash that matches
        # nothing, and the check quietly stops being able to pass. That is not
        # a hypothetical. It is how "a feed with a download date says how old
        # its prices are" came to fail on every real build while printing a
        # correct sentence -- the demo feed carries no download date, so the
        # branch was dead in CI and the escape was never read by a browser.
        # A single escape is fine and is used; only the doubled kind is refused,
        # and a deliberate literal-backslash matcher is listed rather than
        # tolerated, so the exception is visible instead of assumed.
        suite = (Path(__file__).resolve().parent / "browser_test.cjs").read_text(encoding="utf-8")
        deliberate = set()
        doubled = chr(92) * 2
        for line in serialised_callback_lines(suite):
            if doubled in line and line.strip() not in deliberate:
                self.fail(f"a doubled escape inside a page callback: {line.strip()}")

    def test_no_escape_that_html_cannot_read_reaches_the_page(self) -> None:
        # The same family as the doubled escape above, and the same reason for
        # a test: a backslash escape is read in a script and is only text
        # everywhere else, so the mistake is invisible in the source and
        # visible in the product. The theme switch's moon was written as the
        # escape the script beside it needs, and shipped as the five
        # characters it is in markup. Both halves are checked: no escape in
        # the markup, and none in CSS either, where a \uXXXX sequence is not the
        # escape the author meant.
        escape = re.compile(r"\\u[0-9a-fA-F]{4}")
        marker = chr(92) + "u"
        features = build_demo_page.site_features(
            analytics=False, link_mode="fallback", network=None, disclosure=None
        )
        pages = {
            "station": self.html,
            "chooser": build_demo_page.render_chooser([], budget_pounds=20),
            "privacy": build_demo_page.render_privacy("note", "", "a@b.test", features),
        }
        for name, page in pages.items():
            markup = re.sub(r"<script\b.*?</script>", "", page, flags=re.DOTALL | re.IGNORECASE)
            for match in escape.finditer(markup):
                self.fail(
                    f"{name} states a script escape in its markup: "
                    f"{markup[max(0, match.start() - 40):match.end() + 10]!r}"
                )
            styles = " ".join(
                re.findall(r"<style\b.*?</style>", page, flags=re.DOTALL | re.IGNORECASE)
            )
            self.assertNotIn(marker, styles, f"{name} writes an escape CSS does not read")
        # And the one drawn character in the chrome is that character, so a
        # reader sees a moon rather than a backslash on whichever route they
        # opened.
        self.assertIn("&#9790;", self.html)

    def test_the_freshness_claim_is_judged_against_the_builds_own_date(self) -> None:
        # The suite reports the page's own feedDate and judges the sentence
        # beside it in node, so the age on the page is compared with the age
        # the page should have printed rather than merely looked for. A page
        # claiming "downloaded 24 September 2026" beside a stale "0 days old"
        # passes a presence test and misleads the reader this sentence exists
        # for, which is the reader deciding whether to trust a fare.
        suite = (Path(__file__).resolve().parent / "browser_test.cjs").read_text(encoding="utf-8")
        self.assertIn("feedDate: DATA.feedDate || null,", suite)
        self.assertIn("daysSince(fresh.feedDate)", suite)
        self.assertIn("a feed with a download date says how old its prices are", suite)

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
            self.assertIn(build_demo_page.ISSUE_TRACKER, privacy)
            contact = privacy.split("<h2>Contact</h2>", 1)[1].split("</p>", 1)[0]
            self.assertNotRegex(contact, r"[\w.+-]+@[\w.-]+")

    def test_the_project_contact_is_flagged_for_review_before_publication(self) -> None:
        # Naming the issue tracker is not the same thing as somebody reading it.
        # The review has to stay an open box until that confirmation is written
        # down where the person who publishes will read it.
        self.assertNotIn("@", build_demo_page.DEFAULT_PRIVACY_CONTACT)
        self.assertIn(build_demo_page.ISSUE_TRACKER, build_demo_page.DEFAULT_PRIVACY_CONTACT)
        root_dir = Path(__file__).parent.parent
        checklist = (root_dir / "docs" / "publish-checklist.md").read_text(encoding="utf-8")
        self.assertIn(build_demo_page.ISSUE_TRACKER, checklist)
        box = [
            line
            for line in checklist.splitlines()
            if "monitored contact route exists" in line
        ]
        self.assertEqual(len(box), 1, f"expected one review box, found {box}")
        self.assertTrue(box[0].startswith("- [ ] "), box[0])

    def test_a_shortlist_is_a_list_of_places_and_not_a_booking(self) -> None:
        # S26: the decision the page exists for is which place, so a reader can
        # keep a few, compare them on the price currently shown, and hand the
        # list to somebody else as a link. Nothing about it implies a booking.
        self.assertNotIn('id="shortlistBar"', self.html)
        self.assertIn("not a booking", self.html)
        # One control per row, and it is a checkbox rather than a button:
        # ADR-0054 put a single select above the table in place of twenty
        # buttons, and the reader asked for the control back on each row. What
        # is being kept from that decision is the part it was right about --
        # no twenty copies of the same word, and no control whose text changes
        # when it is pressed.
        self.assertNotIn('id="shortlistPick"', self.html)
        self.assertNotIn("function renderShortlistPicker()", self.html)
        self.assertNotIn("shortlist-toggle", self.html)
        self.assertIn("function holdCell(destination)", self.html)
        self.assertIn('box.type = "checkbox"', self.html)
        self.assertIn('box.setAttribute("aria-label", "List "', self.html)
        # The column the boxes live in is a column of the header too, or the
        # table has a cell with no heading above it.
        self.assertIn('<th scope="col" class="hold">List</th>', self.html)
        from page_templates import STATION_STYLESHEET

        self.assertIn(
            "th.hold, td.hold { width: 1%; white-space: nowrap; padding-left: .2rem; text-align: center; }",
            STATION_STYLESHEET,
        )
        self.assertIn(
            "const cells = [holdCell(destination), stationCell(destination), priceCell(destination)];",
            self.html,
        )
        # ... and the places it holds, and every control for the list, are in
        # the one place the list is drawn: the dock at the foot of the screen.
        self.assertIn('id="shortlistCopy"', self.html)
        self.assertIn('id="shortlistShareBox"', self.html)
        self.assertIn('id="shortlistDockClear"', self.html)
        dock = self.html.split('<aside class="shortlist-dock"', 1)[1].split("</aside>", 1)[0]
        for control in ("shortlistCopy", "shortlistShareBox", "shortlistDockClear", "shortlistBox"):
            self.assertIn(f'id="{control}"', dock)
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
        # Said on the page as well as to the status region: a control that
        # stops responding with no explanation is the one thing a reader
        # cannot act on, and the strip is where they are already looking.
        self.assertIn(
            'const message = "The shortlist holds " + SHORTLIST_LIMIT + " places. Remove one to add another.";',
            self.html,
        )
        self.assertIn(
            "if (shortlistLimit) shortlistLimit.textContent = message;", self.html
        )
        # The control is on every row, and what it shows is the list rather
        # than a copy of itself: the box is ticked from what is held, so a row
        # rebuilt by a render cannot claim a place is held when it is not.
        self.assertIn("box.checked = inShortlist(destination.crs);", self.html)
        # Every box is put back from the list in one place, and it is that one
        # place which makes a row's own handler unnecessary: clearing the list
        # emptied the strip and the dock and left every row still ticked, because
        # nothing but the click handler ever put the boxes back.
        self.assertIn(
            'for (const box of document.querySelectorAll("#rows input.hold-box")) {',
            self.html,
        )
        self.assertIn("if (row) box.checked = inShortlist(row.dataset.crs);", self.html)
        self.assertIn("const SHORTLIST_LIMIT = 8;", self.html)

    def test_a_published_page_survives_a_moment_s_locked_by_a_reader(self) -> None:
        # A full-network build is hours long and publishes thousands of
        # files. Windows refuses to replace a file anything else holds open,
        # and the build that measured the whole network died that way at page
        # 77 of 2,712, holding 76 finished pages: an indexer, a virus scanner
        # or a person reading the resume file is enough. The lock lasts
        # milliseconds, so the replace waits for it rather than ending the
        # build.
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "from" / "grantham" / "index.html"
            build_demo_page.write_page_atomic(page, "<p>first</p>")
            self.assertEqual(page.read_text(encoding="utf-8"), "<p>first</p>")
            # What a lock looks like from inside: the replace raises twice,
            # then succeeds, and the page is published.
            real_replace = Path.replace
            calls = {"n": 0}

            def locked(self, target):
                calls["n"] += 1
                if calls["n"] < 3:
                    raise PermissionError(13, "used by another process")
                return real_replace(self, target)

            with mock.patch.object(Path, "replace", locked):
                build_demo_page.write_page_atomic(page, "<p>second</p>")
            self.assertEqual(calls["n"], 3)
            self.assertEqual(page.read_text(encoding="utf-8"), "<p>second</p>")
            # A lock that never clears is still an error an operator has to
            # see, rather than a page silently left unwritten.
            def never(self, target):
                raise PermissionError(13, "used by another process")

            with mock.patch.object(Path, "replace", never):
                with self.assertRaises(PermissionError):
                    build_demo_page.replace_published(
                        page.with_name("x.tmp"), page, attempts=1
                    )

    def test_railcard_pricing_is_available_from_the_feed(self) -> None:
        # R9 is the railcard's travel condition, not a total ban, so the
        # synthetic fares that carry it remain eligible.
        cards = {card["key"]: card for card in self.payload["railcards"]}
        # All six reviewed cards, with the party each one prices. The
        # fixture used to carry a single card under a code that is not in
        # the reviewed set at all, so the control built to offer six came
        # out with one option in it.
        self.assertEqual(
            list(cards),
            ["YNG", "DIS", "NEW", "SRN", "BB2", "2TR"],
            "the demo feed prices the six reviewed cards",
        )
        self.assertEqual((cards["2TR"]["minAdults"], cards["2TR"]["maxAdults"]), (2, 2))
        self.assertEqual(cards["YNG"]["label"], "16-25 Railcard")
        # Two of the five fares sit on route 00002, which the fixture's RR 0001
        # bans for this card outright. The remaining three are discounted.
        self.assertEqual(cards["YNG"]["eligibleCount"], 3)
        refused = [
            row
            for row in self.payload["destinations"]
            if row["railcards"]["YNG"]["state"] == "blocked"
        ]
        self.assertEqual([row["crs"] for row in refused], ["NOT"], "the total ban refuses the CDR fare")
        self.assertIsNone(refused[0]["railcards"]["YNG"]["pricePence"])
        # A refused fare keeps its standard price rather than showing a
        # discount the feed will not honour.
        self.assertEqual(refused[0]["adultPence"], 1160)
        # LCN's £8.70 SDR fare is not counted either, and for the opposite
        # reason: the card's £12.00 minimum is higher than the discounted fare,
        # so the card raises this price rather than lowering it.
        raised = next(r for r in self.payload["destinations"] if r["crs"] == "LCN")
        self.assertEqual(raised["railcards"]["YNG"]["pricePence"], 1200)
        self.assertGreater(raised["railcards"]["YNG"]["pricePence"], raised["adultPence"])
        self.assertIn("No railcard is selected", self.payload["railcardNote"])
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
        self.assertEqual(rows["NOT"]["railcards"]["YNG"]["pricePence"], 770)
        cards = {card["key"]: card for card in payload["railcards"]}
        self.assertEqual(cards["YNG"]["eligibleCount"], 4)
        self.assertIn("discounted by a third", payload["railcardNote"])

    def test_each_destination_exposes_its_exact_railcard_decision(self) -> None:
        row = next(row for row in self.payload["destinations"] if row["crs"] == "PBO")
        details = row["railcards"]["YNG"]
        self.assertEqual(details["state"], "eligible")
        rule = self.payload["railcardRules"][details["rule"]]
        self.assertIn("RR", rule["text"])
        self.assertIn("16-25 Railcard", rule["text"])
        self.assertEqual(rule["restrictionCode"], "R9")
        # RR 0002 rather than 0001: 0001 is a total ban on route 00002, and this
        # row is not on that route. A restriction code attached to a fare is a
        # travel condition, not a refusal, which is what keeps the row eligible.
        self.assertEqual(rule["sequence"], "0002")
        self.assertFalse(rule["totalBan"])
        self.assertEqual(details["pricePence"], 1490)
        self.assertEqual(
            details["minimumFarePence"],
            self.fares.minimum_fare("YNG", row["ticket"]),
        )
        # The refused fare names the rule that refused it, so the drawer can say
        # which DTD record did it rather than only that it did not apply.
        refused = next(r for r in self.payload["destinations"] if r["crs"] == "NOT")
        ban = self.payload["railcardRules"][refused["railcards"]["YNG"]["rule"]]
        self.assertTrue(ban["totalBan"])
        self.assertEqual(ban["sequence"], "0001")
        # The explanation is one paragraph in the row's own disclosure.
        # A dialog on every row, opened on top of a page the reader was
        # already reading, to be told a number the row beside it carried.
        self.assertIn("function cardNote(destination)", self.html)
        self.assertIn("panel.append(card)", self.html)
        self.assertIn("DATA.railcardRules[details.rule]", self.html)
        self.assertIn("travel condition rather than a card ban", self.html)
        self.assertNotIn('id="railcardDrawer"', self.html)
        # The exact rule is still on the page, filed with the codes it is
        # a record of rather than headlined in a panel of its own.
        self.assertIn("function railcardRuleFor(destination)", self.html)
        self.assertIn('add("Railcard rule", rule)', self.html)

    def test_the_railcard_note_never_names_a_price_above_the_row(self) -> None:
        # The row is priced at the cheaper of the standard fare and the card's.
        # The card's own price used to be printed under the label "Discounted
        # fare", so on a fare whose card minimum is above the discount it
        # showed GBP 12.00 against a row showing GBP 8.70, and called the
        # bigger number a discount.
        row = next(r for r in self.payload["destinations"] if r["crs"] == "LCN")
        card = row["railcards"]["YNG"]
        self.assertEqual(row["adultPence"], 870)
        self.assertEqual(card["pricePence"], 1200)
        shown = min(row["adultPence"], card["pricePence"])
        self.assertEqual(shown, 870)
        self.assertLessEqual(shown, row["adultPence"], "a card never raises a row's price")
        # The note never quotes a number at all, so it cannot quote one
        # above the row: it names the card, says whether the card lowers
        # the fare, and gives the card's own price and the standard fare as
        # two labelled figures a reader can compare.
        self.assertIn("const cardBeatsStandard =", self.html)
        self.assertIn("details.pricePence < destination.adultPence", self.html)
        self.assertIn("does not reduce it", self.html)
        self.assertIn("This row is priced at the cheaper of the two", self.html)
        # The note leads with the figure in the row. It used to lead with the
        # card's own price, which on a real page is the DTD minimum and is
        # routinely the larger number: a reader looking at a £2.70 fare was
        # shown £12.00 first and had to work out which one was theirs.
        # priceOf() is what the Price cell renders, so the two cannot disagree.
        self.assertIn('"This fare is " + money(priceOf(destination)) + ", and "', self.html)
        self.assertLess(
            self.html.index('"This fare is " + money(priceOf(destination))'),
            self.html.index('money(details.pricePence) + " per adult, because the minimum fare'),
            "the note must open with the row's price, not with the card's",
        )
        # The minimum is named as what it is, in the branch where the card
        # does help, rather than as a discount that made the fare dearer.
        self.assertIn("is the price here, so the discount took it no lower.", self.html)
        self.assertIn("does not raise it.", self.html)

    def test_the_two_ticket_note_adds_the_minimums_rather_than_calling_one_per_ticket(self) -> None:
        # A two-ticket row's card price is the two card fares added, and the
        # minimum the note names beside it is the two minimums added. The sum is
        # the pair's own total: reading it as a per-ticket figure would quote
        # 24.00 as the floor on each of two 12.00 tickets.
        self.assertIn(
            "with the feed's minimum fares on the two tickets adding to", self.html
        )
        self.assertNotIn("applied per ticket", self.html)

    def test_the_railcard_note_names_the_card_it_is_about(self) -> None:
        # The reader picked one card out of six, so the note has to name it.
        # A note that explained "the railcard" while the page listed six would
        # answer a question nobody asked.
        # The label is read from the variable, not spelled out, so the test
        # reads the variable and the two sentences the note branches into.
        self.assertIn("const card = railcards[railcardSelect.value];", self.html)
        # The card is named by the variable, and the sentence is split across
        # two lines of source with the label at the end of the first, so the
        # test reads the two halves rather than a sentence that no line holds.
        self.assertIn('+ ", and " + card.label +', self.html)
        self.assertIn('" does not reduce it.', self.html)
        self.assertIn('card.label + " cannot be applied to this fare.', self.html)
        # With no card chosen there is nothing to explain, so there is no
        # paragraph: the control above already says the prices are standard,
        # and a sentence on every expanded row repeating the page's default
        # is the noise this replaced.
        self.assertIn(
            "if (noCard() || !railcards[railcardSelect.value]) return null;", self.html
        )
        self.assertIn(
            '      "This feed prices no " + card.label + " fare to " + destination.name +',
            self.html,
        )

    def test_a_card_whose_minimum_is_higher_shows_the_standard_fare(self) -> None:
        # LCN's SDR fare is £8.70. The card's discounted price would be £5.80,
        # and the feed's £12.00 minimum is higher than that, so the card's own
        # price for this fare is dearer than travelling without it. The reader is
        # never charged the higher figure, because the page prices a row at the
        # cheaper of the standard fare and the card's, and the count of
        # discounted destinations leaves this fare out either way. What the
        # drawer has to say is that the minimum is higher, so a reader who opens
        # it does not read a "discount" that does not apply to this fare.
        row = next(r for r in self.payload["destinations"] if r["crs"] == "LCN")
        details = row["railcards"]["YNG"]
        self.assertEqual(row["adultPence"], 870)
        self.assertEqual(details["minimumFarePence"], 1200)
        self.assertEqual(details["pricePence"], 1200)
        self.assertGreater(details["pricePence"], row["adultPence"])
        # The drawer's own wording for that case: it says the card does not help
        # here, gives both numbers, and names the minimum as the reason, so a
        # reader who opens it is not left reading a discount the row did not get.
        self.assertIn("does not reduce it.", self.html)
        self.assertIn("because the minimum fare the feed applies to this ", self.html)
        self.assertIn("This row is priced at the cheaper of the two", self.html)

    @property
    def stylesheet(self) -> str:
        """The CSS this page is served with, which is no longer inside it.

        ADR-0047: the station route fetches one stylesheet rather than inlining
        it, because the same 34.6 KB on 2,712 pages was 92 MB of a site measured
        at 583 MB. A test that asserts a rule exists therefore asserts it
        against the document the page loads -- one string, identical on every
        station page, written beside them by the build -- rather than against
        the page, which no longer carries any of it.
        """
        from page_templates import STATION_STYLESHEET

        return STATION_STYLESHEET

    def test_a_ticked_row_shows_the_card_price_and_the_standard_fare(self) -> None:
        # Q3: a discounted number never stands alone in the cell. The page
        # builds the price cell so it can carry the standard fare the card was
        # taken from, and carries nothing beside a price the card did not
        # lower. The live behaviour is driven by the browser suite.
        self.assertIn('cell.dataset.label = "Price"', self.html)
        self.assertIn('amount.className = "price"', self.html)
        self.assertIn('was.className = "was"', self.html)
        self.assertIn("if (price < standard)", self.html)
        self.assertIn('money(standard) + " standard"', self.html)
        self.assertIn("td.num .was {", self.stylesheet)

    def test_rule_records_are_hoisted_out_of_the_rows(self) -> None:
        rows = [
            row
            for key in ("destinations", "singleDestinations", "anytimeDestinations")
            for row in self.payload[key]
        ]
        self.assertTrue(rows)
        offered = {card["key"] for card in self.payload["railcards"]}
        for row in rows:
            for key, details in row["railcards"].items():
                self.assertIn(key, offered, "a row prices only reviewed cards")
                rule = details["rule"]
                self.assertIsInstance(rule, str, "rows hold a key, never the record")
                self.assertIn(rule, self.payload["railcardRules"])
        rules = self.payload["railcardRules"]
        self.assertTrue(rules, "a page with rows publishes the shared records")

    def test_unavailable_railcard_hides_its_own_help(self) -> None:
        payload = dict(self.payload, railcards=[])
        html = render_page(payload, budget_pounds=20)
        script = page_script(html)
        self.assertIn("This feed prices no reviewed railcard, so these are standard fares.",
                      script)
        self.assertIn("railcardChoice.hidden = true", script)
        self.assertIn("railcardSelect.disabled = true;", script)
        # The sentence stays rather than being hidden. "Standard fares" is the
        # claim the page rests on, and a reader who owns a 16-25 card is owed
        # the reason their card is not offered rather than an empty space.
        self.assertIn("help.hidden = false", script)
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
        script = page_script(html)
        self.assertIn("if (!DATA.hasJourneys)", script)
        # By heading name, per table. A bare nth-child across the whole page
        # took the dock's own columns instead of the results table's, because
        # the two tables number their cells differently. Naming the columns
        # means a table that gains a column first does not move the removal
        # onto a neighbour, and the dock's remove button keeps its heading.
        self.assertIn('name === "Time" || name === "Changes"', script)
        self.assertNotIn("thead th:nth-child", script)
        # The detail rows must span whatever the table actually has.
        self.assertIn("cell.colSpan = columnCount()", script)
        # And the footer still says what the page is missing.
        self.assertIn("no timetable loaded", html)

    def test_a_page_with_times_keeps_all_six_columns(self) -> None:
        script = page_script(self.html)
        self.assertIn("const columnCount", script)
        # Through journeyFor(), so the number printed is the chosen day's.
        self.assertIn("duration(journey.minutes)", script)

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

    def test_a_page_built_from_a_slice_of_the_timetable_is_the_same_page(self) -> None:
        # The all-origins build hands every page the national index -- one feed
        # and a page for each station it prices -- and a page is built from the
        # slice of it that page can use (`TimetableDb.focused`). A slice is a
        # subset of the database the page would otherwise read from, so the
        # proof that nothing moved is the page itself: two payloads from two
        # databases, one byte-diff. On the real feed the cut is a strict one --
        # 5,262 of 419,589 schedules for Grantham -- and the same byte-diff is
        # taken there (`docs/build-performance-findings.md`).
        day = date(2026, 9, 28)
        whole = build_payload(
            self.fares, self.timetable, "GRN", day=day, built_at="2026-09-27T00:00:00Z"
        )
        slice_ = build_payload(
            self.fares,
            self.timetable.focused("GRN"),
            "GRN",
            day=day,
            built_at="2026-09-27T00:00:00Z",
        )
        self.assertEqual(
            render_page(whole, budget_pounds=20),
            render_page(slice_, budget_pounds=20),
        )
        # The figures a page carries are claims about the feed behind it, and
        # this page was built from a slice of one. A page that reported its
        # slice's own counts would describe a different feed to the one the
        # build read.
        self.assertEqual(slice_["timetable"], whole["timetable"])
        self.assertEqual(slice_["timetableFrom"], whole["timetableFrom"])
        self.assertEqual(slice_["timetableTo"], whole["timetableTo"])

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
        # ADR-0040: the two notes and the build line are one fold above the
        # table, so the block between the count and the table is one line rather
        # than three. What a reader meets is the fold's summary, so the summary
        # has to name what it holds -- and, when the links are tracked, the one
        # fact that must not be a click away.
        self.assertIn('<details class="link-terms" id="linkTerms">', self.html)
        self.assertIn('id="linkTermsSummary"', self.html)
        for note in ('id="linkNote"', 'id="disclosure"'):
            self.assertLess(self.html.index('<details class="link-terms"'), self.html.index(note))
            self.assertLess(self.html.index(note), self.html.index("<table>"))
        # The build stamp is reference material and went under the table
        # with the rest of it, rather than sitting in the fold a reader has
        # to get through before the first fare.
        self.assertGreater(
            self.html.index('id="buildMetadata"'), self.html.index("<table>")
        )
        self.assertIn("About the ticket link", self.html)
        self.assertIn('"About the ticket link, and how this site is paid"', self.html)
        self.assertIn("linkTerms.hidden =", self.html)

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
        self.assertIn("no times are shown", self.html)
        self.assertIn("with the fastest time and the fewest changes", self.html)
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
        self.assertIn("copyJourney(destination, copy, tools)", self.html)

    def test_the_copied_text_names_the_things_a_seller_asks_for(self) -> None:
        for label in ('"From: "', '"To: "', '"Date: "', '"Passengers: "'):
            self.assertIn(label, self.html)

    def test_the_copied_text_names_the_railcard_only_for_the_party_price(self) -> None:
        # The card is never sent anywhere; it is named as something to tick, and
        # only when the price on screen is the one that needs it.
        self.assertIn('const together = unit() === "party";', self.html)
        self.assertIn("if (together && card)", self.html)
        self.assertIn('lines.push(railcards[railcardSelect.value].label + " discount is not sent',
                      self.html)
        self.assertIn('" discount is not sent to the seller', self.html)
        self.assertNotIn('"Two Together discount is not sent to the seller', self.html)

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
        heading = self.html.split("<h1", 1)[1].split("</h1>", 1)[0]
        self.assertIn("Train fares", heading)
        self.assertIn("up to", heading)
        self.assertNotIn("under", heading)
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

    def test_the_filter_bar_is_one_column_and_keeps_one_budget_field(self) -> None:
        # The bar is the budget and one folded block now, so it is a single
        # column rather than three tracks side by side. At 1440px the
        # three-track version laid the refinements out as though a reader
        # wanted all of them at once, above the list they came for.
        self.assertIn("grid-template-columns: minmax(0, 1fr)", self.stylesheet)
        self.assertIn('<section class="filter-bar"', self.html)
        self.assertIn('id="budget" type="range"', self.html)
        self.assertIn('id="budgetNumber" type="number"', self.html.split("<h1", 1)[1].split("</h1>", 1)[0])
        self.assertNotIn('id="budgetNumber" type="number"', self.html.split('<section class="filter-bar"', 1)[1])

    def test_the_shared_stylesheet_has_one_source_and_the_station_route_fetches_it(self) -> None:
        # S39: the palette, spacing, focus ring, links, navigation and disclosure
        # styles have one source. A route's own block holds only what is its own,
        # and a template that still held the placeholder would raise rather than
        # ship unstyled text. ADR-0047 changed how a route gets that source, not
        # what it is: the two single-page routes inline it, and the station route
        # -- 2,712 pages carrying the same 34.6 KB -- fetches the one file the
        # build writes.
        from page_templates import (
            CHOOSER_TEMPLATE,
            PRIVACY,
            SHARED_CSS,
            STATION_CSS,
            STATION_STYLESHEET,
            TEMPLATE,
        )

        for name, template in (("chooser", CHOOSER_TEMPLATE), ("privacy", PRIVACY)):
            self.assertIn(SHARED_CSS, template, f"{name} does not carry the shared stylesheet")
            self.assertNotIn("__SHARED_CSS__", template, f"{name} shipped the placeholder")
        # The station route holds the link where the block used to be, and
        # nothing else: the shared block is fetched, not restated, or the file
        # would be back to being the same bytes on every page.
        self.assertNotIn("__SHARED_CSS__", TEMPLATE, "the station template shipped the placeholder")
        self.assertNotIn(SHARED_CSS, TEMPLATE, "the station page inlines the block it fetches")
        self.assertIn("__STATION_STYLE__", TEMPLATE, "the station template has no stylesheet link")
        self.assertIn(
            build_demo_page.station_style_tag(self.payload["styleSrc"]),
            self.html,
            "the station page does not link the stylesheet this build wrote",
        )
        # The file it links is the shared block and this route's own rules, in
        # that order -- the same bytes the inline <style> element held.
        self.assertTrue(
            STATION_STYLESHEET.startswith(SHARED_CSS), "the asset does not begin with the shared block"
        )
        self.assertTrue(
            STATION_STYLESHEET.endswith(STATION_CSS.strip() + "\n"),
            "the asset is not the shared block plus this route's own rules",
        )
        # The name is a digest of those bytes, so a changed stylesheet is a new
        # file and a cached one can never be served beside a page built from
        # another revision of it.
        import hashlib

        digest = hashlib.sha256(STATION_STYLESHEET.encode("utf-8")).hexdigest()[:12]
        self.assertEqual(build_demo_page.station_style_asset_name(), f"station-{digest}.css")
        self.assertIn(build_demo_page.station_style_asset_name(), self.html)
        # A page that could not name the document would have no styling and no
        # request for any, so render_page refuses rather than shipping it -- the
        # same refusal with_shared() makes for a template that kept a
        # placeholder.
        with self.assertRaises(ValueError):
            build_demo_page.render_page({**self.payload, "styleSrc": ""}, budget_pounds=20)
        # The marker the page reads to know its stylesheet arrived is in the
        # block, so a route that inlined it always answers yes and a route that
        # fetched it answers from the browser rather than from a guess about
        # whether a request is still in flight.
        self.assertIn("--tbe-stylesheet: 1;", SHARED_CSS)
        # One palette, one focus ring, one footer -- each stated once in the
        # source, and present in all three rendered routes.
        # C14 again, in the new shape: a token with a light value but no
        # light-dark() counterpart is a token the dark palette never sets, and
        # that was the defect. The plain value first is deliberate -- it is what
        # a browser without light-dark() falls back to -- so both are required.
        for token in ("--bg", "--fg", "--line", "--muted", "--accent", "--ochre", "--warn", "--field"):
            with self.subTest(token=token):
                self.assertIn(f"{token}: ", SHARED_CSS)
                self.assertIn(f"{token}: light-dark(", SHARED_CSS, f"{token} has no dark counterpart")
        # The NRE credit is dark in both palettes on purpose -- the mark is a
        # light rendering of NRE's blue -- so its two colours are fixed rather
        # than a light-dark pair, and the mark looks the same either way.
        self.assertIn("--nre-plate: #141b3d; --nre-ink: #cdd6ff;", SHARED_CSS)
        # !important is load-bearing, and the browser suite is what proves it:
        # the mark's shapes each carry fill in a style attribute, which
        # outranks a stylesheet rule, so a rule without it would leave the mark
        # in NRE's blue on a dark plate at 1.4:1 without anything here failing.
        self.assertIn(".nre-logo svg * { fill: var(--nre-ink) !important; }", SHARED_CSS)
        self.assertEqual(SHARED_CSS.count(":root {"), 1, "one token block, both schemes in it")
        self.assertIn(':root[data-theme="dark"] { color-scheme: dark; }', SHARED_CSS)
        self.assertIn(':root[data-theme="light"] { color-scheme: light; }', SHARED_CSS)
        self.assertNotIn("prefers-color-scheme: dark", SHARED_CSS, "the scheme is chosen, not inherited")
        # The switch, on every route, hidden until the script that wires it has
        # run: a control that cannot work without JavaScript must not be on the
        # page for a reader who has none.
        for name, template in (("chooser", CHOOSER_TEMPLATE), ("station", TEMPLATE), ("privacy", PRIVACY)):
            with self.subTest(route=name):
                self.assertIn('id="themeToggle"', template)
                self.assertIn('role="switch"', template)
                self.assertIn("hidden>", template.split('id="themeToggle"')[1][:120])
                self.assertIn("toggle.hidden = false", template)
                self.assertIn('localStorage.getItem("tbe-theme")', template)
                # Dark is the default, so the very first thing the script does
                # with an empty store is choose dark.
                self.assertIn("var dark = true;", template)
                self.assertIn('document.documentElement.dataset.theme = dark ? "dark" : "light";', template)
        self.assertIn(":focus-visible { outline: 2px solid var(--accent); outline-offset: 2px;", SHARED_CSS)
        chooser = build_demo_page.render_chooser([], budget_pounds=60)
        privacy = build_demo_page.render_privacy(
            "note", "", "a@b.test", build_demo_page.site_features(
                analytics=False, link_mode="fallback", network=None, disclosure=None
            )
        )
        for name, styled in (
            ("chooser", chooser),
            ("station", self.stylesheet),
            ("privacy", privacy),
        ):
            self.assertIn("--accent: #14509b;", styled, f"{name} lost the shared palette")
            # The dark palette is a light-dark() pair now, not a media query, so
            # what a route has to carry is both values of one token.
            self.assertIn(
                "--accent: light-dark(#14509b, #7db4f5);", styled, f"{name} lost the dark palette"
            )
            self.assertIn(':root[data-theme="dark"] { color-scheme: dark; }', styled, f"{name} cannot be told to paint dark")
            # C25: the shared block holds the 44px minimum on the anchor, not
            # only on a container around it, so the privacy page's single
            # navigation link is a 44px target rather than a 24px one that
            # happened to be 24px because of its line box.
            self.assertIn(
                ".footnav a, .back-link a { display: inline-flex; align-items: center; min-height: 44px; color: inherit; }",
                styled,
                f"{name} restated the footer nav",
            )
        # One column for the whole site. The chooser used to state a width of
        # its own -- 56rem against the station page's 78 -- and the same
        # heading that fit two lines on one route took three on the other,
        # which is most of what made them read as two products. The policy
        # page is the one exception, and deliberately: a document is read in
        # a measure, not in the width of a table.
        for name, own in (
            ("chooser", chooser.split(SHARED_CSS, 1)[1]),
            ("station", self.stylesheet.split(SHARED_CSS, 1)[1]),
        ):
            self.assertNotIn("--page-max", own, f"{name} states a width of its own")
            self.assertNotIn("--page-pad", own, f"{name} states its own padding")
        self.assertIn(":root { --h1: 2rem; --page-max: 42rem; }", privacy)
        self.assertIn("--page-max: 78rem", SHARED_CSS)

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
        # The dark value of --muted, as the second half of its light-dark() pair.
        self.assertIn("--muted: light-dark(#5b6472, #a7b2c0)", self.stylesheet)
        self.assertIn(".synthetic-banner strong { color: color-mix(in srgb, var(--ochre) 80%, var(--fg)); }", self.stylesheet)
        self.assertIn(".feed-record summary { display: inline-flex; align-items: center; min-height: 24px;", self.stylesheet)

    def test_the_budget_is_kept_and_the_refinements_fold_at_every_width(self) -> None:
        # The fold was a phone-only disclosure driven by a media query and a
        # resize listener: two roads to one state, so rotating a device could
        # discard the fold a reader had chosen, and the same control meant two
        # different things at two widths. It is one control and one state now,
        # with no viewport term anywhere near it.
        self.assertIn('<div class="more-filters" id="moreFilters" data-open="false">', self.html)
        self.assertIn('id="moreFiltersToggle"', self.html)
        self.assertIn('aria-controls="moreFiltersPanel"', self.html)
        self.assertIn('id="moreFiltersPanel"', self.html)
        self.assertIn("Filter this list", self.html)
        # The panel is not a card of its own: it and the toggle are one shape,
        # drawn by the accent border they share. The panel therefore carries the
        # border on three sides, no fill and no gap under it, and the open toggle
        # squares off its bottom corners to meet it. These live in the stylesheet
        # the build writes, not in the page that links it.
        from page_templates import STATION_STYLESHEET

        panel_rule = STATION_STYLESHEET.split(
            '.more-filters[data-open="true"] .more-filters-panel {', 1
        )[1].split("}", 1)[0]
        toggle_rule = STATION_STYLESHEET.split(
            '.more-filters[data-open="true"] .more-filters-toggle {', 1
        )[1].split("}", 1)[0]
        self.assertIn("border: 1px solid var(--accent); border-top: 0;", panel_rule)
        self.assertIn("border-radius: 0 0 .45rem .45rem;", panel_rule)
        self.assertIn("padding: 1rem;", panel_rule)
        # The fill and the margin under it are commented out rather than gone, so
        # the line that says what they were is still in the file.
        self.assertIn("/* background: var(--field); */", panel_rule)
        self.assertIn("/* margin-bottom: 1rem; */", panel_rule)
        live = re.sub(r"/\*.*?\*/", "", panel_rule, flags=re.S)
        self.assertNotIn("background:", live)
        self.assertNotIn("margin-bottom:", live)
        self.assertIn("border-radius: .45rem .45rem 0 0;", toggle_rule)
        self.assertNotIn(
            '.more-filters[data-open="true"] .more-filters-toggle { margin-bottom:',
            STATION_STYLESHEET,
        )
        # The three refinements are inside the panel; the budget is not.
        bar = self.html.split('<section class="filter-bar"', 1)[1].split("</section>", 1)[0]
        budget, folded = bar.split('<div class="more-filters"', 1)
        self.assertIn('id="budget" type="range"', budget)
        self.assertIn("more-filters-panel", folded)
        for group in ("ticket-filter", "party-filter", "destination-filter"):
            self.assertIn(group, folded, f"{group} is outside the disclosure")
        # The panel is closed until data-open says otherwise, and the summary
        # is written from that same state, so the two cannot disagree.
        self.assertIn(".more-filters { display: block; }", self.stylesheet)
        self.assertIn(".more-filters-panel { display: none; }", self.stylesheet)
        self.assertIn('.more-filters[data-open="true"] .more-filters-panel { display: grid;', self.stylesheet)
        self.assertIn('moreFilters.dataset.open = open ? "true" : "false";', self.html)
        self.assertIn('moreFiltersToggle.setAttribute("aria-expanded", open ? "true" : "false");', self.html)
        self.assertNotIn("display: contents", self.html)
        self.assertNotIn("matchMedia", self.html)
        self.assertNotIn("followViewport", self.html)
        # The state is written from the page's own controls, on every render
        # and on the path that stands the whole panel down.
        self.assertIn("function filterStateText()", self.html)
        self.assertIn("renderFilterState();", self.html)
        self.assertGreaterEqual(self.html.count("renderFilterState();"), 2)

    def test_the_budget_is_inline_in_the_large_heading(self) -> None:
        heading = self.html.split("<h1", 1)[1].split("</h1>", 1)[0]
        self.assertIn("Train fares", heading)
        self.assertIn("up to", heading)
        self.assertIn('id="budgetNumber"', heading)
        self.assertIn('id="changeOrigin"', heading)
        self.assertIn("h1 { font-size: var(--h1);", self.stylesheet)
        # The currency sign is inside the name a screen reader reads for the
        # heading. It was aria-hidden, so the heading announced "for up to 20"
        # with no unit while the page said "£20.00" everywhere else. The number
        # field keeps its own aria-label, so nothing is announced twice.
        self.assertIn('<span class="budget-prefix">&pound;</span>', heading)
        self.assertNotIn('<span class="budget-prefix" aria-hidden="true">', heading)
        self.assertIn("--h1: clamp(2rem, 7vw, 7rem)", self.stylesheet)
        self.assertIn(".sub { color: var(--muted); max-width: 75ch; }", self.stylesheet)
        self.assertNotIn("max-width: 32ch", self.html)
        self.assertNotIn("margin: -1rem 0 1.5rem", self.html)

    def test_result_changes_and_mobile_cells_are_accessible(self) -> None:
        self.assertIn('id="summary" role="status" aria-live="polite"', self.html)
        self.assertIn("cell.dataset.label =", self.html)
        # The column is the fare in three words. SDR, 2AS and BPS are a
        # seller's vocabulary and they were the column, on every row, in
        # front of the one number the reader came for; the code is in the
        # row's own record (ADR-0053). The label is what the phone reflow
        # reads out.
        self.assertIn('cell.dataset.label = "Fare type"', self.html)
        self.assertIn('function fareTypeWord(destination)', self.html)
        self.assertIn('return "Advance"', self.html)
        self.assertIn('return "Restricted"', self.html)
        self.assertIn('return "Regular"', self.html)
        # And the panel those cells open carries the token the warn colour
        # hangs off, which is what the phone reflow and C14 both read.
        self.assertIn('panel.dataset.status = restricted ? "restricted" : "unrestricted";', self.html)
        self.assertIn('readable.className = "condition";', self.html)
        # C07: the condition is still on the same row, one disclosure away, so
        # the pointer is kept rather than dropped -- and it now points at the
        # thing it names instead of at a column that no longer exists.
        self.assertIn('Restricted fare — the condition is below.', self.html)

    def test_the_page_opens_on_the_cheapest_list_and_every_set_says_what_it_is(self) -> None:
        # C07 was "the set the page opens in is the one PRODUCT.md promises",
        # which for a month meant the reviewed Anytime Day Returns. Q4 changes
        # what the page promises: it opens on the cheapest fare of any type,
        # because a budget question answered with one ticket type is a question
        # about the wrong number. The reviewed set is still offered, still
        # named, and still says what it contains -- the finding C07 recorded is
        # that a reader must be told what the open set holds, not which set it
        # has to be.
        checked = re.search(r'<input type="radio" name="ticketMode" value="(\w+)" checked>', self.html)
        self.assertIsNotNone(checked, "no ticket mode is checked in the markup")
        self.assertEqual("cheapest", checked.group(1))
        self.assertIn("> Anytime Day Return</label>", self.html)
        self.assertIn("> Any return</label>", self.html)
        self.assertIn("> Cheapest of any type</label>", self.html)
        # Each set says what its fares are, above the table rather than inside
        # the methodology accordion, so a reader meets the caveat at the moment
        # they compare two prices.
        for note in ("cheapest:", "anytime:", "return:", "single:"):
            self.assertIn("  " + note, self.html)
        self.assertIn('id="modeNote"', self.html)
        self.assertIn("renderModeNote();", self.html)

    def test_row_actions_carry_a_44px_touch_target(self) -> None:
        # The visible mark stays small; the hit area reaches 44px via ::after.
        self.assertIn('.toggle::after { content: ""; position: absolute; inset: -6px; }', self.stylesheet)
        self.assertIn('.buy::after { content: ""; position: absolute; inset: -11px -4px; }', self.stylesheet)

    # -- the unpriced-origin page ------------------------------------------

    def test_the_hidden_attribute_beats_every_display_rule(self) -> None:
        # The controls grid, the picker, and the footer slots all set display;
        # without this rule, hiding them does nothing and an unpriced page
        # shows a slider that cannot help. Regression: the Sleepy page shipped
        # with the controls still on screen under the unpriced message.
        self.assertIn("[hidden] { display: none !important; }", self.stylesheet)

    def test_an_unpriced_origin_gets_its_own_first_sentence(self) -> None:
        # All three modes, not just the two the test used to empty: an unpriced
        # page is one that priced nothing in any ticket mode, and leaving the
        # Anytime list populated described a page this is not.
        payload = dict(
            self.payload, destinations=[], singleDestinations=[], anytimeDestinations=[]
        )
        html = render_page(payload, budget_pounds=20)
        self.assertIn('id="unpriced"', html)
        script = page_script(html)
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
        script = page_script(html)
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
        script = page_script(html)
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
        # The control names itself in hidden text in front of the station, not
        # through aria-label: an aria-label replaces the text the heading's
        # accessible name is read from, so the heading announced "from Change
        # starting station" and never said which station. The swap arrow is
        # likewise drawn rather than written into the heading's name: the
        # chevron is inline SVG and aria-hidden, because the browser reads
        # CSS generated content inside a heading as text, so a decoration
        # made that way is announced as a word the page never meant to say.
        heading = self.html.split("<h1", 1)[1].split("</h1>", 1)[0]
        self.assertIn('<span class="sr-only">Change starting station: </span>', heading)
        self.assertIn('class="origin-slot" type="button"', heading)
        self.assertIn('<svg class="chevron"', heading)
        self.assertNotIn("origin-swap", self.html)
        self.assertNotIn('aria-label="Change starting station"', self.html)
        # The options are real anchors, not a custom listbox.
        self.assertIn('link.href = station.href', self.html)
        self.assertIn('id="destinationTypes"', page_markup(self.html))
        self.assertIn('name="destinationType" value="city"', page_markup(self.html))
        self.assertIn('name="destinationType" value="seaside"', page_markup(self.html))

    def test_the_nre_credit_is_the_mark_the_guidelines_name(self) -> None:
        # The Developer Brand Guidelines require the "Powered by National Rail
        # Enquiries" logo and a link to NRE's site, inlined so a self-contained
        # page still shows it. The mark is paths, so the name a screen reader
        # reads has to be written out; nothing in an SVG carries it.
        credit = nre_attribution()
        self.assertIn('aria-label="Powered by National Rail Enquiries"', credit)
        self.assertIn("nationalrail.co.uk", credit)
        self.assertIn("<svg", credit)
        self.assertGreater(credit.count("<path"), 5)
        # Inline, not linked: the page is one file and the attribution must not
        # need a second request to appear.
        self.assertNotIn("<?xml", credit)
        self.assertNotIn("Adobe Illustrator", credit)
        self.assertNotIn("<img", credit)
        self.assertNotIn('src="', credit)
        # The mark is reversed onto a dark plate by the page's own stylesheet, so
        # the file in assets/ must still be NRE's, with NRE's colour in it. If
        # somebody "helpfully" baked the light ink into the file, this is what
        # catches it -- and the page would no longer be carrying the artwork it
        # was given.
        mark = (Path(__file__).parent.parent / "assets" / "powered-by-national-rail.svg").read_text(
            encoding="iso-8859-1"
        )
        self.assertIn("2E2D7F", mark)
        self.assertNotIn("cdd6ff", mark.lower())
        self.assertNotIn("141b3d", mark.lower())

    def test_the_credit_is_written_only_where_the_page_acknowledges_nre(self) -> None:
        # Composing the NRE notice is what asks for the mark; a build given
        # verbatim attribution text is not second-guessed.
        self.assertTrue(wants_nre_credit([NOTICES["nre"], NOTICES["ogl"]]))
        self.assertFalse(wants_nre_credit([NOTICES["rdg"], NOTICES["ogl"]]))
        self.assertFalse(wants_nre_credit("some wording of the operator's own"))
        self.assertFalse(wants_nre_credit(None))
        with_credit = render_page(self.payload, budget_pounds=20, nre_credit=True)
        self.assertIn('class="nre-credit"', with_credit)
        self.assertNotIn('class="nre-credit"', render_page(self.payload, budget_pounds=20))
        # The footer credit is the notice the build already uses, linked to the
        # enquiries site, and it says NRE does not endorse the page. A build
        # that did not ask for the NRE notice does not invent the credit.
        self.assertIn(NOTICES["nre"], with_credit)
        self.assertIn('href="https://www.nationalrail.co.uk/"', with_credit)
        self.assertIn("does not endorse this site", with_credit)
        self.assertNotIn("nre-source", render_page(self.payload, budget_pounds=20))

    def test_the_footer_states_a_commission_only_when_one_is_paid(self) -> None:
        # publish-checklist: the affiliate disclosure is present if commission
        # is enabled, and absent otherwise. The sentence is the one retailer.py
        # already uses, and the footer is where a reader who never opens the
        # ticket-link fold still meets it.
        self.assertIn('id="commissionDisclosure" hidden', self.html)
        self.assertIn("commissionDisclosure", self.html)
        self.assertIn("DATA.tracked && DATA.disclosure", self.html)
        plain = render_page(self.payload, budget_pounds=20)
        self.assertNotIn(DISCLOSURE, plain)
        tracked = build_payload(
            self.fares,
            self.timetable,
            "GRN",
            network="partnerize",
            advertiser_id="123456",
        )
        tracked_html = render_page(tracked, budget_pounds=20, nre_credit=True)
        self.assertIn(DISCLOSURE, tracked_html)
        self.assertLess(
            tracked_html.index('id="commissionDisclosure"'),
            tracked_html.index("</footer>"),
        )

    def test_a_missing_nre_mark_is_a_build_failure_not_a_page_without_one(self) -> None:
        # This is the one thing in the footer the licence names, so a build that
        # cannot find it stops rather than publishing a page with the credit
        # quietly absent.
        with mock.patch.object(build_demo_page, "NRE_LOGO", Path("no-such-mark.svg")):
            with self.assertRaises(SystemExit):
                nre_attribution()

    def test_a_build_with_nowhere_to_change_to_names_the_station_as_text(self) -> None:
        # A single-origin build writes one station page, so its picker has no
        # other option. The control was still rendered -- focusable, announced
        # and opening nothing -- and the browser suite failed it four times on
        # the published site. Now the name stands as text and the heading still
        # says which station the page is about.
        payload = dict(self.payload, stations=[])
        heading = render_page(payload, budget_pounds=20).split("<h1", 1)[1].split("</h1>", 1)[0]
        self.assertNotIn("changeOrigin", heading)
        self.assertNotIn("originPicker", heading)
        self.assertIn(f'<span class="origin-name">{payload["origin"]["name"]}</span>', heading)
        # The station's name is escaped on the way into the page, like every
        # other string the build writes into it.
        named = render_page(
            dict(self.payload, stations=[], origin={"crs": "GRN", "name": "A & B <rail>"}),
            budget_pounds=20,
        ).split("<h1", 1)[1].split("</h1>", 1)[0]
        self.assertIn('<span class="origin-name">A &amp; B &lt;rail&gt;</span>', named)
        # The first-use note names the heading's station control, so it cannot
        # be static text on a build that has no such control -- and it has to
        # name the control the page actually shows. It said "Change" until the
        # Change button became the station's own name with a chevron beside it,
        # which left the sentence pointing at a word that was no longer there.
        self.assertNotIn("Change", render_page(payload, budget_pounds=20).split('id="firstUse"')[1].split("</p>")[0])
        with_control = render_page(self.payload, budget_pounds=20).split('id="firstUse"')[1].split("</p>")[0]
        self.assertIn("<b>station name</b>", with_control)

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
        head = page_markup(html)
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
        head = page_markup(render_page(payload, budget_pounds=50))
        self.assertIn('name="destinationType" value="heritage"', head)

    def test_the_chips_are_narrowed_for_the_mode_on_screen(self) -> None:
        # The narrowing reads the active list rather than all three, and runs
        # before the filter is asked what is checked: a chip the list cannot
        # support must not be part of what matchesType is matching.
        script = page_script(self.html)
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
        script = page_script(self.html)
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
        script = page_script(self.html)
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
        # and "Fare code" was rejected while that column read in sentences. The
        # column is now the fare in the reader's own three words and the code
        # is in the row's disclosure (ADR-0053), so the header names what the
        # cells hold rather than what the feed calls them.
        self.assertIn('<th scope="col">Fare type</th>', self.html)
        self.assertNotIn('<th scope="col">Fare code</th>', self.html)
        self.assertIn('<th scope="col">Tickets</th>', self.html)
        self.assertNotIn("<th>Ticket</th><th>Tickets</th>", self.html)
        self.assertNotIn('<th scope="col">Fare</th>', self.html)
        self.assertNotIn('<th scope="col">Conditions</th>', self.html)
        # Six columns, plus the one the hold checkbox sits in: the count is
        # here to catch a column appearing or vanishing unnoticed, which is
        # how the header and the cells drifted apart once before.
        #
        # Counted inside the results table rather than across the page. The
        # shortlist dock is a second table with its own four headings, and a
        # document-wide count would make the dock's arrival look like two new
        # columns in the results table -- which is exactly the drift this
        # assertion exists to catch, now pointing at the wrong table.
        results_header = self.html.split("<table>")[1].split("</thead>")[0]
        self.assertEqual(results_header.count('<th scope="col"'), 7)

    def test_no_numeric_column_can_wrap(self) -> None:
        # Measured on the real Grantham page: the Price column was 56px wide
        # and 13 of the first 20 prices painted as two lines -- £10.10 read as
        # "£10.1" over "0", which is a different number rather than a tighter
        # column. The header word was deciding the width, so neither half of
        # the table wraps, and the browser suite measures the painted lines.
        self.assertIn("color: var(--muted); white-space: nowrap; }", self.stylesheet)
        self.assertIn("font-variant-numeric: tabular-nums; white-space: nowrap; }", self.stylesheet)
        # The station's own code is the widest run of characters in the
        # first column, and it must not wrap either: "KINGS" over "X" is a
        # different place.
        self.assertIn(
            ".station-code { color: var(--muted); font-variant-numeric: tabular-nums; }",
            self.stylesheet,
        )
        self.assertNotIn(".ticket-code", self.stylesheet)

    def test_the_count_line_sits_on_its_table(self) -> None:
        # Finding, 29 September 2026: on the real page the count sat 205px above
        # the first row with six provenance paragraphs between them, so the
        # first fare was below the fold on a laptop. The count belongs to the
        # table it counts, and the provenance that used to sit between them is
        # one fold away.
        self.assertLess(self.html.index('<p id="summary" role="status"'), self.html.index("<table>"))
        between = self.html[self.html.index('<p id="summary" role="status"'):self.html.index("<table>")]
        for moved in ('id="buildMetadata"', 'id="linkNote"', 'id="disclosure"'):
            self.assertNotIn(moved, between)

    def test_keyboard_focus_is_visible_everywhere(self) -> None:
        self.assertIn(":focus-visible { outline: 2px solid var(--accent); outline-offset: 2px;", self.stylesheet)

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
        script = page_script(self.html)
        self.assertIn("We don't have prices from '", script)
        self.assertNotIn('from \\"', script)

    def test_privacy_requires_a_contact_and_uses_the_deployment_route(self) -> None:
        with self.assertRaises(ValueError):
            render_privacy("note")
        html = render_privacy("note", contact="privacy@example.test")
        self.assertIn("privacy@example.test", html)
        self.assertNotIn("goes here before the site is published", html)

    def test_the_chooser_budget_is_carried_into_station_links(self) -> None:
        # Two stations, because a root that offers a choice is the chooser. A
        # root that offers one station is the release root, driven below.
        chooser = render_chooser(
            [
                {"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1},
                {"crs": "GRN", "name": "GRANTHAM", "slug": "grantham", "destinations": 3},
            ],
            budget_pounds=20,
        )
        # The budget is the heading's own inline field, the same one a
        # station page carries, rather than a labelled input above the list.
        self.assertIn('id="budgetNumber"', chooser)
        self.assertIn('url.searchParams.set("budget"', chooser)
        self.assertIn("min-height: 44px", chooser)
        # The station slot is the one thing this route has that a station
        # page does not: a field holding the word station, waiting to be
        # typed in, so the page reads as a question with its answer missing.
        self.assertIn('id="originSearch"', chooser)
        self.assertIn('placeholder="station"', chooser)
        self.assertNotIn("Rail Budget", chooser)

    def test_a_one_station_release_names_the_station_instead_of_asking(self) -> None:
        # Recommendation 2: the published artefact offered one station and asked
        # the reader to type it, so every check that narrowed a list of one had
        # to be reported as not exercised. A field that can only ever confirm a
        # single answer is a control that lies, so the shape states the choice
        # the build has already made. The station's name is escaped on the way
        # into the heading, like every other string the build writes.
        chooser = render_chooser(
            [{"crs": "NOT", "name": "CARK & CARTMEL", "slug": "cark", "destinations": 5}],
            budget_pounds=20,
        )
        self.assertNotIn('id="originSearch"', chooser)
        self.assertNotIn('class="origin-slot"', chooser)
        self.assertIn('<span class="origin-name">CARK &amp; CARTMEL</span>', chooser)
        self.assertIn("built for one station", chooser)
        # Nothing is ordered over one row, so the page makes no ranking claim.
        self.assertNotIn('id="orderingNote"', chooser)
        self.assertNotIn("Ordered by how many destinations", chooser)
        # The tab title names the station, and the script keeps it named as the
        # budget changes rather than falling back to asking where to leave from.
        self.assertIn("&middot; CARK &amp; CARTMEL</title>", chooser)
        self.assertIn('const TITLE_SUFFIX = "CARK & CARTMEL";', chooser)
        self.assertIn('"name":"CARK & CARTMEL"', chooser)
        # The one row is still the release: the page to open, with its count.
        self.assertIn("/from/cark/", chooser)
        self.assertIn('"destinations":5', chooser.replace(" ", ""))
        # A chooser's field is optional now, so the script cannot assume it. It
        # is wired through the shared field block, which owns the typing and
        # hands the route back the text, the field's value and the completion.
        self.assertIn("attachStationField({", chooser)
        self.assertIn("field: pick,", chooser)
        self.assertIn('const needle = typedQuery.trim().toLowerCase();', chooser)
        self.assertIn("if (pick) pick.focus();", chooser)
        # The completion is ranked by relevance before destination count, and
        # the list offers the alternatives a one-row dropdown used to hide
        # (audit items 1 and 2, 9 October 2026).
        self.assertIn("function completionFor(typed) {", chooser)
        self.assertIn("onChange: (_value, query, completion) => {", chooser)
        self.assertIn("typedQuery = query;", chooser)
        self.assertIn("const ordered = completing", chooser)
        self.assertIn("[completing, ...wanted.filter((station) => station !== completing)]", chooser)
        # The list is the whole page's answer, so it is still built and counted.
        self.assertIn('const TITLE_SUFFIX', chooser)
        self.assertIn('status.textContent = wanted.length + " station"', chooser)

    def test_the_chooser_stylesheet_does_not_change_with_the_station_count(self) -> None:
        # The two shapes differ in one place: the heading's station clause, which
        # a one-station release fills with the station's name. That substitution
        # runs over the whole page, so a placeholder named anywhere else -- in a
        # CSS comment, say -- is filled in too, and one route's stylesheet starts
        # depending on what the page happens to list.
        def stylesheet(page: str) -> str:
            return page.split("<style>", 1)[1].split("</style>", 1)[0]

        one = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}],
            budget_pounds=20,
        )
        many = render_chooser(
            [
                {"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1},
                {"crs": "GRN", "name": "GRANTHAM", "slug": "grantham", "destinations": 3},
            ],
            budget_pounds=20,
        )
        self.assertEqual(stylesheet(one), stylesheet(many))

    def test_the_chooser_explains_a_truncated_match_list(self) -> None:
        chooser = render_chooser([], budget_pounds=20)
        # The cap is the number of rows drawn, which is forty while there is a
        # search to run and every station when there is not, so a chooser lists
        # the whole directory rather than its first forty names.
        self.assertIn("const cap = needle ? CHOOSER_LIMIT : wanted.length;", chooser)
        self.assertIn("Showing \" + cap + \" of \" + wanted.length", chooser)
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

    def test_a_compressed_feed_name_is_shown_as_the_stations_own_name(self) -> None:
        # Audit item 5, 9 October 2026: the picker and the chooser ask a reader
        # to choose between places, and the feed's short form -- "LONDON
        # KINGS X", "HEATHROW UNDERGD", "XC ORIGIN" -- is not a name. The
        # registry is keyed by CRS, so a rename can never move a station's
        # address: slugs stay the feed's own spelling.
        locations = self.fares.locations_by_crs
        index = build_station_index({"KGX": 2, "GRN": 1}, locations)
        names = {entry["crs"]: entry["name"] for entry in index}
        slugs = {entry["crs"]: entry["slug"] for entry in index}
        self.assertEqual(names["KGX"], "London Kings Cross")
        self.assertEqual(names["GRN"], "GRANTHAM")
        self.assertEqual(names["KGX"], build_demo_page.display_station_name("KGX", "LONDON KINGS X"))
        self.assertEqual(slugs["KGX"], "london-kings-x")
        # The reviewed registry stays reviewable: three-letter codes, a real
        # name per entry, and nothing that merely repeats the short form.
        for crs, name in build_demo_page.REVIEWED_STATION_NAMES.items():
            self.assertRegex(crs, r"^[A-Z]{3}$")
            self.assertTrue(name.strip(), crs)
            self.assertNotEqual(name, name.upper(), crs)

    def test_the_chooser_is_the_index_and_carries_no_fares(self) -> None:
        index = [
            {"crs": "KGX", "name": "LONDON KINGS X", "slug": "london-kings-x", "destinations": 6},
            {"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 5},
        ]
        html = render_chooser(index, budget_pounds=20)
        self.assertIn("Type the station you are leaving from", html)
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

    def test_a_route_without_a_note_ships_no_empty_paragraph(self) -> None:
        # Audit item 8, 9 October 2026: a real build passes "" for the note,
        # and every route used to write the note's paragraph anyway -- 2rem of
        # dead space on the chooser, an empty block in the privacy footer, and
        # a blank line in the station page's footer. The note travels as the
        # whole element now, the shape the synthetic banner already had.
        chooser = render_chooser([], budget_pounds=20, note="")
        privacy = render_privacy("", "", "a@b.test")
        station = render_page(dict(self.payload, note=""), budget_pounds=20)
        # Each route's note paragraph is gone rather than emptied: the chooser's
        # `p.tag`, the privacy footer's `p.muted` (where the contact is still a
        # real sentence), and the station page's attribute-less paragraph.
        self.assertNotIn('<p class="tag"></p>', chooser)
        self.assertNotIn('<p class="muted"></p>', privacy)
        self.assertNotIn("<p></p>", station)
        for name, page in (("chooser", chooser), ("privacy", privacy), ("station", station)):
            self.assertNotIn(build_demo_page.DEFAULT_NOTE, page, f"the {name} claimed a note it was not given")
        # A note the build was given still reaches every route as a paragraph.
        self.assertIn(
            '<p class="tag">the RSP fares feed</p>',
            render_chooser([], budget_pounds=20, note="the RSP fares feed"),
        )
        self.assertIn(
            '<p class="muted">the RSP fares feed</p>',
            render_privacy("the RSP fares feed", "", "a@b.test"),
        )
        self.assertIn(
            "<p>the RSP fares feed</p>",
            render_page(dict(self.payload, note="the RSP fares feed"), budget_pounds=20),
        )

    def test_the_chooser_heading_is_the_station_pages_sentence(self) -> None:
        # Audit item 7, 9 October 2026: the station page retired its two middot
        # separators when the "from" line arrived, and the chooser kept them --
        # the second one ending the first line at display size. One heading
        # shape on both routes now, and the "from" wears the shared lead.
        field = [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}]
        for chooser in (
            render_chooser(field, budget_pounds=20),
            render_chooser([], budget_pounds=20),
        ):
            self.assertNotIn("heading-sep", chooser)
            self.assertIn('<span class="heading-slot">Train fares up to ', chooser)
            self.assertIn('<span class="heading-lead">from</span>', chooser)
            self.assertNotIn("originClause\"> from <", chooser)

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
        script = page_script(html)
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
        self.assertIn("@media (max-width: 44rem)", self.stylesheet)
        # From the first max-width block to the end of the stylesheet: the
        # footer nav has its own small block, and the table's rules must be
        # found wherever they sit.
        reflow = self.stylesheet[self.stylesheet.index("table, tbody { display: block; }") - 200:]
        self.assertNotIn("display: none", reflow.split("thead")[0])
        self.assertIn("thead { position:absolute; width:1px; height:1px;", reflow)
        self.assertIn("td[data-label]::before { content: attr(data-label)", reflow)
        # The cells wrap rather than hold a width. `minmax(0, 1fr)` is what says
        # so, and it replaced `flex-wrap` here: a fixed or `max-content` track
        # would be as wide as its longest content and push the row sideways.
        self.assertIn("grid-template-columns: 5rem minmax(0, 1fr)", reflow)
        # One rule per row, drawn by the row. Every cell used to keep the border
        # the table gave it and draw a line at its own height, so a stacked row
        # showed up to six horizontal lines at six different heights, none of
        # them reaching the row's own. The panel a row opens had one too, and
        # opening a destination drew a second line across the page.
        self.assertIn("th, td { border-bottom: 0; }", reflow)
        self.assertIn("tr.detail td { padding: .5rem 0 .55rem; border-bottom: 0; }", reflow)
        table_markup = self.html.split("<table>")[1].split("</table>")[0]
        self.assertNotIn("<div", table_markup)

    def test_the_railcard_list_keeps_every_card_and_marks_the_ones_it_cannot_price(self) -> None:
        # Two Together is two adults exactly, so on the default page -- one
        # adult -- the party filter removed it, and it was the only card the
        # selector lost. A reader who owns it could not find out that the page
        # prices it at all. It is listed and struck out of choosing instead: a
        # disabled option cannot hold a value, so nothing downstream can read a
        # card price nobody could buy, which is what ADR-0052 was protecting.
        self.assertEqual(
            len(self.payload["railcards"]), 6,
            "the six reviewed cards are all priced on this page, so all six belong in the list",
        )
        self.assertIn("if (cardCoversParty(card)) {", self.html)
        self.assertIn("option.disabled = true;", self.html)
        # The reason is in the option, in the feed's own bounds, so it is on
        # screen rather than inferred from an absence.
        self.assertIn('" (needs " + card.minAdults + " adults)"', self.html)
        self.assertIn('" (covers up to " + card.maxAdults + " adult"', self.html)
        # And the options are built from every key, not from the filtered set:
        # this is the one assertion that would catch the removal coming back.
        self.assertIn("for (const key of railcardKeys) {", self.html)
        self.assertNotIn("for (const key of offered) {", self.html)

    def test_the_journey_is_the_same_fact_in_all_three_fare_lists(self) -> None:
        # The journey belongs to the origin and the destination, not to the
        # ticket type. It used to be read from each list's own timetable only,
        # so the same destination carried a different answer in each list, and
        # the cheapest list -- which keeps whichever row is cheapest -- showed
        # "No service" and "Unknown" about a destination the same payload times
        # at 45 minutes. The Time and Changes columns were empty for every
        # destination the build could time, and empty for a reason that named
        # nothing true about it.
        lists = (
            self.payload["destinations"],
            self.payload["singleDestinations"],
            self.payload["anytimeDestinations"],
        )
        seen: dict[str, tuple] = {}
        for rows in lists:
            for row in rows:
                fact = (row["journeyState"], row["minutes"], row["changes"])
                self.assertEqual(
                    seen.setdefault(row["crs"], fact),
                    fact,
                    f"{row['crs']} is timed differently in two fare lists: "
                    f"{seen[row['crs']]} and {fact}",
                )
        single = {row["crs"]: row for row in self.payload["singleDestinations"]}
        self.assertTrue(single, "this build prices no outbound single to check")
        for row in single.values():
            self.assertNotEqual(
                row["journeyState"], "no_timetable",
                "a build that loaded a timetable must not say it has none",
            )
        self.assertTrue(
            any(row["minutes"] is not None for row in single.values()),
            "no single-mode row carries a journey",
        )
        # The one thing that does NOT fall back. These are the times the fare is
        # good on, and an advance single's are only knowable from the separate
        # outbound-single timetable; a return-set train listed under an advance
        # single would be a time the reader cannot travel on that ticket.
        self.assertTrue(
            any(row["minutes"] is not None and not row["departures"]
                for row in single.values()),
            "a single-mode row is carrying departure times it has no timetable for",
        )
        # A build with no timetable at all still says so, because that sentence
        # now turns on whether any timetable was searched rather than on whether
        # this row's own list had one.
        prices_only = build_payload(self.fares, None, "GRN")
        for rows in (prices_only["destinations"], prices_only["anytimeDestinations"]):
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(row["journeyState"], "no_timetable")

    def test_the_standard_fare_under_a_discounted_price_is_a_step_down_the_ladder(self) -> None:
        # The price it sits under is the cell's own size, 1rem. One clear step
        # down is a fifth off it, not a twentieth: at .875em the note was 14px
        # against a 16px price, which is the size the page already gives every
        # other small note on a row, so the cell read as two equal numbers
        # rather than one price with a note under it.
        was = float(re.search(r"td\.num \.was \{[^}]*font-size: ([0-9.]+)em",
                              self.stylesheet).group(1))
        self.assertLessEqual(was, 0.8, "the standard fare is not smaller than it was")
        self.assertLessEqual(was, 0.85, "the standard fare is not a clear step down")

    def test_a_destination_type_and_its_count_are_separated(self) -> None:
        # The markup has always had a space between them and it never reached
        # the screen: `.choice-chip` is an inline-flex box, and a flex container
        # drops the whitespace-only text between its items. Measured on the
        # Grantham page, the rendered chip read "Small towns(0)".
        self.assertRegex(
            self.stylesheet,
            r"\.chipcount \{[^}]*margin-left: [^;}]+;",
            "the count is separated from the type name by a margin",
        )

    def test_the_slider_ceiling_covers_the_dearest_destination(self) -> None:
        ceiling = int(re.search(r'id="budget"[^>]*max="(\d+)"', self.html).group(1))
        dearest = max(row["adultPence"] for row in self.payload["destinations"])
        self.assertGreaterEqual(ceiling * 100, dearest)

    def test_the_page_says_where_the_slider_stops_and_the_figure_is_the_stop(self) -> None:
        # A control that stops somewhere for a reason the page never states is
        # a control the reader has to discover by dragging. The budget contract
        # is "up to", inclusive, so a fare at the boundary is included and the
        # figure has to be predictable -- which it is only if the number on the
        # page is the number the input actually stops at. The two are read out
        # of the built page, not out of the resolver that produced them, so a
        # disagreement between them is what fails.
        ceiling = int(re.search(r'id="budget"[^>]*max="(\d+)"', self.html).group(1))
        hint = re.search(r'(id="budgetHint">.*?)</span>\.', self.html, re.S).group(1)
        self.assertIn("It stops at the highest fare", hint)
        self.assertIn("&pound;{}.00 for one adult".format(ceiling), hint)
        self.assertNotIn("__CEILING_NOTE__", self.html)

    def test_the_stated_ceiling_follows_the_party_the_reader_chooses(self) -> None:
        # The ceiling is party-aware -- two adults cost twice one -- so a note
        # written once at build time would name a stop the page leaves behind
        # the moment "Two adults" is chosen, and the figure would contradict the
        # input's own max. It is written from the resolved ceiling on every
        # render, and it names the party that ceiling was resolved for, because
        # "£252.00" is not a budget until the page says whose it is.
        script = page_script(self.html)
        render = script.split("function render(")[1].split("\nfunction ")[0]
        self.assertIn("budgetCeilingNote.textContent = money(ceiling * 100)", render)
        self.assertIn('unit() === "party" ? "two adults" : "one adult"', render)
        # It is written where the ceiling is resolved, and not before an early
        # return that would leave a stale figure on an emptied list.
        self.assertLess(
            render.index("const ceiling = budgetCeiling();"),
            render.index("budgetCeilingNote.textContent"),
        )

    def test_a_script_tag_in_the_data_cannot_close_the_script_early(self) -> None:
        payload = dict(self.payload, note="a note with </script> in it")
        html = render_page(payload, budget_pounds=20)
        payload_region = html.split("const DATA = ")[1].split(";\n")[0]
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
        # The toggle exists on every row now, because the row's fare and its
        # condition are in the panel it opens and a prices-only build has no
        # times to hang a toggle on (finding, 29 September 2026). The control is
        # the page's own chevron rather than a word, so the count no longer has
        # anywhere visible to go; it stays in the accessible name, which is
        # where the word used to be, and the panel still lists the times.
        self.assertIn("const times = destination.departures.length;", self.html)
        self.assertIn("toggle.className = \"toggle row-expand\";", self.html)
        self.assertIn("toggle.insertAdjacentHTML(\"beforeend\", CHEVRON);", self.html)
        self.assertIn(
            '(times ? times + " times and fare details for " : "Fare details for ") + destination.name',
            self.html,
        )
        self.assertNotIn('toggle.textContent = times ? times + " times" : "Fare details";', self.html)

    def test_the_row_expander_is_a_chevron_that_keeps_its_words(self) -> None:
        # The control used to read "5 times" or "Fare details" in the last
        # column of every row. The face of it is now the page's shared chevron,
        # so three things have to hold at once: the mark is the same drawn
        # chevron the filter bar uses rather than a second drawing of it, the
        # words a screen reader needs are still the accessible name, and the
        # button still reaches 44px, because a mark alone is not a target.
        script = page_script(self.html)
        row_cell = script.split("function cellWithLinks")[1].split("function cardNote")[0]
        self.assertIn("toggle.className = \"toggle row-expand\";", row_cell)
        self.assertIn("toggle.setAttribute(\"aria-label\",", row_cell)
        self.assertIn("destination.name", row_cell)
        # The script holds the mark as a string, quoted by json rather than
        # pasted, so the same CHEVRON constant serves the markup and the rows.
        self.assertIn("const CHEVRON = \"<svg class=", script)
        self.assertIn('aria-hidden="true"', script)
        # 2.75rem is the 44px the row's other control is held to, and the
        # rotated state is what distinguishes open from closed.
        from page_templates import STATION_STYLESHEET

        stylesheet = STATION_STYLESHEET
        self.assertIn(".row-expand {", stylesheet)
        expand_rule = stylesheet.split(".row-expand {", 1)[1].split("}", 1)[0]
        self.assertIn("width: 2.75rem;", expand_rule)
        self.assertIn("height: 2.75rem;", expand_rule)
        self.assertIn(
            '.row-expand[aria-expanded=true] .chevron { transform: rotate(180deg); }',
            stylesheet,
        )

    def test_a_row_has_one_panel_and_one_control_that_owns_it(self) -> None:
        # C28: the times list and the manual-copy box both insert the row that
        # follows the data row, and each used to remove whatever was there by
        # reaching for nextElementSibling. The distill pass leaves one panel per
        # row -- the copy text lands inside it, under the button that asked for
        # it -- so the state machine is one region with one owner, keyed weakly
        # so a re-render's detached rows are collectable.
        script = page_script(self.html)
        self.assertNotIn("nextElementSibling", script.split("function toggleDetail")[1].split("\nfunction ")[0])
        self.assertNotIn("nextElementSibling", script.split("function showCopyText")[1].split("\nfunction ")[0])
        self.assertIn("function closePanel", script)
        self.assertIn("const rowPanel = new WeakMap();", script)
        # The two-region machinery went with the second panel: one region cannot
        # be mis-opened over another, which is the bug C28 was written for.
        for gone in ("closeRegion", "rowRegions", "nextRegionId"):
            self.assertNotIn(gone, script)
        opening_times = script.split("function toggleDetail")[1].split("\nfunction ")[0]
        self.assertIn('closePanel(row);', opening_times)
        self.assertIn('toggle.setAttribute("aria-controls", detail.id);', opening_times)
        self.assertIn('toggle.setAttribute("aria-expanded", "true");', opening_times)
        closer = script.split("function closePanel")[1].split("\nfunction ")[0]
        self.assertIn('panel.control.setAttribute("aria-expanded", "false")', closer)
        self.assertIn("rowPanel.delete(row)", closer)
        # C09: the copied journey has to say which ticket it is, or a handoff to
        # a seller can silently become a different one.
        journey = script.split("function journeyText")[1].split("\nfunction ")[0]
        # A reader in a named set gets that set's name; a reader in the cheapest
        # list chose a price rather than a ticket type, so the handoff names the
        # fare the row is actually priced as (Q4). The rule itself lives in
        # fareName, which the shortlist and the copied list read as well, so it
        # is asserted there and named here.
        self.assertIn('"Ticket: " + fareName(destination)', journey)
        self.assertIn("function fareName(destination)", script)

    def test_the_row_keeps_the_action_and_the_panel_holds_the_rest(self) -> None:
        # Finding 4 of the 29 September review: five controls in every row is a
        # hundred targets on page one, and four of them were things a reader
        # wants after deciding rather than while deciding. The row keeps the
        # ticket link, the expander and the shortlist toggle.
        script = page_script(self.html)
        row_cell = script.split("function cellWithLinks")[1].split("function cardNote")[0]
        self.assertIn('link.textContent = "Tickets"', row_cell)
        self.assertIn("toggle.insertAdjacentHTML(\"beforeend\", CHEVRON)", row_cell)
        for moved in ("Card details", "Copy the journey details", "copyJourney(", "toggleShortlist("):
            self.assertNotIn(moved, row_cell)
        # ... and the panel builds them, in one box, with the copy text landing
        # in that same box when the clipboard is refused.
        actions = script.split("function rowActions")[1].split("\nfunction ")[0]
        self.assertNotIn("Card details", actions)
        self.assertIn('copy.textContent = "Copy"', actions)
        self.assertIn("copyJourney(destination, copy, tools)", actions)
        copy_path = script.split("function copyJourney")[1].split("function showCopyText")[0]
        self.assertIn("showCopyText(host, text, button)", copy_path)
        manual = script.split("function showCopyText")[1].split("\nfunction ")[0]
        self.assertIn("host.append(box);", manual)

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

class TwoPartRowTest(unittest.TestCase):
    """ADR-0061: a journey the feed prices in two parts is one row.

    Grantham has no flow to Leicester or to Skegness in the return network,
    and the timetable reaches both with one change. The feed prices each leg.
    """

    MONDAY = date(2026, 10, 5)

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.feed = Path(self.tmp) / "feed"
        build_synthetic_feed(self.feed, include_restrictions=True, include_return_network=True)
        build_synthetic_timetable(self.feed, include_return_network=True)
        self.fares = FaresDb().load_feed(self.feed)
        self.timetable = TimetableDb().load_feed(self.feed)

    def rows(self, payload: dict, key: str = "destinations") -> dict:
        return {row["crs"]: row for row in payload[key]}

    def test_the_row_is_priced_at_both_fares_and_names_both_tickets_and_the_change(self) -> None:
        payload = build_demo_page.build_payload(self.fares, self.timetable, "GRN", day=self.MONDAY)
        leicester = self.rows(payload)["LEC"]
        # Wider rule: the journey changes at Nottingham but calls at Lincoln on
        # the first train. Lincoln is the cheaper valid split (870+2680), so
        # the pricing locus and the physical change need not be the same station.
        self.assertEqual(leicester["adultPence"], 870 + 2680)
        self.assertEqual(leicester["partyPence"], (870 + 2680) * 2)
        self.assertEqual(
            [(t["ticket"], t["fromCrs"], t["toCrs"], t["adultPence"]) for t in leicester["tickets"]],
            [("SDR", "GRN", "LCN", 870), ("SDR", "LCN", "LEC", 2680)],
        )
        self.assertEqual(leicester["changes"], 1)
        self.assertEqual(leicester["changeStations"], [{"crs": "NOT", "name": "NOTTINGHAM"}])
        self.assertEqual(leicester["ticket"], "SDR + SDR")
        # Both tickets carry their own restriction facts; the second is 1A.
        self.assertEqual([t["restrictionCode"] for t in leicester["tickets"]], ["", "1A"])
        self.assertTrue(leicester["tickets"][1]["restrictionDescription"])
        self.assertIn("1A", payload["restrictionValidity"])
        # A two-ticket row is a card decision per ticket, so its card price is
        # the two card prices added together: 1200 (the £12.00 minimum, above
        # two-thirds of the 870 first fare) plus 1785 (two-thirds of 2680,
        # rounded down to 5p). Reporting no card at all showed the reader two
        # standard fares they could plausibly beat.
        yng = leicester["railcards"]["YNG"]
        self.assertEqual(yng["state"], "eligible")
        self.assertEqual(yng["pricePence"], 1200 + 1785)
        self.assertEqual(yng["minimumFarePence"], 1200 + 1200)
        self.assertIn("R9", payload["railcardRules"][yng["rule"]]["text"])
        self.assertLess(yng["pricePence"], leicester["adultPence"])

    def test_the_pair_is_the_journeys_own_and_not_the_cheapest(self) -> None:
        # Skegness's journey changes at Lincoln, so it is quoted the Lincoln
        # pair, in every list whose selector prices both tickets.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "GRN", day=self.MONDAY)
        for key in ("destinations", "anytimeDestinations"):
            skegness = self.rows(payload, key)["SLD"]
            self.assertEqual(skegness["adultPence"], 870 + 3240, key)
            self.assertEqual([t["toCrs"] for t in skegness["tickets"]], ["LCN", "SLD"], key)
            self.assertEqual(skegness["changeStations"][0]["crs"], "LCN", key)




    def test_two_ticket_wording_names_a_change_only_when_the_journey_changes(self) -> None:
        # The panel must not say "changing at" for a through train priced in
        # two parts. Prove the JS helpers the page embeds.
        import subprocess

        payload = build_demo_page.build_payload(self.fares, self.timetable, "GRN", day=self.MONDAY)
        html = render_page(payload, budget_pounds=40)
        self.assertIn("priced via ", html)
        self.assertIn("stay on the train", html)
        self.assertIn("(destination.changes || 0) === 0", html)

        def js_function(source: str, name: str) -> str:
            marker = "function " + name + "(destination) {"
            at = source.index(marker)
            depth = 0
            index = at + len(marker) - 1
            while index < len(source):
                char = source[index]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return source[at : index + 1]
                index += 1
            raise AssertionError(name + " did not close")

        # The page's JavaScript is a file of its own (F1 of the 8 October 2026
        # agent-efficiency audit), so this reads the block the page ships rather
        # than a copy of it inside a Python string.
        source = (Path(__file__).resolve().parents[1] / "page" / "station.js").read_text(encoding="utf-8")
        script = (
            js_function(source, "fareSentence")
            + "\n"
            + js_function(source, "fareSummary")
            + "\n"
            + "const through = {tickets:[{toName:'NOTTINGHAM'}], changes:0};\n"
            + "const changed = {tickets:[{toName:'LINCOLN'}], changes:1};\n"
            + "process.stdout.write(JSON.stringify({\n"
            + "  throughSentence: fareSentence(through),\n"
            + "  throughSummary: fareSummary(through),\n"
            + "  changedSentence: fareSentence(changed),\n"
            + "  changedSummary: fareSummary(changed),\n"
            + "}));\n"
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        shown = json.loads(result.stdout)
        self.assertEqual(
            shown["throughSentence"],
            "Two tickets, priced via NOTTINGHAM (stay on the train): "
            "the price is the two fares added together.",
        )
        self.assertEqual(
            shown["throughSummary"],
            "Two tickets, bought separately, priced via NOTTINGHAM (stay on the train).",
        )
        self.assertNotIn("changing at", shown["throughSentence"])
        self.assertNotIn("changing at", shown["throughSummary"])
        self.assertEqual(
            shown["changedSentence"],
            "Two tickets, changing at LINCOLN: the price is the two fares added together.",
        )
        self.assertEqual(
            shown["changedSummary"],
            "Two tickets, bought separately, changing at LINCOLN.",
        )

    def test_a_direct_journey_prices_via_a_calling_point(self) -> None:
        # Bulwell is reached on one train that calls at Nottingham. Strict
        # change-station-only would skip it (changes == 0). Wider keeps the
        # Nottingham calling point and prices both published fares.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "GRN", day=self.MONDAY)
        bulwell = self.rows(payload)["BUL"]
        self.assertEqual(bulwell["changes"], 0)
        self.assertEqual(bulwell["changeStations"], [])
        self.assertEqual(bulwell["adultPence"], 1160 + 410)
        self.assertEqual(
            [(t["ticket"], t["fromCrs"], t["toCrs"], t["adultPence"]) for t in bulwell["tickets"]],
            [("CDR", "GRN", "NOT", 1160), ("SDR", "NOT", "BUL", 410)],
        )

    def test_a_place_with_its_own_fare_keeps_its_one_ticket_row(self) -> None:
        payload = build_demo_page.build_payload(self.fares, self.timetable, "GRN", day=self.MONDAY)
        for row in payload["destinations"]:
            if row["crs"] in {"LCN", "NOT", "PBO", "KGX"}:
                self.assertNotIn("tickets", row, row["crs"])

    def test_without_a_journey_there_is_no_change_to_price_at(self) -> None:
        # A prices-only build has no journey to read the change from, and a
        # pair guessed without one would be the cheapest pair, not the
        # journey's. Sunday's network does not reach Leicester with one change.
        prices_only = build_demo_page.build_payload(self.fares, None, "GRN", day=self.MONDAY)
        self.assertFalse(any("tickets" in row for row in prices_only["destinations"]))
        sunday = build_demo_page.build_payload(self.fares, self.timetable, "GRN", day=date(2026, 10, 11))
        self.assertNotIn("LEC", self.rows(sunday))

    def test_a_one_origin_build_carries_the_row_from_a_parse_and_from_its_cache(self) -> None:
        # The page a reader gets, through the focused load and its fares cache:
        # the second ticket comes from the change station's fares, which a
        # one-origin load used to drop and an index used to leave behind.
        out = Path(self.tmp) / "site" / "index.html"
        cache = Path(self.tmp) / "cache"
        argv = [
            "--feed", str(self.feed), "--timetable", str(self.feed), "--origin", "GRN",
            "--date", self.MONDAY.isoformat(), "--out", str(out),
        ]
        pages = []
        with mock.patch.object(build_demo_page, "CACHE_DIR", cache):
            for _ in range(2):
                said = io.StringIO()
                with contextlib.redirect_stdout(said):
                    self.assertEqual(build_demo_page.main(argv), 0)
                pages.append((said.getvalue(), embedded_payload(station_page(out).read_text(encoding="utf-8"))))
        (parsed_log, parsed), (restored_log, restored) = pages
        self.assertIn("wrote GRN.pickle", parsed_log)
        self.assertIn("restored from GRN.pickle", restored_log)
        for payload in (parsed, restored):
            leicester = self.rows(payload)["LEC"]
            self.assertEqual(leicester["adultPence"], 870 + 2680)
            self.assertEqual([t["ticket"] for t in leicester["tickets"]], ["SDR", "SDR"])
        self.assertEqual(self.rows(parsed)["LEC"], self.rows(restored)["LEC"])
