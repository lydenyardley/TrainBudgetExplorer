"""The payload: every destination a page lists, and its own wire format.

``build_payload`` is the product. It asks the fares database and the timetable for
one origin's answer, and ``encode_payload`` packs that answer into the embedded JSON
the browser filters -- a column layout with shared tables for the strings that
repeat on every row, which is what keeps a 334-destination page inside its byte
budget.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple

from atoc_fare_declarations import Location, RailcardFamily, Reachable
from atoc_fares import (
    EVERYTHING_PENCE,
    FaresDb,
    PLACEHOLDER_TICKET_CODES,
    TwoPartFare,
    is_pseudo_station,
)
from atoc_knowledgebase import ABSENT, Knowledgebase, RestrictionCheck, check_restrictions
from atoc_timetable import SliceIndex, TimetableDb
# The asset names are read through the module: they are digests of the bytes
# the route fetches, so the payload must name what this release writes, and a
# test that changes the assets changes them in one place (ADR-0071).
import build_assets
from build_assets import (
    LINK_NOTE_FALLBACK,
    station_slugs_for,
    with_base,
)
from build_provenance import STALE_AFTER_DAYS, cif_date_to_iso, restriction_codes_shown
from build_release import DEFAULT_NOTE, DEFAULT_PRICE_SOURCE, service_claim
from build_state import read_service_week, source_fingerprint, write_service_week
from destination_coverage import UnsourcedReport, unnameable_from_tally
from retailer import DEFAULT_PROVIDER, TicketLink, ticket_link


DEPARTURE_LIMIT = 5


# How far past the build's own day a row with no service is asked before it
# is called a station the week does not reach. A week, because that is the span
# a reader plans over and the span that makes the answer a fact about the
# station rather than about a Sunday.
SERVICE_WEEK_HORIZON = 7


# Why a row carries no journey, as three keys rather than a sentence written at
# three places in destination_row and again in the sweep below it. The build
# used to word each absence where it found it, so the payload held prose that
# the page then reworded for the cell it printed in, and two of the six
# sentences the build could write named no day at all -- "no timetable in this
# build" and "no service in this timetable" -- beside a station the network
# runs, which reads as a claim about the station rather than about the date the
# build happened to pick.
#
# The keys travel and the wording is composed in one place on the page, from
# the key, the day the build asked about and the next day the row does run. A
# row that is absent therefore cannot be worded without its day, because there
# is nowhere else for the wording to be written.
JOURNEY_FOUND = "found"


JOURNEY_NO_TIMETABLE = "no_timetable"


JOURNEY_NO_SERVICE = "no_service"


# Why a fare the feed holds did not become a price, in the words an empty page
# needs. Cheaper fares already held and fares to the origin itself are normal
# traffic, not reasons a destination is missing, so they are never listed.
UNPRICED_REASONS = {
    "ticket_is_not_a_standard_return": "fares that are not standard returns",
    "ticket_is_not_one_a_reader_can_buy": (
        "fares a reader cannot buy at the price they are quoted at, "
        "such as a child, a family, a group, a staff or a concession fare"
    ),
    "ticket_is_not_for_public_sale": (
        "fares the catalogue marks as not for public sale"
    ),
    "ticket_is_not_for_public_sale": (
        "fares the catalogue marks as not for public sale"
    ),
    "flow_not_yet_valid": "flows not yet valid",
    "flow_expired": "flows past their last valid day",
    "flow_with_no_fare": "flows carrying no fare",
    "fare_with_no_ticket_type": "fares with no ticket type",
    "destination_has_no_location_record": "flows to destinations with no location record",
    "destination_has_no_station_code": "flows to destinations with no station code",
    "destination_is_a_fare_construction_point": "flows priced only to zone boundaries or coach stops",
    "fare_above_the_budget": "fares above the price this page can show",
}


def explain_unpriced(
    raw_count: int,
    excluded_itx_count: int,
    excluded_codes: list[str],
    tally: dict[str, int],
) -> str:
    """Why an origin priced nothing, for the payload's unpricedNote.

    Called only when every fare set on the page is empty. The count answers
    "how much does the feed even hold from here" and the reasons answer "so
    why is none of it on this page". The origin's name is already in the
    sentence this appends to, so it is not repeated here.

    The placeholder sentence claims every one of those destinations is
    withheld, so it is only said when every excluded row really is: an origin
    priced only into a zone boundary has nothing to withhold and would be told
    it had an ITX problem it does not have (audit A6).
    """
    if raw_count and excluded_itx_count == raw_count:
        codes = ", ".join(excluded_codes)
        if raw_count == 1:
            return (
                "The feed reaches 1 standard-return destination, and its cheapest fare is an "
                f"ITX placeholder ({codes}), which this page does not publish."
            )
        return (
            f"The feed reaches {raw_count} standard-return destinations, and the cheapest fare "
            f"to every one of them is an ITX placeholder ({codes}), which this page does not publish."
        )
    reasons = [
        (count, UNPRICED_REASONS[key])
        for key, count in sorted(tally.items(), key=lambda item: (-item[1], item[0]))
        if key in UNPRICED_REASONS
    ]
    if not reasons:
        return "The feed holds no fare from this origin at all."
    parts = "; ".join(f"{count} {label}" for count, label in reasons[:3])
    return f"The feed holds flows from this origin, but none prices a publishable fare: {parts}."


class PageContext(NamedTuple):
    """Everything one page's rows are built against, fixed for the whole page.

    ``origin`` and ``timetable`` are the resolved ones the page builds against:
    the station the page is about and the slice of the timetable it can use,
    after the fallback to the origin's own slice and the focus of that slice are
    done. ``day`` is the day the page reports, which is the day every fare and
    every journey search on it is asked about.
    """

    fares: FaresDb
    origin: Location
    timetable: TimetableDb | None
    day: date | None
    max_changes: int
    departure_limit: int
    provider: str
    adults: int
    network: str | None
    advertiser_id: str | None
    publisher_id: str
    mode: str
    railcard_families: list[RailcardFamily]


@dataclass
class RulePool:
    """The railcard rule records a page shares, keyed once each (audit B3).

    The full rule record repeats on nearly every row: on the heaviest real page
    one record served all 1,678 rows and the block was 388KB (measured). Rows
    keep a key into one payload map; only the drawer reads the record, and the
    table reads the price straight off the row.

    The pool owns the numbering, so an id is handed out the first time a record
    is asked for and no builder can renumber a page by being called in a
    different order.
    """

    rule_ids: dict[str, str] = field(default_factory=dict)
    railcard_rules: dict[str, dict] = field(default_factory=dict)
    detail_cache: dict[tuple[object, ...], dict] = field(default_factory=dict)

    def share(self, rule: dict | None) -> str | None:
        if rule is None:
            return None
        marker = json.dumps(rule, sort_keys=True)
        rule_id = self.rule_ids.get(marker)
        if rule_id is None:
            rule_id = str(len(self.railcard_rules))
            self.rule_ids[marker] = rule_id
            self.railcard_rules[rule_id] = rule
        return rule_id

    def rule_for(self, rule_id: str | None) -> dict | None:
        """The record a row's key names, for a builder reading back its own rule."""
        return self.railcard_rules.get(rule_id) if rule_id else None


def two_part_query(
    query: Callable[..., list[Reachable]], day: date | None
) -> Callable[[str], list[Reachable]]:
    """One ticket mode's selector, asked of any station's own page.

    ADR-0061: a place the feed prices in two parts is one row, and each ticket
    of it comes through the same selector as the list it joins, so the reader is
    quoted the journey they are shown rather than the cheapest fare on each leg
    found separately. Priced on the build's day, like every other row: the day
    control changes the times and neither price (ADR-0060).
    """
    return functools.partial(query, budget_pence=EVERYTHING_PENCE, adults=1, day=day)


def two_part_candidates(
    timetable,
    origin_crs: str,
    day: date | None,
    max_changes: int,
    *,
    reached: dict | None = None,
) -> dict[str, list[str]]:
    """Where each journey from one origin could be split, keyed by destination.

    ADR-0061: a place the feed prices in two parts is one row, and the split is
    a calling point on the journey the page already shows for it -- plus the
    station the reader leaves when the journey changes trains. The walk is one
    place because two callers need it: the page that writes the row, and the
    count that says how many places the page carries (``_priced_destinations``).
    While they were two copies of the same loop, the count kept the fifty places
    the fare selectors price and missed the two hundred and eighty-four the page
    also writes, so the chooser named a station's size at a fraction of it.

    The database is focused on the origin first, because a journey search
    rebuilds its index whenever the focus or the day changes; a database already
    cut for this origin is returned as it is, so a page's own build pays nothing
    for the second call. A destination the origin prices on one ticket is still
    a candidate here -- its two-part sum can be the cheaper of the two, and the
    page keeps whichever is cheaper -- and a destination no journey reaches is
    no candidate at all.
    """
    if timetable is None:
        return {}
    timetable = timetable.focused(origin_crs)
    if reached is None:
        reached = timetable.journeys_from(origin_crs, max_changes=max_changes, day=day)
    split_at: dict[str, list[str]] = {}
    for crs, journey in reached.items():
        if journey.changes > max_changes or is_pseudo_station(crs):
            continue
        candidates: list[str] = []
        for leg in journey.legs:
            for mid in timetable.intermediate_crs(
                leg.train_uid, leg.origin_crs, leg.destination_crs, day=day
            ):
                if mid not in candidates and mid not in {origin_crs, crs}:
                    candidates.append(mid)
            if leg.destination_crs != crs and leg.destination_crs not in candidates:
                candidates.append(leg.destination_crs)
        if candidates:
            split_at[crs] = candidates
    return split_at


def railcard_details(context: PageContext, pool: RulePool, one: Reachable) -> dict:
    """Each reviewed railcard's exact DTD decision for one destination.

    The reader holds one card at a time, so the payload carries a row per
    card rather than one card's answer repeated six times over the page.
    Each entry is the discounted price and a key into the shared rule map;
    the drawer resolves the rest, because the prose would otherwise be six
    sentences a row and the measured cost of one is already 433 bytes.
    """
    return {
        family.key: railcard_detail_for(context, pool, family, one)
        for family in context.railcard_families
    }


def railcard_pair_details(
    context: PageContext, pool: RulePool, two_part: TwoPartFare
) -> dict:
    """Each reviewed railcard's decision for a two-ticket row (ADR-0061).

    A two-ticket row is two published fares, so a card is decided on each
    ticket and the row's card price is the two card prices added -- the same
    sum the standard price is. A card the feed bans on either ticket cannot
    price the pair as a pair, so it is not offered; the row says so rather
    than quoting half a journey.
    """
    return {
        family.key: railcard_pair_detail_for(context, pool, family, two_part)
        for family in context.railcard_families
    }


