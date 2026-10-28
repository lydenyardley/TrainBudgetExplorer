# Open work

**Opened:** 1 October 2026. **Pruned and numbered:** 21 October 2026.
**Re-read against the tree:** 26 October 2026.

**Scope:** every item this project has left open, in one place, so that nothing is
open only because it lives in a file nobody re-reads. Each item carries its own
number, and the number is what a commit, an audit or a conversation can name.

Three things were pruned out of this file on 21 October 2026. The closed entries --
seven of them, some with a hundred lines of measurement narrative -- moved to
`docs/settled-work.md`, which is where a closure and the check that holds it
belong. The rejected designs moved there too, because a rejection is a decision
already made and this file is what is *not* decided. The four audits still open
were merged into one list on 21 October 2026, which kept their measurements; that
file was removed on 26 October 2026 when this file took over its evidence, so each
item below names the audit ID it came from and carries the figure that matters.
O7, for instance, is S5 of the 19 October critique and states S5's three
measurements.

An item leaves this file when it is done, and it leaves by naming the commit and
the test that hold it, or by naming the ADR where it was a decision rather than a
fix. Nothing leaves on the strength of having been discussed.

Three items left on 21 October 2026, with the measurement and the reading that
closed them recorded in `docs/settled-work.md`: **O2** (a real page was measured
and the ticket-mode split was costed against it), **O17** (the six licence
sentences were corrected against the clearance the owner gave on 16 October 2026)
and **O18** (the enforcer was designed, prototyped and refused). Their numbers are
retired rather than reused, because a number is what a commit or a comment cites
and renumbering would make every one of those citations point at a different item.

## The thirty-five items

| # | Item | Kind | Severity |
|---|---|---|---|
| O3 | The shortlist dock has no total (DL3) | decision | P2 |
| O4 | The dock and the budget rail are pinned at once (OV5) | decision, measured | P2 |
| O5 | The fare horizon on the budget track (OV1, DL6) | decision | P2 for OV1, P3 for DL6 |
| O6 | The chosen station does not morph into the heading (OV7) | decision | P3 |
| O7 | The phone has no fold budget (S5) | decision | P2 |
| O8 | The phone's drag straddles the 50 ms gate (OV3) | decision, measured | P3 |
| O9 | The opened refinements panel leaves a 160px void | code | P3 |
| O10 | The heading's budget field is 37x36px against a 44px promise | decision | P3 |
| O11 | Provenance and approximation are one generic disclaimer (S35) | code, decided | P3 |
| O12 | Deep links are not verified per seller, date and party (S31) | code, decided | P2 |
| O13 | The chooser needs a known station name or a code prefix (C27, S08) | decision with a data question | P2 |
| O14 | Date-specific schedules are not a product mode (S24) | decision | P2 |
| O15 | Bank holidays and service exceptions are not inputs (S25) | decision, downstream of O14 | P3 |
| O16 | The site has no public name (S40) | decision | P3 |
| O19 | A release costs twelve runners, and 39 minutes at the slowest share | decision, measured | P2 |
| O20 | The stop rule's own review was due on 21 October 2026 (S43, S44) | person | P1 for the project |
| O23 | The ticket link says "Tickets" and opens the seller's empty search (critique 2) | decision | P2 |
| O24 | A row's price does not say return or single, or who it covers (critique 4, 20) | decision | P2 |
| O25 | A ticket-mode switch lowers the reader's budget without saying so (critique 5) | code | P2 |
| O26 | A two-ticket row can print "Direct" over its own trains (critique 7) | code | P2 |
| O27 | The privacy contact is escaped markup (critique 9) | code | P2 |
| O28 | A reader with JavaScript off gets no rows and, if the script is disabled rather than missing, no note (critique 3) | code | P3 |
| O29 | An undated timetable build says "No service that day" with no day (critique 1) | code | P3 |
| O30 | Reader-facing prose still carries build vocabulary (critique 10) | decision | P3 |
| O31 | The empty state offers up to five doors (critique 8) | code | P3 |
| O32 | A one-station build's root is a one-row chooser (critique 12) | decision | P3 |
| O33 | The station picker hides the station it is changing from (critique 13) | code | P3 |
| O34 | A phone row's numbers stand alone, and the rail's slider is a few dozen pixels (critique 14, 24) | decision | P3 |
| O35 | The shortlist dock has no fare, no price order and no undo (critique 18) | code | P3 |
| O36 | The row's copied journey leaves out the price and the times (critique 19) | code | P3 |
| O37 | The day control names no day and confirms no change (critique 21) | code | P3 |
| O38 | The theme switch has no visible label (critique 22) | code | P3 |
| O39 | Table columns move between filters (critique 23) | code | P3 |
| O40 | Pagination does not say which results the page shows (critique 17) | code | P3 |
| O41 | Station names are printed in the feed's capitals (critique 16) | decision | P3 |

