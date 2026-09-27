# ADR-0031: A parsed-feed cache is keyed by content, not by timestamp

**Status:** Accepted
**Date:** 27 September 2026
**Relates to:** ADR-0024 (what a build costs), audit findings B1 and B4 (the
fare-index and timetable caches)

## Context

A build parses a licensed feed, keeps part of it, and writes a pickle so the
next build does not have to. Both feeds are cached, and for a long time both
caches were named by `feed_fingerprint`: file names, sizes and mtimes. That is
the right identity for "has the operator changed anything?" — a resume signature
and the deploy workflow's "did the feed change?" step both want to be cheap,
and a mtime is enough to notice that.

It is the wrong identity for a cache that holds *parsed data*, and the
difference is not subtle. A copy that preserves timestamps, an archive
extracted with the dates stored in it, or a feed directory restored from
somewhere else all replace a download with different fares and no visible
change to its name, size or mtime. A cache keyed on any of those goes on
serving the previous download's prices, and the page looks entirely normal:
a reader is quoted a fare that is not the one in force, from a build that
reported success. This is the one class of cache failure that nothing notices.

The fares key had a second, worse gap, found by a test failing for a reason
nobody had predicted. A parsed `FaresDb` also carries the *classification* of
every station on the page, and that is read from files beside the feed — the
checked-in reference data, a corrected `fares.location-types.json`, a revised
destination-facet file — and from the code that reads them. Two feeds with
byte-identical fares and different classification files beside them produced
the same cache name, so a build could be served a database whose station types
came from a source that had since been corrected: current prices, stale
classes. Keying on the feed alone left out everything the parse depends on
except the fares.

## Decision

**A cache that holds parsed data is keyed by the content of every input that
produced it.** For the fares feed that is three things, and all three are in
`fares_cache_identity`:

1. **The feed's bytes**, read in 1MB chunks and hashed.
2. **The content of every classification file a parse could read**, taken from
   the same list the loader reads — `atoc_fares.location_lookup_candidates` is
   a function both the loader and the key call, so the two cannot drift apart
   and a key can never describe a different set of inputs than the parse used.
3. **`source_fingerprint()`**, the hash this project already puts on the page
   to say which code built it. A change to how fares are parsed must not be
   served a database parsed the old way, by the same argument as (1).

The timetable cache is keyed the same way, minus (2): a timetable database
carries nothing read from beside the feed, so its key is the feed's content,
the source fingerprint, and the stations the focus was asked for.

**`feed_fingerprint` is unchanged and still used for what it is good at.** A
resume signature and the workflow's change detection want a cheap answer to
"did anything change", and a mtime answers that. Two functions, two jobs.

**The cost is measured, not assumed.** Hashing the 48MB fares feed, the
reference data and the source files takes 0.12s, against the 29s parse it
exists to avoid. A key that cannot be wrong is worth a tenth of a second.

## What this bought, measured on the real DTD download

| build of one station's page | before | after |
|---|---|---|
| fares: parse, then read the shared metadata and the origin's index | 29.2s | **1.7s** |
| timetable: focused parse, then read the pickle | 61.8s | **2.4s** |
| a page with journeys, end to end | dominated by the two above | the two above, plus the journey search |

The page is byte-for-byte the one the parse produced, which is the property
that makes a cache safe: a restored `FaresDb` is the same database the
parallel build's workers already build pages from, and
`test_the_worker_path_and_the_inprocess_path_build_the_same_pages` was already
holding that equivalence to account.

Caches of digests that can never be named again are tidied on the same rule as
the timetable caches, a digest is dropped whole, and the digest a build just
read or wrote is never a candidate however old its timestamp — a hit cannot
evict itself.

## Re-measured, and a correction worth recording

While making the timetable key match, the timetable cache was measured as
apparently worthless: a focused parse reported 2.6s and a restore 2.6s, so it
looked like 90MB of copy for no time saved, and a rule was written to decline
the cache for any focus that did not cut the feed to a fraction of itself.
**Every one of those "parse" timings was a restore.** The cache file already
existed from an earlier run, so `load_feed` returned on its first branch and
never parsed anything; the scratch harness printed the label it had been given
rather than the branch that ran. With the file deleted, the same focused parse
takes **61.8s** and the restore **2.4s**.

The rule was removed. The cache is a 25× win on the timetable and an 89MB file
is a fair price for it.

The record is here because the mistake is the general one: a measurement that
confirms what you already believed is the measurement most likely to be a
harness bug. `load_feed` returning early was invisible from the call site, and
the only reason it was caught is that the number was suspicious enough to
delete the cache and ask again.

## The remaining cost is not the parse

One station's payload with journeys takes **over 9 minutes** on the real feed,
and none of it is loading: ADR-0024 measured the same cost on a synthetic
network, traced it to the inner loop of `_one_change_journey`, and decided
that the fix is an indexed search rewrite in a new ADR rather than a tweak.
The deploy workflow publishes prices-only pages because of it, and that
decision stands. A build with journeys is now minutes rather than hours, and
the minutes are the search.
