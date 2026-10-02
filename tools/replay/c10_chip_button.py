"""C10: the chip is a button, not a javascript: link.

A chip that scrolls back to its row is a control that does not navigate, and a
`javascript:` URL is the way to say that in a way that breaks under a content
security policy and shows up in a link list. It is a button, it says so, and
it moves focus rather than pretending to be a destination.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD = '''  const name = document.createElement("a");
  name.className = "shortlist-name";
  name.href = "#";
  name.textContent = destination.name;
  // A chip is a shortcut back to the row it came from. The row carries an id
  // the page sets as it renders, so the link lands on the place rather than
  // scrolling the reader nowhere.
  name.href = "javascript:void 0";
  name.addEventListener("click", (event) => {
    event.preventDefault();
    focusDestinationRow(destination.crs);
  });'''

NEW = '''  // A chip is a way back to the row it came from, and a row is not a
  // destination, so it is a button: a link here would be either a fragment
  // that goes nowhere or a javascript: URL, and both are worse than saying
  // what the control does.
  const name = document.createElement("button");
  name.type = "button";
  name.className = "shortlist-name";
  name.textContent = destination.name;
  name.title = "Show " + destination.name + " in the list above";
  name.addEventListener("click", () => focusDestinationRow(destination.crs));'''

patch("page_templates.py", [(OLD, NEW)])

CSS_OLD = '''  .shortlist-name { color: var(--accent); text-decoration: none; font-weight: 600; }
  .shortlist-name:hover, .shortlist-name:focus-visible { text-decoration: underline; }'''

CSS_NEW = '''  .shortlist-name { padding: 0; border: 0; background: transparent; color: var(--accent);
                    font: inherit; font-weight: 600; cursor: pointer; }
  .shortlist-name:hover { text-decoration: underline; }'''

patch("page_templates.py", [(CSS_OLD, CSS_NEW)])
