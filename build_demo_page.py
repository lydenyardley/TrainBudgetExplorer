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
from page_templates import CHOOSER_TEMPLATE, PRIVACY, TEMPLATE
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


def read_feed_metadata(folders: list[Path]) -> dict | None:
    """The first readable metadata.json found in the feed folders.

    A zip feed has no folder of its own, but its download usually lands inside
    one, so the caller passes the zip's parent. None means no metadata file
    was found (a synthetic feed's case); {} means a file was found but could
    not be used, which the caller must not read as ``no metadata`` -- a real
    download whose provenance note is broken still deserves the loud refusal
    in main(), not a quiet fallback to the synthetic default. A file that
    exists but cannot be used is named, because provenance that silently fell
    back to the default is provenance the operator believes is real.
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
    return None


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


def _slug_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "station"


def station_slug(name: str, crs: str, taken: set[str]) -> str:
    """A readable address for one station, unique within ``taken``.

    Single-station primitive. The build uses station_slugs_for instead, which
    is the rule the written folders and every picker obey.
    """
    slug = _slug_text(name)
    if slug in taken:
        slug = _slug_text(f"{name} {crs}")
    if slug in taken:  # pathological: same name AND code seen twice
        counter = 2
        while f"{slug}-{counter}" in taken:
            counter += 1
        slug = f"{slug}-{counter}"
    taken.add(slug)
    return slug


def station_slugs_for(locations: dict[str, object]) -> dict[str, str]:
    """The one map of station addresses every build mode shares.

    Any station whose name another station also holds carries its CRS in the
    address, so the map is computable from the locations alone and does not
    depend on which station was seen first or which priced more destinations
    (audit finding A1: a first-seen-wins rule gave the single-origin and
    --all-origins builds different answers for the same two stations, and one
    of them 404'd). Deterministic beats pretty: both NOTTINGHAMs are named
    plainly in the picker next to their codes anyway.
    """
    names_by_base: dict[str, int] = {}
    base: dict[str, str] = {}
    for crs, location in sorted(locations.items()):
        key = _slug_text(location.name)
        base[crs] = key
        names_by_base[key] = names_by_base.get(key, 0) + 1
    taken: set[str] = set()
    slugs: dict[str, str] = {}
    for crs, location in sorted(locations.items()):
        key = base[crs]
        slug = key if names_by_base[key] == 1 else (_slug_text(f"{location.name} {location.crs}") or key)
        while slug in taken:  # same name AND code twice: numbered fallback
            slug = f"{slug}-2"
        taken.add(slug)
        slugs[crs] = slug
    return slugs


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
        "--workers",
        type=int,
        default=1,
        help="processes to build station pages with. Each origin's page is "
        "independent, so N workers cut the wall time roughly N-fold on a "
        "full-network build (the feed is re-loaded once per worker)",
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
    # The picker's options (ADR-0019), from the one shared slug map, so a page
    # built on its own links to the same folders the --all-origins build writes.
    slugs = station_slugs_for(fares.locations_by_crs)
    return {
        "origin": {"crs": origin_row.crs, "name": origin_row.name},
        "destinations": destinations,
        "stations": [
            {
                "name": loc.name,
                "crs": loc.crs,
                "href": with_base(base_path, f"/from/{slugs[crs]}/"),
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
    slugs = station_slugs_for(all_locations)
    for crs, count in sorted(priced_by_origin.items(), key=lambda item: (-item[1], item[0])):
        if count <= 0:
            continue
        location = all_locations[crs]
        index.append(
            {
                "crs": crs,
                "name": location.name,
                "slug": slugs[crs],
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
    price_source = args.price_source or price_source_from_metadata(metadata or {})
    base_path = "/" + args.base_path.strip("/") if args.base_path.strip("/") else ""
    if not price_source:
        if metadata is not None:
            # A metadata file that exists but names no source is a real feed
            # whose provenance note is unfinished. Falling back here would
            # ship real prices labelled "the synthetic demo feed" -- the one
            # lie this machinery exists to prevent -- so the build refuses and
            # the operator fixes the note or overrides it explicitly.
            print(
                f"error: a feed metadata.json was found beside "
                f"{metadata_folders[0]} but names no 'source' (and no --price-source "
                "was given); the page would claim synthetic demo data for a real "
                "feed. Fill in 'source' in the metadata, or pass --price-source.",
                file=sys.stderr,
            )
            return 2
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
        # One shared job description per page: in-process builds run it inline
        # with the live databases; --workers hands config-only jobs to a pool
        # whose workers load the feed themselves.
        shared = {
            "max_changes": args.max_changes,
            "day": day,
            "note": args.note,
            "attribution": notices_or_attribution(args),
            "price_source": price_source,
            "base_path": base_path,
            "provider": args.provider,
            "link_mode": args.link_mode,
            "adults": args.adults,
            "network": args.affiliate_network,
            "advertiser_id": args.advertiser_id,
            "publisher_id": args.publisher_id,
            "departures": args.departures,
            "analytics": analytics,
        }
        jobs = []
        for crs in origins:
            if crs not in by_crs:
                continue
            jobs.append(
                {
                    **shared,
                    "crs": crs,
                    "slug": by_crs[crs]["slug"],
                    "origin_name": by_crs[crs]["name"],
                    "others": [e for e in index if e["crs"] != crs],
                }
            )
        workers = max(1, args.workers)
        if workers == 1:
            # The in-process path builds through the same job function the
            # pool uses, with the live databases placed in the job dict, so
            # both modes share one page-building code path.
            from build_workers import build_page_job

            for job in jobs:
                job["fares"] = fares
                job["timetable"] = timetable
            results = map(build_page_job, jobs)
        else:
            # ProcessPoolExecutor rather than multiprocessing.Pool: a worker
            # that dies before answering turns into a BrokenProcessPool error
            # here, instead of an imap that waits forever on a dead queue.
            # The workers module is imported here, not at the top: it imports
            # this module's payload and render functions, and a top-level
            # import would be a cycle. Under Windows spawn the child re-imports
            # build_workers, which then imports this module straight through.
            from build_workers import build_page_job, init_worker
            from concurrent.futures import ProcessPoolExecutor

            with ProcessPoolExecutor(
                workers,
                initializer=init_worker,
                initargs=(args.feed, args.timetable),
            ) as executor:
                results = executor.map(build_page_job, jobs, chunksize=1)
        for slug, origin_name, html in results:
            page = out_dir / "from" / slug / "index.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(html, encoding="utf-8")
            print(f"wrote {page} from {origin_name}")
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
    # Windows starts pool workers by re-importing this module, so the entry
    # point must sit under the guard (it does) and the guard must come before
    # main() runs, or each worker re-runs the build recursively.
    raise SystemExit(main())
