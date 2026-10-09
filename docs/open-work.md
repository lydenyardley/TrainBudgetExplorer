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

## Day-out decisions, as shipped

ADR-0063, the hybrid closest-station prune, is done. The facet reference entry
below is the evidence: heritage dropped BDI, BDQ, BUX, CTR and RMD, which is
the prune removing a station the coordinates put too far from the site.

ADR-0064, the seaside chip implying a named coastal proof, is done. ONS stays
the primary tag, the reviewed CRS supplement is what moved seaside from 142 to
150, and a seaside chip on a row is backed by a named proof.

ADR-0062 named RSPB reserves, National Trust visitor properties, and National
Park / National Landscape gateways as a backlog. That backlog is closed by
ADR-0065: the three are registry facets with one reviewed list each, and the
reference file carries them (rspb 9, national_trust 9, national_park 19). They
are not open work. ADR-0062's non-goals (no VisitBritain dump, no full NHLE
sweep, no raw OSM tourism tags, no polygon-wide landscape tagging) still hold.

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

### The slice equivalence sweep is a third done, in shards now (closed 9 October 2026)

**Severity:** P2, because it is the one claim about the published page that is
argued rather than witnessed. **Route:** `tools/check_slice_equivalence.py`.
**Raised:** 8 October 2026 with the slice work; re-measured the same day.
**Closed:** 9 October 2026 by the merge named below.

**Closed by.** `--shards 4` in one invocation over the whole request: **26,369
of 26,369 origin-days compared, 3,767 of 3,767 origins complete, 0 differing,
exit 0**, merged from the four shard checkpoints' own record of the request; an
independent `--merge 4` reproduces the verdict in a second, reading no feed.
The residue this entry existed for is gone -- no origin-day of the request is
left uncompared -- and nothing compared since the first sample has ever
differed: a slice is the whole feed's answers, and now the whole request has
been asked. The measured shape of the run, including what an oversubscribed
machine did to its rate and the launcher's own 4 KB pipe, is in
`docs/build-performance-findings.md`.

**What sharding carried.** `--shard N/M` compares a disjoint share of the request
and checkpoints to a file of its own; `--merge M` reads them back into one
verdict and refuses a union that is not the request; `--shards M` (or `auto`,
for what the machine holds) launches the children, streams each one's output
prefixed by its shard number, and merges -- one command for a whole sweep
(ADR-0066). The overnight single process handed 19,525 compared origin-days to
the shards as the base, so they inherited rather than re-compared; the final
6,844 were done four ways.

**What remains outside this entry.** `day=None`, the undated build, is not one
of the request's days and was never asked; that is the tool's own documented
limit rather than an open sweep, recorded under "What this does not cover" in
`docs/build-performance-findings.md`.

```
python tools/check_slice_equivalence.py --timetable feeds/timetable --shards 4
python tools/check_slice_equivalence.py --merge 4   # the verdict again, reading no feed
```

### The checked-in facet reference data lags the registry (closed 7 October 2026)

**Severity:** P3. **Route:** `reference-data/destination-facets.json`, read by
`atoc_fares.location_lookup_candidates` as one more additive facet source.
**Raised:** 7 October 2026, measured the same day. **Closed:** the same day, by
one `tools/regenerate_destination_facets.py` run committed on its own.

**What moved.** 7 facets and 294 station records become 10 and 463. rspb 0 -> 9,
national_trust 0 -> 9, national_park 0 -> 19 (the three sources ADR-0065 shipped),
heritage 43 -> 38 (dropping BDI, BDQ, BUX, CTR and RMD, which is what the ADR-0063
prune is for), seaside 142 -> 150 (the ADR-0064 reviewed supplement), transport
6 -> 155 and the source list 7 -> 10 (drift from registry changes that predate
this build). airport, island, nature and university are unchanged.

**The part that mattered, closed the same day.** Nothing ran the regenerator when
it should, so the drift was a habit rather than a decision: nothing in the suite
or in CI failed when the file and the registry disagreed. The fix was structural,
not a commit. `tools/check_facet_reference.py` regenerates the file into a
temporary directory and compares the result with the checked-in copy, naming
every facet that moved and the codes it gained or lost (capped at twelve a line,
because the transport facet moved 149 at once). It exits 1 on any difference, 2
when a facet could not be read at all or the checked-in copy is missing, and 0
when the two agree. The deploy workflow runs it beside the other gates, with no
`changed` guard: a gate that skips when the feeds are unchanged cannot catch a
file that is already stale, which is the only case there is. A feed revision that
moves the station count fails it too, deliberately -- the file describes the feed
it was generated from -- and the fix is the regenerator plus a commit.

