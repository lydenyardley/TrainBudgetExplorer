"""F1: the restriction fixture's records, for the fixture commit.

The synthetic feed now writes one RR record per reviewed card rather than one
pair for a single card, so the count the test asserts is the count the fixture
writes, and the comment says why the count is per card: an RR record is keyed by
the card it governs, and a card with no rule of its own is not discounted at
all. That is how the fixture came to offer one card in a control built to offer
six.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = '        self.assertEqual(self.db.restrictions.record_counts["RR"], 2)'

NEW = (
    "        # One pair of rules per reviewed card, because an RR record is"
    + chr(10)
    + "        # keyed by the card it governs: a card with no rule of its own is"
    + chr(10)
    + "        # not discounted at all, which is how the fixture came to offer"
    + chr(10)
    + "        # one card in a control built to offer six."
    + chr(10)
    + '        self.assertEqual(self.db.restrictions.record_counts["RR"], 12)'
)

patch("tests/test_atoc_fares.py", [(OLD, NEW)])
