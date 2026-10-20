// The budget: its field, its clamp, and the width of its own number.
//
// The ceiling is deliberately not here. It is the dearest fare the list on
// screen carries (budgetCeiling, in ticket-modes.js), because which fare is
// dearest depends on the party and the card, and this panel holds neither.

function sizeBudgetField() {
  const digits = Math.max(1, String(STATE.budget).length);
  budgetNumber.style.width = digits + "ch";
}
// The stop is part of the budget's contract, so it is named where the reader is
// holding the control, and it is named as a figure rather than a rule: the
// sentence above the number is what changes, the number is what the reader can
// predict a boundary fare against.
//
// Settled before the chips are narrowed, because which chips exist depends on
// how far this budget reaches: a destination's price, and so whether any
// destination of a type is inside the budget, is read at the cap this returns.
// The list is a parameter rather than read again from the page, because the
// render that calls this has already composed it and the ceiling is the dearest
// fare *in that list*.
// The reader's budget is theirs per ticket mode. A mode switch clamps it to the
// new list's own stop -- the control cannot hold a figure above its ceiling --
// and coming back to a mode restores the figure they set in it. That second
// half is what keeps a filter: a chip is offered on the budget on screen
// (filters.js), so a reader who chose "Small towns" in Return mode and glanced
// at Singles would return to a budget that no longer reaches a small town, and
// the page would drop the filter it promises to keep (C20, critique item 3).
function clampBudget(available) {
  const mode = ticketMode();
  // An empty list has no prices to bound. An unpriced page and a ticket mode
  // with no fares both leave the reader's budget exactly as they set it --
  // clamping to the £1 ceiling of an empty list would silently reset the
  // budget for every mode they switch back to -- so the cap is simply what the
  // field holds.
  if (!available.length) {
    // Nothing is remembered for a mode that bounds nothing: the figure the
    // reader is holding belongs to the mode they set it in.
    STATE.lastClampedMode = mode;
    return STATE.budget * 100;
  }
  const remembered = mode === STATE.lastClampedMode ? undefined : STATE.budgetByMode[mode];
  STATE.lastClampedMode = mode;
  const ceiling = budgetCeiling();
  budget.max = String(ceiling);
  budgetNumber.max = String(ceiling);
  // The rail carries the same stop as the control it stands in for (OV4), so
  // the sentence is composed once here rather than written out twice.
  const stop = money(ceiling * 100) + " for "
    + (unit() === "party" ? "two adults" : "one adult");
  budgetCeilingNote.textContent = stop;
  if (railBudget) railBudget.max = String(ceiling);
  if (railStop) railStop.textContent = stop;
  if (remembered !== undefined && Number(remembered) <= ceiling) setBudget(remembered);
  else if (STATE.budget > ceiling) setBudget(ceiling);
  STATE.budgetByMode[mode] = STATE.budget;
  return STATE.budget * 100;
}
// The floor is zero, not one pound. Every outbound single from the real
// Grindleford page is fifty pence, so a floor of £1 left the
// slider's lowest position showing all thirteen of them: the empty state, and
// the recovery moves that are the entire point of it, could not be reached
// there at all. A budget of £0 matches no fare, which is what a
// reader who drags the control all the way down has asked for. The clamp no
// longer reads a deliberate zero as a missing value either --
// `Number(value) || 1` would, and that is the bug a naive edit to this line
// leaves behind.
function setBudget(value) {
  const wanted = Number(value);
  const top = Number(budget.max);
  const safe = Math.max(0, Math.min(Number.isFinite(top) ? top : 0,
                                    Number.isFinite(wanted) ? wanted : 0));
  STATE.budget = safe;
  budget.value = String(safe);
  budgetNumber.value = String(safe);
  // The rail is a second view of one number, never a second number: it is
  // written here with the two controls it stands in for.
  if (railBudget) railBudget.value = String(safe);
  if (railNow) railNow.textContent = "£" + safe;
  sizeBudgetField();
  return safe;
}

