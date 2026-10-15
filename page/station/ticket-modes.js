// Which fares the list shows -- the three named sets and the cheapest fare
// of any type -- and what the page says when a mode or a budget returns
// nothing.

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
// The empty state may offer another set, and its button names what the button
// does with the count as the object of the verb -- "Show the 7 Anytime Day
// Returns", not the fragment "Anytime Day Return has 7" (audit item 32).
const SHOW_NOUNS = {
  cheapest: ["cheapest fare", "cheapest fares"],
  anytime: ["Anytime Day Return", "Anytime Day Returns"],
  return: ["return", "returns"],
  single: ["single", "singles"],
};
function countWord(count) {
  return count === 1 ? "one" : String(count);
}
function showLabel(mode) {
  const count = modeCount(mode);
  const nouns = SHOW_NOUNS[mode] || [modeLabels()[mode], modeLabels()[mode] + "s"];
  return "Show the " + countWord(count) + " " + nouns[count === 1 ? 0 : 1];
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
// first" beside a control named "Cheapest available" does not tell a reader
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
function stationInFeedMessage(station) {
  return station.name + " (" + station.crs + ") is in the feed, but this origin has no qualifying " +
    "return or single fare flow to it in this download.";
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
// fare of any type, whose caveats are the advance single and the restricted
// fare inside it, and the reviewed set this note was written for is now one of
// the filters beside it. The wider "any return" set is offered for the same reason
// it always was -- a restricted off-peak fare is a real price a reader can buy
// -- and whichever set is open, a restricted fare is not interchangeable with
// an unrestricted one, and the page cannot decode the feed's own validity text.
const MODE_NOTE = {
  cheapest: "Each row is the cheapest fare of any ticket type. An advance fare needs a chosen train; a restricted fare's condition is in the row's details.",
  anytime: "Unrestricted Anytime Day Returns: valid on any train on the route, so these prices compare with each other directly.",
  return: "Every standard-class return the feed prices, restricted off-peak and advance included. A restricted fare is not valid on every train or at every time — its condition is in the row's details.",
  single: "Outbound singles rather than returns. An advance single needs a chosen train, and is labelled where it appears.",
};
function renderModeNote() {
  const note = document.getElementById("modeNote");
  if (!note) return;
  note.textContent = MODE_NOTE[ticketMode()] || "";
  // The budget hint names the ticket mode the ceiling belongs to, because the
  // mode control is inside the folded refinements and "the ticket type you are
  // looking at" named nothing on screen (audit item 12). It is written in the
  // control's own words, so renaming the option renames this too.
  const hintMode = document.getElementById("budgetHintMode");
  if (hintMode) hintMode.textContent = "in " + (modeLabels()[ticketMode()] || "the list on screen");
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
function renderEmptyMode() {
  empty.replaceChildren();
  const why = document.createElement("p");
  why.textContent = emptyModeMessage();
  empty.append(why);
  const actions = document.createElement("p");
  actions.className = "empty-actions";
  for (const mode of Object.keys(modeLabels())) {
    if (mode === ticketMode() || !modeCount(mode)) continue;
    const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toggle";
    button.textContent = showLabel(mode);
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
    offer("Raise the budget to " + money(enough * 100), () => {
      setBudget(enough);
      currentPage = 1;
      render();
      writeUrl({ budget: true });
    });
  }
  if (selectedDestinationTypes().size) {
    offer("Show all destination types", clearDestinationTypes);
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
  for (const mode of Object.keys(modeLabels())) {
    if (mode !== ticketMode() && modeCount(mode)) {
      const input = document.querySelector(`input[name="ticketMode"][value="${mode}"]`);
      offer(showLabel(mode), () => {
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
