"""Measure what a build holds in memory, so the worker budget can be re-derived.

`build_workers.worker_budget` is a set of constants, and constants go stale.
This re-derives the three that matter -- what the parent holds before the pool
starts, what one worker's initialiser costs, and what the machine can hand a
build at all -- by doing the build's own work and watching its own memory.

    python tools/measure_build_memory.py --workers 4

Two figures are measured here and one is read. The parent's peak and a single
worker's initialiser cost come from doing that work in this process; free
memory comes from the platform. The fourth figure the budget leans on -- the
peak of a worker that is *assembling pages* rather than loading the timetable --
cannot be measured from in here, because a worker builds pages in another
process. `worker_budget`'s own comment says where that number came from.

This is slow and it wants the whole feed: it parses both national feeds twice.
It is a tool for the day the constants need re-checking, not a gate.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atoc_fares import FaresDb  # noqa: E402
from atoc_timetable import TimetableDb  # noqa: E402
from build_demo_page import (  # noqa: E402
    _priced_destinations,
    fares_index_cache_paths,
    is_pseudo_station,
)
from build_workers import (  # noqa: E402
    ONE_WORKER_FLOOR,
    PARENT_BYTES,
    RESERVED_BYTES,
    WORKER_BYTES,
    free_memory_bytes,
    worker_budget,
)
from destination_coverage import UnsourcedReport  # noqa: E402

MB = 1_000_000


def memory_mb() -> tuple[int, int]:
    """This process's working set and private bytes, in MB.

    Asked of PowerShell on Windows rather than read through ctypes: the win32
    counter struct has to be laid out exactly or the call fails with a buffer
    error, and a measurement script that can be wrong about its own subject is
    worse than one that shells out. On Linux the same two numbers are first
    and third lines of /proc/self/status.
    """
    if sys.platform == "win32":
        script = ("$p=Get-Process -Id " + str(os.getpid()) + "; "
                  "'{0:N0} {1:N0}' -f ($p.WorkingSet64/1MB), ($p.PrivateMemorySize64/1MB)")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, check=True).stdout
        # PowerShell's -f writes thousands separators, which int() will not take.
        fields = out.split()
        return int(fields[0].replace(",", "")), int(fields[1].replace(",", ""))
    values = {}
    with open("/proc/self/status", encoding="utf-8") as handle:
        for line in handle:
            for key, name in (("VmRSS:", "rss"), ("Private:", "private")):
                if line.startswith(key):
                    values[name] = int(line.split()[1]) // 1024
    return values.get("rss", 0), values.get("private", 0)


class Trace:
    """The running account of what this process holds."""

    def __init__(self) -> None:
        self.start = time.time()
        self.peak = 0

    def say(self, label: str) -> None:
        working, private = memory_mb()
        self.peak = max(self.peak, private)
        print(f"[{time.time() - self.start:6.1f}s] {label:38s} "
              f"working {working:5d} MB  private {private:5d} MB", flush=True)


def measure_worker(args: argparse.Namespace) -> None:
    """What one worker's initialiser costs: shared fare metadata, then the timetable."""
    trace = Trace()
    trace.say("start")
    common_cache, _index_dir = fares_index_cache_paths(args.feed)
    FaresDb.load_fare_common(common_cache)
    trace.say("shared fare metadata")
    if args.timetable:
        TimetableDb().load_feed(args.timetable)
        trace.say("whole national timetable")
    print(f"\none worker's initialiser peaks at {trace.peak:,} MB private "
          f"(the budget assumes {WORKER_BYTES // MB:,} MB)")


def measure_parent(args: argparse.Namespace) -> None:
    """What the parent holds before the pool starts: both feeds, priced, indexed."""
    trace = Trace()
    trace.say("start")
    fares = FaresDb().load_feed(args.feed)
    trace.say("fares feed loaded and kept")
    timetable = TimetableDb().load_feed(args.timetable) if args.timetable else None
    trace.say("national timetable loaded and kept")

    origins = [crs for crs in sorted(fares.locations_by_crs) if not is_pseudo_station(crs)]
    trace.say(f"{len(origins):,} priceable candidates")

    if args.skip_pricing:
        # The pricing pass is the slow half and adds a few tens of MB. Skipped
        # by default only when the feed is small enough that its number is not
        # the one being checked.
        print("skipping the pricing pass; this is not the real peak", flush=True)
    else:
        coverage = UnsourcedReport()
        day = date.today()
        for number, crs in enumerate(origins, 1):
            _priced_destinations(fares, timetable, crs, day, coverage)
            if number % 1000 == 0:
                trace.say(f"priced {number:,}/{len(origins):,}")
        trace.say(f"priced all {len(origins):,}")

    common_cache, index_dir = fares_index_cache_paths(args.feed)
    fares.write_fare_indexes(common_cache, index_dir, origins)
    trace.say(f"{len(origins):,} per-origin indexes written")

    print(f"\nthe parent's peak before the pool starts is {trace.peak:,} MB private "
          f"(the budget assumes {PARENT_BYTES // MB:,} MB)")


def report_machine() -> None:
    free = free_memory_bytes()
    if free is None:
        print("this platform will not say how much memory is free")
        return
    print(f"free memory right now   {free:,} bytes ({free / 1e9:.1f} GB)")
    print(f"reserve                 {RESERVED_BYTES:,} bytes ({RESERVED_BYTES / 1e9:.1f} GB)")
    print(f"one-worker floor        {ONE_WORKER_FLOOR:,} bytes ({ONE_WORKER_FLOOR / 1e9:.1f} GB)")
    print(f"cores                   {os.cpu_count()}")
    print(f"budget here             {worker_budget()} worker(s)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed", default="feeds/fares", type=Path)
    parser.add_argument("--timetable", default="feeds/timetable", type=Path)
    parser.add_argument("--workers", type=int, default=4,
                        help="the count being justified; reported so the two can be compared")
    parser.add_argument("--measure", choices=("worker", "parent", "machine", "all"),
                        default="machine")
    parser.add_argument("--skip-pricing", action="store_true",
                        help="measure the parent's load and index write without pricing every origin")
    args = parser.parse_args(argv)

    if args.measure in ("machine", "all"):
        report_machine()
    if args.measure in ("worker", "all"):
        measure_worker(args)
    if args.measure in ("parent", "all"):
        measure_parent(args)
    if args.measure == "all":
        print(f"\nthe build under test asks for {args.workers} workers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
