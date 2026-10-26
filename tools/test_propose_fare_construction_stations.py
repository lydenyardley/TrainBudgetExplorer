"""Tests for the fare-construction proposal tool.

The tool prints proposals and writes nothing. What has to hold is that it
proposes exactly what the name markers catch, says which of them are already
reviewed, and says so when a reviewed code no longer matches a name -- the
other direction of the same staleness.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from trainbudget.fares.atoc_fares import FARE_CONSTRUCTION_CRS
from tools import propose_fare_construction_stations as proposer


class Station:
    def __init__(self, name: str) -> None:
        self.name = name


class ProposalsTest(unittest.TestCase):
    def test_only_the_marked_names_are_proposed(self) -> None:
        stations = {
            "QAH": Station("BOUNDARY ZONE 4"),
            "KLB": Station("KINGS LYNN COACH"),
            "GRN": Station("GRANTHAM"),
            "ZBF": Station("BLACKFRIARS UND"),
        }
        self.assertEqual(
            proposer.proposals(stations), [("KLB", "KINGS LYNN COACH", True), ("QAH", "BOUNDARY ZONE 4", True)]
        )

    def test_a_code_the_list_does_not_hold_is_marked_for_review(self) -> None:
        rows = proposer.proposals({"QZZ": Station("BRIGHTON ZONE 7")})
        self.assertEqual(rows, [("QZZ", "BRIGHTON ZONE 7", False)])

    def test_the_report_separates_new_codes_from_agreed_ones(self) -> None:
        text = proposer.render(
            [("QAH", "BOUNDARY ZONE 4", True), ("QZZ", "BRIGHTON ZONE 7", False)],
            emit_code=True,
        )
        self.assertIn("1 already on the reviewed list, 1 to decide", text)
        self.assertIn("on the reviewed list", text)
        self.assertIn("NOT YET REVIEWED", text)
        self.assertIn('"QZZ",', text)
        self.assertNotIn('"QAH",', text)

    def test_a_reviewed_code_matching_no_name_is_reported(self) -> None:
        # The other direction of staleness: the feed renamed a zone, so the
        # reviewed code now names nothing the markers would have caught.
        text = proposer.render([("QAH", "BOUNDARY ZONE 4", True)], emit_code=False)
        self.assertIn(f"{len(FARE_CONSTRUCTION_CRS) - 1} reviewed code(s) match no station", text)
        self.assertIn("renamed or withdrew", text)

    def test_a_feed_with_no_marked_names_still_says_so(self) -> None:
        text = proposer.render([], emit_code=True)
        self.assertIn("None", text)
        self.assertIn("the markers changed", text)

    def test_emit_code_prints_nothing_when_there_is_nothing_to_review(self) -> None:
        text = proposer.render([("QAH", "BOUNDARY ZONE 4", True)], emit_code=True)
        self.assertNotIn("codes to review", text)


class ResolveFeedTest(unittest.TestCase):
    """A DTD download is named as a folder or as the archive inside it."""

    def test_a_folder_holding_one_archive_is_opened_through_to_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "fares"
            folder.mkdir()
            archive = folder / "dtd-fares.zip"
            archive.write_bytes(b"not really a zip")
            self.assertEqual(proposer.resolve_feed(folder), archive)

    def test_a_folder_with_several_archives_is_left_to_the_station_reader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "fares"
            folder.mkdir()
            (folder / "a.zip").write_bytes(b"")
            (folder / "b.zip").write_bytes(b"")
            self.assertEqual(proposer.resolve_feed(folder), folder)

    def test_a_file_is_left_alone(self) -> None:
        archive = Path("feeds/dtd-fares.zip")
        self.assertEqual(proposer.resolve_feed(archive), archive)


class MainTest(unittest.TestCase):
    def test_a_missing_feed_is_refused_not_guessed_at(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(proposer.main(["--feed", "no-such-feed"]), 2)
        self.assertIn("no feed at", stderr.getvalue())

    def test_the_run_reads_the_station_records_and_prints_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            feed = Path(tmp) / "dtd-fares.zip"
            feed.write_bytes(b"")
            with mock.patch.object(proposer, "load_stations") as load:
                load.return_value.locations_by_crs = {"QAH": Station("BOUNDARY ZONE 4")}
                out = io.StringIO()
                with redirect_stderr(io.StringIO()), redirect_stdout(out):
                    code = proposer.main(["--feed", str(feed)])
        self.assertEqual(code, 0)
        self.assertIn("BOUNDARY ZONE 4", out.getvalue())
        self.assertIn("1 already on the reviewed list, 0 to decide", out.getvalue())
        self.assertIn(
            "11 reviewed code(s) match no station carrying those markers",
            out.getvalue(),
            "a feed that has lost eleven of them says so",
        )


if __name__ == "__main__":
    unittest.main()
