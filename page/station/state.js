// The page's one mutable state.

// Everything a reader can change while this page is open lives in STATE, and
// nothing else declares a changing fact (R4 of the 18 October 2026 plan, whose
// record and evidence are in `docs/open-work.md`).
//
// The page used to keep each answer where it happened to be standing: the day
// in service-day.js, the shortlist in shortlist.js, the page number in
// filters.js, the card in the select's own value, the budget in two fields that
// had to agree, and the chip selection in fourteen checkboxes. Six of the
// thirty-seven page fixes in the record were a second writer or reader of a fact
// kept that way -- the day lost on Back, the tick that was not the shortlist, a
// card swapping the row under the reader, a budget that could hold a figure its
// own control could not.
//
// A control's listener writes here once, every render reads here, and the
// address is a projection of it in both directions (url-state.js). Panels keep
// the elements they were given; they no longer keep a fact.
const STATE = {
  // The search: what the address carries, and what every row is rendered from.
  budget: 0,
  mode: "",
  unit: "adult",
  railcard: "",
  types: [],
  page: 1,
  day: 0,
  shortlist: [],
  // The row a reader has opened, by CRS, so a render can put it back (E9 of
  // the 17 October 2026 audit). Part of the search rather than of a panel's
  // furniture: it decides what the page shows, and the render that rebuilds the
  // rows is the one that has to reopen it.
  openCrs: "",

  // Per-mode memory. A reader's budget and their chip selection belong to the
  // ticket type they set them in, so switching mode and coming back restores
  // them instead of carrying one mode's figure into another's list (C20).
  budgetByMode: Object.create(null),
  typesByMode: Object.create(null),

  // What a panel remembers between renders, so it can tell "unchanged" from
  // "changed" without reading it back out of a control. None of these is part
  // of the search and none of them reaches the address.
  lastClampedMode: null,
  lastSyncedMode: null,
  rememberedCard: null,
  regionSeq: 0,
  budgetUrlTimer: null,
  // The budget the slider was at when the current drag began (DL1). It is a
  // gesture's memory rather than part of the search: it never reaches the
  // address, and settleBudgetDrag() reads it once and clears it.
  budgetDragFrom: null,
};

// The markup is the build's own statement of where the page opens, so the
// object starts from it rather than from a constant that would have to agree
// with the template. Everything else starts empty: no card is chosen, no chip
// is on, the first page, the build's own day.
function seedState() {
  STATE.budget = Number(budgetNumber.value) || 0;
  STATE.mode = document.querySelector('input[name="ticketMode"]:checked').value;
  STATE.unit = document.querySelector('input[name="unit"]:checked').value;
}
seedState();

// The gestures. A control's listener is one line calling one of these, and so
// is anything else that drives the page from script: the state is written once,
// the control that shows it is written once, and the page is rendered once.
// That is the whole of "controls write into it" -- and it is why the suite can
// drive a reader's gesture instead of setting a field behind the page's back.
//
// The budget's stop and its clamp are setBudget() in budget.js, which this
// calls; the page number has no gesture of its own, because render() clamps
// STATE.page against the list it just composed.
function chooseBudget(value) {
  // A typed or chosen figure ends any drag gesture in progress: a pointerdown
  // that never moved the slider leaves an origin behind, and measuring the
  // next key's gain from a click the reader abandoned is a sentence about the
  // wrong pound.
  STATE.budgetDragFrom = null;
  setBudget(value);
  STATE.page = 1;
  render();
  writeUrl({ budget: true });
}

function chooseUnit(name) {
  STATE.unit = name;
  for (const input of document.querySelectorAll('input[name="unit"]')) {
    input.checked = input.value === name;
  }
  STATE.page = 1;
  render();
  writeUrl();
}
// The radio group is read once and matched by its value attribute, rather than
// through a selector built out of the name: every caller checks its value against
// what the page offers first, so nothing can exploit the interpolation today, but
// a value holding a quote was a SyntaxError that took the gesture with it (audit
// item 4, 28 October 2026). `getAttribute` because a mode's value is the build's
// own, not a state a reader holds -- `.value` here would be the same answer read
// as though a control could change it.
function chooseMode(name) {
  const radios = Array.from(document.querySelectorAll('input[name="ticketMode"]'));
  if (!radios.some((input) => input.getAttribute("value") === name)) return;
  STATE.mode = name;
  for (const input of radios) {
    input.checked = input.getAttribute("value") === name;
  }
  STATE.page = 1;
  render();
  writeUrl();
}
// S3 of the 19 October 2026 critique: a door in the empty list names a ticket
// set and the fare its cheapest row costs, so the mode and the budget are one
// gesture. Set here rather than as two calls from the door, because two
// renders would show the reader a page the door never promised -- the new set
// at the old, empty budget -- for one frame.
function chooseModeAt(mode, pounds) {
  const radios = Array.from(document.querySelectorAll('input[name="ticketMode"]'));
  if (!radios.some((input) => input.getAttribute("value") === mode)) return;
  STATE.mode = mode;
  for (const input of radios) {
    input.checked = input.getAttribute("value") === mode;
  }
  // The figure this mode remembers is the one the door just named. Without it
  // the render's clamp restores whatever the reader last set in that mode -- 0,
  // if they had looked at it at an empty budget -- and the door lands on the
  // empty list it was pressed to leave. The clamp also restores a figure above
  // the stop of the list the reader was looking at, which setBudget would
  // otherwise have clipped to that stop on the way here.
  STATE.budgetByMode[mode] = pounds;
  setBudget(pounds);
  STATE.page = 1;
  render();
  writeUrl({ budget: true });
}
function chooseCard(key) {
  // A card this build does not price is not a card the reader holds, which is
  // the same rule a shared link is held to.
  STATE.railcard = railcards[key] ? key : "";
  railcardSelect.value = STATE.railcard;
  STATE.page = 1;
  render();
  writeUrl();
}
function chooseTypes(types) {
  STATE.types = types.filter((type) => destinationTypeInputs.some((input) => input.value === type));
  for (const input of destinationTypeInputs) {
    input.checked = input.value === "all" ? STATE.types.length === 0 : STATE.types.includes(input.value);
  }
  STATE.page = 1;
  render();
  writeUrl();
}
