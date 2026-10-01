"""Compare two feed snapshots and say what changed, for the operator.

A scheduled publication replaces a feed with no explanation. Every gate in this
project checks that the release it is about to make is *internally* sound --
links resolve, clearances are recorded, the byte budget holds -- and none of
them can say whether the prices moved, because a price moving is not a defect.
It is the ordinary consequence of a new download, and it is also the one thing
an operator most wants to see before the new artefact goes out: a feed that has
quietly lost a station, or moved a fare by a third, deserves a person to look
at it rather than a clean build to vouch for it.

So this tool reads two snapshots and prints the difference. It answers four
questions, and each one is a question a reader of the page would ask:

* **What moved?** The fares whose price changed, largest move first. A move is
  material when it is at least ``--material-pct`` of the old price *and* at
  least ``--material-pence`` in absolute terms -- both, because a fifty percent
  rise on a fifty-pence fare is not a signal and a five percent fall on a
  two-hundred-pound fare is not either.
* **What is gone, and what is new?** Fares the old snapshot carried and this one
  does not, and the reverse. A removed fare is a destination that has left the
  page, which is invisible in a build that succeeds.
* **What changed its conditions?** A fare that kept its price and changed its
  restriction code permits something different, and that is the most dangerous
  kind of change on this site, because the price column looks identical.
* **Whose page changed?** Per origin, the destinations gained and lost. This is
  the coverage question the chooser asks.

It also prints what each snapshot read, because a report that compares two
files and silently skipped one is a report about half a feed. And it names the
fares it could not attribute -- a fare whose flow record the feed does not
carry is counted, not dropped, because a dropped one would appear as a removal
that never happened.

Nothing here decides whether a change is acceptable. That threshold is the
operator's, so ``--fail-on-material`` exists as an opt-in refusal and is off by
default: a tool that refused on its own authority would be inventing a policy,
and a policy nobody chose is one nobody can argue with.

    python tools/feed_change_report.py --previous-feed feeds/previous --feed feeds/fares
    python tools/feed_change_report.py --previous-feed feeds/previous --feed feeds/fares \\
        --previous-timetable feeds/previous --timetable feeds/timetable --top 25
    python tools/feed_change_report.py --previous-feed a --feed b --json change.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Reach the project root whether run as `python tools/feed_change_report.py` or
# imported as tools.feed_change_report (the tests' way).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atoc_fares import FaresDb, format_pence  # noqa: E402
from atoc_timetable import TimetableDb  # noqa: E402

# A move must clear both bars. The defaults are a starting point an operator can
# move, not a judgement: 5% and a pound.
DEFAULT_MATERIAL_PCT = 5.0
DEFAULT_MATERIAL_PENCE = 100
DEFAULT_TOP = 10
# How many names a destination list prints before it is summarised. A reader
# wants to see the shape of a change, not four hundred rows of it.
DEFAULT_NAMES = 8


@dataclass(frozen=True, slots=True)
class FareLine:
    """One fare in one snapshot, named the way a reader would be told."""

    origin: str
    destination: str
    origin_key: str
    destination_key: str
    fare: str
    pence: int
    restriction: str

    def as_dict(self) -> dict[str, object]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "fare": self.fare,
            "pence": self.pence,
            "restriction": self.restriction,
        }


@dataclass(frozen=True, slots=True)
class PriceMove:
    """One fare that is in both snapshots at a different price."""

    before: FareLine
    after: FareLine
    delta: int
    percent: float

    def as_dict(self) -> dict[str, object]:
        return {
            "origin": self.after.origin,
            "destination": self.after.destination,
            "fare": self.after.fare,
            "was": self.before.pence,
            "now": self.after.pence,
            "percent": round(self.percent, 1),
        }


@dataclass(frozen=True, slots=True)
class RestrictionChange:
    """One fare whose condition changed while its price stood still."""

    before: FareLine
    after: FareLine

    def as_dict(self) -> dict[str, object]:
        return {
            "origin": self.after.origin,
            "destination": self.after.destination,
            "fare": self.after.fare,
            "was": self.before.restriction,
            "now": self.after.restriction,
        }


@dataclass(frozen=True, slots=True)
class CoverageChange:
    """One origin's set of priced destinations, before and after."""

    origin_key: str
    origin: str
    gained: tuple[str, ...]
    lost: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "origin": self.origin,
            "gained": list(self.gained),
            "lost": list(self.lost),
        }


