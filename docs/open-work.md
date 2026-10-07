# Open work

**Opened:** 1 October 2026
**Scope:** every item the project's own audits left open, in one place, so that
nothing is open only because it lives in a file nobody has re-read.

This file replaces three audit documents that sat in `docs/audits/` and were
removed in `826dfeb`, the commit that created this one. Two of them are closed —
every finding in each is fixed, and the record of the fix is the ADR that carries
it, not a restatement here. One had a single open finding. What is left is what
is below, and the closed work is listed at the foot so that a reader looking for
"was this ever looked at" finds the answer without reading three files of prose
first.

An item leaves this file when it is done, and it leaves by naming the commit and
the test that hold it, or by naming the ADR where it was a decision rather than a
fix. Nothing leaves on the strength of having been discussed.

---

## The open findings

### C27 — the chooser requires a known station name or a code prefix

**Severity:** P2. **Route:** the full-build root chooser.
**Raised:** 27 September 2026, re-verified the same day, still open.

**Evidence.** Matching is by name substring or three-letter code prefix, and the
first forty matches are ranked by how many destinations the download prices from
that station. `PRODUCT.md` records correctly that the fares location records
carry no coordinates and no region. The chooser now says what its order is and
is not — "Ordered by how many destinations this download prices from each
station — not by how busy it is, and not by how near it is" — and a no-match
names the three-letter code route, so a reader is no longer left guessing what a
code is for.

**Why it is still open.** The limitation is now stated on the page; the
capability gap is unchanged. A traveller who knows the town they live in but not
the official station name or its code still has no natural way to choose an
origin, and a high destination count is not a "near me" signal.

**What it is not.** "Nearest station" is not derivable from this feed, and no
amount of work on the chooser will produce it. An earlier attempt to derive a
geography from the fares location records was the wrong answer to a real
question.

**What would close it.** An opt-in geographic lookup backed by a **named,
reviewed** station-coordinate source, with manual search kept as the default and
the location permission explained in full before it is asked for — and a source
whose licence and provenance are recorded alongside the station index. That is a
decision with a data question inside it, which is why it is here and not in the
code.

### The checked-in facet reference data lags the registry

**Severity:** P3. **Route:** `reference-data/destination-facets.json`, read by
`atoc_fares.location_lookup_candidates` as one more additive facet source.
**Raised:** 7 October 2026, measured the same day, still open.

**Evidence.** A regeneration run on the 24 September 2026 download
(`python tools/regenerate_destination_facets.py --out <a copy>`) writes 10 facets
and 463 station records against the checked-in file's 7 facets and 294. Beyond
the three day-out sources that run added (rspb 9, national_trust 9,
national_park 19), the file predates three shipped decisions: the ADR-0063
hybrid prune (heritage 43 -> 38, dropping BDI, BDQ, BUX, CTR, RMD, which is what
the prune exists to do), the ADR-0064 seaside supplement (+8: Blackpool x3,
Brighton, Southend x3, Weston-super-Mare), and the transport name markers
(6 -> 155).

**Why it is still open.** It is a generated artefact and it is read additively,
so a stale copy costs nothing at build time; refreshing it is a data commit of
its own, and bundling three releases of drift into one facet change hides what
moved. ADR-0062 and ADR-0064 each shipped without a regeneration run, so the
lag is a habit rather than a decision.

**What would close it.** One `tools/regenerate_destination_facets.py` run on the
current download, committed on its own with the per-facet counts in the message,
plus a decision on whether the run belongs in the release checklist or in CI
behind a comparison that fails when the file and the registry disagree.

### A whole-network build gives every page the national timetable

**Severity:** P1 for build cost. **Route:** `run.bat` / `build_stations.py` / the
deploy workflow, that is, every path that builds through `--all-origins`.
**Raised:** 7 October 2026, measured the same day, still open.

**Evidence.** A page built against the fully loaded fares feed takes **5.1 s**
with a timetable index scoped to that origin's destinations and **did not finish
in 8 minutes** with the whole national index (5,262 schedules against 419,589).
`python build_stations.py GRA NOT --no-serve` wrote no page in 23 minutes. The
full table, the reproduction commands, and the caveats (5.5 GB free against a
6.4 GB floor, the unit suite running alongside) are in
`docs/build-performance-findings.md`.

