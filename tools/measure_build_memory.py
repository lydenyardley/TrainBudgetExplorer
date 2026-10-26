"""Measure what a build holds in memory, so the worker budget can be re-derived.

`build_workers.worker_budget` is a set of constants, and constants go stale.
This re-derives the three that matter -- what the parent holds before the pool
starts, what one worker's initialiser costs, and what the machine can hand a
build at all -- by doing the build's own work and watching its own memory.

    python -m tools.measure_build_memory --workers 4

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

from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.timetable.atoc_timetable import TimetableDb
from trainbudget.build.build_demo_page import (
    _priced_destinations,
    fares_index_cache_paths,
    is_pseudo_station,
)
from trainbudget.build.build_workers import (
    ONE_WORKER_FLOOR,
    PARENT_BYTES,
    RESERVED_BYTES,
    WORKER_BYTES,
    free_memory_bytes,
    worker_budget,
)
from trainbudget.fares.destination_coverage import UnsourcedReport

MB = 1_000_000


def memory_mb() -> tuple[int, int]:
    """This process's working set and private bytes, in MB.

    Asked of PowerShell on Windows rather than read through ctypes: the win32
    counter struct has to be laid out exactly or the call fails with a buffer
    error, and a measurement script that can be wrong about its own subject is
    worse than one that shells out. On Linux the same two numbers are first
    resident set from /proc/self/status and the private bytes from
    /proc/self/smaps_rollup. /proc/self/status has no "Private:" line, so the
    private figure used to read 0 on every Linux run -- the broken-instrument
    reading the test exists to refuse. Private_Clean + Private_Dirty is the
    Linux counterpart of Windows' private bytes; a kernel without
    smaps_rollup (before 4.14) falls back to RssAnon, the anonymous memory
    only this process holds.
    """
    if sys.platform == "win32":
        script = ("$p=Get-Process -Id " + str(os.getpid()) + "; "
                  "'{0:N0} {1:N0}' -f ($p.WorkingSet64/1MB), ($p.PrivateMemorySize64/1MB)")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, check=True).stdout
        # PowerShell's -f writes thousands separators, which int() will not take.
        fields = out.split()
        return int(fields[0].replace(",", "")), int(fields[1].replace(",", ""))
    rss_kb = anon_kb = 0
    with open("/proc/self/status", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("VmRSS:"):
                rss_kb = int(line.split()[1])
            elif line.startswith("RssAnon:"):
                anon_kb = int(line.split()[1])
    private_kb = None
    try:
        with open("/proc/self/smaps_rollup", encoding="utf-8") as handle:
            private_kb = sum(
                int(line.split()[1])
                for line in handle
                if line.startswith(("Private_Clean:", "Private_Dirty:"))
            )
    except OSError:
        pass
    if not private_kb:
        private_kb = anon_kb
    return rss_kb // 1024, private_kb // 1024


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
    """What one worker's initialiser costs: shared fare metadata, then the timetable.

    Both databases are bound to a name, and until this commit neither was. The
    load was a temporary: the statement completed, the object had no referrers,
    CPython freed it, and the sample that followed read the arenas Python had
    not returned to the OS rather than the memory the load had held. Measured
    against the real feed the difference is not subtle -- 1,918 MB private with
    the reference kept, 316 MB without it -- and the figure this function has
    been printing, "one worker's initialiser peaks at 338 MB", is the second
    one. A worker holds that timetable for every page it builds, so 338 MB was
    never a figure about a worker at all.

    Holding the reference also gives the peak a meaning: it is what a worker
    holds from its initialiser until it answers its first job, which is the
    figure `build_workers.WORKER_BYTES` is supposed to cover.
    """
    trace = Trace()
    trace.say("start")
    common_cache, _index_dir = fares_index_cache_paths(args.feed)
    fares = FaresDb.load_fare_common(common_cache)
    trace.say(f"shared fare metadata ({len(fares.locations_by_crs):,} locations)")
    if args.timetable:
        timetable = TimetableDb().load_feed(args.timetable)
        stats = timetable.stats()
        trace.say(f"whole national timetable ({stats['schedules']:,} schedules, "
                  f"{stats['calling_points']:,} calling points)")
        assert stats["schedules"] > 0, "the timetable was dropped before the peak"
    budget = WORKER_BYTES // MB
    print(f"\none worker's initialiser peaks at {trace.peak:,} MB private")
    print(f"the budget assumes {budget:,} MB ({trace.peak - budget:+,} MB against it)")


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
