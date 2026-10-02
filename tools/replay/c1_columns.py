"""C1: the table's cells answer to their own headers.

The header row and the row builder had drifted apart: the header read
Station, Price, Time, Changes, Fare code, Tickets while the cells were written
Station, Time, Changes, Price, Fare code, Tickets. Every column was therefore
labelled with its neighbour's contents -- the Price column showed "No service"
and the Changes column showed the fare. This writes both from one list.
"""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_LOOP = '''  for (const destination of pageItems) {
    const row = document.createElement("tr");
    const cells = [
      [destination.name + " (" + destination.crs + ")", "", "Station"],
    ];
    if (DATA.hasJourneys) {
      // S23: a dash said nothing about which of three different absences this
      // is. The fare is real either way, so the cell names the absence and
      // says so in its tooltip too.
      const missing = destination.journeyState !== "found";
      const tone = missing ? "num missing" : "num";
      cells.push([missing ? "No service" : duration(destination.minutes), tone, "Time"]);
      cells.push([missing ? "Unknown" : String(destination.changes), tone, "Changes"]);
    }
    // The FARE and CONDITIONS columns are gone as columns (finding, 29
    // September 2026): on the reviewed page all 20 rows repeated "Unrestricted
    // Anytime Day Return" and "No travel conditions on this fare in the feed."
    // -- 40 cells restating the mode the reader had already chosen with the
    // mode control, and between them the reason every row stood two lines
    // tall. Neither sentence is dropped; both are in the row's own disclosure,
    // beside the times. The row carries the fare's code instead, which is the
    // part that differs between fares and the part a seller asks for.
    row.dataset.crs = destination.crs;
    for (const [text, className, label] of cells) {
      const cell = document.createElement("td");
      cell.dataset.label = label;
      cell.textContent = text;
      if (className) cell.className = className;
      if (label === "Station" && destination.heritageSites?.length) {
        const heritage = document.createElement("span");
        heritage.className = "heritage-proof";
        heritage.append("World heritage: ");
        destination.heritageSites.forEach((site, index) => {
          if (index) heritage.append("; ");
          const link = document.createElement("a");
          link.href = site.url;
          link.target = "_blank";
          link.rel = "noopener";
          link.textContent = site.name;
          link.title = "UNESCO World Heritage List site " + site.id;
          heritage.append(link);
        });
        cell.append(heritage);
      }
      row.append(cell);
    }
    row.append(priceCell(destination));
    row.append(fareCodeCell(destination));
    cellWithLinks(row, destination, wanted);
    rows.append(row);
  }
'''

NEW_LOOP = '''  for (const destination of pageItems) {
    const row = document.createElement("tr");
    row.dataset.crs = destination.crs;
    // The header is one list and the cells are the same list, in the same
    // order, built here. They used to be two lists written in different places
    // and they had drifted: the header read Station, Price, Time, Changes,
    // Fare code, Tickets while the cells were written Station, Time, Changes,
    // Price, Fare code, Tickets, so the Price column showed "No service" and
    // the Changes column showed the fare. A prices-only build stands two of
    // these columns down, and it stands down the same two here and in the
    // header for the same reason.
    const cells = [stationCell(destination), priceCell(destination)];
    if (DATA.hasJourneys) {
      cells.push(journeyCell(destination, "Time"), journeyCell(destination, "Changes"));
    }
    cells.push(fareTypeCell(destination));
    for (const cell of cells) row.append(cell);
    cellWithLinks(row, destination, wanted);
    rows.append(row);
  }
'''

OLD_HEADER = '''  <thead><tr><th scope="col">Station</th><th scope="col" class="num">Price</th><th scope="col" class="num">Time</th><th scope="col" class="num">Changes</th><th scope="col">Fare code</th><th scope="col">Tickets</th></tr></thead>'''

NEW_HEADER = '''  <thead><tr><th scope="col">Station</th><th scope="col" class="num">Price</th><th scope="col" class="num">Time</th><th scope="col" class="num">Changes</th><th scope="col">Fare type</th><th scope="col">Tickets</th></tr></thead>'''

OLD_FARE_CODE_CELL = '''// The row's fare, as a cell of its own: the feed's own code, and one word
// when the fare is one a reader should open. Nothing is said here about what
// every row has in common, because the mode control above the table says it
// once (finding, 29 September 2026).
function fareCodeCell(destination) {
  const cell = document.createElement("td");
  cell.className = "code";
  cell.dataset.label = "Fare code";
  const code = document.createElement("span");
  code.className = "ticket-code";
  code.textContent = destination.ticket || "Not stated";
  if (!destination.ticket) cell.classList.add("missing");
  cell.append(code);
  const flag = fareFlag(destination);
  if (flag) {
    const mark = document.createElement("span");
    mark.className = "condition-flag";
    mark.textContent = flag;
    cell.append(" ", mark);
  }
  cell.title = fareSummary(destination);
  return cell;
}
'''

