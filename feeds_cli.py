"""Shared plumbing for the feed-driven CLI tools.

Six tools (grantham_sweep, sanity_report, feed_audit, benchmark, fuzz_feed,
damage_feed) each began with the same two lines of argument parsing and the
same load-and-check preamble (audit C3). This module gathers exactly that
shared shape -- the feed arguments and the load pair -- and nothing else.

A tool adds its own arguments on top with add_feed_args(parser) and then calls
load_feeds(args) once; the origin/budget flags stay in the tools that own them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb


def add_feed_args(parser: argparse.ArgumentParser, *, timetable_required: bool = False) -> None:
    """The two feed-location arguments every feed tool takes."""
    parser.add_argument("--feed", required=True, help="fares feed folder or zip")
    parser.add_argument(
        "--timetable",
        required=timetable_required,
        default=None,
        help="CIF timetable feed folder or zip",
    )


def load_feeds(args: argparse.Namespace) -> tuple[FaresDb, TimetableDb | None]:
    """Load the feeds the tool's arguments name; the timetable only if given.

    Callers handle a missing origin themselves: that check varies per tool,
    this only loads.
    """
    fares = FaresDb().load_feed(args.feed)
    timetable = TimetableDb().load_feed(args.timetable) if args.timetable else None
    return fares, timetable


def find_origin(fares: FaresDb, origin: str) -> object | None:
    """The origin's location record, or None -- the caller decides the message.

    Every tool words its missing-origin complaint slightly differently; the
    lookup itself never changes, so it lives here.
    """
    return fares.locations_by_crs.get(origin.strip().upper())
