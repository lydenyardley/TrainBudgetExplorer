# ADR-0006: The timetable layer joins at the query, not inside the fare database

**Status:** Accepted
**Date:** 21 September 2026

## Context

A budget result that names a destination and a price is not yet useful. The
buyer also asks how long the trip takes, whether it needs a change, and whether
a train exists at all. The timetable feed arrives in a different format from the
fares feed, with different record types and different identifiers.

## Decision

1. **A separate module, `atoc_timetable.py`.** `FaresDb` keeps answering fares
   and gains no knowledge of trains. `grantham_sweep.py` joins the two, so the
   join is one function a test can call.
2. **The schedule is the unit of data.** A `Schedule` holds a train identity and
   an ordered tuple of calling points. Journeys are built from schedules, so a
   change count is derived from the number of legs rather than stored as a flag.
3. **Two station indexes, built lazily.** Departures and arrivals are indexed by
   station, so a journey query looks up rather than rescanning the feed.
4. **One change by default.** `--max-changes` raises it. A single change covers
   most day trips from a town like Grantham, and it keeps the search cheap.
5. **The station names file wins.** Its CRS code and interchange time override
   anything from a TIPLOC insert record, whatever order the files load in.
6. **The minimum connection time is real data.** It comes from the station names
   file, falling back to five minutes. An illegal five minute connection is
   rejected because the data says the station needs ten.

## Known approximations

Each of these is a place the answer is typical rather than exact:

- **Service days are ignored.** Every schedule in the feed counts, so a
  destination reachable only on a Sunday appears reachable every day.
- **STP overlays are not applied.** A permanent schedule and its overlay both
  count, which can show a train that does not run.
- **Public times win, scheduled times fill the gaps.** A stop with no public time
  is still usable for connections.
- **The routeing guide is not consulted.** A journey is valid if a train runs it,
  which is weaker than the fare rules that decide ticket validity.
- **One day rollover only.** Arrivals before departures are read as the next day,
  which is right for overnight trains and wrong for nothing else we have seen.

## Consequences

- Stage 2 may say "typically 45 minutes, no change", and must not promise a
  specific departure until service days and overlays are honoured.
- The onward search from an interchange is capped at sixty departures. That bound
  is a performance guard, not a data limit, and a national sweep may need it
  tuned.
- The twelve fixed-width helper lines are duplicated between the two parsers.
  Sharing them would mean importing another module's private helpers, which
  costs the reader more than the duplication does.
