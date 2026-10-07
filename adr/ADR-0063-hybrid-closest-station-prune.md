# ADR-0063: Hybrid closest-station prune for attraction labels

**Status:** Accepted
**Date:** 7 October 2026
**Relates to:** ADR-0062 (backlog sources name this prune), ADR-0026 (facet registry)

## Context

World Heritage (and later nature / day-out) labels were attached by curated
station name alone. That let Buxton carry City of Bath and Chester (Cheshire)
carry Hadrian's Wall: true name matches, useless for a day-tripper catching a
train to the attraction.

Lyden accepted a hybrid prune: keep curated candidates, drop anyone beyond a
sanity distance, keep the nearest station or a soft twin, and give corridor
sites component points so a valley is not collapsed by one centroid.

## Decision

1. **Parallel geometry table.** `HERITAGE_SITE_POINTS` is keyed by UNESCO site
   id beside `HERITAGE_PROPERTIES`. Point sites have one WGS84 coordinate.
   Corridor / multi-gateway sites (Derwent Valley Mills, Hadrian's Wall,
   Jurassic Coast, Edwardian castles, slate landscape, mining landscape, Lake
   District) list component points. No GIS stack.

2. **Coordinates from Knowledgebase `stations.xml`.** `load_station_coordinates`
   reads CRS -> (lat, lon) already on disk under `feeds/knowledgebase/`. Missing
   file or missing CRS fails open for that candidate (Underground and some
   heritage-railway names stay curated until coordinates exist).

3. **Defaults.** `max_km = 15`, `twin_m = 2000`. Per attraction point: drop
   beyond `max_km`, keep nearest, keep second when its distance to the point is
   within `twin_m` metres of the nearest's distance. Union across component
   points.

4. **Where it runs.** The heritage facet reader and `heritage_sites()` both use
   `_pruned_heritage_crs`, so chips and named sublines agree. Multi-CRS nature
   proofs (Martin Mere) reuse `select_nearest_stations` with a CRS centroid.
   Coastal proofs stay 1:1 CRS keys and need no prune.

5. **Chester curated name.** The Hadrian's Wall list named `Chester`; the feed
   match is Cheshire Chester, ~190 km from the wall. Evidence supports a
   Chester-le-Street mixup, so the curated token is `Chester-le-Street` and a
   component point sits there.

6. **Cache.** `LOCATION_CACHE_SCHEMA` moves to 6. Older caches still donate
   non-heritage facets and drop their primary classes as before, but any
   cached `heritage` chip is stripped so the live UNESCO reader retags under
   the prune.

## Consequences

Litmus: Buxton loses City of Bath; Cheshire Chester loses Hadrian's Wall;
Bath Spa, Carlisle / Corbridge / Newcastle (and Chester-le-Street), and the
Derwent valley set remain. Distant false friends stop earning the chip.

Product rule (chip -> named proof subline) for Coastal & seaside is ADR-0064.

