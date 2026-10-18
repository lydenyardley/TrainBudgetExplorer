"""What a build keeps between runs, and the names it keeps it under.

A built page is a function of the feeds, the code and the day, and this module is
where that function's answers are written down so the next build does not pay for
them twice: the parsed-fares caches, the timetable caches, the timetable index, the
per-origin facts and the service week the page reports. Every name here is a
content digest rather than a timestamp (ADR-0031), because a build that trusted
timestamps served one download's timetable on a page built from another.

It is also where `SOURCE_FILES` is derived, by walking `build_demo_page.py`'s own
imports: a cache keyed on a stale source list is a cache that survives the fix it
should invalidate.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import html
import json
import pickle
import shutil
import time
from pathlib import Path
from typing import NamedTuple

from atoc_fares import FaresDb, location_lookup_candidates
from atoc_timetable import SLICE_INDEX_SCHEMA, SliceIndex
# The shared assets' names are read through the module rather than bound here.
# They are the identity of the code the pages fetch, so a reader that holds one
# by value holds a copy of a name this release may have stopped writing: a test
# that changes the assets has to change them in one place, and a build that
# resumed past a page because its own copy still matched would leave the page
# naming a file the prune then deletes (ADR-0071).
import build_assets
from build_assets import replace_published
from page_templates import PAYLOAD_MARKER


BUILD_STATE_NAME = ".trainbudget-build.json"


CACHE_DIR = Path(__file__).parent / "_cache"


def module_sources(root: Path, start: str) -> tuple[str, ...]:
    """Every module of this project that ``start`` reaches through its imports.

    A build is a function of the code it runs, and that list used to be kept by
    hand -- once here and again in the runner -- so a module named by neither
    left a built site looking current after a change to it. Three were: every
    build imports ``atoc_fares_loader``, ``atoc_knowledgebase`` and
    ``destination_coverage``, and neither list named one of them (F4 of the 8
    October 2026 agent-efficiency audit, which fixed CI's list the same way).
    The imports answer it now, so nothing has to be remembered.
    """
    found: list[str] = []
    pending = [start]
    while pending:
        name = pending.pop()
        if name in found:
            continue
        found.append(name)
        for node in ast.walk(ast.parse((root / name).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                reached = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                reached = [node.module.split(".")[0]]
            else:
                continue
            pending.extend(f"{module}.py" for module in reached if (root / f"{module}.py").is_file())
    return tuple(sorted(found))


# Read as data rather than imported, and therefore not reachable by walking
# imports. `atoc_fare_declarations` globs `reference-data/*.json` for the
# reviewed destination facets, so regenerating one of those files changes what a
# page calls its destinations; `nre_attribution` inlines the mark in `assets/`
# into every page that carries the NRE credit, and a missing one is a refusal
# rather than a page without a credit.
DATA_PATTERNS = ("reference-data/*.json", "assets/*")


DATA_SOURCES = tuple(
    sorted(
        path.relative_to(Path(__file__).parent).as_posix()
        for pattern in DATA_PATTERNS
        for path in Path(__file__).parent.glob(pattern)
        if path.is_file()
    )
)


# What a generated page is a function of, hashed into `source_fingerprint` and
# so into every cache key built from it.
SOURCE_FILES = module_sources(Path(__file__).parent, "build_demo_page.py") + DATA_SOURCES


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


def feed_content_digest(path: str | Path) -> str:
    """An identity for a feed that cannot outlive the bytes it names.

    Names, sizes and mtimes separate two downloads on any ordinary day and cost
    nothing, which is why the resume key used them. They cannot separate two
    downloads when the replacement holds different bytes of the same length
    under the same timestamp: a copy that preserves mtimes, an archive extracted
    with the dates stored in it, a feed directory restored from somewhere else.
    A key like that goes on serving prices parsed from bytes the feed no longer
    holds, and the page looks entirely normal while quoting fares from a
    download that had been replaced -- the one kind of cache failure nobody
    notices. So every key here -- this cache's, the resume's (E4 of the 17
    October 2026 audit) and the merge's -- is the content itself, at a cost of
    about a fifth of a second over 48MB against the half-minute parse it exists
    to avoid.
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
        # Content, not names and timestamps: the case the fares cache was
        # written for -- a replacement of the same size and mtime -- left the
        # pages resuming as complete while the cache re-parsed, so a release
        # quoted the previous download beside freshly parsed data (E4 of the
        # 17 October 2026 audit). Hashed once per build, not once per page.
        "feed": feed_content_digest(shared["feed"]),
        "timetable": feed_content_digest(shared["timetable"]) if shared["timetable"] else None,
        "config": {key: value for key, value in shared.items()
                   if key not in {"feed", "timetable", "built_at", "analytics"}},
        "stations": index,
        # page/** is not in SOURCE_FILES, so a script or stylesheet change
        # would otherwise resume past every page and leave them naming the
        # previous asset. The names are digests of the bytes, so they are the
        # identity of the code the pages fetch.
        "assets": [
            build_assets.station_style_asset_name(),
            build_assets.station_script_asset_name(),
            build_assets.chooser_script_asset_name(),
        ],
    }
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def read_resume_state(path: Path, signature: str) -> tuple[set[str], dict[str, int]]:
    """The pages this signature already wrote, and the places each one carries.

    The counts ride in the same record because they are the same fact: a page
    recorded here is one this build will not build again, and the chooser still
    has to name its size -- which is the page's own number, not one the index
    pass can work out (see ``places_in_payload``). Schema 2 added them; a
    schema 1 file is ignored rather than read for counts it cannot hold, so a
    build resuming an older one rebuilds the pages it recorded.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set(), {}
    if not isinstance(data, dict) or data.get("schema") != 2 or data.get("signature") != signature:
        return set(), {}
    completed = data.get("completed")
    places = data.get("places")
    return (
        {str(slug) for slug in completed} if isinstance(completed, list) else set(),
        {
            str(crs): int(count)
            for crs, count in places.items()
            if isinstance(count, int) and not isinstance(count, bool)
        }
        if isinstance(places, dict)
        else {},
    )


def write_resume_state(
    path: Path, signature: str, completed: set[str], places: dict[str, int]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema": 2,
                "signature": signature,
                "completed": sorted(completed),
                "places": {crs: places[crs] for crs in sorted(places)},
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    replace_published(temporary, path)


def page_is_current(path: Path, html: str) -> bool:
    """Whether the page on disk already says what this build would write.

    The payload's build stamp changes on every build by design, so the key is
    the payload with builtAt masked rather than the file's bytes (T3): the
    stamp is dropped and the rest is compared with sorted keys, which also
    absorbs the serviceWeek key order that follows the process hash seed. A
    page that cannot be read back is not current -- the safe direction is to
    write -- so every failure here answers False, and a build that changed
    nothing rewrites nothing.
    """
    try:
        current = path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        decoder = json.JSONDecoder()
        marker = PAYLOAD_MARKER
        old_start = current.index(marker) + len(marker)
        new_start = html.index(marker) + len(marker)
        old, old_end = decoder.raw_decode(current, old_start)
        new, new_end = decoder.raw_decode(html, new_start)
    except ValueError:
        return False
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    # The markup around the payload is compared byte for byte: a template,
    # stylesheet or script change leaves the payload alone but renames the
    # hashed asset the page requests, and a page kept because its payload
    # matched would go on naming a file the prune below then deletes.
    if current[:old_start] + current[old_end:] != html[:new_start] + html[new_end:]:
        return False
    old.pop("builtAt", None)
    new.pop("builtAt", None)
    normalise = lambda payload: json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return normalise(old) == normalise(new)


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
    # The load may have written a classification source *beside the feed* --
    # ``fares.location-types.json``, written by the ONS and facet pass -- and
    # ``fares_cache_identity`` hashes every file it could have read, so the
    # paths resolved above can name a folder whose contents have just changed
    # (audit item 2, 14 October 2026). A pair written under that name cannot be
    # asked for by any later build: the next one hashes the file this one wrote,
    # computes a different digest, misses, and pays the parse the cache exists
    # to avoid -- 55.6s against 2.6s restored, measured on this repository's own
    # machine. So the write is named from the bytes as they are *now*, after the
    # classification pass rather than before it, which is also the state the
    # parser just read.
    common_cache, index_dir = fares_index_cache_paths(feed)
    index = index_dir / f"{code}.pickle"
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
                # Unreadable is unrankable, as in prune_timetable_caches.
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


# -- one origin's reusable facts (T2, T3, T6, T9) ---------------------------
#
# A page's two expensive answers, kept per origin under _cache/ beside the
# other derived artefacts: the service week's journey facts, keyed by the
# timetable they were searched from, and the priced counts with the coverage
# they were counted for, keyed by the fares they were priced from. Two
# sections in one file because they share the origin and the read/write
# discipline but not the lifetime: the timetable feed changes weekly at most
# and the fares feed daily, so a fares-only refresh reuses every journey fact
# while re-pricing every origin, which is the daily case (T9).
#
# One file per origin rather than one file per feed, so the store is bounded:
# the same 2,712 names are overwritten in place, and no prune pass is needed.
# A section whose identity does not match is a miss rather than a page
# assembled from another download's answers -- a cache is an optimisation, so
# the worst it may do is be slow.
PAGE_FACTS_SCHEMA = 1


def page_facts_path(origin: str) -> Path:
    """Where one origin's reusable answers live.

    Resolved from CACHE_DIR on every call rather than bound at import, so a
    build that points its cache elsewhere -- the tests do -- reads and writes
    there too.
    """
    return CACHE_DIR / "page-facts" / f"{origin.strip().upper()}.json"


def read_page_facts(origin: str) -> dict | None:
    """One origin's facts, or None when there are none to reuse.

    Anything unreadable is a miss: a missing file, a half-written write, a
    schema this code no longer reads. Each section carries its own identity,
    so a file from another feed is not rejected here -- its sections simply
    miss one by one where they are read.
    """
    try:
        raw = json.loads(page_facts_path(origin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(raw, dict)
        or raw.get("schema") != PAGE_FACTS_SCHEMA
        or raw.get("origin") != origin.strip().upper()
    ):
        return None
    return raw


def write_page_facts(origin: str, facts: dict) -> None:
    """Store one origin's facts atomically."""
    facts = {**facts, "schema": PAGE_FACTS_SCHEMA, "origin": origin.strip().upper()}
    path = page_facts_path(origin)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(facts, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    replace_published(temporary, path)


def service_week_identity(
    timetable_identity: str, source_index: int, origin: str, max_changes: int, days: list
) -> str:
    """Everything one origin's service-week answers depend on, as one string.

    The timetable's own identity (the feed's content digest, or the slice
    index's when the build reads no feed), which of the build's timetables was
    searched -- the main one or the outbound-single focus over the same feed --
    the origin, the change limit, and the exact days of the week. The priced
    destinations are deliberately not in it: a fares-only refresh prices new
    rows out of the same journeys, so the facts it needs are the ones that did
    not move.
    """
    day_key = ",".join(day.isoformat() for day in days)
    return f"{timetable_identity}:{source_index}:{origin.strip().upper()}:{max_changes}:{day_key}"


def priced_facts_identity(fares_identity: str, day) -> str:
    """Everything one origin's priced counts depend on, as one string.

    ``fares_cache_identity`` already covers the feed's bytes, the code that
    reads them and the classification beside them; the day matters because the
    same feed prices differently on different days. Nothing about the timetable
    is here, because the count is a fare-selector question: the places the page
    carries are read off the page by the build that writes it.
    """
    return f"{fares_identity}:{(day.isoformat() if day is not None else 'undated')}"


def timetable_facts_identity(args, timetable, timetable_index) -> str | None:
    """The identity one origin's service-week facts are keyed by.

    The feed's content digest when the pages are built from a feed the build
    loaded, the slice index's own identity when the feed was never read --
    which is the index-covers case, where every page loads its own slice --
    and None when there is no timetable at all. The identity names what the
    pages read rather than what flags were passed, because a build handed both
    a feed and a covering index reads only the index.
    """
    # A single-origin build loads the timetable focused on the destinations
    # its fares price, so what it reaches depends on the fares feed as well as
    # the timetable. A fares-only refresh that prices a new destination would
    # read a stored week that never searched it and call the row "No
    # service". Only the network build, whose pages are cut by origin alone,
    # searches a week that the timetable decides by itself.
    if not getattr(args, "all_origins", False):
        return None
    if timetable is not None and args.timetable:
        return timetable_index_identity(args.timetable)
    if timetable_index is not None:
        return timetable_index.identity
    return None


def read_service_week(
    origin: str, timetable_identity: str | None, source_index: int,
    max_changes: int, days: list,
) -> list | None:
    """The stored (duration, changes) answers for one origin's week, or None.

    The whole reached set is stored but only the week is returned: the build
    filters to the destinations its fares priced, so a fares-only refresh that
    prices a new row still finds that row's journeys waiting.
    """
    if timetable_identity is None or not days:
        return None
    facts = read_page_facts(origin)
    if facts is None:
        return None
    section = facts.get("timetable")
    if not isinstance(section, dict):
        return None
    if section.get("identity") != service_week_identity(
        timetable_identity, source_index, origin, max_changes, days
    ):
        return None
    weeks = section.get("weeks")
    if not isinstance(weeks, list) or len(weeks) != len(days):
        return None
    return weeks


def write_service_week(
    origin: str, timetable_identity: str | None, source_index: int,
    max_changes: int, days: list, weeks: list,
) -> None:
    """Store one origin's whole reached set for the week, for the next build."""
    if timetable_identity is None or not days:
        return
    facts = read_page_facts(origin) or {}
    facts["timetable"] = {
        "identity": service_week_identity(
            timetable_identity, source_index, origin, max_changes, days
        ),
        "weeks": weeks,
    }
    write_page_facts(origin, facts)


def read_priced_facts(origin: str, fares_identity: str | None, day) -> dict | None:
    """The stored priced counts and coverage for one origin, or None."""
    if fares_identity is None:
        return None
    facts = read_page_facts(origin)
    if facts is None:
        return None
    section = facts.get("fares")
    if not isinstance(section, dict):
        return None
    if section.get("identity") != priced_facts_identity(fares_identity, day):
        return None
    return section


def write_priced_facts(
    origin: str, fares_identity: str | None, day, count: int, coverage: dict
) -> None:
    """Store one origin's priced counts and coverage, for the next build."""
    if fares_identity is None:
        return
    facts = read_page_facts(origin) or {}
    facts["fares"] = {
        "identity": priced_facts_identity(fares_identity, day),
        "count": count,
        "coverage": coverage,
    }
    write_page_facts(origin, facts)