def railcard_pair_detail_for(
    context: PageContext,
    pool: RulePool,
    family: RailcardFamily,
    two_part: TwoPartFare,
) -> dict:
    """One card's decision for a two-ticket row: both tickets, added together."""
    origin = context.origin
    legs = (
        railcard_detail_for(
            context, pool, family, two_part.first, leg_origin_crs=origin.crs
        ),
        railcard_detail_for(
            context, pool, family, two_part.second, leg_origin_crs=two_part.change_crs
        ),
    )
    blocking = next((leg for leg in legs if leg["pricePence"] is None), None)
    if blocking is not None:
        price = None
        minimum = None
        state = "blocked"
        total_ban = True
    else:
        price = sum(leg["pricePence"] for leg in legs)
        minimums = [leg["minimumFarePence"] for leg in legs]
        minimum = None if any(value is None for value in minimums) else sum(minimums)
        state = (
            "undiscounted"
            if all(leg["state"] == "undiscounted" for leg in legs)
            else "eligible"
        )
        total_ban = False
    restrictions = [
        (pool.rule_for(leg["rule"]) or {}).get("restrictionCode") for leg in legs
    ]
    restrictions = [code for code in restrictions if code and code != "none"]
    texts = [(pool.rule_for(leg["rule"]) or {}).get("text") for leg in legs]
    # Only what the page reads (the text, the ban and the condition) and
    # nothing that names this row. The tickets, routes and endpoints are on
    # the row's own tickets already; naming them here made every pair a record
    # of its own, so the pool shared nothing: 7,290 records and 3.2 MB on the
    # Crewe page, and a 2,444 MB release against an 800 MB budget (run
    # 38353105980). Without them a page holds one record per distinct rule.
    rule = {
        "sequence": "two",
        "status": "current",
        "restrictionCode": " + ".join(restrictions) or "none",
        "totalBan": total_ban,
        "text": (
            f"Two tickets, both checked for {family.label}: "
            + " ".join(text for text in texts if text)
        ),
    }
    return {
        "state": state,
        "pricePence": price,
        "minimumFarePence": minimum,
        "rule": pool.share(rule),
    }


def railcard_detail_for(
    context: PageContext,
    pool: RulePool,
    family: RailcardFamily,
    one: Reachable,
    *,
    leg_origin_crs: str | None = None,
) -> dict:
    """One card's decision for one fare: its price and its rule key.

    ``leg_origin_crs`` names where the fare starts when that is not the page's
    own station: the second leg of a two-ticket row (ADR-0061) begins at the
    pricing split, and an RR rule matches the endpoints of the journey the
    fare is sold for.
    """
    fares = context.fares
    origin = context.origin
    railcard_code = family.key
    start_crs = leg_origin_crs or origin.crs
    cache_key = (
        railcard_code,
        start_crs,
        one.crs,
        one.origin_nlc,
        one.destination_nlc,
        one.ticket_code,
        one.route_code,
        one.standard_pence,
        context.day,
    )
    cached = pool.detail_cache.get(cache_key)
    if cached is not None:
        return cached
    rules = fares.railcard_rules(
        railcard_code,
        ticket_code=one.ticket_code,
        route_code=one.route_code,
        origin_crs=leg_origin_crs or origin.crs,
        destination_crs=one.crs,
        origin_nlc=one.origin_nlc,
        destination_nlc=one.destination_nlc,
    )
    ban = next((rule for rule in rules if rule.total_ban), None)
    condition = next((rule for rule in rules if rule.restriction_code), None)
    shown_rule = ban or condition
    minimum = fares.minimum_fare(railcard_code, one.ticket_code, context.day)
    rule = None
    if shown_rule is not None:
        rule = {
            "sequence": shown_rule.sequence_no,
            "status": (
                "current"
                if shown_rule.current_or_future.upper() == "C"
                else shown_rule.current_or_future
            ),
            "ticketCode": shown_rule.ticket_code or "any",
            "routeCode": shown_rule.route_code or "any",
            "location": shown_rule.location or "any",
            "restrictionCode": shown_rule.restriction_code or "none",
            "totalBan": shown_rule.total_ban,
        }
    if ban is not None:
        price = None
        state = "blocked"
    else:
        price = fares.railcard_price(
            railcard_code, one.ticket_code, one.standard_pence, day=context.day
        )
        # The feed's status-discount table gives this card nothing on this
        # ticket's category, which the page says rather than blaming a minimum.
        state = (
            "eligible"
            if fares.railcard_discounts_ticket(railcard_code, one.ticket_code, context.day)
            else "undiscounted"
        )
    if rule is not None:
        rule["text"] = (
            f"Current RR {rule['sequence']} for {family.label}: "
            f"ticket {rule['ticketCode']}, route {rule['routeCode']}, "
            f"location {rule['location']}; total ban "
            f"{'yes' if rule['totalBan'] else 'no'}; restriction "
            f"{rule['restrictionCode']}."
        )
    detail = {
        "state": state,
        "pricePence": price,
        "minimumFarePence": minimum,
        "rule": pool.share(
            rule
            or {
                "sequence": "none",
                "status": "current",
                "ticketCode": one.ticket_code,
                "routeCode": one.route_code,
                "location": f"{origin.crs}/{one.crs}",
                "restrictionCode": "none",
                "totalBan": False,
                "text": (
                    f"No matching current RR rule for {family.label}: ticket "
                    f"{one.ticket_code}, route {one.route_code}, endpoints "
                    f"{origin.crs}/{one.crs}."
                ),
            }
        ),
    }
    pool.detail_cache[cache_key] = detail
    return detail


def describe_restriction(context: PageContext, code: str) -> str:
    headers = context.fares.restrictions.headers
    if code in headers:
        return headers[code].description
    if code:
        # D3 of the 17 October 2026 critique: the panel printed this sentence
        # after a lead line that said the same thing, so an undescribed
        # condition was explained twice. One sentence, carrying the code, is
        # the whole explanation, and the page prints it once.
        return (
            "Restriction "
            + code
            + " is not described in this feed, so check the seller's terms."
        )
    return ""


def restriction_has_wording(context: PageContext, code: str) -> bool:
    """Whether the feed holds any wording at all for a restriction code.

    A record with the code and an empty description, outward text and return text
    describes nothing, and the row's lead sentence must not send a reader down
    for a condition the page cannot show (audit item 25, 14 October 2026). What
    counts as holding a description is the rule the reference note already uses:
    the description, or either restriction text (atoc_knowledgebase).
    """
    header = context.fares.restrictions.headers.get(code) if code else None
    if header is None:
        return False
    return bool(
        header.description.strip()
        or header.outward_text.strip()
        or header.return_text.strip()
    )


def destination_row(
    context: PageContext,
    pool: RulePool,
    crs: str,
    one: Reachable | TwoPartFare,
    *,
    quality: str,
    journey_db: TimetableDb | None,
    departures_seen: dict[tuple[int, str], list[dict]] | None = None,
    journeys_by_db: dict[int, dict] | None = None,
) -> tuple[dict, TicketLink]:
    # The journey belongs to the origin and the destination, not to the
    # ticket type, so it is read once per destination from the first
    # timetable this build holds that has one: the row's own, then the
    # page's. It used to be read from the row's own timetable only, so a
    # destination three fare lists reach carried three different answers,
    # and the cheapest list kept the one belonging to the fare that won.
    # Where the cheapest fare is an advance single, that is the list built
    # without a timetable, so the row said no service about a destination
    # the same payload prices a 45-minute direct journey to.
    fares = context.fares
    origin = context.origin
    max_changes = context.max_changes
    departure_limit = context.departure_limit
    day = context.day
    searched = (
        (journey_db,) if journey_db is context.timetable else (journey_db, context.timetable)
    )
    journey = None
    # Which database this row's week belongs to. The first one consulted is
    # the default, and a database that answered keeps it: a build with
    # --with-single-timetable holds a second timetable over the same feed
    # with a different focus, so the week for a row is the week of the
    # database that read that row, not of the page's first one.
    journey_source = None
    for db in searched:
        if db is None:
            continue
        if journey_source is None:
            journey_source = db
        if journeys_by_db is not None and id(db) in journeys_by_db:
            found = journeys_by_db[id(db)].get(crs)
        else:
            found = db.best_journey(origin.crs, crs, max_changes=max_changes, day=day)
        if found:
            journey, journey_source = found, db
            break
    # The departures belong to the journey rather than to the fare record that
    # prices it: every fare set that prices the same journey from the same
    # timetable names the same trains. A single-mode row carried none at all
    # when the build loaded no separate outbound-single timetable, so the
    # cheapest row on the page opened a panel holding a duration and no times,
    # beside a return to the same place that opened onto four (S1 of the 19
    # October 2026 critique). The narrower timetable still wins where the build
    # has one, which is why the row's own list is asked first and the page's
    # timetable is only the fallback.
    #
    # Asked once per journey per page: departures() is a second one-change
    # search, and the three fare lists are walked one after another over the
    # same destinations, so the page that prices a place three times pays for
    # its times once.
    journey_timetable = journey_db or context.timetable
    if journey_timetable is None:
        options: list[dict] = []
    else:
        key = (id(journey_timetable), crs)
        shared = departures_seen.get(key) if departures_seen is not None else None
        if shared is None:
            shared = [
                {
                    "depart": option.departure,
                    "arrive": option.arrival,
                    "changes": option.changes,
                }
                for option in journey_timetable.departures(
                    origin.crs, crs, max_changes=max_changes, day=day, limit=departure_limit
                )
            ]
            if departures_seen is not None:
                departures_seen[key] = shared
        options = shared
    # Q2 (ADR-0045): a journey with a change is where a split ticket
    # can undercut the through fare, and the station it would change at is
    # one fact the build already holds. The page names it and claims no
    # price: the feed prices flows, not itineraries, so which two tickets
    # are cheaper is not in this data.
    change_stations = [
        {
            "crs": leg.destination_crs,
            "name": (
                fares.locations_by_crs[leg.destination_crs].name
                if leg.destination_crs in fares.locations_by_crs
                else leg.destination_crs
            ),
        }
        for leg in (journey.legs[:-1] if journey else ())
    ]
    link = ticket_link(
        origin.crs,
        crs,
        provider=context.provider,
        when=day,
        adults=context.adults,
        network=context.network,
        advertiser_id=context.advertiser_id,
        publisher_id=context.publisher_id,
        mode=context.mode,
    )
    # ADR-0061: a two-part row is two tickets, and every fact the row
    # states about its fare is a fact about both of them.
    two_part = one if isinstance(one, TwoPartFare) else None
    parts = two_part.legs if two_part else (one,)
    restriction_code = next(
        (part.restriction_code for part in parts if part.restriction_code), ""
    )
    row = {
        "crs": crs,
        "name": one.station,
        "adultPence": one.best_pence,
        "partyPence": one.best_pence * 2,
        # One entry per reviewed railcard the feed carries. The reader holds
        # one at a time, so the page picks the key rather than offering six
        # prices per row in the table. A two-ticket row (ADR-0061) is a card
        # decision per ticket, and the row's card price is the two card
        # prices added together, so the card still prices the row.
        "railcards": (
            railcard_pair_details(context, pool, two_part)
            if two_part
            else railcard_details(context, pool, one)
        ),
        "destinationType": fares.destination_type(crs),
        "destinationTypes": fares.destination_types(crs),
        "heritageSites": fares.heritage_sites(crs),
        "natureSites": fares.nature_sites(crs),
        "coastalSites": fares.coastal_sites(crs),
        # ADR-0062: RSPB, National Trust and National Park / Landscape
        # gateways, each with its own reviewed list and named proof.
        "rspbSites": fares.rspb_sites(crs),
        "nationalTrustSites": fares.national_trust_sites(crs),
        "nationalParkSites": fares.national_park_sites(crs),
        "ticket": " + ".join(part.ticket_code for part in parts),
        "isAdvance": any(
            fares.is_advance_fare(part.ticket_name, part.restriction_code)
            for part in parts
        ),
        "quality": quality,
        "offPeak": any(part.off_peak for part in parts),
        "restrictionCode": restriction_code,
        "routeCode": " + ".join(part.route_code for part in parts),
        # C08: a code says which condition, not what it permits. The
        # description is the feed's own wording for the code, and the
        # fallback says plainly that the feed has none, so a reader is
        # never told to "check the seller" as if that were a decoded rule.
        "restrictionDescription": describe_restriction(context, restriction_code),
        # Whether the feed holds any wording for this code at all. The row's
        # lead sentence says where the condition is and must not promise one the
        # page cannot show, and the fallback description is a sentence rather
        # than a fact to branch on (audit item 25, 14 October 2026).
        "restrictionDescribed": restriction_has_wording(context, restriction_code),
        "minutes": journey.duration if journey else None,
        "changes": journey.changes if journey else None,
        # One entry per leg boundary, so a one-change journey carries the
        # one interchange and a longer one carries every change station.
        "changeStations": change_stations,
        # S23: why there is no time, so a reader can tell "the feed has no
        # service" from "this build priced fares only" instead of reading
        # a bare dash for both. A key rather than a sentence: the page words
        # it, in one place, from this and the day.
        "journeyState": (
            JOURNEY_FOUND
            if journey
            # The build has no timetable to read, rather than this row's
            # list not having one: the search above is what decides it, and
            # it is the same search that decided `journey`.
            else JOURNEY_NO_TIMETABLE
            if all(db is None for db in searched)
            else JOURNEY_NO_SERVICE
        ),
        "legs": [leg.train_uid for leg in journey.legs] if journey else [],
        # Which database read this row, for the week walk below. Carried on
        # the row and popped off it again before the payload is encoded, so
        # the build can carry it and the page never sees it.
        "_journeySource": journey_source,
        "link": {"url": link.url, "label": link.label, "rel": link.rel},
        "departures": options,
    }
    if two_part:
        # Both tickets, each with its own price and its own restriction,
        # because two tickets are two purchases with two sets of conditions
        # and a row naming one of them would be silent about the other.
        ends = (
            (origin.crs, origin.name, two_part.change_crs, two_part.change_station),
            (two_part.change_crs, two_part.change_station, crs, one.station),
        )
        row["tickets"] = [
            {
                "ticket": part.ticket_code,
                "fromCrs": start_crs,
                "fromName": start_name,
                "toCrs": end_crs,
                "toName": end_name,
                "adultPence": part.best_pence,
                "restrictionCode": part.restriction_code,
                "restrictionDescription": describe_restriction(context, part.restriction_code),
                "routeCode": part.route_code,
            }
            for part, (start_crs, start_name, end_crs, end_name) in zip(parts, ends)
        ]
    # The link comes back with the row: the payload's two disclosure facts are
    # every row's link folded into one, and a row alone cannot say them, so a
    # caller that took only the row would have to build the link again.
    return row, link


