"""The notices, the credit and the gate that decides whether a site may be published.

A page that carries somebody else's data carries their credit and this project's
notices, and a public build refuses rather than guessing when one is missing. The
same module holds the release manifest, the link crawl and the privacy route,
because those are the release's own promises about itself.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from trainbudget import ROOT
from trainbudget.build.build_assets import internal_hrefs, page_path_for_route, write_page_atomic


DEFAULT_NOTE = (
    "Synthetic demo data: the stations, fares, and times are invented to exercise "
    "the pipeline. Real fares and times replace them once the feed download clears."
)


# The budget every page of a release opens at, in pounds. It was a literal in
# five places -- four in build_pool.py and one in build_workers.py -- and absent
# from the shard manifest, so a merged release opened at £20 by construction and
# the merge could not have learned any other figure (E7 of the 17 October 2026
# audit). One constant, read by the in-process build, the pool and the merge,
# and carried in the shard manifest's `release` beside the note and the price
# source so a merge opens where its shards did.
OPENING_BUDGET_POUNDS = 20


# The provenance line sits with the prices, not the footer, because where a
# number came from is part of the number. A real feed overrides it from its own
# metadata.json (read_feed_metadata), so the default only ever reaches a page
# built from the synthetic feed.
DEFAULT_PRICE_SOURCE = "the synthetic demo feed"


# S45: what a synthetic page states, above the content rather than in the
# footer paragraph that a screenshot crops. One sentence, on every route, and
# written here so the chooser, a station page and the privacy page cannot say
# three different things about the same invented data.
SYNTHETIC_LABEL = "Synthetic demo data."


SYNTHETIC_BANNER = (
    "The stations, fares and times here are invented to exercise the pipeline, "
    "not real journeys."
)


# Railcard prices are emitted unless a current DTD RR total ban matches the
# fare's ticket, route, or endpoint locations. RR restriction codes are retained
# as travel conditions rather than mistaken for bans.
# Licence notice wordings (ADR-0020, ADR-0021). The OGL sentence is the
# standard wording; the accuracy notice carries the substance of the Data
# Sharing Agreement's cl. 3.3.2 and its liability clause 7.2. Composed by
# --notices for a real-data build, never applied to a synthetic one by
# default: crediting RDG for invented prices would be false attribution.
NOTICES = {
    # The NRDP terms grant copying, publishing, distributing and transmitting
    # the Information and its commercial exploitation, on three requirements.
    # One of them is to "acknowledge NRE as the source of Information in
    # accordance with this agreement and the Developer Guidelines", and the
    # guidelines are not published at the URL the terms name, so this is the
    # acknowledgement in the terms' own words: a plain statement that NRE is
    # the source. It names no product, because a fares-only release would then
    # be credited with a timetable it does not carry -- the same overstatement
    # the rest of this table is written to avoid. What the guidelines would
    # add -- an exact wording, and any brand treatment -- is not invented here;
    # it is an open item in docs/publish-checklist.md and in the clearance
    # record.
    "nre": (
        "Provided by National Rail Enquiries (NRE), under the National Rail "
        "Data Portal terms."
    ),
    # The Rail Delivery Group credit is the Data Sharing Agreement's, for what
    # the Rail Data Marketplace publishes: the Knowledgebase reference feeds
    # and the fare-locations reference data. It is not the credit for the
    # fares and the timetable, which are NRE's and carry the notice above, and
    # a page that credited RDG for prices it received from NRE would be
    # crediting the wrong licensor.
    "rdg": (
        "Knowledgebase reference data: \u00a9 Rail Delivery Group, published through "
        "the Rail Data Marketplace."
    ),
    # The second and third sentences are the statements ONS and National
    # Records of Scotland ask for wherever their boundaries are used: the
    # settlement classes are placed by the ONS built-up-area and region
    # boundaries and the NRS settlement boundaries, all of which contain OS
    # data (ADR-0080, ADR-0081).
    "ogl": (
        "Contains public sector information licensed under the Open Government "
        "Licence v3.0. Settlement sizes: Office for National Statistics; contains "
        "OS data \u00a9 Crown copyright and database right 2022. Scottish "
        "settlements: Copyright National Records of Scotland; contains Ordnance "
        "Survey data \u00a9 Crown copyright and database right 2022."
    ),
    "accuracy": (
        "The fares and journey times on this page are provided \u2018as is\u2019, with no "
        "representation as to their accuracy or fitness for a purpose, and they "
        "change without notice: always confirm the price with the seller before "
        "buying. Neither National Rail Enquiries, Rail Delivery Group nor Rail "
        "Settlement Plan Limited accepts liability for any loss arising from "
        "reliance on this data."
    ),
}


# What the times on the page are, said near them rather than assumed, because
# a journey time read as a promise is a complaint waiting to happen.
PRICING_NOTE = (
    "Times are options in the timetable, not a booking: the fare shown is valid "
    "on every service listed, so none is picked for you."
)


# C5: the paragraph above the method disclosure makes the same point at more
# length, and a build that loaded no timetable has no services for a fare to be
# valid on. It shipped the timetable sentence on every page, so a prices-only
# build told its reader about services that are not there -- on a page whose
# first principle is that an approximation never passes for a quote (C5 of the
# 17 October 2026 critique). The words live here, beside the note they restate,
# and the payload carries whichever sentence its own shape supports.
SERVICE_CLAIM = (
    "The times on this page are options in the timetable, not a booking. "
    "Unrestricted fares are valid on the services listed. An Advance single, "
    "shown when it is the cheapest single, is valid only on a qualifying train, "
    "and its price and availability can change — so no train is picked for you."
)
SERVICE_CLAIM_WITHOUT_TIMES = (
    "An Advance single, shown when it is the cheapest single, is valid only on a "
    "qualifying train, and its price and availability can change — so no train "
    "is picked for you. This build prices fares only, so no times are listed."
)


def service_claim(has_journeys: bool) -> str:
    """The paragraph about times that this build's payload can support."""
    return SERVICE_CLAIM if has_journeys else SERVICE_CLAIM_WITHOUT_TIMES


