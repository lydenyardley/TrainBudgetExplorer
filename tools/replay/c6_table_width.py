"""C6: the table is as wide as its content, and the last column is the last column.

The table stretched to the full 78rem column with the station name absorbing
all of it, which put the price 800px from the place it belongs to and left the
ticket action stranded in the middle of a mostly empty page. At content width
the six columns sit together, each number is close to the name above it, and
the whole thing reads as a list rather than a stretched grid.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_TABLE = '''  table { border-collapse: collapse; width: 100%; }'''

NEW_TABLE = '''  /* The table is as wide as its columns need and no wider. Stretched to the
     page's 78rem with the station name absorbing the slack, the price sat
     800px from the place it belongs to and the ticket action floated in the
     middle of an otherwise empty row. At content width the six columns sit
     together, the numbers stay near the names, and the list reads as a list.
     `max-width` keeps a very long station name from pushing the last column
     off a narrow screen; below the phone breakpoint the table stops being a
     table at all. */
  table { border-collapse: collapse; width: auto; max-width: 100%; }'''

OLD_WIDTHS = '''  /* Reading across a row is the whole job, so the columns sit where the eye
     expects them to: the station takes the slack and the numbers keep one
     position each, and the actions stay tight at the end of the row rather
     than being spread to the far edge of a 78rem page. */
  #rows > tr > td:first-child, thead th:first-child { width: 100%; }
  #rows > tr > td:last-child, thead th:last-child { width: 1%; white-space: nowrap; }
'''

NEW_WIDTHS = '''  /* The action column never wraps its two controls onto two lines, which is
     what used to decide when the table had to stack on a tablet. */
  #rows > tr > td:last-child, thead th:last-child { white-space: nowrap; }
'''

OLD_LINK_SUMMARY = '''    document.getElementById("linkTermsSummary").textContent = DATA.tracked && DATA.disclosure
      ? "About the ticket link, and how this site is paid"
      : "About the ticket link, and how this page was built";'''

NEW_LINK_SUMMARY = '''    document.getElementById("linkTermsSummary").textContent = DATA.tracked && DATA.disclosure
      ? "About the ticket link, and how this site is paid"
      : "About the ticket link";'''

OLD_EMPTY = '''  <p id="shortlistEmpty" class="tag">Pick a place above to hold it here while you compare.</p>'''

NEW_EMPTY = '''  <p id="shortlistEmpty" class="tag">Nothing held yet. It is a list to compare and share, not a booking.</p>'''

patch(
    "page_templates.py",
    [
        (OLD_TABLE, NEW_TABLE),
        (OLD_WIDTHS, NEW_WIDTHS),
        (OLD_LINK_SUMMARY, NEW_LINK_SUMMARY),
        (OLD_EMPTY, NEW_EMPTY),
    ],
)
