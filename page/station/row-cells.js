// The cells of a row, and the words each of them carries.

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
  // One word for the shortlist, in the stacked layout too: the column head
  // and this label are the same cell (audit item 13, 9 October 2026).
  cell.dataset.label = "Shortlist";
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
  // And only beside a journey: a row with no journey on the day prints
  // "Unknown" for the count, and naming a station under it would be a route
  // the page has just said it does not know.
  const via = !missing && serviceDayIndex === 0 ? interchangeLine(destination) : null;
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
