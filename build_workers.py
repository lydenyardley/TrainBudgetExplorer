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
from atoc_timetable import SliceIndex, TimetableDb

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
    # The per-origin slices this build reads its timetables from, when it has an
    # index: `shared` carries where they are and which feed cut them, and the
    # object assembled here is the one a page uses. Both ways into a page come
    # through this function, so neither can be the one that forgot it.
    spec = shared.get("timetable_index")
    _WORKER["timetable_index"] = (
        SliceIndex(spec["directory"], identity=spec["identity"]) if spec else None
    )


def restore_worker_fares(feed: str, shared: dict, loaded: FaresDb | None = None) -> None:
    """Put this process's fare database in place: one origin's slice, or the feed.

    Builds persist the shared fare metadata and one index per origin first
    (audit B1), so a process that has them restores the slice it is about to
    render instead of re-parsing all 8.5M flow lines, and holds no national
    fare data while it renders a page. Without those keys it keeps the whole
    feed, because a working page beats a released one.

    Both ways into a page come through here on purpose. The pool took the
    slice and the in-process build kept the feed, which is why a one-worker
    build held 2.1 GB it never read for the whole of its render phase.
    ``loaded`` is a feed this process has already parsed, so the in-process
    caller hands it here rather than paying for a second parse.
    """
    if shared.get("fare_common_cache") and shared.get("fare_index_dir"):
        _WORKER["fares_common"] = FaresDb.load_fare_common(shared["fare_common_cache"])
        _WORKER["fares"] = None
    else:
        _WORKER["fares"] = loaded if loaded is not None else FaresDb().load_feed(feed)


def init_worker(
    feed: str,
    timetable: str | None,
    shared: dict,
    reference: Knowledgebase | None = None,
) -> None:
    configure_worker(shared, reference)
    restore_worker_fares(feed, shared)
    # The national index, kept for the life of the worker as the source every
    # page's slice is cut from. The page itself is built from that slice, so
    # what a page holds and indexes while it renders is its own origin's reach.
    # `timetable` is None for a build whose index covers every page it writes:
    # the parent hands the path down only when it read the feed itself, so a
    # worker of an indexed build parses nothing and reads each page's slice.
    _WORKER["timetable"] = TimetableDb().load_feed(timetable) if timetable else None


MB = 1_000_000

#: What the parent holds while it prepares the build, measured above. It is
#: counted because the pool starts before the parent has let go, so a cap that
#: ignored it would ignore the moment the machine is most committed.
PARENT_BYTES = 4_400 * MB

#: What one worker costs for as long as it is assembling pages.
#:
#: Measured at 2,188 MB private, through the pool's own `init_worker` and
#: `build_page_job` rather than a re-impression of them
#: (`tools/measure_worker_pages.py`). It was 900 MB, and the two figures it came
#: from were both measurements of a database the tool had already freed: a 325 MB
#: initialiser and an 852 MB worker, against a real 2,100 MB and 2,188 MB.
#:
#: This is the whole of a worker's cost, because a worker parses the national
#: timetable itself and keeps it for every page it builds -- as the database
#: each page's slice is cut from (`atoc_timetable.TimetableDb.focused`), so the
#: index a page assembles is its own origin's reach rather than the network's.
#: A worker handed an index instead parses nothing and holds one page's slice
#: at a time, which is a different, smaller shape: see `ONE_WORKER_FLOOR`.
#: It is not a sum with the parent: `build_demo_page.py` releases `fares` and
#: `timetable` before the pool starts, so the parent runs first and the workers
#: run second. Measured on the real feed, that release sheds 4,000 MB of the
#: 4,017 MB held and leaves the parent 36 MB.
#:
#: See ADR-0057 for the two figures this replaced and for why the four-worker
#: tree that appeared to contradict them was a sample taken mid-parse.
WORKER_BYTES = 2_200 * MB

#: What the machine needs for everything that is not the build: the browser a
#: reader is previewing in, the editor, the OS. A build that starves those
#: fails in a way that reads as the build's fault.
RESERVED_BYTES = 2_000 * MB

#: The largest count measured to finish a whole-network build on a 15.8 GB
#: machine. Above this the arithmetic says there is room and the measurement
#: says there is not, and the measurement is what this file trusts.
MAX_WORKERS = 4

