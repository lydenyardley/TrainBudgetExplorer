# ADR-0076: A page lists the places a journey reaches

**Status:** Accepted
**Date:** 24 October 2026
**Relates to:** ADR-0069 (the wire form), ADR-0075 (cluster flows price every member), ADR-0060 (the day names its date), ADR-0019 (a page is written for a station that can answer)

## Context

ADR-0075 made `.FSC` cluster flows price a fare from an origin to nearly every
station the feed knows. Grantham's page carried **2,752 destinations**, and the
timetable reached **1,027** of them within one change on any of the eight days
the page carries. The other **1,725** were priced and unreachable: they rendered
as "No service that day" beside a price, on every day a reader could choose.

They were also **34% of the page's bytes** (233,104 of 690,977), and
`docs/build-performance-findings.md` measured that the release could not reach
its 800 MB budget while carrying them. Whether a fare with no journey is
an answer for this page is a product question, not an encoding one; it is the
largest single lever the audit found.

## Decision

A page lists a place only when a journey from its origin reaches it within the
build's own change limit on at least one day of the week the page carries.

Five rules hold the decision together:

1. **A place, not a row.** The three fare lists price the same place three
   ways, so the rule drops every row for a place and keeps every row for it.
   A page that kept one list's row would say no journey reaches a place beside a
   price for it.
2. **A place that runs another day is kept.** `nextService` already named the
   day a row runs when the build's own day does not; such a row is reachable,
   and a Sunday build must not lose the stations that run the rest of the week.
   Only a place absent from *every* day of the walk goes.
3. **A build with no timetable drops nothing.** Without a week it has no answer
   to give, and its rows already say `no_timetable` rather than claiming an
   absence.
4. **The page says what it left out, and by which rule.** The payload carries
   `unreachableDestinationCount` and `maxChanges`; the coverage line above the
   table names the count, the journey limit and the number of days, and a page
   the rule emptied says the feed prices places from here that no journey
   reaches rather than "we couldn't price any journeys" — a cause it would be
   naming wrongly. The payload's own `unpricedNote` is now asked of what the
   feed priced, so it cannot explain an emptiness the rule caused.
5. **The chooser's number follows the page.** The all-origins build already
   replaced each index entry's planned count with `places_in_payload`, so a
   release's station list counts what its pages list rather than what the feed
   prices. The write set is unchanged: `_priced_destinations` still decides
   which stations get a page, because that is the question "can this page
   answer at all" (ADR-0019 decision 3) and the reachability rule needs the
   week walk that page building does.

## Evidence

Measured on the local feeds on 24 October 2026, Grantham, 2026-10-05:

- **Places 2,752 -> 1,027; rows 4,690 -> 2,092.** Of the 1,730 places that ran
  on no day of the build's own day, 5 ran on another day of the week and stay.
- **Page 690,977 -> 426,972 bytes (-38.2%)** in a single-origin build, gzip
  127,158 -> 90,017 (-29.2%). Unlike the wire changes of ADR-0069, this one
  removes content a reader was paying to receive, so the compressed size falls
  with the raw one.
- With ADR-0069's third half (the station facts out of the page) the
  release-shaped page is **386,505 bytes**, and 373,396 with the service week
  run-length encoded — 46% below the 690,977 the page measured before either.
- The seven-day week is unchanged for every place that stays: the same 8 days,
  the same control, the same per-day answers.

## Consequences

- **A reader no longer sees a fare to a place they cannot reach from here.**
  That is the product claim: a fare is not a journey. The cost is that a reader
  who wanted to know whether a fare *exists* to such a place cannot see it on
  this page, and the sentence above the table is the only place it is said.
- **Some pages list nothing.** An origin whose every priced destination is
  unreachable gets a page that says so. The build still writes it, because the
  write set is the feed's answer and a station is a place a reader may be
  trying to leave from. Where such a page appears differs by list, and each
  list has its own rule: the release manifest and the station picker name every
  page the release serves, because a page is a route; the root chooser offers
  only the pages that answer, because it ranks by count and a zero count sends
  a reader to an empty table (ADR-0019 decision 3). On 24 October 2026 the merge
  read that last list back as the route list, so 244 of these pages were served
  and named by nothing, and `python -m tools.release.manifest` refused the
  release at 2,594 routes against 2,838 pages; `build_pool.py`'s merge names
  the routes from the pages it copies now, which `tests/test_page_runner.py`
  holds.

The browser suite is the second reader of this decision, and it reads a page
that lists nothing as a shape of its own: the checks about a row, a chip or a
ticket action are named as not exercised there, the accessibility matrix and
the page's own sentence still run, and the skip budget is not counted against a
page whose emptiness is its answer. It was three separate failures before that
(24 October 2026): a press on the refinements the page hides, a check that a row
is named, and 16 of that page's 52 checks skipped against a 5% budget.
- **The day the reader chooses does not change what is listed.** A place that
  runs on Tuesday is listed on a page whose build day is Sunday, with "No
  service that day, and it runs on Tuesday". Only a place that runs on no day
  of the week is absent.