**Why it is still open.** The cause is named and not fixed. `build_demo_page`'s
single-origin path already computes `focus_destinations` and a per-origin cache;
`--all-origins` passes `focus_origin=None` and no cache, so
`build_workers.init_worker` indexes the whole country for every worker and every
page.

**What it is not.** Not a machine problem and not a fares problem. The whole
fares feed loads in 37.6 s, the pricing pre-pass is 0.01-0.09 s per origin, and a
prices-only page renders in under half a second. Only the timetable index is out
of scale.

**What would close it.** Give each origin in the all-origins pool its own focused
timetable index and its own cache, exactly as the single-origin path does, and
re-measure the published build's wall clock against the workflow's
`timeout-minutes: 150` (that figure predates ADR-0061 and the service week, so it
needs re-measuring in any case).

---

## Suggestions not yet taken up

From the re-envision pass of 27 September 2026. Each carries the benefit it was
argued for, because a suggestion without one is a wish.

### Needs a data source or a licence answer

| | Suggestion | What it is for | Lyden's comment | Where it stands |
|---|---|---|---|---|
| **S08** | An opt-in "find my station" path, backed by a reviewed coordinate source, keeping manual name/code search as the default and explaining exactly what the permission does before asking | A traveller who knows their town but not the station's CRS code can still start, without silently collecting location data | | Open. It is the same data question as C27, and it is gated on the same named source. |
| **S24** | Date-specific schedules as an explicit product mode: build or select a timetable snapshot for the named date, label its service date beside the times, and keep undated aggregate schedules visibly indicative | A journey time is tied to the day the reader cares about rather than to a mixed schedule set | | Open. The whole network now publishes with the national timetable, which is the aggregate case this is about. |
| **S25** | Calendar handling, but only where the source supports it: bank holidays and service exceptions as first-class inputs, with a clear fallback where they are not | Fewer "typical" schedules are mistaken for holiday-specific service | | Open, and downstream of S24. A service-date label is what makes a fallback honest. |
| **S31** | Deep links verified per seller, date and party before they are enabled, with a working fallback and the destination's link mode stated; never infer success from a URL that merely has query parameters | The handoff is the shortest one known to work, rather than the shortest one that looks right | **Implement** | Queued next. The railcard work it waited on is landed, so the party a link is built for is now whichever the reader chose. |

### Needs a product decision, not a source

| | Suggestion | What it is for | Lyden's comment | Where it stands |
|---|---|---|---|---|
| **S35** | Provenance and approximation as compact confidence signals: distinguish a reviewed fare, a conditional fare, missing service data, classification coverage and seller-link confidence, without inventing a numeric score | A reader can assess the exact uncertainty instead of reading one generic disclaimer as applying to every row equally | **Implement** | Queued. The row already carries every input it needs, so this is presentation rather than new data. |
| **S40** | Decide the public name before designing any identity assets; until then do not present "Rail Budget" as a settled brand | The site looks authored without committing to an unapproved name or to generic SaaS decoration | **Can you help me brainstorm brand/name ideas?** | Answered with a shortlist in `docs/name-ideas.md`. Nothing is named in the code until one is chosen. |

### Needs people, not code

| | Suggestion | What it is for | Lyden's comment | Where it stands |
|---|---|---|---|---|
| **S43** | Short, task-focused sessions with the intended traveller: someone with a price ceiling and no destination has to find a usable day out, then explain the fare and time they chose | The next changes address real interpretation failures rather than adding features because they are technically possible | I will get to this, once the product is a little closer to ready | Held deliberately. The owner's call, and the reasoning still holds. The session is worth more once there is a whole network to find a destination in rather than one station. |
| **S44** | Instrument the existing tripwire before investing in a redesign: venue-level visits, comments and return signal only under an approved privacy approach | Effort stays bounded by the experiment, and a polished interface is not mistaken for demonstrated demand | I don't understand what this suggestion means | **Explained below.** No action; the tripwire's date is the owner's. |

### What S44 means, in plain words

The project already has a stop rule, and it is a date rather than a number.
[ADR-0004](../adr/ADR-0004-staged-plan-and-stop-rules.md) sets a written review
for **21 October 2026**. Two questions. Is there community traction, and does
the owner still think the thing is worth keeping. If the answer is not clearly
yes, the default is to park it, which means the docs stay and no further time
goes into it.

