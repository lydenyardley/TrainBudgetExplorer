// The shortlist and the dock.

// S26: a shortlist of candidate places, and nothing that looks like a
// booking. The list lives in the address like the rest of the search state, so
// it survives a refresh and can be handed to somebody else as a link; what it
// shows is the price currently on screen, because a comparison of a different
// price than the one beside each row would be a comparison of nothing.
const SHORTLIST_LIMIT = 8;
// Read from the address on load and written back on every change, like the rest
// of the search state: a shortlist that only lives in one tab is not a
// shortlist anybody can hand to somebody else.
const shortlistDock = document.getElementById("shortlistDock");
// The one element whose presence means this page has a shortlist at all. It
// was the section between the count and the table; it is the strip at the foot
// of the screen, and every function that guarded on the old id was quietly
// doing nothing on a page without one.
const shortlist = shortlistDock;
const shortlistShareBox = document.getElementById("shortlistShareBox");
const shortlistLimit = document.getElementById("shortlistLimit");
const shortlistStatus = document.getElementById("shortlistStatus");
const shortlistShare = document.getElementById("shortlistShare");
const shortlistCopy = document.getElementById("shortlistCopy");
const shortlistBox = document.getElementById("shortlistBox");
const shortlistDockList = document.getElementById("shortlistDockList");
const shortlistDockCount = document.getElementById("shortlistDockCount");
const shortlistDockClear = document.getElementById("shortlistDockClear");

function shortlisted() {
  const wanted = new Set(STATE.shortlist);
  // In the page's own order, and only rows this ticket mode actually carries:
  // a shortlist that named a destination the reader cannot see priced would be
  // a list of places they cannot buy.
  return activeDestinations().filter((destination) => wanted.has(destination.crs));
}
function inShortlist(crs) {
  return STATE.shortlist.includes(crs);
}
function toggleShortlist(crs) {
  const added = !inShortlist(crs);
  if (!added) {
    STATE.shortlist = STATE.shortlist.filter((code) => code !== crs);
    if (shortlistLimit) shortlistLimit.textContent = "";
  } else {
    if (STATE.shortlist.length >= SHORTLIST_LIMIT) {
      // Said on the page rather than to a screen reader alone: a control that
      // stops responding with no explanation is the one thing a reader cannot
      // act on, and the strip is where they are already looking.
      const message = "The shortlist holds " + SHORTLIST_LIMIT + " destinations. Remove one to add another.";
      setShortlistStatus(message);
      if (shortlistLimit) shortlistLimit.textContent = message;
      return;
    }
    STATE.shortlist = [...STATE.shortlist, crs];
    if (shortlistLimit) shortlistLimit.textContent = "";
  }
  announceShortlist(crs, added);
  renderShortlist();
  writeUrl();
}
// The live region says what changed, not how many there are: the dock's own
// header already carries the count, and the two said the same thing in two
// words (audit item 35).
function announceShortlist(crs, added) {
  const destination = activeDestinations().find((place) => place.crs === crs);
  // A name is always found -- every caller is a row or a dock row of this list
  // -- but the sentence has to read if one is not, rather than saying "Removed
  // from the shortlist." with the place left out.
  const name = destination ? destination.name : "that destination";
  setShortlistStatus(added
    ? "Added " + name + " to the shortlist."
    : "Removed " + name + " from the shortlist.");
}
function setShortlistStatus(text) {
  if (shortlistStatus) shortlistStatus.textContent = text;
}
// One place on the strip. The price is the reason the place is there, so it
// travels with the name; the journey facts did too, and made every chip three
// lines tall on a phone, where the strip is the only thing between the reader
// and the fold. The place's own row still has them.
// The remove control, built once. Two renderings of the shortlist exist --
// the strip above the table and the dock at the foot of the screen -- and a
// cross drawn twice is a cross that will one day mean two things.
function dropButton(destination) {
  const drop = document.createElement("button");
  drop.type = "button";
  drop.className = "shortlist-drop";
  // A drawn cross, not the letter x and not an emoji: it is the only icon on
  // the page, and it is drawn at the same weight as the rule it sits on.
  drop.innerHTML = '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true" focusable="false">'
    + '<path d="M1 1 L11 11 M11 1 L1 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
  drop.setAttribute("aria-label", "Remove " + destination.name + " from the shortlist");
  drop.addEventListener("click", () => toggleShortlist(destination.crs));
  return drop;
}

// One shortlisted place as a row of the dock's table: the four facts the reader
// is comparing, read through the same helpers the results table reads, so a
// place cannot show one duration in the table and another in the dock. A
// journey this build could not find says so here rather than showing a zero
// (journeyCell, same rule).
function dockRow(destination) {
  const journey = journeyFor(destination);
  const missing = !journey.found;
  const row = document.createElement("tr");
  row.dataset.crs = destination.crs;
  const name = document.createElement("td");
  const label = document.createElement("button");
  label.type = "button";
  label.className = "shortlist-dock-name";
  label.textContent = destination.name;
  label.title = "Show " + destination.name + " in the list above";
  label.addEventListener("click", () => focusDestinationRow(destination.crs));
  name.append(label);
  const price = document.createElement("td");
  price.className = "num";
  price.textContent = money(priceOf(destination));
  const time = document.createElement("td");
  time.className = missing ? "num missing" : "num";
  time.textContent = missing ? dayAbsenceText(destination, true) : duration(journey.minutes);
  const changes = document.createElement("td");
  changes.className = missing ? "num missing" : "num";
  changes.textContent = missing ? "Unknown" : changeCount(journey.changes);
  const drop = document.createElement("td");
  drop.className = "dock-drop-cell";
  drop.append(dropButton(destination));
  // A prices-only build stands its Time and Changes headings down, so the row
  // leaves those cells out too. Rendering five cells under three headings is a
  // table whose columns are not the columns it says they are, and the remove
  // button ends up under no heading at all.
  if (DATA.hasJourneys) row.append(name, price, time, changes, drop);
  else row.append(name, price, drop);
  return row;
}

