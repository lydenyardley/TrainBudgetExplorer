# Impeccable critique: the chooser, the station page, the privacy page

**Date:** 17 October 2026
**Reviewed:** the worktree at `main` with that day's uncommitted changes (the
provenance and railcards work, and the new "words this page uses" block).
**Mode:** Operate, as the 14 October critique recorded: every route is a tool used
to answer one question, and the design's job is to get out of the way of the
answer.
**Routes:** `/` (the chooser), `/from/grantham/` (a station page with fares and a
timetable), the same station page built prices-only
(`_shape_site/prices-only/`, the shape the deploy workflow publishes), and
`/privacy/`. There are three routes, not 2,712: `/from/<station>/` is one page per
priced station and differs only in its rows, so a finding about the page's chrome
or its table is route-wide, and a finding that quotes a figure says which page it
came from.
**Artifact:** `_demo_site`, built on 16 October 2026 from `_demo_feed` and
`_demo_kb` at service date 5 October 2026, served at `127.0.0.1:8801`; the
prices-only page at `127.0.0.1:8802`.
**Method:** ⚠️ DEGRADED: single-context, in part. The detector and the browser
evidence were run in this thread, because no sub-agent available to this session
has a terminal or a browser, and a design review written from source alone would
have been the blind assessment the skill's two-agent rule exists to prevent. The
design read below is anchored by measurements taken from the live DOM rather than
by memory of the source. Screenshots were captured at 1280×900 and 390×844 for
the station page, the chooser, the open refinements panel, the empty state, an
open row and the shortlist dock; after the light-theme switch the webview stopped
compositing and no further frames could be captured, so everything the light
theme contributed below is computed-style measurement rather than sight.
**Measurements:** a Playwright script at nine widths (360 to 1440) and four
viewport heights, plus computed style, geometry, accessible names and console
output from the preview browser. Figures are of this demo build, not of the real
feed's 2,712-page release; the demo's handful of destinations is enough for layout
and not enough for the paging arithmetic, which is stated as arithmetic.
**Not re-filed:** the one detector finding (see Run notes), and every item the 14
October critique already closed. Its item 7 is answered in this worktree by the
footer's "The words this page uses" block and is not repeated here.
**How to prune this document:** each finding keeps its number when it lands, so
the gaps in a later version are deliberate. A finding that lands leaves with a row
in a "what landed" table naming the test that holds it, the way the 14 October
document is kept.

## Design health score

| # | Heuristic | Score | The finding that costs it |
|---|---|---|---|
| 1 | Visibility of system status | 3 | The count line, the live regions and the freshness line are good. The page does not say that reopening a row has closed it, and the budget slider carries its value only in the heading (C9). |
| 2 | Match system / real world | 3 | "Cheapest available", "Any return", "Restricted" and "Two tickets" are the trade's words, defined once in a footer disclosure rather than where they are chosen (C21). |
| 3 | User control and freedom | 3 | Every filter can be cleared, but nudging the budget closes the row the reader opened, and a shortlist Clear has no undo (C8). |
| 4 | Consistency and standards | 2 | A phone's row is a different, broken object from a desktop row (C1, C2); three disclosures look like prose (C6); the chooser's footer nav is not the station page's (C16). |
| 5 | Error prevention | 3 | The budget clamps, chips are withdrawn when they would empty the list, and there are no dead ends. Genuinely good. |
| 6 | Recognition rather than recall | 2 | The explanation of the ticket set sits below the table that it governs, and the fare vocabulary lives inside each row's own panel (C12). |
| 7 | Flexibility and efficiency | 2 | No keyboard shortcut reaches the budget or the pager, and on a phone a page of twenty rows is about 5,500px of scrolling before Next (C13). |
| 8 | Aesthetic and minimalist design | 2 | On a 1366×768 laptop the first destination row starts 724px down: the fold is spent on a 208px heading, a slider, a folded filter bar and four note lines (C3). |
| 9 | Error recovery | 3 | The empty state offers four concrete ways back. It also says the reason twice, in the same words (D2 of the distill). |
| 10 | Help and documentation | 3 | Provenance, the method disclosure and the new glossary are thorough and in the right place. Two of the three are invisible as disclosures (C6). |
| **Total** | | **26/40** | **Acceptable (65%). A careful page with three defects a reader meets immediately.** |

## Design specificity verdict

