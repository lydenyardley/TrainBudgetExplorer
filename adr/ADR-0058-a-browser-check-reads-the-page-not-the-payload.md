# ADR-0058: A browser check reads what the page renders, never what the payload holds

**Status:** Accepted
**Date:** 3 October 2026
**Relates to:** ADR-0027 (the browser suite covers the template), ADR-0046 (a row
list ships as a table and a pool), ADR-0053 (the row names its fare).
Amends nothing; the two checks it describes were written under ADR-0027 and were
wrong from the day they were written.

## Context

The browser suite had never been run against a real 2,712-station feed. It runs
against synthetic feeds whose whole destination list fits on one page, and on a
page where everything fits on one page two different readings of the table are
the same reading: payload order and displayed order coincide, so a check can
reason about the payload and appear to be reasoning about the screen.

Running the suite against Nottingham, built from the real feed, failed two
checks. Both were the harness's fault and the product was right both times.

The first: `a changed journey names the station a split ticket would change at`.
Nottingham's changes cell says `1 change via DERBY` for East Midlands Airport,
and the panel beside that row carries the split-ticket sentence the check asks
for. The check read `{"crs":"EMA","name":"DERBY","note":null}` and failed on the
`null`. `noteFor` returns `null` when the row is not in the DOM at all, and the
row was not in the DOM: the table sorts by the price on screen and shows
PAGE_SIZE of them, and EMA is destination 52 of 79 in the anytime list — page 3,
while the probe only ever read page 1. The check reported a missing note for a
note that was on the screen.

The second: `a small town is its own class, not a town`. `checkChip` compared
`expected.rows.slice(0, pageSize)` — the first twenty rows in payload order —
against the twenty the table drew, which are the cheapest twenty. Nottingham has
29 small towns, so the slice named nine rows living on page 2 and the check
reported a correctly filtered table as broken.

The shape of both bugs is the same and neither is a mistake anyone would make
twice knowingly: a check written against the list behind the table, on a suite
whose every fixture made the list and the table the same shape.

## Decision

1. A check that asserts something about a table reads the table. It reads the
   rendered rows — their codes, their count, the text on screen — and compares
   them as a set against the payload. It does not slice the payload and call the
   slice the page.
2. Where a check needs one particular row, it renders the page holding that row
   first. A row that is not on screen is a fact about the screen, and `null` from
   a DOM query means the row is absent, never that the page is silent about it.
3. A fixture whose whole list fits on one page cannot catch either mistake. A
   suite that has only ever run on pages shaped that way has not tested its own
   assumption, and running it against a real feed is the only thing that does.
   This is why the suite is now swept against pages built from the real feed,
   alongside the fixtures rather than instead of them.
4. A check reports a defect; it does not raise. The fix for the small-town check
   initially computed its price sequence through the payload map before testing
   whether each rendered row was in that map, so the one regression the check
   exists to catch would have thrown and taken the rest of the run with it. A
   suite that dies reports the exception, not the defect.

## Consequences

- **The small-town check asserts four things where it asserted one.** Every row
  shown is of that type; exactly as many are shown as fit on a page; each is
  named on screen; and they run cheapest first by the price in the payload. The
  order the old assertion demanded is not among them, and cannot be — a sorted
  paginated table does not have that order. What replaces it is true of any
  correct table.
- **The split-ticket checks are exercised by real pages only.** The fixtures
  skip with "no destination on this page changes". That was true before this
  decision and is the other half of why the bug survived: the checks were live,
  and passing, and never running the code path they exist for.
- **Nottingham goes from 207/209 to 209/209.** Grantham 209/209, the chooser
  63/63, and the fixtures unchanged at 186/186, 204/204 and 186/186.
- **A real feed is now a test input.** That is cheap here — two stations build in
  under five minutes — and it is the only input shaped like production.

## Read by running

```
python build_stations.py --no-serve
cd tests && npx --yes --package playwright node browser_test.cjs \
  ../_stations/from/nottingham/index.html
```

Without a real page the split checks skip rather than pass, and a skip reads as
a green line in the output.