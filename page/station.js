__LIST_KEYS__
__STATION_FIELD__
const DATA = __DATA__;
const FIRST_USE_FALLBACK = __FIRST_USE_FALLBACK__;
// Each row list arrives as a column list and a table of cells, because every row
// in a list carried the same field names and the page was sending them once per
// row. Hydrating here keeps the rest of this script reading rows as objects, and
// it is also what makes an older payload -- a plain list -- still render.
function hydrate(table) {
  if (!table || !Array.isArray(table.rows)) return table || [];
  const pool = DATA.pool || [];
  return table.rows.map((cells) => {
    const row = {};
    for (let i = 0; i < table.columns.length; i += 1) {
      const cell = cells[i];
      // A negative cell is an index into the page's pool of values that repeat,
      // so the rows that share a link or a railcard record share one object.
      row[table.columns[i]] = typeof cell === "number" && cell < 0 ? pool[-cell - 1] : cell;
    }
    return row;
  });
}
for (const key of ["destinations", "singleDestinations", "anytimeDestinations", "stations"]) {
  DATA[key] = hydrate(DATA[key]);
}
// ADR-0033 is re-scoped for the picker: its list is one file the site
// serves once, because the same list on every page was the release's
// largest repeated item (audit, 30 September 2026). The page's own
// destinations still travel in it, and nothing else breaks when this
// request does not arrive -- the branch under the picker says what the
// page is instead of offering a control that opens nothing.
if (window.TBE_STATIONS) {
  DATA.stations = window.TBE_STATIONS.filter(
    (station) => !DATA.origin || station.crs !== DATA.origin.crs
  );
}
const rows = document.getElementById("rows");
const budget = document.getElementById("budget");const budgetNumber = document.getElementById("budgetNumber");const budgetCeilingNote = document.getElementById("budgetCeiling");
const budgetField = document.getElementById("budgetField");
// Q2: the railcard is a select over the reviewed collection rather than one
// checkbox for one card. Its options are written from the payload below, so the
// control can only ever offer a card this build priced.
const railcardSelect = document.getElementById("railcardSelect");
const railcardChoice = document.getElementById("railcardChoice");
// The browser remembers the reader's card between pages. The key is
// per-origin because a reader from one station is answering the same question
// as a reader from another, and a stored card must not travel to a page whose
// feed priced nothing for it.
const RAILCARD_MEMORY = "tbe.railcard.";
// The one drawn disclosure mark, in the script as well as in the markup. The
// filter bar's chevron is written into the HTML at build time; a row's chevron
// is built when the reader opens the list, so the script needs the same path.
// Both come from the one CHEVRON constant below, because two drawings of a
// chevron is one too many marks to keep in step.
const CHEVRON = __CHEVRON_JS__;
let rememberedCard = null;
try {
  rememberedCard = window.localStorage.getItem(RAILCARD_MEMORY + DATA.origin.crs);
} catch (error) {
  // A browser with storage blocked still gets the control; it just asks again.
  rememberedCard = null;
}

// The collection the page offers, keyed by the code the feed priced it under.
const railcards = (DATA.railcards || []).reduce((all, card) => {
  all[card.key] = card;
  return all;
}, {});
const railcardKeys = Object.keys(railcards);
const noCard = () => railcardSelect.value === "";

// The options are written from the payload, so the control lists the cards this
// build actually priced and nothing else. This runs before the address is read
// (ADR-0052): a card named in a shared link is applied to a select that already
// has an option for it, and a card this feed does not price is dropped rather
// than read as one the reader holds.
if (railcardKeys.length) {
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No railcard";
  railcardSelect.append(none);
  for (const key of railcardKeys) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = railcards[key].label;
    railcardSelect.append(option);
  }
  // A remembered card is applied only when this page prices it, so a reader who
  // chose a card on a page that offered it is not silently moved onto a
  // different card where it is absent.
  if (rememberedCard && railcardSelect.querySelector('option[value="' + rememberedCard + '"]')) {
    railcardSelect.value = rememberedCard;
  }
}

// The party a chosen card covers, from the feed's own records for it. A card
// that needs two travellers cannot price one reader's journey, and the page
// says so in the list rather than offering a number nobody could buy: the
// option is there and marked, and cannot be chosen.
function cardCoversParty(card) {
  const adults = unit() === "party" ? 2 : 1;
  return card.minAdults <= adults && adults <= card.maxAdults;
}
const summary = document.getElementById("summary");
const empty = document.getElementById("empty");
const serviceDayBar = document.getElementById("serviceDayBar");
const serviceDaySelect = document.getElementById("serviceDay");
const serviceDayHelp = document.getElementById("serviceDayHelp");

// The day the Time and Changes columns are reporting, as an index into
// DATA.serviceDays. Zero is the build's own day, which is what every one of
// these surfaces said before the reader could choose, so the page opens on the
// day it has always opened on.
let serviceDayIndex = 0;
// Put a day on the control and in the state the table reads. One function for
// every caller, because the reader can ask for a day two ways -- the control,
// or Back -- and a page where only one of them moves the table is a page whose
// address and its table disagree. It only records the day: rendering and the
// address are the caller's, so this is safe to call from applyState, which
// reads the address before the control has written its options, and safe to
// call again afterwards without rendering twice.
function setServiceDay(index) {
  const days = DATA.serviceDays || [];
  const wanted = Math.min(Math.max(Number(index) || 0, 0), Math.max(days.length - 1, 0));
  serviceDayIndex = wanted;
  // The control has no options until the block below writes them, which is
  // after the address is read, so a link's day is recorded first and the
  // control is pointed at it once it exists.
  if (serviceDaySelect && serviceDaySelect.options.length) {
    serviceDaySelect.value = String(wanted);
  }
  return wanted;
}
// A day the reader chose on this page, which moves the table, the dock and the
// address together. A result set that changed under the reader starts again at
// its first page, and the dock is redrawn because a shortlisted row showing the
// build's day beside a table showing the chosen one is the page contradicting
// itself.
function chooseServiceDay(index) {
  setServiceDay(index);
  currentPage = 1;
  render();
  renderShortlist();
  writeUrl();
}
const more = document.getElementById("more");
const destinationTypeInputs = Array.from(document.querySelectorAll('input[name="destinationType"]'));
const destinationType = document.getElementById("destinationTypes");
const PAGE_SIZE = 20;
let currentPage = 1;
const pagination = document.getElementById("pagination");
const previousPage = document.getElementById("previousPage");
const nextPage = document.getElementById("nextPage");
const pageStatus = document.getElementById("pageStatus");
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
  const card = noCard() || !railcards[railcardSelect.value]
    ? "0 railcard"
    : "1 railcard (" + railcards[railcardSelect.value].label + ")";
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

function matches(station, needle) {
  if (!needle) return true;
  return station.name.toLowerCase().includes(needle) ||
    station.crs.toLowerCase().startsWith(needle);
}

function ticketMode() {
  return document.querySelector('input[name="ticketMode"]:checked').value;
}
// One place that knows which payload list each ticket mode shows, so the
// count in a message cannot drift from the list the table is built from.
const MODE_LISTS = {
  return: "destinations",
  single: "singleDestinations",
  anytime: "anytimeDestinations",
};
// Q4 (ADR-0044): the page opens on the cheapest fare
// of any ticket type, because "where can I get to for this much" is the
// question the reader arrived with, and a list of one ticket type answers it
// with a number that is often not the fare they can buy. The three named sets
// above stay, as the filters for a reader who wants one kind of fare.
//
// The list is composed here rather than in the build, so it costs no payload
// bytes -- and because which row is cheapest depends on who the price is for,
// it is composed for the party size and the card on screen rather than once.
const CHEAPEST_MODE = "cheapest";
function cheapestDestinations() {
  const cheapest = new Map();
  for (const key of Object.values(MODE_LISTS)) {
    for (const destination of DATA[key] || []) {
      const held = cheapest.get(destination.crs);
      // The card price decides which fare is cheapest, and the standard
      // breaks a tie. Without the tie-break a card that made two fares equal
      // silently swapped the row, and the cell then named a standard fare the
      // reader had not been shown: an outbound single at 375p became a return
      // at 380p the moment a card was ticked.
      if (!held || isCheaperThan(destination, held)) cheapest.set(destination.crs, destination);
    }
  }
  return Array.from(cheapest.values());
}
// Cheaper for this reader, then cheaper to begin with. Both numbers, so the
// answer does not depend on the order the payload happens to list things in.
function isCheaperThan(candidate, held) {
  const price = priceOf(candidate);
  const other = priceOf(held);
  if (price !== other) return price < other;
  return standardPrice(candidate) < standardPrice(held);
}
// The fare before any card is applied, which is the number the cell names as
// the standard one a discount came from.
function standardPrice(destination) {
  return unit() === "party" ? destination.partyPence : destination.adultPence;
}
function activeDestinations() {
  const mode = ticketMode();
  if (mode === CHEAPEST_MODE) return cheapestDestinations();
  return DATA[MODE_LISTS[mode]] || [];
}
function modeCount(mode) {
  if (mode === CHEAPEST_MODE) return cheapestDestinations().length;
  return (DATA[MODE_LISTS[mode]] || []).length;
}
// The fare a row is priced as, in the words the build's own price-quality
// phrases use. The cheapest list holds one fare per place, so this is what
// names the ticket on a row the reader chose by price rather than by type.
function ticketName(destination) {
  if (destination.tickets) return "Two tickets";
  if (destination.isAdvance) return "Advance single";
  if (destination.quality === "unrestricted Anytime Day Return") return "Unrestricted Anytime Day Return";
  if (destination.quality === "outbound single") return "Standard outbound single";
  return "Standard return";
}
// The fare a price belongs to, for everywhere a price is carried off the
// page: the shortlist, the copied shortlist, and a row's own handoff. The
// cheapest list holds one fare per place and can hold a different fare on
// every row, so it names the ticket on the row; a named list holds one kind
// of fare, so it names the list. One helper rather than the same decision
// written three times, because the count line already names the mix of the
// cheapest list (mixPhrase) and a shortlist that named a different fare from
// the count line beside it would be the page disagreeing with itself.
function fareName(destination) {
  return ticketMode() === CHEAPEST_MODE ? ticketName(destination) : modeLabels()[ticketMode()];
}
// The mix of ticket types in a list, for the count line. A list of one kind is
// the case this exists for rather than the case it stays quiet about: on the
// real Grantham page every one of the 101 opening rows is a single, and "cheapest
// first" beside a control named "Cheapest of any type" does not tell a reader
// why no return is on the page.
const MIX_WORDS = {
  "outbound single": "single",
  "unrestricted Anytime Day Return": "Anytime Day Return",
};
function mixPhrase(destinations) {
  const counts = new Map();
  for (const destination of destinations) {
    const word = MIX_WORDS[destination.quality] || "return";
    counts.set(word, (counts.get(word) || 0) + 1);
  }
  if (!counts.size) return "";
  return ": " + listWords(Array.from(counts.entries()).map(
    ([word, count]) => count + " " + (count === 1 ? word : word + "s")));
}
function budgetCeiling() {
  // The ceiling is the most the reader can be asked to consider, and the price
  // on a row depends on who it covers: two adults cost twice one. A ceiling set
  // by the single fare is therefore a budget nobody reading the party price
  // could ever type -- on a page with one destination it caps the budget at that
  // destination's adult fare, and the "Two adults" control then shows nothing at
  // any budget the page allows. Found by sweeping a published two-station site.
  //
  // The railcard is left out on purpose: it makes prices lower, so including it
  // would move the ceiling down the moment the box was ticked, clamping a
  // budget the reader had already chosen.
  const party = unit() === "party";
  return Math.max(1, Math.ceil(Math.max(0, ...activeDestinations().map((d) => (party ? d.partyPence : d.adultPence))) / 100));
}

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

