# ADR-0053: The row names its fare in the reader's words, and the code waits in the row

**Status:** Accepted
**Date:** 1 October 2026
**Relates to:** ADR-0025 (the restriction gate and the broad fare set), ADR-0040
(the row carries the fare's code), ADR-0041 (no row is tinted as the best fare),
ADR-0043 (the row keeps the action and its panel holds the rest), ADR-0044 (the
page opens on the cheapest fare), ADR-0045 (the row names where a split would
split).
Supersedes **decision 2 of ADR-0040**; its measurements and its other decisions
stand.

## Context

ADR-0040 replaced the FARE and CONDITIONS columns with a column carrying the
feed's own ticket code — `SDR`, `2AS`, `CDR` — and put the sentence about the
fare in the row's disclosure. That was the right call about the *sentence*, which
had been repeated on twenty identical rows, and the wrong one about the *code*.

The code is a seller's vocabulary. It is the field a retailer types into their
booking system, and it is the field the National Rail site shows a passenger who
is looking up an existing ticket. A reader comparing twenty prices does not know
what `2AS` is, cannot tell from it whether a fare is restricted, and cannot act
on it. It was placed in the one column every reader scanned, on every row, in
front of the one number they came for — the same mistake as the twenty repeated
sentences, one level down.

Three further things were true of that column and are worth recording because
each was found by reading the page rather than by reading the code:

- The column header said **Fare code** while the cell beside it could be the fare
  in words, the code, or neither, depending on the build.
- The advance flag ("this fare needs a named train") was a lower-case token —
  `advance`, `restricted` — in the cell, in a monospaced-looking column, with no
  sentence anywhere near it.
- The code is not even a property of the fare a reader compares. It is a
  property of the feed record, and the same journey can be reached by a fare with
  no restriction code and one with a restriction code.

## Decision

**1. The column is a word, not a code.** The header reads `Fare type` and the
cell reads exactly one of **Advance**, **Restricted** or **Regular** — the three
states of the fare that change what a reader may do with it:

| word | the feed says | what it means to a reader |
| --- | --- | --- |
| Advance | `isAdvance`, no restriction code | they must name a train, and the price and availability can change |
| Restricted | a restriction code | there is a condition, and the panel below states it in the feed's own words |
| Regular | neither | nothing to check |

The cell carries `data-kind` so the palette can treat the two that need a second
look differently, and a `title` that says the same thing in a sentence for a
mouse.

**2. The code moves into the row's own disclosure, under "Feed record".** It is
still on the page, in the place ADR-0040 put everything else a seller asks for,
and it is still reachable on every row. It is available when it is asked for and
invisible until then. The panel's record also carries the route, the quality the
fare was priced as, and the validity the restriction feed states.

**3. The sentence in the panel is a full sentence, and the condition is only
there when there is one.** `fareSentence()` opens with what the fare is — "Advance
single: you choose the train, and the price and availability can change." — and a
row with no restriction code in the feed is not given a condition paragraph to
read. A previous version printed "No travel conditions on this fare in the feed"
on every unrestricted row, which is the twenty-identical-sentences defect in a
new place.

**4. The browser suite reads the fare type off the row and the code out of the
panel, separately.** It asserts the word matches the payload's own flags for
that row, and separately that the disclosure carries a non-empty code. A check
that demanded the code be on the row would have been a test of ADR-0040 rather
than of the page.

## Consequences

- **ADR-0040's measurement stands and its decision 2 does not.** The wrap guard,
  the count line's position and the provenance fold are untouched, and the
  review that produced them is still the record of why the table is shaped this
  way.
- **The header is finally true of the cell.** `Fare type` says what the column
  holds, which is the same defect ADR-0040 fixed for the Price column and the
  same class of bug: a header and a cell written in two places that drifted.
- **A reader who needed the code has to open the row.** That is the cost, and it
  is the reader the page does not have: the code is for a seller, and a seller is
  reading one row, not twenty.
- **The advance flag is gone as a token and kept as a word.** The browser suite
  now finds an advance row by `data-kind` rather than by matching the string
  `advance` in a cell, which is a check of the page rather than of a literal.
- **Contrast cover moved with the sentence.** `.fare-line` joined `.condition` in
  the palette probe, and the probe opens a row that *has* a condition rather than
  the first row: a page whose cheapest fare is unrestricted would otherwise have
  reported the C14 regression as covered while measuring no condition at all.
