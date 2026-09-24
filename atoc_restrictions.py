"""Read the RSPS5045 ticket restriction file (``.RST``) from the fares feed.

The file is a stream of fixed-width records. Each record starts with an update
marker, a two-letter record type, and a current/future marker, so a field's
position is the running sum of the widths before it exactly as it is for the
other ATOC files.

The published layout is RSPS5045. The field widths here were cross-checked
against the open-source `pashri/atoc` parser (``atoc/File/Fare/Restrictions.py``)
and against the real DTD ``.RST`` file, whose record widths match to the
character.

This module parses the records and keeps the current and future restriction data
needed by the fare selector. The railcard rows are evaluated against the fare's
ticket, route, and endpoint locations; a matching total ban or restriction code
removes the discount for that fare.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

# Record layouts in file order, as (field_name, width). The keys are the record
# type at line[1:3]. RSPS5045 and pashri/atoc agree on every width used here.
RESTRICTION_LAYOUTS: dict[str, tuple[tuple[str, int], ...]] = {
    "RD": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("start_date", 8),
        ("end_date", 8),
    ),
    "RH": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("description", 30),
        ("desc_out", 50),
        ("desc_rtn", 50),
        ("type_out", 1),
        ("type_rtn", 1),
        ("change_ind", 1),
    ),
    "HD": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("date_from", 4),
        ("date_to", 4),
        ("days", 7),
    ),
    "HL": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("location_crs", 3),
    ),
    "HC": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("allowed_change", 3),
    ),
    "HA": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("additional_restriction", 2),
        ("origin", 3),
        ("destination", 3),
    ),
    "TR": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("sequence_no", 4),
        ("out_ret", 1),
        ("time_from", 4),
        ("time_to", 4),
        ("arr_dep_via", 1),
        ("location", 3),
        ("rstr_type", 1),
        ("train_type", 1),
        ("min_fare_flag", 1),
    ),
    "TD": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("sequence_no", 4),
        ("out_ret", 1),
        ("date_from", 4),
        ("date_to", 4),
        ("days", 7),
    ),
    "TT": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("sequence_no", 4),
        ("out_ret", 1),
        ("toc_code", 2),
    ),
    "TP": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("sequence_no", 4),
        ("out_ret", 1),
        ("barred_class", 1),
        ("barred_tickets", 1),
        ("barred_seasons", 1),
        ("barred_first", 1),
        ("from_location", 3),
        ("to_location", 3),
    ),
    "TE": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("sequence_no", 4),
        ("out_ret", 1),
        ("pass_exception", 1),
    ),
    "SR": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("train_no", 6),
        ("out_ret", 1),
        ("quota_ind", 1),
        ("sleeper_ind", 1),
    ),
    "SD": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("train_no", 6),
        ("out_ret", 1),
        ("date_from", 4),
        ("date_to", 4),
        ("days", 7),
    ),
    "SQ": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("train_no", 6),
        ("out_ret", 1),
        ("location", 3),
        ("quota_ind", 1),
        ("arr_dep", 1),
    ),
    "SP": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("train_no", 6),
        ("out_ret", 1),
        ("barred_class", 1),
        ("barred_tickets", 1),
        ("barred_seasons", 1),
        ("barred_first", 1),
        ("from_location", 3),
        ("to_location", 3),
    ),
    "SE": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("restriction_code", 2),
        ("train_no", 6),
        ("out_ret", 1),
        ("pass_exception", 1),
    ),
    "RR": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("railcard_code", 3),
        ("sequence_no", 4),
        ("ticket_code", 3),
        ("route_code", 5),
        ("location", 3),
        ("restriction_code", 2),
        ("total_ban", 1),
    ),
    "EC": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("exception_code", 1),
        ("description", 50),
    ),
    "CA": (
        ("update_marker", 1),
        ("record_type", 2),
        ("cf_marker", 1),
        ("ticket_code", 3),
        ("cal_type", 1),
        ("route_code", 5),
        ("country_code", 1),
        ("date_from", 4),
        ("date_to", 4),
        ("days", 7),
    ),
}


def _offsets(spec: tuple[tuple[str, int], ...]) -> dict[str, tuple[int, int]]:
    offsets: dict[str, tuple[int, int]] = {}
    position = 0
    for name, width in spec:
        offsets[name] = (position, position + width)
        position += width
    return offsets


RESTRICTION_OFFSETS: dict[str, dict[str, tuple[int, int]]] = {
    record_type: _offsets(spec) for record_type, spec in RESTRICTION_LAYOUTS.items()
}
RESTRICTION_WIDTHS: dict[str, int] = {
    record_type: sum(width for _, width in spec)
    for record_type, spec in RESTRICTION_LAYOUTS.items()
}

# These record types carry a two-character restriction code in the same
# position. RR carries a railcard code instead and CA a ticket code.
CODE_RECORD_TYPES = frozenset(
    {"RH", "HD", "HL", "HC", "HA", "TR", "TD", "TT", "TP", "TE", "SR", "SD", "SQ", "SP", "SE"}
)


def _field(line: str, offsets: dict[str, tuple[int, int]], name: str) -> str:
    start, end = offsets[name]
    return line[start:end].strip()


@dataclass(frozen=True)
class RestrictionHeader:
    """One ``RH`` record: the human description of a restriction code."""

    code: str
    description: str
    outward_text: str
    return_text: str
    outward_type: str
    return_type: str
    change_indicator: str
    current_or_future: str


@dataclass(frozen=True)
class RailcardRestrictionRow:
    """One ``RR`` record: a railcard restriction for a ticket/route/location.

    ``total_ban`` is ``Y`` when the row bans the combination outright. A row is
    kept so the fare selector can evaluate the current rule against the exact
    ticket, route, and location context.
    """

    railcard_code: str
    sequence_no: str
    ticket_code: str
    route_code: str
    location: str
    restriction_code: str
    total_ban: bool
    current_or_future: str
    update_marker: str = "R"


def parse_header(line: str) -> RestrictionHeader:
    offsets = RESTRICTION_OFFSETS["RH"]
    return RestrictionHeader(
        code=_field(line, offsets, "restriction_code"),
        description=_field(line, offsets, "description"),
        outward_text=_field(line, offsets, "desc_out"),
        return_text=_field(line, offsets, "desc_rtn"),
        outward_type=_field(line, offsets, "type_out"),
        return_type=_field(line, offsets, "type_rtn"),
        change_indicator=_field(line, offsets, "change_ind"),
        current_or_future=_field(line, offsets, "cf_marker"),
    )


def parse_railcard_record(line: str) -> RailcardRestrictionRow:
    offsets = RESTRICTION_OFFSETS["RR"]
    return RailcardRestrictionRow(
        railcard_code=_field(line, offsets, "railcard_code"),
        sequence_no=_field(line, offsets, "sequence_no"),
        ticket_code=_field(line, offsets, "ticket_code"),
        route_code=_field(line, offsets, "route_code"),
        location=_field(line, offsets, "location"),
        restriction_code=_field(line, offsets, "restriction_code"),
        total_ban=_field(line, offsets, "total_ban").upper() == "Y",
        current_or_future=_field(line, offsets, "cf_marker"),
        update_marker=_field(line, offsets, "update_marker").upper(),
    )


@dataclass
class RestrictionIndex:
    """What the fares parser keeps from the ``.RST`` file.

    Counts and samples are retained for audits, along with all RR rows needed
    by the fare selector. The active rows for each railcard are cached after the
    first query so a national build does not rescan the complete RR file for
    every fare.
    """

    files_read: list[str] = field(default_factory=list)
    record_counts: Counter[str] = field(default_factory=Counter)
    code_record_counts: Counter[str] = field(default_factory=Counter)
    railcard_record_counts: Counter[str] = field(default_factory=Counter)
    unknown_types: Counter[str] = field(default_factory=Counter)
    headers: dict[str, RestrictionHeader] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)
    railcard_samples: list[RailcardRestrictionRow] = field(default_factory=list)
    # RR rows are small enough to retain (the real feed has about 328,000),
    # and retaining them is what lets the fares query evaluate a railcard
    # against a ticket, route, and station rather than merely report that rules
    # exist. Only current rows are returned by ``active_railcard_rows``.
    railcard_rows: list[RailcardRestrictionRow] = field(default_factory=list)
    _railcard_row_keys: dict[tuple[str, str, str], RailcardRestrictionRow] = field(default_factory=dict)
    _active_railcard_cache: dict[str, list[RailcardRestrictionRow]] = field(default_factory=dict)
    parsed_records: int = 0
    rejected_records: int = 0

    @property
    def loaded(self) -> bool:
        return bool(self.files_read)

    @property
    def railcard_codes(self) -> set[str]:
        return set(self.railcard_record_counts)

    def load_line(self, line: str) -> None:
        """Read one ``.RST`` line into the index."""
        if line.startswith("/"):
            # The first line of the real file is ``/!! Start of file``, not a record.
            return
        if len(line) < 3:
            self.rejected_records += 1
            raise ValueError("restriction record is shorter than its record type")
        record_type = line[1:3].upper()
        width = RESTRICTION_WIDTHS.get(record_type)
        if width is None:
            self.unknown_types[record_type] += 1
            self.rejected_records += 1
            raise ValueError(f"unknown restriction record type {record_type!r}")
        if len(line) < width:
            self.rejected_records += 1
            raise ValueError(
                f"{record_type} record is {len(line)} characters, needs {width}"
            )
        self.record_counts[record_type] += 1
        self.parsed_records += 1
        self.samples.setdefault(record_type, line)
        if record_type in CODE_RECORD_TYPES:
            code = _field(line, RESTRICTION_OFFSETS[record_type], "restriction_code")
            if code:
                self.code_record_counts[code] += 1
        if record_type == "RH":
            header = parse_header(line)
            if header.code:
                self.headers[header.code] = header
        elif record_type == "RR":
            row = parse_railcard_record(line)
            if row.railcard_code:
                key = (row.railcard_code, row.sequence_no, row.current_or_future)
                previous = self._railcard_row_keys.pop(key, None)
                if previous is not None:
                    self.railcard_rows.remove(previous)
                    remaining = self.railcard_record_counts.get(row.railcard_code, 0) - 1
                    if remaining > 0:
                        self.railcard_record_counts[row.railcard_code] = remaining
                    else:
                        self.railcard_record_counts.pop(row.railcard_code, None)
                if row.update_marker == "D":
                    self._active_railcard_cache.clear()
                    return
                # A re-issued current/future row supersedes the same sequence;
                # otherwise an update feed can leave both versions active.
                self.railcard_record_counts[row.railcard_code] += 1
                self.railcard_rows.append(row)
                self._railcard_row_keys[key] = row
                self._active_railcard_cache.clear()
                if len(self.railcard_samples) < 5:
                    self.railcard_samples.append(row)

    def active_railcard_rows(self, railcard_code: str) -> list[RailcardRestrictionRow]:
        """Return current ``RR`` rows for *railcard_code*.

        ``C`` means current and ``F`` means future in the DTD file. A future
        row must not affect today's fare query. Empty fields in an RR row are
        wildcards; the caller applies the ticket, route, and location match.
        """
        code = railcard_code.strip().upper()
        cached = self._active_railcard_cache.get(code)
        if cached is None:
            cached = [
                row
                for row in self.railcard_rows
                if row.railcard_code == code and row.current_or_future.upper() == "C"
            ]
            self._active_railcard_cache[code] = cached
        return cached

    def gate_problem(self) -> str | None:
        """Why a fare must not be published, or ``None`` when the file is usable.

        The gate is deliberately blunt: an unrecognised record or a truncated
        line means this parser did not understand part of the restriction data,
        and a price that depends on it cannot be published.
        """
        if not self.loaded:
            return "the fares feed carries no .RST restriction file, so no fare restriction can be checked"
        if self.rejected_records:
            return (
                f"{self.rejected_records} restriction records were not understood; "
                "the restriction data is incomplete"
            )
        if not self.parsed_records:
            return "the .RST restriction file held no readable records"
        return None

    def summary(self) -> dict[str, object]:
        return {
            "files": len(self.files_read),
            "records": self.parsed_records,
            "rejected": self.rejected_records,
            "record_types": dict(sorted(self.record_counts.items())),
            "restriction_codes": len(self.code_record_counts),
            "railcard_codes": len(self.railcard_record_counts),
            "railcard_records": sum(self.railcard_record_counts.values()),
            "unknown_types": dict(sorted(self.unknown_types.items())),
        }
