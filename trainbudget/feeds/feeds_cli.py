"""Shared plumbing for the feed-driven CLI tools.

Six tools (feed_audit, grantham_sweep, sanity_report, destination_coverage,
tools/propose_nature_stations, tools/regenerate_destination_facets) each began
with the same argument parsing and the same load preamble (audit C3). This
module gathers exactly that shared shape -- the feed arguments and the load
pair -- and nothing else.

A tool adds its own arguments on top with add_feed_args(parser) and then calls
load_feeds(args) once; the origin/budget flags stay in the tools that own them.
A tool that runs without arguments passes feed_default, and a tool that never
reads a timetable passes fares_only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.timetable.atoc_timetable import TimetableDb


def add_feed_args(
    parser: argparse.ArgumentParser,
    *,
    timetable_required: bool = False,
    feed_default: str | Path | None = None,
    fares_only: bool = False,
) -> None:
    """The feed-location arguments every feed tool takes.

    ``feed_default`` gives a tool that runs with no arguments its own default;
    without it ``--feed`` is required. ``fares_only`` omits the timetable flag
    for tools that never read one.
    """
    parser.add_argument(
        "--feed",
        type=Path,
        required=feed_default is None,
        default=feed_default,
        help="fares feed folder or zip",
    )
    if not fares_only:
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
    # A tool that passed fares_only never declared --timetable, so the
    # attribute is read rather than assumed: the load pair has to work for
    # every shape add_feed_args can leave behind.
    timetable_path = getattr(args, "timetable", None)
    timetable = TimetableDb().load_feed(timetable_path) if timetable_path else None
    return fares, timetable


def find_origin(fares: FaresDb, origin: str) -> object | None:
    """The origin's location record, or None -- the caller decides the message.

    Every tool words its missing-origin complaint slightly differently; the
    lookup itself never changes, so it lives here.
    """
    return fares.locations_by_crs.get(origin.strip().upper())
