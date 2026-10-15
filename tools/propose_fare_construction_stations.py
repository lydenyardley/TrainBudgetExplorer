"""Propose station codes for the reviewed fare-construction list, from names.

``FARE_CONSTRUCTION_CRS`` in ``atoc_fares`` is a reviewed list: someone read
the feed's station names and wrote down the ones the fare system draws rather
than the ones a train calls at. A zone boundary or a named coach stop is a
fare-construction point -- the feed records a fare change there -- so it must
not become a destination a reader is offered, or an origin they are asked to
depart from. The list is the right way to record that and the wrong way to
keep it current: a new zone boundary arrives with the next feed revision and a
substring test would catch it, but a substring test would also drop a real
station called Coach House, and would stop catching the zone the day the feed
renamed it.

This tool does the reading and refuses to do the writing. It loads the feed's
station records, applies the name markers, and prints every station they catch
**with the code and the name that caught it**, marking which are already on
the reviewed list and which are not. A person reads that and decides.

It writes nothing, ever, for the reason every proposal in this project writes
nothing: a proposed list is not a reviewed one, and pasting one into
``atoc_fares`` as if a person had checked each entry is the same false claim
as the unreviewed shortcuts this project has already removed.

    python -m tools.propose_fare_construction_stations
    python -m tools.propose_fare_construction_stations --feed feeds/fares
    python -m tools.propose_fare_construction_stations --emit-code
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


from atoc_fares import (
    FARE_CONSTRUCTION_CRS,
    FARE_CONSTRUCTION_NAME_MARKERS,
    looks_like_fare_construction,
)
from feeds_cli import add_feed_args
from tools.regenerate_destination_facets import load_stations


def resolve_feed(feed: Path) -> Path:
    """The file to read, whether the path is the archive or its folder.

    A DTD download is often handed to the tools as the folder the downloader
    wrote (``feeds/fares``) and as the archive inside it. The station reader
    takes one or the other, so a folder holding exactly one archive is opened
    through to it rather than reported as having no station file.
    """
    if not feed.is_dir():
        return feed
    archives = sorted(child for child in feed.iterdir() if child.suffix.lower() == ".zip")
    return archives[0] if len(archives) == 1 else feed


def proposals(stations: dict) -> list[tuple[str, str, bool]]:
    """The stations whose names look like fare-construction points.

    ``(crs, name, already_reviewed)`` for each, sorted by code. The third
    element is what lets a reviewer read the output as "two new, ten
    unchanged" instead of re-checking twelve names it agreed with last time.
    """
    found = [
        (crs, name.strip(), crs in FARE_CONSTRUCTION_CRS)
        for crs, location in stations.items()
        if looks_like_fare_construction(name := getattr(location, "name", location))
    ]
    return sorted(found)


def render(rows: list[tuple[str, str, bool]], *, emit_code: bool) -> str:
    """The report: every proposal, and how each one stands today."""
    lines: list[str] = []
    for crs, name, reviewed in rows:
        state = "on the reviewed list" if reviewed else "NOT YET REVIEWED"
        lines.append(f"  {crs}  {name:<20} {state}")
    new = [row for row in rows if not row[2]]
    missing = sorted(FARE_CONSTRUCTION_CRS - {crs for crs, _, _ in rows})
    summary = [
        f"{len(rows)} station name(s) carry {', '.join(FARE_CONSTRUCTION_NAME_MARKERS)}:",
        f"  {len(rows) - len(new)} already on the reviewed list, {len(new)} to decide.",
    ]
    if missing:
        summary.append(
            f"  {len(missing)} reviewed code(s) match no station carrying those markers: "
            + ", ".join(missing)
        )
        summary.append(
            "    A reviewed code with no matching name is usually a station the feed "
            "renamed or withdrew; check it before adding anything new."
        )
    if not rows:
        summary.append("  None. If this feed has zone boundaries, the markers changed.")
    if emit_code and new:
        summary.append("")
        summary.append("codes to review and add by hand:")
        summary.append('    ' + " ".join(f'"{crs}",' for crs, _, _ in new))
    return "\n".join(summary + ([""] + lines if rows else []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_feed_args(
        parser,
        feed_default=Path("feeds") / "fares" / "dtd-fares.zip",
        fares_only=True,
    )
    parser.add_argument(
        "--emit-code",
        action="store_true",
        help="print the un-reviewed codes in a pasteable form, still for a person to check",
    )
    args = parser.parse_args(argv)
    if not args.feed.exists():
        print(f"no feed at {args.feed}", file=sys.stderr)
        return 2
    db = load_stations(resolve_feed(args.feed))
    rows = proposals(db.locations_by_crs)
    print(render(rows, emit_code=args.emit_code))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
