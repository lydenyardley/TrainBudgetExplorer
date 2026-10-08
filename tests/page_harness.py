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

import build_demo_page


def hydrate_rows(payload: dict) -> dict:
    """The payload as the page reads it: each row table turned back into objects.

    The build ships a row list as a column list and a table of cells, and the page
    hydrates them as it loads, so a test that read the wire text directly would be
    asserting a shape no reader of the page ever sees.
    """
    for key in ("destinations", "singleDestinations", "anytimeDestinations", "stations"):
        table = payload.get(key)
        if isinstance(table, dict) and isinstance(table.get("rows"), list):
            pool = payload.get("pool") or []
            payload[key] = [
                {
                    field: pool[-cell - 1] if isinstance(cell, int) and cell < 0 else cell
                    for field, cell in zip(table["columns"], cells)
                }
                for cells in table["rows"]
            ]
    payload.pop("pool", None)
    return payload


def embedded_text(html: str) -> str:
    """The payload exactly as the page's own script receives it."""
    start = html.index("const DATA = ") + len("const DATA = ")
    return html[start : html.index(";", start)]


def embedded_payload(html: str) -> dict:
    match = re.search(r"const DATA = (\{.*?\});\n", html, re.DOTALL)
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
    """The page's own script, which is the last one in the file.

    The theme block is injected into the head so the palette is decided before
    the first paint, so the *first* script is no longer the page's script, and a
    test reading that slice is reading the theme block. The page's own script
    is the last one, and this says so in one place instead of at fourteen.
    """
    return html.split("<script>")[-1].split("</script>")[0]


def page_markup(html: str) -> str:
    """The page's markup: everything before the page's own script opens."""
    if "<script>" not in html:
        return html
    return html[: html.rindex("<script>")]
