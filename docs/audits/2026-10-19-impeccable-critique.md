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
**Status:** three of its twelve findings landed on 19 October 2026 and are
removed from this file rather than left to be re-derived: S6 (the empty list's
duplicate sentence and its empty table head), S9 (the shortlist's invisible copy
confirmation) and S10 (a keyboard hint shown to a phone, naming two keys). Each
is a row in `docs/settled-work.md` with the check that holds it. The score below
is the one measured before those fixes; nine findings still ask for work and
that is why this review stays.

## Design health score

| # | Heuristic | Score | The finding that costs it |
|---|---|---|---|
| 1 | Visibility of system status | 3 | The count line, the live regions, the freshness line and the URL all report state. A row whose panel has no times says nothing about it (S1). |
| 2 | Match system / real world | 3 | "Restricted" loses its column label on a phone and its definition is about 2,000px below (S4); "your station" reads as a value rather than an instruction (S2). |
| 3 | User control and freedom | 3 | Every filter clears, the budget clamps, and the URL is an undo. Clearing the shortlist still drops focus to `<body>` (S7). |
| 4 | Consistency and standards | 2 | The chooser has no first-use note while the station page does (S2). |
| 5 | Error prevention | 4 | No input can produce an error: the budget clamps, chips are withdrawn when they would empty the list, and the page has no dead ends. Genuinely good. |
| 6 | Recognition rather than recall | 2 | The ticket sets are chosen before they are explained (S8); the fare vocabulary lives in the footer, not where it is chosen; the chooser's list gives a bare count; a phone row's second line has no labels (S4, S11). |
| 7 | Flexibility and efficiency | 3 | `/`, `b`, `n` and `p` exist and the pager works. |
| 8 | Aesthetic and minimalist design | 3 | At 1366×768 one whole row is above the fold; at 390×844 58px of one row is; at 320×640 no row is (S5). The opened refinements panel is 315px. |
| 9 | Error recovery | 2 | The empty state offers four doors at £0, and three of them lead to another empty list (S3). |
| 10 | Help and documentation | 4 | The method fold, the trade-word glossary, the privacy page and the provenance line are thorough and in the right place. |
| **Total** | | **29/40** | **Good (73%). An authored page with three P1s at its hand-offs.** |

## Design specificity verdict

**LLM assessment.** The authored idea is still the strongest thing on the site:
the question is the control. The budget is a gap in a sentence, the starting
station is a gap in the same sentence, and the answer is a price-ordered list
rather than a form. That idea is not a template, and the heading's scale,
weight, and wrapping carry it without an illustration, a logo or a webfont. The
table is category-standard, which is correct here.

Where the idea thins is at the hand-offs rather than in the composition.
Entering on the chooser, the one control the page exists for looks like the rest
of the heading; recovering at £0 leads back to £0; opening the cheapest row can
show no times at all; and on a phone the second line of a row drops the column
names that make "Restricted" mean a fare. The page reads as authored at the
question and assembled at the entry, the recovery and the row. The visual world
is coherent; the behaviour at its edges is what costs this reading.

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
empty state's doors are the right shape. The next pass is not a visual one. It is
the three hand-offs — the chooser's field, the £0 recovery and the row's own
times — where the page stops behaving like the sentence it opens with. Fix those
and the restraint stops being a place where controls go missing.

**Priority issues, in order:** S1 (a row with no times), S2 (a field that does
not look like one), S3 (doors that open onto nothing), S5 (a phone with no fold
budget), S8 (the ticket sets chosen before they are explained).

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

### S1 [P1] The cheapest row can open a panel with no times, and say nothing about it

At £20 the NOTTINGHAM row reads £7.00, 45m, Direct. Its expander opens a panel
containing the restriction sentence, the feed record and "Copy journey" — no
departures, no note. The payload explains it: the row is priced on the
`singleDestinations` record (`SDS`, `departures: []`), while the `destinations`
record for the same station (`CDR`, £11.60) carries four departures. LINCOLN, one
row down, opens onto two departures, so the omission is not the timetable
refusing the day; it is the cheaper fare set not carrying the times the other set
has.

