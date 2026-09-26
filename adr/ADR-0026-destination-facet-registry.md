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

0. The primary class is the ONS size band itself, named for what it is:
   `city` (major, large), `town` (medium), `small_town` (small), `village`
   (minor), and   `other` only where the workbook does not name the station's
   settlement. The reader no longer sees that value as a **No settlement band**
   chip — it read as unfinished work, and the filter could only ever return an
   unsourced remainder. The value stays in the payload for auditing, and a
   reviewed list covers the places the page prices. The
   first cut collapsed the two smallest bands into one "town", which filed
   5,586 settlements — every village, Ancaster and Bottesford among them — as
   "other" and made that bucket meaningless. It also matters which direction
   the error goes: `other` is the answer the page gave when it did not know,
   and it was also the answer for every village.
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
   than inventing a station. A curated list may be checked against its own
   source on every build — the heritage list is keyed by UNESCO site id and a
   delisted site stops contributing — and any curated name that no longer
   matches a station is reported.
   A reviewed facet may also declare name markers, for the categories the feed's
   own names identify without a published list: a coach, tram, metro, stadium
   or parkway station is a node in a network, and a code written per stop would
   be stale the week after it was written. Substring matching is what makes
   "BPOOL NTHBUSTRAM" findable, and it is also what catches Bushey, BUSBY,
   CAMBUSLANG and Shepherd's Bush, so a reviewed facet may exclude the
   settlements its markers catch wrongly.
4. Station names are matched to a source's settlements as whole names, and only
   ever after a trailing bracketed county is dropped ("Ascot (Berks)" is Ascot).
   Prefix matching would be more generous and is wrong: Bathgate is not Bath,
   Bradford-on-Avon is not Bradford, and Chester Road is in Sheffield. Where the
   feed writes a qualifier onto a station name, a curated list names the station
   the way the feed does rather than loosening the match for everything.
5. Facets are merged across every file that names a station — the checked-in
   reference data, a cache beside the feed, an XML lookup — rather than
   replaced. Replacement made the answer depend on the order the directory was
   listed in and let a stale cache delete a facet.
6. A cache written under an older schema is recognised and its primary classes
   dropped, because a cache that predates the band split would otherwise keep
   calling every village "other" for as long as anyone kept the file. Its
   facets are kept, because those are still true.
7. A page offers only the types its own destinations carry. A chip that can only
   ever return nothing reads as a broken control.
8. `tools/regenerate_destination_facets.py` rebuilds the checked-in reference
   data from the named sources, and can carry a facet forward
   (`--keep-unavailable`) when a source is temporarily unreachable, printing
   what it could not read instead of writing a file that quietly lost it.

## Consequences

Adding a sourced type is one registry entry, one reader, and a regeneration
run. The four shipped facets carry their coverage honestly: `seaside` is
England and Wales, `university` and `heritage` are the whole UK, and `island`
is a reviewed list covering the stations this feed carries — a floor, not a
ceiling, because a new feed revision can add island stations without adding
them to the list.

The registry makes the honest answer easy to see: a reviewer can read one list
and learn which classifications are sourced, which are reviewed, and which
countries each one covers. That is the point of writing it down, because the
alternative is a filter whose labels imply a provenance the data does not have.

What is left is stated rather than papered over. The ONS workbook covers
England and Wales only, and it names settlements, not the stations inside them.
On the current Grantham page, 19 of 47 destinations have no settlement band:
15 are real small settlements or halts for which the built-up-area workbook has
no row, and four are airport or underground sites that are not settlements.
`MAN` and `ECR` were found to be genuine omissions in the reviewed major-city
fallback and are now classified as cities. The remaining names cannot safely be
filled by prefix matching: a station qualifier often denotes a junction, halt or
airport label rather than a separately populated settlement. Closing the
remaining gap needs a per-station mapping — either a reviewed alias list, or a
settlement-level source for Scotland and Northern Ireland, which the Rural Urban
Classification would provide if it were published at built-up-area level. It
is not, and it is not what this decision claims.

The registry cannot classify what the feed does not locate, and that is a
hard ceiling. On the 24 September 2026 download, flows reference 5,551
distinct NLCs, 2,027 of which have no location record, and 1,902 of those
are ever used as a destination. The selector counts every row it drops for
want of a name as it goes. Summed over the origins the coverage report
checks, it drops 41,034 rows for having no location record and 39,982 for
having no station code — 81,016 rows in all, 1,001 of them on ECW's page
alone. No reviewed list closes this gap, because a flow runs to an NLC the
feed never locates. `python destination_coverage.py --feed feeds/fares`
prints the count beside the unsourced stations, beginning "A further
81,016 destination rows cannot be named at all". The CI gate's
`--unsourced-ceiling` holds the classifiable half to its measured floor.
The unnameable half is a fact about the feed, not a defect in the
registry.
