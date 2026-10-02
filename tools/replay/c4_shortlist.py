"""C4: the shortlist is one control above the table, not a button on every row.

Twenty rows each carried a button that changed its own text when pressed, so
adding a place shifted the whole table sideways and the confirmation -- the
list itself -- was a screen away below the fold. It is now a select beside the
count line, and the places are chips on the same line, so the thing that
changed is the thing that was pressed.
"""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_SECTION = '''<p id="summary" role="status" aria-live="polite"></p>
<table>'''

NEW_SECTION = '''<p id="summary" role="status" aria-live="polite"></p>
<!-- S26: the shortlist is one control and one strip, above the table and beside
     the count line. It was a named button on every row, so twenty rows carried
     twenty copies of the same word; pressing one changed the button's own text
     and reflowed the table, and the confirmation was a list below the fold the
     reader had to scroll to find. A reader who has just chosen a place is
     looking at the place, not at the foot of the page, so the list is drawn
     where the action is. -->
<section class="shortlist-bar" id="shortlistBar" aria-label="Shortlist" hidden>
  <div class="shortlist-controls">
    <label class="shortlist-label" for="shortlistPick">Shortlist</label>
    <select id="shortlistPick"></select>
    <button id="shortlistCopy" class="toggle" type="button" hidden>Copy</button>
    <button id="shortlistClear" class="toggle" type="button" hidden>Clear</button>
  </div>
  <ul id="shortlistList" class="shortlist-chips"></ul>
  <p id="shortlistEmpty" class="tag">Pick a place above to hold it here while you compare.</p>
  <p id="shortlistLimit" class="tag" role="status"></p>
  <details class="shortlist-share" id="shortlistShareBox" hidden>
    <summary>Share this shortlist</summary>
    <p id="shortlistShare" class="tag"></p>
    <textarea id="shortlistBox" class="copybox" rows="6" readonly hidden aria-label="Shortlist to copy"></textarea>
  </details>
  <span id="shortlistStatus" role="status" class="sr-only"></span>
</section>
<table>'''

OLD_TAIL = '''<section id="shortlist" aria-labelledby="shortlistHeading">
  <h2 id="shortlistHeading">Shortlist</h2>
  <p class="tag">Places you are considering from this station. This is a list to compare and share, not a booking: no train is chosen and no ticket is held.</p>
  <p id="shortlistEmpty" class="tag">Nothing shortlisted yet. Use Shortlist on a row to add a place.</p>
  <ul id="shortlistList" hidden></ul>
  <p id="shortlistShare" class="tag"></p>
  <p class="tag"><button id="shortlistCopy" class="toggle" type="button" hidden>Copy the shortlist</button> <button id="shortlistClear" class="toggle" type="button" hidden>Clear the shortlist</button></p>
  <textarea id="shortlistBox" class="copybox" rows="6" readonly hidden aria-label="Shortlist to copy"></textarea>
  <span id="shortlistStatus" role="status" class="sr-only"></span>
</section>
<div id="empty" hidden></div>'''

NEW_TAIL = '''<div id="empty" hidden></div>'''

OLD_ROW_SAVE = '''  // S26: saving a place to compare later. A toggle with its pressed state
  // announced, not a link, because nothing is booked and nothing navigates.
  const save = document.createElement("button");
  save.type = "button";
  save.className = "toggle shortlist-toggle";
  save.setAttribute("aria-pressed", "false");
  save.setAttribute("aria-label", "Shortlist " + destination.name);
  save.addEventListener("click", () => toggleShortlist(destination.crs));
  cell.append(save);
  row.append(cell);
}'''

NEW_ROW_SAVE = '''  row.append(cell);
}'''

