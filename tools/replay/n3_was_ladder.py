"""N3: "£6.60 standard" one step further down the ladder.

The price the card was taken off sits in the Price cell beside the price, and
it was set at .875em -- 14px against the price's 16px. That is the same size
the page already uses for the small notes on a row (`th` is .8rem, a heritage
line is .75rem), so it did not read as the quieter of two numbers; it read as
the same number twice, and the second one was the larger.

`.8em` is 12.8px. It is the rung the page already uses for a count inside a
label, and it is far enough below 16px that the eye takes the cell as one price
with a note under it rather than as two prices.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = """  td.num .was { color: var(--muted); font-size: .875em; }"""

NEW = """  td.num .was { color: var(--muted); font-size: .8em; }"""

if __name__ == "__main__":
    patch("page_templates.py", [(OLD, NEW)])