# ADR-0082: The refinements sit beside the list on a wide screen

**Status:** Superseded in part by ADR-0085 (the threshold and the width)
**Date:** 3 November 2026
**Relates to:** ADR-0077 (a page lists the places it prices most cheaply), ADR-0040 (the count line's gap to the table), ADR-0083 (the phone half of the 3 November 2026 request)

## Context

The 3 November 2026 review asked for the filters to become a side panel on a
wide screen and a pop-out on a narrow one, so they are more visible and the
noise above the results is smaller.

On the synthetic Grantham page the heading, the first-use sentence, the budget
bar and the folded refinements all sit between the top of the page and the first
destination row, and what is left of the fold holds one row at 1366x768.

The fold is not noise to be removed on the way. The distil pass of 19 October
2026 measured it -- four controls a reader had not asked for above the list --
and about a dozen browser checks hold it: the folded plate, the state it names,
the two-column panel where the bar spans the page, the tab order into it, and
the contrast of the chips inside it. Opening the refinements at every width
would overturn a measured decision to save a bar that is already one line at
390px.

## Decision

At **98rem and above** the filter bar and the results are two columns of one
wrapper, and the page's own content width grows by the rail and its gap. Below
98rem the page is the block it was.

Seven rules hold it together:

1. **Layout only.** One wrapper around the bar and the list. No id, landmark or
   control moves, and the template writes one bar for both layouts, so a control
   cannot exist at one width and not the other.
2. **The fold stays.** The rail is the bar, not a second panel: the budget, the
   "Filter this list" control and the day control are in it, and pressing the
   fold opens the panel it always opened.
3. **The rail takes width the page was not using.** The page caps its content at
   78rem, so a rail inside that cap would take 320px from the results table, and
   the table loses the width its longest station names need -- see Evidence. The
   shared width becomes `calc(--page-max + --rail)`, `--rail` is zero on every
   route, and the station route sets it to 20rem at 98rem and above: 18rem of
   bar and the 2rem between them. The column, and the table's 1176px inside it,
   is the width it was, so the rail cannot wrap a name that fit. The route still
   states no page width of its own -- the token is the shared stylesheet's, which
   is what `tests/test_build_demo_page.py` holds it to.
4. **98rem, not the 44rem of the phone breakpoint, and not 68rem.** The
   six-column table needs its 1176px, measured on the real feed's longest names.
   A 1366 laptop cannot hold the page and the rail side by side, so it keeps the
   bar above the list.
5. **What scrolls is the panel, not the column.** A sticky column that scrolls
   internally can lose the budget slider inside itself. The page reads a slider
   out of its own column as one the reader has passed, and the 56px budget rail
   then arrives while the column is still on screen.
6. **The budget rail reads the slider's box.** Out of view above and out of view
   below are both an intersection ratio of zero, so an IntersectionObserver
   delivers no entry when a reader moves between them, and the rail stayed up
   after a page scrolled past its slider was shrunk to a phone window. A scroll
   or a resize re-reads one rect, at most once a frame.
7. **A narrow screen is a sheet (ADR-0083).** This ADR left the phone's folded
   bar alone, on the reasoning that a pop-out would trade a bar's height for a
   modal interaction over the rows it filters. ADR-0083 measured that trade on
   the build the suite drives, where the bar is 267px and holds the day control
   too: the first row moves from 624px to 441px and the page gains a foot that
   names the list behind the sheet. That is the narrow half, and it is closed
   there rather than here.

## Evidence

Measured 3 November 2026 on the synthetic build
(`python -m tools.build_demo_page --feed _demo_feed --timetable _demo_feed --all-origins`),
reading the same markup twice at each width: once as built, once with the wide
rule cancelled, so only the layout differs.

| Window | First row, bar above the list | First row, rail | Rows at the fold |
|---|---:|---:|---:|
| 1366x768 | 688px | 688px -- the rail does not apply | 1 |
| 1568x900 | 700px | **495px** | 3 -> 6 |
| 1920x1080 | 747px | **542px** | 5 -> 8 |

- **The table is 1176px in both layouts at all three widths**, so the rail costs
  the results nothing: a row measured 63px in both, and no price, time, name or
  heading moves to a second line.
- The wrap rule is why the width is 98rem and not 68rem. At 1280 the page's
  content is already its full 1176px, so the first design's 18rem rail took 320px
  from the table and the real feed's longest names painted on two lines: 5 of the
  32 pages the browser suite drives failed on it (`abbey-wood`, `glasshoughton`,
  `pollokshields-w`, `st-helier`, `tattenham-corner`, 3 November 2026).
- Measured with the real feed's eight longest names in the results, the table at
  1176px in the rail wraps none of them and overflows neither axis.
- No horizontal overflow at any of the three widths, at 390px, or at 200% zoom.
- The panel opens as one column in the rail and two at 1024px, where the bar
  spans the page.
- `python -m tools.verify --browser` drives six pages, **1399 checks**, 50 not
  exercised, and both skip budgets inside their limits.

## Consequences

- **The rail is for screens wider than a laptop.** A 1366 or 1440 window is
  unchanged. The reader who gains is the one on a 1568px display or larger, where
  the page was previously drawing a 1248px column with empty space either side.
  ADR-0085 moved the gate to 1,528px, made the page the window's width and opened
  the refinements in the rail; the width measurement here still stands.
- **The page is 1568px wide where it was 1248px, on a screen that wide.** Every
  element inside the column keeps its own measure -- prose keeps its `ch` caps,
  the table keeps its 1176px -- so what grows is margin, and the rail fills it.
  The chooser and the privacy page are unaffected, and the station page and the
  chooser still share one column: the 20rem beside it is the rail, not a second
  column for the content.
- **The rail releases at its column's end.** On a page whose results column is
  shorter than the rail (a three-row demo page), scrolling past the list takes
  the rail with it, and the 56px budget rail covers the reader from there. A
  real page's twenty rows keep the rail in view.
- **Three checks changed their subject.** "Party beside ticket" and "a rem above
  the bar" are measured where the bar spans the page and again in the rail, and
  "the headings sit below the rail" does not apply once the table has scrolled
  to its own end.
- **The phone is untouched**, including the accessibility matrix at 200% zoom.
