"""Write small synthetic feeds so the parsers can be exercised without a licence.

Every station, flow, price, and train here is invented. The fixtures exist to
prove the parsers read the real record layouts correctly. They say nothing about
real fares or real services.
"""

from __future__ import annotations

import random
import json
from pathlib import Path

from atoc_fares import (
    FLOW_F,
    FLOW_T,
    LOCATION,
    LOCATION_CACHE_SCHEMA,
    MINIMUM_FARE,
    RAILCARD,
    TICKET_TYPE,
)
from atoc_restrictions import RESTRICTION_LAYOUTS
from atoc_timetable import (
    CIF_HEADER,
    CIF_INTERMEDIATE,
    CIF_ORIGIN,
    CIF_SCHEDULE,
    CIF_TERMINUS,
    CIF_TIPLOC_INSERT,
    MSN_STATION,
)

STATIONS = (
    ("1000", "GRN", "GRANTHAM"),
    ("2000", "NOT", "NOTTINGHAM"),
    ("3000", "LCN", "LINCOLN"),
    ("4000", "PBO", "PETERBOROUGH"),
    ("5000", "KGX", "LONDON KINGS X"),
    ("6000", "XFD", "FIRSTONLY"),
)

UNSERVED_STATION = ("7000", "SLP", "TOWER HILL UND")
UNSERVED_FLOW = ("0000007", "1000", "7000", "00000")
UNSERVED_FARE = ("0000007", "SDR", 1200, "")

TICKET_TYPES = (
    ("SDR", "ANYTIME DAY R", "2", "R", "0"),
    ("CDR", "OFF-PEAK DAY R", "2", "R", "1"),
    ("FDR", "FIRST DAY R", "1", "R", "0"),
    ("SDS", "ANYTIME DAY S", "2", "S", "0"),
    ("2AS", "ADVANCE", "2", "S", "1"),
)

# (flow_id, origin NLC, destination NLC, route code). A real feed prices the
# same station pair through several route codes, which is why the route code is
# part of the record rather than an assumption.
FLOWS = (
    ("0000001", "1000", "2000", "00000"),
    ("0000002", "1000", "3000", "00000"),
    ("0000003", "1000", "4000", "00000"),
    ("0000004", "1000", "5000", "00000"),
    ("0000005", "2000", "1000", "00000"),
    ("0000006", "1000", "6000", "00000"),
)

FARES = (
    # SDR is the real ANYTIME DAY R code and the real feed's SDR fares carry a
    # blank restriction code. The fixture matches that: "00" is an invented
    # no-restriction code, blank is what the DTD feed actually writes.
    ("0000001", "SDR", 1420, ""),
    ("0000001", "CDR", 1160, "1A"),
    ("0000001", "FDR", 2600, "00"),
    ("0000001", "SDS", 700, "00"),
    ("0000001", "2AS", 100, "AS"),
    ("0000002", "SDR", 870, ""),
    ("0000003", "SDR", 2240, ""),
    ("0000004", "SDR", 12600, ""),
    ("0000005", "SDR", 1420, ""),
    ("0000006", "FDR", 1500, "00"),
)

# Off by default, because the base fixture is deliberately small and every
# parser test counts its records. The published demo site needs it: the station
# page's Change picker lists the other written stations, so a site pricing two
# origins leaves the picker with one option and nothing to narrow (S01 made the
# picker honest about what exists, which is only testable with three).
THIRD_ORIGIN_FLOWS = (("0000020", "3000", "2000", "00000"),)
THIRD_ORIGIN_FARES = (("0000020", "SDR", 950, ""),)

# The shapes a real feed has and a tidy invented one does not. Off by default,
# so tests about budget arithmetic read a feed with nothing puzzling in it.
#
# 9999 is a location with no station code, which is how a real feed carries a
# group or a non-station destination. 8000 has no location record at all. Both
# carry a fare, so a query that dropped them silently would undercount.
# 1500 is a second location code for Grantham, which is how a real feed carries
# one town, and 0000016 departs from it.
REAL_SHAPE_STATIONS = (
    ("9999", "", "LONDON ZONES"),
    ("1500", "GRN", "GRANTHAM STN"),
)
REAL_SHAPE_FLOWS = (
    ("0000010", "1000", "2000", "00001"),
    ("0000013", "1000", "2000", "00002"),
    ("0000011", "1000", "9999", "00000"),
    ("0000012", "1000", "8000", "00000"),
    ("0000014", "1000", "3000", "00001"),
    ("0000015", "1000", "1500", "00000"),
    ("0000016", "1500", "3000", "00000"),
)
REAL_SHAPE_FARES = (
    ("0000010", "CDR", 990, "00"),
    ("0000013", "CDR", 5000, "00"),
    ("0000011", "SDR", 500, ""),
    ("0000012", "SDR", 500, ""),
    ("0000099", "SDR", 1234, ""),
    ("0000015", "SDR", 800, ""),
    ("0000016", "SDR", 600, ""),
)

