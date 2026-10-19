# Impeccable review: the chooser, the station page, the privacy page

**Date:** 17 October 2026
**Reviewed:** the worktree at `main` with that day's uncommitted changes (the
provenance and railcards work, and the new "words this page uses" block).
**Combined:** 19 October 2026. This file was two documents of the same date, the
critique (C-findings) and the distill (D-findings), run over the same build and
cross-referencing each other. They are one file now: they asked for overlapping
things, and a reader checking one closure was opening two documents. A finding
keeps the number it was filed under, so the gaps in a later version are
deliberate. Where the two asked for the same thing, the C number carries the row
and the D number names it beside it.
**Open state, verified 19 October 2026.** Every finding was re-read against the
tree. What has fully landed is in "What landed" with the check that holds it; what
was argued rather than fixed is in "Design calls answered" with the reason; and
every finding under "Findings" carries its own state line, where anything but
"still open" says which half is left. The figures are the measurements of
17 October 2026 and were not re-measured in this pass.
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
**Method:** degraded: single-context, in part. The detector and the browser
evidence were run in one thread, because no sub-agent available to that session
has a terminal or a browser, and a design review written from source alone would
have been the blind assessment the skill's two-agent rule exists to prevent. The
design read below is anchored by measurements taken from the live DOM rather than
by memory of the source. Screenshots were captured at 1280×900 and 390×844 for
the station page, the chooser, the open refinements panel, the empty state, an
open row and the shortlist dock; after the light-theme switch the webview stopped
compositing and no further frames could be captured, so everything the light
theme contributed is computed-style measurement rather than sight.
**Measurements:** a Playwright script at nine widths (360 to 1440) and four
viewport heights, plus computed style, geometry, accessible names and console
output from the preview browser, and word counts measured on the built page at
1280×900. Figures are of this demo build, not of the real feed's 2,712-page
release; the demo's handful of destinations is enough for layout and not enough
for the paging arithmetic, which is stated as arithmetic.
**Not re-filed:** the one detector finding (see Run notes), and every item the 14
October critique already closed. Its item 7 is answered by the footer's "The
words this page uses" block and is not repeated here.
**How to prune this document:** each finding keeps its number when it lands. A
finding that lands leaves with a row in "What landed" naming the test that holds
it, the way the 14 October document is kept.

## Design health score

Measured on 17 October 2026, before any of the fixes below landed. It is kept as
the dated reading it was: some of the findings that cost it have since landed or
been argued, and those are in the two tables below.

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
| 9 | Error recovery | 3 | The empty state offers four concrete ways back. It also said the reason twice, in the same words (D2, since landed). |
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
the table's own layout broke the station cell into four lines and collided the
last cell's label with its link, so the one component a reader came for was the
one that looked unfinished. Below the table, the trust content is set in 12.8px
lines 140 to 180 characters wide, which is the opposite of the care the heading
gets. The page reads as authored at the top and assembled at the bottom.

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
- **The count line, the empty state's four doors, the last sentence of its method
  note, the synthetic banner, the NRE credit and the affiliate disclosure, and the
  footer's data-source paragraph.** The first is the page's answer sentence; the
  doors are the best-recovered state on the site; the banner, the credit and the
  disclosure are compliance surfaces rather than chrome; and the data-source
  paragraph is the licence's price for the feed and is not the page's to shorten.
- **The budget's two controls.** The field and the slider do the same job and both
  earn it: one types, one drags, and the drag is the gesture the page's whole
  premise invites. Reducing them to one saves 60px and costs the product its
  signature interaction. (D5 and C9 ask for a shorter hint beside them, not for
  one control.)
- **The ticket-type control's four options.** Collapsing "Anytime Day Return" and
  "Any return" into a menu would save a row and hide the distinction the page
  exists to make.

## Findings

Severity follows the critique scale: P1 breaks or misleads a reader now, P2 costs
them real effort, P3 is polish. Route is named per finding.

