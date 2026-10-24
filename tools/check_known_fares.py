"""Refuse a release whose page disagrees with a fare a person checked by hand.

    python -m tools.check_known_fares --site _site
    python -m tools.check_known_fares --site _site --table tests/known_fares.toml

Three times a published fare was one National Rail does not sell, and each was
found by hand against the journey planner: Grantham to Nottingham with a Two
Together railcard 10p over (#149), Grantham to Skegness at £6.60 against £8.70
(#179), and two people with Two Together to Skegness at £8.80 against £12.70
(#421). The rule from 8 October (F7) adds a synthetic record after a defect is
found, which cannot catch the first wrong fare: the fixture only holds cases
already known. `tests/known_fares.toml` holds the checked prices themselves --
expected prices, no feed data, so it stays inside ADR-0005 -- and this reads
the built page for each row and compares (task 2 of the 21 October 2026
re-architecture audit).

The page's price is computed the way page/station/railcards.js `priceOf` and
page/station/ticket-modes.js `cheapestDestinations` compute it, over the payload
decoded by `build_payload.decode_payload`: the party's standard fare, or the
card's price for each traveller when the card covers the party and is cheaper.

A row older than MAX_AGE_DAYS warns rather than fails: fares change every
March, and a stale row is a prompt to check it again, not proof the page is
wrong. A row whose page, railcard or mode is missing fails, because a check that
cannot find its subject has checked nothing.

A destination is the one exception, and only where the page says why it is
absent. Two rules narrow a page by design: ADR-0076 drops the places no journey
reaches within ``maxChanges``, and ADR-0077 stops at the cheapest places it
lists. Each carries its own count in the payload, so a hand-checked fare to one
of those places is a fare the page does not list on purpose. That row warns and
names the rule, because failing it would hold every release on a price the page
never showed and the only cure a person has is to delete the row, which loses
the check. A page that reports it left nothing out has lost a fare the feed
prices, and that still fails.

Exit codes: 0 every row agrees, or is absent only where the page says why it is
absent (a warning, and the last line counts those rows apart so a release cannot
read "all" when some had no price to compare); 1 a row disagrees, or the page
could not answer it, or every row is one of those explained absences so nothing
was compared; 2 the table or the site could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from build_assets import STATION_INDEX_MARKER
from build_payload import decode_payload
from page_templates import PAYLOAD_MARKER

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "tests" / "known_fares.toml"
MAX_AGE_DAYS = 90

#: The words that mark a row the page had no price for, said once so the last
#: line can count them: a release that names the rows it checked cannot claim
#: that every row agreed.
UNCHECKED = "no price on the page to check"

#: The page's ticket modes and the payload list each one shows
#: (MODE_LISTS in page/station/ticket-modes.js). "cheapest" is all three.
MODE_LISTS = {
    "return": ("destinations",),
    "single": ("singleDestinations",),
    "anytime": ("anytimeDestinations",),
    "cheapest": ("destinations", "singleDestinations", "anytimeDestinations"),
}


@dataclass(frozen=True)
class KnownFare:
    origin: str
    destination: str
    mode: str
    adults: int
    railcard: str
    pence: int
    seen_on: date
    link: str
    report: str

    def __str__(self) -> str:
        card = f" with {self.railcard}" if self.railcard else ""
        who = "one adult" if self.adults == 1 else "two adults"
        return f"{self.report} {self.origin} to {self.destination}, {self.mode}, {who}{card}"


def read_table(path: Path) -> list[KnownFare]:
    """The table's rows, refusing one the page could not answer."""
    rows = []
    for number, raw in enumerate(tomllib.loads(path.read_text(encoding="utf-8")).get("fare", []), 1):
        row = KnownFare(
            origin=raw["origin"].upper(),
            destination=raw["destination"].upper(),
            mode=raw["mode"],
            adults=int(raw["adults"]),
            railcard=raw.get("railcard", ""),
            pence=int(raw["pence"]),
            seen_on=raw["seen_on"],
            link=raw["link"],
            report=raw.get("report", f"row {number}"),
        )
        if row.mode not in MODE_LISTS:
            raise ValueError(f"row {number}: mode {row.mode!r} is not one of {', '.join(MODE_LISTS)}")
        if row.adults not in (1, 2):
            raise ValueError(f"row {number}: the page prices one adult or a party of two, not {row.adults}")
        if not isinstance(row.seen_on, date):
            raise ValueError(f"row {number}: seen_on must be a date, as 2026-10-05")
        rows.append(row)
    if not rows:
        raise ValueError(f"{path} holds no [[fare]] row, so there is nothing to check")
    return rows