**LLM assessment.** One idea on this site is genuinely authored, and it is the
same idea on both working routes: the page's question is the page's control, so
the budget and the starting station are gaps in a sentence rather than fields in a
form. That is not a template anyone else ships, and the rest of the composition
follows from it: a filter bar that folds, a count line that belongs to the table,
provenance moved below the answer. The table itself is category-standard, which is
correct for Operate, and the typographic treatment of the heading is the identity
carrier.

What is not authored is the behaviour of that identity at the edges. On a phone
the table's own layout breaks the station cell into four lines and collides the
last cell's label with its link, so the one component a reader came for is the one
that looks unfinished. Below the table, the trust content is set in 12.8px lines
140 to 180 characters wide, which is the opposite of the care the heading gets.
The page reads as authored at the top and assembled at the bottom.

**Deterministic scan.** `impeccable detect --json` over the three built routes
returned one finding, `cramped-padding` on `.origin-slot-wrap`, which is the
station slot's dashed underline. It was assessed and rejected on 14 October for
the same reason it is rejected now: the underline is the affordance. It is not
re-filed.

## What works, and should not be traded away

- **The sentence is the control.** Two gaps in a question, the caret in one and
  the cursor in the other, on both routes. It removes a label, a field and a
  "Search" button from the top of the page and it is the reason the site does not
  look like a fare-enquiry form.
- **The page publishes its own limits where the limits bite.** "No service that
  day" in the Time column, "Unknown" in Changes, the restricted-fare sentence in
  the row's own panel, the count line naming the mix of ticket types. A competitor
  optimising for conversion would have hidden all four.
- **The empty state is a set of doors, not an apology.** At £0 it offers a raised
  budget and each ticket set that would fill the list, with the counts named.

## Findings

Severity follows the critique scale: P1 breaks or misleads a reader now, P2 costs
them real effort, P3 is polish. Route is named per finding.

### The station page

**C1 [P1] A phone's station cell is four fragments, not a name.**
`page/station/row-cells.js:53` builds the cell as
`cell.append(name, " (", code, ")")`, so three bare text nodes sit beside the two
spans. Below 44rem the cell becomes a two-track grid (`page/station.css:477`) and
`td > *` sends elements to track two (`:486`), while a bare text node has no
element to match, so it is auto-placed in track one. Measured at 390px: the name
and the code sit at x=101, `(` and `)` at x=12, one per line. A reader sees

> STATION  NOTTINGHAM
> (        NOT
> )

Every row, every phone, every station page. Fix: one wrapper element around the
whole value, or a rule that also covers text nodes; the wrapper is the smaller
change and the one a check can assert. This is the single most visible defect on
the site.

**C2 [P1] The last cell's label collides with its link: "TICKETSTickets".**
Below 44rem `td:first-child, td:last-child { display: block }`
(`page/station.css:489`) takes the Tickets cell out of the grid, so its
`::before` label is inline with its content. Measured at 390px, the cell is **1px
wide** at x=12, its label paints from x=12 and its link starts at x=60: the two
read as one word, and the expander button sits immediately after. The 1px width is
the second half of the same fault: the cell has collapsed and everything inside it
is overflowing. Fix: give the last cell the same two-track treatment as the rest,
or suppress its `::before`; assert both the label's absence and a 44px minimum cell
width.

**C3 [P1] On a common laptop the answer starts below the fold.**
Measured with the demo's 38px synthetic banner, which production does not carry;
subtract 54px for the real page. First destination row:

| Viewport | First row top | Rows in view |
|---|---|---|
| 390×844 | 872 (818) | 0 |
| 1280×720 | 760 (706) | 0 |
| 1366×768 | 778 (724) | 0 (44px of one row) |
| 1440×900 | 794 | 2 |
| 1920×1080 | 829 | 5 |

The heading alone is 208px at 1366 and 243px at 1920, at `clamp(2rem, 7vw, 7rem)`,
and four blocks sit between it and the count line: the intro paragraph, the filter
bar (which holds the slider, the folded refinements and the day control), the
freshness line and the ticket-link summary. The heading is the identity carrier
and should not be shrunk to a form label, but the fold is a budget and this page
spends all of it above the table. Fix options, cheapest first: drop the intro
paragraph's first sentence (it repeats the count line), fold the freshness line
into the link-terms disclosure, and cap the heading at `6rem` with a `vh` term so
a short laptop gets a smaller question. Recommendation: measure a 1366×768 build
and require at least one full row.