**Why it matters.** `PRODUCT.md` promises "an expander holding the next few
departures", and the row states a duration and a change count. A reader who
opens the cheapest row to plan the day gets a panel that looks broken, or worse,
concludes the page has no times. "Say the unflattering thing on the page" is
principle 2; this is the one place it is not said.

**Fix.** Attach the departures to the journey (the legs the row shares) rather
than to one fare record, so every fare set that prices the same journey opens
onto the same times. If a fare set genuinely has no departures, the panel must
say so in one sentence — "This build has no departures for this fare; 45m is the
fastest journey" — beside the time it explains.

**Verify.** A browser check that every row with a positive duration and
`journeyState: "found"` opens either at least one departure or the sentence.The synthetic fixture already has the two cases (NOT and LCN).

**Suggested command:** `$impeccable harden`, then `$impeccable clarify` for the
sentence.

### S2 [P1] The chooser's station field looks like the heading, not a control

`Train fares up to £20 from your station` is a sentence with a field in it, and
the field is the page's whole job. It has an underline and, because the page
focuses it on load, a caret; it has no visible instruction, no label and no word
that says typing is possible. The station page spends a 24px sentence on exactly
this ("Click the station name to start from somewhere else."); the chooser spends
nothing. Its fallback is a list capped
at 40 stations, so on the real release a reader whose station is not in the first
40 has to discover the field or leave.

**Why it matters.** The page is reached from a community post by a first-timer
who is deciding in seconds whether the site is worth a click. "Your station" is
a value phrase, not a verb; a reader can reasonably read the whole line as a
title. This is the one control where the identity's restraint turns into an
invisible affordance.

**Fix.** One short line under the heading, in the station page's own voice:
"Type your station's name, or pick one below." Keep the heading as it is. If the
line is judged too much, make the placeholder a verb ("type a station") and keep
the line for the empty list only. Either way it must be visible before the list,
not a tooltip.

**Verify.** The chooser's browser suite reads the line from the page and the
field's accessible name; a first-time walkthrough should reach a station without
opening the list.

**Suggested command:** `$impeccable clarify`.

### S3 [P2] Three of the four empty-state doors lead to another empty state

At £0 the empty state offers "Raise the budget to £7.00", "Show the 21 Anytime
Day Returns", "Show the 22 returns" and "Show the one single". Measured: clicking
"Show the 21 Anytime Day Returns" switches the ticket mode to Anytime and leaves
the budget at £0, so the list stays empty and the empty state now offers "Show
the 22 cheapest fares". The three set doors change the filter; they do not open
the door they name. The "Raise the budget" door is the only one that produces a
destination.

**Why it matters.** This is the state where a reader is most likely to leave, and
the page's best recovery idea is spent on three labels that promise a result and
deliver another apology. It also exposes a scope problem: "21 Anytime Day
Returns" is a whole-feed count, while the count line above the table is the
within-budget mix; the two numbers sit in the same state without saying they are
different sums.

**Fix.** Make each set door set the budget to that set's cheapest fare (the payload already has it) and switch the mode, so the label is true. If a set has
no fare inside the current ceiling, do not offer the door. Name the floor on the
label — "Anytime Day Returns, from £6.40" — and move the whole-feed count to a
clause that says so ("21 in the feed"), so both numbers have a scope.

**Verify.** A browser test at `?budget=0` that every door leaves a non-empty
list, and that the button's label and the resulting count agree.

**Suggested command:** `$impeccable harden`.

### S4 [P2] On a phone, "Restricted" loses the column that explains it

At 390px the `<thead>` is clipped for assistive technology and the row's second
line reads "45m · Direct · Restricted · Tickets". The word "Restricted" is the
fare type, but nothing on the visible row says so; the glossary that defines it
is in the footer, about 2,000px below. "Regular" has the same problem and is
the common case, so it reads as a third fact about the journey rather than a
quiet default.

