# ADR-0056: The station name in the heading is the field you type into

**Status:** Accepted
**Date:** 1 October 2026
**Relates to:** ADR-0019 (one page per station), ADR-0024 (the release is
published under the repository's own path), ADR-0039 (the chooser and a station
page are one page), ADR-0042 (the station slot is as wide as its answer),
ADR-0046 (a row list ships as a table and a pool), ADR-0055 (the runner builds
what the reader will ask for).
Settles S12's control, which ADR-0039 left open.

## Context

ADR-0039 made the chooser and a station page one page, and ADR-0042 gave the
station's name in the heading a slot as wide as its answer. The name was a
button with a chevron beside it, labelled "Change". It opened a panel below the
heading that held a field and a list of every other station the build had a page
for.

Three things were wrong with it, and all three were found by using it:

- **The word on the page was "Change".** A heading reading `Train fares up to £20
  from GRANTHAM ▾` next to a button whose only visible text was "Change" made
  the reader go looking for the word "Change" on the page. The first-use note had
  to spend its first clause on naming the control, because the control would not
  name itself.
- **Choosing a station took three gestures and lost the budget.** Open the panel,
  find the field, type. The field was not in the heading, so the reader left the
  thing they were reading to go and look something up.
- **It was a button, so it could not be typed into.** A reader who already knows
  the station is leaving from, or who has it on a receipt, has to aim at a
  30-pixel target and hope the list is short enough to scroll.

## Decision

**1. The name is the control, and clicking it makes it a field.** The name sits
in an `.origin-slot-wrap` in the heading. Clicking it moves the existing
`#originSearch` field into that slot — the same input element, moved, not a second
one — and the name is hidden while the field is there. The field is sized to its
placeholder, so it is as wide as the word **station** and grows as it is typed
into, and the placeholder is the muted `--muted` token so an empty field reads as
"nothing typed yet" rather than as a label.

**2. The list filters as it is typed into.** `input` re-renders the options
through the same `matches()` the chooser uses, so a partial name, a partial code
and a pasted full name all work. There is no "search" gesture, because there is
nothing to search for until the reader has typed something.

**3. Choosing a station is still navigation, and it still carries the search.**
The options are real anchors to that station's page with the reader's budget,
ticket type and facets on the query string, so changing where they are leaving
from is a correction of the decision they have already made rather than a reset
of it.

**4. Escape closes it, from the field.** The keydown listener is on the field
rather than on the panel, because the field is moved *out* of the panel and into
the heading while the picker is open. A listener on the panel alone meant Escape
— pressed in the only place a reader can press it — bubbled past it and did
nothing. Focus returns to the name.

**5. A build with nowhere to change to still says something true.** With no
other station in the build there is no control to render, the station's own name
stands in the slot as plain text, and the first-use note says so: "This is the
only station this build has pages for, so the name above is not a link." The
build refuses to render a control that opens nothing, and it does not leave the
heading saying "from" and nothing.

## Consequences

- **The heading's first-use note got shorter, not longer.** "This page is about
  one station: the station name in the heading opens a list of the others.
  Everything below narrows the destinations from here." became "Click the
  station name to start from somewhere else." — because the control now names
  itself, which is what S12 was asking for.
- **There is no second button to press while the picker is open.** The name *is*
  the field. The browser suite used to check that pressing the control again
  closed the panel; it now checks that closing the picker puts the name back and
  that opening it puts the field where the name was. The old check timed out,
  which is what a control that is not on the page does.
- **The one-origin build is no longer the default**, because it cannot render
  this control at all — see ADR-0055.
- **Escape is a check, not a nicety.** It is asserted from inside the field,
  because a keydown listener on the wrong element is invisible to every other
  test in the suite.
