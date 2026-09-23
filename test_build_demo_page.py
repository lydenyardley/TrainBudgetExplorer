"""Tests for the demo page generator."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from datetime import date
import contextlib
import io
from pathlib import Path

import build_demo_page
from build_demo_page import DEFAULT_PRICE_SOURCE, NOTICES, notices_or_attribution
import argparse
from atoc_fares import LOCATION, FLOW_F, FLOW_T, FaresDb
from atoc_timetable import TimetableDb
from build_demo_page import (
    build_payload,
    build_station_index,
    render_chooser,
    render_page,
    station_slug,
)
from make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_timetable
from retailer import DISCLOSURE


def embedded_payload(html: str) -> dict:
    match = re.search(r"const DATA = (\{.*?\});\n", html, re.DOTALL)
    if match is None:
        raise AssertionError("the page carries no embedded payload")
    return json.loads(match.group(1))


class DemoPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fares = FaresDb().load_feed(
            build_synthetic_feed(Path(cls._tmp.name) / "fares", include_unserved_station=True)
        )
        cls.timetable = TimetableDb().load_feed(build_synthetic_timetable(Path(cls._tmp.name) / "timetable"))
        cls.payload = build_payload(cls.fares, cls.timetable, "GRN")
        cls.html = render_page(cls.payload, budget_pounds=20)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_page_carries_every_priced_destination_not_just_the_cheap_ones(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(sorted(rows), ["KGX", "LCN", "NOT", "PBO", "SLP"])

    def test_every_destination_carries_both_prices_and_a_journey(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["NOT"]["adultPence"], 1160)
        self.assertEqual(rows["NOT"]["railcardPence"], 775)
        self.assertEqual(rows["NOT"]["partyPence"], 1550)
        self.assertEqual(rows["NOT"]["minutes"], 45)
        self.assertEqual(rows["NOT"]["changes"], 0)

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

    def test_the_railcard_estimate_carries_its_checked_basis(self) -> None:
        # The third-off assumption is stated with what the real database said
        # about it, so "estimate" is not a bare warning but a bounded one.
        self.assertIn("5-15p above the real discounted price", self.payload["railcardBasis"])
        self.assertIn('id="railcardBasis" hidden', self.html)
        self.assertIn("DATA.railcardBasis", self.html)

    def test_a_real_data_build_names_its_source_and_drops_the_estimate_caveat(self) -> None:
        payload = build_payload(
            self.fares,
            self.timetable,
            "GRN",
            price_source="the RSP fares feed, downloaded 22 September 2026",
            railcard_basis=None,
        )
        self.assertIn("RSP fares feed", payload["priceSource"])
        self.assertIsNone(payload["railcardBasis"])

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
        self.assertIn('<p id="linkNote" hidden></p>', self.html)
        self.assertIn("DATA.linkNote", self.html)

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
        self.assertIn('if (together) lines.push("Two Together Railcard: tick the box', self.html)

    def test_the_copied_date_is_not_parsed_through_the_date_object(self) -> None:
        # new Date("2026-10-05") is UTC midnight and prints as the 4th for a
        # reader behind UTC. A copied date off by one is worse than no date.
        self.assertIn("function humanDate(iso)", self.html)
        self.assertNotIn("new Date(", self.html)

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
        self.assertIn('id="q"', self.html)
        self.assertIn('value="party"', self.html)

    # -- the origin picker (ADR-0019) -------------------------------------

    def test_the_payload_carries_a_station_list_for_the_picker(self) -> None:
        codes = [s["crs"] for s in self.payload["stations"]]
        self.assertNotIn("GRN", codes)  # the page's own origin is not offered
        self.assertIn("KGX", codes)
        for station in self.payload["stations"]:
            self.assertEqual(sorted(station), ["crs", "href", "name"])
            self.assertTrue(station["href"].startswith("/from/"))

    # -- the layout: budget leads, the rest refines ------------------------

    def test_the_controls_grid_gives_the_budget_the_wider_column(self) -> None:
        self.assertIn("grid-template-columns: minmax(16rem, 1.5fr) minmax(12rem, 1fr)", self.html)
        # The party switch and the town filter share one secondary column.
        self.assertIn('<div class="secondary">', self.html)
        secondary = self.html.split('<div class="secondary">')[1].split("</div>\n</div>")[0]
        self.assertIn('name="unit"', secondary)
        self.assertIn('id="q"', secondary)

    def test_the_budget_is_the_biggest_type_on_the_page(self) -> None:
        budget_size = re.search(r"\.budget \{ font-size: ([\d.]+)rem", self.html).group(1)
        h1_size = re.search(r"h1 \{ font-size: ([\d.]+)rem", self.html).group(1)
        self.assertGreater(float(budget_size), float(h1_size))

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
        payload = dict(self.payload, destinations=[])
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
        # message; on an unpriced page it must not run at all.
        self.assertIn("if (!DATA.destinations.length) return;", script)

    def test_an_unpriced_origin_with_no_stations_at_all_says_that(self) -> None:
        payload = dict(self.payload, destinations=[], stations=[])
        html = render_page(payload, budget_pounds=20)
        script = html.split("<script>")[1].split("</script>")[0]
        self.assertIn("Nothing was priced from any station", script)
        # No chooser exists, so no way-forward link is offered either.
        self.assertIn('if (DATA.stations && DATA.stations.length)', script)

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
        self.assertNotIn("<select", self.html.split("<script")[0])

    def test_the_picker_closes_on_escape_and_returns_focus(self) -> None:
        self.assertIn('event.key === "Escape"', self.html)
        self.assertIn("changeOrigin.focus()", self.html)

    def test_table_headers_name_their_columns_and_scope(self) -> None:
        # "Ticket" and "Tickets" as adjacent headers read as one column twice;
        # the first holds the fare code, so it says so.
        self.assertIn('<th scope="col">Fare code</th>', self.html)
        self.assertNotIn("<th>Ticket</th><th>Tickets</th>", self.html)
        self.assertEqual(self.html.count('<th scope="col"'), 6)

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
        reflow = self.html[self.html.index("@media (max-width: 44rem)"):].split("</style>")[0]
        self.assertIn("flex-wrap", reflow)
        self.assertNotIn("display: none", reflow.split("thead")[0])
        self.assertIn("thead { display: none; }", reflow)
        table_markup = self.html.split("<table>")[1].split("</table>")[0]
        self.assertNotIn("<div", table_markup)

    def test_the_slider_ceiling_covers_the_dearest_destination(self) -> None:
        ceiling = int(re.search(r'id="budget"[^>]*max="(\d+)"', self.html).group(1))
        dearest = max(row["partyPence"] for row in self.payload["destinations"])
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
        self.feed = build_synthetic_feed(root / "fares", include_unserved_station=True)
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
        self.assertEqual(single, pooled)

    def test_the_build_says_how_to_open_what_it_wrote(self) -> None:
        # The pages are build output and their links are root-absolute, so
        # double-clicking the file does not work and a local server does.
        said = self.build()
        self.assertIn("http.server", said)
        self.assertIn("http://localhost", said)



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
        cls.feed = build_synthetic_feed(root / "fares", include_unserved_station=True)
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
                        "restriction_code": "00",
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
                        "restriction_code": "00",
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
        index = build_station_index(
            {
                crs: len(fares.destinations_within(crs, 1_000_000, adults=1))
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
        feed = build_synthetic_feed(root / "fares")
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
        feed = build_synthetic_feed(root / "fares")
        (feed / "metadata.json").write_text(
            json.dumps({"source": "RSP fares feed", "downloaded": "3 October 2026"}),
            encoding="utf-8",
        )
        out = root / "site" / "index.html"
        out.parent.mkdir(parents=True)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(["--feed", str(feed), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertIn("RSP fares feed", out.read_text(encoding="utf-8"))

    def test_price_source_override_settles_an_unfinished_note(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        feed = build_synthetic_feed(root / "fares")
        (feed / "metadata.json").write_text(
            json.dumps({"downloaded": "3 October 2026"}), encoding="utf-8"
        )
        out = root / "site" / "index.html"
        out.parent.mkdir(parents=True)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = build_demo_page.main(
                ["--feed", str(feed), "--out", str(out), "--price-source", "the 2026 RSP download"]
            )
        self.assertEqual(code, 0)
        self.assertIn("the 2026 RSP download", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
