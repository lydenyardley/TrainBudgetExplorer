"""The build itself: the phases, the worker pool, and the merge that joins the shards.

``BuildContext`` is what the phases pass between them, so a reader can see which
values the two build shapes share rather than reading the prologue twice. The shard
merge is here because a split build has to agree with itself about the day, the note
and the provenance before any of it is published.
"""

from __future__ import annotations

import argparse
import gc
import html
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from atoc_fares import EVERYTHING_PENCE, FaresDb, is_pseudo_station
from atoc_timetable import TimetableDb
from build_assets import (
    STATION_ASSET_NAME,
    published_routes_for,
    render_station_asset,
    station_asset_rows,
    with_base,
    write_chooser_script,
    write_page_atomic,
    write_station_script,
    write_station_style,
)
from build_payload import (
    _priced_destinations,
    build_payload,
    build_station_index,
    places_in_payload,
)
from build_provenance import describe_restriction_note, reference_fingerprint
from build_release import (
    DEFAULT_NOTE,
    DEFAULT_PRICE_SOURCE,
    DEFAULT_PRIVACY_CONTACT,
    MEASUREMENT_PLANS,
    OPENING_BUDGET_POUNDS,
    notices_or_attribution,
    release_gate_problems,
    site_features,
    wants_nre_credit,
)
from build_render import render_page, write_release
from build_state import (
    BUILD_STATE_NAME,
    fares_cache_identity,
    fares_index_cache_paths,
    feed_content_digest,
    load_page_fares,
    missing_slice_message,
    open_timetable_index,
    page_is_current,
    prune_fare_index_caches,
    read_priced_facts,
    read_resume_state,
    resumable_signature,
    source_fingerprint,
    timetable_cache_path,
    timetable_facts_identity,
    write_priced_facts,
    write_resume_state,
)
from destination_coverage import UnsourcedReport
from retailer import DISCLOSURE, pairing_warning


# The per-origin tripwire (ADR-0024): one origin should take tens of seconds
# on a real network, not minutes. Exceeding this means the journey search's
# cost is out of hand, and a full-network build would take days -- the build
# stops on the FIRST origin instead of hours later. The measured full-network
# number is ~9 minutes today, which is why this sits far above it: the default
# is a never-fire alarm on today's code, not a target.
MAX_ORIGIN_SECONDS = 1800.0


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
    # -- after _load_timetable -----------------------------------------
    # The identity one origin's service-week facts are keyed by, resolved
    # once here because hashing the feed costs seconds on the national
    # download and both payload paths below would otherwise pay it.
    timetable_identity: str | None = None
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
                "python -m tools.build_timetable_index writes one",
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
    # What the pages read, named once: the feed's content digest when a feed
    # was loaded, the slice index's own identity when it was not, and nothing
    # when there is no timetable to search. Hashed here rather than once per
    # page, because the national download costs seconds to hash.
    if ctx.timetable is not None or ctx.timetable_index is not None:
        print("Hashing the timetable for the journey-facts identity ...", flush=True)
    ctx.timetable_identity = timetable_facts_identity(args, ctx.timetable, ctx.timetable_index)
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
            timetable_identity=ctx.timetable_identity,
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


def parse_shard(spec: str | None) -> tuple[int, int] | None:
    """The shard share ``--shard N/M`` names, or None for the whole list.

    Refused rather than guessed: shard 0, a share past the count, and a
    denominator of zero would all silently build the wrong slice of the
    network, and a merge that cannot tell would publish it.
    """
    if spec is None:
        return None
    try:
        number, total = (int(part) for part in spec.split("/"))
    except ValueError:
        number, total = 0, 0
    if total < 1 or number < 1 or number > total:
        raise ValueError(f"--shard takes N/M with 1 <= N <= M, not {spec!r}.")
    return number, total


SHARD_MANIFEST_NAME = "shard.json"


SHARD_MANIFEST_SCHEMA = 1


