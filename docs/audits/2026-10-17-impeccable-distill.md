# Impeccable distill: the chooser, the station page, the privacy page

**Date:** 17 October 2026
**Reviewed:** the same build as
[the critique of this date](2026-10-17-impeccable-critique.md): `_demo_site` from
`_demo_feed` and `_demo_kb` at service date 5 October 2026, plus the prices-only
shape in `_shape_site`.
**Mode:** Operate. The visitor arrived with a number and wants a list; everything
on the page is either the answer, a control that changes the answer, or a
disclosure that lets them check it.
**Routes:** the same four surfaces the critique covers: `/`, `/from/<station>/` in
both of its shapes, and `/privacy/`. `/from/<station>/` is one page per priced
station and its chrome is identical on every one of them, so a cut here is a cut
on all 2,712 pages the release writes.
**What this document is:** an audit of what does not earn its place. It removes
nothing and changes no code. Where an item here is a defect rather than a
redundancy it is cross-referenced to the critique by number, so the two documents
do not make the same request twice.
**Counts:** measured on the built page at 1280×900. The station page carries 274
words inside `main` and 128 in the footer; 22 controls at rest, 35 with the
refinements panel open (315px tall, 109 words of help text in it); four blocks
between the heading and the count line; 20 destinations per page.

## The essence, per route

- **The station page:** "Here is everywhere this feed prices from this town inside
  your budget, cheapest first, with what the ticket costs and what it commits you
  to." One number in, one list out, and the list's honesty is the product.
- **The chooser:** "Which town are you starting from?" One field and a list of
  towns with a count beside each.
- **The privacy page:** "What this site does with what you type." Five short
  answers.

Everything below is judged against those sentences. An element that does not
serve the sentence, or that serves it twice, is a candidate.

## Findings

### The station page

**D1 [P2] The intro paragraph is a third copy of the page's own claim.**
`#pageIntro` is 29 words and 48px of the fold: "Every destination this feed prices from the
station above, inside the budget, with the fastest time and the fewest changes.
Click the station name to start from somewhere else." The heading says the budget
and the station; the count line says the destinations and the number; the table's
headers say time and changes. What is left that a reader needs is the click
instruction, and it belongs on the control (critique C10). Recommend: delete the
paragraph, keep the instruction where the station is, and recover 48px of a fold
the critique is already short of (C3).

**D2 [P2] The empty state says the same sentence twice, one line apart.**
`page/station/table.js:198` composes "No destinations for up to £X per adult" into
the count line and `page/station/ticket-modes.js:228` composes the identical
sentence, from the same inputs, into the paragraph below the table. Measured at
£0: the count line reads "No destinations for up to £0.00 per adult" and the
paragraph below begins with the same nine words and a full stop. One sentence, one
owner. Recommend: the count line keeps the number ("0 of 8 destinations at £0.00")
and the paragraph keeps the reason and the four ways back, which is the only part
of it that helps.

