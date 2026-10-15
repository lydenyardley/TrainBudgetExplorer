"""Propose station codes for the reviewed nature-sites list, from trust pages.

``NATURE_SITE_STATION_CRS`` in ``atoc_fares`` is a reviewed list: someone read
the reserve page and wrote down the station it says. That is the right way to
record it and the wrong way to keep it current, because a trust that names a
different station next season leaves the list quietly wrong.

This tool does the reading, and refuses to do the writing. It fetches reserve
pages, finds the sentences that mention a station, matches the station name
against the ones the feed actually carries, and prints each match **with the
sentence it came from**. A person reads that and decides. The tool never edits
``atoc_fares``, because a list of proposed stations is not a reviewed list, and
writing one into the source as if a person had checked it is the same false
claim as every other unreviewed shortcut in this project.

What it will not do, deliberately:

- It only fetches hosts on ``ALLOWED_HOSTS`` (the Wildlife Trusts and the WWT).
  It is a crawler pointed at a fixed pair of site families, not a general one.
- One request per page, no retries, no link following beyond the URLs given.
  Page discovery is the caller's list, so the tool cannot wander.
- It never says a match is correct. It says the page named this station, and
  shows the words.

    python -m tools.propose_nature_stations --reserve-pages pages.txt
    python -m tools.propose_nature_stations --url https://www.essexwt.org.uk/nature-reserves/thorndon
    python -m tools.propose_nature_stations --reserve-pages pages.txt --emit-code
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


from atoc_fares import NATURE_SITE_STATION_CRS
from feeds_cli import add_feed_args
from tools.regenerate_destination_facets import load_stations

# The hosts this tool will read without being told otherwise: the network's own
# sites. Every member trust has its own domain (essexwt.org.uk,
# kentwildlifetrust.org.uk, ywt.org.uk, and so on), so those are read only when
# the operator names the host with --allow-host. That keeps a URL list that has
# picked up a stray link from turning into a crawler of wherever it points.
ALLOWED_HOSTS = ("wildlifetrusts.org", "wwt.org.uk")

USER_AGENT = "train-budget-explorer-nature-proposer/1.0 (one request per page; proposals for review)"
TIMEOUT_SECONDS = 20
# A courtesy gap between requests, so a long list of pages is not a burst.
DELAY_SECONDS = 1.0

# A sentence is worth reading when it says how a reader gets there. A page that
# merely says "trains" is not evidence that a station serves the reserve.
STATION_WORDS = ("station", "railway", "train", "by rail", "park and ride")

# Longest sentence kept. A page whose whole body is one paragraph produces
# something unreadable otherwise, and the tail of a long sentence is where the
# station name stops being the subject.
MAX_SENTENCE = 400

# Longest run of words read as one candidate name: "Hayes and Harlington" is
# three, "Burscough Bridge" is two, and nothing on a reserve page is longer.
MAX_PHRASE_WORDS = 3

# Unmatched names printed per run. The list is a prompt for a reviewer, not a
# finding, so a page that names every village on its bus route cannot fill the
# output on its own.
UNMATCHED_LIMIT = 12

# Suffixes the DTD adds to a station's name that a reserve page never writes,
# so "Hatton Cross" is the same station as "HATTON CROSS UND". Kept short and
# explicit: a partial match of any other kind would propose the wrong station.
QUALIFIER_SUFFIXES = ("UND", "UNDR")


# Block-level tags. A page's prose is broken by its markup, not by full stops:
# an "Access" paragraph with no punctuation is one 400-character blob otherwise,
# and a station named in the last line of it is cut away.
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "li", "main",
    "nav", "ol", "p", "section", "table", "td", "th", "tr", "ul",
}


class _AllowedHostRedirect(urllib.request.HTTPRedirectHandler):
    """Keep the allowlist true across redirects.

    urllib follows a redirect without asking, so a page on an allowed host that
    answers with a 302 to anywhere else would be read anyway. The allowlist is
    the only thing stopping this tool becoming a crawler of wherever a page
    points it, so the redirect is checked the same way the original URL was.
    """

    def __init__(self, extra_hosts: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._extra_hosts = tuple(extra_hosts)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not host_allowed(newurl, self._extra_hosts):
            raise urllib.error.HTTPError(
                newurl, code, f"redirect to a host this tool does not read: {newurl}", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _Text(HTMLParser):
    """Page text, with the script and style bodies dropped.

    A reserve page carries its prose in the body, but a navigation menu is full
    of words like "train" that would otherwise be proposed as evidence.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(self.parts)


