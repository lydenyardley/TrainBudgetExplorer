"""Reality-check the budget model against the real fares database.

Usage:
    EASY_FARES_KEY=... EASY_FARES_SECRET=... python easy_fares_check.py

The free demo allows 100 calls per 30 days, so this script is deliberately
frugal: one call per origin-destination pair, responses cached under
_ef_cache/ so a re-run costs nothing. Credentials are read from the
environment and never written to disk. See adr/ADR-0022 for why the demo
exists and what it is for: a check of the model, not a data source.

What is checked:
  1. Model fare choice: is the model's "cheapest standard-class return"
  actually the cheapest purchasable return the real database offers?
  2. Model railcard arithmetic: is the documented "1/3 off, rounded up to
  5p" assumption what the real database computes for the railcards the
  fare carries? The response includes discounted prices per railcard, so
  no railcard code needs to be guessed here.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from fractions import Fraction
from pathlib import Path

BASE_URL = "https://gw.brfares.com/easy_fares"
CACHE_DIR = Path("_ef_cache")
ROUNDING_STEP_PENCE = 5
RAILCARD_DISCOUNT = Fraction(2, 3)  # the model's documented assumption (ADR-0002)

# Grantham pairs that exercise different corners of the database: the ECML
# corridor, a cross-country run, a short hop, and a route with no direct
# service. Grantham is the project's origin of record (stage-1).
ROUTES = [
    ("GRN", "KGX"),
    ("GRN", "YRK"),
    ("GRN", "NWK"),
    ("GRN", "LEI"),
]


def _auth_header(key: str, secret: str) -> str:
    token = base64.b64encode(f"{key}:{secret}".encode()).decode()
    return f"Basic {token}"


def _fetch(origin: str, destination: str, key: str, secret: str) -> dict:
    cache_path = CACHE_DIR / f"{origin}_{destination}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    url = f"{BASE_URL}?orig={origin}&dest={destination}"
    request = urllib.request.Request(url, headers={"Authorization": _auth_header(key, secret)})
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


def public_price(fare: dict) -> int | None:
    """The undiscounted adult price of a fare, from its PUBLIC group."""
    for group in fare.get("discount_groups", []):
        if (group.get("railcard") or {}).get("code", "").strip() == "PUBLIC":
            price = (group.get("adult") or {}).get("price")
            if price is not None:
                return int(price)
    return None


def discounts(fare: dict) -> list[tuple[str, str, int]]:
    """(railcard code, railcard name, adult price) for each real discount."""
    out = []
    for group in fare.get("discount_groups", []):
        code = (group.get("railcard") or {}).get("code", "").strip()
        name = (group.get("railcard") or {}).get("name", "?")
        price = (group.get("adult") or {}).get("price")
        if code and code != "PUBLIC" and price is not None:
            out.append((code, name, int(price)))
    return out


def check_route(body: dict, label: str) -> None:
    orig = body.get("orig") or {}
    dest = body.get("dest") or {}
    print(f"\n{label}")
    print(f"  resolved: {orig.get('name', '?')} ({orig.get('crs', '?')}) -> "
          f"{dest.get('name', '?')} ({dest.get('crs', '?')})")
    if not orig or not dest:
        print("  !! origin or destination did not resolve; nothing to compare")
        return

    cheapest: dict[str, tuple[int, str]] = {}
    for group_name in ("walkup", "payg", "restricted"):
        for entry in body.get(group_name) or []:
            if group_name == "restricted":
                # restricted fares are priced as a group sharing one validity:
                # the group minimum is the honest comparable figure
                if entry.get("tclass") == 2 and entry.get("min_price") is not None:
                    current = cheapest.get("RETURN")
                    if current is None or entry["min_price"] < current[0]:
                        cheapest["RETURN"] = (int(entry["min_price"]),
                                              f"restricted group (advance-style, min {entry.get('min_price')}p)")
            else:
                ticket = entry.get("ticket") or {}
                price = public_price(entry)
                if price is None or ticket.get("tclass") != 2:
                    continue
                if ticket.get("code", "").endswith("R"):  # returns only, like the model
                    name = f"{ticket.get('name', '?')} ({group_name})"
                    current = cheapest.get("RETURN")
                    if current is None or price < current[0]:
                        cheapest["RETURN"] = (price, name)
                elif ticket.get("code", "").endswith("S"):
                    name = f"{ticket.get('name', '?')} ({group_name})"
                    current = cheapest.get("SINGLE")
                    if current is None or price < current[0]:
                        cheapest["SINGLE"] = (price, name)

    for kind in ("RETURN", "SINGLE"):
        if kind in cheapest:
            price, name = cheapest[kind]
            print(f"  cheapest real {kind.lower()}: {price}p - {name}")

    # Railcard arithmetic: compare every discounted price the real database
    # returned against the model's 1/3-off assumption on the same fare.
    compared = mismatches = 0
    for group_name in ("walkup", "payg"):
        for entry in body.get(group_name) or []:
            public = public_price(entry)
            if public is None or (entry.get("ticket") or {}).get("tclass") != 2:
                continue
            for code, name, real in discounts(entry):
                model = model_railcard_price(public)
                compared += 1
                if real != model:
                    mismatches += 1
                    if mismatches <= 4:
                        delta = real - model
                        print(f"  railcard {code} ({name}) on {public}p fare: "
                              f"real {real}p vs model {model}p ({delta:+d}p)")
    print(f"  railcard arithmetic: {compared - mismatches}/{compared} discounts match the model")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    key = os.environ.get("EASY_FARES_KEY", "")
    secret = os.environ.get("EASY_FARES_SECRET", "")
    if not key or not secret:
        print("Set EASY_FARES_KEY and EASY_FARES_SECRET in the environment.", file=sys.stderr)
        return 2

    for origin, destination in ROUTES:
        label = f"{origin} -> {destination}"
        try:
            body = _fetch(origin, destination, key, secret)
        except Exception as error:  # noqa: BLE001 - a network probe reports, not raises
            print(f"\n{label}: request failed: {error}")
            continue
        check_route(body, label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
