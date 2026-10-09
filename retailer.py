"""Build outbound ticket links without pretending to know a journey.

Two questions decide what a link may carry: what the retailer's search URL
accepts, and what this tool actually knows. The tool knows an origin, a
destination, a date if it was given, and a party size. It does not know which
train the reader wants, and it must not imply one.

So a link sends the search, not the journey:

- **sent**: origin code, destination code, date, number of adults, when the
  retailer's URL declares it accepts them
- **not sent**: railcard, because no retailer documents a parameter for it, and a
  wrong railcard silently changes the price the reader sees; the page says so
  instead
- **not sent**: any journey or departure, because the price this tool found is a
  walk-up fare that exists on every train that day, and picking one for the
  reader would invent a decision

Affiliate tracking is a wrapper around a finished URL, not a query parameter,
because that is how the networks work: Awin's cread.php and Partnerize's
prf.hn/click both redirect to a destination you hand them. That means turning
monetisation on cannot change the search the reader lands on, and it cannot
break a link that already worked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from urllib.parse import quote, urlencode

PLAIN_REL = "noopener"
AFFILIATE_REL = "noopener nofollow sponsored"

# What a reader is told before they click, when a link earns anything.
DISCLOSURE = "Links to ticket sellers may earn this site a commission. The price shown is not affected."


@dataclass(frozen=True)
class Provider:
    """A ticket seller's public search URL, and the parameters it accepts.

    ``params`` is a tuple of (url parameter name, value name this module
    supplies). A value name that is missing at build time drops the parameter,
    which is how a link is built without a date. Declaring the parameters rather
    than formatting a template means an unsupported parameter cannot be sent by
    accident.
    """

    key: str
    label: str
    base_url: str
    params: tuple[tuple[str, str], ...]
    note: str
    # The network that is known to run this seller's programme, or None where it
    # is not known. Used only to warn about a pairing that could never track.
    usual_network: str | None = None
    # What a live check of this link found, and when. A provider without a
    # recorded check is one nobody has opened, which is a different claim from
    # one that was opened and worked.
    verified: str = ""
    # The seller's own search page, with no query on it. This is the link to
    # send a reader to when the parameterised one is not known to work: a worse
    # link that lands on a form is better than a good link that lands on
    # "no journeys". See adr/ADR-0017-what-the-live-link-check-found.md.
    fallback_url: str = ""

    def url(self, values: dict[str, str]) -> str:
        pairs = [(name, values[value]) for name, value in self.params if values.get(value)]
        query = urlencode(pairs, quote_via=quote)
        return f"{self.base_url}?{query}" if query else self.base_url


# The URLs are public search pages, and the parameters below are the ones each
# page declares. Declaring a parameter is not the same as the link working, and
# the live check on 22 September 2026 found that neither link can currently be
# relied on to land on a search the reader can use:
#
# - **national_rail**: in a browser the results page renders, then reports "No
#   matching journeys found" for every query tried on 22 September 2026,
#   including King's Cross to Edinburgh -- all of them `leavingType=departAfter`
#   variants. Corrected 9 October 2026: a browser accepts `leavingType=departing`
#   with the date as DDMMYY, a time and adults (journeys render -- Grantham to
#   Nottingham, 16 October 2026, from £24.00), while the bare request was never
#   answering at all: its "No matching journeys" is this planner's own error
#   dictionary inside script elements, in a shell that does not vary with the
#   query. `check_links.py` now ignores markers inside scripts. The shape that
#   searches is recorded here but not sent, because sending a time picks a
#   departure and that is a link-payload decision, not a parameter one.
# - **trainline**: the site served a bot check and refused the search request,
#   so nothing about this link is confirmed either way.
#
# adr/ADR-0017-what-the-live-link-check-found.md records both checks, every variant
# tried, and what would make these links trustworthy.
PROVIDERS: dict[str, Provider] = {
    "national_rail": Provider(
        key="national_rail",
        label="National Rail",
        base_url="https://www.nationalrail.co.uk/journey-planner/",
        params=(
            ("type", "single"),
            ("origin", "origin"),
            ("destination", "destination"),
            ("leavingType", "depart_after"),
            ("leavingDate", "date_compact"),
        ),
        note="The industry's own journey planner. It takes station codes in the URL, but its live search does not return journeys through them.",
        verified="checked 2026-09-22: results page loads, every query reports no journeys; 2026-10-09: the bare request proves nothing either way, the error text was the app's own",
        fallback_url="https://www.nationalrail.co.uk/journey-planner/",
    ),
    "trainline": Provider(
        key="trainline",
        label="Trainline",
        base_url="https://www.thetrainline.com/book/results",
        params=(
            ("origin", "origin"),
            ("destination", "destination"),
            ("outwardDate", "date_iso"),
            ("outwardDateType", "depart_after"),
            ("journeySearchType", "single"),
            ("passengers[]", "adults"),
        ),
        note="Largest UK retailer, and the one whose affiliate programme is best documented.",
        usual_network="partnerize",
        verified="not checked: the live site refused an automated search",
        fallback_url="https://www.thetrainline.com/",
    ),
}


def pairing_warning(provider: str, network: str | None) -> str | None:
    """Say when a seller and a network cannot be right together.

    Linking a seller through a network that does not run their programme produces
    a working link that earns nothing, which is the kind of mistake nobody
    notices for a year.
    """
    if not network:
        return None
    chosen = PROVIDERS.get(provider)
    if chosen is None or chosen.usual_network is None:
        return None
    if chosen.usual_network != network:
        return (
            f"{chosen.label} is sold through {chosen.usual_network}, not {network}: "
            "the links would work and earn nothing."
        )
    return None

DEFAULT_PROVIDER = "national_rail"


@dataclass(frozen=True)
class AffiliateNetwork:
    """A tracked redirect that wraps a finished destination URL."""

    key: str
    label: str
    rewrite: str
    note: str = ""

    def wrap(self, destination: str, *, advertiser_id: str, publisher_id: str = "") -> str:
        return self.rewrite.format(
            advertiser=quote(advertiser_id, safe=""),
            publisher=quote(publisher_id, safe=""),
            # The destination is escaped whole: it is a URL, and the redirect
            # takes it as one value.
            destination=quote(destination, safe=""),
        )


AFFILIATE_NETWORKS: dict[str, AffiliateNetwork] = {
    "awin": AffiliateNetwork(
        key="awin",
        label="Awin",
        rewrite="https://www.awin1.com/cread.php?awinmid={advertiser}&awinaffid={publisher}&ued={destination}",
        note="Runs the TransPennine Express and several other rail merchant programmes.",
    ),
    "partnerize": AffiliateNetwork(
        key="partnerize",
        label="Partnerize",
        rewrite="https://prf.hn/click/camref:{advertiser}/destination:{destination}",
        note="Runs the Trainline programme.",
    ),
}


@dataclass(frozen=True)
class TicketLink:
    """A built link, with everything a page needs to render it honestly."""

    url: str
    label: str
    rel: str
    tracked: bool
    disclosure: str | None = field(default=None)


def ticket_link(
    origin_crs: str,
    destination_crs: str,
    *,
    provider: str = DEFAULT_PROVIDER,
    when: date | None = None,
    adults: int = 2,
    network: str | None = None,
    advertiser_id: str | None = None,
    publisher_id: str = "",
    mode: str = "deep",
) -> TicketLink:
    """Build a search link for one origin and destination.

    ``mode`` chooses between the two links a seller can be given, and neither is
    silent about the other:

    - ``"deep"`` (the default) sends the origin, destination, date, and party
      size, so the reader lands on the search they were already reading.
    - ``"fallback"`` sends only the seller's own search page, for when the
      parameterised link is not known to land on a search.

    With no network or advertiser configured the link is plain and untracked,
    which is the default: the licence terms for commercial use are not read yet
    (adr/ADR-0001-data-sources.md), and monetisation is a switch rather than a
    side effect of generating the page.

    **The page does not use this function's default.** `build_demo_page` passes
    ``mode="fallback"`` unless somebody opts in, because a deep link is only as
    good as the URL behind it. See adr/ADR-0018-the-pages-default-link.md.
    """
    try:
        chosen = PROVIDERS[provider]
    except KeyError:
        raise KeyError(f"{provider!r} is not one of: {', '.join(sorted(PROVIDERS))}") from None

    if mode == "fallback":
        if not chosen.fallback_url:
            raise KeyError(f"{provider!r} has no fallback search page recorded")
        url = chosen.fallback_url
    elif mode == "deep":
        values = {
            "origin": origin_crs.strip().upper(),
            "destination": destination_crs.strip().upper(),
            "date_iso": when.isoformat() if when else "",
            "date_compact": when.strftime("%Y%m%d") if when else "",
            "adults": str(adults) if adults else "",
            # These two are values, not switches: the page declared them so the
            # reader lands on a single search rather than a form to fill in.
            "single": "single",
            "depart_after": "departAfter",
        }
        url = chosen.url(values)
    else:
        raise ValueError(f"{mode!r} is not one of: deep, fallback")

    if not (network and advertiser_id):
        return TicketLink(url=url, label=chosen.label, rel=PLAIN_REL, tracked=False)

    try:
        wrapper = AFFILIATE_NETWORKS[network]
    except KeyError:
        raise KeyError(
            f"{network!r} is not one of: {', '.join(sorted(AFFILIATE_NETWORKS))}"
        ) from None
    return TicketLink(
        url=wrapper.wrap(url, advertiser_id=advertiser_id, publisher_id=publisher_id),
        label=chosen.label,
        rel=AFFILIATE_REL,
        tracked=True,
        disclosure=DISCLOSURE,
    )


def provider_table() -> list[tuple[str, str, list[str], str, str]]:
    """What each provider can be sent and what a live check found.

    The check is carried beside the parameters so that "this page declares these"
    and "this link was opened and worked" cannot be confused for each other.
    """
    return [
        (
            provider.key,
            provider.label,
            [value for _, value in provider.params],
            provider.note,
            provider.verified,
        )
        for provider in PROVIDERS.values()
    ]
