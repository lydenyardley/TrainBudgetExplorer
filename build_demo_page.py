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
import re
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
# The provenance line sits with the prices, not the footer, because where a
# number came from is part of the number. The railcard basis states what the
# Easy Fares reality-check found: the model's third-off estimate sits 5-15p
# ABOVE the database's own discounted price, so it never sends a reader over
# budget on a rounding (checked 2026-09-22, easy_fares_check.py).
DEFAULT_PRICE_SOURCE = "the synthetic demo feed"
DEFAULT_RAILCARD_BASIS = (
    "Railcard prices are estimates - a third off, rounded up to 5p. A check "
    "against the National Rail fares database (Easy Fares demo, 22 September "
    "2026) found the estimate sits 5-15p above the real discounted price, so "
    "any budget that fits the estimate also fits the real fare."
)
# Licence notice wordings (ADR-0020, ADR-0021). The OGL sentence is the
# standard wording; the accuracy notice carries the substance of the Data
# Sharing Agreement's cl. 3.3.2 and its liability clause 7.2. Composed by
# --notices for a real-data build, never applied to a synthetic one by
# default: crediting RDG for invented prices would be false attribution.
NOTICES = {
    "rdg": (
        "Fares and station data: \u00a9 Rail Delivery Group, published through "
        "the Rail Data Marketplace."
    ),
    "ogl": (
        "Contains public sector information licensed under the Open Government "
        "Licence v3.0."
    ),
    "accuracy": (
        "The fares and journey times on this page are provided \u2018as is\u2019, with no "
        "representation as to their accuracy or fitness for a purpose, and they "
        "change without notice: always confirm the price with the seller before "
        "buying. Neither Rail Delivery Group nor Rail Settlement Plan Limited "
        "accepts liability for any loss arising from reliance on this data."
    ),
}
# What the times on the page are, said near them rather than assumed, because
# a journey time read as a promise is a complaint waiting to happen.
PRICING_NOTE = (
    "Times are options in the timetable, not a booking: the fare shown is valid "
    "on every service listed, so none is picked for you."
)

# -- feed metadata ----------------------------------------------------------
# Where the feed came from is recorded once, in metadata.json beside it, and
# every build reads it, so provenance is never retyped by hand and never
# drifts between builds. --price-source still overrides it.
METADATA_NAME = "metadata.json"


def read_feed_metadata(folders: list[Path]) -> dict:
    """The first readable metadata.json found in the feed folders, or empty.

    A zip feed has no folder of its own, but its download usually lands inside
    one, so the caller passes the zip's parent. A file that exists but cannot
    be used is named, because provenance that silently fell back to the
    default is provenance the operator believes is real.
    """
    for folder in folders:
        candidate = folder / METADATA_NAME
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(
                f"warning: {candidate} is unreadable ({error}); the price line "
                "falls back to its default",
                file=sys.stderr,
            )
            return {}
        if not isinstance(data, dict):
            print(f"warning: {candidate} is not a JSON object; ignored", file=sys.stderr)
            return {}
        return data
    return {}


def price_source_from_metadata(metadata: dict) -> str | None:
    """The provenance sentence from the metadata, or None if it names nothing."""
    source = metadata.get("source")
    downloaded = metadata.get("downloaded")
    if source and downloaded:
        return f"the {source}, downloaded {downloaded}"
    if source:
        return f"the {source}"
    return None


def with_base(base_path: str, path: str) -> str:
    """Prefix an internal link with the site's base path, if it has one.

    Hosts that do not serve the site at their domain root (GitHub Pages
    project sites, most shared hosting) need every internal link prefixed;
    a domain root deploy needs plain root-absolute paths. Default is plain.
    """
    return f"{base_path}{path}" if base_path else path


