# ADR-0085: The rail uses the window, and opens its refinements

**Status:** Accepted
**Date:** 7 November 2026
**Relates to:** ADR-0082 (the rail beside the list), ADR-0083 (the phone sheet), ADR-0084 (the row's panel)

## Context

ADR-0082 put the refinements beside the list at 98rem, which is a centred
78rem column plus an 18rem rail and the 2rem between them. Its reason was
width: the results table needs 1,176px for the real feed's longest station
names, and a rail inside the 78rem cap took 320px from it, which wrapped five
of the 32 pages the browser suite drives.

Two things followed. A reader on a 1920x1200 screen at 125% has 1536 CSS
pixels, 32 short of the gate, so the rail never appeared for them. And the
7 November 2026 review asked for three changes: the rail around 1260px, the
page using the whole window when it appears rather than the capped column, and
the rail showing the budget, then the day, then the refinements already open.

## Decision

From **95.5rem (1,528 CSS px)** the station route is the width of the window:

1. **The page stops being a centred column.** `body { max-width: none; }` at
   the breakpoint. The shared `--rail` token and its `calc()` go: the station
   route no longer borrows room from a capped measure, it uses the window.
2. **The rail is 15rem with a 1.25rem gap.** At 95.5rem the results hold
   `1528 - 72 - 240 - 20 = 1,196px`, and 1,179px once the window's own 17px
   scrollbar is taken out; at the review's 1,536px window they hold 1,187px
   with that scrollbar. The narrower rail is what buys the lower threshold
   without wrapping a name. A first cut used 16rem and 1.5rem and measured
   1,167px in a headed browser, 9px under the need, because the media query
   counts the window and the body does not count the scrollbar.
3. **The rail's controls are budget, then day, then refinements.** The day
   control moves above the fold in the template, so the reading order and the
   tab order agree at every width. In the rail the refinements are not a fold:
   the toggle is not drawn and the panel is, in one column. The panel keeps no
   card of its own; the column is the card.
4. **The phone sheet is unchanged** (ADR-0083), and below 95.5rem the page is the
   block it was.
5. **Not 1260.** The review's 1,260px leaves the results 908px. The recorded
   failure at 856px wrapped five pages' longest names, and 908 is 52px from
   it; the measured need is 1,176. The width a reader asked for and the width
   the table can hold are different numbers, and this ADR takes the one that
   keeps a name whole while still clearing a 1920x1200 screen at 125%.

## Evidence

- The breakpoint arithmetic is from the stylesheet's own figures: page padding
  36px a side at this width, rail 256px, gap 24px.
- `python -m tools.verify --fast` passed 318 tests; `python -m tools.verify
  --browser` passed 1,405 checks on 6 pages.
- Measured in the packaged browser at 1536x1200: body 1,519px, rail 240px,
  table 1,187px, no wrapped station name, and the budget, day and open filter
  panel in that order. The same page with a 16rem rail measured a 1,167px
  table, which is the finding that moved the rail.
- The 3 November 2026 record for the 1,176px need and the five wrapped pages
  is ADR-0082 and its commit `14e6189`.

## Consequences

- **A 1536px window gains the rail and holds 1,187px of table**, 11px more
  than the 1,176px the longest names need; a 1600px window gains 72px of table.
- **The rail is 15rem rather than 18.** The destination chips and the party
  choices wrap inside it; the panel is one column in either width.
- **The day control moves above the fold at every width.** On a phone it is
  the first control under the budget in the sheet, which is the same order.
- **A page wider than 78rem is now wider than 78rem.** The footer, the heading
  and the table all use the window from 95.5rem, which is the review's request
  and the end of the centred-column policy for this route only.