// Prices are always two decimal places. The pound sign lines up down the
// column, which is the whole point of a price-first list, and £8.70 is easier
// to compare with £8.65 than £8.70 is with £9.
const money = (pence) => "£" + (pence / 100).toFixed(2);
const duration = (minutes) => {
  if (minutes === null || minutes === undefined) return "-";
  const hours = Math.floor(minutes / 60);
  return hours ? hours + "h " + String(minutes % 60).padStart(2, "0") + "m" : minutes + "m";
};
const clock = (minutes) => {
  const hour = Math.floor(minutes / 60) % 24;
  return String(hour).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0");
};

function unit() {
  return document.querySelector('input[name="unit"]:checked').value;
}
function priceOf(destination) {
  const party = unit() === "party";
  const base = party ? destination.partyPence : destination.adultPence;
  const card = chosenCard(destination);
  if (card) {
    const cardTotal = card.pricePence * (party ? 2 : 1);
    return Math.min(base, cardTotal);
  }
  return base;
}
// The chosen card's decision for one row, or null when none is chosen, this
// row cannot price it, or the card does not cover the party on screen. A card
// the feed blocked for a fare has no price and is not offered as one.
function chosenCard(destination) {
  if (noCard()) return null;
  const card = destination.railcards && destination.railcards[railcardSelect.value];
  if (!card || card.pricePence === null || card.pricePence === undefined) return null;
  const chosen = railcards[railcardSelect.value];
  return chosen && cardCoversParty(chosen) ? card : null;
}
// Q3: with the card ticked the cell shows what the reader would pay *and* the
// standard fare it came from, so a discounted number never stands alone. With
// the box clear there is one price and no second number, because there is one
// price.
function priceCell(destination) {
  const cell = document.createElement("td");
  cell.className = "num";
  cell.dataset.label = "Price";
  const standard = standardPrice(destination);
  const price = priceOf(destination);
  const amount = document.createElement("span");
  amount.className = "price";
  amount.textContent = money(price);
  cell.append(amount);
  if (price < standard) {
    const was = document.createElement("span");
    was.className = "was";
    was.textContent = " " + money(standard) + " standard";
    cell.append(was);
  }
  return cell;
}
// S15: a railcard covers a named number of adults travelling together, so it
// is a constraint on the party rather than a discount a solo reader can tick.
// The number is the feed's own record for each card rather than a rule this
// page invented, and a card that cannot cover the party on screen is taken out
// of the list rather than left there to be picked and then ignored.
function syncRailcardParty() {
  const help = document.getElementById("railcardHelp");
  if (!railcardKeys.length) {
    // The sentence stays and says why: "standard fares" with no explanation is
    // the claim the whole page rests on, and a reader who owns a 16-25 card is
    // owed the reason their card is not in the list.
    if (help) {
      help.textContent = "This feed prices no reviewed railcard, so these are standard fares.";
      help.hidden = false;
    }
    if (railcardChoice) railcardChoice.hidden = true;
    railcardSelect.disabled = true;
    return;
  }
  if (railcardChoice) railcardChoice.hidden = false;
  // A card that cannot price the party on screen is removed from the list
  // rather than left there to be picked and then ignored. The feed's own
  // records decide, so the page is not inventing a rule about who travels.
  //
  // The list is rebuilt rather than filtered in place, because the party
  // control and the card control are two answers to one question and the second
  // has to follow the first. The earlier version computed the offered list and
  // then left the options alone, so a party of two was still offered a card the
  // feed says prices one traveller; the browser suite found it by asking which
  // options a party of two can see.
  //
  // Every card this build priced is listed, including the ones that cannot
  // price the party on screen. They used to be removed, and the one card the
  // default page lost that way was Two Together -- two adults exactly, on a
  // page showing one -- so a reader who owns it could not find out the page
  // prices it at all. The card is listed and struck out of choosing instead,
  // which keeps ADR-0052's actual guarantee: a disabled option cannot hold a
  // value, so nothing downstream can read a card price nobody could buy. The
  // sentence in the option is the feed's own bound, so the reason is on screen
  // rather than inferred from an absence.
  const adults = unit() === "party" ? 2 : 1;
  const wanted = railcardSelect.value;
  railcardSelect.replaceChildren();
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No railcard";
  railcardSelect.append(none);
  const offered = [];
  for (const key of railcardKeys) {
    const card = railcards[key];
    const option = document.createElement("option");
    option.value = key;
    if (cardCoversParty(card)) {
      option.textContent = card.label;
      offered.push(key);
    } else {
      option.textContent = card.label + (adults < card.minAdults
        ? " (needs " + card.minAdults + " adults)"
        : " (covers up to " + card.maxAdults + " adult" + (card.maxAdults === 1 ? "" : "s") + ")");
      option.disabled = true;
    }
    railcardSelect.append(option);
  }
  // The reader's choice survives the rebuild when the party on screen still
  // allows it, and is cleared when it does not.
  railcardSelect.value = offered.includes(wanted) ? wanted : "";
  railcardSelect.disabled = offered.length === 0;
  if (!help) return;
  if (noCard()) {
    help.textContent = "No railcard selected, so these are standard fares. Choose the card you " +
      "hold to price the journey with it; this browser will remember your choice.";
    return;
  }
  const chosen = railcards[railcardSelect.value];
  const covers = "The " + chosen.label + " in this feed covers " + chosen.minAdults + " to " +
    chosen.maxAdults + " adults";
  help.textContent = covers + ", which matches the party on screen. " + chosen.eligibleCount +
    " destinations receive a lower price with it; open a row's own details for the minimum " +
    "fare and the conditions the feed applies.";
}

function selectedDestinationTypes() {
  return new Set(destinationTypeInputs
    .filter((input) => input.value !== "all" && input.checked)
    .map((input) => input.value));
}
function matchesType(destination, wantedTypes) {
  if (wantedTypes.size === 0) return true;
  const types = destination.destinationTypes || [destination.destinationType];
  return types.some((type) => wantedTypes.has(type));
}
function typeLabel() {
  const labels = destinationTypeInputs
    .filter((input) => input.value !== "all" && input.checked)
    .map((input) => input.parentElement.textContent.trim().toLowerCase());
  // "or", not "and": two selected types show the union, and a message that
  // said "and" would describe a filter the page does not apply.
  return labels.length > 1 ? " in " + labels.join(" or ") : labels.length ? " in " + labels[0] : "";
}

// S20: how many of the destinations in the list the reader is looking at are
// inside the budget and carry this type. A chip that can only ever return
// nothing is a broken control; a chip that says it would return nothing is a
// decision the reader gets to make.
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
  for (const input of destinationTypeInputs) input.checked = input.value === "all";
  currentPage = 1;
  render();
  writeUrl();
}
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
function stationInFeedMessage(station) {
  return station.name + " (" + station.crs + ") is in the feed, but this origin has no qualifying " +
    "return or single fare flow to it in this download.";
}
// A chip is offered when a destination in the list the reader is looking at
// carries it. The build offers one from the union of the three ticket modes,
// because it cannot know which a reader will pick, and a chip that can only
// ever return nothing reads as a broken control: on the real Grantham page every
// heritage destination was an outbound single, so return mode offered a
// heritage chip that filtered to no rows at all. So the chips are narrowed to
// the active list, and a chip that disappears takes its selection with it --
// a hidden chip left checked keeps filtering with nothing to show for it.
function syncDestinationTypeChips() {
  const offered = new Set();
  for (const destination of activeDestinations()) {
    for (const type of destination.destinationTypes || [destination.destinationType || "other"]) {
      offered.add(type);
    }
  }
  // C20: a facet present in only one ticket mode used to be silently unchecked
  // when the mode changed, so switching back to the mode the reader had chosen
  // it in showed "All" and no explanation. Each mode now keeps its own
  // selection, and switching restores it, so intent survives the round trip.
  const mode = ticketMode();
  // syncDestinationTypeChips() runs on every render, not only on a mode
  // change, so "the mode changed" is decided once here and the announcement
  // below is tied to it. Without this the same message would be re-announced
  // on every budget drag.
  const modeChanged = lastSyncedMode !== null && lastSyncedMode !== mode;
  if (modeChanged) {
    typeSelectionsByMode[lastSyncedMode] = Array.from(selectedDestinationTypes());
  }
  const all = destinationTypeInputs.find((input) => input.value === "all");
  const dropped = [];
  for (const input of destinationTypeInputs) {
    if (input.value === "all") continue;
    const present = offered.has(input.value);
    const chip = input.closest("label");
    if (chip) chip.hidden = !present;
    if (!present && input.checked) {
      input.checked = false;
      dropped.push(chipLabel(input.value));
    }
  }
  // Restore what the reader chose the last time they were in this mode, minus
  // anything this mode cannot offer. A mode reached for the first time keeps
  // whatever the reader has selected now, which is what the previous behaviour
  // did too.
  const remembered = typeSelectionsByMode[mode];
  const restored = [];
  if (modeChanged && remembered && remembered.length) {
    let anyRestored = false;
    for (const input of destinationTypeInputs) {
      if (input.value === "all") continue;
      const wanted = remembered.includes(input.value) && offered.has(input.value);
      if (wanted) { input.checked = true; anyRestored = true; restored.push(chipLabel(input.value)); }
    }
    if (anyRestored && all) all.checked = false;
  }
  if (!all || !all.checked) {
    const selected = destinationTypeInputs.some(
      (input) => input.value !== "all" && input.checked);
    if (!selected && all) all.checked = true;
  }
  lastSyncedMode = mode;
  if (modeChanged) announceFacetChange(dropped, restored, mode);
}
const typeSelectionsByMode = Object.create(null);
let lastSyncedMode = null;
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
    parts.push("Cleared " + listWords(dropped) + " — " + modeName +
      " has no destination of " + (dropped.length === 1 ? "that type" : "those types") +
      " from this station.");
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