# The privacy page. It is honest by construction: it can only describe what
# the build actually ships, and the two conditional behaviours -- an analytics
# snippet, tracked links -- are named as things that would be disclosed on the
# page itself if they were ever switched on.
PRIVACY = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy</title>
<style>
  :root { --bg:#fff; --fg:#11161d; --muted:#5b6472; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14181d; --fg:#e7ebf0; --muted:#9aa4b2; }
  }
  body { margin:0; padding:1.5rem; max-width:40rem; background:var(--bg); color:var(--fg);
         font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
  h1 { font-size:1.5rem; margin:0 0 1rem; }
  h2 { font-size:1.05rem; margin:1.5rem 0 .25rem; }
  p, li { margin:.4rem 0; }
  .muted { color:var(--muted); }
  a { color:inherit; }
</style>
</head>
<body>
<nav><a href="__BASE__/">Back to the station chooser</a></nav>
<h1>Privacy</h1>
<p>This page works entirely in your browser. There is no account, no sign-in, and nothing you type is stored anywhere: the budget you drag and the filter you type never leave your device.</p>
<h2>What this site does not do</h2>
<ul>
  <li>No cookies are set by this site.</li>
  <li>No analytics run. If the operator later adds analytics, this page will name them here first.</li>
  <li>Nothing about your visit is recorded by this site itself.</li>
</ul>
<h2>Ticket links</h2>
<p>Ticket buttons open the seller's own website in a new tab. Once you are there, that seller's privacy policy applies, not this page. This site receives no information back about whether you bought anything; if tracked links are ever switched on, the footer of the fare pages says so plainly.</p>
<h2>Hosting</h2>
<p>The site is static files served by the operator's chosen host. The host's own logs may record standard technical information such as IP address and pages requested; what happens to it is governed by the operator's hosting arrangement.</p>
<h2>Contact</h2>
<p class="muted">The operator's contact address goes here before the site is published.</p>
<p class="muted">__NOTE__</p>
</body>
</html>
"""
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


def station_slug(name: str, crs: str, taken: set[str]) -> str:
    """A readable address for a station, unique within ``taken``.

    Two stations can share a name, and the CRS code is the disambiguator
    (adr/ADR-0019-one-page-per-station.md): a collision that reached the page as
    two identical links would be a defect, so it is resolved here, at build
    time, where it can be tested.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "station"
    if slug in taken:
        slug = re.sub(r"[^a-z0-9]+", "-", f"{name} {crs}".lower()).strip("-")
    if slug in taken:  # pathological: same name AND code seen twice
        counter = 2
        while f"{slug}-{counter}" in taken:
            counter += 1
        slug = f"{slug}-{counter}"
    taken.add(slug)
    return slug


def notices_or_attribution(args: argparse.Namespace) -> str | list[str] | None:
    """The footer notices: --notices presets composed, or --attribution verbatim.

    --notices wins when both are given, and says so, because silently dropping
    custom wording the operator typed would hide a legal obligation they meant
    to carry.
    """
    if args.notices:
        unknown = [n for n in args.notices.split(",") if n.strip() and n.strip() not in NOTICES]
        if unknown:
            print(
                f"unknown notice(s) {', '.join(unknown)}: choose from {', '.join(sorted(NOTICES))}",
                file=sys.stderr,
            )
            raise SystemExit(2)
        if args.attribution:
            print("--notices given, so --attribution is ignored", file=sys.stderr)
        return [NOTICES[n.strip()] for n in args.notices.split(",") if n.strip()]
    return args.attribution


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
    parser.add_argument(
        "--all-origins",
        action="store_true",
        help="write one page per priceable station under out's folder, plus the chooser",
    )
    parser.add_argument("--max-changes", type=int, default=1)
    parser.add_argument("--date", default=None, help="service date as YYYY-MM-DD")
    parser.add_argument("--note", default=DEFAULT_NOTE, help="provenance note for the footer")
    parser.add_argument(
        "--base-path",
        default="",
        help="prefix for the site's internal links, for hosts that do not serve it "
        "at their domain root, e.g. /trainbudget. No leading/trailing slash needed",
    )
    parser.add_argument(
        "--feed-metadata",
        default=None,
        help="metadata.json for the feeds if it is not beside them (a zip feed's "
        "download folder, say). Found automatically otherwise",
    )
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
        "--price-source",
        default=None,
        help="override the provenance sentence the feed's metadata.json supplies, "
        "e.g. --price-source \"the RSP fares feed, downloaded 3 October 2026\"",
    )
    parser.add_argument(
        "--notices",
        default=None,
        help="comma-separated preset notices: rdg (publisher credit), ogl (Open "
        "Government Licence wording), accuracy (as-is accuracy and liability "
        "notice). Compose them, e.g. --notices rdg,ogl,accuracy",
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
    price_source: str = DEFAULT_PRICE_SOURCE,
    railcard_basis: str | None = DEFAULT_RAILCARD_BASIS,
    base_path: str = "",
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
        # The picker's options (ADR-0019). main() replaces this with the written
        # outputs for a real build; called directly, it carries every station
        # except this origin, from priced flows, so nothing offered can 404.
        "stations": [
            {
                "name": loc.name,
                "crs": loc.crs,
                "href": with_base(base_path, f"/from/{re.sub(r'[^a-z0-9]+', '-', loc.name.lower()).strip('-')}/"),
            }
            for crs, loc in sorted(fares.locations_by_crs.items())
            if crs != origin.crs
        ],
        # Said by the page when this origin priced nothing, so the difference
        # between "nothing inside your budget" and "nothing priced from here at
        # all" is on the page rather than inferred from an empty table.
        "stationCount": len(fares.locations_by_crs),
        "hasJourneys": timetable is not None,
        "hasTwoTogether": bool(pair),
        "serviceDate": day.isoformat() if day else None,
        "note": note,
        "attribution": attribution,
        # Where the numbers on this page came from. It sits with the prices,
        # not in the footer, because where a number came from is part of the
        # number; the footer keeps the licence wording, which is a different
        # reader's question.
        "priceSource": price_source,
        "railcardBasis": railcard_basis,
        # Internal links are prefixed when the host does not serve the site at
        # its domain root (ADR-0024). The template carries it too, for the
        # links that are written as HTML rather than built in JS.
        "baseHref": with_base(base_path, "/"),
        "linkNote": LINK_NOTE_FALLBACK if mode == "fallback" else None,
    # The pricing paragraph is a fixed part of the page, but the payload
    # carries it so tests can assert the page says what the times are.
    "pricingNote": PRICING_NOTE,
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
  /* The budget leads: the biggest type on the page and the wider column. The
     party switch and the town filter refine it, so they share one narrower
     secondary column rather than competing as three equal cards. */
  /* Layouts that set their own display defeat the hidden attribute, so every
     one of them re-declares display:none here. */
  [hidden] { display: none !important; }
  .controls { display: grid; gap: 1.25rem 2rem; grid-template-columns: minmax(16rem, 1.5fr) minmax(12rem, 1fr);
              padding: 1.25rem; border: 1px solid var(--line); border-radius: .5rem; align-items: start; }
  .controls .secondary { display: grid; gap: 1rem; align-content: start; }
  .budget { font-size: 2.75rem; font-weight: 700; color: var(--accent); letter-spacing: -.02em; line-height: 1.1; }
  input[type=range] { width: 100%; accent-color: var(--accent); height: 2.75rem; }
  fieldset { border: 0; margin: 0; padding: 0; display: grid; gap: .35rem; }
  legend, label.caption { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
  /* The whole label is the touch target: the party switch changes every price
     on the page, so a thumb must land it first time. */
  .choices label { display: flex; align-items: center; gap: .5rem; font-size: .95rem; color: var(--fg);
                   padding: .55rem 0; cursor: pointer; }
  .choices input { width: 1.15rem; height: 1.15rem; margin: 0; accent-color: var(--accent); }
  input[type=search] { width: 100%; padding: .5rem; border: 1px solid var(--line); border-radius: .35rem;
                      font: inherit; color: var(--fg); background: var(--field); }
  /* Generous after the controls, tight onto its table: the summary belongs to
     the list below it, not to the panel above. */
  #summary { margin: 1.75rem 0 .5rem; font-weight: 600; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: .5rem .4rem; border-bottom: 1px solid var(--line); }
  th { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
  .toggle { border: 1px solid var(--line); background: var(--field); color: var(--accent);
            border-radius: .3rem; font: inherit; font-size: .85rem; padding: .3rem .55rem;
            margin-left: .75rem; cursor: pointer; position: relative; }
  /* Hit-slop: the visible mark stays small beside its neighbours, but the
     touch target reaches 44px past it. */
  .toggle::after { content: ""; position: absolute; inset: -6px; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: .2rem; }
  ::selection { background: color-mix(in srgb, var(--accent) 25%, transparent); }
  .toggle[aria-expanded=true] { border-color: var(--accent); }
  .buy { color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor;
         white-space: nowrap; position: relative; }
  .buy::after { content: ""; position: absolute; inset: -11px -4px; }
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
  #originPicker { margin: .75rem 0 1rem; }
  #originPicker input[type=search] { width: 100%; max-width: 24rem; padding: .5rem; border: 1px solid var(--line);
                                     border-radius: .35rem; font: inherit; color: var(--fg); background: var(--field); }
  #originPicks { list-style: none; margin: .5rem 0 0; padding: 0; max-width: 24rem; }
  #originPicks a { display: flex; justify-content: space-between; gap: .75rem; padding: .45rem .4rem;
                   color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--line); }
  #originPicks a:hover, #originPicks a:focus-visible { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  #originPicks .code { color: var(--muted); }
  #originNomatch { color: var(--muted); margin-top: .5rem; }
  /* The unpriced-origin message replaces the intro, so it is page-size text in
     the normal foreground colour: a finding, not a footnote. */
  .unpriced { margin: 0 0 1.25rem; }
  #unpriced a { color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor; }
  footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }
  .footnav a { color: inherit; }
  @media (max-width: 44rem) { .footnav { min-height: 44px; display: flex; align-items: center; } }
  code { font-size: .95em; }
  /* On a phone the table reflows into stacked rows, because a six-column table
     pushes the ticket action off-screen (ADR-0019). The markup stays a real
     table for desktop and assistive technology; only the display changes, and
     flex wrapping means no cell can sit outside the viewport however long a
     station name or fare code is. */
  /* 44rem, not 40: measured, the six-column table needs ~700px before its three
     row actions stop wrapping onto a second line, so the stacked layout keeps
     the band between 640 and 704px that the table cannot hold. */
  @media (max-width: 44rem) {
    body { padding: 1rem .75rem; }
    .controls { grid-template-columns: 1fr; gap: 1rem; padding: 1rem; }
    .budget { font-size: 2.5rem; }
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
<h1 id="pageHeading">Where can we go from __ORIGIN__? <button id="changeOrigin" type="button" class="toggle" aria-expanded="false" aria-controls="originPicker">Change</button></h1>
<p class="sub" id="pageIntro">Every destination reachable by train for the budget below, with the fastest journey time and the number of changes.</p>
<p id="unpriced" class="unpriced" hidden></p>

<div id="originPicker" hidden>
  <label class="caption" for="originSearch">Start from a different station</label>
  <input id="originSearch" type="search" placeholder="Type part of a name or its three-letter code" autocomplete="off"
         aria-describedby="originStatus">
  <span id="originStatus" class="sr-only" role="status"></span>
  <ul id="originPicks"></ul>
  <p id="originNomatch" hidden></p>
</div>

<div class="controls">
  <div>
    <label class="caption" for="budget">Budget</label>
    <div class="budget" id="budgetOut">&pound;__BUDGET__</div>
    <input id="budget" type="range" min="1" max="__MAXPOUNDS__" step="1" value="__BUDGET__"
           aria-describedby="budgetHint">
    <div class="tag" id="budgetHint">Drag to change what we can afford.</div>
  </div>
  <div class="secondary">
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
</div>

<p id="summary"></p>
<p class="tag" id="priceSource" hidden></p>
<table>
  <thead><tr><th scope="col">Station</th><th scope="col" class="num">Price</th><th scope="col" class="num">Time</th><th scope="col" class="num">Changes</th><th scope="col">Fare code</th><th scope="col">Tickets</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<p id="empty" hidden>Nothing inside this budget. Raise it or switch who it covers.</p>
<p id="more" hidden></p>

<footer>
  <div id="attribution" hidden></div>
  <p>__NOTE__</p>
  <p>Cheapest Anytime or Off-Peak return found in the feed. Advance single fares can be cheaper, and the tool does not promise them. A return journey is assumed.</p>
  <p>The times on this page are options in the timetable, not a booking: the fare shown is valid on every service listed, so none is picked for you.</p>
  <p id="railcardNote"></p>
  <p id="linkNote" hidden></p>
  <p class="tag" id="railcardBasis" hidden></p>
  <nav class="footnav"><a href="__BASE__/privacy/">Privacy</a></nav>
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

// A prices-only build has no times to show, and two columns of dashes are
// noise where a shorter table is honest: the columns stand down entirely.
if (!DATA.hasJourneys) {
  for (const th of document.querySelectorAll("thead th:nth-child(3), thead th:nth-child(4)")) th.remove();
}
const columnCount = () => document.querySelectorAll("thead th").length;

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
  // An unpriced page has no budget conversation: provenance() has already
  // stood the controls and the table down, and anything this function wrote
  // ("Nothing inside this budget") would contradict the page's own first
  // sentence. So it does nothing at all.
  if (!DATA.destinations.length) return;
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
    ];
    if (DATA.hasJourneys) {
      cells.push([duration(destination.minutes), "num"]);
      cells.push([destination.changes === null ? "-" : String(destination.changes), "num"]);
    }
    cells.push([destination.ticket + (destination.offPeak ? " off-peak" : ""), ""]);
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
  // An unpriced origin has no budget conversation to have, so the summary
  // stays empty rather than implying the budget filtered something out.
  summary.textContent = DATA.destinations.length && wanted.length
    ? wanted.length + (wanted.length === 1 ? " destination" : " destinations") + " within " + money(cap) + " " + what
    : DATA.destinations.length ? "No destinations within " + money(cap) + " " + what : "";
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
  cell.colSpan = columnCount();
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
  // An origin the build could not price is a different page from one whose
  // prices sit outside this budget, so it gets its own first sentence and its
  // own way forward — not an empty table under a slider that can't help.
  if (!DATA.destinations.length) {
    document.getElementById("pageIntro").hidden = true;
    const unpriced = document.getElementById("unpriced");
    const intro = "We couldn't price any journeys from " + DATA.origin.name +
      " (" + DATA.origin.crs + ") in this feed.";
    if (DATA.stations && DATA.stations.length) {
      const link = document.createElement("a");
      link.href = DATA.baseHref;
      link.textContent = "Start from a station we do price";
      unpriced.append(intro + " ", link, ".");
    } else {
      unpriced.textContent = intro + " Nothing was priced from any station, so there is nothing to explore yet.";
    }
    unpriced.hidden = false;
    const controls = document.querySelector(".controls");
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
  // Where the numbers came from, stated beside the prices rather than in the
  // footer, because where a number came from is part of the number.
  if (DATA.priceSource) {
    const line = document.getElementById("priceSource");
    const parts = ["Prices from " + DATA.priceSource];
    if (DATA.serviceDate) parts.push("feed dated " + humanDate(DATA.serviceDate));
    line.textContent = parts.join(", ") + ".";
    line.hidden = false;
  }
  if (DATA.railcardBasis) {
    // Visible small print, not a tooltip: a caveat a reader can only find by
    // hovering is not stated, and touch has no hover at all.
    const basis = document.getElementById("railcardBasis");
    basis.textContent = DATA.railcardBasis;
    basis.hidden = false;
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
  cell.colSpan = columnCount();
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

// The picker (ADR-0019): choosing a station is navigation to that station's
// page, not a filter on this one. The options are real anchors, so keyboard
// handling and accessible naming are the browser's own. The list is built from
// the written outputs, so nothing here can lead to a missing page.
const changeOrigin = document.getElementById("changeOrigin");
const originPicker = document.getElementById("originPicker");
if (changeOrigin && DATA.stations && DATA.stations.length) {
  const originSearch = document.getElementById("originSearch");
  const originPicks = document.getElementById("originPicks");
  const originNomatch = document.getElementById("originNomatch");
  const originStatus = document.getElementById("originStatus");

  function renderPicks() {
    const needle = originSearch.value.trim().toLowerCase();
    const wanted = DATA.stations.filter(
      (s) => !needle || s.name.toLowerCase().includes(needle) || s.crs.toLowerCase() === needle
    );
    originPicks.replaceChildren();
    for (const station of wanted.slice(0, 40)) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = station.href;
      const name = document.createElement("span");
      name.textContent = station.name;
      const code = document.createElement("span");
      code.className = "code";
      code.textContent = station.crs;
      link.append(name, code);
      item.append(link);
      originPicks.append(item);
    }
    if (wanted.length) {
      originNomatch.hidden = true;
    } else {
      originNomatch.textContent = "We don't have prices from '" + originSearch.value.trim() +
        "'. Try the station's name or its three-letter code.";
      originNomatch.hidden = false;
    }
    originStatus.textContent = wanted.length + " station" + (wanted.length === 1 ? "" : "s") + " listed";
  }

  function setPicker(open) {
    changeOrigin.setAttribute("aria-expanded", String(open));
    originPicker.hidden = !open;
    if (open) {
      renderPicks();
      originSearch.focus();
    } else {
      // Escape is a keyboard exit, and focus returns to the control that
      // opened the picker rather than dropping to the top of the page.
      changeOrigin.focus();
    }
  }

  changeOrigin.addEventListener("click", () => {
    setPicker(changeOrigin.getAttribute("aria-expanded") !== "true");
  });
  originPicker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setPicker(false);
  });
  originSearch.addEventListener("input", renderPicks);
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


