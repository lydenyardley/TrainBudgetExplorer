"""Find the settlement a station stands in, from the published area boundaries.

The name match in the loader classifies a station whose name is a settlement's
name. A station named for a district, a street or a landmark -- Alexandra
Palace, Ardwick, Kirkstall Forge -- matched nothing, though it stands inside a
built-up area. This module answers the other question: which area is the
station *in*, and how big is it (ADR-0080, ADR-0081).

Three free, open boundary sets, all under the Open Government Licence:

* ONS Built Up Areas 2022, for England and Wales. The band is the Census 2021
  workbook's, joined on BUA22CD. Chester's area crosses the border and carries
  a K code, so the codes asked for are every one the workbook bands, not only
  the E and W ones.
* The ONS London region. The workbook leaves London out: its built-up areas
  are the boroughs, which no size band describes. An area the workbook does not
  band whose centre is in the London region is part of London, a city.
* NRS Settlements 2020, for Scotland, with their mid-2020 populations, banded
  by the thresholds the ONS workbook's own bands follow.

Standard library only. The boundaries are read once from the services as plain
polygons and kept in one cache file beside the feeds, so a build that has the
file asks no service anything. A build that needs them and cannot read them
fails (BoundaryFeedMissing): a station left unsourced because a service was
down is a page that silently says less than the last one.
"""

from __future__ import annotations

import http.client
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

# Built Up Areas (December 2022) Boundaries GB BGG: the generalised 25 m grid
# version, the same 2022 areas the Census 2021 workbook's BUA22CD column names.
ONS_BUA_BOUNDARIES_DATASET_URL = (
    "https://geoportal.statistics.gov.uk/datasets/ons::built-up-areas-december-2022-boundaries-gb-bgg"
)
ONS_BUA_BOUNDARIES_QUERY_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "BUA_2022_GB/FeatureServer/0/query"
)
# Regions (December 2022) Boundaries EN BGC: only London is read.
ONS_REGIONS_QUERY_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Regions_December_2022_EN_BGC/FeatureServer/0/query"
)
LONDON_REGION_CODE = "E12000007"
ONS_BUA_BOUNDARIES_ATTRIBUTION = (
    "Source: Office for National Statistics licensed under the Open Government "
    "Licence v3.0. Contains OS data \u00a9 Crown copyright and database right 2022."
)
ONS_BUA_BOUNDARIES_SOURCE = (
    "Office for National Statistics, Built Up Areas (December 2022) boundaries, "
    "for stations whose name is not their settlement's"
)
# NRS Settlements 2020: groups of high-density postcodes of 500 people or more,
# with the mid-2020 population of each (layer 5 of the Scottish Government's
# NRS map service).
NRS_SETTLEMENTS_DATASET_URL = (
    "https://www.nrscotland.gov.uk/publications/"
    "population-estimates-for-settlements-and-localities-in-scotland-mid-2020/"
)
NRS_SETTLEMENTS_QUERY_URL = (
    "https://maps.gov.scot/server/rest/services/NRS/NRS/MapServer/5/query"
)
NRS_SETTLEMENTS_ATTRIBUTION = (
    "Copyright National Records of Scotland, licensed under the Open Government "
    "Licence v3.0. Contains Ordnance Survey data \u00a9 Crown copyright and "
    "database right 2022."
)
NRS_SETTLEMENTS_SOURCE = (
    "National Records of Scotland, Settlements 2020 boundaries and mid-2020 "
    "populations, for Scottish stations"
)
# The ONS workbook's bands, read off its own table 1c: every Minor area is under
# 5,000 people, every Small one under 20,000, Medium under 75,000, Large under
# 200,000, and Major is the rest. A Scottish settlement takes the band its
# population would have had in England.
POPULATION_BANDS = ((5_000, "minor"), (20_000, "small"), (75_000, "medium"), (200_000, "large"))
LONDON_BAND = "major"

# The one file the boundaries are kept in, beside the feeds. CI restores it
# from actions/cache so twelve shards do not each ask the services (ADR-0081).
CACHE_FILE = "ons-boundaries.json"
CACHE_SCHEMA = 1
# Features asked for a request. The services allow 1000, but a page of 1000
# ONS areas was 13.6 MB, and the server cut one off after 15 KB; a page of 100
# is about a tenth of that, so a cut-off costs one small request again.
PAGE_SIZE = 100
# A station just outside its area's edge is still in the place: the boundary
# is drawn on a 25 m grid, and track and yard land is often left out of it, so
# Gathurst sits on the Shevington line and Whittlesea 17 m out of Whittlesey.
# Of the 79 unclassified GRA destinations outside every area, 14 sat within
# 100 m of one and 16 more within 500 m, where the station is a halt in the
# fields rather than the edge of the place (ADR-0080).
EDGE_TOLERANCE_M = 100.0
# Five tries over about a minute for a timeout, a dropped or cut-off response,
# a 5xx or a 429, then the build stops; any other refusal stops it at once.
ATTEMPTS = 5
FIRST_WAIT_S = 4.0
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_METRES_PER_DEGREE = 111_320.0
_USER_AGENT = "TrainBudgetExplorer/1.0 (station classification build)"

