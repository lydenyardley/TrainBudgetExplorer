// The results table: the columns it has, the count line that says what is
// in the list, and the render every control re-runs.

// A prices-only build has no times to show, and two columns of dashes are
// noise where a shorter table is honest: the columns stand down entirely.
//
// Each table's own columns are removed, not every fourth and fifth heading on
// the page. The selector used to be a bare nth-child across all of them, which
// took the dock's Changes and Remove columns instead of the results table's
// Time and Changes: the dock row is still built with five cells, so it was left
// with a three-heading table over it and a remove button nothing named.
if (!DATA.hasJourneys) {
  const standingDown = (table) => {
    for (const th of table.querySelectorAll("thead th")) {
      const name = th.textContent.trim();
      if (name === "Time" || name === "Changes") th.remove();
    }
  };
  standingDown(document.getElementById("rows").closest("table"));
  const dock = document.getElementById("shortlistDock");
  if (dock) standingDown(dock.querySelector("table"));
}
// Scoped to the results table rather than counted across the page. Two tables
// carry headings, and a detail row spanning the sum of both asks for more
// columns than its own table has, which the browser silently clamps to full
// width. It read correctly by accident, and the count stopped meaning anything
// the moment either table's headings changed.
const columnCount = () => rows.closest("table").querySelectorAll("thead th").length;
function renderCoverage() {
  const coverage = document.getElementById("feedCoverage");
  if (!coverage || DATA.rawFareDestinationCount === undefined) return;
  const mode = ticketMode();
  const lead = mode === "single"
    ? DATA.singleDestinations.length + " displayable outbound single fares are available in this mode." +
      (DATA.singleJourneyNote ? " " + DATA.singleJourneyNote : "")
    : mode === "anytime"
      ? DATA.anytimeDestinations.length + " reviewed unrestricted Anytime Day Return fares are available in this mode."
      // Q4: the cheapest list is not one of the three sets, so it has a lead of
      // its own rather than borrowing a set's sentence and counting its fares.
      : mode === CHEAPEST_MODE
        ? modeCount(CHEAPEST_MODE) + " destinations are shown, each on the cheapest fare of any ticket type the feed prices for it" + droppedFromFeed() + "."
      : DATA.rawFareDestinationCount + " standard-return destinations were found in the feed" + droppedFromFeed() + "." +
        (DATA.destinations.length
          ? " Raise the budget to include more of the " + DATA.destinations.length + " displayable destinations."
          : "");
  coverage.textContent = lead + classifiedNote() + unnameableNote();
}
function droppedFromFeed() {
  // The naming gap is not listed here. It used to be, in the return mode's
  // sentence only, which is why the single and Anytime modes had no way to
  // report it. unnameableNote() owns that count for all three modes instead,
  // so a reader never sees it stated twice in one line.
  const dropped = [];
  if (DATA.excludedItxCount) dropped.push(DATA.excludedItxCount + " had only ITX placeholder fares");
  return dropped.length ? "; " + dropped.join(" and ") + ", and are not shown" : ", and all are shown";
}
function classifiedNote() {
  if (DATA.unclassifiedDestinationCount) {
    return " " + DATA.unclassifiedDestinationCount + " priced destinations carry no reviewed " +
      "destination type, so no type chip on this page can select them.";
  }
  return DATA.locationTypeReviewed ? " Every destination on this page carries a reviewed type." : "";
}
// C11: the coverage line named destinations lost to a missing *type* but not
// the ones lost to a missing *name*. Those are a different gap with a different
// consequence -- a row the feed could not put a station name on is a row a
// reader cannot recognise -- and saying only the first made a shortlist with a
// known gap in it look complete. It is stated here, as a count of flow records
// the feed could not name, so it is never read as a destination a reader
// should expect to find.
function unnameableNote() {
  if (!DATA.unnameableFareCount) return "";
  return " " + DATA.unnameableFareCount + " priced " +
    (DATA.unnameableFareCount === 1 ? "flow had" : "flows had") +
    " no station name in the feed, so " +
    (DATA.unnameableFareCount === 1 ? "it is" : "they are") +
    " not shown here; that is a gap in the feed's names, not a place with no fare.";
}
function render() {
  // The tab title is the same sentence as the heading, and a reader who
  // dragged the budget and then looked at the tab list had no way to tell two
  // searches apart. Before the early returns, because a page with nothing
  // priced still names its origin and its budget.
  document.title = "Train fares up to £" + budgetNumber.value + " from " + DATA.origin.name;
  // Before any price is read: the railcard changes the price of every row, and
  // a card ticked for a party of one is a number no reader could buy. It also
  // decides which row the cheapest list keeps for a destination, so that list
  // is composed after this and not before it.
  syncRailcardParty();
  const available = activeDestinations();
  // The budget's stop first, because a chip is offered only when this budget
  // can reach a destination of its type. clampBudget returns the reader's own
  // budget for an empty list, so the two empty states below still keep it.
  const cap = clampBudget(available);
  // Before the filter is read, not after: a chip the active list cannot support
  // inside this budget must not be part of what the filter is asked to match,
  // and a chip that goes away must not stay checked halfway through the read.
  syncDestinationTypeChips(available, cap);
  // An unpriced page has no budget conversation: provenance() has already
  // stood the controls and the table down, and anything this function wrote
  // ("Nothing inside this budget") would contradict the page's own first
  // sentence. So it does nothing at all -- but that is the only case where it
  // says nothing.
  if (!DATA.destinations.length && !DATA.singleDestinations.length && !DATA.anytimeDestinations.length) {
    if (filterState) filterState.textContent = "";
    return;
  }
  renderCoverage();
  renderModeNote();
  if (!available.length) {
    // The budget is left alone on purpose. An empty list has no prices to
    // bound, and clamping to the £1 ceiling of an empty list would silently
    // reset the reader's budget for every other mode they switch back to.
    rows.replaceChildren();
    summary.textContent = "No " + modeLabels()[ticketMode()] + " fares from " + DATA.origin.name;
    empty.hidden = false;
    renderEmptyMode();
    more.hidden = true;
    pagination.hidden = true;
    pageStatus.textContent = "";
    // The shortlist is a list of places this mode can price, so a mode that
    // prices none of them empties it rather than leaving a list of names with
    // no fares behind them.
    shortlistCodes = [];
    renderFilterState();
    renderShortlist();
    return;
  }
  const wantedTypes = selectedDestinationTypes();
  // C17: the three fare arrays arrive sorted once by the standard fare. The
  // price on screen is not always that fare -- choosing two adults doubles it,
  // and the railcard replaces it with a per-ticket discounted price that a
  // minimum fare can hold above the adult price -- so the list is re-sorted by
  // the price actually displayed, and the count line below says so in words.
  // Sorting the displayed number is the only ordering that cannot contradict
  // the number in the cell beside it.
  const wanted = available
    .filter((d) => priceOf(d) <= cap && matchesType(d, wantedTypes))
    .sort((a, b) => priceOf(a) - priceOf(b));
  budgetNumber.value = budget.value;
  sizeBudgetField();
  updateChipCounts(available, cap);
  renderFilterState();
  rows.replaceChildren();

  const pageCount = Math.max(1, Math.ceil(wanted.length / PAGE_SIZE));
  currentPage = Math.min(Math.max(1, currentPage), pageCount);
  const pageItems = wanted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  for (const destination of pageItems) {
    const row = document.createElement("tr");
    row.dataset.crs = destination.crs;
    // The header is one list and the cells are the same list, in the same
    // order, built here. They used to be two lists written in different places
    // and they had drifted: the header read Station, Price, Time, Changes,
    // Fare code, Tickets while the cells were written Station, Time, Changes,
    // Price, Fare code, Tickets, so the Price column showed "No service" and
    // the Changes column showed the fare. A prices-only build stands two of
    // these columns down, and it stands down the same two here and in the
    // header for the same reason.
    const cells = [holdCell(destination), stationCell(destination), priceCell(destination)];
    if (DATA.hasJourneys) {
      cells.push(journeyCell(destination, "Time"), journeyCell(destination, "Changes"));
    }
    cells.push(fareTypeCell(destination));
    for (const cell of cells) row.append(cell);
    cellWithLinks(row, destination, wanted);
    rows.append(row);
  }

  // Q4: in the cheapest list every row names its own fare, so the count line
  // names the mix rather than implying one ticket type, and the party figure
  // says what it is two of -- on a single row, two singles, not two returns.
  const what = unit() === "party" ? "for the two of us" : "each";
  const basis = ticketMode() === CHEAPEST_MODE && unit() === "party"
    ? "for the two of us, two of the fare each row names"
    : what;
  // ADR-0041: the order belongs to the list, so it is said once, here, rather
  // than by tinting one row the reader is left to interpret.
  const order = ", cheapest first";
  const mix = ticketMode() === CHEAPEST_MODE ? mixPhrase(wanted) : "";
  // An unpriced origin has no budget conversation to have, so the summary
  // stays empty rather than implying the budget filtered something out.
  summary.textContent = available.length && wanted.length
    ? wanted.length + (wanted.length === 1 ? " destination" : " destinations") + " for up to " + money(cap) + " " + basis + order + mix
    // An empty list names what emptied it. The paragraph below the table has
    // said so since S28; this line -- the first thing a reader reads after
    // dragging the budget -- said only that there was nothing, while the chip
    // that caused it sat inside the folded refinements.
    : available.length ? "No destinations for up to " + money(cap) + " " + basis + typeLabel() : "";
  empty.hidden = wanted.length > 0;
  renderEmpty(available, wanted, cap, basis);
  more.hidden = true;
  pagination.hidden = pageCount <= 1;
  // "Page 1 of 2 of 30 results" was two facts sharing one "of" twice over
  // (audit item 12, 9 October 2026). The page and the count keep one each:
  // "1 of 2 pages · 30 destinations". The singular is spelled rather than
  // left to read "1 pages" on a page whose list happens to fit one.
  pageStatus.textContent = currentPage + " of " + pageCount +
    (pageCount === 1 ? " page · " : " pages · ") + wanted.length +
    (wanted.length === 1 ? " destination" : " destinations");
  previousPage.disabled = currentPage === 1;
  nextPage.disabled = currentPage === pageCount;
  renderShortlist();
}