OLD_SHORTLIST_RENDER = '''function shortlistRow(destination) {
  const item = document.createElement("li");
  const name = document.createElement("span");
  name.className = "shortlist-name";
  name.textContent = destination.name + " (" + destination.crs + ")";
  const facts = document.createElement("span");
  facts.className = "shortlist-facts";
  const price = money(priceOf(destination));
  const changes = destination.changes === null || destination.changes === undefined
    ? "changes unknown"
    : destination.changes === 0 ? "no change" : destination.changes + " change(s)";
  const time = DATA.hasJourneys
    ? (destination.minutes === null || destination.minutes === undefined
      ? "no service found"
      : duration(destination.minutes))
    : "no timetable in this build";
  facts.textContent = price + (unit() === "party" ? " for the two of us" : " each") + " \\u00b7 " + fareName(destination) + " \\u00b7 " + time + " \\u00b7 " + changes;
  const drop = document.createElement("button");
  drop.type = "button";
  drop.className = "toggle";
  drop.textContent = "Remove";
  drop.setAttribute("aria-label", "Remove " + destination.name + " from the shortlist");
  drop.addEventListener("click", () => toggleShortlist(destination.crs));
  item.append(name, facts, drop);
  return item;
}
function renderShortlist() {
  if (!shortlist) return;
  const kept = shortlisted();
  // A row whose fare the reader can no longer see priced -- a different ticket
  // mode -- leaves the list rather than sitting in it as a name with no price.
  shortlistCodes = kept.map((destination) => destination.crs);
  shortlistList.replaceChildren(...kept.map(shortlistRow));
  const empty = kept.length === 0;
  if (shortlistEmpty) shortlistEmpty.hidden = !empty;
  if (shortlistList) shortlistList.hidden = empty;
  for (const control of [shortlistClear, shortlistCopy]) {
    if (control) control.hidden = empty;
  }
  if (shortlistShare) {
    shortlistShare.textContent = empty
      ? ""
      : "Shortlist of " + kept.length + (kept.length === 1 ? " place" : " places") + " from " +
        DATA.origin.name + ". " + window.location.href;
  }
  if (shortlistBox) shortlistBox.hidden = true;
  if (shortlistStatus && !shortlistStatus.textContent) {
    shortlistStatus.textContent = kept.length ? kept.length + " shortlisted." : "";
  }
  for (const row of document.querySelectorAll("#rows tr[data-crs]")) {
    const button = row.querySelector(".shortlist-toggle");
    if (!button) continue;
    const on = inShortlist(row.dataset.crs);
    button.setAttribute("aria-pressed", String(on));
    button.textContent = on ? "Shortlisted" : "Shortlist";
  }
}'''

