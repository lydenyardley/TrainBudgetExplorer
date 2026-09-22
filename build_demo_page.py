"""Write a self-contained page listing every destination inside a budget.

The page runs off one embedded JSON payload and filters in the browser, so the
slider is instant and no server is needed. Point it at the synthetic feeds now,
then at the downloaded feeds, with no change to the page:

    python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN
    python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRA --out demo.html

The synthetic feed invents `GRN` for Grantham; the real code is `GRA`.

A destination is carried at two prices: the cheapest return for one adult, and
the total for two adults travelling together on a Two Together Railcard. The
page lets the reader choose which one the budget applies to, because those are
different questions with different answers.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
from retailer import AFFILIATE_NETWORKS, DEFAULT_PROVIDER, pairing_warning, ticket_link

EVERYTHING_PENCE = 1_000_000
TWO_TOGETHER = "Two Together"
DEPARTURE_LIMIT = 5
DEFAULT_NOTE = (
    "Synthetic demo data: the stations, fares, and times are invented to exercise "
    "the pipeline. Real fares and times replace them once the feed download clears."
)
# Said on the page whenever the link cannot carry the search, which is the
# default (adr/ADR-0018-the-pages-default-link.md). It states what the reader has
# to do, and what does not change, because a fallback the reader only discovers on
# the seller's site is worse than one they were told about.
LINK_NOTE_FALLBACK = (
    "The ticket link opens the seller's own search page, so the journey is not filled in for "
    "you: enter the origin, the destination, the date, and how many of you are travelling. "
    "The price above is the railway's own walk-up fare, so it is the same whichever seller "
    "you buy it from."
)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the budget explorer demo page.")
    parser.add_argument("--feed", required=True, help="fares feed folder or zip")
    parser.add_argument("--timetable", default=None, help="CIF timetable feed folder or zip")
    parser.add_argument(
        "--origin",
        default="GRN",
        help="origin CRS code. Grantham's real code is GRA; the synthetic feed invents GRN",
    )
    parser.add_argument("--out", default="demo.html", help="page to write")
    parser.add_argument("--max-changes", type=int, default=1)
    parser.add_argument("--date", default=None, help="service date as YYYY-MM-DD")
    parser.add_argument("--note", default=DEFAULT_NOTE, help="provenance note for the footer")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER, help="ticket seller to link to")
    parser.add_argument("--adults", type=int, default=2, help="party size sent to the seller")
    parser.add_argument(
        "--departures",
        type=int,
        default=DEPARTURE_LIMIT,
        help="journeys to list under each destination",
    )
    parser.add_argument(
        "--affiliate-network",
        default=None,
        choices=sorted(AFFILIATE_NETWORKS),
        help="wrap ticket links for tracking. Off by default: see ADR-0001 and ADR-0014",
    )
    parser.add_argument("--advertiser-id", default=None, help="the seller's id in the network")
    parser.add_argument("--publisher-id", default="", help="your id in the network")
    parser.add_argument(
        "--link-mode",
        default="fallback",
        choices=("deep", "fallback"),
        help="fallback (default) sends the seller's own search page; deep sends the "
        "search and needs a link somebody has opened. See ADR-0018",
    )
    parser.add_argument(
        "--attribution",
        default=None,
        help="licence-required wording to carry in the footer, once the terms are read",
    )
    parser.add_argument(
        "--analytics-snippet",
        default=None,
        help="file whose contents are injected before </body>, for counting referrers",
    )
    return parser.parse_args(argv)


def build_payload(
    fares: FaresDb,
    timetable: TimetableDb | None,
    origin_crs: str,
    *,
    max_changes: int = 1,
    day: date | None = None,
    note: str = DEFAULT_NOTE,
    attribution: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    # Fallback by default: the parameterised link is not known to land on a
    # search at either seller, and a link that tells a reader there are no trains
    # is worse than one that asks them to type four things.
    mode: str = "fallback",
    adults: int = 2,
    network: str | None = None,
    advertiser_id: str | None = None,
    publisher_id: str = "",
    departure_limit: int = DEPARTURE_LIMIT,
) -> dict:
    """Every priced destination from the origin, with both party prices.

    Each destination carries the ticket links and the next few journeys. The
    journeys are options in the feed, not a booking: the fare reported is a
    walk-up fare valid on any of them, which is why no single one is chosen for
    the reader.
    """
    origin = fares.locations_by_crs[origin_crs.strip().upper()]
    single = {row.crs: row for row in fares.destinations_within(origin.crs, EVERYTHING_PENCE, adults=1)}
    pair = (
        {
            row.crs: row
            for row in fares.destinations_within(
                origin.crs,
                EVERYTHING_PENCE,
                adults=2,
                railcard=TWO_TOGETHER,
                party_budget=True,
            )
        }
        if fares.railcard_code(TWO_TOGETHER)
        else {}
    )

    destinations = []
    tracked = False
    disclosure: str | None = None
    for crs, one in sorted(single.items(), key=lambda item: item[1].best_pence):
        together = pair.get(crs)
        journey = (
            timetable.best_journey(origin.crs, crs, max_changes=max_changes, day=day)
            if timetable
            else None
        )
        options = (
            timetable.departures(origin.crs, crs, max_changes=max_changes, day=day, limit=departure_limit)
            if timetable
            else []
        )
        link = ticket_link(
            origin.crs,
            crs,
            provider=provider,
            when=day,
            adults=adults,
            network=network,
            advertiser_id=advertiser_id,
            publisher_id=publisher_id,
            mode=mode,
        )
        tracked = tracked or link.tracked
        disclosure = disclosure or link.disclosure
        destinations.append(
            {
                "crs": crs,
                "name": one.station,
                "adultPence": one.best_pence,
                "partyPence": together.party_pence if together else one.best_pence * 2,
                "railcardPence": together.railcard_pence if together else None,
                "ticket": one.ticket_code,
                "offPeak": one.off_peak,
                "minutes": journey.duration if journey else None,
                "changes": journey.changes if journey else None,
                "legs": [leg.train_uid for leg in journey.legs] if journey else [],
                "link": {"url": link.url, "label": link.label, "rel": link.rel},
                "departures": [
                    {"depart": option.departure, "arrive": option.arrival, "changes": option.changes}
                    for option in options
                ],
            }
        )

    origin_row = fares.locations_by_crs[origin.crs]
    return {
        "origin": {"crs": origin_row.crs, "name": origin_row.name},
        "destinations": destinations,
        "hasJourneys": timetable is not None,
        "hasTwoTogether": bool(pair),
        "serviceDate": day.isoformat() if day else None,
        "note": note,
        "attribution": attribution,
        "linkNote": LINK_NOTE_FALLBACK if mode == "fallback" else None,
        "feed": fares.stats(),
        "timetable": timetable.stats() if timetable else None,
        "adults": adults,
        "tracked": tracked,
        "disclosure": disclosure,
        "railcardNote": (
            f"Sellers do not accept a railcard in a link, so the price shown for two with a "
            f"{TWO_TOGETHER} Railcard is what it costs with the card: tick the railcard box on "
            "their site."
        ),
        # Without a date every schedule in the feed is read, so a train that has
        # a change of plan appears as its permanent and its covering version.
        "dateNote": (
            None
            if day or timetable is None
            else "No date was given, so every schedule in the feed is read: a train whose plan "
            "has changed appears twice, and Sunday-only trains appear on every day."
        ),
    }


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where can we go from __ORIGIN__ for &pound;__BUDGET__?</title>
<style>
  :root { --bg: #fff; --fg: #11161d; --line: #d0d5dd; --muted: #5b6472; --accent: #14509b;
          --best: rgba(20, 80, 155, .07); --field: #fff; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #14181d; --fg: #e7ebf0; --line: #3a424c; --muted: #9aa4b2; --accent: #7db4f5;
            --best: rgba(125, 180, 245, .12); --field: #1c2127; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 1.5rem; max-width: 60rem;
         background: var(--bg); color: var(--fg);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
  .sub { color: var(--muted); margin: 0 0 1.25rem; }
  .controls { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
              padding: 1rem; border: 1px solid var(--line); border-radius: .5rem; }
  .budget { font-size: 2rem; font-weight: 600; color: var(--accent); letter-spacing: -.01em; }
  input[type=range] { width: 100%; accent-color: var(--accent); }
  fieldset { border: 0; margin: 0; padding: 0; display: grid; gap: .35rem; }
  legend, label.caption { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
  .choices label { display: block; font-size: .95rem; color: var(--fg); }
  input[type=search] { width: 100%; padding: .5rem; border: 1px solid var(--line); border-radius: .35rem;
                      font: inherit; color: var(--fg); background: var(--field); }
  #summary { margin: 1.25rem 0 .5rem; font-weight: 600; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: .5rem .4rem; border-bottom: 1px solid var(--line); }
  th { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
  .toggle { border: 1px solid var(--line); background: var(--field); color: var(--accent);
            border-radius: .3rem; font: inherit; font-size: .85rem; padding: .1rem .4rem;
            margin-left: .5rem; cursor: pointer; }
  .toggle[aria-expanded=true] { border-color: var(--accent); }
  .buy { color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor;
         white-space: nowrap; }
  tr.detail td { background: var(--best); border-bottom: 1px solid var(--line); }
  tr.detail ul { margin: 0; padding-left: 1.1rem; }
  tr.detail li { font-variant-numeric: tabular-nums; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.best td { background: var(--best); }
  .tag { font-size: .75rem; color: var(--muted); }
  #empty { color: var(--muted); }
  #more { color: var(--muted); font-size: .9rem; }
  .copybox { width: 100%; font: inherit; font-size: .9rem; color: var(--fg); background: var(--field);
             border: 1px solid var(--line); border-radius: .35rem; padding: .5rem; resize: vertical; }
  .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
             clip-path: inset(50%); white-space: nowrap; border: 0; }
  footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }
  code { font-size: .95em; }
  /* On a phone the table reflows into stacked rows, because a six-column table
     pushes the ticket action off-screen (ADR-0019). The markup stays a real
     table for desktop and assistive technology; only the display changes, and
     flex wrapping means no cell can sit outside the viewport however long a
     station name or fare code is. */
  @media (max-width: 40rem) {
    body { padding: 1rem .75rem; }
    table, tbody { display: block; }
    thead { display: none; }
    tr { display: flex; flex-wrap: wrap; align-items: baseline; gap: .1rem .75rem;
         padding: .5rem 0; border-bottom: 1px solid var(--line); }
    td { display: block; border-bottom: 0; padding: .1rem .25rem; }
    td:first-child { flex: 1 1 100%; padding-left: 0; font-weight: 600; }
    td.num { text-align: left; }
    td:last-child { margin-left: auto; }
    tr.detail td { flex: 1 1 100%; padding: .5rem 0; }
    tr.best { background: var(--best); }
  }
</style>
</head>
<body>
<h1>Where can we go from __ORIGIN__?</h1>
<p class="sub">Every destination reachable by train for the budget below, with the fastest journey time and the number of changes.</p>

<div class="controls">
  <div>
    <label class="caption" for="budget">Budget</label>
    <div class="budget" id="budgetOut">&pound;__BUDGET__</div>
    <input id="budget" type="range" min="1" max="__MAXPOUNDS__" step="1" value="__BUDGET__"
           aria-describedby="budgetHint">
    <div class="tag" id="budgetHint">Drag to change what we can afford.</div>
  </div>
  <fieldset class="choices">
    <legend>The budget covers</legend>
    <label><input type="radio" name="unit" value="adult" checked> One adult, standard fare</label>
    <label><input type="radio" name="unit" value="party"> The two of us, Two Together Railcard</label>
  </fieldset>
  <div>
    <label class="caption" for="q">Prefer a city or town?</label>
    <input id="q" type="search" placeholder="Type part of a name or code, e.g. Lincoln" autocomplete="off">
  </div>
</div>

<p id="summary"></p>
<table>
  <thead><tr><th>Station</th><th class="num">Price</th><th class="num">Time</th><th class="num">Changes</th><th>Ticket</th><th>Tickets</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<p id="empty" hidden>Nothing inside this budget. Raise it or switch who it covers.</p>
<p id="more" hidden></p>

<footer>
  <p id="attribution" hidden></p>
  <p>__NOTE__</p>
  <p>Cheapest Anytime or Off-Peak return found in the feed. Advance single fares can be cheaper, and the tool does not promise them. A return journey is assumed. The times are options in the timetable, and the fare shown is valid on all of them, so none is picked for you.</p>
  <p id="railcardNote"></p>
  <p id="linkNote" hidden></p>
  <p class="tag" id="provenance"></p>
  <p id="disclosure" hidden></p>
  <p id="copyStatus" role="status" class="sr-only"></p>
</footer>

<script>
const DATA = __DATA__;
const rows = document.getElementById("rows");
const budget = document.getElementById("budget");
const budgetOut = document.getElementById("budgetOut");
const summary = document.getElementById("summary");
const empty = document.getElementById("empty");
const more = document.getElementById("more");
const query = document.getElementById("q");
const PAGE = 40;

const money = (pence) => "\u00a3" + (pence / 100).toFixed(2).replace(/\\.00$/, "");
const duration = (minutes) => {
  if (minutes === null || minutes === undefined) return "-";
  const hours = Math.floor(minutes / 60);
  return hours ? hours + "h " + String(minutes % 60).padStart(2, "0") + "m" : minutes + "m";
};
const clock = (minutes) => {
  const hour = Math.floor(minutes / 60) % 24;
  return String(hour).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0");
};

function unit() {
  return document.querySelector('input[name="unit"]:checked').value;
}
function priceOf(destination) {
  return unit() === "party" ? destination.partyPence : destination.adultPence;
}
function matches(destination, needle) {
  return destination.name.toLowerCase().includes(needle)
    || destination.crs.toLowerCase() === needle;
}

function render() {
  const cap = Number(budget.value) * 100;
  const needle = query.value.trim().toLowerCase();
  const wanted = DATA.destinations.filter(
    (d) => priceOf(d) <= cap && (!needle || matches(d, needle))
  );
  budgetOut.textContent = money(cap);
  rows.replaceChildren();

  for (const destination of wanted.slice(0, PAGE)) {
    const row = document.createElement("tr");
    if (destination === wanted[0]) row.className = "best";
    const cells = [
      [destination.name + " (" + destination.crs + ")", ""],
      [money(priceOf(destination)), "num"],
      [duration(destination.minutes), "num"],
      [destination.changes === null ? "-" : String(destination.changes), "num"],
      [destination.ticket + (destination.offPeak ? " off-peak" : ""), ""],
    ];
    for (const [text, className] of cells) {
      const cell = document.createElement("td");
      cell.textContent = text;
      if (className) cell.className = className;
      row.append(cell);
    }
    cellWithLinks(row, destination, wanted);
    rows.append(row);
  }

  const what = unit() === "party" ? "for the two of us" : "each";
  summary.textContent = wanted.length
    ? wanted.length + (wanted.length === 1 ? " destination" : " destinations") + " within " + money(cap) + " " + what
    : "No destinations within " + money(cap) + " " + what;
  empty.hidden = wanted.length > 0;
  more.hidden = wanted.length <= PAGE;
  more.textContent = "Showing the " + PAGE + " cheapest of " + wanted.length + ".";
}

function cellWithLinks(row, destination, wanted) {
  // The ticket link sits on the row rather than inside the expander: buying is
  // the action, and hiding it behind a second click loses the click. The
  // expander carries the journeys, which are what a reader checks first.
  const cell = document.createElement("td");
  const link = document.createElement("a");
  link.className = "buy";
  link.href = destination.link.url;
  link.rel = destination.link.rel;
  link.target = "_blank";
  link.textContent = "Tickets";
  link.title = destination.link.label + " search for " + destination.crs;
  cell.append(link);
  if (destination.departures.length) {
    const toggle = document.createElement("button");
    toggle.className = "toggle";
    toggle.type = "button";
    toggle.textContent = destination.departures.length + " times";
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", () => toggleDetail(row, destination, toggle));
    cell.append(toggle);
  }
  // The ticket link is the plain one by default and carries no journey, so the
  // row hands the reader the four things the seller will ask for (ADR-0018).
  const copy = document.createElement("button");
  copy.className = "toggle";
  copy.type = "button";
  copy.textContent = "Copy";
  copy.setAttribute("aria-label", "Copy the journey details for " + destination.name);
  copy.title = "Copy the from, to, date and party size for this row";
  copy.addEventListener("click", () => copyJourney(row, destination, copy));
  cell.append(copy);
  row.append(cell);
}

function toggleDetail(row, destination, toggle) {
  const open = toggle.getAttribute("aria-expanded") === "true";
  toggle.setAttribute("aria-expanded", String(!open));
  if (open) {
    row.nextElementSibling?.remove();
    return;
  }
  const detail = document.createElement("tr");
  detail.className = "detail";
  const cell = document.createElement("td");
  cell.colSpan = 6;
  const list = document.createElement("ul");
  for (const option of destination.departures) {
    const item = document.createElement("li");
    item.textContent = clock(option.depart) + " depart, " + clock(option.arrive) + " arrive, " +
      (option.changes ? option.changes + " change(s)" : "no change");
    list.append(item);
  }
  cell.append(list);
  detail.append(cell);
  row.after(detail);
}

function provenance() {
  const parts = [
    "Origin " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    DATA.destinations.length + " priced destinations in the feed",
  ];
  if (DATA.hasJourneys) {
    parts.push(DATA.serviceDate ? "services on " + DATA.serviceDate : "typical services in the feed");
  } else {
    parts.push("no timetable loaded, so no times are shown");
  }
  if (!DATA.hasTwoTogether) parts.push("no Two Together railcard found, so party prices are doubled");
  document.getElementById("provenance").textContent = parts.join(" \u00b7 ");
  document.getElementById("railcardNote").textContent = DATA.railcardNote;
  // What the reader has to do for themselves when the link is the plain one.
  if (DATA.linkNote) {
    const linkNote = document.getElementById("linkNote");
    linkNote.textContent = DATA.linkNote;
    linkNote.hidden = false;
  }
  if (DATA.dateNote) {
    const note = document.createElement("p");
    note.textContent = DATA.dateNote;
    document.getElementById("railcardNote").after(note);
  }
  // The licence wording, when there is some. It sits above the note rather than
  // in a comment, because a term that has to be visible is not satisfied by
  // being present in the file.
  if (DATA.attribution) {
    const attribution = document.getElementById("attribution");
    attribution.textContent = DATA.attribution;
    attribution.hidden = false;
  }
  if (DATA.tracked) {
    const disclosure = document.getElementById("disclosure");
    disclosure.textContent = DATA.disclosure;
    disclosure.hidden = false;
  }
}

const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

// Formatted from the ISO string by hand rather than through Date: new
// Date("2026-10-05") is parsed as UTC midnight, which prints as the 4th for any
// reader behind UTC. A copied date that is off by a day is worse than none.
function humanDate(iso) {
  const parts = iso.split("-").map(Number);
  return parts[2] + " " + MONTHS[parts[1] - 1] + " " + parts[0];
}

// What the reader has to type on the seller's own site, because the ticket link
// carries nothing (ADR-0018). The railcard is named only when the party price is
// what is on screen, and it is named as something to tick rather than sent
// anywhere, because no seller accepts it in a link (ADR-0014).
function journeyText(destination) {
  const together = unit() === "party";
  const lines = [
    "From: " + DATA.origin.name + " (" + DATA.origin.crs + ")",
    "To: " + destination.name + " (" + destination.crs + ")",
  ];
  if (DATA.serviceDate) lines.push("Date: " + humanDate(DATA.serviceDate));
  lines.push("Passengers: " + (together ? DATA.adults + " adults" : "1 adult"));
  if (together) lines.push("Two Together Railcard: tick the box on the seller's site");
  return lines.join("\\n");
}

function showCopyBox(row, text) {
  const next = row.nextElementSibling;
  if (next && next.classList.contains("detail")) next.remove();
  const detail = document.createElement("tr");
  detail.className = "detail";
  const cell = document.createElement("td");
  cell.colSpan = 6;
  const box = document.createElement("textarea");
  box.className = "copybox";
  box.readOnly = true;
  box.rows = 5;
  box.value = text;
  box.setAttribute("aria-label", "Journey details to copy");
  cell.append(box);
  detail.append(cell);
  row.after(detail);
  box.focus();
  box.select();
}

async function copyJourney(row, destination, button) {
  const text = journeyText(destination);
  const status = document.getElementById("copyStatus");
  const done = () => {
    button.textContent = "Copied";
    status.textContent = "Journey details copied: " + text.split("\\n").join(". ");
    window.setTimeout(() => { button.textContent = "Copy"; }, 2000);
  };
  // Never claim a copy that did not happen. Clipboard access is refused when a
  // page is opened from a file or served without a secure context, so the
  // reader is shown the text instead of being told it is on their clipboard.
  const manual = () => {
    button.textContent = "Select below";
    status.textContent = "Could not copy automatically. The details are shown under the row.";
    showCopyBox(row, text);
  };
  if (!navigator.clipboard || !navigator.clipboard.writeText) return manual();
  try {
    await navigator.clipboard.writeText(text);
    done();
  } catch (error) {
    manual();
  }
}

budget.addEventListener("input", render);
query.addEventListener("input", render);
for (const radio of document.querySelectorAll('input[name="unit"]')) radio.addEventListener("change", render);
provenance();
render();
</script>
__ANALYTICS__
</body>
</html>
"""


