"""Tests for the reviewed settlement proposal tool.

The tool prints evidence and writes nothing, so what has to hold is that it is
*selective*: it names a disagreement between a reviewed class and the workbook
where the two are about the same settlement, and it stays quiet where they are
not. A tool that flags everything is a tool nobody reads, so the near-miss rule
is tested at its edges as hard as its middle -- "Ham" is not Hamilton, and a
settlement of the same name in another county is not evidence of anything.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from atoc_fares import LONDON_STATION_CRS, LOCATION, FaresDb, Location
from make_synthetic_feed import _line
from tools import propose_reviewed_settlements as proposer


def area(name: str, kind: str) -> dict[str, str]:
    """A workbook row as ``_read_ons_built_up_areas`` returns it."""
    return {"name": name, "type": kind, "band": kind}


def areas(*rows: tuple[str, str]) -> dict[str, dict[str, str]]:
    # The workbook is keyed by the normalised settlement name, punctuation and
    # all -- "Newton-le-Willows" is stored as NEWTONLEWILLOWS -- so a test
    # workbook that keys on the raw string is not the one the tool reads.
    return {_normalise(row[0]): area(*row) for row in rows}


def _normalise(value: str) -> str:
    return FaresDb._normalise_settlement_name(value)


class Station:
    def __init__(self, name: str) -> None:
        self.name = name


class ReviewedEntriesTest(unittest.TestCase):
    def test_all_three_lists_are_read_and_london_is_a_city(self) -> None:
        entries = proposer.reviewed_entries()
        for crs in LONDON_STATION_CRS:
            self.assertEqual(entries[crs], "city", crs)
        # A code on two lists is one entry, not two, so the report cannot print
        # the same station twice with two classes.
        self.assertEqual(len(entries), len(set(entries)))


class NearMissTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FaresDb()

    def test_a_qualifier_is_a_near_miss(self) -> None:
        found = proposer.near_misses(
            self.db, "NEWTON LE WILL", areas(("Newton-le-Willows", "town"))
        )
        self.assertEqual(found, [("Newton-le-Willows", "town")])

    def test_a_short_settlement_name_is_not_evidence(self) -> None:
        # "Ham" shares three characters with Hamilton Central and proves
        # nothing. Flagging it made the report mostly noise.
        self.assertEqual(
            proposer.near_misses(self.db, "HAMILTON CENTRAL", areas(("Ham", "village"))), []
        )

    def test_a_long_different_settlement_is_not_a_near_miss(self) -> None:
        # The upper bound as well as the lower: Bathgate is not Bath, and the
        # extension rule has to stop somewhere.
        self.assertEqual(
            proposer.near_misses(self.db, "BATHGATE", areas(("Bathampton", "village"))), []
        )

    def test_an_exact_match_is_not_a_near_miss(self) -> None:
        # The reader owns exact matches; reporting them as near misses too
        # would blame the matcher for a lookup that worked.
        self.assertEqual(proposer.near_misses(self.db, "YORK", areas(("York", "city"))), [])

    def test_a_station_with_no_name_has_no_near_miss(self) -> None:
        self.assertEqual(proposer.near_misses(self.db, "", areas(("York", "city"))), [])
        self.assertEqual(proposer.near_misses(self.db, "  ", areas(("York", "city"))), [])


class ProposalsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FaresDb()
        # Reviewed: LDY is a village and PER is a village, and both are read
        # from the live lists, so the report reflects the shipped data.
        self.stations = {
            "LDY": Station("LADYBANK"),
            "PER": Station("PENRHIWCEIBER"),
            "RDF": Station("RADCLIFFE ON TRT"),
            "YRK": Station("YORK"),
        }
        self.workbook = areas(
            ("Ladybank", "village"),
            ("Radcliffe", "town"),
            ("York", "city"),
            ("Newton-le-Willows", "town"),
        )

    def rows(self) -> dict[str, dict]:
        return {
            str(row["crs"]): row
            for row in proposer.proposals(self.db, self.stations, self.workbook)
        }

    def test_a_workbook_match_with_the_same_class_is_in_agreement(self) -> None:
        row = self.rows()["LDY"]
        self.assertEqual(row["verdict"], proposer.AGREED)
        self.assertEqual(row["band"], "village")

    def test_a_workbook_match_with_a_different_class_is_named(self) -> None:
        # A reviewed entry the workbook covers is one the build refuses, and
        # the tool has to point at it rather than report it as agreement.
        with mock.patch.dict(
            proposer.MAJOR_UK_STATION_FALLBACKS, {"LDY": "city"}, clear=False
        ):
            row = self.rows()["LDY"]
        self.assertEqual(row["verdict"], proposer.NAMED)
        self.assertEqual(row["band"], "village")

    def test_a_disagreeing_near_miss_is_the_verdict_the_report_is_for(self) -> None:
        # Radcliffe-on-Trent is a village; the workbook's Radcliffe is in
        # Greater Manchester and is a town. Same name, different place, so the
        # tool flags it and the parser must not act on it.
        row = self.rows()["RDF"]
        self.assertEqual(row["verdict"], proposer.DECIDE)
        self.assertEqual(row["matches"], [("Radcliffe", "town")])

    def test_a_corroborating_near_miss_settles_the_row(self) -> None:
        # "Newcastle" reads as Newcastle Emlyn and as Newcastle upon Tyne. One
        # of them backs the reviewed class, so the row is agreement and not a
        # decision a reviewer has to make.
        stations = {"NCL": Station("NEWCASTLE")}
        workbook = areas(("Newcastle Emlyn", "village"), ("Newcastle upon Tyne", "city"))
        row = [
            r for r in proposer.proposals(self.db, stations, workbook) if r["crs"] == "NCL"
        ][0]
        self.assertEqual(row["verdict"], proposer.AGREED)

    def test_a_code_this_feed_does_not_carry_is_left_to_the_gate(self) -> None:
        # Nothing to compare against, so the tool must not call it agreed and
        # must not call it deletable either: a code the feed dropped is the
        # build's gate to report, not evidence that the entry was wrong.
        rows = {r["crs"]: r for r in proposer.proposals(self.db, {}, self.workbook)}
        self.assertIn("PER", rows)
        self.assertEqual(rows["PER"]["name"], "<NOT IN THIS FEED>")
        self.assertEqual(rows["PER"]["verdict"], proposer.ABSENT)

    def test_the_station_name_is_reported_next_to_the_code(self) -> None:
        row = self.rows()["PER"]
        self.assertEqual(row["name"], "PENRHIWCEIBER")
        self.assertEqual(row["reviewed"], "village")


class RenderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FaresDb()
        self.rows = proposer.proposals(
            self.db,
            {"LDY": Station("LADYBANK"), "RDF": Station("RADCLIFFE ON TRT")},
            areas(("Ladybank", "village"), ("Radcliffe", "town")),
        )

    def test_the_tally_counts_every_verdict(self) -> None:
        said = proposer.render(self.rows, only=None)
        self.assertIn("reviewed entries:", said)
        self.assertIn("to decide", said)
        self.assertIn("in agreement", said)

    def test_a_feed_that_carries_none_of_them_says_so_instead_of_condemning_all(self) -> None:
        # The false and alarming report: a feed the reader failed to parse would
        # otherwise come back as "306 entries to delete", which is a claim about
        # the lists and a reason to act on it.
        rows = proposer.proposals(self.db, {}, areas(("Ladybank", "village")))
        said = proposer.render(rows, only=None)
        self.assertIn("That is every entry", said)
        self.assertIn("0 to delete", said)

    def test_the_report_says_a_near_miss_is_not_a_match(self) -> None:
        # The reason none of this is wired into the parser, stated in the
        # output rather than only in the docstring.
        self.assertIn("not a match", proposer.render(self.rows, only=None))

    def test_only_filters_to_one_verdict(self) -> None:
        said = proposer.render(self.rows, only=proposer.DECIDE)
        self.assertIn("RDF", said)
        self.assertNotIn("LADYBANK", said)
        self.assertIn("Nothing to show for decide", proposer.render([], only=proposer.DECIDE))

    def test_asking_for_agreement_lists_it(self) -> None:
        # Agreement is the tally's job by default, but a reader who asked for
        # it has said they want the rows, not another number.
        said = proposer.render(self.rows, only=proposer.AGREED)
        self.assertIn("LADYBANK", said)
        self.assertNotIn("RADCLIFFE", said)


class MainTest(unittest.TestCase):
    def test_a_missing_feed_is_refused_rather_than_reported_empty(self) -> None:
        # "Nothing disagrees" is a claim the tool cannot support without a
        # feed, so the absence has to be loud.
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = proposer.main(["--feed", str(Path("no-such-feed"))])
        self.assertEqual(code, 2)
        self.assertIn("no feed at", stderr.getvalue())

    def test_an_unreadable_workbook_is_refused_rather_than_reported_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            feed = Path(tmp) / "fares"
            feed.mkdir()
            with mock.patch.object(
                proposer, "download_areas", side_effect=OSError("no network")
            ):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = proposer.main(["--feed", str(feed)])
        self.assertEqual(code, 2)
        self.assertIn("could not be read", stderr.getvalue())

    def test_the_whole_report_runs_end_to_end_without_the_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            feed = Path(tmp) / "fares"
            feed.mkdir()
            (feed / "rjfaf.loc").write_text(
                _line(
                    {
                        "update_marker": "A",
                        "record_type": "L",
                        "nlc": "1",
                        "description": "LADYBANK",
                        "crs": "LDY",
                    },
                    LOCATION,
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with mock.patch.object(
                proposer, "download_areas", return_value=areas(("Ladybank", "village"))
            ):
                with redirect_stdout(stdout):
                    code = proposer.main(["--feed", str(feed)])
        self.assertEqual(code, 0)
        said = stdout.getvalue()
        # The one station this feed carries is corroborated, and the report
        # says so rather than condemning every other entry.
        self.assertIn("0 to delete", said)
        self.assertIn("1 in agreement", said)
        self.assertIn("305 not in this feed", said)


if __name__ == "__main__":
    unittest.main(verbosity=2)