# S38: the measurement plans this project would accept, written out rather than
# left implied. Each is a plan a reader can be told about in one sentence, and
# each is a decision rather than a default: switching analytics on without
# naming one of these is refused, so a familiar flag cannot quietly turn
# measurement on. None is in use -- no snippet is configured -- and the gate is
# here so that turning one on is a recorded act.
# One route for every build, synthetic or real. An email on the page is a
# published address; the issue tracker is a route that does not print one
# (ADR-0068). `--privacy-contact` and PRIVACY_CONTACT still override it.
ISSUE_TRACKER = "https://github.com/lydenyardley/TrainBudgetExplorer/issues"


DEFAULT_PRIVACY_CONTACT = (
    "To report a problem with this site, open an issue in the deployment "
    f'operator\'s public repository: <a href="{ISSUE_TRACKER}">{ISSUE_TRACKER}</a>.'
)


MEASUREMENT_PLANS = {
    "aggregate-referrer-counts": (
        "counts referrers in aggregate, keeps no persistent identifier, sets no "
        "cookie, and retains nothing beyond a short rolling window"
    ),
}


def crawl_internal_links(out_dir: Path, base_path: str = "") -> list[str]:
    """Every internal link in the built site, resolved against written files.

    A generated site is a set of HTML files under ``out_dir``, plus the shared
    picker asset; a link is healthy when the file it names exists. The asset is
    read as well as the pages, because the picker's options moved out of the
    pages and a crawl that stopped reading where they went would keep passing a
    site whose only route contract was broken. The chooser at the root, each
    station page and the privacy page are all crawled, so a link from any page
    to a page that was not written is caught here rather than by a reader.
    External and seller links are left alone: they are not this site's files.

    Returns a list of human-readable broken-link descriptions, empty when the
    site is internally consistent.
    """
    # One walk for both answers. Every file this release publishes, not only
    # its pages: a shared document is as much a route as a page is, and a
    # request for one that was not written is a broken link like any other.
    # This was two walks of the same tree until 18 October 2026, which on a
    # release is 2,712 directories read twice for one list of files.
    files = sorted(path for path in out_dir.rglob("*") if path.is_file())
    written = {path.relative_to(out_dir).as_posix() for path in files}
    broken: list[str] = []
    for page in files:
        if page.suffix.lower() not in (".html", ".js", ".css"):
            continue
        source = page.relative_to(out_dir).as_posix()
        for href in internal_hrefs(page.read_text(encoding="utf-8")):
            # Strip the site base so the manifest is in terms of files on disk.
            route = href[len(base_path):].lstrip("/") if base_path and href.startswith(base_path) else href.lstrip("/")
            if not route:
                target = "index.html"  # the site root
            elif route.endswith("/"):
                target = route + "index.html"
            else:
                target = route
            if target not in written:
                broken.append(f"{source} links to {href}, which was not written")
    return broken


def link_crawl_failed(broken: list[str], out_dir: Path) -> None:
    """Refuse to leave a site whose own links do not resolve (S03).

    Called after the manifest is complete and before the staged folder is
    published, so a build that would ship a dangling internal link never
    becomes the published site.
    """
    if not broken:
        return
    listing = "\n".join(f"  - {entry}" for entry in broken)
    raise SystemExit(
        f"error: the built site has {len(broken)} internal link(s) that do not "
        f"resolve to a written page, so publishing it would ship broken links:\n"
        f"{listing}\n"
        f"Every internal link must come from the route manifest of pages this "
        f"build actually wrote under {out_dir}."
    )


