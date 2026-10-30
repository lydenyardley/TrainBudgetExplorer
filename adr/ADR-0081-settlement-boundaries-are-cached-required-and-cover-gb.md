# ADR-0081: Settlement boundaries are cached, required, and cover Great Britain

**Status:** Accepted
**Date:** 30 October 2026
**Relates to:** ADR-0080 (a station is classed by the area it stands in), ADR-0001 (data sources)

## Context

ADR-0080 left four gaps on the Grantham build, 171 unclassified destinations:

- A boundary service that failed was swallowed as a classification failure,
  which the release build does not refuse. A page could lose hundreds of
  classes silently, against the rule that a build stops when a feed is missing.
- Each of the twelve CI shards would have asked the ONS service for every area
  at the same moment.
- 77 Scottish stations: the ONS workbook bands no Scottish area.
- 25 stations in areas the workbook does not band. Most were London boroughs,
  which the workbook leaves out because its tables are "England (excluding
  London)" and Wales.
- Bache: it stands inside Chester, whose area crosses the Welsh border and so
  carries the code `K08000001`. The query asked for `E%` and `W%` codes only.

## Decision

- **Required.** `ons_boundaries.load_boundaries` raises `BoundaryFeedMissing`
  when the boundaries cannot be read after five tries over about a minute
  (timeouts, 5xx and 429 only). It is not an `OSError` or `ValueError`, so no
  tolerant handler catches it, and the loader no longer wraps the pass. The
  workbook download keeps its old tolerant handling; this ADR does not change it.
- **Cached once a run.** The three sets are kept in `feeds/ons-boundaries.json`
  (about 97 MB of polygons, gitignored). In CI the build job restores it with
  `actions/cache`, fetches only on a miss, and saves it. The shard and assemble
  jobs restore the same key with `fail-on-cache-miss`, so only one runner ever
  asks the services. The key hashes `ons_boundaries.py`, so a change to what is
  fetched fetches again.
- **Every ONS code but Scotland's.** The query is `BUA22CD NOT LIKE 'S%'`, so
  the cross-border `K` areas come too. The workbook bands Chester `large`.
- **London by rule.** An `E` area the workbook does not band whose own centre
  (the service's `LAT`/`LONG`) is inside the ONS London region (`E12000007`,
  Regions December 2022) is `major`, a city. No hand list.
- **Scotland by population.** NRS Settlements 2020 (514 settlements of 500
  people or more, with mid-2020 populations) are banded by the thresholds the
  workbook's own bands follow: under 5,000 minor, 20,000 small, 75,000 medium,
  200,000 large, and major above.

## Licence

All three sets are OGL v3.0. The `ogl` notice adds: "Scottish settlements:
Copyright National Records of Scotland; contains Ordnance Survey data © Crown
copyright and database right 2022." The location cache (schema 8) records the
NRS source and statement beside the ONS ones.

## Consequences

On the same Grantham build the unclassified count fell from 171 to 69. Bache,
the London boroughs and 67 of the Scottish stations are placed. What is left:

- Six stations within 100 m of an ONS area the workbook does not list at all:
  Adlington (Cheshire East), Wendens Ambo (Audley End), Capenhurst, Eccles Road,
  Sellafield and Whatstandwell. The workbook omits them, most likely because
  they hold too few residents to publish (Sellafield and Capenhurst are nuclear
  sites). They are candidates for the reviewed list, not for a rule.
- Ten Scottish stations outside every NRS settlement (Blair Atholl, Dalwhinnie,
  Drem, Shawfair, Eskbank and others): halts, or a new town newer than 2020.
- The rest are English and Welsh halts more than 100 m outside every area.
