"""The worker plumbing for the --all-origins parallel build.

Split out of build_demo_page.py (audit finding C1): the job dict, the
per-process feed cache, and the pool initialiser live here, so the build's CLI
and payload assembly stay one readable file.

Worker-process state: the feed is loaded once per worker by the pool's
initialiser, never pickled per job. The parsed databases hold object()
sentinels that cannot cross a process boundary at all, so jobs carry only
small config and the worker resolves the feed itself.
"""

from __future__ import annotations

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb

from build_demo_page import build_payload, render_page, with_base

_WORKER: dict = {}


def init_worker(feed: str, timetable: str | None) -> None:
    _WORKER["fares"] = FaresDb().load_feed(feed)
    _WORKER["timetable"] = TimetableDb().load_feed(timetable) if timetable else None


def build_page_job(job: dict) -> tuple[str, str, str]:
    """Build one station page in a worker process.

    --all-origins is embarrassingly parallel: each origin's page depends only
    on the feed and its own origin. The worker loads the feed once (a few
    seconds) and returns the rendered HTML, which the parent writes.
    """
    payload = build_payload(
        job.get("fares") or _WORKER["fares"],
        job.get("timetable", _WORKER.get("timetable")),
        job["crs"],
        max_changes=job["max_changes"],
        day=job["day"],
        note=job["note"],
        attribution=job["attribution"],
        price_source=job["price_source"],
        base_path=job["base_path"],
        provider=job["provider"],
        mode=job["link_mode"],
        adults=job["adults"],
        network=job["network"],
        advertiser_id=job["advertiser_id"],
        publisher_id=job["publisher_id"],
        departure_limit=job["departures"],
    )
    payload["stations"] = [
        {"name": e["name"], "crs": e["crs"], "href": with_base(job["base_path"], f"/from/{e['slug']}/")}
        for e in job["others"]
    ]
    html = render_page(payload, budget_pounds=20, analytics=job["analytics"])
    return job["slug"], job["origin_name"], html