RAILCARDS = (
    ("TWO", "TWO TOGETHER RAILCARD", "2", "2"),
    ("YNG", "16-25 RAILCARD", "1", "1"),
)

MINIMUM_FARES = (("TWO", "SDR", 1200),)

# The production fares feed carries CRS, name, and NLC only. The station
# classification is a separate reference feed, so the synthetic fixture keeps
# its small reviewed equivalent in the same shape. These values are chosen to
# exercise every filter the page can render; they are a fixture, not the ONS
# result for these towns, which the checked-in reference data holds.
LOCATION_TYPES = {
    "GRN": "town",
    "NOT": "city",
    "LCN": "city",
    "PBO": "small_town",
    "KGX": "city",
    "XFD": "village",
    "SLP": "other",
}
LOCATION_FACETS = {
    "LCN": ["seaside"],
    "NOT": ["university"],
    "PBO": ["university"],
    "XFD": ["island"],
    "SLP": ["heritage"],
}

# Stations with a minimum interchange time. The 10 minutes at NOTT is what makes
# the T10006 connection in the timetable illegal, and the tests rely on that.
TIMETABLE_STATIONS = (
    ("GRNT", "GRN", "GRANTHAM", "05"),
    ("NOTT", "NOT", "NOTTINGHAM", "10"),
    ("LINC", "LCN", "LINCOLN", "05"),
    ("PETE", "PBO", "PETERBOROUGH", "05"),
    ("NWRK", "NWK", "NEWARK", "05"),
)

# (train_uid, origin, intermediates, terminus, days, stp). Times are H H M M.
# The days string runs Monday to Sunday, so "1111110" is Monday to Saturday.
# The last two entries deliberately share a train identity with a permanent
# schedule, which is how a real feed expresses a change and a cancellation.
TIMETABLE_TRAINS = (
    ("T10001", ("GRNT", "0900"), (), ("NOTT", "0950"), "1111110", "P"),
    ("T10002", ("GRNT", "0915"), (), ("LINC", "1005"), "1111110", "P"),
    ("T10003", ("GRNT", "0930"), (), ("PETE", "1000"), "1111110", "P"),
    ("T10004", ("GRNT", "1000"), (), ("NOTT", "1045"), "1111110", "P"),
    ("T10005", ("NOTT", "1105"), (), ("NWRK", "1130"), "1111110", "P"),
    ("T10006", ("NOTT", "1050"), (), ("NWRK", "1115"), "1111110", "P"),
    ("T10007", ("GRNT", "1200"), (), ("NWRK", "1400"), "1111110", "P"),
    ("T10008", ("GRNT", "0700"), (("LINC", "0752", "0755"),), ("NOTT", "0850"), "1111110", "P"),
    ("T10009", ("GRNT", "0800"), (), ("NOTT", "0855"), "0000001", "P"),
    ("T10004", ("GRNT", "1030"), (), ("NOTT", "1115"), "1111110", "O"),
    ("T10003", ("GRNT", "1130"), (), ("PETE", "1200"), "1111110", "C"),
)

TIPLOC_INSERTS = (("NOTT", "XXX"),)


def _line(values: dict[str, str], spec: tuple[tuple[str, int], ...]) -> str:
    return "".join(str(values.get(name, ""))[:width].ljust(width) for name, width in spec)


