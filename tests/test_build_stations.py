"""What `build_stations.py` runs, and what it asks for before it runs it.

The wrapper is the command `README.md` documents, so its two claims are the ones
a reader acts on: that the flags they passed reach the builder, and that the
feeds it says it needs are the feeds it actually reads. Both are about the
arguments, so they are tested as arguments rather than by running a build.

An index changes the second claim. The point of a per-origin slice index is a
machine that does not hold the national timetable, and a wrapper that demanded
the timetable folder anyway would make the feature unreachable from the command
the documentation gives.
"""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from trainbudget.build.build_stations import build_command, missing_feeds


class MissingFeedsTest(unittest.TestCase):
    """Which feed folders a build is refused without."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def feed(self, name: str) -> Path:
        """A folder with a file in it, which is what the check asks for."""
        path = self.root / name
        path.mkdir()
        (path / "anything.dat").write_text("x", encoding="utf-8")
        return path

    def test_a_build_without_an_index_needs_the_timetable_folder(self) -> None:
        absent = self.root / "absent"
        self.assertEqual(
            missing_feeds(self.feed("fares"), absent, self.feed("kb")), [absent]
        )

    def test_a_build_with_an_index_does_not_ask_for_the_timetable_folder(self) -> None:
        absent = self.root / "absent"
        self.assertEqual(
            missing_feeds(self.feed("fares"), absent, self.feed("kb"), self.feed("index")),
            [],
            "an index build reads the slices, not the feed it has no room for",
        )


class BuildCommandTest(unittest.TestCase):
    """The command line the wrapper assembles."""

    def args(self, index: Path | None = None) -> argparse.Namespace:
        return argparse.Namespace(
            feed=Path("fares"),
            timetable=Path("timetable"),
            knowledgebase=Path("kb"),
            date="2026-10-07",
            workers=1,
            out=Path("_stations/index.html"),
            timetable_index=index,
        )

    def test_an_index_is_passed_through_to_the_builder(self) -> None:
        command = build_command(self.args(Path("index")), ["GRA", "NOT"])
        self.assertIn("--timetable-index", command)
        self.assertEqual(command[command.index("--timetable-index") + 1], "index")

    def test_no_index_means_no_flag(self) -> None:
        # Omitted rather than passed empty: the builder's default is no index,
        # and an empty path argues with it.
        self.assertNotIn("--timetable-index", build_command(self.args(), ["GRA"]))

    def test_the_station_subset_and_the_feed_still_reach_the_builder(self) -> None:
        command = build_command(self.args(Path("index")), ["GRA", "NOT"])
        self.assertEqual(command[command.index("--only-stations") + 1], "GRA,NOT")
        self.assertEqual(command[command.index("--timetable") + 1], "timetable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
