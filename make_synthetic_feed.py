"""Write a small synthetic fares feed so the parser can be exercised without a licence.

Every station, flow, and price here is invented. It exists to prove the parser
reads the real record layouts correctly. It says nothing about real fares.
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

STATIONS = (
    ("1000", "GRN", "GRANTHAM"),
    ("2000", "NOT", "NOTTINGHAM"),
    ("3000", "LCN", "LINCOLN"),
    ("4000", "PBO", "PETERBOROUGH"),
    ("5000", "KGX", "LONDON KINGS X"),
    ("6000", "XFD", "FIRSTONLY"),
)

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


def _line(values: dict[str, str], spec: tuple[tuple[str, int], ...]) -> str:
    return "".join(str(values.get(name, ""))[:width].ljust(width) for name, width in spec)


def build_synthetic_feed(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    flow_lines: list[str] = []
    for flow_id, origin, destination in FLOWS:
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
    for flow_id, ticket_code, pence, restriction in FARES:
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
        for nlc, crs, name in STATIONS
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

    parser = argparse.ArgumentParser(description="Write a synthetic fares feed folder.")
    parser.add_argument("path", help="folder to create the feed files in")
    args = parser.parse_args()
    print(build_synthetic_feed(args.path))
