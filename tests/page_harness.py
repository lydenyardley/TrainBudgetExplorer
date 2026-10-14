"""The page suite's own harness: the fixture its modules share.

The demo feed, the parsed timetable, the one rendered page and the cache
directory they are built through are shared by every page test, so they live
here rather than in the module that happened to hold them first. unittest
calls setUpModule/tearDownModule from every module it collects, so each page
test module gets the same cache-directory rule.

The import is written `from tests.page_harness import ...` because that
resolves for `python -m unittest tests.test_page_runner` and for unittest's
discovery, which imports the module under its own bare name (F6 of the 8
October 2026 agent-efficiency audit)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock
import json
import re
import shutil
import tempfile
import unittest

import build_demo_page
from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
from make_synthetic_feed import build_synthetic_feed, build_synthetic_timetable


def _unpack_railcards(value, codec):
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


def _unpack_tickets(value, codec):
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


def hydrate_rows(payload: dict) -> dict:
    """The payload as the page reads it: each row table turned back into objects.

    The build ships a row list as a column list and a table of cells, with the
    station's own columns placed once per station and railcards and tickets
    packed (ADR-0069); the page hydrates them as it loads, so a test that read
    the wire text directly would be asserting a shape no reader of the page
    ever sees. This mirrors ``hydrate`` in page/station/payload.js.
    """
    pool = payload.get("pool") or []
    codec = payload.get("rowCodec") or {}
    places = payload.get("places") or {"columns": [], "rows": {}}

    def value(cell):
        return pool[-cell - 1] if isinstance(cell, int) and not isinstance(cell, bool) and cell < 0 else cell

    for key in ("destinations", "singleDestinations", "anytimeDestinations", "stations"):
        table = payload.get(key)
        if not (isinstance(table, dict) and isinstance(table.get("rows"), list)):
            continue
        placed = set(table.get("placed") or [])
        own = [column for column in table["columns"] if column not in placed]
        rows = []
        for cells in table["rows"]:
            station = places["rows"].get(value(cells[own.index("crs")])) if placed else None
            row, at = {}, 0
            for column in table["columns"]:
                if column in placed:
                    row[column] = station[places["columns"].index(column)] if station else None
                    continue
                cell = value(cells[at])
                at += 1
                if column == "railcards":
                    cell = _unpack_railcards(cell, codec.get("railcards"))
                elif column == "tickets":
                    cell = _unpack_tickets(cell, codec.get("tickets"))
                row[column] = cell
            rows.append(row)
        payload[key] = rows
    for key in ("pool", "places", "rowCodec"):
        payload.pop(key, None)
    return payload


class PageTestCase(unittest.TestCase):
    """The one page every page-content test reads.

    The synthetic feed, its parsed timetable, the one payload and the one
    rendered page are the fixture of every test that makes a claim about that
    page, so they are built here rather than in each of the modules that read
    them (F6 of the 8 October 2026 agent-efficiency audit). The class holds no
    test of its own, so unittest collects nothing from it, and each subclass
    gets its own build and its own temporary directory.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fares = FaresDb().load_feed(
            build_synthetic_feed(
                Path(cls._tmp.name) / "fares",
                include_unserved_station=True,
                include_restrictions=True,
            )
        )
        cls.timetable = TimetableDb().load_feed(build_synthetic_timetable(Path(cls._tmp.name) / "timetable"))
        cls.payload = build_demo_page.build_payload(cls.fares, cls.timetable, "GRN")
        cls.html = build_demo_page.render_page(cls.payload, budget_pounds=20)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @property
    def stylesheet(self) -> str:
        """The CSS this page is served with, which is no longer inside it.

        ADR-0047: the station route fetches one stylesheet rather than inlining
        it, because the same 34.6 KB on 2,712 pages was 92 MB of a site measured
        at 583 MB. A test that asserts a rule exists therefore asserts it
        against the document the page loads -- one string, identical on every
        station page, written beside them by the build -- rather than against
        the page, which no longer carries any of it.
        """
        from page_templates import STATION_STYLESHEET

        return STATION_STYLESHEET


def embedded_text(html: str) -> str:
    """The payload exactly as the page's own script receives it."""
    start = html.index("window.TBE_DATA = ") + len("window.TBE_DATA = ")
    return html[start : html.index(";", start)]


def embedded_payload(html: str) -> dict:
    match = re.search(r"window\.TBE_DATA = (\{.*?\});\n", html, re.DOTALL)
    if match is None:
        raise AssertionError("the page carries no embedded payload")
    return hydrate_rows(json.loads(match.group(1)))


