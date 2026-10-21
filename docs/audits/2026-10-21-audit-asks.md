# The audits' open asks, merged

**Date:** 21 October 2026. **Merges:** `2026-10-14-app-engineering-audit.md`,
`2026-10-19-impeccable-critique.md`, `2026-10-19-impeccable-delight.md` and
`2026-10-19-impeccable-overdrive.md`, all removed the same day.

Four review files had ten open asks between them, and a reader answering "what is
still asked" had to read four prunings and a fifth file that restated the ones it
remembered. This is the one list. Each ask keeps the ID its own audit gave it, so
the numbers code comments and `docs/settled-work.md` cite still resolve, and each
names the open-work item that tracks it. The evidence stays here, with the
measurements it was taken from; the actionable statement is in
`docs/open-work.md` under that item, so the two cannot say different things about
what is left.

Every other finding in those four files is closed, and is a row in
`docs/settled-work.md`. The coverage table below is the proof that nothing fell
between the two files. Two of the ten asks moved on 21 October 2026: **ask 1**
was measured and its split refused, and **ask 8** was measured with its gate
decision left to O8. Their sections keep the measurements and say so.

## Coverage

| Audit | Finding | Where it is now |
|---|---|---|
| 14 October 2026 engineering, 1 | split `build_demo_page.py` along its seams | settled, ADR-0071 |
| 14 October 2026 engineering, 2 | write the classification cache before the identity that names it | settled, `build_state.load_page_fares` |
| 14 October 2026 engineering, 3 | de-flake the cache-tidying test | settled, `tests/test_page_caches.FaresCacheTest` |
| 14 October 2026 engineering, 4 | a type checker in CI | settled, ADR-0072 and `tools/check_types.py` |
| 14 October 2026 engineering, 5 | declare the Python the app runs on | settled, `.python-version` and `README.md` |
| 14 October 2026 engineering, 6 | decide whether a 354 KB page is the intended payload | settled 21 October 2026: the real page was measured at 397 KB and the split costed, in `docs/build-performance-findings.md` |
| 14 October 2026 engineering, 7 | kill the tools' path dance | settled, `python -m tools.<name>` everywhere |
| 14 October 2026 engineering, 8 | make the suppression census a check | settled, `tests/test_suppressions.py` |
| 14 October 2026 engineering, 9 | correct the documented runtimes | settled, `AGENTS.md` and the findings file |
| 14 October 2026 engineering, 10 | keep the one-owner rule for build inputs | settled, nothing to do |
| 19 October critique, S1-S4, S6, S7, S9-S11 | the entry, the £0 recovery, the row's own times, and the three hand-offs | settled, 19 and 20 October 2026 |
| 19 October critique, S5 | the phone has no fold budget | **ask 2**, O7 |
| 19 October critique, S8 (C21) | the shortlist's cleared-focus loss | settled, 20 October 2026 |
| 19 October critique, S12 (C18) | `<title>Privacy</title>` | rejected by the owner, 19 October 2026 |
| 19 October critique, observation | the refinements panel's 160px void | **ask 3**, O9 |
| 19 October critique, question 2 | the heading's budget field against the 44px promise | **ask 4**, O10 |
| 19 October delight, DL1, DL2, DL4, DL5 | the next-place line, the named door, the copy confirmation, the 120ms reveal | settled, 19 October 2026 |
| 19 October delight, DL3 | the shortlist total | **ask 5**, O3 |
| 19 October delight, DL6 | one tick at the cheapest fare | **ask 6**, O5 |
| 19 October overdrive, OV2, OV6, OV8, OV9 | the next-place line, one document, the interaction budget, the fallbacks | settled, 19 October 2026 |
| 19 October overdrive, OV4 | the budget rail | settled, 20 October 2026 |
| 19 October overdrive, OV1 | draw the fare horizon on the track | **ask 7**, O5 |
| 19 October overdrive, OV3 | keep the drag at 60fps on a mid-range phone | measured 21 October 2026; **ask 8**, O8 holds the gate decision |
| 19 October overdrive, OV5 | the dock under the rail | **ask 9**, O4 |
| 19 October overdrive, OV7 | morph the chosen station | **ask 10**, O6 |

