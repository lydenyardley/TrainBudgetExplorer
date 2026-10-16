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
import datetime
import json
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

# What a schedule is, from the CIF's own code tables (Open Rail Data Wiki, "CIF
# Codes"): the two fields a whole-CIF feed fills and the DTD timetable product
# never makes a reader look at, because it is filtered to passenger services
# before it is published.
#
# A blank or unrecognised value is kept. A synthetic feed does not fill every
# field, and one blank field must not empty a page; a code these tables do not
# name is a reason to read the record rather than to drop it.
NON_PASSENGER_STATUS = frozenset(
    {
        "B",  # bus
        "F",  # freight
        "S",  # ship
        "T",  # trip
        "2",  # freight, short-notice plan
        "3",  # trip, short-notice plan
        "4",  # ship, short-notice plan
        "5",  # bus, short-notice plan
    }
)
NON_PASSENGER_CATEGORY = frozenset(
    {
        "EE",  # empty coaching stock
        "EL",  # empty coaching stock, London Underground / metro
        "ES",  # empty coaching stock and staff
        "JJ",  # postal
        "PM",  # post office controlled parcels
        "PP",  # parcels
        "PV",  # empty NPCCS
    }
)


def is_passenger_service(status: str, category: str) -> bool:
    """Whether a CIF schedule is one a passenger can take.

    The status is what the train is and the category is what it carries, and
    either can disqualify it: an empty-stock move is a passenger train (status
    ``P``) that carries nobody, which is why the status alone is not the test.
    """
    if status.strip().upper() in NON_PASSENGER_STATUS:
        return False
    return category.strip().upper() not in NON_PASSENGER_CATEGORY


def _minutes(value: str) -> int | None:
    """Read a CIF time as minutes past midnight. Blank means the train does not stop.

    So does `0000`, and that is not a detail of the format. The CIF has no
    midnight: a time after it is written 2400 to 2949, so `0000` can only be
    the marker for "no time of this kind here". A train that passes a station
    is recorded that way -- its real time is in the pass-through field, which
    nothing here reads, and its public times are left `0000`.

    Read as a clock time it was midnight, which is a departure: 0 is not None,
    so the departure index took every station on the network to have a service
    leaving at minute zero, and every one of them was a train passing through.
    Measured on the real Grindleford page, that made Manchester eleven minutes
    away and Liverpool seven, because the duration was measured from a
    departure at midnight to a real arrival.
    """
    digits = value.strip()
    if len(digits) < 4 or not digits[:4].isdigit():
        return None
    if digits[:4] == "0000":
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


def _runs_on_window(day: date, date_from: str, date_to: str, days: str) -> bool:
    """Whether a date window and weekday pattern include a date.

    One place, because a schedule and a dropped overlay are both asked
    whether they run on a date, and a schedule that answers one way while
    its own overlay answers the other is how a superseded service comes
    back to life.
    """
    start = _date(date_from)
    if start is not None and day < start:
        return False
    end = _date(date_to)
    if end is not None and day > end:
        return False
    if len(days) < 7:
        return True
    return days[day.weekday()] == "1"


@dataclass(frozen=True, slots=True)
class _SupersedingRecord:
    """An overlay or cancellation the focus filter dropped, kept as a fact.

    A schedule calling at none of the focused stations cannot serve one, so
    the focus drops it. But an overlay supersedes the permanent schedule of
    its own train identity and a cancellation removes it, so dropping one
    resurrects the permanent it was written to replace, and the page then
    offers a journey on a service that is not running that day (audit A10).
    An overlay and a cancellation leave the permanent inactive in the same
    way, so what decides it is the record's dates and weekday pattern and
    none of its calling points. Three short strings a record, not a service
    with a whole timetable, so the memory the focus saves is kept.
    """

    date_from: str
    date_to: str
    days: str
    stp_indicator: str

    def runs_on(self, day: date) -> bool:
        return _runs_on_window(day, self.date_from, self.date_to, self.days)


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
        return _runs_on_window(day, self.date_from, self.date_to, self.days)


