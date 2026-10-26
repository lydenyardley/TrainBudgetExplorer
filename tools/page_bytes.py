"""Measure what a built page costs, in the bytes a host counts.

The site's promise is a page per departure station, and the feed prices 2,712 of
them. The first full-network build stopped after 944 pages with the disk full,
and the projection from the pages it did write was 1.4 to 1.6 GB against GitHub
Pages' 1 GB per-site limit (audit, 29 September 2026). Every number behind that
projection was measured by hand, in a shell, and the picture did not survive the
second reader: the same session costed the bytes identical on every page at 18.6
KB in one place and 116.7 KB in another, because one figure counted ADR-0033's
inlined blocks and the other counted the whole stylesheet and script.

So the measurement is a tool. It splits a page the way a host's limit splits it,
into the stylesheet, the script a browser has to parse, and the JSON the page
ships, and it reports the bytes every page repeats word for word. That last
number is the one the release turns on: it is the ceiling on what a shared asset
could ever save, and it is only real for parts that are equal in *every* page
measured, so a stylesheet one page renders differently is that page's own.

    python -m tools.page_bytes _site/index.html _site/from/grantham/index.html
    python -m tools.page_bytes --site _site --budget-mb 800

**What this tool cannot know.** It cannot measure a page that was never built,
and it cannot see a host's own limit. `--budget-mb` is the number this project
holds itself to, which is 800 MB rather than the 1 GB limit for a reason: a
release that reaches a hard limit with nothing to spare reaches it again on the
next feed revision, and the failure that costs a publication is the one nobody
saw coming. The budget is printed with every site measurement so a reader can
disagree with it.

**What it refuses to call a pass.** A measurement's zero and a page's emptiness
are different facts, and until 18 October 2026 this tool could not tell them
apart. It searched for a marker the renderer had stopped writing, so every page
reported 0 KB of payload and 0 rows and the budget gate passed over a site it had
measured nothing of. Two conditions are now failures: a page that names a payload
which did not parse, because the page says it ships data and the tool did not find
it, and a `--site` run that finds no page at all. Both are checked locally, so a
page that genuinely ships nothing, the privacy route, still passes.

Exit codes: 0 every page measured and the site is inside the budget, 1 the site
is over it, 2 a path could not be read, a page named a payload it did not parse,
or a site held no page. A release that cannot be measured has not passed.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from trainbudget.build.page_templates import CHOOSER_MARKER, PAYLOAD_MARKER

# The number the network has to fit inside, argued in the module docstring.
SITE_BUDGET_MB = 800

# Each of these introduces JSON a page ships inline. Every occurrence is
# measured, so a page that carries more than one block cannot report less than it
# sends, and the code left behind is what a browser must parse to render. They
# are imported from the module that writes them rather than spelled here: a copy
# of a marker is a measurement that goes silently stale when the renderer moves
# on, which is exactly what this tool did.
INLINE_JSON_MARKERS = (PAYLOAD_MARKER, CHOOSER_MARKER)

STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.S)


@dataclass(frozen=True)
class PageBytes:
    """One built page, split so a byte can be argued about.

    ``css`` and ``code`` are kept as text rather than as sizes because the only
    question worth asking of them is whether another page carries the same
    characters, and that question cannot be asked of a length.

    ``named`` counts the markers found, whether or not JSON followed one. It is
    what separates a page that ships no payload from a page whose payload this
    tool failed to read, and those two facts used to look identical.
    """

    path: Path
    total: int
    css: str
    code: str
    payload: int
    rows: int
    named: int = 0

    @property
    def css_bytes(self) -> int:
        return len(self.css.encode("utf-8"))

    @property
    def code_bytes(self) -> int:
        return len(self.code.encode("utf-8"))


def _row_count(value: object) -> int:
    """How many destination rows a payload carries, however it is encoded.

    Counted rather than assumed, because the wire form of the payload is the
    thing under change: the same measurement has to read a row list sent as a list
    of objects and one sent as a column list with a table of cells, or a
    before-and-after comparison would be measuring two different tools.
    """
    if isinstance(value, list):
        return len(value)
    if not isinstance(value, dict):
        return 0
    total = 0
    for key, item in value.items():
        if isinstance(item, dict) and isinstance(item.get("rows"), list):
            total += len(item["rows"])
        elif "destinations" in key.lower() and isinstance(item, list):
            total += len(item)
    return total


def _split_script(script: str) -> tuple[int, int, int, str]:
    """One script split into its inline JSON and the code around it.

    Scanned left to right with a cursor, so a removed payload cannot expose the
    text behind it to a second attempt at the same marker, and a marker with no
    JSON after it is left in the code as the mention it is.

    The count of markers found is returned beside the bytes, because a marker the
    tool could not read is the one case a caller has to hear about.
    """
    payload = 0
    rows = 0
    named = 0
    kept: list[str] = []
    cursor = 0
    while True:
        found = None
        for marker in INLINE_JSON_MARKERS:
            position = script.find(marker, cursor)
            if position != -1 and (found is None or position < found[0]):
                found = (position, marker)
        if found is None:
            break
        position, marker = found
        after = position + len(marker)
        named += 1
        try:
            value, end = json.JSONDecoder().raw_decode(script[after:])
        except json.JSONDecodeError:
            kept.append(script[cursor:after])
            cursor = after
            continue
        kept.append(script[cursor:after])
        payload += len(script[after : after + end].encode("utf-8"))
        rows += _row_count(value)
        cursor = after + end
    kept.append(script[cursor:])
    return payload, rows, named, "".join(kept)


def measure_page(path: Path | str) -> PageBytes:
    """Measure one built page at ``path``."""
    text = io.open(path, encoding="utf-8").read()
    payload = 0
    rows = 0
    named = 0
    code = []
    for script in SCRIPT.findall(text):
        script_payload, script_rows, script_named, remainder = _split_script(script)
        payload += script_payload
        rows += script_rows
        named += script_named
        code.append(remainder)
    return PageBytes(
        path=Path(path),
        total=len(text.encode("utf-8")),
        css="".join(STYLE.findall(text)),
        code="".join(code),
        payload=payload,
        rows=rows,
        named=named,
    )


def identical_bytes(pages: list[PageBytes]) -> int:
    """The bytes every measured page carries word for word.

    Only a part that is equal in every page counts. Claiming a saving from a
    stylesheet that differs on one page would credit the release with bytes it
    still has to send.
    """
    if len(pages) < 2:
        return 0
    total = 0
    for part in ("css", "code"):
        first = getattr(pages[0], part)
        if all(getattr(page, part) == first for page in pages[1:]):
            total += len(first.encode("utf-8"))
    return total


def site_size(root: Path | str) -> tuple[int, int]:
    """A built folder's total bytes and its page count, as a host counts them."""
    total = 0
    pages = 0
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            total += path.stat().st_size
            if path.name == "index.html":
                pages += 1
    return total, pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure the bytes a built page sends, and the bytes every page repeats.",
    )
    parser.add_argument("pages", nargs="*", type=Path, help="built pages to measure")
    parser.add_argument("--site", type=Path, help="a built folder to total against the budget")
    parser.add_argument(
        "--budget-mb",
        type=int,
        default=SITE_BUDGET_MB,
        help=f"the site's budget in MB (default {SITE_BUDGET_MB}, see the module docstring)",
    )
    args = parser.parse_args(argv)

    try:
        measured = [measure_page(path) for path in args.pages]
        site = site_size(args.site) if args.site else None
    except OSError as error:
        print(f"could not read {error.filename}: {error.strerror}", file=sys.stderr)
        return 2

    for page in measured:
        print(
            f"{page.path}: {page.total // 1024} KB total, {page.css_bytes // 1024} KB css, "
            f"{page.code_bytes // 1024} KB script, {page.payload // 1024} KB payload, "
            f"{page.rows} rows"
        )
    blind = [page for page in measured if page.named and not page.payload]
    if blind:
        print(
            f"{blind[0].path} names a payload that did not parse, so its byte cost "
            "is unknown and this measurement says nothing",
            file=sys.stderr,
        )
        return 2
    shared = identical_bytes(measured)
    if len(measured) > 1:
        largest = max(page.total for page in measured)
        print(
            f"identical on all {len(measured)} measured pages: {shared // 1024} KB, "
            f"{shared * 100 // largest}% of the largest page"
        )

    if site is not None:
        total, pages = site
        if pages == 0:
            print(
                f"no page was found under {args.site}, so whether it fits the budget "
                "is unknown. Build the site before measuring it.",
                file=sys.stderr,
            )
            return 2
        budget = args.budget_mb * 1024 * 1024
        print(
            f"site {total / 1024 / 1024:.0f} MB of a {args.budget_mb} MB budget "
            f"over {pages} page(s)"
        )
        if total > budget:
            print(
                f"the site is {total / 1024 / 1024 - args.budget_mb:.0f} MB over budget",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