Sixteen are code, and two of those have their decision already taken (O11, O12).
Eighteen wait on the owner's answer (O3 to O8, O10, O13 to O16, O19, O23, O24,
O30, O32, O34, O41), and one (O20) waits on a person. None is blocked on a tool.
**Kind** says who acts: `code` is a fix waiting for its turn, `decision` is a
question only the owner can answer, and `person` is one neither can settle.

**O1**, the only item that wanted a run this machine could not give it, closed on
26 October 2026: the release measured **370 MB of its 800 MB budget** and
published. **O21** (station-cluster `.FSC` fares and the 109 destinations they
newly price) and **O22** (the twelve destinations newly priced by station-group
expansion) both left on 23 October 2026 once ADR-0075 and
`REVIEWED_SETTLEMENT_FALLBACKS` landed (`docs/settled-work.md`).

The last nineteen (O23 to O41) are the 21 October 2026 Critiquito design
critique, read against the tree on 26 October 2026. Its severity key was applied
to the pages it captured, so three of its P1s are graded lower here: the release
is dated, so "No service that day" has a day to mean (O29), and a script that
fails to arrive now says so (O28). The findings it filed that the page has since
answered are settled in `docs/settled-work.md`, under the critique's own heading.

---

## O3 -- The shortlist dock has no total (DL3)

**Kind:** decision. **Raised:** DL3 of the 19 October 2026 delight pass, ask 5 of
the merged audit list. **Route:** the station page's shortlist dock and its share
text.

One line under the dock's head: "Two places, £13.40 for one adult." It is a
product decision about what the dock is for -- a comparison list, or the beginning
of a plan -- before it is code. If it lands, the sum must be of the rendered rows'
own party price, not a second array, and an unpriced or tied row makes the total
say "from" or omit it rather than guess.

---

## O4 -- The dock and the budget rail are pinned at once (OV5)

**Kind:** decision, measured. **Raised:** OV5 of the 19 October 2026 overdrive pass,
ask 9 of the merged list. **Route:** the station page's two sticky surfaces.

The rail shipped on 20 October 2026 and took the table header's sticky offset with
it; the shortlist dock's own offset was not part of that. A page with a shortlist,
scrolled far enough, shows the rail at the top and the dock at the foot, and the
rail is up exactly when the reader is deep in the list and the shortlist matters.

**Measured 21 October 2026** on the real Grantham page at 390x844, with the page
scrolled until the last row sits just clear of the dock (`node
tools/measure_station_phone.cjs _real_site`, figures in
`docs/build-performance-findings.md`):

| Places held | Between the rail and the dock | Rows fully visible there | Last row | The dock's Copy |
|---|---|---|---|---|
| 2 | **647 px** | **4** | ends exactly at the dock's top | 44 px tall, inside the viewport, topmost at its centre |
| 4 | **571 px** | **4** | ends exactly at the dock's top | 44 px tall, inside the viewport, topmost at its centre |

So neither strip covers a row or a control: the page's body padding buys the last
row its clear space, and the dock's Copy is reachable with the rail up. What the
reader loses is four rows of comparison in the middle of the screen, at both
dock heights, because the rail takes 56 px and the dock 141 or 217. The decision
this still holds is whether four rows, with both strips up, is enough for the
comparison the dock exists for -- or whether the rail should stand down while a
shortlist is held, or the dock collapse to its head until it is wanted.

---

## O5 -- The fare horizon on the budget track (OV1, DL6)

**Kind:** decision, visual. **Raised:** OV1 of the overdrive pass and DL6 of the
delight pass, asks 6 and 7 of the merged list. **Route:** the station page's budget
slider.

A drawn track (1px ticks at every distinct visible fare) and its smallest form, one
tick at the cheapest fare. The mockups of 20 October 2026 argue against the drawn
track as first described: on a £126 ceiling every fare in the demo list is inside
the left fifth of the track -- 22 distinct fares, the furthest short of £19 at
172px of 528 -- so the ticks read as a smudge beside the thumb rather than as a
shape. A non-linear scale, or only the next few fares, is the version worth
drawing; the one-tick form survives that ceiling.

