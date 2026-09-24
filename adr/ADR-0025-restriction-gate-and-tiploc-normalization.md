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

## Finding 2: railcard rules are parsed, not evaluated, so the discount is refused

The `RR` records are keyed by railcard code and carry ticket, route, location,
restriction, and total-ban fields. Two Together (`2TR`) has 1,144 rows: route
bans, ADT location bans, an `R9` row that applies generally, and a single `SDR`
route-00524/Wimbledon ban. Deciding whether any of these applies to one flow
needs the full route and ticket context, which this static query does not model.

**Decision.** The parser reads and counts `RR` rows and keeps a few samples, but
the publishable selector refuses a railcard outright. A cardholder can always
decline the discount, so the standard price is still honest; publishing a
discounted price whose conditions are unknown is not. The broad query and
`require_restrictions=False` still compute railcard prices for analysis.

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
- The party price is two Anytime Day Returns, not a railcard discount, and the
  page says why. This is a deliberate product regression until the `RR` rules are
  evaluated: it keeps a reader's quote honest rather than attractive.
- The `RR` rows are the next review: evaluating route and location bans would let
  the selector price a Two Together party honestly.