// DL1 and OV2 of the 19 October 2026 passes: the drag answers in places, not
// only in a number. "£22.40 adds PETERBOROUGH" is the page's own promise -- a
// price becomes a place -- arriving one pound early.
//
// The threshold is read from the list the reader is looking at: the active
// ticket mode, the party, the card and the destination-type filter, exactly as
// render() composes it. A threshold read from the whole feed would name a place
// the reader's filter has just hidden, and a party or a card moves every price,
// so it is recomputed rather than remembered.
function nextFareAbove(available, cap) {
  const types = selectedDestinationTypes();
  let price = Infinity;
  for (const destination of available) {
    if (!matchesType(destination, types)) continue;
    const pence = priceOf(destination);
    if (pence > cap && pence < price) price = pence;
  }
  if (!Number.isFinite(price)) return null;
  return {
    price: price,
    places: available.filter(
      (destination) => matchesType(destination, types) && priceOf(destination) === price),
  };
}
// What the next pound buys. At the top of the list there is no threshold ahead,
// so the line says where the top is instead of inventing one.
function nextPlaceLine(available, cap) {
  const reach = nextFareAbove(available, cap);
  if (!reach) {
    const top = budgetCeiling();
    return cap >= top * 100 ? money(top * 100) + " is the top fare here." : "";
  }
  // A tie is named as a count rather than as one of the places: naming one of
  // two would read as a recommendation the page refuses to make.
  return money(reach.price) + " adds " +
    (reach.places.length === 1
      ? reach.places[0].name
      : countWord(reach.places.length) + " places") + ".";
}
// What the gesture gained, once the reader lets go. The count is the list the
// page is showing, so it cannot disagree with the rows below it.
function placesWithin(available, cap) {
  const types = selectedDestinationTypes();
  return available.filter(
    (destination) => matchesType(destination, types) && priceOf(destination) <= cap).length;
}
function budgetGainLine(available, cap, before) {
  // Both figures are pence: `cap` is the state's pounds multiplied out by the
  // caller, and `before` is the budget the gesture started at, in pounds.
  const added = placesWithin(available, cap) - placesWithin(available, before * 100);
  if (added > 0) {
    return added === 1 ? "One place added." : countWord(added) + " places added.";
  }
  const reach = nextFareAbove(available, cap);
  if (reach) return "No new places until " + money(reach.price) + ".";
  return money(budgetCeiling() * 100) + " is the top fare here.";
}
function setBudgetNext(text) {
  if (!budgetNext) return;
  budgetNext.textContent = text;
  budgetNext.hidden = !text;
}
// Every render but the drag's own clears the line: it is a remark about the
// gesture that just ended, not a permanent fact about the search.
function clearBudgetNext() {
  setBudgetNext("");
}

// OV3 of the 19 October 2026 overdrive pass: one render a frame while the
// slider is moving. A range input can fire several input events between two
// paints, and each one re-rendered every row; the frame coalesces them, so the
// cost of a drag is bounded by the display rather than by the pointer. What is
// written synchronously is the number the reader is dragging, which setBudget()
// has already put in the field.
let budgetFrame = 0;
function queueBudgetFrame() {
  if (budgetFrame) return;
  const run = () => {
    budgetFrame = 0;
    render();
    writeUrl({ budget: true });
    // An empty list already has its own sentence and its own door, and the door
    // names the same place this line would. Two prices for one place, a line
    // apart, is the page arguing with itself; the empty state owns that moment.
    const available = activeDestinations();
    const cap = STATE.budget * 100;
    setBudgetNext(placesWithin(available, cap) ? nextPlaceLine(available, cap) : "");
  };
  budgetFrame = window.requestAnimationFrame
    ? window.requestAnimationFrame(run)
    : window.setTimeout(run, 16);
}
// The gesture's last statement, on the frame the reader let go: the pending
// render runs now rather than waiting for a paint, and the line settles on what
// the new budget gained.
function settleBudgetDrag() {
  if (budgetFrame) {
    if (window.cancelAnimationFrame) window.cancelAnimationFrame(budgetFrame);
    else window.clearTimeout(budgetFrame);
    budgetFrame = 0;
  }
  render();
  writeUrl({ budget: true });
  const from = STATE.budgetDragFrom;
  STATE.budgetDragFrom = null;
  const available = activeDestinations();
  const cap = STATE.budget * 100;
  // A list with nothing in it says so in the count line and offers the door
  // that fills it, so the gain line would repeat the door. A mode with no fares
  // has no place to name at all. Both are silence here.
  if (from === null || !available.length || !placesWithin(available, cap)) clearBudgetNext();
  else setBudgetNext(budgetGainLine(available, cap, from));
}
// A drag that has moved the budget but not yet rendered is still a search the
// page is running, so anything that needs the list reads the state through the
// same frame the drag uses rather than a frame behind it.
function dragBudget(value) {
  if (STATE.budgetDragFrom === null) STATE.budgetDragFrom = STATE.budget;
  setBudget(value);
  STATE.page = 1;
  queueBudgetFrame();
}
