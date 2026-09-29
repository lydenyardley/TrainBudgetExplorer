# ADR-0043: The row keeps the action; its panel holds the rest

**Status:** Accepted
**Date:** 29 September 2026
**Relates to:** ADR-0014 (ticket links), ADR-0017 (the plain link), ADR-0018 (the
handoff text), ADR-0040 (the row carries the fare's code)
Settles finding 4 of `docs/audits/2026-09-29-real-grantham-page.md`.

## Context

Every row of the table carried five controls: the **Tickets** link, the
`5 times` expander, **Card details**, **Copy** and **Shortlist**. On page one
that is 100 pointer targets for 20 destinations, and the reading of the page
that finding 4 recorded was that four of the five are things a reader wants
*after* deciding rather than while deciding:

- **Card details** opens the railcard drawer, and is only meaningful to a party
  that has a Two Together card and a fare the card applies to.
- **Copy** puts the handoff text (from, to, date, party) on the clipboard, and is
  the fallback for the plain ticket link that carries no journey (ADR-0017).
- **5 times** is the row's expander, and it already exists on every row.

The five sat in one cell, in a row of 44px targets, beside the price the reader
came to compare. The page's own measure of the problem is in its own suite: the
row cell is the densest cluster of controls on the site.

## Decision

**Three controls on the row, and the rest inside the panel the row already has.**

1. The row keeps the **Tickets** link, because buying is the action the page
   exists for and hiding it behind a second click loses the click; the
   **expander**, because the journeys are what a reader checks first; and the
   **Shortlist** toggle, because comparing places is what a reader does while
   scanning the list rather than after opening a row.
2. **Card details** and **Copy** are built into the panel, in one `.row-actions`
   box after the fare's condition. Both are then one click in, beside the
   condition that explains them, and the row is the price, the time, the changes,
   the fare's code and three controls.
3. **The manual-copy fallback lands in that same panel**, under the button that
   asked for it, instead of in a panel of its own. This is the part that made the
   change simple rather than merely smaller: with the copy box gone as a second
   region, the row has **one** panel, so `closeRegion`/`rowRegions`/`nextRegionId`
   collapse into one `rowPanel` WeakMap and one `closePanel(row)`. C28's two-region
   machinery existed to stop two disclosures fighting over one slot; it is not
   needed when there is one disclosure.
4. **A repeated manual copy replaces its text rather than stacking.** The button
   describes one box, so a second refused copy removes the first box and points
   the button at the new one.
5. The two help sentences that named the moved control now name where it went:
   "open a row's own details for its Card details", rather than "Card details on
   any row".

## Consequences

- The suite's copy and target checks open the row before they reach the control,
  which is the honest form of the same check: a control a reader reaches through
  a disclosure is still a control, and the 44px promise is still measured -- the
  target sweep opens one panel so the moved buttons are in the document when it
  measures.
- The Python suite's structural test changed shape with the code: it now asserts
  one panel, one owner, and the absence of the three-region names, so the
  machinery cannot creep back without a decision.
- Nothing about the row's price, time, changes or code changed. The rows got
  shorter in controls, not in facts.