NEW_SHORTLIST_RENDER = '''// One place on the strip. The price is the reason the place is there, so it
// travels with the name; the journey facts did too, and made every chip three
// lines tall on a phone, where the strip is the only thing between the reader
// and the fold. The place's own row still has them.
function shortlistRow(destination) {
  const item = document.createElement("li");
  item.className = "shortlist-chip";
  const name = document.createElement("a");
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
  });
  const price = document.createElement("span");
  price.className = "shortlist-price";
  price.textContent = money(priceOf(destination));
  const drop = document.createElement("button");
  drop.type = "button";
  drop.className = "shortlist-drop";
  // A drawn cross, not the letter x and not an emoji: it is the only icon on
  // the page, and it is drawn at the same weight as the rule it sits on.
  drop.innerHTML = '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true" focusable="false">'
    + '<path d="M1 1 L11 11 M11 1 L1 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
  drop.setAttribute("aria-label", "Remove " + destination.name + " from the shortlist");
  drop.addEventListener("click", () => toggleShortlist(destination.crs));
  item.append(name, price, drop);
  return item;
}

function focusDestinationRow(crs) {
  const row = document.querySelector('#rows tr[data-crs="' + crs + '"]');
  if (!row) return;
  row.scrollIntoView({ block: "center", behavior: "smooth" });
  const link = row.querySelector(".buy");
  if (link) link.focus({ preventScroll: true });
}

function renderShortlist() {
  if (!shortlist) return;
  const kept = shortlisted();
  // A row whose fare the reader can no longer see priced -- a different ticket
  // mode -- leaves the list rather than sitting in it as a name with no price.
  shortlistCodes = kept.map((destination) => destination.crs);
  shortlistList.replaceChildren(...kept.map(shortlistRow));
  const empty = kept.length === 0;
  if (shortlistEmpty) shortlistEmpty.hidden = !empty;
  if (shortlistBar) shortlistBar.hidden = false;
  for (const control of [shortlistClear, shortlistCopy, shortlistShareBox]) {
    if (control) control.hidden = empty;
  }
  if (shortlistShare) {
    shortlistShare.textContent = empty
      ? ""
      : "Shortlist of " + kept.length + (kept.length === 1 ? " place" : " places") + " from " +
        DATA.origin.name + ". " + window.location.href;
  }
  if (shortlistBox) shortlistBox.hidden = true;
  if (shortlistStatus && !shortlistStatus.textContent) {
    shortlistStatus.textContent = kept.length ? kept.length + " shortlisted." : "";
  }
  renderShortlistPicker();
}

// The select that replaces twenty buttons. Its options are the destinations on
// the page the reader is looking at, so it is never longer than the list above
// it, and a place already on the strip is not offered again: the list is the
// record of what is held, and a second way to add the same place is a control
// that silently does nothing.
function renderShortlistPicker() {
  if (!shortlistPick) return;
  const onPage = Array.from(document.querySelectorAll("#rows tr[data-crs]"))
    .map((row) => row.dataset.crs)
    .filter((crs) => !inShortlist(crs));
  const wanted = shortlistPick.value;
  shortlistPick.replaceChildren();
  const prompt = document.createElement("option");
  prompt.value = "";
  prompt.textContent = onPage.length ? "Add a place from this page" : "Nothing on this page to add";
  shortlistPick.append(prompt);
  for (const crs of onPage) {
    const row = document.querySelector('#rows tr[data-crs="' + crs + '"]');
    const name = row ? row.querySelector(".station-name") : null;
    const option = document.createElement("option");
    option.value = crs;
    option.textContent = name ? name.textContent : crs;
    shortlistPick.append(option);
  }
  shortlistPick.disabled = onPage.length === 0;
  // Re-rendering the table rebuilds the select, and a reader who had it open
  // has not chosen yet; the placeholder is the honest state to return to.
  shortlistPick.value = wanted && onPage.includes(wanted) ? wanted : "";
}'''

OLD_CONSTS = '''const shortlistList = document.getElementById("shortlistList");'''
NEW_CONSTS = '''const shortlistBar = document.getElementById("shortlistBar");
const shortlistPick = document.getElementById("shortlistPick");
const shortlistShareBox = document.getElementById("shortlistShareBox");
const shortlistLimit = document.getElementById("shortlistLimit");
const shortlistList = document.getElementById("shortlistList");'''

OLD_LIMIT = '''function toggleShortlist(crs) {
  if (inShortlist(crs)) {
    shortlistCodes = shortlistCodes.filter((code) => code !== crs);
  } else {
    if (shortlistCodes.length >= SHORTLIST_LIMIT) {
      // Said rather than silently ignored: a control that stops responding with
      // no explanation is the one thing a reader cannot act on.
      setShortlistStatus("The shortlist holds " + SHORTLIST_LIMIT + " places. Remove one to add another.");
      return;
    }
    shortlistCodes = [...shortlistCodes, crs];
  }
  setShortlistStatus("");
  renderShortlist();
  writeUrl();
}'''

