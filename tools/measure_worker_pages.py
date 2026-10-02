"""Measure the peak of one pool worker while it is assembling pages.

`build_workers.WORKER_BYTES` is 2,200 MB, from a worker measured at 2,188 MB
through the functions below. It was 900 MB, and both of the figures that
constant came from -- a 325 MB initialiser and an 852 MB worker -- were
measurements of a database the measuring tool had already freed. See ADR-0057
for that, and for why the four-worker ceiling cannot be re-measured on a 16 GB
machine.

This closes the gap without a whole-network build. A pool worker does two
things: `init_worker` restores the shared fare metadata and parses the whole
national timetable, and then `build_page_job` assembles pages from jobs. Both
happen in one process, so both happen here, through the very functions the pool
calls -- this measures the worker's body rather than a re-impression of it.

What it deliberately does not do is restore a timetable from a pickle. The
single-origin build path does, and it is cheaper than parsing, not dearer:
restoring GRN's focused cache reaches about 859 MB private before a page is
assembled, where parsing the whole feed holds about 2,100 MB. So a figure taken
from a single-origin build would *understate* a real worker by more than a
gigabyte, which is the more dangerous direction of the two -- it looks safe.
`init_worker` passes no cache path and a worker never gets one, so the number
this tool prints is the number a worker pays.

    python tools/measure_worker_pages.py --origins GRN,LCN
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import date, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_workers import WORKER_BYTES, _WORKER, build_page_job, init_worker  # noqa: E402

MB = 1_000_000


def memory_mb() -> tuple[int, int]:
    """This process's working set and private bytes, in MB.

    Borrowed from tools/measure_build_memory.py rather than written again, and
    that tool's note is the reason: asked of PowerShell on Windows rather than
    read through ctypes, because the win32 counter struct has to be laid out
    exactly and a measurement script that can be wrong about its own subject is
    worse than one that shells out. An earlier draft of this file read it
    through ctypes, got 0 MB back for every sample, and reported a peak of
    zero -- which is the shape of a measurement that would have said the budget
    holds with enormous margin.
    """
    if sys.platform == "win32":
        import os
        script = ("$p=Get-Process -Id " + str(os.getpid()) + "; "
                  "'{0:N0} {1:N0}' -f ($p.WorkingSet64/1MB), ($p.PrivateMemorySize64/1MB)")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, check=True).stdout
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
    """The running peak of this process's private bytes, per labelled step."""

    def __init__(self) -> None:
        self.start = time.time()
        self.peak = 0

    def say(self, label: str) -> int:
        working, private = memory_mb()
        self.peak = max(self.peak, private)
        print(f"[{time.time() - self.start:6.1f}s] {label:52s} "
              f"working {working:5d} MB  private {private:5d} MB", flush=True)
        return private


def worker_config(day: date) -> dict:
    """The state a pool initialiser fills from the build's config.

    Read from the builder's own defaults rather than invented, so the numbers
    below are the ones a real build uses. Only the fare caches matter to memory;
    the rest are the values every page is rendered with.
    """
    return {
        "max_changes": 4,
        "day": day,
        "note": "",
        "attribution": [],
        "price_source": "the National Rail Data Portal DTD fares feed",
        "feed_date": None,
        "base_path": "",
        "provider": "national_rail",
        "link_mode": "fallback",
        "adults": 2,
        "network": "",
        "advertiser_id": "",
        "publisher_id": "",
        "departures": 5,
        "built_at": datetime_now(),
        "analytics": "",
        "index": {},
        "fare_common_cache": "",
        "fare_index_dir": "",
    }


def datetime_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed", default="feeds/fares", type=Path)
    parser.add_argument("--timetable", default="feeds/timetable", type=Path)
    parser.add_argument("--origins", default="GRN,LCN",
                        help="comma-separated codes whose fare index the parent has "
                             "already written. A hub is the interesting case and the "
                             "one that needs the most parent memory to prepare.")
    parser.add_argument("--pages", type=int, default=2,
                        help="pages per origin; a second page proves the first was "
                             "not a one-off, and a worker in a pool builds many")
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)

    from build_demo_page import fares_index_cache_paths

    common_cache, index_dir = fares_index_cache_paths(args.feed)
    if not Path(common_cache).is_file():
        print(f"no shared fare metadata at {common_cache}. Run a build first: without "
              f"it `init_worker` falls back to parsing the whole feed, and this would "
              f"measure that rather than a worker.", file=sys.stderr)
        return 2

    origins = [code.strip().upper() for code in args.origins.split(",") if code.strip()]
    missing = [code for code in origins
               if not (Path(index_dir) / f"{code}.pickle").is_file()]
    if missing:
        print(f"no fare index written for {', '.join(missing)} in {index_dir}. Those "
              f"pages cannot be built the way a worker builds them; run an "
              f"--all-origins build to write them.", file=sys.stderr)
        return 2

    day = date.fromisoformat(args.date) if args.date else date.today()
    shared = worker_config(day)
    shared["fare_common_cache"] = str(common_cache)
    shared["fare_index_dir"] = str(index_dir)

    trace = Trace()
    trace.say("start")
    init_worker(str(args.feed), str(args.timetable), shared)
    trace.say("init_worker: fare metadata restored, whole timetable parsed")

    timetable = _WORKER.get("timetable")
    stats = timetable.stats() if timetable is not None else {}
    trace.say(f"index: {stats.get('schedules', 0):,} schedules, "
              f"{stats.get('calling_points', 0):,} calling points")

    from atoc_fares import FaresDb

    built = 0
    for code in origins:
        fares = FaresDb.apply_fare_index(
            _WORKER["fares_common"], Path(_WORKER["fare_index_dir"]) / f"{code}.pickle")
        _WORKER["fares"] = fares
        trace.say(f"{code}: fare slice restored")
        for page in range(args.pages):
            job = {
                "crs": code,
                "slug": code.lower(),
                "origin_name": code,
            }
            _slug, _name, html = build_page_job(job)
            built += 1
            trace.say(f"{code} page {page + 1}: {len(html):,} bytes of HTML")

    budget = WORKER_BYTES // MB
    print(f"\nassembled {built} page(s) in one process, through the pool's own functions")
    print(f"one worker assembling pages peaks at {trace.peak:,} MB private")
    print(f"the budget assumes {budget:,} MB")
    print(f"the {budget:,} MB worker budget "
          f"{'holds' if trace.peak <= budget else 'DOES NOT HOLD'} "
          f"({trace.peak - budget:+,} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())