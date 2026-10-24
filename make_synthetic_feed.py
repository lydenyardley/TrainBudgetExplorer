"""Write small synthetic feeds so the parsers can be exercised without a licence.

Every station, flow, price, and train here is invented. The fixtures exist to
prove the parsers read the real record layouts correctly. They say nothing about
real fares or real services.
"""

from __future__ import annotations

import gzip
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
from atoc_restrictions import RESTRICTION_LAYOUTS, RESTRICTION_OFFSETS
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

# Off by default too. Fares from London Kings Cross, the fixture station the
# reviewed list renames ("LONDON KINGS X" is shown as "London Kings Cross"), so
# a page has an origin whose name is not the feed's upper-case CIF name. Every
# other origin the fixtures price keeps its CIF name, and the browser suite's
# heading check compared against an upper-cased name without a page that could
# tell it was wrong; Harwich International's page was the first (run
# 39818671598).
#
# The fares sit between £9 and £17, so the cheapest costs more for two than
# the dearest does for one: every row the first card prices is above the
# one-adult ceiling the page opens on once the party is two. That is the page
# on which the railcard-note check set its budget from a ceiling the party
# change had not yet redrawn and read no rows (Farnborough (Main), same run).
# The destinations are the return network's, so the page has the types, a
# heritage row and enough rows for the suite's other checks to read; it needs
# --return-network for its stations.
REVIEWED_ORIGIN_FARES = (
    ("5000", "1000", 900),   # London Kings Cross -> Grantham
    ("5000", "8000", 1000),  # London Kings Cross -> Matlock
    ("5000", "8100", 1100),  # London Kings Cross -> Retford
    ("5000", "8200", 1300),  # London Kings Cross -> Skegness
    ("5000", "8300", 1500),  # London Kings Cross -> Leicester
    ("5000", "8400", 1700),  # London Kings Cross -> Bulwell
)

# The reviewed origin's own trains, added 24 October 2026.
#
# A place no journey reaches is not listed (ADR-0076), so a reviewed origin with
# fares and no trains became a page with no rows: `tools/verify.py --browser`
# wrote no station page for the reviewed-name shape and the suite drove the page
# an earlier build had left in the folder, against a script this tree no longer
# writes. Retford is priced and still never called at, which is the "no service"
# row's shape and is the return network's to carry; every other priced place here
# has a train, so the page the suite drives has rows and times.
REVIEWED_ORIGIN_TIMETABLE_STATIONS = (("KGXX", "KGX", "LONDON KINGS CROSS", "10"),)
REVIEWED_ORIGIN_TIMETABLE_TRAINS = (
    ("T30001", ("KGXX", "0900"), (("NOTT", "1010", "1015"),), ("GRNT", "1100"), "1111110", "P"),
    ("T30002", ("KGXX", "0930"), (), ("MATL", "1130"), "1111110", "P"),
    ("T30003", ("KGXX", "1000"), (), ("SLDK", "1210"), "1111110", "P"),
    ("T30004", ("KGXX", "1030"), (), ("LEIC", "1140"), "1111110", "P"),
    ("T30005", ("KGXX", "1100"), (("NOTT", "1210", "1220"),), ("BULW", "1245"), "1111110", "P"),
)

