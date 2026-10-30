// The payload the page arrives with, and the elements the panels below reach
// for before one of them owns a place to put them: the table the rows are
// built into, and the budget control that bounds them.
//
// The three placeholders at the top are substituted into the shared asset the
// build writes once. The list keyboard block, the station matcher and the
// station field are shared with the chooser, so they are written once in
// page_templates.py, and they lead this file because this file leads the
// route's script.
//
// The page's own answer arrives separately, in a small block the page inlines
// before the asset: one script cannot be shared across pages while it carries
// a page's destinations. The asset reads it here rather than declaring it, so
// the bytes the browser keeps are the same for every page of the route.

__LIST_KEYS__
__STATION_MATCH__
__STATION_FIELD__
const DATA = window.TBE_DATA;
const FIRST_USE_FALLBACK = window.TBE_FIRST_USE_FALLBACK;
// Each row list arrives as a column list and a table of cells, because every row
// in a list carried the same field names and the page was sending them once per
// row. Hydrating here keeps the rest of this script reading rows as objects, and
// it is also what makes an older payload -- a plain list -- still render.
//
// ADR-0069: the fare lists also leave out what is the station's rather than the
// fare's. A "placed" column is read from DATA.places by the row's station, and
// a row's railcard decisions and tickets arrive packed by the orders in
// DATA.rowCodec. Each is rebuilt here into the object the build wrote, field
// for field and in the same order, so nothing below this function changes.
function unpackRailcards(value, codec) {
  if (!codec || !Array.isArray(value)) return value;
  const out = {};
  codec.cards.forEach((card, i) => {
    const packed = value[i];
    if (!Array.isArray(packed)) return;
    out[card] = {
      state: codec.states[packed[0]],
      pricePence: packed[1],
      minimumFarePence: packed[2],
      rule: packed[3] === null ? null : String(packed[3]),
    };
  });
  return out;
}
function unpackTickets(value, codec) {
  if (!codec || !Array.isArray(value)) return value;
  const named = { fromName: "fromCrs", toName: "toCrs" };
  return value.map((packed) => {
    if (!Array.isArray(packed)) return packed;
    const ticket = {};
    let at = 0;
    for (const field of codec.columns) {
      if (codec.names && named[field]) ticket[field] = codec.names[ticket[named[field]]];
      else ticket[field] = packed[at++];
    }
    return ticket;
  });
}
// A departure option's three facts, sent as an array in the order the codec
// names rather than as an object that spells its keys out on every option.
function unpackDepartures(value, columns) {
  if (!columns || !Array.isArray(value)) return value;
  return value.map((option) => {
    if (!Array.isArray(option)) return option;
    const out = {};
    columns.forEach((field, i) => { out[field] = option[i]; });
    return out;
  });
}
// A column of words that repeat is sent as a list of the words once and an
// index per row, so the page reads the word back from the table's own
// dictionary rather than carrying it on every row.
function hydrate(table) {
  if (!table || !Array.isArray(table.rows)) return table || [];
  const pool = DATA.pool || [];
  const codec = DATA.rowCodec || {};
  const dicts = table.dicts || {};
  const derived = new Set(table.derived || []);
  const placed = new Set(table.placed || []);
  const places = DATA.places || { columns: [], rows: {} };
  const placeDicts = places.dicts || {};
  const placeAt = {};
  places.columns.forEach((column, i) => { placeAt[column] = i; });
  const own = table.columns.filter((column) => !placed.has(column));
  const crsAt = own.indexOf("crs");
  // A negative cell is an index into the page's pool of values that repeat,
  // so the rows that share a link or a railcard record share one object.
  const value = (cell) => (typeof cell === "number" && cell < 0 ? pool[-cell - 1] : cell);
  // A place's columns are read the same way a row's are, because they are
  // counted into the same pool and their own dictionaries.
  const placeCell = (station, column) => {
    const cell = value(station[placeAt[column]]);
    return Object.prototype.hasOwnProperty.call(placeDicts, column) ? placeDicts[column][cell] : cell;
  };
  return table.rows.map((cells) => {
    const row = {};
    const station = placed.size ? places.rows[value(cells[crsAt])] : null;
    let at = 0;
    for (const column of table.columns) {
      if (placed.has(column)) {
        let cell = station ? placeCell(station, column) : null;
        if (column === "departures") cell = unpackDepartures(cell, codec.departures);
        row[column] = cell;
        continue;
      }
      // A column the build left out because another column already says it:
      // the party price of two adults is twice the adult price on every row.
      if (derived.has(column)) {
        row[column] = typeof row.adultPence === "number" ? row.adultPence * 2 : null;
        continue;
      }
      let cell = value(cells[at++]);
      if (Object.prototype.hasOwnProperty.call(dicts, column)) cell = dicts[column][cell];
      else if (column === "railcards") cell = unpackRailcards(cell, codec.railcards);
      else if (column === "tickets") cell = unpackTickets(cell, codec.tickets);
      else if (column === "departures") cell = unpackDepartures(cell, codec.departures);
      row[column] = cell;
    }
    return row;
  });
}
for (const key of ["destinations", "singleDestinations", "anytimeDestinations", "stations"]) {
  DATA[key] = hydrate(DATA[key]);
}
// A station's week is one entry per station and eight answers, and a day that
// answers what the day before it did travels as true: the weekday timetable
// repeats itself five days running. Resolved here, so every reader below sees a
// day's own answer. `true` is not an answer -- an answer is [minutes, changes]
// or null -- which is what makes it usable as the marker.
for (const week of DATA.serviceWeek || []) {
  for (const crs of Object.keys(week)) {
    const answers = week[crs];
    if (!Array.isArray(answers)) continue;
    for (let day = 1; day < answers.length; day++) {
      if (answers[day] === true) answers[day] = answers[day - 1];
    }
  }
}
// ADR-0069, third half: a station's own facts -- the kind of place it is and
// the reviewed sites it is a proof for -- are the same on every page of the
// release that lists it, so they travel in the shared station list rather than
// in each page. On a cluster-priced page they were 120 KB of a 690 KB page,
// repeated 2,900 times over. Joined here, by CRS, so everything below reads a
// row exactly as it did before.
const STATION_FACTS = window.TBE_STATION_FACTS || null;
if (STATION_FACTS) {
  for (const key of ["destinations", "singleDestinations", "anytimeDestinations"]) {
    for (const row of DATA[key]) {
      const facts = STATION_FACTS[row.crs];
      // A destination the feed has no location record for is "other" here as
      // it was in the build, which is the same default the fares query gives
      // it. A place with no facts at all would otherwise lose its type
      // silently, and the "other" chip is offered from the same answer.
      row.destinationType = facts ? facts.types[0] : "other";
      row.destinationTypes = facts ? facts.types : ["other"];
      if (!facts) continue;
      row.heritageSites = facts.heritageSites || [];
      row.natureSites = facts.natureSites || [];
      row.coastalSites = facts.coastalSites || [];
      row.rspbSites = facts.rspbSites || [];
      row.nationalTrustSites = facts.nationalTrustSites || [];
      row.nationalParkSites = facts.nationalParkSites || [];
    }
  }
} else if (DATA.stationsSrc) {
  // This page was built expecting the shared file and it did not arrive, so no
  // row knows its type. An empty list rather than a missing field, because the
  // chips are offered on "a row carries this type": with none, every chip
  // stands down instead of offering a filter that can only empty the list. The
  // rows themselves are unaffected -- prices, times and names are all in the
  // page's own bytes.
  for (const key of ["destinations", "singleDestinations", "anytimeDestinations"]) {
    for (const row of DATA[key]) row.destinationTypes = [];
  }
}
// ADR-0033 is re-scoped for the picker: its list is one file the site
// serves once, because the same list on every page was the release's
// largest repeated item (audit, 30 September 2026). The page's own
// destinations still travel in it, and nothing else breaks when this
// request does not arrive -- the branch under the picker says what the
// page is instead of offering a control that opens nothing.
if (window.TBE_STATIONS) {
  DATA.stations = window.TBE_STATIONS.filter(
    (station) => !DATA.origin || station.crs !== DATA.origin.crs
  );
}
const rows = document.getElementById("rows");
const budget = document.getElementById("budget");const budgetNumber = document.getElementById("budgetNumber");const budgetCeilingNote = document.getElementById("budgetCeiling");
const budgetField = document.getElementById("budgetField");
// The table's own furniture, read here rather than in the panels whose
// declarations merely sat nearest it. #summary and #empty were declared in
// service-day.js and written by table.js; #more, #pagination, #pageStatus and
// the two pager buttons were declared in filters.js and written by table.js or
// wired in wiring.js. A maintainer changing the count line had to open three
// files to learn what may write it (E12 of the 17 October 2026 audit), and this
// is the file the page already reads its elements in.
const summary = document.getElementById("summary");
// The line under the count that names what the next pound buys (DL1). Read
// here, with the rest of the table's furniture; budget.js writes it.
const budgetNext = document.getElementById("budgetNext");
// The rail that keeps the budget in reach once its own control has scrolled
// away (OV4 of the 19 October 2026 overdrive pass). Read here with the page's
// other elements: budget.js writes it, wiring.js listens to it and decides when
// it is shown.
const budgetRail = document.getElementById("budgetRail");
const railBudget = document.getElementById("railBudget");
const railNow = document.getElementById("railNow");
const empty = document.getElementById("empty");
const more = document.getElementById("more");
const pagination = document.getElementById("pagination");
const pageStatus = document.getElementById("pageStatus");
const previousPage = document.getElementById("previousPage");
const nextPage = document.getElementById("nextPage");
