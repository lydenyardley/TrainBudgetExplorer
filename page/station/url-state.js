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
// The build's own default, captured before any control moves: it is the value a
// parameter is left out for. STATE.mode is seeded from the markup, so this is
// the template's answer rather than a second copy of it.
const DEFAULT_MODE = STATE.mode;
function stateQuery() {
  const params = new URLSearchParams();
  // Read from the state, not from the two fields that display it: the address
  // is a projection of the search, so a control that has not been re-rendered
  // yet cannot write a figure the page is no longer searching with.
  params.set("budget", String(STATE.budget));
  if (STATE.mode !== DEFAULT_MODE) params.set("mode", STATE.mode);
  if (STATE.unit === "party") params.set("party", "2");
  if (STATE.railcard) params.set("card", STATE.railcard);
  const types = STATE.types.slice().sort();
  for (const type of types) params.append("types", type);
  if (STATE.page > 1) params.set("page", String(STATE.page));
  // Only a day other than the build's own. A link that arrived without one
  // reads as this build's day, which is what the address then says too, so the
  // parameter has one meaning rather than two.
  if (STATE.day > 0) params.set("day", String(STATE.day));
  // One repeated short key per place rather than a joined list: URLSearchParams
  // would percent-encode the commas, and a shared link is meant to be readable.
  for (const code of STATE.shortlist) params.append("short", code);
  return params.toString();
}

// A decision is one history entry. Dragging the budget is one decision however
// many events it fires, so the budget replaces the address while the pointer
// is down and pushes once it settles; every other control is a single click
// and pushes at once.
function writeUrl({ budget = false } = {}) {
  if (!budget) {
    writeUrlNow(true);
    return;
  }
  if (STATE.budgetUrlTimer) clearTimeout(STATE.budgetUrlTimer);
  writeUrlNow(false);
  STATE.budgetUrlTimer = setTimeout(() => {
    STATE.budgetUrlTimer = null;
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
// Put a search on the page. Every field it is not given keeps what the page
// already has, so a link that names only the budget leaves the reader's card and
// chips alone, and anything driving the page from script can set one part of the
// search without inventing the other seven. The address's own reader below
// always passes all of them.
//
// This is the one place that writes a control from the state, and it reads none
// of them back (R4 of the 18 October 2026 plan, in `docs/open-work.md`): the
// object is decided first and every control is then drawn from it, so a control
// can only ever show the search the page is actually running. A value this page
// does not offer keeps the current one instead of being guessed at -- a link
// from another station can name a mode, a party or a chip this origin's feed
// holds nothing for.
function applyState(given) {
  const pick = (key, current) => (given[key] === undefined || given[key] === null ? current : given[key]);
  const offered = (selector) => new Set(
    Array.from(document.querySelectorAll(selector), (control) => control.value));
  const modes = offered('input[name="ticketMode"]');
  const units = offered('input[name="unit"]');
  const chips = offered('input[name="destinationType"]');
  const mode = pick("mode", STATE.mode);
  // Not `unit`: that is the page's own reader of the radio group, and a local
  // of the same name is a call that throws the moment somebody makes one.
  const chosenUnit = pick("unit", STATE.unit);
  if (modes.has(mode)) STATE.mode = mode;
  if (units.has(chosenUnit)) STATE.unit = chosenUnit;
  // A card code is applied only when this page prices that card. A link from
  // another station can name one this origin's feed holds nothing for, and the
  // reader should get this page's own default rather than a control reading as
  // a card they hold.
  const card = pick("railcard", STATE.railcard);
  STATE.railcard = card && railcards[card] ? card : "";
  // Only a chip this page offers, and never "all": that chip is the selection
  // being empty, so a link naming it as a type would filter every row away.
  STATE.types = [...new Set(pick("types", STATE.types))]
    .filter((type) => type !== "all" && chips.has(type));
  STATE.page = Math.max(1, pick("page", STATE.page));
  const budget = pick("budget", STATE.budget);
  if (Number.isFinite(budget) && budget >= 0) setBudget(budget);
  STATE.shortlist = pick("short", STATE.shortlist).filter(pricedHere);
  // Now the controls, from the object. Nothing below reads one back.
  for (const input of document.querySelectorAll('input[name="ticketMode"]')) {
    input.checked = input.value === STATE.mode;
  }
  for (const input of document.querySelectorAll('input[name="unit"]')) {
    input.checked = input.value === STATE.unit;
  }
  railcardSelect.value = STATE.railcard;
  for (const input of destinationTypeInputs) {
    input.checked = input.value === "all"
      ? STATE.types.length === 0
      : STATE.types.includes(input.value);
  }
  // Back and Forward carry the day like every other part of the search, so the
  // day is set through the state rather than only into a variable the control
  // reads once. No write: Back is a decision the reader already made.
  setServiceDay(pick("day", STATE.day));
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
