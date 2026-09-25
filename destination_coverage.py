"""Name the priced destinations no source could classify.

Every page filters by settlement class, so a station the ONS workbook does not
name has no class a reader can ask for. That gap was invisible: the page simply
offered fewer chips, and a station silently dropped out of every settlement
filter. The "No settlement band" chip made it visible once, badly, and removing
it made it invisible again -- which is worse, because nothing was watching the
number.

This module is the thing that watches it. A build collects the unsourced
destinations it published and prints a bounded summary naming them, so the next
person can add a reviewed class instead of wondering where a station went.
``--fail-on-unsourced`` turns that summary into a refusal, for a release build
where an unclassified destination is a defect rather than a note.

It reports; it does not classify. Guessing a settlement band from a station's
name is exactly what ADR-0026 rejected, and a tool that guessed would undo that
decision silently, once per build.

    python destination_coverage.py --feed feeds/fares/dtd-fares.zip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from atoc_fares import FaresDb  # noqa: E402

# The primary class a station keeps when no source names its settlement. The
# name is the old filter label; the value is what the payload carries.
UNSOURCED = "other"

# A build with 2,500 origins can meet the same unsourced station from hundreds
# of pages. The summary names a bounded number of them and counts the rest, so
# the output is a report rather than a wall.
NAMED_LIMIT = 20

# The sentinel budget used everywhere a build asks "everything this origin can
# reach". It is repeated here rather than imported so this module does not
# import the page builder, which imports this module.
EVERYTHING_PENCE = 1_000_000


class UnsourcedReport:
    """The unsourced destinations a build published, deduped by station.

    One report is shared by the whole build, so a station met from fifty
    origins is named once, and the origins that reached it are kept: "Bristol
    Parkway is unsourced" is less actionable than "unsourced from 12 origins".
    """

    def __init__(self) -> None:
        self._origins: dict[str, set[str]] = {}
        self._names: dict[str, str] = {}

    def note(self, crs: str, name: str, origin: str | None = None) -> None:
        """Record one unsourced station. A blank code is ignored, not invented."""
        code = str(crs or "").strip().upper()
        if not code:
            return
        self._names.setdefault(code, str(name or code).strip())
        if origin:
            self._origins.setdefault(code, set()).add(origin.strip().upper())

    def from_payload(self, payload: dict, origin: str | None = None) -> int:
        """Record the unsourced rows in one page's payload; return how many.

        A station unsourced in any ticket mode is unsourced on the page, and the
        page offers the same filters for all three, so all three are read.
        """
        found = 0
        origin_row = payload.get("origin")
        where = origin or (
            origin_row.get("crs") if isinstance(origin_row, dict) else None
        )
        for key in ("destinations", "singleDestinations", "anytimeDestinations"):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict) and row.get("destinationType") == UNSOURCED:
                    self.note(row.get("crs", ""), row.get("name", ""), where)
                    found += 1
        return found

    def note_fares_rows(self, fares: FaresDb, rows, origin: str | None = None) -> int:
        """Record the unsourced stations among a query's feed rows.

        The rows come from the same published selector the pages are built from,
        so the report describes what would be published rather than a broader
        question.
        """
        found = 0
        for row in rows:
            if fares.destination_type(row.crs) == UNSOURCED:
                self.note(row.crs, row.station, origin)
                found += 1
        return found

    def from_feed(self, fares: FaresDb, origins, day=None) -> int:
        """Record the unsourced priced destinations for each origin in the feed."""
        found = 0
        for crs in origins:
            found += self.note_fares_rows(
                fares,
                fares.publishable_destinations_within(
                    crs, EVERYTHING_PENCE, adults=1, day=day
                ),
                crs,
            )
        return found

    def __len__(self) -> int:
        return len(self._names)

    def __bool__(self) -> bool:
        return bool(self._names)

    def stations(self) -> list[tuple[str, str]]:
        """The (code, name) pairs, most widely reached first."""
        return sorted(
            self._names.items(),
            key=lambda item: (-len(self._origins.get(item[0], ())), item[0]),
        )

    def message(self) -> str:
        """A bounded, human-readable summary. Empty when nothing is unsourced."""
        if not self:
            return ""
        rows = self.stations()
        named = []
        for code, name in rows[:NAMED_LIMIT]:
            origins = len(self._origins.get(code, ()))
            named.append(f"{code} {name}" + (f" (from {origins} origins)" if origins > 1 else ""))
        if len(rows) > NAMED_LIMIT:
            named.append(f"... and {len(rows) - NAMED_LIMIT} more")
        plural = "station has" if len(rows) == 1 else "stations have"
        return (
            f"{len(rows)} priced {plural} no settlement class from any source: "
            + "; ".join(named)
        )

    def report(self) -> None:
        """Print the summary to stderr when there is something to say."""
        if message := self.message():
            print(f"warning: {message}", file=sys.stderr)

    def exit_code(self, strict: bool) -> int:
        """0 to continue, or 2 to refuse the build under ``--fail-on-unsourced``."""
        if not strict or not self:
            return 0
        plural = "" if len(self) == 1 else "s"
        print(
            f"error: refusing to publish with {len(self)} unsourced priced "
            f"destination{plural} (--fail-on-unsourced). Add a reviewed class in "
            "atoc_fares.REVIEWED_SETTLEMENT_FALLBACKS, or drop the flag to publish anyway.",
            file=sys.stderr,
        )
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--feed",
        type=Path,
        default=Path("feeds") / "fares" / "dtd-fares.zip",
        help="fares .zip or a directory of feed files",
    )
    parser.add_argument(
        "--origin",
        action="append",
        default=[],
        help="check only this origin (repeatable). Default checks every station in the feed",
    )
    parser.add_argument(
        "--fail-on-unsourced",
        action="store_true",
        help="exit non-zero when any priced destination is unsourced",
    )
    args = parser.parse_args(argv)

    fares = FaresDb().load_feed(args.feed) if args.feed.exists() else None
    if fares is None:
        print(f"error: no feed at {args.feed}", file=sys.stderr)
        return 2
    origins = args.origin or sorted(fares.locations_by_crs)
    missing = [crs for crs in origins if crs not in fares.locations_by_crs]
    if missing:
        print(
            f"error: {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not in this feed",
            file=sys.stderr,
        )
        return 2

    report = UnsourcedReport()
    report.from_feed(fares, origins)
    report.report()
    return report.exit_code(args.fail_on_unsourced)


if __name__ == "__main__":
    raise SystemExit(main())