#: Below this much free memory the build drops to a single worker.
#:
#: The larger of the two phases, not their sum, plus what the machine needs for
#: itself. The parent loads both feeds and prices every origin; the workers then
#: hold one timetable each. Those are sequential -- `build_demo_page.py` releases
#: the parent's databases before the pool starts -- so a machine needs room for
#: whichever is bigger, and counting both at once would refuse builds this
#: machine can finish. The sum was correct while the parent held its databases
#: for the whole build; it is 7.3 GB as a sum and 6.4 GB here.
#:
#: The release is what makes the two phases sequential on the one-worker path
#: too, and until 7 October 2026 it was pool-only: the in-process build rendered
#: every page from the parent's own fares feed, so its render phase held the
#: 2.1 GB feed beside the 1.87 GB timetable. `restore_worker_fares` now hands
#: that path the same per-origin slice a worker takes, and the feed is released
#: before the first page. The preparation peak is untouched by that -- it is the
#: two whole feeds and the index write, and it is what `PARENT_BYTES` covers --
#: so this floor does not move. What moves is the render phase: it held a whole
#: fares feed it never read, and it no longer does.
#:
#: The timetable half of the render phase is two shapes now. A build that reads
#: the feed holds the database its pages' slices are cut from -- the parent's on
#: the one-worker path, its own in a pool worker, parsed in `init_worker` -- and
#: that is what these two constants describe. A build given `--timetable-index`
#: holds no national index at all: each page reads its own slice off disk, so a
#: worker carries one origin's reach and its fares slice, and nothing parses the
#: timetable. Neither constant moves for that second shape, because they are the
#: floor for the first one and every build without an index still pays it. What
#: an indexed worker costs is measured in docs/build-performance-findings.md.
ONE_WORKER_FLOOR = max(PARENT_BYTES, WORKER_BYTES) + RESERVED_BYTES


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

    The middle ceiling is a division by `WORKER_BYTES`, and that is only
    sound because the divisor is a measurement: one worker holds 2,200 MB,
    measured through the pool's own `init_worker` and `build_page_job`. It was
    not sound when this function refused to divide, and the refusal was right
    for the wrong-looking reason -- `WORKER_BYTES` was 900 MB while a worker
    held 2,188, so a division would have handed out roughly twice the workers
    the machine could hold.

    The parent is not part of the divisor because it is not concurrent with the
    workers. `build_demo_page.py` releases `fares` and `timetable` before the
    pool starts -- the fare indexes the workers restore are already on disk, and
    each worker parses the timetable itself -- which sheds 4,000 MB of the
    4,017 MB the parent held. So the machine runs the parent first and the
    workers second, and only the workers are counted here. `ONE_WORKER_FLOOR`
    covers the other phase.

    A caller that passes ``free_bytes`` has already read it.
    """
    cores = cores or os.cpu_count() or 1
    if free_bytes is None:
        free_bytes = free_memory_bytes()
    if free_bytes is None:
        # The platform will not say. The measured ceiling is a better answer
        # than the one worker a zero would produce.
        return max(1, min(cores, MAX_WORKERS))
    if free_bytes < ONE_WORKER_FLOOR:
        # Not even the smallest parallel build fits. One worker still builds,
        # one page at a time, and that beats refusing to build.
        return 1
    # `int` because a caller that passes a float count of gigabytes -- which is
    # the natural thing to write -- would otherwise get a float back, and
    # ProcessPoolExecutor is handed that float as its worker count.
    affordable = int((free_bytes - RESERVED_BYTES) // WORKER_BYTES)
    return max(1, min(cores, MAX_WORKERS, affordable))


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
        # The change stations' own indexes, for the second ticket of a
        # two-part row (ADR-0061). The parent wrote one for every change
        # station before the pool started.
        fares.merge_interchange_indexes(_WORKER["fare_index_dir"])
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
        # This page's timetable when there is no feed in the process: its own
        # slice, read from the index. `build_payload` uses it only when
        # `_WORKER["timetable"]` is None, so a build with a feed is unchanged.
        timetable_index=_WORKER.get("timetable_index"),
        # The identity the service-week facts are keyed by, handed down with
        # everything else the parent resolved once (T9). Absent on builds from
        # before the facts existed, which search the week every time.
        timetable_identity=_WORKER.get("timetable_identity"),
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
