# Impeccable critique: the chooser, the station page, the privacy page

⚠️ DEGRADED: single-context (no browser-capable sub-agent; the design read and
the DOM, detector and screenshot evidence ran in one thread).

**Date:** 19 October 2026
**Reviewed:** the worktree at `main` (`9143769`), with the 17 October review's
uncommitted rewrite in the tree. Nothing in this pass was built from the real
licensed feeds.
**Mode:** Operate. Every route is a tool used to answer one question, and the
design's job is to get out of the way of the answer.
**Routes:** `/` (the chooser), `/from/grantham/` (a station page with fares and a
timetable), and `/privacy/`. `/from/<station>/` is one route repeated per priced
station, so a finding about the page's chrome or its table is route-wide; a
figure that names a page is from that page. The prices-only release shape uses
the same station template with its time columns stood down; it was read in
source, not in the browser.
**Artifact:** `_demo_site`, built 19 October 2026 at 13:29 from `_demo_feed` and
`_demo_kb`, service date 5 October 2026, served at `127.0.0.1:8801`.
**Method:** one thread. The design assessment was written before the detector
output entered this document; the browser evidence was gathered with Chromium
through the preview pane and with Playwright for geometry at 1366×768, 390×844
and 320×640. Screenshots are in `screenshots/audit-2026-10-19-*.png` in the
worktree. No console error and no page error appeared on any route.
**Measurements:** every figure below is from the demo build unless it says
otherwise: a 17-destination list at £20, 16 returns and 1 single. That is enough
for layout and interaction; it is not enough for the paging arithmetic, which is
stated as arithmetic.
**Read-only:** no source file, template, stylesheet or test was changed.
**Status:** eleven of its twelve findings are closed and removed from this file
rather than left to be re-derived. S6, S9 and S10 landed on 19 October 2026 with
DS1, DL4 and DS3 of the distill and delight passes; S8 landed on 20 October 2026
as C21 of the review before this one; S12 is the owner's rejection of C18 on
19 October 2026, so `<title>Privacy</title>` stands; and S1, S2, S3, S4, S7 and
S11 landed on 20 October 2026. Each is a row in `docs/settled-work.md` with the
check that holds it. S5, the phone's fold budget, is the one finding still open:
it needs a measured budget set before it can be implemented, and that is why this
review stays.

## Design health score

Measured on 19 October 2026, before any of the findings above landed: **29 of 40,
good, with three P1s at the page's hand-offs.** Six of the seven findings that
cost it are closed, so the figure is a reading of that page rather than a score
to hold this one to; the per-heuristic table it was taken from went with the
findings it described.

## Design specificity verdict

**LLM assessment.** The authored idea is still the strongest thing on the site:
the question is the control. The budget is a gap in a sentence, the starting
station is a gap in the same sentence, and the answer is a price-ordered list
rather than a form. That idea is not a template, and the heading's scale,
weight, and wrapping carry it without an illustration, a logo or a webfont. The
table is category-standard, which is correct here.

Where the idea thinned was at the hand-offs rather than in the composition:
the entry, the £0 recovery and the row's own times. All three landed on
20 October 2026 and are rows in `docs/settled-work.md` rather than findings here.
What still costs the reading is the phone's first screen: the composition is
authored, and the screen a reader on a phone meets first does not yet contain the
answer (S5).

**Deterministic scan.** `impeccable detect --json` over the three built routes
returned one finding, `cramped-padding` on `.origin-slot-wrap`, the station
slot's dashed underline. It is the same finding the 14 October pass rejected and
for the same reason: the underline is the affordance, not a padded box. It is
not re-filed. No other rule fired on any route.

**Visual overlays.** Not attempted. The detector was run against the three built
HTML files, and the page was inspected through the preview pane rather than
through a script-injected overlay. No user-visible overlay is claimed.

## Overall impression

The page is closer to its own idea than it was on 17 October: the fold holds a
row at 1366, the phone row is two lines, the disclosures share one mark, and the
empty state's doors are the right shape. The pass's own next step was not a
visual one but the three hand-offs — the chooser's field, the £0 recovery and the
row's own times — and all three landed on 20 October 2026. What is left is S5:
the phone has no fold budget, so on the first screen the page still does not
answer its own question.

**Priority issues, in order:** S5 (a phone with no fold budget). The other
three -- the row with no times, the field that did not look like one, and the
doors that opened onto nothing -- landed on 20 October 2026.

## What is working, and should not be traded away

- **The budget's two controls and the sentence they sit in.** The field and the
  slider do the same job and both earn it: one types, one drags. The count line
  follows a drag in 6–14ms on this 8–20-row list, measured with
  `performance.now()` around the input event. That is the page's signature and
  it works.
- **The row's honesty.** "No service that day" is used instead of a zero, an
  undescribed restriction says so in the row's own panel and carries its code,
  and "Two tickets" names the split. A conversion-first page would have hidden
  all three.
- **The phone row.** Two lines, 112px at 390px, with the shortlist box, the
  ticket link and the expander each reaching 44px. The earlier six-line row is
  gone. The desktop header is sticky, and the phone layout keeps a real table
  for assistive technology.
