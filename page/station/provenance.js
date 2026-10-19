// Where the numbers came from, how old they are, and what the page says
// about itself.

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
  }
  // D4 of the 17 October 2026 critique: the window the timetable covers is a
  // fact about a source, and it sat in the line above the table beside the age
  // of the prices -- two blocks between the count and the first Row. The age
  // of the prices stays where the reader comparing a fare can see it; the
  // window joins the other dates in the method fold.
  const coverage = document.getElementById("timetableCoverage");
  if (DATA.timetableFrom && coverage) {
    // days() is today minus the date, so a start still ahead is negative and
    // an end already past is positive.
    const starts = days(DATA.timetableFrom);
    const ends = days(DATA.timetableTo);
    const verdict = starts < 0
      ? "which has not started yet"
      : ends > 0
        ? "which has ended, so these times describe services that no longer run"
        : "which covers the day these times are for";
    coverage.textContent = "Times are from a timetable covering " + humanDate(DATA.timetableFrom) + " to " +
      humanDate(DATA.timetableTo) + ", " + verdict + ".";
    coverage.hidden = false;
  }
  if (!line) return;
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
// The trade vocabulary the lines in this disclosure quote: ITX, DTD, RR, the
// "feed" itself, a "flow", "Priced as" in a row's own panel, and NRE in the
// credit above. Item 44 of the 14 October 2026 clarity audit asked for them to
// be defined somewhere a reader can find; the answer was a glossary inside the
// method disclosure and no inline glosses, so a reader who wants the words
// opens one thing -- the accordion they are already in -- and finds them
// together. The definitions are written from here rather than shipped in the
// page's markup because this file is one shared asset: the list renders to 944
// bytes, and on every station page of a 2,718-page release that is 2.5 MB.
const FEED_WORDS = [
  ["DTD", "The downloadable fares feed: the industry file these prices are read from."],
  ["ITX", "A ticket-type code. An ITX placeholder is a fare the feed carries without a usable price, and this page leaves those out."],
  ["RR", "The railcard rules inside the fares feed: which card may discount which fare, and the minimum fare it applies over."],
  ["Feed", "One downloaded file of licensed data. \"This download\" means the dated copy these prices and times were read from."],
  ["Flow", "One origin-to-destination pair the fares feed prices. A journey can be one flow or two, which is where a row naming two tickets comes from."],
  ["Priced as", "The kind of fare a price is: Regular, buyable on the day, or Restricted, valid only under the condition the row states."],
  ["NRE", "National Rail Enquiries, whose data portal licenses the feeds this site is built from."],
];

function renderWordList() {
  const list = document.getElementById("wordList");
  if (!list || list.children.length) return;
  for (const [term, meaning] of FEED_WORDS) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = meaning;
    list.append(dt, dd);
  }
}

function provenance() {
  // An origin the build could not price is a different page from one whose
  // prices sit outside this budget, so it gets its own first sentence and its
  // own way forward — not an empty table under a slider that can't help.
  if (!DATA.destinations.length && !DATA.singleDestinations.length && !DATA.anytimeDestinations.length) {
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
  // The reader's facts only: which origin, what the count is, and which day the
  // times are for. The no-timetable fact is said once, in the freshness line
  // above the table (audit item 38), and the destination-type source is a
  // source, so it sits in the attribution block (audit item 48). The day is
  // written in the page's own date words, so no ISO date reaches the reader
  // (audit item 49).
  if (DATA.hasJourneys) {
    parts.push(DATA.serviceDate ? "times for " + humanDate(DATA.serviceDate) : "typical services in the feed");
  }
  document.getElementById("provenance").textContent = parts.join(" · ");
  renderWordList();
  document.getElementById("pricingBasis").textContent = DATA.pricingBasis
    ? DATA.pricingBasis + ". Use the ticket-type control to change which fares are listed, then use the budget filter to narrow the list."
    : "";
  renderCoverage();
  renderModeNote();
  renderFreshness();
  renderRestrictionReference();
  renderRailcardNote();
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
  // The destination-type source is a source, not a reader's fact, so it sits
  // here with the other licence text rather than in the provenance line
  // (audit item 48).
  if (DATA.locationTypeSource) {
    const attribution = document.getElementById("attribution");
    const p = document.createElement("p");
    p.textContent = "Destination types from: " + DATA.locationTypeSource + ".";
    attribution.append(p);
    attribution.hidden = false;
  }
  // Where the numbers came from, stated beside the prices rather than in the
  // footer, because where a number came from is part of the number.
  if (DATA.priceSource) {
    const line = document.getElementById("priceSource");
    // The source names the feed and the download date is carried beside it as
    // its own field, so the sentence is composed here from the pair. Reading
    // the date out of the source sentence is the shape that had the chooser
    // print it twice -- one date, one place it comes from.
    let text = "Prices from " + DATA.priceSource;
    if (DATA.feedDate) text += ", downloaded " + humanDate(DATA.feedDate);
    if (DATA.serviceDate) text += "; fares and times read for " + humanDate(DATA.serviceDate);
    line.textContent = text + ".";
    line.hidden = false;
  }
  if (DATA.builtAt) {
    const line = document.getElementById("buildMetadata");
    // Named for what it is (audit item 46) and dated in the page's own words, so
    // the build stamp is not the one ISO date on the page (audit item 49). The
    // digest stays: it is the citation a person debugging the site looks for.
    const time = DATA.builtAt.slice(11, 16);
    line.textContent = "Site built " + humanDate(DATA.builtAt.slice(0, 10)) +
      (time ? " at " + time + " UTC" : "") +
      " from this revision of the code" +
      (DATA.sourceFingerprint ? ", source " + DATA.sourceFingerprint : "") + ".";
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
