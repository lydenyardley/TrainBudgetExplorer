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
function hydrate(table) {
  if (!table || !Array.isArray(table.rows)) return table || [];
  const pool = DATA.pool || [];
  return table.rows.map((cells) => {
    const row = {};
    for (let i = 0; i < table.columns.length; i += 1) {
      const cell = cells[i];
      // A negative cell is an index into the page's pool of values that repeat,
      // so the rows that share a link or a railcard record share one object.
      row[table.columns[i]] = typeof cell === "number" && cell < 0 ? pool[-cell - 1] : cell;
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
