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
  budgetCeilingNote.textContent = money(ceiling * 100) + " for "
    + (unit() === "party" ? "two adults" : "one adult");
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
  sizeBudgetField();
  return safe;
}