---

## O6 -- The chosen station does not morph into the heading (OV7)

**Kind:** decision. **Raised:** OV7 of the overdrive pass, ask 10 of the merged
list. **Route:** the chooser and the station page's navigation.

Naming the chosen row's station token and the heading's own with one
`view-transition-name` for the length of the click, so the station arrives in the
heading. OV6 shipped without it, and it stays unshipped if the effect is not clean
at 390.

---

## O7 -- The phone has no fold budget (S5)

**Kind:** decision. **Raised:** S5 of the 19 October 2026 critique, ask 2 of the
merged list. **Route:** the station page at 390 and 320.

Measured on arrival, with the refinements folded: at 1366x768 the first row starts
at 690 and a whole row is above the fold; at 390x844 it starts at 786 and 58px of
it shows; at 320x640 it starts at 858 and nothing shows. The laptop fold was given
a stated budget -- one whole row at 1366x768 -- and is held by a browser check.
There is no equivalent for the phone, which is the first encounter the product
describes, and the 320 case is the 200% zoom case too.

**What closes it.** A stated phone budget, bought from the stack rather than
asserted: "at 390x844 the first row starts above 760px; at 320x640 above 620px."
The merge of the 19 October pass left 43px of the 62px this first counted, so the
390 target needs re-measuring before it is claimed, and the 320 target may need the
banner to be one line there. The check goes beside the 1366 measurement in
`tests/browser/station-layout.cjs`.

---

## O8 -- The phone's drag straddles the 50 ms gate (OV3)

**Kind:** decision, measured. **Raised:** OV3 of the overdrive pass. **Route:**
the station page's budget drag, and the gate in
`tests/browser/station-layout.cjs`.

The measurement this item was waiting for was taken on 21 October 2026, on the
real Grantham page at 390x844, over three runs (`node
tools/measure_station_phone.cjs _real_site`; figures in
`docs/build-performance-findings.md`). At a 4x CPU slowdown the budget re-render
medians **46, 57 and 79 ms** on the page's own list, against the **50 ms** gate;
at 6x it is **84, 94 and 142 ms**. The desktop figure the gate was written
against is **7.4 ms**, and this page's own list renders in **8.3 to 9.6 ms**
unthrottled.

The fix the item named -- one render per frame instead of one per input event --
is already shipped (`queueBudgetFrame`, 19 October 2026), so the cost left is
the single render. The decision this now holds is whether the 50 ms gate is a
desktop budget or a phone one: if it is a phone budget, the page is over it on a
slowed CPU and the render has to get cheaper; if it is a desktop budget, the
figure is recorded and the gate says what it always said.

**The single render got cheaper on 28 October 2026**, and the figures above
predate it: one render's script fell from 12.47 ms to 2.3-3.1 ms and its
`priceOf` calls from 57,996 to 8,261 (`docs/build-performance-findings.md`,
"One render of a real page"). The phone figures are therefore a measurement of a
build that no longer exists, and the question above wants a re-run of `node
tools/measure_station_phone.cjs _real_site` at 4x and 6x before it is answered.
What that run has to report is the same three medians against the same gate; the
desktop frame span did not move measurably in the change, because a frame that
fits is pinned to the display's cadence.

---

## O9 -- The opened refinements panel leaves a 160px void

**Kind:** code. **Raised:** minor observation of the 19 October 2026 critique, ask
3 of the merged list. **Route:** the station page's refinements panel.

The panel is a two-column grid with one long row (ticket type) and one short one
(party and railcard), so opening it leaves a 160px hole in the left column. It is a
layout fix with no decision inside it: one column, or a span for the short field.

---

## O10 -- The heading's budget field is 37x36px against a 44px promise

**Kind:** decision. **Raised:** question 2 of the 19 October 2026 critique, ask 4
of the merged list. **Route:** the heading of the station page, on a phone.

The field meets the 24px floor the accessibility matrix holds every target to, and
sits under the 44px the row actions promise. The field is the page's own identity
interaction, so the 44px promise is worth either keeping or saying why it does not
apply here.

---

## O11 -- Provenance and approximation are one generic disclaimer (S35)

