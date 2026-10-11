"""Read the ATOC/RDG fares feed and answer "what can I reach for under £X?".

The feed is fixed-width text. Each spec below is (field_name, width) in file
order, so a field's position is the running sum of the widths before it. That
mirrors how the published record layouts are defined.

Fares are per person. A party buys one ticket per adult unless the ticket type
says otherwise, so a party price is adults x per-adult.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
import math
import os
import pickle
from pathlib import Path
import re
# The readers in atoc_fares_loader reach the ONS, UNESCO and UKPRN sources
# through this module, and the tests stub them by patching
# ``atoc_fares.urllib.request``: it is the same module object there, so the
# binding stays where a reader of this file expects it.
import urllib.request  # noqa: F401
import xml.etree.ElementTree as ET

from atoc_restrictions import RailcardRestrictionRow, RestrictionIndex
from parse_report import ParseReport, read_feed_files

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
# The London list is written in the feed's own CRS. The London Underground,
# DLR and Overground codes carry a leading Z the National Rail ones do not, and
# seven entries had been written without it, so they named no station at all
# (Blackfriars is ZBF, not BKF). A dead code costs nothing at runtime, which is
# exactly why the reader below names it.
#
# Every entry must be a station the ONS workbook does not name, because that is
# the whole point of a fallback: it is applied only where the workbook and the
# name lookup miss. Seventeen entries broke that rule -- Ascot, Battle,
# Knighton, Windermere, Wickford, Welshpool, Brockenhurst, Bramhall, Bangor,
# Truro, York, Solihull, Swansea, Leicester, Bournemouth, Berkhamsted and
# Lostock Gralam are all in the workbook -- and they were removed rather than
# kept, because an entry that never applies is still a claim about a station
# someone else already classified, and the day the name match misses it would
# land: Knighton would become a city, Windermere a city, York a town. The
# workbook names them correctly, so nothing is lost.
LONDON_STATION_CRS = frozenset({
    "BFN", "BWD", "CHC", "CLJ", "CTK", "DLK", "ECR", "EUS", "FST",
    "GTN", "HAY", "HMY", "KGX", "LBG", "LES", "LST", "MYB", "PAD",
    "STP", "SUR", "VIC", "WAT", "WOL", "WWC",
    "ZBF", "ZCD", "ZGR", "ZLP", "ZPD", "ZPI", "ZRY",
})
MAJOR_UK_STATION_FALLBACKS = {
    # Scotland. A reviewed list, because the workbook stops at the border and
    # no Scottish equivalent of its built-up-area bands is published, so these
    # are judgements rather than sources (ADR-0026). Where the old entry named
    # a city and the feed's station for that code is a village or a hamlet, the
    # class is impossible and was corrected: Banavie, Balloch, Ladybank and
    # Cardenden are not cities, and Cardenden is a town. Tulloch is in the
    # London list for no defensible reason and is now a village. Largs sits
    # within ten people of the town/small-town boundary and was left as the
    # Scottish "town" it is.
    "ABD": "city", "BHC": "village", "BNV": "village", "CDD": "town",
    "DEE": "city", "EDB": "city", "GLC": "city", "HGY": "village",
    "INV": "city", "LDY": "village", "LAR": "town", "QGS": "city",
    "SGL": "city",
    # Wales outside the England-and-Wales BUA workbook's usual settlement names.
    # Penrhwceiber was filed as a city; the code is right and the class was not,
    # so it is the village the feed says it is. Swansea was here too, and is
    # gone: the workbook covers Wales and names it.
    "PER": "village",
    # Northern Ireland. Newry is the large town this group was missing: the code
    # was written as NIR, which names no station, and the feed's own code for
    # Newry is NWY. Three more Welsh and island codes (NPT, BFL, BQU) named no
    # station and no settlement could be recovered for them, so they were
    # dropped rather than left to classify a future feed's station from a guess.
    "LBN": "town", "NWY": "town", "PTN": "town",
    # English villages outside the workbook. These were sitting in the
    # Northern Ireland and Scotland groups above, which is how Birchington
    # acquired a "town" class it is not: a group is a claim about where an
    # entry comes from, and a wrong one hides a wrong class. Wrenbury and
    # Britwhir are named in the workbook as Wrenbury-cum-Frith and Britwhir,
    # which the name lookup cannot see; the reviewed entry is what applies.
    "BCH": "village", "BHD": "village", "WRE": "village",
    # England, outside the workbook. Cooksbridge and Chathill were in the
    # London list and are hamlets in East Sussex and Northumberland, so they
    # are villages here; the London Underground, DLR and Overground codes stay
    # in the London list, where a station inside Greater London legitimately
    # has no ONS row to match.
    "CBR": "village", "CHT": "village", "TUL": "village",
    # English cities. A reviewed list, used only where the ONS built-up-area
    # workbook has no row for the station, so a major city is not filed as
    # "other". Bromborough, Bramhall, Brockenhurst, Solihull, Leicester,
    # Bournemouth, Swansea, Truro, York, Berkhamsted, Lostock Gralam, Newport
    # and Bangor were removed because the workbook *does* name them all.
    "NCL": "city", "NCZ": "city", "NCX": "city", "BHM": "city",
    "BRI": "city", "EXC": "city", "EXT": "city", "SOU": "city", "STP": "city",
    "HUL": "city", "MAN": "city",
    # A station inside a conurbation takes the class of the settlement it
    # belongs to, which is the same rule the London list uses. Barming is
    # three miles from Maidstone, a town, and Wakefield Westgate is in
    # Wakefield, a city: so Barming is the town and Wakefield the city. Both
    # were the other way round, and Barming was filed as a city it is nowhere
    # near. The workbook names Wakefield and puts it in a city band, so the
    # entry agrees with the source rather than contradicting it.
    "BMG": "town", "WKF": "city",
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
    # Grantham, Sheffield, Rotherham, Hyde and the Yorkshire settlements.
    # Rotherham Central was filed as a city because it sat in this group
    # beside Sheffield; Rotherham is a town of about 62,000 and the workbook
    # puts it in a medium band, so the entry now says what the source says.
    "DOR": "town", "HOP": "village", "DAN": "town", "MHS": "town",
    "RMC": "town", "CLN": "village", "EDL": "village", "KIV": "village",
    "SWN": "town", "BTD": "village", "BYK": "village", "AWK": "village",
    "NMC": "small_town", "MRP": "village", "SRN": "village", "BDY": "village",
    "BNT": "village", "HYC": "town", "HYT": "town", "CGW": "village",
    "CYB": "village", "HPE": "village",
    # Fernhill was filed as a city in the Cardiff group, and it is a village in
    # the Scottish Borders. Burscough Junction's settlement is in the workbook
    # as a small built-up area, so the entry says so rather than understating
    # it as a village.
    "FER": "village", "BCJ": "small_town",
    # Attenborough is a village; the same page also earns the nature facet.
    "ATB": "village",
    # Settlements the workbook misses because the feed's station name carries a
    # qualifier it omits ("Berwick on Tweed", "Newark Northgate", "Newton
    # le Will" for Newton-le-Willows), or a name it does not hold at all. Each
    # is the settlement the station is named for, and the class is the one the
    # workbook would give it: Newton-le-Willows is a town, not a village.
    "ALM": "village", "ARB": "town", "BDQ": "city", "BEE": "town",
    "BUH": "village", "BWK": "town", "CBG": "city", "CLM": "village",
    "DEE": "city", "DUN": "town", "ELO": "village", "FKG": "small_town",
    "GLE": "village", "HBB": "village", "HRS": "town", "HVN": "village",
    "HYM": "village", "INK": "village", "KDY": "town", "KIN": "village",
    "KTL": "village", "LAG": "village", "LEU": "village", "LGM": "small_town",
    "LJL": "city", "LPY": "city", "MTS": "town", "NLW": "town",
    "NNG": "town", "PIT": "village", "PTH": "city", "RAU": "village",
    "RDF": "village", "SHY": "town", "SPO": "village", "STG": "city",
    "STN": "town", "TPC": "village", "WFL": "village", "WWL": "village",
    # Nottingham Express Transit and East Midlands Parkway tram stops, and
    # park-and-ride platforms named after the village they serve
    "EMD": "village", "PEA": "village", "PPR": "town",
    # Further settlements the workbook does not name, checked against the feed
    "BLW": "town", "DVP": "town", "GBL": "town",
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
    "HHL": "city", "WNG": "city", "CDF": "city",
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
    # Small towns: Maesteg (as MST), Ebbw Vale, Risca,
    # Llandrindod, Galashiels, Linlithgow, Abergele, Larbert, Shotts,
    # Armadale, Blantyre, Dinas Powys, Cobham, Claygate, Earlstown,
    # Milngavie, Bearsden, Westerton, Stepps and Hengoed. Pontypool was
    # here too and is a town: the workbook puts it in a medium band, and the
    # feed's own name for the station is Pontypool and New Inn.
    "MEW": "small_town", "EBB": "small_town", "EBV": "small_town",
    "RCA": "small_town", "LLO": "small_town", "PPL": "town",
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
    "MIA": "city", "MNA": "city", "PRA": "town", "RHA": "city", "SIA": "town", "SOA": "city",
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
    #: Reviewed attraction proofs, linked to the feed by the hybrid prune
    #: (ADR-0062/0063) rather than by a static CRS set: the nearest station is
    #: a fact about coordinates the build has on disk, not something to write
    #: into this table and keep true by hand.
    reviewed_attractions: tuple[ReviewedAttraction, ...] = ()
    reviewed_name_markers: tuple[str, ...] = ()
    # Settlements whose own name merely contains a marker -- Bushey, BUSBY,
    # CAMBUSLANG and Shepherd's Bush are places, not interchanges. The feed
    # truncates names, so a substring marker is the only way to catch
    # "BPOOL NTHBUSTRAM", and these are the settlements it catches wrongly.
    excluded_station_codes: frozenset[str] = frozenset()

    @property
    def is_reviewed(self) -> bool:
        # A reviewed facet has no published dataset reader. Dataset facets may
        # still carry reviewed_station_codes as a supplement (ONS misses
        # Blackpool / Brighton / Southend / Weston), without becoming reviewed.
        return self.reader == "reviewed_station_codes"


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
# Named-site proof for the nature facet. Each tuple is (CRS, official name,
# visit URL). The CRS set is still the facet source of truth; deriving it from
# this table keeps one reviewed list instead of two that can drift. Prefer the
# trust or centre "plan your visit" page over Wikipedia.
NATURE_SITE_PROOFS: tuple[tuple[str, str, str], ...] = (
    # Attenborough Nature Reserve, five minutes from the station on the trust's
    # own "plan your visit" page (Nottinghamshire Wildlife Trust)
    (
        "ATB",
        "Attenborough Nature Reserve",
        "https://www.nottinghamshirewildlife.org/attenborough-plan-your-visit",
    ),
    # Martin Mere Wetland Centre, named as the recommended station on WWT's
    # own directions page (Wildfowl and Wetlands Trust)
    (
        "BCB",
        "Martin Mere Wetland Centre",
        "https://www.wwt.org.uk/wetland-centres/martin-mere/plan-your-visit/directions",
    ),
    (
        "BCJ",
        "Martin Mere Wetland Centre",
        "https://www.wwt.org.uk/wetland-centres/martin-mere/plan-your-visit/directions",
    ),
    # Thorndon Country Park, "close to Brentwood station" per the trust
    # (Essex Wildlife Trust)
    (
        "BRE",
        "Thorndon Country Park",
        "https://www.essexwt.org.uk/nature-reserves/thorndon",
    ),
    # Weeting Heath, about 3.5 km from Brandon on the only documented walk
    # (Norfolk Wildlife Trust)
    (
        "BND",
        "Weeting Heath",
        "https://www.norfolkwildlifetrust.org.uk/WeetingHeath",
    ),
    # Sevenoaks Wildlife Reserve, just under 2 km from the station out of town
    # (Kent Wildlife Trust)
    (
        "SEV",
        "Sevenoaks Wildlife Reserve",
        "https://www.kentwildlifetrust.org.uk/nature-reserves/sevenoaks-wildlife-reserve-and-jeffery-harrison-visitor-centre",
    ),
    # Bodenham Arboretum, about fifteen minutes from Hartlebury
    (
        "HBY",
        "Bodenham Arboretum",
        "https://www.bodenhamarboretum.co.uk/visiting",
    ),
    # WWT Slimbridge: "the nearest train station is Cam & Dursley"
    (
        "CDU",
        "Slimbridge Wetland Centre",
        "https://www.wwt.org.uk/wetland-centres/slimbridge/plan-your-visit/directions",
    ),
    # The three London Wildlife Trust sites that name their station themselves
    (
        "HAY",
        "Yeading Brook Meadows",
        "https://www.wildlondon.org.uk/nature-reserves/yeading-brook-meadows",
    ),
    (
        "ZHX",
        "Huckerby's Meadows",
        "https://www.wildlondon.org.uk/nature-reserves/huckerbys-meadows",
    ),
    (
        "ZHD",
        "Gutteridge Wood and Meadows",
        "https://www.wildlondon.org.uk/nature-reserves/gutteridge-wood-and-meadows",
    ),
    # Bookham Commons is National Trust land (not Surrey Wildlife Trust); the
    # official visit page is the proof we can link.
    (
        "BKA",
        "Bookham Commons",
        "https://www.nationaltrust.org.uk/visit/surrey/bookham-commons",
    ),
    # Titchfield Haven NNR is run by Hampshire County Council; HIWWT does not
    # publish a visit page for the reserve itself.
    (
        "HLS",
        "Titchfield Haven National Nature Reserve",
        "https://www.visit-hampshire.co.uk/things-to-do/titchfield-haven-national-nature-reserve-p1521681",
    ),
)
NATURE_SITE_STATION_CRS = frozenset(crs for crs, _name, _url in NATURE_SITE_PROOFS)
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
    (430, "Hadrian's Wall", ("Carlisle", "Chester-le-Street", "Corbridge", "Newcastle")),
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

# Attraction geometry for the hybrid closest-station prune (ADR-0063). Point
# sites carry one coordinate. Corridor and multi-gateway sites carry component
# points so a valley or wall is not collapsed by a single centroid. Coordinates
# are reviewed WGS84 decimals near the property or gateway, not a GIS import.
HERITAGE_SITE_POINTS: dict[int, tuple[tuple[float, float], ...]] = {
    370: ((54.7747, -1.5761),),  # Durham Castle and Cathedral
    374: (  # Edward I castles in Gwynedd
        (53.1393, -4.2769),  # Caernarfon
        (53.2801, -3.8257),  # Conwy
        (52.8603, -4.1092),  # Harlech
    ),
    422: (  # English Lake District gateways
        (54.1916, -3.0979),  # Ulverston
        (54.3796, -2.9034),  # Windermere
    ),
    426: ((51.4995, -0.1248),),  # Westminster
    429: ((55.6634, -3.7817),),  # New Lanark
    430: (  # Hadrian's Wall gateways
        (54.8951, -2.9338),  # Carlisle
        (54.8546, -1.5780),  # Chester-le-Street
        (54.9663, -2.0186),  # Corbridge
        (54.9682, -1.6173),  # Newcastle
    ),
    488: ((51.5081, -0.0759),),  # Tower of London
    496: (  # Canterbury / Dover
        (51.2790, 1.0830),  # Canterbury
        (51.1257, 1.3053),  # Dover Priory
    ),
    514: ((58.9636, -3.2950),),  # Heart of Neolithic Orkney / Stromness
    728: ((55.9533, -3.1883),),  # Old and New Towns of Edinburgh
    1028: ((53.8389, -1.7916),),  # Saltaire
    1029: (  # Dorset and East Devon Coast
        (50.6216, -3.4150),  # Exmouth
        (50.7194, -1.9833),  # Poole
        (50.6090, -1.9590),  # Swanage
        (50.6160, -2.4549),  # Weymouth
    ),
    1030: (  # Derwent Valley Mills
        (53.0246, -1.4826),  # Belper
        (53.1129, -1.5488),  # Cromford
        (53.1382, -1.5590),  # Matlock
        (53.1220, -1.5577),  # Matlock Bath
    ),
    1084: ((51.4780, -0.2950),),  # Kew Gardens
    1215: (  # Cornwall and West Devon Mining Landscape
        (50.2104, -5.2975),  # Camborne
        (50.2332, -5.2260),  # Redruth
        (50.2638, -5.0649),  # Truro
    ),
    1303: ((52.9700, -3.0880),),  # Pontcysyllte Aqueduct
    1594: ((53.2365, -2.3070),),  # Jodrell Bank
    1613: ((51.3810, -2.3590),),  # City of Bath
    1633: (  # Slate Landscape of Northwest Wales
        (52.7223, -4.0565),  # Barmouth
        (53.1393, -4.2769),  # Caernarfon
        (52.9309, -4.1345),  # Porthmadog
    ),
}

HERITAGE_PRUNE_MAX_KM = 15.0
HERITAGE_PRUNE_TWIN_M = 2000.0

# Default on-disk Knowledgebase stations file used for CRS -> lat/lon. Builds
# that already pass --knowledgebase still resolve stations.xml beside that
# folder; tests without the file fail open and keep the curated candidates.
DEFAULT_STATIONS_XML = Path("feeds") / "knowledgebase" / "stations.xml"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS84 points."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    chord = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(chord))


def select_nearest_stations(
    candidates: Sequence[tuple[str, float, float]],
    points: Sequence[tuple[float, float]],
    *,
    max_km: float = HERITAGE_PRUNE_MAX_KM,
    twin_m: float = HERITAGE_PRUNE_TWIN_M,
) -> list[str]:
    """Keep the nearest CRS per attraction point, plus a soft twin.

    For each component point, drop candidates beyond ``max_km``, keep the
    nearest, and keep the second when its distance to the point is within
    ``twin_m`` metres of the nearest's distance. Corridor sites pass several
    points and the survivors are unioned, so a valley set is not forced through
    a hard top-2.
    """
    kept: dict[str, float] = {}
    twin_km = twin_m / 1000.0
    for point_lat, point_lon in points:
        scored = sorted(
            (
                haversine_km(lat, lon, point_lat, point_lon),
                crs,
            )
            for crs, lat, lon in candidates
        )
        within = [(distance, crs) for distance, crs in scored if distance <= max_km]
        if not within:
            continue
        best_distance, best_crs = within[0]
        kept[best_crs] = min(kept.get(best_crs, best_distance), best_distance)
        if len(within) > 1:
            second_distance, second_crs = within[1]
            if second_distance - best_distance <= twin_km:
                kept[second_crs] = min(
                    kept.get(second_crs, second_distance), second_distance
                )
    return sorted(kept, key=lambda crs: (kept[crs], crs))


def load_station_coordinates(path: Path | str | None = None) -> dict[str, tuple[float, float]]:
    """Return CRS -> (lat, lon) from a Knowledgebase stations.xml file."""
    source = Path(path) if path is not None else DEFAULT_STATIONS_XML
    if not source.is_file():
        return {}
    coordinates: dict[str, tuple[float, float]] = {}
    for _event, element in ET.iterparse(source, events=("end",)):
        if element.tag.rsplit("}", 1)[-1] != "Station":
            continue
        fields = {
            child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
            for child in element
        }
        crs = fields.get("CrsCode", "").upper()
        try:
            lat = float(fields.get("Latitude", ""))
            lon = float(fields.get("Longitude", ""))
        except ValueError:
            element.clear()
            continue
        if crs:
            coordinates[crs] = (lat, lon)
        element.clear()
    return coordinates


# Classic seaside day-outs the ONS coastal BUA workbook does not attach to a
# station name match (Brighton's university tag wins the settlement string;
# Blackpool / Southend / Weston truncate or miss in the same pass). Reviewed
# CRS codes supplement the ONS facet; they do not replace it. See ADR-0064.
SEASIDE_SUPPLEMENT_CRS = frozenset({
    "BPN",  # Blackpool North
    "BPB",  # Blackpool Pleasure Beach
    "BPS",  # Blackpool South
    "BTN",  # Brighton
    "SOC",  # Southend Central
    "SOE",  # Southend East
    "SOV",  # Southend Victoria
    "WSM",  # Weston-super-Mare
})

# Named coastal day-outs for stations that also carry the seaside facet. Every
# seaside-tagged CRS must appear here (chip implies named subline). Floor of
# beaches, harbours, castles, and estuary walks a reader would catch a train
# for - not a fake beach on an inland quay.
COASTAL_SITE_PROOFS: tuple[tuple[str, str, str], ...] = (
    (
        "ARN",
        "Arnside Knott and Kent estuary",
        "https://www.arnsideandsilverdaleaonb.org.uk/",
    ),
    (
        "AVN",
        "Avonmouth and Severn estuary",
        "https://www.visitbristol.co.uk/",
    ),
    (
        "AVY",
        "Aberdyfi Beach",
        "https://www.visitwales.com/attraction/beach/aberdyfi-beach-526461",
    ),
    (
        "AYW",
        "Aberystwyth North Beach",
        "https://www.visitwales.com/attraction/beach/aberystwyth-north-beach-526471",
    ),
    (
        "BDT",
        "Bridlington",
        "https://www.visiteastyorkshire.co.uk/explore/bridlington/",
    ),
    (
        "BEB",
        "Bebington and Mersey shore",
        "https://www.visitliverpool.com/",
    ),
    (
        "BMH",
        "Bournemouth Beach",
        "https://www.bcpcouncil.gov.uk/beaches-and-seafront/visit-a-beach/bournemouth-beach",
    ),
    (
        "BNG",
        "Bangor Pier and Menai Strait",
        "https://www.visitwales.com/attraction/attraction-landing-page/bangor-pier-508641",
    ),
    (
        "BOG",
        "Bognor Regis East Beach",
        "https://www.bognorregisbeach.co.uk/beaches/east-beach",
    ),
    (
        "BOH",
        "Bosham Harbour",
        "https://www.visitsouthdowns.com/",
    ),
    (
        "BPB",
        "Blackpool Pleasure Beach",
        "https://www.blackpoolpleasurebeach.com/",
    ),
    (
        "BPN",
        "Blackpool Beach",
        "https://www.visitblackpool.com/things-to-do/beach/",
    ),
    (
        "BPS",
        "Blackpool South Beach",
        "https://www.visitblackpool.com/things-to-do/beach/",
    ),
    (
        "BRH",
        "Borth Beach",
        "https://www.visitwales.com/attraction/beach/borth-beach-535131",
    ),
    (
        "BRM",
        "Barmouth Beach",
        "https://www.visitwales.com/attraction/beach/barmouth-beach-532101",
    ),
    (
        "BSR",
        "Broadstairs Viking Bay",
        "https://www.visitthanet.co.uk/beaches/viking-bay-broadstairs/",
    ),
    (
        "BTN",
        "Brighton Beach",
        "https://www.visitbrighton.com/things-to-do/brighton-beach-p1033963",
    ),
    (
        "CBB",
        "Carbis Bay Beach",
        "https://www.visitcornwall.com/things-to-do/beaches/carbis-bay",
    ),
    (
        "CCC",
        "Criccieth Beach and castle",
        "https://www.visitwales.com/attraction/beach/criccieth-beach-541151",
    ),
    (
        "CDT",
        "Caldicot and Severn estuary",
        "https://www.visitmonmouthshire.com/",
    ),
    (
        "CFH",
        "Chafford Hundred Lakeside",
        "https://www.thurrock.gov.uk/",
    ),
    (
        "CFS",
        "Caernarfon Castle and harbour",
        "https://www.visitwales.com/attraction/castle/caernarfon-castle-660471",
    ),
    (
        "CLE",
        "Cleethorpes",
        "https://discovernortheastlincolnshire.co.uk/explore/cleethorpes/",
    ),
    (
        "CLT",
        "Clacton-on-Sea",
        "https://www.visitessex.com/explore/coastal-destinations/clacton-on-sea",
    ),
    (
        "CMR",
        "Cromer Beach",
        "https://www.visitnorthnorfolk.com/towns-villages/cromer.aspx",
    ),
    (
        "CNF",
        "Carnforth and Morecambe Bay",
        "https://www.lancasterandmorecambebay.com/",
    ),
    (
        "CNW",
        "Conwy Castle and waterfront",
        "https://www.visitwales.com/attraction/castle/conwy-castle-660481",
    ),
    (
        "CTM",
        "Chatham Historic Dockyard",
        "https://thedockyard.co.uk/",
    ),
    (
        "CWB",
        "Colwyn Bay Beach",
        "https://www.visitwales.com/attraction/beach/colwyn-bayrhos-sea-beach-535141",
    ),
    (
        "DEA",
        "Deal Beach and pier",
        "https://www.whitecliffscountryside.org.uk/deal-beach",
    ),
    (
        "DFD",
        "Dartford riverside",
        "https://www.visitkent.co.uk/",
    ),
    (
        "DWL",
        "Dawlish Beach and sea wall",
        "https://www.visitdawlish.co.uk/",
    ),
    (
        "DWW",
        "Dawlish Warren Beach",
        "https://www.visitdawlish.co.uk/dawlish-warren",
    ),
    (
        "EBN",
        "Eastbourne Beaches",
        "https://www.visiteastbourne.com/explore/seafront/beaches",
    ),
    (
        "EMS",
        "Emsworth Harbour",
        "https://www.conservancy.co.uk/page/emsworth",
    ),
    (
        "ETL",
        "East Tilbury and Thames estuary",
        "https://www.thurrock.gov.uk/",
    ),
    (
        "EXM",
        "Exmouth Beach",
        "https://www.visitsouthdevon.co.uk/beaches/exmouth",
    ),
    (
        "FBY",
        "Formby Beach and dunes",
        "https://www.nationaltrust.org.uk/visit/liverpool-lancashire/formby",
    ),
    (
        "FIL",
        "Filey Beach",
        "https://visitnorthyorkshire.com/index/filey-beach",
    ),
    (
        "FLM",
        "Flimby and Solway coast",
        "https://www.visitcumbria.com/",
    ),
    (
        "FLN",
        "Flint Castle and Dee estuary",
        "https://www.visitwales.com/attraction/castle/flint-castle-660501",
    ),
    (
        "FLX",
        "Felixstowe Beach",
        "https://www.visitsuffolk.com/destinations/felixstowe",
    ),
    (
        "FRB",
        "Fairbourne Beach",
        "https://www.visitwales.com/attraction/beach/fairbourne-beach-541161",
    ),
    (
        "FRI",
        "Frinton-on-Sea Beach",
        "https://www.tendringcoastalheritage.org.uk/frinton-on-sea",
    ),
    (
        "GRV",
        "Gravesend Thames riverside",
        "https://www.visitkent.co.uk/destinations/gravesend/",
    ),
    (
        "GRY",
        "Grays Thameside",
        "https://www.thurrock.gov.uk/",
    ),
    (
        "GYM",
        "Great Yarmouth Central Beach",
        "https://www.visitgreatyarmouth.co.uk/things-to-do/great-yarmouth-central-beach-p1379051",
    ),
    (
        "HAV",
        "Havant and Langstone Harbour",
        "https://www.visithampshire.co.uk/",
    ),
    (
        "HES",
        "Hessle foreshore and Humber Bridge",
        "https://www.visithull.org/what-to-do/humber-bridge/",
    ),
    (
        "HGS",
        "Hastings Beach",
        "https://www.visit1066country.com/things-to-do/outdoors/beaches/hastings-beach",
    ),
    (
        "HHD",
        "Holyhead Breakwater Country Park",
        "https://www.visitanglesey.co.uk/en-gb/explore/holyhead-breakwater-country-park",
    ),
    (
        "HNB",
        "Herne Bay Beach and pier",
        "https://www.canterbury.co.uk/herne-bay",
    ),
    (
        "HOL",
        "Holton Heath and Poole Harbour",
        "https://www.pooletourism.com/",
    ),
    (
        "HPL",
        "Hartlepool Headland and marina",
        "https://www.destinationhartlepool.com/",
    ),
    (
        "HRE",
        "Horden Beach (Durham Heritage Coast)",
        "https://www.thisisdurham.com/",
    ),
    (
        "HRL",
        "Harlech Beach and castle",
        "https://www.visitwales.com/attraction/beach/harlech-beach-547051",
    ),
    (
        "HYK",
        "Hoylake Beach",
        "https://www.visitwirral.com/beaches/hoylake-beach",
    ),
    (
        "HYL",
        "Hayle Towans Beach",
        "https://www.visitcornwall.com/things-to-do/beaches/hayle-towans",
    ),
    (
        "IHS",
        "Ilfracombe Harbour and Capstone",
        "https://www.visitilfracombe.co.uk/",
    ),
    (
        "KBX",
        "Kirby Cross and Tendring coast",
        "https://www.visitessex.com/",
    ),
    (
        "KLN",
        "King's Lynn and the Wash",
        "https://www.visitwestnorfolk.com/",
    ),
    (
        "KNT",
        "Kenton and Exe estuary",
        "https://www.visitdevon.co.uk/",
    ),
    (
        "LBR",
        "Llanbedr and Ardudwy coast",
        "https://www.visitwales.com/",
    ),
    (
        "LEL",
        "Lelant Saltings and Hayle estuary",
        "https://www.visitcornwall.com/",
    ),
    (
        "LIT",
        "Littlehampton Beach",
        "https://www.visitlittlehampton.co.uk/beaches/",
    ),
    (
        "LLD",
        "Llandudno West Shore Beach",
        "https://www.visitwales.com/attraction/beach/llandudno-west-shore-beach-547071",
    ),
    (
        "LLE",
        "Llanelli Millennium Coastal Path",
        "https://www.visitwales.com/attraction/walking/millennium-coastal-path-554151",
    ),
    (
        "LLF",
        "Llanfairfechan Beach",
        "https://www.visitwales.com/attraction/beach/llanfairfechan-beach-547061",
    ),
    (
        "LLW",
        "Llwyngwril Beach",
        "https://www.visitwales.com/destinations/north-wales/llwyngwril",
    ),
    (
        "LOO",
        "Looe Beach and harbour",
        "https://www.visitcornwall.com/destinations/looe",
    ),
    (
        "LWM",
        "Llantwit Major Beach",
        "https://www.visitthevale.com/beaches/llantwit-major-beach",
    ),
    (
        "LWT",
        "Lowestoft Beach",
        "https://www.visitlowestoft.co.uk/beaches/",
    ),
    (
        "MAR",
        "Margate Main Sands",
        "https://www.thanet.gov.uk/locations/margate-main-sands/",
    ),
    (
        "MCM",
        "Morecambe Beach",
        "https://lancasterandmorecambebay.com/things-to-do/days-out/morecambe-beach",
    ),
    (
        "MEO",
        "Meols Beach (Wirral)",
        "https://www.visitwirral.com/",
    ),
    (
        "MFH",
        "Milford Haven waterfront",
        "https://www.visitpembrokeshire.com/explore-pembrokeshire/towns-and-villages/milford-haven",
    ),
    (
        "MIS",
        "Mistley Thames-side quay",
        "https://www.visitessex.com/",
    ),
    (
        "MNG",
        "Manningtree and Stour estuary",
        "https://www.visitessex.com/",
    ),
    (
        "MRB",
        "Manorbier Beach",
        "https://www.visitpembrokeshire.com/explore-pembrokeshire/beaches/manorbier",
    ),
    (
        "MRY",
        "Maryport harbour and promenade",
        "https://www.visitcumbria.com/wc/maryport/",
    ),
    (
        "NFL",
        "Northfleet Thames riverside",
        "https://www.visitkent.co.uk/",
    ),
    (
        "NHL",
        "New Holland Humber foreshore",
        "https://www.visithull.org/",
    ),
    (
        "NQY",
        "Fistral Beach",
        "https://www.visitcornwall.com/things-to-do/beaches/fistral-beach",
    ),
    (
        "NTL",
        "Netley and Southampton Water",
        "https://www.visitsouthampton.co.uk/",
    ),
    (
        "PEB",
        "Pevensey Bay Beach",
        "https://www.visiteastbourne.com/explore/nearby/pevensey-bay",
    ),
    (
        "PEN",
        "Penarth Pier and Esplanade",
        "https://www.visitthevale.com/penarth",
    ),
    (
        "PES",
        "Pensarn Beach",
        "https://www.visitwales.com/attraction/beach/pensarn-beach-556621",
    ),
    (
        "PGN",
        "Paignton Sands",
        "https://www.torbay.gov.uk/leisure-sports-and-community/beaches/find-a-beach/paignton-sands/",
    ),
    (
        "PIA",
        "Pill riverside (River Avon)",
        "https://www.n-somerset.gov.uk/",
    ),
    (
        "PLY",
        "Plymouth Hoe and waterfront",
        "https://www.visitplymouth.co.uk/",
    ),
    (
        "PMD",
        "Pembroke Dock waterfront",
        "https://www.visitpembrokeshire.com/explore-pembrokeshire/towns-and-villages/pembroke-dock",
    ),
    (
        "PMW",
        "Penmaenmawr Beach",
        "https://www.visitwales.com/attraction/beach/penmaenmawr-beach-556631",
    ),
    (
        "PNA",
        "Penally Beach",
        "https://www.visitpembrokeshire.com/explore-pembrokeshire/beaches/penally",
    ),
    (
        "PNZ",
        "Penzance and Battery Rocks Beach",
        "https://www.visitcornwall.com/destinations/penzance",
    ),
    (
        "POH",
        "Portishead Marina and Lake Grounds",
        "https://www.portisheadtowncouncil.co.uk/",
    ),
    (
        "POO",
        "Poole Harbour and Sandbanks",
        "https://www.pooletourism.com/beaches/sandbanks-beach",
    ),
    (
        "PRH",
        "Penrhyndeudraeth and Dwyryd estuary",
        "https://www.visitwales.com/destination/penrhyndeudraeth",
    ),
    (
        "PRN",
        "Parton Solway shore",
        "https://www.visitcumbria.com/",
    ),
    (
        "PRT",
        "Prestatyn Central Beach",
        "https://www.visitwales.com/attraction/beach/prestatyn-central-beach-556641",
    ),
    (
        "PTM",
        "Porthmadog harbour",
        "https://www.visitwales.com/destination/porthmadog",
    ),
    (
        "PWL",
        "Pwllheli Beach",
        "https://www.visitwales.com/attraction/beach/pwllheli-beach-556651",
    ),
    (
        "QBR",
        "Queenborough and Swale estuary",
        "https://www.visitkent.co.uk/",
    ),
    (
        "RAM",
        "Ramsgate Main Sands",
        "https://www.visitthanet.co.uk/beaches/ramsgate-main-sands/",
    ),
    (
        "RHL",
        "Rhyl Central Beach",
        "https://www.visitwales.com/attraction/beach/rhyl-central-beachseafront-557761",
    ),
    (
        "RHO",
        "Rhosneigr Beach",
        "https://www.visitanglesey.co.uk/en-gb/explore/rhosneigr-beach",
    ),
    (
        "RIA",
        "Rhoose Point and Wales Coast Path",
        "https://www.visitthevale.com/",
    ),
    (
        "RTR",
        "Rochester Castle and riverside",
        "https://www.visitmedway.org/rochester/",
    ),
    (
        "SAN",
        "Sandown Beach",
        "https://www.visitisleofwight.co.uk/beaches/sandown-beach",
    ),
    (
        "SAU",
        "St Austell Bay",
        "https://www.visitcornwall.com/destinations/st-austell",
    ),
    (
        "SBS",
        "St Bees Beach",
        "https://www.visitcumbria.com/wc/st-bees/",
    ),
    (
        "SCA",
        "Scarborough North Bay",
        "https://visitnorthyorkshire.com/index/scarborough-north-bay",
    ),
    (
        "SCS",
        "Starcross and Exe estuary",
        "https://www.visitdevon.co.uk/",
    ),
    (
        "SDD",
        "St Davids and coast path",
        "https://www.visitpembrokeshire.com/explore-pembrokeshire/towns-and-villages/st-davids",
    ),
    (
        "SDF",
        "Saundersfoot Beach",
        "https://www.visitpembrokeshire.com/explore-pembrokeshire/beaches/saundersfoot-beach",
    ),
    (
        "SEA",
        "Seaham Beach and marina",
        "https://www.thisisdurham.com/explore-durham/seaham",
    ),
    (
        "SFO",
        "Stanford-le-Hope Thames estuary",
        "https://www.thurrock.gov.uk/",
    ),
    (
        "SGE",
        "Swanage Beach",
        "https://www.visitswanage.info/beaches/",
    ),
    (
        "SGM",
        "St Germans and Lynher estuary",
        "https://www.visitcornwall.com/",
    ),
    (
        "SHM",
        "Sheringham Beach",
        "https://www.visitnorthnorfolk.com/towns-villages/sheringham.aspx",
    ),
    (
        "SHN",
        "Shanklin Beach",
        "https://www.visitisleofwight.co.uk/beaches/shanklin-beach",
    ),
    (
        "SIV",
        "Porthmeor Beach",
        "https://www.visitcornwall.com/things-to-do/beaches/porthmeor-beach",
    ),
    (
        "SKG",
        "Skegness Beach",
        "https://www.visitlincolnshire.com/destinations/skegness/",
    ),
    (
        "SOC",
        "Southend-on-Sea Beach",
        "https://www.visitsouthendonsea.co.uk/explore/beaches/",
    ),
    (
        "SOE",
        "Southend-on-Sea Beach",
        "https://www.visitsouthendonsea.co.uk/explore/beaches/",
    ),
    (
        "SOP",
        "Southport Beach",
        "https://sefton.gov.uk/around-sefton/coast-and-countryside/visiting-our-beaches/southport-beach",
    ),
    (
        "SOV",
        "Southend-on-Sea Beach",
        "https://www.visitsouthendonsea.co.uk/explore/beaches/",
    ),
    (
        "SSC",
        "Seascale Beach",
        "https://www.visitcumbria.com/wc/seascale/",
    ),
    (
        "SSE",
        "Shoreham Beach",
        "https://www.visitsussex.org/destination/shoreham-by-sea/",
    ),
    (
        "STS",
        "Saltash and Tamar Bridge",
        "https://www.visitcornwall.com/",
    ),
    (
        "SUN",
        "Sunderland Roker Beach",
        "https://www.seesunderland.com/see-and-do/roker-beach",
    ),
    (
        "SVB",
        "Severn Beach",
        "https://www.visitsouthglos.org.uk/",
    ),
    (
        "SVR",
        "Silverdale and Morecambe Bay",
        "https://www.arnsideandsilverdaleaonb.org.uk/",
    ),
    (
        "SWA",
        "Swansea Bay Beach",
        "https://www.visitswanseabay.com/things-to-do/beaches/swansea-bay/",
    ),
    (
        "SWM",
        "Swanscombe Thames marshes",
        "https://www.visitkent.co.uk/",
    ),
    (
        "TEN",
        "Tenby North Beach",
        "https://www.visitpembrokeshire.com/explore-pembrokeshire/beaches/tenby-north-beach",
    ),
    (
        "TGM",
        "Teignmouth Beach",
        "https://www.visitdevon.co.uk/destinations/teignmouth",
    ),
    (
        "TQY",
        "Torre Abbey Sands",
        "https://www.torbay.gov.uk/leisure-sports-and-community/beaches/find-a-beach/torre-abbey-sands/",
    ),
    (
        "TTN",
        "Totton and Southampton Water",
        "https://www.visitsouthampton.co.uk/",
    ),
    (
        "TYW",
        "Tywyn Beach",
        "https://www.visitwales.com/attraction/beach/tywyn-beach-557771",
    ),
    (
        "ULV",
        "Ulverston and Morecambe Bay",
        "https://www.visitcumbria.com/sl/ulverston/",
    ),
    (
        "VAL",
        "Valley and Anglesey coast",
        "https://www.visitanglesey.co.uk/en-gb",
    ),
    (
        "WEY",
        "Weymouth Beach",
        "https://www.weymouthtowncouncil.gov.uk/services/the-beach/",
    ),
    (
        "WHI",
        "Whitstable Beach",
        "https://www.visitkent.co.uk/attractions/whitstable-beach-2847/",
    ),
    (
        "WKG",
        "Workington harbour",
        "https://www.visitcumbria.com/wc/workington/",
    ),
    (
        "WKI",
        "West Kirby Marine Lake and beach",
        "https://www.visitwirral.com/beaches/west-kirby-beach",
    ),
    (
        "WRH",
        "Worthing Beach",
        "https://www.visitworthing.co.uk/beaches",
    ),
    (
        "WSM",
        "Weston-super-Mare Beach",
        "https://www.visit-westonsupermare.com/beaches/",
    ),
    (
        "WTB",
        "Whitby Beach",
        "https://visitnorthyorkshire.com/index/whitby-beach",
    ),
    (
        "WTH",
        "Whitehaven harbour",
        "https://www.visitcumbria.com/wc/whitehaven/",
    ),
    (
        "XMT",
        "Dartmouth Embankment",
        "https://www.visitdartmouth.com/",
    ),
)


def seaside_crs_missing_coastal_proofs(
    facets_by_crs: dict[str, set[str]],
) -> list[str]:
    """Return seaside-tagged CRS codes that lack a COASTAL_SITE_PROOFS row."""
    proved = {crs for crs, _name, _url in COASTAL_SITE_PROOFS}
    return sorted(
        crs
        for crs, facets in facets_by_crs.items()
        if "seaside" in facets and crs not in proved
    )


UNESCO_WORLD_HERITAGE_FILE_URL = "https://whc.unesco.org/en/list/xml"


# The day-out sources ADR-0062 put on the integration backlog, each as its own
# reviewed list. ADR-0063 links a list to the feed with the hybrid
# closest-station prune: the curated candidate stations are kept, any candidate
# beyond ``max_km`` from the attraction point is dropped, and the nearest
# station or a soft twin survives. A reviewed list is a floor rather than a
# ceiling -- a reserve, a property or a gateway added later needs one entry
# here -- and the source text on the facet says so.
@dataclass(frozen=True)
class ReviewedAttraction:
    """One reviewed day-out and the station(s) a reader reaches it from.

    ``stations`` are the curated candidate names as the feed writes them;
    ``points`` are WGS84 decimals near the attraction, with a component point
    per gateway for a corridor or a multi-entrance landscape, so a valley or a
    coastline is not collapsed by one centroid. The point judges the candidate,
    it does not replace it: with no coordinate file the curated list stands as
    written.
    """

    name: str
    url: str
    stations: tuple[str, ...]
    points: tuple[tuple[float, float], ...]


# RSPB reserves. Rainham Marshes is the Rainham-class gap the nature comments
# already named: a reserve on the Thames estuary no Wildlife Trust list covers.
RSPB_RESERVES: tuple[ReviewedAttraction, ...] = (
    ReviewedAttraction(
        "Rainham Marshes",
        "https://www.rspb.org.uk/nature-reserves/rainham-marshes/",
        ("Purfleet",),
        ((51.4870, 0.2190),),
    ),
    ReviewedAttraction(
        "Leighton Moss",
        "https://www.rspb.org.uk/nature-reserves/leighton-moss/",
        ("Silverdale",),
        ((54.1704, -2.7996),),
    ),
    ReviewedAttraction(
        "Bempton Cliffs",
        "https://www.rspb.org.uk/nature-reserves/bempton-cliffs/",
        ("Bempton",),
        ((54.1500, -0.1660),),
    ),
    ReviewedAttraction(
        "Minsmere",
        "https://www.rspb.org.uk/nature-reserves/minsmere/",
        ("Darsham",),
        ((52.2430, 1.6140),),
    ),
    ReviewedAttraction(
        "Conwy",
        "https://www.rspb.org.uk/nature-reserves/conwy/",
        ("Conwy",),
        ((53.2880, -3.8180),),
    ),
    ReviewedAttraction(
        "Frampton Marsh",
        "https://www.rspb.org.uk/nature-reserves/frampton-marsh/",
        ("Boston",),
        ((52.9240, 0.0120),),
    ),
    ReviewedAttraction(
        "Fairburn Ings",
        "https://www.rspb.org.uk/nature-reserves/fairburn-ings/",
        ("Castleford",),
        ((53.7400, -1.3420),),
    ),
    ReviewedAttraction(
        "Newport Wetlands",
        "https://www.rspb.org.uk/nature-reserves/newport-wetlands/",
        ("Newport (S Wales)",),
        ((51.5560, -2.9560),),
    ),
    ReviewedAttraction(
        "Saltholme",
        "https://www.rspb.org.uk/nature-reserves/saltholme/",
        ("Middlesbrough",),
        ((54.5950, -1.2200),),
    ),
)

# National Trust visitor properties. Bookham already carries the CRS + URL
# proof shape the ADR names; these are the same shape rather than a sweep of
# every NT holding.
NATIONAL_TRUST_PROPERTIES: tuple[ReviewedAttraction, ...] = (
    ReviewedAttraction(
        "Bookham Commons",
        "https://www.nationaltrust.org.uk/visit/surrey/bookham-commons",
        ("Bookham",),
        ((51.2880, -0.3730),),
    ),
    ReviewedAttraction(
        "Cliveden",
        "https://www.nationaltrust.org.uk/visit/buckinghamshire/cliveden",
        ("Bourne End",),
        ((51.5580, -0.6930),),
    ),
    ReviewedAttraction(
        "Quarry Bank",
        "https://www.nationaltrust.org.uk/visit/cheshire/quarry-bank-mill",
        ("Styal",),
        ((53.3450, -2.2420),),
    ),
    ReviewedAttraction(
        "Speke Hall",
        "https://www.nationaltrust.org.uk/visit/liverpool/speke-hall-garden-and-estate",
        # The feed truncates this name to "LIVERPOOL S PWAY"; a curated list
        # names a station the way the feed writes it (ADR-0026).
        ("Liverpool S Pway",),
        ((53.3420, -2.8580),),
    ),
    ReviewedAttraction(
        "Sissinghurst Castle Garden",
        "https://www.nationaltrust.org.uk/visit/kent/sissinghurst-castle-garden",
        ("Staplehurst",),
        ((51.1160, 0.5600),),
    ),
    ReviewedAttraction(
        "Bodiam Castle",
        "https://www.nationaltrust.org.uk/visit/east-sussex/bodiam-castle",
        ("Robertsbridge",),
        ((50.9460, 0.5430),),
    ),
    ReviewedAttraction(
        "Corfe Castle",
        "https://www.nationaltrust.org.uk/visit/dorset/corfe-castle",
        # Corfe Castle has its own station in the feed (CFC), so the reader
        # steps off beside the castle rather than at Wareham, six miles away.
        ("Corfe Castle",),
        ((50.6390, -2.0580),),
    ),
    ReviewedAttraction(
        "Chartwell",
        "https://www.nationaltrust.org.uk/visit/kent/chartwell",
        ("Sevenoaks",),
        ((51.2440, 0.0820),),
    ),
    ReviewedAttraction(
        "Kedleston Hall",
        "https://www.nationaltrust.org.uk/visit/derbyshire/kedleston-hall",
        ("Derby",),
        ((52.9590, -1.5350),),
    ),
)

# National Park and National Landscape (AONB) gateways. The reviewed list names
# gateways only, never every station inside a polygon: a chip that tagged the
# whole of Snowdonia would be louder and less useful, which is the failure
# ADR-0026 exists to prevent.
NATIONAL_PARK_GATEWAYS: tuple[ReviewedAttraction, ...] = (
    ReviewedAttraction(
        "Peak District",
        "https://www.peakdistrict.gov.uk/",
        ("Edale",),
        ((53.3650, -1.8160),),
    ),
    ReviewedAttraction(
        "Lake District",
        "https://www.lakedistrict.gov.uk/",
        ("Windermere",),
        ((54.3796, -2.9034),),
    ),
    ReviewedAttraction(
        "Eryri (Snowdonia)",
        "https://www.eryri.llyw.cymru/",
        ("Betws-y-Coed",),
        ((53.0930, -3.8030),),
    ),
    ReviewedAttraction(
        "Yorkshire Dales",
        "https://www.yorkshiredales.org.uk/",
        ("Settle",),
        ((54.0680, -2.2790),),
    ),
    ReviewedAttraction(
        "North York Moors",
        "https://www.northyorkmoors.org.uk/",
        ("Whitby",),
        ((54.4850, -0.6150),),
    ),
    ReviewedAttraction(
        "South Downs",
        "https://www.southdowns.gov.uk/",
        ("Amberley",),
        ((50.8970, -0.5350),),
    ),
    ReviewedAttraction(
        "New Forest",
        "https://www.newforestnpa.gov.uk/",
        ("Brockenhurst",),
        ((50.8160, -1.5730),),
    ),
    ReviewedAttraction(
        "Broads",
        "https://www.broads-authority.gov.uk/",
        # The feed truncates this name to "HOVETON &WROXHM".
        ("Hoveton &Wroxhm",),
        ((52.7150, 1.4090),),
    ),
    ReviewedAttraction(
        "Pembrokeshire Coast",
        "https://www.pembrokeshirecoast.wales/",
        ("Tenby",),
        ((51.6720, -4.7030),),
    ),
    ReviewedAttraction(
        "Cairngorms",
        "https://cairngorms.co.uk/",
        ("Aviemore",),
        ((57.1890, -3.8290),),
    ),
    ReviewedAttraction(
        "Dartmoor",
        "https://www.dartmoor.gov.uk/",
        ("Okehampton",),
        ((50.7320, -4.0000),),
    ),
    ReviewedAttraction(
        "Northumberland",
        "https://www.northumberlandnationalpark.org.uk/",
        ("Haltwhistle",),
        ((54.9700, -2.4560),),
    ),
    ReviewedAttraction(
        "Cotswolds",
        "https://www.cotswolds-nl.org.uk/",
        ("Moreton-in-Marsh",),
        ((51.9880, -1.7030),),
    ),
    ReviewedAttraction(
        "Chilterns",
        "https://www.chilterns.org.uk/",
        ("Great Missenden",),
        ((51.7040, -0.7070),),
    ),
    ReviewedAttraction(
        "Shropshire Hills",
        "https://www.shropshirehills-nl.org.uk/",
        ("Craven Arms",),
        ((52.4400, -2.8300),),
    ),
    ReviewedAttraction(
        "Wye Valley",
        "https://www.wyevalley-nl.org.uk/",
        ("Chepstow",),
        ((51.6420, -2.6760),),
    ),
    ReviewedAttraction(
        "Malvern Hills",
        "https://www.malvernhills-nl.org.uk/",
        ("Great Malvern",),
        ((52.1130, -2.3170),),
    ),
    ReviewedAttraction(
        "Cannock Chase",
        "https://www.cannockchase-nl.org.uk/",
        ("Rugeley Town",),
        ((52.7630, -1.9300),),
    ),
    ReviewedAttraction(
        "Dedham Vale",
        "https://www.dedhamvale-nl.org.uk/",
        ("Manningtree",),
        ((51.9700, 0.9500),),
    ),
)

REVIEWED_ATTRACTIONS_BY_FACET: dict[str, tuple[ReviewedAttraction, ...]] = {
    "rspb": RSPB_RESERVES,
    "national_trust": NATIONAL_TRUST_PROPERTIES,
    "national_park": NATIONAL_PARK_GATEWAYS,
}

DESTINATION_FACET_SOURCES: tuple[DestinationFacet, ...] = (
    DestinationFacet(
        key="seaside",
        label="Coastal & seaside",
        source=(
            "Office for National Statistics, Census 2021 coastal communities "
            "characteristics of built-up areas, plus a reviewed CRS supplement "
            "for classic day-out stations the workbook name-match misses"
        ),
        url=ONS_COASTAL_BUILT_UP_AREAS_DATASET_URL,
        coverage="England and Wales",
        reader="ons_coastal_built_up_areas",
        reviewed_station_codes=SEASIDE_SUPPLEMENT_CRS,
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
    DestinationFacet(
        key="rspb",
        label="RSPB reserves",
        source=(
            "reviewed list of stations reaching RSPB reserves, linked by the "
            "hybrid closest-station prune"
        ),
        url="https://www.rspb.org.uk/nature-reserves/",
        coverage="United Kingdom, as covered by the DTD feed",
        reader="reviewed_station_codes",
        reviewed_attractions=RSPB_RESERVES,
    ),
    DestinationFacet(
        key="national_trust",
        label="National Trust",
        source=(
            "reviewed list of stations reaching National Trust visitor "
            "properties, linked by the hybrid closest-station prune"
        ),
        url="https://www.nationaltrust.org.uk/visit",
        coverage="England, Wales and Northern Ireland, as covered by the DTD feed",
        reader="reviewed_station_codes",
        reviewed_attractions=NATIONAL_TRUST_PROPERTIES,
    ),
    DestinationFacet(
        key="national_park",
        label="National parks and landscapes",
        source=(
            "reviewed gateway stations for National Parks and National "
            "Landscapes (AONBs), linked by the hybrid closest-station prune"
        ),
        url="https://www.nationalparks.uk/",
        coverage="England, Wales and Scotland, as covered by the DTD feed",
        reader="reviewed_station_codes",
        reviewed_attractions=NATIONAL_PARK_GATEWAYS,
    ),
)
SUPPORTED_DESTINATION_FACETS = frozenset(facet.key for facet in DESTINATION_FACET_SOURCES)
# Bumped when the primary classes change shape, so a cache written before the
# change is recognised rather than trusted.
# Bumped to 4 when the reviewed settlement lists were corrected, and to 5 when a
# second review corrected five more of them: Barming, Wakefield Westgate,
# Rotherham Central, Newton-le-Willows and Southend Airport. The cache holds the
# *final* classification, fallbacks included, and a reload only applies a
# fallback where the loaded value is missing or "other" -- so a corrected
# fallback could not reach any machine holding a cache written before the
# correction, and the wrong class would have kept being served from it. A
# schema bump is the existing mechanism for exactly this: the old primary
# classes are discarded and re-derived, and the facets are kept.
LOCATION_CACHE_SCHEMA = 6
# The two file names the classification pass may read from beside a feed, and
# the only ones it trusts. A build writes the bare name beside the feed; a
# fixture or a download writes the same name behind its own feed's name
# (``fares.location-types.json``), so those two shapes are accepted and nothing
# else is. A looser ``*location*types*.json`` matched any name that spelled
# those words in order -- a backup, a staging probe, a copy left behind by
# hand -- and loaded it as a source.
LOCATION_TYPES_FILE = "location-types.json"
DESTINATION_FACETS_FILE = "destination-facets.json"


def classification_files(directory: Path) -> list[Path]:
    """List the classification files this project may have written in a directory.

    The name is the contract: the bare name, or the bare name behind a feed's
    own (``fares.location-types.json``). Any other prefix is a name this project
    never writes, whatever it looks like.
    """
    return sorted(
        path
        for name in (LOCATION_TYPES_FILE, DESTINATION_FACETS_FILE)
        for pattern in (name, f"*.{name}")
        for path in directory.glob(pattern)
        if path.is_file()
    )


def location_lookup_candidates(path: str | Path) -> list[Path]:
    """Every file a load of ``path`` could take a station's type from.

    This is the list ``FaresDb._load_location_lookup`` reads, in the same
    order, and it is a function rather than a body inside that method because
    a second caller needs the same answer: a fares cache is keyed on the feed's
    bytes *and* these files, and a key that listed them separately would be a
    list that could drift from the one the loader actually reads. A corrected
    classification file beside the feed, or a reviewed facet added to the
    checked-in reference data, changes what a parse produces without changing
    a single byte of the feed.
    """
    root = Path(path)
    candidates: list[Path] = []
    candidates.extend((Path(__file__).parent / "reference-data").glob("*.json"))
    if root.is_dir():
        candidates.extend(root.glob("*.xml"))
        candidates.extend(root.glob("*.json"))
        candidates.extend(root.parent.glob("FareLocationsRefData*.xml"))
        candidates.extend(classification_files(root.parent))
    elif root.suffix.lower() == ".zip":
        # The checked-in download lives at feeds/fares/dtd-fares.zip while its
        # reference files live one level up in feeds/. Accept both that layout
        # and feeds/dtd-fares.zip beside its references.
        for base in (root.parent, root.parent.parent):
            candidates.extend(base.glob("FareLocationsRefData*.xml"))
            candidates.extend(classification_files(base))
    return candidates
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


# The fare-construction points the 24 September 2026 download carries, read
# off its own station names. A reviewed list rather than a name test: the codes
# are the feed's identity for a station, so a rename surfaces as a dead code
# the build names, instead of a new name that quietly stops matching. Tools
# propose additions to this list with the evidence; only a person adds one.
FARE_CONSTRUCTION_CRS = frozenset({
    "QAG",  # BOUNDARY ZONE 3
    "QAH",  # BOUNDARY ZONE 4
    "QAI",  # BOUNDARY ZONE 5
    "QAJ",  # BOUNDARY ZONE 6
    "QAK",  # BOUNDARY ZONE 2
    "QBU",  # BRIGHTON UNIZONE
    "QWU",  # WORTHING UNIZONE
    "QMZ",  # METRO T&W ZONE A
    "KLB",  # KINGS LYNN COACH
    "QDM",  # DEREHAM (COACH)
    "SWB",  # SWAFFHAM (COACH)
    "WIS",  # WISBECH (COACH)
})

# The name shape that proposes a code for review. It proposes; it never
# decides. On the 24 September 2026 download it matched exactly the twelve
# codes above and nothing else, which is why the split is worth keeping: the
# evidence is cheap to gather, the judgement is not.
FARE_CONSTRUCTION_NAME_MARKERS = ("ZONE", "COACH")


def looks_like_fare_construction(name: str) -> bool:
    """Whether a station's *name* looks like a fare-construction point.

    The evidence ``tools/propose_fare_construction_stations.py`` prints with
    each proposal, and nothing more. On the current feed it is exact, but a
    future station called COACH HOUSE would match it, so a person decides
    whether the code joins FARE_CONSTRUCTION_CRS.
    """
    upper = name.strip().upper()
    return any(marker in upper for marker in FARE_CONSTRUCTION_NAME_MARKERS)


def is_not_for_public_sale(name: str | None) -> bool:
    """Whether the catalogue's own name says this fare is not on sale.

    Upper-cases first, so the caller cannot get this wrong by passing a name
    it already upper-cased or one it did not. Shared by the single and return
    selectors, because when the two held their own copy the return half was
    never added to and a fare called NOT FOR TRAVEL reached a page.
    """
    upper = (name or "").upper()
    return any(marker in upper for marker in NOT_FOR_PUBLIC_SALE_MARKERS)


def is_pseudo_station(crs: str) -> bool:
    """A fare-construction point rather than a place a reader can stand.

    Zone boundaries and zoned-area labels, and named coach stops, are where the
    DTD feed records a fare change rather than a journey. A flow through one is
    real and priced, but no train calls there, so the page must not offer the
    reader a destination or an origin it cannot serve (audit A6).

    The list is reviewed and keyed by CRS rather than matched on the name. A
    substring test over station names is a guess about every future station:
    a real station called Coach House or Hazleton would be silently dropped
    from the chooser, and a renamed zone would start being offered. The CRS is
    the feed's own identity for a station and changes with a rename, so the
    twelve codes below were read off the 24 September 2026 download and the
    names are recorded so a person can check them.
    """
    return crs.strip().upper() in FARE_CONSTRUCTION_CRS

# The real feed's standard-return catalogue contains a family of ITX
# placeholder records. They are not purchasable public fares: the current
# audit found EIS/EIF/IF1/IF3/IS0/IS1/IS3 and LIS/LIF at the £0.05/£0.10
# minimum with restriction GA. Keep the names explicit so a future catalogue
# rename cannot silently reintroduce them, while the ITX name check catches
# new members of the same family.
# Names the catalogue gives a fare that is not on sale. The single selector
# has always tested these and the return selector did not, which let a
# standard return called ZZZ NOT FOR TRAVEL through to a page: 1,001 live rows
# out of Cameron Bridge with a blank restriction and a plausible price. One
# tuple read by both selectors is the fix, because a literal duplicated in two
# places is how the two drifted apart.
NOT_FOR_PUBLIC_SALE_MARKERS = (
    "NOT FOR TRAVEL",
    "TEST",
    "DUMMY",
    "FOR TEST",
    "COMP",
)

PLACEHOLDER_TICKET_CODES = frozenset({
    "EIS", "EIF", "IF1", "IF3", "IS0", "IS1", "IS3", "LIS", "LIF",
    # A GBP 9,998.00 sentinel on one Lincolnshire pair, not an ITX name and so
    # not caught by the check below. It is not a fare, so it belongs here
    # rather than among the conditional tickets, which are real.
    "XD3",
})


# A standard-class fare a reader cannot buy alone at the price it quotes.
# A child, an accompanied child, a party of a stated size, an event or a
# school group are all priced for the whole party, so the number that
# reaches the page is not the number one traveller pays. A 10p UNDER 11
# single reached a page as the cheapest way to its destination and is not
# a journey any adult can buy at that price, so these fares must not win
# the cheapest slot.
#
# The codes are reviewed and read off the feed rather than matched on a word
# in a name, for the reason PLACEHOLDER_TICKET_CODES above gives. The name
# of each family is recorded beside its block so a person can check a code
# against what it prices without opening the feed.
#
# The feed cannot be asked instead. The ticket type record carries a
# passenger block, and SCR GROUP 05, which won 1,486 of the single slots in
# a 60-origin sample, reads one passenger and one adult there, so the block
# does not mark a group. The restriction those fares carry is blank, so
# there is no text on the fare to read either. What the page can say about
# a conditional fare is its price, and its price is the thing in question.
CONDITIONAL_TICKET_CODES = frozenset({
    "GF3",  # ADVANCE GROUP 3
    "GF4",  # ADVANCE GROUP 4
    "GF5",  # ADVANCE GROUP 5
    "BJD",  # AWC STAFF
    "DGA", "DGB", "DGC",  # SALE ADVANCE, all three on route 00429
    "COR",  # WAG CONCES RTN
    "COS",  # WAG CONCES SGL
    "KWA",  # KID WITH ADULT
    "FG3",  # ANYTIME GROUP 3
    "FG4",  # ANYTIME GROUP 4
    "FG5",  # ANYTIME GROUP 5
    "VCA",  # AWC 2 GROUP A
    "VCB",  # AWC 2 GROUP B
    "VCC",  # AWC 2 GROUP C
    "VCD",  # AWC 2 GROUP D
    "VCE",  # AWC 2 GROUP E
    "VCF",  # AWC 2 GROUP F
    "VCG",  # AWC 2 GROUP G
    "VCH",  # AWC 2 GROUP H
    "VCI",  # AWC 2 GROUP I
    "VCJ",  # AWC 2 GROUP J
    "VCK",  # AWC 2 GROUP K
    "VCL",  # AWC 2 GROUP L
    "VSI",  # AWC SCHOOLGRP S
    "TKT",  # CHILD FLAT TRAV
    "TKR",  # CHILD FLTFARE R
    "TKS",  # CHILD FLTFARE S
    "AX0", "AX1", "AX2", "AX3", "AX4", "AX7", "AX8", "AX9",  # CLSC SOLO+CHILD
    "GO3",  # EMR GROUP OPK3
    "GO5",  # EMR GROUP OPK5
    "C2R",  # EVENING GROUP
    "EGP",  # EVENING GROUP R
    "CMR",  # EVENT SOP
    "CE2", "EVE",  # EVENTS STD
    "GF1",  # FLYAWAY 1-CHILD
    "1SH", "1SL", "1SM",  # GROUP CLSIC SOL
    # GROUP PREM STD
    "5GA", "5GB", "5GC", "5GD", "5GE", "5GF", "5GG", "5GH", "5GI", "5GJ", "5GK", "5GL",
    "SE3",  # GROUP SINGLE 3
    "SE4",  # GROUP SINGLE 4
    "GR3",  # GROUPSAVE DAY 3
    "GR4",  # GROUPSAVE DAY 4
    "GR5",  # GROUPSAVE DAY 5
    "2SH", "2SL", "2SM",  # GRP CLSIC TWIN
    "WG2",  # GWR GRP 3 STD
    "WI2",  # GWR GRP 5 STD
    "SPN",  # LNER GRP SGL
    "OPG",  # OFFPEAK GROUP10
    "S01",  # SCR GROUP 01
    "S02",  # SCR GROUP 02
    "S03",  # SCR GROUP 03
    "S04",  # SCR GROUP 04
    "S05",  # SCR GROUP 05
    "S06",  # SCR GROUP 06
    "S07",  # SCR GROUP 07
    "S08",  # SCR GROUP 08
    "S09",  # SCR GROUP 09
    "S10",  # SCR GROUP 10
    "S11",  # SCR GROUP 11
    "S12",  # SCR GROUP 12
    "S13",  # SCR GROUP 13
    "S14",  # SCR GROUP 14
    "S15",  # SCR GROUP 15
    "S16",  # SCR GROUP 16
    "S17",  # SCR GROUP 17
    "S18",  # SCR GROUP 18
    "S19",  # SCR GROUP 19
    "S20",  # SCR GROUP 20
    "S3G",  # SMALL GROUP 3
    "S4G",  # SMALL GROUP 4
    "S5G",  # SMALL GROUP 5
    "S6G",  # SMALL GROUP 6
    "S7G",  # SMALL GROUP 7
    "S8G",  # SMALL GROUP 8
    "S9G",  # SMALL GROUP 9
    "SGD",  # SMALL GROUP DAY
    "V5S",  # SPEC GROUP PREM
    "ENT",  # TFW EVENT CON
    "HX2",  # UNACCOMP CHILD
    "CTR",  # UNDER 11 RETURN
    "CTS",  # UNDER 11 SINGLE
    "TCR",  # UNDER 16 RETURN
    "TCS",  # UNDER 16 SINGLE
})

# The tally key for a fare that lost the slot because a reader cannot buy it at
# the price it quotes. Named once here because three places read it: both
# selectors, the page's empty-page note, and the coverage report that counts
# the loss. The wording names the reason rather than the three conditions the
# table started with, because a staff pass and a staff concession are the same
# fact about a fare and a reader does not care which category it came from.
CONDITIONAL_REASON = "ticket_is_not_one_a_reader_can_buy"
# A fare sold on one named date and train is not a fare to a reader who has not
# chosen a train. It is counted apart from the conditional reason because it is
# a different loss: the fare is real and sold, it just is not the price of the
# journey, and a coverage report that files it under "cannot buy" cannot say
# what a train-restricted fare is costing the list.
ADVANCE_REASON = "fare_is_valid_on_one_train_only"


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
# The reviewed railcard selector. The real DTD catalogue carries 382 railcard
# codes, most of them group-travel, agency, football-club and operator passes
# that no reader arriving at this site holds. Publishing all of them would put
# 382 controls on a page whose premise is that a reader has a budget and an
# hour; publishing none would be a page that cannot answer the question a
# railcard holder arrives with.
#
# An entry is therefore a product and not a code, because the feed gives one
# product several: 16-25 is YNG, and Y3R for three years, YN3 bought online,
# RYP as a repaperminted replacement and GCM through a corporate scheme. A
# reader holding any of them holds the same card and pays the same price, so one
# control reads all of them and the page names the codes it recognised. The
# primary code is the one the discount and the minimum fare are read through.
#
# Set here and reviewed by a person, the same way the anytime-return ticket
# codes are, so a name test cannot widen what the site offers. Removing an
# entry removes that card from the page, and the build then says how many
# catalogue codes it is no longer offering, so the omission is visible rather
# than silent.
REVIEWED_PUBLIC_RAILCARDS: dict[str, dict[str, object]] = {
    "2TR": {"label": "Two Together", "codes": ()},
    "YNG": {
        "label": "16-25 Railcard",
        "codes": ("Y3R", "YN3", "RYP", "GCM"),
    },
    "NEW": {"label": "Network Railcard", "codes": ("RNW", "NCP")},
    "SRN": {
        "label": "Senior Railcard",
        "codes": ("RSN", "GCO", "SRS"),
    },
    "DIS": {
        "label": "Disabled Persons Railcard",
        "codes": ("AT1", "AT4", "DIR"),
    },
    "BB2": {"label": "Student Discount Card", "codes": ()},
}

# The one restriction code this project reviewed and pinned by hand. The
# feed's own ``.RST`` wording decides the rest, but a synthetic or
# truncated feed carries no restriction descriptions at all, and EMR
# advances must still be recognised there. Pinning it keeps the test a
# catalogue can answer without a restriction file.
ADVANCE_RESTRICTION_CODES = frozenset({"AS"})


def is_advance_ticket(name: object) -> bool:
    """Whether a ticket name identifies a yield-managed, train-specific fare."""
    return bool(re.search(r"\bADV(?:ANCE)?\b", str(name or "").upper()))


# The DTD writes its flags as ``Y`` or ``N``. This project's own synthetic feed
# writes ``1`` and ``0`` for the same fields, because it was written before any
# licensed file was available to copy the spelling from. Reading the flag as
# ``== "1"`` therefore matched the synthetic feed and nothing else: on the real
# feed every train-restricted ticket read as unrestricted, and the flag that
# exists to stop an advance fare being quoted as a walk-up price silently never
# fired. The value is read here, at the boundary, rather than at each use, so
# one spelling mistake cannot come back.
DTD_TRUE_FLAGS = frozenset({"Y", "1"})


def dtd_flag(value: object) -> bool:
    """Whether a DTD flag field means yes.

    ``Y`` is what the licensed feeds write. ``1`` is what this project's
    synthetic feed writes. Both mean yes; ``N`` and ``0`` mean no, and so does
    a blank field, which is how the feed spells a flag it does not state.
    """
    return str(value or "").strip().upper() in DTD_TRUE_FLAGS


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


@dataclass(frozen=True, slots=True)
class MinimumFare:
    """One ``.RCM`` record: the floor a discounted fare cannot go below.

    The DTD catalogue writes a validity window on every record, and a key can
    hold several records for different windows. Reading past the window applied
    a lapsed minimum as if it were current (ADR-0025, amended), so the window
    travels with the price and only a record that covers the query day can
    raise a fare.
    """

    pence: int
    start_date: date | None
    end_date: date | None

    def covers(self, day: date) -> bool:
        """Whether this record's own window includes ``day``, ends included."""
        return not (
            (self.start_date is not None and day < self.start_date)
            or (self.end_date is not None and day > self.end_date)
        )