def build_synthetic_feed(
    path: str | Path,
    *,
    include_unserved_station: bool = False,
    include_real_shapes: bool = False,
    include_restrictions: bool = False,
    include_third_origin: bool = False,
) -> Path:
    """Write the fares feed.

    The unserved station carries a fare and no train. The real shapes add the
    awkward records: several route codes for one station pair, destinations with
    a fare and no station code, a flow with no fare, and a fare with no flow.
    The third origin prices a departure from a station that is only ever a
    destination, so a published site has a picker with more than one option.
    The restrictions file is off by default so existing fixtures keep their five
    files; tests for the publishable selector turn it on.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    stations = STATIONS + (UNSERVED_STATION,) if include_unserved_station else STATIONS
    flows = FLOWS + (UNSERVED_FLOW,) if include_unserved_station else FLOWS
    fares = FARES + (UNSERVED_FARE,) if include_unserved_station else FARES
    if include_real_shapes:
        stations += REAL_SHAPE_STATIONS
        flows += REAL_SHAPE_FLOWS
        fares += REAL_SHAPE_FARES
    if include_third_origin:
        flows += THIRD_ORIGIN_FLOWS
        fares += THIRD_ORIGIN_FARES

    flow_lines: list[str] = []
    for flow_id, origin, destination, route_code in flows:
        flow_lines.append(
            _line(
                {
                    "update_marker": "A",
                    "record_type": "F",
                    "origin_nlc": origin,
                    "destination_nlc": destination,
                    "route_code": route_code,
                    "flow_id": flow_id,
                },
                FLOW_F,
            )
        )
    for flow_id, ticket_code, pence, restriction in fares:
        flow_lines.append(
            _line(
                {
                    "update_marker": "A",
                    "record_type": "T",
                    "flow_id": flow_id,
                    "ticket_code": ticket_code,
                    "fare_pence": str(pence),
                    "restriction_code": restriction,
                },
                FLOW_T,
            )
        )

    location_lines = [
        _line({"update_marker": "A", "record_type": "L", "nlc": nlc, "description": name, "crs": crs}, LOCATION)
        for nlc, crs, name in stations
    ]

    ticket_lines = [
        _line(
            {
                "update_marker": "A",
                "ticket_code": code,
                "description": name,
                "tkt_class": tkt_class,
                "tkt_type": tkt_type,
                "restricted_by_train": restricted_by_train,
            },
            TICKET_TYPE,
        )
        for code, name, tkt_class, tkt_type, restricted_by_train in TICKET_TYPES
    ]

    railcard_lines = [
        _line({"railcard_code": code, "description": name, "min_adults": min_adults, "max_adults": max_adults}, RAILCARD)
        for code, name, min_adults, max_adults in RAILCARDS
    ]

    minimum_lines = [
        _line({"railcard_code": railcard, "ticket_code": ticket, "minimum_fare_pence": str(pence)}, MINIMUM_FARE)
        for railcard, ticket, pence in MINIMUM_FARES
    ]

    (path / "rjfaf.ffl").write_text("\n".join(flow_lines) + "\n", encoding="utf-8")
    (path / "rjfaf.loc").write_text("\n".join(location_lines) + "\n", encoding="utf-8")
    (path / "rjfaf.tty").write_text("\n".join(ticket_lines) + "\n", encoding="utf-8")
    (path / "rjfaf.rlc").write_text("\n".join(railcard_lines) + "\n", encoding="utf-8")
    (path / "rjfaf.rcm").write_text("\n".join(minimum_lines) + "\n", encoding="utf-8")
    (path.parent / f"{path.name}.location-types.json").write_text(
        json.dumps(
            {
                "schema": LOCATION_CACHE_SCHEMA,
                "source": "reviewed synthetic station classification",
                "records": {
                    crs: {
                        "primary": kind,
                        "facets": LOCATION_FACETS.get(crs, []),
                    }
                    for crs, kind in LOCATION_TYPES.items()
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    if include_restrictions:
        (path / "rjfaf.rst").write_text(
            "\n".join(_restriction_lines()) + "\n", encoding="utf-8"
        )
    return path


def _restriction_lines() -> list[str]:
    """One clean .RST fixture, exercising every record type the parser reads."""
    return [
        _line(
            {
                "update_marker": "R",
                "record_type": "RH",
                "cf_marker": "C",
                "restriction_code": "R1",
                "description": "PEAK TO LONDON",
                "desc_out": "NOT VALID DEPARTING BEFORE 0930",
                "desc_rtn": "NOT VALID ARRIVING BEFORE 0930",
                "type_out": "O",
                "type_rtn": "R",
                "change_ind": "N",
            },
            RESTRICTION_LAYOUTS["RH"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "HD",
                "cf_marker": "C",
                "restriction_code": "R1",
                "date_from": "0101",
                "date_to": "1231",
                "days": "YYYYYNN",
            },
            RESTRICTION_LAYOUTS["HD"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "TR",
                "cf_marker": "C",
                "restriction_code": "R1",
                "sequence_no": "0001",
                "out_ret": "O",
                "time_from": "0430",
                "time_to": "0930",
                "arr_dep_via": "D",
                "location": "EUS",
                "rstr_type": "T",
                "train_type": "A",
                "min_fare_flag": "N",
            },
            RESTRICTION_LAYOUTS["TR"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "TD",
                "cf_marker": "C",
                "restriction_code": "R1",
                "sequence_no": "0001",
                "out_ret": "O",
                "date_from": "0101",
                "date_to": "1231",
                "days": "YYYYYNN",
            },
            RESTRICTION_LAYOUTS["TD"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "TT",
                "cf_marker": "C",
                "restriction_code": "R1",
                "sequence_no": "0001",
                "out_ret": "O",
                "toc_code": "LM",
            },
            RESTRICTION_LAYOUTS["TT"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "RR",
                "cf_marker": "C",
                "railcard_code": "TWO",
                "sequence_no": "0001",
                "ticket_code": "SDR",
                "route_code": "00002",
                "location": "",
                "restriction_code": "",
                "total_ban": "Y",
            },
            RESTRICTION_LAYOUTS["RR"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "RR",
                "cf_marker": "C",
                "railcard_code": "TWO",
                "sequence_no": "0002",
                "ticket_code": "",
                "route_code": "",
                "location": "",
                "restriction_code": "R9",
                "total_ban": "",
            },
            RESTRICTION_LAYOUTS["RR"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "EC",
                "cf_marker": "C",
                "exception_code": "A",
                "description": "TEST EXCEPTION",
            },
            RESTRICTION_LAYOUTS["EC"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "CA",
                "cf_marker": "C",
                "ticket_code": "SDR",
                "cal_type": "1",
                "route_code": "00000",
                "country_code": "0",
                "date_from": "0101",
                "date_to": "1231",
                "days": "YYYYYNN",
            },
            RESTRICTION_LAYOUTS["CA"],
        ),
    ]


def build_synthetic_timetable(path: str | Path) -> Path:
    """Write a CIF timetable and a station names file in the real record layouts."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    cif_lines = [_line({"record_type": "HD", "file_identity": "SYNTHETIC"}, CIF_HEADER)]
    for train_uid, origin, intermediates, terminus, days, stp_indicator in TIMETABLE_TRAINS:
        cif_lines.append(
            _line(
                {
                    "record_type": "BS",
                    "transaction_type": "N",
                    "train_uid": train_uid,
                    "date_runs_from": "260921",
                    "date_runs_to": "261211",
                    "days": days,
                    "stp_indicator": stp_indicator,
                },
                CIF_SCHEDULE,
            )
        )
        cif_lines.append(
            _line(
                {
                    "record_type": "LO",
                    "location": origin[0],
                    "scheduled_departure": origin[1],
                    "public_departure": origin[1],
                },
                CIF_ORIGIN,
            )
        )
        for tiploc, arrival, departure in intermediates:
            cif_lines.append(
                _line(
                    {
                        "record_type": "LI",
                        "location": tiploc,
                        "scheduled_arrival": arrival,
                        "scheduled_departure": departure,
                        "public_arrival": arrival,
                        "public_departure": departure,
                    },
                    CIF_INTERMEDIATE,
                )
            )
        cif_lines.append(
            _line(
                {
                    "record_type": "LT",
                    "location": terminus[0],
                    "scheduled_arrival": terminus[1],
                    "public_arrival": terminus[1],
                },
                CIF_TERMINUS,
            )
        )
    for tiploc, crs in TIPLOC_INSERTS:
        cif_lines.append(_line({"record_type": "TI", "tiploc": tiploc, "crs": crs}, CIF_TIPLOC_INSERT))
    cif_lines.append(_line({"record_type": "ZZ"}, CIF_HEADER))

    station_lines = [
        _line(
            {
                "record_type": "A",
                "name": name,
                "category": "0",
                "tiploc": tiploc,
                "crs": crs,
                "change_time": change_time,
            },
            MSN_STATION,
        )
        for tiploc, crs, name, change_time in TIMETABLE_STATIONS
    ]

    (path / "timetable.mca").write_text("\n".join(cif_lines) + "\n", encoding="utf-8")
    (path / "stations.msn").write_text("\n".join(station_lines) + "\n", encoding="utf-8")
    return path


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}{minutes % 60:02d}"