**Kind:** code, decided. **Raised:** the re-envision pass of 27 September 2026; the
owner's comment is **Implement**. **Route:** the row's provenance panel.

Distinguish a reviewed fare, a conditional fare, missing service data,
classification coverage and seller-link confidence as compact signals, without
inventing a numeric score, so a reader can assess the exact uncertainty instead of
reading one disclaimer as applying to every row equally. The row already carries
every input it needs: this is presentation rather than new data.

---

## O12 -- Deep links are not verified per seller, date and party (S31)

**Kind:** code, decided. **Raised:** the re-envision pass; the owner's comment is
**Implement**, and it was queued next behind the railcard work, which has landed.
**Route:** `retailer.py` and the row's ticket link.

Verify the handoff per seller, date and party before it is enabled, with a working
fallback and the destination's link mode stated, and never infer success from a URL
that merely has query parameters. The party a link is built for is now whichever
the reader chose.

---

## O13 -- The chooser needs a known station name or a code prefix (C27, S08)

**Kind:** decision with a data question inside it. **Raised:** C27 on 27 September
2026, re-verified the same day; S08 is the same ask. **Route:** the root chooser.

**Evidence.** Matching is by name substring or three-letter code prefix, and the
first forty matches are ranked by how many destinations the download prices from
that station. `PRODUCT.md` records correctly that the fares location records carry
no coordinates and no region. The chooser now says what its order is and is not,
and a no-match names the three-letter code route, so a reader is no longer left
guessing what a code is for.

**Why it is still open.** The limitation is stated on the page; the capability gap
is unchanged. A traveller who knows the town they live in but not the official
station name or its code has no natural way to choose an origin, and a high
destination count is not a "near me" signal.

**What it is not.** "Nearest station" is not derivable from this feed, and no
amount of work on the chooser will produce it. An earlier attempt to derive a
geography from the fares location records was the wrong answer to a real question.

**What would close it.** An opt-in geographic lookup backed by a **named,
reviewed** station-coordinate source, with manual search kept as the default, the
location permission explained in full before it is asked for, and the source's
licence and provenance recorded alongside the station index.

---

## O14 -- Date-specific schedules are not a product mode (S24)

**Kind:** decision. **Raised:** the re-envision pass. **Route:** the timetable and
the day control.

The release publishes times again since 16 October 2026 (NWR Schedule, ADR-0073),
so the question is whether a date-specific snapshot is worth having over the
aggregate schedules the CIF carries. The day control is a filter over them, and the
page already names the date each row's time is for. S25 sits downstream of whatever
this answer is.

**21 October 2026: the release is dated again, and this is why.** That day's run
published nothing: its share 3 wrote **78 pages in 139 minutes** and timed out at the
step's 150-minute bound, and the other eleven shares were cancelled with it. A share
of the six on 13 October wrote **458 pages in 108 minutes**; the difference is
that the release had no `--date`, and an undated page indexes the feed's whole
schedule window rather than one day's share of it (**2.4 s against 16.7 s** for one
Linlithgow page, and a Nottingham page still unfinished after ten minutes where the
dated one takes 49 s; the table is in `docs/build-performance-findings.md`). So the
release is dated again, and the page names its day.

That leaves this decision with a shape and a price, not a flag. An aggregate page
is not "the same build without `--date`": it would be one search that carries every
service day as an answer of its own, which is the shape the day control is for. Until
somebody builds that, this item is the design of it; the dated release is the
fallback, and it costs the 7x above.

---

## O15 -- Bank holidays and service exceptions are not inputs (S25)

**Kind:** decision, downstream of O14. **Raised:** the re-envision pass. **Route:**
the timetable's service dates.

Calendar handling, but only where the source supports it: bank holidays and service
exceptions as first-class inputs, with a clear fallback where they are not, so
fewer typical schedules are mistaken for holiday-specific service. A service-date
label is what makes such a fallback honest.

---

## O16 -- The site has no public name (S40)

**Kind:** decision. **Raised:** the re-envision pass; the owner asked for ideas and
got a shortlist in `docs/name-ideas.md`. **Route:** every page's title and heading.

Decide the public name before designing any identity assets, so the site is not
presented as a settled brand. Nothing is named in the code until one is chosen.

---

## O19 -- A release costs twelve runners, 39 minutes at the slowest share

**Kind:** decision. **Raised:** A1 of the 20 October 2026 poteto audit, whose
findings are settled in `docs/settled-work.md`. **Route:** the shard job.

