# ADR-0082: The refinements sit beside the list on a wide screen

**Status:** Accepted
**Date:** 3 November 2026
**Relates to:** ADR-0077 (a page lists the places it prices most cheaply), ADR-0040 (the count line's gap to the table), `docs/open-work.md` O42

## Context

The 3 November 2026 review asked for the filters to become a side panel on a
wide screen and a pop-out on a narrow one, so they are more visible and the
noise above the results is smaller.

On the synthetic Grantham page at 1366x768 the first destination row began at
**603px** of the 768px window. The heading, the first-use sentence, the budget
bar and the folded refinements sat above it, and one whole row was on screen at
the fold.

The fold is not noise to be removed on the way. The distil pass of 19 October
2026 measured it -- four controls a reader had not asked for above the list --
and about a dozen browser checks hold it: the folded plate, the state it names,
the two-column panel where the bar spans the page, the tab order into it, and
the contrast of the chips inside it. Opening the refinements at every width
would overturn a measured decision to save a bar that is already one line at
390px.

## Decision

At **68rem and above** the filter bar and the results are two columns of one
wrapper. The bar is sticky, the results take the rest, and below 68rem the page
is the block it was.

Six rules hold it together:

1. **Layout only.** One wrapper around the bar and the list. No id, landmark or
   control moves, and the template writes one bar for both layouts, so a control
   cannot exist at one width and not the other.
2. **The fold stays.** The rail is the bar, not a second panel: the budget, the
   "Filter this list" control and the day control are in it, and pressing the
   fold opens the panel it always opened.
3. **68rem, not the 44rem of the phone breakpoint.** The six-column table needs
   about 700px before its three row actions wrap, and an 18rem rail plus its
   2rem gap only leaves that much above 68rem.
4. **What scrolls is the panel, not the column.** A sticky column that scrolls
   internally can lose the budget slider inside itself. The page reads a slider
   out of its own column as one the reader has passed, and the 56px budget rail
   then arrives while the column is still on screen.
5. **The budget rail reads the slider's box.** Out of view above and out of view
   below are both an intersection ratio of zero, so an IntersectionObserver
   delivers no entry when a reader moves between them, and the rail stayed up
   after a page scrolled past its slider was shrunk to a phone window. A scroll
   or a resize re-reads one rect, at most once a frame.
6. **A narrow screen keeps the fold.** At 390px the folded bar is 177px and the
   first row is at 600px, so a pop-out would trade that height for a modal
   interaction over the rows it filters. The narrow half of the request is
   **O42**.

## Evidence

Measured 3 November 2026 on the synthetic build
(`python -m tools.build_demo_page --feed _demo_feed --timetable _demo_feed --all-origins`),
reading the same markup twice: once as built, and once with the wide rule
cancelled, so only the layout differs.

| Window | First row, bar above the list | First row, rail | Table |
|---|---:|---:|---:|
| 1366x768 | 603px | **458px** | 856px of a 1176px page |
| 1280x800 | 612px | **467px** | 856px |
| 390x844 | 600px | 600px, unchanged | 366px |

- At 1366x768 the fold holds four whole rows where it held one, because the rail
  no longer stands between the heading and the list.
- The table keeps 856px at 1280, above the ~700px its row actions need: a row
  measured 63px in both layouts, so nothing wraps that did not wrap before.
- No horizontal overflow at any of the three widths.
- The panel opens as one column in the rail and two at 1024px, where the bar
  spans the page.
- `python -m tools.verify --browser` drives six pages, **1395 checks**, 54 not
  exercised, and both skip budgets inside their limits.

## Consequences

- **The rail releases at its column's end.** On a page whose results column is
  shorter than the rail (a three-row demo page), scrolling past the list takes
  the rail with it, and the 56px budget rail covers the reader from there. A
  real page's twenty rows keep the rail in view.
- **Three checks changed their subject.** "Party beside ticket" and "a rem above
  the bar" are measured where the bar spans the page and again in the rail, and
  "the headings sit below the rail" does not apply once the table has scrolled
  to its own end.
- **The phone is untouched**, including the accessibility matrix at 200% zoom.