Ring = tuple[tuple[float, float], ...]


class BoundaryFeedMissing(RuntimeError):
    """The boundaries were needed and could not be read: the build stops.

    Not an OSError or a ValueError, so no classification handler that lets a
    source go quietly can catch it.
    """


@dataclass(frozen=True)
class Area:
    """One area: its code, its bounding box, and its rings as (lon, lat)."""

    code: str
    west: float
    south: float
    east: float
    north: float
    rings: tuple[Ring, ...]


@dataclass(frozen=True)
class Boundaries:
    """Every area the services gave, before any band is put on it.

    ``centres`` is each ONS area's own centre point (LONG, LAT), ``london`` the
    London region's rings, and ``populations`` each Scottish settlement's.
    """

    ons: tuple[Area, ...]
    centres: Mapping[str, tuple[float, float]]
    london: tuple[Ring, ...]
    scotland: tuple[Area, ...]
    populations: Mapping[str, float]


def band_for_population(population: float) -> str:
    for ceiling, band in POPULATION_BANDS:
        if population < ceiling:
            return band
    return "major"


def banded_areas(boundaries: Boundaries, workbook_bands: Mapping[str, str]) -> list[tuple[Area, str]]:
    """Each area with the band it is classed by; an area with none is left out."""
    banded: list[tuple[Area, str]] = []
    for area in boundaries.ons:
        band = workbook_bands.get(area.code)
        if band is None and area.code.startswith("E") and boundaries.london:
            centre = boundaries.centres.get(area.code)
            if centre and _inside(centre[0], centre[1], boundaries.london):
                band = LONDON_BAND
        if band:
            banded.append((area, band))
    for area in boundaries.scotland:
        banded.append((area, band_for_population(boundaries.populations[area.code])))
    return banded


