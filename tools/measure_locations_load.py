"""What the shard merge stops paying for, measured on the real feed.

E6 of the 17 October 2026 audit: the merge loaded every record type of the
fares feed to read one field of it, the station list. `load_feed` can now read
the `.loc` file alone, and this is the comparison a reviewer reruns.

Each load runs in its own process, because a heap warmed by a full parse would
pay for the next one. The location maps are compared first: a cheaper reader
that disagreed would refuse a correct split, and no timing would show it.

    python -m tools.measure_locations_load
    python -m tools.measure_locations_load --feed feeds/fares/dtd-fares.zip --runs 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_FEED = "feeds/fares/dtd-fares.zip"


def _load(feed: str, locations_only: bool) -> tuple[float, dict[str, tuple[str, str, str]]]:
    """Load once and return the seconds and the location map as plain values."""
    from trainbudget.fares.atoc_fares import FaresDb

    started = time.perf_counter()
    db = FaresDb().load_feed(feed, locations_only=locations_only)
    elapsed = time.perf_counter() - started
    return elapsed, {
        crs: (location.nlc, location.name, location.group_nlc)
        for crs, location in db.locations_by_crs.items()
    }


def _in_its_own_process(feed: str, locations_only: bool) -> tuple[float, dict]:
    # Run as a module from the repository root, so the child imports the same
    # checkout this one did rather than whatever its script directory happens
    # to be.
    root = Path(__file__).resolve().parent.parent
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.measure_locations_load",
            "--one",
            "locations" if locations_only else "full",
            "--feed",
            str(Path(feed).resolve()),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"error: the {'locations-only' if locations_only else 'full'} load failed:\n"
            f"{completed.stderr.strip()}"
        )
    seconds, stations, digest = completed.stdout.strip().splitlines()[0].split()
    return float(seconds), {"stations": int(stations), "digest": digest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed", default=DEFAULT_FEED)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--one", choices=("full", "locations"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.one:
        seconds, locations = _load(args.feed, args.one == "locations")
        # A digest of the whole map rather than the map itself: the parent
        # compares one line, and the point of the comparison is equality.
        digest = hashlib.sha256(
            json.dumps(sorted(locations.items()), ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        print(f"{seconds:.1f} {len(locations)} {digest}")
        return 0

    feed = str(Path(args.feed))
    if not Path(feed).exists():
        print(f"error: no feed at {feed}", file=sys.stderr)
        return 2
    results = {"full": [], "locations": []}
    for run in range(args.runs):
        for mode in results:
            seconds, facts = _in_its_own_process(feed, mode == "locations")
            results[mode].append(seconds)
            if run == 0:
                print(
                    f"{'locations-only' if mode == 'locations' else 'full load'}: "
                    f"{facts['stations']:,} stations, map digest {facts['digest']}"
                )
    digests = {
        mode: _in_its_own_process(feed, mode == "locations")[1]["digest"]
        for mode in results
    }
    if len(set(digests.values())) != 1:
        print(
            f"error: the two loads disagree about the stations: {digests}",
            file=sys.stderr,
        )
        return 1
    print("the two loads read the same stations")
    for mode, label in (("full", "full load"), ("locations", "locations-only")):
        seconds = results[mode]
        print(
            f"{label}: {min(seconds):.1f} s best of {len(seconds)} "
            f"({', '.join(f'{value:.1f}' for value in seconds)})"
        )
    full = min(results["full"])
    cheap = min(results["locations"])
    print(f"the merge stops paying {full - cheap:.1f} s, {full / cheap:.1f}x, of its feed load")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