def _priced_destinations(fares: FaresDb, timetable, origin_crs: str) -> int:
    """How many destinations an origin's page would carry, for the index."""
    return len(fares.destinations_within(origin_crs, EVERYTHING_PENCE, adults=1))


def build_station_index(
    priced_by_origin: dict[str, int], all_locations: dict[str, object]
) -> list[dict[str, str]]:
    """The picker's option list, built from what was actually written.

    ``priced_by_origin`` maps CRS to the number of priced destinations that
    origin's page carries; ``all_locations`` supplies names. A station that
    priced nothing is **absent**, not offered and then refused (ADR-0019
    decision 3): offering one would put "0 destinations" in the picker and send
    the reader to a page that cannot answer them. The count also ranks the root
    chooser's cold start, which is derived from the feed rather than an invented
    "popular stations" list.
    """
    taken: set[str] = set()
    index = []
    for crs, count in sorted(priced_by_origin.items(), key=lambda item: (-item[1], item[0])):
        if count <= 0:
            continue
        location = all_locations[crs]
        index.append(
            {
                "crs": crs,
                "name": location.name,
                "slug": station_slug(location.name, crs, taken),
                "destinations": count,
            }
        )
    return index


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
        .replace("__BASE__", payload.get("baseHref", "/").rstrip("/"))
        .replace("__ANALYTICS__", analytics)
    )