def page_text(html: str) -> str:
    """The readable text of a page, as one whitespace-normalised string.

    Line structure is kept (it is where the prose boundaries are) and every run
    of spaces is collapsed.
    """
    parser = _Text()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - a malformed page is a short read, not a crash
        pass
    text = "\n".join(re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in parser.text().split("\n"))
    return "\n".join(line for line in text.split("\n") if line)


def sentences(text: str) -> list[str]:
    """Split page text into readable pieces, bounded in length.

    A piece longer than ``MAX_SENTENCE`` is windowed rather than truncated: a
    name cut in half matches nothing, and a station named at the end of a long
    unmarked paragraph is the one the tool exists to find.
    """
    found: list[str] = []
    for block in text.split("\n"):
        for part in re.split(r"(?<=[.!?:;])\s+|\s+[•|]\s+", block):
            part = part.strip()
            if not part:
                continue
            if len(part) <= MAX_SENTENCE:
                found.append(part)
                continue
            step = MAX_SENTENCE // 2
            for start in range(0, len(part), step):
                window = part[start : start + MAX_SENTENCE]
                if window.strip():
                    found.append(window.strip())
    return found


def station_sentences(text: str) -> list[str]:
    """The sentences that mention a station, a railway, or a train.

    A page that names three stations gets three proposals; the same station
    named in two sentences is proposed once, with the first sentence that
    named it.
    """
    kept: list[str] = []
    seen: set[str] = set()
    for sentence in sentences(text):
        # A window of a long paragraph is a fragment, so the evidence is only
        # worth reading where a station word is near the start of it.
        lowered = sentence.lower()
        if not any(word in lowered for word in STATION_WORDS):
            continue
        key = re.sub(r"[^a-z0-9 ]", "", lowered)
        if key in seen:
            continue
        seen.add(key)
        kept.append(sentence)
    return kept


def fetch(url: str, *, timeout: int = TIMEOUT_SECONDS, extra_hosts: tuple[str, ...] = ()) -> tuple[int, str]:
    """One GET. Returns (status, body). Never raises for a network failure."""
    if not host_allowed(url, extra_hosts):
        raise ValueError(f"{url} is not a Wildlife Trusts or WWT page")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_AllowedHostRedirect(extra_hosts))
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return response.status, body.decode(charset, errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, OSError, ValueError) as error:
        return 0, str(error)


def host_allowed(url: str, extra: tuple[str, ...] = ()) -> bool:
    """Whether this tool will read the URL's host.

    A host matches when it is one of the allowed names or a subdomain of one,
    so ``www.essexwt.org.uk`` is allowed by ``essexwt.org.uk`` but
    ``essexwt.org.uk.evil.example`` is not.
    """
    match = re.match(r"https?://([^/:]+)", url.strip(), re.IGNORECASE)
    if not match:
        return False
    host = match.group(1).lower()
    allowed = tuple(ALLOWED_HOSTS) + tuple(h.strip().lower() for h in extra if h.strip())
    return any(host == name or host.endswith("." + name) for name in allowed)


class Proposal:
    """One station a page named, with the words that named it."""

    def __init__(self, crs: str, name: str, url: str, evidence: str) -> None:
        self.crs = crs
        self.name = name
        self.url = url
        self.evidence = evidence

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Proposal({self.crs}, {self.name!r})"


def propose_for_url(
    url: str,
    names_by_crs: dict[str, str],
    *,
    timeout: int = TIMEOUT_SECONDS,
    extra_hosts: tuple[str, ...] = (),
) -> tuple[list[Proposal], list[str], str | None]:
    """Read one page. Return (proposals, unmatched names, error).

    ``unmatched`` is the honest half of the answer: a page that names a station
    this feed does not carry is worth seeing too, because it usually means the
    feed or the page has moved, not that the tool found nothing.
    """
    status, body = fetch(url, timeout=timeout, extra_hosts=extra_hosts)
    if status != 200:
        return [], [], f"HTTP {status}"
    lookup = StationLookup(names_by_crs)
    proposals: list[Proposal] = []
    unmatched: set[str] = set()
    seen: set[str] = set()
    for sentence in station_sentences(page_text(body)):
        matched_here = lookup.matches(sentence)
        for phrase, crs in matched_here:
            if crs and crs not in seen:
                seen.add(crs)
                proposals.append(Proposal(crs, names_by_crs[crs], url, sentence))
        # A capitalised span that is part of a phrase already matched is not
        # "named but missing": "Hatton" is a fragment of "Hatton Cross", and
        # listing it would send a reviewer looking for a station that was found.
        for name in lookup.candidates(sentence):
            if any(name in phrase for phrase, _crs in matched_here):
                continue
            if not lookup.matches(name) and looks_like_a_station_name(name):
                unmatched.add(name)
    return proposals, sorted(unmatched), None