def unreachable_places(rows: list[dict]) -> set[str]:
    """The places among ``rows`` that no day the page carries reaches.

    A row is reached when the build's own day found a journey, or when the
    week walk found a day it runs -- ``nextService`` is only ever set from that
    walk, so the two facts are the whole answer. Asked only by a build that
    walked the week: a build with no timetable has no answer to give, and says
    so with ``no_timetable`` rather than with an absence.

    A place is the unit rather than a row, because the three fare lists price
    the same place three ways: dropping one list's row and keeping another's
    would leave a page that says no journey reaches a place beside a price for
    it.
    """
    return {
        row["crs"]
        for row in rows
        if row["journeyState"] != JOURNEY_FOUND and not row.get("nextService")
    }


def day_answer(row: dict, offset: int, service_week: list[list[dict]]) -> list[int] | None:
    # What this row's station is on the day at this offset, or nothing.
    # The row names its own database by index, so a row read by the second
    # timetable is looked up in the second timetable's week.
    index = row.get("serviceWeekIndex")
    if index is None or index < 0 or not service_week:
        return None
    return service_week[index][offset].get(row["crs"])


def build_payload(
    fares: FaresDb,
    timetable: TimetableDb | None,
    origin_crs: str,
    *,
    single_timetable: TimetableDb | None = None,
    max_changes: int = 1,
    day: date | None = None,
    note: str = DEFAULT_NOTE,
    attribution: str | None = None,
    price_source: str = DEFAULT_PRICE_SOURCE,
    feed_date: str | None = None,
    base_path: str = "",
    provider: str = DEFAULT_PROVIDER,
    # Fallback by default: the parameterised link is not known to land on a
    # search at either seller, and a link that tells a reader there are no trains
    # is worse than one that asks them to type four things.
    mode: str = "fallback",
    adults: int = 2,
    network: str | None = None,
    advertiser_id: str | None = None,
    publisher_id: str = "",
    departure_limit: int = DEPARTURE_LIMIT,
    built_at: str | None = None,
    published_routes: list[dict] | None = None,
    reference: "Knowledgebase | None" = None,
    reference_published: str = "",
    reference_checked: str = "",
    timetable_index: SliceIndex | None = None,
    # The identity the service-week facts are keyed by: the timetable feed's
    # content digest, or the slice index's when the build reads no feed. None
    # means the week is searched every time, which is what every caller did
    # before the facts existed.
    timetable_identity: str | None = None,
) -> dict:
    """Every publishable destination from the origin, at both party prices.

    Each destination carries the ticket links and the next few journeys. The
    journeys are options in the feed, not a booking: an unrestricted fare is
    valid on any of them, while an Advance single is valid only on a
    qualifying train, which is why no train is chosen for the reader.

    ``timetable_index`` is where this page's timetable comes from when there is
    no ``timetable``: the slice of the feed that was cut for this origin and
    written to disk. The caller checked that the slice was there before the
    build started, so a miss here is a file that vanished or will not read --
    and it raises, because a page assembled without times would say the station
    has no services.
    """
    if timetable is None and timetable_index is not None:
        timetable = timetable_index.load(origin_crs)
        if timetable is None:
            # The caller checked every page this build writes had a slice before
            # it got here, so a miss now is a file that vanished or one that will
            # not read. A page assembled without times would say the station has
            # no services, which is worse than a build that stops.
            raise OSError(
                f"{origin_crs} has no readable slice in {timetable_index.directory}"
            )
    origin = fares.locations_by_crs[origin_crs.strip().upper()]
    # Every destination is included, then the browser's price filter decides
    # which rows are within the reader's budget. The fare shown is the cheapest
    # displayable standard-class return found in the feed; ITX placeholder fares
    # are excluded, while legitimate restrictions remain visible with their code.
    # The tally survives on the payload's unpricedNote: without it the rejected
    # fares vanish before any message could count them (audit A1).
    raw_tally: dict[str, int] = {}
    raw_destinations = fares.destinations_within(
        origin.crs, EVERYTHING_PENCE, adults=1, day=day, tally=raw_tally
    )
    single = {
        row.crs: row
        for row in fares.page_destinations_within(
            origin.crs, EVERYTHING_PENCE, adults=1, day=day
        )
    }
    excluded_itx = [
        row for row in raw_destinations
        if row.ticket_code in PLACEHOLDER_TICKET_CODES
        or "ITX" in row.ticket_name.upper()
    ]
    single_ticket_rows = fares.page_single_destinations_within(
        origin.crs, EVERYTHING_PENCE, adults=1, day=day
    )
    single_tickets = {row.crs: row for row in single_ticket_rows}
    anytime_ticket_rows = fares.publishable_destinations_within(
        origin.crs, EVERYTHING_PENCE, adults=1, day=day
    )
    anytime_tickets = {row.crs: row for row in anytime_ticket_rows}
    # ADR-0061: a place the feed prices in two parts is one row. The feed
    # publishes flows along pricing-route boundaries rather than journeys, so
    # a place with no origin-destination flow is priced as two tickets that
    # meet at a calling point on the journey the page already shows for it.
    # Candidates are every intermediate stop on each of the journey's trains,
    # plus the station the reader leaves when the journey changes trains.
    # When several of those both sell, the cheapest valid sum wins. Each
    # ticket still comes through the same selector as the list it joins, so
    # the reader is quoted the journey they are shown and not the cheapest
    # fare on each leg found separately. Priced on the build's day, like
    # every other row: the day control changes the times and neither price
    # (ADR-0060).
    journeys_by_db: dict[int, dict] = {}
    if timetable is not None:
        # One page, one station, so the page is built from the slice of the
        # timetable it can use rather than from the national index. The
        # all-origins path hands every page the whole country -- one feed, one
        # page for each of 3,424 stations -- and holding that while a page is
        # assembled is where a two-station build's hour of paging went
        # (docs/build-performance-findings.md). A database that was already
        # loaded for this origin is returned unchanged, so the single-origin
        # path pays nothing here and its pages do not move. The focused
        # database is what the page's own searches use below, which is why the
        # cut is made here and not inside the walk.
        raw_timetable = timetable
        timetable = timetable.focused(origin.crs)
        if single_timetable is raw_timetable:
            single_timetable = timetable
        journeys_by_db[id(timetable)] = timetable.journeys_from(
            origin.crs, max_changes=max_changes, day=day
        )
    if (
        single_timetable is not None
        and id(single_timetable) not in journeys_by_db
        and hasattr(single_timetable, "journeys_from")
    ):
        if hasattr(single_timetable, "focused"):
            single_timetable = single_timetable.focused(origin.crs)
        if id(single_timetable) not in journeys_by_db:
            journeys_by_db[id(single_timetable)] = single_timetable.journeys_from(
                origin.crs, max_changes=max_changes, day=day
            )
    split_at = two_part_candidates(
        timetable,
        origin.crs,
        day,
        max_changes,
        reached=journeys_by_db.get(id(timetable)) if timetable is not None else None,
    )
    if split_at:
        for priced, query in (
            (single, fares.page_destinations_within),
            (single_tickets, fares.page_single_destinations_within),
            (anytime_tickets, fares.publishable_destinations_within),
        ):
            for two_part in fares.two_part_fares(
                origin.crs,
                split_at,
                two_part_query(query, day),
            ):
                priced[two_part.crs] = two_part
    # Two Together is evaluated against the current DTD RR records below. A
    # destination carries a railcard price unless its ticket, route, and
    # locations have a matching total ban.

    tracked = False
    disclosure: str | None = None
    # Every railcard the project has reviewed and the feed carries, as products.
    # Two Together is one of them rather than the only one, so a reader who
    # holds a 16-25 or a Senior card answers the same question with the same
    # page. The price of each is calculated from the feed's minimum-fare table
    # and the current RR restriction records; only a matching total ban removes
    # it, per card.
    railcard_families = fares.reviewed_railcard_families()

    # The page's own configuration, held once: the row and railcard builders
    # read a dozen of these facts between them, and one object keeps the list
    # in one place and lets a builder be called on its own terms.
    context = PageContext(
        fares=fares,
        origin=origin,
        timetable=timetable,
        day=day,
        max_changes=max_changes,
        departure_limit=departure_limit,
        provider=provider,
        adults=adults,
        network=network,
        advertiser_id=advertiser_id,
        publisher_id=publisher_id,
        mode=mode,
        railcard_families=railcard_families,
    )
    # The full rule record repeats on nearly every row: on the heaviest real
    # page one record served all 1,678 rows and the block was 388KB (audit B3,
    # measured). Rows keep a key into one payload map; only the drawer reads
    # the record, and the table reads the price straight off the row. The pool
    # owns the map, so a builder asks it for a key rather than threading the
    # two dicts that hold the records and their numbering.
    pool = RulePool()

    destinations: list[dict] = []
    single_destinations: list[dict] = []
    anytime_destinations: list[dict] = []
    # One list of departure times per journey, shared by every fare list that
    # prices it (S1 of the 19 October 2026 critique).
    departures_seen: dict[tuple[int, str], list[dict]] = {}
    all_row_crs = set(single) | set(single_tickets) | set(anytime_tickets)
    for db_candidate in (timetable, single_timetable):
        if (
            db_candidate is None
            or not hasattr(db_candidate, "departures_from")
            or any(db_id == id(db_candidate) for db_id, _ in departures_seen)
        ):
            continue
        db_id = id(db_candidate)
        by_dest = db_candidate.departures_from(
            origin.crs, max_changes=max_changes, day=day, limit=departure_limit
        )
        for dest_crs in all_row_crs:
            options = by_dest.get(dest_crs)
            departures_seen[(db_id, dest_crs)] = (
                [
                    {
                        "depart": option.departure,
                        "arrive": option.arrival,
                        "changes": option.changes,
                    }
                    for option in options
                ]
                if options
                else []
            )
    # The row and its link come back together, because the page's two
    # disclosure facts are every row's link folded into one: the payload says
    # once whether this page's links are tracked and what it discloses.
    for crs, one in sorted(single.items(), key=lambda item: item[1].best_pence):
        row, link = destination_row(
            context,
            pool,
            crs,
            one,
            quality="standard return",
            journey_db=timetable,
            departures_seen=departures_seen,
            journeys_by_db=journeys_by_db,
        )
        destinations.append(row)
        tracked = tracked or link.tracked
        disclosure = disclosure or link.disclosure
    for crs, one in sorted(single_tickets.items(), key=lambda item: item[1].best_pence):
        row, link = destination_row(
            context,
            pool,
            crs,
            one,
            quality="outbound single",
            journey_db=single_timetable,
            departures_seen=departures_seen,
            journeys_by_db=journeys_by_db,
        )
        single_destinations.append(row)
        tracked = tracked or link.tracked
        disclosure = disclosure or link.disclosure
    for crs, one in sorted(anytime_tickets.items(), key=lambda item: item[1].best_pence):
        row, link = destination_row(
            context,
            pool,
            crs,
            one,
            quality="unrestricted Anytime Day Return",
            journey_db=timetable,
            departures_seen=departures_seen,
            journeys_by_db=journeys_by_db,
        )
        anytime_destinations.append(row)
        tracked = tracked or link.tracked
        disclosure = disclosure or link.disclosure

    # S23, one step further. "No service" is a statement about the day this
    # build asked about, not about the station: measured from Nottingham on
    # 2026-10-04, a Sunday, Langwith, Shirebrook, Creswell and Whitwell all read
    # "No service", and all four are direct journeys of 46 to 58 minutes on
    # every other day of that week. The feed calls at every one of them, so
    # nothing about them is missing from the network -- only from that Sunday.
    # A reader cannot reach the day the build happened to pick, so a row with no
    # service on it is asked the week as well and carries the day it does run.
    #
    # The week is walked once, outermost, because best_journey() rebuilds its
    # index whenever the day changes: one index build per day whatever the number
    # of rows, rather than one per row. The sweep runs only when the page has a
    # row that needs it, so a build on a day the network runs normally pays
    # nothing for it. Wirksworth is the other kind of row: no service on any day
    # of the week, so it keeps saying so and gains no key.
    # S23, one step further, and then the reader picks the day. "No service" is
    # a statement about the day this build asked about, not about the station:
    # measured from Nottingham on 2026-10-04, a Sunday, Langwith, Shirebrook,
    # Creswell and Whitwell all read "No service", and all four are direct
    # journeys of 46 to 58 minutes on every other day of that week. The feed
    # calls at every one of them, so nothing about them is missing from the
    # network, only from that Sunday.
    #
    # So the whole week is walked and every answer kept, and the page hands the
    # reader the choice of which day the times are for. The sweep this replaces
    # asked only the rows with no service that day, which is a fifth of them on
    # a Sunday and none on a Wednesday, and it could answer "does it run at all
    # that week" and nothing finer: a row taking 46 minutes on the Tuesday and
    # 70 on the Monday had no way to say so.
    #
    # The days are outermost because the search rebuilds its index whenever the
    # day changes: one index build a day, not one a row. Within a day it is one
    # walk for every destination, not one walk per destination, which is what
    # journeys_from() is for and what makes this shape affordable.
    #
    # Held once per page and keyed by station, because a destination priced by
    # three fare lists wants one answer three times. Only the stations a row
    # names are kept: the walk reaches the whole network, and the rest of it is
    # an answer nobody asked for.
    collections = (destinations, single_destinations, anytime_destinations)
    sources: list = []
    for collection in collections:
        for row in collection:
            source = row.get("_journeySource")
            if source is not None and not any(source is seen for seen in sources):
                sources.append(source)
    service_days: list[str] = []
    service_week: list[list[dict]] = []
    if sources and day is not None:
        service_days = [
            (day + timedelta(days=offset)).isoformat()
            for offset in range(0, SERVICE_WEEK_HORIZON + 1)
        ]
        wanted = {row["crs"] for collection in collections for row in collection}
        week_days = [day + timedelta(days=offset) for offset in range(0, SERVICE_WEEK_HORIZON + 1)]
        for position, source in enumerate(sources):
            # The week's answers outlive the fares they were searched for: a
            # fares-only refresh prices new rows out of the same journeys, so
            # the timetable half is read from the facts when they match and
            # searched only when they do not (T9). The whole reached set is
            # stored rather than the wanted subset, so a row the next fares
            # feed prices for the first time still finds its journeys waiting.
            source_index = 0 if source is timetable else 1
            stored = read_service_week(
                origin.crs, timetable_identity, source_index, max_changes, week_days
            )
            if stored is not None:
                service_week.append(
                    [
                        {crs: pair for crs, pair in day_facts.items() if crs in wanted}
                        for day_facts in stored
                    ]
                )
                continue
            per_day = []
            full_week = []
            for offset in range(0, SERVICE_WEEK_HORIZON + 1):
                reached = source.journeys_from(
                    origin.crs, max_changes=max_changes, day=day + timedelta(days=offset)
                )
                full_week.append(
                    {
                        crs: [journey.duration, journey.changes]
                        for crs, journey in reached.items()
                    }
                )
                per_day.append(
                    {
                        crs: [journey.duration, journey.changes]
                        for crs, journey in reached.items()
                        if crs in wanted
                    }
                )
            write_service_week(
                origin.crs, timetable_identity, source_index, max_changes, week_days, full_week
            )
            service_week.append(per_day)

    # Read out of the table by the day, not copied into the row. The index
    # is what the page needs: which of the page's tables this row belongs to,
    # because a row read by the second timetable is not in the first one's.
    for collection in collections:
        for row in collection:
            source = row.get("_journeySource")
            index = -1
            for position, seen in enumerate(sources):
                if seen is source:
                    index = position
                    break
            # Null rather than -1 for "no week". A pool reference is a
            # negative number, so -1 would be read by the page as pool entry
            # zero, which is a railcard record: the cell would decode into
            # somebody's railcards rather than into a row with no week.
            row["serviceWeekIndex"] = index if service_week else None
            row.pop("_journeySource", None)

    for collection in collections:
        for row in collection:
            if row["journeyState"] == "found":
                continue
            # The day this row next runs, which is the day the absence wording
            # in JOURNEY_ABSENCE names. Only a row carrying an absence gains it,
            # so a page whose every destination runs that day pays nothing here,
            # and the state itself does not change: it is the same absence, and
            # only what is known about the week around it has moved.
            for offset in range(1, SERVICE_WEEK_HORIZON + 1):
                if day_answer(row, offset, service_week) is not None:
                    row["nextService"] = service_days[offset]
                    break

    # D2 of the 23 October 2026 byte audit: a place no journey reaches is a
    # fare, not an answer, and a cluster-priced feed gives every page one of
    # those for most of the network. From Grantham 1,730 of 2,752 places were
    # priced and reachable on none of the eight days the page covers, which was
    # a third of the page's bytes spent on rows whose Time column said "No
    # service" beside a price.
    #
    # Only an absence every day of the walk drops the row. A place that runs on
    # any day keeps its row and carries that day in ``nextService``, which is
    # the answer the page already words ("no service on Sunday, and it runs on
    # Monday"), so a Sunday build does not lose the stations that run the rest
    # of the week. A build with no timetable has no week to judge and drops
    # nothing: it never enters this branch, because ``service_week`` is empty
    # when the walk did not run.
    had_rows = bool(destinations or single_destinations or anytime_destinations)
    unreachable_count = 0
    if service_week:
        unreachable = unreachable_places(
            [row for collection in collections for row in collection]
        )
        unreachable_count = len(unreachable)
        for collection in collections:
            collection[:] = [row for row in collection if row["crs"] not in unreachable]
        reached = {
            crs
            for collection in collections
            for crs in (row["crs"] for row in collection)
        }
        # The week narrows with the rows: an answer for a place the page no
        # longer lists is a station code and eight durations nobody reads, and
        # on this page the dropped places were most of it.
        service_week = [
            [
                {crs: answer for crs, answer in day.items() if crs in reached}
                for day in week
            ]
            for week in service_week
        ]

    # C08: the feed's own outward and return validity for each restriction
    # code these rows carry. Keyed by code and held once, because the rows
    # already carry the code: repeating the wording on every row would put the
    # same sentence on a page 1,678 times, which is what the railcard rule map
    # below already had to be fixed for.
    restriction_validity: dict[str, dict[str, str]] = {}
    shown_codes = restriction_codes_shown(
        row
        for collection in (destinations, single_destinations, anytime_destinations)
        for row in collection
    )
    for collection in (destinations, single_destinations, anytime_destinations):
        for row in collection:
            # A two-ticket row's own code is its first restricted ticket's, so
            # each ticket is asked as well (ADR-0061).
            for code in [row["restrictionCode"]] + [
                ticket["restrictionCode"] for ticket in row.get("tickets") or ()
            ]:
                header = fares.restrictions.headers.get(code) if code else None
                if header is None or code in restriction_validity:
                    continue
                if not (header.outward_text or header.return_text):
                    continue
                restriction_validity[code] = {
                    "outwardText": header.outward_text,
                    "returnText": header.return_text,
                }

    excluded_codes = sorted({row.ticket_code for row in excluded_itx})
    # The freshness claim for the conditions above. Carried as plain data
    # rather than as a sentence so the page writes it in its own voice, and so
    # a test can assert on the fact rather than on a wording that changes.
    # The second opinion is about the conditions *this page* shows, so it is
    # asked here rather than once for the run. Reading the reference feed stays
    # a single parse for the whole build; only the set difference is per page,
    # and it is a handful of codes against a dict.
    reference_check = (
        check_restrictions(
            shown_codes,
            reference,
            published=reference_published,
            checked_at=reference_checked,
        )
        if reference is not None
        else RestrictionCheck(status=ABSENT, note="no reference feed was named")
    )
    restriction_reference_note = {
        "status": reference_check.status,
        "compared": reference_check.compared,
        "listed": reference_check.listed,
        "missing": reference_check.missing,
        "unlisted": list(reference_check.unlisted),
        "note": reference_check.note,
        "published": reference_check.published,
        "checkedAt": reference_check.checked_at,
        "verified": reference_check.verified,
    }
    # Asked of what the feed priced, not of what the page lists: a page emptied
    # by the reachability rule above is explained by ``unreachableDestinationCount``
    # instead, and a note about ITX placeholders would name the wrong cause.
    unpriced_note = (
        explain_unpriced(
            len(raw_destinations), len(excluded_itx), excluded_codes, raw_tally
        )
        if not had_rows
        else None
    )

    origin_row = fares.locations_by_crs[origin.crs]
    # The picker's options (ADR-0019), from the one shared slug map, so a page
    # built on its own links to the same folders the --all-origins build writes.
    slugs = station_slugs_for(fares.locations_by_crs)
    every_row = list(destinations) + list(single_destinations) + list(anytime_destinations)
    # S15, per card: a railcard is a constraint on the party, not a discount a
    # solo reader can tick. The bounds are the feed's own records, so the page
    # states the rule the data states rather than one this project invented, and
    # a card whose range does not cover the chosen party is not offered for it.
    railcards = []
    for family in railcard_families:
        eligible = {
            row["crs"]
            for row in every_row
            if family.key in row["railcards"]
            and row["railcards"][family.key]["pricePence"] is not None
            and row["railcards"][family.key]["pricePence"] < row["adultPence"]
        }
        railcards.append(
            {
                "key": family.key,
                "label": family.label,
                "codes": list(family.codes),
                "minAdults": family.min_adults,
                "maxAdults": family.max_adults,
                "eligibleCount": len(eligible),
            }
        )
    # The timetable's own service window, read once for both dates below.
    service_window = timetable.service_window() if timetable else ("", "")
    # S29: how much of the feed's coverage this page could not show, counted
    # rather than asserted. A destination whose type is not in the reviewed
    # registry is still priced and still listed, but no chip can ever select it,
    # so the count is the difference between "every type" and "every type we
    # have reviewed".
    unclassified = {
        row["crs"]
        for collection in (destinations, single_destinations, anytime_destinations)
        for row in collection
        if not set(row.get("destinationTypes") or []) - {"other"}
    }

    # One fact, read once: whether this build loaded a timetable decides both
    # what the payload says about journeys and which sentence about times it
    # carries (C5). Two spellings of it could disagree.
    has_journeys = timetable is not None

    return {
        "origin": {"crs": origin_row.crs, "name": display_station_name(origin_row.crs, origin_row.name)},
        "sourceFingerprint": source_fingerprint(),
        "builtAt": built_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "destinations": destinations,
        "singleDestinations": single_destinations,
        "anytimeDestinations": anytime_destinations,
        "singleJourneyNote": (
            "Single fares are timed from the same timetable as the returns, because "
            "this build loaded no separate outbound-single timetable."
            if single_timetable is None and timetable is not None
            else None
        ),
        "rawFareDestinationCount": len(raw_destinations),
        "singleFareDestinationCount": len(single_ticket_rows),
        "excludedItxCount": len(excluded_itx),
        "excludedItxCodes": excluded_codes,
        # Destination rows this origin lost to a missing name: the feed's own
        # ceiling on coverage, carried so the report can count it beside the
        # unsourced stations (audit A3).
        "unnameableFareCount": unnameable_from_tally(raw_tally),
        # S29: priced rows no chip can select, because their type is not in the
        # reviewed registry. Shown beside the counts so "every destination"
        # stays a defensible claim.
        "unclassifiedDestinationCount": len(unclassified),
        # D2: places the feed prices that no journey reaches on any day the
        # page carries. They are not listed, and the page says how many and why
        # rather than letting the gap read as coverage.
        "unreachableDestinationCount": unreachable_count,
        # The journey limit the reachability rule above was judged against, so
        # the sentence that explains it names the same bound the build used.
        "maxChanges": max_changes if has_journeys else None,
        "locationTypeReviewed": bool(fares.location_type_source),
        "unpricedNote": unpriced_note,
        # The picker's options, from the route manifest of pages this release
        # actually writes (S01). When the caller supplies published_routes
        # those are the only stations offered, so no link can point at a page
        # that was not generated. When it does not -- the single-page unit
        # build and the direct build_payload tests -- the options are every
        # real station in the feed, which is what a full-network site serves.
        "stations": (
            [
                {"name": entry["name"], "crs": entry["crs"], "href": entry["href"]}
                for entry in published_routes
                if entry["crs"] != origin.crs
            ]
            if published_routes is not None
            else [
                {
                    "name": loc.name,
                    "crs": loc.crs,
                    "href": with_base(base_path, f"/from/{slugs[crs]}/"),
                }
                for crs, loc in sorted(fares.locations_by_crs.items())
                if crs != origin.crs and not is_pseudo_station(crs)
            ]
        ),
        # Said by the page when this origin priced nothing, so the difference
        # between "nothing inside your budget" and "nothing priced from here at
        # all" is on the page rather than inferred from an empty table.
        "stationCount": len(fares.locations_by_crs),
        "hasJourneys": has_journeys,
        # The collection, and the shared RR rule records behind it. Nothing is
        # selected: the reader names the card they hold, or reads standard
        # fares, and the browser remembers which they chose.
        "railcards": railcards,
        "railcardRules": pool.railcard_rules,
        # C08: the reader-facing validity behind a restriction code, once per
        # code. The page resolves a row's code against this rather than each
        # row repeating the same strings.
        "restrictionValidity": restriction_validity,
        "restrictionReference": restriction_reference_note,
        "pricingBasis": "Each price is the cheapest displayable standard-class fare found in the feed, in the ticket mode the page opens in; each mode names above the table what its fares are, with ITX placeholders excluded and Advance singles labelled as train-specific",
        "serviceDate": day.isoformat() if day else None,
        # The span the sweep asked, so the page can say which days a row with
        # no next service was actually checked for rather than saying "no
        # service" and leaving the window unstated.
        "serviceHorizon": SERVICE_WEEK_HORIZON,
        # The days themselves, and every destination's answer on each of
        # them. Held at page level rather than per row because a destination
        # priced by three fare lists wants one answer three times, and three
        # copies of the same eight answers is the same sentence eight times
        # over in three places. The rows carry serviceWeekIndex instead, so
        # the page reads the table through the row rather than the row
        # carrying a copy of the table. Empty when the build had no day to
        # walk the week from, which is when the page shows no day control.
        "serviceDays": service_days,
        "serviceWeek": service_week,
        "note": note,
        "attribution": attribution,
        # Where the numbers on this page came from. It sits with the prices,
        # not in the footer, because where a number came from is part of the
        # number; the footer keeps the licence wording, which is a different
        # reader's question.
        "priceSource": price_source,
        # S33: the dates the reader needs to judge the numbers. The fares date
        # is the download's own, the timetable dates are the service window the
        # feed states, and the threshold is the number a reader can hold this
        # page to. With no timetable the page says it prices fares only, which
        # is a choice rather than a stale feed.
        "feedDate": feed_date,
        "timetableFrom": cif_date_to_iso(service_window[0]) if service_window else None,
        "timetableTo": cif_date_to_iso(service_window[1]) if service_window else None,
        "staleAfterDays": STALE_AFTER_DAYS,
        # Internal links are prefixed when the host does not serve the site at
        # its domain root (ADR-0024). The template carries it too, for the
        # links that are written as HTML rather than built in JS.
        "baseHref": with_base(base_path, "/"),
        # The station route fetches one stylesheet, at the path this release is
        # published at (ADR-0047). The picker sets its own the same way.
        "styleSrc": with_base(base_path, "/" + build_assets.station_style_asset_name()),
        # And one script, at the path this release is published at (T1). The
        # page's own answer is its destinations; the code that reads them is
        # the same on every page of the route, so it travels once.
        "scriptSrc": with_base(base_path, "/" + build_assets.station_script_asset_name()),
        # S45: the state is a fact about the build, so it is carried in the
        # payload rather than re-derived by each renderer.
        "synthetic": price_source == DEFAULT_PRICE_SOURCE,
        "linkNote": LINK_NOTE_FALLBACK if mode == "fallback" else None,
        # The paragraph about times is not the same on every build: a
        # prices-only page has no services for a fare to be valid on, so it
        # carries the sentence its own shape supports (C5, 17 October 2026).
        # The renderer writes this string into the page, so the payload and the
        # page cannot say different things.
        "pricingNote": service_claim(has_journeys),
        "feed": fares.stats(),
        "locationTypeSource": fares.location_type_source,
        "timetable": timetable.stats() if timetable else None,
        "adults": adults,
        "tracked": tracked,
        "disclosure": disclosure,
        "railcardNote": (
            (
                "No railcard is selected, so the prices shown are standard fares. Choose the "
                "card you hold and the fares it lowers are repriced from that card's own "
                "minimum-fare table, discounted by the percentage the feed gives that card on that ticket (33.4% for the mainstream cards) and rounded down to the nearest 5p. "
                "Current DTD RR route, ticket, location and total-ban rules are checked for "
                "every destination and every card; matching restriction codes are retained as "
                "travel conditions rather than treated as bans."
            )
            if railcards
            else (
                "No reviewed railcard is present in this feed. The prices shown are standard fares."
            )
        ),
        # The half of the paragraph that is true whichever card is chosen. The
        # page rewrites the opening sentence from the state on screen, because a
        # paragraph about the numbers has to agree with the numbers (audit item
        # 24).
        "railcardMethod": (
            "The card's own fare is repriced from its minimum-fare table, "
            "discounted by the percentage the feed gives that card on that ticket (33.4% for the mainstream cards) and rounded down to the nearest 5p. Current DTD RR route, "
            "ticket, location and total-ban rules are checked for every destination and every "
            "card; matching restriction codes are retained as travel conditions rather than "
            "treated as bans."
        )
        if railcards
        else None,
        # Without a date every schedule in the feed is read, so a train that has
        # a change of plan appears as its permanent and its covering version.
        "dateNote": (
            None
            if day or timetable is None
            else "No date was given, so every schedule in the feed is read: a train whose plan "
            "has changed appears twice, and Sunday-only trains appear on every day."
        ),
    }


