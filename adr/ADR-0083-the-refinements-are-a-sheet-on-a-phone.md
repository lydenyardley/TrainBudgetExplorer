# ADR-0083: The refinements are a sheet on a phone

**Status:** Accepted
**Date:** 4 November 2026
**Relates to:** ADR-0082 (the refinements sit beside the list on a wide screen), ADR-0019 (the page reflows at 44rem), `docs/open-work.md` O42

## Context

The 3 November 2026 review asked for the refinements as a side panel where the
screen is wide and a pop-out where it is too narrow. ADR-0082 shipped the wide
half and recorded the narrow half as O42, because a drawer over the rows it
filters is a different bargain and nobody had measured it.

Measured on the build the browser suite drives
(`_shape_site/reviewed-name/from/london-kings-x`, which carries the day control),
at 390x844 the folded bar was 267px: the budget track, the folded plate, the key
line and the day control, and the first destination row began at 624px, with one
whole row above the fold and a second cut to its last two pixels. Of a 844px
window the controls a reader had not asked for took the top two thirds of the
list.

ADR-0082 put the bar at 177px at that width; that is the fold alone, and the
whole bar this ADR moves is 267px, because the budget track and the day control
sit beside it on the strip. The 267 is the number a sheet has to beat.

The budget is already on the page twice: the heading holds the number in an
editable field, and the bar held a slider for the same number.

## Decision

**Below 44rem the whole filter bar is a sheet over the list.** The same
breakpoint the table stacks at, because it is the one width where the controls
can neither sit beside the results nor fit in a line above them.

Eight rules hold it together:

1. **One bar at every width.** No control exists in only one layout: the budget,
   the plate, the panel, the day and the key line are the same elements in the
   same order, written once by the template. The foot is hidden at every other
   width rather than absent from the markup.
2. **The state stays the reader's.** The same button opens and closes the same
   panel; there is no resize listener and no media query in the script. What is
   width-dependent is where the open panel is painted, which is the one thing a
   layout decides. The fold a reader chose survives a rotation.
3. **The budget goes into the sheet, because the heading already asks it.** The
   page's question is in the heading's own editable field, on the page at every
   width. A slider is a convenience for that number, and a convenience is what a
   sheet may hold. It also satisfies the 56px rail's own rule by construction:
   the rail is a shortcut to a control the reader has scrolled past, and a slider
   inside a closed sheet has not been reached, so `budget.getBoundingClientRect()`
   reports a box on no screen and the observer keeps the rail away. No code
   changed for that; the rule's own words already say it.
4. **It is not a modal.** No scrim, no focus trap, no disabled page: the sheet
   lifts off the list with a shadow and nothing behind it is turned off. Focus
   stays on the plate, which is the sheet's own header, so Escape has nothing to
   restore and no key handler was added.
5. **The foot is the count from the sheet's side.** The one control that closes
   the sheet says what is behind it ("Show 42 destinations"), and it is written by
   the same render that writes the count line, so the two cannot disagree. It is
   stuck to the sheet's foot, because the sheet is 88vh of a phone and a reader who
   has scrolled to the day control must not have to find the way out again.
6. **The day goes with it, and it is not a filter.** Below 44rem the sheet is the
   only road to the day control, which is why the check that reads it lives beside
   the sheet's own: `<div class="service-day">` is inside the bar in the markup, so
   the sheet cannot lose it without the bar losing it, but a panel that clipped its
   contents instead of scrolling would leave a phone unable to change the day. The
   suite scrolls the sheet to its end and reads the control there. The label stays
   "Times for", so it reads as itself rather than as a sixth filter.
7. **The sheet takes the scroll, not the page.** `max-height: 88vh`,
   `overflow-y: auto` and `overscroll-behavior: contain`, so a reader's thumb on
   the sheet does not scroll the list underneath it.
8. **44rem, not 98rem.** Between the phone breakpoint and the rail's 98rem the bar
   is two columns above the list, and the reader can see the controls and the
   results at the same time; the sheet's cost, a press before the list, buys
   nothing there that the bar's 204px was not already worth. Measured at 768x800,
   the bar is 204px and the first row at 598px, so a sheet would save 120px; the
   decision is that a pointer reader's controls stay in reach instead.

## Evidence

Measured 4 November 2026, reading the same markup twice at each width: once as
built, once with the phone rules cancelled, so only the layout differs. The page
is the shape page the browser suite drives at 390px, which carries the day
control the demo feed does not.

| Window | Bar | First row | Whole rows above the fold |
|---|---:|---:|---:|
| 390x844, folded bar | 267px | 624px | 1 |
| 390x844, sheet | **84px** | **441px** | **3** |
| 390x720, folded bar | 267px | 624px | 0 |
| 390x720, sheet | **84px** | **441px** | **2** |
| 1366x768 | 204px | 646px | 1 (unchanged) |

- **The strip is 84px with a fine pointer** (the toggle and the key line at its
  own 18px plus the bar's margin), **and 44px on touch**, where the key line is
  already hidden. So the sheet saves 183px against the 267px bar on a fine
  pointer and 223px on a phone.
- **No horizontal overflow** at 390, at 304 (200% zoom) or with the sheet open,
  and the sheet's contents scroll inside a 88vh box rather than the page.
- **The demo page saves 182px** (690 to 508) because its taller heading and short
  list differ from the shape page's: what the sheet takes away is whatever the bar
  was carrying.
- `python -m tools.verify --browser` drives six pages, **1417 checks**, 52 not
  exercised, and the five sheet checks run on the four station pages it sweeps.
- The browser suite's page-opening step folds the sheet where the page draws one,
  so a section that opens a page to read its list reads it and not the panel: one
  helper, and a check that presses a control inside the panel opens it around that
  press. `tests/browser/station-layout.cjs` holds the five claims.
- The rail check that made a 304px window read a slider below the fold now reads
  at 768, because below the phone breakpoint the slider has no above-the-fold
  state to be passed: at 304 the check could only report itself not exercised.

## Amendment — 5 November 2026: the open sheet meets the viewport

An 88vh sheet leaves a crack above its top edge. Measured on the published
Grantham page at 390x844 with the sheet open, the heading runs from 71px to
144px and the sheet began at 101px, so "Train fares up to £20" sat above the
budget slider and "from GRANTHAM" was cut off by the sheet. The open sheet now
meets the viewport (`inset: 0`). It is still not a modal: no scrim, nothing
behind it is disabled, and the sheet still takes the scroll. The heading, and
the budget field in it, are there again when the sheet closes.

## Consequences

- **The phone gains two rows.** The first destination moves from 624px to 441px
  on an 844px window, and the fold holds three whole rows rather than one.
- **A phone reader presses once to narrow and once to see the list.** That is the
  trade: the controls are no longer above the results, and the price is two
  presses instead of none.
- **A narrow desktop window gets the sheet too.** A 704px window with a keyboard
  and a mouse is the phone layout, as it already was for the table; the sheet's
  header and foot are buttons, so the keyboard reaches both.
- **The bar's own line goes.** Below 44rem the page shows one plate between the
  heading and the first row. The budget slider and the day control travel with the
  sheet rather than the strip, so a phone reaches both in one press; the count line,
  the ticket-link fold and the headline's own budget field stay where they were.
- **Opening the sheet moves the list up by the strip and its margins** (100px
  measured), because the strip leaves the flow to become the sheet's header. That
  is a shift behind a panel that covers the window, not a page jump; the scroll
  position is unchanged.
- **The budget slider is one press away on a phone**, and the heading's field, the
  `/` and `b` keys and the address all still set it without opening anything.