@dataclass(frozen=True, slots=True)
class Freshness:
    """What a timetable snapshot says about the days it covers."""

    label: str
    schedules: int
    earliest: str
    latest: str
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "schedules": self.schedules,
            "earliest": self.earliest,
            "latest": self.latest,
            "note": self.note,
        }


@dataclass
class ChangeReport:
    """Everything the comparison found, held so it can be printed or written."""

    previous_label: str
    current_label: str
    previous_stats: dict[str, int]
    current_stats: dict[str, int]
    moves: list[PriceMove] = field(default_factory=list)
    removed: list[FareLine] = field(default_factory=list)
    added: list[FareLine] = field(default_factory=list)
    restrictions: list[RestrictionChange] = field(default_factory=list)
    coverage: list[CoverageChange] = field(default_factory=list)
    previous_cheapest: tuple[str, int] | None = None
    current_cheapest: tuple[str, int] | None = None
    previous_dearest: tuple[str, int] | None = None
    current_dearest: tuple[str, int] | None = None
    unattributed_previous: int = 0
    unattributed_current: int = 0
    previous_read: str = ""
    current_read: str = ""
    freshness: list[Freshness] = field(default_factory=list)
    material_pct: float = DEFAULT_MATERIAL_PCT
    material_pence: int = DEFAULT_MATERIAL_PENCE

    def as_dict(self) -> dict[str, object]:
        return {
            "previous": self.previous_label,
            "current": self.current_label,
            "counts": {
                "previous": self.previous_stats,
                "current": self.current_stats,
            },
            "materiality": {
                "percent": self.material_pct,
                "pence": self.material_pence,
            },
            "moves": [move.as_dict() for move in self.moves],
            "removed": [fare.as_dict() for fare in self.removed],
            "added": [fare.as_dict() for fare in self.added],
            "restrictionChanges": [change.as_dict() for change in self.restrictions],
            "coverage": [change.as_dict() for change in self.coverage],
            "cheapest": {
                "previous": self.previous_cheapest,
                "current": self.current_cheapest,
            },
            "dearest": {
                "previous": self.previous_dearest,
                "current": self.current_dearest,
            },
            "unattributed": {
                "previous": self.unattributed_previous,
                "current": self.unattributed_current,
            },
            "freshness": [item.as_dict() for item in self.freshness],
        }

    def material_count(self) -> int:
        """How many fares cleared both materiality bars."""
        return len(self.moves)


def _place(db: FaresDb, nlc: str) -> tuple[str, str]:
    """A location as a reader would name it, and the key coverage counts it by.

    The key is the station code where the feed carries one and the name where
    it does not, so a coverage line can always be read and never collides with
    another station's on the strength of a missing code.
    """
    location = db.locations_by_nlc.get(nlc)
    if location is None:
        return (f"location {nlc}", f"nlc:{nlc}")
    name = (location.name or "").strip()
    code = (location.crs or "").strip()
    if name and code:
        return (f"{name} ({code})", code)
    if name:
        return (name, name)
    if code:
        return (code, code)
    return (f"location {nlc}", f"nlc:{nlc}")


def fare_lines(db: FaresDb) -> tuple[dict[tuple[str, str, str, str], FareLine], int]:
    """Every fare in *db*, keyed by what identifies it across two downloads.

    The key is the pair of location codes, the route code and the ticket code,
    not the flow id: a flow id is the feed's own record key and can be
    renumbered between downloads, and a key that moved would report the whole
    catalogue as removed and added.

    A fare whose flow record is absent is counted and left out, because a fare
    the feed cannot attribute to a pair of places has no place on a reader's
    page and calling it a removal would be a finding about this tool.
    """
    lines: dict[tuple[str, str, str, str], FareLine] = {}
    unattributed = 0
    for flow_id, bucket in db.fares_by_flow.items():
        flow = db.flows.get(flow_id)
        if flow is None:
            unattributed += len(bucket)
            continue
        origin, origin_key = _place(db, flow.origin_nlc)
        destination, destination_key = _place(db, flow.destination_nlc)
        for ticket_code, fare in bucket.items():
            ticket = db.ticket_types.get(ticket_code)
            name = (ticket.name if ticket is not None else "") or ""
            key = (flow.origin_nlc, flow.destination_nlc, flow.route_code, ticket_code)
            lines[key] = FareLine(
                origin=origin,
                destination=destination,
                origin_key=origin_key,
                destination_key=destination_key,
                fare=name or ticket_code,
                pence=fare.pence,
                restriction=fare.restriction_code or "",
            )
    return lines, unattributed


