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
## Amendment -- 23 October 2026: the pool reaches the places, and a column can carry a dictionary

`.FSC` cluster flows (ADR-0075) price a fare to **2,752 destinations** from
Grantham, so `places` became the largest part of a page -- 806,498 bytes of
1,333,421 -- and the pool above never saw it, because it was built from the row
tables only. The same page then measured what the shape costs:

- **A place's cells join the page pool.** A value that repeats is sent once and
  referred to by a negative index wherever it sits. The same ticket link on all
  2,752 places was 272,448 bytes and is now 8,256.
- **A departure option is an array.** `{depart, arrive, changes}` becomes
  `[341, 1095, 1]`, with the three names once per page in
  `rowCodec.departures`. 189,089 bytes became 56,726.
- **A column of repeating words is a list of indices.** `table.dicts` holds the
  values and each cell is its index, for a column whose values are all strings or
  booleans (an index cannot be told from a real number) and only where the
  indices cost less. The route code, ticket code, restriction code and wording,
  `quality`, `isAdvance`, `offPeak`, `journeyState` and `destinationType` are
  worth 162,000 bytes between them on that page.
- **A party price of two adults is derived.** `partyPence` is twice `adultPence`
  on every row the build writes, so `table.derived` names the column, the row
  keeps its place in the key order, and the hydrator multiplies. A payload whose
  rows disagree is sent as it was.
- **The service week is transposed.** It was a table per day keyed by station, so
  a destination running all eight days sent its code eight times: 105,169 bytes
  became 70,552.
- **A pooled value has to pay for itself.** Sharing a value that repeats n times
  costs one copy plus n references, and a reference into a 754-entry pool is four
  bytes against an empty list's two, so pooling everything repeated made `places`
  larger. The pool now keeps only the entries whose reference is cheaper.

**Measured, same page and same rows:** 1,368,721 bytes -> **690,977 (-49.5%)**,
the payload 1,333,421 -> 655,677, and a small station (Ashwell & Morden)
1,301,965 -> 657,135 with 6,056 rows either side. The old encoder run over the new
page's own decoded payload reproduces the old bytes exactly, and every row reads
back as the object the build wrote, in order. The full profile is in
`docs/build-performance-findings.md` under "Twelve release-shaped pages"; the two
decisions the remaining bytes needed are ADR-0076 and ADR-0077.

**What the amendment does not buy.** The same page gzips from 139,782 to 128,201
bytes, **8.3%**, because the repetition removed was what deflate was already
removing. The wire form is smaller and the release is smaller; a reader's
transfer is not where the gain is.

## Amendment -- 24 October 2026: the station's facts leave the page, and a day can repeat the day before

The byte audit's D1 asked for the same treatment the picker's list already had.
`name` is the station's, and so are `destinationType`, `destinationTypes` and the
six named-site lists: they are the same on every page of the release that lists
the place, and a page that carried them paid for them 2,930 times.

- **The station's own facts travel in the shared station list.**
  `window.TBE_STATION_FACTS` sits beside `window.TBE_STATIONS` in the one
  document every station page already fetches, keyed by CRS and covering every
  station the feed names rather than only the ones with a page: a page's rows can
  name a place whose own page does not exist (a zone boundary, a station whose
  only flows leave it). `page/station/payload.js` joins them to each row by CRS,
  so every panel below reads a row exactly as before. A page whose copy of the
  document did not arrive gives every row no type, and the chips stand down
  instead of offering a filter that can only empty the list.
- **A day that answers what the day before it did travels as `true`.** The week
  was already transposed to one entry per station; a weekday timetable then
  repeated the same [minutes, changes] five days running, and a place with no
  service repeated nothing six times. `true` cannot be an answer, so it needs no
  escape, and the hydrator carries the previous day forward.

**Measured the same day, on the same Grantham page.** The facts out of the page
and into the shared list: 426,972 -> **386,505** bytes, with 3,436 stations'
facts in a 124,286-byte `stations.js` the release serves once. The week's
run-length: 70,552 -> 57,443 bytes, and the page **373,396**. Against the
690,977 this page measured before ADR-0076 or this amendment, that is **46%**.

The single-origin build keeps its facts inline: it writes no shared list, so a
page that dropped them would have no way to read them back.
