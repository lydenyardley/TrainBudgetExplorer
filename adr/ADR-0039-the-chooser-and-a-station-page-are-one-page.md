# ADR-0039: The chooser and a station page are one page with different content

**Status:** Accepted
**Date:** 29 September 2026
**Relates to:** ADR-0019 (one page per station), ADR-0033 (one stylesheet inlined
per route), ADR-0037 (the reader chooses the palette), ADR-0038 (the heading
names the mode)

## Context

The chooser and a station page are the same page twice. Both ask the same
question with the same two editable slots in it, and a reader who arrives at one
and clicks through to the other should recognise where they are. They did not:

- the chooser's column was 56rem against the station page's 78, so the same
  sentence fitted two lines on one route and three on the other, and the first of
  those three was two words long;
- the chooser's heading was 1.5rem against a `clamp(2rem, 6vw, 6rem)`;
- the chooser named its budget in a labelled input of its own, while a station
  page had it as a field inside the heading's sentence, so the two routes had two
  different controls for one value under two different names;
- the chooser carried a kicker line above the heading, which is the pattern the
  privacy page had already dropped for reading as a marketing hero (C30);
- its station was a plain text field, while a station page's was a slot that opens
  a list of the others — the same idea in two components;
- and the station page carried the filter bar, the provenance block and a fold
  that behaved differently at different viewport widths.

Two of those were bugs rather than taste. The fold was opened and closed by a
media query plus a `resize` listener, so the same control meant "show the panel"
at one width and "hide it" at another, and rotating a device could discard the
fold the reader had chosen. And the station page's disclosure mark was written as
a CSS escape inside a Python string, where Python read it first: every station
page shipped a control character followed by the letters "be" as the label of its
disclosure, which no reviewer would see in the source and every reader would see
on the page.

## Decision

**One column, one heading, one slot component, one fold — and the differences
that remain are the two facts each route has and the other does not.**

1. **One column for the site.** `--page-max: 78rem` and `--page-pad` live in the
   shared block, and no route states its own. The station page's table simply uses
   the width it is given. The policy page keeps its 42rem measure, deliberately:
   a document is read in a measure, not in the width of a table (ADR-0033's block
   is the one exception, and the test says so by name).
2. **The chooser's station slot is the station page's slot.** The same
   `.origin-slot` skin, the same accent, the same dashed underline — a field
   holding the word *station* where a station page holds a name that opens a list.
   The difference a reader sees is the difference the data supports: on the
   chooser there is no answer yet, so the slot is empty, focused on arrival, and
   its caret is the browser's own.
3. **The chooser has no filter bar.** Its only two controls are the two gaps in
   its heading, and the list below answers them. The suite asserts the absence in
   both directions — no `.filter-bar`, no `#moreFilters` — so a bar cannot come
   back without a decision.
4. **The fold is the reader's, at every width, and it is one state.** One toggle,
   one `data-open`, no `matchMedia`, no resize listener, and the summary is
   rewritten from the page's own controls on every render, so it cannot describe a
   filter the reader has already cleared.
5. **The refinements are the only thing that folds; the budget never does.** The
   budget is the page's question rather than a refinement of it, and a reader
   should never have to open a drawer to answer the question on the page.
6. **The disclosure mark is drawn, not written.** One inline SVG chevron, shared
   by the refinements control and the station slot, `aria-hidden` because a
   decoration is not a word — and because the browser reads CSS generated content
   inside a heading as part of the heading's name, which is how the header's old
   "↕" became text in the accessible name.
7. **The chooser's list is a grid of fixed-measure cells, not one row per
   station.** In a 78rem column a single row per station put a station's own
   destination count most of a screen away from its name, so the three facts of a
   row stopped being one thing. Cells are `minmax(min(20rem, 100%), 1fr)`: the
   `min()` is not decoration — a 20rem track in a 288px column is a page that
   scrolls sideways at 200% zoom, which the suite caught.
8. **The distill pass, in the order the reader meets it.** The palette control
   lost its box and became a muted glyph at the same 44px target; the slider and
   its note share a line, the note being the one sentence that says the slider and
   the heading's number are the same number; the slider is capped at a control's
   width instead of stretching to the width of a table; the filter bar lost the
   card that held two controls, which said nothing the controls do not say
   themselves; and the fine print sits as a block with tighter margins rather than
   as eight paragraphs with a paragraph's spacing between them.

## Consequences

- **The two routes can no longer drift in width or heading size**, because neither
  states one. A test asserts that neither route's own block contains
  `--page-max` or `--page-pad`, which is the shape of the guarantee.
- The browser suite had two checks that were silently testing the old chooser:
  they filled `#pick`, an id that no longer exists, and one reported a variable
  that a block removed in the same pass had owned. Both were found by running the
  suite, not by reading it — the run is the only thing that reads the whole file
  as a program.
- A test now refuses a script escape in markup or in CSS on any route. The
  chevron bug and the moon bug in the theme switch are one family: a backslash
  escape means something in a script and is five characters everywhere else, and
  the mistake is invisible in the source. Both halves are covered, and both were
  proved by putting the bug back and watching the guard fail.
- The chooser's heading is now read out of the fields the reader sees rather than
  out of `textContent`, which cannot see an input (ADR-0038).
- Two numbers moved: the demo site's checks went from 236 to 241 and its sweep
  from 548 to 555, because the absence of a filter bar, the shared column and the
  escape guard are all assertions now.
