# ADR-0062: Three day-out sources wait on the backlog

**Status:** Accepted; all three sources shipped, see ADR-0065
**Date:** 7 October 2026
**Relates to:** ADR-0026 (destination facet registry), the heritage / nature /
coastal proof sublines already on the station row.

## Context

The station page already attaches named proof under a destination when a
reviewed source says so. UNESCO World Heritage properties drive the heritage
subline. Wildlife Trust and WWT reserves drive the nature subline. A curated
coastal floor names a few beaches for the seaside chip. ONS coastal communities
still own the `seaside` facet itself.

Lyden asked for more credible day-outs on more stations, and named three
sources to integrate later. He also accepted a hybrid closest-station prune so
a property only labels the nearest station or two, once that prune ships. This
ADR records both decisions. It does not add readers, registry entries, or proof
tables.

## Decision

1. **These three sources are on the integration backlog**, in this order:
   1. **RSPB reserves.** Named day-outs with spatial data. They close the
      Rainham-class gap the nature comments already call out (a reserve the
      Wildlife Trust list does not cover). Suggested shape: grow the `nature`
      proof path, or a sibling reviewed CRS + URL table that the nature chip
      and subline already understand. Station link: reserve coordinates to
      nearest station under the hybrid prune below.
   2. **National Trust visitor properties.** High day-out value. Bookham
      already shows the intended CRS + URL proof shape. Suggested shape: the
      same reviewed table pattern as heritage and nature proofs, not a raw dump
      of every NT holding. Station link: property coordinates under the hybrid
      prune.
   3. **National Park and National Landscape (AONB) gateways.** Chip plus a
      curated set of gateway stations. Do not tag every station inside the
      polygon. Suggested shape: a new facet (or an extension of an existing
      outdoor chip) whose reviewed list names gateways only.

2. **Live sources stay as they are until each backlog item ships its own
   reviewed list.** Current live provenance remains UNESCO WH (`heritage`),
   Wildlife Trusts / WWT (`nature`), and ONS coastal communities (`seaside`),
   with coastal named beaches as a curated proof floor beside the chip.

3. **Station link method for every new proof table** (and for tightening
   heritage and nature once built) is the hybrid closest-station prune already
   accepted as follow-up policy:
   - Keep curated candidate stations.
   - At build time, drop any candidate beyond `max_km` from the attraction
     point, using lat/lon already on disk in Knowledgebase `stations.xml`.
   - Keep the nearest station, or two when the second sits within a soft twin
     distance (about 1.5–2.5 km).
   - Corridor sites (Derwent Valley Mills, Jurassic Coast, Hadrian's Wall) need
     component points or an explicit gateway flag, not one centroid.
   - Litmus drops for the prune: Buxton labelled for City of Bath, and Chester
     labelled for Hadrian's Wall.

4. **Non-goals for this backlog.** No VisitBritain dump. No full NHLE Grade II
   sweep. No raw OSM tourism tags until the ordered list above earns its keep.

5. **Later candidates**, after the three above: HES / Cadw properties in care
   (Scotland and Wales day-outs on OGL terms), and Wikidata only as a proposer
   into reviewed tables (same ethos as `tools/propose_nature_stations.py`).
   Neither is scheduled ahead of RSPB, National Trust, or park / landscape
   gateways.

6. **This commit documents only.** No facet reader, no `DESTINATION_FACET_SOURCES`
   entry, and no proof table lands with this ADR.

## Consequences

A reviewer looking for "what day-out sources do we still want" has one place to
read. Adding a source still follows ADR-0026: one registry entry, one reader or
reviewed table, and a regeneration run that can prove provenance.

The hybrid prune is the default when any of these sources (or a heritage /
nature cleanup) implements station linking. Until that code exists, curated
lists stay as written and may still carry distant stations. The litmus cases
above are the first checks that prune must pass.

Ordering protects the day-tripper first: named reserves and visitor properties
before polygon-wide landscape chips. Skipping that order for a noisier dump
would make the filter less trustworthy, which is the failure ADR-0026 exists to
prevent.

## Amendment, 7 October 2026

All three sources shipped, in the order above, on the hybrid prune this ADR
asked for: `rspb`, `national_trust` and `national_park` are registry facets
with one reviewed list each (9, 9 and 19 day-outs). The decision is recorded in
`adr/ADR-0065-three-day-out-sources-ship-on-one-reviewed-list-each.md`. The
non-goals in point 4 and the later candidates in point 5 are unchanged.