## The ten asks

### Ask 1 -- [P2] Decide whether a 354 KB page is the intended payload (14 October 2026, item 6, settled)

Measured on a fresh real-feed build served from `127.0.0.1:8899`: a station page is
**354 KB raw, 53 KB gzip**, of which the route's CSS is 54 KB (17 KB gzip) and its
script 149 KB (45 KB gzip); the chooser and privacy pages are 28 KB and 26 KB. The
800 MB site budget is not the constraint -- 2,712 such pages are -- so this is
per-page parse and paint on a phone.

**Settled 21 October 2026.** The page was measured again on a real build (397 KB
of HTML, 56 KB gzip, plus 21 KB gzip of stylesheet and 60 KB gzip of script), the
first paint was timed on a throttled connection (720 to 865 ms, a fare on screen
at 1.25 to 1.37 s), and the ticket-mode split was costed at 10 KB gzip saved
against a round trip of 150 ms. The split was refused, and the figures are in
`docs/build-performance-findings.md` under "A real-feed station page's bytes".

### Ask 2 -- [P2] The phone has no fold budget, and at 320x640 it has no answer above it (S5, tracks O7)

Measured on arrival, with the refinements folded:

| Viewport | First row top | Fold | One whole row above? |
|---|---|---|---|
| 1366x768 | 690 | 768 | yes (row bottom 754) |
| 390x844 | 786 | 844 | no; 58px of the row is visible |
| 320x640 | 858 | 640 | no; nothing |

The laptop fold was given a stated budget by the 17 October pass (one whole row at
1366x768) and is now held by a browser check. There is no equivalent for the phone,
which is the first encounter the product describes. At 390 the chrome above the row
is 786px: banner 79, theme row 44, heading 73, first-use 48, filter bar 364, link
terms 24, summary 48. At 320 the same stack plus the wrapped hint and day help is
858px.

**Why it matters.** A community link opened on a phone shows a heading, a slider, a
folded filter bar and a note before it shows a single destination. The page's
promise is "17 destinations for £20"; the first screen does not contain one. The 320
case is the 200% zoom case too, so the reader who zooms for legibility is the one who
sees no answer at all.

**Fix.** Set a phone budget the way the laptop one was set -- "at 390x844 the first
row starts above 760px; at 320x640 above 620px" -- and buy it from the stack. The
key hint on coarse pointers (S10, 19px) was taken on 19 October 2026 and is no
longer available to spend; the budget hint cut is about 19px, and shortening the
first-use note to one line ("Click the station name to start elsewhere.") saves
24px and updates the two browser assertions that quote the old wording. With the
hint gone that leaves 43px of the 62px this finding first counted, so the 390 target
needs re-measuring before it is claimed. At 320 the filter bar itself is 403px; the
wrapped hint and the taller day control add about 39px, and the heading is three
lines (107px). The 320 target may need the banner to be one line there or the
heading's vh term lowered again; state the budget first, then choose.

**Verify.** Add the two measurements to `tests/browser/station-layout.cjs` beside
the 1366 one, with the banner on the page.

### Ask 3 -- [P3] The refinements panel leaves a 160px void (19 October 2026, minor observation, tracks O9)

The opened refinements panel leaves a 160px void in its left column, because the
ticket-type fieldset is short and the party/railcard column is tall. The panel is a
two-column grid with one long row and one short one.

### Ask 4 -- [P3] Should the heading's budget field be held to the 44px the row actions promise? (19 October 2026, question 2, tracks O10)

The heading's budget field is 37x36px on a phone. It meets the 24px floor the
accessibility matrix holds every target to, and sits under the 44px the row actions
promise. The field is the identity's own interaction, so the 44px promise is worth
deciding deliberately rather than by omission.