# A real network for the two secondary origins, off by default with the rest of
# the optional blocks.
#
# The browser suite drives every station page a build writes, so a station with
# one priced destination leaves most of the page untested on two pages out of
# three: a shortlist of one thing, no fare the Two Together minimum does not
# already exceed, a single destination type so multi-select cannot be tried, and
# no heritage row. The destinations below are chosen so that between them the
# two pages carry a UNESCO property, a small town, a seaside town and a city,
# and so that some fares sit above the £12.00 Two Together minimum, which is
# what makes the card worth offering. Matlock is here because Derwent Valley
# Mills is a real World Heritage Site whose settlement list names it, so the
# heritage row the suite looks for comes from the feed's own data rather than
# from a flag.
RETURN_NETWORK_STATIONS = (
    ("8000", "MAT", "MATLOCK"),
    ("8100", "RET", "RETFORD"),
    ("8200", "SLD", "SKEGNESS"),
    ("8300", "LEC", "LEICESTER"),
    # Bulwell has no Grantham flow. A through train calls at Nottingham, so the
    # wider ADR-0061 rule prices Grantham to Nottingham plus Nottingham to
    # Bulwell with no physical change. Strict change-station-only misses it.
    ("8400", "BUL", "BULWELL"),
)
RETURN_NETWORK_TYPES = {
    "MAT": "town",
    "RET": "small_town",
    "SLD": "small_town",
    "LEC": "city",
    "BUL": "small_town",
}
RETURN_NETWORK_FACETS = {
    "MAT": ["heritage"],
    "SLD": ["seaside"],
    "LEC": ["university"],
}
# (origin NLC, destination NLC, fare pence). Every fare is an unrestricted SDR,
# so each row appears in the reviewed set the page opens in as well as the
# broad one. The two fares under £12.00 are deliberate: without them every row
# would be railcard-eligible and the page could not show what happens to a fare
# the card minimum does not beat.
RETURN_NETWORK_FARES = (
    ("3000", "8000", 1560),  # Lincoln -> Matlock
    ("3000", "8100", 980),   # Lincoln -> Retford
    ("3000", "8200", 3240),  # Lincoln -> Skegness
    ("3000", "8300", 2680),  # Lincoln -> Leicester
    ("2000", "8000", 1980),  # Nottingham -> Matlock
    ("2000", "8100", 1120),  # Nottingham -> Retford
    ("2000", "8200", 3560),  # Nottingham -> Skegness
    ("2000", "8300", 2400),  # Nottingham -> Leicester
    ("2000", "8400", 410),   # Nottingham -> Bulwell
)
# One restricted fare on each secondary page. The reviewed Anytime set drops
# restricted fares by design, so without one of these the two secondary pages
# carry no restriction code at all -- and a check that asks what a condition
# permits has nothing to ask about on two pages out of three. The code is the
# one the .RST fixture below describes with a validity the reader can read.
RETURN_NETWORK_RESTRICTED = (("3000", "8300"), ("2000", "8300"))
# Retford is priced but never called at, which is the shape a real feed has and
# the one the page's "no service" row exists to report. The other three are
# called at, so a page has both a timed row and an untimed one.
RETURN_NETWORK_TIMETABLE_STATIONS = (
    ("MATL", "MAT", "MATLOCK", "05"),
    ("SLDK", "SLD", "SKEGNESS", "05"),
    ("LEIC", "LEC", "LEICESTER", "10"),
    ("BULW", "BUL", "BULWELL", "05"),
)
RETURN_NETWORK_TIMETABLE_TRAINS = (
    ("T20001", ("LINC", "0740"), (), ("MATL", "0825"), "1111110", "P"),
    ("T20002", ("NOTT", "0800"), (), ("MATL", "0855"), "1111110", "P"),
    ("T20003", ("LINC", "1100"), (), ("SLDK", "1205"), "1111110", "P"),
    ("T20004", ("NOTT", "1120"), (), ("SLDK", "1230"), "1111110", "P"),
    ("T20005", ("NOTT", "0905"), (), ("LEIC", "0940"), "1111110", "P"),
    # Direct Grantham to Bulwell calling at Nottingham: wider split, no change.
    ("T20006", ("GRNT", "0830"), (("NOTT", "0915", "0918"),), ("BULW", "0945"), "1111110", "P"),
)

