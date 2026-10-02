"""C7b: a wrapper for the station slot, so the field is styled as the slot.

The field is appended to whatever element holds the button, which was the h1
itself. A wrapper keeps it inside one inline box with the dashed underline that
says "this part of the sentence is yours", instead of inheriting the heading's
own weight and size by accident.

The selectors are rewritten by counting occurrences rather than by anchoring on
a line, because the same selector appears on three rules of differing length and
an anchor that has to be unique is a rule that has to be written twice.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patch as patcher  # noqa: E402

OLD_CONTROL = """    return (
        '<button id="changeOrigin" class="origin-slot" type="button" aria-expanded="false"'"""
NEW_CONTROL = """    # The wrapper is the slot: it carries the underline and the heading's own
    # weight whether the reader is looking at the station's name or at the field
    # that replaces it, so clicking the name and typing into it are the same
    # gesture in the same place.
    return (
        '<span class="origin-slot-wrap">'
        '<button id="changeOrigin" class="origin-slot" type="button" aria-expanded="false"'"""

OLD_CLOSE = """        f'<span>{name}</span>{CHEVRON}</button>'
    )"""
NEW_CLOSE = """        f'<span>{name}</span>{CHEVRON}</button>'
        '</span>'
    )"""

path = patcher.ROOT / "build_demo_page.py"
text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
for old, new in ((OLD_CONTROL, NEW_CONTROL), (OLD_CLOSE, NEW_CLOSE)):
    if text.count(old) != 1:
        raise SystemExit(f"build_demo_page.py anchor matched {text.count(old)} times")
    text = text.replace(old, new)
path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
print("patched build_demo_page.py (2 replacement(s), CRLF preserved)")

page = patcher.ROOT / "page_templates.py"
body = page.read_bytes().decode("utf-8").replace("\r\n", "\n")
selector = ".origin-slot #originSearch"
count = body.count(selector)
if count != 3:
    raise SystemExit(f"expected 3 originSearch selectors, found {count}")
body = body.replace(selector, ".origin-slot-wrap #originSearch")

for old, new in (
    (".heading-field, .origin-slot {", ".heading-field, .origin-slot-wrap {"),
    (".heading-field:focus-within, .origin-slot:focus-within {",
     ".heading-field:focus-within, .origin-slot-wrap:focus-within {"),
):
    if body.count(old) != 1:
        raise SystemExit(f"selector anchor matched {body.count(old)} times: {old}")
    body = body.replace(old, new)

# The name inside the wrapper is a button, not a slot: the underline belongs to
# the wrapper so that the field which replaces the name keeps the same line.
anchor = "  .heading-field { cursor: text; }"
if body.count(anchor) != 1:
    raise SystemExit("cursor anchor did not match once")
body = body.replace(anchor, anchor + "\n" + "\n".join([
    "  /* The name inside the wrapper is a button, not a slot of its own, so the",
    "     shared rule does not draw a second underline under it. */",
    "  .origin-slot-wrap .origin-slot { display: inline-flex; align-items: baseline;",
    "                                   color: inherit; border-bottom: 0; padding: 0; }",
]))
page.write_bytes(body.replace("\n", "\r\n").encode("utf-8"))
print("patched page_templates.py (6 replacement(s), CRLF preserved)")