**C4 [P2] The page's trust content is the least readable text on it.**
Every footer paragraph spans the full 1,176px at 1280, at 13.6px and 12.8px with
20.4px leading. Measured characters per line: 155, 177, 178, 148, 141, 127, 124.
The railcard paragraph (424 characters) runs at 141 characters per line. The body
copy above it is held to `75ch`; the footer, which is where the page keeps its
honesty, is held to nothing. Fix: one `max-width: 75ch` on the footer, or a
`--measure` token the `.sub` rule already implies.

**C6 [P2] Three disclosures look like prose.**
"About the ticket link" (24px tall), "Where these prices come from…" and "The
words this page uses" are `<summary>` elements with no marker, no chevron, no
underline and the body colour. Measured: 143×24 at 390 and 24px tall at 1280. They
sit in a column of muted paragraphs, so the reader has no way to know two of them
open. The page already has one drawn disclosure mark (`CHEVRON`, used by the
filter bar and the station slot and the row expander); the summaries are the only
disclosures on the site that do not use it. Fix: the same chevron, and the same
`aria-expanded` behaviour the filter bar has.

**C7 [P2] The row's two actions have inverted weight.**
The primary action is "Tickets", a 48×22 link with an 11px invisible slop ring.
The secondary action is a 44×44 bordered button with a chevron. Measured at 1280:
44×44 for the expander, 48×22 for the link. The row's target sizes are legal
(WCAG 2.5.8 is met by the slop, and the checkbox sits in a 44px label: the eleven
sub-24px boxes the measurement finds are all enclosed), but the eye is drawn to
the disclosure rather than to the purchase. Fix: give the link the bordered
treatment and the expander the bare one, or leave both bare.

**C8 [P2] Changing the budget closes the row the reader opened.**
Measured: open a row, type a new budget, and `aria-expanded` goes from `true` to
`false` with zero detail rows left. `rows.replaceChildren()`
(`page/station/table.js:153`) rebuilds every row, and the panel's open state is
not carried across. The budget is the page's primary control, so this is a lost
place, not a lost pixel: the reader who opens Peterborough to read its conditions
and then nudges the budget has to find Peterborough again. Fix: keep the open CRS
in a variable and re-open it after the render, as the shortlist already keeps its
own list across renders.