# One origin with more than a page of destinations, off by default with the rest
# of the optional blocks.
#
# The table shows twenty rows before it offers a pager, so a fixture whose every
# origin prices fewer than twenty-one places cannot exercise the second page or
# the n/p keys: the suite reported both as not exercised on every page it drove.
# These are destinations Grantham is priced to directly, chosen so the demo
# page the suite drives has a second page to turn to. The all-origins demo build
# is the only caller, so the fixtures every parser test counts stay untouched.
LONG_LIST_STATIONS = (
    ("8500", "SLR", "SLEAFORD"),
    ("8600", "BSN", "BOSTON"),
    ("8700", "NCT", "NEWARK CASTLE"),
    ("8800", "WRK", "WORKSOP"),
    ("8900", "MFT", "MANSFIELD"),
    ("9000", "DBY", "DERBY"),
    ("9100", "OKM", "OAKHAM"),
    ("9200", "SMD", "STAMFORD"),
    ("9300", "SPA", "SPALDING"),
    ("9400", "CBG", "CAMBRIDGE"),
    ("9500", "NMP", "NORTHAMPTON"),
    ("9600", "KET", "KETTERING"),
    ("9700", "ELY", "ELY"),
    ("9800", "HUN", "HUNTINGDON"),
)
LONG_LIST_TYPES = {
    "SLR": "small_town",
    "BSN": "town",
    "NCT": "town",
    "WRK": "town",
    "MFT": "town",
    "DBY": "city",
    "OKM": "small_town",
    "SMD": "town",
    "SPA": "small_town",
    "CBG": "city",
    "NMP": "town",
    "KET": "town",
    "ELY": "small_town",
    "HUN": "town",
}
# (origin NLC, destination NLC, fare pence). Every one is a direct Grantham
# flow, because a row the split rule composes would make the page's length a
# property of the timetable rather than of the feed.
LONG_LIST_FARES = (
    ("1000", "8500", 640),
    ("1000", "8600", 890),
    ("1000", "8700", 1120),
    ("1000", "8800", 780),
    ("1000", "8900", 960),
    ("1000", "9000", 1340),
    ("1000", "9100", 710),
    ("1000", "9200", 830),
    ("1000", "9300", 1050),
    ("1000", "9400", 2450),
    ("1000", "9500", 1890),
    ("1000", "9600", 1520),
    ("1000", "9700", 1680),
    ("1000", "9800", 1180),
)

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

# TWO is carried so the fixture still holds a code the page does not offer,
# which is what keeps the reviewed set honest: a page can only show a card it
# has reviewed, so a fixture whose only cards are reviewed would never exercise
# the difference. YNG is the reviewed card the page therefore prices, and the
# rules and minimum fare below hang off it.
# The six reviewed public railcards, with the party each one prices, measured
# against the real feed on 1 October 2026. Bounds are the card's own, so the
# party filter has something to take out: Two Together cannot price one
# traveller, and the Student Discount Card cannot price two. That all six reach
# the page as six options is held twice over:
# tests/test_build_fares.py::test_railcard_pricing_is_available_from_the_feed
# and check 7c in tests/browser/station-fares.cjs.
RAILCARDS = (
    ("YNG", "16-25 RAILCARD", "1", "8"),
    ("DIS", "DISABLED PERSONS RAILCARD", "1", "2"),
    ("NEW", "NETWORK RAILCARD", "1", "4"),
    ("SRN", "SENIOR RAILCARD", "1", "8"),
    ("BB2", "STUDENT DISCOUNT CARD", "1", "1"),
    ("2TR", "TWO TOGETHER RAILCARD", "2", "2"),
)

MINIMUM_FARES = (("YNG", "SDR", 1200),)

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


def build_synthetic_knowledgebase(
    path: str | Path, *, omit: str | None = "1A"
) -> Path:
    """Write a Knowledgebase ``ticket-restrictions`` reference feed.

    The wording is taken from the very same ``RH`` records the fares feed's
    ``.RST`` carries, so the two fixtures cannot drift apart and a test of
    "the portal still publishes every condition this build quotes" is a
    statement about the comparison rather than about two hand-kept copies of
    the same list.

    *omit* names one code the reference feed does not carry at all. That is the
    case worth testing: a reference feed holding everything proves only that
    the comparison ran, while one missing a condition proves the page names the
    one the portal no longer lists instead of quietly printing "all of them".

    It used to reword a record instead, which was the right way to build a
    disagreement when a disagreement meant "these two feeds word the same
    condition differently". Run against the real portal feed, that comparison
    reported every one of 628 conditions disagreeing, because the portal words
    a condition in prose and the fares feed compresses it. The check now asks
    about publication, so the fixture omits rather than rewords.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    records = []
    for line in _restriction_lines():
        if not line[1:3] == "RH":
            continue
        offsets = RESTRICTION_OFFSETS["RH"]
        code = line[offsets["restriction_code"][0]:offsets["restriction_code"][1]].strip()
        if not code or code == omit:
            continue
        description = line[offsets["description"][0]:offsets["description"][1]].strip()
        outward = line[offsets["desc_out"][0]:offsets["desc_out"][1]].strip()
        back = line[offsets["desc_rtn"][0]:offsets["desc_rtn"][1]].strip()
        records.append(
            "    <Restriction>\n"
            f"      <RestrictionCode>{code}</RestrictionCode>\n"
            f"      <Description>{_xml_escape(description)}</Description>\n"
            f"      <DescOut>{_xml_escape(outward)}</DescOut>\n"
            f"      <DescRtn>{_xml_escape(back)}</DescRtn>\n"
            "    </Restriction>"
        )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Knowledgebase>\n"
        "  <TicketRestrictions>\n"
        + "\n".join(records)
        + "\n  </TicketRestrictions>\n"
        "</Knowledgebase>\n"
    )
    target = path / "ticket-restrictions.xml"
    target.write_text(document, encoding="utf-8")
    return path


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_synthetic_station_coordinates(path: str | Path) -> Path:
    """Write a Knowledgebase ``stations.xml`` holding a few station positions.

    The heritage prune reads station coordinates from the licensed
    Knowledgebase download, which a clean checkout -- CI's -- does not have,
    and a missing file is reported as a skipped source, rightly. A test about
    something else points the prune here instead, so it neither depends on
    the local download nor reads that report as its own subject.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    stations = (
        ("GRA", 52.9064, -0.6424),
        ("NOT", 52.9472, -1.1461),
        ("KGX", 51.5320, -0.1233),
    )
    body = "".join(
        f"<Station><CrsCode>{crs}</CrsCode><Latitude>{lat}</Latitude>"
        f"<Longitude>{lon}</Longitude></Station>"
        for crs, lat, lon in stations
    )
    target.write_text(
        f'<?xml version="1.0" encoding="utf-8"?><StationList>{body}</StationList>\n',
        encoding="utf-8",
    )
    return target


