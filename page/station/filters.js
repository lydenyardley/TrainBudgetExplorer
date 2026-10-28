// The refinements: the fold that holds them, the destination-type chips,
// their counts, and the line that says what is narrowed.

// #more, #pagination, #pageStatus and the two pager buttons are read in
// payload.js: table.js and wiring.js write them, and only the pager's own page
// arithmetic below lives here (E12 of the 17 October 2026 audit).
const destinationTypeInputs = Array.from(document.querySelectorAll('input[name="destinationType"]'));
const destinationType = document.getElementById("destinationTypes");
const PAGE_SIZE = 20;
const clearTypes = document.getElementById("clearTypes");
// The facets disclosure: the ten thematic chips are one press away from the
// row of four settlement bands the build writes them beside (critique item 3,
// second half), and the count in the disclosure is kept true by the same
// function that hides the chips.
const moreTypes = document.getElementById("moreTypes");
const moreTypesPanel = document.getElementById("moreTypesPanel");
const moreTypesCount = moreTypes ? moreTypes.querySelector(".more-types-count") : null;
const facetInputs = moreTypesPanel
  ? Array.from(moreTypesPanel.querySelectorAll('input[name="destinationType"]'))
  : [];
const moreFilters = document.getElementById("moreFilters");
const moreFiltersToggle = document.getElementById("moreFiltersToggle");
const keyHints = document.getElementById("keyHints");
const filterState = document.getElementById("filterState");
// A chip's count, and a chip's label, found by the value the chip carries rather
// than by a selector built out of that value. Those selectors were written as
// `[data-count-for="<value>"]` and `[value="<value>"]`, and a value holding a
// quote was a SyntaxError that took the whole render with it (audit item 4, 28
// October 2026). Neither map changes during a visit, so both are built once.
//
// `getAttribute` rather than `.value` throughout: this is what the build said a
// chip is, not a state a reader can hold, and the two maps are the page's copy of
// the markup rather than a second record of the search.
const chipCountSlots = new Map();
for (const slot of document.querySelectorAll(".chipcount")) {
  const value = slot.getAttribute("data-count-for");
  if (value) chipCountSlots.set(value, slot);
}
const chipLabels = new Map();
for (const input of destinationTypeInputs) {
  const label = input.closest("label");
  const value = input.getAttribute("value");
  if (label && value) chipLabels.set(value, label);
}

// The refinements are folded at every width, and the reader is the only thing
// that opens them. The control is a button carrying aria-expanded, so the
// state is announced without any of this: the markup opens folded and this
// only flips that. There used to be a second road in -- a media query and a
// resize listener that opened the panel above the phone breakpoint and closed
// it below -- which meant the state a reader had chosen could be overwritten
// by rotating a device, and meant the fold was a different thing at each
// width. Both are gone: one control, one state, one place it changes.
function setFiltersOpen(open) {
  if (!moreFilters) return;
  moreFilters.dataset.open = open ? "true" : "false";
  if (moreFiltersToggle) moreFiltersToggle.setAttribute("aria-expanded", open ? "true" : "false");
  // The toggle's name depends on which half of the fold it is showing (DS4),
  // so opening or closing it re-writes the name as well as the state.
  renderFilterState();
}
if (moreFiltersToggle) moreFiltersToggle.addEventListener("click", () => {
  setFiltersOpen(moreFilters.dataset.open !== "true");
});

// The facets are one press away inside the refinements panel above (#moreFiltersPanel,
// which the stylesheet leaves display:none until #moreFilters opens it). The
// fold is the reader's, exactly as that panel's fold is: the markup arrives
// closed and this only flips it, so no render reads it back and a reader who
// opens it and then narrows something keeps it open. A page whose script did
// not arrive is no worse off, because these chips are already inside a panel
// that only that script opens.
if (moreTypes && moreTypesPanel) moreTypes.addEventListener("click", () => {
  const open = moreTypes.getAttribute("aria-expanded") === "true";
  moreTypesPanel.hidden = open;
  moreTypes.setAttribute("aria-expanded", String(!open));
});