The shard step runs twelve shares of about 237 pages against a 150-minute bound.
The figure this item was waiting for arrived on 26 October 2026: the twelve shares
took **18, 20, 20, 25, 27, 30, 33, 33, 33, 34, 34 and 39 minutes**, mean 28.8,
against the 100-minute nearing warning and the 150-minute bound
(`docs/build-performance-findings.md`, "The release's own bytes"). So the price of
a release is about twelve runners for forty minutes, not twelve runners that each
spend the bound.

What is left is whether that is too much for a site of 2,838 pages. The answer, if
it is, is less work per page rather than a longer bound: the per-share figure every
run prints says which part of a share is paying it.

---

## O20 -- The stop rule's own review was due on 21 October 2026 (S43, S44)

**Kind:** person. **Raised:** ADR-0004, which sets a written review for 21 October
2026; S43 and S44 are the two suggestions that attach to it. **Route:** no code.

Two questions: is there community traction, and does the owner still think the
thing is worth keeping. If the answer is not clearly yes, the default is to park it
-- the docs stay and no further time goes into it.

S43 is the part that would inform the answer: short, task-focused sessions with
someone who has a price ceiling and no destination, observed rather than recorded,
so the next changes come from interpretation failures instead of features that were
possible. S44 is the argument about what to measure before the date, and it is
measured at the community posts named in `PRODUCT.md` rather than by putting
analytics on the site: counting at the post level answers "is anyone coming"
without recording what a reader typed, filtered or shortlisted, which is personal
data with a different approval question attached and a separate licence gate.

The advice in one line is **do not spend the next week on polish before knowing
whether anyone is using the thing**. It is not a request to build anything.

---

## O23 -- The ticket link says "Tickets" and opens the seller's empty search

**Kind:** decision. **Raised:** task 2 of the 21 October 2026 Critiquito critique,
its second P1. **Route:** the row's ticket link and the disclosure above the table.

The visible word is "Tickets" beside a price, and the link opens the seller's own
search page with the journey not filled in. The comment in `row-actions.js` says
the word is deliberate: it is the one word a price-first column can hold, and the
accessible name and tooltip carry "opens in a new tab" and what the link does. The
longer explanation is in the folded "About the ticket link".

**What closes it.** Either the visible label ("Search at seller") or one
always-visible line above the table saying the links open the seller's search, and
the choice is what the row's primary action claims at a glance.

## O24 -- A row's price does not say return or single, or who it covers

**Kind:** decision. **Raised:** tasks 4 and 20 of the critique. **Route:** the
price and fare cells, the count line and the heading.

Two facts a reader needs to budget are not on the price. The fare cell says
"Regular fare", "Restricted fare", "Advance fare" or "Two tickets", so a plain
outbound single reads "Regular fare" and its price looks like a return's; the
helper that would say "Standard outbound single" (`ticketName`) is only used in
text that leaves the page. And with two adults the heading still reads "Train
fares up to £20 from GRANTHAM": the party appears in the count line
("for the two of us, two of the fare each row names"), not in the sentence a
reader reads first.

**What closes it.** A word in the fare cell (or a "single"/"return" tag beside the
price) and a heading clause when the party is two. The count line's wording is
already the party's own, so this is the two other surfaces agreeing with it.

## O25 -- A ticket-mode switch lowers the reader's budget without saying so

**Kind:** code. **Raised:** task 5 of the critique. **Route:** `clampBudget`.

A mode's ceiling is the dearest fare it carries, so choosing Singles on a £20
budget can lower it to the dearest single without a word. The state is better than
it was when the critique read it: the budget is remembered per mode and restored on
the way back (`STATE.budgetByMode`), so the reader's choice is not lost. What is
missing is the sentence at the moment it happens.

**What closes it.** One line beside the budget naming the new ceiling, the same
place the reader already reads "£126.00 for one adult". No undo is needed, because
the mode memory is the undo.

## O26 -- A two-ticket row can print "Direct" over its own trains

**Kind:** code. **Raised:** task 7 of the critique. **Route:** the Changes cell and
a two-ticket row's departures.

The cell reads the priced journey's change count, and a two-ticket row's panel
lists the tickets' own departures with their own change counts. On the critique's
Bulwell row the cell said "Direct" while two of the three listed trains changed,
and `fareSentence` added "(a through train, so you stay on the train the whole
way)". A row that contradicts the trains it lists is the one defect here that
undermines the price rather than the wording.

