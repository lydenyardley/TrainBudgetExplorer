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

    python tools/check_slice_equivalence.py --timetable feeds/timetable --probe 5
    python tools/check_slice_equivalence.py --timetable feeds/timetable \\
        --date 2026-10-07 --days 7 --progress _cache/slice-equivalence.json
    python tools/check_slice_equivalence.py --timetable feeds/timetable --origins GRA,NOT --limit 2

The sweep is hours of CPU on the real feed, so it checkpoints every origin and
resumes: run it again with the same `--progress` file and it skips the pairs it
has already compared. `--probe N` times the first N origins and prints the
projected total instead of running it.

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
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Reach the project root whether run as `python tools/check_slice_equivalence.py`
# (the README's way) or imported as tools.check_slice_equivalence (the tests' way).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atoc_timetable import TimetableDb  # noqa: E402

#: The service week the harness compares unless told otherwise. The build's own
#: date, so a failure names a day a page was actually assembled for.
DEFAULT_DATE = "2026-10-07"

#: Legs per origin-day whose `intermediate_crs` is compared. None means every
#: leg of every journey the page would show, which is the complete question and
#: is affordable because `TimetableDb` keeps a train-identity index for the day:
#: before that index existed this call read the day's whole schedule list, 0.6s
#: on the real feed, and a sample was the only way to ask it at scale.
DEFAULT_MAX_LEGS: int | None = None

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


def coverage(progress: dict, origins: list[str], days: list[date]) -> str:
    """What has been compared, as one line, so a partial sweep says so plainly."""
    pairs = progress.get("pairs", {})
    requested = requested_pairs(origins, days)
    done = sum(1 for key in requested if pairs.get(key) == "ok")
    failed = sum(1 for key in requested if pairs.get(key) not in (None, "ok"))
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
        "--timetable", type=Path, required=True, help="CIF timetable feed folder or zip"
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
    parser.add_argument("--progress", type=Path, default=Path("_cache/slice-equivalence.json"), help="checkpoint file, resumed on the next run")
    parser.add_argument("--probe", type=int, default=None, help="time this many origins and print the projection")
    args = parser.parse_args(argv)

    if not Path(args.timetable).exists():
        print(f"no timetable feed at {args.timetable}", flush=True)
        return 2
    days = week_days(date.fromisoformat(args.date), args.days)

    print(f"Loading timetable feed from {args.timetable} ...", flush=True)
    started = time.monotonic()
    db = TimetableDb().load_feed(args.timetable)
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
    legs_note = (
        "every leg of every journey" if args.max_legs is None else f"{args.max_legs} legs sampled"
    )
    print(f"{len(origins):,} origin(s) x {len(days)} day(s), {legs_note}", flush=True)

    if args.probe:
        return _probe(db, origins, days, args)

    progress = load_progress(args.progress)
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
                save_progress(args.progress, progress)
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
                save_progress(args.progress, progress)
                # Over the whole run, not over this origin: a rate computed from
                # the origin that happened to be last reported 0.01s and 0.37s
                # for the same sweep, which is a number that tells a reader
                # nothing about how long the work takes.
                per_origin_day = (time.monotonic() - sweep_started) / compared
                remaining = len(requested_pairs(origins, days)) - len(progress["pairs"])
                print(
                    f"{coverage(progress, origins, days)}; {per_origin_day:.3f}s per "
                    f"origin-day, about {per_origin_day * remaining / 60:.0f} min left",
                    flush=True,
                )
        save_progress(args.progress, progress)
        print(f"{day.isoformat()}: {coverage(progress, origins, days)}", flush=True)

    save_progress(args.progress, progress)
    print(coverage(progress, origins, days), flush=True)
    print(f"checkpoint: {args.progress.resolve()}", flush=True)
    # The verdict is about the request, not about this run: a sweep resumed to
    # the end of its work compares nothing and has still concluded. What decides
    # is whether every pair asked for is in the checkpoint, and what it says.
    requested = requested_pairs(origins, days)
    outcomes = [progress["pairs"].get(key) for key in requested]
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
    print(f"every origin-day asked for agreed ({len(requested):,} compared this run: {compared:,})", flush=True)
    return 0


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