// A mode can be empty while other modes are not. An Anytime Day Return is sold
// on a handful of interurban routes, so most origins have none, and the page
// used to return early and leave the reader looking at the previous mode's
// rows with every destination-type chip hidden -- which reads as a broken
// control, not as an answer. So an empty mode now says so, clears the table,
// and says where the fares this origin does have are.
function modeLabels() {
  const labels = {};
  for (const input of document.querySelectorAll('input[name="ticketMode"]')) {
    labels[input.value] = input.parentElement.textContent.trim();
  }
  return labels;
}
const MODE_WHY = {
  anytime: "An Anytime Day Return is valid on any train, so sellers offer it on only some routes and most stations have none.",
};
// C07: a reader has to be told what the open set contains *before* they
// compare two numbers in it, so the note sits above the table rather than
// inside the methodology accordion, and is read at the moment the comparison
// is made. Q4 then changed which set is open: the page opens on the cheapest
// fare of any type, whose caveats are the mix itself and the advance single
// inside it, and the reviewed set this note was written for is now one of the
// filters beside it. The wider "any return" set is offered for the same reason
// it always was -- a restricted off-peak fare is a real price a reader can buy
// -- and whichever set is open, a restricted fare is not interchangeable with
// an unrestricted one, and the page cannot decode the feed's own validity text.
const MODE_NOTE = {
  cheapest: "Each row is the cheapest fare of any ticket type, so this list mixes singles and returns. An advance fare needs a chosen train; a restricted fare's condition is in the row's details.",
  anytime: "Unrestricted Anytime Day Returns: valid on any train on the route, so these prices compare with each other directly.",
  return: "Every standard-class return the feed prices, restricted off-peak and advance included. A restricted fare is not valid on every train or at every time — its condition is in the row's details.",
  single: "Outbound singles rather than returns. An advance single needs a chosen train, and is labelled where it appears.",
};
function renderModeNote() {
  const note = document.getElementById("modeNote");
  if (!note) return;
  note.textContent = MODE_NOTE[ticketMode()] || "";
}
function emptyModeMessage() {
  const labels = modeLabels();
  const mode = ticketMode();
  const elsewhere = [CHEAPEST_MODE, "return", "single", "anytime"]
    .filter((other) => other !== mode && modeCount(other))
    .map((other) => labels[other] + " has " + modeCount(other));
  const why = MODE_WHY[mode] ? " " + MODE_WHY[mode] : "";
  const where = elsewhere.length
    ? " " + elsewhere.join(" and ") + (elsewhere.length === 1 ? " destination." : " destinations — switch modes to see them.")
    : "";
  return "No " + labels[mode] + " fares were found from " + DATA.origin.name + " in this download." + why + where;
}
// S28: an empty list is a decision the reader has not finished making, so it
// says which of the choices on this page would change the answer and offers
// each as a control. Every move is offered only when it is true for this
// page's own rows -- a "raise the budget" button on a page where the budget
// already covers everything is a control that does nothing.
// The empty-mode case has one recovery this page can offer -- another ticket
// type that does have fares from here -- and it is the same control as
// everywhere else, so a reader who is offered a move is never offered one that
// does nothing.
// S29: "every destination" is a claim about the feed, so the page counts what
// it dropped and what it cannot classify. A destination whose type is not in
// the reviewed registry is still priced and still listed -- it is simply one no
// type chip can select, and saying so is the difference between a complete
// claim and a true one. Written in one place because the ticket-mode switch
// and the first render both rewrite this line.
// S33: how old the numbers are, beside the numbers. Two ages, because they
// answer different questions: a fare download is a snapshot of prices that
// change without expiring, and a timetable is current for the window it says
// it covers. Both are judged against the reader's own clock, not the build's,
// so a page published in March says in June that it is five months old. A
// build with no timetable says so plainly: that is a choice about what to
// compute, not a feed that has gone stale.
function renderFreshness() {
  const line = document.getElementById("freshness");
  if (!line) return;
  const parts = [];
  // Whole calendar days, not elapsed 24-hour periods: a timetable that starts
  // yesterday has not "not started yet" because it started at ten yesterday
  // morning, and a reader reading this at breakfast should get the same answer
  // as one reading it at midnight.
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  // Positive is in the past, negative is in the future.
  const days = (iso) => Math.round((today - Date.parse(iso + "T00:00:00Z")) / 86400000);
  if (DATA.feedDate) {
    const age = days(DATA.feedDate);
    const limit = DATA.staleAfterDays;
    // A download dated in the future is a clock problem, not a fresh feed, and
    // is named as one rather than counted as negative days old.
    const when = age < 0
      ? "dated after today, so the clock or the download is wrong"
      : age + (age === 1 ? " day" : " days") + " old";
    const verdict = age < 0
      ? ""
      : age <= limit
        ? "within the " + limit + "-day freshness threshold"
        : "past the " + limit + "-day freshness threshold, so check the fare before you travel";
    parts.push("Prices are from a fares feed downloaded " + humanDate(DATA.feedDate) + ", " + when +
      (verdict ? " and " + verdict : "") + ".");
  }
  if (!DATA.timetableFrom) {
    parts.push("This build prices fares only: no timetable was supplied, so no times or changes are shown.");
  } else {
    // days() is today minus the date, so a start still ahead is negative and
    // an end already past is positive.
    const starts = days(DATA.timetableFrom);
    const ends = days(DATA.timetableTo);
    const verdict = starts < 0
      ? "which has not started yet"
      : ends > 0
        ? "which has ended, so these times describe services that no longer run"
        : "which includes today";
    parts.push("Times are from a timetable covering " + humanDate(DATA.timetableFrom) + " to " +
      humanDate(DATA.timetableTo) + ", " + verdict + ".");
  }
  line.textContent = parts.join(" ");
  line.hidden = !parts.length;
}

// The conditions printed in the table are the fares feed's own wording, from
// the same publication as the prices. The reference feed is a second opinion,
// published on its own schedule, and this is the claim the page makes about it.
//
// Every branch says what was compared. "All of them" with nothing behind it
// would be a claim the build never checked, so a check that compared no codes
// is written as not checked, and an unreadable reference feed is written as
// unreadable rather than passed over in silence.
//
// The count is the conditions *the fares in this build can carry*, which is a
// bigger set than the rows on screen and deliberately so. Naming only the codes
// the reader's current budget happens to surface would make the sentence change
// meaning when they drag the slider -- and would leave a fare carrying a
// retired condition unremarked, because the page cannot know a budget the
// reader has not chosen yet. Taken from the flows, the set holds at every
// budget, party and ticket mode, so a reader who later sees one of these
// conditions was warned before they saw it.
function renderRestrictionReference() {
  const line = document.getElementById("restrictionReference");
  if (!line) return;
  const ref = DATA.restrictionReference;
  if (!ref) { line.hidden = true; return; }
  // Every date is written through dayPhrase, which returns "" for a date it
  // cannot read. A clause is then built by concatenation, so a missing date
  // removes the clause rather than printing a broken one.
  const published = dayPhrase(ref.published);
  const checked = ref.checkedAt ? dayPhrase(ref.checkedAt) : "";
  const checkedClause = checked ? ", last checked" + checked : "";
  const text = (() => {
    if (ref.status === "absent") {
      return "Ticket conditions are quoted from the fares feed. No portal reference feed was checked.";
    }
    if (ref.status === "unknown") {
      return "Ticket conditions are quoted from the fares feed. The portal's own restriction feed could not be checked"
        + (ref.note ? " (" + ref.note + ")" : "")
        + ", so nothing here has been confirmed against it"
        + (published ? "; it was published" + published : "") + ".";
    }
    if (ref.status === "unpublished") {
      const codes = (ref.unlisted || []).join(", ");
      // The comma belongs to the publication clause, so the verb phrase starts
      // with a space. Built as "feed, published <date>, no longer lists" when
      // there is a date and "feed no longer lists" when there is not, which is
      // what the portal actually sends: no Last-Modified on these feeds, so the
      // clause is usually absent and a leading comma would be a comma splice.
      return "Ticket conditions are quoted from the fares feed. The National Rail Data Portal's own "
        + "restriction feed"
        + (published ? ", published" + published : "")
        + " no longer lists " + ref.missing + " of the " + ref.compared
        + " conditions on this page (" + codes + ")" + checkedClause
        + ". The wording below is the fares feed's, which is the same publication the prices are from.";
    }
    // The publication clause belongs to the publication date, so the verb
    // phrase carries its own connector. Built as "feed, published <date>, still
    // publishes" when the portal gave a date and "feed still publishes" when it
    // did not -- which is the usual case, because these feeds carry no
    // Last-Modified: joining the absent clause with a comma printed "restriction
    // feed, still publishes all 10", a splice a reader sees on the real page.
    return "Ticket conditions are quoted from the fares feed"
      + (DATA.feedDate ? ", downloaded" + dayPhrase(DATA.feedDate) : "")
      + ". The National Rail Data Portal's own restriction feed"
      + (published ? ", published" + published + ", still publishes all " : " still publishes all ")
      + ref.compared + " conditions on this page"
      + checkedClause + ".";
  })();
  line.textContent = text;
  line.hidden = !text;
}

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

function renderEmptyMode() {
  empty.replaceChildren();
  const why = document.createElement("p");
  why.textContent = emptyModeMessage();
  empty.append(why);
  const actions = document.createElement("p");
  actions.className = "empty-actions";
  for (const [mode, label] of Object.entries(modeLabels())) {
    if (mode === ticketMode() || !modeCount(mode)) continue;
    const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toggle";
    button.textContent = label + " has " + modeCount(mode);
    button.addEventListener("click", () => {
      input.checked = true;
      currentPage = 1;
      render();
      writeUrl();
    });
    actions.append(button);
  }
  if (actions.childElementCount) {
    actions.prepend(document.createTextNode("Try: "));
    empty.append(actions);
  }
}

function renderEmpty(available, wanted, cap, what) {
  empty.replaceChildren();
  if (wanted.length) return;
  const why = document.createElement("p");
  // C21: the predicate is price <= cap, so every place the budget is named
  // says "up to". "Within" and "under" both read as exclusive to a reader
  // comparing them with a fare that lands exactly on the ceiling, and the
  // summary, the empty state and the heading have to agree.
  why.textContent = "No destinations for up to " + money(cap) + " " + what + typeLabel() + ".";
  empty.append(why);
  const actions = document.createElement("p");
  actions.className = "empty-actions";
  const offer = (label, run) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toggle";
    button.textContent = label;
    button.addEventListener("click", run);
    actions.append(button);
  };
  // The cheapest destination this mode carries, whatever the budget: the
  // budget that would include it is the one number the reader is missing.
  const cheapest = available.reduce(
    (low, destination) => Math.min(low, priceOf(destination)), Infinity);
  if (Number.isFinite(cheapest) && cheapest > cap) {
    const enough = Math.ceil(cheapest / 100);
    offer("Show everything up to " + money(enough * 100), () => {
      setBudget(enough);
      currentPage = 1;
      render();
      writeUrl({ budget: true });
    });
  }
  if (selectedDestinationTypes().size) {
    offer("Clear the destination type", clearDestinationTypes);
  }
  // A pair's price is a different number, so a party the reader has not chosen
  // yet is a real way out of an empty list rather than advice.
  if (unit() === "adult" && railcardKeys.length) {
    const cheaper = activeDestinations().some((destination) => destination.partyPence <= cap * 100);
    if (cheaper) {
      offer("Price it for two adults", () => {
        document.querySelector('input[name="unit"][value="party"]').checked = true;
        currentPage = 1;
        render();
        writeUrl();
      });
    }
  }
  // Another ticket type on this origin, with its own count.
  for (const [mode, label] of Object.entries(modeLabels())) {
    if (mode !== ticketMode() && modeCount(mode)) {
      const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
      offer(label + " has " + modeCount(mode), () => {
        input.checked = true;
        currentPage = 1;
        render();
        writeUrl();
      });
    }
  }
  if (actions.childElementCount) {
    actions.prepend(document.createTextNode("Try: "));
    empty.append(actions);
  }
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
  // Before the filter is read, not after: a chip the active list cannot support
  // must not be part of what the filter is asked to match.
  syncDestinationTypeChips();
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
  const ceiling = budgetCeiling();
  budget.max = String(ceiling);
  budgetNumber.max = String(ceiling);
  // The stop is part of the budget's contract, so it is named where the
  // reader is holding the control, and it is named as a figure rather
  // than a rule: the sentence above the number is what changes, the number
  // is what the reader can predict a boundary fare against.
  budgetCeilingNote.textContent = money(ceiling * 100) + " for "
    + (unit() === "party" ? "two adults" : "one adult");
  if (Number(budget.value) > ceiling) setBudget(ceiling);
  const cap = Number(budget.value) * 100;
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
    : available.length ? "No destinations for up to " + money(cap) + " " + basis : "";
  empty.hidden = wanted.length > 0;
  renderEmpty(available, wanted, cap, basis);
  more.hidden = true;
  pagination.hidden = pageCount <= 1;
  pageStatus.textContent = "Page " + currentPage + " of " + pageCount + " of " + wanted.length +
    (wanted.length === 1 ? " result" : " results");
  previousPage.disabled = currentPage === 1;
  nextPage.disabled = currentPage === pageCount;
  renderShortlist();
}