def coverage_by_origin(db: FaresDb) -> dict[str, tuple[str, set[str]]]:
    """Every origin, with the set of destinations it prices at least one fare to."""
    out: dict[str, tuple[str, set[str]]] = {}
    for flow_id, bucket in db.fares_by_flow.items():
        if not bucket:
            continue
        flow = db.flows.get(flow_id)
        if flow is None:
            continue
        origin, origin_key = _place(db, flow.origin_nlc)
        _, destination_key = _place(db, flow.destination_nlc)
        name, destinations = out.setdefault(origin_key, (origin, set()))
        destinations.add(destination_key)
    return out


def _extreme(
    lines: dict[tuple[str, str, str, str], FareLine], *, dearest: bool
) -> tuple[str, int] | None:
    """The cheapest or dearest fare record in a snapshot, and where it runs.

    Every record in the feed, not every fare the page would publish: this is
    what the download contains, which is the question a feed comparison asks.
    """
    if not lines:
        return None
    line = (max if dearest else min)(lines.values(), key=lambda fare: fare.pence)
    return (f"{line.origin} to {line.destination}", line.pence)


def _is_material(before: int, after: int, *, pct: float, pence: int) -> tuple[bool, float]:
    """Whether a price move clears both bars, and how large it was in percent."""
    if before == 0:
        # A fare that cost nothing and now costs something is a change a reader
        # would see, and a percentage of zero is not a way to say so.
        return (after != 0, 100.0 if after else 0.0)
    change = (after - before) / before * 100
    return (abs(change) >= pct and abs(after - before) >= pence, change)


def compare(
    previous: FaresDb,
    current: FaresDb,
    *,
    previous_label: str,
    current_label: str,
    material_pct: float = DEFAULT_MATERIAL_PCT,
    material_pence: int = DEFAULT_MATERIAL_PENCE,
) -> ChangeReport:
    """Everything that differs between two loaded fares feeds."""
    before, before_unattributed = fare_lines(previous)
    after, after_unattributed = fare_lines(current)
    report = ChangeReport(
        previous_label=previous_label,
        current_label=current_label,
        previous_stats=previous.stats(),
        current_stats=current.stats(),
        unattributed_previous=before_unattributed,
        unattributed_current=after_unattributed,
        material_pct=material_pct,
        material_pence=material_pence,
    )
    report.previous_read = _read_line(previous_label, previous)
    report.current_read = _read_line(current_label, current)
    report.previous_cheapest = _extreme(before, dearest=False)
    report.current_cheapest = _extreme(after, dearest=False)
    report.previous_dearest = _extreme(before, dearest=True)
    report.current_dearest = _extreme(after, dearest=True)

    for key, line in after.items():
        was = before.get(key)
        if was is None:
            report.added.append(line)
            continue
        if was.pence != line.pence:
            material, change = _is_material(
                was.pence, line.pence, pct=material_pct, pence=material_pence
            )
            if material:
                report.moves.append(
                    PriceMove(before=was, after=line, delta=line.pence - was.pence, percent=change)
                )
        # A restriction that appears or disappears changes what the fare
        # permits at the same price, so it is reported whether the code moved or
        # only the knowledge base behind it did -- the code is what the feed
        # says, and the report claims nothing beyond it.
        if was.restriction != line.restriction:
            report.restrictions.append(RestrictionChange(before=was, after=line))
    for key, line in before.items():
        if key not in after:
            report.removed.append(line)

    # Biggest moves first, then the dearest fare involved, so the top of the
    # table is the change a reader would care about most rather than whichever
    # the feed happened to list first.
    report.moves.sort(key=lambda move: (-abs(move.percent), -move.after.pence))
    report.removed.sort(key=lambda fare: (-fare.pence, fare.origin, fare.destination))
    report.added.sort(key=lambda fare: (-fare.pence, fare.origin, fare.destination))
    report.restrictions.sort(
        key=lambda change: (change.after.origin, change.after.destination, change.after.fare)
    )
    report.coverage = _coverage(previous, current)
    return report


def _coverage(previous: FaresDb, current: FaresDb) -> list[CoverageChange]:
    """Origins whose priced destinations changed, biggest change first."""
    was = coverage_by_origin(previous)
    now = coverage_by_origin(current)
    changes: list[CoverageChange] = []
    for origin_key in set(was) | set(now):
        was_name, was_destinations = was.get(origin_key, ("", set()))
        now_name, now_destinations = now.get(origin_key, ("", set()))
        gained = tuple(sorted(now_destinations - was_destinations))
        lost = tuple(sorted(was_destinations - now_destinations))
        if not gained and not lost:
            continue
        changes.append(
            CoverageChange(
                origin_key=origin_key,
                origin=now_name or was_name,
                gained=gained,
                lost=lost,
            )
        )
    changes.sort(
        key=lambda change: (-len(change.gained) - len(change.lost), change.origin)
    )
    return changes


