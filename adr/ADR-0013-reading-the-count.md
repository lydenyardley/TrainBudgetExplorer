# ADR-0013: The go/no-go count is read with its report, not on its own

**Status:** Accepted
**Date:** 21 September 2026

## Context

ADR-0004 gates the build on one number: how many destinations are reachable from
Grantham for under £20. The number comes out of a parser reading a 100 MB
fixed-width file released three times a year by an industry, and it cannot be
checked by hand. ADR-0011 made the query say what it refused to guess and
ADR-0012 made a damaged feed report itself. Neither says what to do with the
number once it exists.

The failure mode to design against is not being wrong. It is being wrong
confidently, in the direction of "too few destinations", and concluding the idea
is dead when the parser is what died.

## Decision

`sanity_report.py` accompanies every count, and the decision is made from the
two together. It answers four things:

1. **The count under each reading of the budget.** "Under £20" for one adult on
   the standard fare, for one adult with a Two Together Railcard, and for the two
   of them with the budget as the party total. On the invented feed the four
   readings give 3, 4, 1 and 2. Those are not four answers to one question; the
   gap between them is the finding, because it says the idea is worth more or
   less depending on who is asking. The report also states a property worth
   relying on: a railcard can only ever add destinations, since the cardholder
   can decline the discount.
2. **What the count left out, by reason.** Every dropped flow or fare is an
   explanation for a number that is too low.
3. **How close the count is to the line.** The destinations within ten per cent
   of the budget are the ones a small pricing error moves, and the count is
   printed at ten per cent either side of the budget. If the count at £18 and at
   £22 is the same as at £20, the answer is not sitting on a knife edge. If it is
   not, the number is a coincidence of where the line was drawn.
4. **What looks wrong with the fares.** Values that are not multiples of five
   pence, values below the floor or above the ceiling for a day return. Real
   fares are multiples of five pence, so a feed full of others means the fields
   are being read at the wrong offsets.

The report prints the files it read, first, above the numbers. A count from the
invented feed and a count from the real feed are otherwise indistinguishable on
the page.

## Consequences

- The report is a second, independent consumer of the same query path as the
  sweep, so a disagreement between the two is a signal rather than a nuisance.
- The decision rule changes slightly and deliberately: a count whose dropped
  reasons are unexplained is not a result yet. It is a number awaiting one.
- The report is not a validator. It cannot tell that a fare is wrong, only that
  its shape is surprising. Somebody still has to look at the loose ends and
  decide whether the answer that survives them is the answer.
- Nothing here changes ADR-0004's gate, the tripwire, or the 21 October review.
  It changes what evidence arrives at them: previously a count, now a count with
  its arithmetic shown.
