# ADR-0045: The row names where a split ticket would split

**Status:** Accepted
**Date:** 30 September 2026
**Relates to:** ADR-0043 (the row keeps the action, its panel holds the rest),
ADR-0040 (the row carries the fare's code), ADR-0018 (the handoff text)
Settles Q2 of the promise-gap audit of 29 September 2026, which is filed in the
repository's history and whose durable findings live in these ADRs, in
PRODUCT.md and in the measured tables beside them.

## Context

"Split ticketing is cheaper" is the reply a fare tool gets in the first thread
it posts in, and it is true often enough to be the answer. The launch checklist
had one line about it — agree with it, and name it as a known limitation — and
the page itself said nothing at all, so the limitation lived in a launch post
rather than on the page a reader was already looking at.

Two facts make it answerable rather than rhetorical:

- The page already carries `changes` and `legs` for every row, and a `Leg` has
  `origin_crs` and `destination_crs`. The station a journey changes at is not a
  new fact; it is one field the build was already holding and folding away.
- The feed prices **flows**, not itineraries. A fare is priced for an origin and
  a destination; nothing in it prices "this itinerary, bought as two tickets".
  Any number the page could print about a split would be a number it invented.

## Decision

**A journey with a change gets one line in the row's own panel, naming the
change station as where a two-ticket split may undercut the through fare, and no
price for either half.**

1. The build writes `changeStations` on the rows that change: one entry per leg
   boundary, so a one-change journey carries its one interchange and a longer one
   carries every change station. The name is the fares feed's own station record,
   with the code as the fallback when the feed has no name for the TIPLOC.
2. The line is built by `splitNote` and appended in `fareDetails`, the panel the
   fare's condition already lives in (ADR-0043). The row gains no control, the
   table gains no column, and the line is read where a reader opens a row to ask
   what the fare allows.
3. **The sentence states a possibility and stops there:** a split through that
   station "can sometimes cost less than this through fare; this page prices the
   through fare only". A direct journey says nothing, because there is no change
   to split at.

## Consequences

- **A known limitation is now visible on the page rather than in a launch post**,
  so the reply the project expects can be met by the reader's current screen.
- **The cost is one payload field on the changed rows only.** It rides along with
  the row encoding (ADR-0046), and on the real Grantham page the 47 returns it
  adds are a few hundred bytes.
- **The panel is the right place, not a new column.** A reader comparing prices
  does not want a "may be cheaper if you buy two tickets" column; a reader
  opening a row is asking what the fare is and what it allows, which is the
  question the answer belongs to.
- **The suite reads the sentence out of a live panel**, at a budget that reaches
  a changed row and in a list that carries one, and it checks that a direct row's
  panel does not show it. Both directions, because a page that says it always
  would be as wrong as a page that never says it.
- **Nothing about the price changed.** The page still prices the through fare,
  and the split line claims nothing the feed cannot support.

## Alternatives rejected

- **Price the splits.** It needs a fare lookup for every leg boundary, and the
  feed does not price itineraries: the number would be a sum of two fares the
  feed quotes, compared against a through fare the feed quotes, presented as if
  it were a fare. It also doubles the lookups per row and makes a row mean
  several prices at once, which is the opposite of what a price list is for.
- **Leave it out and say so only in the launch post.** Weaker, now that the
  station is nameable from data the build already holds: it spends the same
  effort and leaves the reader to find the caveat somewhere else.
- **Add a "split ticket" button on the row that links to a seller.** It is the
  only one of the three that needs a price, and it is the one the feed cannot
  support. A link that appears to price something it does not is worse than no
  link.
