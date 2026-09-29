# The real Grantham page — five findings on the results table

**Date:** 29 September 2026
**Scope:** the published one-origin build of the station page (`--origin GRA`),
reviewed as it renders rather than as it reads in the source.
**Artefact reviewed:** `_site/from/grantham/index.html`, built 29 September 2026
06:14:36 UTC, source fingerprint `b7ec6fde496c030f`. 20 rows on page one of 42
priced destinations in the mode it opens in.
**Method:** the page was served over HTTP and measured in Chromium in both
palettes at 1440×900 and 390×844. Every number below is a DOM measurement
(`getBoundingClientRect`, `getClientRects`, computed style), taken from the
rendered page and not from the template; the two figures the review reported
that are not independently re-measured here are marked as the review's own.
**Disposition:** findings 1–3 are fixed in this pass and the ADR that carries
them is ADR-0040. Findings 4 and 5 are recorded and deliberately not fixed.

## 1. The price column was 56px wide, so the price wrapped

**Measured:** the seven columns were station 176px, price 56px, time 62px,
changes 72px, fare 225px, conditions 234px, tickets 352px. With a 56px price
column, **13 of the first 20 prices painted as two lines**: `£10.10` rendered as
`£10.1` over `0`, and the same for £12.60, £13.30, £13.70, £14.10, £14.40,
£14.70 and £15.40. `CHANGES` wrapped mid-word in its 72px column.

**Cause:** nothing in `SHARED_CSS` refused a wrap on `th` or on `td.num`, so
each column's width came from the widest thing in it that could not break — and
for a two-word header that is the header. The one figure the page exists to
compare was competing for width with the word above it.

**Disposition: fixed** (ADR-0040 §1). `white-space: nowrap` on `th` and
`td.num`; the Price column now measures **81px** and the widest number is what
sets it. The guard is a new browser check that counts *painted line boxes* over
every header, every numeric cell and every fare code — `getClientRects()` over a
cell's own contents, distinct tops — and it was proved by putting the defect
back:

| Tamper | Check result |
|---|---|
| price column forced to 56px, `white-space: normal`, CHANGES-only | **FAIL** — `{"text":"Changes","lines":2,"width":56}` |
| price column forced to 40px, same | **FAIL** — `£8.70` in 2 lines, `50m` in 2 lines, `CHANGES` in 3 |
| as shipped | **ok** — 18 cells measured, price column 78–81px |

## 2. Forty cells restated the mode the reader had already chosen

**Measured:** all 20 rows read `Unrestricted Anytime Day Return` in FARE and
`No travel conditions on this fare in the feed.` in CONDITIONS. **All 40 cells
were two lines tall.** Each row was **81px** high, of which the two columns were
the greater part.

**Cause:** the two sentences are facts about the *mode*, and the page already
states the mode once, in the ticket-type control and in the note above the
table. Printing them per row is the same sentence twenty times, and the page
paid for it in height — 20 rows occupied 1620px, about two laptop screens.

**Disposition: fixed** (ADR-0040 §2). The row carries the feed's own ticket code
where the sentence was, with one word beside it only when the row differs from
its neighbours (`advance` for a train-specific fare, `restricted` for a fare with
conditions to read). The fare in words, its condition, the validity the feed
states and the feed's own record are in the row's own disclosure, beside the
times. Rows now measure **49px**, so 20 rows occupy 980px instead of 1620px.

Two things were kept rather than dropped with the columns:

- **the condition is still on the row**, one disclosure away, so C07's pointer
  survives with its wording made true (`Restricted fare — condition below`);
- **the toggle now exists on every row**, not only where the build has times, so
  a prices-only build cannot leave a fare's condition unreachable. On the
  reviewed page five of the twenty rows have no departures, and five conditions
  had no home at all under the old shape.

The contrast cover moved with the sentence. The palette probe used to find
`.condition` in the DOM of every row; it is now inside a fold, so a probe that
measured only what was unfolded would report the sentence a reader must not
misread as 0×0 and skip it — silently losing the C14 regression cover. The probe
opens the first row and closes it again, a check fails if `.condition` stops
being measured on a page that has rows, and the mechanism was proved by probe:

