"""C2: the railcard explanation moves out of a modal and into the row.

The "Card details" button opened a dialog on top of a page the reader was
already reading, three times per destination, to be told a number the row
beside it already carried. The same sentences are now one line in the row's
own disclosure, and the feed's exact RR rule joins the feed record, which is
where a code belongs.
"""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_DIALOG = '''<dialog id="railcardDrawer" aria-labelledby="railcardDrawerTitle" aria-describedby="railcardReason">
  <div class="drawer-head">
    <h2 id="railcardDrawerTitle">Railcard eligibility</h2>
    <button id="railcardClose" class="toggle drawer-close" type="button" aria-label="Close railcard details">Close</button>
  </div>
  <p id="railcardDestination" class="tag"></p>
  <p id="railcardReason" class="drawer-status"></p>
  <dl>
    <dt>Card</dt><dd id="railcardName"></dd>
    <dt>Standard fare</dt><dd id="railcardStandard"></dd>
    <dt>Price with this card</dt><dd id="railcardDiscounted"></dd>
    <dt>DTD minimum</dt><dd id="railcardMinimum"></dd>
  </dl>
  <h3>Exact DTD rule</h3>
  <p id="railcardRule"></p>
</dialog>
'''

OLD_ACTIONS = '''// The row's two secondary actions, built into the panel rather than onto the
// row. Both take the reader somewhere the row has no space for: the railcard
// drawer, which is the one fare question the feed answers with a rule, and the
// copied handoff text, which is what a reader pastes to a seller or a friend
// (ADR-0018). The copy text of a refused clipboard lands in this same panel,
// under the button that asked for it.
function rowActions(row, destination) {
  const tools = document.createElement("div");
  tools.className = "row-actions";
  const cardDetails = document.createElement("button");
  cardDetails.className = "toggle";
  cardDetails.type = "button";
  cardDetails.textContent = "Card details";
  cardDetails.setAttribute("aria-label", "Railcard eligibility for " + destination.name);
  cardDetails.addEventListener("click", () => showRailcardDetails(destination));
  const copy = document.createElement("button");
  copy.className = "toggle";
  copy.type = "button";
  copy.textContent = "Copy";
  copy.setAttribute("aria-label", "Copy the journey details for " + destination.name);
  copy.title = "Copy the from, to, date and party size for this row";
  copy.addEventListener("click", () => copyJourney(destination, copy, tools));
  tools.append(cardDetails, copy);
  return tools;
}

function showRailcardDetails(destination) {
  document.getElementById("railcardDestination").textContent =
    destination.name + " (" + destination.crs + ") \\u00b7 " + destination.quality;
  const status = document.getElementById("railcardReason");
  const name = document.getElementById("railcardName");
  const discounted = document.getElementById("railcardDiscounted");
  const minimum = document.getElementById("railcardMinimum");
  // The row is priced at the cheaper of the standard fare and the card's, so
  // the drawer leads with that number rather than with the card's own. A card
  // whose minimum fare is above the discounted fare has a price that is dearer
  // than travelling without it, and printing that as the fare would show a
  // reader a bigger number than the row they opened it from.
  const shownPrice = (destination, details) => {
    if (details.pricePence === null) return destination.adultPence;
    return Math.min(destination.adultPence, details.pricePence);
  };
  const ruleText = document.getElementById("railcardRule");
  document.getElementById("railcardStandard").textContent = money(destination.adultPence) + " per adult";

  if (noCard() || !railcards[railcardSelect.value]) {
    status.dataset.state = "none";
    status.textContent =
      "No railcard is selected, so this fare is shown at its standard price. Choose the card " +
      "you hold above and every destination is priced against that card's own rules.";
    name.textContent = "None selected";
    discounted.textContent = "Not priced with a card";
    minimum.textContent = "Not priced with a card";
    ruleText.textContent = "No card is selected, so no railcard rule is consulted.";
    railcardDrawer.showModal();
    return;
  }

  const card = railcards[railcardSelect.value];
  const details = (destination.railcards || {})[card.key];
  if (!details) {
    status.dataset.state = "unavailable";
    status.textContent =
      "This feed prices no " + card.label + " fare to " + destination.name + ", so there is " +
      "nothing to compare it against.";
    name.textContent = card.label;
    discounted.textContent = "Not in this feed";
    minimum.textContent = "Not in this feed";
    ruleText.textContent = "No " + card.label + " record applies to this fare.";
    railcardDrawer.showModal();
    return;
  }

  // The rule record lives once in DATA.railcardRules and every card's row
  // carries its key, because repeating the record per row cost 388KB on the
  // heaviest real page (audit B3).
  const rule = details.rule ? DATA.railcardRules[details.rule] : null;
  const condition = rule && !rule.totalBan && rule.restrictionCode !== "none"
    ? rule.restrictionCode
    : null;
  const cardBeatsStandard = details.pricePence !== null && details.pricePence < destination.adultPence;
  const shown = shownPrice(destination, details);
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

  status.dataset.state = details.state;
  name.textContent = card.label + " (" + card.codes.join(", ") + ")";
  // The number here is the one the row is priced at, so it is never dearer than
  // the row the reader opened the drawer from. When the card does not help, the
  // card's own price is still shown, labelled as what it is, because it is the
  // fact that explains the standard fare beside it.
  discounted.textContent = details.pricePence === null
    ? "Not available, so " + money(destination.adultPence) + " per adult stands"
    : cardBeatsStandard
      ? money(shown) + " per adult"
      : money(shown) + " per adult, which is the standard fare";
  minimum.textContent =
    details.minimumFarePence === null
      ? "None current for " + destination.ticket
      : money(details.minimumFarePence);

  // The sentences are written here rather than shipped per row per card. Six
  // cards at the build's own wording measured 2,598 bytes a row against 433
  // for one, on a page that already carries 411KB; the facts cost 98.
  if (details.state === "blocked") {
    status.textContent =
      card.label + " cannot be applied to this fare. A current DTD RR rule matches this ticket, " +
      "route or endpoint and records a total ban, so the standard fare is the only price the feed " +
      "offers here.";
  } else if (!cardBeatsStandard) {
    // The three numbers the build already sent are enough to say this. The
    // discounted price before the minimum is not one of them, and recomputing it
    // here would put a second copy of the rounding rule in the page, where it
    // could drift from the build's.
    status.textContent =
      card.label + " does not reduce this fare. Its own price here is " +
      money(details.pricePence) + " per adult, against a standard fare of " +
      money(destination.adultPence) + ", because the minimum fare the feed applies to this " +
      "ticket is " + money(details.minimumFarePence) +
      ". This row is priced at the cheaper of the two, so travelling without the card would " +
      "cost the same.";
  } else if (condition) {
    status.textContent =
      card.label + " is available for this fare, subject to condition " + condition + ". No " +
      "matching total ban applies; the restriction is a travel condition rather than a card ban. " +
      "The feed's one-third discount gives " + money(details.pricePence) + " per adult" +
      minimumClause;
  } else {
    status.textContent =
      card.label + " is available for this fare. No current RR rule matches this ticket, route or " +
      "either endpoint. The feed's one-third discount gives " + money(details.pricePence) +
      " per adult" + minimumClause;
  }
  ruleText.textContent = rule
    ? rule.text
    : "No matching current RR rule for " + card.label + " on this fare.";
  railcardDrawer.showModal();
}
railcardClose.addEventListener("click", () => railcardDrawer.close());
'''

