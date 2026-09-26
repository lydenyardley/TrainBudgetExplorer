"""Read the ATOC/RDG fares feed and answer "what can I reach for under £X?".

The feed is fixed-width text. Each spec below is (field_name, width) in file
order, so a field's position is the running sum of the widths before it. That
mirrors how the published record layouts are defined.

Fares are per person. A party buys one ticket per adult unless the ticket type
says otherwise, so a party price is adults x per-adult.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
import io
import os
import json
import pickle
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from atoc_restrictions import RailcardRestrictionRow, RestrictionIndex
from parse_report import ParseReport, count, decode_lines, read_feed_files

ROUNDING_STEP_PENCE = 5

# "1/3 off" is the published discount for the mainstream UK railcards, Two
# Together included. The feed carries the authoritative rules in its dis and frr
# files; see adr/ADR-0002-budget-semantics-and-railcards.md for the upgrade path.
RAILCARD_DISCOUNT = Fraction(2, 3)

# The station KB FareLocations feed describes fare locations; it does not carry
# settlement metadata. Real DTD builds use ONS Census 2021 data instead: one
# primary settlement class from BUA size bands, plus independent coastal facets.
# The generated cache lives beside the downloaded feed, so later builds remain
# deterministic and do not need a network connection.
ONS_BUILT_UP_AREAS_DATASET_URL = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "townsandcitiescharacteristicsofbuiltupareasenglandandwalescensus2021"
)
ONS_BUILT_UP_AREAS_FILE_URL = (
    "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
    "townsandcitiescharacteristicsofbuiltupareasenglandandwalescensus2021/2021/"
    "townsandcitiescharacteristicsofbuiltupareasenglandandwalescensus2021.xlsx"
)
ONS_COASTAL_BUILT_UP_AREAS_DATASET_URL = (
    "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/"
    "coastalcommunitiescharacteristicsofbuiltupareasenglandandwalescensus2021"
)
ONS_COASTAL_BUILT_UP_AREAS_FILE_URL = (
    "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/"
    "coastalcommunitiescharacteristicsofbuiltupareasenglandandwalescensus2021/current/"
    "coastalcommunitiescharacteristicsofbuiltupareasenglandandwalescensus2021.xlsx"
)
# UK Learning Providers publishes the UK's universities as linked open data
# keyed by the official UKPRN, with the provider's town in the same record.
# HESA and Office for Students both gate their provider files behind a login,
# so this is the one university list that can be read and re-checked from a
# script without an account.
LEARNING_PROVIDERS_FILE_URL = (
    "http://learning-provider.data.ac.uk/data/learning-providers-plus.tsv"
)
UNESCO_WORLD_HERITAGE_DATASET_URL = "https://whc.unesco.org/en/list"
LOCATION_TYPE_SOURCE = (
    "Office for National Statistics, Census 2021 built-up-area size bands and "
    "coastal classification"
)
# The cited ONS workbook covers England (excluding London) and Wales. London
# station names therefore cannot match its settlement rows, and the major
# stations in Scotland and Northern Ireland cannot match a national table that
# does not cover those countries. Keep that gap explicit rather than allowing
# every unmatched station to be called "other".
#
# These are station-to-settlement fallbacks, not a second guess at the ONS
# bands. A London name is in the ONS Greater London region, whose capital
# built-up area is a major BUA; the remaining codes are reviewed classifications
# for the largest destinations outside the workbook's coverage. They are applied
# only after the ONS/name lookup misses, so a future ONS match always wins.
LONDON_STATION_CRS = frozenset({
    "ACT", "BAT", "BFN", "BKF", "BWD", "CDL", "CHC", "CHT", "CLJ", "CBR",
    "CTK", "DLK", "DLP", "ECR", "EUS", "FST", "GLR", "GTN", "HAY", "HMY",
    "IPD", "KGX", "KNI", "LBG", "LDY", "LES", "LST", "MYB", "PAD", "PIM",
    "RGY", "STP", "SUR", "TUL", "VIC", "WAT", "WDM", "WIC", "WLP", "WOL", "WWC",
})
MAJOR_UK_STATION_FALLBACKS = {
    # Scotland
    "ABD": "city", "DEQ": "city", "EDB": "city", "GLC": "city", "INV": "city",
    "MAN": "city", "PER": "city", "QGS": "city", "SGL": "city",
    # Wales outside the England-and-Wales BUA workbook's usual settlement names
    "CDD": "city", "SWA": "city", "NPT": "town",
    # Northern Ireland
    "BNV": "city", "BHC": "city", "LBN": "town", "BNG": "town", "LAR": "town",
    "NIR": "town", "PTN": "town", "LDY": "city", "BCH": "town", "BFL": "town",
    "BQU": "town", "BHD": "town", "WRE": "town",
    # England. A reviewed list, used only where the ONS built-up-area workbook
    # has no row for the station, so a major city is not filed as "other".
    "NCL": "city", "NCZ": "city", "NCX": "city", "BMG": "city", "BMH": "city",
    "BML": "city", "BCU": "city", "BHM": "city", "SOL": "city", "LEI": "city",
    "TRU": "city", "BRI": "city", "EXC": "city", "EXT": "city", "SOU": "city",
    "STP": "city", "HGY": "city", "YRK": "town", "WKF": "town", "HUL": "town",
}
LOCATION_FALLBACK_SOURCE = (
    "ONS 2021 geography coverage with reviewed London, Scottish, Welsh, "
    "Northern Ireland, major-city, and reach-ranked settlement fallbacks"
)
LOCATION_BAND_TYPES = {
    "major": "city",
    "large": "city",
    "medium": "town",
    "small": "small_town",
    "minor": "village",
}

# Some stations the workbook cannot name are nevertheless an obvious
# settlement, and the page's "No settlement band" answer was poor UX for
# them. This reviewed list is the floor that removes that answer from the
# destinations a page can actually price. Each entry is a judgement, so it
# lives beside the other reviewed lists and is only applied to stations the
# feed contains.
REVIEWED_SETTLEMENT_FALLBACKS: dict[str, str] = {
    # Grantham, Sheffield, Rotherham, Hyde and the Yorkshire settlements
    "DOR": "town", "HOP": "village", "DAN": "town", "MHS": "town",
    "RMC": "city", "CLN": "village", "EDL": "village", "KIV": "village",
    "SWN": "town", "BTD": "village", "BYK": "village", "AWK": "village",
    "NMC": "small_town", "MRP": "village", "SRN": "village", "BDY": "village",
    "BNT": "village", "HYC": "town", "HYT": "town", "CGW": "village",
    "CYB": "village", "HPE": "village", "BCJ": "village",
    # Attenborough is a village; the same page also earns the nature facet.
    "ATB": "village",
    # Settlements the workbook misses because the feed's station name carries a
    # qualifier it omits ("Berwick on Tweed", "Newark Northgate"), or a name it
    # does not hold at all. Each is the settlement the station is named for.
    "ALM": "village", "ARB": "town", "BDQ": "city", "BEE": "town",
    "BUH": "village", "BWK": "town", "CBG": "city", "CLM": "village",
    "DEE": "city", "DUN": "town", "ELO": "village", "FKG": "small_town",
    "GLE": "village", "HBB": "village", "HRS": "town", "HVN": "village",
    "HYM": "village", "INK": "village", "KDY": "town", "KIN": "village",
    "KTL": "village", "LAG": "village", "LEU": "village", "LGM": "small_town",
    "LJL": "city", "LPY": "city", "MTS": "town", "NLW": "village",
    "NNG": "town", "PIT": "village", "PTH": "city", "RAU": "village",
    "RDF": "village", "SHY": "town", "SPO": "village", "STG": "city",
    "STN": "town", "TPC": "village", "WFL": "village", "WWL": "village",
    # Nottingham Express Transit and East Midlands Parkway tram stops, and
    # park-and-ride platforms named after the village they serve
    "EMD": "village", "PEA": "village", "PPR": "town",
    # Further settlements the workbook does not name, checked against the feed
    "BKM": "town", "BLW": "town", "DVP": "town", "GBL": "town", "LTG": "village",
    "MDL": "village", "MRD": "village", "SAF": "village", "SGB": "town",
    # Audit A2: the unsourced destinations ranked by how many origins reach
    # them, reviewed one entry at a time under the same rule as everything
    # above -- the class of the settlement the station serves. A station in
    # Greater London, Glasgow, Cardiff, Manchester, Liverpool, Newport or the
    # West Midlands conurbation sits inside that city's built-up area and
    # inherits its class, because the workbook would have matched the same
    # settlement if the feed's name had lined up. A station outside the
    # workbook's nations or its name gets its town's size band. Where the size
    # sat on a band boundary the entry was left out rather than guessed, and
    # the coverage report keeps naming the station instead.
    #
    # London localities: city (the capital's built-up area, as with every
    # LONDON_STATION_CRS entry).
    "ZFD": "city", "SFA": "city", "QRP": "city", "PMR": "city",
    "EDW": "city", "NDL": "city", "NXG": "city", "SBM": "city",
    "WBP": "city", "KPA": "city", "SPB": "city", "RMD": "city",
    # Glasgow localities: city (GLC, GLR and QGS already carry that class).
    "AND": "city", "ANL": "city", "AXP": "city", "BCG": "city", "CAY": "city",
    "CML": "city", "DST": "city", "DMC": "city", "DMY": "city",
    "EST": "city", "EXG": "city", "GAR": "city", "GRS": "city",
    "HST": "city", "HYN": "city", "JOR": "city", "MTV": "city",
    "PTK": "city", "RRN": "city", "SCH": "city", "SLS": "city",
    "SPR": "city", "AGS": "city", "BIO": "city",
    # Cardiff localities, and the three Cardiff stations whose qualifier kept
    # them out of the workbook's "Cardiff" row: city (as XCF Cardiff Airport).
    "CYS": "city", "LLN": "city", "LLS": "city", "NNP": "city",
    "RHI": "city", "LVT": "city", "WHT": "city", "FRW": "city",
    "DCT": "city", "COY": "city", "TGS": "city", "RDR": "city",
    "HHL": "city", "WNG": "city", "FER": "city", "CDF": "city",
    "CDQ": "city", "CDB": "city",
    # Manchester, Liverpool, Newport and the West Midlands conurbation.
    "MCO": "city", "EDY": "city", "LIV": "city", "NWP": "city",
    "SAD": "city",
    # Towns outside the workbook's reach or its names: Runcorn, Preston,
    # Motherwell, Hamilton, Airdrie, Clydebank, Falkirk, Coatbridge,
    # Airbles, Wrexham and Cwmbran.
    "RUE": "town", "PRE": "town", "MTH": "town", "HNC": "town",
    "HNW": "town", "ADR": "town", "CYK": "town", "CMO": "town",
    "COA": "town", "CBS": "town", "BAI": "town", "KWD": "town",
    "AIR": "town", "DRU": "town", "DMR": "town", "SIN": "town",
    "WRX": "town", "CWM": "town",
    # Small towns: Maesteg (as MST), Ebbw Vale, Risca, Pontypool,
    # Llandrindod, Galashiels, Linlithgow, Abergele, Larbert, Shotts,
    # Armadale, Blantyre, Dinas Powys, Cobham, Claygate, Earlstown,
    # Milngavie, Bearsden, Westerton, Stepps and Hengoed.
    "MEW": "small_town", "EBB": "small_town", "EBV": "small_town",
    "RCA": "small_town", "PPL": "small_town", "LLO": "small_town",
    "GAL": "small_town", "LIN": "small_town", "AGL": "small_town",
    "LBT": "small_town", "SHS": "small_town", "ARM": "small_town",
    "BLT": "small_town", "DNS": "small_town", "CSD": "small_town",
    "CLG": "small_town", "ERL": "small_town", "MLN": "small_town",
    "BRN": "small_town", "WES": "small_town", "SPS": "small_town",
    "HNG": "small_town",
    # Villages: Sunningdale, Clandon, Horsley, Hinchley Wood, Oxshott,
    # Effingham, Llanfairpwll, Bodorgan, Llanbister, Pantyffynnon, Llangadog,
    # Llangammarch, Llanwrda, Llanwrtyd, Cilmeri, Dolau, Builth Road, Stow,
    # Bynea, Glan Conwy, Gorebridge, Carstairs, Bowling, Carfin, Holytown,
    # Deganwy, Llwynypia, Ton Pentre, Troed y Rhiw, Trehafod, Ynyswen,
    # Gilfach Fargoed, Pengam, Quakers Yard, Tondu and Tir Phil.
    "SNG": "village", "CLA": "village", "HSY": "village", "HYW": "village",
    "OXS": "village", "EFF": "village", "LPG": "village", "BOR": "village",
    "LLT": "village", "PTF": "village", "LLG": "village", "LLM": "village",
    "LNR": "village", "LNW": "village", "CIM": "village", "DOL": "village",
    "BHR": "village", "SOI": "village", "BYE": "village", "GCW": "village",
    "GBG": "village", "CRS": "village", "BWG": "village", "CRF": "village",
    "HLY": "village", "DGY": "village", "LLY": "village", "TPN": "village",
    "TRD": "village", "TRH": "village", "YNW": "village", "GFF": "village",
    "PGM": "village", "QYD": "village", "TDU": "village", "TIR": "village",
}

# An airport station is a destination in its own right, and the settlement it
# serves is still a place a reader might budget for. These are the settlement
# classes behind the airport list below, so an airport row is not left as the
# unsourced remainder.
AIRPORT_SETTLEMENT_CLASSES: dict[str, str] = {
    "APN": "city", "BHI": "city", "EDA": "village", "EMA": "village",
    "GGT": "city", "GTW": "city", "HAF": "city", "HLL": "city", "HWA": "city",
    "HWE": "city",    "HWV": "city", "HWX": "city", "HXX": "city", "IVA": "city",
    "LHR": "city", "LJL": "city", "LPD": "city", "LTN": "city", "LUA": "city",
    "MIA": "city", "MNA": "city", "PRA": "town", "RHA": "city", "SIA": "city", "SOA": "city",
    "SSD": "village", "TEA": "village", "XCF": "city", "XFI": "village",
    "XPB": "city", "XQB": "village", "XTH": "village", "ZHJ": "city",
}
REVIEWED_SETTLEMENT_FALLBACKS.update(AIRPORT_SETTLEMENT_CLASSES)

# Settlement class and destination facets are deliberately separate. A station
# has exactly one primary settlement class, while independent tags such as
# ``seaside`` may overlap it. The UI and payload both consume this catalogue so
# adding a sourced type does not require another hard-coded HTML checkbox.
#
# A facet is added by writing one entry in DESTINATION_FACET_SOURCES: the label
# the reader sees, the dataset it comes from, where that dataset lives, what
# geography it covers, and which reader turns it into settlement names. The
# filter chips, the payload, the generated cache's provenance, and the
# reference-data file are all derived from that list, so there is no second
# place to remember to update. ``reviewed_station_codes`` is the escape hatch
# for a facet no published dataset names at station level; it is only
# intersected with stations the feed actually contains, and the entry says so
# in its ``source`` text rather than implying an official list. A facet the
# published sources cannot name at all, but whose stations the feed's own names
# identify, declares ``reviewed_name_markers`` instead: the markers are matched
# against the feed's station name, so a new coach stop or parkway is tagged
# without a code being written for it.
@dataclass(frozen=True)
class DestinationFacet:
    """One destination facet, its official source, and how to read it."""

    key: str
    label: str
    source: str
    url: str
    coverage: str
    reader: str
    reviewed_station_codes: frozenset[str] = frozenset()
    reviewed_name_markers: tuple[str, ...] = ()
    # Settlements whose own name merely contains a marker -- Bushey, BUSBY,
    # CAMBUSLANG and Shepherd's Bush are places, not interchanges. The feed
    # truncates names, so a substring marker is the only way to catch
    # "BPOOL NTHBUSTRAM", and these are the settlements it catches wrongly.
    excluded_station_codes: frozenset[str] = frozenset()

    @property
    def is_reviewed(self) -> bool:
        return bool(self.reviewed_station_codes or self.reviewed_name_markers)


# Island settlements are the one facet with no published settlement list this
# project can read: Ordnance Survey Open Names and the Scottish islands layer
# are either gated or carry no names, and UNESCO names whole sites rather than
# the towns inside them. These station codes were reviewed against the DTD
# feed's station names instead, and each is a settlement on Anglesey, the Isle
# of Wight, the Isle of Sheppey, Bute, or a Scottish island the feed serves.
# A new feed revision can add island stations without adding them here, so this
# list is a floor, not a ceiling.
ISLAND_STATION_CRS = frozenset({
    # Anglesey
    "HHD", "VAL",
    # Isle of Wight
    "BDN", "ECW", "FSB", "LKE", "RYD", "RYP", "RYR", "SAB", "SAN", "SHN", "WTW",
    "XRD", "YMH",
    # Isle of Sheppey
    "KML", "SWL", "SSS",
    # Scottish islands
    "ADS", "CRU", "CTB", "KYL", "MLG", "PEE", "RTY", "SCB", "SOY", "SOS", "ULP",
})

# Airport stations are their own destination category: a reader budgeting for
# a city centre does not mean the airport bus stop or the airport park-and-ride.
# The codes are the feed's own names for a rail station serving a UK airport.
AIRPORT_STATION_CRS = frozenset({
    "APN", "BHI", "EDA", "EMA", "GGT", "GTW", "HAF", "HLL", "HWA", "HWE",
    "HWV", "HWX", "HXX", "IVA", "LHR", "LJL", "LPD", "LTN", "LUA", "MIA",
    "MNA", "PRA", "RHA", "SIA", "SOA", "SSD", "TEA", "XCF", "XFI", "XQB",
    "XTH", "XPB", "ZHJ",
})

# The Wildlife Trusts run roughly 2,300 reserves across the UK. This reviewed
# list records the station a reader reaches them from; the trust names and the
# reserve pages are in the source text so the evidence is checkable. It is a
# floor, not a ceiling: a reserve added later needs one entry here.
WILDLIFE_TRUSTS = (
    "Alderney", "Avon", "Berkshire, Buckinghamshire and Oxfordshire",
    "Birmingham and the Black Country", "Cheshire", "Cornwall", "Cumbria",
    "Derbyshire", "Devon", "Dorset", "Durham", "Essex", "Gloucestershire",
    "Gwent", "Hampshire and Isle of Wight", "Herefordshire",
    "Herts and Middlesex", "Isles of Scilly", "Kent",
    "Leicestershire and Rutland", "Lincolnshire", "London", "Manx",
    "Montgomeryshire", "Norfolk", "North Wales", "Northumberland",
    "Nottinghamshire", "Radnorshire", "Scottish", "Sheffield and Rotherham",
    "Shropshire", "Somerset", "Staffordshire", "Suffolk", "Surrey", "Sussex",
    "Tees Valley", "Bedfordshire, Cambridgeshire and Northamptonshire",
    "Birmingham and the Black Country", "Lancashire, Manchester and North Merseyside",
    "South and West Wales", "Ulster", "Warwickshire", "Wiltshire",
    "Worcestershire",
)
NATURE_SITE_STATION_CRS = frozenset({
    # Attenborough Nature Reserve, five minutes from the station on the trust's
    # own "plan your visit" page (Nottinghamshire Wildlife Trust)
    "ATB",
    # Martin Mere Wetland Centre, named as the recommended station on WWT's
    # own directions page (Wildfowl and Wetlands Trust, the reserve the
    # Lancashire, Manchester and North Merseyside Wildlife Trust sits beside)
    "BCB", "BCJ",
    # Thorndon Country Park, "close to Brentwood station" per the trust
    # (Essex Wildlife Trust)
    "BRE",
    # Weeting Heath, about 3.5 km from Brandon on the only documented walk
    # (Norfolk Wildlife Trust)
    "BND",
    # Sevenoaks Wildlife Reserve, just under 2 km from the station out of town
    # and up past the A25 (Kent Wildlife Trust)
    "SEV",
    # Bodenham Arboretum, about fifteen minutes from Hartlebury
    # (Worcestershire Wildlife Trust)
    "HBY",
    # WWT Slimbridge: "the nearest train station is Cam & Dursley"
    "CDU",
    # The three London Wildlife Trust sites that name their station themselves
    "HAY",  # Yeading Brook Meadows, 30 minutes from Hayes and Harlington
    "ZHX",  # Huckerby's Meadows, 15 minutes from Hatton Cross
    "ZHD",  # Gutteridge Wood and Meadows, 12 minutes from Hillingdon
    # Reserves whose trust names no station of its own, checked against the
    # trust's reserve page
    "BKA",  # Bookham Common (Surrey Wildlife Trust)
    "HLS",  # Titchfield Haven (Hampshire and Isle of Wight Wildlife Trust)
})
# Three places a reader might expect here are deliberately absent: Kempton Park
# is one of the Royal Parks, Epping Forest is run by Epping Forest District
# Council, and Rainham Marshes is an RSPB reserve. None of them is a Wildlife
# Trusts site, so tagging them would be a false claim.

# Locations whose purpose is to move people between networks: coach and bus
# stations, tram and metro stops, stadium stations, and parkway or park-and-ride
# platforms. These are destinations a reader can travel to, and without the
# tag the page had no answer for them at all. Most are found by the facet's
# name markers; the codes here are the ones whose names say nothing (a park and
# ride named after the village it serves, for instance).
TRANSPORT_STATION_CRS = frozenset({
    # Nottingham Express Transit and East Midlands Parkway tram stops
    "EMD", "LGM", "PEA",
    # Park and ride named after its settlement
    "PPR", "TPC",
})

# UNESCO's list names whole properties, not the towns inside them, so the
# settlement side of a World Heritage facet is a reviewed list. Each tuple is
# (site id, official site name, feed station names). The reader checks the ids
# against the live list: a site that has been delisted stops contributing, and
# a curated station name that no longer matches anything is reported rather
# than silently doing nothing. Keeping the title beside the stations also lets
# the page explain why a destination earned the tag instead of reducing the
# evidence to an unexplained boolean.
HERITAGE_PROPERTIES: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (370, "Durham Castle and Cathedral", ("Durham",)),
    (374, "Castles and Town Walls of King Edward in Gwynedd", ("Caernarfon", "Conwy", "Harlech")),
    (422, "English Lake District", ("Ulverston", "Windermere")),
    (426, "Westminster Palace, Westminster Abbey and St Margaret's Church", ("Westminster Und",)),
    (429, "New Lanark", ("Lanark",)),
    (430, "Hadrian's Wall", ("Carlisle", "Chester", "Corbridge", "Newcastle")),
    (488, "Tower of London", ("Tower Hill Und",)),
    (496, "Canterbury Cathedral, St Augustine's Abbey, and St Martin's Church", ("Canterbury East", "Canterbury West", "Dover Priory")),
    (514, "Heart of Neolithic Orkney", ("Stromness",)),
    (728, "Old and New Towns of Edinburgh", ("Edinburgh",)),
    (1028, "Saltaire", ("Bradford F Sq", "Bradford Interch", "Saltaire")),
    (1029, "Dorset and East Devon Coast", ("Exmouth", "Poole", "Swanage", "Weymouth")),
    (1030, "Derwent Valley Mills", ("Belper", "Cromford", "Matlock", "Matlock Bath")),
    (1084, "Royal Botanic Gardens, Kew", ("Kew Bridge", "Kew Gardens", "Richmond London")),
    (1215, "Cornwall and West Devon Mining Landscape", ("Camborne", "Redruth", "Truro")),
    (1303, "Pontcysyllte Aqueduct and Canal", ("Wrexham Central", "Wrexham General")),
    (1594, "Jodrell Bank", ("Macclesfield",)),
    (1613, "City of Bath", ("Bath Spa", "Buxton")),
    (1633, "Slate Landscape of Northwest Wales", ("Barmouth", "Caernarfon", "Porthmadog")),
)
HERITAGE_SITE_NAMES_BY_ID = {
    site_id: name for site_id, name, _stations in HERITAGE_PROPERTIES
}
HERITAGE_STATIONS_BY_SITE = {
    site_id: stations for site_id, _name, stations in HERITAGE_PROPERTIES
}
UNESCO_WORLD_HERITAGE_FILE_URL = "https://whc.unesco.org/en/list/xml"

DESTINATION_FACET_SOURCES: tuple[DestinationFacet, ...] = (
    DestinationFacet(
        key="seaside",
        label="Coastal & seaside",
        source=(
            "Office for National Statistics, Census 2021 coastal communities "
            "characteristics of built-up areas"
        ),
        url=ONS_COASTAL_BUILT_UP_AREAS_DATASET_URL,
        coverage="England and Wales",
        reader="ons_coastal_built_up_areas",
    ),
    DestinationFacet(
        key="university",
        label="University towns",
        source=(
            "UK Learning Providers, university providers keyed by UKPRN and "
            "HESA provider id"
        ),
        url=LEARNING_PROVIDERS_FILE_URL,
        coverage="United Kingdom",
        reader="uk_learning_provider_towns",
    ),
    DestinationFacet(
        key="heritage",
        label="World heritage",
        source=(
            "UNESCO World Heritage List, UK properties, with a reviewed list "
            "of the stations those properties are reached from"
        ),
        url=UNESCO_WORLD_HERITAGE_DATASET_URL,
        coverage="United Kingdom",
        reader="unesco_world_heritage_stations",
    ),
    DestinationFacet(
        key="island",
        label="Islands",
        source=(
            "reviewed island station list (no official UK settlement-level "
            "island list is published as open data)"
        ),
        url="",
        coverage="England, Wales and Scotland, as covered by the DTD feed",
        reader="reviewed_station_codes",
        reviewed_station_codes=ISLAND_STATION_CRS,
    ),
    DestinationFacet(
        key="airport",
        label="Airports",
        source=(
            "reviewed rail stations serving a UK airport, checked against the "
            "UK airport station list and the feed's own station names"
        ),
        url="https://www.nationalrail.co.uk/travel-information/airport-stations/",
        coverage="United Kingdom, as covered by the DTD feed",
        reader="reviewed_station_codes",
        reviewed_station_codes=AIRPORT_STATION_CRS,
    ),
    DestinationFacet(
        key="nature",
        label="Nature sites",
        source=(
            "reviewed list of stations reaching The Wildlife Trusts' reserve "
            "sites (46 member trusts) and the Wildfowl and Wetlands Trust's "
            "wetland centres, cross-referenced against the station each reserve "
            "or trust page names"
        ),
        url="https://www.wildlifetrusts.org/nature-reserves",
        coverage="United Kingdom, as covered by the DTD feed",
        reader="reviewed_station_codes",
        reviewed_station_codes=NATURE_SITE_STATION_CRS,
    ),
    DestinationFacet(
        key="transport",
        label="Transport interchanges",
        source=(
            "reviewed coach, tram, metro, stadium, and parkway or park-and-ride "
            "locations, identified from the feed's own station names and each "
            "operator's interchange list"
        ),
        url="",
        coverage="United Kingdom, as covered by the DTD feed",
        reader="reviewed_station_codes",
        reviewed_station_codes=TRANSPORT_STATION_CRS,
        # The markers are what let a new coach stop or parkway earn the tag
        # without a code here. They are deliberately narrow: a name that says
        # BUS, TRAM, METRO or STADIUM, or ends in a parkway or park-and-ride
        # marker, is a node in a network rather than a settlement.
        reviewed_name_markers=(
            "BUS", "TRAM", "METRO", "METROLINK", "STADIUM", "PARKWAY", "PKWY",
            "S PWAY", "PRK LDNR",
        ),
        excluded_station_codes=frozenset({"BSH", "BUS", "CBL", "SPB"}),
    ),
)
SUPPORTED_DESTINATION_FACETS = frozenset(facet.key for facet in DESTINATION_FACET_SOURCES)
# Bumped when the primary classes change shape, so a cache written before the
# change is recognised rather than trusted.
LOCATION_CACHE_SCHEMA = 3
DESTINATION_FACETS_BY_KEY = {facet.key: facet for facet in DESTINATION_FACET_SOURCES}
# Reader id -> the FaresDb method that returns normalised settlement names for
# it. Registering the reader here keeps a new facet to a registry entry plus a
# method instead of another branch in the loading code.
DESTINATION_FACET_READERS: dict[str, str] = {
    "ons_coastal_built_up_areas": "_read_ons_coastal_facet",
    "uk_learning_provider_towns": "_read_learning_provider_facet",
    "unesco_world_heritage_stations": "_read_unesco_heritage_facet",
}
# The primary settlement classes come from ONS BUA size bands; the facets are
# appended from the registry so a new sourced type shows up in the UI with no
# other edit. The bands are population classes, so the labels say what they
# are: 10,000-24,999 is a town and under 5,000 is a village. There is no
# "No settlement band" chip: a station the published workbooks cannot name is
# still a destination, and a filter that only ever returns an unsourced
# remainder reads as a gap in the page rather than a choice. Those stations keep
# the ``other`` class in the payload, so a build can still audit them.
DESTINATION_TYPE_FILTERS: tuple[tuple[str, str], ...] = (
    ("city", "Cities"),
    ("town", "Towns"),
    ("small_town", "Small towns"),
    ("village", "Villages"),
) + tuple((facet.key, facet.label) for facet in DESTINATION_FACET_SOURCES)


def is_pseudo_station(name: str) -> bool:
    """A name the fare system draws rather than a place a reader can stand.

    Zone boundaries and zoned-area labels (BOUNDARY ZONE 4, BRIGHTON UNIZONE,
    METRO T&W ZONE A) and named coach stops are fare-construction points: the
    DTD feed prices flows through them, so they arrive in the chooser as
    origins you could depart from and at the top of the coverage report as the
    most-reached destinations -- with no train stopping there (audit A6).
    One predicate, wherever a station list is offered.
    """
    upper = name.upper()
    return "ZONE" in upper or "COACH" in upper

# The real feed's standard-return catalogue contains a family of ITX
# placeholder records. They are not purchasable public fares: the current
# audit found EIS/EIF/IF1/IF3/IS0/IS1/IS3 and LIS/LIF at the £0.05/£0.10
# minimum with restriction GA. Keep the names explicit so a future catalogue
# rename cannot silently reintroduce them, while the ITX name check catches
# new members of the same family.
PLACEHOLDER_TICKET_CODES = frozenset({
    "EIS", "EIF", "IF1", "IF3", "IS0", "IS1", "IS3", "LIS", "LIF",
})


def _offsets(spec: tuple[tuple[str, int], ...]) -> dict[str, tuple[int, int]]:
    offsets: dict[str, tuple[int, int]] = {}
    position = 0
    for name, width in spec:
        offsets[name] = (position, position + width)
        position += width
    return offsets


def _text(line: str, offsets: dict[str, tuple[int, int]], name: str) -> str:
    start, end = offsets[name]
    return line[start:end].strip()


FLOW_F = (
    ("update_marker", 1),
    ("record_type", 1),
    ("origin_nlc", 4),
    ("destination_nlc", 4),
    ("route_code", 5),
    ("status_code", 3),
    ("usage_code", 1),
    ("direction", 1),
    ("end_date", 8),
    ("start_date", 8),
    ("toc", 3),
    ("cross_london", 1),
    ("non_standard_discount", 1),
    ("publication_indicator", 1),
    ("flow_id", 7),
)

FLOW_T = (
    ("update_marker", 1),
    ("record_type", 1),
    ("flow_id", 7),
    ("ticket_code", 3),
    ("fare_pence", 8),
    ("restriction_code", 2),
)

# Only the leading fields are needed. Later location fields carry railcard,
# zone, and LU data that budget discovery does not read.
LOCATION = (
    ("update_marker", 1),
    ("record_type", 1),
    ("uic_code", 7),
    ("end_date", 8),
    ("start_date", 8),
    ("quote_date", 8),
    ("admin_area_code", 3),
    ("nlc", 4),
    ("description", 16),
    ("crs", 3),
    # The next ten characters hold location attributes this reader does not
    # interpret. Keeping them in the layout preserves the published offsets.
    ("location_attributes", 10),
    ("group_nlc", 4),
)

TICKET_TYPE = (
    ("update_marker", 1),
    ("ticket_code", 3),
    ("end_date", 8),
    ("start_date", 8),
    ("quote_date", 8),
    ("description", 15),
    ("tkt_class", 1),
    ("tkt_type", 1),
    ("tkt_group", 1),
    ("last_valid_day", 8),
    ("max_passengers", 3),
    ("min_passengers", 3),
    ("max_adults", 3),
    ("min_adults", 3),
    ("max_children", 3),
    ("min_children", 3),
    ("restricted_by_date", 1),
    ("restricted_by_train", 1),
)

RAILCARD = (
    ("railcard_code", 3),
    ("end_date", 8),
    ("start_date", 8),
    ("quote_date", 8),
    ("holder_type", 1),
    ("description", 20),
    ("restricted_by_issue", 1),
    ("restricted_by_area", 1),
    ("restricted_by_train", 1),
    ("restricted_by_date", 1),
    ("master_code", 3),
    ("display_flag", 1),
    ("max_passengers", 3),
    ("min_passengers", 3),
    ("max_holders", 3),
    ("min_holders", 3),
    ("max_accompanying_adults", 3),
    ("min_accompanying_adults", 3),
    ("max_adults", 3),
    ("min_adults", 3),
)

MINIMUM_FARE = (
    ("railcard_code", 3),
    ("ticket_code", 3),
    ("end_date", 8),
    ("start_date", 8),
    ("minimum_fare_pence", 8),
)

# A record shorter than its layout is truncated, and slicing it anyway hands
# back empty fields that read as real values: a cut off fare becomes 0, and a cut
# off flow id becomes a flow keyed on nothing. The width of the fields actually
# read is the cheapest test that says so.
def _read_width(spec: tuple[tuple[str, int], ...], last_field: str) -> int:
    offsets = _offsets(spec)
    end = offsets[last_field][1]
    return end


FLOW_F_WIDTH = _read_width(FLOW_F, "flow_id")
FLOW_T_WIDTH = _read_width(FLOW_T, "restriction_code")

FLOW_F_OFFSETS = _offsets(FLOW_F)
FLOW_T_OFFSETS = _offsets(FLOW_T)
# The same spans as slice objects, for the FFL reader: a _text call per field
# cost a Python call and a dict lookup for each of the 53.8M fields it reads,
# and the reader keeps only these (audit B2).
FLOW_F_SLICES = {name: slice(start, end) for name, (start, end) in FLOW_F_OFFSETS.items()}
FLOW_T_SLICES = {name: slice(start, end) for name, (start, end) in FLOW_T_OFFSETS.items()}
LOCATION_OFFSETS = _offsets(LOCATION)
TICKET_TYPE_OFFSETS = _offsets(TICKET_TYPE)
RAILCARD_OFFSETS = _offsets(RAILCARD)
MINIMUM_FARE_OFFSETS = _offsets(MINIMUM_FARE)

STANDARD_CLASS = "2"
RETURN_TYPE = "R"

# The reviewed public selector. These are the ticket codes whose real ticket
# type is standard class, return, marked unrestricted by train, and whose name
# is exactly ANYTIME DAY R in the DTD feed. The code set is fixed here rather
# than derived by a name test, so a future ticket-catalogue change cannot widen
# what the site publishes without a person editing this table.
#
# The real DTD feed carries fares for 8AE, HX9, SDR and XAR. AAB and E2R are
# listed because the ticket catalogue defines them as the same product; they are
# harmless to include and would otherwise be an unexplained omission.
REVIEWED_ANYTIME_DAY_RETURN_TICKETS: dict[str, str] = {
    "8AE": "ANYTIME DAY R",
    "AAB": "ANYTIME DAY R",
    "E2R": "ANYTIME DAY R",
    "HX9": "ANYTIME DAY R",
    "SDR": "ANYTIME DAY R",
    "XAR": "ANYTIME DAY R",
}


# The restriction code the DTD uses for a yield-managed fare. A row carrying it
# is train-specific whatever its ticket is called, and a ticket called ADVANCE
# is train-specific whatever code it carries, so a caller asks about both
# through one predicate rather than retyping either test.
ADVANCE_RESTRICTION_CODE = "AS"


def is_advance_ticket(name: object) -> bool:
    """Whether a ticket name identifies a yield-managed, train-specific fare."""
    return bool(re.search(r"\bADV(?:ANCE)?\b", str(name or "").upper()))


def is_advance_fare(ticket_name: object, restriction_code: object) -> bool:
    """Whether a published fare row is an Advance single, by either test."""
    return is_advance_ticket(ticket_name) or str(
        restriction_code or ""
    ).strip().upper() == ADVANCE_RESTRICTION_CODE


@dataclass(frozen=True)
class Location:
    nlc: str
    crs: str
    name: str
    group_nlc: str


@dataclass(frozen=True)
class TicketType:
    code: str
    name: str
    tkt_class: str
    tkt_type: str
    restricted_by_train: bool

    @property
    def is_standard_return(self) -> bool:
        return self.tkt_class == STANDARD_CLASS and self.tkt_type == RETURN_TYPE

    @property
    def is_standard_single(self) -> bool:
        return self.tkt_class == STANDARD_CLASS and self.tkt_type == "S"

    @property
    def is_advance(self) -> bool:
        """Whether the catalogue explicitly identifies a yield-managed fare.

        This is the one definition of "advance": the page builder asks the
        ticket and the restriction code through the same test rather than
        retyping the word, so a catalogue that spells it differently cannot
        leave the page labelling a fare two ways.
        """
        return is_advance_ticket(self.name)


@dataclass(frozen=True, slots=True)
class Flow:
    flow_id: str
    origin_nlc: str
    destination_nlc: str
    route_code: str
    direction: str
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True, slots=True)
class Fare:
    ticket_code: str
    pence: int
    restriction_code: str


@dataclass(frozen=True)
class Railcard:
    code: str
    name: str
    min_adults: int
    max_adults: int


@dataclass(frozen=True)
class Reachable:
    crs: str
    station: str
    ticket_code: str
    ticket_name: str
    standard_pence: int
    best_pence: int
    railcard_pence: int | None
    party_pence: int
    off_peak: bool
    restriction_code: str
    # The fare's flow context is retained so a page builder can evaluate a
    # railcard rule again without guessing which route produced the row.
    route_code: str
    origin_nlc: str
    destination_nlc: str


def format_pence(pence: int) -> str:
    return f"£{pence // 100}.{pence % 100:02d}"


def _round_down_to(value: Fraction, step: int) -> int:
    units = value.numerator // (value.denominator * step)
    return units * step


def _parse_dtd_date(value: str) -> date | None:
    """Parse a blank or DDMMYYYY feed date without guessing its format."""
    if not value:
        return None
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"DTD date {value!r} is not DDMMYYYY")
    return date(int(value[4:8]), int(value[2:4]), int(value[0:2]))


def _require_width(line: str, width: int, what: str) -> None:
    """Refuse a record that is shorter than the fields it needs."""
    if len(line) < width:
        raise ValueError(f"{what} record is {len(line)} characters, needs {width}")


def _tally(counts: dict[str, int] | None, reason: str) -> None:
    """Count why a fare or flow did not become a destination, when asked."""
    if counts is not None:
        counts[reason] = counts.get(reason, 0) + 1


class FaresDb:
    """Indexes the feed files that budget discovery reads."""

    def __init__(self) -> None:
        self.locations_by_nlc: dict[str, Location] = {}
        self.locations_by_crs: dict[str, Location] = {}
        # Destination settlement type is reference data, not a fares LOC field.
        # A reviewed JSON cache beside the feed is preferred; a real DTD build
        # can populate it from the ONS Census built-up-area source.
        self.location_types_by_crs: dict[str, str] = {}
        self.location_facets_by_crs: dict[str, set[str]] = {}
        self.location_type_source: str | None = None
        # One station code can hold several location codes, and a real feed does
        # this for most towns. Flows are keyed by location code, so a query has
        # to consider all of them or it misses fares that are right there.
        self.nlcs_by_crs: dict[str, set[str]] = {}
        self.ticket_types: dict[str, TicketType] = {}
        self.railcards: dict[str, Railcard] = {}
        self.flows: dict[str, Flow] = {}
        self.fares_by_flow: dict[str, dict[str, Fare]] = {}
        # Flows grouped by every NLC that touches them: most are usable only
        # from their recorded origin, but a reversible (``direction == "R"``)
        # flow is indexed under both endpoints, so a bucket can hold inbound
        # flows too. The query loop swaps the recorded destination when it
        # entered via the far side (audit A4). destinations_within asks the
        # same question per origin; scanning every flow for each origin would
        # turn a full-network build into 2,500 full scans.
        self.flows_touching_nlc: dict[str, list[Flow]] = {}
        self.minimum_fares: dict[tuple[str, str], int] = {}
        self.restrictions = RestrictionIndex()
        self.report = ParseReport()
        self.files_read = self.report.files_read
        # A single-origin build only needs fares queryable from that origin.
        # Reversible flows count in both directions. The national feed has
        # millions of unrelated fare records, so retaining
        # every Fare object makes the local app spend most of its time building
        # prices it will never query. This is None for the normal/full database.
        self._focus_origin_nlcs: set[str] | None = None
        # Focus caches are named by the feed and origin, but keep the identity
        # inside the object too so a hand-reused path cannot silently return a
        # different origin's fares.
        self._cache_origin: str | None = None
        # The whole feed's stats(), recorded when the shared half of a fare
        # index is written. An index database holds only one origin's flows,
        # so recomputing stats() from it would report a slice as the feed
        # (audit B1): every page built through the indexes answers with the
        # same national numbers the full load would have given.
        self.feed_stats: dict[str, int] | None = None

    # -- loading ---------------------------------------------------------

    def _write_cache(self, cache: Path, value: object) -> None:
        """Write a cache atomically without assuming a process-local suffix."""
        cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache.with_name(f"{cache.name}.{os.getpid()}.tmp")
        with temporary.open("wb") as handle:
            pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(cache)

    def write_fare_indexes(
        self,
        base_path: str | Path,
        index_dir: str | Path,
        origins: list[str] | tuple[str, ...],
    ) -> None:
        """Persist common fare metadata once and a small index per origin.

        A worker's page build needs the location/ticket/restriction tables, but
        only the flows and fares queryable from its own origin. Keeping those
        two pieces in the common file would make every origin cache a copy of
        the national feed. The index files therefore contain just the selected
        flow/fare objects; workers load the common file once and apply one
        index per page.
        """
        common = FaresDb()
        common.locations_by_nlc = self.locations_by_nlc
        common.locations_by_crs = self.locations_by_crs
        common.location_types_by_crs = self.location_types_by_crs
        common.location_facets_by_crs = self.location_facets_by_crs
        common.location_type_source = self.location_type_source
        common.nlcs_by_crs = self.nlcs_by_crs
        common.ticket_types = self.ticket_types
        common.railcards = self.railcards
        common.minimum_fares = self.minimum_fares
        common.restrictions = self.restrictions
        common.report = self.report
        common.files_read = common.report.files_read
        common.feed_stats = self.stats()
        self._write_cache(Path(base_path), common)

        directory = Path(index_dir)
        directory.mkdir(parents=True, exist_ok=True)
        for origin in origins:
            origin = origin.strip().upper()
            location = self.locations_by_crs.get(origin)
            if location is None:
                continue
            origin_nlcs = self.nlcs_by_crs.get(origin, {location.nlc})
            flow_ids: set[str] = set()
            flows_touching_nlc: dict[str, list[Flow]] = {}
            for nlc in origin_nlcs:
                selected = [
                    flow
                    for flow in self.flows_touching_nlc.get(nlc, ())
                    if flow.flow_id not in flow_ids
                ]
                if selected:
                    flows_touching_nlc[nlc] = selected
                    flow_ids.update(flow.flow_id for flow in selected)
            self._write_cache(
                directory / f"{origin}.pickle",
                {
                    "schema": 1,
                    "origin": origin,
                    "origin_nlcs": set(origin_nlcs),
                    "flows": {
                        flow_id: self.flows[flow_id]
                        for flow_id in flow_ids
                        if flow_id in self.flows
                    },
                    "fares": {
                        flow_id: self.fares_by_flow.get(flow_id, {})
                        for flow_id in flow_ids
                    },
                    "flows_touching_nlc": flows_touching_nlc,
                },
            )

    @classmethod
    def load_fare_common(cls, common_path: str | Path) -> "FaresDb":
        """Load the shared metadata half of a persisted fares cache."""
        with Path(common_path).open("rb") as handle:
            db = pickle.load(handle)
        if not isinstance(db, FaresDb):
            raise ValueError("invalid common fares cache")
        return db

    @classmethod
    def load_fare_index(
        cls, common_path: str | Path, index_path: str | Path
    ) -> "FaresDb":
        """Load common metadata and one persisted origin index."""
        return cls.apply_fare_index(cls.load_fare_common(common_path), index_path)

    @classmethod
    def apply_fare_index(cls, db: "FaresDb", index_path: str | Path) -> "FaresDb":
        """Apply one origin index to an already loaded common database."""
        with Path(index_path).open("rb") as handle:
            index = pickle.load(handle)
        if not isinstance(index, dict):
            raise ValueError("invalid fares index")
        if index.get("schema") != 1:
            raise ValueError("unsupported fares index schema")
        origin = str(index.get("origin", "")).strip().upper()
        if not origin:
            raise ValueError("fares index has no origin")
        db.flows = index["flows"]
        db.fares_by_flow = index["fares"]
        db.flows_touching_nlc = index["flows_touching_nlc"]
        db._focus_origin_nlcs = set(index["origin_nlcs"])
        db._cache_origin = origin
        return db

    def _preload_focus_locations(self, path: str | Path, origin_crs: str) -> None:
        """Find the origin NLCs before the stream reaches the FFL file.

        DTD archives put LOC after FFL. A quick LOC-only pass lets the FFL
        reader discard unrelated fare records as it streams, without retaining
        a second copy of the feed or changing the normal full-load behaviour.
        """
        root = Path(path)
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if not child.is_file():
                    continue
                if child.suffix.lower() == ".loc":
                    with child.open("rb") as handle:
                        for line in decode_lines(handle, ParseReport()):
                            self._load_location_for_focus(line, origin_crs)
                elif child.suffix.lower() == ".zip" and zipfile.is_zipfile(child):
                    with zipfile.ZipFile(child) as archive:
                        for name in sorted(archive.namelist()):
                            if not name.lower().endswith(".loc"):
                                continue
                            with archive.open(name) as handle:
                                for line in decode_lines(handle, ParseReport()):
                                    self._load_location_for_focus(line, origin_crs)
        elif root.suffix.lower() == ".zip" and zipfile.is_zipfile(root):
            with zipfile.ZipFile(root) as archive:
                for name in sorted(archive.namelist()):
                    if not name.lower().endswith(".loc"):
                        continue
                    with archive.open(name) as handle:
                        for line in decode_lines(handle, ParseReport()):
                            self._load_location_for_focus(line, origin_crs)

    def _load_location_for_focus(self, line: str, origin_crs: str) -> None:
        if _text(line, LOCATION_OFFSETS, "record_type").upper() != "L":
            return
        if _text(line, LOCATION_OFFSETS, "crs").upper() != origin_crs:
            return
        if self._focus_origin_nlcs is not None:
            self._focus_origin_nlcs.add(_text(line, LOCATION_OFFSETS, "nlc"))

    def load_feed(
        self,
        path: str | Path,
        *,
        focus_origin: str | None = None,
        cache_path: str | Path | None = None,
    ) -> "FaresDb":
        """Load a feed, optionally retaining fares for one origin only.

        ``focus_origin`` is for a one-origin page build. It is deliberately not
        used by audit or multi-origin builds, whose results must describe the
        whole feed. When ``cache_path`` is supplied, a focused database is
        persisted atomically and reused on later page builds. The cache is
        opt-in so audit and general analysis retain their complete-feed
        semantics.
        """
        origin = focus_origin.strip().upper() if focus_origin is not None else None
        if cache_path is not None and origin is not None:
            cache = Path(cache_path)
            if cache.is_file():
                try:
                    with cache.open("rb") as handle:
                        loaded = pickle.load(handle)
                    if (
                        isinstance(loaded, FaresDb)
                        and loaded._cache_origin == origin
                    ):
                        return loaded
                except (OSError, EOFError, pickle.PickleError, AttributeError, TypeError):
                    pass

        if focus_origin is not None:
            self._focus_origin_nlcs = set()
            self._preload_focus_locations(path, origin)
        read_feed_files(path, self.report, self._load_lines)
        self._load_location_lookup(path)
        if cache_path is not None and focus_origin is not None:
            self._cache_origin = origin
            cache = Path(cache_path)
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_name(
                f"{cache.name}.{os.getpid()}.tmp"
            )
            with temporary.open("wb") as handle:
                pickle.dump(self, handle, protocol=pickle.HIGHEST_PROTOCOL)
            temporary.replace(cache)
        return self

    def _load_location_lookup(self, path: str | Path) -> None:
        """Load the checked-in reference data, or derive it from its sources.

        ``FareLocationsRefData`` is deliberately not treated as a settlement
        classification: it contains fare-location records, not CRS-to-type
        records. A real DTD download can be recognised by its sibling download
        manifest; only then is a missing cache filled from ONS and the other
        named sources, and written back.

        Several files can describe the same station -- the checked-in
        reference data, a cache beside the feed, an XML lookup -- so facets are
        merged rather than replaced. Overwriting let a stale cache silently
        drop a facet the checked-in file had, and left the answer depending on
        the order the directory happened to be listed in.
        """
        root = Path(path)
        candidates: list[Path] = []
        candidates.extend(
            (Path(__file__).parent / "reference-data").glob("*.json")
        )
        if root.is_dir():
            candidates.extend(root.glob("*.xml"))
            candidates.extend(root.glob("*.json"))
            candidates.extend(root.parent.glob("FareLocationsRefData*.xml"))
            candidates.extend(root.parent.glob("*location*types*.json"))
            candidates.extend(root.parent.glob("*destination*facets*.json"))
        elif root.suffix.lower() == ".zip":
            # The checked-in download lives at feeds/fares/dtd-fares.zip while
            # its reference files live one level up in feeds/. Accept both that
            # layout and feeds/dtd-fares.zip beside its references.
            for base in (root.parent, root.parent.parent):
                candidates.extend(base.glob("FareLocationsRefData*.xml"))
                candidates.extend(base.glob("*location*types*.json"))
                candidates.extend(base.glob("*destination*facets*.json"))
        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            try:
                if candidate.suffix.lower() == ".json":
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    self._load_location_types_json(data)
                else:
                    self._load_location_types_xml(candidate)
            except (OSError, ValueError, ET.ParseError) as error:
                self.report.skip_file(f"{candidate.name}: station classification lookup unreadable: {error}")
            self._apply_major_station_fallbacks()

        # A reviewed facet needs no download, so it is applied whether the
        # types came from a cache, from ONS, or from a synthetic feed.
        self._apply_reviewed_facets()

        if (
            self.location_types_by_crs
            and self.location_type_source != LOCATION_FALLBACK_SOURCE
        ):
            return

        lookup_roots = (
            (root.parent, root.parent.parent)
            if root.suffix.lower() == ".zip"
            else (root.parent,)
        )
        lookup_root = next(
            (
                base
                for base in lookup_roots
                if base.joinpath("download-manifest.json").is_file()
                or any(base.glob("*location*types*.json"))
            ),
            root.parent,
        )
        if lookup_root.joinpath("download-manifest.json").is_file():
            try:
                self._load_ons_location_types()
            except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as error:
                self.report.skip_classification(f"ONS station classification unavailable: {error}")
        for facet in DESTINATION_FACET_SOURCES:
            if facet.is_reviewed:
                continue
            try:
                self._apply_destination_facet(facet)
            except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as error:
                self.report.skip_classification(
                    f"{facet.key} station classification unavailable: {error}"
                )
        # One cache write for the whole pass: the facets above have all landed
        # by now, so a per-facet write would publish a partial classification.
        if self.location_types_by_crs:
            self._write_location_cache(lookup_root / "location-types.json")
        self._apply_major_station_fallbacks()
        self._apply_reviewed_facets()

    @staticmethod
    def _normalise_location_type(value: object) -> str | None:
        text = str(value or "").strip().lower()
        if "city" in text or "cities" in text or text in {"c", "urban", "metropolitan"}:
            return "city"
        if "small" in text and ("town" in text or text == "small"):
            return "small_town"
        if "village" in text or text in {"v", "hamlet"}:
            return "village"
        if "town" in text or text in {"t", "rural"}:
            return "town"
        return "other" if text else None

    def _apply_reviewed_facets(self) -> None:
        """Tag the stations named by a reviewed facet that the feed contains.

        These facets exist because no open settlement list covers them, so the
        entry says so in its source text and the codes are intersected with the
        feed's own stations: a stale code is dropped rather than inventing a
        station. A facet that also declares name markers tags any feed station
        whose own name carries one, which is how a new coach stop reaches the
        page without a code being written for it.
        """
        for facet in DESTINATION_FACET_SOURCES:
            if not facet.is_reviewed:
                continue
            for crs in facet.reviewed_station_codes:
                if crs in self.locations_by_crs:
                    self._tag_station(crs, facet.key)
            for marker in facet.reviewed_name_markers:
                needle = marker.upper()
                for crs, location in self.locations_by_crs.items():
                    if crs in facet.excluded_station_codes:
                        continue
                    if needle in location.name.upper():
                        self._tag_station(crs, facet.key)

    def _apply_destination_facet(self, facet: DestinationFacet) -> None:
        """Tag every station whose settlement is named by the facet's source."""
        if facet.is_reviewed:
            self._apply_reviewed_facets()
            return
        reader = DESTINATION_FACET_READERS.get(facet.reader)
        method = getattr(self, reader, None) if reader else None
        if method is None:
            # A missing reader is a ValueError so the caller reports it as an
            # unreadable source instead of the build dying on a KeyError.
            raise ValueError(f"no reader {facet.reader!r} for facet {facet.key!r}")
        names = method()
        if not names:
            raise ValueError(f"{facet.source} returned no settlement names")
        matched = {
            crs
            for crs, location in self.locations_by_crs.items()
            if self._settlement_matches(location.name, names)
        }
        if facet.key == "heritage":
            # A curated name that no longer names a station is a list that has
            # gone stale, and silence would leave it looking current.
            unmatched = sorted(
                station
                for station in names
                if not any(
                    self._settlement_matches(location.name, {station})
                    for location in self.locations_by_crs.values()
                )
            )
            if unmatched:
                self.report.skip_file(
                    f"heritage: {len(unmatched)} curated station names match no station in this "
                    f"feed: {', '.join(unmatched[:8])}"
                    + (" ..." if len(unmatched) > 8 else "")
                )
        for crs in matched:
            self._tag_station(crs, facet.key)
        if self.location_type_source:
            self.location_type_source = LOCATION_TYPE_SOURCE

    def _apply_major_station_fallbacks(self) -> None:
        """Classify major stations outside the ONS workbook's national coverage."""
        for crs, location in self.locations_by_crs.items():
            if location.name.strip().upper().startswith("LONDON") and crs not in self.location_types_by_crs:
                self.location_types_by_crs[crs] = "city"
        for crs in LONDON_STATION_CRS:
            if crs in self.locations_by_crs and crs not in self.location_types_by_crs:
                self.location_types_by_crs[crs] = "city"
        for crs, kind in MAJOR_UK_STATION_FALLBACKS.items():
            if crs in self.locations_by_crs and crs not in self.location_types_by_crs:
                self.location_types_by_crs[crs] = kind
        for crs, kind in REVIEWED_SETTLEMENT_FALLBACKS.items():
            if crs in self.locations_by_crs and self.location_types_by_crs.get(crs) in (None, "other"):
                self.location_types_by_crs[crs] = kind
        if (
            not self.location_type_source
            and any(
                crs in self.location_types_by_crs
                for crs in set(LONDON_STATION_CRS)
            | set(MAJOR_UK_STATION_FALLBACKS)
            | set(REVIEWED_SETTLEMENT_FALLBACKS)
            )
        ):
            self.location_type_source = LOCATION_FALLBACK_SOURCE
        # A reviewed code the feed does not carry is a dead tail on the list.
        # Every entry here is intersected before it is applied, so a stale code
        # costs nothing at runtime; silence is what lets the list grow one
        # unnoticed (audit A7), the way the heritage reader names an unmatched
        # curated station.
        absent = sorted(
            crs
            for crs in set(LONDON_STATION_CRS)
            | set(MAJOR_UK_STATION_FALLBACKS)
            | set(REVIEWED_SETTLEMENT_FALLBACKS)
            if crs not in self.locations_by_crs
        )
        if absent:
            self.report.skip_file(
                f"{len(absent)} reviewed fallback codes match no station in this "
                f"feed: " + ", ".join(absent[:12])
                + (" ..." if len(absent) > 12 else "")
            )

    def _load_location_types_json(self, data: object) -> None:
        # A cache written under an older schema still holds valid facets, but
        # its primary classes were collapsed into three values and would call
        # every village and small town "other" forever. Drop those records and
        # say so; keeping the facets costs nothing because they are additive.
        if isinstance(data, dict) and isinstance(data.get("schema"), int):
            if data["schema"] < LOCATION_CACHE_SCHEMA and isinstance(data.get("records"), dict):
                self.report.skip_file(
                    f"station classification cache is schema {data['schema']}, this build writes "
                    f"schema {LOCATION_CACHE_SCHEMA}: its primary classes were ignored, its facets kept"
                )
                # Keep the facets, which are additive and still true, and drop
                # only the primary class each record carried.
                data = {
                    **data,
                    "records": {
                        crs: {**value, "primary": None} if isinstance(value, dict) else None
                        for crs, value in data["records"].items()
                    },
                }
        if isinstance(data, dict):
            top_level_facets = data.get("facets")
            if isinstance(top_level_facets, dict):
                if self.location_types_by_crs:
                    self.location_type_source = LOCATION_TYPE_SOURCE
                for crs, value in top_level_facets.items():
                    self._merge_location_facets(crs, value)
            nested = data.get("records")
            if isinstance(nested, dict):
                self.location_type_source = str(
                    data.get("source") or data.get("sourceName") or ""
                ) or self.location_type_source
                has_embedded_facets = any(
                    isinstance(value, dict)
                    and self._normalise_location_facets(value.get("facets", ()))
                    for value in nested.values()
                )
                if self.location_facets_by_crs and not has_embedded_facets:
                    self.location_type_source = LOCATION_TYPE_SOURCE
                for crs, value in nested.items():
                    code = str(crs).strip().upper()
                    raw_facets: object = ()
                    raw_kind: object = value
                    if isinstance(value, dict):
                        raw_kind = value.get("primary", value.get("type"))
                        raw_facets = value.get("facets", ())
                    kind = self._normalise_location_type(raw_kind)
                    if code and kind:
                        self.location_types_by_crs[code] = kind
                    self._merge_location_facets(crs, raw_facets)
                return
        records = data.get("records") if isinstance(data, dict) else data
        if not isinstance(records, (list, tuple)):
            return
        for record in records:
            if not isinstance(record, dict):
                continue
            crs = next((record.get(key) for key in ("crs", "CRS", "crsCode", "locationCode") if record.get(key)), None)
            kind = next((record.get(key) for key in ("type", "classification", "locationType", "LocationClassification") if record.get(key)), None)
            kind = self._normalise_location_type(kind)
            if crs and kind:
                code = str(crs).strip().upper()
                self.location_types_by_crs[code] = kind
                self._merge_location_facets(crs, record.get("facets"))

    def _tag_station(self, crs: str, facet_key: str) -> None:
        self.location_facets_by_crs.setdefault(crs, set()).add(facet_key)

    def _merge_location_facets(self, crs: object, value: object) -> None:
        """Add a station's facets to what is already known about it.

        More than one file can describe the same station, and each may know a
        facet the others do not. Merging keeps a stale cache beside the feed
        from deleting a facet the checked-in reference data recorded.
        """
        code = str(crs).strip().upper()
        facets = self._normalise_location_facets(value)
        if code and facets:
            self.location_facets_by_crs.setdefault(code, set()).update(facets)

    @staticmethod
    def _normalise_location_facets(value: object) -> set[str]:
        if isinstance(value, str):
            value = (value,)
        if not isinstance(value, (list, tuple, set, frozenset)):
            return set()
        return {
            facet
            for item in value
            if (facet := str(item).strip().lower()) in SUPPORTED_DESTINATION_FACETS
        }

    def _load_location_types_xml(self, path: Path) -> None:
        root = ET.parse(path).getroot()
        crs_tags = {"CRS", "CRS_CODE", "CRSCODE", "LOCATION_CRS_CODE", "LOCATIONCRSCODE"}
        kind_tags = {"TYPE", "CLASSIFICATION", "LOCATION_TYPE", "LOCATIONTYPE", "LOCATION_CLASSIFICATION", "LOCATIONCLASSIFICATION"}
        for element in root.iter():
            values: dict[str, str] = {}
            for child in element.iter():
                tag = child.tag.rsplit("}", 1)[-1].upper()
                if child.text and (tag in crs_tags or tag in kind_tags):
                    values.setdefault(tag, child.text.strip())
            for tag, value in element.attrib.items():
                name = tag.rsplit("}", 1)[-1].upper()
                if name in crs_tags or name in kind_tags:
                    values.setdefault(name, value.strip())
            crs = next((values[tag] for tag in crs_tags if tag in values), None)
            kind = next((values[tag] for tag in kind_tags if tag in values), None)
            kind = self._normalise_location_type(kind)
            if crs and kind:
                self.location_types_by_crs[crs.strip().upper()] = kind

    @staticmethod
    def _normalise_settlement_name(value: object) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())

    @classmethod
    def _settlement_name_candidates(cls, name: object) -> list[str]:
        """Return the station name and, for a qualifier, the settlement under it.

        The feed disambiguates with a bracketed county -- "Ascot (Berks)" --
        where the ONS workbook simply says "Ascot". Dropping a trailing
        bracketed qualifier is safe in a way that dropping any other word is
        not, because a county never changes which settlement a station is in.
        """
        text = str(name or "").strip()
        candidates = [cls._normalise_settlement_name(text)]
        bracketed = re.match(r"^(.*?)\s*\([^)]*\)\s*$", text)
        if bracketed and bracketed.group(1).strip():
            candidates.append(cls._normalise_settlement_name(bracketed.group(1)))
        return [candidate for candidate in candidates if candidate]

    def _settlement_matches(self, name: object, settlements: set[str]) -> bool:
        """Say whether a station's name is one of a source's settlements.

        Only the whole name matches. Loosening this to "starts with" is what
        would make Bathgate claim Bath and Bradford-on-Avon claim Bradford, so
        a curated list names stations as the feed writes them instead.
        """
        return any(candidate in settlements for candidate in self._settlement_name_candidates(name))

    @staticmethod
    def _xlsx_cell_value(cell: ET.Element, shared: list[str]) -> str:
        cell_type = cell.attrib.get("t", "")
        if cell_type == "inlineStr":
            return "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
        value = next((node.text or "" for node in cell if node.tag.endswith("}v")), "")
        if cell_type == "s" and value.isdigit():
            return shared[int(value)]
        return value

    def _read_ons_built_up_areas(self, data: bytes) -> dict[str, dict[str, str]]:
        """Read ONS table 1c/1d using only the standard library.

        The workbook's row shape is stable: F is the BUA name and G its size
        band. Reading only those two cells avoids pinning a spreadsheet library
        into this otherwise self-contained project.
        """
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
                    for item in root
                    if item.tag.endswith("}si")
                ]

            bands: dict[str, dict[str, str]] = {}
            for name in archive.namelist():
                if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                    continue
                root = ET.fromstring(archive.read(name))
                for row in root.iter():
                    if not row.tag.endswith("}row"):
                        continue
                    values = {
                        cell.attrib.get("r", "").rstrip("0123456789"):
                        self._xlsx_cell_value(cell, shared)
                        for cell in row
                        if cell.tag.endswith("}c")
                    }
                    band = values.get("G", "").strip().lower()
                    settlement = values.get("F", "").strip()
                    if settlement and band in LOCATION_BAND_TYPES:
                        bands[self._normalise_settlement_name(settlement)] = {
                            "name": settlement,
                            "type": LOCATION_BAND_TYPES[band],
                            "band": band,
                        }
            if not bands:
                raise ValueError("ONS workbook contains no built-up-area size bands")
            return bands

    def _load_ons_location_types(self) -> None:
        request = urllib.request.Request(
            ONS_BUILT_UP_AREAS_FILE_URL,
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            workbook = response.read()
        areas = self._read_ons_built_up_areas(workbook)
        for crs, location in self.locations_by_crs.items():
            if not crs or not location.name:
                continue
            for candidate in self._settlement_name_candidates(location.name):
                area = areas.get(candidate)
                if area:
                    self.location_types_by_crs[crs] = area["type"]
                    break
        self._apply_major_station_fallbacks()
        if not self.location_type_source:
            self.location_type_source = LOCATION_TYPE_SOURCE

    def _read_ons_coastal_areas(self, data: bytes) -> set[str]:
        """Read the 568 ONS coastal BUA names from table 1d."""
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
                    for item in root
                    if item.tag.endswith("}si")
                ]
            names: set[str] = set()
            for name in archive.namelist():
                if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                    continue
                root = ET.fromstring(archive.read(name))
                in_coastal_bua_table = False
                for row in root.iter():
                    if not row.tag.endswith("}row"):
                        continue
                    values = {
                        cell.attrib.get("r", "").rstrip("0123456789"):
                        self._xlsx_cell_value(cell, shared)
                        for cell in row
                        if cell.tag.endswith("}c")
                    }
                    if (
                        values.get("D", "").strip() == "BUA size classification"
                        and values.get("F", "").strip() == "BUA name"
                    ):
                        in_coastal_bua_table = True
                        continue
                    if not in_coastal_bua_table:
                        continue
                    if values.get("A", "").strip().lower() != "coastal":
                        continue
                    settlement = self._normalise_settlement_name(values.get("F", ""))
                    if settlement:
                        names.add(settlement)
            if not names:
                raise ValueError("ONS coastal workbook contains no coastal built-up areas")
            return names

    def _read_ons_coastal_facet(self) -> set[str]:
        """Return the coastal built-up-area names the ONS workbook lists."""
        request = urllib.request.Request(
            ONS_COASTAL_BUILT_UP_AREAS_FILE_URL,
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            workbook = response.read()
        return self._read_ons_coastal_areas(workbook)

    def _read_unesco_heritage_facet(self) -> set[str]:
        """Return station names for the UK properties the curated list names.

        The list is validated against UNESCO's own XML on every read: an id
        that is no longer a current UK property stops contributing, so a
        delisted site cannot keep tagging destinations.
        """
        request = urllib.request.Request(
            UNESCO_WORLD_HERITAGE_FILE_URL,
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        root = ET.fromstring(body)
        current: set[int] = set()
        for row in root:
            if row.tag.rsplit("}", 1)[-1] != "row":
                continue
            fields = {
                child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in row
            }
            if "united kingdom" not in fields.get("states", "").lower():
                continue
            try:
                current.add(int(fields.get("id_number", "")))
            except ValueError:
                continue
        names: set[str] = set()
        for site_id, stations in HERITAGE_STATIONS_BY_SITE.items():
            if site_id not in current:
                self.report.skip_file(
                    f"heritage: curated site {site_id} is not a current UK World Heritage "
                    "property; its stations were not applied"
                )
                continue
            for station in stations:
                names.add(self._normalise_settlement_name(station))
        if not names:
            raise ValueError("no curated World Heritage site is a current UK property")
        return names

    def _read_learning_provider_facet(self) -> set[str]:
        """Return the towns that have a university in the UKPRN provider list.

        The file is a tab-separated table whose TOWN column is the settlement
        the provider is in. Reading it by column name rather than position
        keeps a re-ordered file from silently moving the wrong column into the
        facet.
        """
        request = urllib.request.Request(
            LEARNING_PROVIDERS_FILE_URL,
            headers={"User-Agent": "TrainBudgetExplorer/1.0 (station classification build)"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode("utf-8-sig", errors="replace")
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("learning provider list is empty")
        header = [column.strip().upper() for column in lines[0].split("\t")]
        if "TOWN" not in header:
            raise ValueError("learning provider list has no TOWN column")
        town = header.index("TOWN")
        names: set[str] = set()
        for line in lines[1:]:
            columns = line.split("\t")
            if len(columns) <= town:
                continue
            if (settle := self._normalise_settlement_name(columns[town])):
                names.add(settle)
        return names

    def _write_location_cache(self, path: Path) -> None:
        cache = {
            # 3: the primary classes split into city/town/small_town/village,
            # so a cache written under 2 would call every village and small
            # town "other" forever.
            "schema": 3,
            "source": LOCATION_TYPE_SOURCE,
            "sources": {
                "primary": {
                    "name": "Office for National Statistics, Census 2021 built-up-area size bands",
                    "url": ONS_BUILT_UP_AREAS_DATASET_URL,
                },
            },
            "facetSources": {
                facet.key: {
                    "name": facet.source,
                    "url": facet.url,
                    "coverage": facet.coverage,
                }
                for facet in DESTINATION_FACET_SOURCES
            },
            "mapping": {
                type_name: [
                    band for band, kind in LOCATION_BAND_TYPES.items() if kind == type_name
                ]
                for type_name in ("city", "town", "small_town", "village")
            },
            "supportedFacets": sorted(SUPPORTED_DESTINATION_FACETS),
            "coverage": (
                "ONS Census 2021 BUA and coastal-classification matches, then reviewed "
                "major-station fallbacks for London and UK areas outside the workbooks"
            ),
            "fallbackSource": LOCATION_FALLBACK_SOURCE,
            "fallbackLondonStations": sorted(LONDON_STATION_CRS),
            "fallbackOtherStations": dict(sorted(MAJOR_UK_STATION_FALLBACKS.items())),
            "records": dict(sorted(self.location_types_by_crs.items())),
            "facets": {
                crs: sorted(facets)
                for crs, facets in sorted(self.location_facets_by_crs.items())
                if facets
            },
        }
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def destination_type(self, crs: str) -> str:
        """Return the station's primary ``city``, ``town`` or ``other`` class."""
        return self.location_types_by_crs.get(crs.strip().upper(), "other")

    def destination_types(self, crs: str) -> list[str]:
        """Return the primary class followed by any independent destination facets."""
        code = crs.strip().upper()
        return [self.destination_type(code), *sorted(self.location_facets_by_crs.get(code, set()))]

    def heritage_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the UNESCO properties that make this station a heritage match."""
        code = crs.strip().upper()
        location = self.locations_by_crs.get(code)
        if location is None or "heritage" not in self.location_facets_by_crs.get(code, set()):
            return []
        return [
            {
                "id": site_id,
                "name": name,
                "url": f"https://whc.unesco.org/en/list/{site_id}/",
            }
            for site_id, name, stations in HERITAGE_PROPERTIES
            if self._settlement_matches(
                location.name,
                {self._normalise_settlement_name(station) for station in stations},
            )
        ]

    def _load_lines(self, name: str, lines) -> None:
        extension = Path(name).suffix.lower().lstrip(".")
        # The optional station classification lookup lives beside the fares
        # files and is read after the feed stream. It is still a known input,
        # not an unreadable file that should pollute the damage audit.
        if extension == "json":
            self.report.files_read.append(name)
            return
        loader = {
            "ffl": self._load_flows,
            "loc": self._load_locations,
            "tty": self._load_ticket_types,
            "rlc": self._load_railcards,
            "rcm": self._load_minimum_fares,
            "rst": self._load_restrictions,
        }.get(extension)
        if loader is None:
            # A download this project has no reader for must be named, or the
            # audit reports "files 0" and reads as an empty download when the
            # real story is an unrecognised format. See adr/ADR-0023.
            suffix = Path(name).suffix.lower().lstrip(".")
            self.report.skip_file(
                f"{name}: no reader for the .{suffix or 'unknown'} format, not opened"
            )
            return
        self.report.files_read.append(name)
        if extension == "rst":
            self.restrictions.files_read.append(name)
        count(lines, loader, self.report, name)

    def _flow_index_nlcs(self, flow: Flow) -> tuple[str, ...]:
        if flow.direction == "R" and flow.destination_nlc != flow.origin_nlc:
            return (flow.origin_nlc, flow.destination_nlc)
        return (flow.origin_nlc,)

    def _index_flow(self, flow: Flow) -> None:
        for nlc in self._flow_index_nlcs(flow):
            self.flows_touching_nlc.setdefault(nlc, []).append(flow)

    def _unindex_flow(self, flow: Flow) -> None:
        for nlc in self._flow_index_nlcs(flow):
            flows = self.flows_touching_nlc.get(nlc)
            if flows is not None and flow in flows:
                flows.remove(flow)
                if not flows:
                    self.flows_touching_nlc.pop(nlc, None)

    def _load_flows(self, line: str) -> None:
        # Direct slices rather than _text per field: this reader sees every FFL
        # line in the feed, so its per-field call overhead is the parse's cost
        # centre (audit B2).
        f = FLOW_F_SLICES
        t = FLOW_T_SLICES
        record_type = line[f["record_type"]].strip().upper()
        if record_type == "F":
            _require_width(line, FLOW_F_WIDTH, "flow")
            marker = line[f["update_marker"]].strip().upper()
            flow_id = line[f["flow_id"]].strip()
            previous = self.flows.get(flow_id)
            if previous is not None:
                self._unindex_flow(previous)
            if marker == "D":
                self.flows.pop(flow_id, None)
                self.fares_by_flow.pop(flow_id, None)
                return
            flow = Flow(
                flow_id=flow_id,
                origin_nlc=line[f["origin_nlc"]].strip(),
                destination_nlc=line[f["destination_nlc"]].strip(),
                route_code=line[f["route_code"]].strip(),
                direction=line[f["direction"]].strip().upper(),
                start_date=_parse_dtd_date(line[f["start_date"]].strip()),
                end_date=_parse_dtd_date(line[f["end_date"]].strip()),
            )
            self.flows[flow_id] = flow
            self._index_flow(flow)
        elif record_type == "T":
            _require_width(line, FLOW_T_WIDTH, "fare")
            marker = line[t["update_marker"]].strip().upper()
            flow_id = line[t["flow_id"]].strip()
            ticket_code = line[t["ticket_code"]].strip()
            if self._focus_origin_nlcs is not None:
                flow = self.flows.get(flow_id)
                if flow is None or self._focus_origin_nlcs.isdisjoint(
                    self._flow_index_nlcs(flow)
                ):
                    return
            bucket = self.fares_by_flow.setdefault(flow_id, {})
            if marker == "D":
                bucket.pop(ticket_code, None)
                return
            fare_text = line[t["fare_pence"]].strip()
            if not fare_text.isdigit():
                # Raise rather than count here: the line counter decides once
                # whether a line was parsed or rejected, and counting it in both
                # places makes a rejected record look handled, with no example.
                raise ValueError(f"fare {fare_text!r} is not a number")
            bucket[ticket_code] = Fare(
                ticket_code=ticket_code,
                pence=int(fare_text),
                restriction_code=line[t["restriction_code"]].strip(),
            )

    def _load_locations(self, line: str) -> None:
        if _text(line, LOCATION_OFFSETS, "record_type").upper() != "L":
            return
        marker = _text(line, LOCATION_OFFSETS, "update_marker").upper()
        nlc = _text(line, LOCATION_OFFSETS, "nlc")
        existing = self.locations_by_nlc.get(nlc)
        if existing is not None and existing.crs:
            self.nlcs_by_crs.get(existing.crs, set()).discard(nlc)
            if self.locations_by_crs.get(existing.crs) is existing:
                self.locations_by_crs.pop(existing.crs, None)
        if marker == "D":
            self.locations_by_nlc.pop(nlc, None)
            return
        location = Location(
            nlc=nlc,
            crs=_text(line, LOCATION_OFFSETS, "crs").upper(),
            name=_text(line, LOCATION_OFFSETS, "description"),
            group_nlc=(
                _text(line, LOCATION_OFFSETS, "group_nlc") or nlc
            ),
        )
        self.locations_by_nlc[nlc] = location
        if location.crs:
            self.nlcs_by_crs.setdefault(location.crs, set()).add(nlc)
            self.locations_by_crs.setdefault(location.crs, location)

    def _load_ticket_types(self, line: str) -> None:
        marker = _text(line, TICKET_TYPE_OFFSETS, "update_marker").upper()
        code = _text(line, TICKET_TYPE_OFFSETS, "ticket_code")
        if marker == "D":
            self.ticket_types.pop(code, None)
            return
        if not code:
            return
        self.ticket_types[code] = TicketType(
            code=code,
            name=_text(line, TICKET_TYPE_OFFSETS, "description"),
            tkt_class=_text(line, TICKET_TYPE_OFFSETS, "tkt_class"),
            tkt_type=_text(line, TICKET_TYPE_OFFSETS, "tkt_type").upper(),
            restricted_by_train=_text(line, TICKET_TYPE_OFFSETS, "restricted_by_train") == "1",
        )

    def _load_railcards(self, line: str) -> None:
        code = _text(line, RAILCARD_OFFSETS, "railcard_code")
        if not code:
            return
        self.railcards[code] = Railcard(
            code=code,
            name=_text(line, RAILCARD_OFFSETS, "description"),
            min_adults=_as_int(_text(line, RAILCARD_OFFSETS, "min_adults")),
            max_adults=_as_int(_text(line, RAILCARD_OFFSETS, "max_adults")),
        )

    def _load_minimum_fares(self, line: str) -> None:
        railcard_code = _text(line, MINIMUM_FARE_OFFSETS, "railcard_code")
        ticket_code = _text(line, MINIMUM_FARE_OFFSETS, "ticket_code")
        pence = _as_int(_text(line, MINIMUM_FARE_OFFSETS, "minimum_fare_pence"))
        if not railcard_code or not ticket_code or pence <= 0:
            return
        self.minimum_fares[(railcard_code, ticket_code)] = pence

    def _load_restrictions(self, line: str) -> None:
        self.restrictions.load_line(line)

    # -- querying --------------------------------------------------------

    def _flow_valid_on(self, flow: Flow, query_day: date) -> bool:
        return not (
            (flow.start_date is not None and query_day < flow.start_date)
            or (flow.end_date is not None and query_day > flow.end_date)
        )

    def fare_coverage_audit(
        self, *, day: date | None = None, sample_limit: int = 10
    ) -> dict[str, object]:
        """Find fares that location or group relationships can hide.

        The query currently expands a station's direct location codes, but DTD
        locations also carry a group NLC. A fare flow from a shared group can
        therefore be valid for a station without appearing in that station's
        direct flow index. This report names those cases instead of silently
        calling the station unreachable.
        """
        query_day = day or date.today()
        limit = max(0, sample_limit)
        group_members: dict[str, set[str]] = {}
        for location in self.locations_by_nlc.values():
            if location.crs:
                group_members.setdefault(location.group_nlc, set()).add(location.nlc)
        multi_groups = {
            group: nlcs for group, nlcs in group_members.items() if len(nlcs) > 1
        }
        active_fare_flows = {
            flow.flow_id
            for flow in self.flows.values()
            if self.fares_by_flow.get(flow.flow_id)
            and self._flow_valid_on(flow, query_day)
        }
        direct_stations: set[str] = set()
        for crs, nlcs in self.nlcs_by_crs.items():
            if any(
                flow.flow_id in active_fare_flows
                for nlc in nlcs
                for flow in self.flows_touching_nlc.get(nlc, ())
            ):
                direct_stations.add(crs)

        group_by_nlc = {
            location.nlc: location.group_nlc
            for location in self.locations_by_nlc.values()
            if location.crs
        }
        group_origin_flows: dict[str, set[str]] = {
            group: set() for group in multi_groups
        }
        for flow in self.flows.values():
            group = group_by_nlc.get(flow.origin_nlc)
            if (
                group in group_origin_flows
                and flow.flow_id in active_fare_flows
            ):
                group_origin_flows[group].add(flow.flow_id)
        hidden_by_group: list[dict[str, object]] = []
        for group, flow_ids in group_origin_flows.items():
            if not flow_ids:
                continue
            for nlc in sorted(multi_groups[group]):
                location = self.locations_by_nlc.get(nlc)
                if location is None or location.crs in direct_stations:
                    continue
                hidden_by_group.append(
                    {
                        "crs": location.crs,
                        "name": location.name,
                        "groupNlc": group,
                        "flowCount": len(flow_ids),
                    }
                )

        location_aliases = [
            {
                "crs": crs,
                "name": self.locations_by_crs[crs].name,
                "nlcs": sorted(nlcs),
            }
            for crs, nlcs in sorted(self.nlcs_by_crs.items())
            if len(nlcs) > 1
        ]
        unmapped_destinations: list[dict[str, str]] = []
        missing_location = 0
        no_station_code = 0
        for flow in self.flows.values():
            if flow.flow_id not in active_fare_flows:
                continue
            destination = self.locations_by_nlc.get(flow.destination_nlc)
            if destination is None:
                missing_location += 1
                label = "missing location record"
            elif not destination.crs:
                no_station_code += 1
                label = destination.name or "location without CRS"
            else:
                continue
            if len(unmapped_destinations) < limit:
                unmapped_destinations.append(
                    {
                        "flowId": flow.flow_id,
                        "destinationNlc": flow.destination_nlc,
                        "label": label,
                    }
                )

        return {
            "day": query_day.isoformat(),
            "groupCodes": len(multi_groups),
            "groupOriginFlows": sum(len(ids) for ids in group_origin_flows.values()),
            "stationsPotentiallyHiddenByGroup": len(hidden_by_group),
            "sampleStationsPotentiallyHiddenByGroup": hidden_by_group[:limit],
            "stationsWithMultipleLocationCodes": len(location_aliases),
            "sampleStationsWithMultipleLocationCodes": location_aliases[:limit],
            "fareFlowsWithMissingLocation": missing_location,
            "fareFlowsWithNoStationCode": no_station_code,
            "sampleFareFlowsWithUnmappedDestinations": unmapped_destinations,
        }

    def stats(self) -> dict[str, int]:
        if self.feed_stats is not None:
            return dict(self.feed_stats)
        return {
            "stations": len(self.locations_by_crs),
            "flows": len(self.flows),
            "fares": sum(len(bucket) for bucket in self.fares_by_flow.values()),
            "ticket_types": len(self.ticket_types),
            "railcards": len(self.railcards),
            # A feed carries locations with no station code, and fares whose flow
            # is not in the file. Neither is an error, and both change any count
            # that ignores them, so both are reported.
            "locations_without_a_station_code": sum(
                1 for location in self.locations_by_nlc.values() if not location.crs
            ),
            "extra_location_codes_for_a_station": sum(
                max(0, len(nlcs) - 1) for nlcs in self.nlcs_by_crs.values()
            ),
            "fares_with_no_flow_record": sum(
                1
                for flow_id, bucket in self.fares_by_flow.items()
                if flow_id not in self.flows
                for _ in bucket
            ),
            "restriction_files": len(self.restrictions.files_read),
            "restriction_records": self.restrictions.parsed_records,
            "restriction_codes": len(self.restrictions.code_record_counts),
            "restriction_railcards": len(self.restrictions.railcard_record_counts),
        }

    def railcard_code(self, name: str) -> str | None:
        needle = name.strip().lower()
        if not needle:
            return None
        for code, railcard in sorted(self.railcards.items()):
            if railcard.name.lower() == needle:
                return code
        for code, railcard in sorted(self.railcards.items()):
            if needle in railcard.name.lower():
                return code
        return None

    def railcard_price(self, railcard_code: str, ticket_code: str, standard_pence: int) -> int:
        # National Rail's published third-off result is rounded down to the
        # nearest 5p for each ticket, not up. Rounding up costs 5p per traveller
        # whenever the exact discount falls between two 5p amounts.
        discounted = _round_down_to(standard_pence * RAILCARD_DISCOUNT, ROUNDING_STEP_PENCE)
        minimum = self.minimum_fares.get((railcard_code, ticket_code))
        if minimum is not None:
            discounted = max(discounted, minimum)
        return discounted

    def railcard_rules(
        self,
        railcard_code: str,
        *,
        ticket_code: str,
        route_code: str,
        origin_crs: str,
        destination_crs: str,
        origin_nlc: str,
        destination_nlc: str,
    ) -> list[RailcardRestrictionRow]:
        """Return every current DTD ``RR`` rule that applies to one fare.

        Blank RR fields are wildcards. An RR restriction code changes or
        overrides the fare's restriction; it is not itself a total ban. The
        caller can therefore preserve conditions such as Two Together's R9
        without refusing the discount.
        """
        stations = {value.strip().upper() for value in (origin_crs, destination_crs, origin_nlc, destination_nlc) if value}
        return [
            row
            for row in self.restrictions.active_railcard_rows(railcard_code)
            if (not row.ticket_code or row.ticket_code == ticket_code)
            and (not row.route_code or row.route_code == route_code)
            and (not row.location or row.location.strip().upper() in stations)
        ]

    def railcard_restriction(
        self,
        railcard_code: str,
        *,
        ticket_code: str,
        route_code: str,
        origin_crs: str,
        destination_crs: str,
        origin_nlc: str,
        destination_nlc: str,
    ) -> RailcardRestrictionRow | None:
        """Return the first matching current ``RR`` total ban, if there is one."""
        return next(
            (
                row
                for row in self.railcard_rules(
                    railcard_code,
                    ticket_code=ticket_code,
                    route_code=route_code,
                    origin_crs=origin_crs,
                    destination_crs=destination_crs,
                    origin_nlc=origin_nlc,
                    destination_nlc=destination_nlc,
                )
                if row.total_ban
            ),
            None,
        )

    def railcard_price_for(
        self,
        railcard_code: str,
        *,
        ticket_code: str,
        route_code: str,
        origin_crs: str,
        destination_crs: str,
        origin_nlc: str,
        destination_nlc: str,
        standard_pence: int,
    ) -> int | None:
        restriction = self.railcard_restriction(
            railcard_code,
            ticket_code=ticket_code,
            route_code=route_code,
            origin_crs=origin_crs,
            destination_crs=destination_crs,
            origin_nlc=origin_nlc,
            destination_nlc=destination_nlc,
        )
        if restriction is not None:
            return None
        return self.railcard_price(railcard_code, ticket_code, standard_pence)

    def destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        day: date | None = None,
    ) -> list[Reachable]:
        """Cheapest standard-class return to each destination inside the budget.

        With a railcard, the comparison uses whichever of the railcard price and
        the standard price is cheaper, since a cardholder can always decline the
        discount. party_budget tests the total for the party instead of the
        per-adult price.

        Pass a dict as tally to record why each flow or fare did not become a
        destination. A destination the feed prices but cannot name is dropped,
        and a count that ignores those is wrong without saying so.

        This is the broad query, and it still accepts every class-2 return fare
        the feed offers, restricted or not. Use ``publishable_destinations_within``
        before putting a price on a public page.
        """
        return self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=None,
            day=day,
        )

    def page_destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        day: date | None = None,
    ) -> list[Reachable]:
        """Rows suitable for the reader-facing page, including restrictions.

        The feed contains ITX placeholder fares such as ``EIS`` at the £0.05
        minimum with restriction ``GA``. They are not usable public fares, so
        they must not win the broad query's cheapest-fare comparison. Other
        restricted standard returns remain visible and carry their restriction
        code to the page.
        """
        rows = self.destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            day=day,
        )
        return [
            row for row in rows
            if row.ticket_code not in PLACEHOLDER_TICKET_CODES
            and "ITX" not in row.ticket_name.upper()
        ]

    def page_single_destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        day: date | None = None,
    ) -> list[Reachable]:
        """Displayable standard-class singles, excluding catalogue placeholders.

        Advance singles are valid fares, but they are attached to a particular
        train rather than being an unrestricted walk-up price. They remain in
        the result; callers must label them as train-specific instead of
        silently treating them like an anytime fare.
        """
        rows = self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=lambda fare, ticket: (
                None
                if ticket.is_standard_single
                and fare.ticket_code not in PLACEHOLDER_TICKET_CODES
                and "ITX" not in ticket.name.upper()
                and not any(
                    marker in ticket.name.upper()
                    for marker in ("NOT FOR TRAVEL", "TEST", "DUMMY", "FOR TEST", "COMP")
                )
                else "ticket_is_not_a_displayable_standard_single"
            ),
            day=day,
        )
        return rows

    def publishable_destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        require_restrictions: bool = True,
        day: date | None = None,
    ) -> list[Reachable]:
        """The reviewed selector for public prices: Anytime Day Return only.

        With ``require_restrictions`` true (the default), the query refuses to
        run at all unless the ``.RST`` restriction file loaded cleanly, keeps
        only ticket codes in ``REVIEWED_ANYTIME_DAY_RETURN_TICKETS`` whose real
        ticket type is a standard-class, train-unrestricted exact ANYTIME DAY R,
        and drops any fare whose restriction code is not blank. Railcard prices
        are evaluated against the current ``RR`` rows in the same feed: blank
        fields are wildcards, a matching total ban removes the discount, and a
        matching restriction code supplies the railcard fare's travel condition.

        ``require_restrictions=False`` is for analysis and synthetic feeds only.
        It allows the conventional no-restriction code ``00`` and computes
        railcard discounts as the broad query does. Do not put its output on a
        public page.
        """
        if require_restrictions:
            problem = self.restrictions.gate_problem()
            if problem is not None:
                raise ValueError(problem)
        return self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=self._publishable_rejection(strict=require_restrictions),
            day=day,
        )

    def priced_destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int = 1,
        railcard: str | None = None,
        party_budget: bool = False,
        tally: dict[str, int] | None = None,
        day: date | None = None,
    ) -> list[Reachable]:
        """Every destination the origin's page can price, in any ticket mode.

        The page publishes restricted standard returns, displayable singles and
        reviewed anytime returns, so a station priced in any one of them has a
        page a reader can use (ADR-0019 decision 3). The chooser's priceable
        test and the unsourced-destination report share this one selector so
        they cannot drift: audit A1 caught the chooser measuring the anytime
        mode alone while King's Cross published 171 returns from the other two.
        A destination priced in several modes appears once, so a coverage check
        over the rows names it exactly once.

        A ``tally`` counts each flow's rejection once: all three modes drop an
        unnameable destination in the shared loop before mode-specific
        filtering, so the tally rides on one mode only, where passing it to
        all three would triple-count (audit A3).
        """
        rows: dict[str, Reachable] = {}
        queries = (
            (self.page_destinations_within, tally),
            (self.page_single_destinations_within, None),
            (self.publishable_destinations_within, None),
        )
        for query, mode_tally in queries:
            for row in query(
                origin_crs,
                budget_pence,
                adults=adults,
                railcard=railcard,
                party_budget=party_budget,
                tally=mode_tally,
                day=day,
            ):
                rows.setdefault(row.crs, row)
        return list(rows.values())

    def _publishable_rejection(
        self, *, strict: bool
    ) -> Callable[[Fare, TicketType], str | None]:
        """Build the reviewed selector used by ``publishable_destinations_within``."""

        def reject(fare: Fare, ticket: TicketType) -> str | None:
            expected_name = REVIEWED_ANYTIME_DAY_RETURN_TICKETS.get(ticket.code)
            if (
                expected_name is None
                or ticket.name.strip().upper() != expected_name
                or not ticket.is_standard_return
                or ticket.restricted_by_train
            ):
                return "ticket_is_not_a_reviewed_anytime_day_return"
            restriction = fare.restriction_code.strip()
            if not restriction:
                return None
            if not strict and restriction == "00":
                return None
            return "fare_restriction_code_is_not_reviewed"

        return reject

    def _destinations_within(
        self,
        origin_crs: str,
        budget_pence: int,
        *,
        adults: int,
        railcard: str | None,
        party_budget: bool,
        tally: dict[str, int] | None,
        selector: Callable[[Fare, TicketType], str | None] | None,
        day: date | None,
    ) -> list[Reachable]:
        """Shared query loop. ``selector`` adds the publishable-fare filter."""
        query_day = day or date.today()
        origin = self.locations_by_crs.get(origin_crs.strip().upper())
        if origin is None:
            raise KeyError(f"origin station {origin_crs!r} is not in the feed")
        origin_nlcs = self.nlcs_by_crs.get(origin.crs, {origin.nlc})
        railcard_code = self.railcard_code(railcard) if railcard else None
        if railcard and railcard_code is None:
            raise KeyError(f"railcard {railcard!r} is not in the feed")

        best_by_crs: dict[str, Reachable] = {}
        # Only flows queryable from this origin: one grouped list per origin NLC
        # replaces a scan of every flow in the database per call. The index also
        # contains reversible flows under their recorded destination, so a query
        # for the opposite direction reaches the same fare without duplicating it.
        for origin_nlc in origin_nlcs:
            for flow in self.flows_touching_nlc.get(origin_nlc, ()):
                if not self._flow_valid_on(flow, query_day):
                    _tally(
                        tally,
                        "flow_not_yet_valid"
                        if flow.start_date is not None and query_day < flow.start_date
                        else "flow_expired",
                    )
                    continue
                # A reversible flow is indexed under both endpoints, but its
                # stored destination still points at the recorded origin. Use
                # the opposite endpoint when this query entered via that side.
                destination_nlc = (
                    flow.origin_nlc
                    if flow.direction == "R" and flow.destination_nlc == origin_nlc
                    else flow.destination_nlc
                )
                destination = self.locations_by_nlc.get(destination_nlc)
                if destination is None:
                    _tally(tally, "destination_has_no_location_record")
                    continue
                if not destination.crs:
                    _tally(tally, "destination_has_no_station_code")
                    continue
                if destination.crs == origin.crs:
                    _tally(tally, "fare_to_the_origin_itself")
                    continue
                bucket = self.fares_by_flow.get(flow.flow_id)
                if not bucket:
                    _tally(tally, "flow_with_no_fare")
                    continue
                for fare in bucket.values():
                    ticket = self.ticket_types.get(fare.ticket_code)
                    if ticket is None:
                        _tally(tally, "fare_with_no_ticket_type")
                        continue
                    if selector is not None:
                        rejection = selector(fare, ticket)
                        if rejection is not None:
                            _tally(tally, rejection)
                            continue
                    elif not ticket.is_standard_return:
                        _tally(tally, "ticket_is_not_a_standard_return")
                        continue
                    railcard_pence = (
                        self.railcard_price_for(
                            railcard_code,
                            ticket_code=fare.ticket_code,
                            route_code=flow.route_code,
                            origin_crs=origin.crs,
                            destination_crs=destination.crs,
                            origin_nlc=origin_nlc,
                            destination_nlc=destination_nlc,
                            standard_pence=fare.pence,
                        )
                        if railcard_code
                        else None
                    )
                    best_pence = min(fare.pence, railcard_pence) if railcard_pence else fare.pence
                    party_pence = best_pence * adults
                    tested = party_pence if party_budget else best_pence
                    if tested > budget_pence:
                        _tally(tally, "fare_above_the_budget")
                        continue
                    candidate = Reachable(
                        crs=destination.crs,
                        station=destination.name,
                        ticket_code=ticket.code,
                        ticket_name=ticket.name,
                        standard_pence=fare.pence,
                        best_pence=best_pence,
                        railcard_pence=railcard_pence,
                        party_pence=party_pence,
                        off_peak=ticket.restricted_by_train,
                        restriction_code=fare.restriction_code.strip(),
                        route_code=flow.route_code,
                        origin_nlc=origin_nlc,
                        destination_nlc=destination_nlc,
                    )
                    current = best_by_crs.get(destination.crs)
                    if current is not None and candidate.best_pence >= current.best_pence:
                        _tally(tally, "cheaper_index_already_held")
                        continue
                    best_by_crs[destination.crs] = candidate
        return sorted(best_by_crs.values(), key=lambda reachable: (reachable.best_pence, reachable.crs))


def _as_int(value: str) -> int:
    return int(value) if value.isdigit() else 0