def station_pages(site: Path) -> dict[str, Path]:
    """CRS to station page, from the station index every page loads.

    The asset holds two documents since ADR-0069's amendment: the picker's
    options, then every station's own facts. This reads the options and stops
    there. Reading to the end of the file instead parsed the facts as data after
    the options and refused the whole release -- ``Extra data: line 1 column
    233653`` in the 24 October 2026 assemble job, one character after the
    options' closing bracket.
    """
    asset = site / "stations.js"
    text = asset.read_text(encoding="utf-8")
    if STATION_INDEX_MARKER not in text:
        raise ValueError(f"{asset} carries no station index, so the release's pages cannot be found")
    stations = json.JSONDecoder().raw_decode(text.split(STATION_INDEX_MARKER, 1)[1])[0]
    pages = {}
    for station in stations:
        slug = re.search(r"/from/([^/]+)/$", station["href"])
        if slug:
            pages[station["crs"]] = site / "from" / slug.group(1) / "index.html"
    return pages


def page_payload(page: Path) -> dict:
    html = page.read_text(encoding="utf-8")
    match = re.search(re.escape(PAYLOAD_MARKER) + r"(\{.*?\});\n", html, re.DOTALL)
    if match is None:
        raise ValueError(f"{page} carries no embedded payload")
    return decode_payload(json.loads(match.group(1)))


def page_price(payload: dict, row: KnownFare) -> int | str | None:
    """What the page shows for the row, in pence, or why it shows nothing.

    ``None`` means the page carries no fare of the row's kind for the place,
    which is the answer ``modes_listing`` reads: a place absent from every list
    may be one the page dropped by rule, and one absent from a single list is
    not.
    """
    party = row.adults == 2
    card = None
    if row.railcard:
        offered = {entry["key"]: entry for entry in payload.get("railcards") or []}
        card = offered.get(row.railcard)
        if card is None:
            return f"the page offers no {row.railcard} railcard"
        if not card["minAdults"] <= row.adults <= card["maxAdults"]:
            return f"{row.railcard} does not cover {row.adults} adult(s) on the page"
    prices = []
    for key in MODE_LISTS[row.mode]:
        for destination in payload.get(key) or []:
            if destination["crs"] != row.destination:
                continue
            price = destination["partyPence" if party else "adultPence"]
            decision = (destination.get("railcards") or {}).get(row.railcard) if card else None
            if decision and decision.get("pricePence") is not None:
                price = min(price, decision["pricePence"] * (2 if party else 1))
            prices.append(price)
    return min(prices) if prices else None


def modes_listing(payload: dict, crs: str) -> list[str]:
    """The page's ticket modes that list the place, in the table's own words."""
    return [
        mode
        for mode in ("return", "single", "anytime")
        if any(destination["crs"] == crs for destination in payload.get(MODE_LISTS[mode][0]) or [])
    ]


def _places(count: int) -> str:
    return f"{count:,} place" if count == 1 else f"{count:,} places"