**Why it matters.** The fare type is the distinction the page exists to make —
"the headline is a one-way price list" is a fact a reader has to be able to read
off the row, not recover from a footer. On a phone the row's compactness is
paid for by the one label that carries the product's honesty.

**Fix.** Let the cell's text carry its noun: "Restricted fare" / "Regular fare"
(or "Advance fare"), which adds five characters and survives the flex row at 390
and at 320. The row's disclosure already carries the condition, so the cell only
needs the category.

**Verify.** The 390px layout check asserts the visible fare cell includes "fare",
and the row still fits two lines at 390 and three at 320.

**Suggested command:** `$impeccable clarify`.

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

### S7 [P2] Clearing the shortlist drops focus to `<body>`

Measured: focus `#shortlistDockClear`, press it, and `document.activeElement` is
`BODY`. The dock removes itself with the focus inside it. The 17 October review
fixed the same class of loss when the budget closed an open row; this is the
remaining one.

**Why it matters.** A keyboard or screen-reader reader who clears the list is
returned to the top of the document with no announcement of where they are. The
page already has a status region for the clear; the focus is the half that is
missing.

**Fix.** Before removing the dock, move focus to the summary line (or the first
row's checkbox when a row exists) and announce "Shortlist cleared." Keep the
status region. The same rule the row's own panel follows when it closes.

**Verify.** A browser check that presses Clear from the keyboard and asserts the
active element is not `<body>` and that the status names the clear.

**Suggested command:** `$impeccable harden`.

### S8 [P2] The ticket-set vocabulary is still chosen before it is explained

The refinements panel offers four ticket sets — "Cheapest available", "Anytime
Day Return", "Any return", "Single" — with no clause saying what each contains.
The sentence that defines them is `#modeNote`, which sits at 1,778px on the demo
page, below the table (which ends at 1,775px) and about 1,200px below the control
when the panel is open at 1366; on a phone it is at 2,694px on the page. The empty state
asks the same vocabulary of a reader who is already lost: at £0 it offers "Show
the 21 Anytime Day Returns", "Show the 22 returns" and "Show the one single"
side by side.

**Why it matters.** The four sets are the product's central distinction — a
restricted return is a real price, an unrestricted Anytime Day Return is the
return the page promises, a single is the headline's unit. A reader choosing a filter is
choosing which of those questions to ask; a reader who has to open a footer or
scroll past the answer to learn the difference will leave the default on without
knowing what it excludes.

**Fix.** Put one clause on each option where it is chosen: "Anytime Day Return
(unrestricted)", "Any return (may be restricted)", "Single (one way)", and let
"Cheapest available" stay bare because it is the default. Keep the full note
below the table for the reader who wants the arithmetic. Alternatively, move a
one-sentence version of the difference directly under the fieldset and leave
only the counts below the table.

**Verify.** The opened panel's four labels each carry a clause (or the note is
within 100px of the fieldset); a browser check reads the labels and the note's
position.

**Suggested command:** `$impeccable clarify`.

### S11 [P3] The chooser's destination count is a bare number

The list reads "GRANTHAM GRN 22", "NOTTINGHAM NOT 6", "LINCOLN LCN 6". The
number has an `aria-label` ("22 destinations") and a `title`, so a screen reader
is told what it is; a sighted reader sees a number after a code with nothing above
it that names the column. The heading "Destinations this feed prices" says what
the list is, not what the third column is.

**Why it matters.** The count is the one piece of evidence that tells a reader
whether a station is worth opening; it should not need a hover to decode.

**Fix.** Put a small column line above the grid — "Station · Code · Destinations"
— or write "22 destinations" in the row where the title currently is. The first
keeps the row clean; the second is unambiguous at the cost of a wider row.

