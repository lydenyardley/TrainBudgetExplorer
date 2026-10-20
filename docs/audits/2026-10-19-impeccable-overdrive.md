# Impeccable overdrive: make the budget feel like an instrument

```
──────────── ⚡ OVERDRIVE ─────────────
》》》 Entering overdrive mode...
```

**Date:** 19 October 2026
**Reviewed:** the station page and the chooser in `_demo_site`, built 19 October
2026 at 13:29, service date 5 October 2026, served at `127.0.0.1:8801`.
**Mode:** Operate. This is a data-heavy tool used on a phone, often one-handed,
often at night. "Extraordinary" here is not a visual effect; it is an interface
that never hesitates and a budget that behaves like a physical instrument.
**Status:** four of the nine suggestions landed on 19 October 2026 — the
next-place line (OV2), the cross-document view transition (OV6), the
interaction budget as a check (OV8) and the fallbacks those two need (OV9, for
the transitions and the reveal). What is left is OV1, OV3, OV4, OV5 and OV7, and
each needs a decision only the owner can make: a new visual language on the
track, a second control that spends 56px of every viewport, or a morph. The pass
that shipped them is recorded in `docs/settled-work.md` with the check that
holds each.

## What extraordinary means for this product

The page already does the hard part: the question is the control, the answer is
a price-ordered list, and the list is generated from licensed data with its
limits stated. The next level is not more surface. It is **continuity and
feedback**: the budget should feel like a dial that reveals places, the page
should never blink while it answers, and moving between stations should feel
like turning the page of one instrument rather than loading 2,712 separate files.

The constraints are the design:

- one self-contained HTML file per route, plus the shared station list and the
  route's CSS and script — no framework, no external asset;
- the only image in the repository is the National Rail credit; anything new is
  authored in CSS, SVG or canvas, and no external asset is fetched;
- the page's JavaScript is shared by every station page, so a feature costs the
  release once, not 2,712 times;
- `prefers-reduced-motion`, keyboard, touch and no-JS all keep the answer.

## The measured starting point

| What | 1366×768 | 390×844 | 320×640 |
|---|---|---|---|
| Budget control top | 370 | 319 | 353 |
| Last row bottom | 1,775 | 2,691 | 3,157 |
| Distance from the budget to the last row | 1,405px | 2,372px | 2,804px |
| First row top | 690 | 786 | 858 |
| Row height | 64 | 112 | 138 (wrapped rows) |

- A budget change re-rendered the 17-row demo list in **6.3–14.3ms**, measured
  around the input event with a forced layout read: 8 rows 6.3ms, 17 rows
  11.0ms, 19 rows 14.3ms. The post-change figure over 101 destinations is
  **7.4ms** for a page of 20 rows, recorded in
  `docs/build-performance-findings.md`.
- Route assets at the audit: **48.0KB HTML / 11.7KB gzip**, **60.3KB CSS /
  18.6KB gzip**, **177.4KB JS / 54.0KB gzip**, plus the 0.4KB station list.
- No console error or page error on any route; every visible text node cleared
  4.5:1 in both palettes.

The table matters more than the demo's 17 rows: the real Grantham page's opening
list carries **101 destinations** (`PRODUCT.md`), and a page opened at the ceiling
carries every destination the feed prices from that origin. A page whose list
runs 2,372px below the budget on a phone is a page whose budget is gone by row 6.

## What landed

### OV2 — the next-place line (also DL1 of the delight pass)

During a drag a line under the count names the next fare and the place it adds —
"£22.40 adds PETERBOROUGH." — and the release says what the budget gained. The
thresholds are the visible rows, not the whole feed, so a party, a railcard or a
filter changes them correctly. The live region still speaks once, on settle.
**Check:** `tests/browser/station-filters.cjs` drives the pointer down, input and
change path and reads both halves of the line.

### OV6 — one document, not 2,712

`@view-transition { navigation: auto; }` in `page/shared.css`, with the 180ms
cross-fade the chevron already uses, and `animation: none` under
`prefers-reduced-motion`. A browser without the API ignores it and navigates as
it always did. **Check:** the stylesheet assertion in
`tests/test_build_demo_page.py`; the real transition is the browser's, and the
suite only proves the page asks for it and turns it off.

### OV8 — the interaction budget as a check

**Figure:** 7.4ms for `render()` plus a forced layout over 101 destinations and
20 painted rows, measured 19 October 2026 on this machine. The 50ms budget is a
check, not a paragraph: `tests/browser/station-layout.cjs` measures the same
statements on every station page the suite drives and fails above it, naming the
figure and the row count. The method and the machine are in
`docs/build-performance-findings.md`.

### OV9 — the fallbacks, as tests

The reveal (120ms of opacity and 4px) is asserted off under reduced motion by
the layout section; the view transition's fallback is the browser's own
instant navigation, which is the page as it shipped before this pass. The
canvas fallback in OV1 has no implementation to fall back from yet.

