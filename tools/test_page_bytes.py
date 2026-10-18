"""Tests for the byte-budget measurer.

The tool exists so a byte argument can be re-run instead of retold, which means
the tests are mostly about the split being honest. A page's payload is measured
from the marker to its closing bracket rather than to the end of the script, a
payload that a later statement follows is counted once, and a marker with no JSON
behind it is left as the code it is.

Every fixture here is built from `page_templates.PAYLOAD_MARKER` or the template
itself, never from a marker written out by hand. That is the regression this file
exists for as much as any of the above: the tool held its own copy of the marker,
the renderer stopped writing it, and for months every page measured 0 KB of
payload with 0 rows while the budget gate passed. A test that types the marker
itself cannot catch that, because the test and the tool go stale together.

The other half is the comparison. ``identical_bytes`` is the ceiling on what a
shared asset could save, so it has to refuse to count a part that differs on one
page: a number that flatters the release is worse than no number, because the
release is planned against it.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import page_templates
from page_templates import CHOOSER_MARKER, PAYLOAD_MARKER
from tools.page_bytes import (
    PageBytes,
    SITE_BUDGET_MB,
    identical_bytes,
    main,
    measure_page,
    site_size,
)

PAGE = (
    "<!doctype html><html><head><style>p{color:red}</style></head>"
    '<body><script>const x = 1; '
    + PAYLOAD_MARKER
    + '{"destinations":[{"crs":"GRA"}]}; afterPayload();</script></body></html>'
)


def page_in(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class MeasurePage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_payload_stops_at_its_closing_bracket(self) -> None:
        measured = measure_page(page_in(self.root, "index.html", PAGE))
        self.assertEqual(measured.payload, len('{"destinations":[{"crs":"GRA"}]}'))
        self.assertEqual(measured.rows, 1)

    def test_rows_are_counted_in_a_table_of_cells_as_well_as_in_a_list(self) -> None:
        text = (
            "<script>"
            + PAYLOAD_MARKER
            + '{"destinations":{"columns":["crs"],"rows":[["GRA"],["NOT"]]}};</script>'
        )
        measured = measure_page(page_in(self.root, "index.html", text))
        self.assertEqual(measured.rows, 2)

    def test_the_code_keeps_everything_the_payload_was_hiding(self) -> None:
        measured = measure_page(page_in(self.root, "index.html", PAGE))
        self.assertIn("const x = 1;", measured.code)
        self.assertIn(PAYLOAD_MARKER, measured.code)
        self.assertIn("afterPayload();", measured.code)
        self.assertNotIn('"crs"', measured.code)

    def test_a_payload_a_statement_follows_is_counted_once(self) -> None:
        text = (
            "<script>"
            + PAYLOAD_MARKER
            + '{"rows":[1,2]}'
            "[3].forEach(f);</script>"
        )
        measured = measure_page(page_in(self.root, "index.html", text))
        self.assertEqual(measured.payload, len('{"rows":[1,2]}'))
        self.assertIn("[3].forEach(f);", measured.code)

    def test_an_escaped_closing_tag_is_still_measurable_json(self) -> None:
        text = (
            "<script>"
            + PAYLOAD_MARKER
            + '{"note":"a<\\/script> tag","destinations":[]};</script>'
        )
        measured = measure_page(page_in(self.root, "index.html", text))
        self.assertGreater(measured.payload, 0)
        self.assertEqual(measured.rows, 0)

    def test_both_markers_a_page_can_write_are_measured(self) -> None:
        text = (
            "<script>"
            + CHOOSER_MARKER
            + '[{"name":"Grantham","crs":"GRN"}];</script>'
        )
        measured = measure_page(page_in(self.root, "index.html", text))
        self.assertGreater(measured.payload, 0)
        self.assertEqual(measured.named, 1)

    def test_a_marker_with_no_json_behind_it_is_code(self) -> None:
        text = (
            "<script>"
            + PAYLOAD_MARKER
            + "nothingBehindIt; "
            + CHOOSER_MARKER
            + "notJsonAtAll;</script>"
        )
        measured = measure_page(page_in(self.root, "index.html", text))
        self.assertEqual(measured.payload, 0)
        # Named and unreadable, which is a fact the caller has to be able to act
        # on: it is what separates this page from one that ships no payload.
        self.assertEqual(measured.named, 2)
        self.assertIn(PAYLOAD_MARKER + "nothingBehindIt;", measured.code)

    def test_the_stylesheet_is_measured_separately_from_the_script(self) -> None:
        measured = measure_page(page_in(self.root, "index.html", PAGE))
        self.assertEqual(measured.css, "p{color:red}")
        self.assertEqual(measured.total, len(PAGE.encode("utf-8")))

    def test_a_page_the_template_writes_is_measured(self) -> None:
        """The fixture the tool cannot go stale against.

        The template is the thing that writes a real page, so a page carrying its
        marker is a page the build produces. When this test was written it failed
        on the shipped tool, which reported 0 payload and 0 rows.
        """
        payload = {"destinations": [{"crs": "GRA"}, {"crs": "NOT"}]}
        text = page_templates.TEMPLATE.replace("__DATA__", json.dumps(payload))
        measured = measure_page(page_in(self.root, "index.html", text))
        self.assertGreater(measured.payload, 0)
        self.assertEqual(measured.rows, 2)
        self.assertEqual(measured.named, 1)


class IdenticalBytes(unittest.TestCase):
    def page(self, css: str, code: str, payload: int = 0) -> PageBytes:
        page = PageBytes(path=Path("x"), total=1, css=css, code=code, payload=payload, rows=0)
        return page

    def test_a_part_every_page_shares_is_counted(self) -> None:
        pages = [self.page("a{}", "const x = 1;"), self.page("a{}", "const x = 1;")]
        self.assertEqual(identical_bytes(pages), len("a{}const x = 1;"))

    def test_one_page_that_differs_makes_the_part_its_own(self) -> None:
        pages = [self.page("a{}", "const x = 1;"), self.page("b{}", "const x = 1;")]
        self.assertEqual(identical_bytes(pages), len("const x = 1;"))

    def test_one_page_has_nothing_to_share(self) -> None:
        self.assertEqual(identical_bytes([self.page("a{}", "b")]), 0)


class SiteBudget(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        page_in(self.root, "index.html", PAGE)
        page_in(self.root, "from/grantham/index.html", PAGE)
        page_in(self.root, "release-manifest.json", "{}")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_site_counts_every_file_and_every_page(self) -> None:
        total, pages = site_size(self.root)
        self.assertEqual(pages, 2)
        self.assertEqual(total, sum(len(io.open(p, encoding="utf-8").read().encode()) for p in
                                    (self.root / "index.html", self.root / "release-manifest.json"))
                         + len(PAGE.encode()))

    def test_a_site_over_budget_fails_and_says_by_how_much(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(["--site", str(self.root), "--budget-mb", "0"])
        self.assertEqual(code, 1)
        self.assertIn("over budget", err.getvalue())

    def test_a_site_inside_the_budget_passes_and_names_the_number(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = main(["--site", str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn(f"of a {SITE_BUDGET_MB} MB budget", out.getvalue())
        self.assertIn("over 2 page(s)", out.getvalue())

    def test_a_page_that_cannot_be_read_is_not_a_pass(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = main([str(self.root / "missing.html")])
        self.assertEqual(code, 2)

    def test_two_pages_report_what_they_share(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = main([str(self.root / "index.html"), str(self.root / "from/grantham/index.html")])
        self.assertEqual(code, 0)
        self.assertIn("identical on all 2 measured pages", out.getvalue())

    def test_a_site_with_no_page_is_not_a_pass(self) -> None:
        """An empty tree passed the gate until 18 October 2026.

        It printed "0 MB of a 800 MB budget over 0 page(s)" and exited 0, and that
        is the invocation CI runs. A build that wrote nothing fitted inside the
        budget it was never measured against.
        """
        empty = self.root / "empty"
        empty.mkdir()
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(["--site", str(empty)])
        self.assertEqual(code, 2)
        self.assertIn("no page was found", err.getvalue())

    def test_a_page_failing_to_parse_is_not_a_pass(self) -> None:
        broken = page_in(
            self.root, "broken/index.html", "<script>" + PAYLOAD_MARKER + "{not json};</script>"
        )
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = main([str(broken)])
        self.assertEqual(code, 2)
        self.assertIn("names a payload that did not parse", err.getvalue())

    def test_a_page_that_ships_no_payload_still_passes(self) -> None:
        """The refusal has to be local to the page.

        The privacy route carries no payload, so a check that failed on "no page
        had a payload" would refuse a correct site. It reads the page instead.
        """
        plain = page_in(self.root, "privacy/index.html", "<p>Nothing is collected.</p>")
        with contextlib.redirect_stdout(io.StringIO()):
            code = main([str(plain)])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
