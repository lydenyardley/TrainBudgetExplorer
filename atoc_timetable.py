"""Read the CIF timetable feed and answer journey questions.

Data shape: the feed is a stream of schedules. Each schedule has a train
identity and an ordered list of calling points with public arrival and departure
times. Two indexes, departures and arrivals by station, turn a per-query scan of
the whole feed into a lookup.

Field layouts follow the published CIF record formats, as implemented by the
open-source parsers named in README.md.
"""

from __future__ import annotations

import bisect
import pickle
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from parse_report import ParseReport, count, decode_lines, peek, read_feed_files

# Onward departures the one-change search will consider at each interchange.
# 200 is measured, not guessed: it is the smallest cap that lost no journey on
# either synthetic network, and it held the median query under 400 ms on the
# densest one. See adr/ADR-0009-onward-departure-cap.md.
MAX_ONWARD_DEPARTURES = 200
MINUTES_PER_DAY = 1440
DEFAULT_CONNECTION_MINUTES = 5

_UNSET = object()
_MISSING = object()

# The fixed-width helpers are deliberately local. Sharing them across modules
# would mean importing another module's private helpers, which costs the reader
# more than these twelve lines do. See adr/ADR-0006-timetable-layer.md.


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


def normalize_tiploc(value: str) -> str:
    """Canonicalise a TIPLOC so padded and lower-case keys cannot split it.

    A CIF location field is eight characters wide but only the first seven are
    the TIPLOC; the eighth can be a non-space path/platform flag. Taking the
    stripped whole field and then slicing it (the old behaviour) turned
    ``ABHLJN 2`` into ``ABHLJN `` while the station names file held ``ABHLJN``,
    so one location acquired two keys. The raw value is kept for the audit.
    """
    return value.strip().upper()


def stop_tiploc_from_field(field: str) -> str:
    """Read the seven-character TIPLOC from an eight-character location field."""
    return normalize_tiploc(field[:7])


CIF_HEADER = (
    ("record_type", 2),
    ("file_identity", 20),
    ("extract_date", 6),
    ("extract_time", 4),
    ("current_file_ref", 7),
    ("last_file_ref", 7),
    ("bleed_off", 1),
    ("version", 1),
    ("extract_start", 6),
    ("extract_end", 6),
    ("spare", 20),
)

CIF_SCHEDULE = (
    ("record_type", 2),
    ("transaction_type", 1),
    ("train_uid", 6),
    ("date_runs_from", 6),
    ("date_runs_to", 6),
    ("days", 7),
    ("bank_holiday", 1),
    ("status", 1),
    ("category", 2),
    ("train_identity", 4),
    ("headcode", 4),
    ("course_indicator", 1),
    ("service_code", 8),
    ("bussec", 1),
    ("power_type", 3),
    ("timing_load", 4),
    ("speed", 3),
    ("operating_chars", 6),
    ("class", 1),
    ("sleepers", 1),
    ("reservations", 1),
    ("connect_indicator", 1),
    ("catering", 4),
    ("service_brand", 4),
    ("spare", 1),
    ("stp_indicator", 1),
)

CIF_ORIGIN = (
    ("record_type", 2),
    ("location", 8),
    ("scheduled_departure", 5),
    ("public_departure", 4),
    ("platform", 3),
    ("line", 3),
    ("engineering_allowance", 2),
    ("path_time", 2),
    ("activity", 12),
    ("performance_allowance", 2),
    ("spare", 37),
)

CIF_INTERMEDIATE = (
    ("record_type", 2),
    ("location", 8),
    ("scheduled_arrival", 5),
    ("scheduled_departure", 5),
    ("scheduled_pass", 5),
    ("public_arrival", 4),
    ("public_departure", 4),
    ("platform", 3),
    ("line", 3),
    ("path", 3),
    ("activity", 12),
    ("engineering_allowance", 2),
    ("path_time", 2),
    ("performance_allowance", 2),
    ("spare", 20),
)

CIF_TERMINUS = (
    ("record_type", 2),
    ("location", 8),
    ("scheduled_arrival", 5),
    ("public_arrival", 4),
    ("platform", 3),
    ("path", 3),
    ("activity", 12),
    ("spare", 43),
)

CIF_TIPLOC_INSERT = (
    ("record_type", 2),
    ("tiploc", 7),
    ("capitals", 2),
    ("nalco", 6),
    ("nlc_check", 1),
    ("description", 26),
    ("stanox", 5),
    ("po_mcp", 4),
    ("crs", 3),
    ("capri_description", 16),
    ("spare", 8),
)