**C9 [P3] The budget has two controls and one of them is unlabelled on screen.**
The heading field and the slider are the same value, 90px apart, and the slider's
only visible name is the 130-character hint beside it ("Drag to change the budget
in the heading. It stops at the highest fare…"), which wraps to two lines at 1280
and three at 390. Its accessible name is the `<label class="sr-only">`. Keep both
controls; cut the hint to the ceiling fact, which is the only thing the reader
cannot infer ("Stops at £126, the highest fare in this list").

**C10 [P3] The page's one instruction is in the wrong place.**
"Click the station name to start from somewhere else" is how a reader learns that
the heading's station is a control, and it sits in body copy 250px below the word
it describes, in the same paragraph as a sentence about what the list contains.
The station slot has no visible label of its own: its accessible name is "Change
starting station: GRANTHAM", which is right for a screen reader and invisible to
everyone else. Fix: attach the instruction to the control (a title, a hinted
underline, or the picker's own first line) and drop the rest of the paragraph
(D1).

### The chooser

**C11 [P2] The filtered list appears 200px below the field that opened it.**
Typing in the heading's station field switches `#picks` to a fixed-position panel
placed at the list's original document position. Measured: the field's bottom is
at y=349 and the panel's top at y=552 at 1280 (a 204px gap); 223px at 390. In
between sits the intro prose, which the panel does not cover, so the menu looks
detached from the sentence and floats over the paragraph and the footer note. The
comment in `page_templates.py` says anchoring to the list keeps prose clickable,
and it does; the cost is that the answer is nowhere near the question. Fix: anchor
the panel to the field (the station page's picker already does exactly this) and
let the prose below the fold stay where it is.

**C12 [P2] Every station row repeats the same phrase.**
"6 destinations this feed prices" is the last third of every row. In the demo
that is three repetitions; on the real release it is 2,712, and the phrase is the
same in all of them. The row is a name, a code and a count, and the count has no
heading of its own. Fix: a heading for the list that carries the phrase once
("Destinations this feed prices"), and a bare number per row.

**C13 [P2] Twenty rows at 275px is 5,500px of scrolling to reach Next.**
Measured row height on a phone: 275px at 360, 390, 414, 640 and 704, against 61px
at 768 and above. `PAGE_SIZE` is 20 (`page/station/filters.js:7`), so a phone page
is 5,500px of rows before the pager, and the real Grantham page holds 334
destinations. That is arithmetic from a measured row height, not a scroll test.
The stacked row is the right call (a seven-column table cannot fit 390px); its
height is the defect: the label column, the value column, the site-proof subline
and the action line add up to five or six lines per destination. Fix: two lines
per row on a phone, name and price on the first, time and fare type on the second,
with the actions in the row's own disclosure. This is also the change that makes
C1 and C2 disappear rather than be repaired.

**C14 [P3] The empty heading reads "from station".**
With nothing typed, the sentence is "Train fares up to £20 from station". The
placeholder is the muted word "station" under a dashed underline, and the
instruction below explains it. It is not wrong, it is not English either. Fix: the
placeholder is the prompt ("your station"), which is a word the sentence can take.

**C15 [P3] Three paragraphs of equal weight before the list.**
Instruction, provenance line and ordering note, at 18.4px, 13.6px and 13.6px,
each its own paragraph. The ordering note is the one that is genuinely about the
list ("most first — not by how busy it is, and not by how near it is"), and it
reads as another apology. Fix: the ordering note becomes the list's heading
subtitle (C12's heading), the provenance line stays, the instruction folds into
the field's placeholder (C14).

**C16 [P3] The chooser's footer is not the station page's footer.**
`Privacy.` alone, as a paragraph. The station page's is `Station list · Privacy`
in a `nav`. A reader who came from a station page and went back has one link where
they had two. Fix: the same `.footnav`, with the current route omitted.

### The privacy page

**C17 [P2] Three bullets say one thing.**
"No cookies are set by this site." / "No analytics run. If analytics are ever
added to this site, this page will name them here first." / "This site does not
collect visit data." The third is the union of the first two and adds a claim
(visit data) that the second has already narrowed. Fix: two bullets, cookies and
analytics, and keep the forward promise attached to analytics where it belongs.

**C18 [P3] The page's title is a single word.**
`<title>Privacy</title>`, against "Train fares up to £30 from GRANTHAM" and "Train
fares up to £20 · pick your station". In a row of tabs a reader looking for the
fare page has three titles and one of them is indistinguishable from any other
site's privacy notice. Fix: "Privacy · Train fares" or the release's own name once
there is one (it is undecided, `PRODUCT.md`).

**C19 [P3] The first thing on the page is a back link, then a switch, then the
title.**
The back link is outside `main` (correct for the landmark), the theme switch is
pinned right and sits between the link and the heading, so the reading order on a
900px screen is: banner, link, switch, "Privacy". It is the only route where the
heading is not the first thing under the banner. Fix: put the switch after the
heading on this route, or accept it as chrome and align it with the back link.

**C20 [P3] The build date is the page's only date, in the page's voice.**
"This notice describes the build dated 17 October 2026." That is a sentence for a
maintainer. A reader wants to know when the policy changed, which is the same date
on a static site, phrased as a fact about the notice. Fix: "Last updated 17 October
2026" and drop the sentence.

### Cross-route

**C21 [P2] The ticket-set vocabulary is chosen before it is explained.**
The four options are "Cheapest available", "Anytime Day Return", "Any return"
and "Single", and the paragraph that defines what the chosen set contains sits
below the table (`#modeNote`), more than a screen away from the control once the
panel that holds it is open. The empty state asks the same vocabulary of a reader
who is already lost: at £0 it offers "Show the 7 Anytime Day Returns", "Show the
8 returns" and "Show the one single" side by side. The new "The words this page
uses" block defines the terms correctly and is in the right place for a reader who
has already decided to check; it is the wrong place for a reader choosing a
filter. Fix: one clause per option in the control itself ("Anytime Day Return
(unrestricted)"), or the mode note moved directly under the ticket-type field and
shortened to the difference between the sets. This is not the 14 October
critique's item 7, which is answered: that was where the words are defined, this
is when.

## Persona red flags

**Sam, screen reader and keyboard only.** The table's column headers are removed on
a phone and replaced by `::before` labels, which are read as part of the cell, so
the reading order per row is "Shortlist, Station, NOTTINGHAM, (, NOT, ), Price,
£7.00…" with the fragments announced separately. The row's own panel is announced
correctly (`aria-expanded`, a labelled region). Two focus losses: clearing the
shortlist hides the dock with focus inside it, and changing the budget destroys
the row that held focus (C8). Both drop focus to `<body>`.

**Casey, phone, one hand, interrupted.** 275px rows mean three destinations per
screen and no sense of a list; the count line is 872px down; the pager is 5,500px
further. Nothing in the thumb zone except the row it happens to be on. The dock,
when it appears, is well built: it clears the footer by 16px at full scroll and
gets 119px of body padding.

**Jordan, first timer.** "Cheapest available" is checked and nothing on screen says
what it means; the sentence that would explain it is 900px below the control that
set it. "Restricted" is the third column from the right and is defined only inside
the row's disclosure. The railcard help paragraph explains the discount, the
privacy consequence and the default in one three-line breath. The page never uses
the word "return" in the heading, so a reader who wants a day trip has to find
"Ticket: Cheapest available" in the folded bar to learn that their price is a
single.

## Questions to consider

- If the phone row were two lines instead of six (C13), would C1, C2 and the pager
  problem all disappear at once? The row's height is the parent defect.
- What is the page's fold budget, in numbers, and who owns it? A stated budget
  ("one full row at 1366×768") would have caught C3 before this audit did.
- The footer is the page's conscience. Why is it the only text on the page with no
  measure and the smallest type?
- If the chooser's list had a heading, would the ordering note still need to
  apologize for the ordering?

## What landed

| Finding | Closed by | Held by |
|---|---|---|
| C5 [P1] a prices-only build claims timetable content it does not have | the paragraph is the payload's own sentence, chosen once from `hasJourneys`, and the renderer writes that string into the page, so the page cannot claim a window its payload does not carry | `tests/test_build_demo_page.py`'s `test_the_sentence_about_times_names_only_what_this_build_has`, which renders both shapes; the words are `build_release.SERVICE_CLAIM` and `SERVICE_CLAIM_WITHOUT_TIMES` |
| C1 [P1] a phone's station cell is four fragments, not a name | the value is one wrapper element (`.station-value`), so every line of it is placed in the cell's value track rather than the bare text nodes landing in the label track. Landed 18 October 2026 | `tests/browser/station-layout.cjs`, "every value starts in the value track, never under its own label", measured at 390px over every cell of every row; with the wrapper put back it reports `worst: -89px` |
| C2 [P1] the last cell's label collides with its link | the hold column and the action column drop the desktop widths (1% and 1px) inside the phone block, so the cell is its row's width and its label sits in the track beside the value rather than inside it. Landed 18 October 2026 | the same section: "no value paints outside the cell that holds it" and "the value track is the rest of the cell". With `width: auto` removed it reports a 1px Tickets cell painting 88px outside itself |
| C8 [P2] changing the budget closes the row the reader opened | the open row is `STATE.openCrs` and every render reopens it, so the panel and the fare inside survive a budget move. Landed 18 October 2026 | `tests/browser/station-rows.cjs`, "a row the reader opened is still open when the budget moves"; with the state half removed it reports `stillOpen: false` |

Everything else in this critique is still open. It lives in `docs/open-work.md`,
which is where a reader looks for what is left, rather than in a second copy here.

## Run notes

Target slugs: the three routes above. Ignore list: `.impeccable/critique/ignore.md`
does not exist, so nothing was suppressed. Assessment independence: not achieved;
the reason is in the method line. CLI detector: one finding
(`cramped-padding` on `.origin-slot-wrap`), assessed as a false positive and not
re-filed. Browser: Chromium through this thread's preview at 127.0.0.1:8801 and
:8802, plus a Playwright pass for geometry at nine widths; screenshots at 1280 and
390 for seven states, then no frames after the light-theme switch (the same
limitation the 14 October run recorded). Light theme: text contrast measured on
every visible text node of the station page in both palettes, no ratio below 4.5:1.
Server: `python -m http.server 8801 --directory _demo_site`, stopped after the run.
Temp files: the measurement scripts live in the system temp directory, not the
repository.