def load_boundaries(
    cache: Path | None,
    *,
    opener: Callable[..., object] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Boundaries:
    """Read the boundaries from ``cache``, or fetch them and write it.

    Any failure is BoundaryFeedMissing. A cache that cannot be read is fetched
    again rather than trusted, and is replaced only by a complete fetch.
    """
    raw = None
    if cache is not None and cache.is_file():
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            if raw.get("schema") != CACHE_SCHEMA:
                raw = None
        except (OSError, ValueError, AttributeError):
            raw = None
    if raw is None:
        try:
            raw = fetch_raw(opener=opener, sleep=sleep)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise BoundaryFeedMissing(f"settlement boundaries could not be read: {error}") from error
        if cache is not None:
            temporary = cache.with_name(cache.name + ".tmp")
            temporary.write_text(json.dumps(raw, separators=(",", ":")), encoding="utf-8")
            os.replace(temporary, cache)
    try:
        return _boundaries(raw)
    except (KeyError, TypeError, ValueError) as error:
        raise BoundaryFeedMissing(f"settlement boundaries are malformed: {error}") from error


def fetch_raw(
    *,
    opener: Callable[..., object] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Fetch all three sets as the plain JSON the cache holds."""
    opener = opener or urllib.request.urlopen
    ons = [
        [str(attributes["BUA22CD"]), [float(attributes["LONG"]), float(attributes["LAT"])], rings]
        for attributes, rings in _features(
            ONS_BUA_BOUNDARIES_QUERY_URL,
            {"where": "BUA22CD NOT LIKE 'S%'", "outFields": "BUA22CD,LONG,LAT"},
            opener, sleep,
        )
    ]
    london = [
        rings
        for _attributes, rings in _features(
            ONS_REGIONS_QUERY_URL,
            {"where": f"RGN22CD = '{LONDON_REGION_CODE}'", "outFields": "RGN22CD"},
            opener, sleep,
        )
    ]
    scotland = [
        [str(attributes["code"]), float(attributes["pop"]), rings]
        for attributes, rings in _features(
            NRS_SETTLEMENTS_QUERY_URL,
            # About 20 m: the NRS shapes are drawn on postcode edges, finer than
            # the ONS 25 m grid, and a station is placed to 100 m.
            {"where": "1=1", "outFields": "code,pop", "maxAllowableOffset": "0.0002"},
            opener, sleep,
        )
    ]
    if not ons or len(london) != 1 or not scotland:
        raise ValueError(
            f"boundary services returned {len(ons)} ONS areas, {len(london)} London regions "
            f"and {len(scotland)} Scottish settlements"
        )
    return {"schema": CACHE_SCHEMA, "ons": ons, "london": london[0], "scotland": scotland}


def _features(url: str, fields: dict[str, str], opener, sleep) -> list[tuple[dict, list]]:
    found: list[tuple[dict, list]] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode({
            **fields,
            "outSR": "4326",
            "geometryPrecision": "5",
            "resultOffset": str(offset),
            "resultRecordCount": str(PAGE_SIZE),
            "f": "json",
        })
        page = _get_json(f"{url}?{query}", opener, sleep)
        if "error" in page:
            raise ValueError(f"{url} refused the query: {page['error']}")
        features = page.get("features") or []
        for feature in features:
            rings = (feature.get("geometry") or {}).get("rings") or []
            if rings:
                found.append((feature.get("attributes") or {}, rings))
        if not page.get("exceededTransferLimit") or not features:
            return found
        offset += len(features)


def _get_json(url: str, opener, sleep) -> dict:
    """One page as JSON, asked again on a passing fault; else BoundaryFeedMissing."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    wait = FIRST_WAIT_S
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with opener(request, timeout=120) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code not in _RETRYABLE_STATUS:
                raise BoundaryFeedMissing(f"settlement boundaries could not be read from {url}: {error}") from error
            cause: Exception = error
        # A cut-off body (IncompleteRead), a dropped connection, or JSON that
        # ends early because the body did is a passing fault like a timeout.
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as error:
            cause = error
        if attempt == ATTEMPTS:
            raise BoundaryFeedMissing(
                f"settlement boundaries could not be read from {url} after {ATTEMPTS} tries: "
                f"{type(cause).__name__}: {cause}"
            ) from cause
        sleep(wait)
        wait *= 2
    raise AssertionError("unreachable")


def _boundaries(raw: dict) -> Boundaries:
    ons: list[Area] = []
    centres: dict[str, tuple[float, float]] = {}
    for code, centre, rings in raw["ons"]:
        area = _area(code, rings)
        if area:
            ons.append(area)
            centres[code] = (float(centre[0]), float(centre[1]))
    london = _rings(raw["london"])
    scotland: list[Area] = []
    populations: dict[str, float] = {}
    for code, population, rings in raw["scotland"]:
        area = _area(code, rings)
        if area:
            scotland.append(area)
            populations[code] = float(population)
    return Boundaries(tuple(ons), centres, london, tuple(scotland), populations)


def _rings(rings: Iterable[Iterable[Iterable[float]]]) -> tuple[Ring, ...]:
    kept = tuple(tuple((float(x), float(y)) for x, y, *_ in ring) for ring in rings)
    return tuple(ring for ring in kept if len(ring) >= 3)


def _area(code: str, rings: Iterable[Iterable[Iterable[float]]]) -> Area | None:
    kept = _rings(rings)
    if not kept:
        return None
    xs = [x for ring in kept for x, _ in ring]
    ys = [y for ring in kept for _, y in ring]
    return Area(code, min(xs), min(ys), max(xs), max(ys), kept)


def _inside(lon: float, lat: float, rings: tuple[Ring, ...]) -> bool:
    """Even-odd ray test across every ring, so a hole is outside."""
    inside = False
    for ring in rings:
        previous = ring[-1]
        for point in ring:
            (x1, y1), (x2, y2) = previous, point
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                inside = not inside
            previous = point
    return inside


def _edge_distance_m(lon: float, lat: float, rings: tuple[Ring, ...]) -> float:
    """Metres from the point to the nearest edge, on a local flat projection."""
    scale_x = _METRES_PER_DEGREE * math.cos(math.radians(lat))
    best = math.inf
    for ring in rings:
        previous = ring[-1]
        for point in ring:
            ax, ay = (previous[0] - lon) * scale_x, (previous[1] - lat) * _METRES_PER_DEGREE
            bx, by = (point[0] - lon) * scale_x, (point[1] - lat) * _METRES_PER_DEGREE
            dx, dy = bx - ax, by - ay
            length = dx * dx + dy * dy
            t = 0.0 if length == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length))
            best = min(best, math.hypot(ax + t * dx, ay + t * dy))
            previous = point
    return best


def locate(
    points: Mapping[str, tuple[float, float]],
    areas: Iterable[Area],
    *,
    tolerance_m: float = EDGE_TOLERANCE_M,
) -> dict[str, str]:
    """Return station -> the code of the area it stands in, for ``points`` of (lat, lon).

    Inside an area wins. A point inside none takes the area whose edge is
    nearest, if that is within ``tolerance_m``. A point inside two (the
    generalised shapes can overlap by a grid cell) takes the first listed,
    which is stable across downloads of one release.
    """
    areas = list(areas)
    margin_lat = tolerance_m / _METRES_PER_DEGREE
    found: dict[str, str] = {}
    for crs, (lat, lon) in points.items():
        margin_lon = margin_lat / max(math.cos(math.radians(lat)), 1e-6)
        near: list[Area] = []
        for area in areas:
            if area.south - margin_lat <= lat <= area.north + margin_lat and area.west - margin_lon <= lon <= area.east + margin_lon:
                if area.south <= lat <= area.north and area.west <= lon <= area.east and _inside(lon, lat, area.rings):
                    found[crs] = area.code
                    break
                near.append(area)
        else:
            distances = [(_edge_distance_m(lon, lat, area.rings), area.code) for area in near]
            if distances:
                distance, code = min(distances)
                if distance <= tolerance_m:
                    found[crs] = code
    return found
