"""The acknowledgement travels with the pages that show a fare.

The portal terms require the publisher to "acknowledge NRE as the source of
Information", and the Developer Brand Guidelines place the *Powered by National
Rail Enquiries* mark where the fares feed is the product's predominant
information. The station route is that page: the build writes the feed's own
answer into it (``window.TBE_DATA``, filled by ``render_page``) and writes the
acknowledgement into its footer when ``--notices`` names ``nre``.

Two ways that comes apart, and neither is visible in the flags:

- a notice set without ``nre`` still builds station pages, because the build's
  own release gate refuses only a build with *no* notice at all
  (``release_gate_problems``), not a build missing this one;
- a new route that inlines the feed's answer is a route nobody asked for the
  credit on.

So this reads the built site rather than the command line: a page carrying the
feed's answer must carry both halves of the acknowledgement -- the mark the
guidelines name and the source sentence in the terms' own words. Both are
written together (``nre_attribution`` and ``nre_source_line``), so requiring
both refuses a page that lost one of them rather than only both.

**Which pages are asked, and why the others are not.** Only the route carrying
the feed's answer is asked. The chooser at ``/`` shows the feed's station index
and the count of destinations it prices, and the privacy notice shows neither a
price nor a station; the reading that a station *index* is not the feed's
predominant information, and that the fares are, is recorded in
``licences/release-clearance.md`` beside the clearance it supports. That reading
is what this tool encodes, and it is the tool's own limit as much as its rule.

**What this cannot see.** It reads the marker the station template writes. A
route that inlined the feed's fares under another name would pass here, and the
marker is one string in one template -- if that template is renamed, this check
stops checking rather than failing, so the marker lives beside the template's
own name in the test.

    python -m tools.check_source_credit --site _site

Exit codes: 0 every page that shows a fare carries the acknowledgement, 1 a
page shows a fare without it, 2 nothing was read -- a folder that is not there,
or a site with no fare page at all. A check that passes having read nothing is
the one outcome a gate must never produce.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: The station template writes the page's own answer under this name, and it is
#: the one part of the page that differs per origin. A page carrying it is a
#: page showing fares from the feed that has to be acknowledged.
FARE_MARK = "window.TBE_DATA"

#: The acknowledgement, both halves, as ``build_release`` writes them. The label
#: is what a failure says is missing, so it reads as the licence's own words.
CREDIT_MARKS = {
    "the 'Powered by National Rail Enquiries' mark": 'class="nre-credit"',
    "the National Rail Enquiries acknowledgement": 'class="nre-source"',
}


def site_pages(site: Path) -> dict[str, str]:
    """Every HTML page under ``site``, keyed by a path a failure can name."""

    root = Path(site)
    pages: dict[str, str] = {}
    for path in sorted(root.rglob("*.html")):
        if path.is_file():
            pages[path.relative_to(root).as_posix()] = path.read_text(
                encoding="utf-8", errors="replace"
            )
    return pages


def credit_gaps(pages: dict[str, str]) -> tuple[list[str], int]:
    """``(problems, how many pages show a fare)`` for a site's pages.

    A problem is a page that carries the feed's answer and is missing an
    acknowledgement. The count is returned so a caller can tell "every fare page
    is credited" from "no page showed a fare", which are different claims and
    only one of them is a pass.
    """

    problems: list[str] = []
    showing = 0
    for name, text in sorted(pages.items()):
        if FARE_MARK not in text:
            continue
        showing += 1
        missing = [
            label for label, mark in CREDIT_MARKS.items() if mark not in text
        ]
        if missing:
            problems.append(f"{name}: shows fares, and is missing " + " and ".join(missing))
    return problems, showing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every page showing a fare carries the National Rail credit.",
    )
    parser.add_argument("--site", type=Path, required=True, help="a built site folder")
    args = parser.parse_args(argv)

    if not args.site.is_dir():
        print(
            f"{args.site} is not a folder, so no page was read and whether a page "
            "showing a fare carries the credit is unknown.",
            file=sys.stderr,
        )
        return 2

    try:
        pages = site_pages(args.site)
    except OSError as error:
        print(f"could not read {error.filename}: {error.strerror}", file=sys.stderr)
        return 2

    if not pages:
        print(
            f"no HTML page was read under {args.site}, so whether a page showing a "
            "fare carries the credit is unknown. Build the site before checking it.",
            file=sys.stderr,
        )
        return 2

    problems, showing = credit_gaps(pages)
    if not showing:
        print(
            f"no page under {args.site} carries the feed's fares, so the credit has "
            "no subject and this release is not the shape it was checked as.",
            file=sys.stderr,
        )
        return 2

    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1

    print(
        f"{showing} page(s) show fares and every one carries the National Rail "
        "credit and acknowledgement"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