def _adult_bounds(codes: tuple[str, ...], railcards: dict[str, "Railcard"]) -> tuple[int, int]:
    """The adult range a set of railcard codes states between them.

    A bound of zero is the feed's way of not stating one. The 16-25 3-year
    codes Y3R and YN3 both carry 0-0, and reading that at face value reported
    the 16-25 Railcard as covering zero to eight adults. A card cannot price a
    party of no one, so both ends skip an unstated zero, and a set that states
    no bound at all falls back to one adult, which is the only party size the
    feed prices for every railcard it carries.
    """
    lows = [railcards[code].min_adults for code in codes if railcards[code].min_adults > 0]
    highs = [railcards[code].max_adults for code in codes if railcards[code].max_adults > 0]
    return (min(lows) if lows else 1, max(highs) if highs else 1)


@dataclass(frozen=True, slots=True)
class RailcardFamily:
    """One railcard a reader holds, and every code the feed gives it."""

    #: The code the discount and the minimum fare are read through, chosen from
    #: the reviewed entry's primary code and the codes the feed actually has.
    key: str
    #: What the reader is shown. Never a feed string: the catalogue's names are
    #: upper case and truncated ("SEASON HOLDER DSCT"), and this is the one
    #: place a reader is asked to recognise their own card.
    label: str
    #: Every code the feed carries for this product, primary first.
    codes: tuple[str, ...]
    min_adults: int
    max_adults: int


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True)
class TwoPartFare:
    """A place the feed prices only as two published fares, split once.

    ADR-0061. The feed publishes flows along pricing-route boundaries, not along
    the journeys passengers buy, so Grantham to Leeds has no flow of its own and
    a Grantham to Doncaster fare and a Doncaster to Leeds fare that both exist.
    The row is the two of them added together. ``change_crs`` is the pricing
    split: a calling point on the journey's own train(s), or the station the
    reader leaves if that is the only priced locus. ``first`` is exactly the
    row the origin's own page prices for that split, and ``second`` is exactly
    the row the split station's page prices for the destination, read through
    the same selector. When several calling points on the journey both sell,
    the page keeps the cheapest valid sum among those candidates - still the
    journey's own stops, not the cheapest fare on each leg found independently
    of the journey.
    """

    crs: str
    station: str
    change_crs: str
    change_station: str
    first: Reachable
    second: Reachable

    @property
    def best_pence(self) -> int:
        return self.first.best_pence + self.second.best_pence

    @property
    def legs(self) -> tuple[Reachable, Reachable]:
        return (self.first, self.second)


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