def _priced_destinations(
    fares: FaresDb,
    timetable,
    origin_crs: str,
    day: date | None = None,
    coverage: UnsourcedReport | None = None,
) -> int:
    """How many places the feed prices from an origin, for the write set.

    The page offers three ticket modes, so "priceable" is the union of all
    three: a station whose only fares are restricted returns or singles still
    has a page a reader can use, and ADR-0019 decision 3 asks whether that
    page can answer, not whether one mode of it can. Audit A1 caught the
    previous test using the reviewed-anytime selector alone, which kept King's
    Cross out of the chooser while its page carried 171 returns; the union now
    lives in ``FaresDb.priced_destinations_within`` so this test, the chooser
    and the coverage report cannot ask three different questions. When a
    coverage report is passed, the same rows are checked for a station no
    source could classify -- the queries have already been run, so naming the
    gap costs nothing extra on a 2,500-origin build.

    This is the *write set's* question -- can this origin's page answer at all,
    and which stations does the chooser offer -- and it is deliberately not the
    number the chooser prints beside a station. That number is the places the
    page carries, read from the page itself (``places_in_payload``): a place
    the feed prices in two fares is a row the page writes and no single selector
    prices (ADR-0061), and counting it here would mean walking every origin's
    journeys a second time before any page was built. Measured on the real feed
    on 15 October 2026, that walk cost 3.0s for Grantham, 12.9s for King's Cross
    and 15.9s for Manchester Piccadilly, against a release share of about 450
    origins that already takes 87 to 114 minutes inside a 150-minute timeout.
    """
    tally: dict[str, int] = {}
    rows = fares.priced_destinations_within(
        origin_crs, EVERYTHING_PENCE, adults=1, day=day, tally=tally
    )
    if coverage is not None:
        coverage.note_fares_rows(fares, rows, origin_crs)
        coverage.note_unnameable(origin_crs, unnameable_from_tally(tally))
    return len(rows)