### The station page

**C3 [P1] On a common laptop the answer starts below the fold.** Measured with the
demo's 38px synthetic banner, which production does not carry; subtract 54px for
the real page. First destination row:

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
*Still open.* `--h1` is `clamp(2rem, 7vw, 7rem)` in `page/shared.css` with no
viewport term, and the browser suite measures the count-to-first-row gap rather
than a row above the fold.

**C4 [P2] The page's trust content is the least readable text on it.** Every
footer paragraph spans the full 1,176px at 1280, at 13.6px and 12.8px with 20.4px
leading. Measured characters per line: 155, 177, 178, 148, 141, 127, 124. The
railcard paragraph (424 characters) runs at 141 characters per line. The body copy
above it is held to `75ch`; the footer, which is where the page keeps its honesty,
is held to nothing. Fix: one `max-width: 75ch` on the footer, or a `--measure`
token the `.sub` rule already implies.
*Still open.* `.sub` carries `max-width: 75ch`; the `footer` rule carries no
measure.

**C6 [P2] Three disclosures look like prose.** "About the ticket link" (24px
tall), "Where these prices come from…" and "The words this page uses" are
`<summary>` elements with no marker, no chevron, no underline and the body colour.
Measured: 143×24 at 390 and 24px tall at 1280. They sit in a column of muted
paragraphs, so the reader has no way to know two of them open. The page already
has one drawn disclosure mark (`CHEVRON`, used by the filter bar and the station
slot and the row expander); the summaries are the only disclosures on the site
that do not use it. Fix: the same chevron, and the same `aria-expanded` behaviour
the filter bar has.
*Still open.* `.method summary` is accent-coloured and neither it nor
`.link-terms summary` renders a chevron; both are `display: flex`, which also
suppresses the default marker, so the resting affordance is weaker than the
critique found.

**C7 [P2] The row's two actions have inverted weight.** The primary action is
"Tickets", a 48×22 link with an 11px invisible slop ring. The secondary action is
a 44×44 bordered button with a chevron. Measured at 1280: 44×44 for the expander,
48×22 for the link. The row's target sizes are legal (WCAG 2.5.8 is met by the
slop, and the checkbox sits in a 44px label: the eleven sub-24px boxes the
measurement finds are all enclosed), but the eye is drawn to the disclosure rather
than to the purchase. Fix: give the link the bordered treatment and the expander
the bare one, or leave both bare.
*Still open.* `.buy` is a text link with a 1px underline; `.row-expand` is a
bordered 2.75rem button.

