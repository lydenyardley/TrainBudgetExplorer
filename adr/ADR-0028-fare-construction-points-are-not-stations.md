# ADR-0028: A fare-construction point is not a station

**Status:** Accepted
**Date:** 26 September 2026
**Relates to:** ADR-0019 (one page per station, decision 3), ADR-0026 (the
facet registry and the ceiling it cannot lift), audit findings A6 and A7 of
25 September 2026

## Context

The DTD feed prices fares through places that are not places. `BOUNDARY ZONE 4`
is where a fare crosses from an inner to an outer London zone; `BRIGHTON
UNIZONE` and `WORTHING UNIZONE` are the same idea for a single fare area;
`METRO T&W ZONE A` is the Tyne and Wear equivalent. `KINGS LYNN COACH`,
`DEREHAM (COACH)`, `SWAFFHAM (COACH)` and `WISBECH (COACH)` are coach stops
standing in for the town they serve. No train calls at any of them.

They are priced like stations, so the page treated them like stations. The
chooser offered them as origins a reader could depart from, the `--all-origins`
build wrote pages for them, and they led the coverage report's
most-reached-destinations table — a table a reader would reasonably read as
"where do people actually go".

Audit finding A6 removed them from the chooser, the write set and the coverage
report. That left one place where a fare-construction point was still published
as a destination a reader could buy a ticket to: the destination rows on the
station pages themselves. The question this ADR answers is whether that is
deliberate.

## The question

A zone boundary is where the feed records a fare change. A page that offers
"Cambridge to BOUNDARY ZONE 4, £14.20" is offering a journey to a line on a
map. It is the same class of defect as offering a journey to a station that
has no service, which ADR-0019 already decided against: absent, not offered
and then refused. The only argument for leaving them is that a real fare
exists, and a real fare to a place that cannot be reached is not a price a
reader can act on.

## Decision

**A fare-construction point is not a destination, and the rule is applied in
the shared query loop rather than in each caller.**

`FaresDb._destinations_within` drops a destination whose CRS is in
`FARE_CONSTRUCTION_CRS` and tallies the row as
`destination_is_a_fare_construction_point`. That is the one place every caller
passes through — `destinations_within`, the three page modes,
`priced_destinations_within`, the chooser's count, the coverage report — so
there is no second place to remember. The row is counted rather than dropped
silently, which puts it in the same "can never be a destination" total as the
flows with no location record, and into the empty state's reason list: an
origin priced only into a zone now says so instead of claiming an ITX
placeholder problem it does not have.

**The list is reviewed and keyed by CRS, not matched on the name.** The
substring test the audit's fix shipped with was measured against the 24
September 2026 download: it matched exactly the twelve codes on the list and
nothing else, with no false positives. It was replaced anyway. A name test is a
claim about every station that does not exist yet, and it fails in both
directions — a real station called Coach House or Hazleton would be silently
dropped from the chooser, and the day the feed renames a zone the test stops
catching it. The CRS is the feed's own identity for a station and changes with
a rename, which turns the failure into a dead code the build names.

The name markers are kept as `looks_like_fare_construction`, and
`tools/propose_fare_construction_stations.py` prints every station they catch,
with the name that caught it and whether the code is already reviewed. It
writes nothing. Evidence and judgement stay apart, and the evidence is exact
on today's feed, so the split has cost nothing so far.

## The gate that came with it

Making the list reviewed is only half of it. Audit finding A7 asked for the
dead codes to be named, and on the real feed the note named **twelve** —
which is twelve bugs the previous commit had been printing without fixing:

- **Seven London codes had lost their leading `Z`.** The feed writes the
  Underground, DLR and Overground codes as `Z` plus the first two letters
  (`ZBF` Blackfriars, `ZCD` Colindale, `ZGR` Gloucester Road, `ZLP` Langdon
  Park, `ZPD` Prince Regent, `ZPI` Pinner, `ZRY` Royal Oak). The list had them
  as `BKF`, `CDL`, `GLR`, `DLP`, `IPD`, `PIM`, `RGY`, so seven London stations
  were classified by nothing at all. Corrected.
- **`DEQ` named no station and no city it could have been.** Dundee's code is
  `DEE`, one letter away, and Dundee is conspicuously absent from a list of
  Scottish cities. Corrected to `DEE`.
- **`NIR` was Newry** in a group holding Lisburn and Portadown. Newry's code
  is `NWY`. Corrected.
- **`NPT`, `BFL` and `BQU` named no station and no settlement could be
  recovered for them.** Left as a guess, a future feed revision introducing a
  station with that code would classify it from a decision nobody made. They
  were removed.

The codes now have their own channel on `ParseReport` rather than riding in
`skipped_files`, because nothing was left unread: this is a reviewed list
naming a station the feed does not carry, and reporting it as an unopened
source was both untrue and a way to lose it among the
archive-inside-an-archive notes. `feed_audit.py` prints it under its own
heading, and `build_demo_page.py --require-live-reviewed-codes` refuses before
writing anything. The deploy workflow passes the flag.

The gate is **not** on by default, for the same reason
`--require-classification` is not: a fuzzed, damaged or synthetic feed is
*meant* to be missing most of the network, and a default refusal would make
those tools untestable. Both flags print what they found either way.

## What this would change

- `--all-origins` will not write pages for a station a reader asked for by
  hand with `--origin QAH`. That is deliberate: an explicit request still
  builds, and the note is the operator's.
- The coverage report's "can never be a destination at all" total now includes
  these rows, so that number is not comparable with one measured before this
  ADR.
- A feed that adds a zone boundary without a code on the list will publish it
  as a destination again, until someone runs the proposer. The gate only
  catches the *reverse* direction. This is the known cost of a reviewed list
  and the reason the proposer exists.

## Verified

The 24 September 2026 download: 3,436 stations with a CRS, twelve matching the
name markers, all twelve on the reviewed list, zero reviewed fallback codes
absent. `build_demo_page.py --feed feeds/fares --origin KGX
--require-live-reviewed-codes` publishes King's Cross with 171 returns, 304
priced rows, 475 rows across the three modes, no zone or coach row among them
and none among the 3,423 picker entries, and no dead-code refusal.