### Ask 5 -- [P2] The shortlist has no total and no sentence (DL3, tracks O3)

**Moment.** Two places are on the shortlist, the dock is open, and the reader is
looking at two prices. The page's question was "what can I do for £20"; the
shortlist is the beginning of a plan, and it never adds up.

**Add.** One line under the dock's head: "Two places, £13.40 for one adult." When
the party is two, "Two places, £26.80 for two." The sum is of the visible row prices
on the fare each row names, the same basis as the count line. The share text gains
the same sentence before the link: "Two places from GRANTHAM for £13.40 return."
Keep "not a booking" exactly where it is.

**Cost and risk.** The rows are already in `STATE.shortlist` and each carries its
price and party price; sum the rendered values, not a separate array, or a
single-priced row will be summed as a return. A tie or an unpriced row must make the
total say "from" or omit it rather than guess. Do not call it a "day out" or an
"itinerary"; the page refuses to choose trains, and the total is only the fares.

**Verify.** Add SLEAFORD and NOTTINGHAM at £20 and assert "£13.40 for one adult";
switch to two adults and assert the party sum; add a row with a railcard and assert
the card price is what is summed. The share text test reads the same sentence.

### Ask 6 -- [P3] The track has no mark where the first fare begins (DL6, tracks O5)

At £0 the thumb is at the far left and the list is empty, so the reader does not
know how far to drag. One 1px tick on the slider's track at the cheapest fare in the
active list, with the same muted ink as the track and no label: a mark, not a chart.
When the budget crosses it the tick takes the accent for the rest of the drag and
settles back.

The tick's position is `cheapest / ceiling`; a ceiling of zero hides it. A 1px span
positioned over the track avoids restyling the browser's own range track, so the
native keyboard and touch behaviour is untouched. It must be decorative
(`aria-hidden`) and must not imply that the cheapest fare is the best place. No
animation loop; one position update per render.

**Verify.** At £0 the tick is at the cheapest fare's fraction of the track; at the
ceiling it is at the right edge; with a filter that removes the cheapest place, it
moves. A screenshot at 390 and 1366.

### Ask 7 -- [P2] Draw the fare horizon on the track (OV1, tracks O5)

**Decision needed:** is a drawn track (1px ticks at every distinct visible fare) part
of the page's identity, or is the plain track the identity? This is a visual
direction, not a fix.

**The shape, if yes.** One tick for every distinct fare in the visible list, 1px,
muted, denser where the fares cluster. No axes, no labels, `aria-hidden`, drawn on a
canvas at devicePixelRatio or as absolutely positioned spans. Redrawn on render and
resize. The plain track is the fallback.

**Trade-off.** A canvas is the site's only drawing surface; spans avoid it but put up
to 101 nodes in the control. The line under the count already says what the next
pound buys (OV2), so the ticks must add the shape of the list rather than repeat the
sentence. A tick that reads as "the best place" is a lie.

**What the 20 October 2026 mockup changed.** Both forms were drawn over the built
page and measured before the owner was asked. On a £126 ceiling every fare in the
demo list is inside the left fifth of the track (22 distinct fares, the furthest
short of £19 at 172px of 528), so the ticks read as a smudge beside the thumb rather
than as a horizon, and the single far fare sits alone at the right end. The one-tick
form (ask 6) survives that ceiling; the full track needs a non-linear scale or only
the next few fares to say anything.

**What would prove it.** At 101 rows the draw is under 8ms and the drag holds 60fps;
with reduced motion the ticks still appear; without the ticks the drag is blind
again. And the ticks must read as a shape at the ceiling the page actually opens on,
which the left-fifth smear above says they do not yet.

### Ask 8 -- [P3] Keep the drag at 60fps on a mid-range phone (OV3, measured 21 October 2026)

