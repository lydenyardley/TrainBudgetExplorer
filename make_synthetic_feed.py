"""Write small synthetic feeds so the parsers can be exercised without a licence.

Every station, flow, price, and train here is invented. The fixtures exist to
prove the parsers read the real record layouts correctly. They say nothing about
real fares or real services.
"""

from __future__ import annotations

from pathlib import Path

from atoc_fares import (
    FLOW_F,
    FLOW_T,
    LOCATION,
    MINIMUM_FARE,
    RAILCARD,
    TICKET_TYPE,
)
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

UNSERVED_STATION = ("7000", "SLP", "SLEEPY")
UNSERVED_FLOW = ("0000007", "1000", "7000")
UNSERVED_FARE = ("0000007", "SDR", 1200, "00")

TICKET_TYPES = (
    ("SDR", "ANYTIME DAY R", "2", "R", "0"),
    ("CDR", "OFF-PEAK DAY R", "2", "R", "1"),
    ("FDR", "FIRST DAY R", "1", "R", "0"),
    ("SDS", "ANYTIME DAY S", "2", "S", "0"),
)

FLOWS = (
    ("0000001", "1000", "2000"),
    ("0000002", "1000", "3000"),
    ("0000003", "1000", "4000"),
    ("0000004", "1000", "5000"),
    ("0000005", "2000", "1000"),
    ("0000006", "1000", "6000"),
)

FARES = (
    ("0000001", "SDR", 1420, "00"),
    ("0000001", "CDR", 1160, "1A"),
    ("0000001", "FDR", 2600, "00"),
    ("0000001", "SDS", 700, "00"),
    ("0000002", "SDR", 870, "00"),
    ("0000003", "SDR", 2240, "00"),
    ("0000004", "SDR", 8400, "00"),
    ("0000005", "SDR", 1420, "00"),
    ("0000006", "FDR", 1500, "00"),
)

RAILCARDS = (
    ("TWO", "TWO TOGETHER RAILCARD", "2", "2"),
    ("YNG", "16-25 RAILCARD", "1", "1"),
)

MINIMUM_FARES = (("TWO", "SDR", 1200),)

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


def build_synthetic_feed(path: str | Path, *, include_unserved_station: bool = False) -> Path:
    """Write the fares feed. The unserved station carries a fare and no train."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    stations = STATIONS + (UNSERVED_STATION,) if include_unserved_station else STATIONS
    flows = FLOWS + (UNSERVED_FLOW,) if include_unserved_station else FLOWS
    fares = FARES + (UNSERVED_FARE,) if include_unserved_station else FARES

    flow_lines: list[str] = []
    for flow_id, origin, destination in flows:
        flow_lines.append(
            _line(
                {
                    "update_marker": "A",
                    "record_type": "F",
                    "origin_nlc": origin,
                    "destination_nlc": destination,
                    "route_code": "00000",
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
    return path


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
    arguments = parser.parse_args()

    if arguments.kind in {"fares", "both"}:
        print(build_synthetic_feed(arguments.path, include_unserved_station=arguments.unserved_station))
    if arguments.kind in {"timetable", "both"}:
        print(build_synthetic_timetable(arguments.path))
