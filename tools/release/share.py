"""Build one share of the whole-network site, for the run's one service day.

    python -m tools.release.share --shard 3/12 --date 2026-10-22

Every priced station, not one of them: the release answers where a reader can go
from anywhere, so a reader who arrives from any station finds a page there. The
fares are the audited DTD feed and the times come from Network Rail's CIF under
the Open Government Licence, not from the DTD timetable (ADR-0073). A real-feed
build carries the notices its licences require and a privacy contact
(ADR-0032); the contact is the project's own unless PRIVACY_CONTACT overrides
it, which the build reads from the environment.

A share with no day is refused before it starts. Without `--date` every page
indexes the feed's whole schedule window and carries no day control: share 3 of
run 39618401726 wrote 78 pages in 139 minutes that way, where a dated share wrote
458 in 108 (docs/build-performance-findings.md, 21 October 2026).

The worker count is read from the runner, because every worker holds the whole
national timetable and a core count is not a memory budget (build_workers.py).
The share reports what it cost, and warns at NEARING_MINUTES of the step's
150-minute bound: a share that nears it means more shares, not a longer bound.

Exit codes: the build's own, or 1 when no day was named.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from build_workers import worker_budget
from tools.release import RELEASE, error, warning

#: Two thirds of the shard step's bound. `tests/test_workflows.py` holds it,
#: the bound and the share count to docs/build-performance-findings.md (A8 of
#: the 20 October 2026 poteto audit).
NEARING_MINUTES = 100

OUT = "_shard/index.html"

#: The places a page lists. Without a cap the release is about 1.14 GiB of HTML
#: against the 800 MiB budget `tools/page_bytes.py` holds it to, and the three
#: fare lists are most of a page; cutting every list to the cheapest 600 places
#: lands the twelve measured pages at 743 MiB with every fare below the stop
#: unchanged (docs/build-performance-findings.md, "A cap on the places a page
#: lists"). `tools/test_release.py` holds this number, because a cap that
#: drifted from the figure that justifies it would be a budget nobody measured.
PLACE_CAP = 600


def command(shard: str, day: str, workers: int, base_path: str = "") -> list[str]:
    build = [sys.executable, "build_demo_page.py", "--feed", "feeds/fares"]
    if "timetable" in RELEASE:
        build += ["--timetable", "feeds/nwr-schedule"]
    build += [
        "--knowledgebase", "feeds/knowledgebase",
        "--date", day,
        "--max-places", str(PLACE_CAP),
        "--all-origins",
        "--workers", str(workers),
        "--shard", shard,
        "--out", OUT,
        "--notices", "nre,rdg,ogl,accuracy",
        "--require-live-reviewed-codes",
    ]
    if base_path:
        build += ["--base-path", base_path]
    return build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shard", required=True, help="N/M, this share of M")
    parser.add_argument("--date", default="", help="the service day the build job named")
    args = parser.parse_args(argv)
    if not args.date:
        error(
            "service day",
            "the build job named no day for this run, and a share built without one indexes the "
            "whole feed for every page and has no day control; rerun the workflow.",
        )
        return 1
    started = time.monotonic()
    code = subprocess.run(command(args.shard, args.date, worker_budget(), os.environ.get("SITE_BASE_PATH", ""))).returncode
    minutes = int((time.monotonic() - started) // 60)
    print(f"share {args.shard} took {minutes} minutes (nearing at {NEARING_MINUTES})")
    if minutes >= NEARING_MINUTES:
        warning(
            "The share is nearing its bound",
            f"share {args.shard} took {minutes} minutes of the step's bound: split the shares rather than raise the bound.",
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