| Probe | `.condition` |
|---|---|
| as shipped, row closed | absent (would be skipped) |
| as shipped, row opened by the probe | measured |
| after the probe closes the row again | absent |

## 3. The count line was 205px from its table

**Measured at 1440×900:** the count line `24 destinations for up to £20.00 each`
sat at y=654 and the table began at y=859 — **205px**, with six paragraphs
between them: mode note (686), price source (709), restriction reference (731),
freshness (773), build metadata (795), link note (818). The first fare began at
y=914, **14px below the fold of a 900px laptop**. At 390×844 the same block
measured **455px** (the review's own measurement: the same six paragraphs wrap
to more lines in a phone column).

**Cause:** every one of those paragraphs is a statement worth making, and there
was no line between "worth making" and "worth making *here, before the first
fare*". The build fingerprint and the wording of the seller handoff are the two
a reader comparing prices does not need rendered.

**Disposition: fixed** (ADR-0040 §3). The count line moved onto its table, with
its 1.75rem top margin reduced to a caption's gap, and `linkNote`, `disclosure`
and `buildMetadata` are one `<details>` above it. The **rendered** fold summary
is what is promoted: it states what it holds, and when the links are tracked it
says the site is paid, so C03's fact is a line rather than three paragraphs.
Measured after the change, in both palettes:

| | before | after |
|---|---|---|
| block between the count and the table | 205px | **8px**, nothing between them |
| what stands between the provenance and the table | six paragraphs | `linkTerms`, `summary` |
| first fare, 1440×900 | y=914 (14px below the fold) | **y=867 (33px above it)** |
| first fare, 390×844 | below the fold | visible, table reflow unchanged |
| sideways scroll at 321/705/760/1024/1280/1440px | none | none |

## 4. Five controls on every row — recorded, not fixed

**Measured:** the Tickets cell carried `Tickets`, `5 times`, `Card details`,
`Copy` and `Shortlist` — 100 pointer targets on page one, all inside one cell
352px wide on a 1440px screen and 240px at 705px.

**Assessment:** two of the five — `Card details` and `Copy` — are not actions a
reader takes per row; they are detail about the row and belong in the row's own
disclosure, which now exists on every row and already carries the fare and its
condition. That would halve the row's controls without losing an action.

**Not fixed here** because it changes what the row promises at a glance (a
reader who could see `Copy` now has to open the row), and that is a decision
worth making on its own evidence. Recorded with the measurements so it does not
have to be re-measured.

## 5. The cheapest row is tinted with no legend — recorded, not fixed

**Measured:** `tr.best` sets `background: var(--best)` on the first row of the
price-sorted list — the cheapest — and nothing on the page says so. Every row on
the page carries the tier-and-shade difference as a background wash on the cell
that also carries `tr.detail`'s panel, so the tint is not decoration the reader
can infer.

**Assessment:** on a page that is scrupulous about not implying a recommendation
(no "best", no "recommended", no star), an unexplained tint on exactly one row
does imply one. It either needs a word — the cheapest row, labelled — or it
should go.

**Not fixed here** because the tint is also the page's only visual grouping of
the sort order, and which of the two readings is right is a product decision, not
a defect. Recorded.

## What was already right

Verified in both palettes at 1440×900 and 390×844, before any change in this
pass:

- the heading holds at 390px and at 1440px, the same two lines, with no dangling
  separator — the only line break is the one written before the origin;
- the two palettes are one design: the same measurements and the same contrast
  in both, which the accessibility matrix checks per scheme;
- the palette switch is a quiet glyph with its state announced;
- at 390px the table reflows to labelled cards with price, time and changes on
  one line, and no cell leaves the viewport;
- the provenance block's *placement* was the only thing wrong with it; its
  contents were correct and are unchanged.

## Not a design fix

The deploy workflow publishes a single origin (`--origin GRA`), so the published
artefact has one station page, no Change chevron in the heading and only Privacy
in the footer. That is a coverage fact about the release command and not a defect
in the page; it is measured here so that the next reader of this document does
not file it as one.
