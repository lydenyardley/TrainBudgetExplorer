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
tree. Twenty of the thirty findings landed in that pass and are rows in
"What landed" with the check that holds each; two were argued rather than fixed
and are in "Design calls answered" with the reason; and what is left under
"Findings" is the three that are still open. The figures are the measurements of
17 October 2026, except the two the pass re-measured (C3's fold and C13's row
height), and they say so where they are quoted.
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

### The privacy page

**C18 [P3] The page's title is a single word.** `<title>Privacy</title>`, against
"Train fares up to £30 from GRANTHAM" and "Train fares up to £20 · pick your
station". In a row of tabs a reader looking for the fare page has three titles and
one of them is indistinguishable from any other site's privacy notice. Fix:
"Privacy · Train fares" or the release's own name once there is one (it is
undecided, `PRODUCT.md`).
*Still open.* The privacy template's title is `Privacy`.

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

**Casey, phone, one hand, interrupted.** 111px rows mean six or seven
destinations per screen, so the list reads as a list; the pager that was 5,500px
away is about 2,220px away. The dock, when it appears, is well built: it clears
the footer by 16px at full scroll and gets 119px of body padding. What is left for
her is the count line above the table and the ticket vocabulary C21 describes.

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
  problem all disappear at once? The row's height was the parent defect, and it
  landed in the 19 October pass: all three went with it.
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
| C10 [P3] the page's one instruction is in the wrong place | the instruction is the first-use note under the heading, beside the control it describes, and the paragraph that carried the rest of it is gone with D1 | `tests/browser/station-picker.cjs`, which reads `#firstUse` and requires it to name the station without saying "Change" |
| C3 [P1] the answer starts below the fold on a laptop | the heading's viewport-height term was capped at 10vh and the intro paragraph left (D1), which moves a whole row above the fold at 1366×768: measured on arrival at row top 690, height 64, viewport 768, with the demo's 38px banner still on the page | `tests/browser/station-layout.cjs`, "at 1366x768 one whole destination row is above the fold", measured with the refinements folded and the panel's own 316px excluded |
| C4 [P2] the trust content is the least readable text | the footer is held to 75ch, the measure the body copy above it already has | `tests/browser/station-layout.cjs`, "the footer is held to a readable measure rather than the whole page" |
| C6 [P2] three disclosures look like prose | the ticket and method disclosures wear the page's drawn chevron, turned over when open, so all three openers are one mark in one place | the same section, "both disclosures wear the page's drawn mark" |
| C7 [P2] the row's actions have inverted weight | the ticket link is the bordered 44px control and the row expander is the bare mark beside it, in that order | the same section, "the ticket link is the bordered control and the expander the bare mark", and the a11y matrix's target-size measurement |
| C13 / D8 [P2] a phone row is six lines | at 390px the row is two lines, place and price then time, count, fare and ticket, measured at 111px, so a page of twenty is 2,220px rather than 5,500 | `tests/browser/station-layout.cjs`, "at 390px the typical row is two lines rather than six" |
| D1 [P2] the intro paragraph is a third copy of the claim | `#pageIntro` is gone; its one non-redundant sentence is the first-use note under the heading | `tests/test_build_demo_page.py`, "the station page says which control changes station" |
| D3 [P2] the restricted-fare panel explains itself twice | an undescribed condition is one sentence carrying the code, composed once in `build_payload.describe_restriction` and printed once | `tests/test_build_fares.py`, "a restriction the feed cannot describe says so plainly", and the browser suite's condition checks |
| D4 [P2] the day control has two explanations | the help line is one clause about the limitation; the timetable's coverage window moved into the method fold with the other dates | `tests/browser/station-shortlist.cjs`, "and it is labelled, described by its help text, and on show"; `station-fares.cjs`, "the timetable sentence carries the feed's own service window" |
| D6 [P2] the footer is five paragraphs and two disclosures | a page with no feed note writes no note paragraph, so a synthetic build's footer is the banner only and a real build's is banner and note | `tests/test_build_chooser.py`, "a route without a note ships no empty paragraph" |
| D7 [P3] two disclosures could be one | the trade words are the end of the method disclosure rather than a second disclosure inside it | `tests/browser/station-render.cjs`, "the trade words the page quotes are defined together, in the method disclosure" |
| C11 [P2] the filtered list appears below the field that opened it | the chooser's panel is anchored to the field that opened it, the same rule the station page's picker follows, so the answer is under the question and the prose behind it stays reachable | `tests/browser/chooser.cjs`, "the panel opens under the field rather than over the prose it is written below" |
| C12 / D10 [P2] every chooser row repeats the phrase | the phrase is the list's heading, written once as "Destinations this feed prices", and each row carries a bare number | `tests/browser/chooser.cjs`, "every option carries its name, its code and a bare count" |
| C14 / D11 [P3] the empty heading reads "from station" | the placeholder is "your station", a word the sentence can take | `tests/browser/chooser.cjs`, "the station it has no answer for is a field holding the prompt"; `tests/test_build_chooser.py` carries the budget into the link |
| C15 [P3] three paragraphs of equal weight | the instruction paragraph is gone; the ordering note is the list's subtitle | `tests/test_build_chooser.py`, "the chooser is the index and carries no fares" |
| D9 [P2] the ordering note argues with nobody | "Most first." is the subtitle and the denial of busyness and nearness is deleted | `tests/test_build_chooser.py`, "the chooser says what its order is and is not", and `tests/browser/chooser.cjs` |
| C17 / D12 [P2] three bullets say one thing | the visit-data bullet is gone; the cookies and analytics bullets are the list, and the forward promise stays with analytics | `tests/test_build_provenance.py`, "the privacy page describes the build that was made" |
| C19 [P3] the page opens with a back link, then a switch, then the title | the back link and the theme switch share one row of chrome above the document, so the reading order under it is the title | the same test, which checks the chrome row holds both and sits above `main` |
| C20 / D14 [P3] the build date is in the page's voice | "Last updated 17 October 2026." in place of the maintainer's sentence | the same test |
| D13 [P2] the address section is one paragraph and two bullets | the parameters are one line of short names, then the two consequences as the two bullets | the same test, which reads the parameter line and the absent sentence |

## Design calls answered

Two findings were argued rather than fixed, and the record is the reason so the
same request is not re-derived.

| Finding | The answer | Where it is recorded |
|---|---|---|
| C9 / D5 [P3] the budget hint is 130 characters for a 44px slider, and "Stops at £126, the highest fare here" would do | kept as it is. The ceiling is party-aware, so the sentence has to name the party it was resolved for or it is a number without a subject, and the two extra words were judged worth them beside a control that is four lines in total | ADR-0048, "The budget names where it stops" |
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
