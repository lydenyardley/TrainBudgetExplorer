"""T1: the tests that asserted the old table, the old shortlist and the old drawer.

Every one of these was a true statement about a design that has been replaced:
the fare code in a column, a named button on every row, a dialog for the card's
numbers, six paragraphs between the budget and the first fare. The tests are
rewritten against what the page now says, and each one says why, because a test
that only checks a string is a test that cannot tell a fix from a regression.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

BS = chr(92)
MIDDOT = BS + "u00b7"

PAIRS = [
    # -- the heading's station control ------------------------------------
    (
        '        self.assertIn(\'id="firstUse"\', self.html)\n'
        '        self.assertIn("<b>the station name</b>", self.html)',
        '        self.assertIn(\'id="firstUse"\', self.html)\n'
        '        self.assertIn("<b>station name</b>", self.html)\n'
        '        # The note is half of the opening sentence rather than a\n'
        '        # paragraph of its own: the page\'s promise and the one thing a\n'
        '        # reader cannot guess are read together, not two blocks apart.\n'
        '        self.assertLess(\n'
        '            self.html.index(\'id="pageIntro"\'),\n'
        '            self.html.index(\'id="firstUse"\'),\n'
        '        )\n'
        '        self.assertIn("</span></p>", self.html)',
    ),
    (
        '        self.assertIn("one ticket to that station and another from it", self.html)',
        '        # The station itself is named in the Changes column now, so the\n'
        '        # panel says only what is still worth saying and is nowhere else.\n'
        '        self.assertIn("one ticket to the station above", self.html)\n'
        '        self.assertIn(\'line.className = "interchange"\', self.html)\n'
        '        self.assertIn(\'"via " + stations.map((station) => station.name)\', self.html)',
    ),
    (
        '        self.assertIn("<b>the station name</b>", with_control)',
        '        self.assertIn("<b>station name</b>", with_control)',
    ),
    # -- the fare in the reader's words ------------------------------------
    (
        '        self.assertIn(\'(destination.restrictionDescription || "This fare carries a restriction code\', self.html)',
        '        self.assertIn(\'readable.textContent = destination.restrictionDescription ||\', self.html)\n'
        '        self.assertIn(\'if (restricted) {\', self.html)',
    ),
    (
        '        self.assertIn(\'readable.className = "condition"\', self.html)\n'
        '        self.assertIn("No travel conditions on this fare in the feed.", self.html)',
        '        self.assertIn(\'readable.className = "condition"\', self.html)\n'
        '        # An unrestricted fare used to open with a second paragraph saying\n'
        '        # there was nothing to read, which is the same information as\n'
        '        # silence said in a line.\n'
        '        self.assertIn("with no conditions in the feed.", self.html)\n'
        '        self.assertNotIn("No travel conditions on this fare in the feed.", self.html)',
    ),
    (
        '        self.assertIn(\'missing ? "No service" : duration(destination.minutes)\', self.html)\n'
        '        self.assertIn(\'missing ? "Unknown" : String(destination.changes)\', self.html)',
        '        self.assertIn(\'cell.textContent = missing ? "No service" : duration(destination.minutes);\', self.html)\n'
        '        # The change count is a word rather than a digit, and the station it\n'
        '        # changes at sits under it in the column whose header says Changes.\n'
        '        self.assertIn("function changeCount(changes)", self.html)\n'
        '        self.assertIn(\'return changes === 0 ? "Direct"\'.replace("? ", "? "), self.html)\n'
        '        self.assertIn(\'count.textContent = missing ? "Unknown" : changeCount(destination.changes);\', self.html)',
    ),
    (
        '        self.assertEqual((card["minAdults"], card["maxAdults"]), (1, 1))',
        '        # The bounds are each card\'s own, measured on the real feed on\n'
        '        # 1 October 2026, so the party filter has something to take out.\n'
        '        bounds = {c["key"]: (c["minAdults"], c["maxAdults"]) for c in self.payload["railcards"]}\n'
        '        self.assertEqual(bounds["YNG"], (1, 8))\n'
        '        self.assertEqual(bounds["2TR"], (2, 2))\n'
        '        self.assertEqual(bounds["BB2"], (1, 1))',
    ),
    # -- the shortlist is a strip, not a section ---------------------------
    (
        '        self.assertIn(\'id="shortlistHeading">Shortlist\', self.html)\n'
        '        self.assertIn("not a booking: no train is chosen and no ticket is held", self.html)\n'
        '        self.assertIn(\'save.className = "toggle shortlist-toggle"\', self.html)\n'
        '        self.assertIn(\'save.setAttribute("aria-pressed", "false")\', self.html)',
        '        self.assertIn(\'id="shortlistBar" aria-label="Shortlist"\', self.html)\n'
        '        self.assertIn("not a booking", self.html)\n'
        '        # One control, above the table, rather than a named button on every\n'
        '        # row: twenty rows carried twenty copies of the same word, and\n'
        '        # pressing one changed its own text and reflowed the table.\n'
        '        self.assertIn(\'id="shortlistPick"\', self.html)\n'
        '        self.assertIn("function renderShortlistPicker()", self.html)\n'
        '        self.assertIn("shortlistPick.addEventListener(\\"change\\"", self.html)\n'
        '        self.assertNotIn("shortlist-toggle", self.html)\n'
        '        # ... and the places it holds are drawn where the control is.\n'
        '        self.assertLess(\n'
        '            self.html.index(\'id="shortlistBar"\'),\n'
        '            self.html.index("<table>"),\n'
        '        )',
    ),
    (
        '        row = script.split("function shortlistRow(")[1].split("\\nfunction ")[0]\n'
        '        self.assertIn(r\'" ' + MIDDOT + ' " + fareName(destination)\', row)',
        '        # The chip carries the name and the price -- the reason the place is\n'
        '        # there -- and the fare name travels in the copied text and on the\n'
        '        # row itself rather than making every chip three lines tall.\n'
        '        row = script.split("function shortlistRow(")[1].split("\\nfunction ")[0]\n'
        '        self.assertIn(\'price.textContent = money(priceOf(destination));\', row)\n'
        '        self.assertNotIn("fareName(destination)", row)',
    ),
    # -- the railcard collection the page offers ---------------------------
    (
        '        self.assertEqual(list(cards), ["YNG"], "the demo feed carries one reviewed card")',
        '        # All six reviewed cards, with the party each one prices. The\n'
        '        # fixture used to carry a single card under a code that is not in\n'
        '        # the reviewed set at all, so the control built to offer six came\n'
        '        # out with one option in it.\n'
        '        self.assertEqual(\n'
        '            list(cards),\n'
        '            ["YNG", "DIS", "NEW", "SRN", "BB2", "2TR"],\n'
        '            "the demo feed prices the six reviewed cards",\n'
        '        )\n'
        '        self.assertEqual((cards["2TR"]["minAdults"], cards["2TR"]["maxAdults"]), (2, 2))',
    ),
    # -- the card's numbers, in the row rather than in a dialog -------------
    (
        '        self.assertIn(\'id="railcardDrawer"\', self.html)\n'
        '        self.assertIn("showRailcardDetails(destination)", self.html)\n'
        '        self.assertIn("DATA.railcardRules[details.rule]", self.html)\n'
        '        self.assertIn("travel condition rather than a card ban", self.html)\n'
        '        self.assertIn("Exact DTD rule", self.html)',
        '        # The explanation is one paragraph in the row\'s own disclosure.\n'
        '        # A dialog on every row, opened on top of a page the reader was\n'
        '        # already reading, to be told a number the row beside it carried.\n'
        '        self.assertIn("function cardNote(destination)", self.html)\n'
        '        self.assertIn("panel.append(card)", self.html)\n'
        '        self.assertIn("DATA.railcardRules[details.rule]", self.html)\n'
        '        self.assertIn("travel condition rather than a card ban", self.html)\n'
        '        self.assertNotIn(\'id="railcardDrawer"\', self.html)\n'
        '        # The exact rule is still on the page, filed with the codes it is\n'
        '        # a record of rather than headlined in a panel of its own.\n'
        '        self.assertIn("function railcardRuleFor(destination)", self.html)\n'
        '        self.assertIn(\'add("Railcard rule", rule)\', self.html)',
    ),
    (
        '    def test_the_drawer_never_shows_more_than_the_row_it_was_opened_from(self) -> None:\n'
        '        # The row is priced at the cheaper of the standard fare and the card\'s.\n'
        '        # The drawer used to print the card\'s own price under the label\n'
        '        # "Discounted fare", so on a fare whose card minimum is above the\n'
        '        # discount it opened showing GBP 12.00 against a row showing GBP 8.70,\n'
        '        # and called the bigger number a discount.',
        '    def test_the_railcard_note_never_names_a_price_above_the_row(self) -> None:\n'
        '        # The row is priced at the cheaper of the standard fare and the card\'s.\n'
        '        # The card\'s own price used to be printed under the label "Discounted\n'
        '        # fare", so on a fare whose card minimum is above the discount it\n'
        '        # showed GBP 12.00 against a row showing GBP 8.70, and called the\n'
        '        # bigger number a discount.',
    ),
    (
        '        # The drawer takes its headline number from the same rule the table uses.\n'
        '        self.assertIn("const shownPrice = (destination, details) =>", self.html)\n'
        '        self.assertIn(\n'
        '            "return Math.min(destination.adultPence, details.pricePence);", self.html\n'
        '        )\n'
        '        # And the label no longer calls a price above the standard fare a discount.\n'
        '        self.assertIn("<dt>Price with this card</dt>", self.html)\n'
        '        self.assertNotIn("<dt>Discounted fare</dt>", self.html)\n'
        '        self.assertIn("which is the standard fare", self.html)\n'
        '        self.assertIn("does not reduce this fare", self.html)\n'
        '        self.assertIn(\n'
        '            \': money(shown) + " per adult, which is the standard fare";\', self.html\n'
        '        )\n'
        '        self.assertLess(\n'
        '            self.html.index(\'? money(shown) + " per adult"\'),\n'
        '            self.html.index(\n'
        '                \': money(shown) + " per adult, which is the standard fare";\'\n'
        '            ),\n'
        '            "the caption is on the branch where the card is not the price shown",\n'
        '        )',
        '        # The note never quotes a number at all, so it cannot quote one\n'
        '        # above the row: it names the card, says whether the card lowers\n'
        '        # the fare, and gives the card\'s own price and the standard fare as\n'
        '        # two labelled figures a reader can compare.\n'
        '        self.assertIn("const cardBeatsStandard =", self.html)\n'
        '        self.assertIn("details.pricePence < destination.adultPence", self.html)\n'
        '        self.assertIn("does not reduce this fare", self.html)\n'
        '        self.assertIn("This row is priced at the cheaper of the two", self.html)\n'
        '        # The minimum is named as what it is, in the branch where the card\n'
        '        # does help, rather than as a discount that made the fare dearer.\n'
        '        self.assertIn("is the price here, so the discount took it no lower.", self.html)\n'
        '        self.assertIn("does not raise it.", self.html)',
    ),
    (
        '    def test_the_drawer_explains_which_card_it_is_about(self) -> None:\n'
        '        # The reader picked one card out of six, so the drawer has to name it.\n'
        '        # A drawer that explained "the railcard" while the page listed six\n'
        '        # would answer a question nobody asked.\n'
        '        self.assertIn(\'id="railcardName"\', self.html)\n'
        '        self.assertIn(\'name.textContent = card.label + " (" + card.codes.join(", ") + ")";\',\n'
        '                      self.html)\n'
        '        # With no card chosen there is nothing to explain, and the drawer says\n'
        '        # that rather than describing a rule for a card the reader did not name.\n'
        '        self.assertIn(\'status.dataset.state = "none";\', self.html)\n'
        '        self.assertIn("No railcard is selected, so this fare is shown at its standard price.",\n'
        '                      self.html)',
        '    def test_the_railcard_note_names_the_card_it_is_about(self) -> None:\n'
        '        # The reader picked one card out of six, so the note has to name it.\n'
        '        # A note that explained "the railcard" while the page listed six would\n'
        '        # answer a question nobody asked.\n'
        '        self.assertIn("const card = railcards[railcardSelect.value];", self.html)\n'
        '        self.assertIn("note.textContent =\\n      card.label +", self.html)\n'
        '        # With no card chosen there is nothing to explain, so there is no\n'
        '        # paragraph: the control above already says the prices are standard,\n'
        '        # and a sentence on every expanded row repeating the page\'s default\n'
        '        # is the noise this replaced.\n'
        '        self.assertIn(\n'
        '            "if (noCard() || !railcards[railcardSelect.value]) return null;", self.html\n'
        '        )\n'
        '        self.assertIn(\n'
        '            "This feed prices no " + card.label + " fare to " + destination.name, self.html\n'
        '        )',
    ),
    # -- what stands between the count and the table ------------------------
    (
        '        for note in (\'id="linkNote"\', \'id="disclosure"\', \'id="buildMetadata"\'):\n'
        '            self.assertLess(self.html.index(\'<details class="link-terms"\'), self.html.index(note))\n'
        '            self.assertLess(self.html.index(note), self.html.index("<table>"))\n'
        '        self.assertIn("About the ticket link, and how this page was built", self.html)',
        '        for note in (\'id="linkNote"\', \'id="disclosure"\'):\n'
        '            self.assertLess(self.html.index(\'<details class="link-terms"\'), self.html.index(note))\n'
        '            self.assertLess(self.html.index(note), self.html.index("<table>"))\n'
        '        # The build stamp is reference material and went under the table\n'
        '        # with the rest of it, rather than sitting in the fold a reader has\n'
        '        # to get through before the first fare.\n'
        '        self.assertGreater(\n'
        '            self.html.index(\'id="buildMetadata"\'), self.html.index("<table>")\n'
        '        )\n'
        '        self.assertIn("About the ticket link", self.html)',
    ),
    (
        '        self.assertIn("no times or changes are shown", self.html)\n'
        '        self.assertIn("fastest journey time and the number of changes", self.html)',
        '        self.assertIn("no times are shown", self.html)\n'
        '        self.assertIn("with the fastest time and the fewest changes", self.html)',
    ),
    # -- the heading's size -------------------------------------------------
    (
        '        self.assertIn("--h1: clamp(2rem, 6vw, 6rem)", self.stylesheet)',
        '        self.assertIn("--h1: clamp(2rem, 7vw, 7rem)", self.stylesheet)',
    ),
    # -- what the phone reflow reads out ------------------------------------
    (
        '        self.assertIn("cell.dataset.label = label", self.html)',
        '        self.assertIn("cell.dataset.label =", self.html)\n'
        '        self.assertIn(\'cell.dataset.label = "Fare type"\', self.html)',
    ),
    (
        '        # Finding, 29 September 2026: the FARE and CONDITIONS columns repeated\n'
        '        # one sentence on all 20 rows, so the row carries the fare\'s own code\n'
        '        # and the sentence moved into the row\'s disclosure. The label on the\n'
        '        # new cell is what the phone reflow reads out.\n'
        '        self.assertIn(\'cell.dataset.label = "Fare code"\', self.html)',
        '        # The column is the fare in three words. SDR, 2AS and BPS are a\n'
        '        # seller\'s vocabulary and they were the column, on every row, in\n'
        '        # front of the one number the reader came for; the code is in the\n'
        '        # row\'s own record. The label is what the phone reflow reads out.\n'
        '        self.assertIn(\'cell.dataset.label = "Fare type"\', self.html)\n'
        '        self.assertIn(\'function fareTypeWord(destination)\', self.html)\n'
        '        self.assertIn(\'return "Advance"\', self.html)\n'
        '        self.assertIn(\'return "Restricted"\', self.html)\n'
        '        self.assertIn(\'return "Regular"\', self.html)',
    ),
    # -- the header row ------------------------------------------------------
    (
        '        self.assertIn(\'<th scope="col">Fare code</th>\', self.html)',
        '        self.assertIn(\'<th scope="col">Fare type</th>\', self.html)\n'
        '        self.assertNotIn(\'<th scope="col">Fare code</th>\', self.html)',
    ),
    (
        '        self.assertIn(".ticket-code { font-variant-numeric: tabular-nums; letter-spacing: .02em; white-space: nowrap; }",\n'
        '                      self.stylesheet)',
        '        # The station\'s own code is the widest run of characters in the\n'
        '        # first column, and it must not wrap either: "KINGS" over "X" is a\n'
        '        # different place.\n'
        '        self.assertIn(\n'
        '            ".station-code { color: var(--muted); font-variant-numeric: tabular-nums; }",\n'
        '            self.stylesheet,\n'
        '        )\n'
        '        self.assertNotIn(".ticket-code", self.stylesheet)',
    ),
    # -- what the row keeps -------------------------------------------------
    (
        '        row_cell = script.split("function cellWithLinks")[1].split("function rowActions")[0]\n'
        '        self.assertIn(\'link.textContent = "Tickets"\', row_cell)\n'
        '        self.assertIn("toggle.textContent = times", row_cell)\n'
        '        self.assertIn(\'save.className = "toggle shortlist-toggle"\', row_cell)\n'
        '        for moved in ("Card details", "Copy the journey details", "copyJourney("):\n'
        '            self.assertNotIn(moved, row_cell)',
        '        row_cell = script.split("function cellWithLinks")[1].split("function cardNote")[0]\n'
        '        self.assertIn(\'link.textContent = "Tickets"\', row_cell)\n'
        '        self.assertIn("toggle.textContent = times", row_cell)\n'
        '        for moved in ("Card details", "Copy the journey details", "copyJourney(", "toggleShortlist("):\n'
        '            self.assertNotIn(moved, row_cell)',
    ),
    (
        '        actions = script.split("function rowActions")[1].split("function showRailcardDetails")[0]\n'
        '        self.assertIn(\'cardDetails.textContent = "Card details"\', actions)',
        '        actions = script.split("function rowActions")[1].split("\\nfunction ")[0]\n'
        '        self.assertNotIn("Card details", actions)',
    ),
    # -- the runner ----------------------------------------------------------
    (
        '    def test_a_second_run_serves_what_the_first_one_wrote(self) -> None:\n'
        '        _, said, builds, served = self.run_main(site_exists=True)\n'
        '        self.assertEqual(builds, 0)\n'
        '        self.assertEqual(len(served), 1)\n'
        '        self.assertIn("without rebuilding", said)',
        '    def test_a_second_run_serves_what_the_first_one_wrote(self) -> None:\n'
        '        # --origin is the fast single-station build, and it is the one a\n'
        '        # second run of it serves without rebuilding.\n'
        '        _, said, builds, served = self.run_main("--origin", "GRA", site_exists=True)\n'
        '        self.assertEqual(builds, 0)\n'
        '        self.assertEqual(len(served), 1)\n'
        '        self.assertIn("without rebuilding", said)\n'
        '\n'
        '    def test_the_default_builds_the_whole_network(self) -> None:\n'
        '        # A one-station build has nowhere for the heading\'s station control\n'
        '        # to go, so the name renders as plain text -- the page that cannot\n'
        '        # change station. The default is the network, and it says what that\n'
        '        # costs before it starts.\n'
        '        _, said, builds, served = self.run_main(site_exists=False)\n'
        '        self.assertEqual(builds, 1)\n'
        '        self.assertEqual(len(served), 1)\n'
        '        self.assertIn("one page per priced station", said)\n'
        '        self.assertIn("--origin GRA", said)\n'
        '\n'
        '    def test_a_build_older_than_the_sources_is_not_served(self) -> None:\n'
        '        # Nine hours of committed work, a double-clicked runner, and a page\n'
        '        # from before it: nothing on the page says so. The runner rebuilds\n'
        '        # when what it would serve is out of date, and names the reason.\n'
        '        with tempfile.TemporaryDirectory() as tmp:\n'
        '            site = Path(tmp)\n'
        '            manifest = site / run.RELEASE_MANIFEST_NAME\n'
        '            manifest.write_text("{}", encoding="utf-8")\n'
        '            os.utime(manifest, (1000, 1000))\n'
        '            with mock.patch.object(run, "SITE", site):\n'
        '                self.assertTrue(run.sources_are_newer())\n'
        '            os.utime(manifest, (time.time() + 60, time.time() + 60))\n'
        '            with mock.patch.object(run, "SITE", site):\n'
        '                self.assertFalse(run.sources_are_newer())\n'
        '        # A build with no manifest answers no: an unreadable answer must\n'
        '        # never be the one that starts an hour-long build.\n'
        '        with tempfile.TemporaryDirectory() as tmp:\n'
        '            with mock.patch.object(run, "SITE", Path(tmp)):\n'
        '                self.assertFalse(run.sources_are_newer())',
    ),
]

patch("tests/test_build_demo_page.py", PAIRS)

patch(
    "tests/test_atoc_fares.py",
    [
        (
            '        self.assertEqual(self.db.restrictions.record_counts["RR"], 2)',
            '        # One pair of rules per reviewed card, because an RR record is\n'
            '        # keyed by the card it governs: a card with no rule of its own is\n'
            '        # not discounted at all, which is how the fixture came to offer\n'
            '        # one card in a control built to offer six.\n'
            '        self.assertEqual(self.db.restrictions.record_counts["RR"], 12)',
        ),
    ],
)
