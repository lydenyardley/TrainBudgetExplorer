# ADR-0075: A fare filed under a station cluster prices every station in it

**Status:** Accepted
**Date:** 23 October 2026
**Relates to:** ADR-0005 (a licensed feed is never checked in), ADR-0026 (the
settlement class and the unsourced count), ADR-0074 (a fare filed under a station
group prices every station in it), open work O21 in `docs/settled-work.md`

## Context

RSPS5045 section 4.2 defines the station-cluster file (`.FSC`). Each 25-byte
record (`UPDATE_MARKER`, `CLUSTER_ID`, `CLUSTER_NLC`, `END_DATE`, `START_DATE`)
places a station NLC or a station-group NLC inside a cluster for a date window,
keyed on `(CLUSTER_ID, CLUSTER_NLC, END_DATE)`. A flow in `.FFL` whose origin or
destination is a `CLUSTER_ID` is a fare from or to every member of that cluster
on a day inside the membership's validity window.

On the 24 September 2026 download (`RJFAF470`), `.FSC` carries 2,472 cluster
codes with 43,714 memberships (43,697 active on 24 September 2026 and 17
renewals in cluster `LS57` starting 1 November 2026), and 369,889 of the
1,517,455 active priced flows in `.FFL` (24.4%) have a cluster code at origin,
destination or both. ADR-0074 read through station groups (`.LOC` field 14) and
left `.FSC` clusters as open work O21, so those 369,889 flows still priced
nothing.

## Decision

1. **Read `.FSC` into `FaresDb.station_clusters` and expand active memberships in
   `fare_nlcs(crs, *, day=None)` and `stations_for_fare_nlc(nlc, *, day=None)`.**
   A cluster member may be a station's own NLC or a station-group NLC (`0260`
   `FARNBOROUGH STNS`), so cluster lookup composes with `_direct_fare_nlcs` and
   `_direct_stations_for_fare_nlc`. Only memberships whose `StationClusterMember.covers(day)`
   is true are expanded. The `.FSC` loader handles `A`/`U`/`R` by upserting on
   `(member_nlc, end_date)` and `D` by deleting matching records.
2. **Keep the same exclusions and precedence order.** `UNEXPANDED_FARE_GROUPS`
   (`1072` London Terminals) and group codes that are themselves a named station
   (`5564` Heathrow Bus `LHR`) are not expanded even when a cluster lists them.
   Candidate origin codes are read in order: own NLCs first, then station-group
   NLCs, then cluster NLCs, each sorted by code. The cheapest valid fare wins,
   and ties keep the narrower code.
3. **Keep `interchange_crs` on direct and group flows.** A regional cluster can
   group dozens of stations; pulling every member of an origin's clusters into
   a single-origin timetable load (`focus_origin`) would treat every station in
   the cluster as an interchange candidate. `interchange_crs` therefore stays on
   `_direct_fare_nlcs` and `_direct_stations_for_fare_nlc`, while `focus_origin`
   and `write_fare_indexes` preload the origin's cluster flows.
4. **Reject Caledonian Sleeper staff concession codes `1ZB` and `1ZE` in
   `CONDITIONAL_TICKET_CODES`.** Cluster flows `0453592`, `0453683`, `0461152`
   and `0463659` (`Q990`/`Q991` to `Q992`) carry £0.10 Caledonian Sleeper staff
   concessions (`1ZB` `CS F&F CC SO` and `1ZE` `CS LEISURE CC S`). Their sibling
   `1ZC` (`COMP`) and `1ZD` (`DUTY`) codes are already caught by
   `NOT_FOR_PUBLIC_SALE_MARKERS` and `2ZB`-`2ZE` by `min_passengers=2`; adding
   `1ZB` and `1ZE` to `CONDITIONAL_TICKET_CODES` keeps `tools/check_fare_rate.py`
   at zero offenders.
5. **Memoize per-day destination resolution and per-flow fare bucket evaluation
   in `_destinations_within`.** Because an origin belongs to roughly ten clusters
   and cluster flows reach up to 2,700 stations, `FaresDb` caches resolved
   `(real_locations, pseudo_count, real_crs_frozenset)` per `destination_nlc` and
   memoizes selector/budget evaluations per `flow_id`, pruning repeat flows to
   the same `destination_nlc` once a cheaper price is already held while keeping
   exact `Reachable` and `tally` parity.