@dataclass
class _CifState:
    """One schedule under construction while a record stream is read."""

    train_uid: str = ""
    stops: list[CallingPoint] = field(default_factory=list)
    date_from: str = ""
    date_to: str = ""
    days: str = ""
    stp_indicator: str = ""
    # The two fields that decide whether a passenger can take the service. Held
    # on the schedule under construction because the calling points arrive
    # after the record that carries them, so the decision cannot be made where
    # they are read.
    status: str = ""
    category: str = ""

    def reset(self) -> None:
        self.train_uid = ""
        self.stops = []
        self.status = ""
        self.category = ""


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
        self._schedules_by_uid: dict[str, list[int]] = {}
        # A focused load keeps only schedules touching the requested stations.
        # None means the normal complete database used by audit and analysis.
        self._focus_tiplocs: set[str] | None = None
        # The origin this database was loaded or cut for, so `focused()` can
        # tell one that already answers a page's question from one that has to
        # be cut down to it.
        self._focus_origin: str | None = None
        # TIPLOC -> the indexes of the schedules calling there, and the indexes
        # of this database's overlays and cancellations. Built on the first
        # `focused()` call and kept: a build cuts one slice per page, and the
        # pass that builds these costs more than every slice after the first.
        self._by_tiploc: dict[str, list[int]] | None = None
        self._by_tiploc_len = 0
        self._overlays: list[int] = []
        # Overlays and cancellations the focus dropped, by train identity, so
        # the activity test can still honour them (audit A10).
        self._superseding: dict[str, list[_SupersedingRecord]] = {}
        self._service_window: tuple[tuple[str, str], int] | None = None
        # The counts a slice reports: the database it was cut from rather than
        # the part of it the page needed.
        self._source_stats: dict[str, int] | None = None

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
        if not self._focus_tiplocs:
            # An empty focus is not a small focus, it is an empty feed: every
            # schedule that names no station in the set is dropped, one at a
            # time, while the whole file is read to do it. A whole-CIF feed has
            # no station names file beside its records -- the DTD archive has
            # `.msn`, Network Rail's CIF is one gzipped file -- so asking it to
            # focus itself answered "nowhere" to every page and looked like a
            # station with no journeys. The focus decides how much is held, not
            # whether an answer exists, so the feed is read unfocused instead
            # and the report says which feed and why.
            self._focus_tiplocs = None
            self.report.skip_file(
                f"{Path(path).name}: no station names, so the focus {sorted(focus_crs)} is "
                "not applied and the whole feed is held"
            )

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
            self._focus_origin = focus_origin.strip().upper()
            focus_crs.add(self._focus_origin)
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

    def _tiploc_index(self) -> tuple[dict[str, list[int]], list[int]]:
        """Which schedules call at each TIPLOC, and which records are overlays.

        Indexes rather than schedules: a slice is assembled from the source's
        own schedule objects, so all it costs is a list of references, and this
        is the one pass that has to touch every calling point in the feed to
        make that possible. Rebuilt if the schedule list has since grown, the
        way ``service_window`` re-derives its own answer rather than trusting a
        memo of a database that has changed.
        """
        if self._by_tiploc is None or self._by_tiploc_len != len(self.schedules):
            by_tiploc: dict[str, list[int]] = {}
            overlays: list[int] = []
            for index, schedule in enumerate(self.schedules):
                if schedule.stp_indicator in ("O", "C"):
                    overlays.append(index)
                for stop in schedule.stops:
                    indexes = by_tiploc.get(stop.tiploc)
                    if indexes is None:
                        by_tiploc[stop.tiploc] = [index]
                    else:
                        indexes.append(index)
            self._by_tiploc = by_tiploc
            self._by_tiploc_len = len(self.schedules)
            self._overlays = overlays
        return self._by_tiploc, self._overlays

    def focused(self, origin_crs: str) -> "TimetableDb":
        """The slice of this database that one origin's page is built from.

        A page asks its timetable about one station: what leaves it, where the
        journey changes, and where the onward service calls. Nothing else in the
        feed can answer any of those questions, and on the real DTD download the
        rest of it is 1.87 GB held while the page is assembled -- which is what
        turned a two-station build into an hour of paging on a machine with
        5.1 GB free (docs/build-performance-findings.md).

        The schedules a page can use are exactly two sets. The first is the
        schedules that call the origin, because a journey starts there. The
        second is the schedules that call a station the first set calls, because
        a one-change journey boards its onward service at an interchange on the
        first train's own stop chain. Both are read off the feed's own calling
        points, so every page of every build gets the same answer; the
        single-origin path's focus comes from the destinations the fares feed
        prices, which is a different question and a narrower answer.

        The focus is taken by station code rather than by the exact TIPLOC a
        service was seen to use. A station can have more than one, and an onward
        service calling at another platform group's TIPLOC of an interchange is
        a journey a slice that dropped it would lose while the national index
        still answered it.

        Cut, not parsed. A focused parse costs the same 50.6s as a national one,
        because the loader reads every record before it can decide to drop one
        (measured; see the findings document), so one parse per origin is two
        days of CPU for the network. This is a pass over indexes of a database
        already in memory.

        A database that was already loaded or cut for this origin is returned as
        it is. The single-origin build loads focused on its own origin and then
        asks here for that same focus; re-cutting it would rebuild a database
        that answers identically, and would cut the differently focused
        ``--with-single-timetable`` database down to one focus that has to
        answer for both.

        The slice reports the window and the counts of the database it was cut
        from. The dates and the figures a page carries are claims about the feed
        behind it, and a reader cannot tell which part of a feed the page
        needed.
        """
        origin = origin_crs.strip().upper()
        if self._focus_origin == origin:
            return self
        by_tiploc, overlays = self._tiploc_index()
        # Station code -> its TIPLOCs, from both maps `crs_for_tiploc` resolves
        # through, so a station the CIF inserts name but the station names file
        # does not is still a station this can be asked about.
        by_crs: dict[str, set[str]] = {}
        for mapping in (self.crs_by_tiploc, self.cif_crs_by_tiploc):
            for tiploc, crs in mapping.items():
                by_crs.setdefault(crs, set()).add(tiploc)
        origin_tiplocs = by_crs.get(origin, frozenset())
        origin_indexes: set[int] = set()
        for tiploc in origin_tiplocs:
            origin_indexes.update(by_tiploc.get(tiploc, ()))
        reachable: set[str] = set()
        for index in origin_indexes:
            reachable.update(stop.tiploc for stop in self.schedules[index].stops)
        focus_crs = {origin}
        focus_tiplocs = set(origin_tiplocs)
        for tiploc in reachable:
            crs = self.crs_for_tiploc(tiploc)
            if crs:
                focus_crs.add(crs)
                focus_tiplocs.update(by_crs.get(crs, ()))
        kept: set[int] = set()
        for tiploc in focus_tiplocs:
            kept.update(by_tiploc.get(tiploc, ()))
        schedules = [self.schedules[index] for index in sorted(kept)]
        # The overlays and cancellations the slice drops still decide whether the
        # permanent schedule of the same train runs on a day (audit A10).
        superseding: dict[str, list[_SupersedingRecord]] = {}
        for index in overlays:
            if index in kept:
                continue
            dropped = self.schedules[index]
            superseding.setdefault(dropped.train_uid, []).append(
                _SupersedingRecord(
                    dropped.date_from,
                    dropped.date_to,
                    dropped.days,
                    dropped.stp_indicator,
                )
            )
        slice_ = TimetableDb()
        # Shared, not copied. A station record is not a schedule, and a page
        # answering about one origin still names every station it can be asked
        # about.
        slice_.stations_by_tiploc = self.stations_by_tiploc
        slice_.crs_by_tiploc = self.crs_by_tiploc
        slice_.cif_crs_by_tiploc = self.cif_crs_by_tiploc
        slice_.cif_locations_by_tiploc = self.cif_locations_by_tiploc
        slice_.tiploc_variants = self.tiploc_variants
        slice_.report = self.report
        slice_.files_read = self.files_read
        slice_._focus_origin = origin
        slice_._source_stats = self.stats()
        slice_.schedules = schedules
        slice_._superseding = superseding
        first, last = self.service_window()
        slice_._service_window = ((first, last), len(schedules))
        return slice_

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
            state.status = _text(line, CIF_SCHEDULE_OFFSETS, "status").upper()
            state.category = _text(line, CIF_SCHEDULE_OFFSETS, "category").upper()
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
            if not is_passenger_service(state.status, state.category):
                # Counted rather than dropped in silence: a feed with no freight
                # in it and a feed whose freight was filtered out look the same
                # from every page, so nothing else in the build could say which
                # one this was.
                self.report.non_passenger_schedules += 1
                return
            if self._focus_tiplocs is not None and not any(
                stop.tiploc in self._focus_tiplocs for stop in state.stops
            ):
                if state.stp_indicator in ("O", "C"):
                    self._superseding.setdefault(state.train_uid, []).append(
                        _SupersedingRecord(
                            state.date_from,
                            state.date_to,
                            state.days,
                            state.stp_indicator,
                        )
                    )
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
        self._schedules_by_uid.clear()

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
            elif train_uid not in cancelled and not self._superseded(train_uid, day):
                active.extend(bucket["permanent"])
        return sorted(active)

    def _superseded(self, train_uid: str, day: date) -> bool:
        """Whether the focus dropped an overlay or cancellation covering this date.

        The record is not in ``schedules``, because it calls nowhere the
        focus asked about. Its dates still decide whether the permanent
        schedule of the same train runs on this day.
        """
        return any(record.runs_on(day) for record in self._superseding.get(train_uid, ()))

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
        # Train identity -> the indexes of that train's schedules today. A page
        # asks which stations a journey's train calls at between two ends, once
        # per leg (ADR-0061), and that question was answered by scanning every
        # schedule in the day for the identity: measured at 0.6s a call on the
        # real feed, which is minutes inside one page and was most of what an
        # equivalence sweep spent its time on. Building this is one more pass
        # over indexes the loop above already walks.
        self._schedules_by_uid = {}
        for schedule_index in schedule_indexes:
            self._schedules_by_uid.setdefault(
                self.schedules[schedule_index].train_uid, []
            ).append(schedule_index)
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
        """What this database holds: its stations, schedules and calling points.

        A slice reports the database it was cut from. Those figures are a claim
        about the feed a page was built from, and a page is built from a slice
        of a feed rather than from a feed's worth of it -- the payload carries
        them for the same reason it carries the download's date.
        """
        if self._source_stats is not None:
            return dict(self._source_stats)
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
            # The same stop crs the one-change search reads from the index,
            # rather than resolving the tiploc again: this resolved 6,330 times
            # per destination over ten destinations in a profile of the
            # Nottingham sweep, which is 16% of the whole search spent
            # re-answering a question _ensure_indexes had already answered
            # once per schedule.
            crs_chain = self._schedule_crs[schedule_index]
            for later in range(stop_index + 1, len(schedule.stops)):
                stop = schedule.stops[later]
                if crs_chain[later] != destination_crs:
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
            # The prune is a lower bound on this journey's DURATION, which is
            # what the search ranks on. An onward service cannot arrive before
            # it departs, so this journey is at least this long whatever it
            # catches, and a candidate whose floor is already no better than
            # the best held cannot win (audit A11).
            #
            # It used to ask whether earliest_onward was after best.arrival
            # instead. That is a different question, and ranking by duration
            # while pruning by arrival time discards journeys that leave later
            # and arrive barely any later: Grantham to Alfreton read 122
            # minutes when the same database holds 67, and 28 of Grantham's 101
            # destinations were wrong that way.
            if best is not None and earliest_onward - departure >= best.duration:
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

        Every departure is asked, and there is no early break. There was one,
        on the grounds that a journey leaving after the best journey arrives
        cannot beat it. That holds for the earliest arrival, not for the
        shortest duration this function promises, so the break threw away
        departures on the strength of a ranking it was not doing (audit A11).
        """
        for departure, schedule_index, stop_index in self._departures.get(origin_crs, ()):
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

    def journeys_from(
        self,
        origin_crs: str,
        *,
        max_changes: int = 1,
        connection_minutes: int | None = None,
        day: date | None = None,
        max_onward: int | None = MAX_ONWARD_DEPARTURES,
    ) -> dict[str, Journey]:
        """The best journey from the origin to every station it reaches.

        best_journey() asks this question once per destination, and on the
        one-change path it walks the origin's departures and their interchanges
        and their onward windows afresh each time. All of that work is the same
        for every destination: what differs is only the last step, which asks
        where the onward service calls the destination. So the walk is done once
        and the destinations are answered out of it, which is what a page that
        times every destination on several days needs -- measured on the
        Nottingham page, asking 163 destinations one at a time took 45.9s for a
        seven-day window against this walk once per day.

        The prune is the same one, kept per destination rather than per origin,
        so a destination with a good journey held is pruned exactly as it was
        when it was the only destination under consideration. Every answer is
        asserted equal to best_journey() over the whole page in
        tests/test_journey_fanout.py, because a faster search that answers a
        different question is not a faster search.
        """
        self._ensure_indexes(day)
        best: dict[str, Journey] = {}
        for destination_crs in self._reachable(origin_crs):
            found = self._direct_journey(origin_crs, destination_crs)
            if found is not None:
                best[destination_crs] = found
        if max_changes < 1:
            return best
        for departure, schedule_index, stop_index in self._departures.get(origin_crs, ()):
            schedule = self.schedules[schedule_index]
            crs_chain = self._schedule_crs[schedule_index]
            for interchange_index in range(stop_index + 1, len(schedule.stops)):
                interchange_crs = crs_chain[interchange_index]
                if interchange_crs is None or interchange_crs == origin_crs:
                    continue
                arrival_at_interchange = schedule.stops[interchange_index].alight
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
                    for destination_crs, positions in self._schedule_dest_stops[onward_index].items():
                        if destination_crs == origin_crs or destination_crs == interchange_crs:
                            continue
                        held = best.get(destination_crs)
                        if held is not None and earliest_onward - departure >= held.duration:
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
                            if held is None or _rank(journey) < _rank(held):
                                # Held is refreshed with it. A train can call
                                # a station twice (Georgemas Junction, before
                                # and after Thurso), and the later call was
                                # compared with the answer read before the
                                # loop, so it replaced the better first one.
                                best[destination_crs] = held = journey
        return best

    def intermediate_crs(
        self,
        train_uid: str,
        origin_crs: str,
        destination_crs: str,
        *,
        day: date | None = None,
    ) -> tuple[str, ...]:
        """CRS codes this train calls at between origin and destination, exclusive.

        ADR-0061 wider rule: a two-ticket price may split at any calling point on
        the journey's own train(s), not only at the station the reader leaves.
        The journey names a train_uid and its ends; this reads the schedule's
        stop chain for the stations between those ends. Origin and destination
        are excluded. A train the day does not run, or a pair the train never
        joins in that order, returns an empty tuple.
        """
        self._ensure_indexes(day)
        origin = origin_crs.strip().upper()
        destination = destination_crs.strip().upper()
        uid = train_uid.strip()
        # One lookup, from the day's own index. This scanned every schedule in
        # the day for the identity, which is why a page that asks the question
        # once per leg spent minutes here (see `_ensure_indexes`).
        for schedule_index in self._schedules_by_uid.get(uid, ()):
            schedule = self.schedules[schedule_index]
            crs_chain = self._schedule_crs.get(schedule_index)
            if crs_chain is None:
                crs_chain = tuple(self.crs_for_tiploc(stop.tiploc) for stop in schedule.stops)
            start = None
            end = None
            for position, stop_crs in enumerate(crs_chain):
                if stop_crs == origin and start is None:
                    start = position
                elif (
                    stop_crs == destination
                    and start is not None
                    and position > start
                ):
                    end = position
                    break
            if start is None or end is None:
                continue
            found: list[str] = []
            for stop_crs in crs_chain[start + 1 : end]:
                if (
                    stop_crs
                    and stop_crs not in (origin, destination)
                    and stop_crs not in found
                ):
                    found.append(stop_crs)
            return tuple(found)
        return ()


    def _reachable(self, origin_crs: str) -> set[str]:
        """Every station a service leaving the origin calls after it boards.

        The set the direct pass walks, and the set the one-change pass can only
        add to, so neither pass decides the question for itself.
        """
        found: set[str] = set()
        for _departure, schedule_index, stop_index in self._departures.get(origin_crs, ()):
            crs_chain = self._schedule_crs[schedule_index]
            for later in range(stop_index + 1, len(self.schedules[schedule_index].stops)):
                station = crs_chain[later]
                if station is not None and station != origin_crs:
                    found.add(station)
        return found


#: The on-disk layout of a slice index. Bumped when what a slice file holds
#: changes, because a pickle says nothing about which version of these classes
#: wrote it: without a version, an index written by an older build would be read
#: as if it were current, and a page would be assembled from a timetable that is
#: not the one the code expects.
SLICE_INDEX_SCHEMA = 1


class SliceIndex:
    """A directory of per-origin timetable slices, so a build can skip the feed.

    `TimetableDb.focused` cuts a page's timetable out of a database already in
    memory, which costs holding the whole national index first -- 56.7 s and
    1.87 GB on the real DTD download, in every process that builds a page. A
    slice is the part one page needs and it stays the same for as long as the
    feed does, so it can be written once and read by every build after that.
    That is what this directory is: the timetables a set of pages are built
    from, on disk, so a build can answer them with no feed on the machine at
    all.

    **What a hit depends on.** Everything a slice was cut from: the feed's bytes
    and the source that reads them, as the identity the caller passes. The
    directory *is* that identity, so an index cut from another download is a
    different directory rather than a wrong answer, which is the same discipline
    the fare index and the focused timetable cache follow (ADR-0031).

    **What it costs.** One file per origin, and a slice is as large as that
    origin's reach -- about a quarter of the feed for a main-line station, and
    the schedules are what the bytes are. An index is therefore for the origins
    a build actually writes: `tools/build_timetable_index.py --origins` names
    them, and it reports the size before and after rather than leaving the
    discovery to the file system.

    **What it is not.** Not a whole-network cache. Holding every origin's slice
    is holding the network 3,400 times over, so the tool refuses `--all-origins`
    unless it is told where to put them and how much room it may use.
    """

    def __init__(
        self,
        directory: str | Path,
        *,
        identity: str,
        source: dict | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.identity = identity
        #: Written into the manifest by the first `save`, so a reader can see
        #: what the index was cut from without re-deriving the identity.
        self.source = dict(source or {})
        # The manifest as last read, with the file's own stamp. A build asks
        # `has` once per page -- 3,424 JSON reads of a file that grows with every
        # slice, which is quadratic in the number of slices for no answer that
        # changed -- and another process may write the file while this one runs,
        # so it is revalidated by stamp rather than trusted.
        self._manifest_memo: dict | None = None
        self._manifest_stamp: tuple[int, int] | None = None

    @classmethod
    def open(cls, location: str | Path) -> "SliceIndex | None":
        """Open an index that is already on disk, or None when there is not one.

        Two shapes are accepted, because both are things a build log prints: the
        directory a feed's slices live in, and the root they were written under,
        holding one directory per feed-and-parser identity. With more than one
        identity under the root this is a None rather than a guess, because
        which download a page was built from is not a question to answer by
        taking the first name in a folder.
        """
        root = Path(location)
        if (root / "manifest.json").is_file():
            return cls._opened(root)
        candidates = sorted(
            child for child in root.glob("*") if child.is_dir() and (child / "manifest.json").is_file()
        ) if root.is_dir() else []
        if len(candidates) == 1:
            return cls._opened(candidates[0])
        return None

    @classmethod
    def _opened(cls, directory: Path) -> "SliceIndex | None":
        """An index checking itself against the identity its manifest declares.

        A build with no feed to compare against has only the index's own word
        for what it was cut from, so this trusts the manifest's identity -- and
        the manifest's schema is still checked, because a directory written by a
        different version of this code is not a directory this one can read.
        """
        try:
            raw = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(raw, dict) or raw.get("schema") != SLICE_INDEX_SCHEMA:
            return None
        identity = raw.get("identity")
        if not identity:
            return None
        return cls(directory, identity=identity, source=raw.get("source"))

    @property
    def manifest_path(self) -> Path:
        return self.directory / "manifest.json"

    def slice_path(self, origin_crs: str) -> Path:
        """Where one origin's slice lives, whether or not it is there yet."""
        return self.directory / f"{origin_crs.strip().upper()}.pickle"

    def manifest(self) -> dict:
        """What this directory says it holds, or an empty index when it says nothing.

        A manifest that cannot be read, that another schema wrote, or that was
        cut from a different feed or a different parser is not a manifest: it is
        an empty index, so every origin in it is a miss and the build falls back
        to the feed instead of answering from a stale slice.
        """
        empty = {"schema": SLICE_INDEX_SCHEMA, "identity": self.identity, "origins": {}}
        try:
            stat = self.manifest_path.stat()
        except OSError:
            self._manifest_memo = self._manifest_stamp = None
            return empty
        stamp = (stat.st_mtime_ns, stat.st_size)
        if self._manifest_memo is not None and self._manifest_stamp == stamp:
            return self._manifest_memo
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return empty
        if (
            not isinstance(raw, dict)
            or raw.get("schema") != SLICE_INDEX_SCHEMA
            or raw.get("identity") != self.identity
        ):
            # A directory another feed or another version of this code wrote.
            self._manifest_memo = self._manifest_stamp = None
            return empty
        raw.setdefault("origins", {})
        self._manifest_memo = raw
        self._manifest_stamp = stamp
        return raw

    def has(self, origin_crs: str) -> bool:
        """Whether this index holds a usable file for one origin."""
        origin = origin_crs.strip().upper()
        return origin in self.manifest()["origins"] and self.slice_path(origin).is_file()

    def covers(self, origins) -> bool:
        """Whether every one of these origins is here, so no feed is needed."""
        return all(self.has(origin) for origin in origins)

    def load(self, origin_crs: str) -> TimetableDb | None:
        """One origin's slice, or None when this index has not got it.

        None is a miss, never a partial answer: a file that is not a database,
        that was cut for another origin, or that cannot be read is treated the
        same as one that is not here, and the caller decides whether to fall
        back on the feed or to build the page without times.
        """
        origin = origin_crs.strip().upper()
        if not self.has(origin):
            return None
        try:
            with self.slice_path(origin).open("rb") as handle:
                loaded = pickle.load(handle)
        except (OSError, EOFError, pickle.PickleError, AttributeError, TypeError, ValueError):
            return None
        if not isinstance(loaded, TimetableDb) or loaded._focus_origin != origin:
            return None
        loaded._invalidate_indexes()
        return loaded

    def save(self, origin_crs: str, db: TimetableDb) -> Path:
        """Write one origin's slice, and read it back before calling it written.

        The read-back is the point of this method rather than a formality: a
        slice is written once and read by every build after it, so a file that
        was written badly would be a miss on every one of those builds and the
        cost of finding out would be paid at the far end. A writer that cannot
        read its own output raises here, where the feed that produced it is
        still in hand.
        """
        origin = origin_crs.strip().upper()
        path = self.slice_path(origin)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("wb") as handle:
            pickle.dump(db, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(path)
        # The file itself, not `load`: that one consults the manifest, and this
        # is the step that decides whether the manifest entry is true yet.
        try:
            with path.open("rb") as handle:
                restored = pickle.load(handle)
        except (OSError, EOFError, pickle.PickleError, AttributeError, TypeError, ValueError):
            restored = None
        if (
            not isinstance(restored, TimetableDb)
            or restored._focus_origin != origin
            or len(restored.schedules) != len(db.schedules)
        ):
            raise OSError(
                f"{path} was written but does not read back as {origin}'s slice "
                f"of {len(db.schedules):,} schedules"
            )
        manifest = self.manifest()
        first, last = db.service_window()
        manifest["schema"] = SLICE_INDEX_SCHEMA
        manifest["identity"] = self.identity
        manifest.setdefault("created", datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"))
        manifest.setdefault("source", self.source)
        manifest["origins"][origin] = {
            "schedules": len(db.schedules),
            "feed_schedules": db.stats()["schedules"],
            "calling_points": sum(len(schedule.stops) for schedule in db.schedules),
            "window": [first, last],
            "bytes": path.stat().st_size,
        }
        temporary_manifest = self.manifest_path.with_suffix(".json.tmp")
        temporary_manifest.write_text(
            json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8"
        )
        temporary_manifest.replace(self.manifest_path)
        # The write is this instance's own, so the memo is replaced rather than
        # left to be re-derived: a writer saving 3,400 slices should not read
        # back a manifest it just wrote 3,400 times to find out it is unchanged.
        self._manifest_memo = None
        self._manifest_stamp = None
        return path

    def totals(self) -> dict[str, int]:
        """What the manifest says this index holds, without reading a slice."""
        origins = self.manifest()["origins"]
        return {
            "origins": len(origins),
            "schedules": sum(entry.get("schedules", 0) for entry in origins.values()),
            "calling_points": sum(entry.get("calling_points", 0) for entry in origins.values()),
            "bytes": sum(entry.get("bytes", 0) for entry in origins.values()),
        }

    def describe(self) -> str:
        """One line naming what is here, for a build log."""
        totals = self.totals()
        if not totals["origins"]:
            return f"no slices yet at {self.directory}"
        return (
            f"{totals['origins']:,} slice(s), {totals['schedules']:,} schedules, "
            f"{totals['calling_points']:,} calling points, "
            f"{totals['bytes'] / 1_000_000:.1f} MB at {self.directory}"
        )