def _read_line(label: str, db: FaresDb) -> str:
    """What a snapshot's loader read, so a skipped file cannot pass as a fact."""
    summary = db.report.summary()
    return (
        f"{label}: {summary['files']} file(s), {summary['parsed']} record(s), "
        f"{summary['skipped']} skipped, {summary['skipped_files']} file(s) not read"
    )


def freshness(label: str, timetable: TimetableDb) -> Freshness:
    """The days a timetable snapshot covers, and how many services it holds."""
    days = sorted(
        day
        for schedule in timetable.schedules
        for day in (schedule.date_from, schedule.date_to)
        if day
    )
    if not days:
        return Freshness(
            label=label,
            schedules=len(timetable.schedules),
            earliest="",
            latest="",
            note="no schedule in this snapshot carries a validity window",
        )
    return Freshness(
        label=label,
        schedules=len(timetable.schedules),
        earliest=days[0],
        latest=days[-1],
    )


def _names(values: tuple[str, ...], limit: int) -> str:
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f", and {len(values) - limit} more"


def render(report: ChangeReport, *, top: int = DEFAULT_TOP, names: int = DEFAULT_NAMES) -> str:
    """The report as Markdown, so it can be read, pasted or committed."""
    out: list[str] = []
    out.append(f"# Feed change report: {report.previous_label} -> {report.current_label}")
    out.append("")
    out.append(
        f"A fare counts as moved when it moved at least {report.material_pct:g}% and at "
        f"least {format_pence(report.material_pence)}."
    )
    out.append("")

    out.append("## What was read")
    out.append("")
    out.append(f"- {report.previous_read}")
    out.append(f"- {report.current_read}")
    unattributed = [
        (report.previous_label, report.unattributed_previous),
        (report.current_label, report.unattributed_current),
    ]
    named = [f"{count} from {label}" for label, count in unattributed if count]
    if named:
        out.append(
            "- fares with no flow record, counted here rather than compared: "
            + "; ".join(named)
        )
    out.append("")

    out.append("## Counts")
    out.append("")
    out.append("| | previous | current | change |")
    out.append("|---|---:|---:|---:|")
    for key in sorted(set(report.previous_stats) | set(report.current_stats)):
        was = report.previous_stats.get(key, 0)
        now = report.current_stats.get(key, 0)
        change = f"{now - was:+d}" if now != was else "0"
        out.append(f"| {key.replace('_', ' ')} | {was} | {now} | {change} |")
    out.append("")

    for label, was, now in (
        ("cheapest fare record in the feed", report.previous_cheapest, report.current_cheapest),
        ("dearest fare record in the feed", report.previous_dearest, report.current_dearest),
    ):
        if was is None or now is None:
            continue
        # "moved from X to X" is a sentence that says a change happened when
        # none did, which is the one thing a change report must not do.
        if was[1] == now[1]:
            out.append(f"The {label} held at {format_pence(now[1])} ({now[0]}).")
        else:
            out.append(
                f"The {label} moved from {format_pence(was[1])} ({was[0]}) to "
                f"{format_pence(now[1])} ({now[0]})."
            )
    out.append("")

    out.append(f"## Prices that moved ({len(report.moves)})")
    out.append("")
    if not report.moves:
        out.append("No fare cleared both bars.")
    else:
        if len(report.moves) > top:
            out.append(f"The {top} largest of {len(report.moves)}, by size of move.")
        out.append("")
        out.append("| from | to | fare | was | now | move |")
        out.append("|---|---|---|---:|---:|---:|")
        for move in report.moves[:top]:
            out.append(
                f"| {move.after.origin} | {move.after.destination} | {move.after.fare} | "
                f"{format_pence(move.before.pence)} | {format_pence(move.after.pence)} | "
                f"{move.percent:+.1f}% |"
            )
    out.append("")

    out.append(f"## Fares removed ({len(report.removed)}) and added ({len(report.added)})")
    out.append("")
    if not report.removed and not report.added:
        out.append("The two snapshots carry the same fares.")
    else:
        for word, fares in (("removed", report.removed), ("added", report.added)):
            if not fares:
                out.append(f"- {word}: none")
                continue
            listed = tuple(
                f"{fare.origin} to {fare.destination} {fare.fare} at {format_pence(fare.pence)}"
                for fare in fares
            )
            out.append(f"- {word}, dearest first: {_names(listed, names)}")
    out.append("")

    out.append(f"## Fares whose restriction changed ({len(report.restrictions)})")
    out.append("")
    if not report.restrictions:
        out.append("No fare kept its price and changed its condition.")
    else:
        out.append("| from | to | fare | was | now |")
        out.append("|---|---|---|---|---|")
        for change in report.restrictions[:top]:
            out.append(
                f"| {change.after.origin} | {change.after.destination} | {change.after.fare} | "
                f"{change.before.restriction or 'none'} | {change.after.restriction or 'none'} |"
            )
        if len(report.restrictions) > top:
            out.append("")
            out.append(f"And {len(report.restrictions) - top} more.")
    out.append("")

    out.append(f"## Stations whose coverage changed ({len(report.coverage)})")
    out.append("")
    if not report.coverage:
        out.append("Every station prices the same destinations it did.")
    else:
        for change in report.coverage[:top]:
            parts = []
            if change.gained:
                parts.append(f"gains {len(change.gained)}: {_names(change.gained, names)}")
            if change.lost:
                parts.append(f"loses {len(change.lost)}: {_names(change.lost, names)}")
            out.append(f"- **{change.origin}** " + "; ".join(parts))
        if len(report.coverage) > top:
            out.append("")
            out.append(f"And {len(report.coverage) - top} more stations.")
    out.append("")

    if report.freshness:
        out.append("## Timetable freshness")
        out.append("")
        out.append("| snapshot | services | earliest | latest | |")
        out.append("|---|---:|---|---|---|")
        for item in report.freshness:
            out.append(
                f"| {item.label} | {item.schedules} | {item.earliest or '-'} | "
                f"{item.latest or '-'} | {item.note} |"
            )
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two fare-feed snapshots and report what changed.",
    )
    parser.add_argument("--feed", type=Path, required=True, help="the snapshot being published")
    parser.add_argument(
        "--previous-feed", type=Path, required=True, help="the snapshot it replaces"
    )
    parser.add_argument("--timetable", type=Path, help="timetable for the new snapshot")
    parser.add_argument(
        "--previous-timetable", type=Path, help="timetable for the snapshot it replaces"
    )
    parser.add_argument(
        "--material-pct",
        type=float,
        default=DEFAULT_MATERIAL_PCT,
        help="a price move counts at this percentage or above (default %(default)s)",
    )
    parser.add_argument(
        "--material-pence",
        type=int,
        default=DEFAULT_MATERIAL_PENCE,
        help="and at this many pence or more (default %(default)s)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help="rows per section (default %(default)s)",
    )
    parser.add_argument("--names", type=int, default=DEFAULT_NAMES, help=argparse.SUPPRESS)
    parser.add_argument("--json", type=Path, help="also write the report as JSON here")
    parser.add_argument(
        "--fail-on-material",
        action="store_true",
        help="exit 1 when any fare cleared both materiality bars",
    )
    arguments = parser.parse_args(argv)

    missing = [
        str(path)
        for path in (arguments.previous_feed, arguments.feed)
        if not Path(path).exists()
    ]
    if missing:
        for path in missing:
            print(f"{path} is not there. Point both snapshots at folders you have.", file=sys.stderr)
        return 2

    previous = FaresDb().load_feed(arguments.previous_feed)
    current = FaresDb().load_feed(arguments.feed)
    report = compare(
        previous,
        current,
        previous_label=str(arguments.previous_feed),
        current_label=str(arguments.feed),
        material_pct=arguments.material_pct,
        material_pence=arguments.material_pence,
    )
    for path, label in (
        (arguments.previous_timetable, str(arguments.previous_timetable)),
        (arguments.timetable, str(arguments.timetable)),
    ):
        if path is None:
            continue
        if not Path(path).exists():
            print(f"{path} is not there, so its freshness is not reported.", file=sys.stderr)
            continue
        report.freshness.append(freshness(label, TimetableDb().load_feed(path)))

    print(render(report, top=arguments.top, names=arguments.names))
    if arguments.json:
        arguments.json.write_text(
            json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {arguments.json}")
    if arguments.fail_on_material and report.material_count():
        print(
            f"{report.material_count()} fare(s) moved by at least "
            f"{report.material_pct:g}% and {format_pence(report.material_pence)}.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