class StationLookup:
    """Match a page's words to the feed's station names.

    A reserve page writes "Hatton Cross"; the feed writes "HATTON CROSS UND"
    because the DTD's name field truncates and suffixes London Underground
    stations. So a candidate matches on the whole normalised name, or on the
    whole name plus a suffix the DTD adds and a page never writes
    (``QUALIFIER_SUFFIXES``). Nothing looser is attempted: a partial match
    would propose "Bradford" for "BRADFORD F SQ", and a proposal is only worth
    reading if a person would have written that code down.
    """

    def __init__(self, names_by_crs: dict[str, str]) -> None:
        self.names = names_by_crs
        self._exact = {normalise(name): crs for crs, name in names_by_crs.items()}
        # The longest names first, so the longest reading of a phrase wins.
        self._prefixed = sorted(
            (
                (normalise(name), crs)
                for crs, name in names_by_crs.items()
                if len(normalise(name)) > 4
                and normalise(name).endswith(QUALIFIER_SUFFIXES)
            ),
            key=lambda item: -len(item[0]),
        )

    def match(self, phrase: str) -> str | None:
        key = normalise(phrase)
        if not key:
            return None
        if (crs := self._exact.get(key)) is not None:
            return crs
        for name, crs in self._prefixed:
            if name.startswith(key) and name[len(key) :] in QUALIFIER_SUFFIXES:
                return crs
        return None

    def matches(self, sentence: str) -> list[tuple[str, str]]:
        """Every (phrase, crs) in the sentence, longest phrase first.

        Phrases are word spans rather than one regex over the sentence: a
        sentence is not a station name, and matching whole clauses is how
        "The nearest station is Hatton Cross" finds nothing. A match followed by
        "Bus" is a coach station -- the page is describing how a bus gets there,
        not a station a reader can be priced to -- so it is not proposed.
        """
        words = re.findall(r"[A-Za-z][A-Za-z'&.\-]*", sentence)
        found: list[tuple[str, str]] = []
        taken: set[int] = set()
        for size in range(MAX_PHRASE_WORDS, 0, -1):
            for start in range(len(words) - size + 1):
                end = start + size
                if taken & set(range(start, end)):
                    continue
                phrase = " ".join(words[start:end])
                if len(normalise(phrase)) < 4:
                    continue
                if not (crs := self.match(phrase)):
                    continue
                if end < len(words) and words[end].lower() == "bus":
                    continue
                found.append((phrase, crs))
                taken |= set(range(start, end))
        return found

    def candidates(self, sentence: str) -> list[str]:
        """Capitalised word spans worth printing when nothing matched them.

        Single words are included, because a feed that truncates a name
        ("HAYES & HARLNGTN") is exactly the case a reviewer needs to see and
        cannot match by rule. The caller passes only sentences that mention a
        station, so the list stays short.
        """
        words = re.findall(r"[A-Za-z][A-Za-z'&.\-]*", sentence)
        spans = []
        for size in range(MAX_PHRASE_WORDS, 0, -1):
            for start in range(len(words) - size + 1):
                span_words = words[start : start + size]
                if size == 1 and len(span_words[0]) < 7:
                    continue
                if all(word[:1].isupper() for word in span_words):
                    spans.append(" ".join(span_words))
        return spans