**D3 [P2] The restricted-fare panel explains itself twice.**
A row opened on the demo's Nottingham fare shows:
"Restricted fare — the fare's own condition is not in this feed, so check the
seller's terms." and, directly beneath, "This fare carries restriction 00, which
this feed does not describe, so the condition has to be read from the seller's own
terms." The second is the first with the restriction code in it. Where the feed
does describe the condition the two do differ; where it does not, they collapse.
Recommend: one sentence, carrying the code when there is one ("Restriction 00 is
not described in this feed, so check the seller's terms"), and the panel's first
line becomes that sentence rather than a headline plus a restatement.

**D4 [P2] The day control has two explanations and needs one.**
`#serviceDayHelp` is 31 words in three clauses ("Times and changes for every row,
on the date you pick. Days of the week are not the same as each other, so the date
is named. Interchange stations are shown for the build's own day only.") and
`#freshness` is a further sentence about the timetable's coverage window. Between
them they occupy 64px above the count line. The second clause is the reason the
control exists and the third is a limitation of the build. Recommend: the help line
keeps the limitation in one clause; the reason ("a Saturday is not a Monday") moves
into the control's own option labels or goes; the coverage window joins the
provenance below the table, where the rest of the feed's dates already are.

**D5 [P2] The budget hint is 130 characters for a 44px slider.**
"Drag to change the budget in the heading. It stops at the highest fare in
Cheapest available — £126.00 for one adult." Two lines at 1280, three at 390. The
only fact in it that the reader cannot infer from the slider is the ceiling.
Recommend: "Stops at £126, the highest fare here." Ten words, one line, and the
number the ceiling refers to is already in the count line.

**D6 [P2] The footer is five paragraphs and two disclosures where two paragraphs
would do.**
Visible in the footer: destination-type sources (27 words), the synthetic-data
note (18), the ITX/Advance note (30), the timetable note (34), then "Where these
prices come from…" and "The words this page uses". The first is a data-source
credit and must stay. The synthetic-data note only exists on a demo build and is
already carried by the banner at the top of the page, so it is duplicated. The
timetable note is the one that is untrue on a prices-only build (critique C5), so
it is the one that needs rewriting rather than shortening. Recommend: three
visible paragraphs (credit, fares caveat, timetable caveat), the dataset note
deleted where the banner already says it, and everything else inside the existing
method disclosure. That is about 40 words and 60px off every page of the release.

**D7 [P3] Two of the three disclosures could be one.**
"Where these prices come from, and how they were calculated" and "The words this
page uses" are both answers to "can I trust this number", and the second nests
inside the first. The first is 78 words of provenance; the second is a definition
list. Recommend: one disclosure, "About these numbers", whose body ends with the
word list. One summary label fewer, one chevron fewer, and the page's trust
content acquires a single entrance (which is also critique C6's fix).

**D8 [P2] A phone row is six lines where the list needs two.**
Measured at 390px: each row is 275px, made of a label column, a value column, a
site-proof subline and an action line, with the station's parentheses on lines of
their own (critique C1) and the ticket label inline with its link (C2). Twenty rows
at 275px is 5,500px per page. Recommend: below 44rem drop the label column
entirely, put the name and the price on the first line, the time and fare type on
the second, and move the site proof and both actions into the row's existing
disclosure. Two lines is about 90px, which is a page of twenty in 1,800px and
removes C1 and C2 as a side effect. This is the largest single reduction available
on the site.

### The chooser

**D9 [P2] The ordering note argues with nobody.**
"Every station this page prices journeys from, most first — not by how busy it is,
and not by how near it is." The first clause is the list's heading in disguise and
the last two are a defence against an expectation the page has not created: nothing
on the screen suggests busyness or distance, and the picker cannot offer either
(`PRODUCT.md` says the feed carries no geography). Recommend: keep "most first"
as the list's heading subtitle and delete the denial. If a reader does wonder why
Grantham is above Lincoln, the count beside the name is the answer.

**D10 [P2] Each row re-says the list's own sentence.**
"6 destinations this feed prices" appears once per station (critique C12).
Recommend: a heading on the list carrying the phrase once, and the count alone in
the row, right-aligned in a fixed column so the numbers line up. On 2,712 stations
this is the difference between a directory and a paragraph repeated 2,712 times.

**D11 [P3] Two instruction paragraphs become one clause.**
"Type the station you are starting from, then pick it from the list." and the
placeholder "station" are the same instruction in two voices. Recommend: the
placeholder becomes "your station" and the paragraph goes; the provenance line
("Prices from the synthetic demo feed") stays and moves directly under the list
heading.

### The privacy page

**D12 [P2] Three bullets say one thing.**
"No cookies are set by this site." / "No analytics run…" / "This site does not
collect visit data." The third is entailed by the first two (critique C17).
Recommend: two bullets, and the forward promise stays attached to analytics, which
is the claim it qualifies.

**D13 [P2] The address-bar section is one 90-word paragraph plus two bullets for
one fact.**
The fact: your search is in the url, so the host sees it and a shared link carries
it. It currently takes a paragraph that lists all seven parameters, then two
bullets that re-state the consequences. The list of parameters is the part a
reader cannot guess and the part worth keeping. Recommend: one sentence, the
parameter list as a single line of short names, and the two consequences as the
two bullets. About 40% fewer words, same disclosure.

**D14 [P3] The build-date sentence is written for a maintainer.**
"This notice describes the build dated 17 October 2026." (critique C20).
Recommend: delete it and date the page in the conventional place.

## What must not be cut

- **The count line.** It is the page's answer sentence and the only thing that
  says what the list is sorted by and which ticket types are in it.
- **The empty state's four doors.** "Raise the budget", and each ticket set with
  its count. This is the best-recovered state on the site; D2 removes the repeated
  sentence, not the doors.
- **The last sentence of the empty state's method note.** "An advance fare needs a
  chosen train; a restricted fare's condition is in the row's details." It is both
  a definition and a warning.
- **The synthetic-data banner, the NRE credit and the affiliate disclosure.** All
  three are compliance surfaces; none of them is chrome.
- **The footer's data-source paragraph.** It is the licence's price for using the
  feed, and it is not the page's to shorten.
- **The station slot's dashed underline.** The detector calls it cramped padding;
  it is the affordance (critique, run notes).

## Where cutting would be wrong

- **The budget's two controls.** The field and the slider do the same job and both
  earn it: one types, one drags, and the drag is the gesture the page's whole
  premise invites. Reducing them to one saves 60px and costs the product its
  signature interaction.
- **The railcard help paragraph.** It is three sentences about three different
  things (discount, privacy, default) and reads as one. Cut two and the page loses
  either the reason the price changed or the fact that the choice travels in the
  address. Rewrite it as three short lines if it must change.
- **The ticket-type control's four options.** Collapsing "Anytime Day Return" and
  "Any return" into a menu would save a row and hide the distinction the page
  exists to make.

## Order, if someone picks this up

1. D8, because it removes two other findings (C1, C2) and the paging problem with
   them.
2. D2, D3 and D4, which are pure deletions and carry no design risk.
3. D1, D5 and D9 to D11, which recover the fold.
4. D6 and D7, which change the footer's shape and want the disclosure affordance
   (C6) first so the two do not fight.
5. D12 and D13 on the privacy page, which is read by the fewest people and can
   wait.

Each of these should be verified by the same measurement that found it: row height
at 390px, first-row offset at 1366×768, and the word counts above. A reduction
that cannot be measured is not a reduction.