def _append_train(
    cif_lines: list[str],
    uid: str,
    route: list[int],
    start: int,
    rng: random.Random,
) -> None:
    """Append one schedule: a header, an origin, any intermediates, a terminus.

    Station indices map to TIPLOC codes the same way the enclosing builder
    names them, so a route handed in as indices writes a coherent file.
    """

    def tiploc_of(index: int) -> str:
        return f"T{index:04d}"
    cif_lines.append(
        _line(
            {
                "record_type": "BS",
                "transaction_type": "N",
                "train_uid": uid,
                "date_runs_from": "260921",
                "date_runs_to": "261211",
                "days": "1111110",
                "stp_indicator": "P",
            },
            CIF_SCHEDULE,
        )
    )
    clock = start
    cif_lines.append(
        _line(
            {
                "record_type": "LO",
                "location": tiploc_of(route[0]),
                "scheduled_departure": _clock(clock),
                "public_departure": _clock(clock),
            },
            CIF_ORIGIN,
        )
    )
    for index in route[1:-1]:
        clock += rng.randint(10, 30)
        arrival = clock
        clock += rng.randint(1, 4)
        cif_lines.append(
            _line(
                {
                    "record_type": "LI",
                    "location": tiploc_of(index),
                    "scheduled_arrival": _clock(arrival),
                    "scheduled_departure": _clock(clock),
                    "public_arrival": _clock(arrival),
                    "public_departure": _clock(clock),
                },
                CIF_INTERMEDIATE,
            )
        )
    clock += rng.randint(10, 30)
    cif_lines.append(
        _line(
            {
                "record_type": "LT",
                "location": tiploc_of(route[-1]),
                "scheduled_arrival": _clock(clock),
                "public_arrival": _clock(clock),
            },
            CIF_TERMINUS,
        )
    )


