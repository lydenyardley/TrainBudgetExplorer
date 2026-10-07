"""Tests for the demo page generator."""

from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from unittest import mock
from datetime import date
import contextlib
import io
from pathlib import Path

import build_demo_page
import build_workers
import run
from build_demo_page import DEFAULT_PRICE_SOURCE, NOTICES, notices_or_attribution
import argparse
from atoc_fares import LOCATION, FLOW_F, FLOW_T, TICKET_TYPE, FaresDb
from atoc_timetable import TimetableDb
from build_workers import (  # noqa: E402
    ONE_WORKER_FLOOR,
    PARENT_BYTES,
    RESERVED_BYTES,
    WORKER_BYTES,
    free_memory_bytes,
    worker_budget,
)
from build_demo_page import (
    nre_attribution,
    wants_nre_credit,
    build_payload,
    build_station_index,
    encode_payload,
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


def hydrate_rows(payload: dict) -> dict:
    """The payload as the page reads it: each row table turned back into objects.

    The build ships a row list as a column list and a table of cells, and the page
    hydrates them as it loads, so a test that read the wire text directly would be
    asserting a shape no reader of the page ever sees.
    """
    for key in ("destinations", "singleDestinations", "anytimeDestinations", "stations"):
        table = payload.get(key)
        if isinstance(table, dict) and isinstance(table.get("rows"), list):
            pool = payload.get("pool") or []
            payload[key] = [
                {
                    field: pool[-cell - 1] if isinstance(cell, int) and cell < 0 else cell
                    for field, cell in zip(table["columns"], cells)
                }
                for cells in table["rows"]
            ]
    payload.pop("pool", None)
    return payload


def embedded_text(html: str) -> str:
    """The payload exactly as the page's own script receives it."""
    start = html.index("const DATA = ") + len("const DATA = ")
    return html[start : html.index(";", start)]


def embedded_payload(html: str) -> dict:
    match = re.search(r"const DATA = (\{.*?\});\n", html, re.DOTALL)
    if match is None:
        raise AssertionError("the page carries no embedded payload")
    return hydrate_rows(json.loads(match.group(1)))


def serialised_callback_lines(source: str) -> list[str]:
    """The lines of every page callback node does not run where it is written.

    ``page.evaluate`` stringifies its callback and the page parses the string
    again, so the text inside one is read twice by two parsers. Pairing the
    brackets by hand is enough here: the suite's callbacks are either an
    arrow function in parentheses or a brace-delimited block, and a suite that
    made that untrue would fail to run at all.
    """
    lines: list[str] = []
    for call in re.finditer(r"page\.(?:evaluate|waitForFunction|evaluateHandle)\(", source):
        depth = 0
        index = source.index("(", call.end() - 1)
        while index < len(source):
            if source[index] == "(":
                depth += 1
            elif source[index] == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        lines.extend(source[source.index("(", call.end() - 1) : index + 1].split("\n"))
    return lines


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



def page_script(html: str) -> str:
    """The page's own script, which is the last one in the file.

    The theme block is injected into the head so the palette is decided before
    the first paint, so the *first* script is no longer the page's script, and a
    test reading that slice is reading the theme block. The page's own script
    is the last one, and this says so in one place instead of at fourteen.
    """
    return html.split("<script>")[-1].split("</script>")[0]


def page_markup(html: str) -> str:
    """The page's markup: everything before the page's own script opens."""
    if "<script>" not in html:
        return html
    return html[: html.rindex("<script>")]


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
        # hands the route back the value.
        self.assertIn("attachStationField({", chooser)
        self.assertIn("onChange: () => render(),", chooser)
        self.assertIn("field: pick,", chooser)
        self.assertIn('const needle = pick ? pick.value.trim().toLowerCase() : "";', chooser)
        self.assertIn("if (pick) pick.focus();", chooser)
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


class OnlyStationsCliTest(unittest.TestCase):
    """`--only-stations`: a few stations, and still one site.

    The flag exists so a person can build two stations to read without paying
    for the other 2,710. What must not change is the contract underneath it: the
    chooser offers what was written, the release manifest names what was
    written, and a code the feed does not price is refused rather than quietly
    dropped -- because a subset that quietly drops one of the two codes you
    named is a build that lies about what it wrote.
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

    def build(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build_demo_page.main(
                [
                    "--feed",
                    str(self.feed),
                    "--timetable",
                    str(self.timetable),
                    "--all-origins",
                    "--out",
                    str(self.out),
                    *extra,
                ]
            )
        return code, out.getvalue(), err.getvalue()

    def page(self, slug: str) -> str:
        return (self.out.parent / "from" / slug / "index.html").read_text(encoding="utf-8")

    def written_slugs(self) -> list[str]:
        from_dir = self.out.parent / "from"
        if not from_dir.is_dir():
            return []
        return sorted(child.name for child in from_dir.iterdir())

    def test_only_the_named_station_gets_a_page(self) -> None:
        code, said, _ = self.build("--only-stations", "GRN")
        self.assertEqual(code, 0)
        self.assertEqual(self.written_slugs(), ["grantham"])
        self.assertRegex(said, r"Building 1 of the feed's [\d,]+ priceable station\(s\): GRN")

    def test_two_named_stations_are_one_site_with_one_chooser(self) -> None:
        code, _, _ = self.build("--only-stations", "GRN,NOT")
        self.assertEqual(code, 0)
        self.assertEqual(self.written_slugs(), ["grantham", "nottingham"])
        chooser = (self.out.parent / "index.html").read_text(encoding="utf-8")
        self.assertIn("/from/grantham/", chooser)
        self.assertIn("/from/nottingham/", chooser)

    def test_the_station_list_offers_the_subset_and_nothing_else(self) -> None:
        self.build("--only-stations", "GRN")
        stations_js = (self.out.parent / build_demo_page.STATION_ASSET_NAME).read_text(
            encoding="utf-8"
        )
        self.assertIn('"name":"GRANTHAM"', stations_js)
        self.assertNotIn("NOTTINGHAM", stations_js)

    def test_the_release_manifest_names_the_subset(self) -> None:
        self.build("--only-stations", "GRN")
        manifest = json.loads(
            (self.out.parent / build_demo_page.RELEASE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(
            sorted(manifest["routes"]), ["/", "/from/grantham/", "/privacy/"]
        )

    def test_a_subset_page_is_a_full_page_not_a_summary(self) -> None:
        # The point of the flag is a page you can read: with the timetable
        # loaded it must carry what the prices-only build of the same station
        # cannot show. Asserted as a difference between the two builds rather
        # than against any wording, because the wording is the template's
        # business and this is the flag's.
        self.build("--only-stations", "GRN")
        with_times = self.page("grantham")
        second = Path(self._tmp.name) / "prices"
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build_demo_page.main(
                [
                    "--feed",
                    str(self.feed),
                    "--all-origins",
                    "--only-stations",
                    "GRN",
                    "--out",
                    str(second / "index.html"),
                ]
            )
        self.assertEqual(code, 0)
        without_times = (second / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        # The page says so in its own payload, which is the build's answer and
        # not the template's wording: "no timetable in this build" also appears
        # in the template's shortlist fallback, so it would pass either way.
        self.assertIn('"hasJourneys":true', with_times)
        self.assertIn('"hasJourneys":false', without_times)

    def test_a_code_the_feed_does_not_price_is_refused_and_nothing_is_written(self) -> None:
        code, _, err = self.build("--only-stations", "GRN,ZZZ")
        self.assertEqual(code, 2)
        self.assertIn("ZZZ", err)
        self.assertFalse(self.out.parent.exists(), "a refused build must write nothing")

    def test_lowercase_and_spaced_codes_are_accepted(self) -> None:
        code, said, _ = self.build("--only-stations", " grn , not ")
        self.assertEqual(code, 0)
        self.assertEqual(self.written_slugs(), ["grantham", "nottingham"])
        self.assertIn("GRN, NOT", said)

    def test_no_code_at_all_is_refused_rather_than_building_nothing(self) -> None:
        code, _, err = self.build("--only-stations", " , ")
        self.assertEqual(code, 2)
        self.assertIn("no code", err)

    def test_without_all_origins_the_flag_is_refused_rather_than_ignored(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build_demo_page.main(
                [
                    "--feed",
                    str(self.feed),
                    "--only-stations",
                    "GRN,NOT",
                    "--out",
                    str(self.out),
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("--all-origins", err.getvalue())


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



class SharedStationAssetTest(unittest.TestCase):
    """Unit 1d: the picker's list is one file per site, not a copy per page.

    The station list was the release's largest repeated item -- the same rows on
    every page, 445 MB across the projected network -- so the network build
    writes it once and each page names it. The page's own destinations still
    travel inside it (ADR-0033, re-scoped), and a page whose copy of the list
    did not arrive states the station as text rather than offering a control
    that opens nothing.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.feed = build_synthetic_feed(root / "fares", include_restrictions=True)
        self.timetable = build_synthetic_timetable(root / "timetable")
        self.out = root / "site" / "index.html"
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
        self.log = buffer.getvalue()
        self.site = self.out.parent

    def test_the_whole_site_gets_one_station_asset(self) -> None:
        assets = sorted(self.site.rglob("stations.js"))
        self.assertEqual(
            [path.relative_to(self.site).as_posix() for path in assets], ["stations.js"]
        )
        asset = assets[0].read_text(encoding="utf-8")
        self.assertIn("window.TBE_STATIONS = ", asset)
        rows = json.loads(asset.split("window.TBE_STATIONS = ", 1)[1].rstrip().rstrip(";"))
        # Every station this build wrote, including each page's own: a page
        # filters its own origin out as it loads, which is what keeps this one
        # file byte-identical for every page.
        self.assertEqual(sorted(row["crs"] for row in rows), ["GRN", "NOT"])
        self.assertTrue(all(row["href"].startswith("/from/") for row in rows))
        self.assertIn("stations.js", self.log)

    def test_a_station_page_names_the_asset_and_ships_no_station_rows(self) -> None:
        pages = sorted((self.site / "from").glob("*/index.html"))
        self.assertEqual(len(pages), 2)
        for page in pages:
            html = page.read_text(encoding="utf-8")
            self.assertIn('<script src="/stations.js"></script>', html)
            self.assertNotIn('"stations":', embedded_text(html))
            # The page keeps its own destination rows, and the heading control
            # is still the page's own markup rather than something built here.
            self.assertIn('id="changeOrigin"', html)
            self.assertTrue(embedded_payload(html)["destinations"])

    def test_the_page_puts_the_station_name_back_if_the_asset_does_not_arrive(self) -> None:
        page = (self.site / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        self.assertIn("if (window.TBE_STATIONS) {", page)
        # The fallback is a name in the heading, never an empty one: a heading
        # reading "from" and nothing is the failure this guards against.
        self.assertIn('stationName.className = "origin-name";', page)
        self.assertIn('stationName.textContent = DATA.origin ? DATA.origin.name : "";', page)
        self.assertIn("changeOrigin.replaceWith(stationName);", page)
        self.assertIn("originPicker.remove();", page)
        self.assertIn("fallbackNote.textContent = FIRST_USE_FALLBACK;", page)

    def test_the_stylesheet_is_written_once_and_named_for_its_own_bytes(self) -> None:
        # One file beside the pages, and every station page names it. The
        # filename holds a digest of the stylesheet, so a changed stylesheet is
        # a new file: a cached copy can never be served beside a page built
        # from another revision of the CSS, and no build step has to be told to
        # rename anything.
        from page_templates import STATION_STYLESHEET

        name = build_demo_page.station_style_asset_name()
        assets = sorted(path.name for path in self.site.rglob("*.css"))
        self.assertEqual(assets, [name], assets)
        written = (self.site / name).read_text(encoding="utf-8")
        self.assertEqual(written, STATION_STYLESHEET)
        self.assertTrue(name.startswith("station-") and name.endswith(".css"), name)
        self.assertRegex(name, r"^station-[0-9a-f]{12}\.css$")
        self.assertIn(name, self.log, "the build says what it wrote and where")

    def test_every_station_page_links_the_stylesheet_and_inlines_none_of_it(self) -> None:
        pages = sorted((self.site / "from").glob("*/index.html"))
        self.assertEqual(len(pages), 2)
        for page in pages:
            html = page.read_text(encoding="utf-8")
            self.assertIn(build_demo_page.station_style_tag("/" + build_demo_page.station_style_asset_name()), html)
            # Not inlined: the whole point is that 2,712 pages stop carrying the
            # same 34.6 KB, so a page that still held a <style> element would
            # mean the file is being fetched and paid for anyway.
            self.assertNotIn("<style>", html)
            # And the script stays inline, because it draws the page's own
            # rows: a request that did not arrive would leave an empty table,
            # which is not a failure mode the picker models (ADR-0047).
            self.assertIn("const DATA = ", html)
            self.assertIn("function render()", html)

    def test_the_page_takes_the_switch_away_when_the_stylesheet_does_not_arrive(self) -> None:
        # The picker's failure mode, one route down: a control that cannot do
        # what it offers is removed rather than left inert, and the page says
        # what state it is in. A switch that rewrites an attribute no rule reads
        # is the same defect as a picker that opens an empty panel.
        page = (self.site / "from" / "grantham" / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="sub" id="styleNote" hidden', page)
        self.assertIn("function stylesheetArrived() {", page)
        self.assertIn('.getPropertyValue("--tbe-stylesheet").trim() !== "";', page)
        self.assertIn("if (!stylesheetArrived()) {", page)
        self.assertIn("toggle.remove();", page)
        self.assertIn("note.hidden = false;", page)
        self.assertIn("styling did not load", page)
        # Asked again once the page has loaded, because a stylesheet still in
        # flight when the body exists has not failed yet.
        self.assertIn('window.addEventListener("load", function () {', page)
        # A page whose stylesheet is here keeps the switch, whatever the order
        # the two events arrived in.
        self.assertIn("    toggle.hidden = false;", page)
        self.assertIn("if (toggle && !toggle.hidden) return;", page)

    def test_the_crawl_resolves_a_stylesheet_a_page_asks_for(self) -> None:
        # The crawl read href attributes only, so a page could have asked for a
        # stylesheet the build never wrote and the run would still have said
        # every internal link resolves. A shared document is a route like any
        # other, and it is named in src as well as href.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text(
                '<link rel="stylesheet" href="/station-abc.css">', encoding="utf-8"
            )
            broken = build_demo_page.crawl_internal_links(site)
            self.assertEqual(len(broken), 1, broken)
            self.assertIn("station-abc.css", broken[0])
            (site / "station-abc.css").write_text(":root { --x: 1; }", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site), [])
            # And a <script src> is followed now, which it was not: the
            # picker's asset was named in one and the crawl never looked.
            (site / "index.html").write_text(
                '<script src="/stations.js"></script>', encoding="utf-8"
            )
            self.assertEqual(
                [entry.split(" links to ")[1].split(",")[0] for entry in
                 build_demo_page.crawl_internal_links(site)],
                ["/stations.js"],
            )

    def test_the_asset_is_the_whole_list_in_plain_objects(self) -> None:
        rows = build_demo_page.station_asset_rows(
            [{"name": "A & B", "crs": "ABB", "slug": "a-b", "destinations": 2}],
            base_path="/tb",
        )
        self.assertEqual(rows, [{"name": "A & B", "crs": "ABB", "href": "/tb/from/a-b/"}])
        asset = build_demo_page.render_station_asset(rows)
        self.assertTrue(asset.endswith(";\n"), asset[-20:])
        # Plain objects keep "href" in the file, which is the shape the route
        # crawl reads: a table of cells would hide every option from it.
        self.assertIn('"href":"/tb/from/a-b/"', asset)

    def test_the_crawl_reads_the_asset_and_fails_a_route_it_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / "from" / "grantham").mkdir(parents=True)
            (site / "from" / "grantham" / "index.html").write_text(
                "<p>the page asks for the asset, and the asset asks for a route</p>",
                encoding="utf-8",
            )
            (site / "stations.js").write_text(
                'window.TBE_STATIONS = [{"name":"LINCOLN","crs":"LCN","href":"/from/lincoln/"}];\n',
                encoding="utf-8",
            )
            broken = build_demo_page.crawl_internal_links(site)
            self.assertEqual(len(broken), 1, broken)
            self.assertIn("stations.js", broken[0])
            self.assertIn("/from/lincoln/", broken[0])
            (site / "from" / "lincoln").mkdir()
            (site / "from" / "lincoln" / "index.html").write_text("ok", encoding="utf-8")
            self.assertEqual(build_demo_page.crawl_internal_links(site), [])


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

    def test_the_timetable_cache_key_covers_the_code_that_reads_the_feed(self) -> None:
        # The key is the feed's bytes, the focus, and `source_fingerprint` --
        # and the fingerprint covers atoc_timetable.py, so a change to how the
        # feed is *read* invalidates the cache even when the bytes are the same.
        # That is the case a fingerprint over the feed alone cannot catch, and
        # it is not hypothetical: fixing how `0000` is read (that record is the
        # CIF's absent marker, not midnight) changes no byte of the download and
        # changes every calling point the cache holds. A build that kept the
        # old pickle would serve the old timetables and say nothing.
        self.assertIn("atoc_timetable.py", build_demo_page.SOURCE_FILES)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feed = build_synthetic_timetable(root / "timetable")
            before = build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"})
            # Every source file the fingerprint hashes is read off disk and
            # written back, so a one-byte change anywhere in the parser shows up
            # in the cache name. Nothing is left edited: a suite that dirties
            # the tree it runs in is a suite that cannot be trusted to report
            # this at all.
            touched = []
            try:
                for name in build_demo_page.SOURCE_FILES:
                    source = pathlib.Path(build_demo_page.__file__).parent / name
                    original = source.read_bytes()
                    touched.append((source, original))
                    source.write_bytes(original + b"\n")
                build_demo_page.source_fingerprint.cache_clear()
                after = build_demo_page.timetable_cache_path(feed, "GRN", {"LCN", "NOT"})
            finally:
                for source, original in touched:
                    source.write_bytes(original)
                build_demo_page.source_fingerprint.cache_clear()
        self.assertNotEqual(
            before, after,
            "a change to any source file the parser reads is a different cache",
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
    A release now writes a root at the site root -- the chooser when it offers a
    choice, and the one station named in the heading when that is all it priced
    (recommendation 2, 30 September 2026) -- one page per station at its
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

    def test_a_single_origin_build_is_a_site_with_its_own_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, log = self.build_site(root)
            self.assertEqual(code, 0)
            site = root / "site"
            # The root is this release's own: it names the one station it priced
            # rather than asking for it, the station has its canonical route, and
            # the privacy page the footer links to is present (S01, S04, rec 2).
            chooser = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn("const STATIONS", chooser)
            self.assertNotIn("const DATA", chooser)  # the root carries no fares
            self.assertNotIn('id="originSearch"', chooser)
            self.assertIn('class="origin-name"', chooser)
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
        # Built with --all-origins, because a one-station release has no search
        # to wire: its root names the station instead of asking for it (rec 2).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_site(root, "--all-origins")
            chooser = (root / "site" / "index.html").read_text(encoding="utf-8")
            self.assertIn("attachStationField({", chooser)
            self.assertIn("onChange: () => render(),", chooser)

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


class RunnerPassthroughTest(unittest.TestCase):
    """What `python run.py` can reach on the builder.

    The runner assembles a fixed argument list, so a flag the builder
    understands is a flag the double-click path cannot pass. That is how the
    licence notice and the privacy contact became unreachable from the entry
    point a first-time user actually takes: a real feed could only be built by
    calling the builder by hand. These assert the argument list, because that
    is the whole of the passthrough -- the build itself is covered elsewhere.
    """

    def _command(self, **overrides) -> list[str]:
        captured: list[str] = []

        class _Result:
            returncode = 0

        def fake_run(cmd, cwd=None):
            captured.extend(cmd)
            return _Result()

        values = {
            "feed": Path("feeds/fares"),
            "origin": "GRA",
            "timetable": None,
            "with_single_timetable": False,
            "date": None,
            "all_origins": False,
            "base_path": None,
            "notices": None,
            "privacy_contact": None,
        }
        values.update(overrides)
        args = argparse.Namespace(**values)
        with mock.patch.object(run, "ROOT", Path(__file__).parent.parent), mock.patch.object(
            run, "_feed_exists", return_value=True
        ), mock.patch.object(run.subprocess, "run", fake_run), contextlib.redirect_stdout(
            io.StringIO()
        ):
            run.build(args)
        return captured

    def test_the_notice_and_contact_flags_reach_the_builder(self) -> None:
        command = self._command(
            notices="rdg,ogl,accuracy", privacy_contact="me@example.org"
        )
        self.assertIn("--notices", command)
        self.assertEqual(command[command.index("--notices") + 1], "rdg,ogl,accuracy")
        self.assertEqual(command[command.index("--privacy-contact") + 1], "me@example.org")

    def test_neither_flag_is_passed_when_neither_was_given(self) -> None:
        # Passing an empty --notices would satisfy the builder's "is it
        # present" test with nothing in it, so an absent flag has to stay
        # absent rather than become an empty one. This is the synthetic feed:
        # nothing here is a public build, and crediting NRE for prices NRE did
        # not supply would be false attribution rather than a missing one.
        command = self._command(feed=run.ROOT / "_demo_feed")
        self.assertNotIn("--notices", command)
        self.assertNotIn("--privacy-contact", command)

    def test_a_real_feed_carries_every_notice_without_being_asked(self) -> None:
        # `python run.py` with no arguments swaps the demo feed for the
        # downloaded one the moment it exists, so the default path *is* a public
        # build. It used to be refused by the builder for carrying no notice,
        # which made the documented way to run the app fail as soon as the feeds
        # were downloaded. The set comes from the builder's own table, so a
        # notice added there cannot be missing here.
        command = self._command()
        self.assertIn("--notices", command)
        carried = command[command.index("--notices") + 1].split(",")
        self.assertEqual(sorted(carried), sorted(build_demo_page.NOTICES))
        self.assertEqual(len(carried), len(set(carried)))

    def test_a_narrower_notice_set_is_passed_verbatim(self) -> None:
        # The direction that is allowed is narrowing. A person who knows why
        # their release owes less can say so; nothing here widens a set past
        # what the builder offers.
        command = self._command(notices="rdg,ogl")
        self.assertEqual(command[command.index("--notices") + 1], "rdg,ogl")

    def test_a_real_feed_builds_through_the_runner_with_only_the_notice(self) -> None:
        # The contact now defaults in the builder, so the notice is the only
        # thing a real-feed build needs the runner to carry.
        self.assertIn("--notices", self._command(notices="rdg"))

    def test_an_explicitly_empty_notice_set_is_not_replaced_by_the_default(self) -> None:
        # The default is for a flag that was never passed. An empty one is a
        # person asking for no notice, and the honest answer is the builder's
        # refusal -- not this line handing over the set they just declined.
        self.assertNotIn("--notices", self._command(notices=""))


    def test_a_whole_network_run_asks_the_builder_for_what_this_machine_can_hold(self) -> None:
        # Left at the builder's default of one worker, the 2,712-page set
        # takes most of a working day: each origin's page is independent and
        # the work is CPU-bound, so one worker leaves every other core idle.
        # Cores were the wrong ceiling -- eight workers on this machine die
        # with a MemoryError having written no pages -- so the count is the
        # measured budget, and this holds the runner to passing it through
        # rather than recomputing it.
        command = self._command(all_origins=True)
        self.assertIn("--workers", command)
        workers = int(command[command.index("--workers") + 1])
        self.assertEqual(workers, worker_budget())
        self.assertGreaterEqual(workers, 1)
        self.assertLessEqual(workers, build_workers.MAX_WORKERS)
        # A single-origin run has one page to build, so a worker count says
        # nothing there and passing one would only misreport the shape of the
        # work.
        self.assertNotIn("--workers", self._command(all_origins=False))

    def test_a_relative_demo_feed_path_is_still_synthetic(self) -> None:
        # The same folder arrives as "_demo_feed" on the command line and as an
        # absolute path from the default. Comparing the two as strings would let
        # the relative one through as a real feed, and every generated price
        # would be credited to NRE.
        command = self._command(feed=Path("_demo_feed"))
        self.assertNotIn("--notices", command)


class RunnerBuildOrServeTest(unittest.TestCase):
    """Which of the two jobs the runner does on a given run.

    The decision is the point. A runner that rebuilds on every start cannot
    answer "is this the build I made?", and these tests are about that answer
    being knowable rather than about the build itself.
    """

    def run_main(self, *flags, site_exists=True, stale=False):
        served = []

        class FakeServer:
            allow_reuse_address = True

            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def serve_forever(self):
                served.append(1)

        # The flags are the tokens a reader would type, because the decision
        # under test belongs to run.py and a dict would rewrite them.
        argv = ["run.py"] + list(flags)
        # The decision turns on whether _site/ is there, so the two states have
        # to be real directories rather than a flag the runner cannot see.
        if site_exists:
            site = Path(__file__).parent.parent / "_site"
        else:
            site = Path(tempfile.mkdtemp()) / "never-built"
            self.addCleanup(shutil.rmtree, site.parent, True)
        builder = mock.Mock(return_value=0)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", argv))
            stack.enter_context(mock.patch.object(run, "SITE", site))
            stack.enter_context(mock.patch.object(run.socketserver, "ThreadingTCPServer", FakeServer))
            stack.enter_context(mock.patch.object(run, "webbrowser", mock.Mock()))
            stack.enter_context(mock.patch.object(run.threading, "Timer", mock.Mock()))
            stack.enter_context(mock.patch.object(run, "build", builder))
            # The freshness check reads this machine's file times, which
            # are not what is under test; the decision is.
            stack.enter_context(
                mock.patch.object(run, "sources_are_newer", lambda: stale)
            )
            stack.enter_context(mock.patch.object(run.os, "chdir", mock.Mock()))
            out = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            code = run.main()
        return code, out.getvalue(), builder.call_count, served

    def test_a_clean_checkout_builds_because_there_is_nothing_to_serve(self) -> None:
        _, _, builds, _ = self.run_main("--no-build", site_exists=True)
        self.assertEqual(builds, 0)
        _, _, builds, served = self.run_main(site_exists=False)
        self.assertEqual(builds, 1)
        self.assertEqual(len(served), 1)

    def test_a_second_run_serves_what_the_first_one_wrote(self) -> None:
        # --origin is the fast single-station build, and it is the one a
        # second run of it serves without rebuilding.
        _, said, builds, served = self.run_main("--origin", "GRA", site_exists=True)
        self.assertEqual(builds, 0)
        self.assertEqual(len(served), 1)
        self.assertIn("without rebuilding", said)

    def test_the_default_builds_the_whole_network(self) -> None:
        # A one-station build has nowhere for the heading's station control
        # to go, so the name renders as plain text -- the page that cannot
        # change station. The default is the network, and it says what that
        # costs before it starts.
        _, said, builds, served = self.run_main(site_exists=False)
        self.assertEqual(builds, 1)
        self.assertEqual(len(served), 1)
        self.assertIn("one page per priced station", said)
        self.assertIn("--origin GRA", said)

    def test_a_build_older_than_the_sources_is_not_served(self) -> None:
        # Nine hours of committed work, a double-clicked runner, and a page
        # from before it: nothing on the page says so. The runner rebuilds
        # when what it would serve is out of date, and names the reason.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            manifest = site / run.RELEASE_MANIFEST_NAME
            manifest.write_text("{}", encoding="utf-8")
            os.utime(manifest, (1000, 1000))
            with mock.patch.object(run, "SITE", site):
                self.assertTrue(run.sources_are_newer())
            os.utime(manifest, (time.time() + 60, time.time() + 60))
            with mock.patch.object(run, "SITE", site):
                self.assertFalse(run.sources_are_newer())
        # A build with no manifest answers no: an unreadable answer must
        # never be the one that starts an hour-long build.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(run, "SITE", Path(tmp)):
                self.assertFalse(run.sources_are_newer())

    def test_a_build_the_sources_have_moved_past_is_rebuilt(self) -> None:
        # Nine hours of committed work, a double-clicked runner and a page
        # from before it, with nothing on the page saying so. The runner
        # rebuilds when what it would serve is out of date, and says why.
        _, said, builds, served = self.run_main(
            "--origin", "GRA", site_exists=True, stale=True
        )
        self.assertEqual(builds, 1)
        self.assertEqual(len(served), 1)
        self.assertIn("newer than _site/", said)

    def test_rebuild_builds_even_when_a_site_is_already_there(self) -> None:
        _, _, builds, _ = self.run_main("--rebuild", site_exists=True)
        self.assertEqual(builds, 1)

    def test_no_build_refuses_rather_than_building_what_it_was_told_not_to(self) -> None:
        code, _, builds, served = self.run_main("--no-build", site_exists=False)
        self.assertEqual(code, 1)
        self.assertEqual(builds, 0)
        self.assertEqual(served, [])


class WorkerBudgetTest(unittest.TestCase):
    """How many build workers this machine can hold.

    `min(8, cpu_count())` was a core count wearing a memory claim. On a
    twelve-core machine with 15.8 GB it asked for eight, every worker was
    handed the whole national timetable, and the build died with a
    MemoryError in the pool initialiser after five minutes having written no
    pages -- reproducibly, twice. These hold the budget to the answers that
    matter rather than to the arithmetic behind them.
    """

    GB = 10 ** 9

    def test_a_machine_with_room_gets_the_measured_ceiling(self) -> None:
        # Twelve cores and plenty of memory is the case the ceiling exists
        # for: it is the machine the old core count got wrong.
        self.assertEqual(worker_budget(cores=12, free_bytes=16 * self.GB), 4)

    def test_the_ceiling_is_not_the_core_count(self) -> None:
        # The whole point: cores are not the question. Sixty-four cores with
        # room to spare still gets four, because four is the largest count
        # measured to finish a whole-network build.
        self.assertEqual(worker_budget(cores=64, free_bytes=64 * self.GB), 4)
        self.assertLess(worker_budget(cores=64, free_bytes=64 * self.GB), 64)

    def test_a_machine_without_room_gets_one_worker_and_still_builds(self) -> None:
        # Never zero. A build that cannot have a pool still builds, one page
        # at a time; refusing to build would be a worse answer than a slow one.
        for free in (0, 2 * self.GB, 6 * self.GB):
            with self.subTest(free=free):
                self.assertEqual(worker_budget(cores=12, free_bytes=free), 1)

    def test_the_floor_is_the_larger_phase_and_not_the_sum_of_both(self) -> None:
        # The parent loads both feeds and prices every origin; the workers then
        # hold one timetable each. `build_demo_page.py` releases the parent's
        # databases before the pool starts, so the two phases are sequential and
        # the machine needs room for the larger, not for both at once. The sum
        # was the right formula while the parent held its databases for the
        # whole build, and it is 900 MB too high now.
        self.assertEqual(
            ONE_WORKER_FLOOR,
            max(PARENT_BYTES, WORKER_BYTES) + RESERVED_BYTES,
        )
        self.assertLess(ONE_WORKER_FLOOR,
                        PARENT_BYTES + WORKER_BYTES + RESERVED_BYTES)

    def test_the_floor_still_covers_the_both_phases_case(self) -> None:
        # The floor is a floor, not a target: a machine with less free than this
        # cannot run the parent and the workers at all, so the build drops to
        # one. Checked against a whole number of gigabytes because the reserve
        # and the worker cost are both rounded up from a measurement.
        self.assertLessEqual(ONE_WORKER_FLOOR, 7 * 10 ** 9)
        self.assertGreater(ONE_WORKER_FLOOR, 6 * 10 ** 9)

    def test_the_core_count_still_bounds_it_from_below(self) -> None:
        # A two-core runner cannot use four workers whatever it has free.
        self.assertEqual(worker_budget(cores=2, free_bytes=16 * self.GB), 2)
        self.assertEqual(worker_budget(cores=1, free_bytes=16 * self.GB), 1)

    def test_a_platform_that_will_not_say_falls_back_on_the_ceiling(self) -> None:
        # None is not zero. A machine that will not report its memory gets the
        # measured count rather than the one-worker answer a zero would give.
        with mock.patch.object(build_workers, "free_memory_bytes", lambda: None):
            self.assertEqual(worker_budget(cores=12), 4)
        with mock.patch.object(build_workers, "free_memory_bytes", lambda: 0):
            self.assertEqual(worker_budget(cores=12), 1)

    def test_passing_none_means_ask_the_machine_not_trust_the_ceiling(self) -> None:
        # free_bytes=None is "I have not read it yet", which is not the same
        # answer as "the machine could not tell me". Conflating them would let
        # a caller who meant one get the other.
        with mock.patch.object(build_workers, "free_memory_bytes",
                               return_value=4 * self.GB),                 mock.patch.object(build_workers.os, "cpu_count", return_value=12):
            self.assertEqual(worker_budget(cores=12, free_bytes=None), 1)

    def test_the_budget_reads_the_machine_when_it_is_not_told(self) -> None:
        # The no-argument path is the one the runner and the workflow use, so
        # it has to consult the platform rather than answer from a constant.
        with mock.patch.object(build_workers, "free_memory_bytes",
                               return_value=16 * self.GB):
            with mock.patch.object(build_workers.os, "cpu_count", return_value=12):
                self.assertEqual(worker_budget(), 4)

    def test_free_memory_is_a_number_or_nothing_at_all(self) -> None:
        free = free_memory_bytes()
        self.assertTrue(free is None or (isinstance(free, int) and free > 0))

    def test_the_figures_the_budget_is_built_from_are_the_measured_ones(self) -> None:
        # Both constants are measurements now rather than recollections, so this
        # pins each in both directions. One below the figure it came from hands
        # out workers the machine cannot hold -- which is how this constant was
        # wrong by a factor of 2.4 for as long as it stood at 900 MB. One well
        # above refuses builds that would have finished.
        #
        # A little headroom is expected, because both are rounded up: the parent
        # is 4,017 MB measured here against 4,110 recorded. Ten per cent is
        # rounding up and not inventing, and it is what makes this catch a
        # constant doubled by an edit that was not looking for it.
        mb = 10 ** 6
        self.assertGreaterEqual(PARENT_BYTES, 4_110 * mb)
        self.assertLess(PARENT_BYTES, 4_110 * 1.1 * mb)
        self.assertGreaterEqual(WORKER_BYTES, 2_188 * mb)
        self.assertLess(WORKER_BYTES, 2_188 * 1.1 * mb)

    def test_four_workers_fitted_and_eight_did_not(self) -> None:
        # The reconciliation ADR-0057 records, held as arithmetic rather than
        # prose. A worker measures 2,188 MB through `init_worker` and
        # `build_page_job`. The parent is not added: it releases its databases
        # before the pool starts, so the workers are the whole of the tree's
        # demand while they run.
        #
        # Four workers is 8,752 MB against this machine's 15.8 GB, which is why
        # the four-worker build in the committed log finished. Eight is
        # 17,504 MB, which is why the eight-worker log holds a MemoryError
        # rather than a page. Note that four workers no longer fit in the 8 GB
        # the old records describe: that observation predates the corrected
        # worker figure and cannot be reproduced on today's feed.
        worker = 2_188
        machine = 15_800
        self.assertLess(4 * worker, machine)
        self.assertGreater(8 * worker, machine)
        self.assertGreater(4 * WORKER_BYTES, 8 * 10 ** 9)

    @staticmethod
    def _worker_branch() -> tuple[ast.AST, ast.AST]:
        """The two halves of the `if workers == 1` branch in the builder.

        Returns (in-process body, pool body). Found through the AST rather than
        by slicing the text, because the text of a 3,000-line module offers far
        too many places to start from and none of them are the right one.
        """
        tree = ast.parse((pathlib.Path(__file__).resolve().parent.parent
                          / "build_demo_page.py").read_text(encoding="utf-8"))
        found = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) in ("workers == 1", "max(1, args.workers) == 1")
        ]
        # Two sites assert on `workers`: the all-origins branch, which renders
        # in-process or in the pool, and the fast path's own default. Only the
        # first has a pool in its `orelse`.
        with_pool = [node for node in found if node.orelse]
        assert len(with_pool) == 1, f"expected one worker-count branch, got {len(with_pool)}"
        branch = with_pool[0]
        return branch.body, branch.orelse

    @staticmethod
    def _deleted_names(body: list[ast.stmt]) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(ast.Module(body=list(body), type_ignores=[])):
            if isinstance(node, ast.Delete):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
        return names

    def test_the_pool_branch_releases_the_databases_the_workers_do_not_need(self) -> None:
        # The budget divides free memory by a worker's cost and does not add the
        # parent's, because `build_demo_page.py` drops `fares` and `timetable`
        # before the pool starts. That premise lives in one place in the source,
        # and if the release is moved, narrowed or deleted the division starts
        # overcounting, so a machine gets more workers than it can hold. So the
        # premise is pinned where it is written.
        _in_process, pool = self._worker_branch()
        released = self._deleted_names(pool)
        self.assertIn("fares", released)
        self.assertIn("timetable", released)

    def test_the_in_process_branch_keeps_the_databases_it_renders_from(self) -> None:
        # The other half, and the one a careless reader of the test above would
        # break. With one worker the build renders in this process and puts both
        # objects straight into `_WORKER`, so releasing them there would delete
        # the databases the build is about to use. No number in this file can
        # catch that; only the placement can.
        in_process, _pool = self._worker_branch()
        # Structurally rather than by text: `ast.unparse` normalises quotes, so
        # a test written against the source's own spelling fails on `"` vs `'`
        # and says nothing about the code.
        handed = {
            (node.targets[0].slice.value, node.value.id)
            for node in ast.walk(ast.Module(body=list(in_process), type_ignores=[]))
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Subscript)
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "_WORKER"
            and isinstance(node.targets[0].slice, ast.Constant)
            and isinstance(node.value, ast.Name)
        }
        self.assertIn(("fares", "fares"), handed)
        self.assertIn(("timetable", "timetable"), handed)
        self.assertEqual(self._deleted_names(in_process), set())


