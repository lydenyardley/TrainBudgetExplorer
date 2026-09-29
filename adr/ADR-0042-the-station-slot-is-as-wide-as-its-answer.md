# ADR-0042: The station slot is as wide as its answer, and it opens the list it belongs to

**Status:** Accepted
**Date:** 29 September 2026
**Relates to:** ADR-0019 (one page per station), ADR-0033 (one stylesheet inlined
per route), ADR-0039 (the chooser and a station page are one page)
Settles the review finding of 29 September 2026 that the slot's underline ran on
past the word it belongs to, and that the field had no way into its own list.

## Context

The chooser's station slot is the one editable gap in the heading, and it shipped
as a text field at a fixed `width: 9ch`. At the heading size that is wider than
the word *station* it holds while empty, so the dashed underline — the whole
affordance, the shape a browser draws under a field — ran past the word and said
the question was bigger than it is. Two further facts about the same field:

- **It was wider than the answer on a short name and too narrow on a long one.**
  `GRANTHAM` is eight characters and `LONDON KINGS CROSS` is seventeen; a fixed
  width cannot hold either one honestly.
- **The list it filters was reachable only by tabbing.** The chooser's list is a
  column of anchors under the field, capped at forty; a keyboard reader had no
  key that meant "down into what I just typed", which is the one key a field
  sitting over a list is expected to answer.

Both routes that offer the slot — the chooser's field and a station page's picker
behind the station name in the heading — are the same control, and only one of
them had any keyboard way into its list.

## Decision

**The field is sized to its content, capped in `ch` and in `vw`; and both fields
answer ArrowDown into their list and ArrowUp/Escape back to the field.**

1. **`field-sizing: content`**, with the old fixed width kept as the
   `@supports not` fallback: a browser that cannot size a field to its content
   still gets the honest-in-one-direction 9ch rather than a field that collapses.
   The empty field is then exactly as wide as the word *station*, and the field
   grows as the reader types.
2. **The cap is `min(18ch, 90vw)`, and neither half may be a percentage.** This
   is the part that took a measurement rather than a preference. The slot is
   shrink-to-fit, so a percentage `max-width` on its only child is treated as
   `none` while the slot decides its own width — and the heading's line then
   measured the field's content: 3,047px with sixty characters typed, which
   scrolled the page 1,739px sideways on a 1440px screen. `ch` scales with the
   heading's own size, and the `vw` share is what fits on a phone.
3. **ArrowDown from the field focuses the first option; ArrowDown/ArrowUp walk
   the options; ArrowUp from the first, or Escape anywhere in the list, returns
   to the field.** The options stay real anchors, so the browser keeps its own
   accessible naming, its own Enter, and its own open-in-a-new-tab; this is why
   the block is a dozen lines rather than a combobox implementation. It is one
   shared block inlined into both routes, the way the chevron and the theme
   block are, because two routes that ask for the same keys should not be able to
   answer them differently.
4. **Clicking the slot focuses the field and selects nothing.** The first form of
   this put the caret in the field with the whole value selected, so that a
   reader could replace the last answer by typing over it; it was dropped because
   the value on this route is the reader's own query, and selecting it means a
   reader who clicked the edge of what they had typed lost it on the next
   keystroke. The caret goes where the browser puts it.

## Consequences

- The underline is the width of the answer at every heading size, which is what
  it was always claiming.
- The browser suite now measures the overflow with sixty characters typed at both
  1440px and 390px, and drives the arrow keys in both the chooser's list and the
  station page's picker. The cap was proved in both directions by restoring the
  percentage form and watching the check fail.
- The one-origin artefact is unaffected by 3: with no other station to move to,
  the heading states the name as text and there is no picker to enter, which the
  suite asserts as the absence of the control.
