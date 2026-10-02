"""N6: the tests for the five fixes.

`test_the_mobile_reflow_keeps_the_markup_a_real_table` asserted `flex-wrap`
appears in the reflow, because the rule it was really protecting is that no
cell can sit outside the viewport however long a station name is. A flex wrap
was how that was achieved; a `minmax(0, 1fr)` grid track is how it is achieved
now, and the assertion is moved onto the mechanism that carries the property,
plus a check that no cell was given a width.

Four new tests, one per remaining fix, each asserting the property rather than
the string that happens to carry it where one exists.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = '''        self.assertIn("@media (max-width: 44rem)", self.stylesheet)
        # From the first max-width block to the end of the stylesheet: the
        # footer nav has its own small block, and the table's rules must be
        # found wherever they sit.
        reflow = self.stylesheet[self.stylesheet.index("table, tbody { display: block; }") - 200:]
        self.assertIn("flex-wrap", reflow)
        self.assertNotIn("display: none", reflow.split("thead")[0])
        self.assertIn("thead { position:absolute; width:1px; height:1px;", reflow)
        self.assertIn("td[data-label]::before { content: attr(data-label)", reflow)
        table_markup = self.html.split("<table>")[1].split("</table>")[0]
        self.assertNotIn("<div", table_markup)
'''

NEW = '''        self.assertIn("@media (max-width: 44rem)", self.stylesheet)
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
                row["journeyState"], "no timetable in this build",
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
                self.assertEqual(row["journeyState"], "no timetable in this build")

    def test_the_standard_fare_under_a_discounted_price_is_a_step_down_the_ladder(self) -> None:
        # The price it sits under is the cell's own size, 1rem. One clear step
        # down is a fifth off it, not a twentieth: at .875em the note was 14px
        # against a 16px price, which is the size the page already gives every
        # other small note on a row, so the cell read as two equal numbers
        # rather than one price with a note under it.
        was = float(re.search(r"td\\.num \\.was \\{[^}]*font-size: ([0-9.]+)em",
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
            r"\\.chipcount \\{[^}]*margin-left: [^;}]+;",
            "the count is separated from the type name by a margin",
        )
'''

if __name__ == "__main__":
    patch("tests/test_build_demo_page.py", [(OLD, NEW)])