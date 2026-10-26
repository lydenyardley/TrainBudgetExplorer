"""Write a self-contained page listing every destination inside a budget.

The page runs off one embedded JSON payload and filters in the browser, so the
slider is instant and no server is needed. Point it at the synthetic feeds now,
then at the downloaded feeds, with no change to the page:

    python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN
    python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRA --out demo.html

The synthetic feed invents `GRN` for Grantham; the real code is `GRA`.

Every price on the page comes from the fare feed: a destination carries the
cheapest standard-class return for one adult, a two-adult total, and a Two
Together price when the current DTD railcard rules permit that fare.
"""
# The build is seven modules and this is its command. What follows is the one
# place they are named together, because `python build_demo_page.py` is the
# entry point every operator tool, test and workflow runs, and each of them
# reaches into this module for the pieces. A name is re-exported here rather
# than reached for at its own module so that no caller has to know which module
# the split put it in; the definitions are where the header comment on each
# `from build_*` says they are.

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from trainbudget.fares.atoc_fare_declarations import is_pseudo_station
from trainbudget.fares.atoc_fares import EVERYTHING_PENCE
from trainbudget.build.build_assets import (
    STATION_ASSET_NAME,
    chooser_script_asset_name,
    chooser_script_tag,
    prune_shared_assets,
    render_station_asset,
    replace_published,
    station_asset_rows,
    station_script_asset_name,
    station_script_tag,
    station_style_asset_name,
    station_style_tag,
    with_base,
    write_page_atomic,
)
from trainbudget.build.build_payload import (
    DEPARTURE_LIMIT,
    REVIEWED_STATION_NAMES,
    SERVICE_WEEK_HORIZON,
    _priced_destinations,
    build_payload,
    build_station_index,
    display_station_name,
    encode_payload,
    explain_unpriced,
    places_in_payload,
)
from trainbudget.build.build_pool import (
    BuildContext,
    MAX_ORIGIN_SECONDS,
    _build_all_origins,
    _build_single_origin,
    _load_timetable,
    load_inputs,
    merge_shards,
    parse_shard,
    price_one_payload,
    release_gates,
)
from trainbudget.build.build_provenance import (
    STALE_AFTER_DAYS,
    _iso_day,
    cif_date_to_iso,
    describe_restriction_note,
    feed_date_from,
    is_dtd_download,
    knowledgebase_dates,
    price_source_from_manifest,
    price_source_from_metadata,
    read_feed_metadata,
    read_provenance,
    reference_fingerprint,
    restriction_codes_shown,
)
from trainbudget.build.build_release import (
    DEFAULT_NOTE,
    DEFAULT_PRICE_SOURCE,
    DEFAULT_PRIVACY_CONTACT,
    ISSUE_TRACKER,
    MEASUREMENT_PLANS,
    NOTICES,
    RELEASE_MANIFEST_NAME,
    SYNTHETIC_LABEL,
    crawl_internal_links,
    link_crawl_failed,
    manifest_problems,
    notices_or_attribution,
    nre_attribution,
    privacy_gaps,
    release_gate_problems,
    site_features,
    wants_nre_credit,
    write_release_manifest,
)
from trainbudget.build.build_render import render_chooser, render_page, render_privacy
from trainbudget.build.build_state import (
    CACHE_DIR,
    FARE_INDEX_CACHE_VERSION,
    SOURCE_FILES,
    TIMETABLE_INDEX_ROOT,
    fares_index_cache_paths,
    load_page_fares,
    module_sources,
    page_facts_path,
    page_is_current,
    prune_fare_index_caches,
    prune_timetable_caches,
    read_page_facts,
    read_priced_facts,
    read_service_week,
    source_fingerprint,
    timetable_cache_path,
    timetable_facts_identity,
    timetable_index_location,
    write_priced_facts,
    write_service_week,
)
from trainbudget.build.page_templates import CHOOSER_SCRIPT, STATION_SCRIPT
from trainbudget.fares.retailer import AFFILIATE_NETWORKS, DEFAULT_PROVIDER


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the budget explorer demo page.")
    parser.add_argument("--feed", required=True, help="fares feed folder or zip")
    parser.add_argument("--timetable", default=None, help="CIF timetable feed folder or zip")
    parser.add_argument(
        "--timetable-index",
        type=Path,
        default=None,
        help=(
            "directory of per-origin timetable slices to build from, written by "
            "python -m tools.build_timetable_index; when it holds a slice for "
            "every page, no timetable feed is read at all"
        ),
    )
    parser.add_argument(
        "--knowledgebase",
        default=None,
        help=(
            "Knowledgebase reference feed folder, holding the ticket-restrictions "
            "XML. Read as a second opinion on the fares feed's own restriction "
            "wording, never as its replacement; omit it and the page says the "
            "reference feed was not checked"
        ),
    )
    parser.add_argument(
        "--with-single-timetable",
        action="store_true",
        help="also load/cache journey times for the larger outbound-single destination set",
    )
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
    parser.add_argument(
        "--only-stations",
        default=None,
        help=(
            "with --all-origins: build only these origin codes, comma-separated "
            "(GRA,NOT). Still one site -- one chooser, one station list, one "
            "release manifest -- so a subset costs build time and nothing else"
        ),
    )
    parser.add_argument(
        "--fast-all-origins",
        action="store_true",
        help="build every station page in prices-only parallel mode, report live "
        "progress, and resume pages already completed from the same feeds/config",
    )
    parser.add_argument(
        "--shard",
        default=None,
        metavar="N/M",
        help="build a disjoint share of the origin list as N of M (1-based): "
        "this process writes every M-th origin starting at the N-th. Each "
        "shard writes its own folder; --merge combines them into one site, "
        "after proving they partition the feed's origins.",
    )
    parser.add_argument(
        "--merge",
        nargs="+",
        default=None,
        metavar="SHARD_DIR",
        help="combine shard folders written by --shard into one site at --out. "
        "Needs --feed, for the origin list the shards must partition.",
    )
    parser.add_argument("--max-changes", type=int, default=1)
    parser.add_argument(
        "--max-places",
        type=int,
        default=None,
        metavar="N",
        help="list only the N cheapest places a page prices, cutting every fare "
        "list to the same places. The page counts the rest and says where it "
        "stops. Off by default: the release sets it to fit the site's byte "
        "budget (docs/build-performance-findings.md, 'A cap on the places a "
        "page lists')",
    )
    parser.add_argument(
        "--fail-on-unsourced",
        action="store_true",
        help="refuse to write pages when a priced destination has no settlement "
        "class from any source. Off by default, because a full-network build "
        "meets stations no filter can name; the warning is printed either way",
    )
    parser.add_argument(
        "--require-classification",
        action="store_true",
        help="refuse to write pages when a sourced classification source (the "
        "ONS types workbook or a sourced facet) could not be read, rather than "
        "publishing with the reviewed fallbacks only. The skips are printed "
        "either way",
    )
    parser.add_argument(
        "--require-live-reviewed-codes",
        action="store_true",
        help="refuse to write pages when a reviewed settlement-fallback code "
        "names no station in this feed, or names one the ONS workbook already "
        "classifies. Both are silent at runtime -- a stale code is intersected "
        "away before it is applied, and a redundant one never applies at all -- "
        "so without this flag a reviewed list can go stale unnoticed",
    )
    parser.add_argument("--date", default=None, help="service date as YYYY-MM-DD")
    parser.add_argument(
        "--note",
        default=None,
        help="footer note. Defaults to the synthetic-demo note only when the "
        "provenance is synthetic; a real feed gets no footer note unless one "
        "is written here",
    )
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
        "full-network build (workers share one parsed feed through persisted "
        "per-origin fare indexes rather than re-parsing it each)",
    )
    parser.add_argument(
        "--max-origin-seconds",
        type=float,
        default=MAX_ORIGIN_SECONDS,
        help="tripwire (ADR-0024): if building ONE origin's page takes longer "
        "than this, the build names it and stops. A superquadratic search makes "
        "a full-network run silently unfinishable; this makes that visible on "
        "the first origin instead of after hours. 0 disables the check",
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
        help="comma-separated preset notices: nre (National Rail Enquiries as "
        "the source, required by the National Rail Data Portal terms), rdg (Rail "
        "Data Marketplace publisher credit), ogl (Open Government Licence "
        "wording), accuracy (as-is accuracy and liability notice). Compose them, "
        "e.g. --notices nre,rdg,ogl,accuracy",
    )
    parser.add_argument(
        "--privacy-contact",
        default=None,
        help="who to contact about this site, on the privacy page (overrides PRIVACY_CONTACT)",
    )
    parser.add_argument(
        "--measurement-plan",
        choices=sorted(MEASUREMENT_PLANS),
        default=None,
        help=(
            "the reviewed measurement plan an analytics snippet is allowed under "
            "(ADR-0032); a snippet without one is refused"
        ),
    )
    parser.add_argument(
        "--analytics-snippet",
        default=None,
        help="file whose contents are injected before </body>, for counting referrers",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run one build: the phases both shapes share, then the shape itself.

    A build is a sequence of phases, and each refuses before the next runs
    (four-dimension audit R9). Nothing here writes a page: the phases resolve
    the feeds and the provenance, one payload is priced so the tripwire fires on
    the first origin, and the release gates decide what may be published. The
    two shapes below write the pages, and both of them end by handing their
    routes to the same ``write_release``.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    if args.merge and (args.all_origins or args.fast_all_origins or args.shard or args.only_stations):
        print(
            "error: --merge combines shard folders; it takes no build shape flags.",
            file=sys.stderr,
        )
        return 2
    if args.merge:
        return merge_shards(args)
    if args.fast_all_origins:
        args.all_origins = True
        if args.timetable:
            print("--fast-all-origins is prices-only; ignoring --timetable", file=sys.stderr)
        args.timetable = None
        args.with_single_timetable = False
        if args.workers == 1:
            args.workers = min(8, os.cpu_count() or 1)
    if args.only_stations and not args.all_origins:
        print(
            "error: --only-stations names a subset of a whole-network build, so it "
            "needs --all-origins. Without it this build writes only --origin.",
            file=sys.stderr,
        )
        return 2
    if args.shard and not args.all_origins:
        print(
            "error: --shard names a share of a whole-network build, so it "
            "needs --all-origins.",
            file=sys.stderr,
        )
        return 2
    if args.shard:
        try:
            parse_shard(args.shard)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
    if args.max_places is not None and args.max_places < 1:
        print(
            f"error: --max-places {args.max_places} lists no places at all; "
            "leave the flag off to list every place the feed prices.",
            file=sys.stderr,
        )
        return 2
    day: date | None = None
    if args.date:
        try:
            day = date.fromisoformat(args.date)
        except ValueError:
            print(f"date {args.date!r} is not YYYY-MM-DD", file=sys.stderr)
            return 2
    ctx = BuildContext(args=args, day=day)
    for phase in (load_inputs, _load_timetable, read_provenance, price_one_payload, release_gates):
        code = phase(ctx)
        if code:
            return code
    return _build_all_origins(ctx) if args.all_origins else _build_single_origin(ctx)




if __name__ == "__main__":
    # Windows starts pool workers by re-importing this module, so the entry
    # point must sit under the guard (it does) and the guard must come before
    # main() runs, or each worker re-runs the build recursively.
    raise SystemExit(main())
