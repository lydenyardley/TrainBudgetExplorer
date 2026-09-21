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
import zipfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONNECTION_MINUTES = 5
MAX_ONWARD_DEPARTURES = 60
MINUTES_PER_DAY = 1440

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
        self.schedules: list[Schedule] = []
        self.files_read: list[str] = []
        self._departures: dict[str, list[tuple[int, int, int]]] | None = None
        self._arrivals: dict[str, list[tuple[int, int, int]]] | None = None
        self._departure_times: dict[str, list[int]] = {}

    # -- loading ---------------------------------------------------------

    def load_feed(self, path: str | Path) -> "TimetableDb":
        path = Path(path)
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file():
                    self._load_file(child.name, child.read_text(encoding="utf-8", errors="replace"))
        elif path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for name in sorted(archive.namelist()):
                    if name.endswith("/"):
                        continue
                    with archive.open(name) as handle:
                        self._load_file(name, handle.read().decode("utf-8", errors="replace"))
        else:
            self._load_file(path.name, path.read_text(encoding="utf-8", errors="replace"))
        return self

    def _load_file(self, name: str, text: str) -> None:
        kind = self._detect(name, text)
        if kind is None:
            return
        self.files_read.append(name)
        self._invalidate_indexes()
        if kind == "cif":
            self._load_cif(text)
        else:
            self._load_station_names(text)

    @staticmethod
    def _detect(name: str, text: str) -> str | None:
        extension = Path(name).suffix.lower().lstrip(".")
        if extension in CIF_EXTENSIONS:
            return "cif"
        if extension in MSN_EXTENSIONS:
            return "msn"
        for line in text.splitlines():
            if not line.strip():
                continue
            if line[:2] in CIF_RECORD_TYPES:
                return "cif"
            if line[:1] in {"A", "L", "V"} and len(line) > 20:
                return "msn"
            return None
        return None

    def _load_station_names(self, text: str) -> None:
        for line in text.splitlines():
            if not line.strip() or line[:1] != "A":
                continue
            tiploc = _text(line, MSN_STATION_OFFSETS, "tiploc")
            crs = _text(line, MSN_STATION_OFFSETS, "crs").upper()
            if not tiploc:
                continue
            self.stations_by_tiploc[tiploc] = TimetableStation(
                tiploc=tiploc,
                crs=crs,
                name=_text(line, MSN_STATION_OFFSETS, "name"),
                change_time=int(_text(line, MSN_STATION_OFFSETS, "change_time") or 0),
            )
            if crs:
                self.crs_by_tiploc[tiploc] = crs

    def _load_cif(self, text: str) -> None:
        train_uid = ""
        stops: list[CallingPoint] = []
        for line in text.splitlines():
            record_type = line[:2]
            if record_type == "BS":
                self._commit_schedule(train_uid, stops)
                train_uid = ""
                stops = []
                if _text(line, CIF_SCHEDULE_OFFSETS, "transaction_type").upper() == "D":
                    continue
                train_uid = _text(line, CIF_SCHEDULE_OFFSETS, "train_uid")
            elif record_type == "LO":
                stops.append(
                    CallingPoint(
                        tiploc=_text(line, CIF_ORIGIN_OFFSETS, "location")[:7],
                        arrival=None,
                        departure=_minutes(_text(line, CIF_ORIGIN_OFFSETS, "scheduled_departure")),
                        public_arrival=None,
                        public_departure=_minutes(_text(line, CIF_ORIGIN_OFFSETS, "public_departure")),
                    )
                )
            elif record_type == "LI":
                stops.append(
                    CallingPoint(
                        tiploc=_text(line, CIF_INTERMEDIATE_OFFSETS, "location")[:7],
                        arrival=_minutes(_text(line, CIF_INTERMEDIATE_OFFSETS, "scheduled_arrival")),
                        departure=_minutes(_text(line, CIF_INTERMEDIATE_OFFSETS, "scheduled_departure")),
                        public_arrival=_minutes(_text(line, CIF_INTERMEDIATE_OFFSETS, "public_arrival")),
                        public_departure=_minutes(_text(line, CIF_INTERMEDIATE_OFFSETS, "public_departure")),
                    )
                )
            elif record_type == "LT":
                stops.append(
                    CallingPoint(
                        tiploc=_text(line, CIF_TERMINUS_OFFSETS, "location")[:7],
                        arrival=_minutes(_text(line, CIF_TERMINUS_OFFSETS, "scheduled_arrival")),
                        departure=None,
                        public_arrival=_minutes(_text(line, CIF_TERMINUS_OFFSETS, "public_arrival")),
                        public_departure=None,
                    )
                )
            elif record_type in {"TI", "TA"}:
                tiploc = _text(line, CIF_TIPLOC_INSERT_OFFSETS, "tiploc")
                crs = _text(line, CIF_TIPLOC_INSERT_OFFSETS, "crs").upper()
                if tiploc and crs:
                    self.cif_crs_by_tiploc.setdefault(tiploc, crs)
            elif record_type == "TD":
                tiploc = _text(line, CIF_TIPLOC_DELETE_OFFSETS, "tiploc")
                self.cif_crs_by_tiploc.pop(tiploc, None)
                self.stations_by_tiploc.pop(tiploc, None)
        self._commit_schedule(train_uid, stops)

    def _commit_schedule(self, train_uid: str, stops: list[CallingPoint]) -> None:
        if train_uid and len(stops) >= 2:
            self.schedules.append(Schedule(train_uid=train_uid, stops=tuple(stops)))

    def _invalidate_indexes(self) -> None:
        self._departures = None
        self._arrivals = None

    # -- lookups ---------------------------------------------------------

    def crs_for_tiploc(self, tiploc: str) -> str | None:
        """Resolve a TIPLOC to a station code. The station names file wins, whatever the load order."""
        crs = self.crs_by_tiploc.get(tiploc)
        if crs:
            return crs
        return self.cif_crs_by_tiploc.get(tiploc)

    def station_for_tiploc(self, tiploc: str) -> TimetableStation | None:
        return self.stations_by_tiploc.get(tiploc)

    def connection_minutes_at(self, crs: str) -> int:
        for station in self.stations_by_tiploc.values():
            if station.crs == crs and station.change_time:
                return station.change_time
        return DEFAULT_CONNECTION_MINUTES

    def _ensure_indexes(self) -> None:
        if self._departures is not None:
            return
        departures: dict[str, list[tuple[int, int, int]]] = {}
        arrivals: dict[str, list[tuple[int, int, int]]] = {}
        for schedule_index, schedule in enumerate(self.schedules):
            for stop_index, stop in enumerate(schedule.stops):
                crs = self.crs_for_tiploc(stop.tiploc)
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

    def stats(self) -> dict[str, int]:
        return {
            "stations": len(self.stations_by_tiploc),
            "schedules": len(self.schedules),
            "calling_points": sum(len(schedule.stops) for schedule in self.schedules),
        }

    # -- journeys --------------------------------------------------------

    def best_journey(
        self,
        origin_crs: str,
        destination_crs: str,
        *,
        max_changes: int = 1,
        connection_minutes: int | None = None,
    ) -> Journey | None:
        self._ensure_indexes()
        best = self._direct_journey(origin_crs, destination_crs)
        if max_changes >= 1:
            best = self._one_change_journey(origin_crs, destination_crs, best, connection_minutes)
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

    def _one_change_journey(
        self,
        origin_crs: str,
        destination_crs: str,
        best: Journey | None,
        connection_minutes: int | None,
    ) -> Journey | None:
        for departure, schedule_index, stop_index in self._departures.get(origin_crs, ()):
            if best is not None and departure >= best.arrival:
                break
            schedule = self.schedules[schedule_index]
            for interchange_index in range(stop_index + 1, len(schedule.stops)):
                interchange_stop = schedule.stops[interchange_index]
                interchange_crs = self.crs_for_tiploc(interchange_stop.tiploc)
                if interchange_crs is None or interchange_crs in {origin_crs, destination_crs}:
                    continue
                arrival_at_interchange = interchange_stop.alight
                if arrival_at_interchange is None:
                    continue
                if arrival_at_interchange < departure:
                    arrival_at_interchange += MINUTES_PER_DAY
                wait = connection_minutes if connection_minutes is not None else self.connection_minutes_at(interchange_crs)
                earliest_onward = arrival_at_interchange + max(wait, 1)
                if best is not None and earliest_onward >= best.arrival:
                    continue
                entries = self._departures.get(interchange_crs)
                if not entries:
                    continue
                times = self._departure_times[interchange_crs]
                start = bisect.bisect_left(times, earliest_onward)
                for onward_departure, onward_index, onward_stop_index in entries[start : start + MAX_ONWARD_DEPARTURES]:
                    if onward_index == schedule_index:
                        continue
                    onward_schedule = self.schedules[onward_index]
                    for later in range(onward_stop_index + 1, len(onward_schedule.stops)):
                        stop = onward_schedule.stops[later]
                        if self.crs_for_tiploc(stop.tiploc) != destination_crs:
                            continue
                        arrival = stop.alight
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
