# Open work

**Opened:** 1 October 2026. **Pruned and numbered:** 21 October 2026.

**Scope:** every item this project has left open, in one place, so that nothing is
open only because it lives in a file nobody re-reads. Each item carries its own
number, and the number is what a commit, an audit or a conversation can name.

Three things were pruned out of this file on 21 October 2026. The closed entries --
seven of them, some with a hundred lines of measurement narrative -- moved to
`docs/settled-work.md`, which is where a closure and the check that holds it
belong. The rejected designs moved there too, because a rejection is a decision
already made and this file is what is *not* decided. The four audits still open
were merged into `docs/audits/2026-10-21-audit-asks.md`, which keeps their
measurements; each item below names the audit ID it came from, so a reader who
wants the evidence for O7 goes there and reads S5.

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

## The seventeen items

| # | Item | Kind | Severity |
|---|---|---|---|
| O1 | The release's bytes may be over the budget, and the run that would print them stopped before building | measurement, then a settings decision | P1 for the release |
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
| O19 | A release costs twelve runners times a 150-minute bound | decision | P2 |
| O20 | The stop rule's own review was due on 21 October 2026 (S43, S44) | person | P1 for the project |

One wants a run this machine cannot give it (O1). Three are code whose decision
is already taken, and each changes what a reader sees (O9, O11, O12). Thirteen
wait on the owner's answer (O3, O4, O5, O6, O7, O8, O10, O13, O14, O15, O16,
O19, O20), and two of those now wait with their measurement in hand (O4 and O8).
None of them is blocked on a tool. **O21** (station-cluster `.FSC` fares and
the 109 destinations they newly price) and **O22** (the twelve destinations
newly priced by station-group expansion) both left on 23 October 2026 once
ADR-0075 and `REVIEWED_SETTLEMENT_FALLBACKS` landed (`docs/settled-work.md`).

---

## O1 -- The release's bytes may be over the budget, and the run that would print them stopped before building

**Kind:** measurement, then a settings decision. **Raised:** 12 October 2026 as a
P1 projection and lowered to P2 once ADR-0069's re-encoding made 536 MB look
comfortable; raised back to **P1 for the release on 21 October 2026**, because the
four pages measured that day suggest the budget may now be breached. **Route:**
the release build's own output, `tools/page_bytes.py`'s gate, and this file.

**What the 2.2 GB was, and what replaced it.** The projection came from a
24-station sample measured 12 October 2026, before ADR-0069 changed the payload's
encoding: re-encoding shard 1's 458 real pages gave **90.8 MB in place of 429 MB**,
which is **about 536 MB for 2,707 pages** against the **800 MB** budget. The 2.2 GB
figure is void and is not quoted here.

**What is still not measured.** 536 MB is an extrapolation from one shard, and it
predates the 16 October 2026 switch to Network Rail's CIF (ADR-0073), which added
schedules and therefore possible departures to every row. No whole-network build in
the release's own shape has run since either change. The gate runs in CI and
refuses an over-budget site, so a release cannot publish over budget; what no run
has printed is the number it would print, because the two runs since 19 October
stopped earlier than that.

**21 October 2026: four real pages, measured, and the bracket they leave.** Four
station pages were built from the local feeds and measured the same afternoon:
**Grantham 397 KB, Nottingham 449 KB, Linlithgow 283 KB, Ashwell & Morden
345 KB** of HTML, each with 41 to 63 KB gzip (the table and the command are in
`docs/build-performance-findings.md`). They were built from the DTD timetable,
because the build that reads the release's NWR CIF was killed while loading on
this machine, so the bracket is close rather than exact. They average **369 KB**, and at that average
2,707 pages are **975 MB against the 800 MB budget**. The 536 MB projection in the
paragraph above rests on a **198 KB** average measured on 12 October, before times
returned to the page on 16 October, and none of these four pages is near it,
including one from a small station. The budget holds only if the network's
average page is under **302 KB**, and nothing measured here shows that it is.

A whole-network spread build that would replace the extrapolation was attempted
the same day and was killed while building its pages, on a machine with **5.8 GB
free against the 6.4 GB the two feeds want**; it wrote its shared assets and no
station page. So this is not a curiosity about a number any more: if the average
is where these four pages are, **the release's own byte gate will refuse it**,
and the only way to know is the run.

**The earlier stop.** The push run of 19 October 2026 halted on a missing
`SCHEDULE_URL` repository variable, and the 20 October run's two-byte probe
answered that the fares feed's credential pair is refused by the CIF endpoint with
HTTP 401. Both are settings, written out in `docs/github-pages-deployment.md`; the
CIF subscription's own `SCHEDULE_USERNAME` and `SCHEDULE_PASSWORD` are what the
endpoint accepts.

**What closes it.** One release run that reaches the assemble job. Its
`python -m tools.page_bytes --site _site` prints the assembled site's bytes whether
it passes or refuses, and that figure replaces the extrapolation. No code change
is on this path.

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

## O19 -- A release costs twelve runners times a 150-minute bound

**Kind:** decision. **Raised:** A1 of the 20 October 2026 poteto audit, whose
findings are settled in `docs/settled-work.md`. **Route:** the shard job.

The shard step runs twelve shares of about 226 pages against a 150-minute bound,
and the 20 October 2026 run spent the whole bound on every share before writing a
page. If that price is too high, the answer is less work per page rather than a
longer bound, and the per-share figure every run now prints is what would say which
part of a share is paying it.

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

## Rejected, with the reason

Moved to `docs/settled-work.md` on 21 October 2026, under "Rejected designs, with
the reason", together with the five comments a comment audit saw and deliberately
kept.

## Where this came from

Every audit file that used to sit in `docs/audits/` is gone from the working tree,
each removed by the commit named with it, and its findings are either fixed, an
item above, or a rejection in `docs/settled-work.md`. `git show <commit>` reads one
back.

The four reviews that were still open on 19 October 2026 were merged into
`docs/audits/2026-10-21-audit-asks.md` on 21 October 2026: the engineering audit of
14 October, the critique, delight and overdrive passes of 19 October. The merged
file keeps their measurements and the coverage table that says, for every finding,
whether it is settled in `docs/settled-work.md` or open as one of the seventeen
items above. Removing the four files is the rule this directory keeps -- a review with
nothing open does not keep a file -- applied one level up: four files had ten open
asks between them, and the asks now live in one place.

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
  — removed on 21 October 2026, merged into `docs/audits/2026-10-21-audit-asks.md`.
