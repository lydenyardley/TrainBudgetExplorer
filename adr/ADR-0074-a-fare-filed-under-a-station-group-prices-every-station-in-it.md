# ADR-0074: A fare filed under a station group prices every station in it

**Status:** Accepted
**Date:** 22 October 2026
**Relates to:** ADR-0005 (a licensed feed is never checked in), ADR-0026 (the
settlement class and the unsourced count), ADR-0061 (a two-part fare is one row),
O21 (settled by ADR-0075) and O22 in `docs/settled-work.md`

## Context

RSPS5045 4.19.2 gives every location record a FARE_GROUP (field 14). A flow whose
origin or destination is a group code is a fare from or to each station that names
that group, which is how IDMS 8.2.3 describes them too. The build read a flow's
codes as stations only, so a fare filed under a group priced nothing.

On the 24 September 2026 download, 42 group codes have member stations with a CRS,
and 16,795 flow records run from or to one of them (10,277 group to station, 6,280
station to group, 238 group to group). FARNBOROUGH STNS (0260) holds 459 of them,
and Farnborough Main priced one destination, London Waterloo, at 35.70. Twelve
stations appear in no flow under their own code, so nothing priced them at all:
Glasgow Queen Street, Glasgow Central low level, Helensburgh Central and Upper,
Catford Bridge, Dorchester West, Upper Tyndrum, the three Heathrow terminals and
the two Belfast stations.

## Decision

`FaresDb.fare_nlcs(crs)` is the station's own codes plus each own location's fare
group, and `FaresDb.stations_for_fare_nlc(nlc)` is the station a code names or the
members of the group it names. Every place that asked which flows belong to a
station asks those two methods: the page query's origin and destination sides,
the interchange list, the focused loader and the per-origin index writer. One
flow priced for several members goes through the same selector, railcard, budget
and cheapest-per-station rule as a station's own flow, so every exclusion a page
applies (party limits, the no-discount flags, 25Q, the T2x placeholders, the
corporate, staff, duty and penalty tickets, the sentinel prices) applies to it.

RSPS5045 names no precedence between a station's own fare and its group's, so the
cheapest valid fare wins. A tie keeps the station's own fare, because own codes are
read first.

Two kinds of group are not read through:

- **A group that is itself a station.** HEATHROW BUS (5564) carries the CRS LHR,
  so a fare to it is a fare to that stop, not to every terminal that names it.
- **London Terminals (1072).** IDMS 8.2.4 makes its validity depend on the route
  travelled, which the page cannot show, so its fares stay unpriced as before.
  `UNEXPANDED_FARE_GROUPS` holds the exception, and the coverage audit counts the
  flows it leaves (`unexpandedGroupFareFlows`).

A fare cache written before this change is not reused: its key carries the
fingerprint of the build's own source files, which this change alters. The
pickle's shape is unchanged, so `FARE_INDEX_CACHE_VERSION` stays.

## Consequences

Measured on lean extracts of the 24 September 2026 download, a few origins at a
time, old code against new on the same bytes, return / single / anytime counts:

| Origin | Before | After |
|---|---|---|
| FNB Farnborough Main | 1 / 0 / 0 | 80 / 79 / 77 |
| FNN Farnborough North | 3 / 3 / 0 | 82 / 82 / 77 |
| BHM Birmingham New Street | 121 / 121 / 60 | 258 / 259 / 192 |
| MAN Manchester Piccadilly | 264 / 266 / 44 | 481 / 481 / 230 |
| LDS Leeds | 141 / 143 / 128 | 150 / 155 / 134 |
| CDF Cardiff Central | 143 / 135 / 113 | 146 / 138 / 113 |
| GRA Grantham | 50 / 50 / 42 | 59 / 59 / 46 |

Of the twelve stations no flow named, seven now price a page from the group's
fares (Glasgow Queen Street and Central low level 311 returns each, Helensburgh
Central and Upper 238, Catford Bridge 149, Upper Tyndrum 59, Dorchester West 28);
the two Belfast stations still price none, because no group fare to them is one the
page publishes. The 40 groups read through cover 91 member stations.

No destination was lost and no price rose. Where a price fell it is a group fare
the page's selector already accepts for a station's own flow, such as Birmingham
to Coventry at 3.50 on West Midlands' evening return (EF) rather than 7.30. The
four rows in `tests/known_fares.toml` price the same.

Across the whole 24 September 2026 download, reading through station groups
raises the number of priced destinations from 2,732 to 2,749 (+17). Five of the
seventeen already carried a settlement class (`BDQ` Bradford Forster Square,
`GBL` Gainsborough Lea Road, and the three Heathrow terminals `HAF`, `HWV`,
`HXX`); the other twelve did not (the seven stations above with no flow of their
own -- `CFB` Catford Bridge, `DCW` Dorchester West, `GCL` Glasgow Central low
level, `GLQ` Glasgow Queen Street, `HLC` Helensburgh Central, `HLU` Helensburgh
Upper and `UTY` Upper Tyndrum -- plus five stations whose own flows carry no
publishable adult fare: `GNB` Gainsborough Central, `LVL` Liverpool Lime Street
low level, `TNN` Thorne North, `TYL` Tyndrum Lower and `WGW` Wigan Wallgate).
Those twelve are classified in `REVIEWED_SETTLEMENT_FALLBACKS` under the
existing settlement rules (closing O22): five cities (`CFB`, `GCL`, `GLQ`,
`LVL`, `WGW`), two towns (`DCW`, `GNB`), three small towns (`HLC`, `HLU`, `TNN`)
and two villages (`TYL`, `UTY`). That keeps the net change to the
unsourced-destination count at zero (1,528 before and after on the local 24
September 2026 download; 1,542 against the 1,544 ceiling on the live feed).

Not done here:

- **Railcard rows keyed on a member's own code.** A railcard restriction row names
  a flow by CRS or NLC; a group flow passes the group code and the member's CRS,
  so a row filed against a member's own NLC alone is not matched. None was seen.
- **Station clusters.** Handled separately in ADR-0075 (closing O21).

`tests/test_fare_groups.py` holds the rule on a synthetic feed: a group-only fare
prices both members, a station's own cheaper fare wins, the destination side and a
reversible flow both work, the page's exclusions hold, London Terminals is not
read through, and a focused load and an index-restored database price the same.
