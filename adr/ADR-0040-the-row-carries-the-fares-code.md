# ADR-0040: The row carries the fare's code, and its condition waits in the row

**Status:** Accepted
**Date:** 29 September 2026
**Relates to:** ADR-0019 (one page per station), ADR-0025 (the restriction gate and
the broad fare set), ADR-0033 (one stylesheet inlined per route), ADR-0038 (the
heading names the mode), ADR-0039 (the chooser and a station page are one page).
Settles findings C03, C07 and C14 as they stood against the table.

## Context

A review of the published Grantham page measured the table at 1440×900 and
390×844, in both palettes. The measurements are filed in
`docs/open-work.md` (which keeps that audit's measurements); the ones that
force a decision
are these:

- **The Price column was 56px wide and 13 of the first 20 prices painted as two
  lines.** `£10.10` read as `£10.1` over `0` — the same glyphs, a different
  number — and `CHANGES` wrapped mid-word in a 72px column. Nothing in the
  stylesheet refused either: a cell's width came from the header word above it,
  and the price paid for it. A wrapped price is not a cramped column. It is a
  wrong number, on the one figure the page exists to compare.
- **The FARE and CONDITIONS columns repeated one sentence on all twenty rows.**
  Every row read `Unrestricted Anytime Day Return` and `No travel conditions on
  this fare in the feed.`: 40 cells restating the mode the mode control had
  already named, and between them the reason every row stood 81px tall. The
  rows a reader actually compares differed in price, in time and in changes,
  and in nothing these two columns said.
- **The count line sat 205px above the first row on desktop, 455px on a phone**,
  with six provenance paragraphs between them (`modeNote`, `priceSource`,
  `restrictionReference`, `freshness`, `buildMetadata`, `linkNote`). The first
  fare therefore began 14px below the fold of a 900px laptop: the reader who
  came for a price met a build fingerprint first.
- **C03 was satisfied by a paragraph where it should be satisfied by a line.**
  The seller handoff and the commission had been moved out of the methodology
  accordion, which was right, but they were three paragraphs of prose above a
  table — and the same argument that moved them there ("a reader must learn what
  the click costs before they click") does not require the whole wording to be
  rendered, only the fact.

Two further findings were measured and are **not** decided here, and are left in
the audit rather than quietly fixed: the Tickets cell carries five controls on
every row (100 targets on page one, of which `Card details` and `Copy` belong in
the row's own disclosure), and the cheapest row is tinted with no legend on a
page that refuses to imply a recommendation.

## Decision

**1. Neither half of the table wraps, so a column's width comes from a number and
never from a header word.** `th` and `td.num` carry `white-space: nowrap`, and the
browser suite measures the *painted* lines — `getClientRects()` over each cell's
own contents, counting distinct tops — rather than reading `nowrap` off the
stylesheet. A CSS reading would have passed on the day the prices wrapped. On the
reviewed page the Price column measures 81px, and its widest number is what sets
it.

**2. The row carries the fare's code; the sentence about it waits in the row's own
disclosure.** The FARE and CONDITIONS columns are gone as columns. The cell that
held the fare in words holds the feed's own ticket code (`SDR`, `CDR`, `SVR`), and
one word beside it only where the row differs from its neighbours: `advance` for a
fare that is train-specific, `restricted` for a fare with conditions to read. What
every row has in common stays unsaid on the row, because the mode control above
the table says it once. The sentence itself — the fare in words, the condition,
the validity the feed states, and the feed's own record — is in the panel the row
already had, beside the times. That is C07's pointer kept and made true: it used
to say "conditions in the next column", and there is no next column any more, so
it says "condition below" and the condition is the next thing in the same panel.

The toggle exists on **every** row now, not only where the build has times. A
prices-only build has no times to hang a toggle on and still has a fare to explain,
and the state that used to fall out of that — a condition unreachable on a
timetable-free page — was a content loss hiding inside a layout choice. Where there
are times to count, the label still counts them.

**3. The count line sits on its table, and the provenance above it is one fold.**
`#summary` moved from above the provenance block to immediately above `<table>`,
with its own generous margin reduced to the gap between a caption and the table it
captions. `#linkNote`, `#disclosure` and `#buildMetadata` are one `<details>` above
it, and the **fold's summary is rendered, states what it holds, and is what is
measured**: when the ticket links are tracked it says so — "and how this site is
paid" — so the one fact C03 insists on is not behind a click. On the reviewed page
the block between the count and the table went from 205px to one line, and the first
fare from 14px below a 900px fold to 33px above it.

**4. What a fold may hold is bounded by the promise it does not break.** The
budget is never folded (ADR-0039). The freshness, price-source and
reference-feed lines are not folded here either: the first two are statements
about the numbers themselves and the third is a claim about the conditions whose
whole point is that a reader meets it before comparing two prices. What folds is
the material that describes the *build* and the *link* — and the line that stays
visible names both.

## Consequences

- **A test could no longer be a reading of the template.** The wrap guard is a
  measurement of painted line boxes, and it was proved by putting the defect
  back: with the price column forced to 56px the check fails on the header word,
  and at 40px it fails on `£8.70` and `50m` as well. The ledger is in the audit.
- **The contrast cover for a condition had to move with it.** `.condition` and
  `.restriction` are one disclosure away now, so a probe that measured only what
  happened to be unfolded would report the sentence a reader must not misread as
  0×0 and skip it silently — silently losing C14. The palette probe opens the
  first row, closes it again, and a check fails if `.condition` stops being among
  the things measured on a page that has rows.
- **Rows lost two fifths of their height.** 81px to 49px on the reviewed page,
  which is what a reader who came for a price gets back: twenty rows in 980px
  instead of 1620px.
- **The browser suite grew rather than shrank.** On the demo site 555 checks
  became 570 and on the published one 231 became 236: three checks for the wrap,
  the count's position and what stands between the provenance and the first row;
  two for the advance flag on the row and the sentence one disclosure away; one
  for the condition still being measured for contrast.
- **ADR-0025's mechanism is superseded, not its decision.** The mode note still
  states what the open set contains and that a restricted fare is not valid on
  every train; a restricted row still points at the feed's own words. What
  changed is only where those words are: a panel in the row rather than a column
  beside it. ADR-0025 is left as the record of the decision it was.
- **Two findings are deliberately left open** — the five controls per row and
  the unlabelled tint on the cheapest row — and are recorded in the audit so the
  next pass starts from the measurement rather than from a fresh look.
