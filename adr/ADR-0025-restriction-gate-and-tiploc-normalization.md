# ADR-0025: A reviewed fare selector, and a TIPLOC that is one key

**Status:** Accepted
**Date:** 24 September 2026

## Context

The DTD feeds now download and parse, but two things stood between a parsed feed
and a public price. The fares parser accepted every class-2 return ticket it
found, including off-peak and promotional products whose validity varies by
date, train, TOC, and route. It ignored the `.RST` restriction file entirely, so
there was no way to tell a genuinely unrestricted Anytime fare from one carrying
a restriction code. And the timetable audit reported 1,211 unresolved TIPLOCs
without saying whether they were missing records, padded duplicates, or the
operational locations a public timetable is full of.

## Finding 1: the `.RST` file is the only honest source for "is this fare unrestricted"

The real `.RST` file holds 468,516 records across 12 types: 1,682 `RH` headers,
6,728 `HD` date bands, 66,852 `TR` time rules, 32,016 `TD` date/day rules,
8,454 `TT` TOC rules, 327,668 `RR` railcard rows, and the `SD`/`SQ`/`SR`/`CA`/
`EC`/`RD` records. The field widths match the published RSPS5045 layout and the
open-source `pashri/atoc` reader to the character.

The real feed settles the fare question concretely. The exact standard-class
`ANYTIME DAY R` ticket codes are `8AE`, `AAB`, `E2R`, `HX9`, `SDR`, and `XAR`.
Their fares are `8AE` 1,264 (all blank), `HX9` 2 (blank), `SDR` 275,317 (275,315
blank, 2 with `Y2`), and `XAR` 6 (blank). Off-peak `CDR` is not safe: it carries
scores of restriction codes (`B1`, `B3`, `C4`, `UO`, `ND`, `US`, and more).

**Decision.** A new `publishable_destinations_within` selector keeps only those
six ticket codes, requires the real ticket type to be standard class, return,
train-unrestricted, and named exactly `ANYTIME DAY R`, and drops any fare whose
restriction code is not blank. It requires the `.RST` file to have loaded with
zero rejected records; without that file it raises rather than running. The broad
`destinations_within` stays for analysis, but the page-side query is the
selector.

## Finding 2: railcard rules need exact fare context, and only total bans remove a discount

The `RR` records are keyed by railcard code and carry ticket, route, location,
restriction, and total-ban fields. Two Together (`2TR`) has 1,144 rows: route
bans, ADT location bans, an `R9` row that applies generally, and a single `SDR`
route-00524/Wimbledon ban. The first implementation refused every discounted
price because it treated both a total ban and a restriction code as a ban.

The real Granham-to-Nottingham fare disproved that interpretation. Its only
matching current rule is `RR 0001`, any ticket/route/location, `R9`, with
`TOTAL_BAN=N`. RSPS5045 uses that row to attach the Two Together travel
condition; it does not prohibit the card.

**Decision.** Evaluate every current `RR` row against the fare's ticket, route,
and endpoint locations. A matching `TOTAL_BAN=Y` removes the price. A matching
restriction code is retained and explained as a condition on the discounted
fare. This restores valid prices such as GRA-NOT while preserving the exact rule
in the per-fare Card details drawer.

## Finding 3: padded TIPLOCs split one location into two keys

A CIF location field is eight characters wide, but only the first seven are the
TIPLOC; the eighth can be a path or platform flag. The old parser read the
stripped whole field and then sliced it, so a raw value like `ABHLJN 2` became
`"ABHLJN "` while the station names file held `ABHLJN`. The audit counted the
second key as unresolved.

The station names header was also being read as a station: its category field is
the letter `S`, not one of the numeric categories, so it produced a bogus
`PEC=05` TIPLOC and the invalid CRS `2/0`.

**Decision.** TIPLOCs are canonicalised with `strip().upper()`; a calling point's
value is taken from the first seven characters of the raw field and then stripped,
and the raw padding is kept under `tiploc_variants` for the audit. An MSN record
whose category is not a digit is skipped, which removes the header and the bogus
station. A CIF `TD` delete removes the CIF insert, not the station names entry,
because the station names file wins whatever the load order (ADR-0006). CIF
inserts with a blank CRS are kept, so the audit can say "known location, no CRS"
rather than "no record".

## Consequences

- The real audit now reports 4,139 used TIPLOCs, 1,146 unresolved (1,070 known
  locations with a blank CRS, 76 with no record at all), and 1,294 TIPLOCs
  normalised from a padded raw value. The old "1,211 unresolved" conflated three
  different things.
- The station count fell from 3,302 to 3,301 because the MSN header is no longer
  a station. The fares count is unchanged.
- `SDR`'s 2 restricted fares are dropped by the selector; the other 275,315 are
  publishable on ticket-and-restriction-code grounds alone. That is not a claim
  that every one of those is valid on every train: it is a claim that the feed
  marks them unrestricted, which is the strongest claim this parser can support.
- `build_demo_page.py` now calls `publishable_destinations_within` for its single
  price and refuses to run without a clean `.RST` file. The page therefore shows
  only reviewed Anytime Day Returns. The cheap off-peak `CDR` that the demo used
  to lead with is gone by design, and the page's footer says which fare it shows.
- The page now emits a Two Together price when no matching `RR` total ban
  applies. Any matching restriction code, including Two Together's general R9
  condition, is shown in the fare's rule drawer rather than being misreported as
  unavailability.
- A restriction condition still has to be honoured when buying (for R9, that
  includes its day/time rules). The page identifies the condition; it does not
  turn a conditional railcard fare into an unconditional one.

