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

## The twenty items

| # | Item | Kind | Severity |
|---|---|---|---|
| O1 | The release's bytes are an extrapolation, and the run that would print them stopped before building | measurement, then a settings decision | P2 |
| O2 | A station page is 354 KB, and nobody has decided whether that is the payload | measurement, then a decision | P2 |
| O3 | The shortlist dock has no total (DL3) | decision | P2 |
| O4 | The dock and the budget rail are pinned at once (OV5) | measurement, then a decision | P2 |
| O5 | The fare horizon on the budget track (OV1, DL6) | decision | P2 for OV1, P3 for DL6 |
| O6 | The chosen station does not morph into the heading (OV7) | decision | P3 |
| O7 | The phone has no fold budget (S5) | decision | P2 |
| O8 | The drag has not been profiled on a phone (OV3) | measurement | P3 |
| O9 | The opened refinements panel leaves a 160px void | code | P3 |
| O10 | The heading's budget field is 37x36px against a 44px promise | decision | P3 |
| O11 | Provenance and approximation are one generic disclaimer (S35) | code, decided | P3 |
| O12 | Deep links are not verified per seller, date and party (S31) | code, decided | P2 |
| O13 | The chooser needs a known station name or a code prefix (C27, S08) | decision with a data question | P2 |
| O14 | Date-specific schedules are not a product mode (S24) | decision | P2 |
| O15 | Bank holidays and service exceptions are not inputs (S25) | decision, downstream of O14 | P3 |
| O16 | The site has no public name (S40) | decision | P3 |
| O17 | Six licence sentences still describe a prices-only release | reading | P2 |
| O18 | `docs/build-performance-findings.md` is a rule with no enforcer | design | P3 |
| O19 | A release costs twelve runners times a 150-minute bound | decision | P2 |
| O20 | The stop rule's own review was due on 21 October 2026 (S43, S44) | person | P1 for the project |

Six want a measurement or a reading before they are a change (O1, O2, O4, O8,
O17, O18). Three are code whose decision is already taken (O9, O11, O12). Eleven
wait on the owner's answer (O3, O5, O6, O7, O10, O13, O14, O15, O16, O19, O20).
None of them is blocked on a tool.

---

## O1 -- The release's bytes are an extrapolation, and the run that would print them stopped before building

**Kind:** measurement, then a settings decision. **Raised:** 12 October 2026 as a
P1 projection; lowered to P2 on 21 October 2026. **Route:** the release build's
own output, `tools/page_bytes.py`'s gate, and this file.

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

## O2 -- A station page is 354 KB, and nobody has decided whether that is the payload

**Kind:** measurement, then a decision. **Raised:** item 6 of the 14 October 2026
engineering audit, merged into `docs/audits/2026-10-21-audit-asks.md` as ask 1.
**Route:** the station page's payload and its shared script.

**Evidence, measured 14 October 2026** on a fresh real-feed build served from
`127.0.0.1:8899`: a station page is **354 KB raw, 53 KB gzip**, of which the
route's own CSS is 54 KB (17 KB gzip) and its script 149 KB (45 KB gzip); the
chooser is 28 KB and the privacy page 26 KB. The 800 MB site budget is not the
constraint here -- 2,712 such pages are -- so this is per-page parse and paint on a
phone.

**18 October 2026: the instrument was repaired, the figure was not taken.** The
audit's own measurement stood, but `tools/page_bytes` had been reporting 0 KB of
payload on every page, because it searched for a marker the renderer had stopped
writing. Both that and the empty-site case are failures now, and the split it
reports for the demo page is in `docs/build-performance-findings.md`. The
real-feed figure is still a real-feed build away.

**What would close it: a measurement, then a decision, in that order.** Split the
payload by ticket mode, time first paint on a 4x-throttled connection, and compare
that against the cost of the split -- a page whose payload becomes three fetches
learns a waterfall and can paint its list no sooner (ADR-0032 wants the plan
written before the figure is quoted). If the script or the CSS is the half that
matters, the cheaper change is a smaller shared asset rather than a split payload,
and `page/station/*` is already one file per panel, so the split is a build
decision and not a rewrite.

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

**Kind:** measurement, then a decision. **Raised:** OV5 of the 19 October 2026
overdrive pass, ask 9 of the merged list. **Route:** the station page's two sticky
surfaces.

The rail shipped on 20 October 2026 and took the table header's sticky offset with
it; the shortlist dock's own offset was not part of that. A page with a shortlist,
scrolled far enough, therefore shows the rail at the top and the dock at the foot
with about 700px between them at 390, and the rail is up exactly when the reader is
deep in the list and the shortlist matters.

**What proves it.** At 390 with two places shortlisted and the page scrolled to the
last row: how many rows are visible between the rail and the dock, and whether the
dock's own Copy is reachable without covering the row above it. The dock's height
depends on how many places are in it, which is why this is a measurement before it
is a change.

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

## O8 -- The drag has not been profiled on a phone (OV3)

**Kind:** measurement. **Raised:** OV3 of the overdrive pass. **Route:** the
station page's budget drag.

The desktop figure is **7.4ms** against a 50ms gate, measured 19 October 2026 and
recorded in `docs/build-performance-findings.md`. A mid-range phone is a different
machine, and ADR-0032 wants the machine named beside the figure. If the phone is
inside the budget, the figure is recorded and this closes; if not, the fix is one
`requestAnimationFrame` per burst of input events.

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

## O17 -- Six licence sentences still describe a prices-only release

**Kind:** reading, and the owner's. **Raised:** the NWR Schedule work of 16 October
2026. **Route:** two documents' licence prose.

`docs/publish-checklist.md`'s licence section carries the stale shape in three
places: the DTD terms paragraph's "how a prices-only page meets them" and "that is
why the release is prices-only", the Darwin bullet's "the published pages carry
prices only", and the Darwin-consistency bullet's "on a prices-only page".
`docs/dtd-licensing-and-data-access.md` carries it in three more: "which is why the
release is prices-only", "the release this project ships is prices-only", and "what
the prices-only release does today". Each is an assertion about this release rather
than about a hypothetical page, and each is a licence reading the owner holds. What
is owed is a re-reading, not a rewrite by whoever notices.

---

## O18 -- `docs/build-performance-findings.md` is a rule with no enforcer

**Kind:** design. **Raised:** 18 October 2026, when `AGENTS.md`'s rule table gained
a column for what fails and this rule could not fill it. **Route:** the rule table,
and every Markdown file that quotes a figure.

A document that quotes a figure in its own words, or a comment that dates a
measurement it took from elsewhere, is caught by a person or not at all. What would
close it is a check that reads every figure this repository states about itself and
holds it to the one place it was measured -- which needs the figures to be findable
in the prose, and nothing marks them today.

**The first version, and its cost.** Fail on a documented number that appears in
two files with different values, spelled as a plain integer or one of the money and
duration shapes the findings file uses. The false positives are dates, prices in
worked examples and counts of tests, so the allowlist is the work rather than the
reading. That is why this is a design item: a check whose allowlist is a list of
exceptions on the day it lands is the rule-with-no-enforcer again, wearing a gate.

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
whether it is settled in `docs/settled-work.md` or open as one of the twenty items
above. Removing the four files is the rule this directory keeps -- a review with
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
  `docs/audits/2026-09-29-real-grantham-page.md` — removed in `826dfeb`, the commit
  that created this file.
- `docs/audits/2026-09-29-promise-gap-audit.md` — filed away in `d33b762`.
- `docs/audits/2026-09-23-poteto-mode-audit.md` — retired in `1ce8741`.
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
