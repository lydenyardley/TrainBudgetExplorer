"""Where the numbers came from: the feed metadata, the download manifest and the dates.

Every page states its own vintage -- which feed, downloaded when, and how old that
is -- and this module is the only reader of that evidence. The download date is a
value (``feed_date_from``), not a fragment of a sentence, because two routes
composing the same sentence from a fragment is how one page came to print the same
date twice.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from trainbudget.fares.atoc_fares import EVERYTHING_PENCE
from trainbudget.timetable.atoc_knowledgebase import (
    ABSENT,
    Knowledgebase,
    UNKNOWN,
    UNPUBLISHED,
    load_ticket_restrictions,
)
from trainbudget.timetable.atoc_timetable import TimetableDb
from trainbudget.build.build_release import DEFAULT_NOTE, DEFAULT_PRICE_SOURCE
from trainbudget.build.build_state import CACHE_DIR, prune_timetable_caches, timetable_cache_path

from typing import TYPE_CHECKING
from typing import TYPE_CHECKING
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from trainbudget.build.build_pool import BuildContext



if TYPE_CHECKING:
    from trainbudget.build.build_pool import BuildContext


if TYPE_CHECKING:
    from trainbudget.build.build_pool import BuildContext


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


# The downloader records its own non-secret provenance (URL, size, hash, and
# timestamp) in a manifest beside the feeds it writes. A feed downloaded
# without a hand-written metadata.json still has that, so a real download can
# never fall back to the synthetic default just because nobody typed a note.
MANIFEST_NAME = "download-manifest.json"


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
    """The feed's own name from the metadata, or None if it names nothing.

    The name and nothing else. The download date travels beside it as a value
    (``feed_date_from``), because a route that has to name both has to compose
    one sentence from the pair: while the date was inside this string, the
    chooser appended its own copy of it and printed the same date twice.
    """
    source = metadata.get("source")
    if not source:
        return None
    return f"the {source}"


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


# The month names every date this build writes in words is spelled from, so a
# date read back out of words and a date written into words can never disagree
# about what a month is called.
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def dtd_download_entry(manifest: dict | None) -> dict | None:
    """The download the prices came from, from the downloader's manifest, or None.

    A fares entry wins over a timetable entry because it is the feed the prices
    are built from; within the same feed type the newest download wins, and a
    newer timetable download must never restate the fares' provenance. A
    timetable-only manifest still names its download rather than claiming the
    prices came from a download that never carried them.

    The name and the date are both read out of the entry this returns, so the
    two halves of a provenance sentence cannot describe different downloads.
    """
    entries = manifest.get("downloads") if isinstance(manifest, dict) else None
    best: dict | None = None
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        if entry.get("source") != "dtd" or entry.get("name") not in ("fares", "timetable"):
            continue
        # A stamp short of a date names no download this can date, and a name
        # with no date beside it is the pair this exists to keep together.
        if not isinstance(entry.get("downloaded_at"), str) or len(entry["downloaded_at"]) < 10:
            continue
        if best is None:
            best = entry
            continue
        if best.get("name") == "fares" and entry.get("name") != "fares":
            continue
        if entry["downloaded_at"] > best["downloaded_at"]:
            best = entry
    return best


def price_source_from_manifest(manifest: dict) -> str | None:
    """The name of the feed the prices came from, or None.

    The name, not the sentence: the download date travels beside it as a value
    (``feed_date_from`` reads the same entry), so each route composes one
    sentence from the pair instead of appending its own date to a sentence that
    already ended in one.
    """
    best = dtd_download_entry(manifest)
    if best is None:
        return None
    return f"the National Rail Data Portal DTD {best['name']} feed"


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
    try:
        year, month, day = (int(part) for part in iso[:10].split("-"))
        return f"{day} {MONTH_NAMES[month - 1]} {year}"
    except (ValueError, IndexError):
        return iso


def feed_date_from(metadata: dict | None, manifest: dict | None = None) -> str | None:
    """The fares download's own date, as YYYY-MM-DD, or None.

    The provenance sentence says when a feed was downloaded in words; this is
    the same fact as a value, so the page can measure the age of the prices it
    is showing against its own clock rather than repeating a sentence the build
    wrote once. A timetable entry never wins: the date has to describe the
    fares, because that is the number the reader is judging.

    The metadata is read as ISO or as the words a hand-written note uses
    (``downloaded: "3 October 2026"``), because this date is the only carrier
    of the download date now that the source sentence names the feed alone: a
    stamp this cannot read is no date at all, rather than a cut-off string that
    reaches a reader as "downloaded 3 October".
    """
    if metadata:
        stamp = metadata.get("downloaded")
        if isinstance(stamp, str):
            found = iso_from_download_stamp(stamp)
            if found:
                return found
    entry = dtd_download_entry(manifest)
    return entry["downloaded_at"][:10] if entry else None


def iso_from_download_stamp(stamp: str) -> str | None:
    """A download stamp as YYYY-MM-DD, from either form a note may hold.

    The manifests dtd_download.py writes are ISO with a Z, and a metadata.json
    is hand-written, so both the value a machine produced and the value a
    person typed are read here. Anything else is None: a stamp is not guessed
    at, the same rule ``cif_date_to_iso`` follows for the feed's own dates.
    """
    if len(stamp) >= 10 and stamp[4] == "-" and stamp[7] == "-":
        return stamp[:10]
    words = stamp.replace(",", " ").split()
    if len(words) == 3 and words[0].isdigit() and words[1] in MONTH_NAMES and words[2].isdigit():
        return (
            f"{int(words[2]):04d}-{MONTH_NAMES.index(words[1]) + 1:02d}-{int(words[0]):02d}"
        )
    return None


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
