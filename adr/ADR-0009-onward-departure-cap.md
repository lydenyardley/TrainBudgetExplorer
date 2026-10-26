# ADR-0009: The onward departure cap is 200, and it was measured

**Status:** Accepted
**Date:** 21 September 2026
**Supersedes:** the uncited guess of 60 in ADR-0006

## Context

A one-change journey is found by taking every departure from the origin, then
looking for an onward train from each place it reaches. On a dense network that
is a lot of combinations, so ADR-0006 capped the onward search at the 60
earliest departures from each interchange. That number was a guess, written
before any feed existed, and `adr/ADR-0006-timetable-layer.md` said so.

`benchmark.py` now measures a cap against an uncapped search over the same feed:
total time, median, 95th percentile, and how many journeys the cap lost or
lengthened. Two feed shapes matter, and they disagree, which is the whole point.

- **uniform**: random stopping patterns, so most pairs have a direct train.
- **hub_spoke**: the origin is served only by trains to one hub, and every other
  station is served only by trains to that hub. So every journey past the hub
  needs a change. This is where a cap can lose a journey, and the uniform shape
  can never show that. Grantham's real position, on a main line with branch
  destinations hanging off it, is closer to this shape.

Both shapes are invented, uniform in price and speed, and neither predicts a
real network. They bound the work and expose the direction of the error.

## Measurements

`python -m trainbudget.measure.benchmark --shape uniform --stations 300 --schedules 8000 --queries 30 --caps 0,60,200`
on 38 priced target pairs:

| cap | total s | median ms | p95 ms | journeys worse than uncapped |
|---|---|---|---|---|
| uncapped | 37.69 | 1157.5 | 1996.3 | — |
| 60 | 9.38 | 282.9 | 494.8 | 0 |
| 200 | 13.09 | 395.6 | 679.6 | 0 |

`python -m trainbudget.measure.benchmark --shape hub_spoke --stations 300 --schedules 8000 --queries 30 --caps 0,60,200 --transfer-only`
on 30 pairs that need a change:

| cap | total s | median ms | p95 ms | journeys worse than uncapped |
|---|---|---|---|---|
| uncapped | 0.31 | 9.8 | 18.2 | — |
| 60 | 0.01 | 0.3 | 0.6 | **10 of 30** |
| 200 | 0.01 | 0.5 | 0.8 | 0 |

The same run at 200 stations and 3000 schedules, on 40 transfer-only pairs, lost
nothing at 60 and nothing at 200, which shows the loss depends on how many
departures a hub has rather than on the feed being large.

## Decision

`MAX_ONWARD_DEPARTURES` is **200**.

200 is the smallest cap that lost no journey on either shape. It costs about
113 ms of median query time against 60 on the densest feed, and about 0.2 ms on
the transfer-heavy one. The work it saves on the uniform shape buys nothing that
matters, because the query behind the product is per destination and will be
precomputed, not run live on a request.

**60 was wrong in a way that would have hidden itself.** On the shape that
resembles real branch-line travel it silently dropped a third of the journeys
that need a change, and it did so in a fraction of a millisecond each, so a
timing-only measurement would have called 60 a success.

## Alternatives rejected

- **Keep 60 for its speed.** Rejected: the speed is real but worthless here, and
  the loss is concentrated exactly in the journeys a budget trip-finder exists to
  find.
- **Remove the cap entirely.** Rejected for now: 1157 ms median on the dense
  uniform feed is tolerable for a precomputed sweep and unnecessary for any
  single query, and an unbounded search is the thing that becomes a timeout on
  real data. 200 keeps a bound with no measured accuracy cost.
- **Cap by time window instead of departure count.** Untested. It would likely
  behave better, since a branch train four hours after arrival is not a
  connection anyone wants, but it is a change to the search and deserves its own
  measurement rather than a swap on the same day.

## Consequences

- `test_benchmark.py` asserts the shipped value and rebuilds the hub_spoke feed,
  so lowering the cap to buy speed fails a test instead of passing quietly.
- The numbers are synthetic. The first real feed should be measured with
  `--shape uniform` replaced by the real timetable, which `benchmark.py` allows
  by pointing it at a feed folder.
- A cap of 200 departures covers roughly a full service day at a station with
  twenty departures an hour. Real branch departures after an evening arrival
  remain the case to re-measure.
- Two-change journeys are still unsupported, so this cap is the whole story of
  what the one-change search sees.