**Verify.** A chooser screenshot at 1366 and 390, plus the existing accessible
name check.

**Suggested command:** `$impeccable clarify`.

### S12 [P3] The privacy page's title is a single word

`<title>Privacy</title>` against "Train fares up to £20 from GRANTHAM" and
"Train fares up to £20 · pick your station". In a row of tabs it is the only
route whose title could belong to any site.

**Fix:** "Privacy · Train fares", or the release's own name once `PRODUCT.md` has
one. The name is explicitly undecided, so the generic form is the honest one for
now.

**Verify:** the privacy template test asserts the title contains "Train fares".

**Suggested command:** `$impeccable clarify`.

## Persona red flags

**Jordan, first timer, arrives from a community post.** On the chooser, "your
station" reads as the end of a title; there is no line telling them to type, and
the list is a directory rather than a prompt (S2). On a station page, "Restricted"
is the third word on the row's second line with no column label on a phone (S4),
and the sentence that defines it is in the footer. At £0, three of the four
doors lead to another empty list (S3). Jordan can use the page only after
guessing the field and the vocabulary.

**Casey, phone, one hand, interrupted.** The first destination starts at 786px
on an 844px screen; at 320 nothing is visible (S5). The budget is 2,372px above
the last row. The two-line row and the 44px actions are good; the page above them
is the cost. The dock survives a scroll, but it has no total (DL3 of the delight
pass).

**Sam, keyboard and screen reader.** The focus ring is clear and every control is
reachable; the table keeps its headings for assistive technology when the phone
layout clips them. Clearing the shortlist drops focus to `<body>` (S7), and the
cheapest row's panel gives no times without saying why (S1). The count line is a
polite live region, so a budget drag is announced, but the empty state's doors
switch modes silently apart from the status.

## Minor observations

- The station page sets eight type sizes at 1366, six of them between 11.5px and 14.4px
  (`11.52`, `12`, `12.8`, `13.6`, `14.4`, `16`, `18.4`, `69.12`). The trust
  content is at the small end; it measures 4.5:1 or better, but the hierarchy is
  carried by six near-neighbours.
- The opened refinements panel leaves a 160px void in its left column, because
  the ticket-type fieldset is short and the party/railcard column is tall. The
  panel is a two-column grid with one long row and one short one.
- The budget hint is 117 characters: one line at 1366, two at 390, three at 320.
  It names the party and the mode, which is the right content; the length is the
  cost.
- "Show the one single" is grammatical but reads oddly beside "Show the 22
  returns"; "Show the single" is the same offer in four fewer characters.
- The empty state's counts (21 Anytime, 22 returns, 1 single) and the count
  line's mix (16 returns, 1 single at £20) are different scopes. S3 asks for the
  floor on the door; the labels should say "at any budget" if they keep the
  whole-feed count.
- The heading's budget field is 37×36px on a phone; it meets the 24px floor the
  matrix holds every target to, and sits under the 44px the row actions promise.
  The field is the identity's own interaction, so the 44px promise is worth
  deciding deliberately rather than by omission.
- The chooser's page fits 768px exactly at 1366 with the demo's three stations.
  The release caps the list at 40, so the page grows by 37 rows there; the
  header and the list heading are the only things above it.
- The privacy page is 1,468px tall at 1366 and 600px wide, with the document
  starting at 127px. Its title is S12; its body is the best-measured prose on the
  site.

## Questions to consider

- If the chooser's field is the page's only control, why is the station page the
  only route that explains its control?
- Should a door at £0 be allowed to switch ticket mode when the budget cannot
  reach that set? A door that changes the question without changing the answer
  is worse than no door.
- What is the phone's fold budget, in numbers, and who owns it? The laptop has
  one and a check; the phone has neither.
- When a fare set has no departures, is the row's speed a promise or a summary?
  The page currently treats it as a promise and then withholds the evidence.
- Can "Restricted" be understood from the row alone, or is the glossary's
  position an admission that it cannot?

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
