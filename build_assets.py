"""The files a site is made of and the addresses that reach them.

A route's script and stylesheet are written once per site rather than inlined into
every page, and the file names carry their own content digest so a reader never runs
code the page was not built with (ADR-0038). The slug helpers live here because the
payload and the chooser both need the same address for the same station.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from pathlib import Path

from page_templates import CHOOSER_SCRIPT, STATION_SCRIPT, STATION_STYLESHEET


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
    "travelling. Each row's price is the railway's own walk-up fare — the fare you can buy on "
    "the day — so it is the same whichever seller you buy it from."
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


# The hashed files one build leaves for the next: a stylesheet or script whose
# content changed is a new name rather than a changed one, so a rebuild into
# the same folder leaves the copy the previous build wrote beside the one this
# build wrote. Five station stylesheets accumulated in _site/ that way, and
# `git status` listed what no page named. Only these three patterns are ever
# removed: everything else in the folder is somebody else's to delete.
SHARED_ASSET_PATTERNS = ("station-*.css", "station-*.js", "chooser-*.js")


def prune_shared_assets(out_dir: Path, *keep: str) -> list[str]:
    """Remove the hashed assets this build did not write, and name them.

    ``keep`` holds the file names this build wrote. A name the manifest no
    longer names is served to nobody and read by no page, so keeping it grows
    the folder and lies in `git status` about what the release is.
    """
    kept = set(keep)
    # A page this build did not write -- a station an earlier build priced and
    # this one does not, which the build names rather than deletes -- still
    # requests the asset it was built with. Deleting that asset would break a
    # page the build promised to leave alone, so anything a file in the folder
    # still names is kept.
    for page in out_dir.rglob("*.html"):
        try:
            text = page.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        kept.update(
            href.rsplit("/", 1)[-1] for href in internal_hrefs(text)
        )
    removed: list[str] = []
    for pattern in SHARED_ASSET_PATTERNS:
        for path in sorted(out_dir.glob(pattern)):
            if path.is_file() and path.name not in kept:
                path.unlink()
                removed.append(path.name)
    if removed:
        print(
            f"removed {len(removed)} asset file(s) no page names: "
            + ", ".join(removed),
            flush=True,
        )
    return removed


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
