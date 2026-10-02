"""C4b: wire the select, and point the guard at the bar that replaced the section."""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = '''const shortlist = document.getElementById("shortlist");
const shortlistBar = document.getElementById("shortlistBar");'''

NEW = '''const shortlistBar = document.getElementById("shortlistBar");
// The one element whose presence means this page has a shortlist at all. It
// was the section below the table; it is the strip above it, and every
// function that guarded on the old id was quietly doing nothing on a page
// without one.
const shortlist = shortlistBar;'''

OLD_CLEAR = '''if (shortlistClear) {'''

NEW_CLEAR = '''// The select is the way in. It is a change rather than a click because a
// <select> has no click to hang a handler on that means anything, and because
// the browser's own list is the control: one tap to open, one to choose, and
// the choice is made in the same gesture the reader used to look at the page.
if (shortlistPick) {
  shortlistPick.addEventListener("change", () => {
    const crs = shortlistPick.value;
    if (!crs || inShortlist(crs)) return;
    toggleShortlist(crs);
    // Focus goes back to the control rather than staying on an option that no
    // longer exists: renderShortlist() rebuilds the option list, and a select
    // left with no matching option drops to its placeholder silently.
    shortlistPick.focus({ preventScroll: true });
  });
}
if (shortlistClear) {'''

patch("page_templates.py", [(OLD, NEW), (OLD_CLEAR, NEW_CLEAR)])
