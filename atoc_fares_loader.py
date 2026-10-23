"""Read a feed and its classification sources into the state a query reads.

Everything here writes into tables the ``FaresDb`` instance owns and answers
nothing: the queries are ``atoc_fares.FaresDb``. The split keeps the two
questions apart -- which bytes a database is made of, and what it can be asked
-- without moving a table out of the object that holds it, so a database that
has loaded a feed is still one object with one state, and a reader is reached
exactly as it always was, as ``db._load_location_lookup(...)``.
"""

from __future__ import annotations

import io
import json
import os
import pickle
from fractions import Fraction
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from atoc_fare_declarations import (
    UNEXPANDED_FARE_GROUPS,
    DESTINATION_FACET_READERS,
    DESTINATION_FACET_SOURCES,
    FLOW_F_SLICES,
    FLOW_F_WIDTH,
    FLOW_T_SLICES,
    FLOW_T_WIDTH,
    HERITAGE_STATIONS_BY_SITE,
    LEARNING_PROVIDERS_FILE_URL,
    LOCATION_BAND_TYPES,
    LOCATION_CACHE_SCHEMA,
    LOCATION_FALLBACK_SOURCE,
    LOCATION_OFFSETS,
    LOCATION_TYPES_FILE,
    LOCATION_TYPE_SOURCE,
    LONDON_STATION_CRS,
    MAJOR_UK_STATION_FALLBACKS,
    MINIMUM_FARE_OFFSETS,
    ONS_BUILT_UP_AREAS_DATASET_URL,
    ONS_BUILT_UP_AREAS_FILE_URL,
    ONS_COASTAL_BUILT_UP_AREAS_FILE_URL,
    RAILCARD_OFFSETS,
    REVIEWED_SETTLEMENT_FALLBACKS,
    STATION_CLUSTER_SLICES,
    STATION_CLUSTER_WIDTH,
    STATUS_DISCOUNT_OFFSETS,
    SUPPORTED_DESTINATION_FACETS,
    TICKET_TYPE_OFFSETS,
    UNESCO_WORLD_HERITAGE_FILE_URL,
    DestinationFacet,
    Fare,
    Flow,
    Location,
    MinimumFare,
    Railcard,
    StationClusterMember,
    StatusDiscount,
    TicketType,
    _as_int,
    _parse_dtd_date,
    _require_width,
    _text,
    classification_files,
    dtd_flag,
    location_lookup_candidates,
)
from parse_report import ParseReport, count, decode_lines, read_feed_files


def _count_or_none(value: str) -> int | None:
    """A passenger count, or None for a blank field, which sets no limit."""
    return int(value) if value.isdigit() else None


if TYPE_CHECKING:
    from atoc_fares import FaresDb


# The one feed file a caller needs to answer "which stations does this feed
# name". The shard merge asks exactly that question, and reading the flows to
# answer it is a full parse of the national feed in the process that exists to
# be cheap at the end of a distributed build (E6).
LOCATION_FILE_SUFFIXES = frozenset({"loc"})


