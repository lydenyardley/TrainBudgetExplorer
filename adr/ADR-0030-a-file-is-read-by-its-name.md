# ADR-0030: A file is read by its name, and a build names every source it used

**Status:** Accepted
**Date:** 26 September 2026
**Relates to:** ADR-0026 (the facet registry and the cache's provenance),
ADR-0029 (the reviewed lists, and the discard this replaces)

## Context

Two defects were found beside each other in the classification pass, and both
are about what a feed-side file is allowed to say.

**One label, many sources.** `FaresDb.location_type_source` was a single slot
every source wrote to, so the answer was whichever file was loaded last. On the
real download that is wrong in the direction that matters: the cache beside the
feed carries classes from the ONS workbook *and* from the reviewed London,
Scottish, Welsh and Northern Irish lists, and the page published all of them
under the workbook's name alone. The reviewed fallbacks are a source, and the
page's provenance line is the only place a reader can learn where a
destination's type came from.

The same slot was why two clearing hacks existed. A cache written under an
older schema has its primary classes dropped, and its `source` label described
those classes, so the label was cleared twice — once in the loader and once in
the pass, on a sticky `_location_classes_discarded` flag, because the loader
reads its label back out of the same discarded data. Clearing a whole label to
remove one file's claim also removed every other file's: ADR-0029 records the
test that had to be written to stop a discard from erasing a later source's
label. A design that needs that test is describing the defect.

**A name that merely looked right was trusted.** The candidate files beside a
feed were matched by `*location*types*.json` and `*destination*facets*.json`,
so any file whose name spelled those words in order was loaded as a
classification source: a backup, a staging copy, a scratch probe. It happened —
a probe left beside a feed by earlier work this session broke an unrelated test
by classifying stations the feed's own cache had left alone — and the failure is
silent, because a plausible-looking file produces plausible-looking classes.

## Decision

**A source is recorded when it supplies classes, and never overwritten.** Every
source is appended to `FaresDb.location_type_sources` in load order and
`location_type_source` is a property that joins them. The reviewed fallback
label is presented last, because it is the floor under the sourced classes:
"the workbook, plus the reviewed fallbacks for the areas it does not cover" is
how the coverage reads. A file whose classes are dropped contributes no label,
which is what the two clearing hacks were trying to express.

The rules that *guessed* at a source are gone with the slot. A records-bearing
file names what it claims in its own `source`; a cache this build wrote names
every source in `provenance`, a list written beside the joined `source` string
so a reader from before the list existed still sees every source, and so a label
that contains the joiner cannot be split back wrongly. Two rules that stamped
the ONS label on a build because facets were present, and one that relabelled
after a facet was applied, claimed classes the workbook had never supplied.

The early return keeps its meaning with the list: a build whose only classes are
the reviewed fallbacks has to read the workbook, so the test is
`_has_sourced_classes()` — anything but the fallback label — rather than a
comparison against one string.

**A classification file is read when its name is a name this project writes.**
`LOCATION_TYPES_FILE` and `DESTINATION_FACETS_FILE` are the single declaration
of both names, next to `LOCATION_CACHE_SCHEMA`; the writer, the four globs and
the lookup-root test all use them. Both the bare name beside a feed
(`feeds/location-types.json`) and the same name behind a feed's own
(`fares.location-types.json`, which the synthetic fixture and the write-back
use) are accepted, and nothing else is.

## Consequences

The real page's provenance line now reads:

> destination types: Office for National Statistics, Census 2021 built-up-area
> size bands and coastal classification + ONS 2021 geography coverage with
> reviewed London, Scottish, Welsh, Northern Ireland, major-city, and
> reach-ranked settlement fallbacks

Two sentences where there was one, and the second is the one that was missing:
of the 1,210 stations the 24 September 2026 download classifies, the London,
Scottish and Northern Irish ones are the reviewed lists' work.

The cache is not rewritten for this. Its classes are unchanged, the labels are
computed at read time from what the file claims, and a `provenance` list appears
when a build next writes a cache for its own reasons — a schema bump or a
one-off re-derivation. Bumping `LOCATION_CACHE_SCHEMA` to make the key appear
would throw away 3,436 correct classes and a workbook download to add a field
the reader already derives.

A file that names no source records none, even when its classes are kept. Such a
build writes `"source": ""` rather than a citation nothing supports, and the
next build re-derives from the real sources: slower, and honest.

## Verified

`_cache/probe_provenance.py` runs the classification pass against the real
download's `RJFAF896.LOC` in the real `feeds/` layout, with the cache write
intercepted. On the 24 September 2026 download: 3,436 stations with a CRS, 1,210
classified (208 cities, 239 towns, 289 small towns, 474 villages, 0 `other`),
434 stations with facets, 0 reviewed codes absent, 0 redundant, 0 classification
failures, no cache write, and `feeds/location-types.json` byte-identical
afterwards. The production layout was run too, `feeds/fares/dtd-fares.zip` with
the same stations: same classes, same label, no write, no failure. The
corrected classes hold, which is what the probes read back: Penrhwceiber,
Harringay, Ladybank and Balloch Central are villages; Truro, Cardenden and
Barming are towns; York, Hull and Wakefield Westgate are cities.

The suite is 407 tests in `tests/` and 83 in `tools/`, both green, with the
coverage gate at 81.2% (floor 79). The new tests pin the parts that were guesses
before: a name that only mentions locations and types is not a source beside a
feed, and the same bytes are read under a name this project writes; a build names both the workbook and the reviewed
lists, and writes both to the cache in load order; a discarded cache's own claim
is not in the label, and the workbook is still read after the discard; and a
fare-index pickle written before the labels were accumulated still reports its
one label instead of dying on an attribute it predates.
