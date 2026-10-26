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
7. A page offers only the types the list on screen carries, narrowed per ticket
   mode. A chip that can only ever return nothing reads as a broken control, and
   on a real feed that is not hypothetical: from King's Cross every heritage
   destination is an outbound single, so the returns page offered a heritage
   chip that could not return a row, and the same is true in the other
   direction on other stations. The build cannot decide this -- it offers the
   union of the three modes, because it does not know which one a reader will
   pick -- so the page narrows the chips again at render time, from the list it
   is about to filter, and unticks a chip that goes away so the filter is never
   matching a selection the reader can no longer see.
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
feed never locates. `python -m trainbudget.fares.destination_coverage --feed feeds/fares`
prints the count beside the unsourced stations. Re-measured on 30 September
2026 against the same download, the same three reasons sum to **84,544** rows:
41,034 with no location record, 39,986 with no station code, and 3,524 to a
fare-construction point with no train behind it. The CI gate's
`--unsourced-ceiling` holds the classifiable half to its measured floor.
(Raised 2026-10-14 from 1,533 to 1,544 with Lyden's approval: the station
count went from 3,437 to 3,453 (3e441bb), adding 11 unsourced priced
destinations (e.g. CPK, WFH, WFJ, BID, PMT). Lower it again as reviewed
classes are added.)
The unnameable half is a fact about the feed, not a defect in the
registry.

## Amendment, 30 September 2026: the district the workbook appends, and a rule measured and dropped

The workbook writes a settlement with its district in brackets where the name
needs one -- "Watford (Watford)", "Neston (Cheshire West and Chester)",
"Blackburn (Blackburn with Darwen)" -- and the station side of the match has
always dropped its own bracketed qualifier ("Ascot (Berks)"). The two sides were
normalised differently, so a station whose settlement the workbook names was
left unclassified for no reason but the bracket. Keying the workbook name
without its district closed it: 43 stations the feed prices gained the
workbook's own class, 42 of them as priced destinations, and the coverage
report's count fell from **1,575 to 1,533** on the 24 September 2026 download
(`python -m trainbudget.fares.destination_coverage --feed feeds/fares`). That measured floor is
what the CI ceiling now holds.

Where one name the workbook holds twice collapses onto the same key with
different bands -- Wick appears three times, in Arun, South Gloucestershire and
the Vale of Glamorgan -- the station keeps the report's attention rather than a
class that may belong to the other settlement. One cost is accepted knowingly:
"Newquay" and "New Quay" normalise to one key, so Newquay (Cornwall) is refused
beside the Ceredigion village of the same name rather than guessed.

A wider version of the same idea was measured and dropped. Dropping a trailing
qualifier from the *station's* name -- Acton Central, Clapham High Street,
Watford Junction -- reached 28 more of the 1,575, but it also matched London
stations to same-named settlements the workbook holds elsewhere: Acton Central
to Acton, Clapham High Street to Clapham (Arun). This ADR's own warning about
prefix matching applies to that rule too, and a wrong class is a claim about a
place, so the rule was not kept. The qualifier families stay with the reviewed
list.

What is left of the 1,533 is not one gap. Measured the same day, the worst
origins are bus links and underground sites whose destinations are outside the
workbook's nations -- PEE Portree Bus and UIG Uig Bus price 44 Highland
stations each, and MYB prices ten Underground and Overground stations -- and the
largest family is Greater London and the conurbations, which the workbook
excludes by design because it cannot separate settlements inside them. Scotland
and Northern Ireland need a settlement source of their own, the Rural Urban
Classification the decision above names, before those classes can be sourced
rather than reviewed. Nothing in this amendment closes that gap; the reviewed
lists and the ceiling are what keep it visible until a source lands.