// The dock is fixed to the foot of the screen, so the page has to end above
// it. The height is read back from the rendered dock rather than guessed,
// because the height depends on how many places are shortlisted, on the
// width, and on which theme is on.
function padForDock() {
  // Guarded like the rest of the shortlist, because the resize listener below
  // runs on any page this script reaches and a page with no dock has no dock
  // to measure.
  if (!shortlistDock) return;
  document.body.style.paddingBottom = shortlistDock.hidden
    ? ""
    : (shortlistDock.offsetHeight + 16) + "px";
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
  STATE.shortlist = kept.map((destination) => destination.crs);
  // Every row's tick is this list, drawn on the row. Anything that empties the
  // shortlist takes the ticks with it: the Clear above the table, the Clear in
  // the dock, and a place leaving the ticket mode the reader is looking at.
  // Without this the page showed two places held and a list of none, and the
  // reader had to tick the boxes off by hand to believe the page.
  for (const box of document.querySelectorAll("#rows input.hold-box")) {
    const row = box.closest("tr[data-crs]");
    if (row) box.checked = inShortlist(row.dataset.crs);
  }
  // The dock appears on the first place shortlisted and leaves with the last,
  // because a strip holding nothing is a bar across the bottom of the screen
  // for no reason a reader can see.
  if (shortlistDock) {
    shortlistDock.hidden = kept.length === 0;
    shortlistDockList.replaceChildren(...kept.map(dockRow));
    if (shortlistDockCount) {
      shortlistDockCount.textContent = kept.length + (kept.length === 1 ? " destination" : " destinations");
    }
    padForDock();
  }
  const empty = kept.length === 0;
  for (const control of [shortlistCopy, shortlistShareBox]) {
    if (control) control.hidden = empty;
  }
  if (shortlistShare) {
    // The address carries the search, and saying so beside it is the point:
    // the privacy page's claim and the share control were never in the same
    // place. It is a real link, so a reader can open or copy it in one action
    // (audit item 36).
    shortlistShare.replaceChildren();
    if (!empty) {
      // The card is a key in the address only when one is chosen (stateQuery),
      // so the list of what the link carries is built from that rather than
      // naming a railcard a reader without one did not send.
      const carried = "budget, ticket type, party size" + (noCard() ? "" : ", railcard") +
        " and shortlist";
      shortlistShare.append(
        "Shortlist of " + kept.length + (kept.length === 1 ? " destination" : " destinations") + " from " +
        DATA.origin.name + ". This link carries your " + carried + " to whoever opens it: ");
      const link = document.createElement("a");
      link.href = window.location.href;
      link.textContent = window.location.href;
      shortlistShare.append(link, ".");
    }
  }
  if (shortlistBox) {
    shortlistBox.hidden = true;
    if (shortlistShareBox) shortlistShareBox.open = false;
  }
}

function shortlistText() {
  const kept = shortlisted();
  const what = unit() === "party" ? "for the two of us" : "per adult";
  // The budget the page is searching with, which is the state's own figure: the
  // copied list used to read the field that displays it (R4).
  const lines = [
    "Shortlist from " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    "Budget: £" + STATE.budget + " " + what,
  ];
  // The day the reader chose, not the day the build happened to pick: a
  // pasted line that says otherwise sends someone to the wrong day.
  const chosen = (DATA.serviceDays || [])[STATE.day] || DATA.serviceDate;
  if (chosen) lines.push("Times for: " + humanDate(chosen));
  for (const destination of kept) {
    const journey = journeyFor(destination);
    const changes = journey.changes === null || journey.changes === undefined
      ? "changes unknown"
      : journey.changes === 0 ? "no change" : journey.changes + " change(s)";
    const time = journey.found
      ? duration(journey.minutes)
      : dayAbsenceText(destination, false);
    lines.push("- " + destination.name + " (" + destination.crs + "): " + money(priceOf(destination)) +
      " " + what + ", " + fareName(destination) + ", " + time + ", " + changes);
  }
  lines.push("A shortlist of destinations, not a booking: no train is chosen and no ticket is held.");
  return lines.join("\n");
}
if (shortlistCopy) {
  shortlistCopy.addEventListener("click", async () => {
    const text = shortlistText();
    const show = () => {
      // Never claim a copy that did not happen, the same rule the row copy
      // follows: a denied clipboard shows the text, in the dock's own share
      // panel, which is where the reader can reach it.
      shortlistBox.value = text;
      shortlistBox.hidden = false;
      if (shortlistShareBox) shortlistShareBox.open = true;
      shortlistStatus.textContent = "Could not copy automatically. The list is shown to copy by hand.";
    };
    if (!navigator.clipboard || !navigator.clipboard.writeText) return show();
    try {
      await navigator.clipboard.writeText(text);
      shortlistStatus.textContent = "Shortlist copied.";
    } catch (error) {
      show();
    }
  });
}
if (shortlistDockClear) {
  shortlistDockClear.addEventListener("click", () => {
    STATE.shortlist = [];
    setShortlistStatus("");
    renderShortlist();
    writeUrl();
  });
}
window.addEventListener("resize", padForDock);