// What is narrowed, said in the summary, so a reader who has collapsed the
// refinements on a phone can still see that a filter is on.
function filterStateText() {
  // selectedDestinationTypes() is a Set, and the chip's own label is the only
  // wording a reader has seen for it.
  const types = Array.from(selectedDestinationTypes());
  const party = unit() === "party" ? "Two adults" : "One adult";
  // How many cards rather than whether there is one. A reader who has chosen a
  // card is reading the price beside it, and the fold hides the panel that
  // offered it, so "no card selected" and "no railcard" were both a fact this
  // line could not state without reading the panel again.
  const card = noCard() || !railcards[STATE.railcard]
    ? "0 railcard"
    : "1 railcard (" + railcards[STATE.railcard].label + ")";
  const labelOf = (value) => {
    const chip = chipLabels.get(value);
    const span = chip ? chip.querySelector("span") : null;
    return span ? span.textContent : value;
  };
  const typeText = types.length ? types.map(labelOf).join(", ") : "All";
  return "Ticket: " + modeLabels()[ticketMode()] + " · Travellers: " + party + ", " + card +
    " · Destination: " + typeText;
}
function renderFilterState() {
  const text = filterStateText();
  if (filterState) filterState.textContent = text;
  // DS4 of the 19 October 2026 distill pass: the summary is hidden while the
  // panel is open (the stylesheet does that), because the controls below it show
  // the same state. A hidden line is not part of the toggle's name either, so the
  // state travels in an aria-label for exactly as long as it is hidden -- and it
  // is rewritten on every render, because a chip chosen with the panel open
  // changes the state the toggle names.
  if (moreFiltersToggle) {
    if (moreFilters && moreFilters.dataset.open === "true") {
      moreFiltersToggle.setAttribute("aria-label", "Filter this list. " + text);
    } else {
      moreFiltersToggle.removeAttribute("aria-label");
    }
  }
}
// The page's accelerators, named in the strip that stays on screen while the
// refinements are folded, because a key nobody is told about is not offered.
// The paging half is only promised while the pager is on screen, and only the
// render that decides the pager's visibility knows that, so this is called from
// there rather than from here at load.
function renderKeyHints() {
  if (!keyHints) return;
  // DS3 of the 19 October 2026 distill pass: one key named, not two. `b` still
  // works (wiring.js), because a reader who has met it once should not lose it;
  // it is simply not one of the two keys a newcomer is asked to remember. The
  // stylesheet shows this line only to a fine pointer, so a phone is not told
  // about a keyboard it does not have.
  keyHints.textContent = "Press / to set the budget" +
    (pagination && !pagination.hidden ? ", and n or p to change page." : ".");
  keyHints.hidden = false;
}
// The chips as the reader has them. This is the one adapter that reads the
// controls rather than the state, because a chip's own click is the only place
// its value is news: everything else asks selectedDestinationTypes(), which
// reads STATE.types.
function chipSelection() {
  return destinationTypeInputs
    .filter((input) => input.value !== "all" && input.checked)
    .map((input) => input.value);
}
function selectedDestinationTypes() {
  return new Set(STATE.types);
}
function matchesType(destination, wantedTypes) {
  if (wantedTypes.size === 0) return true;
  const types = destination.destinationTypes || [destination.destinationType];
  return types.some((type) => wantedTypes.has(type));
}
function typeLabel() {
  const labels = destinationTypeInputs
    .filter((input) => input.value !== "all" && input.checked)
    // The chip's own label span, not the whole label element: the count beside
    // it says how many destinations the chip would show, and a sentence reading
    // "in cities (2)" states that number as part of the filter.
    .map((input) => input.parentElement.querySelector("span").textContent.trim().toLowerCase());
  // "or", not "and": two selected types show the union, and a message that
  // said "and" would describe a filter the page does not apply.
  return labels.length > 1 ? " in " + labels.join(" or ") : labels.length ? " in " + labels[0] : "";
}

