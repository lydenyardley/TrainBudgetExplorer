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

from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb

from build_demo_page import build_payload, render_page, with_base

# Per-process state: the feed databases and the shared build config. In pool
# mode the initialiser fills it once per worker; the in-process build fills
# it once per run. Same shape either way -- one way to read it.
_WORKER: dict = {}


def init_worker(feed: str, timetable: str | None, shared: dict) -> None:
    _WORKER.clear()
    _WORKER.update(shared)
    # Fast builds load the shared fare metadata once, then each worker applies
    # the persisted index for the origin it is about to render. The normal
    # path deliberately retains its full-feed worker semantics for callers
    # that use --all-origins without the fast/resumable mode.
    if shared.get("fare_common_cache") and shared.get("fare_index_dir"):
        _WORKER["fares_common"] = FaresDb.load_fare_common(shared["fare_common_cache"])
        _WORKER["fares"] = None
    else:
        _WORKER["fares"] = FaresDb().load_feed(feed)
    _WORKER["timetable"] = TimetableDb().load_feed(timetable) if timetable else None


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
        base_path=_WORKER["base_path"],
        provider=_WORKER["provider"],
        mode=_WORKER["link_mode"],
        adults=_WORKER["adults"],
        network=_WORKER["network"],
        advertiser_id=_WORKER["advertiser_id"],
        publisher_id=_WORKER["publisher_id"],
        departure_limit=_WORKER["departures"],
        built_at=_WORKER.get("built_at"),
    )
    base_path = _WORKER["base_path"]
    payload["stations"] = [
        {"name": e["name"], "crs": e["crs"], "href": with_base(base_path, f"/from/{e['slug']}/")}
        for e in _WORKER["index"] if e["crs"] != origin_crs
    ]
    html = render_page(payload, budget_pounds=20, analytics=_WORKER["analytics"])
    return job["slug"], job["origin_name"], html
