"""Tests for the shared feed-CLI plumbing.

`add_feed_args` now declares three shapes -- a required feed, a defaulted feed,
and a fares-only tool with no timetable flag at all -- and `load_feeds` is the
one call every tool makes afterwards. A tool that takes the fares-only shape
must still be able to load, so the pair is tested together rather than
separately: each argument shape in, one load out.
"""

from __future__ import annotations

import argparse
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest import mock

import feeds_cli
from feeds_cli import add_feed_args, find_origin, load_feeds


def parse(build) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    build(parser)
    return parser.parse_args([])


class FeedArgumentsTest(unittest.TestCase):
    def test_a_tool_with_no_default_has_to_name_its_feed(self) -> None:
        parser = argparse.ArgumentParser()
        add_feed_args(parser)
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            parser.parse_args([])

    def test_a_tool_with_a_default_runs_bare(self) -> None:
        args = parse(lambda p: add_feed_args(p, feed_default=Path("feeds/fares.zip")))
        self.assertEqual(args.feed, Path("feeds/fares.zip"))
        self.assertIsNone(args.timetable)

    def test_a_fares_only_tool_has_no_timetable_flag(self) -> None:
        args = parse(lambda p: add_feed_args(p, feed_default=Path("f"), fares_only=True))
        self.assertFalse(hasattr(args, "timetable"))

    def test_a_required_timetable_is_enforced(self) -> None:
        parser = argparse.ArgumentParser()
        add_feed_args(parser, timetable_required=True)
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--feed", "f"])
        self.assertEqual(parser.parse_args(["--feed", "f", "--timetable", "t"]).timetable, "t")


class LoadFeedsTest(unittest.TestCase):
    """The load pair, once per argument shape `add_feed_args` can leave."""

    def load(self, args) -> tuple:
        with mock.patch.object(feeds_cli, "FaresDb") as fares, mock.patch.object(
            feeds_cli, "TimetableDb"
        ) as timetable:
            return load_feeds(args) + (fares, timetable)

    def test_a_fares_only_tool_loads_without_a_timetable(self) -> None:
        # fares_only never declared --timetable, so reading the attribute
        # directly raised AttributeError here and took the tool's whole run
        # with it.
        args = parse(lambda p: add_feed_args(p, feed_default=Path("f"), fares_only=True))
        fares_db, timetable_db, fares, timetable = self.load(args)
        fares.return_value.load_feed.assert_called_once_with(Path("f"))
        self.assertIsNone(timetable_db)
        timetable.return_value.load_feed.assert_not_called()

    def test_a_timetable_is_loaded_when_one_is_named(self) -> None:
        args = parse(lambda p: add_feed_args(p, feed_default=Path("f")))
        args.timetable = Path("t")
        fares_db, timetable_db, _fares, timetable = self.load(args)
        self.assertIsNotNone(timetable_db)
        timetable.return_value.load_feed.assert_called_once_with(Path("t"))


class FindOriginTest(unittest.TestCase):
    def test_a_known_origin_is_found_and_normalised(self) -> None:
        location = object()
        with mock.patch.object(feeds_cli, "FaresDb") as fares:
            fares.return_value.locations_by_crs = {"GRA": location}
            self.assertIs(find_origin(fares.return_value, " gra "), location)

    def test_an_unknown_origin_is_none_and_the_caller_decides(self) -> None:
        with mock.patch.object(feeds_cli, "FaresDb") as fares:
            fares.return_value.locations_by_crs = {}
            self.assertIsNone(find_origin(fares.return_value, "GRA"))


if __name__ == "__main__":
    unittest.main()
