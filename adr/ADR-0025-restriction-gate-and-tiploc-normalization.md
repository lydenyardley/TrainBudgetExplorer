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