# The routes one release serves, as a list beside the pages (S07). The host
# consumes the folder this build wrote; this says which routes in it are part
# of this release, so "the whole verified output" is a set somebody can read
# rather than a promise about a folder.
RELEASE_MANIFEST_NAME = "release-manifest.json"


def write_release_manifest(
    out_dir: Path,
    routes: list[str],
    *,
    price_source: str,
    built_at: str,
    base_path: str = "",
) -> Path:
    """Write the release manifest, and return where it went."""
    manifest = {
        "schema": 1,
        "builtAt": built_at,
        "basePath": base_path,
        "priceSource": price_source,
        "synthetic": price_source == DEFAULT_PRICE_SOURCE,
        "routes": sorted(set(routes)),
    }
    path = out_dir / RELEASE_MANIFEST_NAME
    write_page_atomic(path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return path


def manifest_problems(out_dir: Path, manifest: dict, base_path: str = "") -> list[str]:
    """Every route the manifest claims, proved to be a written file.

    The link crawl walks the other way: it asks whether every link a reader can
    follow resolves. This asks whether every route the release says it serves
    exists, which is the direction a host or a person reading the manifest needs
    -- a release that claims a station it did not write is a release whose
    completeness cannot be taken on trust.
    """
    problems: list[str] = []
    for route in manifest.get("routes") or []:
        if not isinstance(route, str) or not route.startswith("/"):
            problems.append(f"the manifest names {route!r}, which is not a route on this site")
            continue
        if not page_path_for_route(out_dir, route, base_path).is_file():
            problems.append(f"the manifest names {route}, which was not written")
    return problems


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


NRE_LOGO = ROOT / "assets" / "powered-by-national-rail.svg"


NRE_WEBSITE = "https://www.nationalrail.co.uk/developers/"


# The enquiries site itself, as distinct from the developer page the logo
# links to. The brand guidelines ask for a link to the NRE website.
NRE_ENQUIRIES = "https://www.nationalrail.co.uk/"


def wants_nre_credit(attribution: str | list[str] | None) -> bool:
    """Whether this build asked for the NRE acknowledgement, and so the mark.

    Keyed on the composed notice rather than on the flag, so both ways into a
    page -- the in-process build and the worker pool -- ask the same question of
    the same value and cannot come out differently. A build given verbatim
    ``--attribution`` text is not second-guessed: the operator chose that
    wording, and the licence question behind it is theirs to answer, not this
    function's to decide.
    """

    notices = [attribution] if isinstance(attribution, str) else list(attribution or [])
    return NOTICES["nre"] in notices


def nre_attribution() -> str:
    """The NRE source credit the portal terms require, logo and all.

    The Developer Brand Guidelines (September 2026) make this specific: the
    licensee "must acknowledge NRE as the source of information, where
    possible, by providing a link to the NRE website for more information and
    by displaying the 'Powered by National Rail Enquiries' logo", and where the
    feed is "the predominant or standalone information" the attribution is to be
    "shown directly alongside, above or underneath the Information derived from
    the feed". The footer's credit block is underneath the table, and the whole
    page is the information, so this is the placement the guidelines name.

    The logo is inlined rather than linked, because the page is one
    self-contained file (ADR-0033) and an attribution that needs a second
    request to appear is an attribution a reader on a train may never see. The
    mark is the file NRE supplies, byte for byte; the strip below removes only
    the XML prolog and the generator comment, which cannot appear inside HTML.

    A missing or unreadable mark is a build failure, not a page without a
    credit: this is the one thing in the footer the licence requires by name.
    """

    try:
        svg = NRE_LOGO.read_text(encoding="iso-8859-1").strip()
    except OSError as error:
        raise SystemExit(
            f"the NRE 'Powered by National Rail Enquiries' mark is required by the "
            f"Developer Brand Guidelines and is missing at {NRE_LOGO}: {error}"
        ) from error
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg, count=1).strip()
    svg = re.sub(r"<!--.*?-->", "", svg, count=1, flags=re.S).strip()
    # The mark is hidden from the accessibility tree because the span around it
    # is the image and carries the name: a bare <svg> is exposed as an image of
    # its own, and an image with no name is a control a screen reader announces
    # as nothing.
    svg = re.sub(r"<svg\b", '<svg aria-hidden="true" focusable="false"', svg, count=1)
    return (
        '<div class="nre-credit">'
        f'<a href="{NRE_WEBSITE}" rel="external noreferrer">'
        # The mark is paths, so nothing in it is readable: the name a screen
        # reader gets is the words the guidelines require it to carry.
        '<span class="nre-logo" role="img" aria-label="Powered by National Rail '
        f'Enquiries">{svg}</span></a></div>'
    )