CIF_TIPLOC_DELETE = (
    ("record_type", 2),
    ("tiploc", 7),
    ("spare", 71),
)

MSN_STATION = (
    ("record_type", 1),
    ("spaces1", 4),
    ("name", 30),
    ("category", 1),
    ("tiploc", 7),
    ("subsidiary", 3),
    ("spaces2", 3),
    ("crs", 3),
    ("easting", 5),
    ("estimated", 1),
    ("northing", 5),
    ("change_time", 2),
    ("footnote", 2),
    ("spaces3", 11),
    ("region", 3),
    ("spaces4", 1),
)

CIF_HEADER_OFFSETS = _offsets(CIF_HEADER)
CIF_SCHEDULE_OFFSETS = _offsets(CIF_SCHEDULE)
CIF_ORIGIN_OFFSETS = _offsets(CIF_ORIGIN)
CIF_INTERMEDIATE_OFFSETS = _offsets(CIF_INTERMEDIATE)
CIF_TERMINUS_OFFSETS = _offsets(CIF_TERMINUS)
CIF_TIPLOC_INSERT_OFFSETS = _offsets(CIF_TIPLOC_INSERT)
CIF_TIPLOC_DELETE_OFFSETS = _offsets(CIF_TIPLOC_DELETE)
MSN_STATION_OFFSETS = _offsets(MSN_STATION)

CIF_RECORD_TYPES = frozenset(
    {"HD", "BS", "BX", "LO", "LI", "LT", "CR", "TN", "LN", "AA", "TI", "TA", "TD", "ZZ"}
)
CIF_EXTENSIONS = frozenset({"mca", "cfa", "ztr", "cif"})
MSN_EXTENSIONS = frozenset({"msn"})


def _minutes(value: str) -> int | None:
    """Read a CIF time as minutes past midnight. Blank means the train does not stop."""
    digits = value.strip()
    if len(digits) < 4 or not digits[:4].isdigit():
        return None
    return int(digits[0:2]) * 60 + int(digits[2:4])


def _date(value: str) -> date | None:
    """Read a CIF date. A two digit year is read as 2000 based."""
    digits = value.strip()
    if len(digits) != 6 or not digits.isdigit():
        return None
    try:
        return date(int(digits[0:2]) + 2000, int(digits[2:4]), int(digits[4:6]))
    except ValueError:
        return None


def format_minutes(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}h{remainder:02d}"
    if hours:
        return f"{hours}h"
    return f"{remainder}m"


@dataclass(frozen=True)
class CallingPoint:
    tiploc: str
    arrival: int | None
    departure: int | None
    public_arrival: int | None
    public_departure: int | None

    @property
    def alight(self) -> int | None:
        return self.public_arrival if self.public_arrival is not None else self.arrival

    @property
    def board(self) -> int | None:
        return self.public_departure if self.public_departure is not None else self.departure


@dataclass(frozen=True)
class Schedule:
    train_uid: str
    stops: tuple[CallingPoint, ...]
    date_from: str = ""
    date_to: str = ""
    days: str = ""
    stp_indicator: str = ""

    def runs_on(self, day: date) -> bool:
        """Whether the schedule runs on a date, before overlays and cancellations."""
        start = _date(self.date_from)
        if start is not None and day < start:
            return False
        end = _date(self.date_to)
        if end is not None and day > end:
            return False
        if len(self.days) < 7:
            return True
        return self.days[day.weekday()] == "1"


@dataclass
class _CifState:
    """One schedule under construction while a record stream is read."""

    train_uid: str = ""
    stops: list[CallingPoint] = field(default_factory=list)
    date_from: str = ""
    date_to: str = ""
    days: str = ""
    stp_indicator: str = ""

    def reset(self) -> None:
        self.train_uid = ""
        self.stops = []


@dataclass(frozen=True)
class TimetableStation:
    tiploc: str
    crs: str
    name: str
    change_time: int


@dataclass(frozen=True)
class Leg:
    train_uid: str
    origin_crs: str
    destination_crs: str
    departure: int
    arrival: int


@dataclass(frozen=True)
class Journey:
    origin_crs: str
    destination_crs: str
    departure: int
    arrival: int
    legs: tuple[Leg, ...]

    @property
    def changes(self) -> int:
        return max(0, len(self.legs) - 1)

    @property
    def duration(self) -> int:
        return self.arrival - self.departure


def _rank(journey: Journey) -> tuple[int, int, int]:
    return (journey.duration, journey.changes, journey.departure)


