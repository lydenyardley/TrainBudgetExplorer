"""Propose the settlement class of every reviewed station fallback, from evidence.

``LONDON_STATION_CRS``, ``MAJOR_UK_STATION_FALLBACKS`` and
``REVIEWED_SETTLEMENT_FALLBACKS`` in ``atoc_fares`` are reviewed lists: a person
read the feed's station names and wrote down the settlement each station serves
and the band that settlement belongs to. They are the right way to record a
judgement and the wrong way to keep one current, because a wrong entry is
silent. The code resolves, the class applies, the page builds, and the gate that
catches a dead code has nothing to say -- a reader is offered a "city" filter
that contains a village, and nothing in the build can see it.

So this tool prints the evidence for every entry, on demand, and refuses to do
the writing. For each reviewed code it shows the feed's own name for the station
(the authority on which station a code means), the reviewed class, and what the
ONS built-up-area workbook says. It splits the entries into three:

* **named** -- the workbook names this station, so the entry can never apply and
  the gate refuses the build. A person should delete the entry.
* **decide** -- the workbook names a settlement the name lookup cannot see, and
  the band it gives disagrees with the reviewed class. Newton-le-Willows is the
  worked example: the feed writes ``NEWTON LE WILL``, the workbook writes
  ``Newton-le-Willows``, and the entry said village where the workbook says
  town. This is the class of error a hard gate cannot catch and a person can.
* **agreed** -- the workbook's band and the reviewed class match, so the entry is
  doing the job it exists for. These are listed so a reviewer reads "40
  unchanged" rather than re-checking them.

The near-miss search is deliberately *not* wired into the parser. Prefix
matching is unsound -- ``BATHGATE`` is not Bath, ``BRADFORD`` is not Bradford on
Avon -- which is why the reader matches whole names only, and why this output is
a proposal list rather than a lookup. A person decides; nothing is pasted.

    python -m tools.propose_reviewed_settlements
    python -m tools.propose_reviewed_settlements --feed feeds/fares
    python -m tools.propose_reviewed_settlements --only decide
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path


from trainbudget.fares.atoc_fares import (
    LONDON_STATION_CRS,
    MAJOR_UK_STATION_FALLBACKS,
    ONS_BUILT_UP_AREAS_FILE_URL,
    ONS_BUILT_UP_AREAS_DATASET_URL,
    REVIEWED_SETTLEMENT_FALLBACKS,
    FaresDb,
)
from trainbudget.feeds.feeds_cli import add_feed_args
from tools.propose_fare_construction_stations import resolve_feed

# A near miss needs a shared prefix long enough to be evidence of the same
# settlement and an extension short enough to be a qualifier: "-on-Tweed",
# "-upon-Tyne", "-on-Sea" and "OWS" are all inside these bounds, while a
# three-letter settlement name is not evidence of anything and made the report
# mostly noise ("Ham" is not Hamilton, "Heath" is not Heathrow).
NEAR_MISS_MIN_PREFIX = 8
NEAR_MISS_SLACK = 12

NAMED = "named"
DECIDE = "decide"
AGREED = "agreed"
# A code this feed does not carry is the build's own gate to report, not this
# tool's: the list may be perfectly good and the feed may be the wrong one. It
# gets its own verdict so the report cannot say "306 entries to delete" about a
# feed it plainly failed to read, which is a claim that is both false and
# alarming in exactly the direction a reader would act on.
ABSENT = "absent"
VERDICTS = (NAMED, DECIDE, AGREED, ABSENT)


def reviewed_entries() -> dict[str, str]:
    """Every reviewed settlement entry, keyed by CRS.

    The London list is one class for every code it names, so it is read as
    "city" here: a London station inside Greater London has no ONS row to
    match, which is why those codes are on a list at all.
    """
    entries = {crs: "city" for crs in LONDON_STATION_CRS}
    entries.update(MAJOR_UK_STATION_FALLBACKS)
    entries.update(REVIEWED_SETTLEMENT_FALLBACKS)
    return entries


def download_areas(db: FaresDb) -> dict[str, dict[str, str]]:
    """The ONS built-up-area workbook, as the parser reads it.

    Downloaded here rather than reused from a run so the report states the band
    as of this invocation, and so the tool can be run against a feed without a
    cache. A read failure is the tool's own error, not a silent empty report:
    "nothing disagrees" would be a claim it cannot support.
    """
    request = urllib.request.Request(
        ONS_BUILT_UP_AREAS_FILE_URL,
        headers={"User-Agent": "TrainBudgetExplorer/1.0 (reviewed settlement proposal)"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return db._read_ons_built_up_areas(response.read())


def near_misses(
    db: FaresDb, name: str, areas: dict[str, dict[str, str]]
) -> list[tuple[str, str]]:
    """Settlements the workbook names that the name lookup cannot reach.

    ``(workbook name, class)``, sorted. The rule is one normalised name being a
    short extension of the other, which is how a station name and its workbook
    spelling drift apart: the feed abbreviates, the workbook qualifies.
    """
    station = db._normalise_settlement_name(name)
    if not station:
        return []
    found: dict[str, str] = {}
    for key, meta in areas.items():
        if key == station:
            continue
        shorter, longer = (station, key) if len(station) <= len(key) else (key, station)
        shared = len(shorter)
        if (
            shared >= NEAR_MISS_MIN_PREFIX
            and longer.startswith(shorter)
            and len(longer) - shared <= NEAR_MISS_SLACK
        ):
            found[meta["name"]] = meta["type"]
    return sorted(found.items())


def proposals(
    db: FaresDb,
    stations: dict,
    areas: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    """One row per reviewed code, with the evidence and a verdict.

    Every row carries the feed's name because that is the authority on which
    station a code means: a code whose class was copied from the wrong station
    is the error this tool exists to find, and the name is what gives it away.
    """
    rows: list[dict[str, object]] = []
    for crs, reviewed in sorted(reviewed_entries().items()):
        location = stations.get(crs)
        name = str(getattr(location, "name", "") or "").strip()
        row: dict[str, object] = {
            "crs": crs,
            "name": name or "<NOT IN THIS FEED>",
            "reviewed": reviewed,
            "band": None,
            "matches": [],
            "verdict": AGREED,
        }
        if not name:
            row["verdict"] = ABSENT
            rows.append(row)
            continue
        candidates = db._settlement_name_candidates(name)
        matched = next((key for key in candidates if key in areas), None)
        if matched is not None:
            row["band"] = areas[matched]["type"]
            row["verdict"] = NAMED if areas[matched]["type"] != reviewed else AGREED
        else:
            row["matches"] = near_misses(db, name, areas)
            # A disagreement matters only when nothing backs the reviewed
            # class. A station whose name also reads as a settlement of the
            # reviewed band is corroborated; "Newcastle" matching both
            # Newcastle Emlyn and Newcastle upon Tyne is corroborated by the
            # second and contradicted by the first, and that is a judgement
            # for a person rather than a defect to report.
            row["verdict"] = (
                DECIDE
                if row["matches"] and all(kind != reviewed for _, kind in row["matches"])
                else AGREED
            )
        rows.append(row)
    return rows


def render(rows: list[dict[str, object]], *, only: str | None) -> str:
    """The report: the rows worth reading, then the tally, then the rest."""
    chosen = [row for row in rows if only is None or row["verdict"] == only]
    lines: list[str] = []
    # Agreement is the tally's job, not a list of three hundred rows -- but a
    # reader who asked for it has said they want it.
    groups = [
        (DECIDE, "the workbook names a settlement the lookup cannot see, and disagrees"),
        (NAMED, "the workbook names this station, so the entry can never apply"),
    ]
    if only == AGREED:
        groups.append((AGREED, "the reviewed class and the workbook agree"))
    for verdict, heading in groups:
        group = [row for row in chosen if row["verdict"] == verdict]
        if not group:
            continue
        lines.append(f"{heading} ({len(group)}):")
        for row in group:
            matches = ", ".join(f"{kind} {n}" for n, kind in row["matches"]) or "-"
            lines.append(
                f"  {row['crs']}  {str(row['name'])[:24]:24} reviewed {row['reviewed']:<10} {matches}"
            )
        lines.append("")
    missing = [row for row in rows if row["verdict"] == ABSENT]
    if missing:
        codes = [str(row["crs"]) for row in missing]
        lines.append(
            f"{len(missing)} reviewed code(s) this feed does not carry: "
            + ", ".join(codes[:12])
            + (" ..." if len(codes) > 12 else "")
        )
        if len(missing) == len(rows):
            lines.append(
                "  That is every entry, so this feed holds none of the reviewed "
                "stations: the report below says nothing about the lists. Check "
                "the --feed path before reading anything into it."
            )
        else:
            lines.append(
                "  The build's own gate names these; a code the feed dropped is "
                "not evidence that the entry was wrong."
            )
        lines.append("")
    tally = {verdict: sum(1 for row in rows if row["verdict"] == verdict) for verdict in VERDICTS}
    lines.append(
        f"{len(rows)} reviewed entries: {tally[NAMED]} to delete, "
        f"{tally[DECIDE]} to decide, {tally[AGREED]} in agreement, "
        f"{tally[ABSENT]} not in this feed."
    )
    lines.append(
        "A near miss is a suggestion, not a match: prefix matching is unsound "
        "(Bathgate is not Bath), so none of it is wired into the parser. The "
        f"workbook is {ONS_BUILT_UP_AREAS_DATASET_URL}"
    )
    if not chosen:
        lines.insert(0, f"Nothing to show for {only or 'every verdict'}.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_feed_args(
        parser,
        feed_default=Path("feeds") / "fares" / "dtd-fares.zip",
        fares_only=True,
    )
    parser.add_argument(
        "--only",
        choices=VERDICTS,
        default=None,
        help="print one verdict only: decide for the disagreements, named for the "
        "entries the workbook already covers, agreed for the rest",
    )
    args = parser.parse_args(argv)
    if not args.feed.exists():
        print(f"no feed at {args.feed}", file=sys.stderr)
        return 2
    db = FaresDb()
    db.load_feed(resolve_feed(args.feed))
    try:
        areas = download_areas(db)
    except (OSError, ValueError) as error:
        print(f"the ONS workbook could not be read: {error}", file=sys.stderr)
        return 2
    print(render(proposals(db, db.locations_by_crs, areas), only=args.only))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