6. **Classify the 109 newly priced destinations that lacked a settlement class.**
   Reading through station clusters raises priced destinations across the
   24 September 2026 download from 2,749 to 2,864 (+115). Six already carried a
   settlement class (`GGT` city, `LBN` town, `LDR` city, `NWY` town, `PTN` town,
   `WNO` small_town). The other 109 are classified in `REVIEWED_SETTLEMENT_FALLBACKS`
   from the ONS 2021 Built-Up Areas workbook, Greater London / Tyne & Wear
   settlements, NISRA Census 2021 settlement populations for Northern Ireland
   (clusters `Q791`-`Q793`), CSO Census 2022 built-up area and settlement
   populations for SailRail Ireland stations (clusters `Q768`-`Q770`,
   `Q783`-`Q786`) and Hoek van Holland (`HVH` small_town): 17 cities, 23 towns,
   34 small towns and 35 villages, with no chip-only attraction facets added.

## Consequences

Measured on the 24 September 2026 download (`day = date(2026, 9, 24)`), return /
single / anytime / priced destination counts before (ADR-0074) and after:

| Origin | Before (ADR-0074) | After (ADR-0075) | Return price drops |
|---|---|---|---|
| FNB Farnborough Main | 80 / 79 / 77 / 80 | 2,432 / 2,755 / 1,010 / 2,757 | 10 (e.g. LHR 35.30 -> 24.30, BTO/BXW 15.30 -> 13.90) |
| FNN Farnborough North | 82 / 82 / 77 / 82 | 2,435 / 2,755 / 1,010 / 2,756 | 11 |
| BHM Birmingham New Street | 258 / 259 / 192 / 259 | 2,617 / 2,710 / 220 / 2,711 | 12 (e.g. LEO 41.30 -> 28.10, BCK/FLN/HSW 58.60 -> 50.50) |
| MAN Manchester Piccadilly | 481 / 481 / 230 / 483 | 2,621 / 2,720 / 364 / 2,722 | 7 (e.g. OXN 55.80 -> 26.20, RET 42.50 -> 37.80) |
| LDS Leeds | 150 / 155 / 134 / 155 | 1,664 / 2,729 / 249 / 2,729 | 11 (e.g. BUH/FRY 28.10 -> 22.90, GBD 25.70 -> 22.90) |
| CDF Cardiff Central | 146 / 138 / 113 / 146 | 2,637 / 2,728 / 213 / 2,730 | 4 (e.g. HAF/HWV/HXX 145.30 -> 117.90, ALV 84.90 -> 82.70) |
| GRA Grantham | 59 / 59 / 46 / 59 | 1,596 / 2,747 / 88 / 2,747 | 3 (BDM/BSJ 97.00 -> 66.90, ATB 12.20 -> 12.10) |
| GLQ Glasgow Queen Street | 310 / 312 / 232 / 313 | 2,398 / 2,719 / 279 / 2,720 | 36 |
| KGX London King's Cross | 204 / 215 / 0 / 215 | 232 / 275 / 0 / 275 | 6 (GCL/GLC/GLQ 206.00 -> 186.00, FKG/FKK 194.00 -> 186.00) |

Across all 2,590 origins in `UnsourcedReport.from_feed`:

- Priced origins rise from 2,719 to 2,835 (+116) and priced destinations from
  2,749 to 2,864 (+115), with 0 destinations lost and 0 price increases.
- All four hand-checked rows in `tests/known_fares.toml` match unchanged.
- `tools/check_fare_rate.py` reports 0 suspiciously cheap fares across 2,824
  origins.
- `UnsourcedReport.from_feed` completes across all 2,590 origins in 124.7 s, and
  the unsourced destination count stays unchanged at 1,528 on the local
  24 September 2026 download (1,542 against the 1,544 ceiling on the live feed),
  with `reviewed_codes_absent == []` and `reviewed_codes_redundant == []`.

`FareClusterTest` in `tests/test_fare_groups.py` holds the rule on a synthetic
feed: cluster-to-cluster reversible flows, clusters containing a station group,
precedence ties keeping group over cluster, London Terminals left unexpanded
inside a cluster, membership validity windows and delete markers, exclusions and
rejection tallies, focused loads and fare-index round-trips, coverage audit
cluster counts, and settlement classes for newly priced cluster destinations.