class TimetableDb:
    """Indexes the CIF schedules and the station names that name their stops."""

    def __init__(self) -> None:
        self.stations_by_tiploc: dict[str, TimetableStation] = {}
        self.crs_by_tiploc: dict[str, str] = {}
        self.cif_crs_by_tiploc: dict[str, str] = {}
        # Every CIF TIPLOC insert, including the ones with a blank CRS. Those
        # are real operational or non-passenger locations, not missing data, and
        # the audit separates them from a TIPLOC no record mentions at all.
        self.cif_locations_by_tiploc: dict[str, str] = {}
        # canonical TIPLOC -> raw seven-character values that differ from it.
        self.tiploc_variants: dict[str, set[str]] = {}
        self.schedules: list[Schedule] = []
        self.report = ParseReport()
        self.files_read = self.report.files_read
        self._departures: dict[str, list[tuple[int, int, int]]] | None = None
        self._arrivals: dict[str, list[tuple[int, int, int]]] | None = None
        self._departure_times: dict[str, list[int]] = {}
        self._index_day: date | None | object = _UNSET
        self._crs_cache: dict[str, str | None] = {}
        self._schedule_crs: dict[int, tuple[str | None, ...]] = {}
        self._schedule_dest_stops: dict[int, dict[str, list[int]]] = {}
        self._change_times: dict[str, int] = {}
        # A focused load keeps only schedules touching the requested stations.
        # None means the normal complete database used by audit and analysis.
        self._focus_tiplocs: set[str] | None = None
        self._service_window: tuple[tuple[str, str], int] | None = None

    # -- loading ---------------------------------------------------------

    def _preload_focus_stations(self, path: str | Path, focus_crs: set[str]) -> None:
        """Read MSN station names before CIF schedules are streamed.

        DTD timetable archives place MSN before MCA, but this explicit pass also
        handles extracted folders and keeps the focused loader independent of
        directory ordering.
        """
        root = Path(path)

        def read_station_file(handle) -> None:
            for line in decode_lines(handle, ParseReport()):
                self._load_station_line(line)

        if root.is_dir():
            for child in sorted(root.iterdir()):
                if not child.is_file():
                    continue
                if child.suffix.lower() == ".msn":
                    with child.open("rb") as handle:
                        read_station_file(handle)
                elif child.suffix.lower() == ".zip" and zipfile.is_zipfile(child):
                    with zipfile.ZipFile(child) as archive:
                        for name in sorted(archive.namelist()):
                            if name.lower().endswith(".msn"):
                                with archive.open(name) as handle:
                                    read_station_file(handle)
        elif root.suffix.lower() == ".zip" and zipfile.is_zipfile(root):
            with zipfile.ZipFile(root) as archive:
                for name in sorted(archive.namelist()):
                    if name.lower().endswith(".msn"):
                        with archive.open(name) as handle:
                            read_station_file(handle)
        self._focus_tiplocs = {
            station.tiploc
            for station in self.stations_by_tiploc.values()
            if station.crs in focus_crs
        }

    def load_feed(
        self,
        path: str | Path,
        *,
        focus_origin: str | None = None,
        focus_destinations: set[str] | None = None,
        cache_path: str | Path | None = None,
    ) -> "TimetableDb":
        """Load a timetable, optionally focused and cached for one page build.

        A cache hit skips the multi-million-record parse entirely. On the real
        DTD timetable a focused parse takes 55.6s and reading the 90MB pickle
        back takes 2.6s, which is why this cache exists: the focus decides how
        much of the feed is held, not how long the feed takes to read, because
        the loader still has to see every record to know to drop it. The cache
        is opt-in so audit and general analysis retain their complete-feed
        semantics; the page builder supplies a path derived from the feed and
        the requested stations.
        """
        if cache_path is not None:
            cache = Path(cache_path)
            if cache.is_file():
                try:
                    with cache.open("rb") as handle:
                        loaded = pickle.load(handle)
                    if isinstance(loaded, TimetableDb):
                        loaded._invalidate_indexes()
                        return loaded
                except (OSError, EOFError, pickle.PickleError, AttributeError, TypeError):
                    pass

        focus_crs = set(focus_destinations or ())
        if focus_origin:
            focus_crs.add(focus_origin.strip().upper())
        if focus_crs:
            self._preload_focus_stations(path, focus_crs)
        read_feed_files(path, self.report, self._load_lines)
        if cache_path is not None:
            self._invalidate_indexes()
            cache = Path(cache_path)
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_suffix(cache.suffix + ".tmp")
            with temporary.open("wb") as handle:
                pickle.dump(self, handle, protocol=pickle.HIGHEST_PROTOCOL)
            temporary.replace(cache)
        return self

    def _load_lines(self, name: str, lines) -> None:
        kind = self._kind_from_name(name)
        if kind is None:
            first, lines = peek(lines)
            if first is None:
                # An empty file is skipped, but it is named: silence here reads
                # as "the download was empty" when the file list says otherwise.
                self.report.skip_file(f"{name}: empty, nothing to read")
                return
            kind = self._kind_from_line(first)
            if kind is None:
                # Content sniffing means a non-timetable file is declined here.
                # Naming it keeps "files 0" from reading as an empty download.
                self.report.skip_file(
                    f"{name}: first line {first[:20]!r} is not a timetable record, not opened"
                )
                return
        self.report.files_read.append(name)
        self._invalidate_indexes()
        if kind == "cif":
            state = _CifState()
            count(
                lines,
                lambda line: self._cif_line(line, state),
                self.report,
                name,
                finish=lambda: self._commit(state),
            )
        else:
            count(lines, self._load_station_line, self.report, name)

    @staticmethod
    def _kind_from_name(name: str) -> str | None:
        extension = Path(name).suffix.lower().lstrip(".")
        if extension in CIF_EXTENSIONS:
            return "cif"
        if extension in MSN_EXTENSIONS:
            return "msn"
        return None

    @staticmethod
    def _kind_from_line(line: str) -> str | None:
        """Classify a file with no useful extension, and refuse anything ambiguous.

        A fares record also starts with an update marker, so a loose test would
        read fares files as station records. Station names records carry four
        spaces after the record type, which separates the two.
        """
        if len(line) < 60:
            return None
        if line[:2] in CIF_RECORD_TYPES:
            return "cif"
        if line[:1] == "A" and not line[1:5].strip():
            return "msn"
        return None

    def _load_station_line(self, line: str) -> None:
        if line[:1] != "A":
            return
        # The first line of the real MSN file is a control record whose category
        # is the letter S, not one of the numeric station categories. Reading it
        # as a station is how the invalid "tiploc" PEC=05 and CRS 2/0 appeared.
        if not _text(line, MSN_STATION_OFFSETS, "category").isdigit():
            return
        raw_tiploc = _text(line, MSN_STATION_OFFSETS, "tiploc")
        tiploc = normalize_tiploc(raw_tiploc)
        if not tiploc:
            return
        if raw_tiploc != tiploc:
            self.tiploc_variants.setdefault(tiploc, set()).add(raw_tiploc)
        crs = _text(line, MSN_STATION_OFFSETS, "crs").upper()
        self.stations_by_tiploc[tiploc] = TimetableStation(
            tiploc=tiploc,
            crs=crs,
            name=_text(line, MSN_STATION_OFFSETS, "name"),
            change_time=int(_text(line, MSN_STATION_OFFSETS, "change_time") or 0),
        )
        if crs:
            self.crs_by_tiploc[tiploc] = crs

    def _cif_line(self, line: str, state: _CifState) -> None:
        record_type = line[:2]
        if record_type == "BS":
            self._commit(state)
            state.reset()
            state.date_from = _text(line, CIF_SCHEDULE_OFFSETS, "date_runs_from")
            state.date_to = _text(line, CIF_SCHEDULE_OFFSETS, "date_runs_to")
            state.days = _text(line, CIF_SCHEDULE_OFFSETS, "days")
            state.stp_indicator = _text(line, CIF_SCHEDULE_OFFSETS, "stp_indicator").upper()
            if _text(line, CIF_SCHEDULE_OFFSETS, "transaction_type").upper() == "D":
                return
            state.train_uid = self._require(line, CIF_SCHEDULE_OFFSETS, "train_uid")
        elif record_type == "LO":
            state.stops.append(
                CallingPoint(
                    tiploc=self._stop_tiploc(line, CIF_ORIGIN_OFFSETS),
                    arrival=None,
                    departure=_minutes(self._require(line, CIF_ORIGIN_OFFSETS, "scheduled_departure")),
                    public_arrival=None,
                    public_departure=_minutes(self._require(line, CIF_ORIGIN_OFFSETS, "public_departure")),
                )
            )
        elif record_type == "LI":
            state.stops.append(
                CallingPoint(
                    tiploc=self._stop_tiploc(line, CIF_INTERMEDIATE_OFFSETS),
                    arrival=_minutes(self._require(line, CIF_INTERMEDIATE_OFFSETS, "scheduled_arrival")),
                    departure=_minutes(self._require(line, CIF_INTERMEDIATE_OFFSETS, "scheduled_departure")),
                    public_arrival=_minutes(self._require(line, CIF_INTERMEDIATE_OFFSETS, "public_arrival")),
                    public_departure=_minutes(self._require(line, CIF_INTERMEDIATE_OFFSETS, "public_departure")),
                )
            )
        elif record_type == "LT":
            state.stops.append(
                CallingPoint(
                    tiploc=self._stop_tiploc(line, CIF_TERMINUS_OFFSETS),
                    arrival=_minutes(self._require(line, CIF_TERMINUS_OFFSETS, "scheduled_arrival")),
                    departure=None,
                    public_arrival=_minutes(self._require(line, CIF_TERMINUS_OFFSETS, "public_arrival")),
                    public_departure=None,
                )
            )
        elif record_type in {"TI", "TA"}:
            tiploc = normalize_tiploc(_text(line, CIF_TIPLOC_INSERT_OFFSETS, "tiploc"))
            raw_crs = _text(line, CIF_TIPLOC_INSERT_OFFSETS, "crs")
            crs = raw_crs.upper()
            if tiploc:
                # Keep the location even when its CRS is blank: a blank CRS is
                # how the feed marks an operational or non-passenger location.
                existing = self.cif_locations_by_tiploc.get(tiploc)
                if existing is None or (not existing and crs):
                    self.cif_locations_by_tiploc[tiploc] = crs
                if crs:
                    self.cif_crs_by_tiploc.setdefault(tiploc, crs)
        elif record_type == "TD":
            tiploc = normalize_tiploc(_text(line, CIF_TIPLOC_DELETE_OFFSETS, "tiploc"))
            # A CIF delete removes a CIF insert, not a station names entry. The
            # station names file wins whatever the load order (ADR-0006), so
            # popping stations_by_tiploc here was wrong.
            self.cif_crs_by_tiploc.pop(tiploc, None)
            self.cif_locations_by_tiploc.pop(tiploc, None)

    @staticmethod
    def _require(line: str, offsets: dict[str, tuple[int, int]], name: str) -> str:
        """Read a field that must be present, so a truncated record is reported rather than guessed."""
        end = offsets[name][1]
        if len(line) < end:
            raise ValueError(f"record is {len(line)} characters, {name} needs {end}")
        return _text(line, offsets, name)

    def _stop_tiploc(self, line: str, offsets: dict[str, tuple[int, int]]) -> str:
        """Read and canonicalise a calling point's TIPLOC, keeping the raw value."""
        start, end = offsets["location"]
        if len(line) < end:
            raise ValueError(f"record is {len(line)} characters, location needs {end}")
        raw = line[start:start + 7]
        tiploc = stop_tiploc_from_field(line[start:end])
        if raw != tiploc:
            self.tiploc_variants.setdefault(tiploc, set()).add(raw)
        return tiploc

    def _commit(self, state: _CifState) -> None:
        if state.train_uid and len(state.stops) >= 2:
            if self._focus_tiplocs is not None and not any(
                stop.tiploc in self._focus_tiplocs for stop in state.stops
            ):
                return
            self.schedules.append(
                Schedule(
                    train_uid=state.train_uid,
                    stops=tuple(state.stops),
                    date_from=state.date_from,
                    date_to=state.date_to,
                    days=state.days,
                    stp_indicator=state.stp_indicator,
                )
            )

    def _invalidate_indexes(self) -> None:
        self._departures = None
        self._arrivals = None
        self._index_day = _UNSET
        self._crs_cache.clear()
        self._schedule_crs.clear()
        self._schedule_dest_stops.clear()
        self._change_times.clear()

    # -- lookups ---------------------------------------------------------

    def crs_for_tiploc(self, tiploc: str) -> str | None:
        """Resolve a TIPLOC to a station code. The station names file wins, whatever the load order.

        Memoized: the mapping is static once the feed is loaded, and the
        journey search calls this once per stop of every candidate journey -
        millions of times on a full-network build, where an uncached double
        dict probe per call is the profile's single largest cost.
        """
        key = normalize_tiploc(tiploc)
        cached = self._crs_cache.get(key, _MISSING)
        if cached is not _MISSING:
            return cached
        crs = self.crs_by_tiploc.get(key)
        if not crs:
            crs = self.cif_crs_by_tiploc.get(key)
        self._crs_cache[key] = crs
        return crs

    def station_for_tiploc(self, tiploc: str) -> TimetableStation | None:
        return self.stations_by_tiploc.get(normalize_tiploc(tiploc))

    def used_tiplocs(self) -> set[str]:
        """Every canonical TIPLOC a schedule calls at."""
        return {
            stop.tiploc
            for schedule in self.schedules
            for stop in schedule.stops
            if stop.tiploc
        }

    def tiploc_resolution(self, tiploc: str) -> str:
        """Classify why a TIPLOC does or does not resolve to a station code.

        "No CRS" is not the same as "not a station": the feed marks operational
        and non-passenger locations with a TIPLOC insert and a blank CRS, and
        those must not be read as a missing station record.
        """
        key = normalize_tiploc(tiploc)
        if not key:
            return "empty"
        if self.crs_for_tiploc(key):
            return "resolved"
        if key in self.stations_by_tiploc:
            return "station_record_without_crs"
        if key in self.cif_locations_by_tiploc:
            return "location_record_without_crs"
        return "no_record"

    def normalized_tiploc_count(self) -> int:
        """Canonical TIPLOCs whose raw seven-character value was not identical."""
        return len(self.tiploc_variants)

    def connection_minutes_at(self, crs: str) -> int:
        for station in self.stations_by_tiploc.values():
            if station.crs == crs and station.change_time:
                return station.change_time
        return DEFAULT_CONNECTION_MINUTES

    def active_schedules(self, day: date) -> list[int]:
        """Schedule indexes running on a date, with overlays and cancellations applied.

        An overlay replaces the permanent schedule of the same train identity. A
        cancellation removes it, unless an overlay covers the same date.
        """
        buckets: dict[str, dict[str, list[int]]] = {}
        cancelled: set[str] = set()
        for index, schedule in enumerate(self.schedules):
            if not schedule.runs_on(day):
                continue
            if schedule.stp_indicator == "C":
                cancelled.add(schedule.train_uid)
                continue
            bucket = buckets.setdefault(schedule.train_uid, {"overlay": [], "permanent": []})
            key = "overlay" if schedule.stp_indicator == "O" else "permanent"
            bucket[key].append(index)
        active: list[int] = []
        for train_uid, bucket in buckets.items():
            if bucket["overlay"]:
                active.extend(bucket["overlay"])
            elif train_uid not in cancelled:
                active.extend(bucket["permanent"])
        return sorted(active)

    def _ensure_indexes(self, day: date | None = None) -> None:
        if self._departures is not None and self._index_day == day:
            return
        schedule_indexes = range(len(self.schedules)) if day is None else self.active_schedules(day)
        departures: dict[str, list[tuple[int, int, int]]] = {}
        arrivals: dict[str, list[tuple[int, int, int]]] = {}
        # Each schedule's stop CRS chain is resolved once here, and the search
        # loops read the chain instead of re-resolving tiplocs per candidate
        # journey. On a full-network build that lookup was the profile's
        # largest single cost - millions of calls to re-answer a question the
        # feed answers once.
        self._schedule_crs = {
            schedule_index: tuple(self.crs_for_tiploc(stop.tiploc) for stop in self.schedules[schedule_index].stops)
            for schedule_index in schedule_indexes
        }
        # Where each schedule calls at each station, by position. The one-change
        # search used to walk every remaining stop of every candidate onward
        # service to find the destination; this index answers it with a bisect,
        # which is what keeps a full-network build out of quadratic time.
        self._schedule_dest_stops = {}
        for schedule_index in schedule_indexes:
            chain = self._schedule_crs[schedule_index]
            stops_of: dict[str, list[int]] = {}
            for position, stop_crs in enumerate(chain):
                if stop_crs is not None:
                    stops_of.setdefault(stop_crs, []).append(position)
            self._schedule_dest_stops[schedule_index] = stops_of
        # Connection time per station, first station record wins - the same
        # answer connection_minutes_at gives, minus its linear scan per call,
        # which sat inside the search's hottest loop.
        self._change_times = {}
        for station in self.stations_by_tiploc.values():
            if station.crs and station.change_time and station.crs not in self._change_times:
                self._change_times[station.crs] = station.change_time
        for schedule_index in schedule_indexes:
            schedule = self.schedules[schedule_index]
            crs_chain = self._schedule_crs[schedule_index]
            for stop_index, stop in enumerate(schedule.stops):
                crs = crs_chain[stop_index]
                if crs is None:
                    continue
                board = stop.board
                alight = stop.alight
                if board is not None:
                    departures.setdefault(crs, []).append((board, schedule_index, stop_index))
                if alight is not None:
                    arrivals.setdefault(crs, []).append((alight, schedule_index, stop_index))
        for entries in departures.values():
            entries.sort()
        for entries in arrivals.values():
            entries.sort()
        self._departures = departures
        self._arrivals = arrivals
        self._departure_times = {
            crs: [entry[0] for entry in entries] for crs, entries in departures.items()
        }
        self._index_day = day

    def stats(self) -> dict[str, int]:
        return {
            "stations": len(self.stations_by_tiploc),
            "schedules": len(self.schedules),
            "calling_points": sum(len(schedule.stops) for schedule in self.schedules),
        }

    def service_window(self) -> tuple[str, str]:
        """The earliest start and latest end across every schedule's dates.

        The dates are the feed's own, not the download's: a timetable is current
        for the window it says it covers, whatever day the file was fetched. A
        reader deciding whether to trust a journey time needs that window beside
        the time, so it is computed here once and read by the page and the
        audit rather than re-derived from the schedules in each.
        """
        if self._service_window is None or self._service_window[1] != len(self.schedules):
            # One pass rather than two sorts, and memoised: a full-network build
            # asks for the window once per origin, and the answer cannot change
            # while the database is loaded.
            first = last = ""
            for schedule in self.schedules:
                if schedule.date_from and (not first or schedule.date_from < first):
                    first = schedule.date_from
                if schedule.date_to and schedule.date_to > last:
                    last = schedule.date_to
            self._service_window = ((first, last), len(self.schedules))
        return self._service_window[0]

    # -- journeys --------------------------------------------------------

    def best_journey(
        self,
        origin_crs: str,
        destination_crs: str,
        *,
        max_changes: int = 1,
        connection_minutes: int | None = None,
        day: date | None = None,
        max_onward: int | None = MAX_ONWARD_DEPARTURES,
    ) -> Journey | None:
        self._ensure_indexes(day)
        best = self._direct_journey(origin_crs, destination_crs)
        if max_changes >= 1:
            best = self._one_change_journey(origin_crs, destination_crs, best, connection_minutes, max_onward)
        return best

    def _direct_journey(self, origin_crs: str, destination_crs: str) -> Journey | None:
        best: Journey | None = None
        for departure, schedule_index, stop_index in self._departures.get(origin_crs, ()):
            schedule = self.schedules[schedule_index]
            for later in range(stop_index + 1, len(schedule.stops)):
                stop = schedule.stops[later]
                if self.crs_for_tiploc(stop.tiploc) != destination_crs:
                    continue
                arrival = stop.alight
                if arrival is None:
                    continue
                if arrival < departure:
                    arrival += MINUTES_PER_DAY
                leg = Leg(schedule.train_uid, origin_crs, destination_crs, departure, arrival)
                journey = Journey(origin_crs, destination_crs, departure, arrival, (leg,))
                if best is None or _rank(journey) < _rank(best):
                    best = journey
        return best

    def departures(
        self,
        origin_crs: str,
        destination_crs: str,
        *,
        limit: int = 6,
        max_changes: int = 1,
        connection_minutes: int | None = None,
        day: date | None = None,
        max_onward: int | None = MAX_ONWARD_DEPARTURES,
    ) -> list[Journey]:
        """The next few ways to make the trip, earliest departure first.

        One entry per departure time, so a destination served twice at 09:00
        does not fill the list twice, and each entry is the best journey leaving
        at that time. This is a list of options in the feed, not a booking
        system: it does not know which of them is cheapest, because the fare
        this tool reports is a walk-up fare valid on any of them.
        """
        self._ensure_indexes(day)
        found: dict[int, Journey] = {}
        for departure, schedule_index, stop_index in self._departures.get(origin_crs, ()):
            if len(found) >= limit and departure > max(found):
                break
            schedule = self.schedules[schedule_index]
            chosen = self._direct_from(origin_crs, destination_crs, departure, schedule, stop_index)
            if max_changes >= 1:
                via = self._one_change_from(
                    origin_crs,
                    destination_crs,
                    departure,
                    schedule,
                    schedule_index,
                    stop_index,
                    chosen,
                    connection_minutes,
                    max_onward,
                )
                if via is not None and (chosen is None or _rank(via) < _rank(chosen)):
                    chosen = via
            if chosen is None:
                continue
            current = found.get(departure)
            if current is None or _rank(chosen) < _rank(current):
                found[departure] = chosen
        return [found[key] for key in sorted(found)][:limit]

    def _direct_from(
        self,
        origin_crs: str,
        destination_crs: str,
        departure: int,
        schedule: Schedule,
        stop_index: int,
    ) -> Journey | None:
        """The best direct journey on one schedule leaving at one time."""
        best: Journey | None = None
        for later in range(stop_index + 1, len(schedule.stops)):
            arrival = self._arrival_at(schedule, later, destination_crs, departure)
            if arrival is None:
                continue
            leg = Leg(schedule.train_uid, origin_crs, destination_crs, departure, arrival)
            journey = Journey(origin_crs, destination_crs, departure, arrival, (leg,))
            if best is None or _rank(journey) < _rank(best):
                best = journey
        return best

    def _one_change_from(
        self,
        origin_crs: str,
        destination_crs: str,
        departure: int,
        schedule: Schedule,
        schedule_index: int,
        stop_index: int,
        best: Journey | None,
        connection_minutes: int | None,
        max_onward: int | None,
    ) -> Journey | None:
        """The best one-change journey leaving on one schedule at one time.

        The one place the one-change search is written. best_journey() drives
        it over every origin departure through _one_change_journey, and
        departures() calls it per departure directly, so the two share one
        implementation. It reads three indexes built once in _ensure_indexes:
        the schedule's crs chain, a per-destination position map, and a
        per-station change-time dict. It used to resolve each interchange with
        crs_for_tiploc, look the connection time up with connection_minutes_at
        (a linear scan over every station), and find the onward arrival by
        walking every later stop of every candidate onward service. On a real
        origin that last scan was 283 million stop reads for a single
        origin-to-destination pair, so one station page cost hours. The results
        are unchanged: byte-identical to the scan it replaced.
        """
        crs_chain = self._schedule_crs[schedule_index]
        for interchange_index in range(stop_index + 1, len(schedule.stops)):
            interchange_stop = schedule.stops[interchange_index]
            interchange_crs = crs_chain[interchange_index]
            if interchange_crs is None or interchange_crs in {origin_crs, destination_crs}:
                continue
            arrival_at_interchange = interchange_stop.alight
            if arrival_at_interchange is None:
                continue
            if arrival_at_interchange < departure:
                arrival_at_interchange += MINUTES_PER_DAY
            wait = (
                connection_minutes
                if connection_minutes is not None
                else self._change_times.get(interchange_crs, DEFAULT_CONNECTION_MINUTES)
            )
            earliest_onward = arrival_at_interchange + max(wait, 1)
            if best is not None and earliest_onward >= best.arrival:
                continue
            entries = self._departures.get(interchange_crs)
            if not entries:
                continue
            times = self._departure_times[interchange_crs]
            start = bisect.bisect_left(times, earliest_onward)
            window = entries[start:] if max_onward is None else entries[start : start + max_onward]
            for onward_departure, onward_index, onward_stop_index in window:
                if onward_index == schedule_index:
                    continue
                onward_schedule = self.schedules[onward_index]
                # Where this onward service calls the destination after the
                # boarding stop, from the same index _one_change_journey reads.
                # The same train may call there more than once, and each call is
                # a candidate arrival.
                positions = self._schedule_dest_stops[onward_index].get(destination_crs)
                if positions is None:
                    continue
                for later in positions[bisect.bisect_right(positions, onward_stop_index) :]:
                    arrival = onward_schedule.stops[later].alight
                    if arrival is None:
                        continue
                    if arrival < onward_departure:
                        arrival += MINUTES_PER_DAY
                    legs = (
                        Leg(schedule.train_uid, origin_crs, interchange_crs, departure, arrival_at_interchange),
                        Leg(onward_schedule.train_uid, interchange_crs, destination_crs, onward_departure, arrival),
                    )
                    journey = Journey(origin_crs, destination_crs, departure, arrival, legs)
                    if best is None or _rank(journey) < _rank(best):
                        best = journey
        return best

    def _arrival_at(
        self, schedule: Schedule, stop_index: int, destination_crs: str, departure: int
    ) -> int | None:
        """When this schedule reaches the destination at or after stop_index.

        Returns None when it does not call there. Both searches read arrivals
        through here, so a change in how a destination is matched cannot reach
        one and miss the other.
        """
        stop = schedule.stops[stop_index]
        if self.crs_for_tiploc(stop.tiploc) != destination_crs:
            return None
        arrival = stop.alight
        if arrival is None:
            return None
        return arrival + MINUTES_PER_DAY if arrival < departure else arrival

    def _one_change_journey(
        self,
        origin_crs: str,
        destination_crs: str,
        best: Journey | None,
        connection_minutes: int | None,
        max_onward: int | None,
    ) -> Journey | None:
        """The best one-change journey from the origin to the destination.

        Drives _one_change_from over every departure the origin makes. The
        per-departure one-change search lives in exactly one place, in
        _one_change_from, so best_journey() and departures() cannot read the
        data differently -- the divergence that let an 81-second un-indexed
        copy sit beside a 1.7-second indexed one for a whole release.
        """
        for departure, schedule_index, stop_index in self._departures.get(origin_crs, ()):
            if best is not None and departure >= best.arrival:
                break
            best = self._one_change_from(
                origin_crs,
                destination_crs,
                departure,
                self.schedules[schedule_index],
                schedule_index,
                stop_index,
                best,
                connection_minutes,
                max_onward,
            )
        return best