NEW_ACTIONS = '''// What the railcard did to this row's price, in the row's own disclosure.
//
// It was a dialog: a button on every row, opening a panel on top of a page
// the reader was already reading, to be told a number the row beside it
// already carried. The sentences are unchanged -- they are the ones that keep
// the page honest about a card that cannot help -- but they now sit under the
// fare they explain, where the reader opened the row to look, and the feed's
// exact RR rule sits in the feed record below them with the codes.
function cardNote(destination) {
  const note = document.createElement("p");
  note.className = "card-note";
  if (noCard() || !railcards[railcardSelect.value]) {
    note.dataset.state = "none";
    note.textContent =
      "No railcard is selected, so this fare is shown at its standard price. Choose the card " +
      "you hold above and every destination is priced against that card\\u2019s own rules.";
    return note;
  }

  const card = railcards[railcardSelect.value];
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
    note.textContent =
      card.label + " does not reduce this fare. Its own price here is " +
      money(details.pricePence) + " per adult, against a standard fare of " +
      money(destination.adultPence) + ", because the minimum fare the feed applies to this " +
      "ticket is " + money(details.minimumFarePence) +
      ". This row is priced at the cheaper of the two, so travelling without the card would " +
      "cost the same.";
  } else if (condition) {
    note.textContent =
      card.label + " is available for this fare, subject to condition " + condition + ". No " +
      "matching total ban applies; the restriction is a travel condition rather than a card ban. " +
      "The feed\\u2019s one-third discount gives " + money(details.pricePence) + " per adult" +
      minimumClause;
  } else {
    note.textContent =
      card.label + " is available for this fare. No current RR rule matches this ticket, route or " +
      "either endpoint. The feed\\u2019s one-third discount gives " + money(details.pricePence) +
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
'''