**Proved against the real thing, not only the fixtures.** On the committed file
it exits 0 (10 facets, 463 station records). Given a copy with `seaside` removed
from AYW it exits 1 having printed `facet seaside: 149 in the checked-in copy,
150 regenerated; added AYW`. Given a path that does not exist it exits 2 before
reading a feed. `tests/test_check_facet_reference.py` holds 16 tests over the
comparison itself, which is a pure function and needs no feed.

### A whole-network build holds the national timetable for its whole life

**Severity:** P1 for build cost, and no longer blocking a two-station preview.
**Route:** `run.bat` / `build_stations.py` / the deploy workflow, that is, every
path that builds through `--all-origins`. **Raised:** 7 October 2026.
**Partial fix landed:** the same day for the fares feed, 8 October 2026 for the
timetable a page reads, and the same day again for the feed that timetable is
read from.

**Evidence, corrected by measurement on 7 October 2026.** The index's *footprint*
costs the minutes, not the work per search. National index: 1.87 GB held (4.92 ->
3.05 GB free), 30 `best_journey` searches in 0.31 s, `_ensure_indexes` 1.1-2.3 s
per day. Focused on one origin: 50 MB held, the same 30 searches in 0.14 s, the
index build free. Searches are 2.3x slower nationally, not 80x: the page against
the unloaded-for-it national index does not fail because it is slow, it fails
because 1.87 GB is held beside the 2.1 GB fares feed on a machine with ~5 GB
free, and the build pages. `python build_stations.py GRA NOT --no-serve` wrote no
page in 23 minutes on 6 October 2026, and none in **24 minutes** on 7 October 2026
with the machine idle: 5.1 GB free against the 6.4 GB floor, the two feeds taking
11 minutes to load against the 93 s they take with room, and 0.88 GB free when the
first page started. `docs/build-performance-findings.md` has the table and the
reproduction.

**Partly fixed, 7 October 2026, and re-measured.** The fares half of the peak is
gone. Every build now writes the shared fare metadata and one index per origin
before it renders, and `build_workers.restore_worker_fares` gives the in-process
path the same per-origin slice a pool worker takes, so the 2.1 GB national fare
feed is released before the first page. The same command on the same idle machine
that had written no page in 24 minutes now **finished, exit 0 in 63 min 38 s**:
Grantham at 35 minutes, Nottingham at 63. Free memory bottomed at 0.39 GB while
both feeds were held, was back to 2.6-3.0 GB once the fares feed was released, and
held above 1.5 GB through both page writes. The entry stayed open after that run,
because the timetable half was untouched: `focus_origin=None` still held the
1.87 GB national index for every page, and that is what 35 minutes to the first
page was.

**Fixed for the page, 8 October 2026, and re-measured.** A page is now built from
`TimetableDb.focused(origin)`: the schedules that call the origin, and the
schedules that call any station those services call, cut in one pass out of the
database the build already holds. The cut costs **1.66 s** the first time (it
builds a TIPLOC-to-schedules index) and **0.248 s** for every cut after that, and
Grantham's slice is **114,244 of 419,589 schedules** -- a quarter of the feed
rather than the 5,262 a focus built from the fares feed's destination lists would
keep, because ADR-0061 lets a page show a row for a place with no flow, so the
services those rows are timed from have to be in the slice whatever the fares feed
priced. The same two-station command on the same feeds, on a machine with **2.1 GB
free** against the 6.4 GB floor, **finished, exit 0, in 20 min 53 s**: Grantham at
9.7 minutes against the 35 the run before it took, Nottingham at 20.8 against 63.
Both pages carry the same destinations, times and change counts as the pages of
that release and the same bytes apart from `builtAt`, the source fingerprint and
the key order of the page's `serviceWeek` object, which follows the process hash
seed (see `docs/build-performance-findings.md`). A control run of the same build with
`TimetableDb.focused` replaced by one that hands back the whole database wrote no
page in **25 minutes**, on more free memory through its page phase than the fixed
run had: `docs/build-performance-findings.md` has the numbers, the diff and that
control.

**Fixed on disk, 8 October 2026: the slices no longer need the feed.** A slice
used to be a list of references into the database it was cut from, so that
database had to be in the process: the one-worker path kept the parent's national
index for the whole build, and a pool worker parsed its own in `init_worker`,
56 s and 1.87 GB per process. `atoc_timetable.SliceIndex` writes each slice once
as a pickle, under a directory named for the feed, the parser's source
fingerprint and the layout version, and `build_demo_page.py --timetable-index`
reads a page's slice back with no timetable feed on the machine at all. When the
index covers every page the build writes, the feed is not read in the parent and
the pool workers are handed no timetable to parse either.

