"""N13: the timetable index must cover every station the page can show.

The build decided which stations the timetable has to cover from the return
destinations alone:

    focus_destinations = {row.crs for row in fares.page_destinations_within(...)}

But the page composes three lists, and the outbound-single list reaches stations
the return list does not. On the real Grindleford page that was thirteen of
them, and every one was a row reading "No service" and "Unknown":

    returns focus set: 43 stations
    singles focus set: 56 stations
    reachable only as a single: BON BPN BSV CRL EDG HWI LDS LIV LPY MAN MSH WSA ZHJ

A station outside the focus set has none of its services in the index, so the
journey search finds nothing and the page reports that absence as a fact about
the network. It is a fact about the build.

The fix is the union. The cost is real and worth naming: a wider focus means
more schedules held in memory, and the index is the largest thing a worker
carries (ADR-0057). Measured on this origin below.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = '''    cache_path: Path | None = None
    if args.timetable:
        focus_destinations: set[str] = set()
        if not args.all_origins and args.origin in fares.locations_by_crs:
            focus_destinations = {
                row.crs
                for row in fares.page_destinations_within(
                    args.origin, EVERYTHING_PENCE, adults=1, day=day
                )
            }'''

NEW = '''    cache_path: Path | None = None
    if args.timetable:
        # Every station the page can show, not only the ones a return reaches.
        # It was the returns alone, and the outbound-single list reaches
        # thirteen more on a real page -- Bolton, Blackpool North, Chorley,
        # Edge Hill among them -- whose services were therefore never in the
        # index at all. Each of them was a row reading "No service" and
        # "Unknown", which is not a fact about those stations. It is a fact
        # about which stations this build asked the timetable about.
        # The three lists the page composes are the three the index must cover.
        focus_destinations: set[str] = set()
        if not args.all_origins and args.origin in fares.locations_by_crs:
            for rows in (
                fares.page_destinations_within(
                    args.origin, EVERYTHING_PENCE, adults=1, day=day
                ),
                fares.page_single_destinations_within(
                    args.origin, EVERYTHING_PENCE, adults=1, day=day
                ),
                fares.publishable_destinations_within(
                    args.origin, EVERYTHING_PENCE, adults=1, day=day
                ),
            ):
                focus_destinations.update(row.crs for row in rows)'''

if __name__ == "__main__":
    patch("build_demo_page.py", [(OLD, NEW)])