# The feed names a station with the CIF short form, and a few entries are
# compressed past what a reader can read as a place: "WARRINGTON BK QY",
# "HEATHROW UNDERGD", "XC ORIGIN". This is the reviewed list of the ones a
# reader-facing list was showing raw, keyed by CRS because the code is the
# feed's identity for a station -- a rename would otherwise surface as an
# entry that quietly stops matching, the same rule as the facet registry
# (audit item 5, 9 October 2026). A value is the station's ordinary name: the
# National Rail name where it has one, and the label its operator uses where
# the entry is a rail-air bus link or a fares origin rather than a station.
#
# Some of these are the names a cold chooser shows first, because a compressed
# name is most visible on the busiest stations: the real 24-station build listed
# "LONDON ST PANCRS", "MANCHESTER PIC", "LIVERPOOL L ST", "BIRMINGHAM N ST",
# "BRISTOL TEMPLE M" and "NEWPORT S.WALES" above every name it got right.
# `python build_demo_page.py --feed feeds/fares --all-origins` writes the list
# those six came from.
REVIEWED_STATION_NAMES: dict[str, str] = {
    "AFK": "Ashford International",
    "APN": "Newcastle Airport",
    "BHI": "Birmingham International",
    "BHM": "Birmingham New Street",
    "BRI": "Bristol Temple Meads",
    "EFF": "Effingham Junction",
    "EXG": "Exhibition Centre (Glasgow)",
    "HPQ": "Harwich International",
    "IVA": "Inverness Airport",
    "KGX": "London Kings Cross",
    "LIV": "Liverpool Lime Street",
    "LJL": "Liverpool Airport Bus",
    "LNE": "London International (CIV)",
    "LPY": "Liverpool South Parkway",
    "MAN": "Manchester Piccadilly",
    "MCO": "Manchester Oxford Road",
    "MIA": "Manchester Airport",
    "NWP": "Newport (South Wales)",
    "PRA": "Prestwick International Airport",
    "QEO": "East Midlands Railway (origin)",
    "QGA": "Glasgow Airport Bus",
    "QNO": "Northern (origin)",
    "QSO": "South Western Railway (origin)",
    "QTO": "TransPennine Express (origin)",
    "QXO": "CrossCountry (origin)",
    "SFA": "Stratford International",
    "STP": "London St Pancras International",
    "WBQ": "Warrington Bank Quay",
    "ZHJ": "Heathrow Underground",
}