NEW_LIMIT = '''function toggleShortlist(crs) {
  if (inShortlist(crs)) {
    shortlistCodes = shortlistCodes.filter((code) => code !== crs);
    if (shortlistLimit) shortlistLimit.textContent = "";
  } else {
    if (shortlistCodes.length >= SHORTLIST_LIMIT) {
      // Said on the page rather than to a screen reader alone: a control that
      // stops responding with no explanation is the one thing a reader cannot
      // act on, and the strip is where they are already looking.
      const message = "The shortlist holds " + SHORTLIST_LIMIT + " places. Remove one to add another.";
      setShortlistStatus(message);
      if (shortlistLimit) shortlistLimit.textContent = message;
      return;
    }
    shortlistCodes = [...shortlistCodes, crs];
    if (shortlistLimit) shortlistLimit.textContent = "";
  }
  setShortlistStatus("");
  renderShortlist();
  writeUrl();
}'''

OLD_SHORTLIST_CSS = '''  /* S26: the shortlist reads as a list, not a table, because it is a handful of
     places to compare rather than a result set to scan. */
  #shortlist { margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--line); }
  #shortlist h2 { font-size: 1.05rem; margin: 0 0 .25rem; }
  #shortlistList { list-style: none; margin: .5rem 0; padding: 0; }
  #shortlistList li { display: flex; flex-wrap: wrap; align-items: baseline; gap: .25rem .75rem;
                     padding: .4rem 0; border-bottom: 1px solid var(--line); }
  .shortlist-name { font-weight: 600; }
  .shortlist-facts { color: var(--muted); font-variant-numeric: tabular-nums; }
  .empty-actions .toggle { min-height: 44px; }'''

NEW_SHORTLIST_CSS = '''  /* S26: the shortlist is a strip, not a section. It is a handful of places to
     compare rather than a result set to scan, and it sits directly above the
     table so that the place a reader just added appears in the same view as
     the control they added it with. */
  .shortlist-bar { margin: .35rem 0 .5rem; }
  .shortlist-controls { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }
  .shortlist-label { font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
                     color: var(--muted); font-weight: 700; }
  #shortlistPick { width: auto; min-width: 14rem; min-height: 2.75rem; }
  #shortlistPick:disabled { opacity: .6; }
  .shortlist-controls .toggle { margin-left: 0; min-height: 2.75rem; }
  .shortlist-chips { list-style: none; display: flex; flex-wrap: wrap; gap: .4rem;
                     margin: .55rem 0 0; padding: 0; }
  /* A chip is a place and its price with one way out of it. The cross is
     drawn rather than typed: the page has no icon set, and a letter x at this
     size reads as a multiplication sign. */
  .shortlist-chip { display: inline-flex; align-items: center; gap: .45rem;
                    padding: .3rem .3rem .3rem .6rem; border: 1px solid var(--line);
                    border-radius: 2rem; background: var(--field); }
  .shortlist-name { color: var(--accent); text-decoration: none; font-weight: 600; }
  .shortlist-name:hover, .shortlist-name:focus-visible { text-decoration: underline; }
  .shortlist-price { color: var(--muted); font-variant-numeric: tabular-nums; font-size: .85em; }
  .shortlist-drop { display: inline-flex; align-items: center; justify-content: center;
                    width: 1.75rem; height: 1.75rem; padding: 0; border: 0; border-radius: 50%;
                    background: transparent; color: var(--muted); cursor: pointer; }
  .shortlist-drop:hover { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); }
  .shortlist-share { margin-top: .5rem; }
  .shortlist-share summary { min-height: 44px; display: inline-flex; align-items: center;
                             color: var(--accent); cursor: pointer; }
  .empty-actions .toggle { min-height: 44px; }'''

patch(
    "page_templates.py",
    [
        (OLD_SECTION, NEW_SECTION),
        (OLD_TAIL, NEW_TAIL),
        (OLD_ROW_SAVE, NEW_ROW_SAVE),
        (OLD_CONSTS, NEW_CONSTS),
        (OLD_LIMIT, NEW_LIMIT),
        (OLD_SHORTLIST_RENDER, NEW_SHORTLIST_RENDER),
        (OLD_SHORTLIST_CSS, NEW_SHORTLIST_CSS),
    ],
)
