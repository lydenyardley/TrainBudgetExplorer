# Impeccable delight: where the page has earned a moment, and where it has not

**Date:** 19 October 2026
**Reviewed:** the chooser, a station page and the privacy page in `_demo_site`,
built 19 October 2026 at 13:29, service date 5 October 2026, served at
`127.0.0.1:8801`.
**Mode:** Operate. Delight is concentrated at first use, a change the reader
made, recovery, and completion; reliability carries everything else.
**Status:** four of the six suggestions below landed on 19 October 2026 — the
next-place line (DL1), the empty door that names the place it reaches (DL2), the
visible copy confirmation (DL4) and the 120ms reveal (DL5). What is left is DL3,
the shortlist total, and DL6, the tick at the cheapest fare. The pass that landed
them is settled in `docs/settled-work.md`, with the check that holds each.

## The brief, and what it does not say

`PRODUCT.md` is explicit that the public name, the tone, and any mark are
undecided. What it does commit to is a voice: prices are never approximations,
limitations are content, the link is part of the promise, and nothing is built
on a signal that has not appeared. The page already sounds like that — dry,
precise, unafraid of the unflattering sentence ("no train is chosen", "not a
booking", "Restriction 00 is not described in this feed"). It is a page read at
night, on a phone, on a train; the default palette is dark for that reason.

So the emotional range this pass assumes is **quiet satisfaction, not
celebration**. Delight here is the feeling that the page is answering a
question the reader did not have to phrase, and that it noticed what they just
did. It is not confetti, a mascot, or a pun. If the owner wants a warmer or a
more playful voice, that is a brand decision this document cannot make; the
proposals below are written to survive either answer.

## Delight thesis

**The budget is a horizon. Turning it should feel like watching places come
into reach, and every acknowledgement should answer in places, not numbers, in
the same plain voice the page uses for a restriction.**

That thesis is specific to this product: a neighbouring fare search could copy
a slider, but it could not copy "£22.40 adds PETERBOROUGH" without inverting its
own question.

## What the page already does, and what is left

The heading is a sentence with a field in it, the count line answers a drag in
milliseconds, the drag answers in places, a copy becomes "Copied" for two
seconds, the empty state is a set of doors, and the theme switch is a moon. The
four moments that arrived in this pass (DL1, DL2, DL4, DL5) are recorded in
`docs/settled-work.md` with the check that holds each. Two are still missing.

## Where a moment is missing

### DL3 [P2] The shortlist has no total and no sentence

**Moment:** two places are on the shortlist, the dock is open, and the reader is
looking at two prices. The page's question was "what can I do for £20"; the
shortlist is the beginning of a plan, and it never adds up.

**Add:** one line under the dock's head: "Two places, £13.40 for one adult."
When the party is two, "Two places, £26.80 for two." The sum is of the visible
row prices on the fare each row names, the same basis as the count line. The
share text gains the same sentence before the link: "Two places from GRANTHAM
for £13.40 return." Keep "not a booking" exactly where it is.

**Why it belongs:** the dock is the one place the reader has expressed a
preference; a total is the page completing the thought. It is also the honest
number: it uses the fare the row already names and does not add a journey the
page cannot price.

**Cost and risk:** the rows are already in `STATE.shortlist` and each carries its
price and party price; sum the rendered values, not a separate array, or a
single-priced row will be summed as a return. A tie or an unpriced row must make
the total say "from" or omit it rather than guess. Do not call it a "day out" or
an "itinerary"; the page refuses to choose trains, and the total is only the
fares.

**Verify:** add SLEAFORD and NOTTINGHAM at £20 and assert "£13.40 for one
adult"; switch to two adults and assert the party sum; add a row with a railcard
and assert the card price is what is summed. The share text test reads the same
sentence.

### DL6 [P3] The track has no mark where the first fare begins

**Moment:** at £0 the thumb is at the far left and the list is empty. The
reader does not know how far to drag.

**Add:** one 1px tick on the slider's track at the cheapest fare in the active
list, with the same muted ink as the track, and no label. It is a mark, not a
chart. When the budget crosses it, the tick takes the accent for the rest of the
drag and settles back.

**Why it belongs:** it turns the first drag into a small discovery — "the first
place is here" — and it is the cheapest possible version of the fare-horizon
idea. It also makes the ceiling's arithmetic visible without another sentence.

**Cost and risk:** the tick's position is `cheapest / ceiling`; a ceiling of zero
hides it. A 1px span positioned over the track avoids restyling the browser's own
range track, so the native keyboard and touch behaviour is untouched. It must be
decorative (`aria-hidden`) and must not imply that the cheapest fare is the best
place. No animation loop; one position update per render.

**Verify:** at £0 the tick is at the cheapest fare's fraction of the track; at
the ceiling it is at the right edge; with a filter that removes the cheapest
place, it moves. A screenshot at 390 and 1366.

## Guardrails

- **Never delay the answer.** No entrance animation on the table, no staged
  count-up, no skeleton. The page's speed is the delight.
- **No sound, no confetti, no mascot, no fake progress.** They would contradict
  the voice and the operating context (a train, a phone, a reader who wants a
  price).
- **The live region speaks once, on settle.** A drag that announces every pound
  is a worse experience for a screen-reader reader than silence.
- **Reduced motion is a full alternative, not a shorter duration.**
- **Every added sentence must be true of the payload**, including the empty
  state and the party case. A delightful lie is a defect.
- **Repeat-safe.** The budget is dragged repeatedly; the tick and the next-place
  line must survive the hundredth drag without becoming noise. No variation for
  its own sake.

## What not to add

- A celebration when a place is shortlisted. It is a two-second decision, not a
  milestone.
- A "best value" badge or a ranking beyond cheapest-first; the page refuses to
  recommend.
- A weather, sunset, or "things to do" line for the destination. The data does
  not carry it, and inventing it is the exact failure `PRODUCT.md` forbids.
- A total that calls itself a day out or a plan. The fares are a sum; the day is
  the reader's.

## Numbered suggestions, in order

1. **DL3** — the shortlist total and the sentence in the share text.
2. **DL6** — one tick on the track at the cheapest fare.

## Open decisions for the owner

- **Voice:** quiet and dry (the current page), or a little warmer at the two
  moments above? The proposals are written for the first; the second would change
  the copy, not the mechanics.
- **The shortlist's purpose:** a comparison list, or the beginning of a plan? DL3
  is the smallest version of the second; anything more (times, an itinerary) is a
  product decision, not a delight pass.
- **Motion:** settled in the 19 October 2026 pass — 120ms of opacity and 4px is
  the page's one reveal, and reduced motion removes it. DL5 is in
  `docs/settled-work.md`.

## Evidence

- Built page and assets: `_demo_site` (48.0KB HTML, 60.3KB CSS, 177.4KB route
  script; 11.7KB, 18.6KB and 54.0KB gzip) served at `127.0.0.1:8801`, Chromium.
- Budget re-render: 6.3ms at 8 rows, 11.0ms at 17, 14.3ms at 19, measured with
  `performance.now()` around the input event and a forced layout read. The
  post-change figure is in `docs/build-performance-findings.md` (7.4ms for a
  page of 20 rows over 101 destinations).
- Shortlist prices used in DL3: SLEAFORD £6.40 and NOTTINGHAM £7.00 on the
  visible single, so £13.40 for one adult; the two-adult sum must be read from
  the rendered rows because the single's party price is not the return's.
- Next fare above £20 in the demo payload: PETERBOROUGH, £22.40; at £0 the door
  reaches SLEAFORD for £7.00 and the list at £7.00 holds two places.
- No console or page errors on any route. Both palettes were inspected; the
  screenshots are in `screenshots/audit-2026-10-19-*.png`.