- **The accessibility floor is measured, not asserted.** Every visible text node
  in both palettes cleared 4.5:1 in this pass (0 failures), the focus ring is a
  2px accent outline on every control, and the phone layout did not scroll
  sideways at 320, 390 or 1366.

## Findings and numbered suggestions

Severity: P1 breaks or misleads a reader now, P2 costs real effort, P3 is polish.

### S5 [P2] The phone has no fold budget, and at 320×640 it has no answer above it

Measured on arrival, with the refinements folded:

| Viewport | First row top | Fold | One whole row above? |
|---|---|---|---|
| 1366×768 | 690 | 768 | yes (row bottom 754) |
| 390×844 | 786 | 844 | no; 58px of the row is visible |
| 320×640 | 858 | 640 | no; nothing |

The laptop fold was given a stated budget by the 17 October pass (one whole row
at 1366×768) and is now held by a browser check. There is no equivalent for the
phone, which is the first encounter the product describes. At 390 the chrome
above the row is 786px: banner 79, theme row 44, heading 73, first-use 48, filter
bar 364, link terms 24, summary 48. At 320 the same stack plus the wrapped hint
and day help is 858px.

**Why it matters.** A community link opened on a phone shows a heading, a slider,
a folded filter bar and a note before it shows a single destination. The page's
promise is "17 destinations for £20"; the first screen does not contain one. The
320 case is the 200% zoom case too, so the reader who zooms for legibility is the
one who sees no answer at all.

**Fix.** Set a phone budget the way the laptop one was set — "at 390×844 the
first row starts above 760px; at 320×640 above 620px" — and buy it from the
stack: hide the key hint on coarse pointers (S10, 19px, taken on 19 October 2026
and no longer available to spend), trim the budget hint to one line at 390 (the
budget-hint cut, about 19px), and shorten the first-use note to one line ("Click
the station name to start elsewhere.", 24px saved), updating the two browser
assertions that quote the old wording. With the hint gone that leaves 43px of the
62px this finding first counted, so the 390 target needs re-measuring before it is
claimed. At 320 the filter bar itself is
403px; the wrapped hint and the taller day control add about 39px, and the heading is
three lines (107px). The 320 target may need the banner to be one line there or
the heading's vh term lowered again; state the budget first, then choose.

**Verify.** Add the two measurements to `tests/browser/station-layout.cjs` beside
the 1366 one, with the banner on the page.

**Suggested command:** `$impeccable adapt`.

## Persona red flags

The obstacles each reader met on the 19 October build, pruned to the ones still
open. The rest landed on 20 October 2026 and are rows in
`docs/settled-work.md`.

**Casey, phone, one hand, interrupted.** The first destination starts at 786px
on an 844px screen; at 320 nothing is visible (S5). The budget is 2,372px above
the last row. The two-line row and the 44px actions are good; the page above them
is the cost. The dock survives a scroll, but it has no total (DL3 of the delight
pass).

**Sam, keyboard and screen reader.** The focus ring is clear and every control is
reachable; the table keeps its headings for assistive technology when the phone
layout clips them. The two losses this pass measured — clearing the shortlist
dropped focus to `<body>`, and the cheapest row's panel gave no times without
saying why — landed on 20 October 2026. The count line is a polite live region,
so a budget drag is announced.

## Minor observations

- The opened refinements panel leaves a 160px void in its left column, because
  the ticket-type fieldset is short and the party/railcard column is tall. The
  panel is a two-column grid with one long row and one short one.
- The heading's budget field is 37×36px on a phone; it meets the 24px floor the
  matrix holds every target to, and sits under the 44px the row actions promise.
  The field is the identity's own interaction, so the 44px promise is worth
  deciding deliberately rather than by omission.
- The privacy page is 1,468px tall at 1366 and 600px wide, with the document
  starting at 127px. Its body is the best-measured prose on the site.

## Questions to consider

- What is the phone's fold budget, in numbers, and who owns it? The laptop has
  one and a check; the phone has neither (S5).
- Should the heading's budget field be held to the 44px the row actions promise?
  The field is the identity's own interaction, so the answer is a decision rather
  than an omission.

## Run notes

- **Target:** the three routes above; the worktree root as the target path.
- **Ignore list:** `.impeccable/critique/ignore.md` does not exist; nothing was
  suppressed.
- **Assessment independence:** not achieved. One thread ran the design read and
  the browser/detector evidence; the design read was written first, and the
  detector output is reported after it. This is the degraded banner at the top.
- **CLI detector:** one finding, `cramped-padding` on `.origin-slot-wrap`,
  assessed as a false positive (the underline is the affordance) and not
  re-filed.
- **Browser:** Chromium at `127.0.0.1:8801`; 1366×768, 390×844, 320×640; both
  palettes; 0 console errors, 0 page errors. Contrast: every visible text node
  in both palettes at or above 4.5:1 (computed over the composited background,
  0 failures).
- **Snapshot:** not written to `.impeccable/critique/`; this pass's archive is
  this file in `docs/audits`, as asked. No trend line is claimed.
- **Server:** `python -m http.server 8801 --directory _demo_site`, stopped after
  the run.
- **Temp files:** the Playwright probes live in the system temp directory, not
  the repository. The screenshots referenced above are in `screenshots/` in the
  worktree and are not part of the audit's source.