## What is left, and the decision each needs

### OV1 [P2] Draw the fare horizon on the track

**Decision needed:** is a drawn track (1px ticks at every distinct visible fare)
part of the page's identity, or is the plain track the identity? This is a visual
direction, not a fix; the 17 October review's "two budget controls, one
instrument" argument does not settle it either way.

**The shape, if yes.** One tick for every distinct fare in the visible list, 1px,
muted, denser where the fares cluster. No axes, no labels, `aria-hidden`, drawn
on a canvas at devicePixelRatio or as absolutely positioned spans. Redrawn on
render and resize. The plain track is the fallback.

**Trade-off.** A canvas is the site's only drawing surface; spans avoid it but
put up to 101 nodes in the control. The line under the count already says what
the next pound buys (OV2), so the ticks must add the shape of the list rather
than repeat the sentence. A tick that reads as "the best place" is a lie.

**What would prove it.** At 101 rows the draw is under 8ms and the drag holds
60fps; with reduced motion the ticks still appear; without the ticks the drag is
blind again.

### OV3 [P3] Keep the drag at 60fps on a mid-range phone

**Decision needed:** whether to profile on a real device, which the repository
has not done. The desktop figure is 7.4ms against a 50ms budget; a phone is a
different machine, and ADR-0032 wants the machine named.

**The shape.** One `requestAnimationFrame` per burst of input events, so the
count line and the next-place line update once per frame; no layout reads inside
the handler beyond the one the count line already does; measure the long tasks
on the interaction. If the phone figure is under the budget, record it and close
this; if not, coalesce.

### OV4 + OV5 [P2] The sticky budget rail, and the two sticky surfaces

**Decision needed:** 56px of every viewport, forever, in exchange for the budget
being one gesture away at row 101. It changes the page's rhythm: the heading is
the question, and a second control that repeats it is a statement about how the
page should be read. This is the owner's call, not a defect.

**The shape, if yes.** A sentinel at the heading toggles a class; the rail is a
second range input that writes through `chooseBudget`, so there is one source of
truth. Its accessible name says which control it is ("Budget, compact") and its
description is the same ceiling sentence. On desktop the table's sticky header
moves under the rail; on a phone the header is already hidden, so the rail owns
the top. It retires when the heading returns and never covers the shortlist dock.

**What would prove it.** At the last row the budget is one gesture away at 390
and 1366; the rail's value and the heading's value are always equal; the header
and the dock do not overlap it; keyboard focus reaches both controls with one
source of truth. The assertions that measure the height above the table or count
range inputs will see the rail and must be updated deliberately.

### OV7 [P3] Morph the chosen station

**Decision needed:** whether the transition should carry the station token from
the chosen row into the heading. OV6 shipped without it; the morph is the
visible half of "one document", and it is also the one effect that can look
cheap if it lands mid-scroll.

**The shape.** Name the chosen row's station span and the heading's token with
the same `view-transition-name` for the duration of the click. If it is not clean
at 390, it stays unshipped — OV6 works without it.

## Not this

- **Particles, confetti, a mascot, or a WebGL map.** The fares feed carries no
  coordinates, and the coordinates that do exist elsewhere are not a fare's
  position; a map would invent geography the page's data does not have.
- **A loading skeleton.** The page is static and answers in milliseconds; a
  skeleton would fake work.
- **Sound or haptics on the drag.** The context is a train and a phone; silence
  is the feature.
- **A second ranking.** The page orders by price and says so; a "best value"
  score is a recommendation the data cannot support.
- **A virtualised table before it is needed.** The station page's opening list
  is 101 rows; virtualisation would buy complexity the page cannot spend. Measure
  the ceiling build first if that changes.

## Verification plan for what remains

- **Rows:** the demo's 17 and a real single-origin build's 101. Time the input
  handler and the paint with `performance.now()` and the Performance panel; state
  the machine and the date beside the figure (ADR-0032).
- **Widths:** 320×640, 390×844, 768×1024, 1366×768; both palettes; the
  refinements open and closed; the dock open and closed.
- **Modes:** one adult, two adults, a railcard, each ticket set; a rail and a
  horizon must agree with the visible rows in every one.
- **Fallbacks:** JavaScript disabled, canvas unavailable, reduced motion, Firefox
  for the view transitions.
- **No regression:** the browser suite's layout, row, fare and shortlist
  sections; `python -m unittest tests.test_build_demo_page`.

## Evidence

- `_demo_site` served at `127.0.0.1:8801`, Chromium, 19 October 2026; geometry
  and re-render timings from a Playwright probe at the three widths above.
- The 101-destination figure and its method: `docs/build-performance-findings.md`,
  section "The budget's re-render while dragging, 19 October 2026".
- Assets and gzip sizes from the built files in `_demo_site`.
- No console or page errors; contrast clean in both palettes.
- Screenshots: `screenshots/2026-10-19-*.png` in the worktree.
