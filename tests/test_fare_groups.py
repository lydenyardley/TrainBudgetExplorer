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

from datetime import date

from trainbudget.fares.atoc_fares import FLOW_F, FLOW_T, LOCATION, STATION_CLUSTER, TICKET_TYPE, FaresDb
from trainbudget.feeds.make_synthetic_feed import _line, build_synthetic_feed

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

    def test_newly_priced_group_member_destinations_carry_their_settlement_class(self) -> None:
        # O22: reading through station groups newly prices 17 destinations on
        # the real feed, 12 of which had no settlement class from the ONS name
        # lookup because of a station qualifier or because they sit in London or
        # Scotland. All 12 are classified in REVIEWED_SETTLEMENT_FALLBACKS so
        # group-NLC expansion adds zero unsourced priced destinations.
        expected = {
            "CFB": ("5047", "CATFORD BRIDGE", "0258", "city"),
            "DCW": ("5962", "DORCHESTER WEST", "0429", "town"),
            "GCL": ("9922", "GLASGOW CENT LL", "0433", "city"),
            "GLQ": ("9950", "GLASGOW QUEEN ST", "0433", "city"),
            "GNB": ("6465", "GAINSBOROUGH CTL", "0415", "town"),
            "HLC": ("9981", "HELENSBURGH CTL", "0404", "small_town"),
            "HLU": ("9982", "HELENSBURGH UPP", "0404", "small_town"),
            "LVL": ("2270", "LIVERPOOL L S LL", "0435", "city"),
            "TNN": ("6530", "THORNE NORTH", "0271", "small_town"),
            "TYL": ("8728", "TYNDRUM LOWER", "0443", "village"),
            "UTY": ("8838", "UPPER TYNDRUM", "0443", "village"),
            "WGW": ("2406", "WIGAN WALLGATE", "0446", "city"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "o22")
            with (feed / "rjfaf.loc").open("a", encoding="utf-8") as handle:
                for crs, (nlc, name, group, _) in expected.items():
                    handle.write(
                        _line(
                            {
                                "update_marker": "A",
                                "record_type": "L",
                                "nlc": nlc,
                                "description": name,
                                "crs": crs,
                                "group_nlc": group,
                            },
                            LOCATION,
                        )
                        + "\n"
                    )
            db = FaresDb().load_feed(feed)
        self.assertEqual(
            {crs: db.destination_type(crs) for crs in expected},
            {crs: kind for crs, (_, _, _, kind) in expected.items()},
        )


CLUSTER_ROWS = (
    # (update_marker, cluster_id, member_nlc, start_date, end_date)
    # Q001 groups Farnborough North (5688) and Lincoln (3000) directly.
    ("A", "Q001", "5688", "01012026", "31122999"),
    ("A", "Q001", "3000", "01012026", "31122999"),
    # Q002 groups London Kings Cross (5000) directly.
    ("A", "Q002", "5000", "01012026", "31122999"),
    # Q003 holds the station group 0260 (Farnborough Stns -> FNB, FNN) and
    # London Terminals 1072 (which must remain unexpanded even inside a cluster).
    ("A", "Q003", "0260", "01012026", "31122999"),
    ("A", "Q003", "1072", "01012026", "31122999"),
    # Q004 has an expired row and a future row around 2026-09-24.
    ("A", "Q004", "5521", "01012025", "31082026"),
    ("A", "Q004", "5521", "01112026", "31122999"),
    # Q005 adds then deletes a member with marker D.
    ("A", "Q005", "5521", "01012026", "31122999"),
    ("D", "Q005", "5521", "01012026", "31122999"),
)

# (flow id, origin, destination, direction, route, ((ticket, pence), ...))
CLUSTER_FLOWS = (
    # Cluster-to-cluster reversible flow: FNN/LCN <-> KGX at 1200p.
    ("0000301", "Q001", "Q002", "R", "00001", (("SDR", 1200),)),
    # Cluster containing a station group (Q003 -> 0260 -> FNB, FNN) to NOT (2000).
    # At 400p: cheaper than group 0260's 500p for FNN, dearer than FNB's own 300p.
    ("0000302", "Q003", "2000", "", "00002", (("SDR", 400),)),
    # Precedence tie-break to GRN (1000): group 0260 prices GRN at 700p on
    # route 00000; Q003 also prices GRN at 700p on route 00099. Group precedes
    # cluster, so the tie keeps route 00000.
    ("0000303", "Q003", "1000", "", "00099", (("SDR", 700),)),
    # Exclusions on a cluster flow: Caledonian Sleeper 1ZB/1ZE staff 10p codes
    # and ITX placeholder EIS must be rejected in favour of the public fare.
    ("0000304", "Q001", "4000", "", "00003", (("1ZB", 10), ("1ZE", 10), ("EIS", 5), ("SDR", 1500))),
    # Windowed cluster Q004 to Skegness (8200): only active outside Sep/Oct 2026.
    ("0000305", "Q004", "8200", "", "00004", (("SDR", 800),)),
    # Deleted cluster Q005 to Skegness (8200): never active.
    ("0000306", "Q005", "8200", "", "00005", (("SDR", 250),)),
)


def build_cluster_feed(path: Path) -> Path:
    feed = build_group_feed(path)
    with (feed / "rjfaf.loc").open("a", encoding="utf-8") as handle:
        handle.write(
            _line(
                {
                    "update_marker": "A",
                    "record_type": "L",
                    "nlc": "8200",
                    "description": "SKEGNESS",
                    "crs": "SKG",
                },
                LOCATION,
            )
            + "\n"
        )
    with (feed / "rjfaf.tty").open("a", encoding="utf-8") as handle:
        for code, desc in (("1ZB", "CS F&F CC SO"), ("1ZE", "CS LEISURE CC S")):
            handle.write(
                _line(
                    {
                        "update_marker": "A",
                        "ticket_code": code,
                        "description": desc,
                        "tkt_class": "2",
                        "tkt_type": "R",
                        "restricted_by_train": "0",
                    },
                    TICKET_TYPE,
                )
                + "\n"
            )
    with (feed / "rjfaf.fsc").open("w", encoding="utf-8") as handle:
        for marker, cid, member, start_d, end_d in CLUSTER_ROWS:
            handle.write(
                _line(
                    {
                        "update_marker": marker,
                        "cluster_id": cid,
                        "cluster_nlc": member,
                        "end_date": end_d,
                        "start_date": start_d,
                    },
                    STATION_CLUSTER,
                )
                + "\n"
            )
    with (feed / "rjfaf.ffl").open("a", encoding="utf-8") as handle:
        for flow_id, origin, destination, direction, route, fares in CLUSTER_FLOWS:
            values = {
                "update_marker": "A",
                "record_type": "F",
                "origin_nlc": origin,
                "destination_nlc": destination,
                "route_code": route,
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


class FareClusterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.feed = build_cluster_feed(Path(cls._tmp.name) / "clusters")
        cls.db = FaresDb().load_feed(cls.feed)
        cls.day = date(2026, 9, 24)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def from_(self, crs: str, db: FaresDb | None = None, day: date | None = None) -> dict[str, int]:
        return prices((db or self.db).page_destinations_within(crs, 1_000_000, day=day or self.day))

    def test_cluster_to_cluster_reversible_flow_prices_both_ends(self) -> None:
        self.assertEqual(self.from_("FNN")["KGX"], 1200)
        self.assertEqual(self.from_("KGX")["FNN"], 1200)
        self.assertEqual(self.from_("KGX")["LCN"], 1200)

    def test_cluster_containing_a_station_group_reaches_every_group_member(self) -> None:
        # Q003 holds group 0260 (FNB, FNN). To NOT: FNB keeps its cheaper own
        # 300p fare; FNN drops from group 0260's 500p to cluster Q003's 400p.
        self.assertEqual(self.from_("FNB")["NOT"], 300)
        self.assertEqual(self.from_("FNN")["NOT"], 400)

    def test_precedence_keeps_group_over_cluster_when_prices_tie(self) -> None:
        rows = {
            row.crs: row
            for row in self.db.page_destinations_within("FNN", 1_000_000, day=self.day)
        }
        self.assertEqual(rows["GRN"].best_pence, 700)
        self.assertEqual(rows["GRN"].route_code, "00000")

    def test_london_terminals_is_not_expanded_even_inside_a_cluster(self) -> None:
        self.assertNotIn("1072", self.db.fare_nlcs("EUS", day=self.day))
        self.assertNotIn("Q003", self.db.fare_nlcs("EUS", day=self.day))
        self.assertNotIn("EUS", self.db.stations_for_fare_nlc("Q003", day=self.day))
        self.assertNotIn("NOT", self.from_("EUS"))

    def test_cluster_validity_window_and_delete_marker_are_respected(self) -> None:
        # On 2026-09-24, Q004 is between its expired and future windows, and
        # Q005 was deleted by marker D.
        self.assertNotIn("SKG", self.from_("FNB", day=date(2026, 9, 24)))
        # Inside the earlier or later Q004 window, FNB reaches SKG at 800p.
        self.assertEqual(self.from_("FNB", day=date(2026, 8, 15))["SKG"], 800)
        self.assertEqual(self.from_("FNB", day=date(2026, 11, 15))["SKG"], 800)

    def test_exclusions_and_rejection_tallies_apply_to_cluster_fares(self) -> None:
        tally: dict[str, int] = {}
        rows = {
            row.crs: row
            for row in self.db.page_destinations_within(
                "FNN", 1_000_000, day=self.day, tally=tally
            )
        }
        self.assertEqual(rows["PBO"].best_pence, 1500)
        self.assertGreaterEqual(tally.get("ticket_is_a_catalogue_placeholder", 0), 2)
        self.assertGreaterEqual(tally.get("ticket_is_not_one_a_reader_can_buy", 0), 2)

    def test_focused_load_and_fare_index_preserve_cluster_fares(self) -> None:
        focused = FaresDb().load_feed(self.feed, focus_origin="FNN")
        self.assertEqual(self.from_("FNN", focused), self.from_("FNN"))
        with tempfile.TemporaryDirectory() as tmp:
            common = Path(tmp) / "common.pickle"
            self.db.write_fare_indexes(common, Path(tmp) / "origins", ["FNN"])
            restored = FaresDb.load_fare_index(common, Path(tmp) / "origins" / "FNN.pickle")
        self.assertEqual(self.from_("FNN", restored), self.from_("FNN"))

    def test_coverage_audit_reports_active_clusters_and_cluster_flows(self) -> None:
        coverage = self.db.fare_coverage_audit(day=self.day)
        self.assertEqual(coverage["clusterCodes"], 4)
        self.assertEqual(coverage["clusterMemberships"], 5)
        self.assertEqual(coverage["stationsInClusters"], 4)
        self.assertEqual(coverage["clusterFareFlows"], 5)

    def test_newly_priced_cluster_stations_carry_settlement_classes(self) -> None:
        expected = {
            "BFA": ("9001", "BELFAST PORT", "city"),
            "BFC": ("9002", "BELFAST CEN NI", "city"),
            "COK": ("9003", "CORK CIE", "city"),
            "DCL": ("9004", "DUBLIN CONNOLLY", "city"),
            "DHT": ("9005", "DUBLIN HEUSTON", "city"),
            "GWY": ("9006", "GALWAY CIE", "city"),
            "SFS": ("9007", "SOUTHFIELDS UND", "city"),
            "STI": ("9008", "STADIUM OF LIGHT", "city"),
            "STZ": ("9009", "ST PETERS METRO", "city"),
            "WPK": ("9010", "WIMBLEDON PK UND", "city"),
            "ANM": ("9011", "ANTRIM NI", "town"),
            "CBZ": ("9012", "CORBY BUS", "town"),
            "FEG": ("9013", "FELLGATE METRO", "town"),
            "KEZ": ("9014", "KETTERING BUS", "town"),
            "SLI": ("9015", "SLIGO CIE", "town"),
            "CGT": ("9016", "GALASHIELS V BWK", "small_town"),
            "HVH": ("9017", "HOEK VAN HOLLAND", "small_town"),
            "PTS": ("9018", "PORTRUSH NI", "small_town"),
            "WPT": ("9019", "WESTPORT CIE", "small_town"),
            "ATM": ("9020", "ATTYMON CIE", "village"),
            "BFB": ("9021", "BEAUFORT BUS", "village"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "o21")
            with (feed / "rjfaf.loc").open("a", encoding="utf-8") as handle:
                for crs, (nlc, name, _) in expected.items():
                    handle.write(
                        _line(
                            {
                                "update_marker": "A",
                                "record_type": "L",
                                "nlc": nlc,
                                "description": name,
                                "crs": crs,
                            },
                            LOCATION,
                        )
                        + "\n"
                    )
            db = FaresDb().load_feed(feed)
        self.assertEqual(
            {crs: db.destination_type(crs) for crs in expected},
            {crs: kind for crs, (_, _, kind) in expected.items()},
        )


if __name__ == "__main__":
    unittest.main()
