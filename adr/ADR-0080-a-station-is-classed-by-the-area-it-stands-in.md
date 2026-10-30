# ADR-0080: A station is classed by the built-up area it stands in

**Status:** Accepted
**Date:** 30 October 2026
**Relates to:** ADR-0029 (reviewed fallbacks must be fallbacks), ADR-0001 (data sources)

## Context

A station's settlement class came from matching its name against the ONS
Census 2021 built-up-area workbook. The match fails for any station named for a
district, a street or a landmark rather than for its settlement. A Grantham
build on 30 October 2026 left 454 priced destinations with no class from any
source. Placing each of them in the ONS Built Up Areas (December 2022)
boundaries showed why:

- 273 stand inside a built-up area the workbook bands, under another name
  (Alexandra Palace is in Haringey, Ardwick in Manchester).
- 102 stand inside an area the workbook does not band: 77 in Scotland, which
  the workbook does not cover, and 25 mostly in London borough areas.
- 79 stand outside every area. 14 of those are within 100 m of an edge and 16
  more within 500 m.

## Decision

After the name match and the reviewed lists, a station that is still
unclassified takes the band of the area it stands in. The band is the
workbook's own, joined on the area code `BUA22CD`, so the boundaries say where
a station is and the workbook still says how big the place is.

- **Last, and only for gaps.** The pass runs after everything else and only for
  stations with no class or `other`. A reviewed entry still wins (ADR-0029). The
  redundant-reviewed-entry gate still asks only whether the *name* matched,
  because placed stations go in their own set, `ons_position_classified_crs`.
- **Polygons, not radii.** The areas run from a few hundred metres to tens of
  kilometres across, so no single radius around a centroid fits them all. The
  generalised (25 m grid) boundaries are read as plain rings and tested with an
  even-odd ray test. `trainbudget/fares/ons_boundaries.py` uses the standard
  library only.
- **100 m edge tolerance.** Track and yard land is often left out of the
  boundary, so a station a few metres outside it is still in the place. Beyond
  100 m the station is more often a halt in the fields, and it stays
  unclassified.
- **Fetched, not committed.** The boundaries are read from the ONS feature
  service on each classifying build, England and Wales only, just as the
  workbook is downloaded. The location cache (schema 7) records the source and
  its licence. If the service fails, the build keeps the name classes and
  records a classification failure, as it would for the workbook.

## Licence

The boundaries are published under the Open Government Licence v3.0. The
build's `ogl` notice and the cache's source record carry: "Source: Office for
National Statistics licensed under the Open Government Licence v3.0. Contains
OS data © Crown copyright and database right 2022."

## Consequences

On the same Grantham build, the unclassified count fell from 454 to 171:

- 77 are Scottish. The workbook bands no Scottish area; a National Records of
  Scotland settlements source would be the next step.
- 25 stand in areas the workbook lists without a band. Most are London borough
  areas such as Haringey, Enfield, Islington, Croydon and Newham. The rest are
  small places such as Capenhurst, Sellafield and Whatstandwell.
- 68 are outside every area by more than 100 m.
- 1 (Bache, inside Chester) was placed by the diagnosis and not by the build.
  It is unexplained.

The page's `ogl` notice now names the ONS and OS statement. The text quoted in
`licences/release-clearance.md` is the older wording and needs a review there.
