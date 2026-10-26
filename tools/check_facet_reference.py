"""Refuse a release whose checked-in facet reference data has drifted from the registry.

`reference-data/destination-facets.json` is a generated artefact: a build reads
it as one more facet source, and `tools/regenerate_destination_facets.py` is the
only thing that should write it. Nothing tied the two together, so the file went
stale in silence. On 7 October 2026 the checked-in copy held 7 facets and 294
station records against the registry's 10 and 463, three of those sources having
shipped a release earlier, and neither a build nor a test said a word.

This tool is that missing tie. It regenerates the file from its sources into a
temporary directory and compares the result with the copy in the repository, so
the failure lands in a pull request or in CI rather than in a build that
classifies stations from a description of the registry that was true last month.

    python -m tools.check_facet_reference
    python -m tools.check_facet_reference --feed feeds/fares/dtd-fares.zip
    python -m tools.check_facet_reference --keep-unavailable heritage

Exit codes: 0 the checked-in copy matches the registry, 1 it differs and every
difference is named, 2 a facet could not be read at all or the checked-in copy is
missing. The third code exists because comparing a regeneration that lost a facet
against a file that has it would report the loss as movement, and a reader would
then go looking for a change to the registry that never happened.

**What this tool will not do.** It does not write the file. Regenerating is a data
change a person reviews with the per-facet counts in front of them, and a check
that repaired itself would hide the drift it exists to show.

**What it cannot compare.** `--keep-unavailable` carries a facet whose source is a
website that may be unreachable. A facet kept that way is reported as not compared
rather than compared against itself, because the regeneration never read it. Its
registry entry still is compared, so a facet that changed its source, url or
coverage is caught whether or not its source answered today.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple


from trainbudget.fares.atoc_fares import SUPPORTED_DESTINATION_FACETS
from trainbudget.feeds.feeds_cli import add_feed_args
from tools.regenerate_destination_facets import DEFAULT_FEED, build

DEFAULT_REFERENCE = (
    Path(__file__).resolve().parent.parent / "reference-data" / "destination-facets.json"
)

#: How many codes one line names before it counts the rest. A facet that gains a
#: hundred stations is one line an operator has to read, not a hundred of them.
CODES_SHOWN = 12

# The fields the registry owns, and therefore the fields worth comparing. `feed`
# and `source` are deliberately absent. The first is the path this check was
# pointed at rather than anything the registry says, and the second is the
# regenerator's own constant, so neither can be drift between the file and the
# registry, and a difference in either would be a false alarm.
COMPARED_FIELDS = ("schema", "stations")


class Comparison(NamedTuple):
    """What a fresh regeneration says about the copy in the repository."""

    moved: int
    lines: list[str]
    unreadable: list[str]
    kept: list[str]


def facet_stations(payload: dict) -> dict[str, set[str]]:
    """Return facet key -> the station codes a payload records for it."""
    per: dict[str, set[str]] = {}
    for crs, facets in (payload.get("facets") or {}).items():
        for facet in facets or ():
            per.setdefault(str(facet), set()).add(str(crs))
    return per


def _named(codes: set[str]) -> str:
    """The codes a line names, with the rest counted rather than listed."""
    shown = sorted(codes)
    if len(shown) <= CODES_SHOWN:
        return ", ".join(shown)
    return ", ".join(shown[:CODES_SHOWN]) + f" and {len(shown) - CODES_SHOWN} more"


def compare(
    recorded: dict,
    regenerated: dict,
    kept: frozenset[str] = frozenset(),
) -> Comparison:
    """Return every way two facet payloads disagree, and what could not be read.

    ``kept`` names the facets this run was told to carry forward instead of
    reading. Their stations are not compared, because a facet nobody read has
    nothing to be compared with.

    A facet the checked-in copy records stations for, and the regeneration
    records none for, is reported as unread rather than as movement. That is the
    regenerator's own judgement (an empty facet is a source that did not answer),
    and the other reading would send a reader looking for a registry change that
    never happened. A facet the regeneration has and the checked-in copy does not
    is movement, which is the case this check exists for: a source that shipped
    without the file being regenerated.
    """
    lines: list[str] = []
    unreadable: list[str] = []

    for field in COMPARED_FIELDS:
        if recorded.get(field) != regenerated.get(field):
            lines.append(
                f"{field}: {recorded.get(field)!r} in the checked-in copy, "
                f"{regenerated.get(field)!r} regenerated"
            )

    here = set(recorded.get("supportedFacets") or ())
    there = set(regenerated.get("supportedFacets") or ())
    for name in sorted(there - here):
        lines.append(
            f"supportedFacets: {name} is regenerated and the checked-in copy has no such facet"
        )
    for name in sorted(here - there):
        lines.append(
            f"supportedFacets: {name} is in the checked-in copy and the registry no longer declares it"
        )

    recorded_sources = recorded.get("facetSources") or {}
    regenerated_sources = regenerated.get("facetSources") or {}
    for name in sorted(set(regenerated_sources) - set(recorded_sources)):
        lines.append(f"facetSources: {name} is regenerated and the checked-in copy has no entry for it")
    for name in sorted(set(recorded_sources) - set(regenerated_sources)):
        lines.append(f"facetSources: {name} is in the checked-in copy and the registry no longer declares it")
    for name in sorted(set(recorded_sources) & set(regenerated_sources)):
        before = recorded_sources[name] or {}
        after = regenerated_sources[name] or {}
        for field in sorted(set(before) | set(after)):
            if before.get(field) != after.get(field):
                lines.append(
                    f"facetSources.{name}.{field}: {before.get(field)!r} in the checked-in copy, "
                    f"{after.get(field)!r} regenerated"
                )

    recorded_per = facet_stations(recorded)
    regenerated_per = facet_stations(regenerated)
    moved = 0
    for name in sorted(set(recorded_per) | set(regenerated_per)):
        if name in kept:
            continue
        before = recorded_per.get(name, set())
        after = regenerated_per.get(name, set())
        if before == after:
            continue
        if before and not after:
            unreadable.append(name)
            continue
        moved += 1
        named = [f"facet {name}: {len(before)} in the checked-in copy, {len(after)} regenerated"]
        if after - before:
            named.append(f"added {_named(after - before)}")
        if before - after:
            named.append(f"removed {_named(before - after)}")
        lines.append("; ".join(named))

    return Comparison(moved=moved, lines=lines, unreadable=unreadable, kept=sorted(kept))


def check(feed: Path, reference: Path, keep_unavailable: set[str]) -> int:
    """Regenerate the facets, compare them with the checked-in copy, and report.

    The reference is read before anything else, so a checkout without it fails in
    a second rather than after a regeneration nobody can compare.
    """
    if not reference.is_file():
        print(f"error: no checked-in facet reference data at {reference}", file=sys.stderr)
        return 2
    recorded = json.loads(reference.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / reference.name
        # The regenerator narrates every facet as it reads it, which is what an
        # operator wants from a regeneration and noise from a check. A facet it
        # could not read still reaches this tool's own report below.
        with contextlib.redirect_stdout(io.StringIO()):
            regenerated = build(feed, out, keep_unavailable)

    result = compare(recorded, regenerated, frozenset(keep_unavailable))
    for name in result.kept:
        print(f"facet {name}: kept, so not compared")
    for line in result.lines:
        print(line)
    if result.unreadable:
        for name in result.unreadable:
            print(
                f"facet {name}: the checked-in copy records stations for it and the "
                "regeneration read none",
                file=sys.stderr,
            )
        print(
            f"error: could not read {len(result.unreadable)} facet(s): "
            + ", ".join(result.unreadable)
            + ". Pass --keep-unavailable for a source that is unreachable.",
            file=sys.stderr,
        )
        return 2
    if result.lines:
        # Counted as differences, not as moved facets: a source that shipped with
        # no station behind it yet moves no facet and still makes the file wrong,
        # and a red run reading "0 facet(s) moved" would send its reader looking
        # for the mistake in the wrong place.
        stations = f", {result.moved} of them stations" if result.moved else ""
        print(
            f"{len(result.lines)} difference(s) against the registry{stations}: run "
            "python -m tools.regenerate_destination_facets and commit the result"
        )
        return 1
    records = len(regenerated.get("facets") or {})
    facets = len(regenerated.get("supportedFacets") or ())
    print(f"the checked-in copy matches the registry: {facets} facet(s), {records} station record(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_feed_args(parser, feed_default=DEFAULT_FEED, fares_only=True)
    parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REFERENCE,
        help="the checked-in copy to compare against",
    )
    parser.add_argument(
        "--keep-unavailable",
        action="append",
        default=[],
        choices=sorted(SUPPORTED_DESTINATION_FACETS),
        help="report this facet as not compared, for a source that is unreachable",
    )
    args = parser.parse_args(argv)
    return check(args.feed, args.reference, set(args.keep_unavailable))


if __name__ == "__main__":
    raise SystemExit(main())
