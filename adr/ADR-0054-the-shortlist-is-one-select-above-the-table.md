# ADR-0054: The shortlist is one select, and its strip sits above the table

**Status:** Accepted, and superseded on its control choice. See "Amended
3 October 2026" at the foot of this file: the select is gone and each row
carries a checkbox. What it decided about the strip is unchanged and still
stands.
**Date:** 1 October 2026
**Relates to:** ADR-0019 (one page per station), ADR-0038 (the heading names the
mode), ADR-0041 (no row is tinted as the best fare), ADR-0044 (the page opens on
the cheapest fare), ADR-0046 (a row list ships as a table and a pool).
Settles S26's control choice, which no ADR had decided.

## Context

S26 asks for a shortlist of places to compare, share and copy, and never a
booking. The list was built and it worked: the codes are in the address, a shared
link restores them, and the copy names the origin, the budget, the fare, the time
and the changes for each place.

The control for adding a place was a button on every row, and that was wrong in
four ways, all of which were visible on the published page rather than argued
about:

- **Twenty copies of the same word.** Every row carried a button reading
  "Shortlist", so the one control a reader uses twice was the one control
  repeated twenty times, and it was repeated on the rows they were *not*
  choosing.
- **Pressing it reflowed the table.** The button's label was the state, so the
  row changed width when it was pressed, and the row above and below moved with
  it. A reader comparing rows had the ground shift under them at the moment they
  chose something.
- **The confirmation was 205px below the fold.** The list it produced was a
  section under the table, so the reader who had just chosen a place was told
  about it by scrolling away from the place.
- **The place a reader chose was the one that scrolled away.** Once a row was
  shortlisted, the row did not say so; only the section at the bottom did.

## Decision

**1. One control for the page, not one per row.** A `<select id="shortlistPick">`
sits in a strip above the table and lists exactly the destinations on the page
the reader is looking at. It is never longer than the table below it, and it
never offers a place that is already on the strip: the strip is the record of
what is held, and a second way to add the same place is a control that silently
does nothing.

**2. The strip is above the table, and above the count line.** A reader who has
just chosen a place is looking at the place. The strip is drawn where the action
is, and the held places are chips — the station's name, its price, and a way to
take it off the list. A chip's name is a `<button>` that scrolls to the row it
came from and puts the focus on its ticket link, because a chip is a way back
rather than a destination.

**3. The strip is above the count line, not between it and the table.** The count
line describes the rows under it. With the strip in between, the count sat 89px
above its own table with a row of controls in the gap, which is the same defect
ADR-0040 fixed for the provenance block: the thing a reader reads as a caption
is not next to what it captions. The reader chooses a place, then reads what the
list beneath them contains.

**4. The limit is said on the page.** Eight places is the limit. Reaching it
writes the sentence into the strip as well as into the status region, because a
control that stops responding with no explanation is the one thing a reader
cannot act on, and the strip is where they are already looking.

**5. The chip is a name and a price; the copied list carries everything.** The
chip is compact on purpose — it is a strip, not a second table. The copy still
names the fare, the time and the changes for each place, which is where a
comparison travels to somebody else.

## Consequences

- **A row is shorter and quieter.** The Tickets cell is a ticket link and the
  disclosure; it no longer carries a stateful button whose text changes.
- **Two browser checks became four.** Adding a place is now checked through the
  select, and three claims that used to be covered by the per-row button are
  checked directly: a held place is not offered again, the held places are
  announced to a screen reader as well as drawn, and each chip is a way back to
  its row.
- **A chip is a button, not a link.** An earlier version made it a
  `javascript:` URL. A control that says what it does is better than one that
  looks like navigation and goes nowhere.
- **The station pages this suite runs against now exercise the strip rather than
  the button**, and a page with one row cannot exercise either; the suite says so
  rather than passing on an empty list.

## Amended 3 October 2026: the control is back on each row, as a checkbox

The reader asked for a checkbox on each row, and the select is gone. That
reverses the decision above and keeps the objection it was made on: twenty rows
is still twenty controls, and the answer was never to have fewer of them. What
changed is that these twenty say the same thing in the same way -- a tick and an
untick, where the button they replaced changed its own text and reflowed the
table when it was pressed -- and each one sits beside the place it acts on
instead of in a select above the table, so holding a place is a tick on the row
the reader is already reading rather than finding its name in a list of names.

What is kept from the original decision:

- **The strip stays where it is**, above the table, with the chips that say what
  is held and the copy and share controls that were its point.
- **No twenty copies of the same word.** A checkbox has no text to repeat.
- **The control never changes its own label.** A ticked box is the state.

What had to be built rather than assumed:

- **A refused tick unticks itself.** The list is capped at eight and says so on
  the strip rather than adding. The browser has already ticked the box by the
  time `toggleShortlist` returns, so the box is put back to what is actually
  held. A ticked box beside a place that is not on the strip is a shortlist the
  reader cannot account for. Verified: with eight held, a ninth tick leaves
  `checked` false, the codes at eight, and the strip carrying the explanation.
- **The box is named per row** -- "Hold <place> in the shortlist" -- because a
  column of unticked boxes is a column of controls with no name of their own.
- **The box reads its state from the list on every render** rather than
  remembering itself, so a row rebuilt by a mode change cannot claim a place is
  held when the fare behind it has changed.
- **The column exists in the header too**, and the two columns a prices-only
  build stands down move with it: they are removed by index, so they are now the
  fourth and fifth rather than the third and fourth. The test that pins those
  indices says so in its comment, because the failure mode -- header and cells
  drifting apart -- is the one this file's own predecessor recorded happening.
- **The target is 44px and the mark is not.** The checkbox is the size a
  checkbox is meant to be; a label around it is what a finger aims at, and the
  label is also what makes the whole cell the target.

Two browser checks became three. The old pair -- the select adds a place, and a
held place is not offered again -- becomes: every row carries a box and a held
place's box is ticked, checked in both directions against the list itself, and
every box is named for the place it holds. The assertion that is gone is the one
about the select's options, which was a claim about a control that no longer
exists rather than about the shortlist.
