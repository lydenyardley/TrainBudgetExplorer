"""The loaded fares database and the queries asked of it.

`FaresDb` mixes the feed readers of `atoc_fares_loader.py` into the budget query,
the publishable selector and the destination classification. The feed's record
layouts and row types are declared in `atoc_fare_declarations.py`, and this module
imports them for its own use and re-exports the ones other modules already took
from here, so the split moved where the declarations live and not what a caller
imports them from.

Fares are per person. A party buys one ticket per adult unless the ticket type
says otherwise, so a party price is adults x per-adult."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from fractions import Fraction
from functools import partial
import os
from pathlib import Path
import pickle

from atoc_restrictions import RailcardRestrictionRow, RestrictionIndex
from atoc_fares_loader import LOCATION_FILE_SUFFIXES, FaresLoader
from parse_report import ParseReport, read_feed_files

from atoc_fare_declarations import (
    ADVANCE_REASON,
    ADVANCE_RESTRICTION_CODES,
    COASTAL_SITE_PROOFS,
    CONDITIONAL_REASON,
    CONDITIONAL_TICKET_CODES,
    DEFAULT_STATIONS_XML,
    DESTINATION_FACETS_FILE,
    DESTINATION_FACET_READERS,
    DESTINATION_FACET_SOURCES,
    DESTINATION_TYPE_FILTERS,
    DestinationFacet,
    FARE_CONSTRUCTION_CRS,
    FARE_CONSTRUCTION_NAME_MARKERS,
    FLOW_F,
    FLOW_F_SLICES,
    FLOW_F_WIDTH,
    FLOW_T,
    FLOW_T_SLICES,
    FLOW_T_WIDTH,
    Fare,
    Flow,
    HERITAGE_PROPERTIES,
    HERITAGE_SITE_POINTS,
    HERITAGE_STATIONS_BY_SITE,
    LEARNING_PROVIDERS_FILE_URL,
    LOCATION,
    LOCATION_BAND_TYPES,
    LOCATION_CACHE_SCHEMA,
    LOCATION_FALLBACK_SOURCE,
    LOCATION_OFFSETS,
    LOCATION_TYPES_FILE,
    LOCATION_TYPE_SOURCE,
    LONDON_STATION_CRS,
    Location,
    MAJOR_UK_STATION_FALLBACKS,
    MINIMUM_FARE,
    MINIMUM_FARE_OFFSETS,
    MinimumFare,
    NATIONAL_PARK_GATEWAYS,
    NATIONAL_TRUST_PROPERTIES,
    NATURE_SITE_PROOFS,
    NATURE_SITE_STATION_CRS,
    ONS_BUILT_UP_AREAS_DATASET_URL,
    ONS_BUILT_UP_AREAS_FILE_URL,
    ONS_COASTAL_BUILT_UP_AREAS_FILE_URL,
    PLACEHOLDER_TICKET_CODES,
    SENTINEL_FARE_PENCE,
    RAILCARD,
    RAILCARD_DISCOUNT,
    RAILCARD_OFFSETS,
    REVIEWED_ANYTIME_DAY_RETURN_TICKETS,
    REVIEWED_ATTRACTIONS_BY_FACET,
    REVIEWED_PUBLIC_RAILCARDS,
    REVIEWED_SETTLEMENT_FALLBACKS,
    ROUNDING_STEP_PENCE,
    RSPB_RESERVES,
    Railcard,
    RailcardFamily,
    Reachable,
    StatusDiscount,
    ReviewedAttraction,
    SEASIDE_SUPPLEMENT_CRS,
    STATION_CLUSTER,
    STATION_CLUSTER_OFFSETS,
    STATION_CLUSTER_SLICES,
    STATION_CLUSTER_WIDTH,
    SUPPORTED_DESTINATION_FACETS,
    StationClusterMember,
    TICKET_TYPE,
    TICKET_TYPE_OFFSETS,
    TicketType,
    TwoPartFare,
    UNEXPANDED_FARE_GROUPS,
    UNESCO_WORLD_HERITAGE_FILE_URL,
    _adult_bounds,
    _as_int,
    _parse_dtd_date,
    _require_width,
    _round_down_to,
    _tally,
    _text,
    classification_files,
    dtd_flag,
    format_pence,
    haversine_km,
    is_advance_ticket,
    is_not_for_public_sale,
    is_pseudo_station,
    load_station_coordinates,
    location_lookup_candidates,
    looks_like_fare_construction,
    seaside_crs_missing_coastal_proofs,
    select_nearest_stations,)

# The budget that means no budget, for the queries that ask "everything this
# origin can reach" rather than "what is inside ten pounds". It lives beside
# those queries because it is a bound on them: the caches, the provenance pass,
# the page builder and the coverage report all ask the same question, and four
# copies of the sentinel was four places for it to drift apart.
EVERYTHING_PENCE = 1_000_000


class FaresDb(FaresLoader):
    """Indexes the feed files that budget discovery reads."""

    def __init__(self) -> None:
        self.locations_by_nlc: dict[str, Location] = {}
        self.locations_by_crs: dict[str, Location] = {}
        # Destination settlement type is reference data, not a fares LOC field.
        # A reviewed JSON cache beside the feed is preferred; a real DTD build
        # can populate it from the ONS Census built-up-area source.
        self.location_types_by_crs: dict[str, str] = {}
        self.location_facets_by_crs: dict[str, set[str]] = {}
        # CRS -> (lat, lon) from Knowledgebase stations.xml, loaded lazily when
        # a heritage (or multi-CRS nature) prune needs it.
        self._station_coordinates: dict[str, tuple[float, float]] | None = None
        self._station_coordinates_path: Path | None = None
        # Reviewed attraction -> the CRS codes the prune kept, per facet. Built
        # lazily because a page asks for a destination's proof once per row and
        # a whole-network build asks for thousands: without this the prune would
        # be recomputed for every attraction on every row.
        self._attraction_crs_cache: dict[str, dict[str, frozenset[str]]] = {}
        self._heritage_crs_cache: tuple[object, dict[int, frozenset[str]]] | None = None
        self._nature_crs_cache: tuple[object, dict[tuple[str, str], frozenset[str]]] | None = None
        # Every source whose classes this database carries, in load order. One
        # slot made the provenance line the last writer's: a cache beside the
        # feed described classes the ONS workbook had supplied, and the reviewed
        # London, Scottish, Welsh and Northern Irish fallbacks were published as
        # the workbook's own work. Read through the property below.
        self.location_type_sources: list[str] = []
        # One station code can hold several location codes, and a real feed does
        # this for most towns. Flows are keyed by location code, so a query has
        # to consider all of them or it misses fares that are right there.
        self.nlcs_by_crs: dict[str, set[str]] = {}
        # Keyed by cluster_id (RSPS5045 §4.2). One cluster holds a list of
        # date-bounded member records, and a member code may be a station NLC or
        # a fare-group NLC.
        self.station_clusters: dict[str, list[StationClusterMember]] = {}
        self.ticket_types: dict[str, TicketType] = {}
        self.railcards: dict[str, Railcard] = {}
        self.flows: dict[str, Flow] = {}
        self.fares_by_flow: dict[str, dict[str, Fare]] = {}
        # Flows grouped by every NLC that touches them: most are usable only
        # from their recorded origin, but a reversible (``direction == "R"``)
        # flow is indexed under both endpoints, so a bucket can hold inbound
        # flows too. The query loop swaps the recorded destination when it
        # entered via the far side (audit A4). destinations_within asks the
        # same question per origin; scanning every flow for each origin would
        # turn a full-network build into 2,500 full scans.
        self.flows_touching_nlc: dict[str, list[Flow]] = {}
        # Keyed by (railcard code, ticket code). A key holds a list, because
        # the catalogue writes one record per validity window rather than one
        # per key: in the 24 September 2026 download 613 of 639 keys carried
        # more than one window, 3,355 records in all.
        self.minimum_fares: dict[tuple[str, str], list[MinimumFare]] = {}
        # Keyed by (status code, discount category), the DIS file's own key. A
        # key can hold several windows, so the record covering the day is read.
        self.status_discounts: dict[tuple[str, str], list[StatusDiscount]] = {}
        self.restrictions = RestrictionIndex()
        self.report = ParseReport()
        self.files_read = self.report.files_read
        # A single-origin build only needs fares queryable from that origin.
        # Reversible flows count in both directions. The national feed has
        # millions of unrelated fare records, so retaining
        # every Fare object makes the local app spend most of its time building
        # prices it will never query. This is None for the normal/full database.
        self._focus_origin_nlcs: set[str] | None = None
        # The stations the ONS workbook itself named, kept so the reviewed
        # fallbacks can be checked against the rule they exist to serve: each
        # one must be a station no source could name.
        self.ons_classified_crs: set[str] = set()
        # Focus caches are named by the feed and origin, but keep the identity
        # inside the object too so a hand-reused path cannot silently return a
        # different origin's fares.
        self._cache_origin: str | None = None
        # The whole feed's stats(), recorded when the shared half of a fare
        # index is written. An index database holds only one origin's flows,
        # so recomputing stats() from it would report a slice as the feed
        # (audit B1): every page built through the indexes answers with the
        # same national numbers the full load would have given.
        self.feed_stats: dict[str, int] | None = None

    @property
    def location_type_source(self) -> str | None:
        """Name every source whose classes this database carries, in load order.

        A source is recorded when it classified part of this feed, and the page
        joins them: with a cache beside the feed, the reviewed fallbacks are a
        source in their own right rather than the workbook's unwritten work.
        """
        recorded = getattr(self, "location_type_sources", ())
        if recorded:
            # The reviewed fallback label is the floor under the sourced classes,
            # so it is named last: "the workbook, plus the reviewed fallbacks for
            # the areas it does not cover" is how the coverage reads. The stable
            # sort keeps every other label in the order it was loaded.
            return " + ".join(
                sorted(recorded, key=lambda label: label == LOCATION_FALLBACK_SOURCE)
            )
        # A database unpickled from a fare-index cache written before the labels
        # were accumulated keeps its one label in the instance dictionary, where
        # this property shadows it. Read that back rather than report no source
        # for classes that have one.
        return str(self.__dict__.get("location_type_source") or "") or None

    def load_feed(
        self,
        path: str | Path,
        *,
        focus_origin: str | None = None,
        cache_path: str | Path | None = None,
        locations_only: bool = False,
    ) -> "FaresDb":
        """Load a feed, optionally retaining fares for one origin only.

        ``focus_origin`` is for a one-origin page build. It is deliberately not
        used by audit or multi-origin builds, whose results must describe the
        whole feed. When ``cache_path`` is supplied, a focused database is
        persisted atomically and reused on later page builds. The cache is
        opt-in so audit and general analysis retain their complete-feed
        semantics.

        ``locations_only`` reads the station list and nothing else, for a caller
        whose only question is which origins this feed names (the shard merge,
        E6). The database it returns keeps no fares, so focusing or caching one
        is refused rather than silently ignored.
        """
        origin = focus_origin.strip().upper() if focus_origin is not None else None
        if locations_only:
            if origin is not None or cache_path is not None:
                raise ValueError(
                    "a locations-only load keeps no fares, so it cannot be "
                    "focused or cached"
                )
            read_feed_files(
                path,
                self.report,
                partial(self._load_lines, only=LOCATION_FILE_SUFFIXES),
            )
            return self
        if cache_path is not None and origin is not None:
            cache = Path(cache_path)
            if cache.is_file():
                try:
                    with cache.open("rb") as handle:
                        loaded = pickle.load(handle)
                    if (
                        isinstance(loaded, FaresDb)
                        and loaded._cache_origin == origin
                    ):
                        return loaded
                except (OSError, EOFError, pickle.PickleError, AttributeError, TypeError):
                    pass

        if focus_origin is not None:
            self._focus_origin_nlcs = set()
            self._preload_focus_locations(path, origin)
        self._flow_eval_caches = None
        self._dest_nlc_cache = None
        read_feed_files(path, self.report, self._load_lines)
        if focus_origin is not None:
            self._load_interchange_fares(path, origin)
        self._load_location_lookup(path)
        if cache_path is not None and focus_origin is not None:
            self._cache_origin = origin
            cache = Path(cache_path)
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_name(
                f"{cache.name}.{os.getpid()}.tmp"
            )
            with temporary.open("wb") as handle:
                pickle.dump(self, handle, protocol=pickle.HIGHEST_PROTOCOL)
            temporary.replace(cache)
        return self

    def interchange_crs(self, origin_crs: str) -> set[str]:
        """Every named station a direct or fare-group flow out of the origin reaches.

        These are the stations a two-part price can change at (ADR-0061): the
        first ticket is a fare from the origin, so the change station is one
        the origin's own flows name. Read from the flow records, which a
        focused load keeps whole, so the answer is the same before and after
        the fares themselves have been narrowed to one origin. Kept on the
        station's own and fare-group flows so a single-origin load does not
        pull in every station reached by a regional cluster.
        """
        origin = self.locations_by_crs.get(origin_crs.strip().upper())
        if origin is None:
            return set()
        found: set[str] = set()
        for origin_nlc in self._direct_fare_nlcs(origin.crs):
            for flow in self.flows_touching_nlc.get(origin_nlc, ()):
                other = (
                    flow.origin_nlc
                    if flow.direction == "R" and flow.destination_nlc == origin_nlc
                    else flow.destination_nlc
                )
                for location in self._direct_stations_for_fare_nlc(other):
                    if location.crs == origin.crs or is_pseudo_station(location.crs):
                        continue
                    found.add(location.crs)
        return found

    def _direct_fare_nlcs(self, crs: str) -> set[str]:
        """The station's own location codes and its expanded fare group's code."""
        code = crs.strip().upper()
        own = self.nlcs_by_crs.get(code)
        if not own:
            location = self.locations_by_crs.get(code)
            own = {location.nlc} if location is not None else set()
        found = set(own)
        members = self._fare_group_members()
        for nlc in own:
            location = self.locations_by_nlc.get(nlc)
            if location is not None and location.group_nlc in members:
                found.add(location.group_nlc)
        return found

    def _all_fare_nlcs(self, crs: str) -> set[str]:
        """Every location, group or cluster code for ``crs`` across all dates."""
        found = self._direct_fare_nlcs(crs)
        station_clusters = getattr(self, "station_clusters", None)
        if not station_clusters:
            return found
        all_clusters_by_member = self._all_clusters_by_member()
        for nlc in tuple(found):
            found.update(all_clusters_by_member.get(nlc, ()))
        return found

    def _all_clusters_by_member(self) -> dict[str, tuple[str, ...]]:
        station_clusters = getattr(self, "station_clusters", {})
        key = (len(station_clusters), len(getattr(self.report, "files_read", ())))
        cached = getattr(self, "_all_clusters_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        by_member: dict[str, set[str]] = {}
        for cluster_id, rows in station_clusters.items():
            for row in rows:
                by_member.setdefault(row.member_nlc, set()).add(cluster_id)
        result = {
            member: tuple(sorted(clusters))
            for member, clusters in by_member.items()
        }
        self._all_clusters_cache = (key, result)
        return result

    def _direct_stations_for_fare_nlc(self, nlc: str) -> list[Location]:
        """Named stations reached directly by a station or fare-group code."""
        location = self.locations_by_nlc.get(nlc)
        if location is not None and location.crs:
            return [location]
        return [
            self.locations_by_crs[crs]
            for crs in self._fare_group_members().get(nlc, ())
            if crs in self.locations_by_crs
        ]

    def fare_nlcs(self, crs: str, *, day: date | None = None) -> set[str]:
        """Every location code a fare for this station can be filed under.

        A station's fares sit under its own codes -- one town often has several
        -- under its fare group's (RSPS5045 §4.19.2, ADR-0074), and under any
        station cluster whose ``.FSC`` rows include the station's own code or
        its expanded fare group on ``day`` (RSPS5045 §4.2, ADR-0075). A group
        that is itself a named station is not read through, and neither is one
        in ``UNEXPANDED_FARE_GROUPS`` (London Terminals, ``1072``), whether it
        appears on a location record or inside a cluster.
        """
        found = self._direct_fare_nlcs(crs)
        station_clusters = getattr(self, "station_clusters", None)
        if not station_clusters:
            return found
        query_day = day or date.today()
        clusters_by_crs, _ = self._cluster_tables(query_day)
        found.update(clusters_by_crs.get(crs.strip().upper(), ()))
        return found

    def stations_for_fare_nlc(
        self, nlc: str, *, day: date | None = None
    ) -> list[Location]:
        """The named stations a fare filed under this location code reaches.

        A station's code reaches that station. A fare group's code reaches each
        member (ADR-0074). A station cluster's code reaches each active member
        station and each member of an active expanded fare group (ADR-0075).
        Anything else -- a zone, a county code, an unexpanded group such as
        London Terminals, or a code with no record -- reaches nothing this
        database can name, and the query counts it as such rather than guessing.
        """
        direct = self._direct_stations_for_fare_nlc(nlc)
        if direct:
            return direct
        station_clusters = getattr(self, "station_clusters", None)
        if not station_clusters or nlc not in station_clusters:
            return []
        query_day = day or date.today()
        _, stations_by_cluster = self._cluster_tables(query_day)
        return list(stations_by_cluster.get(nlc, ()))

    def _cluster_tables(
        self, query_day: date
    ) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[Location, ...]]]:
        """Return (crs -> active cluster IDs, cluster ID -> active Locations) on ``query_day``."""
        station_clusters = getattr(self, "station_clusters", {})
        key = (len(self.locations_by_nlc), len(station_clusters), len(getattr(self.report, "files_read", ())), query_day)
        cached = getattr(self, "_cluster_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        groups = self._fare_group_members()
        clusters_by_crs_sets: dict[str, set[str]] = {}
        stations_by_cluster: dict[str, tuple[Location, ...]] = {}
        for cluster_id, rows in station_clusters.items():
            crs_in_cluster: set[str] = set()
            for row in rows:
                if not row.covers(query_day):
                    continue
                member = row.member_nlc
                if member in UNEXPANDED_FARE_GROUPS:
                    continue
                location = self.locations_by_nlc.get(member)
                if location is not None and location.crs:
                    if location.crs in self.locations_by_crs:
                        crs_in_cluster.add(location.crs)
                    continue
                for crs in groups.get(member, ()):
                    if crs in self.locations_by_crs:
                        crs_in_cluster.add(crs)
            if crs_in_cluster:
                ordered_crs = sorted(crs_in_cluster)
                stations_by_cluster[cluster_id] = tuple(
                    self.locations_by_crs[crs] for crs in ordered_crs
                )
                for crs in ordered_crs:
                    clusters_by_crs_sets.setdefault(crs, set()).add(cluster_id)
        clusters_by_crs = {
            crs: tuple(sorted(cluster_ids))
            for crs, cluster_ids in clusters_by_crs_sets.items()
        }
        result = (clusters_by_crs, stations_by_cluster)
        self._cluster_cache = (key, result)
        return result

    def _fare_group_members(self) -> dict[str, tuple[str, ...]]:
        """Fare group code -> the CRS of each member station, sorted.

        Derived from the location records, so it is rebuilt when they change
        and never has to be kept in step by a loader. A group counts when some
        named station names it as its FARE_GROUP, the group code is not that
        station's own, the group carries no station code of its own (a group
        that is a station -- 5564 HEATHROW BUS, CRS LHR -- keeps meaning that
        station), and it is not one the page refuses to read through.
        """
        key = (len(self.locations_by_nlc), len(getattr(self.report, "files_read", ())))
        cached = getattr(self, "_fare_group_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        members: dict[str, set[str]] = {}
        for location in self.locations_by_nlc.values():
            group = location.group_nlc
            if not location.crs or not group or group == location.nlc:
                continue
            if group in UNEXPANDED_FARE_GROUPS:
                continue
            record = self.locations_by_nlc.get(group)
            if record is not None and record.crs:
                continue
            members.setdefault(group, set()).add(location.crs)
        result = {group: tuple(sorted(crs)) for group, crs in members.items()}
        self._fare_group_cache = (key, result)
        return result

    def station_coordinates(self) -> dict[str, tuple[float, float]]:
        """Return CRS -> (lat, lon), loading Knowledgebase stations.xml once."""
        if self._station_coordinates is not None:
            return self._station_coordinates
        path = self._station_coordinates_path or DEFAULT_STATIONS_XML
        self._station_coordinates = load_station_coordinates(path)
        if not self._station_coordinates and path.is_file() is False:
            self.report.skip_file(
                f"heritage prune: station coordinates file {path} is missing; "
                "curated candidates were kept without a distance filter"
            )
        return self._station_coordinates

    def _candidate_crs(self, stations: tuple[str, ...]) -> list[str]:
        """Return feed CRS codes whose names match the curated station tokens."""
        names = {self._normalise_settlement_name(station) for station in stations}
        return [
            crs
            for crs, location in self.locations_by_crs.items()
            if self._settlement_matches(location.name, names)
        ]

    def _pruned_attraction_crs(self, attraction: ReviewedAttraction) -> list[str]:
        """Return the curated candidate CRS codes kept by the hybrid prune.

        The same rule the heritage reader uses (ADR-0063): keep the curated
        candidates, drop any beyond ``max_km`` from an attraction point, keep
        the nearest and a soft twin, and leave a candidate the coordinate file
        does not locate in place, because distance cannot judge it.
        """
        candidates = self._candidate_crs(attraction.stations)
        coordinates = self.station_coordinates()
        if not candidates or not coordinates:
            return candidates
        located = [
            (crs, coordinates[crs][0], coordinates[crs][1])
            for crs in candidates
            if crs in coordinates
        ]
        missing = [crs for crs in candidates if crs not in coordinates]
        selected = select_nearest_stations(located, attraction.points)
        return [*selected, *missing]

    def _facet_attraction_crs(self, facet: DestinationFacet) -> set[str]:
        """Every CRS the facet's reviewed attractions are reached from."""
        if not facet.reviewed_attractions:
            return set()
        return {
            crs
            for attraction in facet.reviewed_attractions
            for crs in self._attraction_crs_by_facet(facet.key).get(attraction.name, ())
        }

    def _attraction_crs_by_facet(self, facet_key: str) -> dict[str, frozenset[str]]:
        """Attraction name -> kept CRS codes, computed once per facet."""
        cached = self._attraction_crs_cache.get(facet_key)
        if cached is not None:
            return cached
        cached = {}
        for attraction in REVIEWED_ATTRACTIONS_BY_FACET.get(facet_key, ()):
            cached[attraction.name] = frozenset(self._pruned_attraction_crs(attraction))
        self._attraction_crs_cache[facet_key] = cached
        return cached

    def _pruned_heritage_crs(
        self,
        site_id: int,
        stations: tuple[str, ...],
    ) -> list[str]:
        """Return curated candidate CRS codes kept by the hybrid distance prune."""
        candidates = self._candidate_crs(stations)
        points = HERITAGE_SITE_POINTS.get(site_id)
        if not candidates or not points:
            return candidates
        coordinates = self.station_coordinates()
        if not coordinates:
            return candidates
        located = [
            (crs, coordinates[crs][0], coordinates[crs][1])
            for crs in candidates
            if crs in coordinates
        ]
        missing = [crs for crs in candidates if crs not in coordinates]
        selected = select_nearest_stations(located, points)
        # Stations absent from the Knowledgebase file (some Underground and
        # heritage-railway names) stay as curated candidates: distance cannot
        # judge them, and dropping them would silence real gateways.
        return [*selected, *missing]

    def destination_type(self, crs: str) -> str:
        """Return the station's primary ``city``, ``town`` or ``other`` class."""
        return self.location_types_by_crs.get(crs.strip().upper(), "other")

    def destination_types(self, crs: str) -> list[str]:
        """Return the primary class followed by any independent destination facets."""
        code = crs.strip().upper()
        return [self.destination_type(code), *sorted(self.location_facets_by_crs.get(code, set()))]

    def _heritage_crs_by_site(self) -> dict[int, frozenset[str]]:
        """UNESCO site id -> kept CRS codes, computed once per coordinate set."""
        key = (
            len(self.locations_by_crs),
            id(self._station_coordinates),
            self._station_coordinates_path,
        )
        cached = getattr(self, "_heritage_crs_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        by_site = {
            site_id: frozenset(self._pruned_heritage_crs(site_id, stations))
            for site_id, _name, stations in HERITAGE_PROPERTIES
        }
        self._heritage_crs_cache = (key, by_site)
        return by_site

    def heritage_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the UNESCO properties that make this station a heritage match."""
        code = crs.strip().upper()
        location = self.locations_by_crs.get(code)
        if location is None or "heritage" not in self.location_facets_by_crs.get(code, set()):
            return []
        by_site = self._heritage_crs_by_site()
        sites: list[dict[str, object]] = []
        for site_id, name, _stations in HERITAGE_PROPERTIES:
            if code not in by_site.get(site_id, ()):
                continue
            sites.append(
                {
                    "id": site_id,
                    "name": name,
                    "url": f"https://whc.unesco.org/en/list/{site_id}/",
                }
            )
        return sites

    def _nature_crs_by_site(self) -> dict[tuple[str, str], frozenset[str]]:
        """(name, url) -> kept CRS codes for nature reserves, computed once."""
        key = (
            len(self.locations_by_crs),
            id(self._station_coordinates),
            self._station_coordinates_path,
        )
        cached = getattr(self, "_nature_crs_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        by_name: dict[tuple[str, str], list[str]] = {}
        for site_crs, name, url in NATURE_SITE_PROOFS:
            by_name.setdefault((name, url), []).append(site_crs)
        coordinates = None
        by_site: dict[tuple[str, str], frozenset[str]] = {}
        for pair, site_codes in by_name.items():
            kept = site_codes
            if len(site_codes) > 1:
                if coordinates is None:
                    coordinates = self.station_coordinates()
                located = [
                    (site_crs, coordinates[site_crs][0], coordinates[site_crs][1])
                    for site_crs in site_codes
                    if site_crs in coordinates
                ]
                if len(located) >= 2:
                    # One attraction point: the centroid of the reviewed CRS set.
                    lats = [lat for _crs, lat, _lon in located]
                    lons = [lon for _crs, _lat, lon in located]
                    point = (sum(lats) / len(lats), sum(lons) / len(lons))
                    kept = select_nearest_stations(located, (point,))
                    missing = [site_crs for site_crs in site_codes if site_crs not in coordinates]
                    kept = [*kept, *missing]
            by_site[pair] = frozenset(kept)
        self._nature_crs_cache = (key, by_site)
        return by_site

    def nature_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the named nature reserves that make this station a nature match."""
        code = crs.strip().upper()
        if "nature" not in self.location_facets_by_crs.get(code, set()):
            return []
        return [
            {"name": name, "url": url}
            for (name, url), kept in self._nature_crs_by_site().items()
            if code in kept
        ]

    def coastal_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the named coastal day-outs for a seaside-tagged station."""
        code = crs.strip().upper()
        if "seaside" not in self.location_facets_by_crs.get(code, set()):
            return []
        return [
            {"name": name, "url": url}
            for site_crs, name, url in COASTAL_SITE_PROOFS
            if site_crs == code
        ]

    def _attraction_sites(self, crs: str, facet_key: str) -> list[dict[str, object]]:
        """Return the named day-outs that make this station a facet match.

        The same chip-implies-named-proof shape as the coastal and nature
        sublimes (ADR-0064): if the facet tagged the station, the reviewed
        attraction it was tagged for is named rather than left to a bare chip.
        """
        code = crs.strip().upper()
        if facet_key not in self.location_facets_by_crs.get(code, set()):
            return []
        by_attraction = self._attraction_crs_by_facet(facet_key)
        return [
            {"name": attraction.name, "url": attraction.url}
            for attraction in REVIEWED_ATTRACTIONS_BY_FACET.get(facet_key, ())
            if code in by_attraction.get(attraction.name, ())
        ]

    def rspb_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the RSPB reserves that make this station an RSPB match."""
        return self._attraction_sites(crs, "rspb")

    def national_trust_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the National Trust properties this station is a proof for."""
        return self._attraction_sites(crs, "national_trust")

    def national_park_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the National Park / Landscape gateways this station serves."""
        return self._attraction_sites(crs, "national_park")

    # -- querying --------------------------------------------------------

    def _flow_valid_on(self, flow: Flow, query_day: date) -> bool:
        return not (
            (flow.start_date is not None and query_day < flow.start_date)
            or (flow.end_date is not None and query_day > flow.end_date)
        )

    def fare_coverage_audit(
        self, *, day: date | None = None, sample_limit: int = 10
    ) -> dict[str, object]:
        """Count the fares that reach a station through a code that is not its own.

        A station's fares sit under its own location codes and under its fare
        group's (ADR-0074), and the query reads both. This report says how much
        of the feed the group half is -- the flows filed under a group, and the
        stations that only those flows price -- and how much sits under a group
        the query deliberately does not read through (London Terminals), so the
        part left unpriced is named instead of silent.
        """
        query_day = day or date.today()
        limit = max(0, sample_limit)
        groups = self._fare_group_members()
        active_fare_flows = {
            flow.flow_id
            for flow in self.flows.values()
            if self.fares_by_flow.get(flow.flow_id)
            and self._flow_valid_on(flow, query_day)
        }
        station_clusters = getattr(self, "station_clusters", {})
        clusters_by_crs, stations_by_cluster = self._cluster_tables(query_day)
        active_memberships = sum(
            1
            for rows in station_clusters.values()
            for row in rows
            if row.covers(query_day)
        )
        group_flows: dict[str, set[str]] = {group: set() for group in groups}
        cluster_flows: set[str] = set()
        unexpanded_flows: set[str] = set()
        for flow_id in active_fare_flows:
            flow = self.flows[flow_id]
            for nlc in {flow.origin_nlc, flow.destination_nlc}:
                if nlc in group_flows:
                    group_flows[nlc].add(flow_id)
                elif nlc in UNEXPANDED_FARE_GROUPS:
                    unexpanded_flows.add(flow_id)
                if nlc in station_clusters:
                    cluster_flows.add(flow_id)
        direct_stations: set[str] = set()
        for crs, nlcs in self.nlcs_by_crs.items():
            if any(
                flow.flow_id in active_fare_flows
                for nlc in nlcs
                for flow in self.flows_touching_nlc.get(nlc, ())
            ):
                direct_stations.add(crs)
        only_through_group: list[dict[str, object]] = []
        for group in sorted(groups):
            if not group_flows[group]:
                continue
            for crs in groups[group]:
                location = self.locations_by_crs.get(crs)
                if location is None or crs in direct_stations:
                    continue
                only_through_group.append(
                    {
                        "crs": crs,
                        "name": location.name,
                        "groupNlc": group,
                        "flowCount": len(group_flows[group]),
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
            if (
                flow.destination_nlc in groups
                or flow.destination_nlc in stations_by_cluster
            ):
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
            "groupCodes": len(groups),
            "groupFareFlows": len(set().union(*group_flows.values())),
            "stationsPricedOnlyThroughGroup": len(only_through_group),
            "sampleStationsPricedOnlyThroughGroup": only_through_group[:limit],
            "unexpandedGroupFareFlows": len(unexpanded_flows),
            "clusterCodes": len(station_clusters),
            "clusterMemberships": active_memberships,
            "stationsInClusters": len(clusters_by_crs),
            "clusterFareFlows": len(cluster_flows),
            "stationsWithMultipleLocationCodes": len(location_aliases),
            "sampleStationsWithMultipleLocationCodes": location_aliases[:limit],
            "fareFlowsWithMissingLocation": missing_location,
            "fareFlowsWithNoStationCode": no_station_code,
            "sampleFareFlowsWithUnmappedDestinations": unmapped_destinations,
        }

    def stats(self) -> dict[str, int]:
        if self.feed_stats is not None:
            return dict(self.feed_stats)
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

    def reviewed_railcard_families(self) -> list[RailcardFamily]:
        """The published railcards, as products, in the order the page lists them.

        Only products whose primary code the feed carries are published. A
        product whose primary code is absent but whose aliases are present is
        still published, through the alias, because refusing a card the reader
        holds because the feed dropped one of its spellings would be a page
        answering the wrong question.

        The adult bounds are the union across every code the feed carries for
        the product: the feed gives the Senior Railcard 1-1 under SRN and 1-8
        under RSN, and a reader with the replacement is still one traveller. A
        bound of zero is read as unstated rather than as a bound, so the 16-25
        Railcard is one adult rather than none.

        Ordered by label, so adding a product to the middle of the reviewed set
        cannot silently reshuffle the menu.
        """
        families: list[RailcardFamily] = []
        absent: list[str] = []
        for primary, entry in REVIEWED_PUBLIC_RAILCARDS.items():
            wanted = (primary,) + tuple(entry.get("codes") or ())
            present = tuple(code for code in wanted if code in self.railcards)
            missing = [code for code in wanted if code not in self.railcards]
            if not present:
                absent.extend(missing)
                continue
            # An alias standing in for an absent primary is promoted, so the
            # card is offered under the code the feed actually has.
            lead = present[0]
            low, high = _adult_bounds(present, self.railcards)
            families.append(
                RailcardFamily(
                    key=lead,
                    label=str(entry["label"]),
                    codes=present,
                    min_adults=low,
                    max_adults=high,
                )
            )
        if absent and not self.report.reviewed_railcard_codes_absent:
            self.report.reviewed_railcard_codes_absent = sorted(absent)
        return sorted(families, key=lambda family: family.label)

    def railcard_label(self, code: str) -> str:
        """The label a reviewed railcard is shown by, or an empty string."""
        return REVIEWED_PUBLIC_RAILCARDS.get(code, {}).get("label", "")

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

    def is_advance_fare(self, ticket_name: object, restriction_code: object) -> bool:
        """Whether a fare row is valid on one named date and train only.

        A ticket called ADVANCE is train-specific whatever code it carries,
        and a code the ``.RST`` file describes as "valid on date&train shown
        only" is train-specific whatever the ticket is called. The second
        test reads the restriction file rather than naming one code: this
        build recognised AS alone, so the 51 other codes the feed describes
        the same way -- GA among them, on every LNER promotion -- reached
        the page as an ordinary walk-up single (audit A9).
        """
        code = str(restriction_code or "").strip().upper()
        return (
            is_advance_ticket(ticket_name)
            or code in ADVANCE_RESTRICTION_CODES
            or self.restrictions.binds_to_date_and_train(code)
        )

    def minimum_fare(
        self, railcard_code: str, ticket_code: str, day: date | None = None
    ) -> int | None:
        """The minimum fare in force for this ticket on ``day``, if any.

        A blank start or end date is an open end, so a record that names no
        window applies to every day. When a key holds several windows only the
        ones covering the query day are considered; if a feed ever lists two
        that both cover it, the later start wins, so the record nearest the
        query is the one applied rather than whichever the file wrote last.
        """
        query_day = day or date.today()
        active = [
            record
            for record in self.minimum_fares.get((railcard_code, ticket_code), ())
            if record.covers(query_day)
        ]
        if not active:
            return None
        return max(active, key=lambda record: record.start_date or date.min).pence

    def railcard_discount(
        self, railcard_code: str, ticket_code: str, day: date | None = None
    ) -> Fraction | None:
        """What the card takes off this ticket, from the feed's DIS table.

        The card's adult status and the ticket's discount category name the
        record. ``None`` is the record saying the card gives no discount on this
        ticket (``X`` or ``N``, RSPS5045 §4.16.3): the card's price is then the
        standard fare. Where the feed has no record for the pair -- no DIS file,
        as in the synthetic fixture, or a key it does not carry -- the reading
        is a third, the published figure the page used before it read the table.
        """
        railcard = self.railcards.get(railcard_code)
        ticket = self.ticket_types.get(ticket_code)
        key = (
            getattr(railcard, "adult_status", "") if railcard else "",
            getattr(ticket, "discount_category", "") if ticket else "",
        )
        query_day = day or date.today()
        current = [
            record
            for record in getattr(self, "status_discounts", {}).get(key, ())
            if record.covers(query_day)
        ]
        if current:
            # The window that ends first is the one in force today.
            return min(current, key=lambda record: record.end_date or date.max).discount
        return 1 - RAILCARD_DISCOUNT

    def railcard_discounts_ticket(
        self, railcard_code: str, ticket_code: str, day: date | None = None
    ) -> bool:
        """Whether the feed gives this card any discount on this ticket."""
        return self.railcard_discount(railcard_code, ticket_code, day) is not None

    def railcard_price(
        self,
        railcard_code: str,
        ticket_code: str,
        standard_pence: int,
        *,
        day: date | None = None,
    ) -> int:
        # The discounted fare is rounded down to the nearest 5p for each
        # ticket, not up, and not on the party's total: £12.10 is £8.05 and
        # £13.30 is £8.85 with Two Together (#149), so the step is 5p, and two
        # people pay twice the one ticket.
        discount = self.railcard_discount(railcard_code, ticket_code, day)
        if discount is None:
            # No discount, so no railcard minimum either: the minimum is a floor
            # under a discounted fare (RSPS5045 §4.15), and the card's price is
            # the fare itself.
            return standard_pence
        discounted = _round_down_to(standard_pence * (1 - discount), ROUNDING_STEP_PENCE)
        minimum = self.minimum_fare(railcard_code, ticket_code, day)
        if minimum is not None:
            discounted = max(discounted, minimum)
        return discounted

    def railcard_rules(
        self,
        railcard_code: str,
        *,
        ticket_code: str,
        route_code: str,
        origin_crs: str,
        destination_crs: str,
        origin_nlc: str,
        destination_nlc: str,
    ) -> list[RailcardRestrictionRow]:
        """Return every current DTD ``RR`` rule that applies to one fare.

        Blank RR fields are wildcards. An RR restriction code changes or
        overrides the fare's restriction; it is not itself a total ban. The
        caller can therefore preserve conditions such as Two Together's R9
        without refusing the discount.
        """
        stations = {value.strip().upper() for value in (origin_crs, destination_crs, origin_nlc, destination_nlc) if value}
        return [
            row
            for row in self.restrictions.active_railcard_rows(railcard_code)
            if (not row.ticket_code or row.ticket_code == ticket_code)
            and (not row.route_code or row.route_code == route_code)
            and (not row.location or row.location in stations or row.location.strip().upper() in stations)
        ]

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
        """Return the first matching current ``RR`` total ban, if there is one."""
        return next(
            (
                row
                for row in self.railcard_rules(
                    railcard_code,
                    ticket_code=ticket_code,
                    route_code=route_code,
                    origin_crs=origin_crs,
                    destination_crs=destination_crs,
                    origin_nlc=origin_nlc,
                    destination_nlc=destination_nlc,
                )
                if row.total_ban
            ),
            None,
        )

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
        day: date | None = None,
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
        return self.railcard_price(railcard_code, ticket_code, standard_pence, day=day)

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

    @staticmethod
    def _displayable_single_rejection(
        restrictions,
        include_conditional: bool = False,
        include_advance: bool = False,
    ) -> Callable[[Fare, TicketType], str | None]:
        """The reviewed rule for a single a page may quote, or why not.

        One method so the page row and the priced chooser cannot drift apart.
        The reasons are distinct because the coverage report counts them, and a
        count that files a child's fare under "not a standard single" cannot
        answer what happened to a destination.

        A fare bound to one date and train is rejected under its own reason,
        because it is a different failure from a fare that is merely
        conditional: the fare exists and is sold, but not at that price to
        anyone who has not chosen a train. It is a staticmethod that needs the
        restriction index for two different questions, and the advance test
        needs the fare's own ticket name and restriction code, so the callable
        is closed over them here rather than re-derived per fare.
        """
        advance_codes = ADVANCE_RESTRICTION_CODES

        def reject(fare: Fare, ticket: TicketType) -> str | None:
            if not include_conditional and (
                fare.ticket_code in CONDITIONAL_TICKET_CODES
                or not ticket.sold_to_one_adult
            ):
                return CONDITIONAL_REASON
            if restrictions.requires_another_ticket(fare.restriction_code):
                return CONDITIONAL_REASON
            if not include_advance and (
                ticket.is_advance
                or fare.restriction_code.strip().upper() in advance_codes
                or restrictions.binds_to_date_and_train(fare.restriction_code)
            ):
                return ADVANCE_REASON
            if not ticket.is_standard_single:
                return "ticket_is_not_a_standard_single"
            name = ticket.name.upper()
            if (
                fare.ticket_code in PLACEHOLDER_TICKET_CODES
                or "ITX" in name
                or fare.pence in SENTINEL_FARE_PENCE
            ):
                return "ticket_is_a_catalogue_placeholder"
            if is_not_for_public_sale(name):
                return "ticket_is_not_for_public_sale"
            return None

        setattr(
            reject,
            "_selector_key",
            (
                "single",
                id(restrictions),
                getattr(restrictions, "parsed_records", 0),
                include_conditional,
                include_advance,
            ),
        )
        return reject

    @staticmethod
    def _displayable_return_rejection(
        restrictions,
        include_conditional: bool = False,
    ) -> Callable[[Fare, TicketType], str | None]:
        """The same rule for a return, which the feed prices the same way.

        A group return is quoted for the party, so it cannot be a reader's
        cheapest return either. The catalogue placeholder test stays, and its
        own reason, because a placeholder is a different mistake from a fare
        that is real and simply not the reader's.

        The not-for-public-sale test the single selector has always run runs
        here too. It was missing, and a fare the catalogue calls NOT FOR
        TRAVEL reached a page through the gap.
        """

        def reject(fare: Fare, ticket: TicketType) -> str | None:
            if not include_conditional and (
                fare.ticket_code in CONDITIONAL_TICKET_CODES
                or not ticket.sold_to_one_adult
            ):
                return CONDITIONAL_REASON
            if restrictions.requires_another_ticket(fare.restriction_code):
                return CONDITIONAL_REASON
            if not ticket.is_standard_return:
                return "ticket_is_not_a_standard_return"
            name = ticket.name.upper()
            if (
                fare.ticket_code in PLACEHOLDER_TICKET_CODES
                or "ITX" in name
                or fare.pence in SENTINEL_FARE_PENCE
            ):
                return "ticket_is_a_catalogue_placeholder"
            if is_not_for_public_sale(name):
                return "ticket_is_not_for_public_sale"
            return None

        setattr(
            reject,
            "_selector_key",
            (
                "return",
                id(restrictions),
                getattr(restrictions, "parsed_records", 0),
                include_conditional,
            ),
        )
        return reject

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
        include_conditional: bool = False,
    ) -> list[Reachable]:
        """Rows suitable for the reader-facing page, including restrictions.

        The feed contains ITX placeholder fares such as ``EIS`` at the £0.05
        minimum with restriction ``GA``. They are not usable public fares, so
        they must not win the broad query's cheapest-fare comparison. Other
        restricted standard returns remain visible and carry their restriction
        code to the page.

        ``include_conditional`` puts the child, family, group and event fares back.
        Nothing on a page sets it. It exists so the coverage report can ask
        what the rule costs, by asking this selector the same question both
        ways and counting the destinations that differ.
        """
        # The test runs inside the shared loop rather than on the rows the broad
        # query returns. Filtering afterwards would let a conditional fare win
        # the slot and then take the destination with it, leaving the page
        # without the adult fare the feed also holds for that pair.
        return self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=self._displayable_return_rejection(
                self.restrictions, include_conditional
            ),
            day=day,
        )

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
        include_conditional: bool = False,
        include_advance: bool = False,
    ) -> list[Reachable]:
        """Displayable standard-class singles, excluding catalogue placeholders.

        A train-restricted fare is out of the result by default. An advance
        single is attached to one named train, so its price is not the price of
        the journey: quoting it as the cheapest way to reach a place told a
        reader Grantham to Skegness cost £6.60 when no train on the day sold
        that fare, and the page had no way to name the train that did. The
        figure was arithmetically correct and practically untrue, which is worse
        than being loose, and a page whose whole claim is a price cannot carry
        a number it would not honour at a seller.

        ``include_advance`` puts them back, for the coverage report's
        measurement of what the rule costs and nothing else.

        ``include_conditional`` puts the child, family, group and event fares back, for
        the coverage report's measurement and nothing else.
        """
        rows = self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=self._displayable_single_rejection(
                self.restrictions, include_conditional, include_advance
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
        fields are wildcards, a matching total ban removes the discount, and a
        matching restriction code supplies the railcard fare's travel condition.

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

    def priced_destinations_within(
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
        """Every destination the origin's page can price, in any ticket mode.

        The page publishes restricted standard returns, displayable singles and
        reviewed anytime returns, so a station priced in any one of them has a
        page a reader can use (ADR-0019 decision 3). The chooser's priceable
        test and the unsourced-destination report share this one selector so
        they cannot drift: audit A1 caught the chooser measuring the anytime
        mode alone while King's Cross published 171 returns from the other two.
        A destination priced in several modes appears once, so a coverage check
        over the rows names it exactly once.

        A ``tally`` counts each flow's rejection once: all three modes drop an
        unnameable destination in the shared loop before mode-specific
        filtering, so the tally rides on one mode only, where passing it to
        all three would triple-count (audit A3).
        """
        rows: dict[str, Reachable] = {}
        queries = (
            (self.page_destinations_within, tally),
            (self.page_single_destinations_within, None),
            (self.publishable_destinations_within, None),
        )
        for query, mode_tally in queries:
            for row in query(
                origin_crs,
                budget_pence,
                adults=adults,
                railcard=railcard,
                party_budget=party_budget,
                tally=mode_tally,
                day=day,
            ):
                rows.setdefault(row.crs, row)
        return list(rows.values())

    def two_part_fares(
        self,
        origin_crs: str,
        splits: dict[str, str | Sequence[str]],
        rows_from: Callable[[str], list[Reachable]],
    ) -> list[TwoPartFare]:
        """Places with no fare of their own, priced as two fares (ADR-0061).

        ``splits`` maps each destination to one pricing-split CRS or a sequence
        of candidates on that destination's journey (calling points and, when
        the journey changes trains, the change station). ``rows_from`` is the
        page's own selector for one ticket mode, asked of any station. For each
        candidate the first ticket is what ``rows_from(origin)`` prices for the
        split and the second is what ``rows_from(split)`` prices for the
        destination, so each is the fare a page for that pair would quote. When
        several candidates both sell, the cheapest valid sum wins, then the
        split CRS. A destination the origin already prices on one ticket keeps
        that row, and a pair with either ticket missing is no row at all: the
        price is the journey's own or nothing.
        """
        origin = origin_crs.strip().upper()
        asked: dict[str, dict[str, Reachable]] = {}

        def priced_from(crs: str) -> dict[str, Reachable]:
            if crs not in asked:
                asked[crs] = (
                    {row.crs: row for row in rows_from(crs)}
                    if crs in self.locations_by_crs
                    else {}
                )
            return asked[crs]

        def candidates_of(value: str | Sequence[str]) -> tuple[str, ...]:
            if isinstance(value, str):
                return (value.strip().upper(),)
            return tuple(crs.strip().upper() for crs in value)

        direct = priced_from(origin)
        needed_by_change: dict[str, set[str]] = {}
        for destination, raw in splits.items():
            dest = destination.strip().upper()
            if dest in direct or dest == origin:
                continue
            for change in candidates_of(raw):
                if change in {origin, dest} or change not in direct:
                    continue
                needed_by_change.setdefault(change, set()).add(dest)
        if not needed_by_change:
            return []

        def priced_from_change(crs: str) -> dict[str, Reachable]:
            if crs not in asked:
                if crs not in self.locations_by_crs:
                    asked[crs] = {}
                else:
                    self._two_part_target_crs = frozenset(needed_by_change.get(crs, ()))
                    try:
                        asked[crs] = {row.crs: row for row in rows_from(crs)}
                    finally:
                        self._two_part_target_crs = None
            return asked[crs]

        found: list[TwoPartFare] = []
        for destination, raw in sorted(splits.items()):
            destination = destination.strip().upper()
            if destination in direct or destination == origin:
                continue
            best: TwoPartFare | None = None
            for change in candidates_of(raw):
                if change in {origin, destination}:
                    continue
                first = direct.get(change)
                if first is None:
                    continue
                second = priced_from_change(change).get(destination)
                if second is None:
                    continue
                candidate = TwoPartFare(
                    crs=destination,
                    station=second.station,
                    change_crs=change,
                    change_station=first.station,
                    first=first,
                    second=second,
                )
                if best is None or (candidate.best_pence, candidate.change_crs) < (
                    best.best_pence,
                    best.change_crs,
                ):
                    best = candidate
            if best is not None:
                found.append(best)
        return sorted(found, key=lambda fare: (fare.best_pence, fare.crs))

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

        setattr(reject, "_selector_key", ("publishable", strict))
        return reject

    def _dest_nlcs_for_origin_nlc(
        self,
        origin_nlc: str,
        origin_crs: str,
        is_own_nlc: bool,
    ) -> frozenset[str]:
        if origin_nlc not in self.flows_touching_nlc:
            if is_own_nlc:
                if origin_crs not in getattr(self, "_pending_interchange_crs", ()):
                    return frozenset()
            elif origin_nlc not in getattr(self, "_pending_cluster_nlcs", ()):
                return frozenset()
        table = getattr(self, "_origin_nlc_dest_nlcs", None)
        if table is None:
            table = {}
            self._origin_nlc_dest_nlcs = table
        cached = table.get(origin_nlc)
        if cached is not None:
            return cached
        if getattr(self, "_has_full_origin_nlc_dest_nlcs", False):
            return frozenset()
        if origin_nlc not in self.flows_touching_nlc:
            self._ensure_interchange_loaded(
                origin_crs,
                (origin_nlc,),
                {origin_nlc} if is_own_nlc else frozenset(),
            )
        flows = self.flows_touching_nlc.get(origin_nlc)
        if not flows:
            return frozenset()
        result = frozenset(
            flow.origin_nlc
            if flow.direction == "R" and flow.destination_nlc == origin_nlc
            else flow.destination_nlc
            for flow in flows
        )
        table[origin_nlc] = result
        return result

    def _flows_for_origin_and_dest_nlcs(
        self,
        origin_nlc: str,
        matching_dest_nlcs: frozenset[str],
    ) -> list[Flow]:
        table = getattr(self, "_flows_by_origin_dest_nlc", None)
        if table is None:
            table = {}
            self._flows_by_origin_dest_nlc = table
        by_dest = table.get(origin_nlc)
        if by_dest is None:
            buckets: dict[str, list[tuple[int, Flow]]] = {}
            for idx, flow in enumerate(self.flows_touching_nlc.get(origin_nlc, ())):
                dest_nlc = (
                    flow.origin_nlc
                    if flow.direction == "R" and flow.destination_nlc == origin_nlc
                    else flow.destination_nlc
                )
                buckets.setdefault(dest_nlc, []).append((idx, flow))
            by_dest = {
                dest_nlc: tuple(pairs) for dest_nlc, pairs in buckets.items()
            }
            table[origin_nlc] = by_dest
        if len(matching_dest_nlcs) == 1:
            only_nlc = next(iter(matching_dest_nlcs))
            return [flow for _idx, flow in by_dest.get(only_nlc, ())]
        pairs = [
            pair
            for dest_nlc in matching_dest_nlcs
            for pair in by_dest.get(dest_nlc, ())
        ]
        pairs.sort(key=lambda item: item[0])
        return [flow for _idx, flow in pairs]

    def _resolved_destination_cache(
        self, query_day: date
    ) -> dict[str, tuple[tuple[Location, ...], int, frozenset[str], bool, str]]:
        station_clusters = getattr(self, "station_clusters", {})
        key = (len(self.locations_by_nlc), len(station_clusters), len(getattr(self.report, "files_read", ())), query_day)
        cached = getattr(self, "_dest_nlc_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        table: dict[
            str, tuple[tuple[Location, ...], int, frozenset[str], bool, str]
        ] = {}
        self._dest_nlc_cache = (key, table)
        return table

    def _resolve_destination_nlc(
        self, destination_nlc: str, query_day: date
    ) -> tuple[tuple[Location, ...], int, frozenset[str], bool, str]:
        destinations = self.stations_for_fare_nlc(destination_nlc, day=query_day)
        if not destinations:
            reason = (
                "destination_has_no_location_record"
                if destination_nlc not in self.locations_by_nlc
                else "destination_has_no_station_code"
            )
            return ((), 0, frozenset(), False, reason)
        real_locs = tuple(
            destination
            for destination in destinations
            if not is_pseudo_station(destination.crs)
        )
        pseudo_count = len(destinations) - len(real_locs)
        real_crs = frozenset(destination.crs for destination in real_locs)
        return (real_locs, pseudo_count, real_crs, True, "")

    def _flow_eval_cache(
        self,
        selector_key: tuple[object, ...] | None,
        budget_pence: int,
        adults: int,
        party_budget: bool,
    ) -> dict[
        str,
        tuple[
            tuple[tuple[str, int], ...],
            tuple[int, ...],
            tuple[int, str, str, int, int, bool, str] | None,
        ],
    ]:
        if selector_key is None:
            return {}
        db_key = (
            id(self.fares_by_flow),
            len(self.ticket_types),
            len(getattr(self.report, "files_read", ())),
            getattr(self.restrictions, "parsed_records", 0),
        )
        caches = getattr(self, "_flow_eval_caches", None)
        if caches is None or caches[0] != db_key:
            caches = (db_key, {})
            self._flow_eval_caches = caches
        full_key = (selector_key, budget_pence, adults, party_budget)
        table = caches[1].get(full_key)
        if table is None:
            table = {}
            caches[1][full_key] = table
        return table

    def _evaluate_flow_bucket(
        self,
        flow_id: str,
        *,
        budget_pence: int,
        adults: int,
        party_budget: bool,
        selector: Callable[[Fare, TicketType], str | None] | None,
    ) -> tuple[
        tuple[tuple[str, int], ...],
        tuple[int, ...],
        tuple[int, str, str, int, int, bool, str] | None,
    ]:
        bucket = self.fares_by_flow.get(flow_id)
        if not bucket:
            return ((("flow_with_no_fare", 1),), (), None)
        reject_counts: dict[str, int] = {}
        accepted_prices: list[int] = []
        best_meta: tuple[int, str, str, int, int, bool, str] | None = None
        min_accepted_pence: int | None = None
        in_bucket_losers = 0
        for fare in bucket.values():
            ticket = self.ticket_types.get(fare.ticket_code)
            if ticket is None:
                reject_counts["fare_with_no_ticket_type"] = (
                    reject_counts.get("fare_with_no_ticket_type", 0) + 1
                )
                continue
            if selector is not None:
                rejection = selector(fare, ticket)
                if rejection is not None:
                    reject_counts[rejection] = reject_counts.get(rejection, 0) + 1
                    continue
            elif not ticket.is_standard_return:
                reject_counts["ticket_is_not_a_standard_return"] = (
                    reject_counts.get("ticket_is_not_a_standard_return", 0) + 1
                )
                continue
            candidate_pence = fare.pence
            party_pence = candidate_pence * adults
            tested = party_pence if party_budget else candidate_pence
            if tested > budget_pence:
                reject_counts["fare_above_the_budget"] = (
                    reject_counts.get("fare_above_the_budget", 0) + 1
                )
                continue
            if min_accepted_pence is not None and candidate_pence >= min_accepted_pence:
                in_bucket_losers += 1
                continue
            min_accepted_pence = candidate_pence
            accepted_prices.append(candidate_pence)
            best_meta = (
                candidate_pence,
                ticket.code,
                ticket.name,
                fare.pence,
                party_pence,
                ticket.restricted_by_train,
                fare.restriction_code.strip(),
            )
        if in_bucket_losers:
            reject_counts["cheaper_index_already_held"] = in_bucket_losers
        return (tuple(reject_counts.items()), tuple(accepted_prices), best_meta)

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
        # The station's own codes first, then its group's, then its clusters',
        # each in code order: a tie between two fares keeps the one read first,
        # so a broader code only displaces a narrower one when it is strictly
        # cheaper, and the same feed always shows the same ticket.
        own_nlcs = self.nlcs_by_crs.get(origin.crs, {origin.nlc})
        direct_nlcs = self._direct_fare_nlcs(origin.crs)
        origin_nlcs = sorted(
            self.fare_nlcs(origin.crs, day=query_day),
            key=lambda nlc: (
                0 if nlc in own_nlcs else (1 if nlc in direct_nlcs else 2),
                nlc,
            ),
        )
        railcard_code = self.railcard_code(railcard) if railcard else None
        if railcard and railcard_code is None:
            raise KeyError(f"railcard {railcard!r} is not in the feed")
        target_crs: frozenset[str] | None = (
            getattr(self, "_two_part_target_crs", None)
            if tally is None and railcard_code is None
            else None
        )
        matching_by_origin: dict[str, frozenset[str]] | None = None
        if target_crs is not None:
            if not target_crs:
                return []
            dest_nlc_set: set[str] = set()
            for crs in target_crs:
                if crs in self.locations_by_crs and not is_pseudo_station(crs):
                    dest_nlc_set.update(self.fare_nlcs(crs, day=query_day))
            if not dest_nlc_set:
                return []
            target_dest_nlcs = frozenset(dest_nlc_set)
            matching_by_origin = {}
            filtered_origin_nlcs: list[str] = []
            for nlc in origin_nlcs:
                matching = (
                    self._dest_nlcs_for_origin_nlc(nlc, origin.crs, nlc in own_nlcs)
                    & target_dest_nlcs
                )
                if matching:
                    matching_by_origin[nlc] = matching
                    filtered_origin_nlcs.append(nlc)
            if not filtered_origin_nlcs:
                return []
            origin_nlcs = filtered_origin_nlcs
        self._ensure_interchange_loaded(origin.crs, origin_nlcs, own_nlcs)
        if railcard and railcard_code is None:
            raise KeyError(f"railcard {railcard!r} is not in the feed")

        if railcard_code is not None:
            best_by_crs: dict[str, Reachable] = {}
            for origin_nlc in origin_nlcs:
                for flow in self.flows_touching_nlc.get(origin_nlc, ()):
                    if not self._flow_valid_on(flow, query_day):
                        _tally(
                            tally,
                            "flow_not_yet_valid"
                            if flow.start_date is not None and query_day < flow.start_date
                            else "flow_expired",
                        )
                        continue
                    destination_nlc = (
                        flow.origin_nlc
                        if flow.direction == "R" and flow.destination_nlc == origin_nlc
                        else flow.destination_nlc
                    )
                    destinations = self.stations_for_fare_nlc(
                        destination_nlc, day=query_day
                    )
                    if not destinations:
                        _tally(
                            tally,
                            "destination_has_no_location_record"
                            if destination_nlc not in self.locations_by_nlc
                            else "destination_has_no_station_code",
                        )
                        continue
                    for destination in destinations:
                        self._price_flow_to(
                            flow,
                            origin,
                            origin_nlc,
                            destination,
                            destination_nlc,
                            best_by_crs,
                            budget_pence=budget_pence,
                            adults=adults,
                            railcard_code=railcard_code,
                            party_budget=party_budget,
                            tally=tally,
                            selector=selector,
                            query_day=query_day,
                        )
            return sorted(
                best_by_crs.values(),
                key=lambda reachable: (reachable.best_pence, reachable.crs),
            )

        dest_cache = self._resolved_destination_cache(query_day)
        selector_key: tuple[object, ...] | None = (
            ("default_return",)
            if selector is None
            else getattr(selector, "_selector_key", None)
        )
        flow_cache = self._flow_eval_cache(
            selector_key, budget_pence, adults, party_budget
        )
        best_pence_by_crs: dict[str, int] = {}
        best_entry_by_crs: dict[
            str,
            tuple[
                Location,
                tuple[int, str, str, int, int, bool, str],
                str,
                str,
                str,
            ],
        ] = {}
        best_nlc_pence: dict[str, int] = {}
        cheaper_already_held = 0

        for origin_nlc in origin_nlcs:
            flows_iter = (
                self._flows_for_origin_and_dest_nlcs(
                    origin_nlc, matching_by_origin[origin_nlc]
                )
                if matching_by_origin is not None
                else self.flows_touching_nlc.get(origin_nlc, ())
            )
            for flow in flows_iter:
                if not self._flow_valid_on(flow, query_day):
                    if tally is not None:
                        _tally(
                            tally,
                            "flow_not_yet_valid"
                            if flow.start_date is not None and query_day < flow.start_date
                            else "flow_expired",
                        )
                    continue
                destination_nlc = (
                    flow.origin_nlc
                    if flow.direction == "R" and flow.destination_nlc == origin_nlc
                    else flow.destination_nlc
                )
                resolved = dest_cache.get(destination_nlc)
                if resolved is None:
                    resolved = self._resolve_destination_nlc(
                        destination_nlc, query_day
                    )
                    dest_cache[destination_nlc] = resolved
                real_locs, pseudo_count, real_crs, has_any, empty_reason = resolved
                if not has_any:
                    if tally is not None:
                        _tally(tally, empty_reason)
                    continue
                origin_in_dest = origin.crs in real_crs
                if tally is not None:
                    if pseudo_count:
                        tally["destination_is_a_fare_construction_point"] = (
                            tally.get("destination_is_a_fare_construction_point", 0)
                            + pseudo_count
                        )
                    if origin_in_dest:
                        tally["fare_to_the_origin_itself"] = (
                            tally.get("fare_to_the_origin_itself", 0) + 1
                        )
                count_dest = len(real_locs) - (1 if origin_in_dest else 0)
                if count_dest <= 0:
                    continue
                flow_eval = flow_cache.get(flow.flow_id)
                if flow_eval is None:
                    flow_eval = self._evaluate_flow_bucket(
                        flow.flow_id,
                        budget_pence=budget_pence,
                        adults=adults,
                        party_budget=party_budget,
                        selector=selector,
                    )
                    flow_cache[flow.flow_id] = flow_eval
                rejections, accepted_prices, best_meta = flow_eval
                if tally is not None and rejections:
                    for reason, reason_count in rejections:
                        tally[reason] = tally.get(reason, 0) + reason_count * count_dest
                if best_meta is None:
                    continue
                min_pence = best_meta[0]
                prev_nlc_pence = best_nlc_pence.get(destination_nlc)
                if prev_nlc_pence is not None and min_pence >= prev_nlc_pence:
                    if tally is not None:
                        cheaper_already_held += len(accepted_prices) * count_dest
                    continue
                best_nlc_pence[destination_nlc] = min_pence
                route_code = flow.route_code
                for destination in real_locs:
                    crs = destination.crs
                    if crs == origin.crs or (
                        target_crs is not None and crs not in target_crs
                    ):
                        continue
                    prev_best = best_pence_by_crs.get(crs)
                    if prev_best is None:
                        best_pence_by_crs[crs] = min_pence
                        best_entry_by_crs[crs] = (
                            destination,
                            best_meta,
                            route_code,
                            origin_nlc,
                            destination_nlc,
                        )
                    elif min_pence >= prev_best:
                        if tally is not None:
                            cheaper_already_held += len(accepted_prices)
                    else:
                        if tally is not None and len(accepted_prices) > 1:
                            for price in accepted_prices:
                                if price >= prev_best:
                                    cheaper_already_held += 1
                                else:
                                    break
                        best_pence_by_crs[crs] = min_pence
                        best_entry_by_crs[crs] = (
                            destination,
                            best_meta,
                            route_code,
                            origin_nlc,
                            destination_nlc,
                        )

        if tally is not None and cheaper_already_held:
            tally["cheaper_index_already_held"] = (
                tally.get("cheaper_index_already_held", 0) + cheaper_already_held
            )
        return [
            Reachable(
                crs=destination.crs,
                station=destination.name,
                ticket_code=best_meta[1],
                ticket_name=best_meta[2],
                standard_pence=best_meta[3],
                best_pence=best_meta[0],
                railcard_pence=None,
                party_pence=best_meta[4],
                off_peak=best_meta[5],
                restriction_code=best_meta[6],
                route_code=route_code,
                origin_nlc=origin_nlc,
                destination_nlc=destination_nlc,
            )
            for _pence, _crs, (
                destination,
                best_meta,
                route_code,
                origin_nlc,
                destination_nlc,
            ) in sorted(
                (best_meta[0], crs, entry)
                for crs, entry in best_entry_by_crs.items()
                for best_meta in (entry[1],)
            )
        ]

    def _price_flow_to(
        self,
        flow: Flow,
        origin: Location,
        origin_nlc: str,
        destination: Location,
        destination_nlc: str,
        best_by_crs: dict[str, Reachable],
        *,
        budget_pence: int,
        adults: int,
        railcard_code: str | None,
        party_budget: bool,
        tally: dict[str, int] | None,
        selector: Callable[[Fare, TicketType], str | None] | None,
        query_day: date,
    ) -> None:
        """Offer one flow's fares to one named destination, keeping the cheapest.

        A group or cluster flow reaches each member, and every member's fare
        passes the same selector, railcard rules and budget a station's own
        fare does: the group or cluster changes which flows are read, never
        which fares are kept.
        """
        # A zone boundary or a coach stop is where the feed records a fare
        # change, not a place. Dropping it here rather than in each caller is
        # what makes the chooser, the page rows, the write set and the coverage
        # report agree: there is one rule and one place it is applied (audit A6).
        if is_pseudo_station(destination.crs):
            _tally(tally, "destination_is_a_fare_construction_point")
            return
        if destination.crs == origin.crs:
            _tally(tally, "fare_to_the_origin_itself")
            return
        bucket = self.fares_by_flow.get(flow.flow_id)
        if not bucket:
            _tally(tally, "flow_with_no_fare")
            return
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
                    day=query_day,
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