def serialised_callback_lines(source: str) -> list[str]:
    """The lines of every page callback node does not run where it is written.

    ``page.evaluate`` stringifies its callback and the page parses the string
    again, so the text inside one is read twice by two parsers. Pairing the
    brackets by hand is enough here: the suite's callbacks are either an
    arrow function in parentheses or a brace-delimited block, and a suite that
    made that untrue would fail to run at all.
    """
    lines: list[str] = []
    for call in re.finditer(r"page\.(?:evaluate|waitForFunction|evaluateHandle)\(", source):
        depth = 0
        index = source.index("(", call.end() - 1)
        while index < len(source):
            if source[index] == "(":
                depth += 1
            elif source[index] == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        lines.extend(source[source.index("(", call.end() - 1) : index + 1].split("\n"))
    return lines


def browser_suite_text() -> str:
    """Every file of the browser suite, read as one string.

    The suite is split by route and by section under tests/browser/, and the
    entry point that verify.py and CI invoke holds none of the checks itself.
    A Python test that reads the suite as text -- the doubled escape inside a
    page callback, the labels the accessibility matrix is wired with -- has to
    read all of it rather than the file that holds the command line.
    """
    folder = Path(__file__).resolve().parent
    files = [folder / "browser_test.cjs", *sorted((folder / "browser").glob("*.cjs"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def station_page(out: Path) -> Path:
    """The station page a single-origin build wrote beside its chooser.

    A single-origin build is a site: --out names the root index.html, which is
    the chooser, and the one station page is written to its canonical
    /from/<slug>/ route (S01, S04). Tests that want the station's own content
    read it from here rather than from the root.
    """
    pages = sorted((out.parent / "from").glob("*/index.html"))
    if len(pages) != 1:
        raise AssertionError(f"expected exactly one station page under {out.parent / 'from'}, got {pages}")
    return pages[0]


# Every build writes a parsed-fares cache named by the feed's content, so a
# suite that built in the repository's own cache directory would leave one
# pair of files per fixture behind, and would read whichever pair an earlier
# run happened to leave -- which is how a test that should have parsed the
# feed ends up passing on a cache it did not write. The tests that care where
# the cache lives patch the directory themselves.
_CACHE_DIR_PATCH: mock._patch | None = None


def setUpModule() -> None:
    global _CACHE_DIR_PATCH
    _CACHE_DIR_PATCH = mock.patch.object(
        build_demo_page, "CACHE_DIR", Path(tempfile.mkdtemp(prefix="page-cache-"))
    )
    _CACHE_DIR_PATCH.start()


def tearDownModule() -> None:
    if _CACHE_DIR_PATCH is not None:
        cache = build_demo_page.CACHE_DIR
        _CACHE_DIR_PATCH.stop()
        shutil.rmtree(cache, ignore_errors=True)



def page_script(html: str) -> str:
    """The code the page executes.

    The page inlines its own DATA and names the route's script beside the
    stylesheet, so the last inline block is the payload rather than the code.
    The bytes the browser keeps are the asset the build wrote once, so this
    reads that asset rather than the inline block -- and the asset the page
    names has to be the one this tree would write, or the test is reading code
    the page does not run.
    """
    match = re.search(r'<script src="([^"]*station-[0-9a-f]+\.js)"', html)
    if match is None:
        return html.split("<script>")[-1].split("</script>")[0]
    name = match.group(1).rsplit("/", 1)[-1]
    assert name == build_demo_page.station_script_asset_name(), (
        f"the page names {name} but this tree writes "
        f"{build_demo_page.station_script_asset_name()}"
    )
    return build_demo_page.STATION_SCRIPT


def js_function(source: str, name: str) -> str:
    """One of the page's own functions, braces matched, source and all.

    A test that runs a helper the page ships is testing behaviour rather than
    a string, which is why it is allowed to reach into the script at all --
    what it must not do is assert on a statement, and this returns the text to
    run rather than to match. Locating a function by its name and pairing the
    braces keeps the search from being a quote of the signature.
    """
    match = re.search(r"function\s+" + re.escape(name) + r"\s*\(", source)
    if match is None:
        raise AssertionError(name + " is not in this script")
    depth = 0
    start = source.index("{", match.end())
    index = start
    while index < len(source):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
        index += 1
    raise AssertionError(name + " did not close")


def page_markup(html: str) -> str:
    """The page's markup: everything before the page's own script opens."""
    if "<script>" not in html:
        return html
    return html[: html.rindex("<script>")]
