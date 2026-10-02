"""N4: the journey is a fact about the origin and the destination, so it is
looked up once per destination rather than once per fare list.

`destination_row` was given a timetable per fare list and read the journey only
from that one. Three lists reach the same destinations, so the same destination
carried three different answers:

    DATA.destinations            NOTTINGHAM   found    45m  0 changes
    DATA.anytimeDestinations     NOTTINGHAM   found    45m  0 changes
    DATA.singleDestinations      NOTTINGHAM   no timetable in this build  null  null

The page opens on the cheapest list (ADR-0044), and the cheapest list keeps
whichever row is cheapest. Where the cheapest fare is an advance single, that
is the third row above -- so the row that won carried its own list's absence,
and the page said "No service" and "Unknown" about a destination it prices a
45-minute direct journey to, three lines further down the same payload. The
Time and Changes columns were empty for every destination the build could
actually time, and empty for a reason that named nothing true about it.

The lookup now falls back: a row's own timetable first, the page's after it.
The state sentence follows the same search, so it says "no timetable in this
build" only when there is genuinely no timetable to read.

The departures do NOT fall back, and that is the point of the exception. They
are the times a fare is good on, and an advance single's times are only knowable
from the separate outbound-single timetable; listing a return-set train under
an advance single would be a time the reader cannot travel on that ticket.

`singleJourneyNote` is reworded because it is no longer true. It said singles
"may show fares without times", which was the absence this removes; the note
now says where the single rows are timed from.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD_SIGNATURE = """    def destination_row(
        crs: str,
        one,
        *,
        with_journey: bool = True,
        quality: str,
        journey_db: TimetableDb | None = timetable,
    ) -> dict:
        journey = (
            journey_db.best_journey(origin.crs, crs, max_changes=max_changes, day=day)
            if journey_db and with_journey
            else None
        )
        options = (
            journey_db.departures(origin.crs, crs, max_changes=max_changes, day=day, limit=departure_limit)
            if journey_db and with_journey
            else []
        )"""

NEW_SIGNATURE = """    def destination_row(
        crs: str,
        one,
        *,
        with_departures: bool = True,
        quality: str,
        journey_db: TimetableDb | None = timetable,
    ) -> dict:
        # The journey belongs to the origin and the destination, not to the
        # ticket type, so it is read once per destination from the first
        # timetable this build holds that has one: the row's own, then the
        # page's. It used to be read from the row's own timetable only, so a
        # destination three fare lists reach carried three different answers,
        # and the cheapest list kept the one belonging to the fare that won.
        # Where the cheapest fare is an advance single, that is the list built
        # without a timetable, so the row said no service about a destination
        # the same payload prices a 45-minute direct journey to.
        searched = (journey_db,) if journey_db is timetable else (journey_db, timetable)
        journey = None
        for db in searched:
            if db is None:
                continue
            journey = db.best_journey(origin.crs, crs, max_changes=max_changes, day=day)
            if journey:
                break
        # The departures do not fall back. They are the times this fare is good
        # on, and an advance single's are only knowable from the separate
        # outbound-single timetable; a return-set train listed under an advance
        # single would be a time the reader cannot travel on that ticket.
        options = (
            journey_db.departures(origin.crs, crs, max_changes=max_changes, day=day, limit=departure_limit)
            if journey_db and with_departures
            else []
        )"""

OLD_STATE = """            "journeyState": (
                "found"
                if journey
                else "no timetable in this build"
                if journey_db is None
                else f"no service on {day.isoformat()}" if day
                else "no service in this timetable"
            ),"""

NEW_STATE = """            "journeyState": (
                "found"
                if journey
                # The build has no timetable to read, rather than this row's
                # list not having one: the search above is what decides it, and
                # it is the same search that decided `journey`.
                else "no timetable in this build"
                if all(db is None for db in searched)
                else f"no service on {day.isoformat()}" if day
                else "no service in this timetable"
            ),"""

OLD_CALL = """    single_destinations = [
        destination_row(
            crs,
            one,
            with_journey=single_timetable is not None,
            quality="outbound single",
            journey_db=single_timetable,
        )
        for crs, one in sorted(single_tickets.items(), key=lambda item: item[1].best_pence)
    ]"""

NEW_CALL = """    single_destinations = [
        destination_row(
            crs,
            one,
            with_departures=single_timetable is not None,
            quality="outbound single",
            journey_db=single_timetable,
        )
        for crs, one in sorted(single_tickets.items(), key=lambda item: item[1].best_pence)
    ]"""

OLD_NOTE = """        "singleJourneyNote": (
            "Journey times are currently loaded for the return set; single-mode rows may show fares without times."
            if single_timetable is None and timetable is not None
            else None
        ),"""

NEW_NOTE = """        "singleJourneyNote": (
            "Single fares are timed from the same timetable as the returns, because "
            "this build loaded no separate outbound-single timetable."
            if single_timetable is None and timetable is not None
            else None
        ),"""

if __name__ == "__main__":
    patch(
        "build_demo_page.py",
        [
            (OLD_SIGNATURE, NEW_SIGNATURE),
            (OLD_STATE, NEW_STATE),
            (OLD_CALL, NEW_CALL),
            (OLD_NOTE, NEW_NOTE),
        ],
    )