def render_privacy(note: str, base_path: str = "") -> str:
    return PRIVACY.replace("__BASE__", base_path).replace("__NOTE__", note)


CHOOSER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where can we go for &pound;__BUDGET__? Pick your station</title>
<style>
  :root { --bg: #fff; --fg: #11161d; --line: #d0d5dd; --muted: #5b6472; --accent: #14509b;
          --field: #fff; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #14181d; --fg: #e7ebf0; --line: #3a424c; --muted: #9aa4b2; --accent: #7db4f5;
            --field: #1c2127; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 1.5rem; max-width: 40rem;
         background: var(--bg); color: var(--fg);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
  .sub { color: var(--muted); margin: 0 0 1.25rem; }
  label.caption { display: block; font-size: .8rem; text-transform: uppercase;
                  letter-spacing: .04em; color: var(--muted); margin-bottom: .35rem; }
  input[type=search] { width: 100%; padding: .6rem; border: 1px solid var(--line); border-radius: .35rem;
                       font: inherit; color: var(--fg); background: var(--field); }
  #picks { list-style: none; margin: .5rem 0 0; padding: 0; }
  #picks a { display: flex; justify-content: space-between; gap: 1rem; padding: .5rem .4rem;
             color: var(--accent); text-decoration: none; border-bottom: 1px solid var(--line); }
  #picks a:hover, #picks a:focus-visible { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  #picks .code { color: var(--muted); font-variant-numeric: tabular-nums; }
  #picks .count { color: var(--muted); font-size: .85rem; white-space: nowrap; }
  #nomatch { color: var(--muted); margin-top: .5rem; }
  p.tag { color: var(--muted); font-size: .85rem; margin-top: 2rem; }
  .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
             clip-path: inset(50%); white-space: nowrap; border: 0; }