// The destination, and nothing else: the name, the three-letter code a seller
// asks for, and the World Heritage proof where the feed names one. The station
// is the widest thing in the row, so the column takes the slack and the
// numbers beside it keep one position each.
// The way a place is held. ADR-0054 replaced a button on every row with one
// select above the table, on the grounds that twenty controls is a wall of
// controls; the reader asked for the checkbox back on each row, which is the
// other honest answer to the same problem -- the control sits beside the thing
// it acts on, and a place is held by ticking the row you are already reading
// rather than by finding its name in a list of names.
function holdCell(destination) {
  const cell = document.createElement("td");
  cell.className = "hold";
  cell.dataset.label = "Hold";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.className = "hold-box";
  // Read from the list rather than remembered per row: every render rebuilds
  // these cells, and a box that kept its own state across a mode change would
  // claim a place is held when the row is now priced as something else.
  box.checked = inShortlist(destination.crs);
  // Named per row. A column of unticked boxes is a column of controls with no
  // name of their own, and what a screen reader announces has to say which
  // place this one holds.
  box.setAttribute("aria-label", "List " + destination.name + " in the shortlist");
  box.addEventListener("change", () => {
    // The list is capped, and a refused addition says so on the strip rather
    // than adding. The browser has already ticked the box by then, and
    // renderShortlist puts every box back to what the list actually holds.
    toggleShortlist(destination.crs);
  });
  // The label is the target, not decoration: clicking anywhere in the cell
  // holds the place, which is what a 44px square means.
  const target = document.createElement("label");
  target.className = "hold-target";
  target.append(box);
  cell.append(target);
  return cell;
}
function stationCell(destination) {
  const cell = document.createElement("td");
  cell.dataset.label = "Station";
  const name = document.createElement("span");
  name.className = "station-name";
  name.textContent = destination.name;
  const code = document.createElement("span");
  code.className = "station-code";
  code.textContent = destination.crs;
  cell.append(name, " (", code, ")");
  function appendSiteProof(label, sites, titleFor) {
    if (!sites?.length) return;
    const proof = document.createElement("span");
    proof.className = "site-proof";
    proof.append(label);
    sites.forEach((site, index) => {
      if (index) proof.append("; ");
      const link = document.createElement("a");
      link.href = site.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = site.name;
      const title = titleFor ? titleFor(site) : "";
      if (title) link.title = title;
      proof.append(link);
    });
    cell.append(proof);
  }
  appendSiteProof(
    "World heritage: ",
    destination.heritageSites,
    (site) => "UNESCO World Heritage List site " + site.id,
  );
  appendSiteProof("Nature sites: ", destination.natureSites);
  appendSiteProof("Coastal & seaside: ", destination.coastalSites);
  // ADR-0062: the backlog day-out sources, each a reviewed list whose proof is
  // the property, reserve or gateway the station was tagged for.
  appendSiteProof("RSPB reserves: ", destination.rspbSites);
  appendSiteProof("National Trust: ", destination.nationalTrustSites);
  appendSiteProof("National parks and landscapes: ", destination.nationalParkSites);
  return cell;
}

// Time and Changes, in one builder because they are the same fact read twice:
// a journey this build could not find has neither a duration nor a change
// count, and saying "Unknown" beside a real duration would be a lie. S23's
// point stands -- a dash said nothing about which of three different absences
// it was, so the cell names the absence.
function journeyCell(destination, column) {
  const journey = journeyFor(destination);
  const missing = !journey.found;
  const cell = document.createElement("td");
  cell.className = missing ? "num missing" : "num";
  cell.dataset.label = column;
  // The interchange is dropped on any day but the build's own, because the
  // build holds one change-station list per row and it is that day's. Printing
  // Sunday's interchange beside Monday's change count would be a row claiming
  // two facts about two different days; the count alone is what the chosen
  // day supports. The help line under the control says so once for the table.
  if (column === "Time") {
    cell.textContent = missing ? dayAbsenceText(destination, true) : duration(journey.minutes);
    return cell;
  }
  const count = document.createElement("span");
  count.className = "changes-count";
  count.textContent = missing ? "Unknown" : changeCount(journey.changes);
  cell.append(count);
  // Q2 (ADR-0045): the station a journey changes at is the part a reader can
  // act on, and it was only ever inside a disclosure they had to open on every
  // row to find. It sits under the count now, in the column whose header is
  // the word "Changes".
  const via = serviceDayIndex === 0 ? interchangeLine(destination) : null;
  // The station sits on its own line under the count, so this cell is two
  // lines tall by design. It says so in the markup, because the check that
  // measures wrapped numbers cannot otherwise tell that from a number that
  // ran out of room.
  if (via) {
    cell.classList.add("changes");
    cell.append(via);
  }
  return cell;
}

function changeCount(changes) {
  if (changes === null || changes === undefined) return "Unknown";
  if (changes === 0) return "Direct";
  return changes === 1 ? "1 change" : changes + " changes";
}

function interchangeLine(destination) {
  const stations = destination.changeStations || [];
  if (!stations.length) return null;
  const line = document.createElement("span");
  line.className = "interchange";
  line.textContent = "via " + stations.map((station) => station.name).join(" and ");
  return line;
}

// The fare in the reader's own three words. The feed's code is a seller’s
// vocabulary -- SDR, 2AS, BPS -- and it was the column, on every row, in front
// of the one number the reader came for. It is still here, in the row's own
// disclosure under "Feed record", which is where a code belongs: available
// when it is asked for, invisible until then.
function fareTypeCell(destination) {
  const cell = document.createElement("td");
  cell.className = "fare-type";
  cell.dataset.label = "Fare type";
  cell.dataset.kind = destination.isAdvance ? "advance"
    : destination.restrictionCode ? "restricted" : "regular";
  const kind = document.createElement("span");
  kind.className = "fare-kind";
  kind.textContent = fareTypeWord(destination);
  cell.append(kind);
  cell.title = fareSummary(destination);
  return cell;
}

function fareTypeWord(destination) {
  if (destination.tickets) return "Two tickets";
  if (destination.isAdvance) return "Advance";
  if (destination.restrictionCode) return "Restricted";
  return "Regular";
}

// The one word beside the code, and only where the row differs from its
// neighbours: a fare that needs a second look says so, and a fare that does not
// stays quiet rather than repeating a sentence the mode note already made.
function fareFlag(destination) {
  if (destination.isAdvance) return "advance";
  if (destination.restrictionCode) return "restricted";
  return "";
}

// The fare in words, inside the row's own disclosure. It is a full sentence
// because it is the only thing the panel says before the condition: a fragment
// with a semicolon in it was read as two facts of equal weight, and the second
// half of it ("price and availability can change") was the one a reader needed
// before deciding whether to trust the price at all.
function fareSentence(destination) {
  if (destination.tickets) {
    const via = destination.tickets[0].toName;
    // A through train priced in two parts (ADR-0061 wider) never leaves the
    // train at the pricing split, so "changing at" would be a lie. A journey
    // that does change keeps the change wording.
    if ((destination.changes || 0) === 0) {
      return "Two tickets, priced via " + via +
        " (stay on the train): the price is the two fares added together.";
    }
    return "Two tickets, changing at " + via +
      ": the price is the two fares added together.";
  }
  if (destination.isAdvance) {
    return "Advance single: you choose the train, and the price and availability can change.";
  }
  if (destination.restrictionCode) return "Restricted fare — the condition is below.";
  if (destination.quality === "outbound single") return "Standard outbound single, with no conditions in the feed.";
  if (destination.quality === "unrestricted Anytime Day Return") {
    return "Unrestricted Anytime Day Return: valid on any train on the route.";
  }
  return "Standard return fare, with no conditions in the feed.";
}

// What the row's title attribute says, in the same voice as the sentence: the
// flag explained without repeating the panel behind it.
function fareSummary(destination) {
  if (destination.tickets) {
    const via = destination.tickets[0].toName;
    if ((destination.changes || 0) === 0) {
      return "Two tickets, bought separately, priced via " + via + " (stay on the train).";
    }
    return "Two tickets, bought separately, changing at " + via + ".";
  }
  if (destination.isAdvance) return "Advance single: valid only on a qualifying train, and the price and availability can change.";
  if (destination.restrictionCode) return destination.restrictionDescription || "This fare has a restriction code; the condition is in this row's details.";
  return "No fare restriction code is attached to this fare.";
}

// Q2 (ADR-0045): a journey with a change is where a split ticket can undercut
// the through fare, and the station it would change at is the part a reader can
// act on. The page states the possibility and no price: the feed prices flows,
// not itineraries, so which two tickets are cheaper is not in this data.
//
// Only on the build's own day, for the same reason the interchange line in the
// Changes column is: the change stations are that day's, and the note points at
// the station printed above it. On any other day the Changes cell prints the
// chosen day's count and no station, so a note still saying "the station above"
// would point a reader at a row that no longer names one, and a journey that
// reads Direct beside a claim that it changes somewhere is a row contradicting
// itself. The same suppression, and for the same reason.
function splitNote(destination) {
  if (serviceDayIndex !== 0) return null;
  // A two-ticket row (ADR-0061) is the split this note describes, priced, and
  // it has no through fare for the note to compare against.
  if (destination.tickets) return null;
  const stations = destination.changeStations || [];
  if (!stations.length) return null;
  // The station itself is named in the Changes column now, so this says only
  // the thing that is still worth saying and is nowhere else on the page: the
  // through fare is not the cheapest way to buy this journey, and this page
  // cannot tell you which two tickets would be.
  const note = document.createElement("p");
  note.className = "split";
  note.textContent = "A split ticket — one ticket to the station above and " +
    "another from it — can sometimes cost less than this through fare. " +
    "This page prices the through fare only.";
  return note;
}

// ADR-0061: a place the feed prices only in two parts is one row, and the row
// is two purchases. Each ticket is named with its own price and its own
// condition, a ticket with none says so, and the panel says what a static page
// cannot know: whether both are on sale together. None of it depends on the
// day picked above, because neither price does (ADR-0060).
function twoTicketList(destination) {
  const list = document.createElement("ul");
  list.className = "two-tickets";
  for (const ticket of destination.tickets) {
    const item = document.createElement("li");
    item.dataset.ticket = ticket.ticket;
    item.textContent = ticket.fromName + " to " + ticket.toName + ": " + money(ticket.adultPence) +
      ", ticket " + ticket.ticket + ", " + (ticket.restrictionCode
        ? "restriction " + ticket.restrictionCode + (ticket.restrictionDescription ? " (" + ticket.restrictionDescription + ")" : "")
        : "no restriction") + ".";
    list.append(item);
  }
  return list;
}
function twoTicketCaveat() {
  const note = document.createElement("p");
  note.className = "two-ticket-note";
  note.textContent = "These are two separate purchases. This page cannot promise both are on sale " +
    "together, so check each before you buy.";
  return note;
}