## The `EIS` question (26 September 2026)

The 25 September audit found King's Cross excluded from every publishable set
and asked whether `EIS` at 5p is really the ITX placeholder family, or a
placeholder record standing in for a genuine non-placeholder operator's offer
at the busiest origin in the country. If the second, the honest answer would
have been to admit the fare and list King's Cross with it.

Measured on the real feed: the origin's 9,212 rejected rows are all
`ticket_is_not_a_reviewed_anytime_day_return`; of its 213 raw tickets, 128 are
`SOR`, 42 `EIS`, 27 `SVR`. `EIS` sits in `PLACEHOLDER_TICKET_CODES` with the
rest of the family at the 5p minimum, restriction `GA` and never blank, so it
fails this ADR's selector on ticket name, class, restriction and placeholder
grounds at once. **The verdict is no change**: `EIS` stays excluded.

The premise of the question dissolved with it. King's Cross was never empty
because of `EIS` — the chooser counted destinations with the anytime-return
selector alone while the page publishes three modes. `priced_destinations_within`
(ADR-0019, 26 September) counts all three, and King's Cross publishes 171
returns and 305 singles and is listed in the chooser with them. The audit's
other option — list King's Cross with a note that the feed has no fares — is
now unnecessary, and admitting a placeholder to get there would have replaced
a real page with a fake one.

## Which set the page opens in (27 September 2026)

ADR-0019 added two more ticket modes to the page, and the default one was the
**broad** standard-return set from `page_destinations_within` — restricted
off-peak and advance fares included — while the reviewed selector this ADR
defines sat behind a third radio. That quietly reversed the decision above. The
27 September audit caught it as C07: `PRODUCT.md` promises reviewed Anytime Day
Returns, the page's own footer said the same, and the list a reader landed on
was a different set from the one the promise describes.

**The page now opens in the reviewed set.** The radio carrying
`publishable_destinations_within`'s output is the checked one, so the default
list is the one this ADR reviewed and the one the product brief names. The mode
values did not change — `anytime` still reads `anytimeDestinations` — so a
shared link written before this decision still resolves to the set it meant.

**The broad set is kept, renamed, and qualified rather than deleted.** Three
reasons:

1. A restricted off-peak return is a real price a reader can buy on a real
   date. Removing it would remove true information to fix a labelling problem.
2. It is often the cheapest thing on the page, and this product is built around
   the cheapest thing. A budget tool that hid off-peak fares because they are
   conditional would be answering a different question than the one asked.
3. `priced_destinations_within` counts a station priced in *any* mode, so the
   chooser already depends on the broad set existing. Deleting it would change
   which stations have pages at all.

What changed is the naming and the qualification. The mode is "Any return",
not "Return", and a line above the table states what the open set contains:
that the broad set includes restricted off-peak and advance fares, that a
restricted fare is not valid on every train or at every time, and that the
Conditions column carries the feed's own text. A restricted row's Fare cell
points at that column rather than at a seller. The note sits above the table
rather than inside the methodology accordion, because the moment a reader
misreads the caveat is the moment they compare two prices, not the moment they
go looking for methodology.

**What this does not settle.** The feed's `desc_out` and `desc_rtn` — the
outward and return validity text — still never reach the page, so where the
feed cannot explain a condition the page says so plainly and sends the reader
to the seller. That is C08, and it is open. This ADR fixes which set a reader
is shown and what they are told about it; it does not make the page able to
decode a rule it has not been given.

## Amendment, 30 September 2026: the minimum fare has a window, and the cell shows both numbers

Two claims this ADR made about the Two Together price were not quite true, and
one document had stopped being true with them. All three are corrected here
rather than left for the next reader to find.

**The `.RCM` record's own window, which was being read past.** Every record in
the minimum-fare catalogue carries a start date and an end date, and the loader
kept one price per `(railcard, ticket)` key, so the *last* window in the file won
whatever day the reader asked about. The 24 September 2026 download holds 639
keys and 3,355 records, and 613 of those keys carry more than one window, so this
is the normal case rather than an edge. A floor the catalogue had retired kept
raising discounted fares as if it were current, which is a price invented out of
a record that no longer applied.

`MinimumFare` now carries its window, `covers()` is inclusive at both ends, a
blank start or end is an open end, a re-issued window replaces the record it
re-issues rather than stacking a second price on it, and
`minimum_fare(railcard, ticket, day)` only lets a record that covers the query
day raise a fare. Where a feed ever lists two windows that both cover the day,
the later start wins, so the record nearest the query is the one applied rather
than whichever the file happened to write last. The query day is the day the
page is built for, and it reaches the query through `destinations_within`,
`railcard_price_for` and the row's own Card details, so a lapsed floor now leaves
the card's own one-third-off price in place instead of replacing it.

**The cell, so a discounted number never stands alone.** With the card ticked, a
row's price is built in `priceCell`, which also prints the standard fare the
discount came from ("£18.40 standard"). With the box clear there is one price
and no second number, because there is one price. The browser suite ticks the
card, reads both numbers off the live rows, compares them and clears it again, so
a cell that lost its second number or kept it when it had none would fail rather
than ship.

**What was stale.** The product brief, the launch checklist, the glossary and
the licensing note all said the railcard records were "parsed but not evaluated".
The code evaluates them: a matching `TOTAL_BAN` removes the discount, a matching
restriction code supplies the travel condition, and the `.RCM` floor applies
when its own window covers the day. Those four documents now say that instead,
and none of them promises anything the parser does not do.