**What closes it.** The count derived from the trains the row shows ("Direct or 1
change" where they differ), or the two-ticket row's changes derived from the
tickets' own legs instead of the through journey's.

## O27 -- The privacy contact is escaped markup

**Kind:** code. **Raised:** task 9 of the critique. **Route:**
`build_release.DEFAULT_PRIVACY_CONTACT` and `build_render.render_privacy`.

The default contact is a sentence containing an `<a href>` to the issue tracker,
and the template writes it through `html.escape`, so the privacy page shows the tag
as text and the only way to reach the operator is not a link. The escaping is
right for a `PRIVACY_CONTACT` a person supplies; the default is not that. The test
asserts the URL is in the constant, not that the page renders a link.

**What closes it.** The default becomes plain text plus a URL the template links,
or the template stops escaping that one reviewed constant and keeps escaping the
configured one. One line, plus the check that reads the page.

## O28 -- A reader with JavaScript off gets no rows, and if the script is disabled rather than missing, no note

**Kind:** code. **Raised:** task 3 of the critique. **Route:** both routes, and the
note at `#scriptNote`.

The rows and the chooser's links are built by the script. A script that fails to
arrive is handled: the tag's `onerror` reveals a note, and the browser suite drives
that case. A script that never runs because JavaScript is off fires no `onerror`,
so the page is a heading, a table head and no rows, with no message and controls
that look usable.

**What closes it.** A `<noscript>` line on both routes. The data is already inline,
so rendering the first page of rows from the build is the larger version of the
same answer, and the critique offered both.

## O29 -- An undated timetable build says "No service that day" with no day

**Kind:** code. **Raised:** task 1 of the critique, its first P1. **Route:**
`JOURNEY_ABSENCE.no_service`.

The cell's brief form is the constant "No service that day", and the full form
falls back to "no service on the day this build asked about" when the build carried
no `--date`. The release is dated, so the reader of the published site always has a
day the words can mean; a hand-built undated timetable page does not, and its note
says no date was given. The critique read 14 of 17 rows that way on a synthetic
undated build.

**What closes it.** The brief form says "No service listed" when `DATA.serviceDate`
is empty, or an undated timetable build is refused and says why.

## O30 -- Reader-facing prose still carries build vocabulary

**Kind:** decision. **Raised:** task 10 of the critique. **Route:** the fare panel,
the empty state, the venue notes.

"Feed record (technical details)", "(21 in the feed)", "in this download",
"the feed's own rule", and the chooser's column line, which says "Code" and
"Destinations", are the build's words in a traveller's sentence. The
glossary inside the method disclosure now defines ITX, DTD, RR, flow and NRE
(audit item 44), so the words are explained where the method is; the question is
which of them belong in the list itself.

**What closes it.** A decision on the handful of phrases a reader meets before
opening anything ("Technical details", "21 places priced from here"), with the
method detail left in the disclosure.

## O31 -- The empty state offers up to five doors

**Kind:** code. **Raised:** task 8 of the critique. **Route:** `renderEmpty`.

The block can hold the raise-the-budget door, "Show all destination types", the
two-adult door, and one door per other ticket mode that survives the type filter.
The critique pressed a page holding five buttons and found the £20 view offering
"Raise the budget to £7.00" beside a set whose own floor was £6.40. Two of those
have since improved: the raise door is now in the cheapest reachable row's own
price and names the place, and the two-adult door is offered only when it is
actually cheaper (`renderEmpty`). What remains is how many doors one moment holds.

**What closes it.** One primary door and at most one secondary; the other modes
are already reachable through the mode control above.

## O32 -- A one-station build's root is a one-row chooser

**Kind:** decision. **Raised:** task 12 of the critique. **Route:**
`_build_single_origin`.

A single-origin build writes a root chooser offering exactly the station it
priced, headed with that station's count, so the shape costs a click before its
only page. The published release is multi-origin and has no such root. The shape
is `run.py build`'s default and every test page is built through it.

**What closes it.** The root sends the reader straight to the page, or the shape
keeps the chooser and says why a one-row list is the honest index.

## O33 -- The station picker hides the station it is changing from

**Kind:** code. **Raised:** task 13 of the critique. **Route:** `picker.js`.

Opening the picker hides the heading's control and moves the field into the
heading, so the current station's name leaves the sentence it was in, and the list
below has no row marked as the one the reader is on. The critique's other points
in the same task have landed: the chooser writes its column line only over a list
that has rows, the no-match note has its own margin, the list is no longer headed
"EVERY STATION ON THIS SITE", and a page whose station list did not arrive
replaces the control with a plain name rather than explaining that it is not a
link.

**What closes it.** The open panel keeps the current station visible and marks it
in the list.

## O34 -- A phone row's numbers stand alone, and the rail's slider is a few dozen pixels

**Kind:** decision. **Raised:** tasks 14 and 24 of the critique. **Route:** the
phone row and the budget rail.

Below 44rem the row drops the label track on purpose -- the comment in
`station.css` argues each value says what it is -- so "45m" and "Unknown" read with
nothing beside them, which is the half the critique is right about: a duration and
an absence do not name themselves. The rail is `flex: 1; min-width: 4rem` beside a
`white-space: nowrap` ceiling note, so at 304px (200% zoom) the note overhangs the
right edge, which is the defect the 25 October fix found from the other side, and
the slider is squeezed into what is left.

**What closes it.** A word after the duration and the absence ("45 min", "Changes
not listed"), and a rail whose slider keeps a usable width at 304px, or a stated
decision that the phone row needs no labels.

## O35 -- The shortlist dock has no fare, no price order and no undo

**Kind:** code. **Raised:** task 18 of the critique. **Route:** the dock.

A dock row carries the name, price, time, changes and a remove control, so two
places priced as different kinds of ticket cannot be compared; the order is the
active list's, which is price-sorted for the three named modes and the cheapest
list's own order otherwise; and Clear announces the clear and moves focus but
offers no undo. Share and Copy have since landed properly: Share opens a panel with
a real link and says what the link carries (audit item 36), and a refused
clipboard says so.

**What closes it.** The fare's name in the row, a sort by the price on screen, and
an "Undo" on the clear announcement.

## O36 -- The row's copied journey leaves out the price and the times

**Kind:** code. **Raised:** task 19 of the critique. **Route:** `journeyText`.

The copied text names both stations, the ticket, the date and the passengers, and
the shortlist's copy adds the price, the time and the changes. The row's does not,
so the note a reader pastes to a seller has no fare on it. The failure path is
fixed: a refused clipboard says "Could not copy automatically" and shows the text.

**What closes it.** The price and the day's time in `journeyText`, which is two
lines and one assertion.

## O37 -- The day control names no day and confirms no change

**Kind:** code. **Raised:** task 21 of the critique. **Route:** the day control and
the heading.

The control's label is "Times for", its help line explains that interchange
stations are the build's day only, and the heading is the budget and the station.
Choosing another day re-renders the table with no sentence saying what changed, and
the choice does travel: the copied shortlist writes "Times for: <date>", and the
address carries the day.

**What closes it.** The day in the heading (or on the control's own line) and one
confirmation after a change.

## O38 -- The theme switch has no visible label

**Kind:** code. **Raised:** task 22 of the critique. **Route:** `THEME_TOGGLE`.

The control is a `role="switch"` with `aria-checked` and an sr-only "Dark theme",
so a screen reader says what it is; a sighted reader sees a moon or a sun and gets
no tooltip. The other half of the task has landed: the footer's two links are real
links with a space between them and 44px targets.

**What closes it.** A visible word or a title on the switch.

## O39 -- Table columns move between filters

**Kind:** code. **Raised:** task 23 of the critique. **Route:** the results table.

No column has a stated width and the table is not `table-layout: fixed`, so the
Time column's edge follows the longest value in the list and moves when a
destination type or a ticket mode changes the rows.

**What closes it.** Widths per column, and a check that reads a column's edge
across two filters.

## O40 -- Pagination does not say which results the page shows

**Kind:** code. **Raised:** task 17 of the critique. **Route:** the pager.

Both unusable controls are now disabled at their ends, and the page line reads
"2 of 3 pages" while the count line above the table says how many destinations the
list holds. No surface says where this page starts and ends in that list, so on
page 2 a reader has to work it out from twenty rows.

**What closes it.** A range ("showing 21 to 40 of 52") in the page line, or a
decision that the page line and the count line are enough between them.

## O41 -- Station names are printed in the feed's capitals

**Kind:** decision. **Raised:** task 16 of the critique. **Route:** every station
name: the heading, each row, the chooser, the picker's list, the tab title.

The feed writes station names on a fixed-width card, so "GRANTHAM" and
"NEWARK CASTLE" arrive in capitals and the page prints them as the feed spells
them. The critique read a long list as shouting and asked for title case
("Newark Castle (NCT)"). The page's rule elsewhere is to say what the feed says,
so this is a decision rather than a defect: a title-cased name is the page's own
spelling of somebody else's record.

**What closes it.** A title-case rule at the one place a name is rendered, with
the accessible names and the known-fares table's own comparisons read to see what
else moves; or a decision that the feed's capitalisation is the honest name.

## Rejected, with the reason

Moved to `docs/settled-work.md` on 21 October 2026, under "Rejected designs, with
the reason", together with the five comments a comment audit saw and deliberately
kept.

## Where this came from

Every audit file that used to sit in `docs/audits/` is gone from the working tree,
each removed by the commit named with it, and its findings are either fixed, an
item above, or a rejection in `docs/settled-work.md`. `git show <commit>` reads one
back.

The four reviews that were still open on 19 October 2026 were merged into one list
on 21 October 2026: the engineering audit of 14 October, the critique, delight and
overdrive passes of 19 October. That file was itself removed on 26 October 2026,
the way a review with nothing open is removed: nine of its ten asks were already
items above (O3 to O10), the tenth was settled, its measurements moved here or to
`docs/build-performance-findings.md`, and its coverage table moved to
`docs/settled-work.md`, which is where a reader checks that no finding fell
between the two files. The same pass read the 21 October 2026 Critiquito critique
and the 23 October 2026 page-byte audit, filed what either still asked as items
above, settled the rest, and removed both. `docs/audits/` is empty, and a new
review belongs there only while it has an ask this file has not yet numbered.

- `docs/audits/2026-10-17-poteto-audit.md` and `docs/audits/2026-10-17-impeccable-distill.md`
  — removed on 19 October 2026; nineteen findings and the checks that hold them are
  in `docs/settled-work.md`.
- `docs/audits/2026-10-17-impeccable-review.md` — removed on 20 October 2026 once
  C21 landed; its C and D findings are in `docs/settled-work.md`, which is where the
  numbers code comments cite still resolve.
- `docs/audits/2026-10-14-impeccable-critique.md` — removed on 19 October 2026; its
  eight recommendations are settled in `docs/settled-work.md`.
- `docs/audits/2026-09-27-impeccable-critique.md`, `docs/audits/2026-09-27-reenvision.md`,
  `docs/audits/2026-09-29-real-grantham-page.md` — removed on 1 October 2026, in the
  commit that created this file.
- `docs/audits/2026-09-29-promise-gap-audit.md` — filed away on 30 September 2026.
- `docs/audits/2026-09-23-poteto-mode-audit.md` — retired on 23 September 2026.
- `docs/audits/2026-10-10-test-suite-audit.md`, `docs/audits/2026-10-08-agent-efficiency-architecture.md`,
  `docs/audits/2026-10-10-four-dimension-app-audit.md`,
  `docs/audits/2026-10-12-build-cost-and-data-architecture.md`,
  `docs/audits/comment-audit-2026-10-14.md`, `docs/audits/2026-10-09-impeccable-route-audit.md`,
  `docs/audits/2026-10-14-impeccable-clarify.md`, `docs/audits/2026-10-18-agent-friendliness-plan.md`
  — removed between 14 and 18 October 2026, each in the commit that settled its
  findings; their rows and figures are in `docs/settled-work.md` and
  `docs/build-performance-findings.md`.
- `docs/audits/2026-10-14-app-engineering-audit.md`, `docs/audits/2026-10-19-impeccable-critique.md`,
  `docs/audits/2026-10-19-impeccable-delight.md`, `docs/audits/2026-10-19-impeccable-overdrive.md`
  — removed on 21 October 2026, merged into one asks list, itself removed on
  26 October 2026.
- `docs/audits/2026-10-21-audit-asks.md`, `docs/audits/2026-10-21-critiquito-design-critique.md`
  and `docs/audits/2026-10-23-page-byte-budget.md` — removed on 26 October 2026.
  The first two left their still-open asks as O3 to O10 and O23 to O41; the third
  left O1, which the release measured and closed the same day. Every settled
  finding, the merged list's coverage table and the critique's exclusions are in
  `docs/settled-work.md`, and every figure in
  `docs/build-performance-findings.md`.
