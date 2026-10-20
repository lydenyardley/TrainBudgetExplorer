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
function hydrate(table) {
  if (!table || !Array.isArray(table.rows)) return table || [];
  const pool = DATA.pool || [];
  const codec = DATA.rowCodec || {};
  const placed = new Set(table.placed || []);
  const places = DATA.places || { columns: [], rows: {} };
  const placeAt = {};
  places.columns.forEach((column, i) => { placeAt[column] = i; });
  const own = table.columns.filter((column) => !placed.has(column));
  const crsAt = own.indexOf("crs");
  // A negative cell is an index into the page's pool of values that repeat,
  // so the rows that share a link or a railcard record share one object.
  const value = (cell) => (typeof cell === "number" && cell < 0 ? pool[-cell - 1] : cell);
  return table.rows.map((cells) => {
    const row = {};
    const station = placed.size ? places.rows[value(cells[crsAt])] : null;
    let at = 0;
    for (const column of table.columns) {
      if (placed.has(column)) {
        row[column] = station ? station[placeAt[column]] : null;
        continue;
      }
      let cell = value(cells[at++]);
      if (column === "railcards") cell = unpackRailcards(cell, codec.railcards);
      else if (column === "tickets") cell = unpackTickets(cell, codec.tickets);
      row[column] = cell;
    }
    return row;
  });
}
for (const key of ["destinations", "singleDestinations", "anytimeDestinations", "stations"]) {
  DATA[key] = hydrate(DATA[key]);
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
const railStop = document.getElementById("railStop");
const empty = document.getElementById("empty");
const more = document.getElementById("more");
const pagination = document.getElementById("pagination");
const pageStatus = document.getElementById("pageStatus");
const previousPage = document.getElementById("previousPage");
const nextPage = document.getElementById("nextPage");
