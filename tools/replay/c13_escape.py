"""C13: Escape stopped closing the picker when the field moved into the heading.

The keydown listener was on the panel, and the field the reader types in is
moved out of that panel and into the heading's own line while the picker is
open. Escape from the field therefore bubbled to the document and never
reached the panel, so the one keyboard exit the page offered did nothing. The
listener is put on the field as well, which is where the key is actually
pressed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = """  originPicker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });"""

NEW = """  // The listener is on the field rather than on the panel, because the field
  // is moved out of the panel and into the heading while the picker is open.
  // A listener on the panel alone meant Escape -- pressed in the field, which
  // is the only place a reader can press it -- bubbled past it and did nothing.
  originSearch.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });
  originPicker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });"""

patch("page_templates.py", [(OLD, NEW)])
