# ADR-0011: Fares the query refuses to guess, and one station with several codes

**Status:** Accepted
**Date:** 21 September 2026

## Context

The Grantham count is the go/no-go input, and nobody can check it by hand. That
makes silent loss the most expensive kind of bug in this repository: a count that
is too low looks like a real answer. Two things were dropped without a word.

## Finding 1: one station code, several location codes

The fares feed keys a flow by *location code* (NLC). A station code (CRS) can
hold several location codes, and real feeds do this for most towns. The query
matched flows with `flow.origin_nlc != origin.nlc`, where `origin.nlc` was
whichever record the file happened to load last for that station code.

Reproduced in a five-line feed: two location codes for `GRN`, one flow leaving
from the first code, and `destinations_within("GRN", ...)` returned **nothing**.
Not fewer destinations. None. Whether the sweep answered at all would have been
decided by the order of records in a file nobody reads.

**Decision.** Index every location code per station code (`nlcs_by_crs`) and
match a flow when its origin is any of them. A withdrawal of one location code
removes only that code: the station keeps the others, which a test now pins.

## Finding 2: what else was dropped in silence

`destinations_within` skipped four kinds of record by falling through a
condition:

| dropped | why it matters |
|---|---|
| a destination with no location record | the fare is real and the destination is unnameable |
| a destination with a location record but no station code | this is how a real feed carries a group or a non-station destination |
| a flow with no fare | the pair is priced nowhere, so it can never appear |
| a fare whose flow is missing | the record is in the file and belongs to nothing |
| a flow back to another code for the origin | normal in a feed, never a trip |

None of these is an error. All of them change the count. **Decision:** a budget
query may take a `tally` dict and record every reason a flow or fare did not
become a destination. `stats()` reports the two that are properties of the feed
rather than of a query: locations with no station code, extra location codes for
a station, and fares with no flow record.

The tally is optional, and two tests assert that passing one changes no result.
It exists so the count can be questioned, not so it can be tuned.

## What is deliberately still not handled

**A destination that is a group is not resolved to the stations inside it.** The
layout that defines groups is not knowable from inside this repository, and the
Marketplace is behind a sign-in. Guessing a fixed-width layout is exactly the
mechanism that produces a confident wrong answer, so groups are counted and
sampled instead: the audit prints how many destination codes have no station code
and a sample of them. Resolving them is a decision to make with the real file
open, not before it.

**A group destination is not counted as a destination either.** The tool reports
that it saw one, not where it goes. A user reading "12 destinations" is reading
about the 12 it can name.

## Consequences

- The go/no-go count is now accompanied by a list of what it left out. It is not
  a better number, it is a number that can be audited.
- `adr/ADR-0005-data-access-and-blocker.md`'s instructions for the first real run
  should be read alongside this: run the audit, then question the count, then
  trust it.
- The station-code index also fixes a second-order problem: a name lookup for a
  station now resolves by first record rather than last, so the name shown for a
  town no longer depends on file order.
- The invented feed grew a `--real-shapes` flag carrying all of the above. It is
  off by default, so tests about budget arithmetic still read a feed with nothing
  puzzling in it, and the tests about real shapes opt in.
