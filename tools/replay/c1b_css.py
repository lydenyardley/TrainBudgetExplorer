"""C1b: the table's own rules -- hover, column widths, and the new cell parts.

The old rules styled a fare code and a condition flag, both of which the
column no longer shows. This replaces them with what the row is made of now:
a name and its code, a change count and the station it changes at, and one
word for the fare type.
"""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = '''  /* The fare's own code, where the sentence used to be repeated on every row,
     and one word beside it when the fare is one a reader should open. The
     condition itself is in the row's disclosure; a reader who never opens it
     still has to know there is one to read, so the word is the signal and the
     colour is only the second cue. */
  .ticket-code { font-variant-numeric: tabular-nums; letter-spacing: .02em; white-space: nowrap; }
  .condition-flag { color: var(--warn); font-size: .85em; white-space: nowrap; }
  /* No row is highlighted. The top row was tinted as the "best" fare, which on
     a page that refuses to imply a recommendation is a recommendation stated by
     a colour and never by a word (finding, 29 September 2026). The order the
     tint stood for is in the count line above the table, in words (ADR-0041). */
'''

NEW = '''  /* The destination and its three-letter code, which a seller asks for. The
     name carries the weight and the code recedes, because the code identifies
     the place to a booking system and says nothing to a reader. */
  .station-name { font-weight: 600; }
  .station-code { color: var(--muted); font-variant-numeric: tabular-nums; }
  /* The change count, and under it the station the journey changes at. Q2
     (ADR-0045) put the station in a disclosure on every row, which is a click
     per row to learn the one fact in the row worth acting on. */
  .changes-count { display: block; }
  .interchange { display: block; color: var(--muted); font-size: .82em; font-weight: 400; }
  /* The fare in three words. Two of the three are a warning, so they are the
     accent and the warning colour respectively, and the common case -- an
     ordinary fare -- stays in the page's own voice rather than being tinted to
     draw attention to nothing. The feed's code is in the row's own record. */
  .fare-kind { white-space: nowrap; }
  .fare-type[data-kind="advance"] .fare-kind { color: var(--warn); }
  .fare-type[data-kind="restricted"] .fare-kind { color: var(--warn); }
  .fare-type[data-kind="regular"] .fare-kind { color: var(--muted); }
  /* No row is highlighted for rank. The top row was tinted as the "best" fare,
     which on a page that refuses to imply a recommendation is a recommendation
     stated by a colour and never by a word (finding, 29 September 2026). The
     order the tint stood for is in the count line above the table, in words
     (ADR-0041).

     A row IS tinted under the pointer, and that is a different promise: it
     answers "which line am I reading", which is the one question a table of
     six columns asks and the one the eye cannot otherwise answer when the
     numbers run down the page. It is the field colour, not the accent, so it
     never reads as "this is the best fare", and it is skipped on touch, where
     there is no pointer to hover and the tint would stick. */
  @media (hover: hover) {
    #rows > tr[data-crs]:hover > td { background: var(--field); }
    #rows > tr[data-crs]:hover > td:first-child { border-radius: .3rem 0 0 .3rem; }
    #rows > tr[data-crs]:hover > td:last-child { border-radius: 0 .3rem .3rem 0; }
  }
  /* Reading across a row is the whole job, so the columns sit where the eye
     expects them to: the station takes the slack and the numbers keep one
     position each, and the actions stay tight at the end of the row rather
     than being spread to the far edge of a 78rem page. */
  #rows > tr > td:first-child, thead th:first-child { width: 100%; }
  #rows > tr > td:last-child, thead th:last-child { width: 1%; white-space: nowrap; }
  /* The two halves of one fact, stacked, never side by side: a change count
     with a station after it on the same line reads as two columns. */
  td.num .was { display: block; }
'''

OLD_MOBILE = '''    td:first-child { flex: 1 1 100%; padding-left: 0; font-weight: 600; }
    td.num { text-align: left; }
    td:last-child { margin-left: auto; }'''

NEW_MOBILE = '''    td:first-child { flex: 1 1 100%; padding-left: 0; }
    td.num { text-align: left; }
    /* On a phone the numbers and the fare type share the line under the
       destination, and the actions take the line below them: `margin-left:
       auto` pushed them to the right edge, which is where the thumb is, and
       where a stray tap buys a ticket. */
    td:last-child { margin-left: 0; }'''

patch(
    "page_templates.py",
    [
        (OLD, NEW),
        (OLD_MOBILE, NEW_MOBILE),
        (
            '  h1 { font-size: var(--h1); line-height: 1.2; letter-spacing: -.025em; font-weight: 700;\n'
            "       text-wrap: balance; }",
            "  h1 { font-size: var(--h1); line-height: 1.06; letter-spacing: -.03em; font-weight: 700;\n"
            "       text-wrap: balance; }",
        ),
        (
            "--h1: clamp(2rem, 6vw, 6rem);",
            "--h1: clamp(2rem, 7vw, 7rem);",
        ),
    ],
)
