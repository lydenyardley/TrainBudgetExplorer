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
    row = dict(origin="GRN", destination="LCN", mode="return", adults=1, railcard="", pence=870,
               seen_on=date(2026, 10, 5), link="https://www.nationalrail.co.uk/", report="test")
    row.update(changes)
    return KnownFare(**row)  # type: ignore[arg-type]


class KnownFaresTest(unittest.TestCase):
    """Over the synthetic site, whose Grantham page prices Lincoln at £8.70 a
    head, £5.80 with a Two Together or Senior card, and Nottingham's single at
    £7.00, £4.65 with one. The numbers are the feed's: `tests/test_build_fares`
    holds Lincoln's £8.70 and the £5.80 its card gives from the fare records, so
    an error in either reading shows up here as a disagreement rather than as
    two copies of one mistake.

    Sleaford, whose £6.40 and £4.25 rows these were until 24 October 2026, left
    the page when ADR-0076 stopped listing a place no journey reaches: the
    fixture's timetable calls at neither, so the fare feed prices it and the
    page drops it. A known-fare row for it would fail the gate for a reason that
    is not about the price.

    So the site is built three ways, because what the page leaves out is what a
    row's absence means: with the timetable (ADR-0076 drops the places no
    journey reaches), with the place cap at two (ADR-0077 stops after
    Grantham's two cheapest places), and fares only (no week, so it drops
    nothing, ADR-0076 decision 3).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        subprocess.run(
            [sys.executable, "-m", "trainbudget.feeds.make_synthetic_feed", str(tmp / "feed"), "--unserved-station", "--third-origin",
             "--return-network", "--long-list", "--knowledgebase", str(tmp / "kb")],
            cwd=ROOT, check=True, capture_output=True,
        )
        for name, extra in (
            # The demo site `tools.verify --browser` builds and drives.
            ("site", ["--timetable", str(tmp / "feed"), "--date", "2026-10-05"]),
            ("capped", ["--timetable", str(tmp / "feed"), "--date", "2026-10-05", "--max-places", "2"]),
            ("fares", []),
        ):
            subprocess.run(
                [sys.executable, "-m", "trainbudget.build.build_demo_page", "--feed", str(tmp / "feed"),
                 "--knowledgebase", str(tmp / "kb"), "--all-origins", *extra,
                 "--out", str(tmp / name / "index.html")],
                cwd=ROOT, check=True, capture_output=True,
            )
        cls.site = tmp / "site"
        cls.capped = tmp / "capped"
        cls.fares_only = tmp / "fares"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_a_fare_the_page_shows_passes(self) -> None:
        rows = [
            fare(),
            fare(adults=2, pence=1740),
            fare(adults=2, railcard="2TR", pence=1160),
            fare(railcard="SRN", pence=580),
            fare(destination="NOT", mode="single", pence=700),
        ]
        self.assertEqual(check(self.site, rows, DAY), ([], []))

    def test_the_station_index_is_read_past_the_facts_below_it(self) -> None:
        # The asset holds two documents since ADR-0069's amendment: the picker's
        # options, then every station's own facts. The 24 October 2026 assemble
        # job stopped on `Extra data: line 1 column 233653` because the gate read
        # from the first `=` to the end of the file, so the facts arrived as data
        # after the options and no release could be checked at all.
        asset = (self.site / "stations.js").read_text(encoding="utf-8")
        self.assertIn("window.TBE_STATION_FACTS", asset)
        pages = check_known_fares.station_pages(self.site)
        self.assertEqual(
            {crs: page.relative_to(self.site).as_posix() for crs, page in pages.items()},
            {
                "GRN": "from/grantham/index.html",
                "LCN": "from/lincoln/index.html",
                "NOT": "from/nottingham/index.html",
            },
        )

    def test_an_asset_with_no_station_index_is_a_site_it_could_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "stations.js").write_text("window.TBE_STATION_FACTS = {};\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "carries no station index"):
                check_known_fares.station_pages(Path(tmp))

    def test_cheapest_is_the_cheapest_of_the_three_lists_for_who_is_travelling(self) -> None:
        # Nottingham's return is £11.60 and blocks the card; its single is £7.00
        # and takes it. Two people with the card pay 2 x £4.65.
        self.assertEqual(check(self.site, [fare(destination="NOT", mode="cheapest", adults=2, railcard="2TR", pence=930)], DAY), ([], []))
        failures, _ = check(self.site, [fare(destination="NOT", mode="return", adults=2, railcard="2TR", pence=930)], DAY)
        self.assertIn("the page shows £23.20", failures[0])

    def test_a_fare_the_page_does_not_show_fails_naming_both_prices(self) -> None:
        failures, _ = check(self.site, [fare(pence=890)], DAY)
        self.assertEqual(len(failures), 1)
        self.assertIn("the page shows £8.70, and National Rail sold £8.90 on 2026-10-05", failures[0])

    def test_a_row_the_page_cannot_answer_fails_rather_than_passes(self) -> None:
        for row, reason in (
            (fare(origin="XXX"), "the site has no page for XXX"),
            (fare(railcard="NOPE"), "the page offers no NOPE railcard"),
            (fare(railcard="2TR"), "2TR does not cover 1 adult(s)"),
        ):
            with self.subTest(reason=reason):
                failures, _ = check(self.site, [row], DAY)
                self.assertTrue(failures and reason in failures[0], failures)

    def test_a_place_the_reachability_rule_dropped_warns_rather_than_fails(self) -> None:
        # Tower Hill is priced from Grantham and called at by no service, so the
        # timetable build drops it (ADR-0076). The fares-only build drops
        # nothing and lists it at £12.00, which is what makes this row a check
        # rather than a hole: the fare exists, and only the rule removed it.
        row = fare(destination="SLP", pence=1200)
        failures, warnings = check(self.site, [row], DAY)
        self.assertEqual(failures, [])
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("the page lists no SLP in any of its fare lists", warnings[0])
        self.assertIn("it leaves 17 places out because no journey from here reaches them within one change", warnings[0])
        self.assertEqual(check(self.fares_only, [row], DAY), ([], []))

    def test_a_place_the_cap_left_out_warns_naming_the_stop(self) -> None:
        # The capped build stops after Grantham's two cheapest places, so
        # Sleaford at £41.10 is priced and reached and still not on it. The
        # uncapped build lists it at that price, so the row is a real fare the
        # cap put beyond the page rather than one the page lost.
        row = fare(destination="SLD", pence=4110)
        failures, warnings = check(self.capped, [row], DAY)
        self.assertEqual(failures, [])
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("it stops before 3 places dearer than the ones it lists", warnings[0])
        self.assertEqual(check(self.site, [row], DAY), ([], []))

    def test_the_sentence_words_one_place_and_a_direct_only_build(self) -> None:
        # Both shapes are real: a page can lose exactly one place
        # (tests/test_build_demo_page builds one), and --max-changes 0 is a
        # build the command accepts, which the page words "on a direct train".
        # A warning saying "them" of one place, or naming no bound where the
        # build allowed no change, would describe a page that is not this one.
        self.assertEqual(
            check_known_fares.left_out({"unreachableDestinationCount": 1, "maxChanges": 0}),
            "it leaves 1 place out because no journey from here reaches it on a direct train",
        )
        self.assertEqual(
            check_known_fares.left_out({"unreachableDestinationCount": 2, "maxChanges": None}),
            "it leaves 2 places out because no journey from here reaches them",
        )

    def test_a_place_no_rule_dropped_still_fails(self) -> None:
        # A fares-only build carries no week, so it drops nothing and reports no
        # place left out. An absent place there is a fare the page lost, and the
        # gate stops on it rather than reading the absence as a rule's work.
        failures, warnings = check(self.fares_only, [fare(destination="ZZZ")], DAY)
        self.assertEqual(warnings, [])
        self.assertEqual(len(failures), 1, failures)
        self.assertIn("the page lists no ZZZ in any of its fare lists, and left no place out", failures[0])

    def test_a_place_listed_with_no_fare_of_the_row_kind_fails_and_names_the_lists(self) -> None:
        # Lincoln is listed in the return and anytime fares and in no single
        # one. No rule drops a mode, so a single row for it is a disagreement
        # worth stopping on rather than an absence the page explains.
        failures, warnings = check(self.site, [fare(destination="LCN", mode="single", pence=580)], DAY)
        self.assertEqual(warnings, [])
        self.assertEqual(len(failures), 1, failures)
        self.assertIn(
            "the page shows no single fare to LCN, though it lists the place in its return and anytime fares",
            failures[0],
        )

    def test_an_old_row_warns_and_still_checks(self) -> None:
        failures, warnings = check(self.site, [fare(seen_on=date(2026, 7, 1))], DAY)
        self.assertEqual(failures, [])
        self.assertIn("checked 113 days ago", warnings[0])

    def test_the_command_exits_on_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "fares.toml"
            good = '[[fare]]\norigin="GRN"\ndestination="LCN"\nmode="return"\nadults=1\npence=870\nseen_on=2026-10-05\nlink="x"\n'
            for text, code in ((good, 0), (good.replace("870", "871"), 1), ("# nothing\n", 2), (good.replace('"return"', '"advance"'), 2)):
                table.write_text(text, encoding="utf-8")
                with self.subTest(code=code), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(check_known_fares.main(["--site", str(self.site), "--table", str(table), "--today", "2026-10-22"]), code)

    def test_the_last_line_counts_the_rows_it_could_check(self) -> None:
        # A release whose last line said every row agreed would claim a
        # comparison it did not make: Tower Hill's row has no price to read on
        # this build, and the sentence counts it apart.
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "fares.toml"
            row = '[[fare]]\norigin="GRN"\ndestination="{}"\nmode="return"\nadults=1\npence={}\nseen_on=2026-10-05\nlink="x"\n'
            table.write_text(row.format("LCN", 870) + row.format("SLP", 1200), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = check_known_fares.main(["--site", str(self.site), "--table", str(table), "--today", "2026-10-22"])
        self.assertEqual(code, 0)
        self.assertIn("1 of 2 known fare(s) agree with the pages; 1 could not be checked here", out.getvalue())

    def test_a_table_with_nothing_to_compare_fails_rather_than_reads_green(self) -> None:
        # The module's own rule, one level up: a check that cannot find its
        # subject has checked nothing. Before this, a table whose every row was
        # for a place the page drops by rule would pass the release having
        # compared no price at all.
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "fares.toml"
            table.write_text(
                '[[fare]]\norigin="GRN"\ndestination="SLP"\nmode="return"\nadults=1\npence=1200\n'
                'seen_on=2026-10-05\nlink="https://www.nationalrail.co.uk/x"\n',
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = check_known_fares.main(["--site", str(self.site), "--table", str(table), "--today", "2026-10-22"])
        self.assertEqual(code, 1)
        self.assertIn("not one price was compared; add a row for a place the page lists", out.getvalue())


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