def display_station_name(crs: str, name: str) -> str:
    """The name a reader sees for a station, reviewed where the feed compresses it."""
    return REVIEWED_STATION_NAMES.get(crs.upper(), name)


def places_in_payload(payload: dict) -> int:
    """How many places one page's rows carry, which is the number the chooser prints.

    The page's own rows are the only thing that knows this. A place the feed
    prices in two fares is a row the page writes, and no fare selector can see
    it before the page exists (ADR-0061), so the count is read off the page the
    build has already assembled rather than asked a second time through
    ``_priced_destinations`` -- which would walk every origin's journeys again
    for a number the page had just worked out. Measured on the real feed on
    15 October 2026: Grantham's selectors priced 50 places, its page carried
    334, and the walk that would close the gap cost 3.0s for that origin and
    15.9s for Manchester Piccadilly inside an index pass that runs for every
    origin before a single page is written.
    """
    return len(
        {
            row["crs"]
            for key in FARE_LISTS
            for row in payload.get(key) or ()
        }
    )


# The station's own facts: what kind of place it is, and the reviewed named
# sites that make it a day out. Every one of them is identical on every page of
# the release that lists that station, so they belong to the station rather
# than to an origin's page (D1 of the 23 October 2026 byte audit). They travel
# once in the shared station list and each page joins its own destinations to
# them by CRS.
STATION_FACT_FIELDS = (
    "destinationType",
    "destinationTypes",
    "heritageSites",
    "natureSites",
    "coastalSites",
    "rspbSites",
    "nationalTrustSites",
    "nationalParkSites",
)


def station_facts(fares: FaresDb) -> dict[str, dict[str, object]]:
    """Every station's own facts, keyed by CRS, for the one shared document.

    Every station the feed names, not only the ones this release writes a page
    for: a page's rows can name a station that prices nothing from itself (a
    zone boundary, a station whose only flows leave it), and a destination with
    no facts of its own would lose its type chips and its site proofs.

    A fact that is empty is left out rather than sent as ``[]``, because most
    stations have no site list and seven empty lists apiece would be a third of
    the document. ``destinationType`` is left out for the same reason it is
    derivable: it is the first of ``types``, which is the order the fares
    queries already give them in.
    """
    facts: dict[str, dict[str, object]] = {}
    for crs in fares.locations_by_crs:
        entry: dict[str, object] = {"types": fares.destination_types(crs)}
        for field, values in (
            ("heritageSites", fares.heritage_sites(crs)),
            ("natureSites", fares.nature_sites(crs)),
            ("coastalSites", fares.coastal_sites(crs)),
            ("rspbSites", fares.rspb_sites(crs)),
            ("nationalTrustSites", fares.national_trust_sites(crs)),
            ("nationalParkSites", fares.national_park_sites(crs)),
        ):
            if values:
                entry[field] = values
        facts[crs] = entry
    return facts


def without_station_facts(payload: dict) -> dict:
    """The payload as a page embeds it, with the station's own facts left out.

    A release page fetches them with the shared station list instead, which is
    the same document on every page and therefore one copy of the facts rather
    than one per page (D1). The build still holds them while it renders: the
    destination-type chips are markup, and the build is the only thing that can
    write them.

    A payload that names no shared station list is returned unchanged, because
    the page that embeds it has no other way to reach the facts -- a
    single-origin build carries its own.
    """
    dropped = set(STATION_FACT_FIELDS)
    stripped = dict(payload)
    for key in FARE_LISTS:
        rows = payload.get(key)
        if isinstance(rows, list):
            stripped[key] = [
                {field: value for field, value in row.items() if field not in dropped}
                for row in rows
            ]
    return stripped


def build_station_index(
    priced_by_origin: dict[str, int], all_locations: dict[str, object]
) -> list[dict[str, str]]:
    """The picker's option list, built from what was actually written.

    ``priced_by_origin`` maps CRS to the number of priced destinations that
    origin's page carries; ``all_locations`` supplies names. A station that
    priced nothing is **absent**, not offered and then refused (ADR-0019
    decision 3): offering one would put "0 destinations" in the picker and send
    the reader to a page that cannot answer them. The count also ranks the root
    chooser's cold start, which is derived from the feed rather than an invented
    "popular stations" list.
    """
    index = []
    slugs = station_slugs_for(all_locations)
    for crs, count in sorted(priced_by_origin.items(), key=lambda item: (-item[1], item[0])):
        location = all_locations[crs]
        # Priced is not enough: a zone boundary prices fares through it but no
        # train stops there, so it is absent rather than offered and then
        # refused (audit A6, same rule as the priced-nothing station).
        if count <= 0 or is_pseudo_station(crs):
            continue
        index.append(
            {
                "crs": crs,
                "name": display_station_name(crs, location.name),
                "slug": slugs[crs],
                "destinations": count,
            }
        )
    return index


# The payload's row lists, and the shape they ship in. Every row in a list
# carries the same field names, so sending them once per page instead of once per
# row costs nothing to read and a third of the payload to send: on the Grantham
# page the names were 67 KB of a 200 KB payload, and the station picker's three
# names were 11 KB of every 168 KB it added to every page (measured 30 September
# 2026 by tools/page_bytes.py).
ROW_LISTS = ("destinations", "singleDestinations", "anytimeDestinations", "stations")


POOL_MIN_BYTES = 12


# A departure option's three facts, in the order the wire sends them. An option
# was an object with three keys, so a page paying for 4,548 of them paid about
# 28 bytes of key names each: 127 KB of a 1.3 MB payload. The names are sent
# once per page instead, in ``rowCodec``, and the page packs them back into the
# objects every reader of a departure already expects.
DEPARTURE_COLUMNS = ("depart", "arrive", "changes")


# The most values a column may stand for and still be sent as a list of indices.
# A column with more is one whose values are mostly unique (a fare, a name), and
# an index into a list that long costs as much as the value it replaces.
DICT_MAX_VALUES = 64


def _wire_bytes(value: object) -> int:
    """What one cell costs on the wire, with the separator after it."""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1


def _pack_departures(value: object) -> object:
    """One list of departure options as arrays, in ``DEPARTURE_COLUMNS`` order.

    Anything that is not an option in that exact order is left as it was, so a
    payload written elsewhere -- a test's own rows, an older page -- still reads
    back through the codec's absence.
    """
    if not isinstance(value, list):
        return value
    packed = []
    for option in value:
        if not isinstance(option, dict) or list(option) != list(DEPARTURE_COLUMNS):
            return value
        packed.append([option[field] for field in DEPARTURE_COLUMNS])
    return packed


