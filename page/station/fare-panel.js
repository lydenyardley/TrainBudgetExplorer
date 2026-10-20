// The row's own disclosure, and the one owner of its state.

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
  } else if (restricted && destination.restrictionDescribed) {
    // Only where the feed has wording. Where it does not, the lead sentence
    // above is the payload's own sentence about the missing condition, and a
    // paragraph under it repeated the same fact (D3 of the 17 October 2026
    // critique).
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
  summary.textContent = "Feed record (technical details)";
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
  if (noCard() || !railcards[STATE.railcard]) return null;
  const details = (destination.railcards || {})[STATE.railcard];
  if (!details || !details.rule) return null;
  const rule = DATA.railcardRules[details.rule];
  return rule ? rule.text : null;
}
// C28: one panel per row, and one owner for it. It used to be two -- the times
// list and the manual-copy box each removed whatever sat under the row -- so
// opening one silently emptied the other and left its control announcing a
// state that had gone. The copy text now lands inside the panel the button that
// asked for it is already in, which leaves one region per row and one control
// whose state is written back when it closes.
// Keyed on the row element, not its station code: every render replaces the
// rows, so a code-keyed map would keep detached rows and their panels alive
// and let one render's state answer for another's row.
const rowPanel = new WeakMap();
function closePanel(row) {
  const panel = rowPanel.get(row);
  STATE.openCrs = "";
  if (!panel) return false;
  panel.row.remove();
  if (panel.control) panel.control.setAttribute("aria-expanded", "false");
  rowPanel.delete(row);
  return true;
}
// Put back the row a reader had open, against the rows this render built. One
// function, so the click a reader made and the render that follows it take the
// same path through the panel; the CRS is read from the state rather than from
// the element the click was on.
function reopenOpenRow(items) {
  if (!STATE.openCrs) return;
  const destination = items.find((candidate) => candidate.crs === STATE.openCrs);
  const row = destination
    ? Array.from(rows.children).find((candidate) => candidate.dataset.crs === STATE.openCrs)
    : null;
  const toggle = row ? row.querySelector(".toggle") : null;
  if (!row || !toggle) {
    STATE.openCrs = "";
    return;
  }
  toggleDetail(row, destination, toggle, false);
}

// `reveal` is whether this panel is appearing because the reader opened it, or
// because a render put back the one they had open (E9). Only the first is a
// surface the page just noticed them using (DL5 of the 19 October 2026 delight
// pass): a budget drag that reopens the panel every frame must not animate it
// on every frame.
function toggleDetail(row, destination, toggle, reveal) {
  if (rowPanel.get(row)) {
    closePanel(row);
    return;
  }
  const detail = document.createElement("tr");
  detail.className = reveal ? "detail reveal" : "detail";
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
  detail.id = "detail-times-" + destination.crs + "-" + (STATE.regionSeq += 1);
  row.after(detail);
  rowPanel.set(row, { row: detail, control: toggle });
  toggle.setAttribute("aria-controls", detail.id);
  toggle.setAttribute("aria-expanded", "true");
  // E9 of the 17 October 2026 audit: the open row is part of the search, so it
  // is recorded where the rest of it is. It used to live only in this WeakMap,
  // keyed on the row element, and every render replaces those elements -- so a
  // reader who opened a row and then moved the budget lost the panel and the
  // fare and condition inside it. table.js reopens this CRS on the row its next
  // render built.
  STATE.openCrs = destination.crs;
}
