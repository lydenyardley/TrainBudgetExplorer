# ADR-0061: A journey the feed prices in two parts is one row

**Status:** Accepted
**Date:** 5 October 2026
**Relates to:** ADR-0011 (the fares query refuses to guess), ADR-0019 (one page
per station), ADR-0025 (the restriction gate), ADR-0044 (the cheapest of any
type is the default), ADR-0045 (the row names where a split would split),
ADR-0053 (the row names its fare in the reader's words), ADR-0060 (the day
changes the times and nothing else).

## Context

The list of rows is a fares question, not a timetable question.
`_priced_destinations` asks `FaresDb.priced_destinations_within`, which walks
flows out of the origin's NLC and prices each one. A place the feed does not
publish an origin-destination flow for is therefore absent from the page,
whatever the timetable says about reaching it.

Measured from Grantham against the reference fares feed, reading all 727,315
flow records in one pass:

| | count |
| --- | --- |
| destinations the feed names on an outward flow from Grantham | 58 |
| of those, published as rows on the page | 12 |
| named but not published | 46 |
| of those 46, priceable as two published fares, one change | 37 |

The 46 are not a data gap. For 37 of them the feed publishes a fare for each
leg, through a named station the feed also prices from Grantham:

| Destination | Change at | Leg 1 | Leg 2 | Sum |
| --- | --- | --- | --- | --- |
| Aberdeen | London Kings Cross | `SVS` £34.00 | `L9N` £33.20 | £67.20 |
| Inverness | London Kings Cross | `SVS` £34.00 | `L9N` £36.00 | £70.00 |
| Leeds | Doncaster | `CDS` £33.00 | `NF2` £7.00 | £40.00 |
| Wakefield Westgate | Doncaster | `CDS` £33.00 | `NF2` £4.40 | £37.40 |
| Sheffield | Doncaster | `CDS` £33.00 | `SDS` £5.60 | £38.60 |
| Edinburgh | Doncaster | `CDS` £33.00 | `XS3` £147.50 | £180.50 |

The flow set is a product of the fare routes the industry publishes, not of the
journeys passengers buy. The feed splits Grantham to Aberdeen at King's Cross
because that is where the pricing route boundary falls, and publishes both
halves and not the whole. Nothing in the download is missing. The arithmetic is
missing, and the arithmetic is a product feature rather than a feed feature.

Nine of the 46 have no two-leg route the page would show, and stay off:
Bradford F Square, Darlington, Glasgow Central, Horsforth, Keighley, Liverpool
Airport, Morpeth, Shipley Yorks, Skipton.

## Two measurements that read as answers and were not

Both were found by checking a number that should not have been zero.

**The record type is the second character of a flow record, not the first.**
Column one is the update marker. A probe filtering on the first character read
zero flows out of 727,315, and the first version of the leg analysis reported
that no destination had a two-leg route at all. It had read no records.

**`focus_origin` decides which fares survive the load.** A feed focused on one
origin reports "flow with no fare" for every flow from anywhere else. Asking
that database what King's Cross charges for Edinburgh returned one destination
and an empty second leg, and the second version of the leg analysis reported 0
of 46 priceable. The right answer is 37. The probe now sets
`_focus_origin_nlcs` to the pairs being asked about before the second pass.

## Decision

**The list becomes the reachable set, and a place the feed prices in two parts
is one row.**

A destination with no single-flow fare becomes a row whose price is the sum of
two published fares, naming both ticket codes and the station the reader
changes at. The row already carries a split-ticket note in its panel
(ADR-0045), so the shape of the thing exists; what is new is that the price
column carries a sum rather than a dash.

The price is **not** the sum of the two cheapest fares. It is the sum of the
two fares that the row's own journey uses, read from the same selectors the
single-flow rows use, so the reader is quoted the journey they are shown.

## Invariants

**The two tickets must be the ones this journey uses.** Choosing the cheapest
fare on each leg independently would quote a pair that no single connection can
be made on. The cheapest Grantham to Doncaster fare and the cheapest Doncaster
to Leeds fare may not be boardable on the same train, and a row that names one
journey and prices another is the defect ADR-0045 exists to prevent.

**Both restrictions are named, not one.** Two tickets means two restriction
codes and two sets of travel conditions. The panel carries both, and a row with
no restriction on the second leg says so rather than staying silent.

**The reader may not be able to buy the pair.** Two tickets are two purchases,
from two sale points, on two dates. The row says it is two tickets. A static
page cannot promise the pair is available together, and does not.

**The day control does not change either price.** Same rule as ADR-0060, and it
now covers two numbers per row rather than one.

**The sum is not the price of the journey to the reader's usual destination.**
A reader comparing this row against a single-ticket row is comparing two
purchases with one. The row says which it is.

## What the opening sentence may claim

The page currently opens with "Every place you can reach from the station above,
inside the budget, with the fastest time and the fewest changes." On a dated
build that is an overclaim, because the list is the priced set rather than the
reachable set. The static fallback in the markup already carries the true
sentence, "Every destination this feed prices from the station above, inside the
budget."

The strong sentence becomes true when this ships. Until then it does not, and
the repair is the honest sentence, not a caveat.

## What would change this

Nine of the 46 stay off with no two-leg route the page would show. Whether a
three-part price should be attempted for them is not decided. Measured cost of
the alternative, from the same timetable: a two-change walk takes 236 s per
origin-day against 1.0 s for one change, and reads 8,573,958 onward departures
against 38,628. Two hundred times the time for 135 more stations. The three-part
question is not worth opening until the two-part row is on a page.

The measurement is one origin on one feed. The join is symmetric and the
selectors are the project's own, so the shape transfers; the proportion is a
figure about Grantham and would need a sweep across the network before anyone
claimed a network-wide number.