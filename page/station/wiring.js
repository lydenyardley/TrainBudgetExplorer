// The last statements the page runs: every control's listener, the day
// control's own options, and the first render.

// S22: a result set that just changed under the reader starts again at its
// first page, because the cheapest destinations are the ones a narrowed
// search wants to see first and page 4 of the previous set is not where they
// are now. The count and the page position are both re-announced by render().
// DL1 and OV3 of the 19 October 2026 passes: the slider has its own path. Its
// first input opens a gesture whose gain is measured from the budget before it,
// the input coalesces one render per frame, and the release settles the wording.
// The number field above keeps chooseBudget(), because typing is one decision
// per keystroke and its value is the sentence's own number.
budget.addEventListener("input", () => dragBudget(budget.value));
budget.addEventListener("change", settleBudgetDrag);
budgetNumber.addEventListener("input", () => chooseBudget(budgetNumber.value));
budgetField.addEventListener("click", (event) => {
  if (event.target === budgetField || event.target.classList.contains("budget-prefix")) {
    budgetNumber.focus();
    budgetNumber.select();
  }
});
railcardSelect.addEventListener("change", () => {
  chooseCard(railcardSelect.value);
  try {
    if (noCard()) window.localStorage.removeItem(RAILCARD_MEMORY + DATA.origin.crs);
    else window.localStorage.setItem(RAILCARD_MEMORY + DATA.origin.crs, STATE.railcard);
  } catch (error) {
    // Storage blocked. The choice still applies to this page and still travels
    // in the URL; it just will not be there next time.
  }
});
// "All" is the selection being empty rather than a chip of its own, so
// choosing it clears every specific chip -- reading the boxes back would find
// the chips still on and keep them, which made the All control do nothing. Any
// other chip is the set of boxes now on, and clearing the last one leaves the
// empty selection that checks All again.
for (const input of destinationTypeInputs) {
  input.addEventListener("change", () => chooseTypes(
    input.value === "all" ? [] : chipSelection()));
}
for (const radio of document.querySelectorAll('input[name="unit"]')) radio.addEventListener("change", () => chooseUnit(radio.value));
for (const radio of document.querySelectorAll('input[name="ticketMode"]')) radio.addEventListener("change", () => chooseMode(radio.value));
previousPage.addEventListener("click", () => { STATE.page -= 1; render(); writeUrl(); window.scrollTo({ top: 0, behavior: "smooth" }); });
nextPage.addEventListener("click", () => { STATE.page += 1; render(); writeUrl(); window.scrollTo({ top: 0, behavior: "smooth" }); });
// Critique item 8: the page's two accelerators. Setting the budget is the
// page's whole question, and the pager is the other control a keyboard reader
// walks a whole tab order to reach. `/` is the convention a reader already
// carries from a search field, and `b` is the same action for a layout where
// `/` needs a shift -- kept for a reader who has met it, though only one key is
// named now (DS3 of the 19 October 2026 distill pass): a hint is not a
// dictionary. A keystroke inside a field belongs to the field, so a reader
// typing a budget, a station name or a railcard keeps every key they press, and
// a held modifier is never an accelerator.
document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const target = event.target;
  const tag = target && target.tagName;
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" ||
      (target && target.isContentEditable)) return;
  const key = event.key.toLowerCase();
  if (key === "/" || key === "b") {
    event.preventDefault();
    budgetNumber.focus();
    budgetNumber.select();
    return;
  }
  // The pager's own buttons decide what paging does, so the keys press them
  // rather than repeat their three statements: one place changes the page, and
  // a key on the first or last page does nothing the button would not do.
  const button = key === "n" ? nextPage : key === "p" ? previousPage : null;
  if (button && pagination && !pagination.hidden && !button.disabled) {
    event.preventDefault();
    button.click();
  }
});
applyState(readState());
// The day control is written from the payload rather than from markup, so a
// page whose build carried no week shows no control at all rather than an empty
// one. Its options are the build's own day first, then the days after it, each
// named the way a reader would name it: "Today" is wrong, because the page may
// have been built days ago, so every option carries its date.
//
// The weekday leads and the date follows, because that is the order a reader
// asks the question in: they want to know whether Sunday works for them. The
// date stays because the weekday cannot stand in for it. Measured from
// Grantham on the reference timetable, Sunday 4 October 2026 reaches 238
// stations and Sunday 11 October reaches 416, and 50 of the 220 both reach have
// a different time, so "Sunday" on its own is a claim the feed does not carry.
// See adr/ADR-0060-the-day-names-its-date.md.
if (serviceDaySelect) {
  const days = DATA.serviceDays || [];
  if (days.length > 1) {
    serviceDaySelect.replaceChildren();
    days.forEach(function (iso, index) {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = shortDay(iso) + ", " + humanDate(iso);
      serviceDaySelect.append(option);
    });
    // The address was read before this block ran, so the day a link asked for is
    // already recorded; the control is pointed at it now that it has options.
    setServiceDay(STATE.day);
    serviceDaySelect.addEventListener("change", function () {
      chooseServiceDay(serviceDaySelect.value);
    });
    serviceDayBar.hidden = false;
    // D4 of the 17 October 2026 critique: this line was three clauses, one of
    // which explained why a date control exists and one of which repeated what
    // the label already says. What is left is the limitation, which is the only
    // part a reader cannot see for themselves.
    serviceDayHelp.textContent = "Interchange stations are shown for the build’s own day only.";
  } else {
    serviceDayBar.remove();
  }
}
if (clearTypes) clearTypes.addEventListener("click", clearDestinationTypes);
provenance();
sizeBudgetField();
render();
