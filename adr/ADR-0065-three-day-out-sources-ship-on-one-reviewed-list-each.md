# ADR-0065: Three day-out sources ship on one reviewed list each

**Status:** Accepted
**Date:** 7 October 2026
**Relates to:** ADR-0062 (the backlog this closes), ADR-0063 (the hybrid
closest-station prune it links through), ADR-0026 (the facet registry),
ADR-0064 (a chip implies a named proof)

## Context

ADR-0062 put three day-out sources on the backlog in a fixed order: RSPB
reserves, then National Trust visitor properties, then National Park and
National Landscape gateways. Each was waiting on a reviewed list and on station
linking, and ADR-0063 shipped the linking. What remained was a shape question:
the registry, the row payload and the station row's proof lines already carry
three named proof tables (heritage, nature, coastal), so three more sources
could either reuse that one shape or invent a fourth mechanism for a polygon
dump.

## Decision

1. **One facet per source, in ADR-0062's order.** `rspb`, `national_trust` and
   `national_park` are three `DESTINATION_FACET_SOURCES` entries, each with
   `reader="reviewed_station_codes"` and a `source` string that says
   "reviewed", as ADR-0026 requires. Nothing else in the registry moves.
2. **One reviewed list per facet, as `ReviewedAttraction` records.** A record
   carries the day-out's name, its page URL, the curated candidate station
   names as the feed writes them, and one or more WGS84 component points. A
   corridor or a multi-entrance landscape carries a component point per
   gateway rather than one centroid, which is the shape ADR-0062 asked for.
3. **Station linking is the hybrid prune, reused unchanged.**
   `_pruned_attraction_crs` keeps a curated candidate unless a coordinate file
   puts it beyond `HERITAGE_PRUNE_MAX_KM` (15 km), keeps the nearest station
   per component point plus a soft twin inside `HERITAGE_PRUNE_TWIN_M`
   (2 km), unions the component points, and fails open when no coordinate file
   is present. The prune judges the curated name; it never replaces it.
4. **Each facet gets its own proof subline on the row**, written through the
   existing `appendSiteProof` path with class `site-proof`, and the row payload
   carries `rspbSites`, `nationalTrustSites` and `nationalParkSites`. The chip
   implies a named proof, which is ADR-0064's rule applied to a fourth, fifth
   and sixth chip.
5. **The lists are deliberately short and named.** 9 RSPB reserves, 9 National
   Trust visitor properties, 19 National Park and National Landscape gateways,
   which is 37 day-outs on 37 distinct stations on the 24 September 2026
   download. These are places a person would name as a day out, not
   memberships, and not every holding of either organisation.
6. **No cache schema bump.** `LOCATION_CACHE_SCHEMA` stays at 6. The schema
   exists to stop a cache serving a *wrong* class or *wrong* chip that nothing
   later removes; a cache written before these facets existed is merely
   incomplete, and `_apply_reviewed_facets` re-applies every reviewed list
   additively after the cache is read, so the three new chips appear on a cache
   written by the previous release. Measured on the 24 September 2026 download
   with the previous release's schema-6 cache in place: 9 RSPB, 9 National
   Trust and 19 National Park stations tagged, each with its row proof
   resolving to the attraction's name and URL. A test
   (`test_a_cache_written_before_the_day_out_sources_still_earns_them`) holds
   the order this depends on, so moving the reviewed pass before the cache load
   fails rather than silently costing three chips.
7. **ADR-0062's non-goals stand.** No VisitBritain dump, no full NHLE Grade II
   sweep, no raw OSM tourism tags, and no polygon-wide landscape tagging. The
   later candidates in that ADR (HES / Cadw properties, Wikidata as a proposer
   into reviewed tables) are still later.

## Consequences

A reader on a station page now sees *RSPB reserves:*, *National Trust:* and
*National parks and landscapes:* sublimes where the reviewed lists reach that
station, from the same mechanism as the three older proofs. Adding a reserve,
a property or a gateway is one record in one tuple, and the prune either keeps
or drops it against `stations.xml`; no second place has to be remembered.

The order the three shipped in is ADR-0062's order, and it is the order they
appear in the registry. The chips themselves follow the registry, so the three
new ones sit after `transport` in the filter rather than interleaved with the
older character chips; the ADR-0062 ordering was about which source earns the
work first, not about where a chip sorts.

The prune reaches four facets now rather than one. Heritage has its own points
table (`HERITAGE_SITE_POINTS`, keyed by UNESCO site id) and its own entry point;
the three new facets share `_pruned_attraction_crs`, because they are the same
kind of thing as each other, a named place with coordinates, and not the same
kind of thing as a UNESCO property whose id is checked against a live list. Two
entry points over one geometry helper is the shape that keeps the id check out
of the day-out path. The fail-open path matters more now that it carries four
facets: a build with no `stations.xml` beside the feed keeps every curated
candidate as written, which is intentional and is covered by a test, but it also
means a fixture build cannot prove a prune that the real feed will apply.

`reference-data/destination-facets.json` is read by a build as one more facet
source, additively, so a checked-in copy from before these facets is not a
correctness problem; it is regenerated from live sources, and its next run
picks the three new facets up from the registry.
