"""Check whether a seller's ticket link lands on a search the reader can use.

A declared parameter is a claim about a page. This is the check that the link
works, and it exists because those two things came apart: the National Rail link
declares station-code parameters and its live search returns no journeys anyway
(adr/ADR-0017-what-the-live-link-check-found.md).

**What this tool will not do:** it never reports a link as working. It has never
seen a working seller page, so it does not know what one looks like, and a marker
invented for one would make the tool lie in the direction that matters. It reports
what a response *proves*:

- ``no_journeys``  the page loaded and said there are no journeys, outside any
                   script element. Proven bad.
- ``http_error``   the seller answered with an error, or did not answer. Proven bad.
- ``blocked``      the seller refused an automated visitor. Proven nothing; a
                   person has to open it.
- ``inconclusive`` the page loaded and said nothing this check can read.

Only ``no_journeys`` and ``http_error`` are failures. ``blocked`` and
``inconclusive`` both mean **unverified**, which is why the publish checklist has a
box that says a human opened the link. That box cannot be ticked from here.

Etiquette: one request per seller, no retries, no crawling, and nothing is read
out of a response beyond which kind of page it is. This does not harvest fares,
and it must not grow into something that does.

    python check_links.py
    python check_links.py --provider trainline --origin GRA --destination NOT
    python check_links.py --mode fallback
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from datetime import date


from retailer import PROVIDERS, ticket_link

TIMEOUT_SECONDS = 20
# Identifies the check so a seller's logs say what knocked.
USER_AGENT = "train-budget-explorer-link-check/1.0 (one request per seller)"

BLOCKED = "blocked"
HTTP_ERROR = "http_error"
NO_JOURNEYS = "no_journeys"
INCONCLUSIVE = "inconclusive"

# Every phrase below was read off a real failure on 22 September 2026, and none
# was invented. The list only grows from an observed page, because a marker that
# condemns a working link is the same class of mistake as passing a broken one:
# both put a wrong answer in front of a reader.
#
# The sellers declined to be checked by a program.
BLOCK_MARKERS = (
    "temporarily restricted",
    "prevent misuse by automated bots",
    "captcha-delivery",
)

# The page ran a search and found nothing. This is the failure this project keeps
# trying to make impossible: a reader cannot tell it apart from "there are no
# trains", and neither can the reader's trust afterwards.
#
# Script elements are dropped before these are looked for. An app ships its own
# error vocabulary: National Rail's shell carries "No matching journeys found" in
# a journeyPlannerErrorsMicrocopy dictionary on every response -- measured 9
# October 2026, three different queries answered byte-for-byte by the same shell,
# the query never echoed. Matching that reads the programme's strings, not the
# search's answer, and a failure proved that way is a false one. Markup outside
# scripts is still read, so a server that renders the error into the page is
# still caught. An open script with no close runs to the end of what was read:
# the `__NEXT_DATA__` block that holds the dictionary opens at byte 82,334 and
# the body ends inside it, so a pattern that needs `</script>` stops stripping
# exactly where the strings are. The cost of reading an open script to the end
# is the other direction: markup below one is not read either, so a server that
# renders the error under an unclosed script would be missed. Unverified rather
# than condemned -- the one direction this tool is allowed to be wrong in.
SCRIPT_ELEMENT = re.compile(
    r"<script\b[^>]*>.*?(?:</script>|$)", re.IGNORECASE | re.DOTALL
)

NO_RESULT_MARKERS = ("no matching journeys",)

# What each verdict means for a person, and what to do about it.
EXPLANATION = {
    NO_JOURNEYS: "the link produces a page that says there are no journeys. Do not publish it.",
    HTTP_ERROR: "the seller answered with an error or did not answer. Do not publish it.",
    BLOCKED: "the seller refused an automated visitor, so this link is unverified, not fine. Open it by hand.",
    INCONCLUSIVE: "the page loaded and said nothing this check can read. Open it by hand and look.",
}

# The verdicts that mean the link itself is broken, rather than unexamined.
FAILURES = frozenset({NO_JOURNEYS, HTTP_ERROR})


def classify(status: int, body: str) -> str:
    """Say what a response proves, and no more than it proves.

    Negative evidence outranks a quiet page: a refusal is reported before an
    error status, and a page that says it found no journeys is reported as such
    however healthy its status. Nothing reaching the end of these branches is
    evidence of a working search, which is why the last branch is a shrug.
    """
    lowered = body.lower()
    if any(marker in lowered for marker in BLOCK_MARKERS):
        return BLOCKED
    if status == 0 or status >= 400:
        return HTTP_ERROR
    if any(marker in SCRIPT_ELEMENT.sub("", lowered) for marker in NO_RESULT_MARKERS):
        return NO_JOURNEYS
    return INCONCLUSIVE


def fetch(url: str, *, timeout: int = TIMEOUT_SECONDS) -> tuple[int, str]:
    """Make the one request. A status of 0 means it never arrived."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en;q=0.9"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read(200_000).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as error:
        return 0, str(error)