def build_synthetic_feed(
    path: str | Path,
    *,
    include_unserved_station: bool = False,
    include_real_shapes: bool = False,
    include_restrictions: bool = False,
    include_third_origin: bool = False,
    include_reviewed_origin: bool = False,
    include_return_network: bool = False,
    include_long_list: bool = False,
    minimum_fares: tuple[tuple[str, ...], ...] | None = None,
) -> Path:
    """Write the fares feed.

    The unserved station carries a fare and no train. The real shapes add the
    awkward records: several route codes for one station pair, destinations with
    a fare and no station code, a flow with no fare, and a fare with no flow.
    The third origin prices a departure from a station that is only ever a
    destination, so a published site has a picker with more than one option. The
    return network gives the two secondary origins a set of destinations to
    price, so a page the browser suite drives has more than one row to choose
    from. The long list gives Grantham more than a page of them, so the pager
    and its keys have a second page to reach. The restrictions file is off by
    default so existing fixtures keep their five files; tests for the
    publishable selector turn it on.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    stations = STATIONS + (UNSERVED_STATION,) if include_unserved_station else STATIONS
    flows = FLOWS + (UNSERVED_FLOW,) if include_unserved_station else FLOWS
    fares = FARES + (UNSERVED_FARE,) if include_unserved_station else FARES
    types = dict(LOCATION_TYPES)
    facets = dict(LOCATION_FACETS)
    if include_real_shapes:
        stations += REAL_SHAPE_STATIONS
        flows += REAL_SHAPE_FLOWS
        fares += REAL_SHAPE_FARES
    if include_third_origin:
        flows += THIRD_ORIGIN_FLOWS
        fares += THIRD_ORIGIN_FARES
    if include_return_network:
        stations += RETURN_NETWORK_STATIONS
        types.update(RETURN_NETWORK_TYPES)
        facets.update(RETURN_NETWORK_FACETS)
        for number, (origin, destination, pence) in enumerate(RETURN_NETWORK_FARES, start=30):
            flow_id = f"{number:07d}"
            restriction = "1A" if (origin, destination) in RETURN_NETWORK_RESTRICTED else ""
            flows += ((flow_id, origin, destination, "00000"),)
            fares += ((flow_id, "SDR", pence, restriction),)
    if include_reviewed_origin:
        if not include_return_network:
            raise ValueError("the reviewed origin prices the return network's stations; pass include_return_network too")
        for number, (origin, destination, pence) in enumerate(REVIEWED_ORIGIN_FARES, start=90):
            flow_id = f"{number:07d}"
            flows += ((flow_id, origin, destination, "00000"),)
            fares += ((flow_id, "SDR", pence, ""),)
    if include_long_list:
        stations += LONG_LIST_STATIONS
        types.update(LONG_LIST_TYPES)
        for number, (origin, destination, pence) in enumerate(LONG_LIST_FARES, start=60):
            flow_id = f"{number:07d}"
            flows += ((flow_id, origin, destination, "00000"),)
            fares += ((flow_id, "SDR", pence, ""),)

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
        _line(
            {
                "railcard_code": record[0],
                "ticket_code": record[1],
                "minimum_fare_pence": str(record[2]),
                # A window is optional: a three-tuple keeps the open-ended
                # record the older fixtures rely on, and a five-tuple writes
                # the dated record the real catalogue carries.
                "start_date": record[3] if len(record) > 3 else "",
                "end_date": record[4] if len(record) > 4 else "",
            },
            MINIMUM_FARE,
        )
        for record in (MINIMUM_FARES if minimum_fares is None else minimum_fares)
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
                        "facets": facets.get(crs, []),
                    }
                    for crs, kind in types.items()
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
        # A header for each restriction code the fixture's own fares carry, so
        # the page has something to decode: without these, every restricted row
        # falls back to "this feed does not describe it" and the validity text
        # the reader is meant to see can never be exercised anywhere -- not in
        # the browser suite, and not on the demo site a contributor reads.
        _line(
            {
                "update_marker": "R",
                "record_type": "RH",
                "cf_marker": "C",
                "restriction_code": "1A",
                # 30 characters, which is the field's real width: a fixture
                # whose description only works because the parser truncated it
                # is testing the truncation, not the description.
                "description": "NOT VALID AT WEEKENDS",
                "desc_out": "NOT VALID FOR TRAVEL ON SATURDAY OR SUNDAY",
                "desc_rtn": "RETURN NOT VALID FOR TRAVEL ON SATURDAY OR SUNDAY",
                "type_out": "D",
                "type_rtn": "D",
                "change_ind": "N",
            },
            RESTRICTION_LAYOUTS["RH"],
        ),
        _line(
            {
                "update_marker": "R",
                "record_type": "RH",
                "cf_marker": "C",
                "restriction_code": "AS",
                "description": "ADVANCE TICKET, VALID ON ONE NAMED TRAIN",
                "desc_out": "VALID ONLY ON THE TRAIN NAMED ON THE TICKET",
                "desc_rtn": "NOT APPLICABLE: THIS IS AN OUTBOUND SINGLE",
                "type_out": "T",
                "type_rtn": "T",
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
        # One pair of rules per card, because an RR record is keyed by the card
        # it governs: a card with no rule of its own is not discounted at all,
        # which is how the fixture came to offer one card rather than six. The
        # pair is the same for each, and is the one shape worth exercising -- a
        # total ban on one ticket, and a travel condition on everything else.
        *[
            _line(
                {
                    "update_marker": "R",
                    "record_type": "RR",
                    "cf_marker": "C",
                    "railcard_code": card[0],
                    "sequence_no": "0001",
                    "ticket_code": "CDR",
                    "route_code": "00000",
                    "location": "",
                    "restriction_code": "",
                    "total_ban": "Y",
                },
                RESTRICTION_LAYOUTS["RR"],
            )
            for card in RAILCARDS
        ],
        *[
            _line(
                {
                    "update_marker": "R",
                    "record_type": "RR",
                    "cf_marker": "C",
                    "railcard_code": card[0],
                    "sequence_no": "0002",
                    "ticket_code": "",
                    "route_code": "",
                    "location": "",
                    "restriction_code": "R9",
                    "total_ban": "",
                },
                RESTRICTION_LAYOUTS["RR"],
            )
            for card in RAILCARDS
        ],
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


def build_synthetic_timetable(
    path: str | Path,
    *,
    include_return_network: bool = False,
    include_passing_stop: bool = False,
    include_reviewed_origin: bool = False,
) -> Path:
    """Write a CIF timetable and a station names file in the real record layouts."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    stations = TIMETABLE_STATIONS
    trains = TIMETABLE_TRAINS
    if include_return_network:
        stations += RETURN_NETWORK_TIMETABLE_STATIONS
        trains += RETURN_NETWORK_TIMETABLE_TRAINS
    if include_reviewed_origin:
        if not include_return_network:
            raise ValueError(
                "the reviewed origin runs to the return network's stations; "
                "pass include_return_network too"
            )
        stations += REVIEWED_ORIGIN_TIMETABLE_STATIONS
        trains += REVIEWED_ORIGIN_TIMETABLE_TRAINS
    cif_lines = [_line({"record_type": "HD", "file_identity": "SYNTHETIC"}, CIF_HEADER)]
    for train_uid, origin, intermediates, terminus, days, stp_indicator in trains:
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
    if include_passing_stop:
        # A train that passes a station rather than calling at it, in the feed's
        # own shape: the through time sits in `scheduled_pass` and both public
        # time fields carry `0000`, which is the marker for "no time of this kind
        # here" and not midnight, because the CIF has no midnight -- a time after
        # it is written 2400 to 2949. Read as a clock time, `0000` manufactured a
        # departure from every station the train ran through; it took four
        # symptoms on one real page to find, and 569e477 fixed it in one line of
        # `_minutes`. That defect's test builds its own feed, so this record is
        # the same shape available to any test that wants it: see
        # SyntheticPassingStopTest in tests/test_atoc_timetable.py.
        cif_lines.append(
            _line(
                {
                    "record_type": "BS",
                    "transaction_type": "N",
                    "train_uid": "T10009",
                    "date_runs_from": "260921",
                    "date_runs_to": "261211",
                    "days": "1111110",
                    "stp_indicator": "P",
                },
                CIF_SCHEDULE,
            )
        )
        cif_lines.append(
            _line(
                {
                    "record_type": "LO",
                    "location": "NWRK",
                    "scheduled_departure": "0905",
                    "public_departure": "0905",
                },
                CIF_ORIGIN,
            )
        )
        cif_lines.append(
            _line(
                {
                    "record_type": "LI",
                    "location": "GRNT",
                    "scheduled_pass": "0912",
                    "public_arrival": "0000",
                    "public_departure": "0000",
                },
                CIF_INTERMEDIATE,
            )
        )
        cif_lines.append(
            _line(
                {
                    "record_type": "LT",
                    "location": "NOTT",
                    "scheduled_arrival": "0950",
                    "public_arrival": "0950",
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
        for tiploc, crs, name, change_time in stations
    ]

    (path / "timetable.mca").write_text("\n".join(cif_lines) + "\n", encoding="utf-8")
    (path / "stations.msn").write_text("\n".join(station_lines) + "\n", encoding="utf-8")
    return path


# The name Network Rail's own schedule feed gives the whole CIF, and the reason
# there is a fixture for this shape: it is one gzipped file holding every record
# type, with no station names file beside it and nothing filtered out of it.
WHOLE_CIF_NAME = "CIF_ALL_FULL_DAILY_toc-full.CIF.gz"


def build_synthetic_whole_cif(
    path: str | Path,
    *,
    gzipped: bool = True,
    with_station_names: bool = False,
    with_non_passenger: bool = True,
) -> Path:
    """Write one whole CIF in the shape Network Rail's own feed has.

    The DTD timetable product ships a folder of record-type files with a station
    names file beside them, and it is filtered to passenger services before it is
    published. Network Rail's own CIF -- the file the Open Government Licence
    route reads -- is one gzipped file, unfiltered, with no station names file at
    all. A test built only the DTD way cannot see either difference, which is how
    a page could answer "nowhere" for a station the feed does serve while also
    being able to offer a journey on an empty-stock move.

    Three invented services, one per case: a passenger train (status P, category
    OO), a freight path (status F, no public calling times), and an empty-stock
    move (status P -- it is a passenger train -- with the category that says it
    carries nobody). The empty-stock move carries public times on purpose: the
    test is that the code table drops it, not that a missing public time does.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    lines = [
        _line(
            {
                "record_type": "HD",
                "file_identity": "SYNTHETIC",
                # A weekly full extract is written on a Friday, which is the only
                # thing about this date that is real: 9 October 2026 is one.
                "extract_date": "261009",
                "extract_time": "0130",
            },
            CIF_HEADER,
        )
    ]
    lines.extend(
        _whole_cif_train(
            train_uid="W10001",
            origin=("GRNT", "0900", "0900"),
            intermediates=[("NWRK", "0925", "0930", "0925", "0930")],
            terminus=("NOTT", "0955", "0955"),
            status="P",
            category="OO",
        )
    )
    if with_non_passenger:
        lines.extend(
            _whole_cif_train(
                train_uid="W10002",
                origin=("GRNT", "2300", "0000"),
                intermediates=[],
                terminus=("NOTT", "2345", "0000"),
                status="F",
                category="",
            )
        )
        lines.extend(
            _whole_cif_train(
                train_uid="W10003",
                origin=("NOTT", "0600", "0600"),
                intermediates=[],
                terminus=("GRNT", "0650", "0650"),
                status="P",
                category="EE",
            )
        )
    for tiploc, crs in TIPLOC_INSERTS:
        lines.append(_line({"record_type": "TI", "tiploc": tiploc, "crs": crs}, CIF_TIPLOC_INSERT))
    lines.append(_line({"record_type": "ZZ"}, CIF_HEADER))

    target = path / (WHOLE_CIF_NAME if gzipped else WHOLE_CIF_NAME[: -len(".gz")])
    body = ("\n".join(lines) + "\n").encode("utf-8")
    if gzipped:
        with gzip.open(target, "wb") as handle:
            handle.write(body)
    else:
        target.write_bytes(body)
    if with_station_names:
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
        (path / "stations.msn").write_text("\n".join(station_lines) + "\n", encoding="utf-8")
    return path


def _whole_cif_train(
    *,
    train_uid: str,
    origin: tuple[str, str, str],
    intermediates: list[tuple[str, str, str, str, str]],
    terminus: tuple[str, str, str],
    status: str,
    category: str,
) -> list[str]:
    """One schedule's records, in the order the CIF writes them."""
    lines = [
        _line(
            {
                "record_type": "BS",
                "transaction_type": "N",
                "train_uid": train_uid,
                "date_runs_from": "260921",
                "date_runs_to": "261211",
                "days": "1111110",
                "status": status,
                "category": category,
                "stp_indicator": "P",
            },
            CIF_SCHEDULE,
        ),
        _line(
            {
                "record_type": "LO",
                "location": origin[0],
                "scheduled_departure": origin[1],
                "public_departure": origin[2],
            },
            CIF_ORIGIN,
        ),
    ]
    for tiploc, arrival, departure, public_arrival, public_departure in intermediates:
        lines.append(
            _line(
                {
                    "record_type": "LI",
                    "location": tiploc,
                    "scheduled_arrival": arrival,
                    "scheduled_departure": departure,
                    "public_arrival": public_arrival,
                    "public_departure": public_departure,
                },
                CIF_INTERMEDIATE,
            )
        )
    lines.append(
        _line(
            {
                "record_type": "LT",
                "location": terminus[0],
                "scheduled_arrival": terminus[1],
                "public_arrival": terminus[2],
            },
            CIF_TERMINUS,
        )
    )
    return lines


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
    parser.add_argument(
        "--reviewed-origin",
        action="store_true",
        help=(
            "price London Kings Cross to the return network (pass that too), an "
            "origin whose page name is the reviewed 'London Kings Cross' rather "
            "than the feed's CIF name"
        ),
    )
    parser.add_argument(
        "--return-network",
        action="store_true",
        help=(
            "give the two secondary origins a set of destinations to price, so "
            "every station page the browser suite drives has more than one row"
        ),
    )
    parser.add_argument(
        "--long-list",
        action="store_true",
        help=(
            "price Grantham to more than twenty destinations, so a driven page "
            "has a second page and the pager's keys can be exercised"
        ),
    )
    parser.add_argument(
        "--knowledgebase",
        metavar="PATH",
        help=(
            "also write a Knowledgebase ticket-restrictions reference feed in "
            "PATH, as a second opinion on the fares feed's own restriction "
            "wording. One code is deliberately worded differently, so the case a "
            "page has to get right -- a disagreement it must report rather than "
            "resolve -- is the case the demo site shows"
        ),
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
                include_reviewed_origin=arguments.reviewed_origin,
                include_return_network=arguments.return_network,
                include_long_list=arguments.long_list,
            )
        )
    if arguments.kind in {"timetable", "both"}:
        print(
            build_synthetic_timetable(
                arguments.path,
                include_return_network=arguments.return_network,
                include_reviewed_origin=arguments.reviewed_origin,
            )
        )
    if arguments.knowledgebase:
        print(build_synthetic_knowledgebase(arguments.knowledgebase))
