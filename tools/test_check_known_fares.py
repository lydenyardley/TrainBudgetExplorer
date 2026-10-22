"""The known-fares gate reads a built page the way the page prices itself."""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tools import check_known_fares
from tools.check_known_fares import KnownFare, check, read_table

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 22)


def fare(**changes: object) -> KnownFare:
    row = dict(origin="GRN", destination="SLR", mode="return", adults=1, railcard="", pence=640,
               seen_on=date(2026, 10, 5), link="https://www.nationalrail.co.uk/", report="test")
    row.update(changes)
    return KnownFare(**row)  # type: ignore[arg-type]


class KnownFaresTest(unittest.TestCase):
    """Over the synthetic site, whose Grantham page prices Sleaford at £6.40 a
    head, £4.25 with a Two Together or Senior card, and Nottingham's single at
    £7.00, £4.65 with one. The same numbers were read off the page in a browser
    for every mode, party and card when this was written: 321 cells, no
    difference from the gate's arithmetic."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        for command in (
            # The demo site `tools.verify --browser` builds and drives.
            [sys.executable, "make_synthetic_feed.py", str(tmp / "feed"), "--unserved-station", "--third-origin",
             "--return-network", "--long-list", "--knowledgebase", str(tmp / "kb")],
            [sys.executable, "build_demo_page.py", "--feed", str(tmp / "feed"), "--timetable", str(tmp / "feed"),
             "--knowledgebase", str(tmp / "kb"), "--all-origins", "--date", "2026-10-05", "--out", str(tmp / "site" / "index.html")],
        ):
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
        cls.site = tmp / "site"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_a_fare_the_page_shows_passes(self) -> None:
        rows = [
            fare(),
            fare(adults=2, pence=1280),
            fare(adults=2, railcard="2TR", pence=850),
            fare(railcard="SRN", pence=425),
            fare(destination="NOT", mode="single", pence=700),
        ]
        self.assertEqual(check(self.site, rows, DAY), ([], []))

    def test_cheapest_is_the_cheapest_of_the_three_lists_for_who_is_travelling(self) -> None:
        # Nottingham's return is £11.60 and blocks the card; its single is £7.00
        # and takes it. Two people with the card pay 2 x £4.65.
        self.assertEqual(check(self.site, [fare(destination="NOT", mode="cheapest", adults=2, railcard="2TR", pence=930)], DAY), ([], []))
        failures, _ = check(self.site, [fare(destination="NOT", mode="return", adults=2, railcard="2TR", pence=930)], DAY)
        self.assertIn("the page shows £23.20", failures[0])

    def test_a_fare_the_page_does_not_show_fails_naming_both_prices(self) -> None:
        failures, _ = check(self.site, [fare(pence=660)], DAY)
        self.assertEqual(len(failures), 1)
        self.assertIn("the page shows £6.40, and National Rail sold £6.60 on 2026-10-05", failures[0])

    def test_a_row_the_page_cannot_answer_fails_rather_than_passes(self) -> None:
        for row, reason in (
            (fare(origin="XXX"), "the site has no page for XXX"),
            (fare(destination="ZZZ"), "the page lists no ZZZ in its return fares"),
            (fare(railcard="NOPE"), "the page offers no NOPE railcard"),
            (fare(railcard="2TR"), "2TR does not cover 1 adult(s)"),
        ):
            with self.subTest(reason=reason):
                failures, _ = check(self.site, [row], DAY)
                self.assertTrue(failures and reason in failures[0], failures)

    def test_an_old_row_warns_and_still_checks(self) -> None:
        failures, warnings = check(self.site, [fare(seen_on=date(2026, 7, 1))], DAY)
        self.assertEqual(failures, [])
        self.assertIn("checked 113 days ago", warnings[0])

    def test_the_command_exits_on_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "fares.toml"
            good = '[[fare]]\norigin="GRN"\ndestination="SLR"\nmode="return"\nadults=1\npence=640\nseen_on=2026-10-05\nlink="x"\n'
            for text, code in ((good, 0), (good.replace("640", "641"), 1), ("# nothing\n", 2), (good.replace('"return"', '"advance"'), 2)):
                table.write_text(text, encoding="utf-8")
                with self.subTest(code=code), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(check_known_fares.main(["--site", str(self.site), "--table", str(table), "--today", "2026-10-22"]), code)


class TableTest(unittest.TestCase):
    def test_the_shipped_table_reads_and_names_its_sources(self) -> None:
        rows = read_table(check_known_fares.TABLE)
        self.assertGreaterEqual(len(rows), 4)
        for row in rows:
            with self.subTest(row=str(row)):
                self.assertTrue(row.link.startswith("https://www.nationalrail.co.uk/"))
                self.assertTrue(row.report)


if __name__ == "__main__":
    unittest.main()