S44 is an argument about what to do before that date. It says that if you are
about to spend a week making the page prettier, you should find out first whether anyone is
arriving, arriving twice, or telling anyone else. And it says to measure that at
the venues the traffic comes from, which are the community posts named in
[PRODUCT.md](../PRODUCT.md), rather than by putting analytics on the site.

The reason it says venues rather than the site is the licence and privacy
position. This project can add a counter or a referrer to a page it serves.
Recording what a reader typed, filtered or shortlisted is personal data with a
different approval question attached, and the DTD feed licence is a separate
gate again. Counting at the community-post level answers is anyone coming
without answering anything on the page.

The advice in one line is **do not spend the next week on polish before knowing
whether anyone is using the thing**. It is not a request to build anything.

## Rejected, with the reason

Three suggestions were rejected by the owner on 1 October 2026. They are kept
here rather than deleted, because a rejected suggestion with a reason stops
the next person from re-deriving it.

| | Suggestion | Why it is not worth doing |
|---|---|---|
| **S09** | Region, town or rail-network grouping once a geography source is chosen | The chooser already ranks all 2,718 priced stations and filters by name or code across them. Grouping adds a second way to browse a list nobody needs a second way to browse, and it needs the same geography source as S08 and C27 for no extra reach. |
| **S27** | Discovery entry points such as "cities under £20" or "seaside under £20" | It is a curated editorial list dressed as a derived one. The project's rule is that a page says what the feed says and nothing more, and a landing page that decides which towns are worth a click is that page making a claim it has no evidence for. |
| **S46** | A "Was this shortlist useful?" prompt or an optional feedback route | It is a tracker with a small payload, and it collects exactly the thing the page is careful not to collect. The same question is answered better by the S43 sessions, which are observed rather than recorded. |

## Questions a future design pass still has to answer

1. **Is the release meant to expose the whole station network now, or
   intentionally just Grantham?** The route contract no longer depends on the
   answer — the deployment publishes a one-station chooser whose contract is the
   same as a full build's, every internal link resolves, and the release
   manifest is proved against the files on disk. What is open is the *coverage*
   decision: a one-station release is coherent, but a reader arriving at a "where
   can we go from anywhere" product meets exactly one origin. This is the only
   question in the 27 September critique that its own re-verification could not
   close, and it is a decision rather than a defect.
   Answer: Should expose the whole station network
   **Answered, and shipped.** The deploy workflow builds `--all-origins`, so
   every one of the 2,718 priced stations has a page and the root is the
   chooser offering all of them. The objection was cost, and it was entirely
   ADR-0024's projection of about two days, measured on an invented uniform feed
   where every station priced 2,500 destinations. The real feed's median origin
   prices 91, and a whole-network build with journey times measures at about 81
   minutes on a two-core runner. ADR-0024 is amended with the numbers, and
   [ADR-0050](../adr/ADR-0050-the-release-is-the-whole-network.md) is the decision.
2. **Is the Two Together enforcement the answer the brief wanted?** The solo case
   is now refused rather than shown, which the enforcement test holds. Whether
   the brief wanted that, or wanted an explicitly conditional per-person
   comparison instead, was never put to it.
   Answer: I don't understand the question exactly, but Two Together is supposed to be just ONE of the entire collection of available railcards to choose from. Also, the default should be no railcards selected, until one is added, then it should be remembered by the browser
   **Answered, and the question was the wrong shape.** Two Together was never
   the only railcard the page knew about; it was the only one it offered. The
   feed's catalogue holds 382 codes, and the passenger cards arrive in families:
   16-25 is YNG, and Y3R for three years, YN3 bought online, RYP as a
   repaperminted replacement. A reader holding any of them holds the same card,
   so a railcard is modelled as a product with the codes the feed carries for it,
   and the reviewed set is six products rather than one card.
   **Landed.** The page offers all six in one control, nothing is selected by
   default, and the browser remembers the reader's card.
   [ADR-0052](../adr/ADR-0052-the-railcard-is-one-of-a-collection.md) is the
   decision, and its argument is the payload shape. A card's whole answer costs
   433 bytes a row, so six of them is a sixfold regression on a page that already
   carries 411KB. The row keeps a price and a rule key per card, and the page
   writes the sentences. The real page went from 411,583 to 421,124 bytes and now
   carries six cards where it carried one.
