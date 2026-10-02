"""C7c: the list opens under the heading, not under the page's own opening line.

The panel was written after the intro paragraph, so clicking the station name
in the heading opened a list two paragraphs further down -- the reader's eye
stayed on the word they had just clicked and found nothing there.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_PANEL = '''<!-- ADR-0047: shown only when the stylesheet did not arrive. The page is
     plain text in that state, and says so rather than leaving a reader to
     wonder why this station looks unlike every other one. -->
<p class="sub" id="styleNote" hidden></p>
<p id="unpriced" class="unpriced" hidden></p>

<!-- The list, not the field. The field is moved into the heading by the
     script, into the place the station's own name was, so that clicking the
     name and typing are the same gesture in the same place. -->
<div id="originPicker" hidden>
  <p class="origin-picker-label" id="originPicksLabel">Every station on this site</p>
  <ul id="originPicks" aria-labelledby="originPicksLabel"></ul>
  <p id="originNomatch" hidden></p>
  <span id="originStatus" class="sr-only" role="status"></span>
</div>
'''

NEW_PANEL = '''<!-- The list, not the field. The field is moved into the heading by the
     script, into the place the station's own name was, so that clicking the
     name and typing are the same gesture in the same place -- and the list
     opens directly under it, because a reader who has just clicked a word
     looks at that word and not two paragraphs further down. -->
<div id="originPicker" hidden>
  <p class="origin-picker-label" id="originPicksLabel">Every station on this site</p>
  <ul id="originPicks" aria-labelledby="originPicksLabel"></ul>
  <p id="originNomatch" hidden></p>
  <span id="originStatus" class="sr-only" role="status"></span>
</div>
<!-- ADR-0047: shown only when the stylesheet did not arrive. The page is
     plain text in that state, and says so rather than leaving a reader to
     wonder why this station looks unlike every other one. -->
<p class="sub" id="styleNote" hidden></p>
<p id="unpriced" class="unpriced" hidden></p>
'''

patch("page_templates.py", [(OLD_PANEL, NEW_PANEL)])
