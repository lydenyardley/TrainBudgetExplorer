"""C11: a layout defect the browser suite found in the new row.

The action column's no-wrap rule was written for the results rows and
   caught the disclosure row too, because a panel is also a last child. The
   panel is prose -- a fare sentence, a condition, a feed record -- and with
   white-space: nowrap inherited its grid could not wrap, so opening a row at
   390px pushed the panel 70px past the edge of the page. The rule now says
   which rows it means: the ones carrying a station.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_CSS = """  /* The action column never wraps its two controls onto two lines, which is
     what used to decide when the table had to stack on a tablet. */
  #rows > tr > td:last-child, thead th:last-child { white-space: nowrap; }"""

NEW_CSS = """  /* The action column never wraps its two controls onto two lines, which is
     what used to decide when the table had to stack on a tablet. Written for
     the results rows by name: the disclosure row is also a last child, and a
     panel is prose, so the no-wrap reached the fare sentence and the feed
     record and pushed the whole panel 70px past a 390px page. */
  #rows > tr[data-crs] > td:last-child, thead th:last-child { white-space: nowrap; }"""

patch("page_templates.py", [(OLD_CSS, NEW_CSS)])
