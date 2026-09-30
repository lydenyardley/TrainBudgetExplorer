# ADR-0046: A row list ships as a table of cells and a pool of repeated values

**Status:** Accepted
**Date:** 30 September 2026
**Relates to:** ADR-0033 (what a route may fetch; the amendment of the same day),
ADR-0032 (measurement needs a written plan), ADR-0010 (one self-contained file)
Settles recommendation 1b and 1c of the promise-gap audit of 29 September 2026,
and records the byte budget they are spent against. The audit itself is filed in
the repository's history; the measurements below are the durable part of it.

## Context

The site is projected at 2,712 station pages, and every page is one
self-contained file with no external asset (ADR-0010, ADR-0033). At the rate the
pages were being written, that is a network the host cannot take: the projection
was around 1.4 GB, against a target of **800 MB**, and the promise that made it
a problem was the project's own ("nothing fetched at runtime").

The bytes were not all the same kind of byte. A page is one request for its own
answer — the rows, the fares, the provenance — and that is the part the
one-file promise is really about. Alongside it sat two kinds of waste that cost
the reader without buying anything:

- **The key names.** Every row was a JSON object, so every row repeated the same
  twenty-odd field names. On the real Grantham page that was 190 rows and 200 KB
  of payload, most of it spelling out which field each number was.
- **The values that repeat.** One ticket link on all 190 rows, one railcard record
  per rule rather than per row, the arrays of destination types. The pool is what
  the same measurement found *after* the encoding: the payload was 149 KB and
  half of it was sentences the page had already written once.

## Decision

**1. Each row list ships as its own column list and a table of cells, and the page
hydrates it as it loads. Each list keeps its own columns.**

- The lists carry different fields, and one shared column set would pad the
  picker's three fields out to a destination row's twenty: a loss disguised as a
  saving.
- Hydration happens once, in the page's own script, so no other line of it
  changed and a row is a row everywhere below.

**2. Values that repeat inside the row lists are sent once in a page-level pool,
and a cell that uses one carries a negative index.**

- A pool reference is a negative index, so it cannot be confused with a real
  cell: `-1` is the pool's first entry and `null` stays `null`.
- **The length floor is what stops a pool costing more than it saves.** Only
  objects, arrays and strings of twelve bytes or more (`POOL_MIN_BYTES`) are
  counted, because for anything shorter a reference is no smaller than the value,
  and booleans and numbers are never pooled for the same reason.
- A value earns a place by appearing more than once and being long enough. The
  picker's rows are three unique fields each, which is why they gain nothing from
  the pool and why moving them to one file was worth more (ADR-0033).

**3. The target is 800 MB, measured by `tools/page_bytes.py`, against the whole
network of 2,712 origins. The host does not change and the network is not
thinned.**

## Measured, on the real Grantham page, three builds of the same feed

| | before | 1b, the encoding | 1c, the pool |
|---|---|---|---|
| page | 336 KB | 286 KB | 209 KB |
| payload | 200 KB | 149 KB | 72 KB |
| rows | 190 | 190 | 190 |

The encoding is 15% off the page and 25.5% off the payload, not the 35% the key
count predicted: a table has to carry a cell where the old object simply left the
key out, so the sparse destination rows give about 15 KB of their 66 KB of key
names back. The picker rows are dense and keep all of it — 63.5 bytes a row as
objects, 43.5 as a table — which is why moving the picker's list to one file was
the larger win (ADR-0033: 295 MB of the projected network, 113,983 B a page
against 168,467 B once).

The pool is the larger half of the saving, and it is the half that only exists
because what repeats on a real page is not only the key names: it is one ticket
link on all 190 rows and one railcard record per rule. The page is 38% smaller
and the payload 64% smaller than the morning's.

## Consequences

- **A page is still one request for its own answer.** Nothing about this decision
  spends the one-file promise; it spends less of it.
- **`tools/page_bytes.py` is the instrument, and it is written down** (ADR-0032):
  it splits a page into stylesheet, script and inline payload, reports the bytes
  every measured page repeats word for word, and totals a built folder against
  the 800 MB target. `python tools/page_bytes.py --site _site` is the command
  that re-checks every number in this ADR.
- **The payload is now the smallest part of a page and the shared blocks are the
  largest.** The real Grantham page today is 219 KB, of which 73 KB is the
  payload; 119.3 KB is byte-identical on every page (the shared stylesheet, the
  station page's own stylesheet and script, the theme block and the picker's
  handling), which over 2,712 pages is about 309 MB. That is the next lever, and
  ADR-0033's amendment is where it would be decided: it must move as a hashed
  asset under the same boundary, and only if a re-measured build is still over the
  target.
- **The wire form is an implementation detail of the payload, not of the page.**
  A row is still a row to every line below the hydrator, which is why the change
  did not touch the browser suite's assertions about rows — it re-reads the same
  `DATA` the page does.

## Alternatives rejected

- **A compact key dictionary per page** (Vowpal Wabbit's dictionary idiom), where
  the page sends a key list and short numeric keys per row. It saves more than a
  column list on sparse rows, and it costs a page-specific indirection: a key
  cannot be a column, so the hydrator has to map keys to columns anyway, and the
  per-row cells stop being readable in the file. The column list keeps the wire
  form inspectable, which is what makes a payload diff legible in review.
- **gzip the payload.** The site is served by GitHub Pages, which compresses
  already; writing a compressed blob into a file the build must also be able to
  read and diff would trade reviewability for bytes nobody pays for.
- **One row per destination with a price per ticket type**, rather than three
  lists. It is the shape rec 6's opening list is composed *from*, and it was
  rejected as a payload: the same destination appears in two or three lists and
  the row's own facts — journey, conditions, heritage, railcard record — would
  be repeated for each fare, which is the exact waste the pool removes.
- **Thin the network to fit** (drop origins, or publish prices only for some
  stations). It would meet the target by publishing less, which is the opposite
  of the product: the site's value is that any station in it has a page.