3. **Does the local preview keep its own build step, or does the runner become a
   server for a folder the builder produces?** The concrete cost of the split has
   been fixed, so the question is open again rather than answered by a defect:
   the runner still shells out to the builder, which works, and no finding says
   it should not.
   Answer: I don't know - apply the best-practice decision
   **Answered.** Best practice for a static site with a build step is that the
   two are separate commands, because a server that rebuilds on every start
   cannot tell you what it is serving. `run.py` now serves `_site/` as it is and
   says so, builds once on a clean checkout because there is nothing to serve
   then, takes `--rebuild` to build again, and `--no-build` to refuse rather than
   build what it was told not to.
   [ADR-0051](../adr/ADR-0051-the-runner-serves-and-the-build-builds.md).
   **Amended 1 October 2026.** The separation stands and the default is
   reversed: `python run.py` now builds the whole network, because a
   single-origin build cannot render the heading's station control at all, and
   it rebuilds when the sources are newer than the build it would serve,
   because a stale page answers nothing on it.
   [ADR-0055](../adr/ADR-0055-the-runner-builds-what-the-reader-will-ask-for.md).

---

## Settled in this pass, and where the record is

Every item below is closed. None of it is restated here beyond the pointer,
because a reader checking a closure wants the ADR and the test.

| Item | Closed by | Held by |
|---|---|---|
| S17's first half — one inclusive "up to £X" resolver feeding the heading, the control, the count line and the URL | ADR-0019, in place before this pass | the budget contract tests in `tests/test_build_demo_page.py` |
| S16 — the list is ordered by the price on screen | no code change needed; `render()` already sorted by `priceOf()` | the railcard reading in `tests/browser_test.cjs`, added and recorded as a guard rather than a gate — see ADR-0048 |
| S17's second half — the page says where the budget stops, and the figure is the stop | ADR-0048 | `test_the_page_says_where_the_slider_stops_and_the_figure_is_the_stop`, the tamper that hardcoded £500.00, and the browser suite's two readings |
| S34 — a human-readable feed-change report for the operator | ADR-0049 | `tools/test_feed_change_report.py` |
| C27's sibling findings, C01–C31 | five passes, 27–28 September 2026 | the commits that carried each change; the finding ids that survive as reasons in the code (`C14` in `SHARED_CSS`) |
| Question 1, the release coverage, settled by building every priced station rather than Grantham alone | ADR-0050 | `timeout-minutes: 150` against the measured extrapolation, and `tools/page_bytes.py --site _site` as the only step that reads the release's bytes |
| A railcard is a product with the feed's codes for it, not a code | landed ahead of the page that consumes it, so each unit builds and verifies | `ReviewedRailcardTest` in `tests/test_atoc_fares.py`, six tests over families, aliases, bounds and the absent-code report |
| Question 2, the railcards, with the page offering the reviewed collection, none selected by default, and the browser remembering the choice | ADR-0052 | `RailcardAdultBoundsTest`, and the browser suite's six collection checks, which are the menu, the default, the memory, the address, an unpriced code, and the party rule |
| Question 3, the runner, with the build and the serve as separate commands | ADR-0051, amended by ADR-0055 | `RunnerBuildOrServeTest`, five tests over a site existing, not existing, a flag asking for a rebuild, and sources newer than the build |
| The row names its fare in a word; the feed's code waits in the row's disclosure | ADR-0053, superseding decision 2 of ADR-0040 | `test_result_changes_and_mobile_cells_are_accessible` and `test_table_headers_name_their_columns_and_scope`, and the browser suite's fare-type and Feed-record readings |
| The shortlist is one select and one strip above the table, not a button on every row | ADR-0054 | the browser suite's five shortlist checks, and the select's change listener's tests in `tests/test_build_demo_page.py` |
| The station name in the heading is the field you type into | ADR-0056 | the heading-picker checks, including Escape pressed in the field rather than in the panel |

### The measurements three ADRs lean on

ADR-0040, ADR-0041 and ADR-0043 were settled from a rendered-page audit of the
published Grantham page on 29 September 2026. Their evidence is kept here rather
than in a file that would otherwise have been deleted, because an ADR that cites
a measurement needs the measurement to still exist.

