# ADR-0064: Seaside chip implies a named coastal proof

**Status:** Accepted
**Date:** 7 October 2026
**Relates to:** ADR-0026 (facet registry), ADR-0063 (chip->proof follow-up)

## Context

Lyden's product rule: every facet chip on a station row leads to a named proof
subline. Coastal & seaside had the opposite shape after ONS tagging: many
stations earned the chip with no `coastalSites` row. Classic day-outs
(Blackpool, Brighton, Southend, Weston-super-Mare) also missed the ONS
settlement name-match entirely, so they could not take a proof even when one
existed.

## Decision

1. **ONS stays primary** for `seaside`. Do not fake ONS rows.
2. **`SEASIDE_SUPPLEMENT_CRS`** is a reviewed CRS list on the seaside
   `DestinationFacet` (`reviewed_station_codes`). `is_reviewed` means
   `reader == "reviewed_station_codes"` only, so a dataset facet can carry a
   supplement without skipping its workbook reader. Supplements apply in
   `_apply_reviewed_facets` after cache or ONS load.
3. **`COASTAL_SITE_PROOFS`** covers every CRS that can carry the seaside chip
   (ONS set ∪ supplement). Names are honest day-outs (beach, harbour, castle,
   estuary walk), not invented beaches. `seaside_crs_missing_coastal_proofs`
   and a unit test against `feeds/location-types.json` enforce the invariant.
4. Nature / heritage / other facets keep their own proof tables; extending the
   same chip->proof rule there is separate work.

## Consequences

Grantham (and any origin) shows a named *Coastal & seaside:* subline whenever
the filter chip appears. Blackpool / Brighton / Southend / Weston earn the
chip via the supplement. Adding an ONS coastal match without a proof row fails
the suite until `COASTAL_SITE_PROOFS` grows.