// The FARE and CONDITIONS columns, moved into the panel the row already had
// rather than deleted: the condition is the reader's, the twenty repetitions of
// it were not (finding, 29 September 2026).
function fareDetails(destination) {
  const panel = document.createElement("div");
  panel.className = "restriction";
  const restricted = Boolean(destination.restrictionCode);
  panel.dataset.status = restricted ? "restricted" : "unrestricted";
  const fare = document.createElement("p");
  fare.className = "fare-line";
  fare.textContent = fareSentence(destination);
  panel.append(fare);
  // S19: what the reader has to know to rule the fare in or out, in sentences.
  // Said only when there is a condition to rule out: an unrestricted fare used
  // to open with a second paragraph saying there was nothing to read, which is
  // the same information as silence, said in a line. A two-ticket row says
  // each ticket's condition in its own line of the list instead.
  if (destination.tickets) {
    panel.append(twoTicketList(destination), twoTicketCaveat());
  } else if (restricted) {
    const readable = document.createElement("p");
    readable.className = "condition";
    readable.textContent = destination.restrictionDescription ||
      "This fare carries a restriction code; check the seller's conditions before buying.";
    panel.append(readable);
  }
  const split = splitNote(destination);
  if (split) panel.append(split);
  // The railcard, when one is in play, and the feed's record of the fare --
  // codes, restriction, route, and the exact RR rule that decided the card's
  // price. All of it is the explanation of the number at the top of the row, so
  // all of it is in the one place the reader opened to find the number.
  const card = cardNote(destination);
  if (card) panel.append(card);
  panel.append(feedRecord(destination));
  panel.title = fareSummary(destination);
  return panel;
}

// C08: what the condition actually permits, in the feed's own words. A code
// and a one-line description tell a reader which fare is restricted, not
// whether the train they have in mind is one of the trains it is valid on --
// which is the thing being decided when two prices are compared. So the
// outward and return validity the feed states is printed here, next to the
// description, and the codes stay in the folded record below as audit detail.
//
// The single-mode row is a one-way ticket, so only the outward text can apply
// to it; showing a return condition beside a single would state a limit on a
// leg the ticket does not have.
function validityNote(destination) {
  if (!destination.restrictionCode) return null;
  const validity = DATA.restrictionValidity
    ? DATA.restrictionValidity[destination.restrictionCode]
    : null;
  if (!validity) return null;
  const single = destination.quality === "outbound single";
  const lines = [];
  if (validity.outwardText) lines.push("Valid outward: " + validity.outwardText);
  if (!single && validity.returnText) lines.push("Valid on the return: " + validity.returnText);
  if (!lines.length) return null;
  const note = document.createElement("span");
  note.className = "validity";
  note.append(lines.join(" "));
  return note;
}

// S19: the record as the feed states it -- ticket code, restriction code,
// route, and which price-quality the build chose it as. Folded away, because a
// reader deciding where to go needs the condition, not the vocabulary.
function feedRecord(destination) {
  const details = document.createElement("details");
  details.className = "feed-record";
  const summary = document.createElement("summary");
  summary.textContent = "Feed record";
  const list = document.createElement("dl");
  const add = (term, value) => {
    if (value === null || value === undefined || value === "") return;
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    list.append(dt, dd);
  };
  add("Ticket", destination.ticket);
  if (destination.tickets) {
    add("Restrictions", destination.tickets.map((ticket) => ticket.restrictionCode || "none").join(" + "));
  } else {
    add("Restriction", destination.restrictionCode || "none");
  }
  add("Route", destination.routeCode);
  add("Priced as", destination.quality);
  if (!journeyFor(destination).found) add("Times", dayAbsenceText(destination, false));
  // C08: what the condition permits, in the feed's own words. It was a third
  // paragraph under the row's own, in capitals, between a sentence and a code,
  // and it was the only part of the three that could not be paraphrased without
  // a licencee's risk. It is here now: still verbatim, still present, and
  // behind the record rather than in front of the decision.
  const validity = validityNote(destination);
  if (validity) {
    const dt = document.createElement("dt");
    dt.textContent = "In the feed’s words";
    const dd = document.createElement("dd");
    dd.append(validity);
    list.append(dt, dd);
  }
  const rule = railcardRuleFor(destination);
  if (rule) add("Railcard rule", rule);
  details.append(summary, list);
  return details;
}

// The exact RR rule behind the chosen card’s price on this fare, if there
// is one. It was the last line of a dialog; a rule is a record, and records
// live in the record.
function railcardRuleFor(destination) {
  if (noCard() || !railcards[railcardSelect.value]) return null;
  const details = (destination.railcards || {})[railcardSelect.value];
  if (!details || !details.rule) return null;
  const rule = DATA.railcardRules[details.rule];
  return rule ? rule.text : null;
}

function cellWithLinks(row, destination, wanted) {
  // Two controls on the row and no more: the ticket link, because buying is the
  // action and hiding it behind a second click loses the click; and the
  // expander, because the journeys are what a reader checks first and the
  // panel behind it is where the fare, the condition, the railcard drawer and
  // the handoff text live. This cell used to carry five controls on every row,
  // which is a hundred targets on page one (finding 4, 29 September 2026); the
  // shortlist toggle stays, because comparing places is a thing a reader does
  // while scanning the list rather than after opening a row.
  const cell = document.createElement("td");
  cell.dataset.label = "Tickets";
  const link = document.createElement("a");
  link.className = "buy";
  link.href = destination.link.url;
  link.rel = destination.link.rel;
  link.target = "_blank";
  link.textContent = "Tickets";
  // C13: the visible label stays the one word a price-first column can hold,
  // but a screen reader's links list used to be a column of identical "Tickets"
  // entries with no way to tell them apart. The name carries the destination,
  // and the same word is in the title so a sighted reader's tooltip agrees.
  link.setAttribute("aria-label", "Tickets for " + destination.name);
  link.title = "Tickets for " + destination.name + " — " +
    destination.link.label + " search for " + destination.crs;
  cell.append(link);
  // One disclosure per row, on every row. It used to exist only where the
  // build had times, which left a fare's condition unreachable on a
  // prices-only page. The control is now the page's own chevron rather than a
  // word, so the visible label is a mark and the accessible name is what
  // carries the words: the count where there is one, the destination either
  // way, and the fact that a fare is behind it at all. Dropping the word from
  // the face of the button is only safe because the name below keeps all of it.
  const times = destination.departures.length;
  const toggle = document.createElement("button");
  toggle.className = "toggle row-expand";
  toggle.type = "button";
  toggle.insertAdjacentHTML("beforeend", CHEVRON);
  toggle.setAttribute("aria-expanded", "false");
  // The name is the label the word used to be. WCAG 2.5.3 is about a visible
  // label being inside the accessible name, and a drawn mark is not one, so
  // what matters here is that a screen reader still says what the control is
  // and which row it belongs to.
  toggle.setAttribute("aria-label",
    (times ? times + " times and fare details for " : "Fare details for ") + destination.name);
  toggle.title = times
    ? times + " departures and the fare for " + destination.name
    : "Fare details for " + destination.name;
  toggle.addEventListener("click", () => toggleDetail(row, destination, toggle));
  cell.append(toggle);
  row.append(cell);
}

// What the railcard did to this row's price, in the row's own disclosure.
//
// It was a dialog: a button on every row, opening a panel on top of a page
// the reader was already reading, to be told a number the row beside it
// already carried. The sentences are unchanged -- they are the ones that keep
// the page honest about a card that cannot help -- but they now sit under the
// fare they explain, where the reader opened the row to look, and the feed's
// exact RR rule sits in the feed record below them with the codes.
function cardNote(destination) {
  // With no card chosen there is nothing to explain: the row is priced at the
  // standard fare, the price cell says so by not saying otherwise, and the
  // control above already reads "No railcard selected, so these are standard
  // fares". A paragraph on every expanded row repeating the page's default is
  // the noise this replaced.
  if (noCard() || !railcards[railcardSelect.value]) return null;
  const note = document.createElement("p");
  note.className = "card-note";

  const card = railcards[railcardSelect.value];
  // ADR-0061: a two-ticket row is two published fares, so a card is decided on
  // each ticket and the row's card price is the two card prices added together.
  // The reader is quoted the pair the journey is, not a card applied to half of
  // it, and a card the feed bans on either ticket is refused rather than shown
  // as a price nobody could buy.
  if (destination.tickets) {
    const pair = (destination.railcards || {})[card.key];
    if (!pair) {
      note.dataset.state = "unavailable";
      note.textContent = "This feed prices no " + card.label + " fare for this two-ticket " +
        "journey, so the row shows the two standard fares.";
      return note;
    }
    note.dataset.state = pair.state;
    if (pair.pricePence === null || pair.pricePence === undefined) {
      note.textContent = card.label + " cannot be applied to this journey, because a current DTD " +
        "RR rule bans it on one of the two tickets, so the row shows both standard fares.";
      return note;
    }
    if (pair.pricePence >= destination.adultPence) {
      // The figure first is the row's own, the same rule as a single-ticket row:
      // opening with the larger card price makes the reader hunt for theirs.
      note.textContent = "This journey is " + money(priceOf(destination)) + " per adult, and " +
        card.label + " does not reduce it. The card's own price for the two tickets is " +
        money(pair.pricePence) + " per adult" + (pair.minimumFarePence === null
          ? "."
          : ", because the minimum fare the feed applies to these tickets is " +
            money(pair.minimumFarePence) + ".");
      return note;
    }
    note.textContent = "Two tickets, and " + card.label + " applies to each one: " +
      money(pair.pricePence) + " per adult is the two card fares added together" +
      (pair.minimumFarePence === null
        ? "."
        // The figure is the two minimums added, so it is the pair's own total
        // and not a floor on one ticket: read as one, it would quote twice what
        // the feed floors each of the two tickets at.
        : ", with the feed's minimum fares on the two tickets adding to " +
          money(pair.minimumFarePence) + ".");
    return note;
  }
  const details = (destination.railcards || {})[card.key];
  if (!details) {
    note.dataset.state = "unavailable";
    note.textContent =
      "This feed prices no " + card.label + " fare to " + destination.name + ", so there is " +
      "nothing to compare it against.";
    return note;
  }

  // The rule record lives once in DATA.railcardRules and every card's row
  // carries its key, because repeating the record per row cost 388KB on the
  // heaviest real page (audit B3).
  const rule = details.rule ? DATA.railcardRules[details.rule] : null;
  const condition = rule && !rule.totalBan && rule.restrictionCode !== "none"
    ? rule.restrictionCode
    : null;
  const cardBeatsStandard = details.pricePence !== null && details.pricePence < destination.adultPence;
  const minimumClause = details.minimumFarePence === null
    ? ", and no minimum fare is current for this ticket."
    // The build floors the card's price at the minimum, so price == minimum is
    // the only way to land here, and it lands on the branches where the card
    // does help. Saying the minimum makes the fare dearer would be false there,
    // and saying it is above a discounted price the page never sent would be a
    // claim about a number nobody can see: so it says the minimum is the price.
    : details.minimumFarePence >= details.pricePence
      ? ", and the DTD minimum fare of " + money(details.minimumFarePence) +
        " is the price here, so the discount took it no lower."
      : ", and the DTD minimum of " + money(details.minimumFarePence) + " does not raise it.";

  note.dataset.state = details.state;
  // The sentences are written here rather than shipped per row per card. Six
  // cards at the build's own wording measured 2,598 bytes a row against 433
  // for one, on a page that already carries 411KB; the facts cost 98.
  if (details.state === "blocked") {
    note.textContent =
      card.label + " cannot be applied to this fare. A current DTD RR rule matches this ticket, " +
      "route or endpoint and records a total ban, so the standard fare is the only price the feed " +
      "offers here.";
  } else if (!cardBeatsStandard) {
    // The three numbers the build already sent are enough to say this. The
    // discounted price before the minimum is not one of them, and recomputing it
    // here would put a second copy of the rounding rule in the page, where it
    // could drift from the build's.
    // The figure first is the one in the row, not the card's. On a real page
    // the card's own price is often the DTD minimum -- £12.00 on a fare the
    // reader is looking at for £2.70 -- and opening a note with the larger
    // number makes the reader hunt for the one that is theirs. priceOf() is
    // the same figure the Price cell renders, so the two cannot disagree.
    note.textContent =
      "This fare is " + money(priceOf(destination)) + ", and " + card.label +
      " does not reduce it. The card's own price here is " +
      money(details.pricePence) + " per adult, because the minimum fare the feed applies to this " +
      "ticket is " + money(details.minimumFarePence) +
      ". This row is priced at the cheaper of the two, so travelling without the card would " +
      "cost the same.";
  } else if (condition) {
    note.textContent =
      card.label + " is available for this fare, subject to condition " + condition + ". No " +
      "matching total ban applies; the restriction is a travel condition rather than a card ban. " +
      "The feed’s one-third discount gives " + money(details.pricePence) + " per adult" +
      minimumClause;
  } else {
    note.textContent =
      card.label + " is available for this fare. No current RR rule matches this ticket, route or " +
      "either endpoint. The feed’s one-third discount gives " + money(details.pricePence) +
      " per adult" + minimumClause;
  }
  return note;
}

