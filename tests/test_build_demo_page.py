"""What the page says: its shape, its controls, its rows and its accessibility.

F6 of the 8 October 2026 agent-efficiency audit moved the page's content
tests out of the class they all shared, by subject, over the fixture in
``tests/page_harness.PageTestCase``.
"""

from __future__ import annotations

import json
import gc
import re
import shutil
import tempfile
import unittest
import weakref
from unittest import mock
from datetime import date
import contextlib
import io
from pathlib import Path
import argparse
from trainbudget.build import build_demo_page
from trainbudget.build import build_state
from trainbudget.fares.atoc_fares import FLOW_F, FLOW_T, TICKET_TYPE, FaresDb
from trainbudget.timetable.atoc_timetable import TimetableDb
from trainbudget.build.build_demo_page import build_payload, explain_unpriced, render_page
from trainbudget.build.build_release import SERVICE_CLAIM, SERVICE_CLAIM_WITHOUT_TIMES
from trainbudget.feeds.make_synthetic_feed import _line, build_synthetic_feed, build_synthetic_timetable
from tests.page_harness import browser_suite_text, embedded_payload, embedded_text, js_function, page_markup, page_script, serialised_callback_lines, setUpModule, station_page, tearDownModule, PageTestCase


class DemoPageTest(PageTestCase):
    def test_the_station_page_says_which_control_changes_station(self) -> None:
        # S12: the navigation-versus-filter distinction, said once, where it is
        # true.
        self.assertIn('id="firstUse"', self.html)
        self.assertIn("<b>station name</b>", self.html)
        # D1 of the 17 October 2026 critique: the paragraph that used to open
        # the page was a third copy of the heading, the count line and the
        # column headings. The one sentence a first-time reader cannot guess
        # is the paragraph now, under the word it describes.
        self.assertNotIn('id="pageIntro"', self.html)
        self.assertIn('<p class="sub" id="firstUse">', self.html)

    def test_the_page_states_where_a_split_ticket_would_split(self) -> None:
        # The other half of Q2: the sentence that states the possibility, in
        # the panel where the fare's condition already sits, and no price for
        # either half. The browser suite drives the live row.
        # The station itself is named in the Changes column now, so the
        # panel says only what is still worth saying and is nowhere else.
        self.assertIn("can sometimes cost less than this through fare", page_script(self.html))
        self.assertIn("This page prices the through fare only.", page_script(self.html))

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

    def test_a_row_states_its_condition_and_folds_the_feed_record_away(self) -> None:
        # S19: the condition a reader can act on sits beside the price; the
        # ticket, restriction and route codes are one disclosure away. The
        # browser suite drives the folded panel and its wording.
        # An unrestricted fare used to open with a second paragraph saying
        # there was nothing to read, which is the same information as
        # silence said in a line.
        self.assertIn("with no conditions in the feed.", page_script(self.html))
        self.assertNotIn("No travel conditions on this fare in the feed.", page_script(self.html))
        row = next(row for row in self.payload["destinations"] if row["crs"] == "NOT")
        self.assertEqual(row["routeCode"], "00000")
        self.assertEqual(row["restrictionCode"], "1A")

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
        suite = browser_suite_text()
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
        self.assertNotIn('id="shortlistPick"', page_script(self.html))
        self.assertNotIn("shortlist-toggle", page_script(self.html))
        self.assertIn("hold-box", page_script(self.html))
        # The column the boxes live in is a column of the header too, or the
        # table has a cell with no heading above it. It says the word the dock,
        # its count and its clear button say, and the stacked layout labels the
        # same cell with the same word (audit item 13, 9 October 2026).
        # DS7 of the 19 October 2026 distill pass: the column headings wear the
        # one uppercase label rule, so the hold column carries both classes.
        self.assertIn('<th scope="col" class="eyebrow hold">Shortlist</th>', self.html)
        from trainbudget.build.page_templates import STATION_STYLESHEET

        self.assertIn(
            "th.hold, td.hold { width: 1%; white-space: nowrap; padding-left: .2rem; text-align: center; }",
            STATION_STYLESHEET,
        )
        # ... and the places it holds, and every control for the list, are in
        # the one place the list is drawn: the dock at the foot of the screen.
        self.assertIn('id="shortlistCopy"', self.html)
        self.assertIn('id="shortlistShareBox"', self.html)
        self.assertIn('id="shortlistDockClear"', self.html)
        dock = self.html.split('<aside class="shortlist-dock"', 1)[1].split("</aside>", 1)[0]
        for control in ("shortlistCopy", "shortlistShareBox", "shortlistDockClear", "shortlistBox"):
            self.assertIn(f'id="{control}"', dock)
        # It is part of the address, one readable key per place, and the
        # comparison is of the price on screen: the browser suite drives the
        # dock, the copied text, the shared link and the refresh that brings
        # the list back.
        # The limit is said, not silently applied.
        # Said on the page as well as to the status region: a control that
        # stops responding with no explanation is the one thing a reader
        # cannot act on, and the strip is where they are already looking. The
        # figure is the page's own cap, written into the sentence it shows.
        self.assertIn('"The shortlist holds "', page_script(self.html))
        self.assertIn('" destinations. Remove one to add another."', page_script(self.html))
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

    def test_a_prices_only_table_stands_its_empty_columns_down(self) -> None:
        # Two columns of dashes on every row is noise; when no timetable is
        # loaded the Time and Changes columns do not exist at all. The page reads
        # that off the payload, so the payload is what is asserted here: this
        # build loaded no timetable, and its page is still shipped with the two
        # headings a build with times would fill.
        payload = build_payload(self.fares, None, "GRN")
        html = render_page(payload, budget_pounds=20)
        script = page_script(html)
        self.assertFalse(payload["hasJourneys"])
        # By heading name, per table. A bare nth-child across the whole page
        # took the dock's own columns instead of the results table's, because
        # the two tables number their cells differently. Naming the columns
        # means a table that gains a column first does not move the removal
        # onto a neighbour, and the dock's remove button keeps its heading.
        # What is asserted here is the names themselves, taken from the
        # results table's own headings -- the dock is a second table further
        # down the document, with headings of its own -- and the browser suite
        # reads the same headings back off the rendered page.
        thead = re.findall(r"<thead>(.*?)</thead>", page_markup(html), re.S)[0]
        headings = re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', thead)
        self.assertIn("Time", headings)
        self.assertIn("Changes", headings)
        self.assertNotIn("thead th:nth-child", script)
        # The detail rows must span whatever the table actually has, which is
        # why a column count written into the span would go stale the moment a
        # build stands a column down. What the span actually is can only be
        # read off a rendered row, so the browser suite reads the opened
        # panel's colSpan against the table's own heading count.
        # And the footer still says what the page is missing.
        self.assertIn("no timetable was supplied", page_script(html))

    def test_a_page_with_times_keeps_all_six_columns(self) -> None:
        # The columns are shipped as headings, so the page counts the table it
        # is in rather than naming a number, and what is asserted here is what
        # the markup gives it to count: every column, and two of them filled.
        self.assertTrue(self.payload["hasJourneys"])
        thead = re.findall(r"<thead>(.*?)</thead>", page_markup(self.html), re.S)[0]
        headings = re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', thead)
        for column in ("Station", "Price", "Time", "Changes", "Fare type", "Tickets"):
            self.assertIn(column, headings)
        # The times a page prints are its own chosen day's answer rather than
        # the build's, so the payload carries every day's and each row names
        # the one to read. This build walked no week, so there is one day and
        # every timed row carries the minutes and change count it prints.
        self.assertEqual(self.payload["serviceDays"], [])
        timed = [row for row in self.payload["destinations"] if row["journeyState"] == "found"]
        self.assertTrue(timed, "this build times at least one destination")
        for row in timed:
            self.assertIsInstance(row["minutes"], int)
            self.assertIsInstance(row["changes"], int)

    # -- feed metadata: provenance recorded once, read by every build ---------

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

    def test_the_opening_sentence_branches_on_whether_a_timetable_was_loaded(
        self,
    ) -> None:
        # C04: the shipped sentence promised a journey time and a change count
        # on a build that removes the columns that carry them. The sentence is
        # written from the payload's own fact now, and the browser suite drives
        # the branch between the two by opening a prices-only page beside a page
        # built with a timetable.
        self.assertTrue(self.payload["hasJourneys"])
        self.assertFalse(build_payload(self.fares, None, "GRN")["hasJourneys"])
        self.assertIn("no times or changes are shown", page_script(self.html))
        # D1 of the 17 October 2026 critique: the sentence that had to branch on
        # this fact is gone, because it was the page's claim stated a third
        # time. What is left above the table is the build's own sentence about
        # its timetable, and the page cannot promise a time it does not show.
        self.assertNotIn("fastest time", self.html)
        self.assertNotIn("journey time", self.html)
        self.assertNotIn('id="pageIntro"', self.html)

    def test_the_sentence_about_times_names_only_what_this_build_has(self) -> None:
        # C5 of the 17 October 2026 critique: the paragraph above the method
        # disclosure shipped "Unrestricted fares are valid on the services
        # listed" on a build that loads no timetable, so a reader of the
        # published shape was told about services that are not there. The
        # sentence is the payload's own now, chosen once from hasJourneys, and
        # the renderer writes that same string into the page.
        prices_only = build_payload(self.fares, None, "GRN")
        self.assertFalse(prices_only["hasJourneys"])
        self.assertEqual(prices_only["pricingNote"], SERVICE_CLAIM_WITHOUT_TIMES)
        self.assertEqual(self.payload["pricingNote"], SERVICE_CLAIM)
        self.assertIn("services listed", self.html)
        without_times = render_page(prices_only, budget_pounds=20)
        self.assertIn(SERVICE_CLAIM_WITHOUT_TIMES, without_times)
        self.assertNotIn("services listed", without_times)
        self.assertNotIn("options in the timetable", without_times)
        # DS5 of the 19 October 2026 distill pass: the limitation is one
        # paragraph, so the visible page says it once. The payload repeats the
        # sentence in its own pricing note, which is not visible copy and is
        # why the count stops at the payload.
        visible = self.html.split("window.TBE_DATA")[0]
        self.assertEqual(visible.count("qualifying train"), 1)
        self.assertEqual(visible.count("Unrestricted fares are valid"), 1)

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
        self.assertIn("DATA.dateNote", page_script(self.html))
        self.assertNotIn(
            'document.getElementById("railcardNote").after(note)', page_script(self.html)
        )

    # -- the copy affordance that gives a row back its memory ---------------

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
        # Items 9 and 13 of the 14 October 2026 clarity audit: the heading holds
        # the budget field and the station control, so its own accessible name is
        # the whole sentence rather than the controls' text run together. The
        # document ships it, so a page whose script never runs still names the
        # heading. That the script rewrites it from the tab title on every render,
        # so the two cannot disagree, is the browser suite's to prove.
        self.assertIn('aria-label="Train fares up to &pound;20 from GRANTHAM"', heading)
        # The other places that name the cap. "Within" is not "under", but it
        # reads the same way beside a fare that lands exactly on the ceiling,
        # and a summary saying "3 destinations within £20" under a heading that
        # says "up to £20" is the same defect in different words.
        #
        # Two phrases, and each is now a different sentence: the count line's
        # "N destinations for up to £X" and the empty list's "No destinations
        # for up to £X". The empty block below the table no longer repeats the
        # second one (DS1 of the 19 October 2026 distill pass), which is a fact
        # about what a reader sees rather than about how many times the words
        # appear in the script; the browser suite reads the rendered page.
        self.assertEqual(2, page_script(self.html).count("for up to "),
                         "the cap is named the old way somewhere")
        self.assertNotIn('"No destinations within "', page_script(self.html))

    def test_every_price_renders_with_two_decimal_places(self) -> None:
        # £9 next to £8.70 is harder to scan down a column than £9.00 is. The
        # browser suite reads the rendered figures -- the budget's own stop and
        # each row's price -- and compares them against a two-decimal figure it
        # builds from the payload, so what is left here is the half a reader
        # cannot see: nothing on the page strips the trailing ".00" back off.
        self.assertNotIn("replace(/\\.00$/", page_script(self.html))

    # -- the origin picker (ADR-0019) -------------------------------------

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
        from trainbudget.build.page_templates import (
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
        # The NRE credit is dark in both palettes on purpose -- the mark is
        # painted white -- so its two colours are fixed rather than a
        # light-dark pair, and the mark looks the same either way.
        self.assertIn("--nre-plate: #141b3d; --nre-ink: #ffffff;", SHARED_CSS)
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
                self.assertIn("toggle", template)
                # The switch ships carrying its state, so a reader meets a
                # control that already says which palette is on. What it
                # remembers between visits, and which palette a reader with no
                # stored choice gets, are the browser suite's: it clears the
                # store, reads the control's state against the palette the page
                # paints, presses it, and reloads.
                self.assertIn('aria-checked="true"', template)
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

    def test_the_footer_flows_into_columns_and_the_method_fold_starts_its_own(self) -> None:
        # C4 held the footer to a 75ch measure, and it obeyed by leaving half
        # of a wide page empty under a table that used all of it. The content
        # flows into 75ch columns now, so the page's width is used without any
        # line growing past the measure the paragraphs above it keep.
        from trainbudget.build.page_templates import SHARED_CSS, STATION_STYLESHEET

        # `columns` is `column-width`: the measure a column wants, so the count
        # follows the page rather than a breakpoint someone has to maintain.
        self.assertIn("columns: 50ch; column-gap: 2rem; }", SHARED_CSS)
        # column-width is a width a column wants, not one it is held to: with
        # room for one column the box stretches to the page, which is the
        # 178-character line C4 found. Each block keeps the measure itself.
        self.assertIn("footer > * { max-width: 50ch; }", SHARED_CSS)
        self.assertNotIn("font-size: .875rem; max-width: 75ch", SHARED_CSS)
        # The provenance fold is reference material rather than a paragraph in
        # that flow: it spans the columns and begins a block of its own, and
        # open it splits into the same measure, so the feed, date and
        # limitation lines are read side by side.
        self.assertIn(".method[open] { columns: 50ch; column-gap: 2rem; }", STATION_STYLESHEET)
        self.assertIn("footer > .method { column-span: all; max-width: none; }", STATION_STYLESHEET)
        self.assertIn("footer > .method > * { max-width: 50ch; }", STATION_STYLESHEET)

    def test_accessibility_is_a_route_matrix_and_not_one_happy_path(self) -> None:
        # S41: the AA commitment was evidenced from one station page. The
        # browser suite now runs a matrix on every route it is pointed at --
        # chooser, station page, privacy page -- in both colour schemes, at
        # desktop, phone and 200% zoom, and this asserts the matrix is wired
        # into that path rather than left in a function nobody calls.
        suite = browser_suite_text()
        for wanted in (
            "async function checkAccessibilityMatrix(",
            "await checkAccessibilityMatrix(page, url, check, kind);",
            # Both schemes, and the scheme has to land or the dark pass is the
            # light pass wearing another name.
            'for (const scheme of ["light", "dark"])',
            "page.emulateMedia({ colorScheme: scheme })",
            # A 304px viewport is what 200% zoom leaves of a 640px screen once
            # a desktop scrollbar has its 15 pixels (A3 of the 20 October 2026
            # poteto audit: 320 was a width no zoomed reader has).
            "width: 304",
            # Computed names, contrast off the rendered pixels, measured targets
            # and a focus indicator: the four things a claim of AA rests on.
            ".ariaSnapshot()",
            "every kind of text meets AA contrast",
            "every pointer target is at least 24px",
            "the controls promised at 44px are at least 44px",
            "the focused control shows where it is",
            "nothing scrolls sideways",
            "at 304px the text is still the base size",
            "zoomed.content === 304",
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
        from trainbudget.build.page_templates import STATION_STYLESHEET

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
        # is written from that same state, so the two cannot disagree. The
        # browser suite drives the fold and the sentence beside it.
        self.assertIn(".more-filters { display: block; }", self.stylesheet)
        self.assertIn(".more-filters-panel { display: none; }", self.stylesheet)
        self.assertIn('.more-filters[data-open="true"] .more-filters-panel { display: grid;', self.stylesheet)
        # The markup opens folded and carries the attribute the stylesheet keys
        # off, so the state the page writes is the state the page shipped with.
        # Pressing the control and reading it back is the browser suite's.
        self.assertIn('<div class="more-filters" id="moreFilters" data-open="false">', self.html)
        self.assertNotIn("display: contents", self.html)
        self.assertNotIn("matchMedia", page_script(self.html))
        self.assertNotIn("followViewport", page_script(self.html))
        # The state is written from the page's own controls, on every render
        # and on the path that stands the whole panel down.
        self.assertIn("filterStateText", page_script(self.html))
        self.assertGreaterEqual(page_script(self.html).count("renderFilterState"), 2)

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
        # C3 of the 17 October 2026 critique: the fold is a budget, so the
        # heading has a viewport-height term as well as a width one.
        self.assertIn("--h1: clamp(2rem, min(7vw, 9vh), 6rem)", self.stylesheet)
        self.assertIn(".sub { color: var(--muted); max-width: 75ch; }", self.stylesheet)
        self.assertNotIn("max-width: 32ch", self.html)
        self.assertNotIn("margin: -1rem 0 1.5rem", self.html)

    def test_result_changes_and_mobile_cells_are_accessible(self) -> None:
        self.assertIn('id="summary" role="status" aria-live="polite"', self.html)
        # A stacked cell shows the column it came from, and what it shows is the
        # heading above it, so the two are asserted here together rather than the
        # assignment that copies one to the other. Which cells carry which label
        # on a phone is read off the rendered rows by the browser suite.
        self.assertIn('<th scope="col" class="eyebrow">Fare type</th>', self.html)
        # C13/D8 of the 17 October 2026 critique: the phone row dropped the
        # label track, so the values are a two-line grid and the heading row is
        # the only place the column names are written.
        self.assertIn("#rows > tr[data-crs] { display: flex; flex-wrap: wrap;", self.stylesheet)
        self.assertNotIn("td[data-label]::before { content: attr(data-label)", self.stylesheet)
        # The column is the fare in three words. SDR, 2AS and BPS are a
        # seller's vocabulary and they were the column, on every row, in
        # front of the one number the reader came for; the code is in the
        # row's own record (ADR-0053). The label is what the phone reflow
        # reads out. The word itself is written by the page and driven by
        # the browser suite.
        self.assertIn("Advance", self.html)
        # And the panel those cells open carries the token the warn colour
        # hangs off, which is what the phone reflow and C14 both read. The
        # browser suite drives the panel, its class and its wording; what is
        # asserted here is the colour that token resolves to, because a token
        # nothing reads is a token that never mattered.
        self.assertIn(
            '.restriction[data-status="restricted"] { color: var(--warn); }',
            self.stylesheet,
        )
        self.assertIn("condition", self.html)
        # C07: the condition is still on the same row, one disclosure away, so
        # the pointer is kept rather than dropped -- and it now points at the
        # thing it names instead of at a column that no longer exists.
        # D3 of the 17 October 2026 critique: an undescribed condition is one
        # sentence, carrying the code, and the page prints it once. The
        # sentence is the payload's own, so it is asserted where it travels.
        self.assertIn("is not described in this feed, so check the seller's terms", self.html)
        self.assertNotIn("which this feed does not describe", self.html)

    def test_row_actions_carry_a_44px_touch_target(self) -> None:
        # The visible mark stays small; the hit area reaches 44px via ::after.
        self.assertIn('.toggle::after { content: ""; position: absolute; inset: -6px; }', self.stylesheet)
        # C7 of the 17 October 2026 critique: the ticket link is the primary
        # action, so it is a control with a 44px floor rather than a word with
        # an invisible ring around it. The browser suite measures the box.
        self.assertIn('.buy { display: inline-flex;', self.stylesheet)
        self.assertIn("min-height: 2.75rem", self.stylesheet.split(".buy {", 1)[1].split("}", 1)[0])

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
        # site's base path like every other internal link. The link the page
        # writes is driven by the browser suite.
        self.assertIn("Start from a station we do price", script)
        # The controls cannot help an origin with no prices, so they stand
        # down. What is asserted here is the payload the page reads to know
        # that, and that the blocks a budget would otherwise write into ship
        # closed: an unpriced page carries no row in any ticket mode, and its
        # budget message and results scaffold are hidden in the markup rather
        # than filled in by a render that has nothing to put there.
        on_the_page = embedded_payload(html)
        for key in ("destinations", "singleDestinations", "anytimeDestinations"):
            self.assertEqual(on_the_page[key], [], f"{key} priced something on an unpriced page")
        self.assertIn('<div id="empty" hidden></div>', html)
        self.assertIn('<p id="more" hidden></p>', html)

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
        # No chooser exists, so the way-forward link the page writes when one
        # does is not on this page at all: with no station to change to, the
        # heading offers no Change control, and that is a markup fact rather
        # than something a reader only discovers by pressing a dead button.
        self.assertNotIn('<button id="changeOrigin"', html)

    def test_the_empty_state_carries_the_payloads_note_after_the_intro(self) -> None:
        payload = dict(
            self.payload,
            destinations=[],
            singleDestinations=[],
            anytimeDestinations=[],
            unpricedNote="The feed reaches 2 destinations, cheapest fare an ITX placeholder.",
        )
        html = render_page(payload, budget_pounds=20)
        # The payload's own note is what the page carries, and the browser
        # suite drives the sentence it is written into.
        self.assertEqual(embedded_payload(html)["unpricedNote"], payload["unpricedNote"])

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
        # The options are real anchors, not a custom listbox, so what is
        # asserted is the list they go into and its own name: the browser
        # suite opens the picker, tabs to the first option and checks it is
        # an <a> pointing at a station page.
        self.assertIn('<ul id="originPicks" aria-labelledby="originPicksLabel">', self.html)
        self.assertIn('id="originPicksLabel"', self.html)
        self.assertIn('id="destinationTypes"', page_markup(self.html))
        self.assertIn('name="destinationType" value="city"', page_markup(self.html))
        self.assertIn('name="destinationType" value="seaside"', page_markup(self.html))

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

    def test_the_picker_closes_on_escape_and_returns_focus(self) -> None:
        # What the keyboard exit acts on: a real region, hidden until the
        # control opens it, that the control in the heading owns and announces
        # as collapsed. Escape and the focus that comes back are the browser
        # suite's -- it presses the key on the open picker and reads
        # document.activeElement afterwards.
        self.assertIn('<div id="originPicker" hidden>', self.html)
        self.assertIn(
            '<button id="changeOrigin" class="origin-slot" type="button" '
            'aria-expanded="false" aria-controls="originPicker">',
            self.html,
        )
        self.assertIn('<span id="originStatus" class="sr-only" role="status"></span>', self.html)

    def test_table_headers_name_their_columns_and_scope(self) -> None:
        # "Ticket" and "Tickets" as adjacent headers read as one column twice,
        # and "Fare code" was rejected while that column read in sentences. The
        # column is now the fare in the reader's own three words and the code
        # is in the row's disclosure (ADR-0053), so the header names what the
        # cells hold rather than what the feed calls them.
        # DS7 of the 19 October 2026 distill pass: every heading wears the one
        # uppercase label rule.
        self.assertIn('<th scope="col" class="eyebrow">Fare type</th>', self.html)
        self.assertNotIn('<th scope="col">Fare code</th>', self.html)
        self.assertIn('<th scope="col" class="eyebrow">Tickets</th>', self.html)
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

    def test_the_ticket_mix_is_stated_once(self) -> None:
        # Audit item 14, 9 October 2026: the count line, #modeNote and the
        # footer paragraph made the same point three times. The count line
        # names the mix (it belongs to the table), the note names what the
        # open mode means, and the footer keeps only the limitations. The
        # browser suite drives the note and the count line.
        self.assertIn("MODE_NOTE", page_script(self.html))
        self.assertIn("The cheapest single or return for each place", page_script(self.html))
        self.assertIn("ITX placeholder fares are excluded", self.html)
        # The sentence that repeated the mix is gone, and the standard-class
        # fact it carried is still in the method note where it belongs.
        self.assertNotIn("and on the list this page opens in", self.html)
        self.assertIn("cheapest displayable standard-class fare found in the feed", self.html)

    def test_the_ticket_set_is_defined_where_it_is_chosen(self) -> None:
        # C21 of the 17 October 2026 review, closed on 20 October 2026: the four
        # sets were chosen in the folded refinements and defined below the
        # table, more than a screen away from the choice and from the empty
        # state that asks a confused reader to read it. The paragraph is inside
        # the ticket fieldset now, directly under the options.
        panel = self.html.split('class="ticket-filter"')[1].split("</fieldset>")[0]
        self.assertIn('id="modeNote"', panel)
        self.assertLess(panel.index('class="filter-options segmented"'), panel.index('id="modeNote"'))
        # And nowhere else: a second copy below the table is the defect again.
        self.assertEqual(1, self.html.count('id="modeNote"'))
        # One sentence per set, saying what makes it different from the others.
        script = page_script(self.html)
        for sentence in (
            "The cheapest single or return for each place",
            "Unrestricted Anytime Day Returns: the same fare on any train.",
            "Every standard-class return the feed prices, restricted and advance included.",
            "Outbound singles rather than returns.",
        ):
            self.assertIn(sentence, script)
        self.assertIn("#modeNote { margin: .5rem 0 0; color: var(--muted); font-size: .875rem;", self.stylesheet)

    def test_the_budget_is_kept_in_reach_once_its_control_scrolls_away(self) -> None:
        # OV4 of the 19 October 2026 overdrive pass: at row 40 the budget is two
        # screens back. The rail holds it in 56px at the top of the viewport, and
        # appears only while the slider itself is out of view, so the page never
        # offers two controls for one number at once.
        rail = self.html.split('id="budgetRail"')[1].split("</div>")[0]
        # Hidden in the markup: a rail over a page whose own slider is on screen
        # would be a second control for one number.
        self.assertTrue(rail.lstrip().startswith("hidden"))
        self.assertIn('id="railBudget"', rail)
        self.assertIn('for="railBudget"', rail)
        self.assertRegex(self.html, r'id="railNow">&pound;\d+</span>')
        # The stop sentence belongs under the control the reader sets, not in a
        # 56px rail after the figure, where it read as a second value.
        self.assertNotIn('id="railStop"', rail)
        self.assertNotIn("aria-describedby", rail)
        self.assertNotIn(".budget-rail .tag", self.stylesheet)
        # Whether it appears when the slider leaves is the browser's fact, held by
        # the four rail checks in `station-filters.cjs`; this test holds the
        # markup a reader is given and the offsets that keep the two surfaces
        # from covering each other.
        # The stuck column headings move down while the rail is up, or the two
        # surfaces cover each other at the moment the rail arrives.
        self.assertIn('body[data-rail="on"] thead th { top: 3.5rem; }', self.stylesheet)
        self.assertIn("height: 3.5rem", self.stylesheet)

    def test_no_numeric_column_can_wrap(self) -> None:
        # Measured on the real Grantham page: the Price column was 56px wide
        # and 13 of the first 20 prices painted as two lines -- £10.10 read as
        # "£10.1" over "0", which is a different number rather than a tighter
        # column. The header word was deciding the width, so neither half of
        # the table wraps, and the browser suite measures the painted lines.
        # DS7 of the 19 October 2026 distill pass: the heading's type is the one
        # uppercase label rule now, and the nowrap that keeps a heading on one
        # line is the table's own.
        self.assertIn("th { white-space: nowrap; }", self.stylesheet)
        self.assertIn("color: var(--muted); font-weight: 700; }", self.stylesheet)
        self.assertIn("font-variant-numeric: tabular-nums; white-space: nowrap; }", self.stylesheet)
        # The station's own code is the widest run of characters in the
        # first column, and it must not wrap either: "KINGS" over "X" is a
        # different place.
        self.assertIn(
            ".station-code { color: var(--muted); font-variant-numeric: tabular-nums; }",
            self.stylesheet,
        )
        self.assertNotIn(".ticket-code", self.stylesheet)

    def test_the_route_asks_for_a_cross_fade_and_can_turn_it_off(self) -> None:
        # OV6 of the 19 October 2026 overdrive pass: moving between the chooser
        # and a station page is the same question with its subject changed, so
        # the browser cross-fades the two documents at the chevron's own .18s
        # rather than painting a white frame between them. A browser without
        # the API ignores the at-rule, which is the page as it was before, and
        # a reader who asked for less motion gets the cut.
        #
        # The opt-in is in the document, before its stylesheet link: the station
        # route fetches its CSS, and a navigation to a page whose fetch was slow
        # was skipped with "ViewTransition opt-in disabled" even though the
        # stylesheet carried the rule. Measured 30 October 2026.
        from trainbudget.build.page_templates import VIEW_TRANSITION_OPT_IN

        self.assertIn(VIEW_TRANSITION_OPT_IN, self.html)
        self.assertLess(
            self.html.index(VIEW_TRANSITION_OPT_IN),
            self.html.index('<link rel="stylesheet"'),
            "the opt-in cannot wait for the stylesheet it is meant to cover",
        )
        self.assertIn("animation-duration: .18s", self.stylesheet)
        self.assertIn(
            "::view-transition-old(root), ::view-transition-new(root) { animation: none; }",
            self.stylesheet,
        )

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
        # A build with no other station to change to ships no Change control at
        # all, so there is nothing focusable that would open nothing; the
        # browser suite reads that absence off the heading of a one-origin page.
        payload = dict(self.payload, stations=[])
        html = render_page(payload, budget_pounds=20)
        self.assertNotIn('<button id="changeOrigin"', html)
        self.assertIn('<div id="originPicker" hidden>', html)

    def test_the_embedded_script_parses_when_the_template_speaks_in_quotes(self) -> None:
        # The Python template is one big string, so a quote meant for the page
        # can terminate a JavaScript literal and take the whole page down. The
        # no-match wording quotes the reader's own input, so it is written with
        # single quotes inside double-quoted literals and must arrive intact.
        script = page_script(self.html)
        self.assertIn("We don’t have a page for ‘", script)
        self.assertNotIn('from \\"', script)

    def test_the_mobile_reflow_is_declared_at_44rem(self) -> None:
        # What this test may claim, and nothing more. The stacked layout's own
        # rules were asserted here as text -- the label rule, the two tracks,
        # the border cancellation -- and all of them were present, all passing,
        # while the station cell painted its brackets under its name and the
        # tickets cell collapsed to 1px (E16 of the 17 October 2026 audit). The
        # failure was how the rules interacted with the markup, which is not
        # something a string can see. The rules are now checked as painted
        # geometry in tests/browser/station-layout.cjs, at 390px, and this keeps
        # only the claim a template string can honestly make: the breakpoint is
        # still 44rem, the width the six-column table needs (ADR-0019).
        self.assertIn("@media (max-width: 44rem)", self.stylesheet)

    def test_the_table_markup_stays_a_real_table(self) -> None:
        # The reflow is display-only CSS. The markup has to stay a table so a
        # screen reader keeps its rows, its column headings and the relation
        # between them on a phone, where a stack of divs has none of the three.
        table_markup = self.html.split("<table>")[1].split("</table>")[0]
        self.assertNotIn("<div", table_markup)

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
        # DS2 of the 19 October 2026 distill pass: the figure is still the stop;
        # the sentence around it no longer spends its first clause saying where
        # the control is, because the heading is directly above it.
        self.assertIn("Stops at", hint)
        self.assertNotIn("in the heading", hint)
        self.assertIn("&pound;{}.00 for one adult".format(ceiling), hint)
        self.assertNotIn("__CEILING_NOTE__", self.html)

    def test_the_shared_station_list_does_not_block_the_page(self) -> None:
        # E2 of the 17 October 2026 audit. A classic script is a parse barrier,
        # and this one is the whole network's station list in front of the first
        # paint of a table that does not need it. The tag is read out of the
        # rendered page rather than off the function that writes it, so a page
        # that stops asking for the list with a deferred tag fails here too.
        page = render_page({**self.payload, "stationsSrc": "/stations-abc.js"}, budget_pounds=20)
        tag = re.search(r'<script src="/stations-abc\.js"[^>]*>', page)
        self.assertIsNotNone(tag, "the page did not ask for the shared station list")
        self.assertIn(" defer", tag.group(0), tag.group(0))

    def test_no_route_ships_a_placeholder(self) -> None:
        # E3 of the 17 October 2026 audit: the renderers substitute forty-odd
        # placeholders over a document they have already embedded a payload in,
        # so a placeholder a template gained and the renderer forgot would ship
        # literally on every page of a release. Each route is read here, not
        # just the station page, because each has its own substitution chain.
        index = build_demo_page.build_station_index({"GRN": 5}, self.fares.locations_by_crs)
        routes = {
            "station page": self.html,
            "station page with a shared list": render_page(
                {**self.payload, "stationsSrc": "/stations-abc.js"}, budget_pounds=20
            ),
            "station list": build_demo_page.render_chooser(index, budget_pounds=20),
            "privacy page": build_demo_page.render_privacy("note", "", "a@b.test"),
        }
        for name, page in routes.items():
            self.assertEqual(re.findall(r"__[A-Z_]+__", page), [], f"{name} shipped a placeholder")

    def test_feed_text_naming_a_placeholder_is_refused(self) -> None:
        # The substitutions run over the whole document after the payload is
        # embedded, so a note containing a placeholder's name would be rewritten
        # by the substitution that ran before it. Refusing is the only answer
        # that does not publish a sentence the feed did not write.
        with self.assertRaises(ValueError) as raised:
            render_page(
                {**self.payload, "note": "__BUDGET__", "synthetic": False},
                budget_pounds=20,
            )
        self.assertIn("__BUDGET__", str(raised.exception))

    def test_the_stated_ceiling_follows_the_party_the_reader_chooses(self) -> None:
        # The ceiling is party-aware -- two adults cost twice one -- so a note
        # written once at build time would name a stop the page leaves behind
        # the moment "Two adults" is chosen, and the figure would contradict the
        # input's own max. It is written from the resolved ceiling on every
        # render, and it names the party that ceiling was resolved for, because
        # "£252.00" is not a budget until the page says whose it is.
        script = page_script(self.html)
        # The note is written where the ceiling is resolved, which is the
        # budget's own clamp: the clamp is what sets the control's max, and the
        # chip rule asks it for the same number, so a note in the render would
        # be a second reader of a fact this panel already holds. The party
        # wording is there with it, because £252.00 is not a budget until
        # the page says whose it is.
        clamp = js_function(script, "clampBudget")
        self.assertIn("budgetCeilingNote", clamp)
        self.assertIn('"two adults"', clamp)
        self.assertIn('"one adult"', clamp)
        # That the clamp runs on every render, ahead of the empty states, is a
        # statement of the page's script and this suite does not assert those
        # (`tests/test_test_suite_shape.py`): what a reader can lose is the
        # sentence itself, and `tests/browser/station-filters.cjs` holds it,
        # reading the stated stop against the control's own max in the empty
        # state and again after the party changes.
        self.assertIn('id="budgetCeiling"', page_markup(self.html))

    def test_a_script_tag_in_the_data_cannot_close_the_script_early(self) -> None:
        payload = dict(self.payload, note="a note with </script> in it")
        html = render_page(payload, budget_pounds=20)
        payload_region = embedded_text(html)
        self.assertNotIn("</script>", payload_region)
        self.assertEqual(embedded_payload(html)["note"], "a note with </script> in it")

    # -- ticket links and the expander ------------------------------------

    def test_the_page_carries_the_journeys_behind_a_toggle_link(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(
            [option["depart"] for option in rows["NOT"]["departures"]],
            sorted(option["depart"] for option in rows["NOT"]["departures"]),
        )
        self.assertTrue(rows["NOT"]["departures"])
        self.assertEqual(rows["SLP"]["departures"], [])
        self.assertIn("toggleDetail", page_script(self.html))
        self.assertIn("buy", self.html)
        self.assertIn("Tickets", self.html)
        # The link opens a new tab, which the browser suite reads off the
        # rendered row and follows.
        self.assertIn('", opens in a new tab"', page_script(self.html))

    def test_the_row_expander_carries_one_name_on_every_row(self) -> None:
        # The toggle exists on every row now, because the row's fare and its
        # condition are in the panel it opens and a prices-only build has no
        # times to hang a toggle on (finding, 29 September 2026). The control is
        # the page's own chevron rather than a word, so the count it used to show
        # had nowhere visible to go and went into the accessible name. That made
        # the name two shapes -- "<n> times and fare details for X" on a timed
        # row and "Fare details for X" on one the build could not price times
        # for -- and a screen reader's list of controls read as two families
        # (audit item 27, 14 October 2026). One shape is kept: the shape is the
        # copy asserted here, and that each row's own name is appended to it is
        # the browser suite's, as are the times the panel lists.
        script = page_script(self.html)
        self.assertIn('"Fare details for "', script)
        self.assertNotIn("times and fare details for", script)
        self.assertIn("departures and the fare for ", script)

    def test_the_row_expander_is_a_chevron_that_keeps_its_words(self) -> None:
        # The control used to read "5 times" or "Fare details" in the last
        # column of every row. The face of it is now the page's shared chevron,
        # so three things have to hold at once: the mark is the same drawn
        # chevron the filter bar uses rather than a second drawing of it, the
        # words a screen reader needs are still the accessible name, and the
        # button still reaches 44px, because a mark alone is not a target. The
        # browser suite drives the chevron and the name.
        script = page_script(self.html)
        # The script holds the mark as a string, quoted by json rather than
        # pasted, so the same CHEVRON constant serves the markup and the rows.
        self.assertIn('const CHEVRON = "<svg class=', script)
        # 2.75rem is the 44px the row's other control is held to, and the
        # rotated state is what distinguishes open from closed.
        from trainbudget.build.page_templates import STATION_STYLESHEET

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
        # so a re-render's detached rows are collectable. The browser suite
        # drives the panel and the control that owns it.
        script = page_script(self.html)
        self.assertNotIn("nextElementSibling", script.split("function toggleDetail")[1].split("\nfunction ")[0])
        self.assertNotIn("nextElementSibling", script.split("function showCopyText")[1].split("\nfunction ")[0])
        # The two-region machinery went with the second panel: one region cannot
        # be mis-opened over another, which is the bug C28 was written for.
        for gone in ("closeRegion", "rowRegions", "nextRegionId"):
            self.assertNotIn(gone, script)
        # C09: the copied journey has to say which ticket it is, or a handoff to
        # a seller can silently become a different one. A reader in a named set
        # gets that set's name; a reader in the cheapest list chose a price
        # rather than a ticket type, so the handoff names the fare the row is
        # actually priced as (Q4). The rule itself lives in fareName, which the
        # shortlist and the copied list read as well, so the label is what is
        # asserted here and which label a reader gets is the browser suite's:
        # it copies a row in each mode and compares the line against the
        # mode's own visible label.
        self.assertIn('"Ticket: "', script)
        self.assertIn("fareName", script)

    def test_the_row_keeps_the_action_and_the_panel_holds_the_rest(self) -> None:
        # Finding 4 of the 29 September review: five controls in every row is a
        # hundred targets on page one, and four of them were things a reader
        # wants after deciding rather than while deciding. The row keeps the
        # ticket link, the expander and the shortlist toggle. The browser suite
        # drives the row and its panel.
        script = page_script(self.html)
        row_cell = js_function(script, "cellWithLinks")
        self.assertIn("Tickets", row_cell)
        for moved in ("Card details", "Copy journey for "):
            self.assertNotIn(moved, row_cell)
        # The shortlist is a column of its own rather than a third control in
        # this one, so it is named by its own heading and not by a word the
        # cell has to carry.
        # ... and the panel builds them, in one box, with the copy text landing
        # in that same box when the clipboard is refused.
        actions = js_function(script, "rowActions")
        self.assertNotIn("Card details", actions)
        self.assertIn("Copy", actions)
        # The Copy control names its row and says what it copies in the visible
        # word, and when the clipboard is refused the text is shown in a box the
        # reader is told about rather than left to guess. That the button is
        # inside the panel, that it copies that row, and what lands in the box
        # when the copy fails is driven by the browser suite.
        self.assertIn("Copy journey for ", script)
        self.assertIn("Could not copy automatically", script)
        self.assertIn("Select below", script)
        self.assertIn("Journey details to copy", script)

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

    def test_a_page_opens_on_a_fare_rather_than_on_an_empty_budget(self) -> None:
        # 9 of the 2,706 pages the 21 October 2026 release wrote priced nothing
        # inside the £20 the build opens at -- Farnborough North's cheapest fare
        # is £29.70, Thorne South's £58.10 -- so each opened on "No destinations
        # for up to £20.00" with the fares it does have one press away. A page
        # opens at the cheapest fare's pound instead: the reader's first screen
        # is the one fare this station sells, which is the question the page
        # answers.
        def opening(html: str) -> int:
            return int(re.search(r'id="budgetNumber"[^>]*value="(\d+)"', html).group(1))

        # The fixture's own fares are inside £20, so its page opens at the
        # build's figure or at its own (lower) ceiling rather than at a fare.
        self.assertGreaterEqual(opening(self.html), 1)
        self.assertLessEqual(opening(self.html), 20)
        dearer = [
            {
                **row,
                "adultPence": row["adultPence"] + 5000,
                "partyPence": row.get("partyPence", 0) + 5000,
            }
            for row in self.payload["destinations"]
        ]
        cheapest = min(row["adultPence"] for row in dearer)
        html = render_page(
            dict(self.payload, destinations=dearer, singleDestinations=[], anytimeDestinations=[]),
            budget_pounds=20,
        )
        self.assertEqual(opening(html), -(-cheapest // 100))
        self.assertGreater(opening(html), 20)

    def test_without_a_timetable_the_page_says_so(self) -> None:
        payload = build_payload(self.fares, None, "GRN")
        self.assertFalse(payload["hasJourneys"])
        self.assertTrue(all(row["minutes"] is None for row in payload["destinations"]))
        self.assertIn("no timetable was supplied", page_script(render_page(payload, budget_pounds=20)))


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
        # The pair's record is the rule, not the row: no tickets, routes or
        # endpoints in it (the row's tickets carry those), so rows that meet
        # the same rules share one record instead of each adding its own.
        pair_rule = payload["railcardRules"][yng["rule"]]
        self.assertFalse({"ticketCode", "routeCode", "location"} & set(pair_rule))
        pair_ids = {
            details["rule"]
            for key in ("destinations", "singleDestinations", "anytimeDestinations")
            for row in payload[key]
            if len(row.get("tickets") or []) == 2
            for details in row["railcards"].values()
        }
        texts = {payload["railcardRules"][rule]["text"] for rule in pair_ids}
        self.assertEqual(len(pair_ids), len(texts), "one record per distinct rule")

        self.assertLess(yng["pricePence"], leicester["adultPence"])

    def test_the_page_carries_more_places_than_the_selectors_price(self) -> None:
        # Two numbers, two questions. The index pass asks the fare selectors'
        # union, which is whether an origin can answer at all and which stations
        # the chooser offers (ADR-0019 decision 3); the chooser then *names* the
        # places the page carries, and that is a bigger number here, because
        # Leicester and Skegness are priced as two fares and no selector sees
        # them (ADR-0061). Measured on the real feed on 15 October 2026, the gap
        # was 50 places against 334 for Grantham -- a number a reader arriving
        # from the chooser had been mis-told by a factor of seven.
        payload = build_demo_page.build_payload(self.fares, self.timetable, "GRN", day=self.MONDAY)
        carries = {
            row["crs"]
            for key in ("destinations", "singleDestinations", "anytimeDestinations")
            for row in payload[key]
        }
        union = {
            row.crs
            for row in self.fares.priced_destinations_within(
                "GRN", build_demo_page.EVERYTHING_PENCE, adults=1, day=self.MONDAY
            )
        }
        self.assertEqual(build_demo_page.places_in_payload(payload), len(carries))
        self.assertEqual(
            build_demo_page._priced_destinations(self.fares, self.timetable, "GRN", self.MONDAY),
            len(union),
        )
        # And the fixture is the shape that catches the two being confused,
        # rather than a page whose numbers happened to agree.
        self.assertLess(len(union), len(carries))

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
        # Whether the through-train wording or the change wording is chosen is
        # settled below by running the page's own helpers over a journey with
        # no change and one with, and comparing what each prints.

        # The page's JavaScript is files of its own (F1 of the 8 October 2026
        # agent-efficiency audit), so this reads the block the page ships rather
        # than a copy of it inside a Python string. Both of these functions are
        # the row's own wording, so they are read from the panel that owns it.
        source = (Path(__file__).resolve().parents[1] / "page" / "station" / "row-cells.js").read_text(encoding="utf-8")
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
            "Two tickets, priced via NOTTINGHAM (a through train, so you stay on the train the "
            "whole way): the price is the two fares added together.",
        )
        self.assertEqual(
            shown["throughSummary"],
            "Two tickets, bought separately, priced via NOTTINGHAM (a through train, so you stay "
            "on the train the whole way).",
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
        with mock.patch.object(build_state, "CACHE_DIR", cache):
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


class BuildContextReleaseTest(unittest.TestCase):
    """A fan-out build holds no feed the workers are supposed to hold.

    The render phases read nothing from the parent's fares or timetable once
    the indexes are on disk, so keeping those objects reachable costs 4.1 GB
    on the measured machine beside four workers that hold 8.7 GB. A weak
    reference proves the memory is actually returned rather than merely
    dropped from the reader's side, which is how a `del` against a context
    field silently stopped freeing anything (four-dimension audit R9).
    """

    def test_release_feeds_returns_the_databases_the_render_does_not_read(self) -> None:
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        feed = Path(tmp) / "feed"
        build_synthetic_feed(feed)
        fares = FaresDb().load_feed(feed)
        timetable = TimetableDb().load_feed(feed)
        watched = (weakref.ref(fares), weakref.ref(timetable))

        ctx = build_demo_page.BuildContext(args=argparse.Namespace(), day=None)
        ctx.fares = fares
        ctx.timetable = timetable
        ctx.single_timetable = timetable
        del fares, timetable
        ctx.release_feeds()
        gc.collect()

        for name, ref in zip(("fares", "timetable"), watched):
            self.assertIsNone(ref(), f"the {name} database outlived the release")


class ReviewedOriginFixtureTest(unittest.TestCase):
    """The reviewed-name shape page holds the two things run 39818671598 found.

    tools/verify.py drives this page in the browser suite so the heading check
    meets an origin whose page name is not the feed's upper-case CIF name, and
    the railcard-note check meets a card-priced row that costs more for two
    than the one-adult ceiling the page opens on. Both checks passed every
    fixture page while being wrong, so this pins the shape that makes them
    meet the case: a fixture that drifted back to an upper-case name or a
    cheap enough party price would let both regressions back in unseen.
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _page(self, **flags: bool) -> Path:
        feed = self.tmp / "feed"
        build_synthetic_feed(feed, include_restrictions=True, **flags)
        out = self.tmp / "site" / "index.html"
        with contextlib.redirect_stdout(io.StringIO()):
            code = build_demo_page.main(["--feed", str(feed), "--origin", "KGX", "--out", str(out)])
        self.assertEqual(code, 0)
        return self.tmp / "site" / "from" / "london-kings-x" / "index.html"

    def test_the_origin_is_named_by_the_reviewed_list_not_the_feed(self) -> None:
        payload = embedded_payload(self._page(include_return_network=True, include_reviewed_origin=True).read_text(encoding="utf-8"))
        self.assertEqual(payload["origin"]["name"], "London Kings Cross")
        self.assertNotEqual(payload["origin"]["name"], payload["origin"]["name"].upper())

    def test_every_card_priced_row_costs_more_for_two_than_the_opening_ceiling(self) -> None:
        payload = embedded_payload(self._page(include_return_network=True, include_reviewed_origin=True).read_text(encoding="utf-8"))
        rows = payload["destinations"]
        self.assertGreater(len(rows), 1)
        # The first card the railcard-note check tries is the first the page
        # lists, with two adults; it has to price these rows for the check to
        # read them.
        first = payload["railcards"][0]["key"]
        priced = [row for row in rows if (row.get("railcards") or {}).get(first, {}).get("pricePence") is not None]
        self.assertEqual(len(priced), len(rows))
        opening_ceiling = max(row["adultPence"] for row in rows)
        self.assertGreater(min(row["partyPence"] for row in priced), opening_ceiling)

    def test_the_shape_page_still_lists_its_places_with_a_timetable(self) -> None:
        # ADR-0076 lists only the places a journey reaches, so a reviewed origin
        # with fares and no trains was a page with no rows: `tools/verify.py
        # --browser` wrote no station page and drove an older one. The fixture's
        # timetable carries this origin's trains, and this is what holds them.
        feed = self.tmp / "feed"
        build_synthetic_feed(
            feed,
            include_restrictions=True,
            include_return_network=True,
            include_reviewed_origin=True,
        )
        timetable = build_synthetic_timetable(
            feed, include_return_network=True, include_reviewed_origin=True
        )
        fares = FaresDb().load_feed(feed)
        payload = build_demo_page.build_payload(
            fares, TimetableDb().load_feed(timetable), "KGX", day=date(2026, 10, 5)
        )
        listed = {
            row["crs"]
            for key in ("destinations", "singleDestinations", "anytimeDestinations")
            for row in payload[key]
        }
        # Five of the six priced places are called at; Retford is the unpriced-by-
        # service row the return network carries, so it is not listed here.
        self.assertEqual(listed, {"GRN", "MAT", "SLD", "LEC", "BUL"})
        self.assertEqual(payload["unreachableDestinationCount"], 1)

    def test_the_flag_is_what_prices_kings_cross(self) -> None:
        # Off by default, so every other fixture keeps the feed it counts.
        self.assertFalse(self._page(include_return_network=True).exists())

    def test_the_flag_says_what_else_it_needs(self) -> None:
        with self.assertRaises(ValueError):
            build_synthetic_feed(self.tmp / "feed", include_reviewed_origin=True)
