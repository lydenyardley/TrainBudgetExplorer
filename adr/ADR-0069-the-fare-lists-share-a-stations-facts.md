# ADR-0069: The fare lists share a station's facts and pack what a row prices

**Status:** Accepted
**Date:** 13 October 2026
**Relates to:** ADR-0047 (shared assets out of the page), ADR-0050 (the release is the whole network), ADR-0061 (two-ticket rows)

## Context

The first whole-network build in shards (run 38353105980) assembled a
**2,444 MB** release against the **800 MB** byte budget. Shard 1's 458 pages
weighed 429 MB, a median page 746 KB. Two causes, measured on those pages:

1. **Two-ticket railcard rules were never shared.** Each pair record named its
   row's tickets, routes and endpoints, so the Crewe page carried 7,306 rule
   records, 7,290 of them pairs, 3.2 MB of 4.8 MB. Fixed in f07a750: the record
   now holds only what the page reads. That alone projects to about 1,060 MB.
2. **The three fare lists repeat each other and pack nothing.** A page ships
   `destinations`, `singleDestinations` and `anytimeDestinations`, and 534 of
   Crewe's 538 single-fare rows are also return rows. Of the Crewe page's
   1.25 MB of rows, a row's `railcards` (an object per card with four named
   fields) was 629 KB and its `tickets` (each naming both stations in full)
   430 KB. The station's own facts -- name, types, named sites -- were the same
   in every list and sent once per list.

## Decision

The wire form of a page's rows (`encode_payload`) gains three things, each
reversed by the page's hydrator before any reader sees a row:

1. **`places`.** A column that every fare list carries with the same value for
   a station -- in practice the name, the destination types and the named
   sites -- is sent once per station in `places` and left out of the rows. Each
   list's table names those columns in `placed`. Only columns that agree for
   every row of every list are placed, and only when there are two or more
   fare lists, so a fare a list prices differently always stays on its row.
2. **Packed railcards.** A row's decisions become an array in the page's card
   order, each `[state, price, minimum, rule]` with the state an index into
   `rowCodec.railcards.states`. A row whose cards arrive in another order, or
   whose decision has other fields, is sent as it was.
3. **Packed tickets.** A ticket becomes an array in `rowCodec.tickets.columns`
   order, without its two station names, which come from one page map
   (`rowCodec.tickets.names`). A ticket with other fields, or a name that
   disagrees with the map, is sent as it was.

The existing value pool then runs over the packed rows, so a packed decision
that repeats is still sent once.

`hydrate` in `page/station/payload.js` rebuilds every row as the object the
build wrote, **the same values in the same key order**, so `fare-panel.js`,
`row-actions.js` and every other reader are unchanged. `tests/page_harness.py`
mirrors it for the Python suite.

## Evidence

- Re-encoding shard 1's 458 real pages (with f07a750 applied) and hydrating
  them back gave byte-identical rows on every page, and 90.8 MB in place of
  429 MB: **about 536 MB** for 2,707 pages, against 800 MB.
- Real-feed pages for Grantham, Crewe and Edinburgh built by the previous and
  the new code, hydrated by each version's own `payload.js`, give identical
  row lists (329/336/136, 544/521/367 and 1,109/1,140/388 rows). Sizes went from
  714 to 389 KB, 1,228 to 626 KB and 1,995 to 1,092 KB.
- The browser suite on the demo and shape builds passes unchanged (259/259,
  73/73, 31/31, 256/256, 219/219). On the real-feed Grantham, Crewe and
  Edinburgh pages the old and new builds fail the same six checks, a fault
  that predates this change; the hydrated rows are identical.

## Consequences

- The page's first script does a little more work per row on load; it is a
  loop over arrays the page already parses.
- A new per-row field travels as before until a codec is written for it; the
  packing never guesses at a shape it was not given.
- The 498 MB figure in the workflow was measured on 1 October, before
  two-ticket rows; the byte budget stays at 800 MB.
