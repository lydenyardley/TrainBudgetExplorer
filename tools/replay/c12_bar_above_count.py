"""C12: put the shortlist strip above the count line, not between it and the table.

The count line exists to describe the rows under it. With the strip in
between, the count sat 89px above the table with a row of controls in the
gap, and the pair a reader reads together were no longer adjacent. The strip
belongs to the page, not to the count, so it goes above: the reader chooses
places, then reads what the list under them contains.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = """<!-- The count line belongs to the table below it, not to the panel above: on
     the real Grantham page it sat 205px above the first row, with six
     provenance paragraphs between them (finding, 29 September 2026). -->
<p id="summary" role="status" aria-live="polite"></p>
<!-- S26: the shortlist is one control and one strip, above the table and beside
     the count line. It was a named button on every row, so twenty rows carried
     twenty copies of the same word; pressing one changed the button's own text
     and reflowed the table, and the confirmation was a list below the fold the
     reader had to scroll to find. A reader who has just chosen a place is
     looking at the place, not at the foot of the page, so the list is drawn
     where the action is. -->
<section class="shortlist-bar" id="shortlistBar" aria-label="Shortlist" hidden>"""

NEW = """<!-- S26: the shortlist is one control and one strip, above the table. It was a
     named button on every row, so twenty rows carried twenty copies of the
     same word; pressing one changed the button's own text and reflowed the
     table, and the confirmation was a list below the fold the reader had to
     scroll to find. A reader who has just chosen a place is looking at the
     place, not at the foot of the page, so the list is drawn where the action
     is.

     It sits above the count line rather than between the count and the table,
     because the count describes the rows under it and the two were 89px apart
     with a row of controls in the gap. The reader chooses a place, then reads
     what the list beneath them contains. -->
<section class="shortlist-bar" id="shortlistBar" aria-label="Shortlist" hidden>"""

TAIL_OLD = """  <span id="shortlistStatus" role="status" class="sr-only"></span>
</section>
"""

TAIL_NEW = """  <span id="shortlistStatus" role="status" class="sr-only"></span>
</section>
<!-- The count line belongs to the table below it, not to the panel above: on
     the real Grantham page it sat 205px above the first row, with six
     provenance paragraphs between them (finding, 29 September 2026). -->
<p id="summary" role="status" aria-live="polite"></p>
"""

patch("page_templates.py", [(OLD, NEW), (TAIL_OLD, TAIL_NEW)])