class RunnerWorkerCountTest(unittest.TestCase):
    """That `python run.py` asks the budget rather than counting cores.

    It carries its own harness rather than borrowing the passthrough test's,
    because that one redirects stdout internally and the notice this is about
    is printed. A harness that swallowed the line under test could not assert
    on it.
    """

    GB = 10 ** 9

    def setUp(self) -> None:
        self.saved = (run.worker_budget, run.free_memory_bytes)
        self.addCleanup(setattr, run, "worker_budget", self.saved[0])
        self.addCleanup(setattr, run, "free_memory_bytes", self.saved[1])

    def _build(self, workers: int, free: int | None) -> tuple[list[str], str]:
        run.worker_budget = lambda free_bytes=None: workers
        run.free_memory_bytes = lambda: free

        captured: list[str] = []

        class _Result:
            returncode = 0

        def fake_run(cmd, cwd=None):
            captured.extend(cmd)
            return _Result()

        args = argparse.Namespace(
            feed=Path("feeds/fares"), origin=None, timetable=None,
            with_single_timetable=False, date="2026-10-02", all_origins=True,
            base_path=None, notices=None, privacy_contact=None,
        )
        out = io.StringIO()
        with mock.patch.object(run, "ROOT", Path(__file__).parent.parent),                 mock.patch.object(run, "_feed_exists", return_value=True),                 mock.patch.object(run.subprocess, "run", fake_run),                 contextlib.redirect_stdout(out):
            run.build(args)
        return captured, out.getvalue()

    def test_the_runner_passes_the_budget_to_the_builder(self) -> None:
        command, _ = self._build(3, 16 * self.GB)
        self.assertIn("--all-origins", command)
        self.assertEqual(command[command.index("--workers") + 1], "3")

    def test_the_runner_says_which_count_it_chose_and_what_it_had_to_work_with(self) -> None:
        # "1 worker" on its own does not say whether that was the ceiling or a
        # shortage of memory, and those are different problems for whoever has
        # to wait for the build.
        _, said = self._build(1, 4 * self.GB)
        self.assertIn("1 worker(s)", said)
        self.assertIn("4.0 GB free", said)

    def test_a_platform_that_cannot_report_memory_is_not_reported_as_having_none(self) -> None:
        _, said = self._build(4, None)
        self.assertIn("4 worker(s)", said)
        self.assertNotIn("GB free", said)

    def test_the_runner_no_longer_asks_for_the_core_count(self) -> None:
        source = Path(run.__file__).read_text(encoding="utf-8")
        self.assertNotIn("min(8, os.cpu_count()", source)
        self.assertIn("worker_budget(", source)
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

    def test_every_row_carries_the_backlog_day_out_lists(self) -> None:
        # ADR-0062: the station cell reads rspbSites, nationalTrustSites and
        # nationalParkSites off each row, so a row without one would render an
        # undefined proof. The key is always present and always a list.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        for row in payload["destinations"]:
            for key in ("rspbSites", "nationalTrustSites", "nationalParkSites"):
                self.assertIsInstance(row[key], list, (row["crs"], key))

    def test_some_fares_sit_above_the_railcard_minimum_and_some_below(self) -> None:
        # Both directions matter: a card with nothing to discount cannot be
        # exercised, and a card that discounts every fare cannot show what the
        # page does with one it does not beat.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        prices = [row["adultPence"] for row in payload["anytimeDestinations"]]
        self.assertTrue(any(p > 1200 for p in prices), "nothing is above the £12.00 minimum")
        self.assertTrue(any(p < 1200 for p in prices), "nothing is below the £12.00 minimum")
        self.assertTrue(
            any(card["eligibleCount"] > 0 for card in payload["railcards"]),
            "no card discounts a displayed fare on this origin",
        )

    def test_a_changed_journey_names_the_station_where_it_changes(self) -> None:
        # Q2 (ADR-0045): a split ticket is the reply the launch post expects,
        # and the page answers it where the fare's condition already sits --
        # naming the interchange, claiming no price.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        changed = [row for row in payload["destinations"] if row["changes"] == 1]
        self.assertTrue(changed, "no destination on this page changes")
        self.assertEqual(changed[0]["changeStations"], [{"crs": "NOT", "name": "NOTTINGHAM"}])
        direct = next(row for row in payload["destinations"] if row["changes"] == 0)
        self.assertEqual(direct["changeStations"], [], "a direct journey has no change to split at")

    def test_one_destination_is_priced_and_never_served(self) -> None:
        # The shape the page's "no service" row exists to report.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "LCN")
        states = {row["journeyState"] for row in payload["anytimeDestinations"]}
        self.assertIn("found", states)
        self.assertTrue(
            any(state != "found" for state in states),
            f"every destination has a journey: {states}",
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

        source = (Path(__file__).resolve().parents[1] / "page_templates.py").read_text(encoding="utf-8")
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


class EncodedPayloadTest(unittest.TestCase):
    """The wire form of the payload: field names once per page, not once per row."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        fares = FaresDb().load_feed(
            build_synthetic_feed(
                Path(cls._tmp.name) / "fares",
                include_unserved_station=True,
                include_restrictions=True,
            )
        )
        timetable = TimetableDb().load_feed(build_synthetic_timetable(Path(cls._tmp.name) / "timetable"))
        cls.page = render_page(build_payload(fares, timetable, "GRN"), budget_pounds=20)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    payload = {
        "origin": {"crs": "GRN", "name": "GRANTHAM"},
        "note": "a note",
        "attribution": [{"url": "https://example.invalid", "label": "Example"}],
        "destinations": [
            {"crs": "NOT", "name": "NOTTINGHAM", "adultPence": 1200, "partyPence": 2400,
             "link": {"url": "https://example.invalid/search", "rel": "noopener"}},
            {"crs": "SLP", "name": "SLEAFORD", "adultPence": 800, "partyPence": 1600,
             "link": {"url": "https://example.invalid/search", "rel": "noopener"}},
        ],
        "singleDestinations": [{"crs": "NOT", "name": "NOTTINGHAM", "adultPence": 700}],
        "stations": [{"name": "LINCOLN", "crs": "LCN", "href": "/from/lincoln/"}],
    }

    def test_every_row_reads_back_as_it_was_written(self) -> None:
        decoded = hydrate_rows(encode_payload(self.payload))
        for key in ("destinations", "singleDestinations", "stations"):
            self.assertEqual(decoded[key], self.payload[key])

    def test_a_field_name_is_sent_once_for_the_whole_list(self) -> None:
        encoded = json.dumps(encode_payload(self.payload), separators=(",", ":"))
        self.assertEqual(encoded.count('"partyPence"'), 1)

    def test_the_lists_keep_their_own_columns(self) -> None:
        encoded = encode_payload(self.payload)
        self.assertEqual(encoded["stations"]["columns"], ["name", "crs", "href"])
        self.assertNotIn("partyPence", encoded["stations"]["columns"])

    def test_a_list_that_is_not_a_row_list_is_left_alone(self) -> None:
        encoded = encode_payload(self.payload)
        self.assertEqual(encoded["attribution"], self.payload["attribution"])

    def test_a_payload_with_no_rows_is_returned_untouched(self) -> None:
        payload = {"origin": {"crs": "GRN"}, "destinations": []}
        self.assertIs(encode_payload(payload), payload)

    def test_the_payload_it_was_given_is_not_modified(self) -> None:
        before = json.loads(json.dumps(self.payload))
        encode_payload(self.payload)
        self.assertEqual(self.payload, before)


    def test_a_value_that_repeats_is_sent_once_for_the_whole_page(self) -> None:
        encoded = encode_payload(self.payload)
        self.assertEqual(len(encoded["pool"]), 1)
        self.assertEqual(encoded["pool"][0]["url"], "https://example.invalid/search")
        link = encoded["destinations"]["columns"].index("link")
        self.assertEqual(encoded["destinations"]["rows"][0][link], -1)

    def test_a_value_used_once_is_left_where_it_is(self) -> None:
        encoded = json.dumps(encode_payload(self.payload), separators=(",", ":"))
        self.assertEqual(encoded.count("NOTTINGHAM"), 2)
        self.assertEqual(encoded.count("https://example.invalid/search"), 1)

    def test_a_payload_with_nothing_repeated_carries_no_pool(self) -> None:
        payload = {"destinations": [{"crs": "NOT", "adultPence": 1}, {"crs": "SLP", "adultPence": 2}]}
        self.assertNotIn("pool", encode_payload(payload))

    def test_a_null_cell_is_still_null(self) -> None:
        payload = {"destinations": [{"crs": "NOT", "minutes": None}, {"crs": "SLP", "minutes": None}]}
        encoded = encode_payload(payload)
        self.assertEqual(encoded["destinations"]["rows"], [["NOT", None], ["SLP", None]])

    def test_the_pool_reads_back_by_hand_as_well_as_through_the_page(self) -> None:
        encoded = encode_payload(self.payload)
        self.assertEqual(hydrate_rows(encoded)["destinations"], self.payload["destinations"])

    def test_a_rendered_page_carries_the_tables_and_the_hydrator(self) -> None:
        self.assertIn('"columns":', embedded_text(self.page))
        self.assertNotIn('"partyPence":', embedded_text(self.page))
        self.assertIn("function hydrate(table)", self.page)

    def test_a_rendered_page_reads_back_as_the_payload_it_was_built_from(self) -> None:
        self.assertTrue(embedded_payload(self.page)["destinations"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