// The row's one secondary action, in the panel rather than on the row: the
// handoff text, which is what a reader pastes to a seller or a friend
// (ADR-0018). The copy text of a refused clipboard lands in this same panel,
// under the button that asked for it.
function rowActions(row, destination) {
  const tools = document.createElement("div");
  tools.className = "row-actions";
  const copy = document.createElement("button");
  copy.className = "toggle";
  copy.type = "button";
  copy.textContent = "Copy";
  copy.setAttribute("aria-label", "Copy the journey details for " + destination.name);
  copy.title = "Copy the from, to, date and party size for this row";
  copy.addEventListener("click", () => copyJourney(destination, copy, tools));
  tools.append(copy);
  return tools;
}

// C28: one panel per row, and one owner for it. It used to be two -- the times
// list and the manual-copy box each removed whatever sat under the row -- so
// opening one silently emptied the other and left its control announcing a
// state that had gone. The copy text now lands inside the panel the button that
// asked for it is already in, which leaves one region per row and one control
// whose state is written back when it closes.
let regionSeq = 0;
// Keyed on the row element, not its station code: every render replaces the
// rows, so a code-keyed map would keep detached rows and their panels alive
// and let one render's state answer for another's row.
const rowPanel = new WeakMap();
function closePanel(row) {
  const panel = rowPanel.get(row);
  if (!panel) return false;
  panel.row.remove();
  if (panel.control) panel.control.setAttribute("aria-expanded", "false");
  rowPanel.delete(row);
  return true;
}
function toggleDetail(row, destination, toggle) {
  if (rowPanel.get(row)) {
    closePanel(row);
    return;
  }
  const detail = document.createElement("tr");
  detail.className = "detail";
  const cell = document.createElement("td");
  cell.colSpan = columnCount();
  if (destination.departures.length) {
    const list = document.createElement("ul");
    for (const option of destination.departures) {
      const item = document.createElement("li");
      item.textContent = clock(option.depart) + " depart, " + clock(option.arrive) + " arrive, " +
        (option.changes ? option.changes + " change(s)" : "no change");
      list.append(item);
    }
    cell.append(list);
  }
  // The fare in words and its condition, in the panel the row already had. A
  // build with no timetable has no times to list and still has a fare to
  // explain, which is why the toggle exists on every row. The row's two
  // secondary actions live at the end of the same panel.
  cell.append(fareDetails(destination), rowActions(row, destination));
  detail.append(cell);
  detail.id = "detail-times-" + destination.crs + "-" + (regionSeq += 1);
  row.after(detail);
  rowPanel.set(row, { row: detail, control: toggle });
  toggle.setAttribute("aria-controls", detail.id);
  toggle.setAttribute("aria-expanded", "true");
}

// C04: the first sentence of the page promised the fastest journey time and
// the number of changes, and the script then removed the Time and Changes
// columns on a prices-only build without revising the sentence. So the
// sentence is written here, from the build's own fact, rather than shipped as
// prose that one shape of build is lying about.
function renderIntro() {
  const intro = document.getElementById("pageIntro");
  if (!intro) return;
  // The first-use note is a child of this paragraph, so it is replaced by
  // writing the first text node and leaving the span the build filled in alone.
  // Setting textContent on the paragraph would delete the build's sentence
  // along with the old one, and a station page with no sentence saying what the
  // station name does is exactly the page the note exists to prevent.
  const first = intro.firstChild;
  const text = DATA.hasJourneys
    ? "Every place you can reach from the station above, inside the budget, with the fastest time and the fewest changes."
    : "Every place this feed prices from the station above, inside the budget. This build has no timetable, so no times are shown.";
  if (first && first.nodeType === 3) first.nodeValue = text + " ";
  else intro.insertBefore(document.createTextNode(text + " "), intro.firstChild);
}

function provenance() {
  // An origin the build could not price is a different page from one whose
  // prices sit outside this budget, so it gets its own first sentence and its
  // own way forward — not an empty table under a slider that can't help.
  if (!DATA.destinations.length && !DATA.singleDestinations.length && !DATA.anytimeDestinations.length) {
    document.getElementById("pageIntro").hidden = true;
    const unpriced = document.getElementById("unpriced");
    const intro = "We couldn't price any journeys from " + DATA.origin.name +
      " (" + DATA.origin.crs + ") in this feed.";
    const why = DATA.unpricedNote ? " " + DATA.unpricedNote : "";
    if (DATA.stations && DATA.stations.length) {
      const link = document.createElement("a");
      link.href = DATA.baseHref;
      link.textContent = "Start from a station we do price";
      unpriced.append(intro + why + " ", link, ".");
    } else {
      unpriced.textContent = intro + why + " Nothing was priced from any station, so there is nothing to explore yet.";
    }
    unpriced.hidden = false;
    const controls = document.querySelector(".filter-bar");
    if (controls) controls.hidden = true;
    // The table scaffold and the budget's empty message answer a question
    // this page is not asking: nothing was priced, so no budget could help.
    for (const id of ["empty", "more"]) {
      const el = document.getElementById(id);
      if (el) el.hidden = true;
    }
    const table = document.querySelector("table");
    if (table) table.hidden = true;
    const summary = document.getElementById("summary");
    if (summary) summary.hidden = true;
  }

  const available = activeDestinations();
  // The same set names itself here as it does above the table: a provenance
  // line counting "return destinations" on a page showing the cheapest fare of
  // any type is the feed's vocabulary, not the reader's.
  const listed = {
    cheapest: "destinations, each on its cheapest fare of any ticket type, in the feed",
    single: "outbound single destinations in the feed",
    anytime: "unrestricted Anytime Day Return destinations in the feed",
    return: "return destinations in the feed",
  };
  const parts = [
    "Origin " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    available.length + " " + (listed[ticketMode()] || "destinations in the feed"),
  ];
  if (DATA.hasJourneys) {
    parts.push(DATA.serviceDate ? "services on " + DATA.serviceDate : "typical services in the feed");
  } else {
    parts.push("no timetable loaded, so no times are shown");
  }
  if (DATA.locationTypeSource) parts.push("destination types: " + DATA.locationTypeSource);
  document.getElementById("provenance").textContent = parts.join(" · ");
  document.getElementById("pricingBasis").textContent = DATA.pricingBasis
    ? DATA.pricingBasis + ". Use the ticket-type control to change which fares are listed, then use the budget filter to narrow the list."
    : "";
  renderCoverage();
  renderModeNote();
  renderFreshness();
  renderRestrictionReference();
  renderIntro();
  document.getElementById("railcardNote").textContent = DATA.railcardNote;
  // C03: what the reader has to do for themselves when the link is the plain
  // one, and what the link earns the site. Both sit above the table now, so
  // they are read before the first ticket action rather than after a click has
  // already left the page; the technical detail stays in the accordion.
  if (DATA.linkNote) {
    const linkNote = document.getElementById("linkNote");
    linkNote.textContent = DATA.linkNote;
    linkNote.hidden = false;
  }
  // C04: the undated-schedule caveat is a statement about the times, so it
  // belongs with the times -- the freshness line, above the table -- and not in
  // the methodology accordion, which a reader has no reason to open before
  // trusting a time.
  if (DATA.dateNote) {
    const note = document.createElement("p");
    note.className = "tag";
    note.id = "dateNote";
    note.textContent = DATA.dateNote;
    // Straight after the freshness line, whether or not that line has anything
    // to say: a hidden element still holds its place in the document, so
    // choosing the anchor by visibility would only move the note around
    // depending on a fact the reader did not ask about.
    document.getElementById("freshness").after(note);
  }
  // The licence wording, when there is some. It sits above the note rather than
  // in a comment, because a term that has to be visible is not satisfied by
  // being present in the file.
  if (DATA.attribution) {
    // One notice per paragraph: the RDG credit, the OGL sentence, and the
    // accuracy/liability notice are distinct statements with distinct
    // obligations (ADR-0020, ADR-0021), and one run-on paragraph would let
    // a reader miss the one that disclaims the numbers.
    const attribution = document.getElementById("attribution");
    for (const notice of [].concat(DATA.attribution)) {
      const p = document.createElement("p");
      p.textContent = notice;
      attribution.append(p);
    }
    attribution.hidden = false;
  }
  // Where the numbers came from, stated beside the prices rather than in the
  // footer, because where a number came from is part of the number.
  if (DATA.priceSource) {
    const line = document.getElementById("priceSource");
    const parts = ["Prices from " + DATA.priceSource];
    if (DATA.serviceDate) parts.push("feed dated " + humanDate(DATA.serviceDate));
    line.textContent = parts.join(", ") + ".";
    line.hidden = false;
  }
  if (DATA.builtAt) {
    const line = document.getElementById("buildMetadata");
    line.textContent = "Site built " + DATA.builtAt.replace("T", " ").replace("Z", " UTC") +
      (DATA.sourceFingerprint ? " · source " + DATA.sourceFingerprint : "") + ".";
    line.hidden = false;
  }
  if (DATA.tracked && DATA.disclosure) {
    const disclosure = document.getElementById("disclosure");
    disclosure.textContent = DATA.disclosure;
    disclosure.hidden = false;
    // The same sentence in the footer. The condition is the payment: a
    // commission line on a page that earns none would invent one.
    const commission = document.getElementById("commissionDisclosure");
    if (commission) {
      commission.textContent = DATA.disclosure;
      commission.hidden = false;
    }
  }
  // ADR-0040: the fold above the first ticket action has to say what it holds,
  // and one of the facts in it must not be a click away -- when the links are
  // tracked, the line names the payment. A fold holding nothing is hidden
  // rather than left as a control that opens onto nothing.
  const linkTerms = document.getElementById("linkTerms");
  if (linkTerms) {
    document.getElementById("linkTermsSummary").textContent = DATA.tracked && DATA.disclosure
      ? "About the ticket link, and how this site is paid"
      : "About the ticket link";
    linkTerms.hidden = !Array.from(linkTerms.querySelectorAll("p")).some((p) => !p.hidden);
  }
}

