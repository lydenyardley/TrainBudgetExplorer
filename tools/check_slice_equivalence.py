"""Check that a slice answers every page question the whole feed does.

`atoc_timetable.TimetableDb.focused(origin)` cuts the part of the timetable one
page can use out of the database a build already holds, and the pages it was
measured against did not move a byte. Two stations on one date is not the claim
the slice makes, though. The claim is that for **any** origin and **any** day of
the service week, the questions a page asks of the slice have the same answers as
the same questions asked of the whole feed. A page is assembled from those
answers, so a difference is a page that says something the whole feed would not
have said: a journey time that moved, a destination that appeared or vanished, or
two-ticket pricing that split at a different calling point.

This tool asks both. For each origin and each day it walks
`journeys_from(origin, day)` on the whole database and on the slice, and compares
the answers destination by destination: the departure, the arrival, the change
count and every leg's train, ends and times. It also compares `service_window()`
and `stats()`, which the page carries and a reader reads as a claim about the
feed.

    python -m tools.check_slice_equivalence --timetable feeds/timetable --probe 5
    python -m tools.check_slice_equivalence --timetable feeds/timetable \\
        --date 2026-10-07 --days 7 --progress _cache/slice-equivalence.json
    python -m tools.check_slice_equivalence --timetable feeds/timetable --origins GRA,NOT --limit 2
    python -m tools.check_slice_equivalence --timetable feeds/timetable --shard 1/8
    python -m tools.check_slice_equivalence --timetable feeds/timetable --merge 8
    python -m tools.check_slice_equivalence --timetable feeds/timetable --shards auto

The sweep is hours of CPU on the real feed, so it checkpoints every origin and
resumes: run it again with the same `--progress` file and it skips the pairs it
has already compared. `--probe N` times the first N origins and prints the
projected total instead of running it.

`--shard N/M` compares only its own share of the request -- origins N, N+M,
N+2M ... of the request's origin list, which is the feed's own sorted list
unless `--origins` named an order -- and checkpoints to a file of its own beside the
base one, so M shards can run side by side without sharing a byte of state.
`--merge M` reads those M files, refuses a union that is not the request they
agree they were given, and prints the one verdict a single run would have
printed. A merge reads no feed at all: the shards record the request, so the
merge costs a second rather than a minute. The shards are disjoint by
construction, and the merge checks that partition rather than trusting it: a
shard asked a different question, a shard whose pairs are not the origin-days it
records, or two shards that overlap are refused rather than counted as coverage.

`--shards M` is the whole sweep in one invocation: it starts M children, streams
their output prefixed with their shard number, and merges them. `--shards auto`
asks the machine instead -- cores, narrowed by free memory divided by what one
shard holds (1,870 MB of index) -- and never answers less than one, because a
machine that cannot hold two still sweeps, one share at a time. A child that
falls silent for `--shard-timeout` seconds (default 1,800) is killed rather than
hung on, and the merge that follows reports its share as still to compare. A
shard starts from the answers the base checkpoint already holds about its own
share, so a sharded run of a request an unsharded sweep has partly asked does
not ask it again, and a merge keeps the base's pairs that its request was not
about.

**What a shard costs to hold.** Each shard parses the feed and holds its own
index -- 1.87 GB on the national download -- so how many fit beside each other
is a memory question before it is a CPU one.

Exit codes: 0 every compared pair agreed, 1 at least one pair differed and every
difference is named, 2 the feed could not be read or nothing was compared.

**What this compares.** By default every leg of every journey the page would
show, so `intermediate_crs` -- the ADR-0061 question about the calling points
between a leg's ends -- is asked for each one on both databases. `--max-legs`
bounds that to a deterministic spread when a quick run is wanted, and the answer
it gives is then a sample of that one question rather than of the whole sweep.

**What it does not compare.** `day=None` (an undated build, which reads every
schedule in the feed) is not one of the compared days, and the sweep asks about
origins the feed can be asked about rather than about every station a page could
be published for.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import date, timedelta
from pathlib import Path


from atoc_timetable import TimetableDb
from build_workers import RESERVED_BYTES, free_memory_bytes

#: The service week the harness compares unless told otherwise. The build's own
#: date, so a failure names a day a page was actually assembled for.
DEFAULT_DATE = "2026-10-07"

#: Legs per origin-day whose `intermediate_crs` is compared. None means every
#: leg of every journey the page would show, which is the complete question and
#: is affordable because `TimetableDb` keeps a train-identity index for the day:
#: before that index existed this call read the day's whole schedule list, 0.6s
#: on the real feed, and a sample was the only way to ask it at scale.
DEFAULT_MAX_LEGS: int | None = None

#: What one shard holds: the whole feed's index, measured at **1,870 MB** for
#: 419,589 schedules (`docs/build-performance-findings.md`). A shard parses the
#: feed for itself rather than sharing one, so this is the divisor the automatic
#: shard count comes from -- the work is CPU-bound only once it fits in memory.
SHARD_INDEX_MB = 1_870

#: Extra headroom subtracted beyond RESERVED_BYTES to avoid paging when memory
#: snapshots are slightly stale or when indexes grow during parsing. This is
#: safety margin, not part of the measured figure: the per-shard hold is the
#: measurement, and this is the buffer that keeps a plan that fits on paper from
#: paging on the machine.
SHARD_SAFETY_MARGIN_MB = 512

#: Seconds a launcher waits for one line from a child before killing it. A
#: shard's own progress line comes every 25 origin-days, and the slowest
#: origin-day ever measured on this request (9.32 s, against 2.45 s on average
#: -- 8 October 2026, the figures in `docs/build-performance-findings.md`)
#: puts that gap at about four minutes, with the feed's 58.0 s load before the
#: first line of all. Silence for half an hour is a hung child, not a slow
#: one, and a hung child would otherwise hold the launcher for ever while the
#: merge that would report it never runs. Zero disables the wait for a run
#: that would rather hang than lose a child.
SHARD_TIMEOUT_SECONDS = 1800

#: Told apart from `None`: leaving `free_bytes` out means "read it here", and
#: `None` means "this platform would not say", which are different answers from
#: `shard_budget`.
_UNREAD = object()

#: A ceiling for the fallback when the platform will not report free memory. A
#: policy rather than a measurement, and a low one: many copies of a 1.87 GB
#: index is a way to make a machine stop responding.
MAX_AUTO_SHARDS = 8

#: Differences named per origin-day before the rest are counted instead.
DIFFERENCES_SHOWN = 5


def week_days(start: date, count: int) -> list[date]:
    """Seven consecutive service dates from ``start``, in order."""
    return [start + timedelta(days=offset) for offset in range(count)]


def _journey_line(journey) -> str:
    legs = ";".join(
        f"{leg.train_uid}>{leg.origin_crs}>{leg.destination_crs}@{leg.departure}-{leg.arrival}"
        for leg in journey.legs
    )
    return f"{journey.departure}-{journey.arrival}/{journey.changes}/{legs}"


def sampled_legs(
    destinations: list[str], reached: dict, max_legs: int | None
) -> list[tuple[str, str, str]]:
    """The legs to ask `intermediate_crs` about: all of them, or a spread of them.

    ``None`` is every leg of every journey -- the page asks this once per leg it
    shows, so that is the whole question. A number takes every k-th destination's
    legs, which covers the list rather than its alphabetical head, and takes the
    same ones every run so a difference is reproducible rather than a different
    draw each time.
    """
    if max_legs == 0 or not destinations:
        return []
    if max_legs is None:
        chosen = list(destinations)
    else:
        if max_legs < 0:
            return []
        step = max(1, len(destinations) // max_legs)
        chosen = destinations[::step][:max_legs]
    legs: list[tuple[str, str, str]] = []
    for crs in chosen:
        journey = reached.get(crs)
        if journey is None:
            continue
        for leg in journey.legs:
            legs.append((leg.train_uid, leg.origin_crs, leg.destination_crs))
    return legs


def answers(db: TimetableDb, origin: str, day: date, max_legs: int | None) -> dict[str, str]:
    """Every page question about one origin on one day, as comparable strings.

    The keys are the destination codes plus three the page also reads:
    ``__legs__`` for the sampled in-between calling points, ``__window__`` for the
    service window and ``__stats__`` for the counts the page reports.
    """
    reached = db.journeys_from(origin, day=day)
    found = {crs: _journey_line(journey) for crs, journey in reached.items()}
    for train_uid, from_crs, to_crs in sampled_legs(sorted(reached), reached, max_legs):
        found[f"__leg__{train_uid}>{from_crs}>{to_crs}"] = ",".join(
            db.intermediate_crs(train_uid, from_crs, to_crs, day=day)
        )
    first, last = db.service_window()
    found["__window__"] = f"{first}-{last}"
    stats = db.stats()
    found["__stats__"] = ",".join(f"{key}={stats[key]}" for key in sorted(stats))
    return found


def compare_origin(
    db: TimetableDb,
    origin: str,
    day: date,
    max_legs: int | None = DEFAULT_MAX_LEGS,
) -> list[str]:
    """Differences between the whole feed's answers and the slice's, or empty.

    A slice is cut here rather than reused, because the database it is cut from
    is the one being asked the other half of the question and only one slice is
    held at a time. The cut costs a quarter of a second once the TIPLOC index
    exists, against the minutes of parsing the whole feed would cost.
    """
    whole = answers(db, origin, day, max_legs)
    slice_db = db.focused(origin)
    sliced = answers(slice_db, origin, day, max_legs)
    differences: list[str] = []
    for key in sorted(set(whole) | set(sliced)):
        if whole.get(key) != sliced.get(key):
            differences.append(f"{key}: whole={whole.get(key)!r} slice={sliced.get(key)!r}")
    return differences


def feed_origins(db: TimetableDb) -> list[str]:
    """Every station code the feed can be asked about, sorted."""
    codes = {station.crs for station in db.stations_by_tiploc.values() if station.crs}
    codes.update(crs for crs in db.cif_crs_by_tiploc.values() if crs)
    return sorted(codes)


def load_progress(path: Path) -> dict:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"pairs": {}, "differences": {}}


def save_progress(path: Path, progress: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(progress, indent=1, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _pair_key(origin: str, day: date) -> str:
    return f"{origin}|{day.isoformat()}"


def requested_pairs(origins: list[str], days: list[date]) -> list[str]:
    """The origin-days this run is about, in the order it compares them.

    The checkpoint outlives the request: an earlier run's `--limit`, `--origins`
    or single day leaves pairs in the file that this run was never asked about.
    Every count here is over these keys rather than over the file, so a coverage
    line is about the question asked and cannot report more compared than there
    is to compare.
    """
    return [_pair_key(origin, day) for day in days for origin in origins]


def parse_shard(text: str) -> tuple[int, int]:
    """`N/M` as a 1-based (index, count), or a ValueError saying why not.

    One flag rather than two, so the index and the count cannot disagree about
    which run this is: a shard checkpoint names both, and a merge reads both
    back out of it rather than being told them a second time.
    """
    left, _, right = text.partition("/")
    if not left.isdigit() or not right.isdigit():
        raise ValueError(f"--shard {text!r} is not N/M")
    index, count = int(left), int(right)
    if count < 1 or not 1 <= index <= count:
        raise ValueError(f"--shard {text!r} is not a share of a run: M at least 1, N in 1..M")
    return index, count


def shard_origins(origins: list[str], index: int, count: int) -> list[str]:
    """Shard N of M's share of the request: disjoint, and together the request.

    Every M-th origin from N-1, so the shares cover the sorted list exactly once
    and the work a shard holds does not move when another shard finishes first.
    """
    return origins[index - 1 :: count]


def shard_progress_path(base: Path, index: int, count: int) -> Path:
    """The checkpoint one shard owns, beside the base one.

    Named rather than numbered: a file called `slice-equivalence.3.json` says
    nothing about which run wrote it or how many there were, and a merge has to
    be able to refuse a shard that came from a run of a different size.
    """
    return base.with_name(f"{base.stem}.shard-{index}-of-{count}{base.suffix or '.json'}")


def shard_budget(cores: int | None = None, free_bytes: int | None | object = _UNREAD) -> int:
    """How many shards fit here: the cores there are, narrowed by memory.

    Each shard parses the feed for itself and holds its own index, so the
    ceiling that binds is free memory divided by `SHARD_INDEX_MB`, and that
    division is only sound because the divisor is a measurement -- the same
    reason `build_workers.worker_budget` divides, and the same warning it
    carries: a divisor smaller than what one process really holds hands out
    roughly the multiple of shards the machine cannot carry.

    Two GB comes off the top first, `build_workers.RESERVED_BYTES`, for the same
    reason a build's parent keeps it: the operating system, the editor and the
    browser that are already open. Without it the division is right and the
    answer is still wrong -- measured once on this machine, when 3.9 GB free and
    a two-shard plan left 0.3 GB and paged.

    Five hundred twelve MB of headroom on top of that, `SHARD_SAFETY_MARGIN_MB`,
    because a memory snapshot is a point in time and the index grows while a
    child parses the feed, so a plan that leaves the machine close enough to the
    line still pages when the children allocate. The margin is a safety buffer,
    not part of the measured hold: the number one shard holds is the measurement;
    this is the gap that keeps that measurement from being exactly the number the
    machine can count on.

    Never zero. A machine that cannot hold two still sweeps, one share at a
    time, paging; saying so and starting is better than refusing.
    """
    cores = cores or os.cpu_count() or 1
    if free_bytes is _UNREAD:
        free_bytes = free_memory_bytes()
    if free_bytes is None:
        # The platform will not say. The cores are the only ceiling left, and
        # the fallback is capped because a number this machine cannot count is
        # not a licence to start thirty copies of an index.
        return max(1, min(cores, MAX_AUTO_SHARDS))
    usable = free_bytes - RESERVED_BYTES - (SHARD_SAFETY_MARGIN_MB * 1_000_000)
    if usable <= 0:
        usable = 1
    holdable = int(usable / (SHARD_INDEX_MB * 1_000_000))
    return max(1, min(cores, holdable))


def base_pairs_for(progress: dict, origins: list[str], days: list[date]) -> dict[str, str]:
    """The base checkpoint's answers about this share, keyed by origin-day.

    A shard's own file is empty the first time it runs, and the base checkpoint
    of earlier unsharded sweeps may already hold hundreds of this share's
    origin-days. They are answers to this question if the days and the legs
    bound are the same, which is what the caller checks before calling here:
    this only picks out the ones inside the share.
    """
    allowed = {_pair_key(origin, day) for origin in origins for day in days}
    return {
        key: value
        for key, value in (progress.get("pairs") or {}).items()
        if key in allowed
    }


def shard_request(progress: dict) -> tuple:
    """The question a checkpoint was made against, for a merge to compare.

    `max_legs` is part of it for the reason the resume guard exists: a pair
    compared with a bounded sample of calling points is not evidence about the
    complete question, and a shard asked the weaker one is not a shard of this
    run.
    """
    return (
        progress.get("timetable"),
        tuple(progress.get("days") or ()),
        progress.get("max_legs", "unrecorded"),
        tuple(progress.get("request_origins") or ()),
    )


def merge_shard_checkpoints(base: Path, count: int) -> tuple[dict, list[str]]:
    """The M shard checkpoints as one, and every reason they are not those M.

    The request is read from the shards rather than recomputed from the feed: a
    merge that parsed the feed would spend a minute and hold an index to learn
    what the files already say, and the thing worth checking is that they agree
    about it. The first file that records a request sets it, every other file is
    compared against that, and the shards' own origins have to be disjoint and
    together that request. Anything else is a reason, and a reason is an exit 2
    rather than a verdict.
    """
    problems: list[str] = []
    read: list[str] = []
    shards: list[tuple[int, str, dict]] = []
    for index in range(1, count + 1):
        path = shard_progress_path(base, index, count)
        if not path.is_file():
            problems.append(f"shard {index} of {count} has no checkpoint at {path}")
            continue
        progress = load_progress(path)
        if "origins" not in progress or "request_origins" not in progress:
            problems.append(
                f"{path.name} records no request, so it cannot say what it is a share of "
                "(a checkpoint written before the sweep had shards?)"
            )
            continue
        read.append(path.name)
        shards.append((index, path.name, progress))
    merged: dict = {"schema": 1, "pairs": {}, "differences": {}, "shards": count}
    if not shards:
        problems.append(f"no shard checkpoint beside {base} to merge")
        return merged, problems

    request = shard_request(shards[0][2])
    merged["timetable"] = request[0]
    merged["days"] = list(request[1])
    merged["max_legs"] = request[2]
    merged["request_origins"] = list(request[3])
    days = [date.fromisoformat(day) for day in request[1]]
    owner: dict[str, int] = {}
    for index, name, progress in shards:
        if shard_request(progress) != request:
            problems.append(
                f"{name} was made against another request "
                f"({len(progress.get('request_origins') or [])} origins, "
                f"{len(progress.get('days') or [])} days, "
                f"max_legs={progress.get('max_legs', 'unrecorded')!r}); "
                "it is not evidence about this one"
            )
            continue
        own = list(progress["origins"])
        for origin in own:
            if origin in owner:
                problems.append(
                    f"{origin} is in shard {owner[origin]} and shard {index}, so the shards overlap"
                )
            owner[origin] = index
        allowed = {_pair_key(origin, day) for origin in own for day in days}
        for key in progress.get("pairs", {}):
            if key not in allowed:
                problems.append(
                    f"{name} holds {key}, which is not one of the origin-days it records"
                )
        merged["pairs"].update(progress.get("pairs") or {})
        merged["differences"].update(progress.get("differences") or {})
    unowned = [origin for origin in request[3] if origin not in owner]
    if unowned:
        problems.append(
            f"{len(unowned)} origin(s) of the request are in no shard, starting {unowned[0]}"
        )
    strangers = [origin for origin in owner if origin not in set(request[3])]
    if strangers:
        problems.append(
            f"{len(strangers)} origin(s) are in a shard and not in this request, "
            f"starting {strangers[0]}"
        )
    merged["origins"] = list(request[3])
    merged["merged_from"] = read
    return merged, problems


def verdict(
    progress: dict,
    origins: list[str],
    days: list[date],
    compared: int,
    note: str,
    checkpoint: Path,
) -> int:
    """The one exit code, and the lines that explain it, over the request.

    One owner for both a run and a merge: the verdict is about the request
    rather than about the process that produced the pairs, so a sweep resumed to
    the end of its work compares nothing and has still concluded, and a merge
    that read M files has concluded about the union of them. What decides is
    whether every pair asked for is in the pairs, and what it says.
    """
    print(coverage(progress, origins, days), flush=True)
    print(f"checkpoint: {checkpoint.resolve()}", flush=True)
    requested = requested_pairs(origins, days)
    pairs = progress.get("pairs") or {}
    outcomes = [pairs.get(key) for key in requested]
    differing = [value for value in outcomes if value not in (None, "ok")]
    if differing:
        print(f"{len(differing)} origin-day(s) did not agree or could not be compared", flush=True)
        return 1
    missing = sum(1 for value in outcomes if value is None)
    if missing:
        print(f"{missing} origin-day(s) still to compare", flush=True)
        return 2
    if not requested:
        print("no origins to compare", flush=True)
        return 2
    print(
        f"every origin-day asked for agreed ({len(requested):,} {note}: {compared:,})",
        flush=True,
    )
    return 0


def compared_counts(progress: dict, origins: list[str], days: list[date]) -> tuple[int, int]:
    """Of the request's origin-days, how many agreed and how many did not.

    The request, not the file: a checkpoint holds every pair written into it by
    every run that has shared it, and a run asked for two origins after a run
    asked for one has to count arithmetically. Both the coverage line and the
    estimate of what is left are this count.
    """
    pairs = progress.get("pairs", {})
    requested = requested_pairs(origins, days)
    done = sum(1 for key in requested if pairs.get(key) == "ok")
    failed = sum(1 for key in requested if pairs.get(key) not in (None, "ok"))
    return done, failed


def coverage(progress: dict, origins: list[str], days: list[date]) -> str:
    """What has been compared, as one line, so a partial sweep says so plainly."""
    pairs = progress.get("pairs", {})
    requested = requested_pairs(origins, days)
    done, failed = compared_counts(progress, origins, days)
    named = sum(
        1
        for origin in origins
        if all(pairs.get(_pair_key(origin, day)) == "ok" for day in days)
    )
    return (
        f"{done + failed:,} of {len(requested):,} origin-days compared"
        f" ({named:,} of {len(origins):,} origins complete, {failed:,} differing)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The timetable and nothing else: every question this asks is a timetable
    # question, and loading the fares feed would put two gigabytes beside the
    # index for no answer the sweep did not already have.
    parser.add_argument(
        "--timetable",
        type=Path,
        default=None,
        help="CIF timetable feed folder or zip (required unless --merge, which reads the shards' own record of the request)",
    )
    parser.add_argument("--date", default=DEFAULT_DATE, help="first service date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=7, help="how many days from --date")
    parser.add_argument("--origins", default=None, help="comma-separated codes, default every station")
    parser.add_argument("--limit", type=int, default=None, help="stop after this many origins")
    parser.add_argument(
        "--max-legs",
        type=int,
        default=DEFAULT_MAX_LEGS,
        help="legs whose calling points are compared per origin-day (default: every leg; 0 to skip)",
    )
    parser.add_argument("--progress", type=Path, default=Path("_cache/slice-equivalence.json"), help="checkpoint file, resumed on the next run; a shard writes its own beside it and --merge reads all of them")
    parser.add_argument("--probe", type=int, default=None, help="time this many origins and print the projection")
    parser.add_argument("--shard", default=None, metavar="N/M", help="compare only share N of M disjoint origin sets, checkpointing to a file of its own")
    parser.add_argument("--merge", type=int, default=None, metavar="M", help="merge M shard checkpoints into one verdict, reading no feed")
    parser.add_argument("--shards", default=None, metavar="M|auto", help="run M shards as children and merge them: one invocation for a whole sweep, or 'auto' for what this machine holds")
    parser.add_argument(
        "--shard-timeout",
        type=int,
        default=SHARD_TIMEOUT_SECONDS,
        help="seconds without a line from one child before the launcher kills it and the merge reports its share; 0 waits for ever",
    )
    args = parser.parse_args(argv)
    if args.shard_timeout < 0:
        # A negative number would take the timeout's `> 0` branch the same way
        # zero does -- silently waiting for ever, which the help does not
        # offer and a hung sweep would not be told about.
        print("--shard-timeout must be at least 0 seconds (0 waits for ever)", flush=True)
        return 2
    raw = list(argv) if argv is not None else sys.argv[1:]

    # One of the four shapes of a run, and no pair of them means anything: a
    # share, the launcher that starts M shares, the merge that concludes about
    # them, and the probe that only times origins.
    selected = [
        name
        for name, value in (
            ("--shard", args.shard),
            ("--shards", args.shards),
            ("--merge", args.merge),
            ("--probe", args.probe),
        )
        if value is not None
    ]
    if len(selected) > 1:
        print(f"{' and '.join(selected)} are different runs; give one", flush=True)
        return 2

    shard = None
    if args.shard:
        try:
            shard = parse_shard(args.shard)
        except ValueError as error:
            print(str(error), flush=True)
            return 2

    feed = Path(args.timetable) if args.timetable is not None else None
    if args.merge is None and feed is None:
        print("no --timetable given: a sweep needs a feed to ask", flush=True)
        return 2
    if feed is not None and not feed.exists():
        print(f"no timetable feed at {feed}", flush=True)
        return 2
    days = week_days(date.fromisoformat(args.date), args.days)
    if args.merge is not None:
        return _merge(args.progress, args.merge)

    free = free_memory_bytes()
    if args.shards is not None:
        try:
            count = shard_count(args.shards, free_bytes=free)
        except ValueError as error:
            print(str(error), flush=True)
            return 2
        if free is not None and count > 1:
            want = count * (SHARD_INDEX_MB + SHARD_SAFETY_MARGIN_MB) / 1000
            have = (free - RESERVED_BYTES) / 1e9
            print(
                f"{count} shard(s): {count * SHARD_INDEX_MB / 1000:.1f} GB of index each, "
                f"plus {SHARD_SAFETY_MARGIN_MB / 1000:.1f} GB headroom; "
                f"about {want:.1f} GB wanted, {have:.1f} GB free after reserve; "
                f"so {count} shard(s)",
                flush=True,
            )

        # The count-and-capacity line is `_shards`'s to print: said here as
        # well, the launcher's first two lines were the same line twice.
        return _shards(args, without_flag(raw, "--shards"), count, free)

    print(f"Loading timetable feed from {feed} ...", flush=True)
    started = time.monotonic()
    db = TimetableDb().load_feed(feed)
    print(
        f"Loaded timetable: {db.stats()['schedules']:,} schedules, "
        f"{db.stats()['calling_points']:,} calling points in {time.monotonic() - started:.1f}s",
        flush=True,
    )

    origins = (
        [code.strip().upper() for code in args.origins.split(",") if code.strip()]
        if args.origins
        else feed_origins(db)
    )
    if args.limit is not None:
        origins = origins[: args.limit]
    # The request is the whole set, whatever share this process carries: every
    # shard records it, which is how a merge tells a shard of this run from a
    # checkpoint of an earlier, narrower one.
    request_origins = list(origins)
    checkpoint = args.progress
    if shard:
        index, count = shard
        origins = shard_origins(origins, index, count)
        checkpoint = shard_progress_path(args.progress, index, count)
    legs_note = (
        "every leg of every journey" if args.max_legs is None else f"{args.max_legs} legs sampled"
    )
    if shard:
        print(
            f"shard {shard[0]} of {shard[1]}: {len(origins):,} of {len(request_origins):,} "
            f"origin(s) x {len(days)} day(s), {legs_note}",
            flush=True,
        )
        # The shards share no state, so the count that fits is a memory
        # question, and it is the same warning `build_workers` prints before a
        # build: say what this machine has rather than let the paging be
        # discovered in the timing.
        print(
            f"  each shard parses the feed for itself, and the national download's "
            f"index is {SHARD_INDEX_MB / 1000:.2f} GB (measured), so {shard[1]} shard(s) "
            f"want about {shard[1] * SHARD_INDEX_MB / 1000:.1f} GB of index; "
            f"{free_memory_bytes() / 1e9:.1f} GB is free here now",
            flush=True,
        )
    else:
        print(f"{len(origins):,} origin(s) x {len(days)} day(s), {legs_note}", flush=True)

    if args.probe:
        return _probe(db, origins, days, args)

    progress = load_progress(checkpoint)
    # A checkpoint answers the question it was made against. `--max-legs`
    # bounds which calling points were compared, so pairs compared under one
    # bound are not evidence about another: a quick sampled run leaving 26,369
    # pairs behind would let a full sweep report every origin-day agreed while
    # having asked the weakest form of the question.
    if progress.get("pairs") and progress.get("max_legs", "unrecorded") != args.max_legs:
        print(
            f"the checkpoint holds {len(progress['pairs']):,} pair(s) compared with "
            f"max_legs={progress.get('max_legs', 'unrecorded')!r}, not {args.max_legs!r}; "
            "they are the other question and are not carried over",
            flush=True,
        )
        progress = {"pairs": {}, "differences": {}}
    progress.setdefault("pairs", {})
    progress.setdefault("differences", {})
    progress["schema"] = 1
    progress["timetable"] = str(args.timetable)
    progress["days"] = [day.isoformat() for day in days]
    progress["max_legs"] = args.max_legs
    # What this file is a share of, so a merge can check the partition instead
    # of trusting it: the origins it holds, and the request they are a share of.
    progress["origins"] = list(origins)
    progress["request_origins"] = list(request_origins)
    if shard:
        progress["shard"] = {"index": shard[0], "count": shard[1]}
        # A base checkpoint's answers about this share are this share's answers:
        # a sharded run of an unsharded sweep's request must not compare a pair
        # the base already compared, which is hours of the sweep. Only pairs the
        # shard does not already hold, so a shard's own verdict wins.
        base = load_progress(args.progress)
        if (base.get("pairs") or {}) and base.get("max_legs", "unrecorded") == args.max_legs:
            inherited = base_pairs_for(base, origins, days)
            if inherited:
                for key, value in inherited.items():
                    progress["pairs"].setdefault(key, value)
                for key, value in (base.get("differences") or {}).items():
                    if key in inherited:
                        progress["differences"].setdefault(key, value)
                print(
                    f"  {len(inherited):,} of this share's origin-days are already in "
                    f"{args.progress.name} and are carried over",
                    flush=True,
                )
        if not origins:
            # A share is empty when M is larger than the origins there are. That
            # is not the same as a request with nothing in it: a child asked for
            # nothing is not a shard that failed, so it records what it was a
            # share of and leaves the merge to conclude.
            save_progress(checkpoint, progress)
            print(
                f"shard {shard[0]} of {shard[1]} holds none of the "
                f"{len(request_origins):,} origins asked for: nothing to compare",
                flush=True,
            )
            return 0
    compared = 0
    sweep_started = time.monotonic()
    for day in days:
        # One index build for the whole feed per day rather than one per origin:
        # `_ensure_indexes` is the largest per-call cost in the whole sweep when
        # the day changes, and it does not change for a whole day of this loop.
        db._ensure_indexes(day)
        for origin in origins:
            key = _pair_key(origin, day)
            if key in progress["pairs"]:
                continue
            started = time.monotonic()
            try:
                differences = compare_origin(db, origin, day, args.max_legs)
            except Exception as error:  # noqa: BLE001 - reported, then the sweep continues
                progress["pairs"][key] = "error"
                progress["differences"][key] = [f"{type(error).__name__}: {error}"]
                print(f"{key}: RAISED {type(error).__name__}: {error}", flush=True)
                save_progress(checkpoint, progress)
                continue
            compared += 1
            if differences:
                progress["pairs"][key] = "differs"
                progress["differences"][key] = differences
                print(
                    f"{key}: {len(differences)} difference(s)\n  "
                    + "\n  ".join(differences[:DIFFERENCES_SHOWN]),
                    flush=True,
                )
                if len(differences) > DIFFERENCES_SHOWN:
                    print(f"  ... {len(differences) - DIFFERENCES_SHOWN} more", flush=True)
            else:
                progress["pairs"][key] = "ok"
            if compared % 25 == 0:
                save_progress(checkpoint, progress)
                # Over the whole run, not over this origin: a rate computed from
                # the origin that happened to be last reported 0.01s and 0.37s
                # for the same sweep, which is a number that tells a reader
                # nothing about how long the work takes.
                per_origin_day = (time.monotonic() - sweep_started) / compared
                done, failed = compared_counts(progress, origins, days)
                remaining = len(requested_pairs(origins, days)) - (done + failed)
                print(
                    f"{coverage(progress, origins, days)}; {per_origin_day:.3f}s per "
                    f"origin-day, about {per_origin_day * remaining / 60:.0f} min left",
                    flush=True,
                )
        save_progress(checkpoint, progress)
        print(f"{day.isoformat()}: {coverage(progress, origins, days)}", flush=True)

    save_progress(checkpoint, progress)
    return verdict(progress, origins, days, compared, "compared this run", checkpoint)


def without_flag(argv: list[str], flag: str) -> list[str]:
    """`argv` without `flag` and its value, however the value was written.

    A launcher passes the run it was given to each child, and `--shards` is the
    only part of it a child must not see: the child is one share of it.
    """
    kept: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == flag:
            index += 2
            continue
        if argv[index].startswith(flag + "="):
            index += 1
            continue
        kept.append(argv[index])
        index += 1
    return kept


def shard_count(
    text: str, cores: int | None = None, free_bytes: int | None | object = _UNREAD
) -> int:
    """`--shards M` as a number, or `auto` as the number this machine holds."""
    if text == "auto":
        return shard_budget(cores=cores, free_bytes=free_bytes)
    if not text.isdigit() or int(text) < 1:
        raise ValueError(f"--shards {text!r} is not M or 'auto'")
    return int(text)


def _shards(args, run_argv: list[str], count: int, free: int | None) -> int:
    """M children, each with its own share, then the one verdict over all of them.

    Each child is this program run as `--shard i/M`, so a share is exactly the
    run documented above and nothing here needs to know how a share is compared.

    The children all start at once and their output is streamed as it arrives,
    each line prefixed with its shard number: M processes writing progress to
    the same terminal line by line would be unreadable, and holding it until
    the end would hide a four-hour sweep for four hours. The children are
    drained all at once rather than one after another -- `_stream` says why
    that is not a readability preference but whether they keep working.

    A child that exits non-zero is not a reason to skip the merge: a 1 is a
    difference it found, which is evidence, and a 2 is a share it could not
    finish, which the merge reports as still to compare. The verdict is the
    merge's to give, and it is given either way.
    """
    cores = os.cpu_count() or 1
    if free is None:
        print(
            f"{count} shard(s): this platform will not report free memory, so the "
            f"count is capped by the {cores} core(s) here",
            flush=True,
        )
    else:
        print(
            f"{count} shard(s): {cores} core(s) and {free / 1e9:.1f} GB free, "
            f"{SHARD_INDEX_MB / 1000:.2f} GB of index each",
            flush=True,
        )
    children: list[tuple[int, subprocess.Popen]] = []
    for index in range(1, count + 1):
        # `-m`, not the script's path: a child started as `python tools/x.py`
        # would have tools/ on its path rather than the project root, and every
        # import of a project module would fail in it (the same reason the tool
        # itself is run as `python -m tools.check_slice_equivalence`).
        command = [
            sys.executable,
            "-m",
            "tools.check_slice_equivalence",
            *run_argv,
            "--shard",
            f"{index}/{count}",
        ]
        print(f"  $ {' '.join(command)}", flush=True)
        children.append(
            (
                index,
                subprocess.Popen(
                    command,
                    cwd=Path(__file__).resolve().parents[1],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                ),
            )
        )
    _stream(children, count, args.shard_timeout)
    return _merge(args.progress, count)


def _stream(
    children: list[tuple[int, subprocess.Popen]],
    count: int,
    timeout: int = SHARD_TIMEOUT_SECONDS,
) -> None:
    """Every child's output at once, each line prefixed with its shard number.

    Not one child after another. An OS pipe holds about 4 KB -- measured on
    this machine, where a writer with no reader blocked after three writes --
    and a shard writes more than that long before it finishes, so a child whose
    turn has not come blocks in write() and stops comparing: draining the
    children in sequence would turn M parallel shares into their sum, decided
    by the order they were started in. The prefix is what makes the interleaved
    lines readable, and one lock around each line keeps a line whole.

    A child that stops producing lines for `timeout` seconds is killed (0 waits
    for ever). Silence is the shape a hung child has: it holds its index, it
    compares nothing, and without this the launcher would wait on it for ever
    and the merge that would report its share as still to compare would never
    run. What the killed child did write survives in its checkpoint.
    """
    lock = threading.Lock()
    spoken_at: dict[int, float | None] = {
        index: time.monotonic() for index, _ in children
    }
    by_index = dict(children)

    def drain(index: int, child: subprocess.Popen) -> None:
        # wait() in a finally, or a read that raises kills this thread and the
        # launcher would merge while that child is still comparing: a thread
        # that dies is invisible to join(), a child that was never waited is
        # not.
        try:
            if child.stdout is not None:
                with child.stdout:
                    for line in child.stdout:
                        with lock:
                            spoken_at[index] = time.monotonic()
                            sys.stdout.write(f"[shard {index}] {line.rstrip()}\n")
                            sys.stdout.flush()
        finally:
            code = child.wait()
            if code:
                with lock:
                    print(f"shard {index} of {count} exited {code}", flush=True)

    readers = [
        threading.Thread(target=drain, args=(index, child))
        for index, child in children
    ]
    for reader in readers:
        reader.start()
    if timeout > 0:
        while any(reader.is_alive() for reader in readers):
            time.sleep(1)
            now = time.monotonic()
            with lock:
                for index, spoken in list(spoken_at.items()):
                    child = by_index[index]
                    # A child that has exited needs no killing, and one already
                    # killed is left alone until its reader sees the end.
                    if (
                        spoken is not None
                        and now - spoken > timeout
                        and child.poll() is None
                    ):
                        print(
                            f"[shard {index}] no line for {timeout}s, killing it",
                            flush=True,
                        )
                        child.kill()
                        spoken_at[index] = None
    for reader in readers:
        reader.join()


def _merge(progress_path: Path, count: int) -> int:
    """The shards' checkpoints as one verdict, or the reasons there is none.

    The feed is not read here at all. The shards record the request each was
    given, so a merge that parsed the feed would spend a minute and hold an
    index to learn what the files already say -- and what is worth checking is
    that the files agree about it.

    `count` is passed rather than read off the flags because both a `--merge M`
    and a launcher's own set of children end here, and the second has no merge
    flag to read it from.
    """
    merged, problems = merge_shard_checkpoints(progress_path, count)
    if problems:
        print(f"{len(problems)} reason(s) these are not one verdict:", flush=True)
        for problem in problems:
            print(f"  {problem}", flush=True)
        return 2
    print("merged shard checkpoint(s): " + ", ".join(merged["merged_from"]), flush=True)
    # Each shard's own coverage, because the reason a merged verdict is exit 2 is
    # nearly always one shard short: a line per shard names which shell to run
    # again instead of leaving the reader to find it in M files.
    for index in range(1, count + 1):
        path = shard_progress_path(progress_path, index, count)
        if not path.is_file():
            continue
        one = load_progress(path)
        print(
            f"  shard {index} of {count}: "
            f"{coverage(one, list(one.get('origins') or ()), [date.fromisoformat(day) for day in one.get('days') or ()])}",
            flush=True,
        )
    # A checkpoint outlives the request that wrote it, and this file is where
    # work lands: pairs it holds that this request was not about are kept rather
    # than dropped, so merging a sample over the file a wider sweep is using
    # cannot throw that sweep's answers away.
    held = load_progress(progress_path)
    foreign = {
        key: value
        for key, value in (held.get("pairs") or {}).items()
        if key not in merged["pairs"]
    }
    if foreign:
        print(
            f"  keeping {len(foreign):,} pair(s) in {progress_path.name} that this "
            "request was not about",
            flush=True,
        )
        merged["pairs"].update(foreign)
        merged["differences"].update(
            {
                key: value
                for key, value in (held.get("differences") or {}).items()
                if key in foreign
            }
        )
    save_progress(progress_path, merged)
    # The verdict is over the request the shards agree they were given, which is
    # the only request a merge can be about: it never read a feed to decide.
    origins = list(merged["origins"])
    days = [date.fromisoformat(day) for day in merged["days"]]
    compared = sum(1 for key in requested_pairs(origins, days) if key in merged["pairs"])
    return verdict(
        merged,
        origins,
        days,
        compared,
        f"from {count} shard checkpoint(s)",
        progress_path,
    )


def _probe(db: TimetableDb, origins: list[str], days: list[date], args) -> int:
    """Time a few origins and project the whole sweep, without writing anything."""
    day = days[0]
    db._ensure_indexes(day)
    per: list[float] = []
    for origin in origins[: args.probe]:
        started = time.monotonic()
        differences = compare_origin(db, origin, day, args.max_legs)
        per.append(time.monotonic() - started)
        print(f"{origin}: {per[-1]:.2f}s, {len(differences)} difference(s)", flush=True)
    if not per:
        print("nothing probed", flush=True)
        return 2
    mean = sum(per) / len(per)
    projected = mean * len(origins) * len(days)
    print(
        f"{mean:.2f}s per origin-day over {len(per)} origin(s); "
        f"{len(origins) * len(days):,} origin-days projects to {projected / 3600:.1f} hours",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
