# ADR-0041: No row is tinted as the best fare; the order is stated in words

**Status:** Accepted
**Date:** 29 September 2026
**Relates to:** ADR-0014 (ticket links), ADR-0035 (what a page may claim about
the reference feed), ADR-0040 (the row carries the fare's code)
Settles finding 5 of the Grantham page audit, whose measurements are kept in
`docs/open-work.md`.

## Context

The list sorted its rows by the price actually on screen and tinted the first
one: `tr.best td { background: var(--best) }`, a blue wash over the whole row.
The page around it is scrupulous about not recommending anything. It names no
"best", no "recommended", no star; its own copy says the list is what the budget
lets the reader reach; and the count line above the table gave the number of  destinations rather than naming a winner. Then exactly one row was painted a
  different colour, with no legend, no label, and nothing in the nearby text.

Two things were wrong with that, and only one of them was cosmetic.

- **The tint stated a recommendation the page would not write down.** Colour is
  a claim, and the only claim the page is entitled to make here is "cheapest
  first" — which is a fact about the sort, not a judgement about the journey.
  The row that happens to be cheapest is not the journey a reader wants whenever
  a longer trip or an extra change is cheaper than the one beside it, and the
  columns give the reader the time and the change count to make that call
  themselves.
- **The cue was invisible to the readers who need a cue most.** A background
  colour on a table row is not announced by any screen reader, is not present in
  the copied journey text, and survives neither a monochrome print nor a
  colourblind reader's perception of a 7% wash on a light background.

The count line is the page's own summary of the list and it already says what
the list is: `24 destinations for up to £20.00 each`. The fact the tint was
standing in for — that the rows are in price order — is one clause.

## Decision

**The order is said in the count line, in words; no row carries a highlight, and
the browser suite fails a page that paints one.**

1. `tr.best td { background: var(--best) }` and its mobile twin
   `tr.best { background: var(--best) }` are deleted, and `render()` no longer
   sets `row.className = "best"`. The `--best` token stays: the row's detail
   row, the copy box and the code pill are still painted with it, so the token is
   a surface rather than the highlight it was named for.
2. The count line ends `, cheapest first`. It is appended where the count is
   already composed, so it cannot describe an order the list is not in: the same
   `wanted` array that sets the text is the array the rows are sliced from.
3. The suite judges the tint as paint rather than as a class name. It reads the
   computed background of every station row and requires one colour, so a row
   highlighted by any rule at all — a new class, a `:first-child`, an inline
   style — is caught. It reads the count line's words in both ticket modes,
   because the defect was only visible in one of them.

## Consequences

- **The page can no longer imply a recommendation it does not state.** The one
  claim left about order is a sentence, next to the number it qualifies, and it
  is the same sentence for the reader using a screen reader as for the reader
  looking at it.
- The row height and the row count are unchanged by this: the tint was paint,
  not layout.
- Finding 4 of the same audit — five controls in every row — is untouched here
  and still stands as recorded.
