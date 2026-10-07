# ADR-0060: The day names its date, and changes the times and nothing else

**Status:** Accepted
**Date:** 5 October 2026
**Relates to:** ADR-0059 (the reader picks the day), ADR-0040 (what stands
between the count and the first row), ADR-0043 (the row keeps the action and its
panel holds the rest), ADR-0009 (the onward departure cap), ADR-0058 (a browser
check reads the page, not the payload). Amends ADR-0059's "What would change
this", which recorded that the control offers eight days and no further.

## Context

ADR-0059 built the control. It offers the build's own day and the seven days
after it, labelled `shortDay + " " + humanDate`, with the first option carrying
the suffix "(this build)".

Two things were then put to it. The first was whether the control should also
be the reason the list, the prices or the budget change, and the answer was no.
The second was this:

> Every Sunday is the same, right? No need to show 2 of them or particular
> dates?

That is a premise about the feed, and it is false. Measured on the reference
timetable, from Grantham, with the shipped one-change search:

| Pair | Stations both days reach | Identical time and changes | Only on the first | Only on the second |
| --- | --- | --- | --- | --- |
| Sun 4 Oct 2026 vs Sun 11 Oct 2026 | 220 | 170 (77.3%) | 18 | 196 |
| Mon 5 Oct 2026 vs Mon 12 Oct 2026 | 574 | 544 (94.8%) | 8 | 0 |

Sunday 4 October reaches 238 stations. Sunday 11 October reaches 416. Of the 220
both reach, 50 carry a different time: Edinburgh is 335 minutes on the first and
208 on the second, Haymarket 357 and 218. Mondays are much closer to each other
than Sundays are, so Sunday is the weekday least able to stand in for a date,
not the most able.

The pair was run twice and returned the same figures both times.

A weekday-of-week selector therefore cannot select a date. It can only name
whichever Sunday the build happened to walk, and on this feed that is a choice
between 238 destinations and 416 presented as if it were one Sunday.

## Decision

**1. The control changes the Time and Changes columns and nothing else.** Not
the list, not the prices, not the budget, not the rows. Day zero is asserted
equal to the row's own `minutes` and `changes` at both ends of the build, and
that invariant is unchanged.

**2. Every option leads with the weekday and carries the date.** The label is
now `shortDay(iso) + ", " + humanDate(iso)`, so the option reads
`Sunday, 4 Oct 2026`. The weekday comes first because that is the order a
reader asks the question in. The date stays because the measurement above is the
reason it stays.

**3. "(this build)" is gone.** It told a reader which day the build asked about,
which is a fact about the build rather than about the journey, and it was the
only part of the label that did not help a reader choose. The build's own day is
still first in the list and still the default.

**4. The help line says that days of the week are not the same as each other.**
It reads "Times and changes for every row, on the date you pick. Days of the
week are not the same as each other, so the date is named. Interchange stations
are shown for the build's own day only."

**5. The browser check asserts the shape of the label, not the old suffix.** It
now requires the first option to match `^(Mon|…|Sun), D Mon YYYY$` and to be
free of "(this build)". A check that asked for the suffix would have been a test
of the old wording rather than of the page.

## Invariants

- **Day zero must not move a cell.** Unchanged from ADR-0059 and still asserted.
- **The date is in the label.** A weekday-only label is not offered, because the
  measurement above is what makes it untrue.
- **The option count equals the days walked.** A build with one day shows no
  control at all rather than a control with one option.

## What would change this

The eight days are still the build's own eight days. This ADR settles the label,
not the horizon. A calendar needs a horizon someone chose, which is open work,
and `docs/open-work.md` carries the date-specific schedule items.

The build's own day is no longer marked in the control, so a reader who wants to
know which day the page was built for must read the provenance rather than the
control. That is a cost of decision 3 and it is accepted. If it proves to cost
anything, the honest repair is a line in the provenance, not a suffix on the
first option.