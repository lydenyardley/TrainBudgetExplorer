"""R3: the tests that pinned the card note's exact wording.

`cardNote`'s "does not reduce" branch opened with the card's own price, which on
a real page is often the DTD minimum -- £12.00 quoted above a row showing
£2.70. It now opens with `priceOf(destination)`, the figure the Price cell
renders.

Three tests asserted the old sentence by name. Two of them are reworded to the
new one. The third is the interesting one: it existed to prove the note never
quotes a number above the row, and the way it proved that was by reading the
source. It can now assert the thing directly -- the note is built from the same
`priceOf` the price cell uses, so the figure it leads with is the figure in the
row by construction rather than by coincidence.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

TARGET = "tests/test_build_demo_page.py"

OLD_1 = '''        self.assertIn("const cardBeatsStandard =", self.html)
        self.assertIn("details.pricePence < destination.adultPence", self.html)
        self.assertIn("does not reduce this fare", self.html)
        self.assertIn("This row is priced at the cheaper of the two", self.html)'''

NEW_1 = '''        self.assertIn("const cardBeatsStandard =", self.html)
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
        )'''

OLD_2 = '''        self.assertIn('card.label + " does not reduce this fare. Its own price here is "', self.html)'''
NEW_2 = '''        # The card is named by the variable, and the sentence is split across
        # two lines of source with the label at the end of the first, so the
        # test reads the two halves rather than a sentence that no line holds.
        self.assertIn('+ ", and " + card.label +', self.html)
        self.assertIn('" does not reduce it.', self.html)'''

OLD_3 = '''        self.assertIn("does not reduce this fare.", self.html)
        self.assertIn("because the minimum fare the feed applies to this ", self.html)'''
NEW_3 = '''        self.assertIn("does not reduce it.", self.html)
        self.assertIn("because the minimum fare the feed applies to this ", self.html)'''

patch(TARGET, [(OLD_1, NEW_1), (OLD_2, NEW_2), (OLD_3, NEW_3)])
