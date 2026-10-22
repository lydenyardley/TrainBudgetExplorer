"""Fares filed under a station's fare group (ADR-0074).

RSPS5045 4.19.2 gives each location a FARE_GROUP, and a flow whose origin or
destination is that group code is a fare from or to every member station. The
24 September 2026 feed files 459 flows under FARNBOROUGH STNS (0260) and one,
to Waterloo, under Farnborough Main's own code, so the station's page priced one
destination. The fixture below is that shape in miniature: two member stations,
a group with no station code of its own, and London Terminals (1072), the group
the query deliberately does not read through.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atoc_fares import FLOW_F, FLOW_T, LOCATION, TICKET_TYPE, FaresDb
from make_synthetic_feed import _line, build_synthetic_feed

GROUP_STATIONS = (
    # (nlc, crs, name, group)
    ("0260", "", "FARNBOROUGH STNS", ""),
    ("5521", "FNB", "FARNBOROUGH MAIN", "0260"),
    ("5688", "FNN", "FARNBOROUGH NORTH", "0260"),
    ("1072", "", "LONDON TERMINALS", ""),
    ("5100", "EUS", "LONDON EUSTON", "1072"),
)

# (flow id, origin, destination, direction, ((ticket, pence), ...))
GROUP_FLOWS = (
    # A group-only flow: neither member has a fare of its own to Grantham.
    ("0000201", "0260", "1000", "", (("SDR", 700),)),
    # An own flow dearer than the group's: the group fare wins for FNB.
    ("0000202", "5521", "1000", "", (("SDR", 900),)),
    # An own flow cheaper than the group's: it wins for FNB, and FNN, which
    # has no own flow, takes the group fare.
    ("0000203", "5521", "2000", "", (("SDR", 300),)),
    ("0000204", "0260", "2000", "", (("SDR", 500),)),
    # The destination side: a fare to the group reaches each member.
    ("0000205", "1000", "0260", "", (("SDR", 650),)),
    # A reversible group flow, entered from either end.
    ("0000206", "3000", "0260", "R", (("SDR", 450),)),
    # Exclusions ride on group fares too: a 5p ITX placeholder must not win
    # Peterborough, and a sentinel price must not price First Only at all.
    ("0000207", "0260", "4000", "", (("EIS", 5), ("SDR", 2000))),
    ("0000208", "0260", "6000", "", (("SDR", 99_999),)),
    # London Terminals is not read through, in either direction.
    ("0000209", "1072", "1000", "", (("SDR", 100),)),
    ("0000210", "1000", "1072", "", (("SDR", 100),)),
)


def build_group_feed(path: Path) -> Path:
    feed = build_synthetic_feed(path)
    with (feed / "rjfaf.loc").open("a", encoding="utf-8") as handle:
        for nlc, crs, name, group in GROUP_STATIONS:
            values = {"update_marker": "A", "record_type": "L", "nlc": nlc, "description": name, "crs": crs}
            if group:
                values["group_nlc"] = group
            handle.write(_line(values, LOCATION) + "\n")
    with (feed / "rjfaf.tty").open("a", encoding="utf-8") as handle:
        handle.write(
            _line(
                {
                    "update_marker": "A",
                    "ticket_code": "EIS",
                    "description": "ITX STD R",
                    "tkt_class": "2",
                    "tkt_type": "R",
                    "restricted_by_train": "0",
                },
                TICKET_TYPE,
            )
            + "\n"
        )
    with (feed / "rjfaf.ffl").open("a", encoding="utf-8") as handle:
        for flow_id, origin, destination, direction, fares in GROUP_FLOWS:
            values = {
                "update_marker": "A",
                "record_type": "F",
                "origin_nlc": origin,
                "destination_nlc": destination,
                "route_code": "00000",
                "flow_id": flow_id,
            }
            if direction:
                values["direction"] = direction
            handle.write(_line(values, FLOW_F) + "\n")
            for ticket, pence in fares:
                handle.write(
                    _line(
                        {
                            "update_marker": "A",
                            "record_type": "T",
                            "flow_id": flow_id,
                            "ticket_code": ticket,
                            "fare_pence": str(pence),
                        },
                        FLOW_T,
                    )
                    + "\n"
                )
    return feed


def prices(rows) -> dict[str, int]:
    return {row.crs: row.best_pence for row in rows}


class FareGroupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_group_feed(Path(cls._tmp.name) / "groups")
        cls.db = FaresDb().load_feed(cls.feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def from_(self, crs: str, db: FaresDb | None = None) -> dict[str, int]:
        return prices((db or self.db).destinations_within(crs, 1_000_000))

    def test_a_group_only_flow_prices_every_member(self) -> None:
        self.assertEqual(self.from_("FNB")["GRN"], 700)
        self.assertEqual(self.from_("FNN")["GRN"], 700)

    def test_the_cheapest_of_own_and_group_fares_wins(self) -> None:
        self.assertEqual(self.from_("FNB")["NOT"], 300)
        self.assertEqual(self.from_("FNN")["NOT"], 500)

    def test_a_fare_to_the_group_reaches_each_member(self) -> None:
        grantham = self.from_("GRN")
        self.assertEqual(grantham["FNB"], 650)
        self.assertEqual(grantham["FNN"], 650)

    def test_a_reversible_group_flow_works_from_either_end(self) -> None:
        self.assertEqual(self.from_("FNB")["LCN"], 450)
        self.assertEqual(self.from_("FNN")["LCN"], 450)
        lincoln = self.from_("LCN")
        self.assertEqual((lincoln["FNB"], lincoln["FNN"]), (450, 450))

    def test_a_member_is_not_its_own_destination(self) -> None:
        self.assertNotIn("FNB", self.from_("FNB"))
        self.assertNotIn("FNN", self.from_("FNB"))

    def test_page_exclusions_apply_to_group_fares(self) -> None:
        page = prices(self.db.page_destinations_within("FNB", 1_000_000))
        self.assertEqual(page["PBO"], 2000)
        self.assertNotIn("XFD", page)
        self.assertEqual(page["GRN"], 700)

    def test_london_terminals_is_not_read_through(self) -> None:
        self.assertNotIn("GRN", self.from_("EUS"))
        self.assertNotIn("EUS", self.from_("GRN"))
        self.assertNotIn("1072", self.db.fare_nlcs("EUS"))

    def test_change_stations_include_group_destinations(self) -> None:
        self.assertTrue({"GRN", "NOT", "LCN"} <= self.db.interchange_crs("FNN"))
        self.assertTrue({"FNB", "FNN"} <= self.db.interchange_crs("GRN"))

    def test_a_focused_load_keeps_the_group_fares(self) -> None:
        focused = FaresDb().load_feed(self.feed, focus_origin="FNN")
        self.assertEqual(self.from_("FNN", focused)["GRN"], 700)
        self.assertEqual(self.from_("FNN", focused), self.from_("FNN"))

    def test_a_page_built_from_the_index_keeps_the_group_fares(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            common = Path(tmp) / "common.pickle"
            self.db.write_fare_indexes(common, Path(tmp) / "origins", ["FNN"])
            restored = FaresDb.load_fare_index(common, Path(tmp) / "origins" / "FNN.pickle")
        self.assertEqual(self.from_("FNN", restored)["GRN"], 700)
        self.assertEqual(self.from_("FNN", restored), self.from_("FNN"))

    def test_the_audit_names_the_stations_only_a_group_prices(self) -> None:
        coverage = self.db.fare_coverage_audit()
        self.assertEqual(coverage["groupCodes"], 1)
        self.assertEqual(coverage["unexpandedGroupFareFlows"], 2)
        self.assertEqual(
            {row["crs"] for row in coverage["sampleStationsPricedOnlyThroughGroup"]},
            {"FNN"},
        )


if __name__ == "__main__":
    unittest.main()