OLD_PANEL_TAIL = '''  const split = splitNote(destination);
  if (split) panel.append(split);
  panel.append(feedRecord(destination));
  panel.title = fareSummary(destination);
  return panel;
}'''

NEW_PANEL_TAIL = '''  const split = splitNote(destination);
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
}'''

OLD_RECORD = '''  add("Ticket", destination.ticket);
  add("Restriction", destination.restrictionCode || "none");
  add("Route", destination.routeCode);
  add("Priced as", destination.quality);
  add("Times", destination.journeyState);
  details.append(summary, list);
  return details;
}'''

NEW_RECORD = '''  add("Ticket", destination.ticket);
  add("Restriction", destination.restrictionCode || "none");
  add("Route", destination.routeCode);
  add("Priced as", destination.quality);
  add("Times", destination.journeyState);
  const rule = railcardRuleFor(destination);
  if (rule) add("Railcard rule", rule);
  details.append(summary, list);
  return details;
}

// The exact RR rule behind the chosen card\\u2019s price on this fare, if there
// is one. It was the last line of a dialog; a rule is a record, and records
// live in the record.
function railcardRuleFor(destination) {
  if (noCard() || !railcards[railcardSelect.value]) return null;
  const details = (destination.railcards || {})[railcardSelect.value];
  if (!details || !details.rule) return null;
  const rule = DATA.railcardRules[details.rule];
  return rule ? rule.text : null;
}'''

OLD_TOGGLE = '''  cell.append(fareDetails(destination), rowActions(row, destination));'''

NEW_TOGGLE = '''  cell.append(fareDetails(destination), rowActions(row, destination));'''

OLD_CONSTS = '''const railcardDrawer = document.getElementById("railcardDrawer");
const railcardClose = document.getElementById("railcardClose");
'''

NEW_CONSTS = ""

OLD_DIALOG_CSS = '''  #railcardDrawer { width: min(30rem, calc(100% - 1rem)); max-width: none; height: 100dvh;
                    max-height: none; margin: 0 0 0 auto; padding: 1.25rem;
                    border: 0; border-left: 1px solid var(--line); color: var(--fg);
                    background: var(--field); box-shadow: -1rem 0 2.5rem rgba(0,0,0,.18); }
  #railcardDrawer::backdrop { background: rgba(0,0,0,.38); }
  .drawer-head { display: flex; align-items: start; justify-content: space-between; gap: 1rem; }
  .drawer-head h2 { margin: 0; font-size: 1.25rem; }
  .drawer-close { min-width: 2.75rem; min-height: 2.75rem; }
  .drawer-status { margin: 1.25rem 0; padding: .8rem; border: 1px solid var(--line);
                    border-radius: .5rem; background: var(--best); }
  .drawer-status[data-state=blocked], .drawer-status[data-state=unavailable] { border-color: #b7791f; }
  #railcardRule { padding: .8rem; border: 1px solid var(--line); border-left-color: var(--accent); background: var(--bg);
                  font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .85rem; }
  #railcardDrawer dl { display: grid; grid-template-columns: max-content 1fr; gap: .55rem .8rem; }
  #railcardDrawer dt { color: var(--muted); }
  #railcardDrawer dd { margin: 0; font-variant-numeric: tabular-nums; }
'''

NEW_DIALOG_CSS = '''  /* The railcard, said in the row's own words, in the row's own disclosure. It
     was a dialog with a Close button and a definition list of three numbers
     the row above it already carried; it is now one paragraph, and the only
     part of it that is ever urgent -- a card that cannot be used on this fare
     -- is the part that is coloured. */
  .card-note { margin: .5rem 0 0; padding: .5rem .6rem; border: 1px solid var(--line);
               border-radius: .4rem; background: var(--bg); }
  .card-note[data-state=blocked], .card-note[data-state=unavailable] { border-color: var(--warn); }
  .card-note[data-state=available] { border-color: color-mix(in srgb, var(--accent) 40%, var(--line)); }
'''

patch(
    "page_templates.py",
    [
        (OLD_DIALOG, ""),
        (OLD_CONSTS, NEW_CONSTS),
        (OLD_ACTIONS, NEW_ACTIONS),
        (OLD_PANEL_TAIL, NEW_PANEL_TAIL),
        (OLD_RECORD, NEW_RECORD),
        (OLD_DIALOG_CSS, NEW_DIALOG_CSS),
    ],
)
