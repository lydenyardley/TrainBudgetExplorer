"""Placing a station in the ONS built-up area it stands in (ADR-0080)."""

from __future__ import annotations

import io
import json
import unittest
from unittest import mock

from trainbudget.fares import ons_boundaries
from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.fares.atoc_fares_loader import LOCATION_FALLBACK_SOURCE
from trainbudget.fares.atoc_fare_declarations import Location
from trainbudget.fares.ons_boundaries import Area, fetch_areas, locate


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


def _page(features, more: bool) -> io.BytesIO:
    return io.BytesIO(json.dumps({"features": features, "exceededTransferLimit": more}).encode())


def _feature(code: str, west: float, south: float) -> dict:
    ring = [[west, south], [west + 0.1, south], [west + 0.1, south + 0.1], [west, south + 0.1]]
    return {"attributes": {"BUA22CD": code}, "geometry": {"rings": [ring]}}


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


class FetchAreasTest(unittest.TestCase):
    def test_pages_are_followed_and_only_the_banded_codes_kept(self) -> None:
        pages = iter([
            _page([_feature("E1", -1.0, 53.0), _feature("E2", 0.0, 52.0)], more=True),
            _page([_feature("W3", -3.0, 52.0)], more=False),
        ])
        seen = []

        def opener(request, timeout=0):
            seen.append(request.full_url)
            return next(pages)

        areas = fetch_areas({"E1", "W3"}, opener=opener)
        self.assertEqual([area.code for area in areas], ["E1", "W3"])
        self.assertIn("resultOffset=0", seen[0])
        self.assertIn("resultOffset=2", seen[1])

    def test_a_refused_query_is_an_error_not_an_empty_country(self) -> None:
        def opener(request, timeout=0):
            return io.BytesIO(json.dumps({"error": {"code": 400}}).encode())

        with self.assertRaises(ValueError):
            fetch_areas({"E1"}, opener=opener)


class PositionPassTest(unittest.TestCase):
    """The pass after the names: it fills only what nothing else classified."""

    def _db(self) -> FaresDb:
        db = FaresDb()
        db.locations_by_crs = {
            "AAP": Location("1", "AAP", "ALEXANDRA PALACE", ""),
            "RVW": Location("2", "RVW", "REVIEWED HALT", ""),
            "FLD": Location("3", "FLD", "FIELD HALT", ""),
        }
        db.location_types_by_crs = {"RVW": "village"}
        db._station_coordinates = {
            "AAP": (53.05, -0.95), "RVW": (53.06, -0.95), "FLD": (50.0, 0.0),
        }
        return db

    def test_a_station_in_a_banded_area_takes_the_area_band(self) -> None:
        db = self._db()
        with mock.patch.object(
            ons_boundaries, "fetch_areas", return_value=[_square("E1", -1.0, 53.0, 0.1)]
        ):
            db._classify_by_position([("E1", "Haringey", "major")])
        self.assertEqual(db.location_types_by_crs["AAP"], "city")
        self.assertEqual(db.ons_position_classified_crs, {"AAP"})
        self.assertNotIn("FLD", db.location_types_by_crs, "outside every area stays unclassified")
        self.assertIn(ons_boundaries.ONS_BUA_BOUNDARIES_SOURCE, db.location_type_sources)

    def test_a_class_already_given_is_kept(self) -> None:
        # The reviewed lists and the names run first (ADR-0029); the area the
        # reviewed halt stands in must not move it.
        db = self._db()
        with mock.patch.object(
            ons_boundaries, "fetch_areas", return_value=[_square("E1", -1.0, 53.0, 0.1)]
        ):
            db._classify_by_position([("E1", "Haringey", "major")])
        self.assertEqual(db.location_types_by_crs["RVW"], "village")
        self.assertNotIn("RVW", db.ons_position_classified_crs)
        self.assertNotIn(LOCATION_FALLBACK_SOURCE, db.location_type_sources)

    def test_a_workbook_without_codes_asks_the_service_nothing(self) -> None:
        db = self._db()
        with mock.patch.object(ons_boundaries, "fetch_areas") as fetch:
            db._classify_by_position([("", "Haringey", "major")])
        fetch.assert_not_called()
        self.assertNotIn("AAP", db.location_types_by_crs)


if __name__ == "__main__":
    unittest.main()
