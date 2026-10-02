"""C2, part two: the tests that followed `cardNote` out of the drawer.

`c2_cardnote.py` rewrote `cardNote` so the card's answer lives in the panel
the row already opens, and never quotes a figure above the row. It rewrote
the page and left every test of the old drawer standing: three of them
asserted on an `id="railcardDrawer"` the page no longer has, and one
asserted a wording the note no longer uses. They were rewritten by hand and
the rewrite was never made a patch script, which is why the replay chain
stopped at `r3_note_tests.py` -- that script's first anchor is a line only
this rewrite produces.

It is here rather than in a later script because this is the script that made
the change the tests describe.

The block was generated from the two files rather than transcribed; see
`_cache/make_c2_gap.py`. It leaves the state `r3_note_tests.py` expects, so
applying this and then `r3` reproduces the committed file.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = '''        # The refused fare names the rule that refused it, so the drawer can say
        # which DTD record did it rather than only that it did not apply.
        refused = next(r for r in self.payload["destinations"] if r["crs"] == "NOT")
        ban = self.payload["railcardRules"][refused["railcards"]["YNG"]["rule"]]
        self.assertTrue(ban["totalBan"])
        self.assertEqual(ban["sequence"], "0001")
        self.assertIn('id="railcardDrawer"', self.html)
        self.assertIn("showRailcardDetails(destination)", self.html)
        self.assertIn("DATA.railcardRules[details.rule]", self.html)
        self.assertIn("travel condition rather than a card ban", self.html)
        self.assertIn("Exact DTD rule", self.html)

    def test_the_drawer_never_shows_more_than_the_row_it_was_opened_from(self) -> None:
        # The row is priced at the cheaper of the standard fare and the card's.
        # The drawer used to print the card's own price under the label
        # "Discounted fare", so on a fare whose card minimum is above the
        # discount it opened showing GBP 12.00 against a row showing GBP 8.70,
        # and called the bigger number a discount.
        row = next(r for r in self.payload["destinations"] if r["crs"] == "LCN")
        card = row["railcards"]["YNG"]
        self.assertEqual(row["adultPence"], 870)
        self.assertEqual(card["pricePence"], 1200)
        shown = min(row["adultPence"], card["pricePence"])
        self.assertEqual(shown, 870)
        self.assertLessEqual(shown, row["adultPence"], "a card never raises a row's price")
        # The drawer takes its headline number from the same rule the table uses.
        self.assertIn("const shownPrice = (destination, details) =>", self.html)
        self.assertIn(
            "return Math.min(destination.adultPence, details.pricePence);", self.html
        )
        # And the label no longer calls a price above the standard fare a discount.
        self.assertIn("<dt>Price with this card</dt>", self.html)
        self.assertNotIn("<dt>Discounted fare</dt>", self.html)
        self.assertIn("which is the standard fare", self.html)
        self.assertIn("does not reduce this fare", self.html)
        self.assertIn(
            ': money(shown) + " per adult, which is the standard fare";', self.html
        )
        self.assertLess(
            self.html.index('? money(shown) + " per adult"'),
            self.html.index(
                ': money(shown) + " per adult, which is the standard fare";'
            ),
            "the caption is on the branch where the card is not the price shown",
        )

    def test_the_drawer_explains_which_card_it_is_about(self) -> None:
        # The reader picked one card out of six, so the drawer has to name it.
        # A drawer that explained "the railcard" while the page listed six
        # would answer a question nobody asked.
        self.assertIn('id="railcardName"', self.html)
        self.assertIn('name.textContent = card.label + " (" + card.codes.join(", ") + ")";',
                      self.html)
        # With no card chosen there is nothing to explain, and the drawer says
        # that rather than describing a rule for a card the reader did not name.
        self.assertIn('status.dataset.state = "none";', self.html)
        self.assertIn("No railcard is selected, so this fare is shown at its standard price.",
                      self.html)

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
        self.assertIn("does not reduce this fare.", self.html)
        self.assertIn("because the minimum fare the feed applies to this ", self.html)
        self.assertIn("This row is priced at the cheaper of the two", self.html)
'''

NEW = '''        # The refused fare names the rule that refused it, so the drawer can say
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
        self.assertIn("does not reduce this fare", self.html)
        self.assertIn("This row is priced at the cheaper of the two", self.html)
        # The minimum is named as what it is, in the branch where the card
        # does help, rather than as a discount that made the fare dearer.
        self.assertIn("is the price here, so the discount took it no lower.", self.html)
        self.assertIn("does not raise it.", self.html)

    def test_the_railcard_note_names_the_card_it_is_about(self) -> None:
        # The reader picked one card out of six, so the note has to name it.
        # A note that explained "the railcard" while the page listed six would
        # answer a question nobody asked.
        # The label is read from the variable, not spelled out, so the test
        # reads the variable and the two sentences the note branches into.
        self.assertIn("const card = railcards[railcardSelect.value];", self.html)
        self.assertIn('card.label + " does not reduce this fare. Its own price here is "', self.html)
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
        self.assertIn("does not reduce this fare.", self.html)
        self.assertIn("because the minimum fare the feed applies to this ", self.html)
        self.assertIn("This row is priced at the cheaper of the two", self.html)
'''

patch("tests/test_build_demo_page.py", [(OLD, NEW)])
