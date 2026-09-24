"""Read the ATOC/RDG fares feed and answer "what can I reach for under £X?".

The feed is fixed-width text. Each spec below is (field_name, width) in file
order, so a field's position is the running sum of the widths before it. That
mirrors how the published record layouts are defined.

Fares are per person. A party buys one ticket per adult unless the ticket type
says otherwise, so a party price is adults x per-adult.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from atoc_restrictions import RailcardRestrictionRow, RestrictionIndex
from parse_report import ParseReport, count, decode_lines, read_feed_files

ROUNDING_STEP_PENCE = 5

# "1/3 off" is the published discount for the mainstream UK railcards, Two
# Together included. The feed carries the authoritative rules in its dis and frr
# files; see adr/ADR-0002-budget-semantics-and-railcards.md for the upgrade path.
RAILCARD_DISCOUNT = Fraction(2, 3)

# The real feed's standard-return catalogue contains a family of ITX
# placeholder records. They are not purchasable public fares: the current
# audit found EIS/EIF/IF1/IF3/IS0/IS1/IS3 and LIS/LIF at the £0.05/£0.10
# minimum with restriction GA. Keep the names explicit so a future catalogue
# rename cannot silently reintroduce them, while the ITX name check catches
# new members of the same family.
PLACEHOLDER_TICKET_CODES = frozenset({
    "EIS", "EIF", "IF1", "IF3", "IS0", "IS1", "IS3", "LIS", "LIF",
})


def _offsets(spec: tuple[tuple[str, int], ...]) -> dict[str, tuple[int, int]]:
    offsets: dict[str, tuple[int, int]] = {}
    position = 0
    for name, width in spec:
        offsets[name] = (position, position + width)
        position += width
    return offsets


def _text(line: str, offsets: dict[str, tuple[int, int]], name: str) -> str:
    start, end = offsets[name]
    return line[start:end].strip()


FLOW_F = (
    ("update_marker", 1),
    ("record_type", 1),
    ("origin_nlc", 4),
    ("destination_nlc", 4),
    ("route_code", 5),
    ("status_code", 3),
    ("usage_code", 1),
    ("direction", 1),
    ("end_date", 8),
    ("start_date", 8),
    ("toc", 3),
    ("cross_london", 1),
    ("non_standard_discount", 1),
    ("publication_indicator", 1),
    ("flow_id", 7),
)

FLOW_T = (
    ("update_marker", 1),
    ("record_type", 1),
    ("flow_id", 7),
    ("ticket_code", 3),
    ("fare_pence", 8),
    ("restriction_code", 2),
)

# Only the leading fields are needed. Later location fields carry railcard,
# zone, and LU data that budget discovery does not read.
LOCATION = (
    ("update_marker", 1),
    ("record_type", 1),
    ("uic_code", 7),
    ("end_date", 8),
    ("start_date", 8),
    ("quote_date", 8),
    ("admin_area_code", 3),
    ("nlc", 4),
    ("description", 16),
    ("crs", 3),
    # The next ten characters hold location attributes this reader does not
    # interpret. Keeping them in the layout preserves the published offsets.
    ("location_attributes", 10),
    ("group_nlc", 4),
)

TICKET_TYPE = (
    ("update_marker", 1),
    ("ticket_code", 3),
    ("end_date", 8),
    ("start_date", 8),
    ("quote_date", 8),
    ("description", 15),
    ("tkt_class", 1),
    ("tkt_type", 1),
    ("tkt_group", 1),
    ("last_valid_day", 8),
    ("max_passengers", 3),
    ("min_passengers", 3),
    ("max_adults", 3),
    ("min_adults", 3),
    ("max_children", 3),
    ("min_children", 3),
    ("restricted_by_date", 1),
    ("restricted_by_train", 1),
)

RAILCARD = (
    ("railcard_code", 3),
    ("end_date", 8),
    ("start_date", 8),
    ("quote_date", 8),
    ("holder_type", 1),
    ("description", 20),
    ("restricted_by_issue", 1),
    ("restricted_by_area", 1),
    ("restricted_by_train", 1),
    ("restricted_by_date", 1),
    ("master_code", 3),
    ("display_flag", 1),
    ("max_passengers", 3),
    ("min_passengers", 3),
    ("max_holders", 3),
    ("min_holders", 3),
    ("max_accompanying_adults", 3),
    ("min_accompanying_adults", 3),
    ("max_adults", 3),
    ("min_adults", 3),
)

MINIMUM_FARE = (
    ("railcard_code", 3),
    ("ticket_code", 3),
    ("end_date", 8),
    ("start_date", 8),
    ("minimum_fare_pence", 8),
)

# A record shorter than its layout is truncated, and slicing it anyway hands
# back empty fields that read as real values: a cut off fare becomes 0, and a cut
# off flow id becomes a flow keyed on nothing. The width of the fields actually
# read is the cheapest test that says so.
def _read_width(spec: tuple[tuple[str, int], ...], last_field: str) -> int:
    offsets = _offsets(spec)
    end = offsets[last_field][1]
    return end


FLOW_F_WIDTH = _read_width(FLOW_F, "flow_id")
FLOW_T_WIDTH = _read_width(FLOW_T, "restriction_code")

FLOW_F_OFFSETS = _offsets(FLOW_F)
FLOW_T_OFFSETS = _offsets(FLOW_T)
LOCATION_OFFSETS = _offsets(LOCATION)
TICKET_TYPE_OFFSETS = _offsets(TICKET_TYPE)
RAILCARD_OFFSETS = _offsets(RAILCARD)
MINIMUM_FARE_OFFSETS = _offsets(MINIMUM_FARE)

STANDARD_CLASS = "2"
RETURN_TYPE = "R"

# The reviewed public selector. These are the ticket codes whose real ticket
# type is standard class, return, marked unrestricted by train, and whose name
# is exactly ANYTIME DAY R in the DTD feed. The code set is fixed here rather
# than derived by a name test, so a future ticket-catalogue change cannot widen
# what the site publishes without a person editing this table.
#
# The real DTD feed carries fares for 8AE, HX9, SDR and XAR. AAB and E2R are
# listed because the ticket catalogue defines them as the same product; they are
# harmless to include and would otherwise be an unexplained omission.
REVIEWED_ANYTIME_DAY_RETURN_TICKETS: dict[str, str] = {
    "8AE": "ANYTIME DAY R",
    "AAB": "ANYTIME DAY R",
    "E2R": "ANYTIME DAY R",
    "HX9": "ANYTIME DAY R",
    "SDR": "ANYTIME DAY R",
    "XAR": "ANYTIME DAY R",
}


@dataclass(frozen=True)
class Location:
    nlc: str
    crs: str
    name: str
    group_nlc: str


@dataclass(frozen=True)
class TicketType:
    code: str
    name: str
    tkt_class: str
    tkt_type: str
    restricted_by_train: bool

    @property
    def is_standard_return(self) -> bool:
        return self.tkt_class == STANDARD_CLASS and self.tkt_type == RETURN_TYPE

    @property
    def is_standard_single(self) -> bool:
        return self.tkt_class == STANDARD_CLASS and self.tkt_type == "S"


@dataclass(frozen=True)
class Flow:
    flow_id: str
    origin_nlc: str
    destination_nlc: str
    route_code: str
    direction: str
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class Fare:
    ticket_code: str
    pence: int
    restriction_code: str


@dataclass(frozen=True)
class Railcard:
    code: str
    name: str
    min_adults: int
    max_adults: int


@dataclass(frozen=True)
class Reachable:
    crs: str
    station: str
    ticket_code: str
    ticket_name: str
    standard_pence: int
    best_pence: int
    railcard_pence: int | None
    party_pence: int
    off_peak: bool
    restriction_code: str
    # The fare's flow context is retained so a page builder can evaluate a
    # railcard rule again without guessing which route produced the row.
    route_code: str
    origin_nlc: str
    destination_nlc: str


def format_pence(pence: int) -> str:
    return f"£{pence // 100}.{pence % 100:02d}"


def _round_down_to(value: Fraction, step: int) -> int:
    units = value.numerator // (value.denominator * step)
    return units * step


def _parse_dtd_date(value: str) -> date | None:
    """Parse a blank or DDMMYYYY feed date without guessing its format."""
    if not value:
        return None
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"DTD date {value!r} is not DDMMYYYY")
    return date(int(value[4:8]), int(value[2:4]), int(value[0:2]))


def _require_width(line: str, width: int, what: str) -> None:
    """Refuse a record that is shorter than the fields it needs."""
    if len(line) < width:
        raise ValueError(f"{what} record is {len(line)} characters, needs {width}")


def _tally(counts: dict[str, int] | None, reason: str) -> None:
    """Count why a fare or flow did not become a destination, when asked."""
    if counts is not None:
        counts[reason] = counts.get(reason, 0) + 1


class FaresDb:
    """Indexes the feed files that budget discovery reads."""

    def __init__(self) -> None:
        self.locations_by_nlc: dict[str, Location] = {}
        self.locations_by_crs: dict[str, Location] = {}
        # DTD location reference data classifies stations as cities, towns, or
        # other places. It is a separate KB feed from the fares LOC file, so
        # keep it as an optional index rather than pretending LOC has this
        # information.
        self.location_types_by_crs: dict[str, str] = {}
        # One station code can hold several location codes, and a real feed does
        # this for most towns. Flows are keyed by location code, so a query has
        # to consider all of them or it misses fares that are right there.
        self.nlcs_by_crs: dict[str, set[str]] = {}
        self.ticket_types: dict[str, TicketType] = {}
        self.railcards: dict[str, Railcard] = {}
        self.flows: dict[str, Flow] = {}
        self.fares_by_flow: dict[str, dict[str, Fare]] = {}
        # Flows grouped by every location code from which they can be queried.
        # Most flows are usable only from their recorded origin. A reversible
        # (``direction == "R"``) flow is also usable with its endpoints swapped,
        # so it is indexed under both locations. destinations_within asks the
        # same question per origin; scanning every flow for each origin would
        # turn a full-network build into 2,500 full scans.
        self.flows_by_origin_nlc: dict[str, list[Flow]] = {}
        self.minimum_fares: dict[tuple[str, str], int] = {}
        self.restrictions = RestrictionIndex()
        self.report = ParseReport()
        self.files_read = self.report.files_read
        # A single-origin build only needs fares queryable from that origin.
        # Reversible flows count in both directions. The national feed has
        # millions of unrelated fare records, so retaining
        # every Fare object makes the local app spend most of its time building
        # prices it will never query. This is None for the normal/full database.
        self._focus_origin_nlcs: set[str] | None = None

    # -- loading ---------------------------------------------------------

    def _preload_focus_locations(self, path: str | Path, origin_crs: str) -> None:
        """Find the origin NLCs before the stream reaches the FFL file.

        DTD archives put LOC after FFL. A quick LOC-only pass lets the FFL
        reader discard unrelated fare records as it streams, without retaining
        a second copy of the feed or changing the normal full-load behaviour.
        """
        root = Path(path)
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if not child.is_file():
                    continue
                if child.suffix.lower() == ".loc":
                    with child.open("rb") as handle:
                        for line in decode_lines(handle, ParseReport()):
                            self._load_location_for_focus(line, origin_crs)
                elif child.suffix.lower() == ".zip" and zipfile.is_zipfile(child):
                    with zipfile.ZipFile(child) as archive:
                        for name in sorted(archive.namelist()):
                            if not name.lower().endswith(".loc"):
                                continue
                            with archive.open(name) as handle:
                                for line in decode_lines(handle, ParseReport()):
                                    self._load_location_for_focus(line, origin_crs)
        elif root.suffix.lower() == ".zip" and zipfile.is_zipfile(root):
            with zipfile.ZipFile(root) as archive:
                for name in sorted(archive.namelist()):
                    if not name.lower().endswith(".loc"):
                        continue
                    with archive.open(name) as handle:
                        for line in decode_lines(handle, ParseReport()):
                            self._load_location_for_focus(line, origin_crs)

    def _load_location_for_focus(self, line: str, origin_crs: str) -> None:
        if _text(line, LOCATION_OFFSETS, "record_type").upper() != "L":
            return
        if _text(line, LOCATION_OFFSETS, "crs").upper() != origin_crs:
            return
        if self._focus_origin_nlcs is not None:
            self._focus_origin_nlcs.add(_text(line, LOCATION_OFFSETS, "nlc"))

    def load_feed(self, path: str | Path, *, focus_origin: str | None = None) -> "FaresDb":
        """Load a feed, optionally retaining fares for one origin only.

        ``focus_origin`` is for a one-origin page build. It is deliberately not
        used by audit or multi-origin builds, whose results must describe the
        whole feed.
        """
        if focus_origin is not None:
            self._focus_origin_nlcs = set()
            self._preload_focus_locations(path, focus_origin.strip().upper())
        read_feed_files(path, self.report, self._load_lines)
        self._load_location_lookup(path)
        return self

    def _load_location_lookup(self, path: str | Path) -> None:
        """Load the optional station classification reference beside a feed.

        The DTD fares ZIP and the Knowledgebase reference feeds are commonly
        kept as siblings under ``feeds/``. Accept a lookup inside the fares
        folder too, which keeps synthetic and downloaded fixtures self-contained.
        JSON is deliberately supported as well as the DTD XML format: it makes a
        small reviewed correction possible without changing the page code.
        """
        root = Path(path)
        candidates: list[Path] = []
        if root.is_dir():
            candidates.extend(root.glob("*.xml"))
            candidates.extend(root.glob("*.json"))
            candidates.extend(root.parent.glob("FareLocationsRefData*.xml"))
            candidates.extend(root.parent.glob("*location*types*.json"))
        elif root.suffix.lower() == ".zip":
            candidates.extend(root.parent.glob("FareLocationsRefData*.xml"))
            candidates.extend(root.parent.glob("*location*types*.json"))
        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            try:
                if candidate.suffix.lower() == ".json":
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    self._load_location_types_json(data)
                else:
                    self._load_location_types_xml(candidate)
            except (OSError, ValueError, ET.ParseError) as error:
                self.report.skip_file(f"{candidate.name}: station classification lookup unreadable: {error}")
            if self.location_types_by_crs:
                return

    @staticmethod
    def _normalise_location_type(value: object) -> str | None:
        text = str(value or "").strip().lower()
        if "city" in text or "cities" in text or text in {"c", "urban", "metropolitan"}:
            return "city"
        if "town" in text or text in {"t", "village", "rural"}:
            return "town"
        return "other" if text else None

    def _load_location_types_json(self, data: object) -> None:
        records = data.values() if isinstance(data, dict) else data
        if not isinstance(records, (list, tuple)):
            return
        for record in records:
            if not isinstance(record, dict):
                continue
            crs = next((record.get(key) for key in ("crs", "CRS", "crsCode", "locationCode") if record.get(key)), None)
            kind = next((record.get(key) for key in ("type", "classification", "locationType", "LocationClassification") if record.get(key)), None)
            kind = self._normalise_location_type(kind)
            if crs and kind:
                self.location_types_by_crs[str(crs).strip().upper()] = kind

    def _load_location_types_xml(self, path: Path) -> None:
        root = ET.parse(path).getroot()
        crs_tags = {"CRS", "CRS_CODE", "CRSCODE", "LOCATION_CRS_CODE", "LOCATIONCRSCODE"}
        kind_tags = {"TYPE", "CLASSIFICATION", "LOCATION_TYPE", "LOCATIONTYPE", "LOCATION_CLASSIFICATION", "LOCATIONCLASSIFICATION"}
        for element in root.iter():
            values: dict[str, str] = {}
            for child in element.iter():
                tag = child.tag.rsplit("}", 1)[-1].upper()
                if child.text and (tag in crs_tags or tag in kind_tags):
                    values.setdefault(tag, child.text.strip())
            for tag, value in element.attrib.items():
                name = tag.rsplit("}", 1)[-1].upper()
                if name in crs_tags or name in kind_tags:
                    values.setdefault(name, value.strip())
            crs = next((values[tag] for tag in crs_tags if tag in values), None)
            kind = next((values[tag] for tag in kind_tags if tag in values), None)
            kind = self._normalise_location_type(kind)
            if crs and kind:
                self.location_types_by_crs[crs.strip().upper()] = kind

    def destination_type(self, crs: str) -> str:
        """Return ``city``, ``town``, or ``other`` for a station CRS."""
        return self.location_types_by_crs.get(crs.strip().upper(), "other")

    def _load_lines(self, name: str, lines) -> None:
        extension = Path(name).suffix.lower().lstrip(".")
        # The optional station classification lookup lives beside the fares
        # files and is read after the feed stream. It is still a known input,
        # not an unreadable file that should pollute the damage audit.
        if extension == "json":
            self.report.files_read.append(name)
            return
        loader = {
            "ffl": self._load_flows,
            "loc": self._load_locations,
            "tty": self._load_ticket_types,
            "rlc": self._load_railcards,
            "rcm": self._load_minimum_fares,
            "rst": self._load_restrictions,
        }.get(extension)
        if loader is None:
            # A download this project has no reader for must be named, or the
            # audit reports "files 0" and reads as an empty download when the
            # real story is an unrecognised format. See adr/ADR-0023.
            suffix = Path(name).suffix.lower().lstrip(".")
            self.report.skip_file(
                f"{name}: no reader for the .{suffix or 'unknown'} format, not opened"
            )
            return
        self.report.files_read.append(name)
        if extension == "rst":
            self.restrictions.files_read.append(name)
        count(lines, loader, self.report, name)

    def _flow_index_nlcs(self, flow: Flow) -> tuple[str, ...]:
        if flow.direction == "R" and flow.destination_nlc != flow.origin_nlc:
            return (flow.origin_nlc, flow.destination_nlc)
        return (flow.origin_nlc,)

    def _index_flow(self, flow: Flow) -> None:
        for nlc in self._flow_index_nlcs(flow):
            self.flows_by_origin_nlc.setdefault(nlc, []).append(flow)

    def _unindex_flow(self, flow: Flow) -> None:
        for nlc in self._flow_index_nlcs(flow):
            flows = self.flows_by_origin_nlc.get(nlc)
            if flows is not None and flow in flows:
                flows.remove(flow)
                if not flows:
                    self.flows_by_origin_nlc.pop(nlc, None)

    def _load_flows(self, line: str) -> None:
        record_type = _text(line, FLOW_F_OFFSETS, "record_type").upper()
        if record_type == "F":
            _require_width(line, FLOW_F_WIDTH, "flow")
            marker = _text(line, FLOW_F_OFFSETS, "update_marker").upper()
            flow_id = _text(line, FLOW_F_OFFSETS, "flow_id")
            previous = self.flows.get(flow_id)
            if previous is not None:
                self._unindex_flow(previous)
            if marker == "D":
                self.flows.pop(flow_id, None)
                self.fares_by_flow.pop(flow_id, None)
                return
            flow = Flow(
                flow_id=flow_id,
                origin_nlc=_text(line, FLOW_F_OFFSETS, "origin_nlc"),
                destination_nlc=_text(line, FLOW_F_OFFSETS, "destination_nlc"),
                route_code=_text(line, FLOW_F_OFFSETS, "route_code"),
                direction=_text(line, FLOW_F_OFFSETS, "direction").upper(),
                start_date=_parse_dtd_date(_text(line, FLOW_F_OFFSETS, "start_date")),
                end_date=_parse_dtd_date(_text(line, FLOW_F_OFFSETS, "end_date")),
            )
            self.flows[flow_id] = flow
            self._index_flow(flow)
        elif record_type == "T":
            _require_width(line, FLOW_T_WIDTH, "fare")
            marker = _text(line, FLOW_T_OFFSETS, "update_marker").upper()
            flow_id = _text(line, FLOW_T_OFFSETS, "flow_id")
            ticket_code = _text(line, FLOW_T_OFFSETS, "ticket_code")
            if self._focus_origin_nlcs is not None:
                flow = self.flows.get(flow_id)
                if flow is None or self._focus_origin_nlcs.isdisjoint(
                    self._flow_index_nlcs(flow)
                ):
                    return
            bucket = self.fares_by_flow.setdefault(flow_id, {})
            if marker == "D":
                bucket.pop(ticket_code, None)
                return
            fare_text = _text(line, FLOW_T_OFFSETS, "fare_pence")
            if not fare_text.isdigit():
                # Raise rather than count here: the line counter decides once
                # whether a line was parsed or rejected, and counting it in both
                # places makes a rejected record look handled, with no example.
                raise ValueError(f"fare {fare_text!r} is not a number")
            bucket[ticket_code] = Fare(
                ticket_code=ticket_code,
                pence=int(fare_text),
                restriction_code=_text(line, FLOW_T_OFFSETS, "restriction_code"),
            )

    def _load_locations(self, line: str) -> None:
        if _text(line, LOCATION_OFFSETS, "record_type").upper() != "L":
            return
        marker = _text(line, LOCATION_OFFSETS, "update_marker").upper()
        nlc = _text(line, LOCATION_OFFSETS, "nlc")
        existing = self.locations_by_nlc.get(nlc)
        if existing is not None and existing.crs:
            self.nlcs_by_crs.get(existing.crs, set()).discard(nlc)
            if self.locations_by_crs.get(existing.crs) is existing:
                self.locations_by_crs.pop(existing.crs, None)
        if marker == "D":
            self.locations_by_nlc.pop(nlc, None)
            return
        location = Location(
            nlc=nlc,
            crs=_text(line, LOCATION_OFFSETS, "crs").upper(),
            name=_text(line, LOCATION_OFFSETS, "description"),
            group_nlc=(
                _text(line, LOCATION_OFFSETS, "group_nlc") or nlc
            ),
        )
        self.locations_by_nlc[nlc] = location
        if location.crs:
            self.nlcs_by_crs.setdefault(location.crs, set()).add(nlc)
            self.locations_by_crs.setdefault(location.crs, location)

    def _load_ticket_types(self, line: str) -> None:
        marker = _text(line, TICKET_TYPE_OFFSETS, "update_marker").upper()
        code = _text(line, TICKET_TYPE_OFFSETS, "ticket_code")
        if marker == "D":
            self.ticket_types.pop(code, None)
            return
        if not code:
            return
        self.ticket_types[code] = TicketType(
            code=code,
            name=_text(line, TICKET_TYPE_OFFSETS, "description"),
            tkt_class=_text(line, TICKET_TYPE_OFFSETS, "tkt_class"),
            tkt_type=_text(line, TICKET_TYPE_OFFSETS, "tkt_type").upper(),
            restricted_by_train=_text(line, TICKET_TYPE_OFFSETS, "restricted_by_train") == "1",
        )

    def _load_railcards(self, line: str) -> None:
        code = _text(line, RAILCARD_OFFSETS, "railcard_code")
        if not code:
            return
        self.railcards[code] = Railcard(
            code=code,
            name=_text(line, RAILCARD_OFFSETS, "description"),
            min_adults=_as_int(_text(line, RAILCARD_OFFSETS, "min_adults")),
            max_adults=_as_int(_text(line, RAILCARD_OFFSETS, "max_adults")),
        )

    def _load_minimum_fares(self, line: str) -> None:
        railcard_code = _text(line, MINIMUM_FARE_OFFSETS, "railcard_code")
        ticket_code = _text(line, MINIMUM_FARE_OFFSETS, "ticket_code")
        pence = _as_int(_text(line, MINIMUM_FARE_OFFSETS, "minimum_fare_pence"))
        if not railcard_code or not ticket_code or pence <= 0:
            return
        self.minimum_fares[(railcard_code, ticket_code)] = pence

    def _load_restrictions(self, line: str) -> None:
        self.restrictions.load_line(line)

    # -- querying --------------------------------------------------------

    def _flow_valid_on(self, flow: Flow, query_day: date) -> bool:
        return not (
            (flow.start_date is not None and query_day < flow.start_date)
            or (flow.end_date is not None and query_day > flow.end_date)
        )

    def fare_coverage_audit(
        self, *, day: date | None = None, sample_limit: int = 10
    ) -> dict[str, object]:
        """Find fares that location or group relationships can hide.

        The query currently expands a station's direct location codes, but DTD
        locations also carry a group NLC. A fare flow from a shared group can
        therefore be valid for a station without appearing in that station's
        direct flow index. This report names those cases instead of silently
        calling the station unreachable.
        """
        query_day = day or date.today()
        limit = max(0, sample_limit)
        group_members: dict[str, set[str]] = {}
        for location in self.locations_by_nlc.values():
            if location.crs:
                group_members.setdefault(location.group_nlc, set()).add(location.nlc)
        multi_groups = {
            group: nlcs for group, nlcs in group_members.items() if len(nlcs) > 1
        }
        active_fare_flows = {
            flow.flow_id
            for flow in self.flows.values()
            if self.fares_by_flow.get(flow.flow_id)
            and self._flow_valid_on(flow, query_day)
        }
        direct_stations: set[str] = set()
        for crs, nlcs in self.nlcs_by_crs.items():
            if any(
                flow.flow_id in active_fare_flows
                for nlc in nlcs
                for flow in self.flows_by_origin_nlc.get(nlc, ())
            ):
                direct_stations.add(crs)

        group_by_nlc = {
            location.nlc: location.group_nlc
            for location in self.locations_by_nlc.values()
            if location.crs
        }
        group_origin_flows: dict[str, set[str]] = {
            group: set() for group in multi_groups
        }
        for flow in self.flows.values():
            group = group_by_nlc.get(flow.origin_nlc)
            if (
                group in group_origin_flows
                and flow.flow_id in active_fare_flows
            ):
                group_origin_flows[group].add(flow.flow_id)
        hidden_by_group: list[dict[str, object]] = []
        for group, flow_ids in group_origin_flows.items():
            if not flow_ids:
                continue
            for nlc in sorted(multi_groups[group]):
                location = self.locations_by_nlc.get(nlc)
                if location is None or location.crs in direct_stations:
                    continue
                hidden_by_group.append(
                    {
                        "crs": location.crs,
                        "name": location.name,
                        "groupNlc": group,
                        "flowCount": len(flow_ids),
                    }
                )

        location_aliases = [
            {
                "crs": crs,
                "name": self.locations_by_crs[crs].name,
                "nlcs": sorted(nlcs),
            }
            for crs, nlcs in sorted(self.nlcs_by_crs.items())
            if len(nlcs) > 1
        ]
        unmapped_destinations: list[dict[str, str]] = []
        missing_location = 0
        no_station_code = 0
        for flow in self.flows.values():
            if flow.flow_id not in active_fare_flows:
                continue
            destination = self.locations_by_nlc.get(flow.destination_nlc)
            if destination is None:
                missing_location += 1
                label = "missing location record"
            elif not destination.crs:
                no_station_code += 1
                label = destination.name or "location without CRS"
            else:
                continue
            if len(unmapped_destinations) < limit:
                unmapped_destinations.append(
                    {
                        "flowId": flow.flow_id,
                        "destinationNlc": flow.destination_nlc,
                        "label": label,
                    }
                )

        return {
            "day": query_day.isoformat(),
            "groupCodes": len(multi_groups),
            "groupOriginFlows": sum(len(ids) for ids in group_origin_flows.values()),
            "stationsPotentiallyHiddenByGroup": len(hidden_by_group),
            "sampleStationsPotentiallyHiddenByGroup": hidden_by_group[:limit],
            "stationsWithMultipleLocationCodes": len(location_aliases),
            "sampleStationsWithMultipleLocationCodes": location_aliases[:limit],
            "fareFlowsWithMissingLocation": missing_location,
            "fareFlowsWithNoStationCode": no_station_code,
            "sampleFareFlowsWithUnmappedDestinations": unmapped_destinations,
        }

    def stats(self) -> dict[str, int]:
        return {
            "stations": len(self.locations_by_crs),
            "flows": len(self.flows),
            "fares": sum(len(bucket) for bucket in self.fares_by_flow.values()),
            "ticket_types": len(self.ticket_types),
            "railcards": len(self.railcards),
            # A feed carries locations with no station code, and fares whose flow
            # is not in the file. Neither is an error, and both change any count
            # that ignores them, so both are reported.
            "locations_without_a_station_code": sum(
                1 for location in self.locations_by_nlc.values() if not location.crs
            ),
            "extra_location_codes_for_a_station": sum(
                max(0, len(nlcs) - 1) for nlcs in self.nlcs_by_crs.values()
            ),
            "fares_with_no_flow_record": sum(
                1
                for flow_id, bucket in self.fares_by_flow.items()
                if flow_id not in self.flows
                for _ in bucket
            ),
            "restriction_files": len(self.restrictions.files_read),
            "restriction_records": self.restrictions.parsed_records,
            "restriction_codes": len(self.restrictions.code_record_counts),
            "restriction_railcards": len(self.restrictions.railcard_record_counts),
        }

    def railcard_code(self, name: str) -> str | None:
        needle = name.strip().lower()
        if not needle:
            return None
        for code, railcard in sorted(self.railcards.items()):
            if railcard.name.lower() == needle:
                return code
        for code, railcard in sorted(self.railcards.items()):
            if needle in railcard.name.lower():
                return code
        return None

    def railcard_price(self, railcard_code: str, ticket_code: str, standard_pence: int) -> int:
        # National Rail's published third-off result is rounded down to the
        # nearest 5p for each ticket, not up. Rounding up costs 5p per traveller
        # whenever the exact discount falls between two 5p amounts.
        discounted = _round_down_to(standard_pence * RAILCARD_DISCOUNT, ROUNDING_STEP_PENCE)
        minimum = self.minimum_fares.get((railcard_code, ticket_code))
        if minimum is not None:
            discounted = max(discounted, minimum)
        return discounted

    def railcard_restriction(
        self,
        railcard_code: str,
        *,
        ticket_code: str,
        route_code: str,
        origin_crs: str,
        destination_crs: str,
        origin_nlc: str,
        destination_nlc: str,
    ) -> RailcardRestrictionRow | None:
        """Find the first current DTD ``RR`` rule that applies to a fare.

        Blank RR fields are wildcards. ``TOTAL_BAN = Y`` disallows the railcard;
        a non-blank restriction code also means that the rule has not been
        cleared for a generic fare query, so it must not receive a discounted
        price. This is deliberately conservative: a railcard price is only
        emitted when the feed has no applicable prohibition.
        """
        stations = {value.strip().upper() for value in (origin_crs, destination_crs, origin_nlc, destination_nlc) if value}
        for row in self.restrictions.active_railcard_rows(railcard_code):
            if row.ticket_code and row.ticket_code != ticket_code:
                continue
            if row.route_code and row.route_code != route_code:
                continue
            if row.location and row.location.strip().upper() not in stations:
                continue
            if row.total_ban or row.restriction_code:
                return row
        return None

    def railcard_price_for(
        self,
        railcard_code: str,
        *,
        ticket_code: str,
        route_code: str,
        origin_crs: str,
        destination_crs: str,
        origin_nlc: str,
        destination_nlc: str,
        standard_pence: int,
    ) -> int | None:
        restriction = self.railcard_restriction(
            railcard_code,
            ticket_code=ticket_code,
            route_code=route_code,
            origin_crs=origin_crs,
            destination_crs=destination_crs,
            origin_nlc=origin_nlc,
            destination_nlc=destination_nlc,
        )
        if restriction is not None:
            return None
        return self.railcard_price(railcard_code, ticket_code, standard_pence)

    def destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        day: date | None = None,
    ) -> list[Reachable]:
        """Cheapest standard-class return to each destination inside the budget.

        With a railcard, the comparison uses whichever of the railcard price and
        the standard price is cheaper, since a cardholder can always decline the
        discount. party_budget tests the total for the party instead of the
        per-adult price.

        Pass a dict as tally to record why each flow or fare did not become a
        destination. A destination the feed prices but cannot name is dropped,
        and a count that ignores those is wrong without saying so.

        This is the broad query, and it still accepts every class-2 return fare
        the feed offers, restricted or not. Use ``publishable_destinations_within``
        before putting a price on a public page.
        """
        return self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=None,
            day=day,
        )

    def page_destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        day: date | None = None,
    ) -> list[Reachable]:
        """Rows suitable for the reader-facing page, including restrictions.

        The feed contains ITX placeholder fares such as ``EIS`` at the £0.05
        minimum with restriction ``GA``. They are not usable public fares, so
        they must not win the broad query's cheapest-fare comparison. Other
        restricted standard returns remain visible and carry their restriction
        code to the page.
        """
        rows = self.destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            day=day,
        )
        return [
            row for row in rows
            if row.ticket_code not in PLACEHOLDER_TICKET_CODES
            and "ITX" not in row.ticket_name.upper()
        ]

    def page_single_destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        day: date | None = None,
    ) -> list[Reachable]:
        """Displayable standard-class singles, excluding catalogue placeholders."""
        rows = self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=lambda fare, ticket: (
                None
                if ticket.is_standard_single
                and fare.ticket_code not in PLACEHOLDER_TICKET_CODES
                and "ITX" not in ticket.name.upper()
                and not any(
                    marker in ticket.name.upper()
                    for marker in ("NOT FOR TRAVEL", "TEST", "DUMMY", "FOR TEST", "COMP")
                )
                else "ticket_is_not_a_displayable_standard_single"
            ),
            day=day,
        )
        return rows

    def publishable_destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        require_restrictions: bool = True,
        day: date | None = None,
    ) -> list[Reachable]:
        """The reviewed selector for public prices: Anytime Day Return only.

        With ``require_restrictions`` true (the default), the query refuses to
        run at all unless the ``.RST`` restriction file loaded cleanly, keeps
        only ticket codes in ``REVIEWED_ANYTIME_DAY_RETURN_TICKETS`` whose real
        ticket type is a standard-class, train-unrestricted exact ANYTIME DAY R,
        and drops any fare whose restriction code is not blank. Railcard prices
        are evaluated against the current ``RR`` rows in the same feed: blank
        fields are wildcards, and a matching total ban or restriction code
        removes the discount for that fare.

        ``require_restrictions=False`` is for analysis and synthetic feeds only.
        It allows the conventional no-restriction code ``00`` and computes
        railcard discounts as the broad query does. Do not put its output on a
        public page.
        """
        if require_restrictions:
            problem = self.restrictions.gate_problem()
            if problem is not None:
                raise ValueError(problem)
        return self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=self._publishable_rejection(strict=require_restrictions),
            day=day,
        )

    def _publishable_rejection(
        self, *, strict: bool
    ) -> Callable[[Fare, TicketType], str | None]:
        """Build the reviewed selector used by ``publishable_destinations_within``."""

        def reject(fare: Fare, ticket: TicketType) -> str | None:
            expected_name = REVIEWED_ANYTIME_DAY_RETURN_TICKETS.get(ticket.code)
            if (
                expected_name is None
                or ticket.name.strip().upper() != expected_name
                or not ticket.is_standard_return
                or ticket.restricted_by_train
            ):
                return "ticket_is_not_a_reviewed_anytime_day_return"
            restriction = fare.restriction_code.strip()
            if not restriction:
                return None
            if not strict and restriction == "00":
                return None
            return "fare_restriction_code_is_not_reviewed"

        return reject

    def _destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int,
        railcard: str | None,
        party_budget: bool,
        tally: dict[str, int] | None,
        selector: Callable[[Fare, TicketType], str | None] | None,
        day: date | None,
    ) -> list[Reachable]:
        """Shared query loop. ``selector`` adds the publishable-fare filter."""
        query_day = day or date.today()
        origin = self.locations_by_crs.get(origin_crs.strip().upper())
        if origin is None:
            raise KeyError(f"origin station {origin_crs!r} is not in the feed")
        origin_nlcs = self.nlcs_by_crs.get(origin.crs, {origin.nlc})
        railcard_code = self.railcard_code(railcard) if railcard else None
        if railcard and railcard_code is None:
            raise KeyError(f"railcard {railcard!r} is not in the feed")

        best_by_crs: dict[str, Reachable] = {}
        # Only flows queryable from this origin: one grouped list per origin NLC
        # replaces a scan of every flow in the database per call. The index also
        # contains reversible flows under their recorded destination, so a query
        # for the opposite direction reaches the same fare without swapping data.
        for origin_nlc in origin_nlcs:
            for flow in self.flows_by_origin_nlc.get(origin_nlc, ()):
                if not self._flow_valid_on(flow, query_day):
                    _tally(
                        tally,
                        "flow_not_yet_valid"
                        if flow.start_date is not None and query_day < flow.start_date
                        else "flow_expired",
                    )
                    continue
                # A reversible flow is indexed under both endpoints, but its
                # stored destination still points at the recorded origin. Use
                # the opposite endpoint when this query entered via that side.
                destination_nlc = (
                    flow.origin_nlc
                    if flow.direction == "R" and flow.destination_nlc == origin_nlc
                    else flow.destination_nlc
                )
                destination = self.locations_by_nlc.get(destination_nlc)
                if destination is None:
                    _tally(tally, "destination_has_no_location_record")
                    continue
                if not destination.crs:
                    _tally(tally, "destination_has_no_station_code")
                    continue
                if destination.crs == origin.crs:
                    _tally(tally, "fare_to_the_origin_itself")
                    continue
                bucket = self.fares_by_flow.get(flow.flow_id)
                if not bucket:
                    _tally(tally, "flow_with_no_fare")
                    continue
                for fare in bucket.values():
                    ticket = self.ticket_types.get(fare.ticket_code)
                    if ticket is None:
                        _tally(tally, "fare_with_no_ticket_type")
                        continue
                    if selector is not None:
                        rejection = selector(fare, ticket)
                        if rejection is not None:
                            _tally(tally, rejection)
                            continue
                    elif not ticket.is_standard_return:
                        _tally(tally, "ticket_is_not_a_standard_return")
                        continue
                    railcard_pence = (
                        self.railcard_price_for(
                            railcard_code,
                            ticket_code=fare.ticket_code,
                            route_code=flow.route_code,
                            origin_crs=origin.crs,
                            destination_crs=destination.crs,
                            origin_nlc=origin_nlc,
                            destination_nlc=destination_nlc,
                            standard_pence=fare.pence,
                        )
                        if railcard_code
                        else None
                    )
                    best_pence = min(fare.pence, railcard_pence) if railcard_pence else fare.pence
                    party_pence = best_pence * adults
                    tested = party_pence if party_budget else best_pence
                    if tested > budget_pence:
                        _tally(tally, "fare_above_the_budget")
                        continue
                    candidate = Reachable(
                        crs=destination.crs,
                        station=destination.name,
                        ticket_code=ticket.code,
                        ticket_name=ticket.name,
                        standard_pence=fare.pence,
                        best_pence=best_pence,
                        railcard_pence=railcard_pence,
                        party_pence=party_pence,
                        off_peak=ticket.restricted_by_train,
                        restriction_code=fare.restriction_code.strip(),
                        route_code=flow.route_code,
                        origin_nlc=origin_nlc,
                        destination_nlc=destination_nlc,
                    )
                    current = best_by_crs.get(destination.crs)
                    if current is not None and candidate.best_pence >= current.best_pence:
                        _tally(tally, "cheaper_index_already_held")
                        continue
                    best_by_crs[destination.crs] = candidate
        return sorted(best_by_crs.values(), key=lambda reachable: (reachable.best_pence, reachable.crs))


def _as_int(value: str) -> int:
    return int(value) if value.isdigit() else 0
