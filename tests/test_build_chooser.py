"""The entry route: the directory, its note, and the links every route carries.

F6 of the 8 October 2026 agent-efficiency audit moved the page's content
tests out of the class they all shared, by subject, over the fixture in
``tests/page_harness.PageTestCase``.
"""

from __future__ import annotations

import json
import re
import build_demo_page
from build_demo_page import build_payload, build_station_index, render_chooser, render_page, render_privacy
from tests.page_harness import embedded_payload, page_script, setUpModule, tearDownModule, PageTestCase


class ChooserTest(PageTestCase):
    def test_the_chooser_says_what_its_order_is_and_is_not(self) -> None:
        # S10: a cold-start order that does not name its measure reads as a
        # recommendation, and priced-destination count is not popularity.
        # D9 of the 17 October 2026 critique: "most first" is the list's own
        # subtitle now, and the denial of busyness and nearness is gone --
        # nothing on the page had asked about either.
        index = build_demo_page.build_station_index({"GRN": 5, "NOT": 2}, self.fares.locations_by_crs)
        chooser = build_demo_page.render_chooser(index, budget_pounds=20)
        self.assertIn('<p class="tag" id="orderingNote">Most first.</p>', chooser)
        self.assertNotIn("not by how busy it is", chooser)
        # And the measure the numbers count is the list's heading, said once.
        self.assertIn('<h2 id="picksHeading">Destinations this feed prices</h2>', chooser)

    def test_the_entry_route_carries_the_same_provenance_the_station_pages_do(self) -> None:
        # The root is the page every community link points at, and it used to
        # say what the ordering was while saying nothing about what the site
        # was, whose feed its prices came from, or how old that feed was
        # (four-dimension audit R3, route audit item 6). The station page has
        # carried all three since the provenance line was written.
        index = build_demo_page.build_station_index({"GRN": 5, "NOT": 2}, self.fares.locations_by_crs)
        chooser = build_demo_page.render_chooser(
            index,
            budget_pounds=20,
            price_source="the 24 September 2026 DTD download",
            feed_date="2026-09-24",
        )
        self.assertIn("Prices from the 24 September 2026 DTD download", chooser)
        self.assertIn("downloaded 24 September 2026", chooser)
        self.assertNotIn("__PROVENANCE__", chooser)
        # A synthetic build names the synthetic feed, and does not invent a
        # date it does not have.
        synthetic = build_demo_page.render_chooser(index, budget_pounds=20)
        self.assertIn("Prices from the synthetic demo feed.", synthetic)
        self.assertNotIn("downloaded", synthetic)

    def test_both_station_lists_accept_a_code_fragment(self) -> None:
        # S11: a code fragment finds its station, and the same matcher serves
        # the chooser and the picker so the two cannot answer differently.
        for script in (page_script(self.html), build_demo_page.CHOOSER_SCRIPT):
            for fragment in (
                "station.name.toLowerCase().includes(needle)",
                "station.crs.toLowerCase().startsWith(needle)",
            ):
                self.assertIn(fragment, script)
        # No alias table: an unreviewed "Grantham = Grantham Stn" is exactly
        # the plausible-looking invention this project refuses to publish.
        self.assertNotIn("aliases", page_script(self.html))

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

    def test_the_payload_carries_a_station_list_for_the_picker(self) -> None:
        codes = [s["crs"] for s in self.payload["stations"]]
        self.assertNotIn("GRN", codes)  # the page's own origin is not offered
        self.assertIn("KGX", codes)
        for station in self.payload["stations"]:
            self.assertEqual(sorted(station), ["crs", "href", "name"])
            self.assertTrue(station["href"].startswith("/from/"))

    # -- the layout: budget leads, the rest refines ------------------------

    def test_the_no_match_wording_names_what_was_tried(self) -> None:
        self.assertIn("We don’t have a page for", page_script(self.html))
        self.assertIn("three-letter code", page_script(self.html))

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
        # The budget travels with every station link and comes back out of one:
        # the browser suite reads the query off each rendered link and opens a
        # page by it.
        self.assertIn("min-height: 44px", chooser)
        # The station slot is the one thing this route has that a station
        # page does not: a field holding the word station, waiting to be
        # typed in, so the page reads as a question with its answer missing.
        self.assertIn('id="originSearch"', chooser)
        # C14/D11 of the 17 October 2026 critique: the placeholder is the
        # prompt, so the sentence reads "from your station" and the instruction
        # paragraph that used to explain it is gone.
        self.assertIn('placeholder="your station"', chooser)
        self.assertNotIn("Type the station you are starting from", chooser)
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
        self.assertIn("This site covers CARK &amp; CARTMEL only", chooser)
        # Nothing is ordered over one row, so the page makes no ranking claim.
        self.assertNotIn('id="orderingNote"', chooser)
        self.assertNotIn("Every station this page prices journeys from", chooser)
        # The tab title names the station, and the script keeps it named as the
        # budget changes rather than falling back to asking where to leave from.
        self.assertIn("&middot; CARK &amp; CARTMEL</title>", chooser)
        self.assertIn('TITLE_SUFFIX', chooser)
        self.assertIn('"name":"CARK & CARTMEL"', chooser)
        # The one row is still the release: the page to open, with its count.
        self.assertIn("/from/cark/", chooser)
        self.assertIn('"destinations":5', chooser.replace(" ", ""))
        # A chooser's field is optional now, so the script cannot assume it. It
        # is wired through the shared field block, which owns the typing and
        # hands the route back the text, the field's value and the completion.
        # The browser suite drives that completion over the real chooser.
        self.assertIn("typedQuery", build_demo_page.CHOOSER_SCRIPT)
        # The list is the whole page's answer, so it is still built and
        # counted: a real list element the script fills, and the status region
        # beside it that says how many stations it is showing.
        self.assertIn('<ul id="picks" aria-labelledby="picksHeading"></ul>', chooser)
        self.assertIn('<span id="pickStatus" class="sr-only" role="status"></span>', chooser)

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
        # the whole directory rather than its first forty names. The browser
        # suite drives the truncated list over the real chooser.
        self.assertIn("CHOOSER_LIMIT", build_demo_page.CHOOSER_SCRIPT)
        # The sentence that names the cap is read off the rendered chooser by
        # the browser suite, which searches for more matches than the cap and
        # reads what the page says about how many it is hiding.
        self.assertIn("Type to narrow the list.", build_demo_page.CHOOSER_SCRIPT)

    def test_the_chooser_counts_destinations_in_the_singular_when_there_is_one(self) -> None:
        # The chooser is read as a fact about the feed, and "1 destinations" is
        # the kind of slip that costs the page its credibility. The count is
        # rendered in the browser, so this asserts the emitted script.
        chooser = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}],
            budget_pounds=20,
        )
        # Both forms are spelled out, so the singular is a word the page owns
        # rather than a plural with an "s" taken off it. The count itself is
        # read off the rendered chooser by the browser suite.
        self.assertIn('" destination"', build_demo_page.CHOOSER_SCRIPT)
        self.assertIn('" destinations"', build_demo_page.CHOOSER_SCRIPT)

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
        # C15 of the 17 October 2026 critique: the instruction folded into the
        # field's placeholder, so the list starts at its own heading.
        self.assertIn('placeholder="your station"', html)
        self.assertIn('<h2 id="picksHeading">', html)
        # No fares payload on the chooser: the reader has not chosen a station
        # yet, so the page carries the index and nothing the station pages read.
        with self.assertRaises(AssertionError):
            embedded_payload(html)
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
        # D6 of the 17 October 2026 critique: on a synthetic page the banner at
        # the top is the note's only copy, so the footer carries none; a real
        # page with a note of its own still gets its paragraph.
        self.assertNotIn(
            "<p>the RSP fares feed</p>",
            render_page(dict(self.payload, note="the RSP fares feed"), budget_pounds=20),
        )
        self.assertIn(
            "<p>the RSP fares feed</p>",
            render_page(
                dict(self.payload, note="the RSP fares feed", synthetic=False),
                budget_pounds=20,
            ),
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
            self.assertIn('Train fares <span class="heading-slot">up to ', chooser)
            self.assertIn('<span class="heading-lead">from</span>', chooser)
            self.assertNotIn("originClause\"> from <", chooser)

    def test_the_chooser_says_what_to_do_with_the_field_it_offers(self) -> None:
        # S2 of the 19 October 2026 critique: the field in the heading is the
        # page's whole job and it looked like the end of the title -- no verb,
        # no label, nothing that said typing was possible. The sentence is
        # under the heading and before the list, and it is only there when the
        # page has a field to point at: a one-station release names its station
        # instead and says so in its own paragraph.
        many = render_chooser(
            [
                {"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1},
                {"crs": "GRN", "name": "GRANTHAM", "slug": "grantham", "destinations": 3},
            ],
            budget_pounds=20,
        )
        self.assertIn('<p class="sub" id="chooserHint">Type your station’s name', many)
        # Before the list, not after it and not in a tooltip.
        self.assertLess(many.index('id="chooserHint"'), many.index('id="picks"'))
        one = render_chooser(
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}],
            budget_pounds=20,
        )
        self.assertNotIn('id="chooserHint"', one)

    def test_the_chooser_names_the_three_columns_its_rows_carry(self) -> None:
        # S11 of the 19 October 2026 critique: a row read "GRANTHAM GRN 22" and
        # only the row's accessible name said what the number counted. One
        # column line above the grid, written once, is what the count needed;
        # the row still does not repeat the phrase (C12 of the 17 October 2026
        # critique), and the line is for the eye because each row's own name
        # already carries the count.
        for index in (
            [{"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1}],
            [
                {"crs": "NOT", "name": "NOTTINGHAM", "slug": "nottingham", "destinations": 1},
                {"crs": "GRN", "name": "GRANTHAM", "slug": "grantham", "destinations": 3},
            ],
        ):
            chooser = render_chooser(index, budget_pounds=20)
            self.assertIn('id="picksColumns"', chooser)
            self.assertIn("Station &middot; Code &middot; Destinations", chooser)
            self.assertLess(chooser.index('id="picksColumns"'), chooser.index('<ul id="picks"'))
            self.assertNotIn(" this feed prices</span>", chooser)
        # A page that priced nothing has no list for a column line to label, and
        # the line would be the only thing in that section.
        self.assertNotIn("id=\"picksColumns\"", render_chooser([], budget_pounds=20))

    def test_a_zero_station_chooser_stands_the_search_down_and_says_so(self) -> None:
        from page_templates import CHOOSER_SCRIPT

        html = render_chooser([], budget_pounds=20)
        self.assertIn("There is nothing here yet", CHOOSER_SCRIPT)
        # The station list the page is built from is empty, so the field has
        # nothing to search and the page says so rather than offering a search
        # that cannot answer.
        self.assertEqual(json.loads(re.search(r"window\.TBE_CHOOSER_STATIONS = (\[.*?\]);", html, re.S).group(1)), [])
        # The no-match wording quotes typed input; it must never address an
        # empty field the reader has not touched, so the paragraph it would be
        # written into ships hidden.
        self.assertIn('<p id="nomatch" hidden></p>', html)
