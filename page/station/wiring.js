// The last statements the page runs: every control's listener, the day
// control's own options, and the first render.

// S22: a result set that just changed under the reader starts again at its
// first page, because the cheapest destinations are the ones a narrowed
// search wants to see first and page 4 of the previous set is not where they
// are now. The count and the page position are both re-announced by render().
budget.addEventListener("input", () => { setBudget(budget.value); currentPage = 1; render(); writeUrl({ budget: true }); });
budgetNumber.addEventListener("input", () => { setBudget(budgetNumber.value); currentPage = 1; render(); writeUrl({ budget: true }); });
budgetField.addEventListener("click", (event) => {
  if (event.target === budgetField || event.target.classList.contains("budget-prefix")) {
    budgetNumber.focus();
    budgetNumber.select();
  }
});
railcardSelect.addEventListener("change", () => {
  try {
    if (noCard()) window.localStorage.removeItem(RAILCARD_MEMORY + DATA.origin.crs);
    else window.localStorage.setItem(RAILCARD_MEMORY + DATA.origin.crs, railcardSelect.value);
  } catch (error) {
    // Storage blocked. The choice still applies to this page and still travels
    // in the URL; it just will not be there next time.
  }
  currentPage = 1;
  render();
  writeUrl();
});
for (const input of destinationTypeInputs) {
  input.addEventListener("change", () => {
    const all = destinationTypeInputs.find((candidate) => candidate.value === "all");
    if (input.value === "all") {
      for (const candidate of destinationTypeInputs) candidate.checked = candidate === all;
    } else if (input.checked) {
      all.checked = false;
    } else if (destinationTypeInputs.filter((candidate) => candidate.value !== "all").every((candidate) => !candidate.checked)) {
      all.checked = true;
    }
    currentPage = 1;
    render();
    writeUrl();
  });
}
for (const radio of document.querySelectorAll('input[name="unit"]')) radio.addEventListener("change", () => { currentPage = 1; render(); writeUrl(); });
for (const radio of document.querySelectorAll('input[name="ticketMode"]')) radio.addEventListener("change", () => { currentPage = 1; render(); writeUrl(); });
previousPage.addEventListener("click", () => { currentPage -= 1; render(); writeUrl(); window.scrollTo({ top: 0, behavior: "smooth" }); });
nextPage.addEventListener("click", () => { currentPage += 1; render(); writeUrl(); window.scrollTo({ top: 0, behavior: "smooth" }); });
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
    setServiceDay(serviceDayIndex);
    serviceDaySelect.addEventListener("change", function () {
      chooseServiceDay(serviceDaySelect.value);
    });
    serviceDayBar.hidden = false;
    serviceDayHelp.textContent = "Times and changes for every row, on the date you pick."
      + " Days of the week are not the same as each other, so the date is named."
      + " Interchange stations are shown for the build’s own day only.";
  } else {
    serviceDayBar.remove();
  }
}
if (clearTypes) clearTypes.addEventListener("click", clearDestinationTypes);
provenance();
sizeBudgetField();
render();