</style>
</head>
<body>
<h1>Where can we go for &pound;__BUDGET__?</h1>
<p class="sub">Pick the station you are starting from, and see every destination reachable by train inside the budget.</p>
<label class="caption" for="pick">Your station</label>
<input id="pick" type="search" placeholder="Type part of a name or its three-letter code" autocomplete="off"
       aria-describedby="pickStatus">
<span id="pickStatus" class="sr-only" role="status"></span>
<ul id="picks"></ul>
<p id="nomatch" hidden></p>
<p class="tag">__NOTE__</p>
<script>
const STATIONS = __STATIONS__;
const picks = document.getElementById("picks");
const nomatch = document.getElementById("nomatch");
const status = document.getElementById("pickStatus");
const pick = document.getElementById("pick");

function render() {
  // A build that priced no stations has nothing to search over, so the field
  // stands down and the page says so, rather than addressing a typed input
  // the reader never made.
  if (!STATIONS.length) {
    pick.hidden = true;
    document.querySelector("label[for='pick']").hidden = true;
    picks.replaceChildren();
    nomatch.textContent = "Nothing is priced from any station in this build, so there is nothing to explore yet. " +
      "When the build prices journeys, this page lists every station it can start from.";
    nomatch.hidden = false;
    status.textContent = "0 stations listed";
    return;
  }
  const needle = pick.value.trim().toLowerCase();
  const wanted = STATIONS.filter(
    (s) => !needle || s.name.toLowerCase().includes(needle) || s.crs.toLowerCase() === needle
  );
  picks.replaceChildren();
  for (const station of wanted.slice(0, 40)) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = station.href;
    const name = document.createElement("span");
    name.textContent = station.name;
    const code = document.createElement("span");
    code.className = "code";
    code.textContent = station.crs;
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = station.destinations + (station.destinations === 1 ? " destination" : " destinations");
    link.append(name, code, count);
    item.append(link);
    picks.append(item);
  }
  // The no-match wording answers typed input; with an empty field it would
  // quote nothing back at the reader, so it stays hidden instead.
  if (wanted.length) {
    nomatch.hidden = true;
  } else if (needle) {
    nomatch.textContent = "We don't have prices from '" + pick.value.trim() +
      "'. Try the station's name or its three-letter code.";
    nomatch.hidden = false;
  } else {
    nomatch.hidden = true;
  }
  status.textContent = wanted.length + " station" + (wanted.length === 1 ? "" : "s") + " listed";
}

