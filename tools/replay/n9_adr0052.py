"""N9: register this pass in the replay driver, and correct ADR-0052.

`replay.py` is the record of edit order. A patch script that is not named there
is not part of the session's history, however good it is.

ADR-0052 said a card that cannot cover the party on screen is *removed* from
the selector. That is no longer what the page does, and the reason is worth
keeping: Two Together's bounds are 2 to 2, the default page shows one adult, so
removal took out the one real card a reader holding one would go looking for,
and its absence read as "this page does not price Two Together".

The amendment keeps the decision's actual purpose. Removal was a way of never
showing a price nobody could buy, and a disabled option does that at least as
strictly -- a disabled option cannot hold a value, so nothing downstream can
read one. What removal also did, and was not asked to do, was hide a card the
build prices.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD_REPLAY = '''"t5_tests.py", "t6_worker_tests.py"):'''

NEW_REPLAY = '''"t5_tests.py", "t6_worker_tests.py",
                # This pass: the five defects found by looking at a page.
                # n1 narrow rows, n2 the railcard list, n3 the price note,
                # n4 the journey facts, n5 the chip count, n6/n7/n8 their
                # checks, n9 this registration.
                "n1_narrow_rows.py", "n2_railcard_cards.py", "n3_was_ladder.py",
                "n4_journey_facts.py", "n5_chip_space.py", "n6_tests.py",
                "n7_browser.py", "n8_railcard_checks.py"):'''

OLD_ADR = """**A card that cannot cover the party on screen is removed from the list**, rather
than left there to be picked and then ignored. The bounds are the feed's own
records for that card. Two Together is two adults, the 16-25 is one to eight,
the Student card is one."""

NEW_ADR = """**A card that cannot cover the party on screen cannot be chosen**, rather than
left there to be picked and then ignored. The bounds are the feed's own records
for that card. Two Together is two adults, the 16-25 is one to eight, the
Student card is one.

*Amended 2 October 2026.* This originally read "is removed from the list", and
removal turned out to cost more than it bought. Two Together's bounds are 2 to
2 and the default page shows one adult, so it was the one card the selector
lost on every page a reader opened by default, and its absence read as "this
page does not price Two Together" rather than "not for the party you have on
screen". Every card the build prices is now listed, and one that cannot cover
the party on screen is struck out of choosing with the reason in its own label.

The guarantee this record was protecting is unchanged and, if anything,
tighter. Removal existed so the page would never show a price nobody could
buy, and a disabled `<option>` prevents that at least as strictly as removing
the option does: a disabled option cannot hold a value, so `priceOf` and
`cardFor` cannot read one. What removal also did, and was never asked to do,
was hide a card the feed prices."""

if __name__ == "__main__":
    patch("tools/replay/replay.py", [(OLD_REPLAY, NEW_REPLAY)])
    patch("adr/ADR-0052-the-railcard-is-one-of-a-collection.md", [(OLD_ADR, NEW_ADR)])