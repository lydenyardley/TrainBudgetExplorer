"""T5: two comments in the tests that had fallen behind the page.

Both describe the fare-type column: one still said the code was back on the
row, and the other said "Fare code" was the right header. ADR-0053 settled what
that column is, and a test comment is the one place a reader looks to find out
what a change meant.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_LABEL = '''        self.assertIn("cell.dataset.label =", self.html)
        self.assertIn('cell.dataset.label = "Fare type"', self.html)
        # The column is the fare in three words. SDR, 2AS and BPS are a
        # seller's vocabulary and they were the column, on every row, in
        # front of the one number the reader came for; the code is in the
        # row's own record. The label is what the phone reflow reads out.'''

NEW_LABEL = '''        self.assertIn("cell.dataset.label =", self.html)
        # The column is the fare in three words. SDR, 2AS and BPS are a
        # seller's vocabulary and they were the column, on every row, in
        # front of the one number the reader came for; the code is in the
        # row's own record (ADR-0053). The label is what the phone reflow
        # reads out.'''

OLD_HEADER = '''        # "Ticket" and "Tickets" as adjacent headers read as one column twice,
        # and "Fare code" was rejected while that column read in sentences. The
        # column holds the feed's own code again, so the name is right again:
        # it is the fare's code, not a second ticket action beside the Tickets
        # column (finding, 29 September 2026).'''

NEW_HEADER = '''        # "Ticket" and "Tickets" as adjacent headers read as one column twice,
        # and "Fare code" was rejected while that column read in sentences. The
        # column is now the fare in the reader's own three words and the code
        # is in the row's disclosure (ADR-0053), so the header names what the
        # cells hold rather than what the feed calls them.'''

patch("tests/test_build_demo_page.py", [(OLD_LABEL, NEW_LABEL), (OLD_HEADER, NEW_HEADER)])