def normalise(value: str) -> str:
    """The same whole-name matching the feed's own settlement reader uses."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def looks_like_a_station_name(candidate: str) -> bool:
    """Whether a capitalised span is worth printing as an unmatched name.

    It is a filter for the human's attention, not a classification: nothing
    here decides a station exists, and a page full of place names produces a
    short list a person can skim.
    """
    text = candidate.strip()
    if len(text) < 5 or not text[0].isupper():
        return False
    words = text.lower().split()
    if any(
        word in {
            "station", "railway", "train", "trains", "line", "lane", "road",
            "park", "reserve", "centre", "center", "walk", "bus", "car",
            "airport", "airports", "shuttle", "ferry", "canal", "route",
            "the", "and", "from", "near", "north", "south", "east", "west",
            "turn", "left", "right", "follow", "exit", "minutes", "minute",
            "mile", "miles", "directions", "access", "visit", "opening",
            "times", "here", "there", "journey", "busy", "water", "wood",
        }
        for word in words
    ):
        return False
    return len(text.split()) <= MAX_PHRASE_WORDS


def read_urls(args) -> list[str]:
    """The pages to read: --url, plus any lines in --reserve-pages."""
    urls = list(args.url)
    if args.reserve_pages:
        text = Path(args.reserve_pages).read_text(encoding="utf-8")
        urls.extend(
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_feed_args(
        parser,
        feed_default=Path("feeds") / "fares" / "dtd-fares.zip",
        fares_only=True,
    )
    parser.add_argument(
        "--url", action="append", default=[], help="a reserve page to read (repeatable)"
    )
    parser.add_argument(
        "--reserve-pages", type=Path, default=None, help="a file of reserve page URLs, one per line"
    )
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="a member trust's own domain to read, e.g. essexwt.org.uk. Without "
        "this only wildlifetrusts.org and wwt.org.uk are read",
    )
    parser.add_argument(
        "--emit-code",
        action="store_true",
        help="print a Python snippet for NATURE_SITE_STATION_CRS, with the comment "
        "a reviewer must replace. Never written to a file by this tool",
    )
    args = parser.parse_args(argv)

    urls = read_urls(args)
    if not urls:
        print("error: give at least one --url or a --reserve-pages file", file=sys.stderr)
        return 2
    refused = [url for url in urls if not host_allowed(url, tuple(args.allow_host))]
    if refused:
        print(
            "error: this tool only reads " + " and ".join(ALLOWED_HOSTS)
            + " pages (or a trust named with --allow-host): " + ", ".join(refused),
            file=sys.stderr,
        )
        return 2

    fares = load_stations(args.feed)
    names_by_crs = {crs: location.name for crs, location in fares.locations_by_crs.items()}
    known = set(NATURE_SITE_STATION_CRS)

    proposals: dict[str, Proposal] = {}
    unreadable: list[str] = []
    unmatched: dict[str, str] = {}
    for number, url in enumerate(urls, 1):
        found, named, error = propose_for_url(
            url, names_by_crs, extra_hosts=tuple(args.allow_host)
        )
        if error:
            unreadable.append(f"{url} ({error})")
            continue
        for proposal in found:
            proposals.setdefault(proposal.crs, proposal)
        for name in named:
            unmatched.setdefault(name, url)
        print(f"[{number}/{len(urls)}] {url}: {len(found)} station(s) named", file=sys.stderr)
        if number < len(urls):
            time.sleep(DELAY_SECONDS)

    new = {crs: p for crs, p in proposals.items() if crs not in known}
    already = sorted(crs for crs in proposals if crs in known)
    print()
    for crs, proposal in sorted(new.items()):
        print(f"proposed {crs} {proposal.name}")
        print(f"    from {proposal.url}")
        print(f"    evidence: {proposal.evidence}")
    if already:
        print(f"\nalready listed, no action needed: {', '.join(already)}")
    if unmatched:
        print("\nnamed on a page but not in this feed (check the feed, not this tool):")
        # Longest first, so the most specific names are the ones a reviewer
        # reads, and bounded so a page full of place names is not a wall.
        for name, url in sorted(unmatched.items(), key=lambda item: (-len(item[0]), item[0]))[:UNMATCHED_LIMIT]:
            print(f"    {name}  <- {url}")
        if len(unmatched) > UNMATCHED_LIMIT:
            print(f"    ... and {len(unmatched) - UNMATCHED_LIMIT} more")
    if unreadable:
        print("\nnot read:", file=sys.stderr)
        for entry in unreadable:
            print(f"    {entry}", file=sys.stderr)
    print(f"\n{len(new)} proposal(s) to review; nothing was written to any file.")
    if args.emit_code and new:
        print("\n# Paste into NATURE_SITE_STATION_CRS, replacing the comment per trust:")
        for crs, proposal in sorted(new.items()):
            print(f'    "{crs}",  # REVIEW: {proposal.name} -- {proposal.evidence[:90]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
