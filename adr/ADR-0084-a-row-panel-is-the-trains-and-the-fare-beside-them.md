# ADR-0084: A row's panel is the trains and the fare beside them

**Status:** Accepted
**Date:** 4 November 2026
**Relates to:** ADR-0061 (a two-ticket row is one row), ADR-0082 and ADR-0083
(the refinements on a wide screen and a phone), `docs/open-work.md` O36 and O43

## Context

A screenshot of an opened row on 4 November 2026 showed what the disclosure had
become: five trains as two clock times with no duration, a sentence reading
"Restricted fare — the condition is below", "OFF-PEAK" under it, and a
"Copy journey" button. Read as a reader reads it, the panel raised four problems
and answered none:

- **The trains carried no duration.** The arrival alone leaves the reader
  subtracting times across an hour boundary to compare one train with the row's
  own Time cell, which is the fastest journey rather than that train's.
- **Nothing said what the condition governed.** "Restricted fare — the condition
  is below" sits under the list, so the condition reads as a claim about the
  trains above it, about all of them, or about the price, depending on where the
  reader's eye stopped.
- **Most of the panel was empty.** The panel spans the whole table -- about
  1,400px at a desktop width -- and held one column of a list and one sentence
  set at 40 characters, with two thirds of the width doing nothing.
- **Copy was in the wrong place.** The row's "Copy journey" copied one place
  while the shortlist's Copy, which names every place held with its price, time
  and fare, was one press away in the dock. Two controls for one job, and the
  row's was the weaker of the two.

## Decision

**The panel is two columns: the trains that the fare pays for, and the fare
itself.** Seven rules hold it together.

1. **`padding: 1rem 2rem`.** The panel is the one reading surface on the page
   that is not a cell, and it was inset like a cell. The phone layout keeps its
   own `1rem 0`, because there the page's gutter is the inset and 2rem would be
   an eighth of the screen.
2. **Each train carries its own duration.** `05:41 depart, 06:22 arrive (41m),
   no change`. The subtraction is done from the same two numbers that are printed,
   so a reader comparing two trains, or a train with the row's Time cell, is not
   doing arithmetic to find out which is which.
3. **The list's lead says which day and who owns the condition.** "Next trains on
   5 October 2026." and, for a fare the feed describes, "The condition OFF-PEAK is
   on the fare, not on one of these trains: it decides which of them you may
   board." The feed's per-train windows (its TR and TD records) are not in this
   page's payload, so what is promised is the relationship and not a verdict on a
   departure. A two-ticket row points at the two conditions listed with the fares
   instead.
4. **Two columns above 60rem, stacked below.** The trains take
   `minmax(0, 26rem)` and the fare takes the rest, so the panel's width is used
   for the two facts a reader is joining rather than for one of them.
5. **The fare sentence stops pointing down.** "Restricted fare." is the whole
   sentence now: the condition is the paragraph directly under it in the same
   column, and "below" pointed past the list on a phone and beside it on a wide
   screen once the panel had two columns.
6. **The row's Copy is gone.** ADR-0054's shortlist is the page's one copying
   surface, and its Copy names every place held -- price, time, changes and fare
   -- in the block a reader pastes. The machinery behind the row's copy went with
   the button rather than staying idle: `rowActions`, `journeyText`, `showCopyText`
   and the row's `copyStatus` region are not on the page.
7. **A time selector is measured and refused, not built.** The complaint behind
   the third bullet -- that five trains means the first five of the day -- is
   real, and the fix a reader would expect is a time control beside the day
   control. It was built to measure rather than argued about: the same page with
   `--departures 40` is 605,049 bytes against 416,682 at the default five, so
   each extra departure costs about **12.5 bytes** and a day of them costs
   **+188 KB (+45%)** on the Grantham page -- and 218 of its 803 timed places hit
   the 40 cap, so a full day is more than 40 on some routes and the figure is a
   floor. The release is already projected over its 800 MB byte budget, so this is
   not cheap. The measurement is in `docs/build-performance-findings.md` and the
   ask is O43.

## Evidence

- `python -m tools.verify --browser` drives six pages and passes **1,401 of
  1,401** checks, 56 not exercised. The panel's own claims are in
  `tests/browser/station-rows.cjs`: no control in it, a duration on every train
  that matches the two clocks it prints, the lead naming the day and the
  condition's owner, the fare sentence standing on its own, the two columns'
  top edge, and the two older ones -- the span, and the row that stays open
  through a render.
- The suite's copy checks moved with the feature: C09 (the copied text names the
  ticket) is now read off the shortlist in `tests/browser/station-shortlist.cjs`,
  and the 44px target for copying is measured on the dock's Copy in
  `tests/browser/station-picker.cjs`.
- `tests/test_build_demo_page.py` holds the markup half -- the panel's copy gone
  from the script and the shortlist's Copy still there -- and
  `tests/test_build_links.py` holds the one copy surface the page acknowledges.
- The two builds behind the byte figure were made on 4 November 2026 from the
  24 September 2026 feeds, with the same tree, the same `--origin GRA --date
  2026-10-05 --notices nre,rdg,ogl,accuracy` flags and the same output shape,
  and differ only in `--departures 5` and `--departures 40`.

## Consequences

- **The panel is quieter and taller in one direction only.** It gains a lead
  sentence and a duration per train, and loses the copy button; measured at a
  1280px window it is two columns, and below 60rem the two stack in reading order.
- **"Next trains" is now a claim.** The list is the first five of the day the
  day control names, and the lead says so rather than leaving a reader to infer
  that the page knows about the 14:00.
- **The shortlist carries the copying.** A reader who wants text to paste about
  one place shortlists it and copies the list, which is one extra press and the
  block that is actually useful away from the page.
- **A day of departures stays unaffordable** on this payload shape, and O43
  records what would have to change for the time control to be built: a cheaper
  encoding of the times, or a decision that eight or twelve departures a
  destination is the compromise.
