# ADR-0048: The budget names where it stops

**Status:** Accepted
**Date:** 1 October 2026
**Relates to:** ADR-0019 (one page per station), ADR-0033 (the shared
stylesheet), ADR-0047 (the station route fetches one hashed stylesheet)
Settles the second half of S17 in the re-envision pass, now carried by
`docs/open-work.md`.

## Context

The budget contract has been settled for a while and stated in four places at
once. The figure is inclusive — "up to £X", never "under £X" — one resolver
(`resolvedBudget`) feeds the heading, the control, the count line and the URL,
and a fare at the boundary is included. That half of S17 is done and has been
for some time.

The other half was not, and it is the half a reader touches. The slider stops
at a figure the page never says out loud: `render()` resolves `budgetCeiling()`
and writes it to `max` on both the slider and the heading's number field, and
until this change nothing on the page named where that number came from or what
it would be. The control's hint said one thing — "Drag to change the budget in
the heading" — which is an instruction, not a contract.

So a reader who wanted to know whether a fare of £126 was inside their £126
budget had no way to find out from reading the page, and a reader who wanted to
know why the slider ended where it did had nothing to read. The inclusive
wording promises the reader can predict the boundary; the control was the one
place that promise could not be checked.

The ceiling is also not a constant, which is the part that made it awkward to
simply print. It is party-aware: two adults cost twice one, so a ceiling set by
the single fare is a budget nobody reading the party price could type, and one
that stood still would name a stop the page left behind the moment "Two
adults" was chosen. The railcard is deliberately left out — it makes prices
lower, so a ceiling that moved when the box was ticked would clamp a budget the
reader had already chosen. Any sentence naming the ceiling therefore has to name
the party it was resolved for, or it is a number without a subject.

## Decision

The budget hint beside the slider now names the stop and its basis, and the
figure is the stop:

> Drag to change the budget in the heading. It stops at the highest fare in the
> ticket type you are looking at — £126.00 for one adult.

Two choices are worth naming.

**The figure is on the page, not only the rule.** "The slider stops at the
highest fare" is true and useless: the reader's question is about a number, and
the number is already known to the build. The page prints it, in the same two
decimal places as every other price on it, so it can be compared with a fare
rather than parsed.

**It says "in the ticket type you are looking at", not "on this page".** The
ceiling is resolved over the active ticket mode's list, so switching mode can
lower it, and a sentence about the page as a whole would be wrong in the mode
the reader is actually looking at.

The figure is written by the build into `#budgetCeiling` before any script runs,
so a reader with no JavaScript is told the truth rather than left with a
half-sentence, and the script overwrites it on every render with the resolved
value and the party it was resolved for. In the state where a ticket type
prices nothing, the note keeps the figure the control kept: that branch already
deliberately leaves the budget alone, because clamping it to the £1 of an empty
list would silently reset the reader's budget for every other mode they switch
back to. The note is part of the control, so it moves when the control moves and
not otherwise.

## Consequences

- A reader can now predict the boundary from the page, which is what the
  inclusive wording has been promising. `render()` already clamped the budget
  when a ceiling fell; the page now says why.
- The build writes one more derived figure into the page, so the resolver and
  the sentence can disagree in principle. Two tests hold them together: one
  reads the figure and the slider's own `max` out of the built page and fails if
  they differ, and the browser suite reads both out of the rendered page — in
  the one-adult state and again after choosing two adults.
- The figure is party-aware, so the sentence names the party. That is two more
  words beside a control that is now four lines of text in total. It was judged
  worth them because the alternative is a figure whose meaning changes under the
  reader's hand.

Read by running:

```bash
python -m unittest tests.test_build_demo_page -k ceiling -v
python build_demo_page.py --feed _demo_feed --timetable _demo_feed --all-origins --out _demo_site/index.html
npx --yes --package playwright node tests/browser_test.cjs _demo_site/from/grantham/index.html
```

## What this does not settle

S16 — sort by the price currently displayed — was taken up at the same time and
needed no code: `render()` has always sorted the visible rows by `priceOf()`,
the same function the price cell prints. What was missing was a measurement, and
the one added is honest about its limits. The existing check reads the order in
the one-adult and two-adult states, and doubling every price leaves an order
untouched, so neither reading can tell a page that re-sorts from one that
happens to be right. The railcard is the only control that replaces each row's
price with a different discount, so it is the only state where a row can move —
and this feed's discounts happen to fall in the same order as the fares they
come from. Measured: with two adults selected the page shows
`2 17.4 24 44.8 252`, and with the card ticked `1.3 17.4 24 29.8 168`; a sort
that ignored the card entirely was substituted, the page was rebuilt, and the
new check passed. It is a guard for a feed whose discounts are not uniform, and
not a gate on this one.