def _pack_service_week(week: object) -> object:
    """One entry per station, holding its answer for every day of the week.

    The week was a table per day, keyed by station, so a destination that runs
    all eight days sent its three-letter code eight times: on the Grantham page
    the week was 105 KB of a 1.3 MB payload, and transposing it returned 35 KB.
    Now the key is sent once and the answers are a list the page indexes by the
    day it is showing.

    A day table is ordered by the walk's own reach, so the transpose also
    removes the one place the payload's bytes depended on a dict's iteration
    order across days.
    """
    if not isinstance(week, list):
        return week
    packed = []
    for source in week:
        if not isinstance(source, list) or not all(isinstance(day, dict) for day in source):
            packed.append(source)
            continue
        stations: dict[str, list[object]] = {}
        for day in source:
            for crs in day:
                stations.setdefault(crs, [None] * len(source))
        for offset, day in enumerate(source):
            for crs, answer in day.items():
                stations[crs][offset] = answer
        # A day that answers what the day before it did travels as ``true``.
        # A weekday timetable repeats the same duration and change count five
        # days running, and a place with no service repeats nothing six times:
        # on the Grantham page 4,870 of 8,216 answers were their predecessor's,
        # worth 24 KB of a 427 KB page. ``true`` cannot be an answer -- one is a
        # [minutes, changes] pair or null -- so it needs no escape.
        for crs, answers in stations.items():
            for offset in range(len(answers) - 1, 0, -1):
                if answers[offset] == answers[offset - 1]:
                    answers[offset] = True
        # A week no station runs in stays as it was: transposed it would be an
        # empty dict, and the day count -- which is what read-back needs to
        # rebuild one empty table per day -- would go with it.
        packed.append(stations if stations else source)
    return packed


def _unpack_service_week(week: object) -> object:
    if not isinstance(week, list):
        return week
    days = []
    for source in week:
        if isinstance(source, list) or not isinstance(source, dict):
            days.append(source)
            continue
        tables = [{} for _ in range(len(next(iter(source.values()), [])))]
        for crs, answers in source.items():
            # Each station's answers are resolved first, because a ``true`` says
            # "the day before" and the day tables below are one day at a time.
            resolved: list[object] = []
            for answer in answers:
                resolved.append(
                    resolved[-1] if answer is True and resolved else answer
                )
            for offset, answer in enumerate(resolved):
                if offset < len(tables) and answer is not None:
                    tables[offset][crs] = answer
        days.append(tables)
    return days


def _unpack_departures(value: object, columns: object) -> object:
    if not isinstance(columns, list) or not isinstance(value, list):
        return value
    return [
        {field: option[index] for index, field in enumerate(columns)}
        if isinstance(option, list)
        else option
        for option in value
    ]


