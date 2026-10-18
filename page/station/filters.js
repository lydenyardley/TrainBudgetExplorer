// The refinements: the fold that holds them, the destination-type chips,
// their counts, and the line that says what is narrowed.

// #more, #pagination, #pageStatus and the two pager buttons are read in
// payload.js: table.js and wiring.js write them, and only the pager's own page
// arithmetic below lives here (E12 of the 17 October 2026 audit).
const destinationTypeInputs = Array.from(document.querySelectorAll('input[name="destinationType"]'));
const destinationType = document.getElementById("destinationTypes");
const PAGE_SIZE = 20;
const clearTypes = document.getElementById("clearTypes");
const moreFilters = document.getElementById("moreFilters");
const moreFiltersToggle = document.getElementById("moreFiltersToggle");
const filterState = document.getElementById("filterState");  // The refinements are folded at every width, and the reader is the only thing
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
  }
  if (moreFiltersToggle) moreFiltersToggle.addEventListener("click", () => {
    setFiltersOpen(moreFilters.dataset.open !== "true");
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
    const input = document.querySelector(`input[name="destinationType"][value="${value}"]`);
    const span = input && input.parentElement ? input.parentElement.querySelector("span") : null;
    return span ? span.textContent : value;
  };
  const typeText = types.length ? types.map(labelOf).join(", ") : "All";
  return "Ticket: " + modeLabels()[ticketMode()] + " · Travellers: " + party + ", " + card +
    " · Destination: " + typeText;
}
function renderFilterState() {
  if (filterState) filterState.textContent = filterStateText();
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
  for (const input of destinationTypeInputs) {
    if (input.value === "all") continue;
    const slot = document.querySelector(`.chipcount[data-count-for="${input.value}"]`);
    if (!slot) continue;
    const count = available.filter(
      (destination) => priceOf(destination) <= cap &&
        (destination.destinationTypes || [destination.destinationType]).includes(input.value)
    ).length;
    slot.textContent = count === 1 ? "(1)" : "(" + count + ")";
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
  const input = document.querySelector(`input[name="destinationType"][value="${value}"]`);
  const chip = input ? input.closest("label") : null;
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
