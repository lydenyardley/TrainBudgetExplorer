# ADR-0059: The reader picks the day the times are for

**Status:** Accepted
**Date:** 5 October 2026
**Relates to:** ADR-0025 (the restriction gate and TIPLOC normalisation),
ADR-0040 (what stands between the count and the first row), ADR-0027 (the
browser suite is `page_templates.py`'s test)

## Context

A page is built for one day. Every journey time on it is that day's. On the
real Nottingham page, 26 of 96 destinations have no train on the build's day
at all, and each of those rows reads "No service Sun, runs Mon" and shows a
dash in the Time and Changes columns. The day is a property of the build, and
the reader has no way to see Monday.

The feed already holds the rest of the week. The build was not asking it.

Two things had to be answered before the control could be built: what does a
week of answers cost, and what shape does the sweep take.

## Decision

**The build walks the week once per timetable with `journeys_from`, and the
page reads the result.**

`atoc_timetable.journeys_from(origin)` answers every station in the network
from one origin for one day, instead of one destination per call. The build
collects the timetable that answered each row, walks `SERVICE_WEEK_HORIZON + 1`
days from the build's day through each one, and keeps only the stations a row
names. One table of answers per day, one index per row.

The same call was measured first against the **sweep**, which asks about the
unserved destinations only. There it is a regression, and it was reverted:
12.90 s per-destination against 32.05 s fan-out for the sweep alone, and
24.9 s / 24.4 s / 62.0 s against 50.6 s / 58.2 s / 97.2 s for three whole
NOT builds, alternating. The mechanism is visible in both numbers. The sweep
asks about 26 unserved destinations, 18 of them answered on day one, leaving 8
asked across all seven days. About 74 questions in total. The fan-out answers
all 1,415 stations every day, which is 9,905 destination-days, regardless of
what was pending.

The earlier figure that recommended the fan-out, 47% to 51% faster, was true
and measured a different question: every destination every day. That is the
shape this control needs and not the shape the sweep had. Same class of error
as the reverted caching attempt. The lesson recorded here is that a
performance number is only evidence for the shape it was taken on.

**The cost of the week, for the shape this control actually has**, measured
back to back in one process, alternating, seven days over 163 rows:

| Origin | Without the week | With the week | Ratio |
| --- | --- | --- | --- |
| NOT | 43.45 s | 88.32 s | 2.03x |
| GRA | 34.59 s | 59.10 s | 1.71x |
| CBX | 34.20 s | 43.25 s | 1.26x |

The fan-out is the cheaper of the two ways to get those days. On NOT it
answers seven days over 163 rows in 24.74 s against 33.74 s for one walk per
destination, **73% of the cost**, with **zero disagreements over 1,141 asked
destination-days**. The other 7,893 answers it produces are for stations no row
names.

The whole-network release is 2,712 pages and was not run, so there is no
release figure. That is the number to take before this reaches every station.

The payload grew 324,848 to 348,118 bytes on the NOT page, **+7.2%**. One
table of 8 days, 137 stations in day zero, and every row carrying an index
rather than a copy.

## The three invariants

**Day zero is the build's own day and must say exactly what the rows already
said.** A reader who touches nothing must not see a single cell move. This is
asserted at both ends: `ServiceWeekPayloadTest` compares every row's day-zero
entry against the row's own `minutes`, `changes` and `journeyState`, and the
browser suite compares every cell before and after the control is exercised.

**A station missing from a day's table has no service that day.** The build
keeps only the stations a walk reached, and it asked about every station a row
names, so absence is an answer rather than a gap in what was asked. This is
what makes `null` the right return and `undefined` the wrong one, and it is
why the page reads the row's own station out of the day's table. Returning the
whole table instead of one station's entry was a bug that shipped into a
build: every row printed a dash, because the object had no index 0 to read a
duration from.

**"No week" is `null`, not `-1`.** A pool reference is a negative number, so
`-1` decoded into pool entry zero, which is a railcard record. The cell named
somebody's railcards rather than a row with no week.

## The control sits on the filter strip, not between the count and the table

The control was built first in the gap between the count line and the table,
next to the columns it changes. The browser suite failed two checks, and both
were right to.

ADR-0040 found the count line 205 px above the first row with six provenance
paragraphs between them, and moved the provenance below the table. What is left
is a measured budget: the count within 12 px of the table, and nothing between
the provenance and the first row except the count, the fold and two named
lines, within 100 px. A 44 px touch target plus its label and help line is
57 px in that gap, which took the count-to-first-row to 116 px and broke both
checks.

So the control moved up onto the always-visible strip, beside the budget
slider and above the count. Above the count it costs nothing and both checks
pass unchanged. It is not inside the collapsible filter panel, because it is
not a filter: it does not hide rows, it changes what the Time and Changes
columns report, and a reader would not find it behind a disclosure. Both
ADR-0040 checks pass with the control present and untouched.

**The chosen day travels in the address**, as `day=N`, alongside the budget,
the ticket type, the party, the card, the facets, the page and the shortlist. A
shared link that opens on the sender's day is the reason a control like this is
worth having, and an address that forgets it on a refresh is a control the
reader sets again every time they come back. The privacy page enumerates
exactly what the address carries and now names the day. The build's own day is
not written, so a link without the parameter and the parameter `day=0` mean
the same thing rather than two things. A value naming a day this build did not
walk is clamped to the last day it did, so a link from a longer build shows a
day rather than an empty table.

**Interchange stations are shown for the build's own day only.** Change-station
lists are only held for the build's own day, so the detail row on any other day
omits them rather than naming the wrong ones. The control's help line says so.

Everything downstream of that station is suppressed with it, and this was
missed on the first pass. The split-ticket note in the row's panel is worded
"one ticket to the station above and another from it", so it points at the very
line this section suppresses: on any other day the Changes cell prints the
chosen day's count and no station, and the note went on claiming a change at a
station the page had stopped naming. On WRK from Nottingham, built for a Sunday,
the row changes at Sheffield on day zero and is direct on the other seven, so
seven of the eight days in the build's own week showed "Direct" beside a claim
that it changes somewhere. Suppressing a fact means suppressing what refers to
it, and the browser check reads every day rather than the one on screen,
because the days that disagree are not the ones a reader happens to be looking
at.

**The day travels both ways through the address.** The chosen day is read from
`day=N` and clamped to the days the build walked, but the first implementation
read it only into a variable the control consulted once, when it wrote its
options. Back and Forward called `applyState`, which parked the day and moved
everything else, so the address said one day and the table showed another. One
function now takes the day for both routes in and points the control at it, and
the browser suite drives Back and Forward through real history entries: a
listener that reads the address and never re-renders looks correct until a
reader presses Back.

## What would change this

The week is sent as a table per timetable, not per origin, so a page with a
second timetable carries a second week. A build with `--with-single-timetable`
is the case, and it is exercised.

`journeys_from` is still inert everywhere else. It is called by
`tests/test_journey_fanout.py` and by this build's week walk, and nothing else.
If a future pass wants it for the sweep, the measurement above is the reason to
measure again rather than to assume.

A reader can currently choose a day, not a date. The build walks
`SERVICE_WEEK_HORIZON` days, which is seven, so the control offers eight days
and no further. A calendar needs a horizon someone chose, and nobody has.

The full-network release has not been built with this. The per-origin ratios
above are three stations. If the release build does not fit the window the
ADR-0024 tripwire allows, the answer is a narrower week rather than a day
control on three of them.
