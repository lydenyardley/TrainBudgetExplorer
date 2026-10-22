// What a row hands the reader: the ticket link, the railcard note that
// explains the price, and the journey details to copy.

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
  // The link opens a new tab and nothing on the row said so (audit item 11,
  // 9 October 2026). The fact travels in the accessible name, where a reader
  // is told what the control does before following it, and in the tooltip.
  link.setAttribute("aria-label", "Tickets for " + destination.name + ", opens in a new tab");
  link.title = "Tickets for " + destination.name + " — " +
    destination.link.label + " search for " + destination.crs + ", opens in a new tab";
  cell.append(link);
  // One disclosure per row, on every row. It used to exist only where the
  // build had times, which left a fare's condition unreachable on a
  // prices-only page. The control is now the page's own chevron rather than a
  // word, so the visible label is a mark and the accessible name is what
  // carries the words: the destination and the fact that a fare is behind it,
  // which is the one shape true on a row with times and one without (audit
  // item 27). Dropping the word from the face of the button is only safe
  // because the name below keeps that much.
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
  // One shape for every row (audit item 27): the count was a second name for
  // the same control, and the panel behind it holds the fare and its condition
  // whether or not the build found times.
  toggle.setAttribute("aria-label", "Fare details for " + destination.name);
  toggle.title = times
    ? times + " departures and the fare for " + destination.name
    : "Fare details for " + destination.name;
  toggle.addEventListener("click", () => toggleDetail(row, destination, toggle, true));
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
  if (noCard() || !railcards[STATE.railcard]) return null;
  const note = document.createElement("p");
  note.className = "card-note";

  const card = railcards[STATE.railcard];
  // ADR-0061: a two-ticket row is two published fares, so a card is decided on
  // each ticket and the row's card price is the two card prices added together.
  // The reader is quoted the pair the journey is, not a card applied to half of
  // it, and a card the feed bans on either ticket is refused rather than shown
  // as a price nobody could buy.
  if (destination.tickets) {
    const pair = (destination.railcards || {})[card.key];
    if (!pair) {
      note.dataset.state = "unavailable";
      note.textContent = "The " + card.label + " has no fare for this two-ticket journey in " +
        "this feed, so the row shows the two standard fares.";
      return note;
    }
    note.dataset.state = pair.state;
    if (pair.pricePence === null || pair.pricePence === undefined) {
      note.textContent = "The " + card.label + " is refused on one of the two tickets by the " +
        "feed's own rule, so the row shows both standard fares.";
      return note;
    }
    if (pair.pricePence >= destination.adultPence) {
      // The figure first is the row's own, the same rule as a single-ticket row:
      // opening with the larger card price makes the reader hunt for theirs.
      note.textContent = "The " + card.label + " does not reduce this journey's " +
        money(priceOf(destination)) + " per adult. The card's own price for the two tickets is " +
        money(pair.pricePence) + " per adult" + (pair.minimumFarePence === null
          ? "."
          : ", because the minimum fare the feed applies to these tickets is " +
            money(pair.minimumFarePence) + ".");
      return note;
    }
    note.textContent = "The " + card.label + " applies to each of the two tickets: " +
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
    // The card is the subject of every other sentence in this panel, including
    // the two-ticket one above, so the same news -- no card fare here -- is
    // told in the same voice (audit item 31).
    note.textContent =
      "The " + card.label + " has no fare to " + destination.name + " in this feed, so there " +
      "is nothing to compare it against.";
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
    // Price first, then the reason, and the feed record below carries the
    // "total ban" vocabulary the rule itself uses (audit items 26, 29).
    note.textContent =
      "This fare is " + money(priceOf(destination)) + ", and " + card.label +
      " cannot be applied to this fare. The feed's own rule refuses the card on this ticket, " +
      "route or endpoint, so the standard fare is the only price the feed offers here.";
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
    // The reader's own price first, one qualifier, then the rule (audit item
    // 29): the discount figure used to be the third sentence.
    note.textContent =
      "The card’s discount in the feed gives " + money(details.pricePence) +
      " per adult for this fare, subject to condition " + condition +
      ", a travel condition rather than a card ban" + minimumClause;
  } else {
    note.textContent =
      "The card’s discount in the feed gives " + money(details.pricePence) +
      " per adult for this fare" + minimumClause;
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
  // One sentence, and it is the visible one: "Copy" on its own left the reader
  // to guess what reached the clipboard, and the answer was in a title no touch
  // reader sees (audit item 28).
  copy.textContent = "Copy journey";
  copy.setAttribute("aria-label", "Copy journey for " + destination.name);
  copy.addEventListener("click", () => copyJourney(destination, copy, tools));
  tools.append(copy);
  return tools;
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
    lines.push(railcards[STATE.railcard].label + " discount is not sent to the seller: confirm the railcard on their site");
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
  box.id = "copy-text-" + (STATE.regionSeq += 1);
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
    window.setTimeout(() => { button.textContent = "Copy journey"; }, 2000);
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