def _as_int(value: str) -> int:
    return int(value) if value.isdigit() else 0


# The loader is imported here, below every name it reads: its readers work on the
# record layouts and the row types declared above, so those names have to exist
# before the module that uses them can be, and ``FaresDb`` below them. The two
# halves of the database are one object with one state, and a query method and a
# reader alike are reached on it.
from atoc_fares_loader import FaresLoader  # noqa: E402


class FaresDb(FaresLoader):
    """Indexes the feed files that budget discovery reads."""

    def __init__(self) -> None:
        self.locations_by_nlc: dict[str, Location] = {}
        self.locations_by_crs: dict[str, Location] = {}
        # Destination settlement type is reference data, not a fares LOC field.
        # A reviewed JSON cache beside the feed is preferred; a real DTD build
        # can populate it from the ONS Census built-up-area source.
        self.location_types_by_crs: dict[str, str] = {}
        self.location_facets_by_crs: dict[str, set[str]] = {}
        # CRS -> (lat, lon) from Knowledgebase stations.xml, loaded lazily when
        # a heritage (or multi-CRS nature) prune needs it.
        self._station_coordinates: dict[str, tuple[float, float]] | None = None
        self._station_coordinates_path: Path | None = None
        # Reviewed attraction -> the CRS codes the prune kept, per facet. Built
        # lazily because a page asks for a destination's proof once per row and
        # a whole-network build asks for thousands: without this the prune would
        # be recomputed for every attraction on every row.
        self._attraction_crs_cache: dict[str, dict[str, frozenset[str]]] = {}
        # Every source whose classes this database carries, in load order. One
        # slot made the provenance line the last writer's: a cache beside the
        # feed described classes the ONS workbook had supplied, and the reviewed
        # London, Scottish, Welsh and Northern Irish fallbacks were published as
        # the workbook's own work. Read through the property below.
        self.location_type_sources: list[str] = []
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
        # Keyed by (railcard code, ticket code). A key holds a list, because
        # the catalogue writes one record per validity window rather than one
        # per key: in the 24 September 2026 download 613 of 639 keys carried
        # more than one window, 3,355 records in all.
        self.minimum_fares: dict[tuple[str, str], list[MinimumFare]] = {}
        self.restrictions = RestrictionIndex()
        self.report = ParseReport()
        self.files_read = self.report.files_read
        # A single-origin build only needs fares queryable from that origin.
        # Reversible flows count in both directions. The national feed has
        # millions of unrelated fare records, so retaining
        # every Fare object makes the local app spend most of its time building
        # prices it will never query. This is None for the normal/full database.
        self._focus_origin_nlcs: set[str] | None = None
        # The stations the ONS workbook itself named, kept so the reviewed
        # fallbacks can be checked against the rule they exist to serve: each
        # one must be a station no source could name.
        self.ons_classified_crs: set[str] = set()
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

    @property
    def location_type_source(self) -> str | None:
        """Name every source whose classes this database carries, in load order.

        A source is recorded when it classified part of this feed, and the page
        joins them: with a cache beside the feed, the reviewed fallbacks are a
        source in their own right rather than the workbook's unwritten work.
        """
        recorded = getattr(self, "location_type_sources", ())
        if recorded:
            # The reviewed fallback label is the floor under the sourced classes,
            # so it is named last: "the workbook, plus the reviewed fallbacks for
            # the areas it does not cover" is how the coverage reads. The stable
            # sort keeps every other label in the order it was loaded.
            return " + ".join(
                sorted(recorded, key=lambda label: label == LOCATION_FALLBACK_SOURCE)
            )
        # A database unpickled from a fare-index cache written before the labels
        # were accumulated keeps its one label in the instance dictionary, where
        # this property shadows it. Read that back rather than report no source
        # for classes that have one.
        return str(self.__dict__.get("location_type_source") or "") or None

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
        if focus_origin is not None:
            self._load_interchange_fares(path, origin)
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

    def interchange_crs(self, origin_crs: str) -> set[str]:
        """Every named station a flow out of the origin reaches.

        These are the stations a two-part price can change at (ADR-0061): the
        first ticket is a fare from the origin, so the change station is one
        the origin's own flows name. Read from the flow records, which a
        focused load keeps whole, so the answer is the same before and after
        the fares themselves have been narrowed to one origin.
        """
        origin = self.locations_by_crs.get(origin_crs.strip().upper())
        if origin is None:
            return set()
        found: set[str] = set()
        for origin_nlc in self.nlcs_by_crs.get(origin.crs, {origin.nlc}):
            for flow in self.flows_touching_nlc.get(origin_nlc, ()):
                other = (
                    flow.origin_nlc
                    if flow.direction == "R" and flow.destination_nlc == origin_nlc
                    else flow.destination_nlc
                )
                location = self.locations_by_nlc.get(other)
                if (
                    location is None
                    or not location.crs
                    or location.crs == origin.crs
                    or is_pseudo_station(location.crs)
                ):
                    continue
                found.add(location.crs)
        return found

    def station_coordinates(self) -> dict[str, tuple[float, float]]:
        """Return CRS -> (lat, lon), loading Knowledgebase stations.xml once."""
        if self._station_coordinates is not None:
            return self._station_coordinates
        path = self._station_coordinates_path or DEFAULT_STATIONS_XML
        self._station_coordinates = load_station_coordinates(path)
        if not self._station_coordinates and path.is_file() is False:
            self.report.skip_file(
                f"heritage prune: station coordinates file {path} is missing; "
                "curated candidates were kept without a distance filter"
            )
        return self._station_coordinates

    def _candidate_crs(self, stations: tuple[str, ...]) -> list[str]:
        """Return feed CRS codes whose names match the curated station tokens."""
        names = {self._normalise_settlement_name(station) for station in stations}
        return [
            crs
            for crs, location in self.locations_by_crs.items()
            if self._settlement_matches(location.name, names)
        ]

    def _pruned_attraction_crs(self, attraction: ReviewedAttraction) -> list[str]:
        """Return the curated candidate CRS codes kept by the hybrid prune.

        The same rule the heritage reader uses (ADR-0063): keep the curated
        candidates, drop any beyond ``max_km`` from an attraction point, keep
        the nearest and a soft twin, and leave a candidate the coordinate file
        does not locate in place, because distance cannot judge it.
        """
        candidates = self._candidate_crs(attraction.stations)
        coordinates = self.station_coordinates()
        if not candidates or not coordinates:
            return candidates
        located = [
            (crs, coordinates[crs][0], coordinates[crs][1])
            for crs in candidates
            if crs in coordinates
        ]
        missing = [crs for crs in candidates if crs not in coordinates]
        selected = select_nearest_stations(located, attraction.points)
        return [*selected, *missing]

    def _facet_attraction_crs(self, facet: DestinationFacet) -> set[str]:
        """Every CRS the facet's reviewed attractions are reached from."""
        if not facet.reviewed_attractions:
            return set()
        return {
            crs
            for attraction in facet.reviewed_attractions
            for crs in self._attraction_crs_by_facet(facet.key).get(attraction.name, ())
        }

    def _attraction_crs_by_facet(self, facet_key: str) -> dict[str, frozenset[str]]:
        """Attraction name -> kept CRS codes, computed once per facet."""
        cached = self._attraction_crs_cache.get(facet_key)
        if cached is not None:
            return cached
        cached = {}
        for attraction in REVIEWED_ATTRACTIONS_BY_FACET.get(facet_key, ()):
            cached[attraction.name] = frozenset(self._pruned_attraction_crs(attraction))
        self._attraction_crs_cache[facet_key] = cached
        return cached

    def _pruned_heritage_crs(
        self,
        site_id: int,
        stations: tuple[str, ...],
    ) -> list[str]:
        """Return curated candidate CRS codes kept by the hybrid distance prune."""
        candidates = self._candidate_crs(stations)
        points = HERITAGE_SITE_POINTS.get(site_id)
        if not candidates or not points:
            return candidates
        coordinates = self.station_coordinates()
        if not coordinates:
            return candidates
        located = [
            (crs, coordinates[crs][0], coordinates[crs][1])
            for crs in candidates
            if crs in coordinates
        ]
        missing = [crs for crs in candidates if crs not in coordinates]
        selected = select_nearest_stations(located, points)
        # Stations absent from the Knowledgebase file (some Underground and
        # heritage-railway names) stay as curated candidates: distance cannot
        # judge them, and dropping them would silence real gateways.
        return [*selected, *missing]

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
        sites: list[dict[str, object]] = []
        for site_id, name, stations in HERITAGE_PROPERTIES:
            if code not in self._pruned_heritage_crs(site_id, stations):
                continue
            sites.append(
                {
                    "id": site_id,
                    "name": name,
                    "url": f"https://whc.unesco.org/en/list/{site_id}/",
                }
            )
        return sites

    def nature_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the named nature reserves that make this station a nature match."""
        code = crs.strip().upper()
        if "nature" not in self.location_facets_by_crs.get(code, set()):
            return []
        by_name: dict[tuple[str, str], list[str]] = {}
        for site_crs, name, url in NATURE_SITE_PROOFS:
            by_name.setdefault((name, url), []).append(site_crs)
        results: list[dict[str, object]] = []
        coordinates = None
        for (name, url), site_codes in by_name.items():
            kept = site_codes
            if len(site_codes) > 1:
                if coordinates is None:
                    coordinates = self.station_coordinates()
                located = [
                    (site_crs, coordinates[site_crs][0], coordinates[site_crs][1])
                    for site_crs in site_codes
                    if site_crs in coordinates
                ]
                if len(located) >= 2:
                    # One attraction point: the centroid of the reviewed CRS set.
                    lats = [lat for _crs, lat, _lon in located]
                    lons = [lon for _crs, _lat, lon in located]
                    point = (sum(lats) / len(lats), sum(lons) / len(lons))
                    kept = select_nearest_stations(located, (point,))
                    missing = [site_crs for site_crs in site_codes if site_crs not in coordinates]
                    kept = [*kept, *missing]
            if code in kept:
                results.append({"name": name, "url": url})
        return results

    def coastal_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the named coastal day-outs for a seaside-tagged station."""
        code = crs.strip().upper()
        if "seaside" not in self.location_facets_by_crs.get(code, set()):
            return []
        return [
            {"name": name, "url": url}
            for site_crs, name, url in COASTAL_SITE_PROOFS
            if site_crs == code
        ]

    def _attraction_sites(self, crs: str, facet_key: str) -> list[dict[str, object]]:
        """Return the named day-outs that make this station a facet match.

        The same chip-implies-named-proof shape as the coastal and nature
        sublimes (ADR-0064): if the facet tagged the station, the reviewed
        attraction it was tagged for is named rather than left to a bare chip.
        """
        code = crs.strip().upper()
        if facet_key not in self.location_facets_by_crs.get(code, set()):
            return []
        by_attraction = self._attraction_crs_by_facet(facet_key)
        return [
            {"name": attraction.name, "url": attraction.url}
            for attraction in REVIEWED_ATTRACTIONS_BY_FACET.get(facet_key, ())
            if code in by_attraction.get(attraction.name, ())
        ]

    def rspb_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the RSPB reserves that make this station an RSPB match."""
        return self._attraction_sites(crs, "rspb")

    def national_trust_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the National Trust properties this station is a proof for."""
        return self._attraction_sites(crs, "national_trust")

    def national_park_sites(self, crs: str) -> list[dict[str, object]]:
        """Return the National Park / Landscape gateways this station serves."""
        return self._attraction_sites(crs, "national_park")

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

    def reviewed_railcard_families(self) -> list[RailcardFamily]:
        """The published railcards, as products, in the order the page lists them.

        Only products whose primary code the feed carries are published. A
        product whose primary code is absent but whose aliases are present is
        still published, through the alias, because refusing a card the reader
        holds because the feed dropped one of its spellings would be a page
        answering the wrong question.

        The adult bounds are the union across every code the feed carries for
        the product: the feed gives the Senior Railcard 1-1 under SRN and 1-8
        under RSN, and a reader with the replacement is still one traveller. A
        bound of zero is read as unstated rather than as a bound, so the 16-25
        Railcard is one adult rather than none.

        Ordered by label, so adding a product to the middle of the reviewed set
        cannot silently reshuffle the menu.
        """
        families: list[RailcardFamily] = []
        absent: list[str] = []
        for primary, entry in REVIEWED_PUBLIC_RAILCARDS.items():
            wanted = (primary,) + tuple(entry.get("codes") or ())
            present = tuple(code for code in wanted if code in self.railcards)
            missing = [code for code in wanted if code not in self.railcards]
            if not present:
                absent.extend(missing)
                continue
            # An alias standing in for an absent primary is promoted, so the
            # card is offered under the code the feed actually has.
            lead = present[0]
            low, high = _adult_bounds(present, self.railcards)
            families.append(
                RailcardFamily(
                    key=lead,
                    label=str(entry["label"]),
                    codes=present,
                    min_adults=low,
                    max_adults=high,
                )
            )
        if absent and not self.report.reviewed_railcard_codes_absent:
            self.report.reviewed_railcard_codes_absent = sorted(absent)
        return sorted(families, key=lambda family: family.label)

    def railcard_label(self, code: str) -> str:
        """The label a reviewed railcard is shown by, or an empty string."""
        return REVIEWED_PUBLIC_RAILCARDS.get(code, {}).get("label", "")

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

    def is_advance_fare(self, ticket_name: object, restriction_code: object) -> bool:
        """Whether a fare row is valid on one named date and train only.

        A ticket called ADVANCE is train-specific whatever code it carries,
        and a code the ``.RST`` file describes as "valid on date&train shown
        only" is train-specific whatever the ticket is called. The second
        test reads the restriction file rather than naming one code: this
        build recognised AS alone, so the 51 other codes the feed describes
        the same way -- GA among them, on every LNER promotion -- reached
        the page as an ordinary walk-up single (audit A9).
        """
        code = str(restriction_code or "").strip().upper()
        return (
            is_advance_ticket(ticket_name)
            or code in ADVANCE_RESTRICTION_CODES
            or self.restrictions.binds_to_date_and_train(code)
        )

    def minimum_fare(
        self, railcard_code: str, ticket_code: str, day: date | None = None
    ) -> int | None:
        """The minimum fare in force for this ticket on ``day``, if any.

        A blank start or end date is an open end, so a record that names no
        window applies to every day. When a key holds several windows only the
        ones covering the query day are considered; if a feed ever lists two
        that both cover it, the later start wins, so the record nearest the
        query is the one applied rather than whichever the file wrote last.
        """
        query_day = day or date.today()
        active = [
            record
            for record in self.minimum_fares.get((railcard_code, ticket_code), ())
            if record.covers(query_day)
        ]
        if not active:
            return None
        return max(active, key=lambda record: record.start_date or date.min).pence

    def railcard_price(
        self,
        railcard_code: str,
        ticket_code: str,
        standard_pence: int,
        *,
        day: date | None = None,
    ) -> int:
        # National Rail's published third-off result is rounded down to the
        # nearest 5p for each ticket, not up. Rounding up costs 5p per traveller
        # whenever the exact discount falls between two 5p amounts.
        discounted = _round_down_to(standard_pence * RAILCARD_DISCOUNT, ROUNDING_STEP_PENCE)
        minimum = self.minimum_fare(railcard_code, ticket_code, day)
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
        day: date | None = None,
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
        return self.railcard_price(railcard_code, ticket_code, standard_pence, day=day)

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

    @staticmethod
    def _displayable_single_rejection(
        restrictions,
        include_conditional: bool = False,
        include_advance: bool = False,
    ) -> Callable[[Fare, TicketType], str | None]:
        """The reviewed rule for a single a page may quote, or why not.

        One method so the page row and the priced chooser cannot drift apart.
        The reasons are distinct because the coverage report counts them, and a
        count that files a child's fare under "not a standard single" cannot
        answer what happened to a destination.

        A fare bound to one date and train is rejected under its own reason,
        because it is a different failure from a fare that is merely
        conditional: the fare exists and is sold, but not at that price to
        anyone who has not chosen a train. It is a staticmethod that needs the
        restriction index for two different questions, and the advance test
        needs the fare's own ticket name and restriction code, so the callable
        is closed over them here rather than re-derived per fare.
        """
        advance_codes = ADVANCE_RESTRICTION_CODES

        def reject(fare: Fare, ticket: TicketType) -> str | None:
            if fare.ticket_code in CONDITIONAL_TICKET_CODES and not include_conditional:
                return CONDITIONAL_REASON
            if restrictions.requires_another_ticket(fare.restriction_code):
                return CONDITIONAL_REASON
            if not include_advance and (
                ticket.is_advance
                or fare.restriction_code.strip().upper() in advance_codes
                or restrictions.binds_to_date_and_train(fare.restriction_code)
            ):
                return ADVANCE_REASON
            if not ticket.is_standard_single:
                return "ticket_is_not_a_standard_single"
            name = ticket.name.upper()
            if fare.ticket_code in PLACEHOLDER_TICKET_CODES or "ITX" in name:
                return "ticket_is_a_catalogue_placeholder"
            if is_not_for_public_sale(name):
                return "ticket_is_not_for_public_sale"
            return None

        return reject

    @staticmethod
    def _displayable_return_rejection(
        restrictions,
        include_conditional: bool = False,
    ) -> Callable[[Fare, TicketType], str | None]:
        """The same rule for a return, which the feed prices the same way.

        A group return is quoted for the party, so it cannot be a reader's
        cheapest return either. The catalogue placeholder test stays, and its
        own reason, because a placeholder is a different mistake from a fare
        that is real and simply not the reader's.

        The not-for-public-sale test the single selector has always run runs
        here too. It was missing, and a fare the catalogue calls NOT FOR
        TRAVEL reached a page through the gap.
        """

        def reject(fare: Fare, ticket: TicketType) -> str | None:
            if fare.ticket_code in CONDITIONAL_TICKET_CODES and not include_conditional:
                return CONDITIONAL_REASON
            if restrictions.requires_another_ticket(fare.restriction_code):
                return CONDITIONAL_REASON
            if not ticket.is_standard_return:
                return "ticket_is_not_a_standard_return"
            name = ticket.name.upper()
            if fare.ticket_code in PLACEHOLDER_TICKET_CODES or "ITX" in name:
                return "ticket_is_a_catalogue_placeholder"
            if is_not_for_public_sale(name):
                return "ticket_is_not_for_public_sale"
            return None

        return reject

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
        include_conditional: bool = False,
    ) -> list[Reachable]:
        """Rows suitable for the reader-facing page, including restrictions.

        The feed contains ITX placeholder fares such as ``EIS`` at the £0.05
        minimum with restriction ``GA``. They are not usable public fares, so
        they must not win the broad query's cheapest-fare comparison. Other
        restricted standard returns remain visible and carry their restriction
        code to the page.

        ``include_conditional`` puts the child, group and event fares back.
        Nothing on a page sets it. It exists so the coverage report can ask
        what the rule costs, by asking this selector the same question both
        ways and counting the destinations that differ.
        """
        # The test runs inside the shared loop rather than on the rows the broad
        # query returns. Filtering afterwards would let a conditional fare win
        # the slot and then take the destination with it, leaving the page
        # without the adult fare the feed also holds for that pair.
        return self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=self._displayable_return_rejection(
                self.restrictions, include_conditional
            ),
            day=day,
        )

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
        include_conditional: bool = False,
        include_advance: bool = False,
    ) -> list[Reachable]:
        """Displayable standard-class singles, excluding catalogue placeholders.

        A train-restricted fare is out of the result by default. An advance
        single is attached to one named train, so its price is not the price of
        the journey: quoting it as the cheapest way to reach a place told a
        reader Grantham to Skegness cost £6.60 when no train on the day sold
        that fare, and the page had no way to name the train that did. The
        figure was arithmetically correct and practically untrue, which is worse
        than being loose, and a page whose whole claim is a price cannot carry
        a number it would not honour at a seller.

        ``include_advance`` puts them back, for the coverage report's
        measurement of what the rule costs and nothing else.

        ``include_conditional`` puts the child, group and event fares back, for
        the coverage report's measurement and nothing else.
        """
        rows = self._destinations_within(
            origin_crs,
            budget_pence,
            adults=adults,
            railcard=railcard,
            party_budget=party_budget,
            tally=tally,
            selector=self._displayable_single_rejection(
                self.restrictions, include_conditional, include_advance
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

    def two_part_fares(
        self,
        origin_crs: str,
        splits: dict[str, str | Sequence[str]],
        rows_from: Callable[[str], list[Reachable]],
    ) -> list[TwoPartFare]:
        """Places with no fare of their own, priced as two fares (ADR-0061).

        ``splits`` maps each destination to one pricing-split CRS or a sequence
        of candidates on that destination's journey (calling points and, when
        the journey changes trains, the change station). ``rows_from`` is the
        page's own selector for one ticket mode, asked of any station. For each
        candidate the first ticket is what ``rows_from(origin)`` prices for the
        split and the second is what ``rows_from(split)`` prices for the
        destination, so each is the fare a page for that pair would quote. When
        several candidates both sell, the cheapest valid sum wins, then the
        split CRS. A destination the origin already prices on one ticket keeps
        that row, and a pair with either ticket missing is no row at all: the
        price is the journey's own or nothing.
        """
        origin = origin_crs.strip().upper()
        asked: dict[str, dict[str, Reachable]] = {}

        def priced_from(crs: str) -> dict[str, Reachable]:
            if crs not in asked:
                asked[crs] = (
                    {row.crs: row for row in rows_from(crs)}
                    if crs in self.locations_by_crs
                    else {}
                )
            return asked[crs]

        def candidates_of(value: str | Sequence[str]) -> tuple[str, ...]:
            if isinstance(value, str):
                return (value.strip().upper(),)
            return tuple(crs.strip().upper() for crs in value)

        direct = priced_from(origin)
        found: list[TwoPartFare] = []
        for destination, raw in sorted(splits.items()):
            destination = destination.strip().upper()
            if destination in direct or destination == origin:
                continue
            best: TwoPartFare | None = None
            for change in candidates_of(raw):
                if change in {origin, destination}:
                    continue
                first = direct.get(change)
                if first is None:
                    continue
                second = priced_from(change).get(destination)
                if second is None:
                    continue
                candidate = TwoPartFare(
                    crs=destination,
                    station=second.station,
                    change_crs=change,
                    change_station=first.station,
                    first=first,
                    second=second,
                )
                if best is None or (candidate.best_pence, candidate.change_crs) < (
                    best.best_pence,
                    best.change_crs,
                ):
                    best = candidate
            if best is not None:
                found.append(best)
        return sorted(found, key=lambda fare: (fare.best_pence, fare.crs))

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
                # A zone boundary or a coach stop is where the feed records a
                # fare change, not a place. Dropping it here rather than in
                # each caller is what makes the chooser, the page rows, the
                # write set and the coverage report agree: there is one rule
                # and one place it is applied (audit A6).
                if is_pseudo_station(destination.crs):
                    _tally(tally, "destination_is_a_fare_construction_point")
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
                            day=query_day,
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