const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

// Formatted from the ISO string by hand rather than through Date: new
// Date("2026-10-05") is parsed as UTC midnight, which prints as the 4th for any
// reader behind UTC. A copied date that is off by a day is worse than none.
// A row with no service says which day the page is about. The reader
// cannot reach the day the build happened to pick, so a bare "No service"
// beside a station the network serves reads as a fact about the station rather
// than about the date. A station with no service in the coming week has no other
// day to be named, and keeps the bare words.
const SHORT_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
function shortDay(iso) {
  const parts = String(iso || "").split("-");
  if (parts.length !== 3) return "";
  return SHORT_DAYS[new Date(Date.UTC(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))).getUTCDay()] || "";
}
// Every absence a row can carry, in one table, because three surfaces print
// one -- the Time cell, the dock's row and the copied text -- and because an
// absence with no day on it reads as a claim about the station rather than
// about the date. The build sends a key, the day it asked about and the day
// the row next runs; nothing here can be worded without them.
//
// A cell is narrow and a copied line is not, so each entry says both: the
// short form goes in the column and the long form in the record. They are two
// lengths of one sentence rather than two sentences, and both name the day.
const JOURNEY_ABSENCE = {
  no_timetable: (day, later) => ({
    brief: day.short ? "No timetable " + day.short : "No timetable",
    full: day.long ? "no timetable in this build for " + day.long : "no timetable in this build",
  }),
  no_service: (day, later) => ({
    brief: later
      ? "No service " + day.short + ", runs " + shortDay(later)
      : "No service " + (day.short ? day.short + " " : "") + "any day this week",
    full: later
      ? "no service on " + day.long + ", and it runs on " + humanDate(later)
      : "no service on " + (day.long || "the day this build asked about") +
        ", nor on the " + (DATA.serviceHorizon || 7) + " days after it",
  }),
};
// The absence a row is carrying, worded from the three facts it holds. A state
// this build does not recognise is worded as an absence, because an
// unrecognised state is not a journey.
function absenceText(destination, brief) {
  const iso = DATA.serviceDate;
  const day = { short: shortDay(iso), long: iso ? humanDate(iso) : "" };
  const build = JOURNEY_ABSENCE[destination.journeyState] || JOURNEY_ABSENCE.no_service;
  return build(day, destination.nextService)[brief ? "brief" : "full"];
}

// What this row's station is on the day now chosen, as [minutes, changes], or
// null when it runs on no day the reader can pick. Null is the honest answer
// for a day the network does not serve, and for a row this build holds no week
// for, and the two are worded differently by the caller rather than collapsed
// into one "unknown".
function serviceAnswer(destination) {
  const days = DATA.serviceWeek;
  if (!days || !days.length) return undefined;
  const index = destination.serviceWeekIndex;
  // Null as well as undefined, because the build sends null for a row it
  // holds no week for rather than -1: a pool reference is a negative number,
  // so -1 would have decoded into pool entry zero and named a railcard.
  if (index === undefined || index === null || index < 0) return undefined;
  const perDay = days[index];
  if (!perDay) return undefined;
  // The day's table is keyed by station, so the row's own station is looked
  // up in it. Handing back the day's whole table instead is a row that
  // prints a dash for every station on the page, because the object has no
  // index 0 in it to read a duration from.
  const day = perDay[serviceDayIndex];
  if (!day) return undefined;
  // The build keeps only the stations a walk reached, so a station this
  // day's table does not name is one it did not run to on that day. The row
  // is known to this table -- the build asked about every station a row
  // names -- so its absence is an answer, not a gap in what was asked.
  return Object.prototype.hasOwnProperty.call(day, destination.crs)
    ? day[destination.crs]
    : null;
}
// The minutes and changes to print, which are the chosen day's rather than the
// build's whenever the build carried a week. Day zero is the build's own answer
// and is asserted equal to it, so choosing the first day changes nothing.
function journeyFor(destination) {
  const answer = serviceAnswer(destination);
  if (answer === undefined) {
    return destination.journeyState === "found"
      ? { minutes: destination.minutes, changes: destination.changes, found: true }
      : { minutes: null, changes: null, found: false };
  }
  return answer === null
    ? { minutes: null, changes: null, found: false }
    : { minutes: answer[0], changes: answer[1], found: true };
}
// The absence, worded for the day being shown rather than the day the build
// asked about. S23's point, kept when the reader chooses the day: "No service"
// beside a station the network serves on the other six days reads as a claim
// about the station unless the sentence names the day it is about. When the
// chosen day has no service and another day in the week does, the sentence
// names both, which is what tells a reader the row is worth reading.
function dayAbsenceText(destination, brief) {
  const days = DATA.serviceDays || [];
  const iso = days[serviceDayIndex];
  const day = { short: shortDay(iso), long: iso ? humanDate(iso) : "" };
  let later = null;
  const answer = serviceAnswer(destination);
  const perDay = DATA.serviceWeek && DATA.serviceWeek[destination.serviceWeekIndex];
  if (perDay) {
    // The next day this station does run on, looked up in that day's table
    // the same way the chosen day is. A day whose table does not name the
    // station is not a day it runs on, so it is passed over.
    for (let index = serviceDayIndex + 1; index < perDay.length; index++) {
      const table = perDay[index];
      if (table && Object.prototype.hasOwnProperty.call(table, destination.crs)) {
        later = days[index];
        break;
      }
    }
  }
  // A row with no week of its own keeps the build's own wording, because there
  // is no chosen day for it to be worded about.
  if (answer === undefined) return absenceText(destination, brief);
  const state = answer === null ? JOURNEY_ABSENCE.no_service : null;
  if (!state) return "";
  const built = state(day, later);
  return built[brief ? "brief" : "full"];
}
function humanDate(iso) {
  const parts = String(iso).split("-").map(Number);
  return parts[2] + " " + MONTHS[parts[1] - 1] + " " + parts[0];
}

// A date the build could not read is left out of the sentence, not printed as
// whatever the formatter makes of it. The reference feed's publication date
// arrives from an HTTP header, and the first version of this line sliced it as
// an ISO timestamp and shipped the words "published undefined undefined NaN" to
// a real reader -- a page making a freshness claim it could not actually make.
// A clause with no readable date is no clause.
function dayPhrase(value) {
  if (!value) return "";
  const text = String(value).slice(0, 10);
  const parts = text.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return "";
  const shown = humanDate(text);
  return shown.includes("undefined") || shown.includes("NaN") ? "" : " " + shown;
}

// What the reader has to type on the seller's own site, because the ticket link
// carries nothing (ADR-0018). The railcard is named only when the party price is
// what is on screen, and it is named as something to tick rather than sent
// anywhere, because no seller accepts it in a link (ADR-0014).
function journeyText(destination) {
  const together = unit() === "party";
  // C09: the copied text named the stations, the date and the party but not
  // the ticket type the reader had chosen, while the same Copy button is
  // offered in every mode. Copied from Singles and pasted to a seller, the
  // handoff could silently become a different ticket, so the mode travels with
  // it.
  const lines = [
    "From: " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    "To: " + destination.name + " (" + destination.crs + ")",
    "Ticket: " + fareName(destination),
  ];
  if (DATA.serviceDate) lines.push("Date: " + humanDate(DATA.serviceDate));
  lines.push("Passengers: " + (together ? DATA.adults + " adults" : "1 adult"));
  const card = chosenCard(destination);
  if (together && card) {
    lines.push(railcards[railcardSelect.value].label + " discount is not sent to the seller: confirm the railcard on their site");
  }
  return lines.join("\n");
}

// The manual copy. The text is put where the reader is already looking, inside
// the panel the button is in, rather than in a panel of its own that would have
// taken the row's one slot from the details the reader opened to get here.
function showCopyText(host, text, button) {
  // A second manual copy replaces the first rather than stacking under it: the
  // button describes one box, and the panel grows no copy of the same text.
  for (const stale of host.querySelectorAll("textarea.copybox")) stale.remove();
  const box = document.createElement("textarea");
  box.className = "copybox";
  box.readOnly = true;
  box.rows = 5;
  box.value = text;
  box.id = "copy-text-" + (regionSeq += 1);
  box.setAttribute("aria-label", "Journey details to copy");
  host.append(box);
  // The copy control is not a disclosure -- it has no collapsed state to speak
  // of -- so it names the text it filled rather than claiming to control it.
  if (button) button.setAttribute("aria-describedby", box.id);
  box.focus();
  box.select();
}

async function copyJourney(destination, button, host) {
  const text = journeyText(destination);
  const status = document.getElementById("copyStatus");
  const done = () => {
    button.textContent = "Copied";
    status.textContent = "Journey details copied: " + text.split("\n").join(". ");
    window.setTimeout(() => { button.textContent = "Copy"; }, 2000);
  };
  // Never claim a copy that did not happen. Clipboard access is refused when a
  // page is opened from a file or served without a secure context, so the
  // reader is shown the text instead of being told it is on their clipboard.
  const manual = () => {
    button.textContent = "Select below";
    status.textContent = "Could not copy automatically. The details are shown under the button.";
    showCopyText(host, text, button);
  };
  if (!navigator.clipboard || !navigator.clipboard.writeText) return manual();
  try {
    await navigator.clipboard.writeText(text);
    done();
  } catch (error) {
    manual();
  }
}