// S20: how many of the destinations in the list the reader is looking at are
// inside the budget and carry this type. A chip that can only ever return
// nothing is a broken control; a chip that says it would return nothing is a
// decision the reader gets to make.
//
// The count is what the chip is offered on: syncDestinationTypeChips() hides the
// chips whose count is zero, and this only writes the numbers, so the two
// cannot disagree about a chip's own count.
function updateChipCounts(available, cap) {
  // One pass counts every type, rather than one pass per chip: fourteen chips
  // against a 1,596-row list re-read the whole list fourteen times, which is
  // some 22,000 predicate calls for a number each chip could be told in one walk
  // (audit item 8, 28 October 2026).
  const counts = new Map();
  for (const destination of available) {
    if (priceOf(destination) > cap) continue;
    const types = destination.destinationTypes || [destination.destinationType];
    for (let at = 0; at < types.length; at += 1) {
      const type = types[at];
      // A type a row lists twice is still one destination carrying it, which is
      // what `.includes` said a chip's count meant.
      if (types.indexOf(type) !== at) continue;
      counts.set(type, (counts.get(type) || 0) + 1);
    }
  }
  for (const input of destinationTypeInputs) {
    if (input.value === "all") continue;
    const slot = chipCountSlots.get(input.value);
    if (!slot) continue;
    const count = counts.get(input.value) || 0;
    const text = count === 1 ? "(1)" : "(" + count + ")";
    // A number that has not changed is not a reason to touch the document: a
    // drag rewrote fourteen counts a frame whether or not the budget moved one.
    if (slot.textContent !== text) slot.textContent = text;
  }
  const clear = document.getElementById("clearTypes");
  if (clear) clear.hidden = selectedDestinationTypes().size === 0;
}
function clearDestinationTypes() {
  chooseTypes([]);
}
// A chip is offered when a destination in the list the reader is looking at
// carries it and is inside the budget. The build offers one from the union of
// the three ticket modes, because it cannot know which a reader will pick, and a
// chip that can only ever return nothing reads as a broken control: on the real
// Grantham page every heritage destination was an outbound single, so return mode
// offered a heritage chip that filtered to no rows at all. The same rule then
// narrows the chips to the budget: three of the fourteen type chips on the real
// Grantham page sat at (0) at the opening budget, each of them selecting an empty
// list, and the count beside a chip is already the number of destinations inside
// the budget, so a zero is the chip saying it cannot succeed here. A chip that
// disappears takes its selection with it -- a hidden chip left checked keeps
// filtering with nothing to show for it -- and a hidden chip is announced, so a
// filter that emptied itself is never silent.
function syncDestinationTypeChips(available, cap) {
  const offered = new Set();
  for (const destination of available) {
    if (priceOf(destination) > cap) continue;
    for (const type of destination.destinationTypes || [destination.destinationType || "other"]) {
      offered.add(type);
    }
  }
  // C20: a facet present in only one ticket mode used to be silently unchecked
  // when the mode changed, so switching back to the mode the reader had chosen
  // it in showed "All" and no explanation. Each mode now keeps its own
  // selection, and switching restores it, so intent survives the round trip.
  const mode = ticketMode();
  // Whether the mode moved is decided once here, because this runs on every
  // render rather than only on a mode change. What it decides is the per-mode
  // memory of what the reader selected, and the name the notice below speaks in.
  // The notice itself is not tied to it: a chip the budget takes away is
  // announced too, and only a chip that was actually selected is announced at
  // all -- so a drag that merely hides the chips already sitting at (0) stays
  // quiet.
  const modeChanged = STATE.lastSyncedMode !== null && STATE.lastSyncedMode !== mode;
  if (modeChanged) {
    STATE.typesByMode[STATE.lastSyncedMode] = STATE.types.slice();
  }
  // The selection is computed from the state and then drawn, rather than read
  // back out of fourteen checkboxes: a chip the budget or the mode takes away
  // leaves STATE.types here, and every chip below is set from what is left. The
  // other direction -- reading the boxes after clearing one of them -- is how
  // the page ended up with two answers to "what is narrowed" (R4).
  const dropped = STATE.types.filter((type) => !offered.has(type));
  const kept = STATE.types.filter((type) => offered.has(type));
  // Restore what the reader chose the last time they were in this mode, minus
  // anything this mode cannot offer. A mode reached for the first time keeps
  // whatever the reader has selected now, which is what the previous behaviour
  // did too.
  const remembered = modeChanged ? STATE.typesByMode[mode] || [] : [];
  const restored = remembered.filter((type) => offered.has(type) && !kept.includes(type));
  STATE.types = kept.concat(restored);
  for (const input of destinationTypeInputs) {
    if (input.value === "all") continue;
    const chip = input.closest("label");
    if (chip) chip.hidden = !offered.has(input.value);
    input.checked = STATE.types.includes(input.value);
  }
  const all = destinationTypeInputs.find((input) => input.value === "all");
  if (all) all.checked = STATE.types.length === 0;
  // The disclosure says how many facets are behind it, and stands down when the
  // budget has taken every one of them: a press into an empty row is the dead
  // end this function already refuses a chip for (S20), and the number in the
  // chip row is read as the count of what it would show -- so it follows the
  // chips rather than the taxonomy.
  if (moreTypes) {
    const offeredFacets = facetInputs.filter((input) => !input.closest("label").hidden).length;
    moreTypes.hidden = offeredFacets === 0;
    if (moreTypesCount) moreTypesCount.textContent = "(" + offeredFacets + ")";
    // A fold left open over no chips is the dead end the chips themselves are
    // refused for (S20), and the control that would close it is gone with them,
    // so the panel goes back to folded.
    if (offeredFacets === 0 && moreTypesPanel) {
      moreTypesPanel.hidden = true;
      moreTypes.setAttribute("aria-expanded", "false");
    }
  }
  STATE.lastSyncedMode = mode;
  // Announced whenever something changed, not only on a mode change: the budget
  // can take a chip away too, and a filter that changed the result set without
  // saying so is indistinguishable from a broken one. Nothing is said when
  // nothing changed, so a budget drag that moves no chip's zero stays quiet.
  if (dropped.length || restored.length) {
    announceFacetChange(dropped.map(chipLabel), restored.map(chipLabel), mode);
  }
}
function chipLabel(value) {
  const chip = chipLabels.get(value);
  return chip ? chip.textContent.replace(/\(\d+\)/, "").trim() : value;
}
// A filter that changed the result set without saying so is indistinguishable
// from a broken one, so what happened is stated next to the chips and pushed to
// assistive technology through the live region it is already in.
function announceFacetChange(dropped, restored, mode) {
  const notice = document.getElementById("facetNotice");
  if (!notice) return;
  const modeName = modeLabels()[mode] || "this ticket type";
  const parts = [];
  if (dropped.length) {
    // "Inside your budget" rather than "from this station": the chip left
    // because no destination of that type is inside the budget in this list,
    // which is the rule the chip was offered on, and the budget is the half of
    // it the reader can act on.
    parts.push("Cleared " + listWords(dropped) + " — " + modeName +
      " has no destination of " + (dropped.length === 1 ? "that type" : "those types") +
      " inside your budget.");
  }
  if (restored.length) {
    parts.push("Restored your " + listWords(restored) + " filter from " + modeName + ".");
  }
  notice.textContent = parts.join(" ");
  notice.hidden = !parts.length;
}
function listWords(items) {
  return items.length > 1 ? items.join(", ") : items[0] || "";
}