**Measured.** The drag's re-render costs **46, 57 and 79 ms** across three runs at
a 4x CPU slowdown, and **84, 94 and 142 ms** at 6x, against the 50 ms gate, on the
real Grantham page at 390x844. The desktop figure the gate was written against is
7.4 ms, and this page's own list renders in 8.3 to 9.6 ms unthrottled. No handset
was used; the machine is a slowed CPU and the findings file says so.

**The coalescing this ask named is already shipped** (`queueBudgetFrame`, 19
October 2026), so what is left is the cost of the single render it schedules.

**Decision still needed:** whether the 50 ms gate is a desktop budget or a phone
one. If it is a phone budget, the render has to get cheaper; if it is a desktop
budget, the figure is recorded and O8 closes.

### Ask 9 -- [P2] The dock under the rail (OV5, tracks O4)

OV4 shipped and took the results table's sticky heading with it: while the rail is
up the headings sit 56px down, and a row scrolled to reserves 6.7rem rather than
3.2rem. The shortlist dock at the foot of the screen was not part of that, so a page
with places shortlisted, scrolled to the last row, has a rail at the top and a dock
at the bottom and about 700px between them at 390.

**Decision needed:** whether the dock yields to the rail (a shorter list, or a
height cap) or whether the two simply coexist. It is a measurement first: the dock's
height depends on how many places are in it, and the rail is only up when the reader
is deep in the list, which is exactly when the shortlist matters.

**What would prove it.** At 390 with two places shortlisted and the page scrolled to
the last row, the number of rows visible between the rail and the dock, and whether
the dock's own Copy is reachable without covering the row above it.

### Ask 10 -- [P3] Morph the chosen station (OV7, tracks O6)

**Decision needed:** whether the transition should carry the station token from the
chosen row into the heading. OV6 shipped without it; the morph is the visible half
of "one document", and it is also the one effect that can look cheap if it lands
mid-scroll.

**The shape.** Name the chosen row's station span and the heading's token with the
same `view-transition-name` for the duration of the click. If it is not clean at
390, it stays unshipped -- OV6 works without it.

## What the audits said not to trade away

Kept because a later pass that does not know it was measured will trade it.

- **The budget's two controls and the sentence they sit in.** The field and the
  slider do the same job and both earn it: one types, one drags. The count line
  follows a drag in 6-14ms on an 8-to-20-row list, and 7.4ms over 101 destinations.
- **The row's honesty.** "No service that day" is used instead of a zero, an
  undescribed restriction says so in the row's own panel and carries its code, and
  "Two tickets" names the split. A conversion-first page would have hidden all three.
- **The phone row.** Two lines, 112px at 390, with the shortlist box, the ticket link
  and the expander each reaching 44px. The desktop header is sticky, and the phone
  layout keeps a real table for assistive technology.
- **The accessibility floor is measured, not asserted.** Every visible text node in
  both palettes cleared 4.5:1 (0 failures), the focus ring is a 2px accent outline on
  every control, and the phone layout did not scroll sideways at 320, 390 or 1366.
- **The page's authored idea.** The question is the control: the budget is a gap in a
  sentence, the starting station is a gap in the same sentence, and the answer is a
  price-ordered list rather than a form. That is not a template, and the heading's
  scale, weight and wrapping carry it without an illustration, a logo or a webfont.

## Run notes worth keeping

- The 19 October critique was a **degraded** pass: one thread ran the design read and
  the browser evidence, and the design read was written first. Its design health
  score (29 of 40) and its per-heuristic table described findings that have since
  landed, so neither is carried forward.
- The detector, `impeccable detect --json`, fired once across the three built routes:
  `cramped-padding` on `.origin-slot-wrap`, the station slot's dashed underline. That
  is a false positive and is recorded as a rejected design in `docs/settled-work.md`,
  not re-filed here.
- The 19 October passes drove Chromium at 1366x768, 390x844 and 320x640 in both
  palettes over `_demo_site`, with 0 console errors and 0 page errors on any route.
  Their build was a 17-destination list at £20, 16 returns and 1 single, so the
  paging arithmetic they state is arithmetic rather than a measurement.
