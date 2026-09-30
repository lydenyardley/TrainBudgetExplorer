# ADR-0044: The list that opens is the cheapest fare of any type

**Status:** Accepted
**Date:** 30 September 2026
**Relates to:** ADR-0025 (the reviewed selector; which set the page opens in),
ADR-0019 (one page per station; the ticket modes), ADR-0040 (the row carries the
fare's code), ADR-0043 (the row's own panel)
Settles Q4 of the promise-gap audit of 29 September 2026, which is filed in
the repository's history and whose durable findings live in these ADRs, in
PRODUCT.md and in the measured tables beside them.

## Context

A reader arrives with a budget and a place in mind, and the page opened in the
reviewed Anytime Day Return set. That set is a defensible thing to show — it is
the one set the fares were reviewed for (ADR-0025) — but it is not the cheapest
way to reach most places, and on the real Grantham feed it is not the cheapest
way to reach *any* of them. Measured on that page:

| | rows |
|---|---|
| returns the feed prices | 47 |
| outbound singles | 101 |
| reviewed Anytime Day Returns | 42 |
| destinations in the opening list | 101 |
| of those, cheapest on a single | **101** |

A £20 budget on that page answered "here is what a return costs", which is not
the question that was asked. The promise and the page were in agreement — both
named the reviewed set — and the agreement was with the wrong question.

The cost of the fix is not hidden, so it is stated here rather than discovered
later: **the opening list is a one-way price list in practice.** A single to a
place always costs less than a return to it, so the headline becomes a list of
singles, and the party figure — two adults — becomes two singles on most rows
rather than two returns. A £30 ceiling read as two returns would be a wrong
answer, not a loose one.

## Decision

**The page opens on the cheapest fare of any ticket type to each destination.
The three named sets stay as the filters beside it, and every row names the fare
it is priced as.**

1. **A fourth ticket mode, `cheapest`, is the checked one.** The other three —
   the reviewed Anytime Day Returns, the broader "any return" set and outbound
   singles — are unchanged, keep their mode values, keep their mode notes, and
   are now what a reader reaches for when they want one kind of fare. A shared
   link written under the old default still resolves: `mode=anytime` still reads
   that set.
2. **The list is composed in the page, not in the build.** One row per
   destination, keeping the cheaper of the fares that destination is priced at,
   so it costs no payload bytes and the build writes no fourth list. It is
   composed per reader rather than once, because which fare is cheapest depends
   on who the price is for: the Two Together card and the party size both change
   which row is cheapest, so `render()` settles the card before it composes the
   list, and the list moves when either control moves.
3. **The row names its fare, in the fare's own words.** The handoff text a reader
   pastes into a seller carries the ticket the row is priced as
   (`Standard outbound single`, `Unrestricted Anytime Day Return`, `Standard
   return`, `Advance single`) rather than the name of the mode, because
   "Ticket: Cheapest of any type" is what the reader chose and not what a seller
   needs to hear. The fare code beside it (ADR-0040) is the code, and the row's
   own panel says which quality the build chose.
4. **The count line names the mix, and the party figure names its basis.** A
   cheapest list reading "12 destinations for up to £20.00 each, cheapest first:
   9 singles, 3 returns" is describing the list the reader is looking at. For two
   adults it reads "…for the two of us, two of the fare each row names", because
   on a single row that is two singles. The set names itself in three other
   places too — the note above the table, the coverage line and the provenance
   line — so no sentence on the page counts the wrong fares.
5. **The empty-list recovery offers the cheapest list**, because a reader in a
   named set with no fares is offered the list that does have them.

## Consequences

- **PRODUCT.md's promise now matches the page's basis**, which is the point: the
  page no longer opens on a number the brief does not describe, and the brief no
  longer describes a number the page does not show.
- **A restricted or advance fare can now lead the list.** The cheapest single
  on a busy route is often an advance one, which is valid on a qualifying train
  only. The row says so (`advance` beside the code, the sentence in the panel,
  and the note above the table), which is the same rule the "any return" set
  already followed.
- **The warn token was darkened.** The restricted and advance marks are the warn
  colour on the row panel's tint, and `#9a6700` measured 4.36:1 there against the
  4.5:1 the browser matrix holds. The light value is `#8f5f00` (4.94:1 on that
  tint), and the Python test measures the ratio rather than asserting the hex.
- **The suite's payload reader composes the opening list itself.** An expectation
  built from one of the three sets fails a page that is behaving correctly, so
  the reader composes the list the way the rule says and the page is checked
  against it. That is the difference between a check that follows the page and
  one that merely re-runs it.
- **The opening list is longer than any of the three sets.** Grantham's page
  goes from 47 rows to 101 at the same budget, on a page whose payload is
  unchanged. The rows are the same shape, so the bytes are the same shape: 219 KB
  for the whole page, of which 73 KB is the payload, and nothing was added to it.
- The page's own claim about the order ("cheapest first", ADR-0041) is now
  truer: it is sorting the cheapest fare of any type, which is what the words
  say.

## Alternatives rejected

- **Keep the reviewed set as the default and add the cheapest list as a fourth
  mode below it.** This is the option that keeps the old promise intact, and it
  is the one that leaves the page answering a question nobody asked: the default
  is the list every reader arrives to, and a reader who has to know that a
  control exists to get the real answer is a reader who does not find it.
- **Build the cheapest list in the build, as a fourth payload list.** It would be
  computed once rather than per reader, at the cost of a fourth copy of every
  row's data — the largest payload item on the page, repeated to answer a
  question two controls can answer. It would also freeze "cheapest" at the
  party's undiscounted fare, which is the basis the card is supposed to change.
- **A separate "cheap places" page or a sort control.** The list is the same
  list: the destinations are the same, the rows are the same, and only the
  chosen fare differs. A second page would be a second place to keep true.
- **Drop the named sets once the cheapest list exists.** They are the reviewed
  set (ADR-0025) the build still refuses to publish without, and the only way a
  reader can see a restricted off-peak return or an outbound single. Removing
  them would remove information to simplify a control.
