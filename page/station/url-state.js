// The address is the search (S05).

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
