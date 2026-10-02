"""C9: the synthetic feed prices all six reviewed cards, not one.

The demo feed carried a railcard record for "TWO TOGETHER RAILCARD", a code
that is not in the reviewed public set, so the page's collection came out with
exactly one member and the control the collection was built for looked like a
select with a single option. The real feed prices all six (measured 1 October
2026: YNG 1-8 adults, DIS 1-2, NEW 1-4, SRN 1-8, BB2 1-1, 2TR 2-2). The
fixture now carries the same six, with the same party bounds, so the demo
exercises the party filter, the memory and the minimum-fare branch rather than
skipping all three.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_CARDS = '''RAILCARDS = (
    ("TWO", "TWO TOGETHER RAILCARD", "2", "2"),
    ("YNG", "16-25 RAILCARD", "1", "1"),
)'''

NEW_CARDS = '''# The six reviewed public railcards, with the party each one prices, measured
# against the real feed on 1 October 2026. The fixture used to carry a single
# card, under a code that is not in the reviewed set at all, so a page built
# from it offered a select with one option in it -- the control that exists to
# offer six. Bounds are the card's own, so the party filter has something to
# take out: Two Together cannot price one traveller, and the Student Discount
# Card cannot price two.
RAILCARDS = (
    ("YNG", "16-25 RAILCARD", "1", "8"),
    ("DIS", "DISABLED PERSONS RAILCARD", "1", "2"),
    ("NEW", "NETWORK RAILCARD", "1", "4"),
    ("SRN", "SENIOR RAILCARD", "1", "8"),
    ("BB2", "STUDENT DISCOUNT CARD", "1", "1"),
    ("2TR", "TWO TOGETHER RAILCARD", "2", "2"),
)'''

OLD_RULES = '''        _line(
            {
                "update_marker": "R",
                "record_type": "RR",
                "cf_marker": "C",
                "railcard_code": "YNG",
                "sequence_no": "0001",
                "ticket_code": "CDR",
                "route_code": "00000",
                "location": "",
                "restriction_code": "",
                "total_ban": "Y",
            },
            RESTRICTION_LAYOUTS["RR"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "RR",
                "cf_marker": "C",
                "railcard_code": "YNG",
                "sequence_no": "0002",
                "ticket_code": "",
                "route_code": "",
                "location": "",
                "restriction_code": "R9",
                "total_ban": "",
            },
            RESTRICTION_LAYOUTS["RR"],
        ),'''

NEW_RULES = '''        # One pair of rules per card, because an RR record is keyed by the card
        # it governs: a card with no rule of its own is not discounted at all,
        # which is how the fixture came to offer one card rather than six. The
        # pair is the same for each, and is the one shape worth exercising -- a
        # total ban on one ticket, and a travel condition on everything else.
        *[
            _line(
                {
                    "update_marker": "R",
                    "record_type": "RR",
                    "cf_marker": "C",
                    "railcard_code": card[0],
                    "sequence_no": "0001",
                    "ticket_code": "CDR",
                    "route_code": "00000",
                    "location": "",
                    "restriction_code": "",
                    "total_ban": "Y",
                },
                RESTRICTION_LAYOUTS["RR"],
            )
            for card in RAILCARDS
        ],
        *[
            _line(
                {
                    "update_marker": "R",
                    "record_type": "RR",
                    "cf_marker": "C",
                    "railcard_code": card[0],
                    "sequence_no": "0002",
                    "ticket_code": "",
                    "route_code": "",
                    "location": "",
                    "restriction_code": "R9",
                    "total_ban": "",
                },
                RESTRICTION_LAYOUTS["RR"],
            )
            for card in RAILCARDS
        ],'''

patch(
    "make_synthetic_feed.py",
    [
        (OLD_CARDS, NEW_CARDS),
        (OLD_RULES, NEW_RULES),
    ],
)
