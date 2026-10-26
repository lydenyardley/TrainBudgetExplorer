"""Reality-check the budget model against the real fares database.

Usage:
    EASY_FARES_KEY=... python -m tools.easy_fares_check

The free demo allows 100 calls per 30 days, so this script is deliberately
frugal: one call per origin-destination-railcard combination per day, responses
cached under _ef_cache/ with the fetch date in the filename (a re-run the same
day costs nothing; a later run fetches fresh prices rather than reporting old
ones as current). The key is read from the environment and never written to
disk. See adr/ADR-0022 for why the demo exists and what it is for: a check of
the model, not a data source.

Endpoint: the Rail Data Marketplace gateway publishes this product at
https://api1.raildata.org.uk/1080-easy-fares-api-v1/easy_fares and takes
the key in an ``x-apikey`` header. BR Fares' own gw.brfares.com answers
401 to marketplace credentials, and the gateway 403s Python's default
user-agent - both verified 2026-09-22.

Two quirks of the real responses shape the comparison:
  * the undiscounted group's railcard code is blank, not "PUBLIC" as the
    spec example shows;
  * requesting a railcard REPLACES the blank group with that railcard's
    group per fare, so the public and discounted prices of one fare come
    from two calls and are joined here by ticket code.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date
from fractions import Fraction
from pathlib import Path

BASE_URL = "https://api1.raildata.org.uk/1080-easy-fares-api-v1/easy_fares"
CACHE_DIR = Path("_ef_cache")
ROUNDING_STEP_PENCE = 5
RAILCARD_DISCOUNT = Fraction(2, 3)  # the model's documented assumption (ADR-0002)

# Grantham pairs that exercise different corners of the database. The real
# database's CRS for Grantham is GRA - the synthetic feed's GRN is
# Grindleford, and querying it would compare the wrong station.
ROUTES = [
    ("GRA", "KGX", None),
    ("GRA", "YRK", None),
    ("GRA", "NWK", None),
    ("GRA", "LEI", None),
    ("GRA", "KGX", "YNG"),  # 16-25 Railcard: exercises the discount arithmetic
]


def _fetch(origin: str, destination: str, railcard: str | None, key: str) -> dict:
    """One API call, cached on disk with the date in the filename.

    The date is part of the cache identity, not a note inside it: a check run
    next week would otherwise silently report last week's prices as current,
    and the finding this script feeds is quoted on the page itself (audit C4).
    """
    stamp = date.today().isoformat()
    cache_path = CACHE_DIR / f"{origin}_{destination}_{railcard or 'none'}_{stamp}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    url = f"{BASE_URL}?orig={origin}&dest={destination}"
    if railcard:
        url += f"&rlc={railcard}"
    request = urllib.request.Request(
        url,
        headers={"x-apikey": key, "User-Agent": "TrainBudgetExplorer/0.1 (fares model check)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return body


def model_railcard_price(standard_pence: int) -> int:
    """The model's price: 1/3 off, rounded up to the next 5p."""
    value = standard_pence * RAILCARD_DISCOUNT
    units = -(-value.numerator // (value.denominator * ROUNDING_STEP_PENCE))
    return units * ROUNDING_STEP_PENCE


def collect_walkup(body: dict) -> dict[str, tuple[str, int, dict[str, int]]]:
    """Class-2 walk-up fares: ticket code -> (name, public price, all groups).

    The public price is the blank-code group. Returns one entry per ticket
    code - the database repeats a fare per route, and the price per route
    can differ, so the cheapest sighting of each code is the one a reader
    could actually buy.
    """
    fares: dict[str, tuple[str, int, dict[str, int]]] = {}
    for section in ("walkup", "payg"):
        for entry in body.get(section) or []:
            ticket = entry.get("ticket") or {}
            code = ticket.get("code")
            if not code or ticket.get("tclass") != 2:
                continue
            groups: dict[str, int] = {}
            for group in entry.get("discount_groups") or []:
                group_code = (group.get("railcard") or {}).get("code", "").strip()
                price = (group.get("adult") or {}).get("price")
                if price is not None:
                    groups[group_code] = int(price)
            if "" not in groups:
                continue
            public = groups[""]
            known = fares.get(code)
            if known is None or public < known[1]:
                fares[code] = (ticket.get("name", "?"), public, groups)
    return fares


def cheapest_return(body: dict) -> tuple[int, str] | None:
    """Cheapest class-2 return in a response, restricted groups included."""
    best: tuple[int, str] | None = None
    for section in ("walkup", "payg"):
        for entry in body.get(section) or []:
            ticket = entry.get("ticket") or {}
            if ticket.get("tclass") != 2 or not ticket.get("code", "").endswith("R"):
                continue
            for group in entry.get("discount_groups") or []:
                if (group.get("railcard") or {}).get("code", "").strip():
                    continue
                price = (group.get("adult") or {}).get("price")
                if price is None:
                    continue
                name = f"{ticket.get('name', '?')} ({section})"
                if best is None or price < best[0]:
                    best = (int(price), name)
    for entry in body.get("restricted") or []:
        if entry.get("tclass") == 2 and entry.get("min_price") is not None:
            # restricted fares are priced as a group sharing one validity:
            # the group minimum is the honest comparable figure
            name = "restricted group (advance-style)"
            if best is None or entry["min_price"] < best[0]:
                best = (int(entry["min_price"]), name)
    return best


def check_route(body: dict, label: str) -> None:
    orig = body.get("orig") or {}
    dest = body.get("dest") or {}
    print(f"\n{label}")
    print(f"  resolved: {orig.get('name', '?')} ({orig.get('crs', '?')}) -> "
          f"{dest.get('name', '?')} ({dest.get('crs', '?')})")
    if not orig or not dest:
        print("  !! origin or destination did not resolve; nothing to compare")
        return
    best = cheapest_return(body)
    if best:
        print(f"  cheapest real return: {best[0]}p - {best[1]}")
    else:
        print("  !! no class-2 return fares in the response")


def check_railcard(body_plain: dict, body_card: dict, railcard: str, label: str) -> None:
    """Compare the model's 1/3-off arithmetic with the database's own prices.

    The two responses are joined per ticket code: the public price comes
    from the no-card call, the discounted price from the card call.
    """
    plain = collect_walkup(body_plain)
    carded = collect_walkup(body_card)
    print(f"\n{label} - railcard arithmetic")
    compared = mismatches = 0
    worst = 0
    for code, (_, public, _) in sorted(plain.items()):
        discounted = carded.get(code, ({}, 0, {}))[2].get(railcard)
        if discounted is None:
            continue
        model = model_railcard_price(public)
        compared += 1
        delta = discounted - model
        if delta != 0:
            mismatches += 1
            worst = max(worst, abs(delta))
            print(f"  {code}: public {public}p - real {discounted}p vs model {model}p ({delta:+d}p)")
    verdict = "every discount matches" if mismatches == 0 else f"{mismatches}/{compared} differ, worst {worst}p"
    print(f"  {compared} fares compared: {verdict}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    key = os.environ.get("EASY_FARES_KEY", "")
    if not key:
        print("Set EASY_FARES_KEY in the environment.", file=sys.stderr)
        return 2

    bodies: dict[tuple[str, str, str | None], dict] = {}
    for origin, destination, railcard in ROUTES:
        label = f"{origin} -> {destination}" + (f" with railcard {railcard}" if railcard else "")
        try:
            bodies[(origin, destination, railcard)] = _fetch(origin, destination, railcard, key)
        except Exception as error:  # noqa: BLE001 - a network probe reports, not raises
            print(f"\n{label}: request failed: {error}")

    for (origin, destination, railcard), body in bodies.items():
        if railcard is None:
            check_route(body, f"{origin} -> {destination}")
    for (origin, destination, railcard), body in bodies.items():
        if railcard is not None:
            plain = bodies.get((origin, destination, None))
            if plain is not None:
                check_railcard(plain, body, railcard, f"{origin} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
