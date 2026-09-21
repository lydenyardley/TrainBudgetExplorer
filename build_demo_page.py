"""Write a self-contained page listing every destination inside a budget.

The page runs off one embedded JSON payload and filters in the browser, so the
slider is instant and no server is needed. Point it at the synthetic feeds now,
then at the downloaded feeds, with no change to the page:

    python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN
    python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRN --out demo.html

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

EVERYTHING_PENCE = 1_000_000
TWO_TOGETHER = "Two Together"
DEFAULT_NOTE = (
    "Synthetic demo data: the stations, fares, and times are invented to exercise "
    "the pipeline. Real fares and times replace them once the feed download clears."
)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the budget explorer demo page.")
    parser.add_argument("--feed", required=True, help="fares feed folder or zip")
    parser.add_argument("--timetable", default=None, help="CIF timetable feed folder or zip")
    parser.add_argument("--origin", default="GRN", help="origin CRS code, e.g. GRN")
    parser.add_argument("--out", default="demo.html", help="page to write")
    parser.add_argument("--max-changes", type=int, default=1)
    parser.add_argument("--date", default=None, help="service date as YYYY-MM-DD")
    parser.add_argument("--note", default=DEFAULT_NOTE, help="provenance note for the footer")
    return parser.parse_args(argv)


def build_payload(
    fares: FaresDb,
    timetable: TimetableDb | None,
    origin_crs: str,
    *,
    max_changes: int = 1,
    day: date | None = None,
    note: str = DEFAULT_NOTE,
) -> dict:
    """Every priced destination from the origin, with both party prices."""
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
    for crs, one in sorted(single.items(), key=lambda item: item[1].best_pence):
        together = pair.get(crs)
        journey = (
            timetable.best_journey(origin.crs, crs, max_changes=max_changes, day=day)
            if timetable
            else None
        )
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
        "feed": fares.stats(),
        "timetable": timetable.stats() if timetable else None,
    }


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where can we go from __ORIGIN__ for __BUDGET__?</title>
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
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.best td { background: var(--best); }
  .tag { font-size: .75rem; color: var(--muted); }
  #empty { color: var(--muted); }
  #more { color: var(--muted); font-size: .9rem; }
  footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }
  code { font-size: .95em; }
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
  <thead><tr><th>Station</th><th class="num">Price</th><th class="num">Time</th><th class="num">Changes</th><th>Ticket</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<p id="empty" hidden>Nothing inside this budget. Raise it or switch who it covers.</p>
<p id="more" hidden></p>

<footer>
  <p>__NOTE__</p>
  <p>Cheapest Anytime or Off-Peak return found in the feed. Advance single fares can be cheaper, and the tool does not promise them. A return journey is assumed.</p>
  <p class="tag" id="provenance"></p>
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
}

budget.addEventListener("input", render);
query.addEventListener("input", render);
for (const radio of document.querySelectorAll('input[name="unit"]')) radio.addEventListener("change", render);
provenance();
render();
</script>
</body>
</html>
"""


def render_page(payload: dict, *, budget_pounds: int) -> str:
    """Fill the template from the payload."""
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
        )
    except KeyError:
        print(f"origin {args.origin!r} not found in feed. Files read: {fares.files_read}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.write_text(render_page(payload, budget_pounds=20), encoding="utf-8")
    print(f"wrote {out} with {len(payload['destinations'])} destinations from {payload['origin']['name']}")
    if not payload["hasJourneys"]:
        print("no timetable given, so the page shows prices without times")
    if not payload["hasTwoTogether"]:
        print("no Two Together railcard in the feed, so party prices are doubled instead of discounted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