**Finding 1 — the price column was 56px wide, so the price wrapped** (settled by
ADR-0040 §1). Seven columns measured station 176px, price 56px, time 62px,
changes 72px, fare 225px, conditions 234px, tickets 352px. Thirteen of the first
twenty prices painted as two lines: `£10.10` rendered as `£10.1` over `0`, and
the same for £12.60, £13.30, £13.70, £14.10, £14.40, £14.70 and £15.40.
`CHANGES` wrapped mid-word in its 72px column. Nothing in `SHARED_CSS` refused a
wrap on `th` or on `td.num`, so each column took its width from the widest thing
in it that could not break — and for a two-word header that is the header.

| Tamper | Check result |
|---|---|
| price column forced to 56px, `white-space: normal`, CHANGES-only | **FAIL** — `{"text":"Changes","lines":2,"width":56}` |
| price column forced to 40px, same | **FAIL** — `£8.70` in 2 lines, `50m` in 2 lines, `CHANGES` in 3 |
| as shipped | **ok** — 18 cells measured, price column 78–81px |

**Finding 2 — forty cells restated the mode the reader had already chosen**
(settled by ADR-0040 §2). All twenty rows read `Unrestricted Anytime Day Return`
in FARE and `No travel conditions on this fare in the feed.` in CONDITIONS — two
sentences about the *mode*, printed twenty times. Each row measured 81px, of
which those two columns were the greater part; twenty rows occupied 1620px,
about two laptop screens. With the fare's own code and a differing-condition
word in their place, rows measure **49px** and twenty occupy 980px. The
condition stayed reachable one disclosure away, so C07's pointer survives with
its wording made true.

**Finding 3 — the count line was 205px from its table** (settled by ADR-0040 §3).
At 1440×900 the count line sat at y=654 and the table began at y=859, with six
paragraphs between them, and the first fare began at y=914 — fourteen pixels
below a 900px laptop's fold. At 390×844 the same block measured 455px. After the
change: **8px**, nothing between them; the first fare at y=867, thirty-three
pixels above the fold; no sideways scroll at 321/705/760/1024/1280/1440px.

**Finding 4 — five controls on every row** (settled by ADR-0043). The Tickets
cell carried `Tickets`, `5 times`, `Card details`, `Copy` and `Shortlist` — a
hundred pointer targets on page one, inside one cell 352px wide at 1440px and
240px at 705px. Recorded rather than fixed at the time, because the decision
changes what the row promises at a glance; ADR-0043 is that decision.

**Finding 5 — the cheapest row was tinted with no legend** (settled by ADR-0041).
`tr.best` set a background wash on the cheapest row and nothing on the page said
so, on a page that names no "best", no "recommended" and no star. Recorded
rather than fixed at the time, because the tint was also the only visual
grouping of the sort order; ADR-0041 is that decision, and the order is now
stated in words in the count line instead.

**Not a design fix.** The deploy workflow publishes a single origin
(`--origin GRA`), so the published artefact has one station page, no Change
chevron in the heading and only Privacy in the footer. That is a coverage fact
about the release command — see question 1 above — and it is measured so the
next reader does not file it as a defect.

---

## Where this came from

All four files below are gone from the working tree; each was removed by the
commit named with it, and the findings they held are either fixed or restated
above. `git show <commit>` reads one back.

- `docs/audits/2026-09-27-impeccable-critique.md` — the public route audit.
  Thirty-one findings, thirty closed across five passes, C27 open. Removed in
  `826dfeb`.
- `docs/audits/2026-09-27-reenvision.md` — the re-envision pass. Thirty of its
  suggestions built; the rest are above, with the three this pass closed marked
  in the settled table. Removed in `826dfeb`.
- `docs/audits/2026-09-29-real-grantham-page.md` — the rendered-page audit of
  the published Grantham page. Five findings, all settled; its measurements are
  above because three ADRs cite them. Removed in `826dfeb`.
- `docs/audits/2026-09-29-promise-gap-audit.md` — filed away in `d33b762` after
  the gap it found was closed, and deliberately not reopened here.
- `docs/audits/2026-09-23-poteto-mode-audit.md` — retired in `1ce8741`, before
  this file existed.