def _pool_key(value: object) -> str:
    """A value's identity, so two equal railcard records share one entry."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


FARE_LISTS = ("destinations", "singleDestinations", "anytimeDestinations")


def _column_dictionaries(columns: list[str], rows: list[list[object]]) -> dict[str, list[object]]:
    """The columns a short index can stand in for, and the values they stand for.

    A row's words repeat across the page: on the Grantham page the route code
    was one of 41 five-character strings across 4,690 rows and the ticket code
    one of 18, and the page paid 66 KB for them. A column whose values are all
    short strings or booleans becomes a small int per cell and a list of the
    values once in the table, which is the same trade the page-level pool makes
    across lists rather than inside one.

    Only strings and booleans qualify. A cell that is a number is either a real
    number or a reference into the pool, and an index cannot be told from
    either; a value is only sent as an index when the whole column costs less
    that way, so a list of unique names gains nothing and is left alone.
    """
    dictionaries: dict[str, list[object]] = {}
    if not rows:
        return dictionaries
    for position, column in enumerate(columns):
        values = [row[position] for row in rows]
        if not all(isinstance(value, (str, bool)) for value in values):
            continue
        distinct: list[object] = []
        index: dict[str, int] = {}
        for value in values:
            marker = _pool_key(value)
            if marker not in index:
                index[marker] = len(distinct)
                distinct.append(value)
        if len(distinct) > DICT_MAX_VALUES:
            continue
        now = sum(_wire_bytes(value) for value in values)
        then = sum(len(str(index[_pool_key(value)])) + 1 for value in values)
        then += sum(_wire_bytes(value) for value in distinct)
        if then >= now:
            continue
        for row in rows:
            row[position] = index[_pool_key(row[position])]
        dictionaries[column] = distinct
    return dictionaries


TICKET_NAME_FIELDS = (("fromCrs", "fromName"), ("toCrs", "toName"))


def _railcard_codec(tables: dict[str, list[dict]]) -> dict | None:
    """The card order and the states a row's railcard decisions are packed by.

    A row's railcards were an object per card with four named fields, the
    largest cell on the page: 629 KB of the Crewe page's 1.25 MB of rows
    (shard 1 of run 38353105980). Packed, a decision is a four-item array in
    the page's card order, and a row whose cards arrive in another order is
    left as it was, so the page reads back the same object either way.
    """
    cards: list[str] = []
    states: list[str] = []
    for key in FARE_LISTS:
        for row in tables.get(key, []):
            value = row.get("railcards")
            if isinstance(value, dict):
                for card, details in value.items():
                    if card not in cards:
                        cards.append(card)
                    if isinstance(details, dict) and details.get("state") not in states:
                        states.append(details.get("state"))
    return {"cards": cards, "states": states} if cards else None


def _pack_railcards(value: object, codec: dict) -> object:
    if not isinstance(value, dict) or not value:
        return value
    cards = codec["cards"]
    if list(value) != [card for card in cards if card in value]:
        return value
    packed: list[object] = []
    for card in cards:
        details = value.get(card)
        if details is None:
            packed.append(0)
            continue
        if not isinstance(details, dict) or list(details) != [
            "state", "pricePence", "minimumFarePence", "rule"
        ]:
            return value
        rule = details["rule"]
        if isinstance(rule, str) and rule.isdigit() and str(int(rule)) == rule:
            rule = int(rule)
        elif rule is not None:
            return value
        packed.append(
            [codec["states"].index(details["state"]), details["pricePence"],
             details["minimumFarePence"], rule]
        )
    return packed


def _ticket_codec(tables: dict[str, list[dict]]) -> dict | None:
    """The field order a row's tickets are packed by, and the names they share.

    A ticket repeated both station names in full on every row (430 KB of the
    Crewe page). Each name is the station's, so it is sent once in a page map
    and the ticket keeps the code; a ticket whose fields differ from the common
    order, or whose name disagrees with the map, is left as it was.
    """
    columns: list[str] | None = None
    names: dict[str, str] = {}
    clash = False
    for key in FARE_LISTS:
        for row in tables.get(key, []):
            tickets = row.get("tickets")
            if not isinstance(tickets, list):
                continue
            for ticket in tickets:
                if not isinstance(ticket, dict):
                    continue
                if columns is None:
                    columns = list(ticket)
                for code_field, name_field in TICKET_NAME_FIELDS:
                    code, name = ticket.get(code_field), ticket.get(name_field)
                    if isinstance(code, str) and isinstance(name, str):
                        if names.setdefault(code, name) != name:
                            clash = True
    if not columns:
        return None
    named = not clash and all(
        code in columns and name in columns and columns.index(code) < columns.index(name)
        for code, name in TICKET_NAME_FIELDS
    )
    packed_columns = [
        field for field in columns
        if not (named and field in {name for _, name in TICKET_NAME_FIELDS})
    ]
    return {"columns": columns, "packed": packed_columns, "names": names if named else None}


def _pack_tickets(value: object, codec: dict) -> object:
    if not isinstance(value, list):
        return value
    out: list[object] = []
    for ticket in value:
        if not isinstance(ticket, dict) or list(ticket) != codec["columns"]:
            out.append(ticket)
            continue
        names = codec["names"]
        if names is not None and any(
            names.get(ticket[code]) != ticket[name] for code, name in TICKET_NAME_FIELDS
        ):
            out.append(ticket)
            continue
        out.append([ticket[field] for field in codec["packed"]])
    return out


def _placed_columns(tables: dict[str, list[dict]]) -> tuple[list[str], dict[str, dict]]:
    """The columns that belong to a station rather than to one list's fare.

    The three fare lists name mostly the same stations (534 of Crewe's 538
    single-fare rows are also return rows), and a station's name, types and
    named sites are the same in every list. A column is placed -- sent once per
    station rather than once per row -- only when every row of every fare list
    carries it with the same value for its station; anything a list prices
    differently stays on the row.
    """
    lists = [tables[key] for key in FARE_LISTS if key in tables]
    # One list has nothing to share with: placing its columns would only move
    # them.
    if len(lists) < 2:
        return [], {}
    column_sets = []
    for items in lists:
        seen: list[str] = []
        for row in items:
            for field in row:
                if field not in seen:
                    seen.append(field)
        column_sets.append(seen)
    if any("crs" not in columns for columns in column_sets):
        return [], {}
    common = [
        field for field in column_sets[0]
        if field != "crs" and all(field in columns for columns in column_sets[1:])
    ]
    by_station: dict[str, dict[str, str]] = {}
    placed = []
    for field in common:
        agreed = True
        values: dict[str, str] = {}
        for items in lists:
            for row in items:
                crs = row.get("crs")
                if not isinstance(crs, str):
                    agreed = False
                    break
                key = _pool_key(row.get(field))
                if values.setdefault(crs, key) != key:
                    agreed = False
                    break
            if not agreed:
                break
        if agreed:
            placed.append(field)
    for items in lists:
        for row in items:
            entry = by_station.setdefault(row["crs"], {})
            for field in placed:
                entry[field] = row.get(field)
    return placed, by_station


def encode_payload(payload: dict) -> dict:
    """The payload in the form a page ships (ADR-0069).

    Each row list is a column list and a table of cells. The fare lists then
    share what is the station's rather than the fare's: a column every list
    agrees on for a station is sent once in ``places`` and left out of the
    rows. A row's railcard decisions and tickets are packed by orders declared
    once in ``rowCodec``. Values that still repeat are sent once in the
    page-level pool and referred to by a negative index.

    The page hydrates all of it back into the objects the build wrote, field
    for field and in the same order, so no reader of the page changes.
    """
    tables = {
        key: payload[key]
        for key in ROW_LISTS
        if isinstance(payload.get(key), list) and payload[key]
    }
    if not tables:
        return payload

    railcard_codec = _railcard_codec(tables)
    ticket_codec = _ticket_codec(tables)
    placed, by_station = _placed_columns(tables)
    codec: dict[str, object] = {}
    if railcard_codec:
        codec["railcards"] = railcard_codec
    if ticket_codec:
        codec["tickets"] = {"columns": ticket_codec["columns"], "packed": ticket_codec["packed"]}
        if ticket_codec["names"] is not None:
            codec["tickets"]["names"] = ticket_codec["names"]

    packed_departures = False

    def pack_departures_in(row: dict) -> dict:
        nonlocal packed_departures
        if "departures" not in row:
            return row
        out = dict(row)
        options = out["departures"]
        packed = _pack_departures(options)
        if packed is not options:
            out["departures"] = packed
            packed_departures = True
        return out

    def packed_row(key: str, row: dict) -> dict:
        if key not in FARE_LISTS:
            return row
        out = dict(row)
        if railcard_codec and "railcards" in out:
            out["railcards"] = _pack_railcards(out["railcards"], railcard_codec)
        if ticket_codec and "tickets" in out:
            out["tickets"] = _pack_tickets(out["tickets"], ticket_codec)
        return pack_departures_in(out)

    # The place's own fields travel through the same packing, because a
    # departure option's keys are no cheaper for having been sent once per
    # station rather than once per row.
    by_station = {crs: pack_departures_in(entry) for crs, entry in by_station.items()}

    packed_tables = {
        key: [packed_row(key, row) for row in items] for key, items in tables.items()
    }
    placed_set = set(placed)

    def row_values(key: str, row: dict, columns: list[str]):
        for field in columns:
            if key in FARE_LISTS and field in placed_set:
                continue
            yield row.get(field)

    columns_by_key: dict[str, list[str]] = {}
    for key, items in packed_tables.items():
        columns: list[str] = []
        for row in items:
            for field in row:
                if field not in columns:
                    columns.append(field)
        columns_by_key[key] = columns

    # A party price of two adults is twice the adult price on every row the
    # build writes, so the page can multiply rather than carry it: 27 KB of the
    # Grantham page's 1.3 MB. It is only left out when the relation holds on
    # every row of every fare list and the adult column comes first, which is
    # what lets the page read it back in the place the row wrote it.
    def party_is_double(row: dict) -> bool:
        adult = row.get("adultPence")
        return (
            isinstance(adult, int)
            and not isinstance(adult, bool)
            and row.get("partyPence") == adult * 2
        )

    fare_rows = [row for key in FARE_LISTS for row in packed_tables.get(key, [])]
    party_from_adult = bool(fare_rows) and all(party_is_double(row) for row in fare_rows)
    party_from_adult = party_from_adult and all(
        "adultPence" in columns
        and columns.index("adultPence") < columns.index("partyPence")
        for key, columns in columns_by_key.items()
        if key in FARE_LISTS and "partyPence" in columns
    )

    # Each column's own dictionary is decided before the page's pool is built,
    # because a cell that has already become an index is a number, and a number
    # is neither poolable nor distinguishable from a real one.
    dictionary_rows: dict[str, list[list[object]]] = {}
    dictionaries_by_key: dict[str, dict[str, list[object]]] = {}
    derived_by_key: dict[str, list[str]] = {}
    for key, items in packed_tables.items():
        # A table that carries ``placed`` columns leaves them out of its cells;
        # the picker's list carries none, so its cells are all of its columns.
        skip = placed_set if key in FARE_LISTS else set()
        own = [field for field in columns_by_key[key] if field not in skip]
        if party_from_adult and key in FARE_LISTS and "partyPence" in own:
            own = [field for field in own if field != "partyPence"]
            derived_by_key[key] = ["partyPence"]
        rows = [list(row_values(key, row, own)) for row in items]
        dictionaries_by_key[key] = _column_dictionaries(own, rows)
        dictionary_rows[key] = rows

    place_dictionary_rows = {
        crs: [entry.get(field) for field in placed] for crs, entry in by_station.items()
    }
    place_dictionaries = _column_dictionaries(placed, list(place_dictionary_rows.values()))

    def poolable(value: object) -> bool:
        return isinstance(value, (dict, list)) or (
            isinstance(value, str) and len(value) >= POOL_MIN_BYTES
        )

    counts: dict[str, int] = {}
    materialized_rows: dict[str, list[list[tuple[object, str | None]]]] = {}
    materialized_places: dict[str, list[tuple[object, str | None]]] = {}
    first_seen: list[tuple[str, object]] = []

    def record(value: object) -> tuple[object, str | None]:
        """The cell as it travels, and the pool key it shares or None."""
        if poolable(value):
            k = _pool_key(value)
            count = counts.get(k, 0) + 1
            counts[k] = count
            if count == 1:
                first_seen.append((k, value))
            return value, k
        return value, None

    for crs, cells in place_dictionary_rows.items():
        materialized_places[crs] = [record(value) for value in cells]

    # The places table is counted into the same pool as the rows. A place's
    # columns were the largest single item on a .FSC-priced page -- 806 KB of
    # the Grantham page's 1.3 MB, of which 272 KB was the same ticket link
    # repeated 2,752 times -- because only the row tables ever asked the pool
    # for a value. A place is not part of a fare, which is the reason it moved
    # out of the rows (ADR-0069), not a reason its repeated values should be
    # beyond the pool's reach.
    for key, rows in dictionary_rows.items():
        materialized_rows[key] = [[record(value) for value in cells] for cells in rows]

    # A referenced value has to be worth referencing. Sharing a value that
    # repeats n times costs one copy of it plus n references, against n copies
    # of it: an empty list or a short boolean is two bytes and a reference into
    # a 700-entry pool is four, so pooling every repeated value made the places
    # table of a .FSC-priced page *larger* (empty site lists, 2,752 of them).
    # The index length is settled by the pool's own size, which is only known
    # once the entries are chosen, so the decision repeats until it stops
    # dropping entries -- two rounds in practice, and never more than three.
    candidates = [(k, value) for k, value in first_seen if counts[k] > 1]
    for _ in range(3):
        pool = {k: position for position, (k, _value) in enumerate(candidates)}
        values = [value for _k, value in candidates]
        kept = [
            (k, value)
            for k, value in candidates
            if (counts[k] - 1) * _wire_bytes(value) > counts[k] * (len(str(-(pool[k] + 1))) + 1)
        ]
        if len(kept) == len(candidates):
            break
        candidates = kept
    pool = {k: position for position, (k, _value) in enumerate(candidates)}
    values = [value for _k, value in candidates]

    def cell(value: object, k: str | None) -> object:
        # A pool reference is a negative index, so it cannot be confused with
        # a real cell: -1 is the pool's first entry, and null stays null.
        position = pool.get(k) if k is not None else None
        return -(position + 1) if position is not None else value

    def table_rows(key: str) -> list[list[object]]:
        return [
            [cell(value, k) for value, k in row_cells]
            for row_cells in materialized_rows[key]
        ]

    encoded = dict(payload)
    for key in packed_tables:
        table: dict[str, object] = {
            "columns": columns_by_key[key],
            "rows": table_rows(key),
        }
        if dictionaries_by_key[key]:
            table["dicts"] = dictionaries_by_key[key]
        if derived_by_key.get(key):
            table["derived"] = derived_by_key[key]
        if key in FARE_LISTS and placed:
            table["placed"] = [field for field in columns_by_key[key] if field in placed_set]
        encoded[key] = table
    if placed:
        place_table: dict[str, object] = {
            "columns": placed,
            "rows": {
                crs: [cell(value, k) for value, k in cells]
                for crs, cells in materialized_places.items()
            },
        }
        if place_dictionaries:
            place_table["dicts"] = place_dictionaries
        encoded["places"] = place_table
    if packed_departures:
        codec["departures"] = list(DEPARTURE_COLUMNS)
    if codec:
        encoded["rowCodec"] = codec
    if values:
        encoded["pool"] = values
    if "serviceWeek" in encoded:
        encoded["serviceWeek"] = _pack_service_week(encoded["serviceWeek"])
    return encoded


def _unpack_railcards(value: object, codec: dict | None) -> object:
    if not codec or not isinstance(value, list):
        return value
    out = {}
    for card, packed in zip(codec["cards"], value):
        if isinstance(packed, list):
            out[card] = {
                "state": codec["states"][packed[0]],
                "pricePence": packed[1],
                "minimumFarePence": packed[2],
                "rule": None if packed[3] is None else str(packed[3]),
            }
    return out


def _unpack_tickets(value: object, codec: dict | None) -> object:
    if not codec or not isinstance(value, list):
        return value
    named = {"fromName": "fromCrs", "toName": "toCrs"}
    out = []
    for packed in value:
        if not isinstance(packed, list):
            out.append(packed)
            continue
        ticket, cells = {}, iter(packed)
        for field in codec["columns"]:
            if codec.get("names") and field in named:
                ticket[field] = codec["names"][ticket[named[field]]]
            else:
                ticket[field] = next(cells)
        out.append(ticket)
    return out


def decode_payload(payload: dict) -> dict:
    """The payload as the page reads it: each row table turned back into objects.

    The build ships a row list as a column list and a table of cells, with the
    station's own columns placed once per station and railcards and tickets
    packed (ADR-0069); the page hydrates them as it loads, so a test that read
    the wire text directly would be asserting a shape no reader of the page
    ever sees. This mirrors ``hydrate`` in page/station/payload.js, and is
    the inverse of ``encode_payload`` above: the release's known-fares check
    reads built pages through it, and the page tests read them the same way.
    """
    pool = payload.get("pool") or []
    codec = payload.get("rowCodec") or {}
    places = payload.get("places") or {"columns": [], "rows": {}}
    place_dicts = places.get("dicts") or {}
    place_at = {column: index for index, column in enumerate(places.get("columns") or [])}

    def value(cell):
        return pool[-cell - 1] if isinstance(cell, int) and not isinstance(cell, bool) and cell < 0 else cell

    def place_cell(station: dict | list, column: str):
        """One of a place's columns, through the pool and its dictionary."""
        if not station or column not in place_at:
            return None
        cell = value(station[place_at[column]])
        return place_dicts[column][cell] if column in place_dicts else cell

    for key in ("destinations", "singleDestinations", "anytimeDestinations", "stations"):
        table = payload.get(key)
        if not (isinstance(table, dict) and isinstance(table.get("rows"), list)):
            continue
        placed = set(table.get("placed") or [])
        dictionaries = table.get("dicts") or {}
        derived = set(table.get("derived") or [])
        own = [column for column in table["columns"] if column not in placed]
        rows = []
        for cells in table["rows"]:
            station = places["rows"].get(value(cells[own.index("crs")])) if placed else None
            row, at = {}, 0
            for column in table["columns"]:
                if column in placed:
                    cell = place_cell(station, column)
                    if column == "departures":
                        cell = _unpack_departures(cell, codec.get("departures"))
                    row[column] = cell
                    continue
                if column in derived:
                    adult = row.get("adultPence")
                    row[column] = adult * 2 if isinstance(adult, int) else None
                    continue
                cell = value(cells[at])
                at += 1
                if column in dictionaries:
                    cell = dictionaries[column][cell]
                elif column == "railcards":
                    cell = _unpack_railcards(cell, codec.get("railcards"))
                elif column == "tickets":
                    cell = _unpack_tickets(cell, codec.get("tickets"))
                elif column == "departures":
                    cell = _unpack_departures(cell, codec.get("departures"))
                row[column] = cell
            rows.append(row)
        payload[key] = rows
    if "serviceWeek" in payload:
        payload["serviceWeek"] = _unpack_service_week(payload["serviceWeek"])
    for key in ("pool", "places", "rowCodec"):
        payload.pop(key, None)
    return payload
