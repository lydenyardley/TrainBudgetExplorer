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

from __future__ import annotations

import argparse
import hashlib
import html
import json
import functools
import gc
import os
import pickle
import re
import shutil
import sys
import time
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

from atoc_fares import (
    DESTINATION_TYPE_FILTERS,
    FaresDb,
    Location,
    PLACEHOLDER_TICKET_CODES,
    RailcardFamily,
    Reachable,
    TwoPartFare,
    format_pence,
    is_pseudo_station,
    location_lookup_candidates,
)
from atoc_timetable import SLICE_INDEX_SCHEMA, SliceIndex, TimetableDb
from atoc_knowledgebase import (
    ABSENT,
    UNKNOWN,
    UNPUBLISHED,
    Knowledgebase,
    RestrictionCheck,
    check_restrictions,
    load_ticket_restrictions,
)
from destination_coverage import UnsourcedReport, unnameable_from_tally
from page_templates import (
     CHEVRON,
     CHOOSER_SCRIPT,
     CHOOSER_TEMPLATE,
     PRIVACY,
     STATION_SCRIPT,
     STATION_STYLESHEET,
     TEMPLATE,
 )
from retailer import (
    AFFILIATE_NETWORKS,
    DEFAULT_PROVIDER,
    DISCLOSURE,
    TicketLink,
    pairing_warning,
    ticket_link,
)

EVERYTHING_PENCE = 1_000_000
DEPARTURE_LIMIT = 5
# The per-origin tripwire (ADR-0024): one origin should take tens of seconds
# on a real network, not minutes. Exceeding this means the journey search's
# cost is out of hand, and a full-network build would take days -- the build
# stops on the FIRST origin instead of hours later. The measured full-network
# number is ~9 minutes today, which is why this sits far above it: the default
# is a never-fire alarm on today's code, not a target.
MAX_ORIGIN_SECONDS = 1800.0
DEFAULT_NOTE = (
    "Synthetic demo data: the stations, fares, and times are invented to exercise "
    "the pipeline. Real fares and times replace them once the feed download clears."
)
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
    "ogl": (
        "Contains public sector information licensed under the Open Government "
        "Licence v3.0."
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

# -- feed metadata ----------------------------------------------------------
# Where the feed came from is recorded once, in metadata.json beside it, and
# every build reads it, so provenance is never retyped by hand and never
# drifts between builds. --price-source still overrides it.
METADATA_NAME = "metadata.json"

# How old a fares download may be before the page says so beside the prices.
# A fortnight is the point at which a reader planning a specific day should be
# told to check the fare again, rather than the point at which the number is
# wrong: fares change, they do not expire.
STALE_AFTER_DAYS = 14

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
    "the deployment operator via its public repository issue tracker ("
    + ISSUE_TRACKER
    + ")"
)

MEASUREMENT_PLANS = {
    "aggregate-referrer-counts": (
        "counts referrers in aggregate, keeps no persistent identifier, sets no "
        "cookie, and retains nothing beyond a short rolling window"
    ),
}
# The downloader records its own non-secret provenance (URL, size, hash, and
# timestamp) in a manifest beside the feeds it writes. A feed downloaded
# without a hand-written metadata.json still has that, so a real download can
# never fall back to the synthetic default just because nobody typed a note.
MANIFEST_NAME = "download-manifest.json"
BUILD_STATE_NAME = ".trainbudget-build.json"
CACHE_DIR = Path(__file__).parent / "_cache"
SOURCE_FILES = (
    "atoc_fares.py",
    "atoc_restrictions.py",
    "atoc_timetable.py",
    "build_demo_page.py",
    "build_workers.py",
    "feeds_cli.py",
    "page_templates.py",
    "parse_report.py",
    "retailer.py",
    "reference-data/destination-facets.json",
)


@functools.lru_cache(maxsize=1)
def source_fingerprint() -> str:
    """Hash the source files that can change a generated page.

    Cached because it is asked once per page by a 2,500-page build, and the
    sources cannot change while one process is running.
    """
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for name in SOURCE_FILES:
        digest.update(name.encode("utf-8"))
        digest.update((root / name).read_bytes())
    return digest.hexdigest()[:16]


def feed_fingerprint(path: str | Path) -> str:
    """A cheap identity for resumable output: file names, sizes, and mtimes."""
    root = Path(path)
    files = [root] if root.is_file() else sorted(item for item in root.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    for item in files:
        try:
            stat = item.stat()
            identity = f"{item}:{stat.st_size}:{stat.st_mtime_ns}"
        except OSError:
            identity = f"{item}:missing"
        digest.update(identity.encode("utf-8", "replace") + b"\n")
    return digest.hexdigest()


def feed_content_digest(path: str | Path) -> str:
    """An identity for a feed that cannot outlive the bytes it names.

    ``feed_fingerprint`` reads names, sizes and mtimes, which separates two
    downloads on any ordinary day and costs nothing. It cannot separate two
    downloads when the replacement holds different bytes of the same length
    under the same timestamp: a copy that preserves mtimes, an archive
    extracted with the dates stored in it, a feed directory restored from
    somewhere else. A cache keyed that way would go on serving prices parsed
    from bytes the feed no longer holds, and the page would look entirely
    normal while quoting fares from a download that had been replaced -- the
    one kind of cache failure nobody notices. So a cache that holds parsed
    data is keyed by the content itself, at a cost of about a fifth of a
    second over 48MB, against the half-minute parse it exists to avoid.
    """
    root = Path(path)
    a_directory = root.is_dir()
    files = [root] if not a_directory else sorted(item for item in root.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    for item in files:
        name = item.relative_to(root) if a_directory else item.name
        digest.update(str(name).encode("utf-8", "replace") + b"\n")
        try:
            with item.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
        except OSError:
            digest.update(b"missing")
    return digest.hexdigest()


def resumable_signature(shared: dict, index: list[dict]) -> str:
    """Identity of the inputs and decisions represented by a station build."""
    stable = {
        "source": source_fingerprint(),
        "feed": feed_fingerprint(shared["feed"]),
        "timetable": feed_fingerprint(shared["timetable"]) if shared["timetable"] else None,
        "config": {key: value for key, value in shared.items()
                   if key not in {"feed", "timetable", "built_at", "analytics"}},
        "stations": index,
    }
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def read_resume_state(path: Path, signature: str) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict) or data.get("schema") != 1 or data.get("signature") != signature:
        return set()
    completed = data.get("completed")
    return {str(slug) for slug in completed} if isinstance(completed, list) else set()


def replace_published(temporary: Path, path: Path, attempts: int = 5) -> None:
    """Put ``temporary`` in place of ``path``, surviving a moment's sharing lock.

    A full-network build is hours long and publishes thousands of files, and
    Windows refuses the replace while anything else holds the destination
    open -- an indexer, a virus scanner, or a person reading the resume file
    to see how far the build has got. The build that measured the network
    died that way at page 77 of 2,712, holding 76 finished pages, and a whole
    measurement to start again, for a lock that is released in milliseconds.
    So the replace is retried, and the last attempt still raises: a lock that
    persists is something an operator has to see.
    """
    for attempt in range(attempts):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1))


