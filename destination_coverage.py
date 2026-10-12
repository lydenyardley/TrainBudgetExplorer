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

from atoc_fares import FaresDb, is_pseudo_station  # noqa: E402
from feeds_cli import add_feed_args  # noqa: E402

# The primary class a station keeps when no source names its settlement. The
# name is the old filter label; the value is what the payload carries.
UNSOURCED = "other"

# A build with 2,500 origins can meet the same unsourced station from hundreds
# of pages. The summary names a bounded number of them and counts the rest, so
# the output is a report rather than a wall.
NAMED_LIMIT = 20

# The share audit A2 asked for: this page's destinations with no settlement
# class, as a percentage. It is reported for the worst origins only, and only
# when the origin has priced enough destinations for a percentage to mean
# something: below ten, one unsourced station moves the share by ten points
# and tiny pages would fill the ranking with noise rather than the gaps worth
# closing.
SHARE_MIN_DESTINATIONS = 10
SHARE_LIMIT = 3

# The sentinel budget used everywhere a build asks "everything this origin can
# reach". It is repeated here rather than imported so this module does not
# import the page builder, which imports this module.
EVERYTHING_PENCE = 1_000_000

# The selector's reasons for dropping a row that can never become a published
# destination: the NLC has no location record, the location carries no station
# code, or the station is a fare-construction point with no train behind it.
# These rows are a hard ceiling on coverage -- a destination that cannot be
# named has no settlement class either, and no reviewed list reaches it
# (audit A3).
UNNAMEABLE_REASONS = (
    "destination_has_no_location_record",
    "destination_has_no_station_code",
    "destination_is_a_fare_construction_point",
)


def unnameable_from_tally(tally: dict[str, int]) -> int:
    """How many destination rows can never become a published destination."""
    return sum(tally.get(reason, 0) for reason in UNNAMEABLE_REASONS)


class ConditionalLossReport:
    """The destinations each origin loses to the conditional-fare rule.

    Counted from the two selectors' answers rather than from the fare rows the
    loop rejected, because a rejected fare usually changes nothing. In a
    60-origin sample the loop rejected 2,450 single fare rows and 30 origins
    lost any destination at all, so a tally of rejected fares would overstate
    the loss by two orders of magnitude.
    """

    def __init__(self) -> None:
        self._lost: dict[str, int] = {}
        self._singles_lost: dict[str, int] = {}
        self._returns_lost: dict[str, int] = {}
        self._kept: dict[str, int] = {}
        self._reach: dict[str, int] = {}
        self._totals = 0
        self._origins = 0
        self._emptied: list[str] = []

    def measure(self, fares: FaresDb, origin_crs: str, day=None) -> int:
        """Record what one origin loses. Returns that origin's lost count."""
        options = {"adults": 1, "day": day}
        kept_singles = fares.page_single_destinations_within(
            origin_crs, EVERYTHING_PENCE, **options
        )
        kept_returns = fares.page_destinations_within(
            origin_crs, EVERYTHING_PENCE, **options
        )
        every_single = fares.page_single_destinations_within(
            origin_crs, EVERYTHING_PENCE, include_conditional=True, **options
        )
        every_return = fares.page_destinations_within(
            origin_crs, EVERYTHING_PENCE, include_conditional=True, **options
        )

        kept = {row.crs for row in kept_singles} | {row.crs for row in kept_returns}
        singles = {row.crs for row in every_single}
        returns = {row.crs for row in every_return}
        lost = (singles | returns) - kept
        singles_lost = len(singles - kept)
        returns_lost = len(returns - kept)

        key = origin_crs.strip().upper()
        self._kept[key] = len(kept)
        self._reach[key] = len(singles | returns)
        if lost:
            self._lost[key] = len(lost)
            self._singles_lost[key] = singles_lost
            self._returns_lost[key] = returns_lost
            if not kept:
                self._emptied.append(key)
        self._totals += len(kept)
        self._origins += 1
        return len(lost)

    def measure_all(self, fares: FaresDb, origins, day=None) -> int:
        """Measure a list of origins. Returns how many lost anything."""
        for crs in origins:
            self.measure(fares, crs, day)
        return len(self._lost)

    def lost_by_origin(self) -> dict[str, int]:
        """Destinations lost, per origin, worst first. Absent means nothing."""
        return dict(sorted(self._lost.items(), key=lambda item: (-item[1], item[0])))

    def singles_by_origin(self) -> dict[str, int]:
        """Of the loss, how much is the single list. Absent means none."""
        return dict(self._singles_lost)

    def returns_by_origin(self) -> dict[str, int]:
        """Of the loss, how much is the return list. Absent means none."""
        return dict(self._returns_lost)

    def empties_the_origin(self) -> list[str]:
        """Origins that keep no destination at all once the rule applies."""
        return list(self._emptied)

    def message(self) -> str:
        """The summary, or an empty string when nothing was lost anywhere."""
        if not self._lost:
            return ""
        ranked = self.lost_by_origin()
        # The share is against what the origin reached with the conditional
        # fares in, because that is the only figure the two runs share. Against
        # what it kept, an origin that loses one of four reads as 100% and one
        # the rule empties divides by zero.
        shares = []
        for origin, count in list(ranked.items())[:3]:
            reach = self._reach.get(origin, 0)
            if reach:
                shares.append(f"{round(100 * count / reach)}% of {origin}'s {reach}")
        summary = (
            f"{sum(ranked.values()):,} destinations across {len(ranked)} of "
            f"{self._origins} origins are lost once a child, group or event fare "
            f"cannot win the cheapest slot, counted against {self._totals:,} that remain"
        )
        if shares:
            summary += ". Worst shares: " + "; ".join(shares)
        if self._emptied:
            summary += (
                f". {len(self._emptied)} origins keep no destination at all: "
                + ", ".join(self._emptied[:10])
            )
        return summary

    def report(self) -> None:
        """Print the summary to stderr when there is something to say."""
        if message := self.message():
            print(f"warning: {message}", file=sys.stderr)

    def print_table(self) -> None:
        """Print every origin that lost anything, one line each."""
        singles = self.singles_by_origin()
        returns = self.returns_by_origin()
        for origin, count in self.lost_by_origin().items():
            print(
                f"  {origin} loses {count} destinations "
                f"({singles.get(origin, 0)} singles, {returns.get(origin, 0)} returns)"
            )


