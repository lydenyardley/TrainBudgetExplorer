"""The worker plumbing for the --all-origins parallel build.

Split out of build_demo_page.py (audit finding C1): the job function, the
per-process state, and the pool initialiser live here, so the build's CLI
and payload assembly stay one readable file.

Everything the workers share -- the feed config and the station index -- is
delivered once per process by the initialiser, never pickled per job (audit
B3). Jobs carry only the origin they build. The parsed databases hold
object() sentinels that cannot cross a process boundary at all.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from atoc_fares import FaresDb
from atoc_knowledgebase import Knowledgebase
from atoc_timetable import TimetableDb

from build_demo_page import (
    STATION_ASSET_NAME,
    build_payload,
    render_page,
    wants_nre_credit,
    with_base,
)

# Per-process state: the feed databases and the shared build config. In pool
# mode the initialiser fills it once per worker; the in-process build fills
# it once per run. Same shape either way -- one way to read it.
_WORKER: dict = {}


def configure_worker(shared: dict, reference: Knowledgebase | None = None) -> None:
    """Fill a process's worker state from the build config.

    Both ways into a page -- the pool initialiser and the in-process build --
    come through here, so the two cannot drift. They did once: the reader was
    handed to the initialiser alone, and a ``--workers 1 --all-origins`` build
    with ``--knowledgebase`` then told every one of its pages that no reference
    feed had been named, while the same build across several processes checked
    every one of them. The in-process branch injects live databases rather than
    paths, but that is the only difference between the two, so it is the only
    thing it sets afterwards.

    The parsed feed travels beside the config rather than inside it: the config
    dict is what the parent serialises into the resume signature, and a parsed
    feed's repr carries an address, which would make every run a different
    build. It is delivered once per process, like the feeds, and never pickled
    per job.
    """

    _WORKER.clear()
    _WORKER.update(shared)
    _WORKER["reference"] = reference


def init_worker(
    feed: str,
    timetable: str | None,
    shared: dict,
    reference: Knowledgebase | None = None,
) -> None:
    configure_worker(shared, reference)
    # Parallel builds persist the shared fare metadata and one index per
    # origin first (audit B1), so a worker restores the slice it is about to
    # render instead of re-parsing all 8.5M flow lines. Without those keys the
    # worker falls back to a full load: the in-process path never calls this,
    # and a direct caller that shares no cache still gets a working feed.
    if shared.get("fare_common_cache") and shared.get("fare_index_dir"):
        _WORKER["fares_common"] = FaresDb.load_fare_common(shared["fare_common_cache"])
        _WORKER["fares"] = None
    else:
        _WORKER["fares"] = FaresDb().load_feed(feed)
    _WORKER["timetable"] = TimetableDb().load_feed(timetable) if timetable else None


MB = 1_000_000

#: What the parent holds while it prepares the build, measured above. It is
#: counted because the pool starts before the parent has let go, so a cap that
#: ignored it would ignore the moment the machine is most committed.
PARENT_BYTES = 4_400 * MB

#: What one worker costs for as long as it is assembling pages. The initialiser
#: measures 325 MB and the largest worker sampled mid-build held 852 MB, so
#: this is the upper of the two rather than the reassuring one.
WORKER_BYTES = 900 * MB

#: What the machine needs for everything that is not the build: the browser a
#: reader is previewing in, the editor, the OS. A build that starves those
#: fails in a way that reads as the build's fault. Set at 2 GB rather than a
#: rounder 3 so that the one parallel build with a measured outcome -- four
#: workers with 8 GB free, observed twice -- clears the floor below instead of
#: being turned away by it.
RESERVED_BYTES = 2_000 * MB

#: The largest count measured to finish a whole-network build on a 15.8 GB
#: machine. Above this the arithmetic says there is room and the measurement
#: says there is not, and the measurement is what this file trusts.
MAX_WORKERS = 4

#: Below this much free memory the build drops to a single worker. It is the
#: parent plus one worker plus what the machine needs for itself, which is the
#: smallest parallel build that can finish at all.
ONE_WORKER_FLOOR = PARENT_BYTES + WORKER_BYTES + RESERVED_BYTES


def free_memory_bytes() -> int | None:
    """How much memory this machine can hand a build right now, in bytes.

    None when the platform will not say, which is a different thing from zero:
    a caller that cannot read the figure falls back on the measured ceiling,
    and a caller that reads zero falls to one worker.
    """
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(MemoryStatusEx)
            ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return int(status.ullAvailPhys) if ok else None
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
        return None
    except (OSError, ValueError, AttributeError):
        return None


def worker_budget(cores: int | None = None, free_bytes: int | None = None) -> int:
    """How many workers an ``--all-origins`` build should use here.

    Three ceilings, narrowest first: the cores there are, whether the machine
    can hold the parent and one worker and itself at the same time, and the
    largest count measured to finish. Never zero -- a build that cannot have a
    pool still builds, one page at a time, and saying so is better than
    refusing to build.

    The middle ceiling is a single step rather than a division, and that is
    deliberate. Dividing the free memory by the per-worker cost gives a number
    the measurements do not support: at 8 GB free it permits four workers and
    at 4 GB it permits one, but a four-worker tree was measured holding 2.9 GB
    in total, because the parent has let most of its 4.1 GB go by the time the
    workers are producing pages. A formula that fits one sample and not the
    other is a formula to distrust, so this asks the one question that has a
    measured answer -- is there room for the smallest parallel build -- and
    otherwise trusts the ceiling.

    A caller that passes ``free_bytes`` has already read it.
    """
    cores = cores or os.cpu_count() or 1
    if free_bytes is None:
        free_bytes = free_memory_bytes()
    if free_bytes is not None and free_bytes < ONE_WORKER_FLOOR:
        return 1
    return max(1, min(cores, MAX_WORKERS))


def build_page_job(job: dict) -> tuple[str, str, str]:
    """Build one station page from a config-only job.

    --all-origins is embarrassingly parallel: each origin's page depends only
    on the feed, the shared config, and its own origin. The worker returns the
    rendered HTML; the parent writes it.
    """
    origin_crs = job["crs"]
    fares = _WORKER["fares"]
    if fares is None:
        fares = FaresDb.apply_fare_index(
            _WORKER["fares_common"], Path(_WORKER["fare_index_dir"]) / f"{origin_crs}.pickle"
        )
    payload = build_payload(
        fares,
        _WORKER.get("timetable"),
        origin_crs,
        max_changes=_WORKER["max_changes"],
        day=_WORKER["day"],
        note=_WORKER["note"],
        attribution=_WORKER["attribution"],
        price_source=_WORKER["price_source"],
        feed_date=_WORKER.get("feed_date"),
        base_path=_WORKER["base_path"],
        provider=_WORKER["provider"],
        mode=_WORKER["link_mode"],
        adults=_WORKER["adults"],
        network=_WORKER["network"],
        advertiser_id=_WORKER["advertiser_id"],
        publisher_id=_WORKER["publisher_id"],
        departure_limit=_WORKER["departures"],
        built_at=_WORKER.get("built_at"),
        # The parent's parsed reference feed, handed down so each page answers
        # from its own rows without any worker re-reading the XML. The answer
        # differs per page by design: it is about the conditions that page
        # shows, and a claim about one station printed on 2,700 pages would be a
        # claim none of the others earned.
        reference=_WORKER.get("reference"),
        reference_published=_WORKER.get("reference_published", ""),
        reference_checked=_WORKER.get("reference_checked", ""),
        # The picker's options are the site's one shared asset, not a copy inside
        # every page, so this page carries the request and not the rows (audit,
        # 30 September 2026: the list was 445 MB across the network).
        published_routes=[],
    )
    base_path = _WORKER["base_path"]
    payload["stations"] = []
    payload["stationsSrc"] = with_base(base_path, "/" + STATION_ASSET_NAME)
    html = render_page(
        payload,
        budget_pounds=20,
        analytics=_WORKER["analytics"],
        nre_credit=wants_nre_credit(_WORKER["attribution"]),
    )
    return job["slug"], job["origin_name"], html
