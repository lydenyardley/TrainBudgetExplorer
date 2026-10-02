"""N5: a space between a destination type and its count.

The markup has always had one -- `<span>Small towns</span> <span
class="chipcount">(0)</span>` -- and it never reached the screen, because
`.choice-chip` is an inline-flex box and a flex container drops the
whitespace-only text nodes between its items. The rendered chip read
"Small towns(0)".

The space is a margin on the count rather than a character in the label. Putting
it in the text would put it in the accessible name, where "Small towns (0)" and
"Small towns(0)" are the same string and the space is noise a screen reader
reads as a pause. The margin is the visual gap and nothing else.

`gap` on the chip would have done the same job, but the chip also holds the
radio input and its label span, and a gap would space those too.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = """  .chipcount { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .8em; }"""

NEW = """  .chipcount { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .8em;
               margin-left: .35rem; }"""

if __name__ == "__main__":
    patch("page_templates.py", [(OLD, NEW)])