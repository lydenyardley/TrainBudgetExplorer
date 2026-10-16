"""Tests for the source-credit check.

The check exists because the flag that turns the credit on is not the flag the
build gate reads: ``release_gate_problems`` refuses a public build with no
notice at all, so a notice set that drops ``nre`` ships station pages with no
acknowledgement and nothing says so. The tests are about that gap -- a fare page
missing one half of the acknowledgement, a fare page missing both, and the pages
that are legitimately not asked.

Two of them tie the check to the code it reads rather than to strings invented
here: the payload marker has to be the one the station template writes, and the
two credit marks have to be the ones ``build_release`` writes. A check whose
marker drifted is a check that passes having found nothing, which is the outcome
it exists to prevent.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from build_release import nre_attribution, nre_source_line
from page_templates import TEMPLATE
from tools.check_source_credit import (
    CREDIT_MARKS,
    FARE_MARK,
    credit_gaps,
    main,
    site_pages,
)

LOGO = CREDIT_MARKS["the 'Powered by National Rail Enquiries' mark"]
WORDS = CREDIT_MARKS["the National Rail Enquiries acknowledgement"]


def fare_page(*marks: str) -> str:
    return "<!doctype html><html><body><script>" + FARE_MARK + " = {};</script>" + "".join(marks) + "</body></html>"


def other_page(body: str = "") -> str:
    return "<!doctype html><html><body>" + body + "</body></html>"


def run(capsys_argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(capsys_argv)
    return code, out.getvalue(), err.getvalue()


class CreditGapsTest(unittest.TestCase):
    def test_a_fare_page_with_both_marks_is_clean(self) -> None:
        problems, showing = credit_gaps({"from/grantham/index.html": fare_page(LOGO, WORDS)})
        self.assertEqual(problems, [])
        self.assertEqual(showing, 1)

    def test_a_fare_page_missing_the_mark_names_that_half(self) -> None:
        problems, _ = credit_gaps({"from/grantham/index.html": fare_page(WORDS)})
        self.assertEqual(len(problems), 1)
        self.assertIn("Powered by National Rail Enquiries", problems[0])
        self.assertNotIn("acknowledgement", problems[0])

    def test_a_fare_page_missing_both_halves_names_both(self) -> None:
        problems, _ = credit_gaps({"from/grantham/index.html": fare_page()})
        self.assertEqual(len(problems), 1)
        self.assertIn("Powered by National Rail Enquiries", problems[0])
        self.assertIn("National Rail Enquiries acknowledgement", problems[0])

    def test_a_page_without_the_fare_payload_is_not_asked(self) -> None:
        # The chooser and the privacy notice: no fare, no station, no credit
        # asked for. The reading this encodes is recorded in
        # licences/release-clearance.md.
        problems, showing = credit_gaps(
            {"index.html": other_page("a station index"), "privacy/index.html": other_page()}
        )
        self.assertEqual(problems, [])
        self.assertEqual(showing, 0)


class MarkerTiesTest(unittest.TestCase):
    def test_the_payload_marker_is_the_one_the_station_template_writes(self) -> None:
        self.assertIn(FARE_MARK, TEMPLATE)

    def test_the_credit_marks_are_the_ones_build_release_writes(self) -> None:
        self.assertIn(LOGO, nre_attribution())
        self.assertIn(WORDS, nre_source_line())


class MainTest(unittest.TestCase):
    def _site(self, pages: dict[str, str]) -> Path:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(directory, ignore_errors=True))
        for name, text in pages.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return directory

    def test_a_credited_fare_page_passes(self) -> None:
        site = self._site({"from/grantham/index.html": fare_page(LOGO, WORDS)})
        code, out, _ = run(["--site", str(site)])
        self.assertEqual(code, 0)
        self.assertIn("every one carries the National Rail credit", out)
        self.assertEqual(site_pages(site).keys(), {"from/grantham/index.html"})

    def test_an_uncredited_fare_page_fails_and_names_itself(self) -> None:
        site = self._site({"from/grantham/index.html": fare_page()})
        code, _, err = run(["--site", str(site)])
        self.assertEqual(code, 1)
        self.assertIn("from/grantham/index.html", err)

    def test_a_site_with_no_fare_page_refuses_rather_than_passing(self) -> None:
        site = self._site({"index.html": other_page("a station index")})
        code, _, err = run(["--site", str(site)])
        self.assertEqual(code, 2)
        self.assertIn("carries the feed's fares", err)

    def test_an_empty_site_refuses_rather_than_passing(self) -> None:
        site = self._site({})
        code, _, err = run(["--site", str(site)])
        self.assertEqual(code, 2)
        self.assertIn("no HTML page was read", err)

    def test_a_missing_site_refuses(self) -> None:
        code, _, err = run(["--site", str(Path(tempfile.mkdtemp()) / "nope")])
        self.assertEqual(code, 2)
        self.assertIn("is not a folder", err)


if __name__ == "__main__":
    unittest.main()
