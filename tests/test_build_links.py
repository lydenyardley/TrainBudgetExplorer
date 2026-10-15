"""What a row hands off: the seller link, its disclosure, and the copy.

F6 of the 8 October 2026 agent-efficiency audit moved the page's content
tests out of the class they all shared, by subject, over the fixture in
``tests/page_harness.PageTestCase``.
"""

from __future__ import annotations

from build_demo_page import build_payload, render_page
from retailer import DISCLOSURE
from tests.page_harness import page_script, setUpModule, tearDownModule, PageTestCase


class TicketHandoffTest(PageTestCase):
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
        self.assertIn("DATA.linkNote", page_script(self.html))

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
        # a deep-link build would then be contradicting. The browser suite
        # drives what each build reveals.
        self.assertIn("linkNote", self.html)
        self.assertIn("disclosure", self.html)
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
        self.assertIn('"About the ticket link, and how this site is paid"', page_script(self.html))
        self.assertIn("linkTerms", self.html)

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

    def test_every_row_offers_to_copy_its_journey_details(self) -> None:
        # The visible word carries what the control does now, so the test names
        # it the way the reader sees it and the accessible name adds only the row
        # it belongs to (audit item 28, 14 October 2026).
        self.assertIn('"Copy journey"', page_script(self.html))
        self.assertIn("Copy journey for ", page_script(self.html))
        # Which row's control copies which row's journey is the browser suite's
        # to answer: it presses the control on a row and reads the clipboard.

    def test_the_copied_text_names_the_things_a_seller_asks_for(self) -> None:
        for label in ('"From: "', '"To: "', '"Date: "', '"Passengers: "'):
            self.assertIn(label, page_script(self.html))

    def test_the_copied_text_names_the_railcard_only_for_the_party_price(self) -> None:
        # The card is never sent anywhere; it is named as something to tick, and
        # only when the price on screen is the one that needs it. Which card is
        # named is the browser suite's to answer: it copies a row as one adult
        # and as two and reads the clipboard both times.
        self.assertIn('" discount is not sent to the seller', page_script(self.html))
        self.assertNotIn('"Two Together discount is not sent to the seller', page_script(self.html))

    def test_the_copied_date_is_not_parsed_through_the_date_object(self) -> None:
        # new Date("2026-10-05") is UTC midnight and prints as the 4th for a
        # reader behind UTC. A copied date off by one is worse than no date.
        # The clock itself is a different question: reading today's date needs
        # no parsing, so a bare new Date() is fine and the ban is on the
        # argument form, which is the one that guesses a time zone.
        self.assertNotIn('new Date("', page_script(self.html))
        self.assertNotIn("new Date(iso", page_script(self.html))

    def test_a_failed_copy_is_never_reported_as_a_copy(self) -> None:
        # Clipboard access is refused when the file is opened from disk, so the
        # failure path has to exist and must not claim the text was copied. The
        # browser suite drives the manual path.
        self.assertIn("navigator.clipboard", page_script(self.html))
        self.assertIn("Could not copy automatically", page_script(self.html))
        self.assertIn("Select below", page_script(self.html))
        self.assertEqual(page_script(self.html).count('"Copied"'), 1)

    def test_the_copy_confirmation_is_announced_and_not_only_shown(self) -> None:
        self.assertIn('id="copyStatus" role="status"', self.html)
        self.assertIn("class=\"sr-only\"", self.html)

    def test_the_newlines_in_the_copy_are_escaped_for_the_browser(self) -> None:
        # A real newline inside a JavaScript string literal is a SyntaxError that
        # takes the whole page down, and a Python template will happily produce
        # one from "\n". The assertion left here is the guard against that: no
        # string the page joins can start with one. That the copied text really
        # does arrive as separate lines is the browser suite's to answer -- it
        # reads the clipboard back and splits it on newlines, so a page that
        # joined on anything else would hand it one long line. That is how this
        # bug shipped past every test in this file, and why browser_test.cjs
        # exists.
        self.assertNotIn('join("\n', page_script(self.html))

    def test_the_footer_states_a_commission_only_when_one_is_paid(self) -> None:
        # publish-checklist: the affiliate disclosure is present if commission
        # is enabled, and absent otherwise. The sentence is the one retailer.py
        # already uses, and the footer is where a reader who never opens the
        # ticket-link fold still meets it.
        self.assertIn('id="commissionDisclosure" hidden', self.html)
        self.assertIn("commissionDisclosure", self.html)
        # The two facts the line is written from: this build pays no
        # commission and carries no disclosure, so nothing reaches the footer.
        # Whether the line then appears above the table, and that the fold
        # above the first ticket action names the payment when it does, is
        # the browser suite's.
        self.assertFalse(self.payload["tracked"])
        self.assertIsNone(self.payload["disclosure"])
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

    def test_the_ticket_link_says_where_it_opens(self) -> None:
        # Audit item 11, 9 October 2026: the row's link opens a new tab and
        # nothing on the row said so. The accessible name carries the fact
        # where the reader is told what the control does, the tooltip repeats
        # it beside the seller it names, and the handoff sentence says it where
        # the reader is told what the link cannot fill in for them.
        # The accessible name is the sentence the reader is given: it names the
        # destination and then what pressing it does, and the tooltip beside
        # the seller repeats the same ending. Which link each row's is, and
        # that pressing one really opens a tab, is driven by the browser suite.
        self.assertIn('"Tickets for "', page_script(self.html))
        self.assertIn('", opens in a new tab"', page_script(self.html))
        self.assertIn("opens the seller's own search page in a new tab", self.html)

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