// The picker (ADR-0019): choosing a station is navigation to that station's
// page, not a filter on this one. The options are real anchors, so keyboard
// handling and accessible naming are the browser's own. The list is built from
// the written outputs, so nothing here can lead to a missing page.
const changeOrigin = document.getElementById("changeOrigin");
const originPicker = document.getElementById("originPicker");
if (changeOrigin && DATA.stations && DATA.stations.length) {
  // The field the page's own script created, read here rather than from the
  // document: it is moved into the heading when the picker opens, and the
  // markup no longer holds it.
  const originSearch = document.createElement("input");
  originSearch.id = "originSearch";
  originSearch.type = "search";
  originSearch.placeholder = "station";
  originSearch.autocomplete = "off";
  originSearch.setAttribute("aria-describedby", "originStatus");
  originSearch.setAttribute("aria-controls", "originPicks");
  originSearch.setAttribute("aria-label", "Start from a different station");
  const originSlot = changeOrigin.parentElement;
  const originPicks = document.getElementById("originPicks");
  const originNomatch = document.getElementById("originNomatch");
  const originStatus = document.getElementById("originStatus");

  function renderPicks() {
    const needle = originSearch.value.trim().toLowerCase();
    const wanted = DATA.stations.filter((station) => !needle || matches(station, needle));
    originPicks.replaceChildren();
    for (const station of wanted.slice(0, 40)) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      // The reader's budget, ticket type and facets travel with them: changing
      // station is a correction of where they are leaving from, not a reset of
      // the decision they have already made.
      link.href = station.href + "?" + stateQuery();
      const name = document.createElement("span");
      name.textContent = station.name;
      const code = document.createElement("span");
      code.className = "code";
      code.textContent = station.crs;
      link.append(name, code);
      item.append(link);
      originPicks.append(item);
    }
    if (wanted.length) {
      originNomatch.hidden = true;
    } else {
      originNomatch.textContent = "We don't have prices from '" + originSearch.value.trim() +
        "'. Try the station's name or its three-letter code.";
      originNomatch.hidden = false;
    }
    originStatus.textContent = wanted.length + " station" + (wanted.length === 1 ? "" : "s") + " listed";
  }

  // The field is moved into the slot rather than duplicated, so there is one
  // input in the document and the heading's own accessible name is the one
  // that gets typed into.
  function setPicker(open) {
    changeOrigin.setAttribute("aria-expanded", String(open));
    originPicker.hidden = !open;
    if (open) {
      if (originSearch.parentElement !== originSlot) originSlot.append(originSearch);
      changeOrigin.hidden = true;
      renderPicks();
      // The field is sized to its placeholder, so it is as wide as the word
      // "station" and no wider until something is typed into it.
      originSearch.focus();
      originSearch.select();
    } else {
      changeOrigin.hidden = false;
      originSearch.remove();
      // Escape is a keyboard exit, and focus returns to the control that
      // opened the picker rather than dropping to the top of the page.
      changeOrigin.focus();
    }
  }

  changeOrigin.addEventListener("click", () => {
    setPicker(changeOrigin.getAttribute("aria-expanded") !== "true");
  });
  // The budget slot beside this one is a real field, so a keyboard reader tabs
  // to it and types. This control is a button, and a button takes no keystroke:
  // a reader tabbed to the station's name and stopped there, and the field was
  // only reachable by pressing Enter or Space on the name first, which is two
  // gestures for one edit. Any printable key opens the picker and carries that
  // one character into it, which is what the budget slot does without saying so.
  changeOrigin.addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    // Space is the button's own key, and it is what opens the picker on its own.
    if (event.key.length !== 1 || event.key === " ") return;
    event.preventDefault();
    setPicker(true);
    originSearch.value = event.key;
    originSearch.setSelectionRange(1, 1);
    originSearch.dispatchEvent(new Event("input", { bubbles: true }));
  });
  originPicker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });
  // The field's own behaviour -- the completion, Tab and Enter, Escape, and the
  // click on the page that puts the station name back -- is the shared block,
  // because the chooser asks for the same three things. Walking away is one
  // path and it only acts while the picker is open, or every click on a
  // closed page would pull focus back to the station name.
  attachStationField({
    field: originSearch,
    stations: DATA.stations,
    dropdown: originPicker,
    inside: [originPicker],
    onChange: () => renderPicks(),
    onChoose: (station) => {
      window.location.href = station.href + "?" + stateQuery();
    },
    onCancel: () => {
      if (changeOrigin.getAttribute("aria-expanded") === "true") setPicker(false);
    },
  });
  // The picker is the field's other half -- the same selector, reached from the
  // heading -- so it answers the same two keys through the same block. Escape
  // from an option goes back to the field; Escape from the field closes it.
  wireListKeys(originSearch, originPicks);
} else if (changeOrigin) {
  // The shared station list did not arrive, so this control can only open
  // an empty panel. Put the station's own name where the control was --
  // the heading must never be left saying "from" and nothing -- and say
  // what the page is instead of naming a control it does not have. This is
  // still one station's page, and the way to another one is the All
  // stations link in the footer. A build that ships the list inside the
  // page never reaches this branch: DATA.stations is filled before this
  // script runs, so there is no request that can fail.
  const stationName = document.createElement("span");
  stationName.className = "origin-name";
  stationName.textContent = DATA.origin ? DATA.origin.name : "";
  changeOrigin.replaceWith(stationName);
  originPicker.remove();
  const fallbackNote = document.getElementById("firstUse");
  if (fallbackNote) fallbackNote.textContent = FIRST_USE_FALLBACK;
}

// S26: a shortlist of candidate places, and nothing that looks like a
// booking. The list lives in the address like the rest of the search state, so
// it survives a refresh and can be handed to somebody else as a link; what it
// shows is the price currently on screen, because a comparison of a different
// price than the one beside each row would be a comparison of nothing.
const SHORTLIST_LIMIT = 8;
// Read from the address on load and written back on every change, like the rest
// of the search state: a shortlist that only lives in one tab is not a
// shortlist anybody can hand to somebody else.
let shortlistCodes = [];
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
  const wanted = new Set(shortlistCodes);
  // In the page's own order, and only rows this ticket mode actually carries:
  // a shortlist that named a destination the reader cannot see priced would be
  // a list of places they cannot buy.
  return activeDestinations().filter((destination) => wanted.has(destination.crs));
}
function inShortlist(crs) {
  return shortlistCodes.includes(crs);
}
function toggleShortlist(crs) {
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
  shortlistCodes = kept.map((destination) => destination.crs);
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
      shortlistDockCount.textContent = kept.length + (kept.length === 1 ? " place" : " places");
    }
    padForDock();
  }
  const empty = kept.length === 0;
  for (const control of [shortlistCopy, shortlistShareBox]) {
    if (control) control.hidden = empty;
  }
  if (shortlistShare) {
    shortlistShare.textContent = empty
      ? ""
      : "Shortlist of " + kept.length + (kept.length === 1 ? " place" : " places") + " from " +
        DATA.origin.name + ". " + window.location.href;
  }
  if (shortlistBox) {
    shortlistBox.hidden = true;
    if (shortlistShareBox) shortlistShareBox.open = false;
  }
  if (shortlistStatus && !shortlistStatus.textContent) {
    shortlistStatus.textContent = kept.length ? kept.length + " shortlisted." : "";
  }
}

function shortlistText() {
  const kept = shortlisted();
  const what = unit() === "party" ? "for the two of us" : "each";
  const lines = [
    "Shortlist from " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    "Budget: £" + budgetNumber.value + " " + what,
  ];
  // The day the reader chose, not the day the build happened to pick: a
  // pasted line that says otherwise sends someone to the wrong day.
  const chosen = (DATA.serviceDays || [])[serviceDayIndex] || DATA.serviceDate;
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
  lines.push("A shortlist of places, not a booking: no train is chosen and no ticket is held.");
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
    shortlistCodes = [];
    setShortlistStatus("");
    renderShortlist();
    writeUrl();
  });
}
window.addEventListener("resize", padForDock);

// The address is the search (S05). A reader who has already decided a budget
// and a ticket type, then refreshes, or shares the tab, or presses Back, must
// land on the search they made rather than the one the page was built with.
// Two rules keep it readable. The budget is always written, because it is the
// decision the page exists to record and a shared link without it would not be
// the search that was made; every other value equal to the page default is left
// out entirely. And the facets are repeated short keys rather than one encoded
// blob. The same query is what a picker option carries, so a link to another
// origin is the same search from a different station (S06) -- one function
// writes both, so they cannot drift apart.
const DEFAULT_MODE = document.querySelector('input[name="ticketMode"]:checked').value;
function stateQuery() {
  const params = new URLSearchParams();
  params.set("budget", budgetNumber.value);
  const mode = ticketMode();
  if (mode !== DEFAULT_MODE) params.set("mode", mode);
  if (unit() === "party") params.set("party", "2");
  if (!noCard()) params.set("card", railcardSelect.value);
  const types = Array.from(selectedDestinationTypes()).sort();
  for (const type of types) params.append("types", type);
  if (currentPage > 1) params.set("page", String(currentPage));
  // Only a day other than the build's own. A link that arrived without one
  // reads as this build's day, which is what the address then says too, so the
  // parameter has one meaning rather than two.
  if (serviceDayIndex > 0) params.set("day", String(serviceDayIndex));
  // One repeated short key per place rather than a joined list: URLSearchParams
  // would percent-encode the commas, and a shared link is meant to be readable.
  for (const code of shortlistCodes) params.append("short", code);
  return params.toString();
}

// A decision is one history entry. Dragging the budget is one decision however
// many events it fires, so the budget replaces the address while the pointer
// is down and pushes once it settles; every other control is a single click
// and pushes at once.
let budgetUrlTimer = null;
function writeUrl({ budget = false } = {}) {
  if (!budget) {
    writeUrlNow(true);
    return;
  }
  if (budgetUrlTimer) clearTimeout(budgetUrlTimer);
  writeUrlNow(false);
  budgetUrlTimer = setTimeout(() => {
    budgetUrlTimer = null;
    writeUrlNow(true);
  }, 700);
}
const STATE_KEYS = ["budget", "mode", "party", "card", "types", "page", "short", "day"];
function writeUrlNow(push) {
  const url = new URL(window.location.href);
  // Only this page's own keys are rewritten. A shared link can carry someone
  // else's parameters -- a campaign tag, a referrer -- and dropping them
  // because the reader moved the budget would quietly break whatever they
  // were for.
  for (const key of STATE_KEYS) url.searchParams.delete(key);
  for (const [key, value] of new URLSearchParams(stateQuery())) url.searchParams.append(key, value);
  if (url.href === window.location.href) return;
  history[push ? "pushState" : "replaceState"](null, "", url);
}

// Read the address back into the controls. A value naming a control this page
// does not have is ignored rather than guessed at: a link from another station
// can carry a mode or a facet this origin has no fares for, and the reader
// should get the page's own defaults for those, not a blank table.
function readState() {
  const params = new URLSearchParams(window.location.search);
  return {
    budget: params.has("budget") ? Number(params.get("budget")) : null,
    mode: params.get("mode"),
    unit: params.get("party") === "2" ? "party" : null,
    railcard: params.get("card"),
    types: params.getAll("types"),
    page: Number(params.get("page")) || 1,
    // Held here and applied once the control has written its options, which is
    // after this function has run. A value naming a day this build did not walk
    // is clamped to the last day it did, because a shared link from a build with
    // a longer week should show a day rather than an empty table.
    day: Number(params.get("day")) || 0,
    // Only codes this page can price are kept: a shared link must not put a
    // place in the list that the reader cannot see a fare for.
    short: params.getAll("short").map((code) => code.trim().toUpperCase()).filter(Boolean),
  };
}
function applyState(state) {
  if (state.budget !== null && Number.isFinite(state.budget) && state.budget >= 0) {
    setBudget(state.budget);
  }
  for (const input of document.querySelectorAll('input[name="ticketMode"]')) {
    if (input.value === state.mode) input.checked = true;
  }
  for (const input of document.querySelectorAll('input[name="unit"]')) {
    if (input.value === state.unit) input.checked = true;
  }
  // A card code that arrived on a link is applied only when this page prices
  // that card. A link from another station can name a card this origin's feed
  // holds nothing for, and the reader should get this page's own default rather
  // than a control reading as a card they hold.
  const wanted = state.railcard && railcards[state.railcard] ? state.railcard : "";
  railcardSelect.value = wanted;
  for (const input of destinationTypeInputs) {
    input.checked = input.value !== "all" && state.types.includes(input.value);
  }
  const all = destinationTypeInputs.find((input) => input.value === "all");
  if (all && !all.checked && !destinationTypeInputs.some((input) => input.value !== "all" && input.checked)) {
    all.checked = true;
  }
  // Back and Forward carry the day like every other part of the search, so the
  // address is read back into the table rather than only into a variable the
  // control reads once. No write: Back is a decision the reader already made.
  setServiceDay(state.day);
  currentPage = Math.max(1, state.page);
  shortlistCodes = state.short.filter(pricedHere);
}
// Whether this page can price that station at all, in any of its ticket modes.
function pricedHere(code) {
  return [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations]
    .some((list) => (list || []).some((destination) => destination.crs === code));
}
window.addEventListener("popstate", () => {
  // Back is a decision the reader already made, so it is applied without
  // writing the address again: re-writing it here would make the entry Back
  // just left unreachable, and the control would never come back.
  applyState(readState());
  render();
});

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