Measured on the real DTD download on 8 October 2026. Writing the index for
Grantham and Nottingham is one parse of the feed (53.9 s) plus the writes, **88 s
in total**, and the two files are 365.8 MB: GRA **114,244 of the feed's 419,589
schedules**, 2,747,086 calling points, 157.0 MB, and NOT 143,560 schedules,
3,728,248 calling points, 208.8 MB. Reading one back costs **4.4-5.9 s** and
**855 MB / 1,133 MB** of Python heap (tracemalloc) for those two files, against
the 56.7 s and 1.87 GB of parsing and holding the national index. `SliceIndex.save`
reads every file back before it reports it written, so an index that cannot be
restored fails at the tool that wrote it rather than at the far end of a build.
The same two-station command, given the index and the same feeds, **finished,
exit 0, in 3 min 44 s** with 4.7 GB free and wrote the same site -- both station
pages line for line apart from `builtAt`, the source fingerprint and the key order
of the page's `serviceWeek` object, which follows the process hash seed and did so
before this change (see `docs/build-performance-findings.md`).

**What is left of this entry, after that.** `build_workers.ONE_WORKER_FLOOR`
still describes the feed-parsing shape, because every build without an index
still pays it, and the indexed shape -- the fares feed plus one page's slice -- is
smaller and is measured in `docs/build-performance-findings.md` rather than
guessed at here. Indexing the whole network is still not a thing to do: holding
every origin's slice is holding the network 3,400 times over, so
`tools/build_timetable_index.py --all-origins` refuses without `--max-bytes`.

**What it is not.** Not a fares problem. The whole fares feed loads in 36.9 s,
the pricing pre-pass is 0.01-0.09 s per origin, and a prices-only page renders in
under half a second.

**The prescription, and what was built instead.** "A focused index and its own
cache per origin" cannot be built by parsing: a focused parse still costs 50.6 s
because the loader reads every record to decide what to drop, so 3,424 origins is
two days of CPU, and one pickle per origin is gigabytes of disk. The fix was the
other half of that sentence: one parse, and a focus derived from it in memory,
with the fares feed released before the first page so the render phase has room
for the slice it is about to cut.

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

### The 8 October 2026 agent-efficiency audit

`docs/audits/2026-10-08-agent-efficiency-architecture.md` is pruned to what it
found still open. Its eight findings are settled here with the artifact that
holds each one.

| Finding | Closed by | Held by |
|---|---|---|
| F1, the station page was one 2,938-line string, so no linter or `rg --type js` could see it and half of all fixes landed in it | the page's CSS and JavaScript are real files now, inlined by `page_templates.py` at import time | `page/*.js` and `page/*.css`, `tests/test_page_assets.py` for the seam, and `node --check page/*.js` in `tools/verify.py --fast` |
| F2, there was no agent entry point and the README's file table had drifted to omit 26 tracked files | `AGENTS.md` is the entry point: the map, both verify commands, and a rule table naming each rule's enforcer | `tests/test_agents_map.py` checks the map in both directions, so a module, page asset or operator tool that is not on it fails the suite |
| F3, `tools/replay/` was 7,492 lines of stale page copies that supplied 40% of the hits for `priceOf` and `shortlist` | deleted in this pass. Its last commit was `5b50a33` (2 October 2026) | `git checkout 5b50a33 -- tools/replay` reads it back. Nothing in the build, the tests or the release referenced it, and `tools/test_replay_driver.py` went with it |
| F4, the CI rebuild fingerprint was a hand-kept three-file list, written twice, and eight of the last 150 commits had changed only unlisted inputs | one script hashes every build input and both workflow steps call it | `tools/build_inputs.py`, held by `tools/test_build_inputs.py`, which fails on a transitively imported module that is not covered |
| F5, there was no single verify command, and the browser suite existed only as 115 lines of bash inside the workflow | `tools/verify.py` with `--fast`, `--full`, `--browser` and `--all`, written in Python so a Windows checkout runs it, called from CI before the feeds are downloaded | `tools/verify.py` itself; `--fast` is the two feed-scale tests its docstring names, and `tests/test_atoc_fares.py` shares its fixture through `setUpClass` |
| F6, the two hot test files were the biggest in the repository | the Python half: the page suite's classes moved out by feature seam, unchanged, over the fixture in `tests/page_harness.py` | `tests/test_page_runner.py`, `tests/test_page_caches.py`, `tests/test_page_output.py` and `tests/test_page_gates.py`; the same 32 classes and 327 tests as before the split. **Still open: `DemoPageTest` itself, 3,043 lines and 163 methods in one class, and the unsplit `tests/browser_test.cjs`** |
| F7, fixture-versus-real-feed gaps recurred | the rule is in `AGENTS.md`: a real-feed defect fix adds the minimal synthetic record with the fixing commit named | the passing-stop record in `make_synthetic_feed.py`, held by a test in `tests/test_atoc_timetable.py` |
| F8, measured figures lived in the README and were withdrawn rather than corrected | the README's measured section is a summary that links | `docs/build-performance-findings.md`, which holds "The whole network, measured" behind the README's link |

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
