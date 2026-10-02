"""C7: the station name is a field you type into, in the sentence it belongs to.

The heading's station slot opened a search box in a panel of its own, further
down the page: the reader clicked a word in a sentence and was moved somewhere
else to type, and the sentence they were reading changed shape while they did
it. The field now takes the name's place. The word "station" is the muted
placeholder, so the caret sits exactly where GRANTHAM was and the reader's own
answer takes the accent the name had.

The panel below the heading still holds the list, because a list of 2,718
stations in the middle of a heading would break it, and because the list is
real links: choosing a station is navigation (ADR-0019), and a link is the only
control assistive technology already announces correctly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_MARKUP = '''<div id="originPicker" hidden>
  <label class="origin-picker-label" for="originSearch">Start from a different station</label>
  <input id="originSearch" type="search" placeholder="Type part of a name or its three-letter code" autocomplete="off"
         aria-describedby="originStatus" aria-controls="originPicks">
  <span id="originStatus" class="sr-only" role="status"></span>
  <ul id="originPicks"></ul>
  <p id="originNomatch" hidden></p>
</div>'''

NEW_MARKUP = '''<!-- The list, not the field. The field is moved into the heading by the
     script, into the place the station's own name was, so that clicking the
     name and typing are the same gesture in the same place. -->
<div id="originPicker" hidden>
  <p class="origin-picker-label" id="originPicksLabel">Every station on this site</p>
  <ul id="originPicks" aria-labelledby="originPicksLabel"></ul>
  <p id="originNomatch" hidden></p>
  <span id="originStatus" class="sr-only" role="status"></span>
</div>'''

OLD_SET_PICKER = '''  function setPicker(open) {
    changeOrigin.setAttribute("aria-expanded", String(open));
    originPicker.hidden = !open;
    if (open) {
      renderPicks();
      originSearch.focus();
    } else {
      // Escape is a keyboard exit, and focus returns to the control that
      // opened the picker rather than dropping to the top of the page.
      changeOrigin.focus();
    }
  }'''

NEW_SET_PICKER = '''  // The field is moved into the slot rather than duplicated, so there is one
  // input in the document and the heading's own accessible name is the one
  // that gets typed into. Moving it back on close keeps the DOM where the
  // script that reads it expects it after a navigation.
  function setPicker(open) {
    changeOrigin.setAttribute("aria-expanded", String(open));
    originPicker.hidden = !open;
    if (open) {
      if (originSearch.parentElement !== originSlot) originSlot.append(originSearch);
      changeOrigin.hidden = true;
      renderPicks();
      // The field is sized to its placeholder, so it is as wide as the word
      // "station" and no wider until something is typed into it.
      originSearch.focus();
      originSearch.select();
    } else {
      changeOrigin.hidden = false;
      if (originSearch.parentElement !== originPicker) originSearch.remove();
      // Escape is a keyboard exit, and focus returns to the control that
      // opened the picker rather than dropping to the top of the page.
      changeOrigin.focus();
    }
  }'''

OLD_CONST = '''const originPicker = document.getElementById("originPicker");
if (changeOrigin && DATA.stations && DATA.stations.length) {
  const originSearch = document.getElementById("originSearch");'''

NEW_CONST = '''const originPicker = document.getElementById("originPicker");
if (changeOrigin && DATA.stations && DATA.stations.length) {
  // The field the page's own script created, read here rather than from the
  // document: it is moved into the heading when the picker opens, and the
  // markup no longer holds it.
  const originSearch = document.createElement("input");
  originSearch.id = "originSearch";
  originSearch.type = "search";
  originSearch.placeholder = "station";
  originSearch.autocomplete = "off";
  originSearch.setAttribute("aria-describedby", "originStatus");
  originSearch.setAttribute("aria-controls", "originPicks");
  originSearch.setAttribute("aria-label", "Start from a different station");
  const originSlot = changeOrigin.parentElement;'''

OLD_CSS = '''  #originPicker { margin: .75rem 0 1rem; }
  .origin-picker-label { display: block; margin-bottom: .35rem; font-size: .8rem;
                         text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
  #originPicker input[type=search] { width: 100%; max-width: 24rem; padding: .5rem; border: 1px solid var(--line);
                                     border-radius: .35rem; font: inherit; color: var(--fg); background: var(--field); }
  #originPicks { list-style: none; margin: .5rem 0 0; padding: 0; max-width: 24rem; }
  #originPicks a { display: flex; justify-content: space-between; gap: .75rem; min-height: 44px; padding: .55rem .4rem;
                   color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--line); }
  #originPicks a:hover, #originPicks a:focus-visible { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  #originPicks .code { color: var(--muted); }
  #originNomatch { color: var(--muted); margin-top: .5rem; }'''

NEW_CSS = '''  /* The list, opened directly under the heading it replaces. It is as wide as
     the heading's own measure and no wider: it is a list of names and codes,
     and a column of links 24rem wide in a 78rem page reads as a sidebar. */
  #originPicker { margin: .4rem 0 1rem; max-width: 34rem; }
  .origin-picker-label { margin: 0 0 .3rem; font-size: .72rem;
                         text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 700; }
  #originPicks { list-style: none; margin: 0; padding: 0; max-height: 60vh; overflow-y: auto;
                 border-top: 1px solid var(--line); }
  #originPicks a { display: flex; justify-content: space-between; gap: .75rem; min-height: 44px;
                   padding: .55rem .4rem; align-items: baseline;
                   color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--line); }
  #originPicks a:hover, #originPicks a:focus-visible { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  #originPicks .code { color: var(--muted); font-variant-numeric: tabular-nums; }
  #originNomatch { color: var(--muted); margin: .5rem 0 0; }'''

OLD_NOTE = '''  const note = document.createElement("p");
  note.className = "card-note";
  if (noCard() || !railcards[railcardSelect.value]) {
    note.dataset.state = "none";
    note.textContent =
      "No railcard is selected, so this fare is shown at its standard price. Choose the card " +
      "you hold above and every destination is priced against that card\\u2019s own rules.";
    return note;
  }'''

NEW_NOTE = '''  // With no card chosen there is nothing to explain: the row is priced at the
  // standard fare, the price cell says so by not saying otherwise, and the
  // control above already reads "No railcard selected, so these are standard
  // fares". A paragraph on every expanded row repeating the page's default is
  // the noise this replaced.
  if (noCard() || !railcards[railcardSelect.value]) return null;
  const note = document.createElement("p");
  note.className = "card-note";'''

patch(
    "page_templates.py",
    [
        (OLD_MARKUP, NEW_MARKUP),
        (OLD_CONST, NEW_CONST),
        (OLD_SET_PICKER, NEW_SET_PICKER),
        (OLD_CSS, NEW_CSS),
        (OLD_NOTE, NEW_NOTE),
    ],
)