def nre_source_line() -> str:
    """The footer credit: the notice this repo already uses, plus the link.

    The sentence is ``NOTICES["nre"]``, which is the acknowledgement in the
    portal terms' own words. The link is the enquiries site. The last sentence
    is the terms' own bar on implying that NRE endorses the product, stated
    rather than left for a reader to infer from a logo.

    This is where the acknowledgement is printed, and the only place it is: it
    is static markup, so it is present in a page whose script never runs, and it
    sits beside the mark the brand guidelines require. ``attribution_paragraphs``
    therefore leaves the same sentence out of the page's own notice block, which
    used to print it a second time four lines later (audit item 2, 28 October
    2026).
    """

    return (
        '<p class="nre-source">Information from '
        f'<a href="{NRE_ENQUIRIES}" rel="external noreferrer">National Rail Enquiries</a>. '
        f"{html.escape(NOTICES['nre'])} "
        "National Rail Enquiries does not endorse this site.</p>"
    )


def attribution_paragraphs(attribution: str | list[str] | None) -> str | list[str] | None:
    """The licence wording the page's own attribution block carries.

    The NRE acknowledgement is not one of them. It has a static home in the
    credit line beside the mark, which is where the brand guidelines place it and
    where ``tools/check_source_credit.py`` reads it; carrying it here as well
    printed the same legal sentence twice in the one part of the page making a
    claim on somebody else's behalf (audit item 2, 28 October 2026). One
    sentence, one owner.

    The filter is exact rather than fuzzy, and it is the same rule
    ``wants_nre_credit`` applies: a build asked for the acknowledgement gets the
    credit line, so the block must not repeat it. Wording of the operator's own
    that is not that sentence is passed through untouched -- it asked for no
    credit line, so nothing else is printing it.

    The shape it was given is the shape it returns, because the field is read
    either as one paragraph of the operator's own or as the list of composed
    notices. ``None`` rather than an empty list when nothing is left, because the
    page tests the field's truth before it unhides the block, and an empty array
    is truthy in JavaScript.
    """

    if isinstance(attribution, str):
        return None if attribution == NOTICES["nre"] else attribution
    remaining = [paragraph for paragraph in (attribution or []) if paragraph != NOTICES["nre"]]
    return remaining or None


def site_features(
    *,
    analytics: bool,
    link_mode: str,
    network: str | None,
    disclosure: str | None,
    measurement: str | None = None,
) -> dict:
    """What this build actually ships, as the facts the notice must state.

    Read from the same values the pages are built from rather than from a
    checklist somebody maintains beside them, so the notice cannot describe a
    site this build did not produce (S36). Every key here is a switch a reader
    would want disclosed.
    """
    return {
        "analytics": analytics,
        "linkMode": link_mode,
        "affiliate": network or None,
        # A tracked link is a redirect that tells the network which page sent
        # the reader. retailer.ticket_link attaches the disclosure itself when
        # a network and an advertiser id are both configured, so this is read
        # the same way: a network that is on is a link that is wrapped.
        "trackedLinks": bool(network),
        "disclosure": disclosure or "",
        # The plan, not a boolean: a reader is told what is measured and for
        # how long, and that sentence has to come from somewhere (S38).
        "measurement": measurement or "",
    }


def privacy_gaps(features: dict, contact: str) -> list[str]:
    """What the notice would have to say and does not, one line per gap.

    Fail closed (S36, S37): a public build that ships a behaviour nobody can
    be told about is refused rather than published with a notice that has
    quietly stopped matching it.
    """
    gaps: list[str] = []
    if not contact.strip():
        gaps.append(
            "no privacy contact is configured, so nobody can be told about a "
            "problem with this site (set PRIVACY_CONTACT or pass --privacy-contact)"
        )
    if features.get("analytics") and not features.get("measurement"):
        gaps.append(
            "an analytics snippet is injected but no measurement plan is "
            "recorded, so nobody can be told what it measures; pass "
            "--measurement-plan to name a reviewed plan (ADR-0032)"
        )
    if features.get("trackedLinks") and not features.get("disclosure"):
        gaps.append(
            "ticket links are wrapped by an affiliate network but no disclosure "
            "is set, so the pages would not say a click can earn a commission"
        )
    return gaps


def release_gate_problems(
    features: dict,
    *,
    public: bool,
    notices: str | list[str] | None,
    contact: str,
) -> list[str]:
    """The conditions a public release has to meet before it can be published.

    S37: these were prose in a checklist, so a familiar flag could turn on a
    feature whose licence, disclosure or contact condition had not been met.
    They are refusals now, and a synthetic demo build -- which publishes no real
    fares and carries no licence obligation -- is exempt by construction rather
    than by a flag somebody can forget to pass.
    """
    problems = privacy_gaps(features, contact)
    if not public:
        return problems
    if not notices:
        problems.append(
            "a public build carries no licence or attribution notice; pass "
            "--notices (or --attribution) so the obligations travel with the site"
        )
    return problems