def write_resume_state(path: Path, signature: str, completed: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(
            {"schema": 1, "signature": signature, "completed": sorted(completed)},
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    replace_published(temporary, path)


def write_page_atomic(path: Path, html: str) -> None:
    """Publish one complete page, never a half-written file after interruption.

    A page is bytes a host serves, and the same build must produce the same
    bytes on every machine: on Windows a text-mode write turns every "\n" in
    the template into CRLF, so a release built there differs from the one CI
    builds while claiming to be the same site (four-dimension audit R14).
    ``newline`` says so, and the read side normalises for the same reason.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(html, encoding="utf-8", newline="\n")
    replace_published(temporary, path)


# -- the route manifest (S01, S04) ------------------------------------------
#
# The single weakness the re-envision audit names is the route contract: a
# build can publish a page whose internal links point at pages it never
# wrote. The fix is one manifest of the routes a release actually serves, and
# every chooser option, picker option and footer link derived from it. Nothing
# else in the build is allowed to invent an href.

HREF_ATTR = re.compile(r'href="([^"]+)"')

# The shared documents are named in src as well as in href -- the
# station stylesheet in a <link href>, the picker's options in a
# <script src> -- and a crawl that read only href would pass a site
# whose every page asked for a file the build never wrote.
SRC_ATTR = re.compile(r'src="([^"]+)"')

# The chooser writes its station options from an embedded JSON array rather
# than as markup, so the links a reader actually follows never appear as an
# href attribute. They are still this site's contract, and a crawl that only
# read attributes would pass a root page pointing at a station nobody wrote.
EMBEDDED_HREF = re.compile(r'"href"\s*:\s*"([^"]+)"')


def internal_hrefs(html: str) -> list[str]:
    """The internal links in one generated page.

    Only root-absolute paths count. A link to the seller's site, a heritage
    site or an external resource is not this site's contract, and a
    fragment-only or relative link resolves against the page it is already on.

    Both attributes and embedded JSON are read, because the chooser builds its
    station list in the browser: a link the page only creates once its script
    runs is still a link a reader follows, and a route contract that skipped
    them would check the root page and find nothing.
    """
    return [
        href
        for href in (
            HREF_ATTR.findall(html)
            + SRC_ATTR.findall(html)
            + EMBEDDED_HREF.findall(html)
        )
        if href.startswith("/") and not href.startswith("//")
    ]


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
    # Every file this release publishes, not only its pages: a shared
    # document is as much a route as a page is, and a request for one
    # that was not written is a broken link like any other.
    written = {
        path.relative_to(out_dir).as_posix()
        for path in out_dir.rglob("*")
        if path.is_file()
    }
    broken: list[str] = []
    for page in sorted(out_dir.rglob("*")):
        if not page.is_file() or page.suffix.lower() not in (".html", ".js", ".css"):
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


def write_release(
    out_dir: Path,
    *,
    index: list[dict],
    routes: list[str],
    budget_pounds: int,
    note: str,
    price_source: str,
    feed_date: str | None,
    analytics: str,
    synthetic: bool,
    privacy_contact: str,
    features: dict,
    built_at: str,
    base_path: str = "",
) -> Path:
    """Write the release's own routes: the chooser, the notice, the manifest.

    One function for both build shapes, because the all-origins path and the
    single-origin path used to hold a copy of this block each -- two writers
    (a plain ``write_text`` against ``write_page_atomic``), two clocks for the
    release's ``builtAt``, and two places for the shapes to drift apart
    (four-dimension audit R8). The chooser carries the build's provenance and
    the notice is dated from the stamp the pages themselves were built with,
    so every route of a release names one build (R3, R6).

    Returns the manifest path, because the caller reports what it wrote.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    # The chooser and the one script it fetches, written together: a release
    # whose chooser names a script it did not write is the contract the crawl
    # below refuses. Both build shapes end here, so neither can drift apart.
    write_chooser_script(out_dir)
    write_page_atomic(
        out_dir / "index.html",
        render_chooser(
            index,
            budget_pounds=budget_pounds,
            analytics=analytics,
            base_path=base_path,
            note=note,
            synthetic=synthetic,
            price_source=price_source,
            feed_date=feed_date,
        ),
    )
    print(f"wrote {out_dir / 'index.html'} (the chooser) offering {len(index)} station(s)")
    privacy = out_dir / "privacy" / "index.html"
    write_page_atomic(
        privacy,
        render_privacy(
            note,
            base_path,
            privacy_contact,
            features,
            synthetic,
            built_at=built_at,
        ),
    )
    print(f"wrote {privacy}")

    broken = crawl_internal_links(out_dir, base_path)
    if broken:
        link_crawl_failed(broken, out_dir)
    print(f"link crawl: every internal link in {out_dir} resolves to a written page")

    manifest_path = write_release_manifest(
        out_dir,
        [with_base(base_path, "/"), with_base(base_path, "/privacy/")] + list(routes),
        price_source=price_source,
        built_at=built_at,
        base_path=base_path,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = manifest_problems(out_dir, manifest, base_path)
    if missing:
        raise SystemExit(
            "error: the release manifest names routes this build did not write:\n"
            + "\n".join(f"  {problem}" for problem in missing)
        )
    print(f"wrote {manifest_path} naming {len(manifest['routes'])} route(s) of this release")
    return manifest_path


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
        relative = route[len(base_path):] if base_path and route.startswith(base_path) else route
        target = out_dir / (relative.lstrip("/") + "index.html" if relative.endswith("/") else relative.lstrip("/"))
        if not target.is_file():
            problems.append(f"the manifest names {route}, which was not written")
    return problems


# Bumped when the fare-index pickle layout changes: a worker restoring an
# index written under an older code version would rebuild the wrong structure,
# so the version segment names a fresh file and directory instead (audit B1).
# Version 2: Flow and Fare became slotted dataclasses (audit B2).
FARE_INDEX_CACHE_VERSION = 2


def fares_cache_identity(feed: str | Path) -> str:
    """Everything a parsed fares database depends on, as one digest.

    The feed's bytes are the obvious part and not the whole of it. A parsed
    database also carries the classification of every station, and that is read
    from files *beside* the feed -- the checked-in reference data, a corrected
    cache, a revised facet -- and from the code that reads them. Keying the
    cache on the feed alone would serve a database classified from sources that
    have since changed, with the same silent wrongness as a stale feed and one
    step further from the thing being cached: a page whose prices are current
    and whose station types are not. So the key covers all three, and each is
    cheap next to the parse it saves: the feed's bytes, a few megabytes of
    reference data, and a hash of the source files.
    """
    digest = hashlib.sha256()
    digest.update(feed_content_digest(feed).encode())
    digest.update(source_fingerprint().encode())
    for candidate in location_lookup_candidates(feed):
        digest.update(str(candidate.name).encode("utf-8", "replace"))
        try:
            digest.update(candidate.read_bytes())
        except OSError:
            digest.update(b"missing")
    return digest.hexdigest()


def fares_index_cache_paths(feed: str | Path) -> tuple[Path, Path]:
    """The shared fares metadata cache and the per-origin index directory.

    Both live in CACHE_DIR beside the timetable caches rather than inside the
    published site, and the format version sits in the name so a schema change
    writes new files instead of reading old ones. The path is keyed by
    ``fares_cache_identity``: a parsed cache is only worth reading while the
    feed, the classification sources, and the code reading them are what they
    were, and nothing weaker than their content can promise that. Two inputs
    that differ by a single byte get two sets of files rather than one, and the
    old set is simply never read again.
    """
    digest = fares_cache_identity(feed)[:20]
    stem = f"fare-index-v{FARE_INDEX_CACHE_VERSION}-{digest}"
    return CACHE_DIR / f"{stem}.pickle", CACHE_DIR / f"{stem}-origins"


class PageFares(NamedTuple):
    """What a one-origin build ended up with, and where it came from.

    ``index`` and ``common`` are the two files a build reads or writes, kept
    together because pruning has to protect both and a caller that only knew
    one of them could delete the other.
    """

    fares: FaresDb
    common: Path
    index: Path
    restored: bool


def load_page_fares(feed: str | Path, origin: str) -> PageFares:
    """The fares one origin's page needs, from disk when they are already there.

    A focused parse of the national feed reads every flow line in the download
    -- 727,315 of them, and half a minute of it -- to keep the ones reachable
    from one station, and a real station's page used to pay that on every
    build. The parallel build already splits a parsed feed into the metadata
    every page shares and a small slice per origin, and restores a slice in
    about a second, so the one-origin build writes the same two files and
    reads them back the same way. Measured on the real DTD download: 32.5s to
    parse and write, 1.0s to restore, and 38MB shared plus half a megabyte per
    origin on disk rather than 107MB of whole-database pickle per origin.

    The restored database is the one the pool workers already build pages from,
    and the pages are byte-for-byte the same either way, so a cache hit cannot
    quietly change a price. Anything the cache cannot answer -- a missing file,
    a half-written pickle, a schema this code no longer writes, an index filed
    under another origin's name -- falls back to parsing the feed and rewrites
    the index. A cache is an optimisation, so the worst it may do is be slow.

    Returns the database, the two cache files it came from or went to, and
    whether they were read or written, because a build that parsed the feed
    and a build that restored it are the same page and very different waits.
    """
    code = origin.strip().upper()
    common_cache, index_dir = fares_index_cache_paths(feed)
    index = index_dir / f"{code}.pickle"
    if common_cache.is_file() and index.is_file():
        try:
            fares = FaresDb.load_fare_index(common_cache, index)
        except (OSError, EOFError, ValueError, KeyError, AttributeError, TypeError, pickle.PickleError):
            pass
        else:
            # The index names the origin whose fares it holds. A file under
            # another station's name is not this station's fares, whatever the
            # path it was asked for, so it is not served. Nor is one whose
            # change stations have no index beside it: their fares are the
            # second tickets of the page's two-part rows (ADR-0061), and a page
            # served without them would quietly lose those rows.
            if fares._cache_origin == code and not fares.merge_interchange_indexes(index_dir):
                return PageFares(fares, common_cache, index, True)
    fares = FaresDb().load_feed(feed, focus_origin=code)
    fares.write_fare_indexes(common_cache, index_dir, [code])
    return PageFares(fares, common_cache, index, False)


def timetable_cache_identity(feed: str | Path, origin: str, destinations: set[str]) -> str:
    """Everything a focused timetable database depends on, as one digest.

    The same discipline as ``fares_cache_identity``: the feed's bytes, the
    source that reads them, and the stations the focus was asked for. A
    timetable cache keyed on names, sizes and mtimes -- which is what this one
    was -- cannot tell two downloads apart when a copy preserves timestamps or
    an archive is extracted with the dates stored in it, and a stale hit would
    put one download's services on a page built from another, which is a
    reader being shown a timetable that is not the one in force.
    """
    digest = hashlib.sha256()
    digest.update(feed_content_digest(feed).encode())
    digest.update(source_fingerprint().encode())
    digest.update((origin + ":" + ",".join(sorted(destinations))).encode())
    return digest.hexdigest()


def timetable_cache_path(feed: str | Path, origin: str, destinations: set[str]) -> Path:
    """Name a timetable cache by the feed's content and the stations it serves."""
    digest = timetable_cache_identity(feed, origin, destinations)[:20]
    return CACHE_DIR / f"timetable-{origin.strip().upper()}-{digest}.pickle"


#: Where a build keeps the per-origin timetable slices it can be built from
#: instead of the feed. Under `_cache/`, like every other derived artefact here:
#: a slice is cut from a feed and reproducible from it, and it is not part of
#: any site.
TIMETABLE_INDEX_ROOT = CACHE_DIR / "timetable-index"


def timetable_index_identity(feed: str | Path) -> str:
    """Everything a slice index is only valid against, as one digest.

    The same discipline as ``timetable_cache_identity``: the feed's bytes, the
    source that reads them, and the layout version of what is written. A slice
    is a database cut from one download by one version of the parser, so an
    index that names which is an index a build can trust, and one that does not
    is a miss rather than a page assembled from another download's services.
    """
    digest = hashlib.sha256()
    digest.update(feed_content_digest(feed).encode())
    digest.update(source_fingerprint().encode())
    digest.update(f"slice-index-{SLICE_INDEX_SCHEMA}".encode())
    return digest.hexdigest()


def timetable_index_location(root: str | Path, feed: str | Path) -> tuple[Path, str]:
    """Where one feed's slices live, and the identity they are only valid against.

    A pair rather than two functions because the identity costs a content digest
    of the whole feed -- about 1.7s over the 419MB timetable -- and both callers
    write into this directory and record the identity in the same breath.

    A directory whose own manifest already names this identity is the identity
    directory rather than a root of them, because that is the path a build log
    prints and so the path a reader has in hand. Only that identity is honoured:
    a directory cut from another download is not this feed's index, so naming it
    is a miss -- and, since this is also what the writer resolves its `--root`
    through, it is not a directory the writer will overwrite either.
    """
    identity = timetable_index_identity(feed)
    root = Path(root)
    if _declared_identity(root) == identity:
        return root, identity
    return root / identity[:20], identity


def _declared_identity(directory: Path) -> str | None:
    """The identity a directory's own manifest declares, if it declares one."""
    try:
        raw = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw.get("identity") if isinstance(raw, dict) else None


def open_timetable_index(root: str | Path, feed: str | Path | None) -> SliceIndex | None:
    """The slice index a build asked for, or None when there is not a usable one.

    With the feed in hand the directory is derived from it, so the index can only
    be the one that was cut from that download. Without it -- a build whose whole
    point is not to read the feed -- the index is opened by its own manifest,
    which is the only description of itself there is.
    """
    if feed is not None and Path(feed).exists():
        directory, identity = timetable_index_location(root, feed)
        return SliceIndex(
            directory,
            identity=identity,
            source={"feed": str(feed), "schema": SLICE_INDEX_SCHEMA},
        )
    return SliceIndex.open(root)


def missing_slice_message(index: SliceIndex, missing: list[str]) -> str:
    """What to say when the index has not got a slice for a page being built.

    Named rather than counted, and named before the build rather than per page:
    a page silently built without times is a page that lies about the services
    its station has, which is the one outcome worse than a build that stops.
    """
    shown = ", ".join(missing[:SLICE_MISSING_SHOWN])
    rest = "" if len(missing) <= SLICE_MISSING_SHOWN else f" and {len(missing) - SLICE_MISSING_SHOWN} more"
    return (
        f"{index.directory} holds no slice for {len(missing):,} of the pages this build "
        f"would write: {shown}{rest}.\n"
        "Add them with tools/build_timetable_index.py --origins, or pass --timetable "
        "to cut them from the feed as the build runs."
    )


#: Codes named in that message before it counts the rest.
SLICE_MISSING_SHOWN = 12


# The newest timetable caches kept per origin. One origin holds at most two
# live caches -- the common and the outbound-single focus -- and every older
# digest belongs to a feed revision that no build can hit again (audit B4).
TIMETABLE_CACHE_KEEP = 2


def prune_timetable_caches(*used: Path, keep: int = TIMETABLE_CACHE_KEEP) -> int:
    """Bound each origin's timetable caches to the newest ``keep`` files.

    The caches this build read or wrote are never deleted, even when an older
    sibling has a newer timestamp, so a cache hit cannot evict itself. Every
    other file past the keep line is a stale digest: the feed bytes or the
    focus set changed, the name can never be hit again, and it sat on disk
    until the next build rewrote the pair (audit B4). Returns how many files
    were deleted.
    """
    protected = {Path(path).resolve() for path in used}
    groups: dict[str, list[Path]] = {}
    for path in CACHE_DIR.glob("timetable-*.pickle"):
        parts = path.name.split("-")
        if len(parts) >= 3:
            groups.setdefault(parts[1], []).append(path)
    deleted = 0
    for paths in groups.values():
        in_use = sum(1 for path in paths if path.resolve() in protected)
        ranked: list[tuple[float, Path]] = []
        for path in paths:
            if path.resolve() in protected:
                continue
            try:
                ranked.append((path.stat().st_mtime, path))
            except OSError:
                # Gone already, or held by a scanner. A file that cannot be
                # read cannot be ranked, and tidying must never be the reason
                # an otherwise good build fails.
                continue
        ranked.sort(key=lambda item: item[0], reverse=True)
        for _, path in ranked[max(keep - in_use, 0) :]:
            try:
                path.unlink()
                deleted += 1
            except OSError:
                pass
    return deleted


# The fares caches kept per feed digest. One digest is the feed being built
# and the one before it; every older one belongs to a revision of the feed that
# no build can name again, and the shared half of each is 37MB of the national
# feed, so they are tidied on the same rule as the timetable caches.
FARE_INDEX_CACHE_KEEP = 2


def prune_fare_index_caches(*used: Path, keep: int = FARE_INDEX_CACHE_KEEP) -> int:
    """Bound the persisted fares caches to the newest ``keep`` feed digests.

    A fares cache is keyed by the feed's content, so every new revision of the
    download writes a new pair of names and the previous pair can never be read
    again. Left alone that is 37MB of shared metadata per revision, for as long
    as the feed is refreshed. A digest is dropped whole -- the shared half and
    the directory of per-origin indexes are one cache, and half of one serves
    nothing -- and the digest this build just read or wrote is never a
    candidate, however old its timestamp, so a hit cannot evict itself.
    Returns how many files were deleted.
    """
    protected = {Path(path).resolve() for path in used}
    groups: dict[str, list[Path]] = {}
    for path in CACHE_DIR.glob("fare-index-v*-*"):
        # fare-index-v2-<digest>.pickle and fare-index-v2-<digest>-origins
        parts = path.name.split("-")
        if len(parts) >= 4:
            groups.setdefault(parts[3].split(".")[0], []).append(path)
    ranked: list[tuple[float, str]] = []
    in_use = 0
    for digest, paths in groups.items():
        stamps: list[float] = []
        for path in paths:
            try:
                stamps.append(path.stat().st_mtime)
            except OSError:
                # Gone already, or held by a scanner. A file that cannot be
                # read cannot be ranked, and tidying must never be the reason
                # an otherwise good build fails.
                continue
        if any(path.resolve() in protected for path in paths):
            in_use += 1
        elif stamps:
            ranked.append((max(stamps), digest))
    ranked.sort(reverse=True)
    deleted = 0
    for _, digest in ranked[max(keep - in_use, 0) :]:
        for path in groups[digest]:
            try:
                if path.is_dir():
                    deleted += sum(1 for _ in path.iterdir())
                    shutil.rmtree(path)
                else:
                    path.unlink()
                    deleted += 1
            except OSError:
                pass
    return deleted


def _iso_day(value: object) -> str:
    """A date as ``YYYY-MM-DD``, from an ISO timestamp or an HTTP-date.

    ``Last-Modified`` arrives as ``Tue, 29 Sep 2026 04:15:00 GMT``, which is the
    portal's word for its own vintage but is not the ``YYYY-MM-DD`` the page's
    date formatting reads. Normalising here means the page never has to know
    which shape it was handed -- and a value in neither shape becomes the empty
    string, so a date the build could not read is left out of the page rather
    than printed as whatever ``undefined`` renders to.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    # Validated rather than pattern-matched: "2026-13-45" has the right shape
    # and is not a date, and a shape that passes would reach the page's
    # formatter and render as a month that does not exist.
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        return ""


def knowledgebase_dates(manifest: dict | None, name: str = "ticket-restrictions") -> tuple[str, str]:
    """When a Knowledgebase feed says it was published, and when it was confirmed.

    The first is the portal's own ``Last-Modified`` for the file -- its word for
    its own vintage, which is the only date a freshness claim about someone
    else's data can honestly rest on. The second is when this project's
    downloader last downloaded or revalidated it. Both come back as
    ``YYYY-MM-DD``.

    Reading it from the manifest rather than the clock is deliberate. "Today"
    would mean the day the page was *built*, which is a fact about the build and
    not about the data, and a claim that ages into a falsehood the longer the
    page sits on a server is not a claim at all.
    """
    entries = manifest.get("downloads") if isinstance(manifest, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        return (
            _iso_day(entry.get("last_modified")),
            _iso_day(entry.get("checked_at") or entry.get("downloaded_at")),
        )
    return "", ""


def describe_restriction_note(note: dict) -> str:
    """One sentence saying what the reference feed was asked and answered.

    Takes the note the page itself carries rather than the check it was made
    from, so the console line and the page cannot describe different answers:
    the console prints what the reader will see. The four answers are worded
    here and nowhere else, so the console, the page and a test all speak about
    the same check. Each says what was asked and what came back, and none of
    them says the portal still publishes something without saying how many
    conditions that was -- because "all" with nothing behind it is not a check.
    """

    when = f" (published {note['published']})" if note.get("published") else ""
    status = note.get("status")
    if status == ABSENT:
        return f"not checked, {note.get('note', '')}{when}"
    if status == UNKNOWN:
        return f"could not be checked, {note.get('note', '')}{when}"
    if status == UNPUBLISHED:
        codes = ", ".join(note.get("unlisted") or ())
        return (
            f"the portal no longer publishes {note.get('missing')} of the "
            f"{note.get('compared')} condition(s) this page shows ({codes}){when}"
        )
    return (
        f"the portal still publishes all {note.get('compared')} condition(s) "
        f"this page shows{when}"
    )


def reference_feed(path: str | Path | None) -> Knowledgebase | None:
    """The portal's own restriction feed, read once for the whole run.

    Read once because it is one document. A --all-origins build renders up to
    2,700 pages and every one of them asks a question of this same file, so it
    is parsed once and each page's answer is worked out from what that page
    shows. ``None`` means no reference feed was named, which the page has
    wording for rather than silence.
    """

    if path is None:
        return None
    return load_ticket_restrictions(path)


def restriction_codes_shown(rows: Iterable[dict]) -> set[str]:
    """The condition codes the given rows print.

    This set *is* the claim: the page reports on the conditions a reader can
    find on it. The first version asked the feed for every code the origin's
    flows could carry -- 32 for Grantham on the real feed, against the 4 its
    rows show -- so the page reported on conditions it did not display, naming
    ``2H`` and ``HR`` as retired while showing neither. A reader cannot check
    that, and on a page whose value is that its claims are checkable, an
    uncheckable claim is noise. What is on screen is the set.
    """

    codes: set[str] = set()
    for row in rows:
        # A two-ticket row prints both tickets' conditions (ADR-0061).
        for code in [row.get("restrictionCode")] + [
            ticket.get("restrictionCode") for ticket in row.get("tickets") or ()
        ]:
            code = (code or "").strip().upper()
            if code:
                codes.add(code)
    return codes


def reference_fingerprint(
    reference: Knowledgebase | None, published: str, checked: str
) -> str:
    """The identity of the reference feed, for a resumed build's signature.

    A build that resumes must not mix pages answered against two different
    reference feeds, so the feed belongs in the signature -- as a digest, not
    as the feed itself. The signature is JSON-serialised, and a parsed feed has
    no stable serialised form: its repr carries an address, which changes every
    run, so every resumed build would look like a different one and resume
    nothing.
    """

    if reference is None:
        return "absent"
    listed = ",".join(sorted(reference.restrictions))
    digest = hashlib.sha256(listed.encode("utf-8")).hexdigest()[:16]
    return f"{published}|{checked}|{digest}"


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


def is_dtd_download(path: str | Path) -> bool:
    """Say whether this feed is a real DTD download rather than a synthetic one.

    The synthetic default price line is only honest for a synthetic feed, and a
    build that cannot prove the feed is synthetic must not use it. A DTD
    download is recognised two ways: a download manifest anywhere beside it
    (the downloader's own record), or a zip whose members are the ``RJ`` series
    the DTD publishes.
    """
    feed = Path(path)
    for base in (feed, feed.parent, feed.parent.parent):
        if (base / MANIFEST_NAME).is_file():
            return True
    if feed.suffix.lower() != ".zip" or not feed.is_file():
        return False
    try:
        with zipfile.ZipFile(feed) as archive:
            return any(name.upper().startswith("RJFAF") for name in archive.namelist())
    except (OSError, ValueError, zipfile.BadZipFile):
        return False


def price_source_from_metadata(metadata: dict) -> str | None:
    """The provenance sentence from the metadata, or None if it names nothing."""
    source = metadata.get("source")
    downloaded = metadata.get("downloaded")
    if source and downloaded:
        return f"the {source}, downloaded {downloaded}"
    if source:
        return f"the {source}"
    return None


def read_feed_manifest(folders: list[Path]) -> dict | None:
    """The first readable download-manifest.json found beside the feeds.

    The downloader writes the manifest at the output root (``feeds/``) while
    the builds are pointed at the feed zip inside ``feeds/fares/``, so a zip
    feed is checked two levels up as well as one -- the same layout the station
    classification lookup uses. Missing the grandparent is what let a real
    fares build fall through to the synthetic price line. Like
    read_feed_metadata, None means no file was found and {} means one was found
    but could not be read -- a manifest that exists but is unusable is a real
    download whose provenance is broken, and the caller must not quietly call
    that synthetic.
    """
    seen: set[Path] = set()
    for folder in folders:
        bases = (folder, folder.parent)
        if folder.suffix.lower() == ".zip":
            bases = bases + (folder.parent.parent,)
        for candidate in tuple(base / MANIFEST_NAME for base in bases):
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                print(
                    f"warning: {candidate} is unreadable ({error}); the price line "
                    "cannot be read from it",
                    file=sys.stderr,
                )
                return {}
            if not isinstance(data, dict):
                print(f"warning: {candidate} is not a JSON object; ignored", file=sys.stderr)
                return {}
            return data
    return None


def price_source_from_manifest(manifest: dict) -> str | None:
    """A provenance sentence from the downloader's manifest, or None.

    A fares entry wins over a timetable entry because this line describes the
    prices, not the journey times. Within the same feed type the newest download
    wins. The timestamp is ISO with a Z; it is read by hand (date-only, fixed
    month names) rather than through a locale, so the sentence reads the same on
    every machine.
    """
    entries = manifest.get("downloads") if isinstance(manifest, dict) else None
    best: dict | None = None
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        if entry.get("source") != "dtd" or entry.get("name") not in ("fares", "timetable"):
            continue
        if not isinstance(entry.get("downloaded_at"), str):
            continue
        if best is None:
            best = entry
            continue
        # Prices are built from fares. A newer timetable download must never
        # change the provenance sentence for those fares.
        if best.get("name") == "fares" and entry.get("name") != "fares":
            continue
        if entry["downloaded_at"] > best["downloaded_at"]:
            best = entry
    if best is None:
        return None
    try:
        day = date.fromisoformat(best["downloaded_at"][:10])
    except ValueError:
        return None
    month = (
        "January February March April May June July August September October"
        " November December".split()
    )[day.month - 1]
    return (
        f"the National Rail Data Portal DTD {best['name']} feed, "
        f"downloaded {day.day} {month} {day.year}"
    )


def cif_date_to_iso(stamp: str) -> str | None:
    """A CIF date (YYMMDD) as the ISO date the page and Python share.

    The feed states its service window in its own six-digit form, which is what
    the audit prints and what a reader comparing it with the file needs to see.
    The page needs the same date as a value it can measure, so the conversion
    happens once here rather than as date arithmetic in the browser. A stamp
    that is not six digits is not a date, and is not guessed at. The century is
    read as 20xx, which is every feed this project has read; a stamp that would
    place the window in another century is a feed problem to notice, not one to
    paper over here.
    """
    if not stamp or len(stamp) != 6 or not stamp.isdigit():
        return None
    return "20" + stamp[:2] + "-" + stamp[2:4] + "-" + stamp[4:]


def human_date(iso: str) -> str:
    """An ISO date as the words a reader reads: "20 September 2026".

    The page's own script formats dates this way rather than through
    ``new Date(iso)``, which reads an ISO date as UTC midnight and prints the
    day before it for any reader behind UTC. The build writes the provenance
    and privacy dates in the same words, so the two routes cannot disagree
    about what a date is.
    """
    months = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )
    try:
        year, month, day = (int(part) for part in iso[:10].split("-"))
        return f"{day} {months[month - 1]} {year}"
    except (ValueError, IndexError):
        return iso


def feed_date_from(metadata: dict | None, manifest: dict | None = None) -> str | None:
    """The fares download's own date, as YYYY-MM-DD, or None.

    The provenance sentence says when a feed was downloaded in words; this is
    the same fact as a value, so the page can measure the age of the prices it
    is showing against its own clock rather than repeating a sentence the build
    wrote once. A timetable entry never wins: the date has to describe the
    fares, because that is the number the reader is judging.
    """
    if metadata:
        stamp = metadata.get("downloaded")
        if isinstance(stamp, str) and len(stamp) >= 10:
            return stamp[:10]
    entries = manifest.get("downloads") if isinstance(manifest, dict) else None
    best: str | None = None
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("source") != "dtd":
            continue
        stamp = entry.get("downloaded_at")
        if not isinstance(stamp, str) or len(stamp) < 10:
            continue
        if entry.get("name") == "fares":
            return stamp[:10]
        if best is None or stamp > best:
            best = stamp[:10]
    return best


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
    # "In a new tab" is the second half of what the link does, and the link's
    # own accessible name says it too (audit item 11, 9 October 2026).
    "The ticket link opens the seller's own search page in a new tab, so the journey is not "
    "filled in for you: enter the origin, the destination, the date, and how many of you are "
    "travelling. The price above is the railway's own walk-up fare, so it is the same "
    "whichever seller you buy it from."
)


def _slug_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "station"


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
        "--timetable-index",
        type=Path,
        default=None,
        help=(
            "directory of per-origin timetable slices to build from, written by "
            "tools/build_timetable_index.py; when it holds a slice for every "
            "page, no timetable feed is read at all"
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
    parser.add_argument("--max-changes", type=int, default=1)
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


# How far past the build's own day a row with no service is asked before it
# is called a station the week does not reach. A week, because that is the span
# a reader plans over and the span that makes the answer a fact about the
# station rather than about a Sunday.
SERVICE_WEEK_HORIZON = 7

# Why a row carries no journey, as three keys rather than a sentence written at
# three places in destination_row and again in the sweep below it. The build
# used to word each absence where it found it, so the payload held prose that
# the page then reworded for the cell it printed in, and two of the six
# sentences the build could write named no day at all -- "no timetable in this
# build" and "no service in this timetable" -- beside a station the network
# runs, which reads as a claim about the station rather than about the date the
# build happened to pick.
#
# The keys travel and the wording is composed in one place on the page, from
# the key, the day the build asked about and the next day the row does run. A
# row that is absent therefore cannot be worded without its day, because there
# is nowhere else for the wording to be written.
JOURNEY_FOUND = "found"
JOURNEY_NO_TIMETABLE = "no_timetable"
JOURNEY_NO_SERVICE = "no_service"

# Why a fare the feed holds did not become a price, in the words an empty page
# needs. Cheaper fares already held and fares to the origin itself are normal
# traffic, not reasons a destination is missing, so they are never listed.
UNPRICED_REASONS = {
    "ticket_is_not_a_standard_return": "fares that are not standard returns",
    "ticket_is_not_one_a_reader_can_buy": (
        "fares a reader cannot buy at the price they are quoted at, "
        "such as a child, a group, a staff or a concession fare"
    ),
    "ticket_is_not_for_public_sale": (
        "fares the catalogue marks as not for public sale"
    ),
    "ticket_is_not_for_public_sale": (
        "fares the catalogue marks as not for public sale"
    ),
    "flow_not_yet_valid": "flows not yet valid",
    "flow_expired": "flows past their last valid day",
    "flow_with_no_fare": "flows carrying no fare",
    "fare_with_no_ticket_type": "fares with no ticket type",
    "destination_has_no_location_record": "flows to destinations with no location record",
    "destination_has_no_station_code": "flows to destinations with no station code",
    "destination_is_a_fare_construction_point": "flows priced only to zone boundaries or coach stops",
    "fare_above_the_budget": "fares above the price this page can show",
}


def explain_unpriced(
    raw_count: int,
    excluded_itx_count: int,
    excluded_codes: list[str],
    tally: dict[str, int],
) -> str:
    """Why an origin priced nothing, for the payload's unpricedNote.

    Called only when every fare set on the page is empty. The count answers
    "how much does the feed even hold from here" and the reasons answer "so
    why is none of it on this page". The origin's name is already in the
    sentence this appends to, so it is not repeated here.

    The placeholder sentence claims every one of those destinations is
    withheld, so it is only said when every excluded row really is: an origin
    priced only into a zone boundary has nothing to withhold and would be told
    it had an ITX problem it does not have (audit A6).
    """
    if raw_count and excluded_itx_count == raw_count:
        codes = ", ".join(excluded_codes)
        if raw_count == 1:
            return (
                "The feed reaches 1 standard-return destination, and its cheapest fare is an "
                f"ITX placeholder ({codes}), which this page does not publish."
            )
        return (
            f"The feed reaches {raw_count} standard-return destinations, and the cheapest fare "
            f"to every one of them is an ITX placeholder ({codes}), which this page does not publish."
        )
    reasons = [
        (count, UNPRICED_REASONS[key])
        for key, count in sorted(tally.items(), key=lambda item: (-item[1], item[0]))
        if key in UNPRICED_REASONS
    ]
    if not reasons:
        return "The feed holds no fare from this origin at all."
    parts = "; ".join(f"{count} {label}" for count, label in reasons[:3])
    return f"The feed holds flows from this origin, but none prices a publishable fare: {parts}."


class PageContext(NamedTuple):
    """Everything one page's rows are built against, fixed for the whole page.

    ``origin`` and ``timetable`` are the resolved ones the page builds against:
    the station the page is about and the slice of the timetable it can use,
    after the fallback to the origin's own slice and the focus of that slice are
    done. ``day`` is the day the page reports, which is the day every fare and
    every journey search on it is asked about.
    """

    fares: FaresDb
    origin: Location
    timetable: TimetableDb | None
    day: date | None
    max_changes: int
    departure_limit: int
    provider: str
    adults: int
    network: str | None
    advertiser_id: str | None
    publisher_id: str
    mode: str
    railcard_families: list[RailcardFamily]


@dataclass
class RulePool:
    """The railcard rule records a page shares, keyed once each (audit B3).

    The full rule record repeats on nearly every row: on the heaviest real page
    one record served all 1,678 rows and the block was 388KB (measured). Rows
    keep a key into one payload map; only the drawer reads the record, and the
    table reads the price straight off the row.

    The pool owns the numbering, so an id is handed out the first time a record
    is asked for and no builder can renumber a page by being called in a
    different order.
    """

    rule_ids: dict[str, str] = field(default_factory=dict)
    railcard_rules: dict[str, dict] = field(default_factory=dict)

    def share(self, rule: dict | None) -> str | None:
        if rule is None:
            return None
        marker = json.dumps(rule, sort_keys=True)
        rule_id = self.rule_ids.get(marker)
        if rule_id is None:
            rule_id = str(len(self.railcard_rules))
            self.rule_ids[marker] = rule_id
            self.railcard_rules[rule_id] = rule
        return rule_id

    def rule_for(self, rule_id: str | None) -> dict | None:
        """The record a row's key names, for a builder reading back its own rule."""
        return self.railcard_rules.get(rule_id) if rule_id else None


def two_part_query(
    query: Callable[..., list[Reachable]], day: date | None
) -> Callable[[str], list[Reachable]]:
    """One ticket mode's selector, asked of any station's own page.

    ADR-0061: a place the feed prices in two parts is one row, and each ticket
    of it comes through the same selector as the list it joins, so the reader is
    quoted the journey they are shown rather than the cheapest fare on each leg
    found separately. Priced on the build's day, like every other row: the day
    control changes the times and neither price (ADR-0060).
    """
    return functools.partial(query, budget_pence=EVERYTHING_PENCE, adults=1, day=day)


def railcard_details(context: PageContext, pool: RulePool, one: Reachable) -> dict:
    """Each reviewed railcard's exact DTD decision for one destination.

    The reader holds one card at a time, so the payload carries a row per
    card rather than one card's answer repeated six times over the page.
    Each entry is the discounted price and a key into the shared rule map;
    the drawer resolves the rest, because the prose would otherwise be six
    sentences a row and the measured cost of one is already 433 bytes.
    """
    return {
        family.key: railcard_detail_for(context, pool, family, one)
        for family in context.railcard_families
    }


def railcard_pair_details(
    context: PageContext, pool: RulePool, two_part: TwoPartFare
) -> dict:
    """Each reviewed railcard's decision for a two-ticket row (ADR-0061).

    A two-ticket row is two published fares, so a card is decided on each
    ticket and the row's card price is the two card prices added -- the same
    sum the standard price is. A card the feed bans on either ticket cannot
    price the pair as a pair, so it is not offered; the row says so rather
    than quoting half a journey.
    """
    return {
        family.key: railcard_pair_detail_for(context, pool, family, two_part)
        for family in context.railcard_families
    }


def railcard_pair_detail_for(
    context: PageContext,
    pool: RulePool,
    family: RailcardFamily,
    two_part: TwoPartFare,
) -> dict:
    """One card's decision for a two-ticket row: both tickets, added together."""
    origin = context.origin
    legs = (
        railcard_detail_for(
            context, pool, family, two_part.first, leg_origin_crs=origin.crs
        ),
        railcard_detail_for(
            context, pool, family, two_part.second, leg_origin_crs=two_part.change_crs
        ),
    )
    blocking = next((leg for leg in legs if leg["pricePence"] is None), None)
    if blocking is not None:
        price = None
        minimum = None
        state = "blocked"
        total_ban = True
    else:
        price = sum(leg["pricePence"] for leg in legs)
        minimums = [leg["minimumFarePence"] for leg in legs]
        minimum = None if any(value is None for value in minimums) else sum(minimums)
        state = "eligible"
        total_ban = False
    restrictions = [
        (pool.rule_for(leg["rule"]) or {}).get("restrictionCode") for leg in legs
    ]
    restrictions = [code for code in restrictions if code and code != "none"]
    texts = [(pool.rule_for(leg["rule"]) or {}).get("text") for leg in legs]
    rule = {
        "sequence": "two",
        "status": "current",
        "ticketCode": two_part.first.ticket_code + " + " + two_part.second.ticket_code,
        "routeCode": two_part.first.route_code + " + " + two_part.second.route_code,
        "location": (
            f"{origin.crs}/{two_part.change_crs} + "
            f"{two_part.change_crs}/{two_part.crs}"
        ),
        "restrictionCode": " + ".join(restrictions) or "none",
        "totalBan": total_ban,
        "text": (
            f"Two tickets, both checked for {family.label}: "
            + " ".join(text for text in texts if text)
        ),
    }
    return {
        "state": state,
        "pricePence": price,
        "minimumFarePence": minimum,
        "rule": pool.share(rule),
    }


def railcard_detail_for(
    context: PageContext,
    pool: RulePool,
    family: RailcardFamily,
    one: Reachable,
    *,
    leg_origin_crs: str | None = None,
) -> dict:
    """One card's decision for one fare: its price and its rule key.

    ``leg_origin_crs`` names where the fare starts when that is not the page's
    own station: the second leg of a two-ticket row (ADR-0061) begins at the
    pricing split, and an RR rule matches the endpoints of the journey the
    fare is sold for.
    """
    fares = context.fares
    origin = context.origin
    railcard_code = family.key
    rules = fares.railcard_rules(
        railcard_code,
        ticket_code=one.ticket_code,
        route_code=one.route_code,
        origin_crs=leg_origin_crs or origin.crs,
        destination_crs=one.crs,
        origin_nlc=one.origin_nlc,
        destination_nlc=one.destination_nlc,
    )
    ban = next((rule for rule in rules if rule.total_ban), None)
    condition = next((rule for rule in rules if rule.restriction_code), None)
    shown_rule = ban or condition
    minimum = fares.minimum_fare(railcard_code, one.ticket_code, context.day)
    rule = None
    if shown_rule is not None:
        rule = {
            "sequence": shown_rule.sequence_no,
            "status": (
                "current"
                if shown_rule.current_or_future.upper() == "C"
                else shown_rule.current_or_future
            ),
            "ticketCode": shown_rule.ticket_code or "any",
            "routeCode": shown_rule.route_code or "any",
            "location": shown_rule.location or "any",
            "restrictionCode": shown_rule.restriction_code or "none",
            "totalBan": shown_rule.total_ban,
        }
    if ban is not None:
        price = None
        state = "blocked"
    else:
        price = fares.railcard_price(
            railcard_code, one.ticket_code, one.standard_pence, day=context.day
        )
        state = "eligible"
    if rule is not None:
        rule["text"] = (
            f"Current RR {rule['sequence']} for {family.label}: "
            f"ticket {rule['ticketCode']}, route {rule['routeCode']}, "
            f"location {rule['location']}; total ban "
            f"{'yes' if rule['totalBan'] else 'no'}; restriction "
            f"{rule['restrictionCode']}."
        )
    return {
        "state": state,
        "pricePence": price,
        "minimumFarePence": minimum,
        "rule": pool.share(
            rule
            or {
                "sequence": "none",
                "status": "current",
                "ticketCode": one.ticket_code,
                "routeCode": one.route_code,
                "location": f"{origin.crs}/{one.crs}",
                "restrictionCode": "none",
                "totalBan": False,
                "text": (
                    f"No matching current RR rule for {family.label}: ticket "
                    f"{one.ticket_code}, route {one.route_code}, endpoints "
                    f"{origin.crs}/{one.crs}."
                ),
            }
        ),
    }


def describe_restriction(context: PageContext, code: str) -> str:
    headers = context.fares.restrictions.headers
    if code in headers:
        return headers[code].description
    if code:
        return (
            "This fare carries restriction "
            + code
            + ", which this feed does not describe, so the condition has to be read "
            "from the seller's own terms"
        )
    return ""


def destination_row(
    context: PageContext,
    pool: RulePool,
    crs: str,
    one: Reachable | TwoPartFare,
    *,
    quality: str,
    journey_db: TimetableDb | None,
    with_departures: bool = True,
) -> tuple[dict, TicketLink]:
    # The journey belongs to the origin and the destination, not to the
    # ticket type, so it is read once per destination from the first
    # timetable this build holds that has one: the row's own, then the
    # page's. It used to be read from the row's own timetable only, so a
    # destination three fare lists reach carried three different answers,
    # and the cheapest list kept the one belonging to the fare that won.
    # Where the cheapest fare is an advance single, that is the list built
    # without a timetable, so the row said no service about a destination
    # the same payload prices a 45-minute direct journey to.
    fares = context.fares
    origin = context.origin
    max_changes = context.max_changes
    departure_limit = context.departure_limit
    day = context.day
    searched = (
        (journey_db,) if journey_db is context.timetable else (journey_db, context.timetable)
    )
    journey = None
    # Which database this row's week belongs to. The first one consulted is
    # the default, and a database that answered keeps it: a build with
    # --with-single-timetable holds a second timetable over the same feed
    # with a different focus, so the week for a row is the week of the
    # database that read that row, not of the page's first one.
    journey_source = None
    for db in searched:
        if db is None:
            continue
        if journey_source is None:
            journey_source = db
        found = db.best_journey(origin.crs, crs, max_changes=max_changes, day=day)
        if found:
            journey, journey_source = found, db
            break
    # The departures do not fall back. They are the times this fare is good
    # on, and an advance single's are only knowable from the separate
    # outbound-single timetable; a return-set train listed under an advance
    # single would be a time the reader cannot travel on that ticket.
    options = (
        journey_db.departures(origin.crs, crs, max_changes=max_changes, day=day, limit=departure_limit)
        if journey_db and with_departures
        else []
    )
    # Q2 (ADR-0045): a journey with a change is where a split ticket
    # can undercut the through fare, and the station it would change at is
    # one fact the build already holds. The page names it and claims no
    # price: the feed prices flows, not itineraries, so which two tickets
    # are cheaper is not in this data.
    change_stations = [
        {
            "crs": leg.destination_crs,
            "name": (
                fares.locations_by_crs[leg.destination_crs].name
                if leg.destination_crs in fares.locations_by_crs
                else leg.destination_crs
            ),
        }
        for leg in (journey.legs[:-1] if journey else ())
    ]
    link = ticket_link(
        origin.crs,
        crs,
        provider=context.provider,
        when=day,
        adults=context.adults,
        network=context.network,
        advertiser_id=context.advertiser_id,
        publisher_id=context.publisher_id,
        mode=context.mode,
    )
    # ADR-0061: a two-part row is two tickets, and every fact the row
    # states about its fare is a fact about both of them.
    two_part = one if isinstance(one, TwoPartFare) else None
    parts = two_part.legs if two_part else (one,)
    restriction_code = next(
        (part.restriction_code for part in parts if part.restriction_code), ""
    )
    row = {
        "crs": crs,
        "name": one.station,
        "adultPence": one.best_pence,
        "partyPence": one.best_pence * 2,
        # One entry per reviewed railcard the feed carries. The reader holds
        # one at a time, so the page picks the key rather than offering six
        # prices per row in the table. A two-ticket row (ADR-0061) is a card
        # decision per ticket, and the row's card price is the two card
        # prices added together, so the card still prices the row.
        "railcards": (
            railcard_pair_details(context, pool, two_part)
            if two_part
            else railcard_details(context, pool, one)
        ),
        "destinationType": fares.destination_type(crs),
        "destinationTypes": fares.destination_types(crs),
        "heritageSites": fares.heritage_sites(crs),
        "natureSites": fares.nature_sites(crs),
        "coastalSites": fares.coastal_sites(crs),
        # ADR-0062: RSPB, National Trust and National Park / Landscape
        # gateways, each with its own reviewed list and named proof.
        "rspbSites": fares.rspb_sites(crs),
        "nationalTrustSites": fares.national_trust_sites(crs),
        "nationalParkSites": fares.national_park_sites(crs),
        "ticket": " + ".join(part.ticket_code for part in parts),
        "isAdvance": any(
            fares.is_advance_fare(part.ticket_name, part.restriction_code)
            for part in parts
        ),
        "quality": quality,
        "offPeak": any(part.off_peak for part in parts),
        "restrictionCode": restriction_code,
        "routeCode": " + ".join(part.route_code for part in parts),
        # C08: a code says which condition, not what it permits. The
        # description is the feed's own wording for the code, and the
        # fallback says plainly that the feed has none, so a reader is
        # never told to "check the seller" as if that were a decoded rule.
        "restrictionDescription": describe_restriction(context, restriction_code),
        "minutes": journey.duration if journey else None,
        "changes": journey.changes if journey else None,
        # One entry per leg boundary, so a one-change journey carries the
        # one interchange and a longer one carries every change station.
        "changeStations": change_stations,
        # S23: why there is no time, so a reader can tell "the feed has no
        # service" from "this build priced fares only" instead of reading
        # a bare dash for both. A key rather than a sentence: the page words
        # it, in one place, from this and the day.
        "journeyState": (
            JOURNEY_FOUND
            if journey
            # The build has no timetable to read, rather than this row's
            # list not having one: the search above is what decides it, and
            # it is the same search that decided `journey`.
            else JOURNEY_NO_TIMETABLE
            if all(db is None for db in searched)
            else JOURNEY_NO_SERVICE
        ),
        "legs": [leg.train_uid for leg in journey.legs] if journey else [],
        # Which database read this row, for the week walk below. Carried on
        # the row and popped off it again before the payload is encoded, so
        # the build can carry it and the page never sees it.
        "_journeySource": journey_source,
        "link": {"url": link.url, "label": link.label, "rel": link.rel},
        "departures": [
            {"depart": option.departure, "arrive": option.arrival, "changes": option.changes}
            for option in options
        ],
    }
    if two_part:
        # Both tickets, each with its own price and its own restriction,
        # because two tickets are two purchases with two sets of conditions
        # and a row naming one of them would be silent about the other.
        ends = (
            (origin.crs, origin.name, two_part.change_crs, two_part.change_station),
            (two_part.change_crs, two_part.change_station, crs, one.station),
        )
        row["tickets"] = [
            {
                "ticket": part.ticket_code,
                "fromCrs": start_crs,
                "fromName": start_name,
                "toCrs": end_crs,
                "toName": end_name,
                "adultPence": part.best_pence,
                "restrictionCode": part.restriction_code,
                "restrictionDescription": describe_restriction(context, part.restriction_code),
                "routeCode": part.route_code,
            }
            for part, (start_crs, start_name, end_crs, end_name) in zip(parts, ends)
        ]
    # The link comes back with the row: the payload's two disclosure facts are
    # every row's link folded into one, and a row alone cannot say them, so a
    # caller that took only the row would have to build the link again.
    return row, link


def day_answer(row: dict, offset: int, service_week: list[list[dict]]) -> list[int] | None:
    # What this row's station is on the day at this offset, or nothing.
    # The row names its own database by index, so a row read by the second
    # timetable is looked up in the second timetable's week.
    index = row.get("serviceWeekIndex")
    if index is None or index < 0 or not service_week:
        return None
    return service_week[index][offset].get(row["crs"])


def build_payload(
    fares: FaresDb,
    timetable: TimetableDb | None,
    origin_crs: str,
    *,
    single_timetable: TimetableDb | None = None,
    max_changes: int = 1,
    day: date | None = None,
    note: str = DEFAULT_NOTE,
    attribution: str | None = None,
    price_source: str = DEFAULT_PRICE_SOURCE,
    feed_date: str | None = None,
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
    built_at: str | None = None,
    published_routes: list[dict] | None = None,
    reference: "Knowledgebase | None" = None,
    reference_published: str = "",
    reference_checked: str = "",
    timetable_index: SliceIndex | None = None,
) -> dict:
    """Every publishable destination from the origin, at both party prices.

    Each destination carries the ticket links and the next few journeys. The
    journeys are options in the feed, not a booking: an unrestricted fare is
    valid on any of them, while an Advance single is valid only on a
    qualifying train, which is why no train is chosen for the reader.

    ``timetable_index`` is where this page's timetable comes from when there is
    no ``timetable``: the slice of the feed that was cut for this origin and
    written to disk. The caller checked that the slice was there before the
    build started, so a miss here is a file that vanished or will not read --
    and it raises, because a page assembled without times would say the station
    has no services.
    """
    if timetable is None and timetable_index is not None:
        timetable = timetable_index.load(origin_crs)
        if timetable is None:
            # The caller checked every page this build writes had a slice before
            # it got here, so a miss now is a file that vanished or one that will
            # not read. A page assembled without times would say the station has
            # no services, which is worse than a build that stops.
            raise OSError(
                f"{origin_crs} has no readable slice in {timetable_index.directory}"
            )
    origin = fares.locations_by_crs[origin_crs.strip().upper()]
    # Every destination is included, then the browser's price filter decides
    # which rows are within the reader's budget. The fare shown is the cheapest
    # displayable standard-class return found in the feed; ITX placeholder fares
    # are excluded, while legitimate restrictions remain visible with their code.
    # The tally survives on the payload's unpricedNote: without it the rejected
    # fares vanish before any message could count them (audit A1).
    raw_tally: dict[str, int] = {}
    raw_destinations = fares.destinations_within(
        origin.crs, EVERYTHING_PENCE, adults=1, day=day, tally=raw_tally
    )
    single = {
        row.crs: row
        for row in fares.page_destinations_within(
            origin.crs, EVERYTHING_PENCE, adults=1, day=day
        )
    }
    excluded_itx = [
        row for row in raw_destinations
        if row.ticket_code in PLACEHOLDER_TICKET_CODES
        or "ITX" in row.ticket_name.upper()
    ]
    single_ticket_rows = fares.page_single_destinations_within(
        origin.crs, EVERYTHING_PENCE, adults=1, day=day
    )
    single_tickets = {row.crs: row for row in single_ticket_rows}
    anytime_ticket_rows = fares.publishable_destinations_within(
        origin.crs, EVERYTHING_PENCE, adults=1, day=day
    )
    anytime_tickets = {row.crs: row for row in anytime_ticket_rows}
    # ADR-0061: a place the feed prices in two parts is one row. The feed
    # publishes flows along pricing-route boundaries rather than journeys, so
    # a place with no origin-destination flow is priced as two tickets that
    # meet at a calling point on the journey the page already shows for it.
    # Candidates are every intermediate stop on each of the journey's trains,
    # plus the station the reader leaves when the journey changes trains.
    # When several of those both sell, the cheapest valid sum wins. Each
    # ticket still comes through the same selector as the list it joins, so
    # the reader is quoted the journey they are shown and not the cheapest
    # fare on each leg found separately. Priced on the build's day, like
    # every other row: the day control changes the times and neither price
    # (ADR-0060).
    split_at: dict[str, list[str]] = {}
    if timetable is not None:
        # One page, one station, so the page is built from the slice of the
        # timetable it can use rather than from the national index. The
        # all-origins path hands every page the whole country -- one feed, one
        # page for each of 3,424 stations -- and holding that while a page is
        # assembled is where a two-station build's hour of paging went
        # (docs/build-performance-findings.md). A database that was already
        # loaded for this origin is returned unchanged, so the single-origin
        # path pays nothing here and its pages do not move.
        timetable = timetable.focused(origin.crs)
        reached = timetable.journeys_from(origin.crs, max_changes=max_changes, day=day)
        for crs, journey in reached.items():
            if journey.changes > max_changes or is_pseudo_station(crs):
                continue
            candidates: list[str] = []
            for leg in journey.legs:
                for mid in timetable.intermediate_crs(
                    leg.train_uid, leg.origin_crs, leg.destination_crs, day=day
                ):
                    if mid not in candidates and mid not in {origin.crs, crs}:
                        candidates.append(mid)
                if leg.destination_crs != crs and leg.destination_crs not in candidates:
                    candidates.append(leg.destination_crs)
            if candidates:
                split_at[crs] = candidates
    if split_at:
        for priced, query in (
            (single, fares.page_destinations_within),
            (single_tickets, fares.page_single_destinations_within),
            (anytime_tickets, fares.publishable_destinations_within),
        ):
            for two_part in fares.two_part_fares(
                origin.crs,
                split_at,
                two_part_query(query, day),
            ):
                priced[two_part.crs] = two_part
    # Two Together is evaluated against the current DTD RR records below. A
    # destination carries a railcard price unless its ticket, route, and
    # locations have a matching total ban.

    tracked = False
    disclosure: str | None = None
    # Every railcard the project has reviewed and the feed carries, as products.
    # Two Together is one of them rather than the only one, so a reader who
    # holds a 16-25 or a Senior card answers the same question with the same
    # page. The price of each is calculated from the feed's minimum-fare table
    # and the current RR restriction records; only a matching total ban removes
    # it, per card.
    railcard_families = fares.reviewed_railcard_families()

    # The page's own configuration, held once: the row and railcard builders
    # read a dozen of these facts between them, and one object keeps the list
    # in one place and lets a builder be called on its own terms.
    context = PageContext(
        fares=fares,
        origin=origin,
        timetable=timetable,
        day=day,
        max_changes=max_changes,
        departure_limit=departure_limit,
        provider=provider,
        adults=adults,
        network=network,
        advertiser_id=advertiser_id,
        publisher_id=publisher_id,
        mode=mode,
        railcard_families=railcard_families,
    )
    # The full rule record repeats on nearly every row: on the heaviest real
    # page one record served all 1,678 rows and the block was 388KB (audit B3,
    # measured). Rows keep a key into one payload map; only the drawer reads
    # the record, and the table reads the price straight off the row. The pool
    # owns the map, so a builder asks it for a key rather than threading the
    # two dicts that hold the records and their numbering.
    pool = RulePool()

    destinations: list[dict] = []
    single_destinations: list[dict] = []
    anytime_destinations: list[dict] = []
    # The row and its link come back together, because the page's two
    # disclosure facts are every row's link folded into one: the payload says
    # once whether this page's links are tracked and what it discloses.
    for crs, one in sorted(single.items(), key=lambda item: item[1].best_pence):
        row, link = destination_row(
            context,
            pool,
            crs,
            one,
            quality="standard return",
            journey_db=timetable,
        )
        destinations.append(row)
        tracked = tracked or link.tracked
        disclosure = disclosure or link.disclosure
    for crs, one in sorted(single_tickets.items(), key=lambda item: item[1].best_pence):
        row, link = destination_row(
            context,
            pool,
            crs,
            one,
            with_departures=single_timetable is not None,
            quality="outbound single",
            journey_db=single_timetable,
        )
        single_destinations.append(row)
        tracked = tracked or link.tracked
        disclosure = disclosure or link.disclosure
    for crs, one in sorted(anytime_tickets.items(), key=lambda item: item[1].best_pence):
        row, link = destination_row(
            context,
            pool,
            crs,
            one,
            quality="unrestricted Anytime Day Return",
            journey_db=timetable,
        )
        anytime_destinations.append(row)
        tracked = tracked or link.tracked
        disclosure = disclosure or link.disclosure

    # S23, one step further. "No service" is a statement about the day this
    # build asked about, not about the station: measured from Nottingham on
    # 2026-10-04, a Sunday, Langwith, Shirebrook, Creswell and Whitwell all read
    # "No service", and all four are direct journeys of 46 to 58 minutes on
    # every other day of that week. The feed calls at every one of them, so
    # nothing about them is missing from the network -- only from that Sunday.
    # A reader cannot reach the day the build happened to pick, so a row with no
    # service on it is asked the week as well and carries the day it does run.
    #
    # The week is walked once, outermost, because best_journey() rebuilds its
    # index whenever the day changes: one index build per day whatever the number
    # of rows, rather than one per row. The sweep runs only when the page has a
    # row that needs it, so a build on a day the network runs normally pays
    # nothing for it. Wirksworth is the other kind of row: no service on any day
    # of the week, so it keeps saying so and gains no key.
    # S23, one step further, and then the reader picks the day. "No service" is
    # a statement about the day this build asked about, not about the station:
    # measured from Nottingham on 2026-10-04, a Sunday, Langwith, Shirebrook,
    # Creswell and Whitwell all read "No service", and all four are direct
    # journeys of 46 to 58 minutes on every other day of that week. The feed
    # calls at every one of them, so nothing about them is missing from the
    # network, only from that Sunday.
    #
    # So the whole week is walked and every answer kept, and the page hands the
    # reader the choice of which day the times are for. The sweep this replaces
    # asked only the rows with no service that day, which is a fifth of them on
    # a Sunday and none on a Wednesday, and it could answer "does it run at all
    # that week" and nothing finer: a row taking 46 minutes on the Tuesday and
    # 70 on the Monday had no way to say so.
    #
    # The days are outermost because the search rebuilds its index whenever the
    # day changes: one index build a day, not one a row. Within a day it is one
    # walk for every destination, not one walk per destination, which is what
    # journeys_from() is for and what makes this shape affordable.
    #
    # Held once per page and keyed by station, because a destination priced by
    # three fare lists wants one answer three times. Only the stations a row
    # names are kept: the walk reaches the whole network, and the rest of it is
    # an answer nobody asked for.
    collections = (destinations, single_destinations, anytime_destinations)
    sources: list = []
    for collection in collections:
        for row in collection:
            source = row.get("_journeySource")
            if source is not None and not any(source is seen for seen in sources):
                sources.append(source)
    service_days: list[str] = []
    service_week: list[list[dict]] = []
    if sources and day is not None:
        service_days = [
            (day + timedelta(days=offset)).isoformat()
            for offset in range(0, SERVICE_WEEK_HORIZON + 1)
        ]
        wanted = {row["crs"] for collection in collections for row in collection}
        for source in sources:
            per_day = []
            for offset in range(0, SERVICE_WEEK_HORIZON + 1):
                reached = source.journeys_from(
                    origin.crs, max_changes=max_changes, day=day + timedelta(days=offset)
                )
                per_day.append(
                    {
                        crs: [journey.duration, journey.changes]
                        for crs, journey in reached.items()
                        if crs in wanted
                    }
                )
            service_week.append(per_day)

    # Read out of the table by the day, not copied into the row. The index
    # is what the page needs: which of the page's tables this row belongs to,
    # because a row read by the second timetable is not in the first one's.
    for collection in collections:
        for row in collection:
            source = row.get("_journeySource")
            index = -1
            for position, seen in enumerate(sources):
                if seen is source:
                    index = position
                    break
            # Null rather than -1 for "no week". A pool reference is a
            # negative number, so -1 would be read by the page as pool entry
            # zero, which is a railcard record: the cell would decode into
            # somebody's railcards rather than into a row with no week.
            row["serviceWeekIndex"] = index if service_week else None
            row.pop("_journeySource", None)

    for collection in collections:
        for row in collection:
            if row["journeyState"] == "found":
                continue
            # The day this row next runs, which is the day the absence wording
            # in JOURNEY_ABSENCE names. Only a row carrying an absence gains it,
            # so a page whose every destination runs that day pays nothing here,
            # and the state itself does not change: it is the same absence, and
            # only what is known about the week around it has moved.
            for offset in range(1, SERVICE_WEEK_HORIZON + 1):
                if day_answer(row, offset, service_week) is not None:
                    row["nextService"] = service_days[offset]
                    break

    # C08: the feed's own outward and return validity for each restriction
    # code these rows carry. Keyed by code and held once, because the rows
    # already carry the code: repeating the wording on every row would put the
    # same sentence on a page 1,678 times, which is what the railcard rule map
    # below already had to be fixed for.
    restriction_validity: dict[str, dict[str, str]] = {}
    shown_codes = restriction_codes_shown(
        row
        for collection in (destinations, single_destinations, anytime_destinations)
        for row in collection
    )
    for collection in (destinations, single_destinations, anytime_destinations):
        for row in collection:
            # A two-ticket row's own code is its first restricted ticket's, so
            # each ticket is asked as well (ADR-0061).
            for code in [row["restrictionCode"]] + [
                ticket["restrictionCode"] for ticket in row.get("tickets") or ()
            ]:
                header = fares.restrictions.headers.get(code) if code else None
                if header is None or code in restriction_validity:
                    continue
                if not (header.outward_text or header.return_text):
                    continue
                restriction_validity[code] = {
                    "outwardText": header.outward_text,
                    "returnText": header.return_text,
                }

    excluded_codes = sorted({row.ticket_code for row in excluded_itx})
    # The freshness claim for the conditions above. Carried as plain data
    # rather than as a sentence so the page writes it in its own voice, and so
    # a test can assert on the fact rather than on a wording that changes.
    # The second opinion is about the conditions *this page* shows, so it is
    # asked here rather than once for the run. Reading the reference feed stays
    # a single parse for the whole build; only the set difference is per page,
    # and it is a handful of codes against a dict.
    reference_check = (
        check_restrictions(
            shown_codes,
            reference,
            published=reference_published,
            checked_at=reference_checked,
        )
        if reference is not None
        else RestrictionCheck(status=ABSENT, note="no reference feed was named")
    )
    restriction_reference_note = {
        "status": reference_check.status,
        "compared": reference_check.compared,
        "listed": reference_check.listed,
        "missing": reference_check.missing,
        "unlisted": list(reference_check.unlisted),
        "note": reference_check.note,
        "published": reference_check.published,
        "checkedAt": reference_check.checked_at,
        "verified": reference_check.verified,
    }
    unpriced_note = (
        explain_unpriced(
            len(raw_destinations), len(excluded_itx), excluded_codes, raw_tally
        )
        if not destinations and not single_destinations and not anytime_destinations
        else None
    )

    origin_row = fares.locations_by_crs[origin.crs]
    # The picker's options (ADR-0019), from the one shared slug map, so a page
    # built on its own links to the same folders the --all-origins build writes.
    slugs = station_slugs_for(fares.locations_by_crs)
    every_row = list(destinations) + list(single_destinations) + list(anytime_destinations)
    # S15, per card: a railcard is a constraint on the party, not a discount a
    # solo reader can tick. The bounds are the feed's own records, so the page
    # states the rule the data states rather than one this project invented, and
    # a card whose range does not cover the chosen party is not offered for it.
    railcards = []
    for family in railcard_families:
        eligible = {
            row["crs"]
            for row in every_row
            if family.key in row["railcards"]
            and row["railcards"][family.key]["pricePence"] is not None
            and row["railcards"][family.key]["pricePence"] < row["adultPence"]
        }
        railcards.append(
            {
                "key": family.key,
                "label": family.label,
                "codes": list(family.codes),
                "minAdults": family.min_adults,
                "maxAdults": family.max_adults,
                "eligibleCount": len(eligible),
            }
        )
    # The timetable's own service window, read once for both dates below.
    service_window = timetable.service_window() if timetable else ("", "")
    # S29: how much of the feed's coverage this page could not show, counted
    # rather than asserted. A destination whose type is not in the reviewed
    # registry is still priced and still listed, but no chip can ever select it,
    # so the count is the difference between "every type" and "every type we
    # have reviewed".
    unclassified = {
        row["crs"]
        for collection in (destinations, single_destinations, anytime_destinations)
        for row in collection
        if not set(row.get("destinationTypes") or []) - {"other"}
    }

    return {
        "origin": {"crs": origin_row.crs, "name": display_station_name(origin_row.crs, origin_row.name)},
        "sourceFingerprint": source_fingerprint(),
        "builtAt": built_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "destinations": destinations,
        "singleDestinations": single_destinations,
        "anytimeDestinations": anytime_destinations,
        "singleJourneyNote": (
            "Single fares are timed from the same timetable as the returns, because "
            "this build loaded no separate outbound-single timetable."
            if single_timetable is None and timetable is not None
            else None
        ),
        "rawFareDestinationCount": len(raw_destinations),
        "singleFareDestinationCount": len(single_ticket_rows),
        "excludedItxCount": len(excluded_itx),
        "excludedItxCodes": excluded_codes,
        # Destination rows this origin lost to a missing name: the feed's own
        # ceiling on coverage, carried so the report can count it beside the
        # unsourced stations (audit A3).
        "unnameableFareCount": unnameable_from_tally(raw_tally),
        # S29: priced rows no chip can select, because their type is not in the
        # reviewed registry. Shown beside the counts so "every destination"
        # stays a defensible claim.
        "unclassifiedDestinationCount": len(unclassified),
        "locationTypeReviewed": bool(fares.location_type_source),
        "unpricedNote": unpriced_note,
        # The picker's options, from the route manifest of pages this release
        # actually writes (S01). When the caller supplies published_routes
        # those are the only stations offered, so no link can point at a page
        # that was not generated. When it does not -- the single-page unit
        # build and the direct build_payload tests -- the options are every
        # real station in the feed, which is what a full-network site serves.
        "stations": (
            [
                {"name": entry["name"], "crs": entry["crs"], "href": entry["href"]}
                for entry in published_routes
                if entry["crs"] != origin.crs
            ]
            if published_routes is not None
            else [
                {
                    "name": loc.name,
                    "crs": loc.crs,
                    "href": with_base(base_path, f"/from/{slugs[crs]}/"),
                }
                for crs, loc in sorted(fares.locations_by_crs.items())
                if crs != origin.crs and not is_pseudo_station(crs)
            ]
        ),
        # Said by the page when this origin priced nothing, so the difference
        # between "nothing inside your budget" and "nothing priced from here at
        # all" is on the page rather than inferred from an empty table.
        "stationCount": len(fares.locations_by_crs),
        "hasJourneys": timetable is not None,
        # The collection, and the shared RR rule records behind it. Nothing is
        # selected: the reader names the card they hold, or reads standard
        # fares, and the browser remembers which they chose.
        "railcards": railcards,
        "railcardRules": pool.railcard_rules,
        # C08: the reader-facing validity behind a restriction code, once per
        # code. The page resolves a row's code against this rather than each
        # row repeating the same strings.
        "restrictionValidity": restriction_validity,
        "restrictionReference": restriction_reference_note,
        "pricingBasis": "cheapest displayable standard-class fare found in the feed, in the ticket mode the page opens in; each mode names above the table what its fares are, with ITX placeholders excluded and Advance singles labelled as train-specific",
        "serviceDate": day.isoformat() if day else None,
        # The span the sweep asked, so the page can say which days a row with
        # no next service was actually checked for rather than saying "no
        # service" and leaving the window unstated.
        "serviceHorizon": SERVICE_WEEK_HORIZON,
        # The days themselves, and every destination's answer on each of
        # them. Held at page level rather than per row because a destination
        # priced by three fare lists wants one answer three times, and three
        # copies of the same eight answers is the same sentence eight times
        # over in three places. The rows carry serviceWeekIndex instead, so
        # the page reads the table through the row rather than the row
        # carrying a copy of the table. Empty when the build had no day to
        # walk the week from, which is when the page shows no day control.
        "serviceDays": service_days,
        "serviceWeek": service_week,
        "note": note,
        "attribution": attribution,
        # Where the numbers on this page came from. It sits with the prices,
        # not in the footer, because where a number came from is part of the
        # number; the footer keeps the licence wording, which is a different
        # reader's question.
        "priceSource": price_source,
        # S33: the dates the reader needs to judge the numbers. The fares date
        # is the download's own, the timetable dates are the service window the
        # feed states, and the threshold is the number a reader can hold this
        # page to. With no timetable the page says it prices fares only, which
        # is a choice rather than a stale feed.
        "feedDate": feed_date,
        "timetableFrom": cif_date_to_iso(service_window[0]) if service_window else None,
        "timetableTo": cif_date_to_iso(service_window[1]) if service_window else None,
        "staleAfterDays": STALE_AFTER_DAYS,
        # Internal links are prefixed when the host does not serve the site at
        # its domain root (ADR-0024). The template carries it too, for the
        # links that are written as HTML rather than built in JS.
        "baseHref": with_base(base_path, "/"),
        # The station route fetches one stylesheet, at the path this release is
        # published at (ADR-0047). The picker sets its own the same way.
        "styleSrc": with_base(base_path, "/" + station_style_asset_name()),
        # And one script, at the path this release is published at (T1). The
        # page's own answer is its destinations; the code that reads them is
        # the same on every page of the route, so it travels once.
        "scriptSrc": with_base(base_path, "/" + station_script_asset_name()),
        # S45: the state is a fact about the build, so it is carried in the
        # payload rather than re-derived by each renderer.
        "synthetic": price_source == DEFAULT_PRICE_SOURCE,
        "linkNote": LINK_NOTE_FALLBACK if mode == "fallback" else None,
    # The pricing paragraph is a fixed part of the page, but the payload
    # carries it so tests can assert the page says what the times are.
    "pricingNote": PRICING_NOTE,
        "feed": fares.stats(),
        "locationTypeSource": fares.location_type_source,
        "timetable": timetable.stats() if timetable else None,
        "adults": adults,
        "tracked": tracked,
        "disclosure": disclosure,
        "railcardNote": (
            (
                "No railcard is selected, so the prices shown are standard fares. Choose the "
                "card you hold and each displayed fare is repriced from that card's own "
                "minimum-fare table, discounted by a third and rounded down to the nearest 5p. "
                "Current DTD RR route, ticket, location and total-ban rules are checked for "
                "every destination and every card; matching restriction codes are retained as "
                "travel conditions rather than treated as bans."
            )
            if railcards
            else (
                "No reviewed railcard is present in this feed. The prices shown are standard fares."
            )
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


def _priced_destinations(
    fares: FaresDb,
    timetable,
    origin_crs: str,
    day: date | None = None,
    coverage: UnsourcedReport | None = None,
) -> int:
    """How many destinations an origin's page would carry, for the index.

    The page offers three ticket modes, so "priceable" is the union of all
    three: a station whose only fares are restricted returns or singles still
    has a page a reader can use, and ADR-0019 decision 3 asks whether that
    page can answer, not whether one mode of it can. Audit A1 caught the
    previous test using the reviewed-anytime selector alone, which kept King's
    Cross out of the chooser while its page carried 171 returns; the union now
    lives in ``FaresDb.priced_destinations_within`` so this test, the chooser
    and the coverage report cannot ask three different questions. When a
    coverage report is passed, the same rows are checked for a station no
    source could classify -- the queries have already been run, so naming the
    gap costs nothing extra on a 2,500-origin build.
    """
    tally: dict[str, int] = {}
    rows = fares.priced_destinations_within(
        origin_crs, EVERYTHING_PENCE, adults=1, day=day, tally=tally
    )
    if coverage is not None:
        coverage.note_fares_rows(fares, rows, origin_crs)
        coverage.note_unnameable(origin_crs, unnameable_from_tally(tally))
    return len(rows)


# The feed names a station with the CIF short form, and a few entries are
# compressed past what a reader can read as a place: "WARRINGTON BK QY",
# "HEATHROW UNDERGD", "XC ORIGIN". This is the reviewed list of the ones a
# reader-facing list was showing raw, keyed by CRS because the code is the
# feed's identity for a station -- a rename would otherwise surface as an
# entry that quietly stops matching, the same rule as the facet registry
# (audit item 5, 9 October 2026). A value is the station's ordinary name: the
# National Rail name where it has one, and the label its operator uses where
# the entry is a rail-air bus link or a fares origin rather than a station.
#
# Some of these are the names a cold chooser shows first, because a compressed
# name is most visible on the busiest stations: the real 24-station build listed
# "LONDON ST PANCRS", "MANCHESTER PIC", "LIVERPOOL L ST", "BIRMINGHAM N ST",
# "BRISTOL TEMPLE M" and "NEWPORT S.WALES" above every name it got right.
# `python build_demo_page.py --feed feeds/fares --all-origins` writes the list
# those six came from.
REVIEWED_STATION_NAMES: dict[str, str] = {
    "AFK": "Ashford International",
    "APN": "Newcastle Airport",
    "BHI": "Birmingham International",
    "BHM": "Birmingham New Street",
    "BRI": "Bristol Temple Meads",
    "EFF": "Effingham Junction",
    "EXG": "Exhibition Centre (Glasgow)",
    "HPQ": "Harwich International",
    "IVA": "Inverness Airport",
    "KGX": "London Kings Cross",
    "LIV": "Liverpool Lime Street",
    "LJL": "Liverpool Airport Bus",
    "LNE": "London International (CIV)",
    "LPY": "Liverpool South Parkway",
    "MAN": "Manchester Piccadilly",
    "MCO": "Manchester Oxford Road",
    "MIA": "Manchester Airport",
    "NWP": "Newport (South Wales)",
    "PRA": "Prestwick International Airport",
    "QEO": "East Midlands Railway (origin)",
    "QGA": "Glasgow Airport Bus",
    "QNO": "Northern (origin)",
    "QSO": "South Western Railway (origin)",
    "QTO": "TransPennine Express (origin)",
    "QXO": "CrossCountry (origin)",
    "SFA": "Stratford International",
    "STP": "London St Pancras International",
    "WBQ": "Warrington Bank Quay",
    "ZHJ": "Heathrow Underground",
}


def display_station_name(crs: str, name: str) -> str:
    """The name a reader sees for a station, reviewed where the feed compresses it."""
    return REVIEWED_STATION_NAMES.get(crs.upper(), name)


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
    index = []
    slugs = station_slugs_for(all_locations)
    for crs, count in sorted(priced_by_origin.items(), key=lambda item: (-item[1], item[0])):
        location = all_locations[crs]
        # Priced is not enough: a zone boundary prices fares through it but no
        # train stops there, so it is absent rather than offered and then
        # refused (audit A6, same rule as the priced-nothing station).
        if count <= 0 or is_pseudo_station(crs):
            continue
        index.append(
            {
                "crs": crs,
                "name": display_station_name(crs, location.name),
                "slug": slugs[crs],
                "destinations": count,
            }
        )
    return index


def origin_control(payload: dict) -> str:
    """The origin in the heading: a control only when there is somewhere to go.

    A one-origin build has no other station's page to move to, and a
    "Change starting station" button that opens nothing is a control that lies: it was
    rendered, focusable, announced, and inert, and the browser suite failed on
    it for exactly that reason. So the control is written only when the build
    wrote another station's page, and the name stands as text when it did not.

    The control names itself "Change starting station" in front of the station
    rather than through aria-label, because an aria-label replaces the text the
    heading is read from: the heading's accessible name came out as "from
    Change starting station", which says what the control does and not which
    station the reader is at. The hidden text is the page's own .sr-only
    pattern, and it keeps the station visible in the name (WCAG 2.5.3).
    """

    name = html.escape(payload["origin"]["name"])
    if not picker_has_options(payload):
        # Plain text, not the shared slot: the slot's underline is the promise
        # that this part of the sentence can be changed, and on a build with
        # nowhere to go that promise would be a lie. The browser suite checks
        # this direction too -- it fails a page that renders a control which
        # opens nothing.
        return f'<span class="origin-name">{name}</span>'
    # The wrapper is the slot: it carries the underline and the heading's own
    # weight whether the reader is looking at the station's name or at the field
    # that replaces it, so clicking the name and typing into it are the same
    # gesture in the same place.
    return (
        '<span class="origin-slot-wrap">'
        '<button id="changeOrigin" class="origin-slot" type="button" aria-expanded="false"'
        ' aria-controls="originPicker">'
        '<span class="sr-only">Change starting station: </span>'
        f'<span>{name}</span>{CHEVRON}</button>'
        '</span>'
    )


NRE_LOGO = Path(__file__).resolve().parent / "assets" / "powered-by-national-rail.svg"
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
        f'<a href="{NRE_WEBSITE}" rel="external">'
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
    """

    return (
        '<p class="nre-source">Information from '
        f'<a href="{NRE_ENQUIRIES}" rel="external">National Rail Enquiries</a>. '
        f"{html.escape(NOTICES['nre'])} "
        "National Rail Enquiries does not endorse this site.</p>"
    )


# The first-use note for a build with nowhere to change to. It is a constant
# because the page ships it twice: as the text in the document, and as the
# sentence the script falls back to if the shared picker list did not arrive.
ONE_STATION_FIRST_USE = (
    "This is the only station this build has pages for, so the name above "
    "is not a link."
)


def first_use_sentence(payload: dict) -> str:
    """The first-use note, which can only name a control the page has.

    The one thing a first-time reader cannot guess is what the station slot in
    the heading does, so this sentence spends its first clause on it. It named
    a "Change" button until that button became the station's own name with a
    chevron beside it, at which point the sentence pointed at a word the page
    no longer showed; it names what is on the page instead -- the name in the
    heading, which is also the accessible name's own words, so the sentence and
    the control agree for a reader using either.

    On a one-origin build there is no such control -- the same condition
    ``origin_control`` writes for -- so the sentence points at nothing and
    keeps the half that is still true either way: everything below the heading
    narrows the destinations.
    """

    if not picker_has_options(payload):
        return ONE_STATION_FIRST_USE
    return "Click the <b>station name</b> to start from somewhere else."


# The payload's row lists, and the shape they ship in. Every row in a list
# carries the same field names, so sending them once per page instead of once per
# row costs nothing to read and a third of the payload to send: on the Grantham
# page the names were 67 KB of a 200 KB payload, and the station picker's three
# names were 11 KB of every 168 KB it added to every page (measured 30 September
# 2026 by tools/page_bytes.py).
ROW_LISTS = ("destinations", "singleDestinations", "anytimeDestinations", "stations")


POOL_MIN_BYTES = 12


def _pool_key(value: object) -> str:
    """A value's identity, so two equal railcard records share one entry."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _value_pool(tables: dict[str, list[dict]]) -> dict[str, int]:
    """The values that repeat inside the row lists, and their pool positions.

    Counting before choosing is what keeps this from being a hoist per field: a
    value earns an entry when it appears more than once and is long enough that a
    reference to it is cheaper than the value. On the Grantham page that is one
    link object on all 190 rows, one railcard record per rule rather than per row,
    and the arrays of destination types.

    The length floor is what stops a pool costing more than it saves: pooling
    false, which is five bytes, would spend five bytes on a reference to save five.
    """
    counts: dict[str, int] = {}
    for items in tables.values():
        for row in items:
            for value in row.values():
                if isinstance(value, (dict, list)) or (
                    isinstance(value, str) and len(value) >= POOL_MIN_BYTES
                ):
                    key = _pool_key(value)
                    counts[key] = counts.get(key, 0) + 1
    pool: dict[str, int] = {}
    for items in tables.values():
        for row in items:
            for value in row.values():
                key = _pool_key(value)
                if counts.get(key, 0) > 1 and key not in pool:
                    pool[key] = len(pool)
    return pool


def encode_payload(payload: dict) -> dict:
    """The payload in the form a page ships: a column list and a row table per list.

    Each row list keeps its own columns. The lists carry different fields, and one
    shared column set would pad the picker's three fields out to a destination
    row's twenty, which is a loss disguised as a saving.
    ``page_templates`` hydrates the tables back into objects as the page loads, so values that repeat
    inside a list are sent once in the page-level pool and referred to by index,
    and
    the rest of the script reads rows exactly as it did before the wire form
    changed.
    """
    tables = {
        key: payload[key]
        for key in ROW_LISTS
        if isinstance(payload.get(key), list) and payload[key]
    }
    if not tables:
        return payload

    pool = _value_pool(tables)
    values: list[object] = [None] * len(pool)
    for items in tables.values():
        for row in items:
            for value in row.values():
                position = pool.get(_pool_key(value))
                if position is not None:
                    values[position] = value

    encoded = dict(payload)
    for key, items in tables.items():
        columns: list[str] = []
        for row in items:
            for field in row:
                if field not in columns:
                    columns.append(field)

        def cell(value: object) -> object:
            # A pool reference is a negative index, so it cannot be confused with
            # a real cell: -1 is the pool's first entry, and null stays null.
            position = pool.get(_pool_key(value)) if value is not None else None
            return -(position + 1) if position is not None else value

        encoded[key] = {
            "columns": columns,
            "rows": [[cell(row.get(field)) for field in columns] for row in items],
        }
    if values:
        encoded["pool"] = values
    return encoded


def render_page(
    payload: dict,
    *,
    budget_pounds: int,
    analytics: str = "",
    nre_credit: bool = False,
) -> str:
    """Fill the template from the payload.

    ``analytics`` is whatever snippet the owner chose for counting referrers. It
    is injected as given, and empty by default, so the page is self-contained
    unless someone deliberately decides otherwise.

    ``payload["stationsSrc"]`` is the one deliberate exception to the one-file
    route (ADR-0033, re-scoped 30 September 2026): the picker's list is the
    site's largest repeated item, so a build may point the page at the shared
    asset while the page's own destination payload still travels inline.

    ``payload["scriptSrc"]`` is the second exception, and the larger one: the
    station route's script measured 149,377 bytes byte-identical across 24
    sampled pages, so it ships as one hashed asset beside the stylesheet (T1,
    ADR-0033 amended). The payload travels inline because it is the one part of
    the page that differs per origin.
    """
    prices = [row["adultPence"] for row in payload["destinations"]]
    prices += [row["adultPence"] for row in payload.get("singleDestinations", [])]
    prices += [row["adultPence"] for row in payload.get("anytimeDestinations", [])]
    ceiling = max(1, -(-max(prices or [100]) // 100)) if prices else 100
    # The picker's list is the one thing a page no longer carries once the
    # build serves it as the shared asset: sending both would be the hundreds
    # of MB across the network the asset exists to remove.
    embedded_payload = (
        {key: value for key, value in payload.items() if key != "stations"}
        if payload.get("stationsSrc")
        else payload
    )
    embedded = json.dumps(encode_payload(embedded_payload), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    initial_budget = max(1, min(int(budget_pounds), ceiling))
    # A facet chip is only offered when this page has a destination carrying
    # it. The taxonomy is shared, so a facet with no matches here is a filter
    # that can only ever return nothing, which reads as a broken control rather
    # than an empty result.
    used = {
        kind
        for row in payload["destinations"] + payload.get("singleDestinations", []) + payload.get("anytimeDestinations", [])
        for kind in row.get("destinationTypes") or [row.get("destinationType", "other")]
    }
    destination_filters = ['<label class="choice-chip"><input type="radio" name="destinationType" value="all" checked> <span>All</span></label>']
    # The count lives in the chip, not beside it, so the number and the thing
    # it counts are one target and one label. render() fills it in from the
    # page's own rows at the budget on screen.
    destination_filters.extend(
        f'<label class="choice-chip"><input type="checkbox" name="destinationType" value="{html.escape(value)}"> '
        f'<span>{html.escape(label)}</span> <span class="chipcount" data-count-for="{html.escape(value)}"></span></label>'
        for value, label in DESTINATION_TYPE_FILTERS
        if value in used
    )
    script_tag = station_script_tag(payload.get("scriptSrc", ""))
    page = (
        TEMPLATE.replace("__DATA__", embedded)
        .replace("__DESTINATION_TYPE_FILTERS__", "".join(destination_filters))
        .replace("__ORIGIN__", html.escape(payload["origin"]["name"]))
        .replace("__STATIONS_SRC__", station_asset_tag(payload.get("stationsSrc")))
        .replace("__ORIGIN_CONTROL__", origin_control(payload))
        .replace("__FIRST_USE__", first_use_sentence(payload))
        .replace("__FIRST_USE_FALLBACK__", json.dumps(ONE_STATION_FIRST_USE, ensure_ascii=False))
        .replace("__NRE_CREDIT__", nre_attribution() if nre_credit else "")
        .replace("__NRE_SOURCE__", nre_source_line() if nre_credit else "")
        .replace("__MAXPOUNDS__", str(ceiling))
        # S17: the control's stop is a build fact, so the page states it
        # before any script runs. The script keeps it true afterwards.
        .replace("__CEILING_NOTE__", "&pound;" + str(ceiling) + ".00 for one adult")
        .replace("__BUDGET__", str(initial_budget))
        .replace("__NOTE__", note_markup(payload["note"]))
        .replace("__BASE__", payload.get("baseHref", "/").rstrip("/"))
        .replace("__ANALYTICS__", analytics)
        .replace("__SYNTHETIC__", "true" if payload.get("synthetic", True) else "false")
        .replace("__SYNTHETIC_BANNER__", synthetic_markup(payload.get("synthetic", True)))
        .replace("__STATION_STYLE__", station_style_tag(payload.get("styleSrc", "")))
        .replace("__STATION_SCRIPT__", script_tag)
    )
    # A station page with no stylesheet link is a page with no styling and no
    # request for any, which reads as a broken page rather than a broken build.
    # with_shared() cannot catch this one: the link needs the path this release
    # is published at, which only the build knows (ADR-0033 inlined the block;
    # ADR-0047 fetches it). Both ways of getting here are refused -- an
    # unfilled placeholder, and a payload that never named the document.
    if "__STATION_STYLE__" in page or '<link rel="stylesheet"' not in page:
        raise ValueError("the station page shipped without a stylesheet link")
    # The same rule for the route's script, and it is the one that decides
    # whether a page carries 149 KB of code or a request for it. A page whose
    # payload names no script would render tables and wire nothing.
    if "__STATION_SCRIPT__" in page or not script_tag:
        raise ValueError("the station page shipped without its script")
    return page


def note_markup(note: str, css_class: str = "") -> str:
    """A route's provenance note as its own paragraph, or nothing at all.

    A real build passes ``""`` for the note, and the template used to ship an
    empty ``<p>`` wherever the note would have been -- a block of dead space
    saying nothing (audit item 8, 9 October 2026). ``synthetic_markup`` beside
    this is the same shape of fix for the same reason.
    """
    if not note:
        return ""
    return f'<p class="{css_class}">{note}</p>' if css_class else f"<p>{note}</p>"


def synthetic_markup(synthetic: bool) -> str:
    """The visible synthetic-data state for a route, or nothing for a real one.

    S45: the marker is markup rather than a sentence passed in, so a build
    cannot ship a page whose banner says something the rest of the page
    contradicts. A real build writes no banner and keeps ``data-synthetic="false"``,
    which is the state a screenshot fixture can assert in either direction.
    """
    if not synthetic:
        return ""
    return (
        '<p class="synthetic-banner" data-synthetic-banner>'
        f"<strong>{html.escape(SYNTHETIC_LABEL)}</strong> {html.escape(SYNTHETIC_BANNER)}</p>"
    )


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


def render_privacy(
    note: str,
    base_path: str = "",
    contact: str = "",
    features: dict | None = None,
    synthetic: bool = True,
    built_at: str | None = None,
) -> str:
    if not contact.strip():
        raise ValueError("a privacy contact is required before publishing the privacy page")
    features = features or {}
    # The three sentences a reader's decision depends on, written from what the
    # build ships. A behaviour that is on is named; one that is off is named as
    # off. Either way the page cannot claim a privacy practice the build does
    # not have.
    practices = [
        "No cookies are set by this site.",
        # C10: the page used to claim the budget and the selected types "never
        # leave your device" while also writing both into the address, and the
        # address is in every request the host logs. The honest statement is
        # that the state is client-side and is disclosed where it is sent: in
        # the URL, to the host's logs and to anyone a link is shared with. The
        # full explanation is its own section on the page; this is the list
        # entry, so it states the fact and points there rather than saying the
        # same paragraph twice.
        # One sentence, not the section it points at (audit item 17, 9 October
        # 2026): the paragraph and the two bullets below make the same point
        # with more room, and a list entry that repeats them is read first and
        # learned last. The word stays true because the summary now comes
        # before the deep dive: "What this site does" is the first section and
        # "What stays in the address bar" the one it points down to (route
        # audit item 18, 9 October 2026).
        (
            "Your search is kept in the page's web address, so the host "
            "serving these files sees it in its request logs; what stays in "
            "the address bar, below, explains it in full."
        ),
        (
            "This build injects an analytics snippet, so visits are measured by "
            "that snippet. The reviewed plan it is allowed under: it "
            + features.get("measurement", "has none recorded, which should not "
              "happen -- a build cannot inject a snippet without one (ADR-0032).")
            if features.get("analytics")
            else "No analytics run. If the operator later adds analytics, this page will name them here first."
        ),
        (
            "Ticket buttons carry a tracked link, so the seller is told which page sent "
            "the reader. The fare pages say so in their footer."
            if features.get("trackedLinks")
            else "The site code does not intentionally collect visit data."
        ),
    ]
    if features.get("affiliate"):
        practices.append(
            "Ticket buttons pass through the " + features["affiliate"] +
            " affiliate network, which may record the click and the fare shown."
        )
    # The date this notice's build-dependent sentences were true of: "no
    # analytics run" is a promise about a build, and the build knows when it
    # was made (route audit item 16, 9 October 2026).
    built_line = (
        '<p class="muted" id="builtLine">This notice describes the build published on '
        + html.escape(human_date(built_at[:10]))
        + ".</p>"
        if built_at
        else ""
    )
    return (
        PRIVACY.replace("__BASE__", base_path)
        .replace("__BUILT_LINE__", built_line)
        .replace("__NOTE__", note_markup(note, "muted"))
        .replace("__CONTACT__", contact)
        .replace("__PRACTICES__", "".join(f"  <li>{item}</li>\n" for item in practices))
        .replace("__SYNTHETIC__", "true" if synthetic else "false")
        .replace("__SYNTHETIC_BANNER__", synthetic_markup(synthetic))
    )




# The station picker is the first thing this project serves as one shared file
# rather than one copy per page, so the name lives in one place: the build
# writes it, the page names it, and the link crawl reads it (ADR-0033, re-scoped
# 30 September 2026 -- a page still carries its own destinations inline).
STATION_ASSET_NAME = "stations.js"


# The station route's stylesheet (ADR-0047). The page's own answer is in its
# own bytes; this is the part of a station page that is the same on every page
# of the route. The name holds a digest of the content, so a changed
# stylesheet is a new file rather than a changed one -- a cached copy
# can never be served beside a page built from another revision of the
# CSS, and no build step has to be told to rename anything.
STATION_STYLE_STEM = "station"


def station_style_asset_name() -> str:
    """The stylesheet's file name, from a digest of its own bytes."""
    digest = hashlib.sha256(STATION_STYLESHEET.encode("utf-8")).hexdigest()[:12]
    return f"{STATION_STYLE_STEM}-{digest}.css"


def write_station_style(out_dir: Path) -> Path:
    """The one stylesheet every station page fetches, written once."""
    path = out_dir / station_style_asset_name()
    write_page_atomic(path, STATION_STYLESHEET)
    print(
        f"wrote {path} ({len(STATION_STYLESHEET.encode('utf-8')):,} bytes) "
        "for every station page's styling",
        flush=True,
    )
    return path


def station_style_tag(src: str) -> str:
    """The one request a station page makes beyond itself.

    A render-blocking <link> rather than a script that injects a style element:
    the page is styled before it is painted, so there is no flash of plain text,
    and a reader with no JavaScript still gets the layout and the dark palette.
    Unlike the picker's tag this one is written for every station page, because
    this document is not optional -- and a page whose copy does not arrive is
    the case ADR-0047 has an answer for.
    """
    if not src:
        return ""
    return f'<link rel="stylesheet" href="{html.escape(src, quote=True)}">' + "\n"


# Both routes' scripts are shared documents beside the stylesheet, for the
# reason ADR-0047 gave the stylesheet: the station route's script measured
# 149,377 bytes byte-identical on every one of 24 sampled pages, so the page's
# own answer is in its own bytes and the code that reads them is one file the
# browser keeps (T1). The chooser's is the same treatment at one copy (T10).
# The stems are the same one the stylesheet uses, so a route's assets are
# grouped by that name in the output folder.
STATION_SCRIPT_STEM = "station"
CHOOSER_STEM = "chooser"


def station_script_asset_name() -> str:
    """The station script's file name, from a digest of its own bytes."""
    digest = hashlib.sha256(STATION_SCRIPT.encode("utf-8")).hexdigest()[:12]
    return f"{STATION_SCRIPT_STEM}-{digest}.js"


def chooser_script_asset_name() -> str:
    """The chooser script's file name, from a digest of its own bytes."""
    digest = hashlib.sha256(CHOOSER_SCRIPT.encode("utf-8")).hexdigest()[:12]
    return f"{CHOOSER_STEM}-{digest}.js"


def write_station_script(out_dir: Path) -> Path:
    """The one script every station page fetches, written once."""
    path = out_dir / station_script_asset_name()
    write_page_atomic(path, STATION_SCRIPT)
    print(
        f"wrote {path} ({len(STATION_SCRIPT.encode('utf-8')):,} bytes) "
        "once for every station page rather than inside every one",
        flush=True,
    )
    return path


def write_chooser_script(out_dir: Path) -> Path:
    """The one script the chooser fetches, written once."""
    path = out_dir / chooser_script_asset_name()
    write_page_atomic(path, CHOOSER_SCRIPT)
    print(
        f"wrote {path} ({len(CHOOSER_SCRIPT.encode('utf-8')):,} bytes) "
        "once for the chooser rather than inside it",
        flush=True,
    )
    return path


def station_script_tag(src: str) -> str:
    """The station route's code, as the one request it makes for it.

    Deferred rather than a plain tag at the foot of the body: the page's answer
    is already in its own bytes, so the reader sees the table while the script
    is still on the wire, and a page whose copy never arrives is a page with no
    wiring rather than a blank one. ADR-0047 dated the stylesheet for the same
    reason.

    The onerror reveals the page's own missing-script note rather than leaving
    an empty table unexplained: the script is what is missing, so it cannot be
    the thing that says so.
    """
    if not src:
        return ""
    return (
        f'<script src="{html.escape(src, quote=True)}" defer '
        "onerror=\"document.getElementById('scriptNote').hidden=false\"></script>\n"
    )


def chooser_script_tag(src: str) -> str:
    """The chooser's code, as the one request it makes for it."""
    if not src:
        return ""
    return (
        f'<script src="{html.escape(src, quote=True)}" defer '
        "onerror=\"document.getElementById('scriptNote').hidden=false\"></script>\n"
    )


def picker_has_options(payload: dict) -> bool:
    """Whether this page was built with another station's page to move to.

    Two ways to answer yes, because the list arrives two ways: inline in the
    payload for a build that ships one file per route, and as the shared asset
    (``stationsSrc``) for the network build that cannot afford 2,712 copies of
    it. The heading control and the first-use note both ask this question rather
    than reading the list, so a page cannot render a control while shipping no
    options, or ship options with no way to open them.
    """
    return bool(payload.get("stations") or payload.get("stationsSrc"))


def station_asset_rows(index: list[dict], base_path: str = "") -> list[dict]:
    """The picker's options for the whole site, not for one page.

    Every station this build wrote a page for, **including** the page's own:
    each page filters its own origin out as it loads (ADR-0019 offers the
    others), and keeping the file identical for every page is the only reason a
    reader pays one request instead of 2,712 copies. Built from the same route
    manifest the chooser and the link crawl read, so an option can only name a
    page this build wrote (S01).
    """
    return [
        {
            "name": entry["name"],
            "crs": entry["crs"],
            "href": with_base(base_path, f"/from/{entry['slug']}/"),
        }
        for entry in index
    ]


def render_station_asset(rows: list[dict]) -> str:
    """The one shared file the picker reads: a station list, loaded by every page.

    Plain objects rather than the column-and-cell encoding a page payload uses.
    A table would save about a third of the bytes, but the list is sent once
    rather than once per page, so the saving is tens of KB on the whole network;
    and the objects keep ``"href": "/from/..."`` in the file, which is the shape
    the route crawl reads to prove every picker option resolves (S03).
    """
    header = (
        "// The station picker's options, one file for the whole site. Every page\n"
        "// filters its own origin out as it loads (ADR-0019), and a page whose copy\n"
        "// of this file did not arrive states the station as text rather than\n"
        "// offering a control that opens nothing.\n"
    )
    return header + "window.TBE_STATIONS = " + json.dumps(
        rows, ensure_ascii=False, separators=(",", ":")
    ) + ";\n"


def station_asset_tag(src: str | None) -> str:
    """The one request a page needs beyond itself, or nothing at all.

    Written only for a build that set ``stationsSrc``, so a single-origin site
    and every direct caller of ``render_page`` still ship one file per route with
    no second request. Without this tag the page's picker reads its list out of
    the page's own payload, exactly as before the list moved.
    """
    if not src:
        return ""
    return f'<script src="{html.escape(src, quote=True)}"></script>\n'


def published_routes_for(index: list[dict], base_path: str = "") -> list[dict]:
    """The route manifest: one entry per station page this release writes.

    The chooser's options, each station page's picker and the link crawl all
    read this same list, so a link can only ever name a page the build wrote
    (S01). ``index`` is the priced station index; an empty index means a build
    that prices nothing, whose chooser says so instead of offering a station
    that has no page.
    """
    return [
        {
            "name": e["name"],
            "crs": e["crs"],
            "slug": e["slug"],
            "destinations": e["destinations"],
            "href": with_base(base_path, f"/from/{e['slug']}/"),
        }
        for e in index
    ]


def render_chooser(
    index: list[dict],
    *,
    budget_pounds: int,
    analytics: str = "",
    base_path: str = "",
    note: str = DEFAULT_NOTE,
    synthetic: bool = True,
    price_source: str = DEFAULT_PRICE_SOURCE,
    feed_date: str | None = None,
) -> str:
    """The root page: the station chooser itself, with no fares on it.

    ``index`` is the priced station index -- the root offers exactly the
    stations whose pages this build wrote, and nothing else, so a root that
    names a station always has a page behind it (S01).

    A release that priced exactly one station is not a chooser: there is no
    choice to make, and the published artefact used to ask the reader to type
    a station that could only ever be the one it already knew. So it states
    the choice in its shape as well as its sentence -- the heading names that
    station, the field and the ordering note are absent, and the one row is
    the page to open (audit recommendation 2, 30 September 2026).

    ``note`` is the same provenance note the station pages carry, so a real-feed
    site does not have a chooser claiming synthetic data above pages that name
    the real feed.

    ``price_source`` and ``feed_date`` are the station page's own provenance:
    the entry route is the one every community link points at, and it used to
    say what the ordering was while saying nothing about what the site was,
    whose feed its prices came from, or how old that feed was
    (four-dimension audit R3, route audit item 6).
    """
    provenance_parts = [f"Prices from {price_source}"]
    if feed_date:
        provenance_parts.append(f"downloaded {human_date(feed_date)}")
    provenance = " ".join(provenance_parts) + "."
    stations = json.dumps(
        [
            {"name": e["name"], "crs": e["crs"], "href": with_base(base_path, f"/from/{e['slug']}/"), "destinations": e["destinations"]}
            for e in index
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    if len(index) == 1:
        only = index[0]
        origin_clause = (
            '<span id="originClause"><span class="heading-lead">from</span> '
            '<span class="origin-name">'
            f'{html.escape(only["name"])}</span></span>'
        )
        intro = (
            '<p class="sub">This site was built for one station: open it below for '
            "every destination your budget reaches from there.</p>"
        )
        # Nothing is ordered, so the page makes no ranking claim: an ordering
        # note over one row describes a choice the reader does not have.
        ordering = ""
        title_suffix = only["name"]
    else:
        origin_clause = (
            '<span id="originClause"><span class="heading-lead">from</span> '
            '<span class="origin-slot-wrap" id="originField">'
            '<input id="originSearch" type="search" placeholder="station" autocomplete="off" '
            'aria-label="The station you are starting from" aria-describedby="pickStatus" '
            'aria-controls="picks"></span></span>'
        )
        intro = (
            '<p class="sub">Type the station you are leaving from, then pick it '
            "from the list.</p>"
        )
        ordering = (
            '<p class="sub" id="orderingNote">Ordered by how many destinations this '
            "download prices from each station &mdash; not by how busy it is, and not by "
            "how near it is.</p>"
        )
        title_suffix = "pick your station"
    return (
        CHOOSER_TEMPLATE.replace("__STATIONS__", stations)
        .replace("__ORIGIN_CLAUSE__", origin_clause)
        .replace("__CHOOSER_INTRO__", intro)
        .replace("__PROVENANCE__", html.escape(provenance))
        .replace("__ORDERING_NOTE__", ordering)
        .replace("__TITLE_SUFFIX_HTML__", html.escape(title_suffix))
        .replace("__TITLE_SUFFIX_JS__", json.dumps(title_suffix, ensure_ascii=False))
        .replace("__BUDGET__", str(budget_pounds))
        .replace("__NOTE__", note_markup(note, "tag"))
        .replace("__BASE__", base_path.rstrip("/"))
        .replace("__CHOOSER_SCRIPT__", chooser_script_tag(with_base(base_path, "/" + chooser_script_asset_name())))
        .replace("__ANALYTICS__", analytics)
        .replace("__SYNTHETIC__", "true" if synthetic else "false")
        .replace("__SYNTHETIC_BANNER__", synthetic_markup(synthetic))
    )


@dataclass
class BuildContext:
    """Everything one build resolved before it wrote a page.

    ``main`` used to hold all of this in locals, which is why it was 1,001
    lines: a reader could not see which values the two build shapes shared and
    which belonged to only one of them, and the shared prologue had to be read
    twice. A build is now a sequence of named phases, and this is what they
    pass between them (four-dimension audit R9). Each field is written by the
    phase named in its comment and read by everything after it.
    """

    args: argparse.Namespace
    day: date | None
    # -- after load_inputs (fares, timetable) ----------------------------
    fares: FaresDb = None  # type: ignore[assignment]
    fare_note: str = ""
    timetable: "TimetableDb | None" = None
    worker_timetable: str | None = None
    timetable_index: "SliceIndex | None" = None
    cache_path: Path | None = None
    planned: list[str] = field(default_factory=list)
    # -- after read_provenance ------------------------------------------
    price_source: str = DEFAULT_PRICE_SOURCE
    feed_date: str | None = None
    note: str = DEFAULT_NOTE
    base_path: str = ""
    metadata_folders: list[Path] = field(default_factory=list)
    reference: "Knowledgebase | None" = None
    reference_published: str = ""
    reference_checked: str = ""
    single_timetable: "TimetableDb | None" = None
    # -- after price_one_payload ---------------------------------------
    payload_origin: str = ""
    sampled_index: "SliceIndex | None" = None
    payload: dict = field(default_factory=dict)
    # -- after release_gates --------------------------------------------
    analytics: str = ""
    features: dict = field(default_factory=dict)
    synthetic: bool = True
    privacy_contact: str = ""
    out: Path = field(default_factory=lambda: Path("_site/index.html"))

    def release_feeds(self) -> None:
        """Drop the parent's names for the fares and the timetables.

        A render that fans out no longer reads these, but a context outlives
        every phase, so a field left holding a 2.1 GB feed keeps it resident
        beside the workers that are meant to hold the memory instead. The
        callers still `del` their own aliases; this clears the other name.
        """
        self.fares = None
        self.timetable = None
        self.single_timetable = None


def load_inputs(ctx: BuildContext) -> int:
    """Load the feeds, and refuse on what cannot be published with them.

    Returns 0 to continue, or the exit code to stop at. The fares and timetable
    loading, the classification and reviewed-code gates, and the provenance read
    are all here because they are all refusals that must happen before any page
    is written.
    """
    args = ctx.args
    print(f"Loading fares feed from {args.feed} ...", flush=True)
    if args.all_origins:
        # A whole-network build needs every origin's flows at once, so there is
        # no single slice to restore; it writes the indexes the workers read
        # below, once the station list is known.
        ctx.fares = FaresDb().load_feed(args.feed)
        ctx.fare_note = ""
    else:
        page_fares = load_page_fares(args.feed, args.origin)
        ctx.fares = page_fares.fares
        ctx.fare_note = (
            f" (restored from {page_fares.index.name})"
            if page_fares.restored
            else f" (parsed; wrote {page_fares.index.name})"
        )
    print(
        f"Loaded fares: {ctx.fares.stats()['flows']:,} flows, "
        f"{ctx.fares.stats()['fares']:,} fares{ctx.fare_note}",
        flush=True,
    )
    if not args.all_origins:
        # Every revision of the feed writes a new pair of cache names, and the
        # old pair can never be read again, so the digests before this build's
        # own are tidied here rather than left for the next one to overwrite.
        stale_fares = prune_fare_index_caches(page_fares.common, page_fares.index.parent)
        if stale_fares:
            print(f"Removed {stale_fares} file(s) from the fares caches of older feeds.", flush=True)
    return 0


def _load_timetable(ctx: BuildContext) -> int:
    """Open the timetable this build prices against: a feed, an index, or none.

    A whole-network build reads no timetable feed at all when the slice index
    holds every page's own reach, which is what makes the whole-network build
    affordable (ADR-0022, docs/build-performance-findings.md). The three
    outcomes are printed, because on the real feed they are 56.7s and a restore
    is 2.6s, and an operator reading a build log needs to know which they paid.
    """
    args = ctx.args
    if args.timetable_index is not None:
        ctx.timetable_index = open_timetable_index(args.timetable_index, args.timetable)
        if ctx.timetable_index is None:
            print(
                f"no usable timetable index under {args.timetable_index}; "
                "tools/build_timetable_index.py writes one",
                file=sys.stderr,
            )
            return 2
        print(f"Timetable index: {ctx.timetable_index.describe()}", flush=True)
    # The codes a named station subset build writes, known before anything is
    # priced: an index that holds all of them means the timetable feed is not
    # read at all. Empty means this build is not a named subset.
    ctx.planned = [
        code.strip().upper()
        for code in (args.only_stations or "").split(",")
        if code.strip()
    ]
    # What the pool workers are handed to parse. A build that skipped the feed
    # has no timetable to give them: passing the path would have every worker
    # parse the national index the parent has just decided not to read.
    ctx.worker_timetable = args.timetable
    ctx.cache_path = None
    if args.timetable:
        # Every station the page can show, not only the ones a return reaches.
        # It was the returns alone, and the outbound-single list reaches
        # thirteen more on a real page -- Bolton, Blackpool North, Chorley,
        # Edge Hill among them -- whose services were therefore never in the
        # index at all. Each of them was a row reading "No service" and
        # "Unknown", which is not a fact about those stations. It is a fact
        # about which stations this build asked the timetable about.
        # The three lists the page composes are the three the index must cover.
        focus_destinations: set[str] = set()
        if not args.all_origins and args.origin in ctx.fares.locations_by_crs:
            for rows in (
                ctx.fares.page_destinations_within(
                    args.origin, EVERYTHING_PENCE, adults=1, day=ctx.day
                ),
                ctx.fares.page_single_destinations_within(
                    args.origin, EVERYTHING_PENCE, adults=1, day=ctx.day
                ),
                ctx.fares.publishable_destinations_within(
                    args.origin, EVERYTHING_PENCE, adults=1, day=ctx.day
                ),
            ):
                focus_destinations.update(row.crs for row in rows)
        ctx.cache_path = (
            timetable_cache_path(args.timetable, args.origin, focus_destinations)
            if not args.all_origins
            else None
        )
        # Whether the cache was there before this build asked for it, which is
        # what distinguishes a restore from a parse that also happened to write.
        cache_was_there = ctx.cache_path is not None and ctx.cache_path.is_file()
        # A named station subset whose slices are all in the index needs no feed
        # at all, and every code is known before anything is priced, so the 56.7s
        # and 1.87 GB can be skipped rather than paid and then ignored. Not with
        # `--with-single-timetable`: that focus is a second cut of the feed, and
        # this index holds each page's own reach rather than it.
        if (
            ctx.timetable_index is not None
            and ctx.planned
            and not args.with_single_timetable
            and ctx.timetable_index.covers(ctx.planned)
        ):
            print(
                f"The index holds all {len(ctx.planned)} station(s) this build will write; "
                "the timetable feed is not read.",
                flush=True,
            )
            ctx.timetable = None
            ctx.worker_timetable = None
        else:
            print(f"Loading timetable feed from {args.timetable} ...", flush=True)
            ctx.timetable = TimetableDb().load_feed(
                args.timetable,
                focus_origin=None if args.all_origins else args.origin,
                focus_destinations=focus_destinations,
                cache_path=ctx.cache_path,
            )
            # The cache note says which of the two happened, because on the real
            # feed they are 2.6s and 55.6s and an operator reading a build log is
            # exactly the person who needs to know which one they paid.
            print(
                f"Loaded timetable: {ctx.timetable.stats()['schedules']:,} schedules, "
                f"{ctx.timetable.stats()['calling_points']:,} calling points"
                + (
                    ""
                    if ctx.cache_path is None
                    else f" (restored from {ctx.cache_path.name})"
                    if cache_was_there
                    else f" (parsed; wrote {ctx.cache_path.name})"
                ),
                flush=True,
            )
    elif ctx.timetable_index is not None:
        # The point of the index: no feed on the machine, and no national index
        # in memory. Each page reads its own slice from disk instead.
        print("No timetable feed: every page is built from its slice in the index.", flush=True)
        ctx.timetable = None
    else:
        print("No timetable supplied; building a prices-only page.", flush=True)
        ctx.timetable = None
    return 0


def read_provenance(ctx: BuildContext) -> int:
    """Refuse a build whose prices cannot say where they came from.

    The metadata, the download manifest, the restriction gate, the classification
    failures and the reviewed-code staleness are all refusals or provenance notes
    that must be resolved before a page exists, so they are one phase: a reader
    who is shown a price is shown a build whose provenance was settled.
    """
    args = ctx.args
    fares = ctx.fares
    # A public price needs the reviewed selector, and the selector needs the
    # .RST restriction file to have parsed cleanly. Refuse before rendering
    # rather than shipping a page whose prices came from the broad query.
    gate_problem = fares.restrictions.gate_problem()
    if gate_problem:
        print(
            f"error: refusing to build a public price page: {gate_problem}. "
            "Download the fares feed with its .RST file, or use the broad query "
            "for analysis only.",
            file=sys.stderr,
        )
        return 2
    # A classification source that could not be read leaves the page with
    # fewer filter chips and a fallback-only source label. Say which source
    # failed alongside the rest of the provenance lines, and let the flag
    # refuse before anything is written (audit A5).
    for failure in fares.report.classification_failures:
        print(f"classification: {failure}")
    if args.require_classification and fares.report.classification_failures:
        print(
            f"error: refusing to publish: {len(fares.report.classification_failures)} "
            "classification source(s) could not be read: "
            + "; ".join(fares.report.classification_failures)
            + ". Restore the source, or drop --require-classification to "
            "publish on the reviewed fallbacks.",
            file=sys.stderr,
        )
        return 2
    # A reviewed fallback code the feed does not carry is a list quietly going
    # stale, and it is silent by construction: the code is intersected away
    # before it is applied, so a page looks exactly as it did. The names are
    # printed either way, and the flag is what turns them into a refusal.
    stale_codes = fares.report.reviewed_codes_absent
    if stale_codes:
        print(
            f"reviewed codes: {len(stale_codes)} match no station in this feed: "
            + ", ".join(stale_codes[:12])
            + (" ..." if len(stale_codes) > 12 else "")
        )
    # The other way the same list goes stale: the code resolves, so nothing
    # looks wrong, but the workbook already names the station, so the entry is
    # a fallback for a station nothing was missing.
    redundant_codes = fares.report.reviewed_codes_redundant
    if redundant_codes:
        print(
            f"reviewed codes: {len(redundant_codes)} name a station the ONS "
            "workbook already classifies, so the entry applies to nothing: "
            + ", ".join(redundant_codes[:12])
            + (" ..." if len(redundant_codes) > 12 else "")
        )
    if args.require_live_reviewed_codes and (stale_codes or redundant_codes):
        # Both lists are truncated the way the notes above truncate them. A
        # synthetic feed is missing most of the network, so the full list runs
        # to hundreds of codes and the tail of it is the part a reader cannot
        # act on anyway; the count beside it is the number to correct.
        def _named(codes: list[str]) -> str:
            if not codes:
                return "none"
            shown = ", ".join(codes[:12]) + (" ..." if len(codes) > 12 else "")
            return shown

        print(
            "error: refusing to publish: "
            f"{len(stale_codes)} reviewed settlement fallback code(s) name no "
            f"station in this feed ({_named(stale_codes)}) and "
            f"{len(redundant_codes)} name a station the workbook already "
            f"classifies ({_named(redundant_codes)}). A reviewed "
            "fallback covers a station no source could name: a code that names "
            "nothing means a station was renamed, merged or withdrawn, and one "
            "the workbook already names has nothing left to cover. Correct or "
            "drop them in atoc_fares.",
            file=sys.stderr,
        )
        return 2

    # Where the prices came from is read from the feed's metadata.json, not
    # retyped per build; --price-source overrides it. A synthetic build with
    # no metadata keeps the honest synthetic default.
    metadata_folders = [Path(args.feed)]
    if args.timetable:
        metadata_folders.append(Path(args.timetable))
    if args.feed_metadata:
        metadata_folders.append(Path(args.feed_metadata))
    ctx.metadata_folders = metadata_folders
    metadata = read_feed_metadata(metadata_folders)
    ctx.price_source = args.price_source or price_source_from_metadata(metadata or {})
    ctx.feed_date = feed_date_from(metadata)
    if not ctx.price_source and metadata is None:
        # No metadata file at all: the downloader's own manifest is the next
        # honest source. It only runs when metadata is genuinely absent -- when
        # a metadata.json exists but is unfinished, the loud refusal below
        # stands, because the operator clearly meant to write one.
        manifest = read_feed_manifest(metadata_folders)
        if manifest is not None:
            ctx.price_source = price_source_from_manifest(manifest)
            if not ctx.price_source:
                print(
                    f"error: a download manifest was found beside "
                    f"{metadata_folders[0]} but names no usable DTD fares or "
                    "timetable download; the page would claim synthetic demo "
                    "data for a feed whose provenance cannot be established. "
                    "Fix the manifest or pass --price-source explicitly.",
                    file=sys.stderr,
                )
                return 2
            print(f"price line read from the download manifest: {ctx.price_source}")
        ctx.feed_date = feed_date_from(metadata, manifest)
    ctx.base_path = "/" + args.base_path.strip("/") if args.base_path.strip("/") else ""
    if not ctx.price_source:
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
        if is_dtd_download(args.feed):
            # A real DTD download with no metadata and no manifest: the build
            # cannot say where the prices came from, and calling them synthetic
            # would be a false claim about real fares. Refuse rather than guess.
            print(
                f"error: {args.feed} is a DTD download, but no metadata.json or "
                "download manifest beside it names its source, so the page would "
                "claim synthetic demo prices for real fares. Write a metadata.json, "
                "or pass --price-source explicitly.",
                file=sys.stderr,
            )
            return 2
        print(
            "warning: no metadata.json or download manifest found; the price "
            "line falls back to the synthetic default, which is only true of a "
            "synthetic feed",
            file=sys.stderr,
        )
        ctx.price_source = DEFAULT_PRICE_SOURCE
    # The footer note follows the provenance: the synthetic note is the
    # default only for a build whose prices say they are synthetic. A real
    # feed -- metadata.json or the downloader's manifest -- must never wear
    # it, so its footer note is empty unless --note writes one.
    if args.note is not None:
        ctx.note = args.note
    else:
        ctx.note = DEFAULT_NOTE if ctx.price_source == DEFAULT_PRICE_SOURCE else ""

    # The reference feed, read once for the whole run. What is *asked* of it is
    # decided per page, because the claim is about the conditions that page
    # shows: one parse for the build, one answer from each page's own rows.
    manifest_for_reference = read_feed_manifest(metadata_folders) or {}
    ctx.reference = reference_feed(args.knowledgebase)
    ctx.reference_published, ctx.reference_checked = knowledgebase_dates(manifest_for_reference)
    if args.knowledgebase and args.all_origins:
        # A single-origin build prints the answer itself, below, once the page's
        # own rows have decided the question. A multi-origin release answers it
        # per station, so one line here would have to be a claim about pages
        # this one is not -- which is the claim the per-page answer exists to
        # stop making.
        print(
            "restriction reference: checked on every station page, against the "
            "conditions that page shows",
            flush=True,
        )

    if args.with_single_timetable:
        if not args.timetable:
            print(
                "--with-single-timetable requires --timetable: the index holds each "
                "page's own reach, not the outbound-single focus",
                file=sys.stderr,
            )
            return 2
        single_focus = {
            row.crs
            for row in fares.page_single_destinations_within(
                args.origin, EVERYTHING_PENCE, adults=1, day=ctx.day
            )
        }
        single_cache = timetable_cache_path(args.timetable, args.origin, single_focus)
        print("Loading separate outbound-single timetable cache ...", flush=True)
        ctx.single_timetable = TimetableDb().load_feed(
            args.timetable,
            focus_origin=args.origin,
            focus_destinations=single_focus,
            cache_path=single_cache,
        )
        print(
            f"Loaded single timetable: {ctx.single_timetable.stats()['schedules']:,} schedules, "
            f"{ctx.single_timetable.stats()['calling_points']:,} calling points "
            f"(cache: {single_cache.name})",
            flush=True,
        )
    used_caches = [path for path in (ctx.cache_path, single_cache if args.with_single_timetable else None) if path is not None]
    if used_caches:
        pruned = prune_timetable_caches(*used_caches)
        if pruned:
            print(f"pruned {pruned} stale timetable cache file(s) from {CACHE_DIR}", flush=True)
    return 0


def price_one_payload(ctx: BuildContext) -> int:
    """Price one page before the build decides what it can publish.

    The tripwire fires here, on the first origin, where it is cheap to learn
    that the full build would take days (ADR-0024). Every build pays for one
    origin before it writes any page: a whole-network build does not publish
    this payload, but a single-origin build is it.
    """
    args = ctx.args
    fares = ctx.fares
    # An all-origins build cannot depend on the single-origin default (GRN is
    # synthetic and absent from the real feed). Sample the requested code when
    # it exists, otherwise the first real station, so the per-origin tripwire
    # still fires before a long full-network batch.
    ctx.payload_origin = args.origin
    if args.all_origins and ctx.payload_origin not in fares.locations_by_crs:
        ctx.payload_origin = sorted(fares.locations_by_crs)[0]
    # A single-origin build writes this payload, so it is a page like any other
    # and its slice has to be here too, or the page would be assembled without
    # times and say the station has no services.
    ctx.sampled_index = ctx.timetable_index
    if (
        ctx.timetable is None
        and ctx.timetable_index is not None
        and not ctx.timetable_index.has(ctx.payload_origin)
    ):
        if not args.all_origins:
            print(missing_slice_message(ctx.timetable_index, [ctx.payload_origin]), file=sys.stderr)
            return 2
        # An all-origins build does not write this payload: it is the first
        # origin built, to prove one can be and to time it before a long batch.
        # Refusing here instead would refuse the request the index is for -- an
        # index of exactly the pages this build writes, whose sample origin is a
        # station nobody asked to build (GRN is Grindleford in the real feed).
        # What is lost is said rather than assumed: with no timetable the sample
        # measures the fares half of a page, and every page the build does write
        # is checked against the index before the pool starts.
        print(
            f"the index holds no slice for {ctx.payload_origin}, the origin this build "
            "samples first; the sample is built from the fares feed alone, so "
            "--max-origin-seconds measures the fares half of a page here rather than "
            "a whole one. Every page this build writes is checked against the index "
            "before the pool starts",
            flush=True,
        )
        # Not a page, so no slice is owed for it and the index is not handed
        # over: `build_payload` raises on an index that cannot answer, and this
        # is the one payload that is legitimately built without a timetable.
        ctx.sampled_index = None
    started = time.perf_counter()
    try:
        ctx.payload = build_payload(
            fares,
            ctx.timetable,
            ctx.payload_origin,
            single_timetable=ctx.single_timetable,
            max_changes=args.max_changes,
            day=ctx.day,
            note=ctx.note,
            attribution=notices_or_attribution(args),
            price_source=ctx.price_source,
            feed_date=ctx.feed_date,
            base_path=ctx.base_path,
            provider=args.provider,
            mode=args.link_mode,
            adults=args.adults,
            network=args.affiliate_network,
            advertiser_id=args.advertiser_id,
            publisher_id=args.publisher_id,
            departure_limit=args.departures,
            built_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            reference=ctx.reference,
            reference_published=ctx.reference_published,
            reference_checked=ctx.reference_checked,
            timetable_index=ctx.sampled_index,
        )
    except (KeyError, IndexError):
        print(f"origin {args.origin!r} not found in feed. Files read: {fares.files_read}", file=sys.stderr)
        return 2
    if ctx.reference is not None and not args.all_origins:
        # Printed from the page's own note rather than from a second check, so
        # the line an operator reads and the sentence a reader reads are the
        # same answer about the same conditions.
        print("restriction reference: " + describe_restriction_note(ctx.payload["restrictionReference"]), flush=True)
    origin_seconds = time.perf_counter() - started
    if args.max_origin_seconds and origin_seconds > args.max_origin_seconds:
        # The tripwire fires on the FIRST origin, where it is cheap to learn
        # that the full build would take days (ADR-0024).
        print(
            f"stopping: building one origin ({ctx.payload['origin']['name']}) took "
            f"{origin_seconds:.0f}s, over the {args.max_origin_seconds:.0f}s tripwire "
            "(--max-origin-seconds). At this per-origin cost the full-network build "
            "would run for days; see ADR-0024 before raising the limit.",
            file=sys.stderr,
        )
        return 3
    return 0


def release_gates(ctx: BuildContext) -> int:
    """What this build ships, described once, and the conditions to publish it.

    S36, S37: what this build ships, described once, and the conditions a
    release has to meet before it can be published. A synthetic demo site is
    exempt from the licence notice because it publishes no real fares; every
    other condition applies to both, because a reader reads both.
    """
    args = ctx.args
    ctx.analytics = ""
    if args.analytics_snippet:
        try:
            ctx.analytics = Path(args.analytics_snippet).read_text(encoding="utf-8")
        except OSError as error:
            print(f"could not read {args.analytics_snippet!r}: {error}", file=sys.stderr)
            return 2
    if ctx.analytics and not args.measurement_plan:
        print(
            "error: an analytics snippet was given without --measurement-plan, so the "
            "build would ship measurement nobody has decided what it measures or how "
            "long it is kept. Choose one of: " + ", ".join(sorted(MEASUREMENT_PLANS)) +
            " (ADR-0032), or drop --analytics-snippet to publish without measurement.",
            file=sys.stderr,
        )
        return 2
    # The affiliate facts come from the same pair of flags retailer.ticket_link
    # needs before it wraps a link, so the notice cannot say a link is tracked
    # when the build would not wrap it, or the reverse (S36).
    affiliate = args.affiliate_network if (args.affiliate_network and args.advertiser_id) else None
    ctx.features = site_features(
        analytics=bool(ctx.analytics),
        link_mode=args.link_mode,
        network=affiliate,
        disclosure=DISCLOSURE if affiliate else None,
        measurement=args.measurement_plan,
    )
    ctx.synthetic = ctx.price_source == DEFAULT_PRICE_SOURCE
    ctx.privacy_contact = args.privacy_contact or os.environ.get("PRIVACY_CONTACT", "")
    if not ctx.privacy_contact:
        # Same route for a synthetic demo and a real-feed build: the public
        # issue tracker, so the page is never blank and never prints an address.
        ctx.privacy_contact = DEFAULT_PRIVACY_CONTACT
    problems = release_gate_problems(
        ctx.features,
        public=not ctx.synthetic,
        notices=notices_or_attribution(args),
        contact=ctx.privacy_contact,
    )
    if problems:
        print(
            "error: this build cannot be published as configured:\n"
            + "".join(f"  - {problem}\n" for problem in problems),
            file=sys.stderr,
        )
        return 2
    ctx.out = Path(args.out)
    return 0


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


def _build_all_origins(ctx: BuildContext) -> int:
    """Write a station page for every origin this feed prices.

    One build, one site: the chooser, the shared station list and the release
    manifest are written once beside the pages, and the pages are built either
    in this process or across a pool that is handed one origin each. The phases
    before this one are the same ones a single-origin build runs.
    """
    args = ctx.args
    day = ctx.day
    fares = ctx.fares
    fare_note = ctx.fare_note
    timetable = ctx.timetable
    worker_timetable = ctx.worker_timetable
    timetable_index = ctx.timetable_index
    cache_path = ctx.cache_path
    planned = ctx.planned
    price_source = ctx.price_source
    feed_date = ctx.feed_date
    note = ctx.note
    base_path = ctx.base_path
    metadata_folders = ctx.metadata_folders
    reference = ctx.reference
    reference_published = ctx.reference_published
    reference_checked = ctx.reference_checked
    single_timetable = ctx.single_timetable
    payload_origin = ctx.payload_origin
    sampled_index = ctx.sampled_index
    payload = ctx.payload
    analytics = ctx.analytics
    features = ctx.features
    synthetic = ctx.synthetic
    privacy_contact = ctx.privacy_contact
    out = ctx.out
    out_dir = out.parent
    # Zone and coach pseudo-stations are priceable in the feed but are not
    # places a reader departs from, so they leave here -- with the chooser,
    # the write set and the coverage report's origin list all following
    # (audit A6).
    origins = [
        crs
        for crs in sorted(fares.locations_by_crs)
        if not is_pseudo_station(crs)
    ]
    # A handful of stations is still one site, not several builds: one
    # chooser, one station list beside it, one release manifest, and nothing
    # linking to a page that was not written. That is what makes a two-station
    # build reviewable in minutes rather than a whole-network build's hours.
    #
    # A code this feed does not price as a departure point is refused rather
    # than dropped, including a zone or coach pseudo-station: a typo that
    # quietly builds one station instead of two is a build that lies about
    # what it wrote, and the chooser would go on offering what it did write.
    if args.only_stations:
        wanted = {
            code.strip().upper()
            for code in args.only_stations.split(",")
            if code.strip()
        }
        missing = sorted(wanted - set(origins))
        if missing:
            print(
                "error: --only-stations names code(s) this feed does not price "
                f"as an origin: {', '.join(missing)}",
                file=sys.stderr,
            )
            return 2
        if not wanted:
            print(
                "error: --only-stations named no code, which would build no "
                "station page at all.",
                file=sys.stderr,
            )
            return 2
        chosen = len(origins)
        origins = [crs for crs in origins if crs in wanted]
        print(
            f"Building {len(origins)} of the feed's {chosen:,} priceable "
            f"station(s): {', '.join(origins)}",
            flush=True,
        )
    if args.fast_all_origins:
        print(f"Finding priceable origins across {len(origins):,} stations ...", flush=True)
    priced_counts: dict[str, int] = {}
    # One report for the whole build: a station met from fifty origins is
    # named once, and the build can refuse on a total rather than per page.
    coverage = UnsourcedReport()
    for number, crs in enumerate(origins, 1):
        priced_counts[crs] = _priced_destinations(fares, timetable, crs, day, coverage)
        if args.fast_all_origins and (number == len(origins) or number % 100 == 0):
            print(f"  priced {number:,}/{len(origins):,} stations", flush=True)
    # Refuse before writing 2,500 pages rather than after: a refused build
    # must leave no half-published site behind, and the check costs nothing
    # here because the origins have already been queried.
    if args.fail_on_unsourced and coverage:
        return coverage.exit_code(True)
    index = build_station_index(priced_counts, fares.locations_by_crs)
    # The picker's options, written once for the whole site rather than into
    # every page. The same list on 2,712 pages was 295 MB of the network in
    # the wire encoding -- 168 KB a page as these objects -- and identical on
    # every page but the one row each page filters out (audit, 30 September
    # 2026, measured from this build's own output).
    write_station_style(out_dir)
    write_station_script(out_dir)
    station_rows = station_asset_rows(index, base_path)
    write_page_atomic(out_dir / STATION_ASSET_NAME, render_station_asset(station_rows))
    print(
        f"wrote {out_dir / STATION_ASSET_NAME} with {len(station_rows):,} station(s) "
        "for every page's picker",
        flush=True,
    )
    by_crs = {entry["crs"]: entry for entry in index}
    # One shared config for every page, handed to workers once through the
    # pool initialiser; each job then carries only its own origin (audit
    # B3: pickling a per-job copy of the whole station index across the
    # process boundary 2,500 times is minutes of waste at network scale).
    shared = {
        "max_changes": args.max_changes,
        "day": day,
        "note": note,
        "attribution": notices_or_attribution(args),
        "price_source": price_source,
        "feed_date": feed_date,
        "base_path": base_path,
        "provider": args.provider,
        "link_mode": args.link_mode,
        "adults": args.adults,
        "network": args.affiliate_network,
        "advertiser_id": args.advertiser_id,
        "publisher_id": args.publisher_id,
        "departures": args.departures,
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "analytics": analytics,
        "index": index,
        "feed": args.feed,
        "timetable": args.timetable,
        "timetable_index": (
            None
            if timetable_index is None
            else {"directory": str(timetable_index.directory), "identity": timetable_index.identity}
        ),
        # The reference feed's identity, for the resume signature. The
        # feed itself travels as its own initialiser argument below, and
        # not in here: this dict is serialised into the signature, and a
        # parsed feed's repr carries an address, so putting it here would
        # give every run a different signature and resume nothing.
        "reference_fingerprint": reference_fingerprint(
            reference, reference_published, reference_checked
        ),
        # The dates the pages will quote, and the only part of the answer
        # that does not come from a feed this dict already fingerprints.
        "reference_published": reference_published,
        "reference_checked": reference_checked,
    }
    jobs = []
    for crs in origins:
        if crs not in by_crs:
            continue
        jobs.append(
            {
                "crs": crs,
                "slug": by_crs[crs]["slug"],
                "origin_name": by_crs[crs]["name"],
            }
        )
    state_path = out_dir / BUILD_STATE_NAME
    signature = resumable_signature(shared, index) if args.fast_all_origins else ""
    completed = read_resume_state(state_path, signature) if args.fast_all_origins else set()
    if completed:
        jobs = [job for job in jobs if job["slug"] not in completed or not (out_dir / "from" / job["slug"] / "index.html").is_file()]
        print(f"resume: {len(completed):,} recorded page(s) already complete", flush=True)
    if args.fast_all_origins:
        print(
            f"Building {len(jobs):,} station page(s) with {max(1, args.workers)} worker(s); "
            f"progress is saved after every page",
            flush=True,
        )

    # Every page this build is about to write has to have a slice when
    # there is no feed to fall back on. Checked on the jobs that survived
    # the resume, so a build that already wrote a page is not refused for
    # it, and before the fares work rather than one page at a time.
    if timetable is None and timetable_index is not None:
        missing = [job["crs"] for job in jobs if not timetable_index.has(job["crs"])]
        if missing:
            print(missing_slice_message(timetable_index, missing), file=sys.stderr)
            return 2

    workers = max(1, args.workers)
    built_now = 0
    # Audit B1: without this, every pool worker re-parsed all 8.5M flow
    # lines on top of the parent's parse -- nine parses for eight workers.
    # Every build writes the shared metadata and one small index per origin
    # first, single-worker builds included, because the write is what lets a
    # page be built from its own slice rather than the national feed. It was
    # pool-only, so the one-worker build -- the one `build_stations.py` and
    # the double-click runner use on a small machine -- was the one holding
    # 2.1 GB of fares through every page it rendered.
    common_cache, index_dir = fares_index_cache_paths(args.feed)
    fares.write_fare_indexes(common_cache, index_dir, [job["crs"] for job in jobs])
    shared["fare_common_cache"] = str(common_cache)
    shared["fare_index_dir"] = str(index_dir)
    print(
        f"Persisted {len(jobs):,} per-origin fare indexes; a page loads one "
        "slice and the shared metadata once.",
        flush=True,
    )
    prune_fare_index_caches(common_cache, index_dir)

    def publish_result(result: tuple[str, str, str]) -> None:
        nonlocal built_now
        slug, origin_name, html = result
        page = out_dir / "from" / slug / "index.html"
        write_page_atomic(page, html)
        built_now += 1
        completed.add(slug)
        if args.fast_all_origins:
            write_resume_state(state_path, signature, completed)
            print(
                f"[{built_now}/{len(jobs)}] "
                f"wrote {slug} from {origin_name}",
                flush=True,
            )
        else:
            print(f"wrote {page} from {origin_name}", flush=True)

    if workers == 1:
        # The in-process path builds through the same job function the
        # pool uses, and takes its fares the same way a worker does: the
        # per-origin slice off disk, with the shared metadata loaded once.
        # It used to keep the parent's whole feed, and that is what paged:
        # 2.1 GB of fares held beside the national timetable through every
        # page of the render, on a machine whose own floor is 6.4 GB free.
        from build_workers import (
            _WORKER,
            build_page_job,
            configure_worker,
            restore_worker_fares,
        )

        # Through the same state assembly the pool initialiser uses, so the
        # two paths cannot disagree about what a worker was given.
        configure_worker(shared, reference)
        restore_worker_fares(args.feed, shared, loaded=fares)
        _WORKER["timetable"] = timetable
        # A page reads its own slice now, and the no-cache fallback has
        # already handed this same object to the worker, so the parent's
        # own name for the feed is finished with. `gc.collect` because the
        # fares are millions of small objects and CPython returns their
        # arenas when they are freed, not when the reference count reaches
        # zero.
        ctx.release_feeds()
        del fares
        gc.collect()
        for job in jobs:
            publish_result(build_page_job(job))
    else:
        # ProcessPoolExecutor rather than multiprocessing.Pool: a worker
        # that dies before answering turns into a BrokenProcessPool error
        # here, instead of an imap that waits forever on a dead queue.
        # Completion is consumed as each page finishes, not in submission
        # order, so a slow early station cannot hide progress on the rest.
        from build_workers import build_page_job, init_worker
        from concurrent.futures import ProcessPoolExecutor, as_completed

        # The parent is finished with every database it loaded. The fare
        # indexes the workers restore are on disk by now, and each worker
        # parses the national timetable itself in `init_worker`, so nothing
        # below hands either object across the process boundary. Holding
        # 4.1 GB here while four workers hold 8.7 GB is the peak that
        # decides how many workers this machine can run at all -- and it is
        # a peak the build pays for nothing.
        #
        # Pool-only, and that is not tidiness. The `workers == 1` branch
        # above puts both names into `_WORKER` and renders in this process,
        # so releasing them there would delete the databases the build is
        # about to use. From here the all-origins branch returns without
        # naming either again.
        #
        # `gc.collect` because the fares are millions of small objects and
        # CPython returns their arenas when they are freed, not when the
        # reference count happens to reach zero.
        ctx.release_feeds()
        del fares, timetable, single_timetable
        gc.collect()

        with ProcessPoolExecutor(
            workers,
            initializer=init_worker,
            initargs=(args.feed, worker_timetable, shared, reference),
        ) as executor:
            futures = [executor.submit(build_page_job, job) for job in jobs]
            for future in as_completed(futures):
                publish_result(future.result())
    if args.fast_all_origins:
        print(f"station pages complete: {len(completed):,}/{len(index):,}", flush=True)
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
    # The release's own routes, through the one writer both build shapes
    # share: the chooser with this build's provenance, the notice dated
    # from the stamp the pages carry, the crawl and the manifest.
    write_release(
        out_dir,
        index=index,
        routes=[with_base(base_path, f"/from/{slug}/") for slug in sorted(written)],
        budget_pounds=20,
        note=note,
        price_source=price_source,
        feed_date=feed_date,
        analytics=analytics,
        synthetic=synthetic,
        privacy_contact=privacy_contact,
        features=features,
        built_at=shared["built_at"],
        base_path=base_path,
    )
    # Say how to open it, because the pages are not in the repository (they
    # are build output) and their station links are root-absolute, so
    # double-clicking the file does not work while a local server does.
    print(
        f"open it through a local server, not by double-clicking: "
        f"python -m http.server --directory {out_dir} 8000, then http://localhost:8000/ "
        f"(station links start at /from/, so the file system cannot resolve them)"
    )
    coverage.report()
    return coverage.exit_code(args.fail_on_unsourced)


def _build_single_origin(ctx: BuildContext) -> int:
    """Write one station page, and the site that page needs to be a site.

    A single-origin build is a release of one: the chooser names that station,
    the notice and the manifest are written beside it, and the page's picker is
    built from the same one-entry manifest, so every internal link resolves.
    """
    args = ctx.args
    day = ctx.day
    fares = ctx.fares
    fare_note = ctx.fare_note
    timetable = ctx.timetable
    worker_timetable = ctx.worker_timetable
    timetable_index = ctx.timetable_index
    cache_path = ctx.cache_path
    planned = ctx.planned
    price_source = ctx.price_source
    feed_date = ctx.feed_date
    note = ctx.note
    base_path = ctx.base_path
    metadata_folders = ctx.metadata_folders
    reference = ctx.reference
    reference_published = ctx.reference_published
    reference_checked = ctx.reference_checked
    single_timetable = ctx.single_timetable
    payload_origin = ctx.payload_origin
    sampled_index = ctx.sampled_index
    payload = ctx.payload
    analytics = ctx.analytics
    features = ctx.features
    synthetic = ctx.synthetic
    privacy_contact = ctx.privacy_contact
    out = ctx.out
    if not payload["destinations"]:
        print(
            f"note: nothing is priced from {payload['origin']['name']} ({payload['origin']['crs']}) in this feed; "
            "the page says so and points at the chooser"
            + (f". {payload['unpricedNote']}" if payload.get("unpricedNote") else "")
        )
    # A destination with no settlement class is a destination the page's own
    # settlement filters cannot return, so the build names it rather than
    # letting it disappear quietly -- and refuses before writing anything, the
    # same rule the other refusals follow.
    coverage = UnsourcedReport()
    coverage.from_payload(payload)
    if args.fail_on_unsourced and coverage:
        return coverage.exit_code(True)
    # A single-origin build is a site too, not a loose page (S01, S04). It
    # writes the station at its canonical /from/<slug>/ route, a root chooser
    # that offers exactly that one station, and the privacy page, and the
    # station page's picker is built from that same one-entry manifest -- so
    # every internal link resolves. The station page is no longer written to
    # --out directly; --out names the site root's index.html, which is the
    # chooser, and the station sits under from/.
    out_dir = out.parent
    station_count = _priced_destinations(fares, timetable, payload_origin, day)
    index = build_station_index({payload_origin: station_count}, fares.locations_by_crs)
    routes = published_routes_for(index, base_path)
    # The picker on this one page offers the written stations except itself.
    payload["stations"] = [
        {"name": entry["name"], "crs": entry["crs"], "href": entry["href"]}
        for entry in routes
        if entry["crs"] != payload["origin"]["crs"]
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    # The station route's stylesheet, written once before the page that
    # asks for it (ADR-0047), and the route's script beside it (T1).
    write_station_style(out_dir)
    write_station_script(out_dir)
    if index:
        station_page = out_dir / "from" / index[0]["slug"] / "index.html"
        write_page_atomic(
            station_page,
            render_page(
                payload,
                budget_pounds=20,
                analytics=analytics,
                nre_credit=wants_nre_credit(notices_or_attribution(args)),
            ),
        )
        print(
            f"wrote {station_page} with {len(payload['destinations'])} destinations "
            f"from {payload['origin']['name']}"
        )
    else:
        # Nothing priced from this origin, so there is no station page to
        # write. The chooser at the root says so and the build names it.
        print(
            f"note: {payload['origin']['name']} priced no destination, so this build "
            "writes only the chooser; there is no station page to serve."
        )
    # The release's own routes, through the one writer both build shapes
    # share. The manifest is dated from the page's own stamp rather than from
    # a second clock read a moment later (four-dimension audit R8).
    write_release(
        out_dir,
        index=index,
        routes=[entry["href"] for entry in routes],
        budget_pounds=20,
        note=note,
        price_source=price_source,
        feed_date=feed_date,
        analytics=analytics,
        synthetic=synthetic,
        privacy_contact=privacy_contact,
        features=features,
        built_at=payload["builtAt"],
        base_path=base_path,
    )
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
    if not payload["railcards"]:
        print("no reviewed railcard is present in this feed; standard fares are shown")
    else:
        priced = [card for card in payload["railcards"] if card["eligibleCount"]]
        if not priced:
            print(
                "the reviewed railcards are in this feed, but no displayed fare is currently "
                "eligible under their DTD rules"
            )
        else:
            for card in priced:
                print(
                    f"{card['label']} ({'/'.join(card['codes'])}): "
                    f"{card['eligibleCount']} displayed fare rows are eligible"
                )
        print("no railcard is selected by default; the reader chooses one")
    coverage.report()
    return 0


if __name__ == "__main__":
    # Windows starts pool workers by re-importing this module, so the entry
    # point must sit under the guard (it does) and the guard must come before
    # main() runs, or each worker re-runs the build recursively.
    raise SystemExit(main())