def render_page(payload: dict, *, budget_pounds: int, analytics: str = "") -> str:
    """Fill the template from the payload.

    ``analytics`` is whatever snippet the owner chose for counting referrers. It
    is injected as given, and empty by default, so the page is self-contained
    unless someone deliberately decides otherwise.
    """
    prices = [row["adultPence"] for row in payload["destinations"]]
    prices += [row["partyPence"] for row in payload["destinations"]]
    ceiling = max(1, -(-max(prices or [100]) // 100)) if prices else 100
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        TEMPLATE.replace("__DATA__", embedded)
        .replace("__ORIGIN__", payload["origin"]["name"])
        .replace("__MAXPOUNDS__", str(ceiling))
        .replace("__BUDGET__", str(budget_pounds))
        .replace("__NOTE__", payload["note"])
        .replace("__ANALYTICS__", analytics)
    )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)

    day: date | None = None
    if args.date:
        try:
            day = date.fromisoformat(args.date)
        except ValueError:
            print(f"date {args.date!r} is not YYYY-MM-DD", file=sys.stderr)
            return 2

    fares = FaresDb().load_feed(args.feed)
    timetable = TimetableDb().load_feed(args.timetable) if args.timetable else None
    try:
        payload = build_payload(
            fares,
            timetable,
            args.origin,
            max_changes=args.max_changes,
            day=day,
            note=args.note,
            attribution=args.attribution,
            provider=args.provider,
            mode=args.link_mode,
            adults=args.adults,
            network=args.affiliate_network,
            advertiser_id=args.advertiser_id,
            publisher_id=args.publisher_id,
            departure_limit=args.departures,
        )
    except KeyError:
        print(f"origin {args.origin!r} not found in feed. Files read: {fares.files_read}", file=sys.stderr)
        return 2

    analytics = ""
    if args.analytics_snippet:
        try:
            analytics = Path(args.analytics_snippet).read_text(encoding="utf-8")
        except OSError as error:
            print(f"could not read {args.analytics_snippet!r}: {error}", file=sys.stderr)
            return 2

    out = Path(args.out)
    out.write_text(render_page(payload, budget_pounds=20, analytics=analytics), encoding="utf-8")
    print(f"wrote {out} with {len(payload['destinations'])} destinations from {payload['origin']['name']}")
    print(f"ticket links to {args.provider}, {args.adults} adult(s), link mode {args.link_mode}")
    if args.link_mode == "fallback":
        print("fallback links: readers get the seller's own search page, not their search")
    if args.attribution:
        print("the page carries the licence attribution wording")
    if analytics:
        print("an analytics snippet was injected, so the page is no longer entirely self-contained")
    if payload["tracked"]:
        print("affiliate tracking is ON, and the page carries the disclosure")
    else:
        print("affiliate tracking is off, so the links are plain and untracked")
    warning = pairing_warning(args.provider, args.affiliate_network)
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    if not payload["hasJourneys"]:
        print("no timetable given, so the page shows prices without times")
    if not payload["hasTwoTogether"]:
        print("no Two Together railcard in the feed, so party prices are doubled instead of discounted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