NEW_CELLS = '''// The destination, and nothing else: the name, the three-letter code a seller
// asks for, and the World Heritage proof where the feed names one. The station
// is the widest thing in the row, so the column takes the slack and the
// numbers beside it keep one position each.
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
  if (destination.heritageSites?.length) {
    const heritage = document.createElement("span");
    heritage.className = "heritage-proof";
    heritage.append("World heritage: ");
    destination.heritageSites.forEach((site, index) => {
      if (index) heritage.append("; ");
      const link = document.createElement("a");
      link.href = site.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = site.name;
      link.title = "UNESCO World Heritage List site " + site.id;
      heritage.append(link);
    });
    cell.append(heritage);
  }
  return cell;
}

// Time and Changes, in one builder because they are the same fact read twice:
// a journey this build could not find has neither a duration nor a change
// count, and saying "Unknown" beside a real duration would be a lie. S23's
// point stands -- a dash said nothing about which of three different absences
// it was, so the cell names the absence.
function journeyCell(destination, column) {
  const missing = destination.journeyState !== "found";
  const cell = document.createElement("td");
  cell.className = missing ? "num missing" : "num";
  cell.dataset.label = column;
  if (column === "Time") {
    cell.textContent = missing ? "No service" : duration(destination.minutes);
    return cell;
  }
  const count = document.createElement("span");
  count.className = "changes-count";
  count.textContent = missing ? "Unknown" : changeCount(destination.changes);
  cell.append(count);
  // Q2 (ADR-0045): the station a journey changes at is the part a reader can
  // act on, and it was only ever inside a disclosure they had to open on every
  // row to find. It sits under the count now, in the column whose header is
  // the word "Changes".
  const via = interchangeLine(destination);
  if (via) cell.append(via);
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

// The fare in the reader's own three words. The feed's code is a seller\\'s
// vocabulary -- SDR, 2AS, BPS -- and it was the column, on every row, in front
// of the one number the reader came for. It is still here, in the row\\'s own
// disclosure under "Feed record", which is where a code belongs: available
// when it is asked for, invisible until then.
function fareTypeCell(destination) {
  const cell = document.createElement("td");
  cell.className = "fare-type";
  cell.dataset.label = "Fare type";
  const kind = document.createElement("span");
  kind.className = "fare-kind";
  kind.textContent = fareTypeWord(destination);
  cell.append(kind);
  cell.title = fareSummary(destination);
  return cell;
}

function fareTypeWord(destination) {
  if (destination.isAdvance) return "Advance";
  if (destination.restrictionCode) return "Restricted";
  return "Regular";
}
'''

OLD_SPLIT = '''function splitNote(destination) {
  const stations = destination.changeStations || [];
  if (!stations.length) return null;
  const named = stations.map((station) => station.name + " (" + station.crs + ")");
  const note = document.createElement("p");
  note.className = "split";
  note.textContent = "Change at " + named.join(" and ") +
    ". A split ticket \\u2014 one ticket to that station and another from it " +
    "\\u2014 can sometimes cost less than this through fare; this page prices the through fare only.";
  return note;
}'''

NEW_SPLIT = '''function splitNote(destination) {
  const stations = destination.changeStations || [];
  if (!stations.length) return null;
  // The station itself is named in the Changes column now, so this says only
  // the thing that is still worth saying and is nowhere else on the page: the
  // through fare is not the cheapest way to buy this journey, and this page
  // cannot tell you which two tickets would be.
  const note = document.createElement("p");
  note.className = "split";
  note.textContent = "A split ticket \\u2014 one ticket to the station above and " +
    "another from it \\u2014 can sometimes cost less than this through fare. " +
    "This page prices the through fare only.";
  return note;
}'''

patch(
    "page_templates.py",
    [
        (OLD_HEADER, NEW_HEADER),
        (OLD_LOOP, NEW_LOOP),
        (OLD_FARE_CODE_CELL, NEW_CELLS),
        (OLD_SPLIT, NEW_SPLIT),
    ],
)

# The fare-code column became a fare-type cell, and the browser suite's wrap
# check selects that column by class name. Both renames -- the page's and the
# suite's -- were made by hand during the pass rather than by this script, so
# the suite's rename was in no patch script at all. Replaying from before the
# pass then produced a suite still asking for `.ticket-code` where the page had
# already moved on, and the next script in the chain, r1, refused to apply
# because its anchor expected the renamed selector. The chain stopped there and
# stayed there: `.ticket-code` names nothing in the page, so the check silently
# selected no column and nobody reading a green run would have known.
#
# This is the edit that was missing. It is here rather than in a later script
# because this is the script that made the change it follows from.
OLD_WRAP_SELECTOR = (
    '        ...document.querySelectorAll("#rows td.num, #rows .ticket-code"),'
)
NEW_WRAP_SELECTOR = (
    '        ...document.querySelectorAll("#rows td.num, #rows .fare-type"),'
)

patch("tests/browser_test.cjs", [(OLD_WRAP_SELECTOR, NEW_WRAP_SELECTOR)])
