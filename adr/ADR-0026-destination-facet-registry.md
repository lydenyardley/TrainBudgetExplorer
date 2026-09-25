# ADR-0026: One registry decides the destination types, and each names its source

**Status:** Accepted
**Date:** 25 September 2026

## Context

The page started with a "Destination type" filter that offered cities, towns
and other. Coastal and seaside destinations were then asked for. The obvious
implementation — a checkbox per type, a lookup table per type, a payload field
per type — had already produced two hard-coded HTML checkboxes, a special case
in the fares loader, and a second list in the reference data, and the three had
to be edited together to stay correct.

Two questions came with the request for more types. Where does a settlement type
come from, and what happens to a type the data cannot supply? Answering the
first honestly mattered: ONS Census 2021 supplies settlement size bands and
coastal built-up areas, and nothing else this page wants. TfL is not an answer
at all — its data covers Greater London, so it can describe London stations and
no other destination in the network. HESA and the Office for Students both gate
their provider files behind a login; the one university list readable from a
script is UK Learning Providers, keyed by the official UKPRN. No UK open dataset
names island *settlements*: Ordnance Survey Open Names is gated, and the Scottish
Government's islands layer carries polygons with blank names.

## Decision

1. A station has exactly one primary settlement class, from ONS built-up-area
   size bands, and any number of independent facets. A station can be a city and
   an island at once, and neither value replaces the other.
2. Every facet is one entry in `DESTINATION_FACET_SOURCES`: its label, the
   dataset, the URL, the coverage, and the reader that produces settlement
   names. The filter chips, the page payload, the generated cache's provenance
   and the checked-in reference data are all derived from that list.
3. A facet whose source is not a published settlement list declares itself as
   reviewed in its own `source` text, and its station codes are intersected with
   the stations the feed actually contains, so a stale code is dropped rather
   than inventing a station.
4. Facets are merged across every file that names a station — the checked-in
   reference data, a cache beside the feed, an XML lookup — rather than
   replaced. Replacement made the answer depend on the order the directory was
   listed in and let a stale cache delete a facet.
5. A page offers only the types its own destinations carry. A chip that can only
   ever return nothing reads as a broken control.
6. `tools/regenerate_destination_facets.py` rebuilds the checked-in reference
   data from the named sources, and can carry a facet forward
   (`--keep-unavailable`) when a source is temporarily unreachable, printing
   what it could not read instead of writing a file that quietly lost it.

## Consequences

Adding a sourced type is one registry entry, one reader, and a regeneration
run. The three shipped facets carry their coverage honestly: `seaside` is
England and Wales, `university` is the whole UK, and `island` is a reviewed
list covering the stations this feed carries — a floor, not a ceiling, because a
new feed revision can add island stations without adding them to the list.

The registry makes the honest answer easy to see: a reviewer can read one list
and learn which classifications are sourced, which are reviewed, and which
countries each one covers. That is the point of writing it down, because the
alternative is a filter whose labels imply a provenance the data does not have.