class FaresLoader:
    """The loading half of a fares database, which ``FaresDb`` inherits.

    A reader holds no state of its own: it writes into the database it is called
    on. That is why the loader is a base class rather than a set of functions
    taking a state dictionary -- the state ownership stays with the object that
    answers the queries, and ``db._load_flows(line)`` is still where a reader is
    found.
    """

    def _record_location_source(self, label: object) -> None:
        """Note a source that classified part of this feed, keeping every one."""
        text = str(label or "").strip()
        if text and text not in self.location_type_sources:
            self.location_type_sources.append(text)

    def _has_sourced_classes(self) -> bool:
        """Say whether anything but the reviewed lists classified this feed.

        The reviewed fallbacks are the floor under the real sources, not one of
        them: a build whose only classes are theirs still has to read the
        workbook. The answer is read through the same accessor the page reads,
        so a database unpickled from an index written before the labels were
        accumulated answers it too, instead of dying on a missing attribute.
        """
        recorded = self.location_type_source
        return bool(recorded) and recorded != LOCATION_FALLBACK_SOURCE

    # -- loading ---------------------------------------------------------

    def _write_cache(self, cache: Path, value: object) -> None:
        """Write a cache atomically without assuming a process-local suffix."""
        cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache.with_name(f"{cache.name}.{os.getpid()}.tmp")
        with temporary.open("wb") as handle:
            pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(cache)

    def write_fare_indexes(
        self,
        base_path: str | Path,
        index_dir: str | Path,
        origins: list[str] | tuple[str, ...],
    ) -> None:
        """Persist common fare metadata once and a small index per origin.

        A worker's page build needs the location/ticket/restriction tables, but
        only the flows and fares queryable from its own origin. Keeping those
        two pieces in the common file would make every origin cache a copy of
        the national feed. The index files therefore contain just the selected
        flow/fare objects; workers load the common file once and apply one
        index per page.
        """
        # The one name this module cannot import with the record layouts: atoc_fares
        # defines the class after the line that imports this module, so the class
        # exists only once that module has finished. Read where it is used.
        from atoc_fares import FaresDb

        common = FaresDb()
        common.locations_by_nlc = self.locations_by_nlc
        common.locations_by_crs = self.locations_by_crs
        common.location_types_by_crs = self.location_types_by_crs
        common.location_facets_by_crs = self.location_facets_by_crs
        # A database unpickled from an index written before the labels were
        # accumulated has no list; its one label rides on the property instead,
        # and this copy keeps a later build from dying on the missing attribute.
        common.location_type_sources = list(getattr(self, "location_type_sources", []))
        common.nlcs_by_crs = self.nlcs_by_crs
        common.station_clusters = self.station_clusters
        common.ticket_types = self.ticket_types
        common.railcards = self.railcards
        common.minimum_fares = self.minimum_fares
        common.status_discounts = self.status_discounts
        common.restrictions = self.restrictions
        common.report = self.report
        common.files_read = common.report.files_read
        common.feed_stats = self.stats()
        self._write_cache(Path(base_path), common)

        directory = Path(index_dir)
        directory.mkdir(parents=True, exist_ok=True)
        # Each origin's change stations get an index too, because the second
        # ticket of a two-part price is read from the change station's own
        # index (ADR-0061, merge_interchange_indexes). A whole-network build
        # already names nearly all of them; a one-origin build names none.
        wanted = [origin.strip().upper() for origin in origins]
        named = set(wanted)
        for origin in list(wanted):
            for crs in sorted(self.interchange_crs(origin)):
                if crs not in named:
                    named.add(crs)
                    wanted.append(crs)
        for origin in wanted:
            location = self.locations_by_crs.get(origin)
            if location is None:
                continue
            # Its group's and clusters' codes too, or a group (ADR-0074) or
            # cluster (ADR-0075) fare would be priced by a full load and missing
            # from the page built through the index.
            origin_nlcs = self._all_fare_nlcs(origin)
            flow_ids: set[str] = set()
            flows_touching_nlc: dict[str, list[Flow]] = {}
            for nlc in origin_nlcs:
                selected = [
                    flow
                    for flow in self.flows_touching_nlc.get(nlc, ())
                    if flow.flow_id not in flow_ids
                ]
                if selected:
                    flows_touching_nlc[nlc] = selected
                    flow_ids.update(flow.flow_id for flow in selected)
            self._write_cache(
                directory / f"{origin}.pickle",
                {
                    "schema": 1,
                    "origin": origin,
                    "origin_nlcs": set(origin_nlcs),
                    "flows": {
                        flow_id: self.flows[flow_id]
                        for flow_id in flow_ids
                        if flow_id in self.flows
                    },
                    "fares": {
                        flow_id: self.fares_by_flow.get(flow_id, {})
                        for flow_id in flow_ids
                    },
                    "flows_touching_nlc": flows_touching_nlc,
                },
            )

    @classmethod
    def load_fare_common(cls, common_path: str | Path) -> "FaresDb":
        """Load the shared metadata half of a persisted fares cache."""
        # See write_fare_indexes: the class is defined below the import that brings
        # this module in, so it is read where it is used.
        from atoc_fares import FaresDb

        with Path(common_path).open("rb") as handle:
            db = pickle.load(handle)
        if not isinstance(db, FaresDb):
            raise ValueError("invalid common fares cache")
        return db

    @classmethod
    def load_fare_index(
        cls, common_path: str | Path, index_path: str | Path
    ) -> "FaresDb":
        """Load common metadata and one persisted origin index."""
        return cls.apply_fare_index(cls.load_fare_common(common_path), index_path)

    @classmethod
    def apply_fare_index(cls, db: "FaresDb", index_path: str | Path) -> "FaresDb":
        """Apply one origin index to an already loaded common database."""
        with Path(index_path).open("rb") as handle:
            index = pickle.load(handle)
        if not isinstance(index, dict):
            raise ValueError("invalid fares index")
        if index.get("schema") != 1:
            raise ValueError("unsupported fares index schema")
        origin = str(index.get("origin", "")).strip().upper()
        if not origin:
            raise ValueError("fares index has no origin")
        db.flows = index["flows"]
        db.fares_by_flow = index["fares"]
        db.flows_touching_nlc = index["flows_touching_nlc"]
        db._focus_origin_nlcs = set(index["origin_nlcs"])
        db._cache_origin = origin
        return db

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
        if not self._focus_origin_nlcs:
            return
        base_nlcs = set(self._focus_origin_nlcs)
        active_clusters: dict[str, set[tuple[str, str]]] = {}
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if not child.is_file():
                    continue
                if child.suffix.lower() == ".fsc":
                    with child.open("rb") as handle:
                        for line in decode_lines(handle, ParseReport()):
                            self._load_cluster_for_focus(
                                line, base_nlcs, active_clusters
                            )
                elif child.suffix.lower() == ".zip" and zipfile.is_zipfile(child):
                    with zipfile.ZipFile(child) as archive:
                        for name in sorted(archive.namelist()):
                            if not name.lower().endswith(".fsc"):
                                continue
                            with archive.open(name) as handle:
                                for line in decode_lines(handle, ParseReport()):
                                    self._load_cluster_for_focus(
                                        line, base_nlcs, active_clusters
                                    )
        elif root.suffix.lower() == ".zip" and zipfile.is_zipfile(root):
            with zipfile.ZipFile(root) as archive:
                for name in sorted(archive.namelist()):
                    if not name.lower().endswith(".fsc"):
                        continue
                    with archive.open(name) as handle:
                        for line in decode_lines(handle, ParseReport()):
                            self._load_cluster_for_focus(
                                line, base_nlcs, active_clusters
                            )
        for cluster_id, rows in active_clusters.items():
            if rows:
                self._focus_origin_nlcs.add(cluster_id)

    def _load_location_for_focus(self, line: str, origin_crs: str) -> None:
        if _text(line, LOCATION_OFFSETS, "record_type").upper() != "L":
            return
        if _text(line, LOCATION_OFFSETS, "crs").upper() != origin_crs:
            return
        if self._focus_origin_nlcs is not None:
            nlc = _text(line, LOCATION_OFFSETS, "nlc")
            self._focus_origin_nlcs.add(nlc)
            # The station's fare group (ADR-0074): its fares are the station's
            # fares, so they have to survive the stream too. A group the query
            # will not read through only keeps a few records it never asks for.
            group = _text(line, LOCATION_OFFSETS, "group_nlc")
            if group and group != nlc and group not in UNEXPANDED_FARE_GROUPS:
                self._focus_origin_nlcs.add(group)

    @staticmethod
    def _load_cluster_for_focus(
        line: str,
        base_nlcs: set[str],
        active_clusters: dict[str, set[tuple[str, str]]],
    ) -> None:
        if not line or line.startswith("/") or len(line) < STATION_CLUSTER_WIDTH:
            return
        slices = STATION_CLUSTER_SLICES
        member_nlc = line[slices["cluster_nlc"]].strip()
        if member_nlc not in base_nlcs:
            return
        cluster_id = line[slices["cluster_id"]].strip()
        if not cluster_id:
            return
        key = (member_nlc, line[slices["end_date"]].strip())
        if line[slices["update_marker"]].strip().upper() == "D":
            rows = active_clusters.get(cluster_id)
            if rows is not None:
                rows.discard(key)
        else:
            active_clusters.setdefault(cluster_id, set()).add(key)

    def _load_interchange_fares(self, path: str | Path, origin_crs: str) -> None:
        """Read the fares out of the origin's change stations, after the fact.

        ADR-0061: a focused load keeps only fares touching the origin, so the
        second ticket of a two-part price -- King's Cross to Aberdeen, for a
        Grantham page -- was dropped as it streamed past, and the leg analysis
        read "flow with no fare" for all 46 places the feed prices that way.
        The change stations are only known once the origin's flows have been
        read, so the flow file is read a second time for those stations' fares
        alone. A focused load is cached, so this costs once per feed.
        """
        origin_nlcs = set(self._focus_origin_nlcs or ())
        wanted: set[str] = set()
        for crs in self.interchange_crs(origin_crs):
            wanted |= self._all_fare_nlcs(crs)
        wanted -= origin_nlcs
        if not wanted:
            return
        t_type = FLOW_T_SLICES["record_type"]

        def consume(name: str, lines) -> None:
            if Path(name).suffix.lower() != ".ffl":
                return
            for line in lines:
                if line[t_type].strip().upper() != "T":
                    continue
                try:
                    self._load_flows(line)
                except ValueError:
                    # Already counted, with its example, by the first pass.
                    continue

        self._focus_origin_nlcs = wanted
        try:
            read_feed_files(path, ParseReport(), consume)
        finally:
            self._focus_origin_nlcs = origin_nlcs

    def merge_interchange_indexes(self, index_dir: str | Path) -> list[str]:
        """Add each change station's own index to this origin's restored one.

        The per-origin index holds the flows out of one station, and a two-part
        price needs the flows out of the station it changes at as well. Those
        are that station's own index, so they are read from there rather than
        copied into every origin's: King's Cross would otherwise ride along in
        the index of every station whose flows reach it. Returns the change
        stations with no usable index, so a caller can parse rather than serve
        a page missing its second tickets.
        """
        origin = self._cache_origin
        if origin is None:
            return []
        missing: list[str] = []
        for crs in sorted(self.interchange_crs(origin)):
            path = Path(index_dir) / f"{crs}.pickle"
            try:
                with path.open("rb") as handle:
                    index = pickle.load(handle)
            except (OSError, EOFError, pickle.PickleError, AttributeError, TypeError, ValueError):
                missing.append(crs)
                continue
            if (
                not isinstance(index, dict)
                or index.get("schema") != 1
                or str(index.get("origin", "")).strip().upper() != crs
            ):
                missing.append(crs)
                continue
            for flow_id, flow in index["flows"].items():
                self.flows.setdefault(flow_id, flow)
            for flow_id, bucket in index["fares"].items():
                self.fares_by_flow.setdefault(flow_id, bucket)
            for nlc, flows in index["flows_touching_nlc"].items():
                held = self.flows_touching_nlc.setdefault(nlc, [])
                seen = {flow.flow_id for flow in held}
                held.extend(flow for flow in flows if flow.flow_id not in seen)
            if self._focus_origin_nlcs is not None:
                self._focus_origin_nlcs |= set(index["origin_nlcs"])
        return missing

    def _load_location_lookup(self, path: str | Path) -> None:
        """Load the checked-in reference data, or derive it from its sources.

        ``FareLocationsRefData`` is deliberately not treated as a settlement
        classification: it contains fare-location records, not CRS-to-type
        records. A real DTD download can be recognised by its sibling download
        manifest; only then is a missing cache filled from ONS and the other
        named sources, and written back.

        Several files can describe the same station -- the checked-in
        reference data, a cache beside the feed, an XML lookup -- so facets are
        merged rather than replaced. Overwriting let a stale cache silently
        drop a facet the checked-in file had, and left the answer depending on
        the order the directory happened to be listed in.

        The classification files beside a feed are the two this project writes,
        matched by their exact names. A name that merely mentions locations and
        types is not a source, however plausible it looks sitting beside a feed.
        """
        root = Path(path)
        candidates = location_lookup_candidates(root)
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
            self._apply_major_station_fallbacks()

        # A reviewed facet needs no download, so it is applied whether the
        # types came from a cache, from ONS, or from a synthetic feed.
        self._apply_reviewed_facets()

        if self.location_types_by_crs and self._has_sourced_classes():
            return

        lookup_roots = (
            (root.parent, root.parent.parent)
            if root.suffix.lower() == ".zip"
            else (root.parent,)
        )
        lookup_root = next(
            (
                base
                for base in lookup_roots
                if base.joinpath("download-manifest.json").is_file()
                or classification_files(base)
            ),
            root.parent,
        )
        if lookup_root.joinpath("download-manifest.json").is_file():
            try:
                self._load_ons_location_types()
            except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as error:
                self.report.skip_classification(f"ONS station classification unavailable: {error}")
        for facet in DESTINATION_FACET_SOURCES:
            if facet.is_reviewed:
                continue
            try:
                self._apply_destination_facet(facet)
            except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as error:
                self.report.skip_classification(
                    f"{facet.key} station classification unavailable: {error}"
                )
        # One cache write for the whole pass: the facets above have all landed
        # by now, so a per-facet write would publish a partial classification.
        if self.location_types_by_crs:
            self._write_location_cache(lookup_root / LOCATION_TYPES_FILE)
        self._apply_major_station_fallbacks()
        self._apply_reviewed_facets()

    @staticmethod
    def _normalise_location_type(value: object) -> str | None:
        text = str(value or "").strip().lower()
        if "city" in text or "cities" in text or text in {"c", "urban", "metropolitan"}:
            return "city"
        if "small" in text and ("town" in text or text == "small"):
            return "small_town"
        if "village" in text or text in {"v", "hamlet"}:
            return "village"
        if "town" in text or text in {"t", "rural"}:
            return "town"
        return "other" if text else None

    def _apply_reviewed_facets(self) -> None:
        """Tag reviewed and supplement CRS codes the feed actually contains.

        Reviewed-only facets exist because no open settlement list covers them.
        Dataset facets may also declare reviewed_station_codes as a supplement
        (seaside: Blackpool / Brighton / Southend / Weston). Codes are
        intersected with the feed's own stations: a stale code is dropped.
        Name markers stay reviewed-only.
        """
        # The attraction prune reads the station names on file, and this pass is
        # the one place that set changes: a first pass over a feed with no
        # classification yet would cache every attraction's kept CRS as empty,
        # and the pass after the ONS read would reuse it and tag nothing.
        self._attraction_crs_cache.clear()
        for facet in DESTINATION_FACET_SOURCES:
            if facet.reviewed_station_codes:
                for crs in facet.reviewed_station_codes:
                    if crs in self.locations_by_crs:
                        self._tag_station(crs, facet.key)
            for crs in self._facet_attraction_crs(facet):
                self._tag_station(crs, facet.key)
            if not facet.is_reviewed:
                continue
            for marker in facet.reviewed_name_markers:
                needle = marker.upper()
                for crs, location in self.locations_by_crs.items():
                    if crs in facet.excluded_station_codes:
                        continue
                    if needle in location.name.upper():
                        self._tag_station(crs, facet.key)

    def _apply_destination_facet(self, facet: DestinationFacet) -> None:
        """Tag every station whose settlement is named by the facet's source."""
        if facet.is_reviewed:
            self._apply_reviewed_facets()
            return
        reader = DESTINATION_FACET_READERS.get(facet.reader)
        method = getattr(self, reader, None) if reader else None
        if method is None:
            # A missing reader is a ValueError so the caller reports it as an
            # unreadable source instead of the build dying on a KeyError.
            raise ValueError(f"no reader {facet.reader!r} for facet {facet.key!r}")
        names = method()
        if not names:
            raise ValueError(f"{facet.source} returned no settlement names")
        matched = {
            crs
            for crs, location in self.locations_by_crs.items()
            if self._settlement_matches(location.name, names)
        }
        if facet.key == "heritage":
            # A curated name that no longer names a station is a list that has
            # gone stale, and silence would leave it looking current.
            unmatched = sorted(
                station
                for station in names
                if not any(
                    self._settlement_matches(location.name, {station})
                    for location in self.locations_by_crs.values()
                )
            )
            if unmatched:
                self.report.skip_file(
                    f"heritage: {len(unmatched)} curated station names match no station in this "
                    f"feed: {', '.join(unmatched[:8])}"
                    + (" ..." if len(unmatched) > 8 else "")
                )
        for crs in matched:
            self._tag_station(crs, facet.key)

    def _apply_major_station_fallbacks(self) -> None:
        """Classify major stations outside the ONS workbook's national coverage."""
        for crs, location in self.locations_by_crs.items():
            if location.name.strip().upper().startswith("LONDON") and crs not in self.location_types_by_crs:
                self.location_types_by_crs[crs] = "city"
        for crs in LONDON_STATION_CRS:
            if crs in self.locations_by_crs and crs not in self.location_types_by_crs:
                self.location_types_by_crs[crs] = "city"
        for crs, kind in MAJOR_UK_STATION_FALLBACKS.items():
            if crs in self.locations_by_crs and crs not in self.location_types_by_crs:
                self.location_types_by_crs[crs] = kind
        for crs, kind in REVIEWED_SETTLEMENT_FALLBACKS.items():
            if crs in self.locations_by_crs and self.location_types_by_crs.get(crs) in (None, "other"):
                self.location_types_by_crs[crs] = kind
        if any(
            crs in self.location_types_by_crs
            for crs in set(LONDON_STATION_CRS)
            | set(MAJOR_UK_STATION_FALLBACKS)
            | set(REVIEWED_SETTLEMENT_FALLBACKS)
        ):
            # The reviewed lists are a source in their own right, and a build
            # that used them says so even when the workbook classified most of
            # the country: on the real feed the London, Scottish, Welsh and
            # Northern Irish classes are theirs, and the page used to publish
            # them as the workbook's own work.
            self._record_location_source(LOCATION_FALLBACK_SOURCE)
        # A reviewed code the feed does not carry is a dead tail on the list.
        # Every entry here is intersected before it is applied, so a stale code
        # costs nothing at runtime; silence is what lets the list grow one
        # unnoticed (audit A7), the way the heritage reader names an unmatched
        # curated station.
        absent = sorted(
            crs
            for crs in set(LONDON_STATION_CRS)
            | set(MAJOR_UK_STATION_FALLBACKS)
            | set(REVIEWED_SETTLEMENT_FALLBACKS)
            if crs not in self.locations_by_crs
        )
        if absent and not self.report.reviewed_codes_absent:
            # Recorded once, and in its own channel. This pass runs again as
            # each classification source lands, and the set of absent codes
            # cannot change between runs -- the stations were all read with
            # the feed -- so a note per pass would print the same thing three
            # times. It is not a skipped file either: nothing was left unread
            # here, a reviewed list is naming a station the feed does not
            # carry, and reporting it as an unopened source would be a lie
            # that also hid it among the archive-inside-an-archive notes.
            # --require-live-reviewed-codes turns it into a refusal.
            self.report.reviewed_codes_absent = absent
        # The other way a reviewed entry goes stale: the code names a real
        # station, so nothing about it looks wrong, but the workbook already
        # names that station, so the entry is a fallback for a station nothing
        # was missing. It applies to nothing today and would apply the day the
        # name match missed -- Knighton as a city, Windermere as a city, York
        # as a town. The rule a fallback exists to serve is that it covers a
        # station no source could name, so it is checked against the workbook
        # rather than left to a reader to notice.
        redundant = sorted(
            crs
            for crs in set(LONDON_STATION_CRS)
            | set(MAJOR_UK_STATION_FALLBACKS)
            | set(REVIEWED_SETTLEMENT_FALLBACKS)
            if crs in self.ons_classified_crs
        )
        if redundant and not self.report.reviewed_codes_redundant:
            self.report.reviewed_codes_redundant = redundant

    def _load_location_types_json(self, data: object) -> None:
        # A cache written under an older schema still holds valid facets, but
        # its primary classes were written by a different set of rules and would
        # be served forever. Drop those records and say so; keeping the facets
        # costs nothing because they are additive. A file whose classes were
        # dropped speaks for no provenance either: its facets are still true,
        # its labels are not.
        discarded = False
        if isinstance(data, dict) and isinstance(data.get("schema"), int):
            if data["schema"] < LOCATION_CACHE_SCHEMA and isinstance(data.get("records"), dict):
                heritage_note = ""
                if data["schema"] < 6:
                    # Schema 6 introduced the hybrid closest-station prune.
                    # Cached heritage chips can still name Buxton for Bath, so
                    # heritage is stripped here and re-applied by the live reader.
                    heritage_note = "; heritage facets discarded for closest-station prune"
                    data = self._without_cached_heritage_facets(data)
                self.report.skip_file(
                    f"station classification cache is schema {data['schema']}, this build writes "
                    f"schema {LOCATION_CACHE_SCHEMA}: its primary classes were ignored, its facets kept"
                    f"{heritage_note}"
                )
                # Keep the facets, which are additive and still true, and drop
                # only the primary class each record carried.
                data = {
                    **data,
                    "records": {
                        crs: {**value, "primary": None} if isinstance(value, dict) else None
                        for crs, value in data["records"].items()
                    },
                }
                # The file's own label described the classes just dropped, so
                # the label is dropped with them. Recording it would publish a
                # provenance for classes this build does not have, and -- while
                # the label was a single slot the pass cleared itself -- it also
                # told the pass above that the workbook had already been
                # applied, so the workbook was not read and every station the
                # cache had classified fell through to the reviewed fallbacks:
                # on the 24 September 2026 download, 3,119 of 3,436 stations
                # lost their class that way.
                discarded = True
        if isinstance(data, dict):
            top_level_facets = data.get("facets")
            if isinstance(top_level_facets, dict):
                for crs, value in top_level_facets.items():
                    self._merge_location_facets(crs, value)
            nested = data.get("records")
            if isinstance(nested, dict):
                if not discarded:
                    # A cache this build wrote names every source its classes
                    # came from; a file from elsewhere names the one it claims,
                    # and a file that names none records none. The list is read
                    # rather than the joined string, so a label that contains
                    # the joiner cannot be split back wrongly.
                    recorded = data.get("provenance")
                    if isinstance(recorded, (list, tuple)) and recorded:
                        for label in recorded:
                            self._record_location_source(label)
                    else:
                        self._record_location_source(data.get("source") or data.get("sourceName"))
                for crs, value in nested.items():
                    code = str(crs).strip().upper()
                    raw_facets: object = ()
                    raw_kind: object = value
                    if isinstance(value, dict):
                        raw_kind = value.get("primary", value.get("type"))
                        raw_facets = value.get("facets", ())
                    kind = self._normalise_location_type(raw_kind)
                    if code and kind:
                        self.location_types_by_crs[code] = kind
                    self._merge_location_facets(crs, raw_facets)
                return
        records = data.get("records") if isinstance(data, dict) else data
        if not isinstance(records, (list, tuple)):
            return
        for record in records:
            if not isinstance(record, dict):
                continue
            crs = next((record.get(key) for key in ("crs", "CRS", "crsCode", "locationCode") if record.get(key)), None)
            kind = next((record.get(key) for key in ("type", "classification", "locationType", "LocationClassification") if record.get(key)), None)
            kind = self._normalise_location_type(kind)
            if crs and kind:
                code = str(crs).strip().upper()
                self.location_types_by_crs[code] = kind
                self._merge_location_facets(crs, record.get("facets"))

    def _tag_station(self, crs: str, facet_key: str) -> None:
        self.location_facets_by_crs.setdefault(crs, set()).add(facet_key)

    @staticmethod
    def _without_cached_heritage_facets(data: dict) -> dict:
        """Drop heritage chips from a pre-prune cache so the live reader retags."""

        def strip(value: object) -> object:
            if isinstance(value, list):
                return [facet for facet in value if facet != "heritage"]
            if isinstance(value, set):
                return {facet for facet in value if facet != "heritage"}
            if isinstance(value, dict):
                return {
                    key: strip(item) if key == "facets" else item
                    for key, item in value.items()
                }
            return value

        cleaned = dict(data)
        if isinstance(cleaned.get("facets"), dict):
            cleaned["facets"] = {
                crs: strip(facets) for crs, facets in cleaned["facets"].items()
            }
        if isinstance(cleaned.get("records"), dict):
            cleaned["records"] = {
                crs: strip(record) for crs, record in cleaned["records"].items()
            }
        return cleaned

    def _merge_location_facets(self, crs: object, value: object) -> None:
        """Add a station's facets to what is already known about it.

        More than one file can describe the same station, and each may know a
        facet the others do not. Merging keeps a stale cache beside the feed
        from deleting a facet the checked-in reference data recorded.
        """
        code = str(crs).strip().upper()
        facets = self._normalise_location_facets(value)
        if code and facets:
            self.location_facets_by_crs.setdefault(code, set()).update(facets)

    @staticmethod
    def _normalise_location_facets(value: object) -> set[str]:
        if isinstance(value, str):
            value = (value,)
        if not isinstance(value, (list, tuple, set, frozenset)):
            return set()
        return {
            facet
            for item in value
            if (facet := str(item).strip().lower()) in SUPPORTED_DESTINATION_FACETS
        }

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

    @staticmethod
    def _normalise_settlement_name(value: object) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

    @classmethod
    def _settlement_name_candidates(cls, name: object) -> list[str]:
        """Return the station name and, for a qualifier, the settlement under it.

        The feed disambiguates with a bracketed county -- "Ascot (Berks)" --
        where the ONS workbook simply says "Ascot". Dropping a trailing
        bracketed qualifier is safe in a way that dropping any other word is
        not, because a county never changes which settlement a station is in.
        """
        text = str(name or "").strip()
        candidates = [cls._normalise_settlement_name(text)]
        bracketed = re.match(r"^(.*?)\s*\([^)]*\)\s*$", text)
        if bracketed and bracketed.group(1).strip():
            candidates.append(cls._normalise_settlement_name(bracketed.group(1)))
        return [candidate for candidate in candidates if candidate]

    def _settlement_matches(self, name: object, settlements: set[str]) -> bool:
        """Say whether a station's name is one of a source's settlements.

        Only the whole name matches. Loosening this to "starts with" is what
        would make Bathgate claim Bath and Bradford-on-Avon claim Bradford, so
        a curated list names stations as the feed writes them instead.
        """
        return any(candidate in settlements for candidate in self._settlement_name_candidates(name))

    @staticmethod
    def _xlsx_cell_value(cell: ET.Element, shared: list[str]) -> str:
        cell_type = cell.attrib.get("t", "")
        if cell_type == "inlineStr":
            return "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
        value = next((node.text or "" for node in cell if node.tag.endswith("}v")), "")
        if cell_type == "s" and value.isdigit():
            return shared[int(value)]
        return value

    def _read_ons_built_up_areas(self, data: bytes) -> dict[str, dict[str, str]]:
        """Read ONS table 1c/1d using only the standard library.

        The workbook's row shape is stable: F is the BUA name and G its size
        band. Reading only those two cells avoids pinning a spreadsheet library
        into this otherwise self-contained project.
        """
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
                    for item in root
                    if item.tag.endswith("}si")
                ]

            found: list[tuple[str, str]] = []
            for name in archive.namelist():
                if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                    continue
                root = ET.fromstring(archive.read(name))
                for row in root.iter():
                    if not row.tag.endswith("}row"):
                        continue
                    values = {
                        cell.attrib.get("r", "").rstrip("0123456789"):
                        self._xlsx_cell_value(cell, shared)
                        for cell in row
                        if cell.tag.endswith("}c")
                    }
                    band = values.get("G", "").strip().lower()
                    settlement = values.get("F", "").strip()
                    if settlement and band in LOCATION_BAND_TYPES:
                        found.append((settlement, band))
            return self._key_settlements(found)

    @classmethod
    def _key_settlements(cls, rows) -> dict[str, dict[str, str]]:
        """Index workbook settlements by the name a station would carry.

        The workbook writes a settlement with its district in brackets
        ("Watford (Watford)", "Neston (Cheshire West and Chester)"), and the
        station side has always dropped its own bracketed qualifier. Keying only
        the full name kept the two sides from meeting, which left priced
        destinations unclassified for no reason but the bracket (ADR-0026).
        Two settlements of one name whose bands differ are kept and marked
        unusable: which of them a station serves is not
        knowable from the name, so the station stays unclassified rather than
        being given a class that may belong to the other one.
        """
        bands: dict[str, dict[str, str]] = {}
        for settlement, band in rows:
            for key in cls._settlement_name_candidates(settlement):
                existing = bands.get(key)
                if existing is None:
                    bands[key] = {
                        "name": settlement,
                        "type": LOCATION_BAND_TYPES[band],
                        "band": band,
                    }
                elif existing["band"] != band:
                    bands[key] = {"name": settlement, "type": None, "band": ""}
        if not bands:
            raise ValueError("ONS workbook contains no built-up-area size bands")
        return bands

    def _load_ons_location_types(self) -> None:
        request = urllib.request.Request(
            ONS_BUILT_UP_AREAS_FILE_URL,
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            workbook = response.read()
        areas = self._read_ons_built_up_areas(workbook)
        for crs, location in self.locations_by_crs.items():
            if not crs or not location.name:
                continue
            for candidate in self._settlement_name_candidates(location.name):
                area = areas.get(candidate)
                # A refused key carries no class: the workbook holds two
                # settlements of this name with different bands, so the station
                # keeps the report's attention instead of a guessed class.
                if area and area["type"]:
                    self.location_types_by_crs[crs] = area["type"]
                    # Which stations the workbook names, kept because it is the
                    # only way to tell a reviewed *fallback* from a reviewed
                    # entry that can never apply: a fallback exists for the
                    # stations no source could name.
                    self.ons_classified_crs.add(crs)
                    break
        self._apply_major_station_fallbacks()
        if self.ons_classified_crs:
            # The workbook classified at least one station of this feed, so it
            # is named as a source. A workbook that matched nothing is not: its
            # label would describe classes it never supplied.
            self._record_location_source(LOCATION_TYPE_SOURCE)

    def _read_ons_coastal_areas(self, data: bytes) -> set[str]:
        """Read the 568 ONS coastal BUA names from table 1d."""
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
                    for item in root
                    if item.tag.endswith("}si")
                ]
            names: set[str] = set()
            for name in archive.namelist():
                if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                    continue
                root = ET.fromstring(archive.read(name))
                in_coastal_bua_table = False
                for row in root.iter():
                    if not row.tag.endswith("}row"):
                        continue
                    values = {
                        cell.attrib.get("r", "").rstrip("0123456789"):
                        self._xlsx_cell_value(cell, shared)
                        for cell in row
                        if cell.tag.endswith("}c")
                    }
                    if (
                        values.get("D", "").strip() == "BUA size classification"
                        and values.get("F", "").strip() == "BUA name"
                    ):
                        in_coastal_bua_table = True
                        continue
                    if not in_coastal_bua_table:
                        continue
                    if values.get("A", "").strip().lower() != "coastal":
                        continue
                    settlement = self._normalise_settlement_name(values.get("F", ""))
                    if settlement:
                        names.add(settlement)
            if not names:
                raise ValueError("ONS coastal workbook contains no coastal built-up areas")
            return names

    def _read_ons_coastal_facet(self) -> set[str]:
        """Return the coastal built-up-area names the ONS workbook lists."""
        request = urllib.request.Request(
            ONS_COASTAL_BUILT_UP_AREAS_FILE_URL,
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            workbook = response.read()
        return self._read_ons_coastal_areas(workbook)

    def _read_unesco_heritage_facet(self) -> set[str]:
        """Return station names for the UK properties the curated list names.

        The list is validated against UNESCO's own XML on every read: an id
        that is no longer a current UK property stops contributing, so a
        delisted site cannot keep tagging destinations. Surviving curated
        names are then pruned to the nearest station (or soft twin) for each
        attraction point so a distant namesake cannot keep the chip.
        """
        request = urllib.request.Request(
            UNESCO_WORLD_HERITAGE_FILE_URL,
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        root = ET.fromstring(body)
        current: set[int] = set()
        for row in root:
            if row.tag.rsplit("}", 1)[-1] != "row":
                continue
            fields = {
                child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in row
            }
            if "united kingdom" not in fields.get("states", "").lower():
                continue
            try:
                current.add(int(fields.get("id_number", "")))
            except ValueError:
                continue
        names: set[str] = set()
        for site_id, stations in HERITAGE_STATIONS_BY_SITE.items():
            if site_id not in current:
                self.report.skip_file(
                    f"heritage: curated site {site_id} is not a current UK World Heritage "
                    "property; its stations were not applied"
                )
                continue
            for crs in self._pruned_heritage_crs(site_id, stations):
                location = self.locations_by_crs.get(crs)
                if location is None:
                    continue
                names.add(self._normalise_settlement_name(location.name))
                # Keep the curated token too when the feed name is a longer
                # form (Bradford Forster Square vs Bradford F Sq), so the
                # later settlement match still finds the station.
                for station in stations:
                    if self._settlement_matches(
                        location.name, {self._normalise_settlement_name(station)}
                    ):
                        names.add(self._normalise_settlement_name(station))
            # Tokens that match no feed station stay in the set so the apply
            # path can report a stale curated list. Distance-pruned stations
            # that do exist in the feed are omitted on purpose.
            for station in stations:
                token = self._normalise_settlement_name(station)
                if not any(
                    self._settlement_matches(location.name, {token})
                    for location in self.locations_by_crs.values()
                ):
                    names.add(token)
        if not names:
            raise ValueError("no curated World Heritage site is a current UK property")
        return names

    def _read_learning_provider_facet(self) -> set[str]:
        """Return the towns that have a university in the UKPRN provider list.

        The file is a tab-separated table whose TOWN column is the settlement
        the provider is in. Reading it by column name rather than position
        keeps a re-ordered file from silently moving the wrong column into the
        facet.
        """
        request = urllib.request.Request(
            LEARNING_PROVIDERS_FILE_URL,
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode("utf-8-sig", errors="replace")
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("learning provider list is empty")
        header = [column.strip().upper() for column in lines[0].split("\t")]
        if "TOWN" not in header:
            raise ValueError("learning provider list has no TOWN column")
        town = header.index("TOWN")
        names: set[str] = set()
        for line in lines[1:]:
            columns = line.split("\t")
            if len(columns) <= town:
                continue
            if (settle := self._normalise_settlement_name(columns[town])):
                names.add(settle)
        return names

    def _write_location_cache(self, path: Path) -> None:
        cache = {
            # The schema number is the constant, not a second copy of it: when
            # it was written here as a literal, the reader moved to 4 and the
            # writer kept saying 3, so every build wrote a cache whose classes
            # the next build was required to discard and re-derive from the
            # workbook. The cache was a cache that never once did its job.
            #
            # 3: the primary classes split into city/town/small_town/village,
            # so a cache written under 2 would call every village and small
            # town "other" forever.
            # 4: the reviewed settlement classes were corrected against the
            # feed's own station names, so a cache written under 3 holds
            # classes the current lists would not produce and is discarded
            # rather than served.
            # 6: hybrid closest-station prune for World Heritage, so a cache
            # written under 5 can still chip Buxton for Bath; those files are
            # ignored rather than partially reused.
            "schema": LOCATION_CACHE_SCHEMA,
            # Every source the classes came from, in the order they were read,
            # and the joined form beside it for a reader from before the list
            # existed. Both are read back through the loader's own recorder.
            "source": self.location_type_source or "",
            "provenance": list(self.location_type_sources),
            "sources": {
                "primary": {
                    "name": "Office for National Statistics, Census 2021 built-up-area size bands",
                    "url": ONS_BUILT_UP_AREAS_DATASET_URL,
                },
            },
            "facetSources": {
                facet.key: {
                    "name": facet.source,
                    "url": facet.url,
                    "coverage": facet.coverage,
                }
                for facet in DESTINATION_FACET_SOURCES
            },
            "mapping": {
                type_name: [
                    band for band, kind in LOCATION_BAND_TYPES.items() if kind == type_name
                ]
                for type_name in ("city", "town", "small_town", "village")
            },
            "supportedFacets": sorted(SUPPORTED_DESTINATION_FACETS),
            "coverage": (
                "ONS Census 2021 BUA and coastal-classification matches, then reviewed "
                "major-station fallbacks for London and UK areas outside the workbooks"
            ),
            "fallbackSource": LOCATION_FALLBACK_SOURCE,
            "fallbackLondonStations": sorted(LONDON_STATION_CRS),
            "fallbackOtherStations": dict(sorted(MAJOR_UK_STATION_FALLBACKS.items())),
            "records": dict(sorted(self.location_types_by_crs.items())),
            "facets": {
                crs: sorted(facets)
                for crs, facets in sorted(self.location_facets_by_crs.items())
                if facets
            },
        }
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _load_lines(
        self, name: str, lines, only: frozenset[str] | None = None
    ) -> None:
        """Read one feed file, or only the suffixes ``only`` names.

        A skipped file is not reported as unreadable: the caller said which
        files it wanted, so the rest are not a gap in the download.
        """
        extension = Path(name).suffix.lower().lstrip(".")
        if only is not None and extension not in only:
            return
        # The optional station classification lookup lives beside the fares
        # files and is read after the feed stream. It is still a known input,
        # not an unreadable file that should pollute the damage audit.
        if extension == "json":
            self.report.files_read.append(name)
            return
        loader = {
            "ffl": self._load_flows,
            "fsc": self._load_station_clusters,
            "loc": self._load_locations,
            "tty": self._load_ticket_types,
            "rlc": self._load_railcards,
            "rcm": self._load_minimum_fares,
            "dis": self._load_status_discounts,
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
        if extension != "rst":
            # Every DTD fares file opens with ``/!! Start of file`` and may close
            # with a ``/!!`` trailer such as ``/!! Records: 3316``; a line that
            # starts with ``/`` is a comment, never a record. The restrictions
            # reader already skips them itself (atoc_restrictions.load_line).
            # Without this the .RCM trailer was rejected as a bad date, and the
            # .RLC reader took a comment's first columns for a railcard code.
            lines = (line for line in lines if not line.startswith("/"))
        count(lines, loader, self.report, name)

    def _flow_index_nlcs(self, flow: Flow) -> tuple[str, ...]:
        if flow.direction == "R" and flow.destination_nlc != flow.origin_nlc:
            return (flow.origin_nlc, flow.destination_nlc)
        return (flow.origin_nlc,)

    def _index_flow(self, flow: Flow) -> None:
        for nlc in self._flow_index_nlcs(flow):
            self.flows_touching_nlc.setdefault(nlc, []).append(flow)

    def _unindex_flow(self, flow: Flow) -> None:
        for nlc in self._flow_index_nlcs(flow):
            flows = self.flows_touching_nlc.get(nlc)
            if flows is not None and flow in flows:
                flows.remove(flow)
                if not flows:
                    self.flows_touching_nlc.pop(nlc, None)

    def _load_flows(self, line: str) -> None:
        # Direct slices rather than _text per field: this reader sees every FFL
        # line in the feed, so its per-field call overhead is the parse's cost
        # centre (audit B2).
        f = FLOW_F_SLICES
        t = FLOW_T_SLICES
        record_type = line[f["record_type"]].strip().upper()
        if record_type == "F":
            _require_width(line, FLOW_F_WIDTH, "flow")
            marker = line[f["update_marker"]].strip().upper()
            flow_id = line[f["flow_id"]].strip()
            previous = self.flows.get(flow_id)
            if previous is not None:
                self._unindex_flow(previous)
            if marker == "D":
                self.flows.pop(flow_id, None)
                self.fares_by_flow.pop(flow_id, None)
                return
            flow = Flow(
                flow_id=flow_id,
                origin_nlc=line[f["origin_nlc"]].strip(),
                destination_nlc=line[f["destination_nlc"]].strip(),
                route_code=line[f["route_code"]].strip(),
                direction=line[f["direction"]].strip().upper(),
                start_date=_parse_dtd_date(line[f["start_date"]].strip()),
                end_date=_parse_dtd_date(line[f["end_date"]].strip()),
            )
            self.flows[flow_id] = flow
            self._index_flow(flow)
        elif record_type == "T":
            _require_width(line, FLOW_T_WIDTH, "fare")
            marker = line[t["update_marker"]].strip().upper()
            flow_id = line[t["flow_id"]].strip()
            ticket_code = line[t["ticket_code"]].strip()
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
            fare_text = line[t["fare_pence"]].strip()
            if not fare_text.isdigit():
                # Raise rather than count here: the line counter decides once
                # whether a line was parsed or rejected, and counting it in both
                # places makes a rejected record look handled, with no example.
                raise ValueError(f"fare {fare_text!r} is not a number")
            bucket[ticket_code] = Fare(
                ticket_code=ticket_code,
                pence=int(fare_text),
                restriction_code=line[t["restriction_code"]].strip(),
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

    def _load_station_clusters(self, line: str) -> None:
        _require_width(line, STATION_CLUSTER_WIDTH, "station cluster")
        slices = STATION_CLUSTER_SLICES
        marker = line[slices["update_marker"]].strip().upper()
        cluster_id = line[slices["cluster_id"]].strip()
        member_nlc = line[slices["cluster_nlc"]].strip()
        if not cluster_id or not member_nlc:
            return
        end_date = _parse_dtd_date(line[slices["end_date"]].strip())
        bucket = self.station_clusters.get(cluster_id)
        if marker == "D":
            if bucket:
                kept = [
                    row
                    for row in bucket
                    if not (row.member_nlc == member_nlc and row.end_date == end_date)
                ]
                if kept:
                    self.station_clusters[cluster_id] = kept
                else:
                    del self.station_clusters[cluster_id]
            return
        member = StationClusterMember(
            member_nlc=member_nlc,
            start_date=_parse_dtd_date(line[slices["start_date"]].strip()),
            end_date=end_date,
        )
        if bucket is None:
            self.station_clusters[cluster_id] = [member]
        else:
            for index, existing in enumerate(bucket):
                if existing.member_nlc == member_nlc and existing.end_date == end_date:
                    bucket[index] = member
                    return
            bucket.append(member)

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
            restricted_by_train=dtd_flag(
                _text(line, TICKET_TYPE_OFFSETS, "restricted_by_train")
            ),
            discount_category=_text(line, TICKET_TYPE_OFFSETS, "discount_category"),
            min_passengers=_as_int(_text(line, TICKET_TYPE_OFFSETS, "min_passengers")),
            min_adults=_as_int(_text(line, TICKET_TYPE_OFFSETS, "min_adults")),
            max_adults=_count_or_none(_text(line, TICKET_TYPE_OFFSETS, "max_adults")),
            min_children=_as_int(_text(line, TICKET_TYPE_OFFSETS, "min_children")),
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
            adult_status=_text(line, RAILCARD_OFFSETS, "adult_status"),
        )

    def _load_status_discounts(self, line: str) -> None:
        # The file's S records describe a status; only D records carry a
        # discount, and only those are read.
        if _text(line, STATUS_DISCOUNT_OFFSETS, "record_type").upper() != "D":
            return
        status = _text(line, STATUS_DISCOUNT_OFFSETS, "status_code")
        category = _text(line, STATUS_DISCOUNT_OFFSETS, "discount_category")
        if not status or not category:
            return
        indicator = _text(line, STATUS_DISCOUNT_OFFSETS, "discount_indicator").upper()
        tenths = _as_int(_text(line, STATUS_DISCOUNT_OFFSETS, "discount_tenths"))
        self.status_discounts.setdefault((status, category), []).append(
            StatusDiscount(
                end_date=_parse_dtd_date(_text(line, STATUS_DISCOUNT_OFFSETS, "end_date")),
                discount=Fraction(tenths, 1000) if indicator == "0" else None,
            )
        )

    def _load_minimum_fares(self, line: str) -> None:
        railcard_code = _text(line, MINIMUM_FARE_OFFSETS, "railcard_code")
        ticket_code = _text(line, MINIMUM_FARE_OFFSETS, "ticket_code")
        pence = _as_int(_text(line, MINIMUM_FARE_OFFSETS, "minimum_fare_pence"))
        if not railcard_code or not ticket_code or pence <= 0:
            return
        record = MinimumFare(
            pence=pence,
            start_date=_parse_dtd_date(_text(line, MINIMUM_FARE_OFFSETS, "start_date")),
            end_date=_parse_dtd_date(_text(line, MINIMUM_FARE_OFFSETS, "end_date")),
        )
        windows = self.minimum_fares.setdefault((railcard_code, ticket_code), [])
        for index, existing in enumerate(windows):
            if (existing.start_date, existing.end_date) == (
                record.start_date,
                record.end_date,
            ):
                # A re-issue of one window replaces it, rather than stacking a
                # second price on a window that can hold one.
                windows[index] = record
                return
        windows.append(record)

    def _load_restrictions(self, line: str) -> None:
        self.restrictions.load_line(line)
