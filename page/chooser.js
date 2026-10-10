__LIST_KEYS__
__STATION_FIELD__
const STATIONS = __STATIONS__;
// What the tab and every retitle say after the budget. A release that
// priced one station names it; a chooser says what it is for.
const TITLE_SUFFIX = __TITLE_SUFFIX_JS__;
const picks = document.getElementById("picks");
const nomatch = document.getElementById("nomatch");
const status = document.getElementById("pickStatus");
const pick = document.getElementById("originSearch");
const budgetNumber = document.getElementById("budgetNumber");
const originClause = document.getElementById("originClause");
const capMessage = document.getElementById("capMessage");
// Every station is listed while the field is empty, because that is what a
// chooser is for: a reader who has not chosen a station is reading a
// directory of every one. Once there is a name in the field the list is a
// search result, and forty matches is more than anybody reads.
const CHOOSER_LIMIT = 40;
// What the reader typed, and the station a completion is offering for it,
// kept apart from the completed name the field shows: the list is the stations
// matching the typed text, with the completion first, so a suggestion never
// hides the alternatives it was chosen over (audit items 1 and 2, 9 October
// 2026).
let typedQuery = "";
let completing = null;
function matches(station, needle) {
  if (!needle) return true;
  return station.name.toLowerCase().includes(needle) ||
    station.crs.toLowerCase().startsWith(needle);
}
if (budgetNumber) {
  const storedBudget = new URLSearchParams(window.location.search).get("budget");
  if (storedBudget !== null && storedBudget !== "" && Number(storedBudget) >= 0) {
    budgetNumber.value = storedBudget;
  }
}
// C15: the heading is the page's most prominent promise, and it is written from
// the same resolved budget as the field, the tab title and every outgoing link,
// so the sentence a reader reads, the title their tab list shows, and the budget
// the page they open next is given cannot disagree.
function resolvedBudget() {
  const value = Number(budgetNumber.value);
  return Math.max(0, Number.isFinite(value) ? value : 0);
}
function syncChooserBudget() {
  const value = resolvedBudget();
  document.title = "Train fares up to £" + value + " · " + TITLE_SUFFIX;
  return value;
}

function render() {
  // A build that priced no stations has nothing to search over. The station
  // slot is the one thing on this page that cannot tell the truth here -- a
  // field that finds nothing is a control that lies -- so the whole "from ..."
  // clause leaves the heading and the page says why underneath it.
  if (!STATIONS.length) {
    if (originClause) originClause.hidden = true;
    picks.replaceChildren();
    nomatch.textContent = "Nothing is priced from any station in this build, so there is nothing to explore yet. " +
      "When the build prices journeys, this page lists every station it can start from.";
    nomatch.hidden = false;
    status.textContent = "0 stations listed";
    return;
  }
  // A one-station release has no field, so there is nothing to filter by
  // and the whole list is what it offers.
  const needle = typedQuery.trim().toLowerCase();
  const wanted = STATIONS.filter((station) => matches(station, needle));
  const cap = needle ? CHOOSER_LIMIT : wanted.length;
  const ordered = completing
    ? [completing, ...wanted.filter((station) => station !== completing)]
    : wanted;
  picks.replaceChildren();
  for (const station of ordered.slice(0, cap)) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = station.href;
    if (budgetNumber) {
      const url = new URL(link.href, window.location.href);
      url.searchParams.set("budget", resolvedBudget());
      link.href = url.pathname + url.search + url.hash;
    }
    const name = document.createElement("span");
    name.textContent = station.name;
    const code = document.createElement("span");
    code.className = "code";
    code.textContent = station.crs;
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = station.destinations + (station.destinations === 1 ? " destination" : " destinations");
    link.append(name, code, count);
    item.append(link);
    picks.append(item);
  }
  if (capMessage) {
    capMessage.textContent = wanted.length > cap
      ? "Showing " + cap + " of " + wanted.length + " matching stations. Refine the search to see the rest."
      : "";
    capMessage.hidden = wanted.length <= cap;
  }
  // The no-match wording answers typed input; with an empty field it would
  // quote nothing back at the reader, so it stays hidden instead.
  if (wanted.length) {
    nomatch.hidden = true;
  } else if (needle) {
    nomatch.textContent = "We don't have prices from '" + typedQuery.trim() +
      "'. Try the station's name or its three-letter code.";
    nomatch.hidden = false;
  } else {
    nomatch.hidden = true;
  }
  status.textContent = wanted.length + " station" + (wanted.length === 1 ? "" : "s") + " listed";
}

if (budgetNumber) {
  budgetNumber.addEventListener("input", () => {
    syncChooserBudget();
    render();
  });
}
// The field the whole page exists for, and the one a reader arrives at. It is
// focused rather than merely present: the caret in the heading is what says the
// page is waiting for a station, without a label above it saying so.
//
// Its three behaviours -- completing the name in the field, Tab and Enter to
// accept it, and the list moving under it while it is in use -- are the
// shared block, the same one a station page's heading uses.
attachStationField({
  field: pick,
  stations: STATIONS,
  dropdown: picks,
  inside: [picks],
  onChange: (_value, query, completion) => {
    typedQuery = query;
    completing = completion;
    render();
  },
  onChoose: (station) => {
    const url = new URL(station.href, window.location.href);
    if (budgetNumber) url.searchParams.set("budget", resolvedBudget());
    window.location.href = url.pathname + url.search + url.hash;
  },
});
// The budget slot has been clickable across its whole width since it was
// written, and the station slot is the other half of the same sentence: both
// are a gap in the heading that the reader fills in. Clicking the slot -- not
// the caret inside it, which is the reader placing the caret -- puts the field
// in focus, so the gap and the field are one target rather than a word beside
// a field. Nothing is selected: the value here is the reader's own query, and
// selecting it would lose it on the next keystroke.
const originField = document.getElementById("originField");
if (originField) {
  originField.addEventListener("click", (event) => {
    if (event.target !== originField) return;
    pick.focus();
  });
}
wireListKeys(pick, picks);
syncChooserBudget();
render();
if (pick) pick.focus();
