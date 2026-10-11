// The budget: its field, its clamp, and the width of its own number.
//
// The ceiling is deliberately not here. It is the dearest fare the list on
// screen carries (budgetCeiling, in ticket-modes.js), because which fare is
// dearest depends on the party and the card, and this panel holds neither.

function sizeBudgetField() {
  const digits = Math.max(1, String(budgetNumber.value || "1").length);
  budgetNumber.style.width = digits + "ch";
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
  budget.value = String(safe);
  budgetNumber.value = String(safe);
  sizeBudgetField();
  return safe;
}
