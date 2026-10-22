"""Check the merged site is the release the workflow declares.

    python -m tools.release.manifest --site _site

S07: the release is a set of routes, written beside the pages and proved
against them by the build. This checks the set an operator or a host would
read, so a manifest that went missing between the build and the publish cannot
pass unnoticed.

And it checks the pages are the shape RELEASE declares. A release that publishes
times must carry them on every station page: a build that lost its timetable, or
a page that silently answered nowhere for every station, would ship a release
whose opening sentence promises times it does not show. The payload is read as
JSON rather than grepped, because it is minified and a pattern written with a
space after the colon would match nothing. A site with no station page fails:
a glob that matches nothing would otherwise report nothing wrong.

Exit codes: 0 the manifest and the pages agree with the release, 1 they do not.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tools.release import RELEASE, error

HAS_JOURNEYS = re.compile(r'"hasJourneys":\s*(true|false)')


def problems(site: Path, with_times: bool = "timetable" in RELEASE) -> list[tuple[str, str]]:
    """(title, message) for each way the site is not the declared release."""
    manifest = site / "release-manifest.json"
    if not manifest.is_file() or not manifest.stat().st_size:
        return [("release manifest", f"the build wrote no {manifest.as_posix()}, so the routes this release serves are not stated anywhere")]
    routes = len(json.loads(manifest.read_text(encoding="utf-8"))["routes"])
    pages = sum(1 for _ in site.rglob("index.html"))
    print(f"the manifest names {routes} route(s) and the folder holds {pages} page(s)")
    if routes != pages:
        return [("release manifest", f"the manifest names {routes} route(s) but the folder holds {pages} page(s), so the release and the artifact disagree")]
    stations = sorted(site.glob("from/*/index.html"))
    if not stations:
        return [("journeys", "no station pages were written, so this build's shape is unverified")]
    expected = "true" if with_times else "false"
    wrong = []
    for path in stations:
        found = HAS_JOURNEYS.search(path.read_text(encoding="utf-8"))
        if not found:
            wrong.append(f"{path.as_posix()} (no hasJourneys field at all)")
        elif found.group(1) != expected:
            wrong.append(f"{path.as_posix()} (hasJourneys is {found.group(1)})")
    if not wrong:
        return []
    if with_times:
        message = (
            "these station pages carry no journey times, so this build published prices under a release "
            "that declares the timetable: " + " ".join(wrong) + ". The release publishes times from "
            "Network Rail's CIF under the Open Government Licence (ADR-0073); load the timetable in the "
            "share build, or declare the release as fares only and build without it."
        )
    else:
        message = "these station pages carry journey times, which a fares-only release does not declare: " + " ".join(wrong)
    return [("journeys", message)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", type=Path, default=Path("_site"))
    args = parser.parse_args(argv)
    found = problems(args.site)
    for title, message in found:
        error(title, message)
    if found:
        return 1
    print("every station page carries the shape the release declares: " + ",".join(RELEASE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