**C10 [P3] The page's one instruction is in the wrong place.** "Click the station
name to start from somewhere else" is how a reader learns that the heading's
station is a control, and it sat in body copy 250px below the word it describes,
in the same paragraph as a sentence about what the list contains. The station slot
has no visible label of its own: its accessible name is "Change starting station:
GRANTHAM", which is right for a screen reader and invisible to everyone else.
Fix: attach the instruction to the control (a title, a hinted underline, or the
picker's own first line) and drop the rest of the paragraph (D1).
*Half landed.* The sentence is the first-use note beside the heading now
(`build_render.first_use_sentence`, `#firstUse`), so it sits under the word it
describes; `tests/browser/station-picker.cjs` reads `#firstUse` and requires it to
name the station and not to say "Change". The intro paragraph kept the promise
half, which is D1.

**C13 / D8 [P2] A phone row is six lines where the list needs two.** Measured at
390px: each row is 275px, made of a label column, a value column, a site-proof
subline and an action line, with the station's parentheses on lines of their own
(C1, since fixed) and the ticket label inline with its link (C2, since fixed).
Twenty rows at 275px is 5,500px per page, and the real Grantham page holds 334
destinations. Measured row height on a phone: 275px at 360, 390, 414, 640 and 704,
against 61px at 768 and above. `PAGE_SIZE` is 20, so a phone page is 5,500px of
rows before the pager. That is arithmetic from a measured row height, not a scroll
test. The stacked row is the right call (a seven-column table cannot fit 390px);
its height is the defect. Fix: below 44rem drop the label column entirely, put the
name and the price on the first line, the time and fare type on the second, and
move the site proof and both actions into the row's existing disclosure. Two lines
is about 90px, which is a page of twenty in 1,800px. This is the largest single
reduction available on the site.
*Still open.* The phone block still gives every cell a 5rem label track
(`page/station.css`), so the row's height is unchanged.

**D1 [P2] The intro paragraph is a third copy of the page's own claim.** `#pageIntro`
was 29 words and 48px of the fold: "Every destination this feed prices from the
station above, inside the budget, with the fastest time and the fewest changes.
Click the station name to start from somewhere else." The heading says the budget
and the station; the count line says the destinations and the number; the table's
headers say time and changes. What is left that a reader needs is the click
instruction, and it belongs on the control (critique C10). Recommend: delete the
paragraph, keep the instruction where the station is, and recover 48px of a fold
the critique is already short of (C3).
*Half landed.* The paragraph is one promise of fourteen words now and the
instruction moved out of it into the first-use note (C10). The paragraph itself
remains, so the 48px is still on the fold's bill.

**D3 [P2] The restricted-fare panel explains itself twice.** A row opened on the
demo's Nottingham fare shows: "Restricted fare — the fare's own condition is not
in this feed, so check the seller's terms." and, directly beneath, "This fare
carries restriction 00, which this feed does not describe, so the condition has to
be read from the seller's own terms." The second is the first with the restriction
code in it. Where the feed does describe the condition the two do differ; where it
does not, they collapse. Recommend: one sentence, carrying the code when there is
one ("Restriction 00 is not described in this feed, so check the seller's terms"),
and the panel's first line becomes that sentence rather than a headline plus a
restatement.
*Still open.* Both sentences are still composed: the row's own line in
`page/station/row-cells.js`, the code clause in `build_payload.destination_row`.

**D4 [P2] The day control has two explanations and needs one.** `#serviceDayHelp`
is 31 words in three clauses ("Times and changes for every row, on the date you
pick. Days of the week are not the same as each other, so the date is named.
Interchange stations are shown for the build's own day only.") and `#freshness` is
a further sentence about the timetable's coverage window. Between them they occupy
64px above the count line. The second clause is the reason the control exists and
the third is a limitation of the build. Recommend: the help line keeps the
limitation in one clause; the reason ("a Saturday is not a Monday") moves into the
control's own option labels or goes; the coverage window joins the provenance
below the table, where the rest of the feed's dates already are.
*Still open.* `page/station/wiring.js` still writes all three clauses.

**D6 [P2] The footer is five paragraphs and two disclosures where two paragraphs
would do.** The visible footer was the destination-type sources (27 words), the
synthetic-data note (18), the ITX/Advance note (30) and the timetable note (34),
then the method disclosure and "The words this page uses". The first is a
data-source credit and must stay. The synthetic-data note only exists on a demo
build and is already carried by the banner at the top of the page, so it is
duplicated. The timetable note is the one that was untrue on a prices-only build
(critique C5, since fixed), so it is the one that needed rewriting rather than
shortening. Recommend: three visible paragraphs (credit, fares caveat, timetable
caveat), the dataset note deleted where the banner already says it, and everything
else inside the existing method disclosure. That is about 40 words and 60px off
every page of the release.
*Partly landed.* The service-claim paragraph is now the payload's own sentence
(C5) and the words list sits inside the method disclosure. The synthetic-data note
is still its own footer paragraph on a demo build, beside the banner that says the
same thing.

**D7 [P3] Two of the three disclosures could be one.** "Where these prices come
from, and how they were calculated" and "The words this page uses" are both
answers to "can I trust this number", and the second nests inside the first. The
first is 78 words of provenance; the second is a definition list. Recommend: one
disclosure, "About these numbers", whose body ends with the word list. One summary
label fewer, one chevron fewer, and the page's trust content acquires a single
entrance (which is also critique C6's fix).
*Partly landed.* The words list nests inside the method disclosure now, which is
the direction asked for, but it is a second `<summary>` rather than the end of the
first.

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
**Answered, not changed.** See "Design calls answered".

**C12 / D10 [P2] Every chooser row repeats the same phrase.** "6 destinations this
feed prices" is the last third of every row. In the demo that is three
repetitions; on the real release it is 2,712, and the phrase is the same in all of
them. The row is a name, a code and a count, and the count has no heading of its
own. Fix: a heading for the list that carries the phrase once ("Destinations this
feed prices"), and a bare number per row, right-aligned in a fixed column so the
numbers line up. On 2,712 stations this is the difference between a directory and
a paragraph repeated 2,712 times.
*Still open.* `page/chooser.js` writes the phrase per row.

**C14 / D11 [P3] The empty heading reads "from station".** With nothing typed, the
sentence is "Train fares up to £20 from station". The placeholder is the muted
word "station" under a dashed underline, and the instruction below explains it. It
is not wrong, it is not English either. Fix: the placeholder is the prompt ("your
station"), which is a word the sentence can take, and the instruction paragraph
goes.
*Still open.* The field is `placeholder="station"`, and `tests/test_build_chooser.py`
asserts that string, so the wording change and the test go together.

**C15 [P3] Three paragraphs of equal weight before the list.** Instruction,
provenance line and ordering note, at 18.4px, 13.6px and 13.6px, each its own
paragraph. The ordering note is the one that is genuinely about the list, and it
reads as another apology. Fix: the ordering note becomes the list's heading
subtitle (C12's heading), the provenance line stays, the instruction folds into
the field's placeholder (C14).
*Still open.* The chooser still renders intro, provenance and ordering as three
`<p>` elements (`build_render.render_chooser`).

**D9 [P2] The ordering note argues with nobody.** "Every station this page prices
journeys from, most first — not by how busy it is, and not by how near it is." The
first clause is the list's heading in disguise and the last two are a defence
against an expectation the page has not created: nothing on the screen suggests
busyness or distance, and the picker cannot offer either (`PRODUCT.md` says the
feed carries no geography). Recommend: keep "most first" as the list's heading
subtitle and delete the denial. If a reader does wonder why Grantham is above
Lincoln, the count beside the name is the answer.
*Still open.* The denial is still in `build_render.render_chooser`, and
`tests/browser/chooser.cjs` asserts all three clauses, so the wording change and
that check go together.

### The privacy page

**C17 / D12 [P2] Three bullets say one thing.** "No cookies are set by this
site." / "No analytics run. If analytics are ever added to this site, this page
will name them here first." / "This site does not collect visit data." The third
is the union of the first two and adds a claim (visit data) that the second has
already narrowed. Fix: two bullets, cookies and analytics, and keep the forward
promise attached to analytics where it belongs.
*Still open.* `build_render.render_privacy` still writes the third bullet.

**C18 [P3] The page's title is a single word.** `<title>Privacy</title>`, against
"Train fares up to £30 from GRANTHAM" and "Train fares up to £20 · pick your
station". In a row of tabs a reader looking for the fare page has three titles and
one of them is indistinguishable from any other site's privacy notice. Fix:
"Privacy · Train fares" or the release's own name once there is one (it is
undecided, `PRODUCT.md`).
*Still open.* The privacy template's title is `Privacy`.

**C19 [P3] The first thing on the page is a back link, then a switch, then the
title.** The back link is outside `main` (correct for the landmark), the theme
switch is pinned right and sits between the link and the heading, so the reading
order on a 900px screen is: banner, link, switch, "Privacy". It is the only route
where the heading is not the first thing under the banner. Fix: put the switch
after the heading on this route, or accept it as chrome and align it with the back
link.
*Still open.* The privacy template keeps `__THEME_TOGGLE__` between the back-link
nav and the `h1`.

**C20 / D14 [P3] The build date is the page's only date, in the page's voice.**
"This notice describes the build dated 17 October 2026." That is a sentence for a
maintainer. A reader wants to know when the policy changed, which is the same date
on a static site, phrased as a fact about the notice. Fix: "Last updated 17
October 2026" and drop the sentence.
*Still open.* The verb half landed with clarity audit item 42, which replaced a
claim of publication with a statement of the build date; the sentence is still
addressed to a maintainer.

**D13 [P2] The address-bar section is one 90-word paragraph plus two bullets for
one fact.** The fact: your search is in the url, so the host sees it and a shared
link carries it. It takes a paragraph that lists all seven parameters, then two
bullets that re-state the consequences. The list of parameters is the part a
reader cannot guess and the part worth keeping. Recommend: one sentence, the
parameter list as a single line of short names, and the two consequences as the
two bullets. About 40% fewer words, same disclosure.
*Still open.* The paragraph is unchanged in the privacy template.

### Cross-route

**C21 [P2] The ticket-set vocabulary is chosen before it is explained.** The four
options are "Cheapest available", "Anytime Day Return", "Any return" and "Single",
and the paragraph that defines what the chosen set contains sits below the table
(`#modeNote`), more than a screen away from the control once the panel that holds
it is open. The empty state asks the same vocabulary of a reader who is already
lost: at £0 it offers "Show the 7 Anytime Day Returns", "Show the 8 returns" and
"Show the one single" side by side. The "The words this page uses" block defines
the terms correctly and is in the right place for a reader who has already decided
to check; it is the wrong place for a reader choosing a filter. Fix: one clause
per option in the control itself ("Anytime Day Return (unrestricted)"), or the
mode note moved directly under the ticket-type field and shortened to the
difference between the sets. This is not the 14 October critique's item 7, which
is answered: that was where the words are defined, this is when.
*Still open.* The four options carry no clause, and `#modeNote` is still below
the table.

## Persona red flags

**Casey, phone, one hand, interrupted.** 275px rows mean three destinations per
screen and no sense of a list; the count line is 872px down; the pager is 5,500px
further. Nothing in the thumb zone except the row it happens to be on. The dock,
when it appears, is well built: it clears the footer by 16px at full scroll and
gets 119px of body padding.

**Jordan, first timer.** "Cheapest available" is checked and nothing on screen
says what it means; the sentence that would explain it is 900px below the control
that set it (C21). "Restricted" is the third column from the right and is defined
only inside the row's disclosure. The railcard help paragraph explains the
discount, the privacy consequence and the default in one three-line breath. The
page never uses the word "return" in the heading, so a reader who wants a day trip
has to find "Ticket: Cheapest available" in the folded bar to learn that their
price is a single.

**Sam's two focus losses, of which one remains.** Changing the budget destroyed
the row that held focus and dropped it to `<body>`; that was C8 and is fixed.
Clearing the shortlist still hides the dock with focus inside it, which drops
focus to `<body>`.

## Questions to consider

- If the phone row were two lines instead of six (C13), would C1, C2 and the pager
  problem all disappear at once? The row's height is the parent defect. C1 and C2
  are fixed and the height is not.
- What is the page's fold budget, in numbers, and who owns it? A stated budget
  ("one full row at 1366×768") would have caught C3 before this audit did.
- The footer is the page's conscience. Why is it the only text on the page with no
  measure and the smallest type (C4)?
- If the chooser's list had a heading, would the ordering note still need to
  apologize for the ordering (C12, D9)?

## What landed

| Finding | Closed by | Held by |
|---|---|---|
| C5 [P1] a prices-only build claims timetable content it does not have | the paragraph is the payload's own sentence, chosen once from `hasJourneys`, and the renderer writes that string into the page, so the page cannot claim a window its payload does not carry | `tests/test_build_demo_page.py`'s `test_the_sentence_about_times_names_only_what_this_build_has`, which renders both shapes; the words are `build_release.SERVICE_CLAIM` and `SERVICE_CLAIM_WITHOUT_TIMES` |
| C1 [P1] a phone's station cell is four fragments, not a name | the value is one wrapper element (`.station-value`), so every line of it is placed in the cell's value track rather than the bare text nodes landing in the label track. Landed 18 October 2026 | `tests/browser/station-layout.cjs`, "every value starts in the value track, never under its own label", measured at 390px over every cell of every row; with the wrapper put back it reports `worst: -89px` |
| C2 [P1] the last cell's label collides with its link | the hold column and the action column drop the desktop widths (1% and 1px) inside the phone block, so the cell is its row's width and its label sits in the track beside the value rather than inside it. Landed 18 October 2026 | the same section: "no value paints outside the cell that holds it" and "the value track is the rest of the cell". With `width: auto` removed it reports a 1px Tickets cell painting 88px outside itself |
| C8 [P2] changing the budget closes the row the reader opened | the open row is `STATE.openCrs` and every render reopens it, so the panel and the fare inside survive a budget move. Landed 18 October 2026 | `tests/browser/station-rows.cjs`, "a row the reader opened is still open when the budget moves"; with the state half removed it reports `stillOpen: false` |
| C16 [P3] the chooser's footer is not the station page's footer | the chooser keeps the same `.footnav` and omits the route it is already on, so it is `Privacy` in a nav rather than a bare paragraph | the chooser template in `page_templates.py`, and the shared `.footnav` rule in `page/shared.css` |
| D2 [P2] the empty state says the same sentence twice | `emptyListSentence(cap, what)` is the one composition, called by the count line and by the empty state, so the two cannot diverge | `tests/browser/station-filters.cjs` asserts the two are the same sentence character for character on a page with an empty list; with a clause added to the empty state it reported two different ones |

## Design calls answered

Three findings were argued rather than fixed, and the record is the reason so the
same request is not re-derived.

| Finding | The answer | Where it is recorded |
|---|---|---|
| C9 / D5 [P3] the budget hint is 130 characters for a 44px slider, and "Stops at £126, the highest fare here" would do | kept as it is. The ceiling is party-aware, so the sentence has to name the party it was resolved for or it is a number without a subject, and the two extra words were judged worth them beside a control that is four lines in total | ADR-0048, "The budget names where it stops" |
| C11 [P2] the filtered list appears 200px below the field that opened it | the mechanism is working as its comment intends. The chooser's panel is anchored to the list's place in the document on purpose, so the prose between the field and the list stays readable and clickable; the station page's picker anchors to the field because it has no prose under it. Moving the chooser's panel to the field is a design call, not a defect, and it has not been taken | the comment on `anchor` in `page_templates.STATION_FIELD_JS`, which names the four-dimension audit's R1 |
| the detector's one finding, `cramped-padding` on `.origin-slot-wrap` | the border it flags is the dashed underline that is the station slot's whole affordance | "Rejected designs, with the reason" in `docs/open-work.md` |

## Run notes

Target slugs: the three routes above. Ignore list: `.impeccable/critique/ignore.md`
does not exist, so nothing was suppressed. Assessment independence: not achieved;
the reason is in the method line. CLI detector: one finding (`cramped-padding` on
`.origin-slot-wrap`), assessed as a false positive and not re-filed. Browser:
Chromium at 127.0.0.1:8801 and :8802, plus a Playwright pass for geometry at nine
widths; screenshots at 1280 and 390 for seven states, then no frames after the
light-theme switch (the same limitation the 14 October run recorded). Light theme:
text contrast measured on every visible text node of the station page in both
palettes, no ratio below 4.5:1. Server:
`python -m http.server 8801 --directory _demo_site`, stopped after the run. Temp
files: the measurement scripts live in the system temp directory, not the
repository.