class UnsourcedReport:
    """The unsourced destinations a build published, deduped by station.

    One report is shared by the whole build, so a station met from fifty
    origins is named once, and the origins that reached it are kept: "Bristol
    Parkway is unsourced" is less actionable than "unsourced from 12 origins".
    """

    def __init__(self) -> None:
        self._origins: dict[str, set[str]] = {}
        self._names: dict[str, str] = {}
        self._origin_totals: dict[str, set[str]] = {}
        self._origin_unnameable: dict[str, int] = {}

    def _note_total(self, crs: str, origin: str | None) -> None:
        """Record one destination of ``origin``, sourced or not.

        The denominator of the share is every destination the origin would
        publish, so it is counted for every row the callers pass, not only the
        unsourced ones they return.
        """
        code = str(crs or "").strip().upper()
        if code and origin:
            self._origin_totals.setdefault(origin.strip().upper(), set()).add(code)

    def note(self, crs: str, name: str, origin: str | None = None) -> None:
        """Record one unsourced station. A blank code is ignored, not invented."""
        code = str(crs or "").strip().upper()
        if not code:
            return
        self._names.setdefault(code, str(name or code).strip())
        if origin:
            self._origins.setdefault(code, set()).add(origin.strip().upper())

    def note_unnameable(self, origin: str | None, count: int) -> None:
        """Record destination rows one origin lost to a missing name (audit A3).

        These rows never reach the unsourced set -- they are dropped before a
        station exists to classify -- so they are counted apart, per origin,
        beside the unsourced count they cap.
        """
        if origin and count:
            key = origin.strip().upper()
            self._origin_unnameable[key] = self._origin_unnameable.get(key, 0) + count

    def unnameable_by_origin(self) -> dict[str, int]:
        """The per-origin counts of destination rows no source could ever name."""
        return dict(self._origin_unnameable)

    def from_payload(self, payload: dict, origin: str | None = None) -> int:
        """Record the unsourced rows in one page's payload; return how many.

        A station unsourced in any ticket mode is unsourced on the page, and
        the page offers the same filters for all three, so all three are read.
        The destination counts behind the share are the union of the three
        modes, which is what the page publishes.
        """
        found = 0
        origin_row = payload.get("origin")
        where = origin or (
            origin_row.get("crs") if isinstance(origin_row, dict) else None
        )
        unnameable = payload.get("unnameableFareCount")
        if isinstance(unnameable, int):
            self.note_unnameable(where, unnameable)
        for key in ("destinations", "singleDestinations", "anytimeDestinations"):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                # A zone or coach pseudo-station is not a place a reader goes,
                # so it is neither named nor counted in the share (audit A6).
                if is_pseudo_station(row.get("crs", "")):
                    continue
                self._note_total(row.get("crs", ""), where)
                if row.get("destinationType") == UNSOURCED:
                    self.note(row.get("crs", ""), row.get("name", ""), where)
                    found += 1
        return found

    def note_fares_rows(self, fares: FaresDb, rows, origin: str | None = None) -> int:
        """Record the unsourced stations among a query's feed rows.

        The rows come from the same published selector the pages are built from
        (``FaresDb.priced_destinations_within``), so the report describes what
        would be published rather than a broader question.
        """
        found = 0
        for row in rows:
            if is_pseudo_station(row.crs):
                continue
            self._note_total(row.crs, origin)
            if fares.destination_type(row.crs) == UNSOURCED:
                self.note(row.crs, row.station, origin)
                found += 1
        return found

    def from_feed(self, fares: FaresDb, origins, day=None) -> int:
        """Record the unsourced priced destinations for each origin in the feed.

        Zone and coach pseudo-stations are skipped as origins as well: their
        pages are not written (audit A6), so the reach measured from them
        describes no reader's journey.
        """
        found = 0
        for crs in origins:
            location = fares.locations_by_crs.get(crs)
            if location is not None and is_pseudo_station(crs):
                continue
            tally: dict[str, int] = {}
            rows = fares.priced_destinations_within(
                crs, EVERYTHING_PENCE, adults=1, day=day, tally=tally
            )
            self.note_unnameable(crs, unnameable_from_tally(tally))
            found += self.note_fares_rows(fares, rows, crs)
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

    def extract_origin(self, origin: str | None) -> dict:
        """One origin's share of this report, as plain data.

        The per-origin slice the priced-facts store keeps beside the count, so
        a warm build replays the coverage instead of re-querying the fares for
        it (T6). Totals are the priced destinations the share is over;
        unsourced pairs the station with the name the report would print.
        """
        key = (origin or "").strip().upper()
        totals = sorted(self._origin_totals.get(key, ()))
        unsourced = sorted(
            (code, self._names.get(code, code))
            for code, origins in self._origins.items()
            if key in origins
        )
        return {
            "totals": totals,
            "unsourced": [list(pair) for pair in unsourced],
            "unnameable": self._origin_unnameable.get(key, 0),
        }

    def replay_origin(self, origin: str | None, data: dict) -> None:
        """Restore one origin's share from ``extract_origin``'s data.

        The same notes the live queries would have written, so a replayed
        report reads exactly as a queried one: the exit code, the message and
        the worst shares cannot tell them apart.
        """
        key = (origin or "").strip().upper()
        if not isinstance(data, dict):
            return
        for code in data.get("totals") or ():
            self._note_total(code, key)
        for pair in data.get("unsourced") or ():
            code, name = pair
            self.note(code, name, key)
        self.note_unnameable(key, int(data.get("unnameable") or 0))

    def worst_shares(self, limit: int = SHARE_LIMIT) -> list[tuple[str, int, int]]:
        """The (origin, unsourced, total) shares, highest first.

        Only origins with a gap and enough destinations for the percentage to
        mean anything are ranked; a 0% share is the report's success state, not
        a finding. The ranking is what makes the number actionable: one page
        publishing mostly unclassified stations is a different defect from a
        single oddity appearing on every page.
        """
        unsourced_by_origin: dict[str, int] = {}
        for origins in self._origins.values():
            for origin in origins:
                unsourced_by_origin[origin] = unsourced_by_origin.get(origin, 0) + 1
        ranked = []
        for origin, total in self._origin_totals.items():
            hits = unsourced_by_origin.get(origin, 0)
            if hits and len(total) >= SHARE_MIN_DESTINATIONS:
                ranked.append((origin, hits, len(total)))
        ranked.sort(key=lambda item: (-item[1] / item[2], item[0]))
        return ranked[:limit]

    def message(self) -> str:
        """A bounded, human-readable summary. Empty when there is nothing to say."""
        parts: list[str] = []
        if self:
            rows = self.stations()
            named = []
            for code, name in rows[:NAMED_LIMIT]:
                origins = len(self._origins.get(code, ()))
                named.append(f"{code} {name}" + (f" (from {origins} origins)" if origins > 1 else ""))
            if len(rows) > NAMED_LIMIT:
                named.append(f"... and {len(rows) - NAMED_LIMIT} more")
            plural = "station has" if len(rows) == 1 else "stations have"
            summary = (
                f"{len(rows)} priced {plural} no settlement class from any source: "
                + "; ".join(named)
            )
            shares = self.worst_shares()
            if shares:
                summary += ". Worst shares: " + "; ".join(
                    f"{round(100 * hits / total)}% of {origin}'s {total} destinations"
                    for origin, hits, total in shares
                )
            parts.append(summary)
        # The feed's own ceiling on coverage, reported whether or not the
        # classifiable gap is still open. It is a fact about the feed, so a
        # reviewed pass that closes the list below must not silence the number
        # that says what is left: the two halves are counted apart precisely so
        # that one cannot be read as the other (audit A3).
        unnameable = sum(self._origin_unnameable.values())
        if unnameable:
            parts.append(
                f"A further {unnameable:,} destination rows can never be named as "
                "a destination at all (no location record, no station code, or a "
                "fare-construction point with no train behind it), counted per origin"
            )
        return ". ".join(parts)

    def report(self) -> None:
        """Print the summary to stderr when there is something to say."""
        if message := self.message():
            print(f"warning: {message}", file=sys.stderr)

    def exit_code(self, strict: bool, ceiling: int | None = None) -> int:
        """0 to continue, or 2 to refuse the build.

        ``strict`` is ``--fail-on-unsourced``: any gap refuses.
        ``ceiling`` is ``--unsourced-ceiling``: a count above it refuses, so a
        CI run can hold today's measured number and stop the gap regrowing
        between deliberate review passes (audit D2). The two are independent, so
        both are evaluated however they were given: passing both flags must not
        quietly drop the ceiling.
        """
        count = len(self)
        if ceiling is not None and count > ceiling:
            print(
                f"error: {count} unsourced priced destination"
                f"{'' if count == 1 else 's'} {'exceeds' if count == 1 else 'exceed'} "
                f"the ceiling of {ceiling} (--unsourced-ceiling). Add a reviewed "
                "class in atoc_fares.REVIEWED_SETTLEMENT_FALLBACKS to lower "
                "the count, or raise the ceiling deliberately with a reason.",
                file=sys.stderr,
            )
            return 2
        if strict and count:
            plural = "" if count == 1 else "s"
            print(
                f"error: refusing to publish with {count} unsourced priced "
                f"destination{plural} (--fail-on-unsourced). Add a reviewed class in "
                "atoc_fares.REVIEWED_SETTLEMENT_FALLBACKS, or drop the flag to publish anyway.",
                file=sys.stderr,
            )
            return 2
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_feed_args(
        parser,
        feed_default=Path("feeds") / "fares" / "dtd-fares.zip",
        fares_only=True,
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
    parser.add_argument(
        "--unsourced-ceiling",
        type=int,
        default=None,
        metavar="N",
        help="exit non-zero when more than N priced destinations are unsourced; "
        "the recorded value for the current feed lives in the CI workflow, so "
        "the count cannot regrow silently between review passes",
    )
    parser.add_argument(
        "--conditional-loss",
        action="store_true",
        help="report the destinations each origin loses when a child, group or "
        "event fare cannot win its cheapest slot, measured by asking the page's "
        "own selectors both ways",
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
    code = report.exit_code(args.fail_on_unsourced, ceiling=args.unsourced_ceiling)

    if args.conditional_loss:
        loss = ConditionalLossReport()
        loss.measure_all(fares, origins)
        loss.report()
        loss.print_table()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