def check(
    provider: str,
    origin: str,
    destination: str,
    *,
    when: date | None = None,
    adults: int = 2,
    mode: str = "deep",
    timeout: int = TIMEOUT_SECONDS,
    fetch_body=fetch,
) -> tuple[str, int, str]:
    """Build the link the page would build, open it once, and classify it.

    ``fetch_body`` is injectable so the verdicts can be tested without a network.
    """
    link = ticket_link(
        origin, destination, provider=provider, when=when, adults=adults, mode=mode
    )
    status, body = fetch_body(link.url, timeout=timeout)
    return link.url, status, classify(status, body)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether the ticket links land on a search. Reads no fares.",
    )
    parser.add_argument(
        "--provider",
        default=None,
        choices=sorted(PROVIDERS),
        help="seller to check. Default: every seller built",
    )
    parser.add_argument(
        "--origin",
        default="GRA",
        help="origin CRS code. Grantham's real code is GRA; the synthetic feed invents GRN",
    )
    parser.add_argument("--destination", default="NOT", help="destination CRS code")
    parser.add_argument("--date", default=None, help="service date as YYYY-MM-DD")
    parser.add_argument("--adults", type=int, default=2, help="party size in the link")
    parser.add_argument(
        "--mode",
        default="deep",
        choices=("deep", "fallback"),
        help="deep is the default here, because checking the parameterised link is "
        "the point; fallback is what the page sends readers to. See ADR-0018",
    )
    parser.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS, help="seconds per request")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)

    day: date | None = None
    if args.date:
        try:
            day = date.fromisoformat(args.date)
        except ValueError:
            print(f"date {args.date!r} is not YYYY-MM-DD", file=sys.stderr)
            return 2

    providers = [args.provider] if args.provider else sorted(PROVIDERS)
    print(f"one request per seller, {args.origin} to {args.destination}, mode {args.mode}")
    print()

    verdicts: dict[str, str] = {}
    for provider in providers:
        try:
            url, status, verdict = check(
                provider,
                args.origin,
                args.destination,
                when=day,
                adults=args.adults,
                mode=args.mode,
                timeout=args.timeout,
            )
        except (KeyError, ValueError) as error:
            print(f"{provider:<16} {error}")
            continue
        verdicts[provider] = verdict
        print(f"{provider:<16} {verdict:<14} http {status}")
        print(f"{'':<16} {url}")
        print(f"{'':<16} {EXPLANATION[verdict]}")
        print(f"{'':<16} recorded: {PROVIDERS[provider].verified or 'no check recorded'}")
        print()

    failures = sorted(p for p, v in verdicts.items() if v in FAILURES)
    unverified = sorted(p for p, v in verdicts.items() if v not in FAILURES)
    if failures:
        print(f"broken: {', '.join(failures)}")
    if unverified:
        print(f"unverified, not fine: {', '.join(unverified)} - a person must open these")
    if not failures and not unverified:
        print("nothing checked")
    print()
    print("this check can only prove a link is broken, never that it works.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
