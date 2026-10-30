"""Placing a station in the settlement area it stands in (ADR-0080, ADR-0081)."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from trainbudget.fares import ons_boundaries
from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.fares.atoc_fares_loader import LOCATION_FALLBACK_SOURCE
from trainbudget.fares.atoc_fare_declarations import Location
from trainbudget.fares.ons_boundaries import (
    Area,
    BoundaryFeedMissing,
    Boundaries,
    band_for_population,
    banded_areas,
    load_boundaries,
    locate,
)


def _square(code: str, west: float, south: float, size: float, hole: float = 0.0) -> Area:
    outer = ((west, south), (west + size, south), (west + size, south + size), (west, south + size))
    rings = [outer]
    if hole:
        middle_x, middle_y = west + size / 2, south + size / 2
        rings.append((
            (middle_x - hole, middle_y - hole), (middle_x + hole, middle_y - hole),
            (middle_x + hole, middle_y + hole), (middle_x - hole, middle_y + hole),
        ))
    return Area(code, west, south, west + size, south + size, tuple(rings))


def _ring(west: float, south: float, size: float = 0.1) -> list:
    return [[west, south], [west + size, south], [west + size, south + size], [west, south + size]]


def _page(features, more: bool = False) -> io.BytesIO:
    return io.BytesIO(json.dumps({"features": features, "exceededTransferLimit": more}).encode())


def _services(ons_pages=None):
    """An opener answering the three services, the ONS one over ``ons_pages``."""
    ons_pages = iter(ons_pages or [[
        {"attributes": {"BUA22CD": "E1", "LONG": -0.95, "LAT": 53.05}, "geometry": {"rings": [_ring(-1.0, 53.0)]}},
    ]])
    seen: list[str] = []

    def opener(request, timeout=0):
        url = request.full_url
        seen.append(url)
        if url.startswith(ons_boundaries.ONS_REGIONS_QUERY_URL):
            return _page([{"attributes": {}, "geometry": {"rings": [_ring(-0.5, 51.3, 0.6)]}}])
        if url.startswith(ons_boundaries.NRS_SETTLEMENTS_QUERY_URL):
            return _page([{"attributes": {"code": "S1", "pop": 750}, "geometry": {"rings": [_ring(-4.0, 56.0)]}}])
        page = next(ons_pages)
        return _page(page)

    return opener, seen


class LocateTest(unittest.TestCase):
    def test_a_station_inside_an_area_takes_its_code(self) -> None:
        areas = [_square("E1", -1.0, 53.0, 0.1)]
        self.assertEqual(locate({"AAA": (53.05, -0.95)}, areas), {"AAA": "E1"})

    def test_a_hole_in_an_area_is_outside_it(self) -> None:
        areas = [_square("E1", -1.0, 53.0, 0.1, hole=0.02)]
        self.assertEqual(locate({"AAA": (53.05, -0.95)}, areas), {})

    def test_a_station_just_outside_the_edge_is_still_in_the_place(self) -> None:
        # About 50 m east of the edge at this latitude, then about 1 km east.
        areas = [_square("E1", -1.0, 53.0, 0.1)]
        near = -0.9 + 50 / (111_320 * 0.6018)
        far = -0.9 + 1000 / (111_320 * 0.6018)
        found = locate({"NEAR": (53.05, near), "FAR": (53.05, far)}, areas)
        self.assertEqual(found, {"NEAR": "E1"})


class BandTest(unittest.TestCase):
    def _boundaries(self) -> Boundaries:
        return Boundaries(
            ons=(
                _square("E63004793", -0.2, 51.55, 0.1),  # a borough, unbanded, inside London
                _square("E63009999", 1.0, 52.0, 0.1),  # unbanded, outside London
                _square("K08000001", -2.95, 53.15, 0.1),  # Chester, across the border
            ),
            centres={"E63004793": (-0.15, 51.6), "E63009999": (1.05, 52.05), "K08000001": (-2.9, 53.2)},
            london=(tuple((x, y) for x, y in _ring(-0.5, 51.3, 0.6)),),
            scotland=(_square("S1", -4.0, 56.0, 0.1), _square("S2", -3.0, 56.0, 0.1)),
            populations={"S1": 750.0, "S2": 250_000.0},
        )

    def test_london_boroughs_are_the_city_by_where_they_stand(self) -> None:
        bands = dict((area.code, band) for area, band in banded_areas(self._boundaries(), {"K08000001": "large"}))
        self.assertEqual(bands["E63004793"], "major")
        self.assertNotIn("E63009999", bands, "unbanded outside London stays unbanded")

    def test_a_cross_border_area_keeps_its_workbook_band(self) -> None:
        bands = dict((area.code, band) for area, band in banded_areas(self._boundaries(), {"K08000001": "large"}))
        self.assertEqual(bands["K08000001"], "large")

    def test_scottish_settlements_take_the_band_their_population_would(self) -> None:
        bands = dict((area.code, band) for area, band in banded_areas(self._boundaries(), {}))
        self.assertEqual((bands["S1"], bands["S2"]), ("minor", "major"))
        self.assertEqual(
            [band_for_population(n) for n in (4_999, 5_000, 19_999, 20_000, 74_999, 75_000, 199_999, 200_000)],
            ["minor", "small", "small", "medium", "medium", "large", "large", "major"],
        )


class LoadBoundariesTest(unittest.TestCase):
    def test_a_fetch_is_cached_and_the_cache_asks_nothing(self) -> None:
        opener, seen = _services()
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / ons_boundaries.CACHE_FILE
            first = load_boundaries(cache, opener=opener, sleep=lambda _s: None)
            asked = len(seen)
            again = load_boundaries(cache, opener=opener, sleep=lambda _s: None)
        self.assertEqual(asked, 3)
        self.assertEqual(len(seen), 3, "the second read came from the cache")
        self.assertEqual(again, first)
        self.assertIn("BUA22CD+NOT+LIKE+%27S%25%27", seen[0], "every ONS area, K codes too")

    def test_pages_are_followed(self) -> None:
        feature = lambda code: {"attributes": {"BUA22CD": code, "LONG": 0, "LAT": 0}, "geometry": {"rings": [_ring(0, 0)]}}
        pages = iter([_page([feature("E1"), feature("K2")], more=True), _page([feature("W3")])])
        seen: list[str] = []

        def opener(request, timeout=0):
            seen.append(request.full_url)
            if request.full_url.startswith(ons_boundaries.ONS_BUA_BOUNDARIES_QUERY_URL):
                return next(pages)
            return _services()[0](request, timeout)

        boundaries = load_boundaries(None, opener=opener)
        self.assertEqual([area.code for area in boundaries.ons], ["E1", "K2", "W3"])
        self.assertIn("resultOffset=2", seen[1])

    def test_a_busy_service_is_asked_again(self) -> None:
        opener, seen = _services()
        busy = [urllib.error.HTTPError("u", 429, "busy", {}, None), urllib.error.URLError("reset")]
        waits: list[float] = []

        def flaky(request, timeout=0):
            if busy:
                raise busy.pop(0)
            return opener(request, timeout)

        load_boundaries(None, opener=flaky, sleep=waits.append)
        self.assertEqual(waits, [4.0, 8.0])

    def test_a_service_that_stays_down_stops_the_build(self) -> None:
        def down(request, timeout=0):
            raise urllib.error.HTTPError("u", 503, "down", {}, None)

        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / ons_boundaries.CACHE_FILE
            with self.assertRaises(BoundaryFeedMissing):
                load_boundaries(cache, opener=down, sleep=lambda _s: None)
            self.assertFalse(cache.exists(), "no partial cache is left")
        self.assertNotIsInstance(BoundaryFeedMissing("x"), (OSError, ValueError))

    def test_a_refused_query_stops_the_build_at_once(self) -> None:
        calls = []

        def refuse(request, timeout=0):
            calls.append(1)
            return io.BytesIO(json.dumps({"error": {"code": 400}}).encode())

        with self.assertRaises(BoundaryFeedMissing):
            load_boundaries(None, opener=refuse, sleep=lambda _s: None)
        self.assertEqual(len(calls), 1)


class PositionPassTest(unittest.TestCase):
    """The pass after the names: it fills only what nothing else classified."""

    def _db(self) -> FaresDb:
        db = FaresDb()
        db.locations_by_crs = {
            "AAP": Location("1", "AAP", "ALEXANDRA PALACE", ""),
            "RVW": Location("2", "RVW", "REVIEWED HALT", ""),
            "FLD": Location("3", "FLD", "FIELD HALT", ""),
            "DRM": Location("4", "DRM", "DREM", ""),
        }
        db.location_types_by_crs = {"RVW": "village"}
        db._station_coordinates = {
            "AAP": (53.05, -0.95), "RVW": (53.06, -0.95), "FLD": (50.0, 0.0), "DRM": (56.05, -2.95),
        }
        return db

    def _boundaries(self) -> Boundaries:
        return Boundaries(
            ons=(_square("E1", -1.0, 53.0, 0.1),), centres={"E1": (-0.95, 53.05)}, london=(),
            scotland=(_square("S1", -3.0, 56.0, 0.1),), populations={"S1": 30_000.0},
        )

    def test_a_station_in_a_banded_area_takes_the_area_band(self) -> None:
        db = self._db()
        with mock.patch.object(ons_boundaries, "load_boundaries", return_value=self._boundaries()):
            db._classify_by_position([("E1", "Haringey", "major")])
        self.assertEqual(db.location_types_by_crs["AAP"], "city")
        self.assertEqual(db.location_types_by_crs["DRM"], "town")
        self.assertEqual(db.ons_position_classified_crs, {"AAP", "DRM"})
        self.assertNotIn("FLD", db.location_types_by_crs, "outside every area stays unclassified")
        self.assertIn(ons_boundaries.ONS_BUA_BOUNDARIES_SOURCE, db.location_type_sources)
        self.assertIn(ons_boundaries.NRS_SETTLEMENTS_SOURCE, db.location_type_sources)

    def test_a_class_already_given_is_kept(self) -> None:
        # The reviewed lists and the names run first (ADR-0029); the area the
        # reviewed halt stands in must not move it.
        db = self._db()
        with mock.patch.object(ons_boundaries, "load_boundaries", return_value=self._boundaries()):
            db._classify_by_position([("E1", "Haringey", "major")])
        self.assertEqual(db.location_types_by_crs["RVW"], "village")
        self.assertNotIn("RVW", db.ons_position_classified_crs)
        self.assertNotIn(LOCATION_FALLBACK_SOURCE, db.location_type_sources)

    def test_a_workbook_without_codes_asks_the_service_nothing(self) -> None:
        db = self._db()
        with mock.patch.object(ons_boundaries, "load_boundaries") as load:
            db._classify_by_position([("", "Haringey", "major")])
        load.assert_not_called()
        self.assertNotIn("AAP", db.location_types_by_crs)

    def test_boundaries_that_cannot_be_read_stop_the_build(self) -> None:
        db = self._db()
        with mock.patch.object(ons_boundaries, "load_boundaries", side_effect=BoundaryFeedMissing("down")):
            with self.assertRaises(BoundaryFeedMissing):
                db._classify_by_position([("E1", "Haringey", "major")])


if __name__ == "__main__":
    unittest.main()
