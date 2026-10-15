"""Rebuild ``reference-data/destination-facets.json`` from its named sources.

The checked-in file is what a build reads, so it is a generated artefact: this
tool is the canonical way to regenerate it, and the facet registry in
``atoc_fares`` is the single place a facet's source is declared. Adding a facet
means adding a registry entry and a reader, then running this.

Only the station list is read from the feed. Fares, flows and restrictions are
not needed to classify a settlement, and the national download has millions of
them, so the tool reads the LOC file and stops.

    python -m tools.regenerate_destination_facets
    python -m tools.regenerate_destination_facets --feed feeds/fares/dtd-fares.zip
    python -m tools.regenerate_destination_facets --keep-unavailable island

``--keep-unavailable`` carries the existing value for the named facets instead
of downloading them. That is how a source that is temporarily unreachable is
carried forward, and the tool prints which facets it could not read rather than
writing a file that quietly lost them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile


from atoc_fares import (
    DESTINATION_FACET_SOURCES,
    LOCATION_TYPE_SOURCE,
    SUPPORTED_DESTINATION_FACETS,
    FaresDb,
)
from feeds_cli import add_feed_args

DEFAULT_FEED = Path("feeds") / "fares" / "dtd-fares.zip"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "reference-data" / "destination-facets.json"


def load_stations(feed: Path) -> FaresDb:
    """Return a FaresDb holding only this feed's stations.

    The national LOC file is a few megabytes and the rest of the download is
    two orders of magnitude larger, so this reads only the station records
    rather than parsing the fares feed it ships with.
    """
    db = FaresDb()
    if feed.suffix.lower() == ".zip":
        with zipfile.ZipFile(feed) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".loc")]
            if not names:
                raise SystemExit(f"{feed} contains no .loc file")
            text = archive.read(names[0]).decode("latin-1")
    else:
        loc = sorted(feed.rglob("*.loc")) or sorted(feed.glob("*.LOC"))
        if not loc:
            raise SystemExit(f"{feed} contains no .loc file")
        text = loc[0].read_bytes().decode("latin-1")
    for line in text.splitlines():
        if len(line.strip()) < 27:
            continue
        try:
            db._load_locations(line)
        except ValueError:
            continue
    return db


def facets_for(db: FaresDb, keep_unavailable: set[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Return the facet mapping, and the facets that could not be read."""
    mapping: dict[str, list[str]] = {}
    unavailable: list[str] = []
    for facet in DESTINATION_FACET_SOURCES:
        if facet.key in keep_unavailable:
            print(f"{facet.key}: kept the previously recorded stations")
            continue
        before = len(db.location_facets_by_crs)
        try:
            db._apply_destination_facet(facet)
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            unavailable.append(facet.key)
            print(f"{facet.key}: unavailable ({error})", file=sys.stderr)
            continue
        matched = sum(
            1 for facets in db.location_facets_by_crs.values() if facet.key in facets
        )
        print(f"{facet.key}: {matched} stations ({facet.coverage})")
        if not matched and len(db.location_facets_by_crs) == before:
            unavailable.append(facet.key)
    for crs, facets in db.location_facets_by_crs.items():
        if facets:
            mapping.setdefault(crs, []).extend(facets)
    return mapping, unavailable


def build(feed: Path, out: Path, keep_unavailable: set[str]) -> dict:
    db = load_stations(feed)
    if keep_unavailable and out.is_file():
        # Seed the previous file so a kept facet keeps what it had rather than
        # silently becoming empty.
        db._load_location_types_json(json.loads(out.read_text(encoding="utf-8")))
    mapping, unavailable = facets_for(db, keep_unavailable)
    payload = {
        "schema": 2,
        "source": LOCATION_TYPE_SOURCE,
        "feed": feed.as_posix(),
        "stations": len(db.locations_by_crs),
        "facetSources": {
            facet.key: {
                "name": facet.source,
                "url": facet.url,
                "coverage": facet.coverage,
            }
            for facet in DESTINATION_FACET_SOURCES
        },
        "supportedFacets": sorted(SUPPORTED_DESTINATION_FACETS),
        "facets": {crs: sorted(facets) for crs, facets in sorted(mapping.items())},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(payload['facets'])} station facet records to {out}")
    if unavailable:
        print(
            "not recorded: " + ", ".join(unavailable) + " (pass --keep-unavailable to carry them)",
            file=sys.stderr,
        )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_feed_args(parser, feed_default=DEFAULT_FEED, fares_only=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="where to write the facet reference data")
    parser.add_argument(
        "--keep-unavailable",
        action="append",
        default=[],
        choices=sorted(SUPPORTED_DESTINATION_FACETS),
        help="keep the recorded value for this facet instead of downloading it",
    )
    args = parser.parse_args(argv)
    build(args.feed, args.out, set(args.keep_unavailable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
