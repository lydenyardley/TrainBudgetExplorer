"""Find the ONS built-up area a station stands in, from the area boundaries.

The name match in the loader classifies a station whose name is a settlement's
name. A station named for a district, a street or a landmark -- Alexandra
Palace, Ardwick, Kirkstall Forge -- matched nothing, though it stands inside a
built-up area the workbook bands. This module answers the other question: which
area is the station *in*. The band is still the workbook's, joined on the area
code (ADR-0080).

Standard library only. The boundaries are read once from the ONS Open Geography
portal's feature service as plain polygons, and a station is placed by an
even-odd ray test. Centroid-plus-radius was rejected: the areas run from a
hamlet of a few hundred metres to Greater Manchester's tens of kilometres, so
no one radius is right, and a radius per area is a circle standing in for a
shape the service already gives exactly.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

# Built Up Areas (December 2022) Boundaries GB BGG: the generalised 25 m grid
# version, the same 2022 areas the Census 2021 workbook's BUA22CD column names.
# Source: Office for National Statistics licensed under the Open Government
# Licence v3.0. Contains OS data (c) Crown copyright and database right 2022.
ONS_BUA_BOUNDARIES_DATASET_URL = (
    "https://geoportal.statistics.gov.uk/datasets/ons::built-up-areas-december-2022-boundaries-gb-bgg"
)
ONS_BUA_BOUNDARIES_QUERY_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "BUA_2022_GB/FeatureServer/0/query"
)
ONS_BUA_BOUNDARIES_ATTRIBUTION = (
    "Source: Office for National Statistics licensed under the Open Government "
    "Licence v3.0. Contains OS data \u00a9 Crown copyright and database right 2022."
)
ONS_BUA_BOUNDARIES_SOURCE = (
    "Office for National Statistics, Built Up Areas (December 2022) boundaries, "
    "for stations whose name is not their settlement's"
)
# The service returns at most this many features a request.
PAGE_SIZE = 1000
# A station just outside its area's edge is still in the place: the boundary
# is drawn on a 25 m grid, and track and yard land is often left out of it, so
# Gathurst sits on the Shevington line and Whittlesea 17 m out of Whittlesey.
# Of the 79 unclassified GRA destinations outside every area, 14 sat within
# 100 m of one and 16 more within 500 m, where the station is a halt in the
# fields rather than the edge of the place (ADR-0080).
EDGE_TOLERANCE_M = 100.0
_METRES_PER_DEGREE = 111_320.0

Ring = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Area:
    """One built-up area: its code, its bounding box, and its rings as (lon, lat)."""

    code: str
    west: float
    south: float
    east: float
    north: float
    rings: tuple[Ring, ...]


def fetch_areas(
    codes: Iterable[str],
    *,
    opener: Callable[..., object] | None = None,
) -> list[Area]:
    """Read the boundaries of the England and Wales areas, a page at a time.

    Only England and Wales are asked for: the workbook that bands an area stops
    at the Scottish border, so a Scottish boundary could place a station and
    still give it no class. ``codes`` limits the result to the areas the
    workbook bands.
    """
    wanted = set(codes)
    opener = opener or urllib.request.urlopen
    areas: list[Area] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode({
            "where": "BUA22CD LIKE 'E%' OR BUA22CD LIKE 'W%'",
            "outFields": "BUA22CD",
            "outSR": "4326",
            "geometryPrecision": "5",
            "orderByFields": "OBJECTID",
            "resultOffset": str(offset),
            "resultRecordCount": str(PAGE_SIZE),
            "f": "json",
        })
        request = urllib.request.Request(
            f"{ONS_BUA_BOUNDARIES_QUERY_URL}?{query}",
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with opener(request, timeout=120) as response:
            page = json.loads(response.read())
        if "error" in page:
            raise ValueError(f"ONS boundary service refused the query: {page['error']}")
        features = page.get("features") or []
        for feature in features:
            code = str((feature.get("attributes") or {}).get("BUA22CD") or "")
            if code in wanted:
                area = _area(code, (feature.get("geometry") or {}).get("rings") or ())
                if area:
                    areas.append(area)
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
    if not areas:
        raise ValueError("ONS boundary service returned no banded built-up areas")
    return areas


def _area(code: str, rings: Iterable[Iterable[Iterable[float]]]) -> Area | None:
    kept = tuple(tuple((float(x), float(y)) for x, y, *_ in ring) for ring in rings)
    kept = tuple(ring for ring in kept if len(ring) >= 3)
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
    generalised shapes can overlap by a grid cell) takes the first the service
    listed, which is stable across downloads of one release.
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