def _emit_hub_spoke(
    cif_lines: list[str],
    *,
    stations: int,
    schedules: int,
    hub: int,
    rng: random.Random,
) -> None:
    """Trains that only ever meet at one interchange.

    Station 0 is served only by trains to the hub, and every other station is
    served only by trains to the hub, so reaching anything past the hub needs a
    change. This is the shape where a cap on the onward search can lose a
    journey, which a uniformly connected feed can never show.
    """
    outer = [index for index in range(stations) if index not in (0, hub)]
    per_pair = max(2, schedules // (2 * max(1, len(outer))))
    span = max(6, 600 // per_pair)
    uid = 0
    hub_trains = max(4, schedules // 20)
    hub_spacing = max(10, 600 // hub_trains)
    for step in range(hub_trains):
        uid += 1
        _append_train(cif_lines, f"L{uid:05d}", [0, hub], 300 + step * hub_spacing, rng)
        uid += 1
        _append_train(cif_lines, f"L{uid:05d}", [hub, 0], 320 + step * hub_spacing, rng)
    for index in outer:
        for step in range(per_pair):
            start = 300 + step * span + (index * 7) % 53
            uid += 1
            _append_train(cif_lines, f"L{uid:05d}", [hub, index], start, rng)
            uid += 1
            _append_train(cif_lines, f"L{uid:05d}", [index, hub], start + 5, rng)


def build_large_synthetic_feed(
    path: str | Path,
    *,
    stations: int = 120,
    schedules: int = 1000,
    seed: int = 7,
    shape: str = "uniform",
) -> Path:
    """Write a large invented feed holding both fares and a timetable.

    The uniform shape randomises stopping patterns and prices, which bounds the
    work a search does. The hub_spoke shape makes every journey past the hub
    need a change, which exposes what a departure cap costs. Neither predicts a
    real network.
    """

    if shape not in {"uniform", "hub_spoke"}:
        raise ValueError(f"unknown shape: {shape}")
    rng = random.Random(seed)
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    crs_codes = [f"{chr(65 + index // 100)}{(index // 10) % 10}{index % 10}" for index in range(stations)]
    tiplocs = [f"T{index:04d}" for index in range(stations)]
    nlcs = [f"{1000 + index}" for index in range(stations)]

    flow_lines: list[str] = []
    fare_lines: list[str] = []
    pairs = [(0, index) for index in range(1, stations)]
    pairs += [(rng.randrange(1, stations), rng.randrange(1, stations)) for _ in range(stations * 5)]
    for number, (origin, destination) in enumerate(pairs, start=1):
        flow_id = f"{number:07d}"
        flow_lines.append(
            _line(
                {
                    "update_marker": "A",
                    "record_type": "F",
                    "origin_nlc": nlcs[origin],
                    "destination_nlc": nlcs[destination],
                    "route_code": "00000",
                    "flow_id": flow_id,
                },
                FLOW_F,
            )
        )
        fare_lines.append(
            _line(
                {
                    "update_marker": "A",
                    "record_type": "T",
                    "flow_id": flow_id,
                    "ticket_code": "SDR",
                    "fare_pence": str(rng.randrange(200, 6000, 5)),
                    "restriction_code": "00",
                },
                FLOW_T,
            )
        )

    location_lines = [
        _line(
            {
                "update_marker": "A",
                "record_type": "L",
                "nlc": nlcs[index],
                "description": f"SYNTH {index:04d}",
                "crs": crs_codes[index],
            },
            LOCATION,
        )
        for index in range(stations)
    ]
    ticket_lines = [
        _line(
            {
                "update_marker": "A",
                "ticket_code": "SDR",
                "description": "ANYTIME DAY R",
                "tkt_class": "2",
                "tkt_type": "R",
                "restricted_by_train": "0",
            },
            TICKET_TYPE,
        )
    ]

    hub = 1
    cif_lines = [_line({"record_type": "HD", "file_identity": "SYNTHETIC-LARGE"}, CIF_HEADER)]
    if shape == "hub_spoke":
        _emit_hub_spoke(cif_lines, stations=stations, schedules=schedules, hub=hub, rng=rng)
    else:
        for train in range(schedules):
            stop_count = min(stations - 1, rng.randint(2, 6))
            candidates = [index for index in range(1, stations) if index != hub]
            route = [0] + rng.sample(candidates, stop_count - 1)
            if rng.random() < 0.4:
                route[rng.randrange(1, len(route))] = hub
            _append_train(cif_lines, f"L{train:05d}", route, rng.randrange(300, 900), rng)
    cif_lines.append(_line({"record_type": "ZZ"}, CIF_HEADER))

    station_lines = [
        _line(
            {
                "record_type": "A",
                # Short enough to survive the fixed width name field. A longer
                # name is truncated on read, which made two stations look alike.
                "name": f"SYNTH {index:04d}",
                "category": "0",
                "tiploc": tiplocs[index],
                "crs": crs_codes[index],
                "change_time": "05",
            },
            MSN_STATION,
        )
        for index in range(stations)
    ]

    (path / "large.ffl").write_text("\n".join(flow_lines + fare_lines) + "\n", encoding="utf-8")
    (path / "large.loc").write_text("\n".join(location_lines) + "\n", encoding="utf-8")
    (path / "large.tty").write_text("\n".join(ticket_lines) + "\n", encoding="utf-8")
    (path / "large.mca").write_text("\n".join(cif_lines) + "\n", encoding="utf-8")
    (path / "large.msn").write_text("\n".join(station_lines) + "\n", encoding="utf-8")
    return path


def write_delete_marker(path: str | Path, flow_id: str, ticket_code: str) -> Path:
    """Append an incremental delete record, as a real update file would."""
    path = Path(path)
    target = path / "rjfaf-update.ffl"
    target.write_text(
        _line(
            {"update_marker": "D", "record_type": "T", "flow_id": flow_id, "ticket_code": ticket_code},
            FLOW_T,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Write synthetic feed folders.")
    parser.add_argument("path", help="folder to create the feed files in")
    parser.add_argument(
        "--kind",
        choices=("fares", "timetable", "both"),
        default="both",
        help="which feed to write",
    )
    parser.add_argument(
        "--unserved-station",
        action="store_true",
        help="add a station that has a fare and no train service",
    )
    parser.add_argument(
        "--real-shapes",
        action="store_true",
        help="add several route codes, a stationless destination, and unmatched records",
    )
    parser.add_argument(
        "--third-origin",
        action="store_true",
        help="price a third station's departures, so a built site's station picker has options",
    )
    arguments = parser.parse_args()

    if arguments.kind in {"fares", "both"}:
        print(
            build_synthetic_feed(
                arguments.path,
                include_unserved_station=arguments.unserved_station,
                include_real_shapes=arguments.real_shapes,
                # The demo page now depends on the reviewed selector, which
                # depends on a clean .RST file, so the demo feed carries one.
                include_restrictions=True,
                include_third_origin=arguments.third_origin,
            )
        )
    if arguments.kind in {"timetable", "both"}:
        print(build_synthetic_timetable(arguments.path))
