"""The normalisation pass every replay starts from.

A pass that went wrong rewrote 21 unicode escapes as the literal text "\\1".
Rather than hand-repair 21 sites, the file goes back to HEAD and the whole
edit sequence is re-applied by script, which is the same result with the
mistake absent. These four rewrites are what that pass left behind, and they
have to happen before the first patch script reads the file.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# The source wrote the feed's apostrophe as an escaped straight quote inside a
# JavaScript string literal. It renders, but it is the only such escape in the
# file and the ones around it use \\u2019, so it is normalised to match.
APOSTROPHES = (
    ("The feed\\'s", "The feed\\u2019s"),
    ("a seller\\'s", "a seller\\u2019s"),
)


def normalise_page() -> None:
    page = ROOT / "page_templates.py"
    text = page.read_bytes().decode("utf-8").replace("\r\n", "\n")
    for old, new in APOSTROPHES:
        text = text.replace(old, new)
    # Six of these shipped two backslashes where one was meant, so the page
    # rendered the characters \\u00b7 rather than the middle dot, in the
    # shortlist, the copied budget line and the theme toggle. The replacement
    # is a raw string here on purpose: "\\1" in a normal string is not a group
    # reference.
    text, count = re.subn(r"\\\\(u[0-9a-fA-F]{4})", lambda m: "\\" + m.group(1), text)
    print(f"normalised {count} double-escaped unicode sequences")
    page.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