def shard_agreement(shared: dict) -> dict:
    """Everything two shards must agree on to merge into one site.

    The page bytes: every shared input the pages are rendered from, with the
    build stamp and the per-shard pieces (the origin subset, the cache paths a
    worker read) left out. A merge of shards that disagree would publish pages
    built as different releases under one chooser, so the merge refuses them
    instead. Compared as canonical JSON, because key order must not decide it.
    """
    excluded = {
        "built_at", "index", "fare_common_cache", "fare_index_dir",
        "feed", "timetable", "timetable_index",
    }
    agreement = {
        "source": source_fingerprint(),
        # Content, like the resume key: two shards built from different bytes
        # of the same size and mtime are different releases (E4 of the 17
        # October 2026 audit).
        "feed": feed_content_digest(shared["feed"]),
        "timetable": feed_content_digest(shared["timetable"]) if shared["timetable"] else None,
        "config": {
            key: value for key, value in shared.items() if key not in excluded
        },
    }
    index_spec = shared.get("timetable_index") or {}
    agreement["timetable_index"] = index_spec.get("identity")
    return json.loads(json.dumps(agreement, sort_keys=True, default=str))


def merge_shards(args) -> int:
    """Combine shard folders into the one site their pages belong to.

    Each shard proves what it is: which share it built, what inputs it built
    from, which origins those were, and what each priced. The merge proves the
    rest: the shares are distinct and cover 1..M, the inputs agree, and the
    origins partition the feed's list -- a shard set that overlaps, gapped, or
    built from another download is refused rather than published. The chooser,
    the station list, the manifest and the coverage report are then written
    once from the union, through the same writers a single build uses.
    """
    if not args.feed:
        print("error: --merge needs --feed, for the origin list the shards must partition.",
              file=sys.stderr)
        return 2
    out_dir = Path(args.out).parent
    shards: list[tuple[Path, dict]] = []
    for raw in args.merge:
        shard_dir = Path(raw)
        try:
            manifest = json.loads((shard_dir / SHARD_MANIFEST_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"error: {shard_dir} holds no readable {SHARD_MANIFEST_NAME}: {error}",
                  file=sys.stderr)
            return 2
        if not isinstance(manifest, dict) or manifest.get("schema") != SHARD_MANIFEST_SCHEMA:
            print(f"error: {shard_dir}/{SHARD_MANIFEST_NAME} is not a shard manifest.",
                  file=sys.stderr)
            return 2
        shards.append((shard_dir, manifest))
    total = shards[0][1].get("of")
    numbers = sorted(manifest.get("shard") for _, manifest in shards)
    if any(manifest.get("of") != total for _, manifest in shards) or numbers != list(range(1, total + 1)):
        print(
            "error: the shards are not shares 1..{} of one split: ".format(total)
            + ", ".join(f"{directory.name} is share {manifest.get('shard')} of {manifest.get('of')}" for directory, manifest in shards),
            file=sys.stderr,
        )
        return 2
    inputs = shards[0][1].get("inputs")
    for shard_dir, manifest in shards[1:]:
        if manifest.get("inputs") != inputs:
            print(
                f"error: {shard_dir.name} was built from different inputs and cannot "
                "merge into this site; rebuild the shards from the same feeds and flags.",
                file=sys.stderr,
            )
            return 2
    # The merge writes the shared assets from the code it runs, while the
    # shards' pages request the assets of the code that built them. Shards
    # from another revision would merge into pages naming files this merge
    # never writes, so the revision is part of what must agree.
    if (inputs or {}).get("source") != source_fingerprint():
        print(
            "error: the shards were built by a different revision of the build "
            "code than this merge; rebuild the shards with this checkout.",
            file=sys.stderr,
        )
        return 2
    fares = FaresDb().load_feed(args.feed)
    universe = sorted(
        crs for crs in fares.locations_by_crs if not is_pseudo_station(crs)
    )
    union = sorted({crs for _, manifest in shards for crs in manifest.get("origins", [])})
    if union != universe:
        missing = [crs for crs in universe if crs not in union]
        extra = [crs for crs in union if crs not in universe]
        print(
            "error: the shards do not partition this feed's origins: "
            + (f"missing {len(missing)}: {', '.join(missing[:12])}" if missing else "")
            + ("; " if missing and extra else "")
            + (f"outside the feed: {', '.join(extra[:12])}" if extra else ""),
            file=sys.stderr,
        )
        return 2
    counts: dict[str, int] = {}
    for _, manifest in shards:
        for row in manifest.get("index", []):
            counts[row["crs"]] = row["destinations"]
    index = build_station_index(counts, fares.locations_by_crs)
    coverage: UnsourcedReport = UnsourcedReport()
    for _, manifest in shards:
        for crs, data in (manifest.get("coverage") or {}).items():
            coverage.replay_origin(crs, data)
    if args.fail_on_unsourced and coverage:
        return coverage.exit_code(True)
    # Every refusal before the first copy, so a refused merge leaves no
    # half-merged site behind, and an overlap is told apart from a folder
    # that already holds an earlier build.
    owners: dict[str, Path] = {}
    for shard_dir, _manifest in shards:
        source = shard_dir / "from"
        if not source.is_dir():
            continue
        for child in sorted(source.iterdir()):
            if child.name in owners:
                print(
                    f"error: {child.name} is written by both {owners[child.name].name} "
                    f"and {shard_dir.name}; the shares overlap.",
                    file=sys.stderr,
                )
                return 2
            owners[child.name] = shard_dir
    existing = out_dir / "from"
    if existing.is_dir() and any(existing.iterdir()):
        print(
            f"error: {existing} already holds station pages; merge into an empty "
            "folder so no page from an earlier build is published as this one.",
            file=sys.stderr,
        )
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, shard_dir in sorted(owners.items()):
        shutil.copytree(shard_dir / "from" / name, out_dir / "from" / name)
    release = shards[0][1].get("release", {})
    built_at = max(str(manifest.get("built_at", "")) for _, manifest in shards)
    write_station_style(out_dir)
    write_station_script(out_dir)
    write_chooser_script(out_dir)
    station_rows = station_asset_rows(index, release.get("base_path", ""))
    write_page_atomic(out_dir / STATION_ASSET_NAME, render_station_asset(station_rows))
    write_release(
        out_dir,
        index=index,
        routes=[
            with_base(release.get("base_path", ""), f"/from/{entry['slug']}/")
            for entry in index
        ],
        # The shard's own figure, so a merge of shards built at another budget
        # opens where they did rather than at this process's constant (E7).
        budget_pounds=release.get("budget_pounds", OPENING_BUDGET_POUNDS),
        note=release.get("note", ""),
        price_source=release.get("price_source", DEFAULT_PRICE_SOURCE),
        feed_date=release.get("feed_date"),
        analytics=release.get("analytics", ""),
        synthetic=release.get("synthetic", True),
        privacy_contact=release.get("privacy_contact", ""),
        features=release.get("features", {}),
        built_at=built_at,
        base_path=release.get("base_path", ""),
    )
    coverage.report()
    return coverage.exit_code(args.fail_on_unsourced)


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
    shard = parse_shard(args.shard)
    if shard is not None:
        number, total = shard
        chosen = len(origins)
        origins = [
            crs for position, crs in enumerate(origins) if position % total == number - 1
        ]
        print(
            f"Building shard {number}/{total}: {len(origins)} of {chosen} "
            "origin(s); --merge combines the shares into one site",
            flush=True,
        )
    if args.fast_all_origins:
        print(f"Finding priceable origins across {len(origins):,} stations ...", flush=True)
    # The identities the per-origin facts are keyed by, read once here rather
    # than hashed once per page: the fares feed's bytes for the priced counts,
    # the timetable's for the journey weeks (T6, T9). A timetable the build
    # reads from a slice index is keyed by that index, because there is no
    # feed to hash.
    print("Hashing the feeds for the priced- and journey-facts identities ...", flush=True)
    fares_identity = fares_cache_identity(args.feed)
    timetable_identity = ctx.timetable_identity
    priced_counts: dict[str, int] = {}
    # One report for the whole build: a station met from fifty origins is
    # named once, and the build can refuse on a total rather than per page.
    coverage = UnsourcedReport()
    for number, crs in enumerate(origins, 1):
        # The counts and the coverage the last build priced out of the same
        # fares, replayed rather than re-queried: the station index below is
        # built from the facts either way, and the report reads the same (T6).
        stored = read_priced_facts(crs, fares_identity, day)
        if stored is not None and isinstance(stored.get("count"), int):
            priced_counts[crs] = stored["count"]
            coverage.replay_origin(crs, stored.get("coverage") or {})
        else:
            priced_counts[crs] = _priced_destinations(fares, timetable, crs, day, coverage)
            write_priced_facts(
                crs, fares_identity, day, priced_counts[crs], coverage.extract_origin(crs)
            )
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
        # The identity the service-week facts are keyed by, so a worker
        # reuses the journeys the last build searched rather than searching
        # them again (T9). The fares feed is read from the per-origin index
        # files, not from here, so it needs no identity in this dict.
        "timetable_identity": timetable_identity,
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
    by_slug = {entry["slug"]: entry["crs"] for entry in index}
    # Resume is for every build, not only the prices-only parallel one: a
    # timetabled build that dies at page 900 starts again at page one without
    # it (T3). The signature already excludes the build stamp, so the key is
    # the inputs with builtAt masked rather than the files' bytes.
    state_path = out_dir / BUILD_STATE_NAME
    signature = resumable_signature(shared, index)
    completed, page_places = read_resume_state(state_path, signature)
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
    rewritten = 0
    unchanged = 0
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

    def publish_result(result: tuple[str, str, str, int]) -> None:
        nonlocal built_now, rewritten, unchanged
        slug, origin_name, html, places = result
        page = out_dir / "from" / slug / "index.html"
        # A rebuild whose inputs did not move rewrites nothing: the stamp is
        # masked, so only a page whose answers changed is written again (T3).
        # The progress record is written either way, so a build that changed
        # nothing still resumes as complete.
        if page_is_current(page, html):
            unchanged += 1
            verb = "unchanged"
        else:
            write_page_atomic(page, html)
            rewritten += 1
            verb = "wrote"
        built_now += 1
        completed.add(slug)
        page_places[by_slug[slug]] = places
        write_resume_state(state_path, signature, completed, page_places)
        if args.fast_all_origins:
            print(
                f"[{built_now}/{len(jobs)}] "
                f"{verb} {slug} from {origin_name}",
                flush=True,
            )
        else:
            print(f"{verb} {page} from {origin_name}", flush=True)

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
    # The chooser's index, with the counts as the pages reported them. The
    # counts the index was planned with stay where they were: they are the write
    # set's question (can this page answer at all, ADR-0019 decision 3), they
    # are cached and replayed as that, and a resumed build replans from them.
    # What changes here is only the number a reader is shown.
    index = [
        {**entry, "destinations": page_places.get(entry["crs"], entry["destinations"])}
        for entry in index
    ]
    if args.fast_all_origins:
        print(f"station pages complete: {len(completed):,}/{len(index):,}", flush=True)
    # Always said, including the all-resumed build that wrote nothing: the
    # incremental answer is the point, and "rewrote nothing" is a result worth
    # reading rather than an absence worth wondering about. Zero rewritten is
    # the expected line on a second build of the same feeds (T3).
    print(f"pages rewritten: {rewritten:,}, unchanged: {unchanged:,}", flush=True)
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
    # The release's own routes: one writer for both build shapes, and what it
    # writes is write_release's own subject.
    write_release(
        out_dir,
        index=index,
        routes=[with_base(base_path, f"/from/{slug}/") for slug in sorted(written)],
        budget_pounds=OPENING_BUDGET_POUNDS,
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
    if shard is not None:
        # What the merge proves: which share this was, what it was built
        # from, which origins that meant, and what each priced -- the counts
        # the union index is built from and the coverage the union report
        # replays, so neither is queried again at merge time (T4).
        number, total = shard
        write_page_atomic(
            out_dir / SHARD_MANIFEST_NAME,
            json.dumps(
                {
                    "schema": SHARD_MANIFEST_SCHEMA,
                    "shard": number,
                    "of": total,
                    "inputs": shard_agreement(shared),
                    "built_at": shared["built_at"],
                    "origins": origins,
                    "index": index,
                    "coverage": {
                        crs: coverage.extract_origin(crs) for crs in origins
                    },
                    "release": {
                        "budget_pounds": OPENING_BUDGET_POUNDS,
                        "note": note,
                        "price_source": price_source,
                        "feed_date": feed_date,
                        "analytics": analytics,
                        "synthetic": synthetic,
                        "privacy_contact": privacy_contact,
                        "features": features,
                        "base_path": base_path,
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        print(f"wrote {out_dir / SHARD_MANIFEST_NAME} (share {number}/{total} of this split)")
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
    # The one station this site serves, and the places its page carries -- read
    # off the page rather than counted again, so the chooser's number is the
    # page's number by construction (see ``places_in_payload``).
    index = build_station_index(
        {payload_origin: places_in_payload(payload)}, fares.locations_by_crs
    )
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
                budget_pounds=OPENING_BUDGET_POUNDS,
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
    # The release's own routes, through the same writer as the other shape.
    write_release(
        out_dir,
        index=index,
        routes=[entry["href"] for entry in routes],
        budget_pounds=OPENING_BUDGET_POUNDS,
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