pick.addEventListener("input", render);
render();
pick.focus();
</script>
__ANALYTICS__
</body>
</html>
"""


def render_chooser(
    index: list[dict], *, budget_pounds: int, analytics: str = "", base_path: str = ""
) -> str:
    """The root page: the station chooser itself, with no fares on it."""
    note = DEFAULT_NOTE
    stations = json.dumps(
        [
            {"name": e["name"], "crs": e["crs"], "href": with_base(base_path, f"/from/{e['slug']}/"), "destinations": e["destinations"]}
            for e in index
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    return (
        CHOOSER_TEMPLATE.replace("__STATIONS__", stations)
        .replace("__BUDGET__", str(budget_pounds))
        .replace("__NOTE__", note)
        .replace("__BASE__", "/" + base_path.strip("/"))
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

    # Where the prices came from is read from the feed's metadata.json, not
    # retyped per build; --price-source overrides it. A synthetic build with
    # no metadata keeps the honest synthetic default.
    metadata_folders = [Path(args.feed)]
    if args.timetable:
        metadata_folders.append(Path(args.timetable))
    if args.feed_metadata:
        metadata_folders.append(Path(args.feed_metadata))
    metadata = read_feed_metadata(metadata_folders)
    price_source = args.price_source or price_source_from_metadata(metadata)
    base_path = "/" + args.base_path.strip("/") if args.base_path.strip("/") else ""
    if not price_source:
        price_source = DEFAULT_PRICE_SOURCE
    try:
        payload = build_payload(
            fares,
            timetable,
            args.origin,
            max_changes=args.max_changes,
            day=day,
            note=args.note,
            attribution=notices_or_attribution(args),
            price_source=price_source,
            base_path=base_path,
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
    # The picker's station list is the written outputs, so it is attached after
    # the payload is built and before the page is rendered. A single-origin
    # build writes only itself; --all-origins writes the whole set (ADR-0019).
    if args.all_origins:
        out_dir = out.parent
        origins = sorted(fares.locations_by_crs)
        index = build_station_index(
            {crs: _priced_destinations(fares, timetable, crs) for crs in origins},
            fares.locations_by_crs,
        )
        by_crs = {entry["crs"]: entry for entry in index}
        for crs in origins:
            if crs not in by_crs:
                continue
            one = build_payload(
                fares,
                timetable,
                crs,
                max_changes=args.max_changes,
                day=day,
                note=args.note,
                attribution=notices_or_attribution(args),
                price_source=price_source,
                base_path=base_path,
                provider=args.provider,
                mode=args.link_mode,
                adults=args.adults,
                network=args.affiliate_network,
                advertiser_id=args.advertiser_id,
                publisher_id=args.publisher_id,
                departure_limit=args.departures,
            )
            others = [e for e in index if e["crs"] != crs]
            one["stations"] = [
                {"name": e["name"], "crs": e["crs"], "href": with_base(base_path, f"/from/{e['slug']}/")} for e in others
            ]
            page = out_dir / "from" / by_crs[crs]["slug"] / "index.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(render_page(one, budget_pounds=20, analytics=analytics), encoding="utf-8")
            print(f"wrote {page} with {len(one['destinations'])} destinations from {one['origin']['name']}")
        chooser = render_chooser(index, budget_pounds=20, analytics=analytics, base_path=base_path)
        root = out_dir / "index.html"
        root.write_text(chooser, encoding="utf-8")
        print(f"wrote {root} (the chooser) with {len(index)} priced stations")
        # Pages from an earlier build are not deleted -- that is destructive
        # without asking -- but they are named, because a stale page in the
        # output folder is exactly what makes a local preview look wrong.
        written = {by_crs[crs]["slug"] for crs in by_crs}
        stale = sorted(
            child.name
            for child in (out_dir / "from").iterdir()
            if child.is_dir() and child.name not in written
        ) if (out_dir / "from").is_dir() else []
        if stale:
            print(
                f"note: {len(stale)} page folder(s) in {out_dir / 'from'} are from an earlier build and were not "
                f"rewritten: {', '.join(stale)}. Delete them yourself if you want the folder to match this build."
            )
        # The privacy page is written once per site, at the base path the
        # station links use, so it resolves wherever the site is served from.
        privacy = out_dir / "privacy" / "index.html"
        privacy.parent.mkdir(parents=True, exist_ok=True)
        privacy.write_text(render_privacy(args.note, base_path), encoding="utf-8")
        print(f"wrote {privacy}")
        # Say how to open it, because the pages are not in the repository (they
        # are build output) and their station links are root-absolute, so
        # double-clicking the file does not work while a local server does.
        print(
            f"open it through a local server, not by double-clicking: "
            f"python -m http.server --directory {out_dir} 8000, then http://localhost:8000/ "
            f"(station links start at /from/, so the file system cannot resolve them)"
        )
        return 0

    payload["stations"] = [
        {
            "name": location.name,
            "crs": crs,
            "href": with_base(base_path, f"/from/{station_slug(location.name, crs, set())}/"),
        }
        for crs, location in sorted(fares.locations_by_crs.items())
        if crs != payload["origin"]["crs"]
    ]
    if not payload["destinations"]:
        print(
            f"note: nothing is priced from {payload['origin']['name']} ({payload['origin']['crs']}) in this feed; "
            "the page says so and points at the chooser"
        )
    out.write_text(render_page(payload, budget_pounds=20, analytics=analytics), encoding="utf-8")
    print(f"wrote {out} with {len(payload['destinations'])} destinations from {payload['origin']['name']}")
    # The footer links to the privacy page, so a single-page build writes it
    # beside the page rather than shipping a link to nowhere.
    if out.parent.is_dir():
        privacy = out.parent / "privacy" / "index.html"
        privacy.parent.mkdir(parents=True, exist_ok=True)
        privacy.write_text(render_privacy(args.note, base_path), encoding="utf-8")
        print(f"wrote {privacy}")
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