def left_out(payload: dict) -> str:
    """What the page says it did not list, or "" when it left nothing out.

    The two narrowing rules each keep their own count, so the sentence says
    which bound put the place beyond the page rather than guessing: a place no
    journey reaches is not on the page because there is nothing to travel to,
    and a place past the cap is on the feed at a fare dearer than the page's
    stop.
    """
    clauses = []
    unreachable = payload.get("unreachableDestinationCount") or 0
    if unreachable:
        # The page's own journeyLimitPhrase words the bound, because a warning
        # that named a different one would describe a rule the build did not
        # use: no changes allowed reads "on a direct train", and a payload with
        # no week carries no bound at all.
        changes = payload.get("maxChanges")
        if changes == 0:
            limit = " on a direct train"
        elif changes:
            limit = " within one change" if changes == 1 else f" within {changes} changes"
        else:
            limit = ""
        reaches = "it" if unreachable == 1 else "them"
        clauses.append(
            f"it leaves {_places(unreachable)} out because no journey from here reaches {reaches}{limit}"
        )
    capped = payload.get("cappedDestinationCount") or 0
    if capped:
        clauses.append(f"it stops before {_places(capped)} dearer than the ones it lists")
    return "; ".join(clauses)


def check(site: Path, rows: list[KnownFare], today: date) -> tuple[list[str], list[str]]:
    """(failures, warnings), one line each."""
    failures, warnings = [], []
    pages = station_pages(site)
    payloads: dict[str, dict] = {}
    for row in rows:
        age = (today - row.seen_on).days
        if age > MAX_AGE_DAYS:
            warnings.append(f"{row}: checked {age} days ago ({row.seen_on}); check it again at {row.link}")
        page = pages.get(row.origin)
        if page is None or not page.is_file():
            failures.append(f"{row}: the site has no page for {row.origin}")
            continue
        if row.origin not in payloads:
            payloads[row.origin] = page_payload(page)
        payload = payloads[row.origin]
        shown = page_price(payload, row)
        modes = modes_listing(payload, row.destination) if shown is None else []
        dropped = left_out(payload) if shown is None and not modes else ""
        if isinstance(shown, str):
            failures.append(f"{row}: {shown}")
        elif shown is None and dropped:
            warnings.append(
                f"{row}: the page lists no {row.destination} in any of its fare lists, and {dropped}, "
                f"so there is {UNCHECKED}; check the fare at {row.link} and retire the row if it is gone"
            )
        elif shown is None and modes:
            failures.append(
                f"{row}: the page shows no {row.mode} fare to {row.destination}, though it lists the "
                f"place in its {' and '.join(modes)} fares"
            )
        elif shown is None:
            failures.append(
                f"{row}: the page lists no {row.destination} in any of its fare lists, and left no place "
                f"out, so nothing on the page explains the absence; check the fare at {row.link}, then "
                "correct the page or retire the row"
            )
        elif shown != row.pence:
            failures.append(
                f"{row}: the page shows £{shown / 100:.2f}, and National Rail sold £{row.pence / 100:.2f} "
                f"on {row.seen_on} ({row.link})"
            )
    return failures, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", type=Path, default=ROOT / "_site")
    parser.add_argument("--table", type=Path, default=TABLE)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today(), help="for a test: the date to age rows from")
    args = parser.parse_args(argv)
    try:
        rows = read_table(args.table)
        failures, warnings = check(args.site, rows, args.today)
    except (OSError, ValueError, KeyError) as problem:
        print(f"the known fares could not be checked: {problem}", file=sys.stderr)
        return 2
    for line in warnings:
        print(f"::warning title=known fare::{line}")
    for line in failures:
        print(f"::error title=known fare::{line}")
    if failures:
        return 1
    unchecked = sum(1 for line in warnings if UNCHECKED in line)
    if unchecked == len(rows):
        # The module's own rule, applied to the table rather than to a row: a
        # check that cannot find any of its subjects has checked nothing, and a
        # release whose fare gate compared no price at all must not read green.
        print(
            "::error title=known fare::every row is for a place its page left out by rule, so not one "
            "price was compared; add a row for a place the page lists"
        )
        return 1
    if unchecked:
        print(
            f"{len(rows) - unchecked} of {len(rows)} known fare(s) agree with the pages; "
            f"{unchecked} could not be checked here"
        )
    else:
        print(f"all {len(rows)} known fare(s) agree with the pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
