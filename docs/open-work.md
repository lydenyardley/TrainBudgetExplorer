# Open work

**Opened:** 1 October 2026
**Scope:** every item the project's own audits left open, in one place, so that
nothing is open only because it lives in a file nobody has re-read.

This file replaces three audit documents that sat in `docs/audits/` and were
removed in `826dfeb`, the commit that created this one. Two of them are closed —
every finding in each is fixed, and the record of the fix is the ADR that carries
it, not a restatement here. One had a single open finding. What is left is what
is below. The closed work is in `docs/settled-work.md`, moved there on 18 October
2026 so that a reader answering "what is open" does not read two thirds of a
closed history first (E19 of the 17 October 2026 poteto audit); a reader looking
for "was this ever looked at" goes there.

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

### P2 — the release's bytes are an extrapolation from one shard, and no run has printed the figure

**Severity:** P2, lowered from P1 on 21 October 2026. **Route:** the release
build's own output, `tools/page_bytes.py`'s gate, and this file. **Raised:** 12
October 2026 as a P1 projection; superseded by ADR-0069 on 13 October 2026 and
restated here (A2 of the 20 October 2026 poteto audit).

**What the 2.2 GB was, and what replaced it.** The projection came from a
24-station sample measured 12 October 2026, before ADR-0069 changed the payload's
encoding: re-encoding shard 1's 458 real pages gave **90.8 MB in place of 429 MB**,
which is **about 536 MB for 2,707 pages** against the **800 MB** budget. The
2.2 GB figure is void and is no longer quoted here.

**What is still not measured.** 536 MB is an extrapolation from one shard, and it
predates the 16 October 2026 switch to Network Rail's CIF (ADR-0073), which added
schedules and therefore possible departures to every row. A whole-network build in
the release's own shape has not run since either change, so the release is
probably inside its budget and nobody has proved it. The gate runs in CI and
refuses an over-budget site, so a release cannot publish over budget; what no run
has printed is the number it would print.

**What closes it.** The next release run. The assemble job's
`python -m tools.page_bytes --site _site` prints the assembled site's bytes
whether it passes or refuses, and that figure replaces this entry. No code change
is on this path.

**Where the bytes were, and why the figure could not be reasoned about.** On the
pre-ADR-0069 sample, Birmingham New Street's 1,626,528-byte payload put 1,050,373
of them in `railcardRules`: almost all two-ticket pair records (one per permitted
ticket × route × location combination, ADR-0061), and all but 18 referenced by a
row. So the block was combinatorial rather than a leak -- a hub that prices 288
destinations across three modes with many permitted pair splits produces thousands
of distinct pairs -- and the release's byte cost was a function of how many
two-ticket combinations the feed allows rather than of how many destinations it
prices. That is why ADR-0069's encoding change, and not a smaller sample, was the
thing to measure.

### A station page is 354 KB, and nobody has decided whether that is the payload

**Severity:** P2. **Route:** the station page's payload and its shared script.
**Raised:** item 6 of the 14 October 2026 engineering audit
(`docs/audits/2026-10-14-app-engineering-audit.md` — the whole-app audit's own file
was pruned to what it still asks for).

**Evidence, measured 14 October 2026** on a fresh real-feed build served from
`127.0.0.1:8899`: a station page is **354 KB raw, 53 KB gzip**, of which the
route's own CSS is 54 KB (17 KB gzip) and its script 149 KB (45 KB gzip); the
chooser is 28 KB and the privacy page 26 KB. The site budget is not the
constraint here — 2,712 such pages are — so this is per-page parse and paint on a
phone rather than the 800 MB question above.

**18 October 2026.** The instrument this item was waiting on was measuring
nothing. `tools/page_bytes` searched for a marker the renderer had stopped
writing, so it reported 0 KB of payload and 0 rows on every page, and the
invocation CI runs passed over an empty site too. Both are failures now, and the
split it reports for the demo page is in `docs/build-performance-findings.md`.
The real-feed figure is still a real-feed build away, so this item stays open: the
instrument is repaired, and the number it was blocking has not been taken yet.

**What would close it: a measurement, then a decision, in that order.** The audit
asked for the figure before the change (ADR-0032): split the payload by ticket
mode, time first paint on a 4x-throttled connection, and compare that against the
cost of the split — a page whose payload becomes three fetches learns a waterfall
and can paint its list no sooner. If the measurement says the script or the CSS is
the half that matters, the cheaper change is a smaller shared asset rather than a
split payload, and `page/station/*` is already one file per panel, so the split
is a build decision and not a rewrite.

### The 19 October 2026 delight and overdrive asks: the shortlist total, the dock under the rail, and two directions

**Severity:** P2 for the shortlist total, P3 for the rest.
**Routes:** the station page's shortlist dock and its budget control; the chooser
and station page's navigation.
**Raised:** the 19 October 2026 delight and overdrive passes,
`docs/audits/2026-10-19-impeccable-delight.md` and
`docs/audits/2026-10-19-impeccable-overdrive.md`, each pruned to what it still
asks. The suggestions that landed on 19 and 20 October 2026 (DL1, DL2, DL4, DL5, plus
OV2, OV6, OV8 and OV9 from the overdrive list, and OV4 since) are rows in
`docs/settled-work.md`, each naming the check that holds it.

What is left, and why each waits:

- **DL3, P2, the shortlist total.** One line under the dock's head: "Two places,
  £13.40 for one adult." It is a product decision about what the dock is for (a
  comparison list, or the beginning of a plan) before it is code, and the sum
  must be of the rendered rows' own party price, not a second array.
- **OV5, P2, the dock under the rail.** The rail shipped on 20 October 2026 and
  took the table header's sticky offset with it; the shortlist dock's own offset
  was not part of that, so a page with a shortlist, scrolled far enough, shows the
  rail and the dock pinned at once. It needs a measurement before it is a change,
  because the dock's height depends on the rows in it.
- **OV1, P2, and DL6, P3, the fare horizon.** A drawn track (1px ticks at every
  distinct visible fare) and its smallest form, one tick at the cheapest fare.
  A visual direction, and the mockups of 20 October 2026 argue against the drawn
  track as first described: on a £126 ceiling every fare is inside the left
  fifth of the slider, so the ticks read as a smudge rather than as a shape. A
  non-linear scale or the next few fares only is the version worth drawing.
- **OV7, P3, the shared-station morph.** Naming the chosen row's station token
  for the length of the click, so it arrives in the heading. OV6 shipped without
  it, and it stays unshipped if it is not clean at 390.
- **OV3, P3, the drag on a phone.** The desktop figure is 7.4ms against a 50ms
  gate; a mid-range phone has not been profiled, and ADR-0032 wants the machine
  named beside the figure.

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
python -m tools.check_slice_equivalence --timetable feeds/timetable --shards 4
python -m tools.check_slice_equivalence --merge 4   # the verdict again, reading no feed
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

### A whole-network build holds the national timetable for its whole life (superseded 12 October 2026)

**Severity:** P1 for build cost, and no longer blocking a two-station preview.
**Route:** `run.bat` / `build_stations.py` / the deploy workflow, that is, every
path that builds through `--all-origins`. **Raised:** 7 October 2026.
**Partial fix landed:** the same day for the fares feed, 8 October 2026 for the
timetable a page reads, and the same day again for the feed that timetable is
read from.
**Superseded 12 October 2026** by the per-origin facts of the build-cost audit:
the entry's own framing — "a whole-network build holds the national timetable
for its whole life" — is a statement about the *parent process*, and a page is
built from a slice of it, so the question is per-page rather than
whole-timetable. What survives is the per-origin slice work measured above,
which the 12 October distribution (`docs/build-performance-findings.md`) shows
costs 0.64 s to 105.17 s an origin rather than being uniform.

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

**12 October 2026: what that prescription would cost is now measurable.** A
per-origin facts pass keyed by the slice index writes one file per origin and
never re-searches a week the same timetable already answered — the shape T2
asked for, without the national day index that would reintroduce the 1.87 GB
whole-feed hold this entry was opened about. Indexing every origin's slice is
still refused, and every build without an index still parses the feed; the
facts layer does not change either, it removes the repeat search.

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

### The fares declaration cycle forces two late imports (closed 14 October 2026)

**Severity:** P3. **Route:** `atoc_fares.py`, `atoc_fares_loader.py` and the new
`atoc_fare_declarations.py`. **Raised:** 14 October 2026, from the comment
audit's suppression census. **Closed:** the same day, by ADR-0070 and the commit
that carries the declarations out.

**What it was.** `FaresDb` is `atoc_fares`'s own class and mixes in `FaresLoader`
from `atoc_fares_loader`, which reads 40 names -- the record layouts, the row
types and the reviewed tables -- from `atoc_fares`. Each module imported the
other below its own definitions, and both imports carried `# noqa: E402`.

**Closed by.** The 103 declarations moved to `atoc_fare_declarations.py`, which
imports neither fares module; both readers import it at the top and
`atoc_fares.py` imports `FaresLoader` at the top. `atoc_fares.py` re-exports
every name other modules already took from it, and ADR-0070 records why that
surface stays whole. The two `# noqa: E402` are deleted rather than moved: the
count in these two modules is 0.

**Held by.** `python -c "import atoc_fares, atoc_fares_loader,
atoc_fare_declarations"`; a scan of every `.py` file for names taken from
`atoc_fares` finds 56 distinct names and none missing; and the fares suites
(`tests/test_atoc_fares.py`, `tests/test_build_fares.py`, `tests/test_page_gates.py`)
pass with the declarations in the new file.

### The comment audit's findings, and the suppressions it left (closed 14 October 2026)

**Route:** the whole default branch's comment text. **Raised:** 14 October 2026.
**Closed:** the same day, when both findings landed and the suppressions were
settled. The audit file was removed then; its three rejected ideas and the five
comments it kept are under "Rejected designs, with the reason" above.

The two findings, and what holds them:

- **Encode the London code rule instead of narrating it.** `LONDON_STATION_CRS`'s
  two paragraphs became named checks: `test_every_london_code_is_one_the_feed_carries`
  pins the seven `Z` codes and the seven bare forms that must not be in the list,
  `test_a_reviewed_code_the_feed_does_not_carry_is_named` holds the dead-code
  record, and `tests/test_page_gates.py` holds that
  `--require-live-reviewed-codes` refuses a dead code or a redundant one.
- **Stop making a production import exist for a test's patch path.**
  `atoc_fares.py`'s `import urllib.request` existed only so tests could patch
  `atoc_fares.urllib.request`; the readers live in the loader and the tests patch
  that now.

**What the tree holds, measured 15 October 2026, and what it must stay.** The
audit counted 54 suppressions on 14 October 2026, 34 of them the same
`# noqa: E402`: a root-reaching `sys.path` insert that every import after it had
to be excused for. Those inserts are gone — each tool is run as
`python -m tools.<name>`, which is what the package's `tools/__init__.py` was
always for, and the tests already imported them that way — so the suppression and
its cause were deleted together (item 7 of the 14 October 2026 engineering audit).
**Six suppressions remain**, each naming its cause:

| Cause | Where |
|---|---|
| an intentional catch-all whose escape *is* the finding | `fuzz_feed.py` (3), `tools/check_slice_equivalence.py`, `tools/easy_fares_check.py`, `tools/propose_nature_stations.py` |

The fares declaration cycle's two are gone (ADR-0070), and no module under
`tests/` reaches for the project root before importing its siblings. A count
written into a document went stale within the hour, so the rule is a check and not
a table now: `tests/test_suppressions.py` walks the tree and fails on a `# noqa`
whose own line, or the comment block above it, does not name what it suppresses
(item 8). The tree also holds **16 `# type: ignore`** comments, and those are read
by `tools/check_types.py`, which fails on a new type error in a module that has
none today (item 4, ADR-0072).

### The journey times are dropped from the release, and the source that brings them back

The prices-only release clears the fares licence by not exercising the Darwin
timetable's Schedule 1 §5, so the published page carries no times at all. That is
a deliberate shape, not a defect, and the way back is a *sourcing* change rather
than a licence request: the same CIF Network Rail's ITPS produces is published
under the Open Government Licence, both as the Rail Data Marketplace's NWR
Schedule product (free, daily) and as Network Rail's own Schedule feed (CIF and
JSON, daily). `atoc_timetable.py` already reads CIF, so the work is a downloader
for that feed, a filter for the freight, empty-stock and non-public calls a raw
CIF carries, the OGL attribution, and a filed licence with a cleared `timetable`
section in `licences/release-clearance.md` — the last two a person's. The licence
basis, the two conditions that ride with it (no NR or National Rail branding
implied, and the "consistent with Darwin" clause the CIF satisfies by
construction), and what it needs are in `docs/dtd-licensing-and-data-access.md`,
"NWR Schedule and the Network Rail open data feeds".

**Where this stands, 16 October 2026.** The licence is filed (NWR Schedule,
read 16 October 2026, `licences/README.md`) and its file list read: the account
offers a full JSON extract (`CIF_ALL_FULL_DAILY_toc-full.json.gz`, 139.95 MB) and
daily CIF *update* extracts (`CIF_ALL_UPDATE_DAILY_toc-update-<day>.CIF.gz`), so
the CIF format `atoc_timetable.py` reads is in the product; whether the weekly
full extract is offered as CIF too is the one line of that page still to read.
The reading that matters is in the record rather than in this paragraph: §5
permits distribution where Darwin's forbids it, §8 names no attribution
statement so the OGL fallback wording is the required one, and §7 confines
exercise of the rights to the UK — the one condition here a public page does not
meet automatically, and a person's to read. The owner read it and cleared the
product on 16 October 2026.

**How the file arrives is settled, and it was the harder half.** The
marketplace's file products have no pull API — its own guide offers the
dashboard's Download button and a file transfer it *pushes* to a destination the
consumer owns — so the three routes weighed were a bucket or an SFTP destination
that CI reads over plain HTTPS, Network Rail's own feed at
`datafeeds.networkrail.co.uk/ntrod/CifFileAuthenticate?type=CIF_ALL_FULL_DAILY&day=toc-full`
(HTTP Basic, a 302 to a signed S3 URL, admission capped at 1,000 accounts), or a
script against the dashboard's own endpoints with a bearer token from a scripted
login. The owner chose Network Rail's own feed on 16 October 2026: it is the same
CIF under the same licence, and it is the only one of the three that needs no new
infrastructure and no undocumented front end. The address is the repository
variable `SCHEDULE_URL`; its credential is `SCHEDULE_USERNAME` and
`SCHEDULE_PASSWORD` from the account that holds the CIF subscription, with the
fares download's `NRDP_USERNAME`/`NRDP_PASSWORD` pair as the fallback, because
the endpoint refused that pair on 20 October 2026 (HTTP 401). It is the pair
the fares download uses, and the run of 19 October downloaded the DTD feeds
with it before stopping at the missing address; the 20 October runs stopped at
the probe, so that download never ran in them.
`docs/dtd-licensing-and-data-access.md` holds the detail and
`docs/github-pages-deployment.md` the configuration steps.

**The build's side of it is done, 16 October 2026** (ADR-0073).
`schedule_download.py` fetches a gzipped whole CIF from a URL with an optional
Basic credential, drops the credential across the redirect, and refuses anything
that is not a schedule before it becomes the feed. The reader takes a `.gz` file,
drops freight, empty-stock and parcels schedules on the CIF's own code tables,
and reads a feed that names no stations unfocused rather than emptily -- that
last one answered "nowhere" for every station, silently, while reading the whole
file to do it. `make_synthetic_feed.build_synthetic_whole_cif` writes the shape
those tests are built on.

**The licence and the gate are done with it, 16 October 2026.**
`licences/release-clearance.md` clears NWR Schedule on the owner's approval of 16
October 2026, and `TIMETABLE_GLOB` in `tools/check_release_clearance.py` names
that product rather than Darwin's, so `--release fares,timetable` passes the gate
while Darwin's exclusion stays in the record. The OGL line was already on every
page the release serves (`--notices nre,rdg,ogl,accuracy`), so nothing new had to
be written for it.

**And the release is wired to it, 16 October 2026.** The workflow fetches the CIF
in `build`, `shard` and `assemble` into `feeds/nwr-schedule/`, the shard build
passes `--timetable feeds/nwr-schedule` and no `--date`, the clearance job declares
`--release fares,timetable`, and the assemble job's journey check now refuses a
station page that carries no journeys instead of one that does. The CIF's digest
joined the rebuild trigger, so a day the DTD feeds answered 304 and this one moved
still rebuilds, and `check_fare_rate` prices against the timetable the pages are
timed from rather than the DTD one beside it. What is left is measurement rather
than code: the first real run is the whole-network build in the release's own
shape that the byte-budget finding above asks for.

**The first real run of that wiring is still owed, and on 19 October 2026 the
reason it had not happened was a repository setting.** A push run stopped at the
download's own gate, which refuses a run whose `SCHEDULE_URL` is empty rather
than publishing prices under a shape the workflow no longer builds — the gate
behaving exactly as the paragraph above says it should. That run held the fares
feed's credential and no timetable address at all, and its message had lost the
flag it names to a backtick, which bash ran as a command and printed nothing in
place of; the words now say what they were written to say, and
`tests/test_workflows.py` holds every line of shell in a `run:` block to
carrying no backtick at all. Setting `SCHEDULE_URL` is a settings-page action,
and `docs/github-pages-deployment.md` is the route; publishing prices only
instead is a licensed shape too, at the cost of the two-place edit that document
names. The credential it needs is a pair of its own, `SCHEDULE_USERNAME` and
`SCHEDULE_PASSWORD`, with the fares pair as the fallback, and a two-byte probe
of the address now runs before any feed is downloaded, so a URL or an account
the feed refuses costs one request rather than the run's wait. The first run
under that wiring, 20 October 2026, proved both halves: the probe answered in
under a second, and its answer was that the fares pair is refused by the CIF
endpoint with HTTP 401. That runbook was still describing the prices-only release the workflow
stopped building on 16 October 2026 — five sentences of it, including the
manifest check's own rule backwards — and they are corrected by the commit that
carries this note.

`docs/publish-checklist.md`'s licence section carries the same stale shape in
three places: the DTD terms paragraph's "how a prices-only page meets them" and
"that is why the release is prices-only", the Darwin bullet's "the published
pages carry prices only", and the Darwin-consistency bullet's "on a prices-only
page". `docs/dtd-licensing-and-data-access.md` carries it in three more, each an
assertion about this release rather than about a hypothetical page: "which is why
the release is prices-only", "the release this project ships is prices-only", and
"what the prices-only release does today". Each is a licence reading the owner
holds rather than a sentence a fact settles, so what is owed there is a
re-reading, not a rewrite by whoever notices.

### `docs/build-performance-findings.md` is a rule with no enforcer

`AGENTS.md` used to carry "Measured figures live in one place" in its rule table,
with the file as the enforcer. It came out of that table on 18 October 2026 when
the table gained a column for what fails when a rule is broken (R7 of the
agent-friendliness plan), because nothing does: a document that quotes a figure in
its own words, or a comment that dates a measurement it took from elsewhere, is
caught by a person or not at all.

What would close it is a check that reads every Markdown figure this repository
states about itself and holds it to the one place it was measured — which needs
the figures to be findable in the prose, and nothing marks them today. A first
step that needs no marker: fail on a documented number that appears in two files
with different values, spelled as a plain integer or one of the money and duration
shapes the findings file uses. The false positives would be dates, prices in
worked examples and counts of tests, so the allowlist is the work rather than the
reading.

## Suggestions not yet taken up

From the re-envision pass of 27 September 2026. Each carries the benefit it was
argued for, because a suggestion without one is a wish.

### Needs a data source or a licence answer

| | Suggestion | What it is for | Lyden's comment | Where it stands |
|---|---|---|---|---|
| **S08** | An opt-in "find my station" path, backed by a reviewed coordinate source, keeping manual name/code search as the default and explaining exactly what the permission does before asking | A traveller who knows their town but not the station's CRS code can still start, without silently collecting location data | | Open. It is the same data question as C27, and it is gated on the same named source. |
| **S24** | Date-specific schedules as an explicit product mode: build or select a timetable snapshot for the named date, label its service date beside the times, and keep undated aggregate schedules visibly indicative | A journey time is tied to the day the reader cares about rather than to a mixed schedule set | | Open, and moved: the release publishes times again (the NWR Schedule wiring of 16 October 2026 in "The journey times are dropped from the release" above), so the question is now whether a date-specific mode is worth having over the aggregate schedules the CIF carries — the day control is a filter over them, and the page already names the date each row's time is for. |
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

### Rejected designs, with the reason

The reviews themselves are gone from the tree, so the structural ideas they
weighed and rejected are kept here: they are the part a later reader would
otherwise re-derive, and each carries the reason it was rejected.

- **Renaming the destination-type chips, or naming the census bands under them**
  (clarity audit item 17, 16 October 2026). "Cities" and "Villages" are Census
  2021 built-up-area size bands, so a reader may bring the ordinary word's meaning
  to a chip that means the band. Read and rejected by the owner: the words stay,
  because the chip is the page's own grouping of a place rather than a claim about
  it, the sourced facets worth naming already carry their named proof, and a
  rename would trade a word every reader knows for a longer one meaning the same.
- **Moving the root Python modules into a package** (8 October 2026). High
  import and CI churn, and the `AGENTS.md` map gets most of the orientation
  benefit.
- **Adding a Python type checker for page defects** (8 October 2026). The defects
  live in JavaScript files, which Python types do not reach; `node --check`
  catches the syntax half of it.
- **Splitting `atoc_fares.py` for its length** (8 October 2026). Length alone was
  not the cost F1 and F6 were about, and the file changed 19 times in 150 commits,
  a third of the page's rate. **Superseded 14 October 2026** by ADR-0070, which
  split it for a different reason: the declaration cycle it forced, not its size.
- **Checking in real feed samples as fixtures** (8 October 2026). The data is
  licensed (ADR-0005), so the synthetic fixture is the only regression test there
  is.
- **The national single-pass search, T2 as written** (12 October 2026). One
  national day index per day of the week, held for the whole build, is the shape
  the 8 October 2026 work removed. The per-origin facts layer delivers the same
  payoff without holding the network, and sharding is what would make such a pass
  affordable rather than a reason to build one.
- **A database, or any store** (12 October 2026). A store removes the page write,
  which measures 1.5 ms for a page as built and 10.9 ms for the largest page that
  audit saw, and none of the work itself, because the facts still have to be
  computed somewhere. ADR-0019's 14 October 2026 amendment holds the reasoning.
- **Extracting the classification tables to data files with schema checks**
  (14 October 2026). They are reviewed judgements with the reason written beside
  each group, and they are checked harder than a schema already: a code the feed
  does not carry and a code the workbook already classifies are both refused by
  `--require-live-reviewed-codes`.
- **`page_templates.py`'s templates rewritten as named template helpers**
  (14 October 2026). The templates are literal HTML whose comments say why a
  shape is what it is; a helper per fragment would separate the markup from its
  reason, and those bytes are what the page tests, the byte budget and the browser
  suite read.
- **Turning the long test preambles into test names or parametrized ids**
  (14 October 2026). Those comments are the "why" this repository asks for, and a
  parametrized id cannot carry the paragraph that names the real-feed shape a
  case came from.
- **`cramped-padding` on `.origin-slot-wrap`, as `impeccable detect` reads it**
  (9 October 2026). A false positive, kept so a later pass does not re-file it:
  the border it flags is the dashed underline that is the station slot's whole
  affordance, chosen in `page/shared.css` because a text field's underline is the
  shape a reader already reads as "this part of the sentence is yours". The
  detector reported it on the station route only; the chooser and the privacy page
  scanned clean.

Five comments were seen and deliberately kept, each for the same shape of reason:

- The two `_add_station` helpers in `tests/test_atoc_timetable.py` carry the same
  comment about appending a station record rather than rewriting the file. They
  are two fixtures with two signatures, and the comment sits on the byte handling
  each one does.
- `atoc_fares.py`'s `location_type_sources` field and the property below it open
  with the same sentence. One is the docstring a caller reads, the other carries
  the incident that shaped the field.
- "One manifest of the routes a release actually serves" in `build_demo_page.py`
  and the class docstring in `tests/test_page_output.py`. One is the build's
  contract, the other says which contract the class tests.
- The tram-stop note in `atoc_fare_declarations.py` appears in the reviewed
  settlement fallback table and in `TRANSPORT_STATION_CRS`. Two tables, two facts:
  one is a settlement class, the other a facet tag.
- The duplicated `try: ... except OSError: continue` in the two prunes in
  `build_demo_page.py`. The five lines of loop are two different rankings (one
  keys by path, one takes the newest stamp per digest, and only the first honours
  `protected` per file), so a shared helper would carry a flag rather than remove
  a branch.

## What is waiting on a person

Everything else in this file is work. These are decisions, and each one changes
what gets built or published, so each is written as the choice it is. None of them
is blocked on a tool.

1. **Where would a "find my station" answer come from, if anywhere?** C27 and S08.
   A traveller who knows their town but not the station's name or three-letter
   code cannot start, and "nearest station" is not derivable from this feed. A
   second path needs a named, reviewed coordinate source, its licence and
   provenance recorded beside the station index, and the location permission
   explained in full before it is asked for. Manual name and code search stays
   the default whichever way this goes.
2. **Is a service date a product mode?** S24 and S25. The times a page carries
   are aggregate schedules and the day control is a filter over them. A
   date-specific snapshot, labelled beside the times and carrying bank holidays
   and service exceptions where the source supports them, is a product decision
   rather than a data one, and S25 sits downstream of whatever this answer is.
   The release has published times again since 16 October 2026 (NWR Schedule, in
   the findings above), so this is waiting on the answer rather than on a source.
3. **Is the release's byte figure worth measuring before anything else?** Two of
   the three ways the byte-budget finding above named are done: ADR-0069 changed
   the pair-rule encoding, and the release build is sharded. What is left is the
   measurement, which the next release run takes for free. The question is
   whether anything should wait on that figure.
4. **Does the site get a public name?** S40. A shortlist is in
   `docs/name-ideas.md`, and nothing in the code is named until one is chosen.
5. **Are the traveller sessions run?** S43. Short, task-focused sessions with
   someone who has a price ceiling and no destination, before the next round of
   polish, so the next changes come from interpretation failures rather than from
   features that were possible.
6. **The stop rule's own date.** ADR-0004 sets a written review for **21 October
   2026**: is there community traction, and is the thing worth keeping. S44 is the
   argument about what to measure before that date, and it is measured at the
   community posts rather than on the page. Nothing is built for this.
7. **Does this repository publish times?** The release declares
`fares,timetable`, and the gate that stopped the push run of 19 October 2026
wants the `SCHEDULE_URL` variable set — a settings page, with a credential for
the CIF subscription beside it and the fares pair as the fallback; all of it
written out in `docs/github-pages-deployment.md`; or publishing prices alone, and the
trade is in "The journey times are dropped from the release, and the source that
brings them back" above. Nothing is left to build either way.
8. **Is a release allowed to cost twelve runners times two hours?** The shard
   step runs twelve shares of about 226 pages against a 150-minute bound, and the
   20 October 2026 run spent the whole bound on every share before writing a page.
   If that price is too high, the answer is less work per page rather than a
   longer bound, and the per-share figure every run now prints is what would say
   which part of a share is paying it (A1 of the 20 October 2026 poteto audit,
   settled in `docs/settled-work.md`).
Four questions this file used to carry are answered and their answers are in the
settled table below: the release covers the whole network (ADR-0050), a railcard
is one of a collection with none selected by default (ADR-0052), the runner
serves while the build builds (ADR-0051, amended by ADR-0055), and the source
credit travels with the pages that show a fare (the reading recorded in
`licences/release-clearance.md`).

A fifth left the list on 16 October 2026 — **how the timetable file reaches the
build** — and its answer is in "The journey times are dropped from the release,
and the source that brings them back" above: Network Rail's own CIF, fetched from
the `SCHEDULE_URL` repository variable, and a release built and declared as
`fares,timetable`. The three routes that were weighed are recorded there so the
question is not re-derived.

Four more left the list on 18 October 2026, all four from the clarity audit and
all four written out under "The 14 October 2026 clarity audit" below: **the
chooser counts the places its page carries**, so at the top of the budget the two
print the same number (item 3, settled by measurement rather than by a person);
**the destination-type chips keep their words** — a rejection rather than a fix,
with its reason; **the notice line dates the build** instead of claiming a
publication it cannot know happened; and **the trade words are defined once**,
inside the method disclosure, with no gloss where the page meets them.

---

## Settled work, and where the record is

The closed record -- every item settled before 18 October 2026, and everything
closed since, with the ADR and the test that hold each one, including the
audit-item numbers code comments cite -- moved to `docs/settled-work.md` on
18 October 2026 (E19 of the 17 October 2026 poteto audit). This file is what is
open, and it stays that way.

---

## Where this came from

All sixteen files below are gone from the working tree; each was removed by the
commit named with it, and the findings they held are either fixed or restated
above. `git show <commit>` reads one back. Most were removed on 14 October 2026,
in the commit that settled their findings here; the route audit below was removed
on 16 October 2026, with the reading that closed its last two items. Their
rejections are under "Rejected designs, with the reason" and their figures are in
`docs/build-performance-findings.md`.

Two reviews from 14 October used to sit in `docs/audits/`, each pruned to what
it still asked for. One is left: the app-engineering audit of that date, whose
recommendation 6 is the entry above. The impeccable critique of the same date
landed its last recommendation on 19 October 2026 and was removed with it; its
eight recommendations, the checks that hold them and its detector's one false
positive are in `docs/settled-work.md`, where the commits that carry them are
named beside them. The impeccable review of 17 October sits
beside the audit as one file, the critique and the distill of that date combined
on 19 October 2026; it is the entry near the top of this file, and it holds its
own measurements. The plan filed on 18 October was removed on the day its items
landed. A review with nothing open does not keep a file.

`docs/audits/2026-10-17-poteto-audit.md` and the distill below it were the two
files removed on 19 October 2026. The poteto audit closed its last two findings on
18 October 2026, named no open item, and its nineteen findings and the checks that
hold them moved to `docs/settled-work.md` on 19 October 2026. The distill was
folded into that date's review.

- `docs/audits/2026-10-17-poteto-audit.md` — the engineering audit of the three
  routes, the build, the tools and the checks. Its nineteen findings are settled
  in the table above, with the two argued recommendations (E5, E6) carrying the
  reason the recommendation changed; its measurements are page measurements of a
  3-station demo. Removed on 19 October 2026, in the commit that moved its
  findings into `docs/settled-work.md`.
- `docs/audits/2026-10-17-impeccable-distill.md` — the same date's distill: what
  on the three routes did not earn its place. Combined on 19 October 2026 into
  that date's review under its D numbers, and both are settled in the table
  above. Removed on 19 October 2026.
- `docs/audits/2026-10-17-impeccable-review.md` — the critique and the distill
  combined, thirty findings across the chooser, the station page and the privacy
  page. Twenty landed on 19 October 2026, C18 was rejected by the owner the same
  day and C21 landed on 20 October 2026, so it named no open item and was
  removed on 20 October 2026; its findings and the checks that hold them are in
  `docs/settled-work.md` under its C and D numbers, which code comments still
  cite.
- `docs/audits/2026-10-14-impeccable-critique.md` — the design critique of the
  chooser, the station page and the privacy page. Its eight recommendations are
  settled in the table above, the last of them on 19 October 2026, and its
  degraded method and its detector's one false positive are recorded there too.
  Removed on 19 October 2026, in the commit that moved its findings into
  `docs/settled-work.md`.
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
- `docs/audits/2026-10-10-test-suite-audit.md` — the whole-suite audit. Its
  twelve recommendations are settled in the table above; the one that keeps the
  first one done is the statement-needle rule in
  `tests/test_test_suite_shape.py`.
- `docs/audits/2026-10-08-agent-efficiency-architecture.md` — the agent-efficiency
  review. Its eight findings settle in the table above, its four rejected designs
  are above, and the F7 rule it left is in `AGENTS.md`. Removed on 14 October
  2026.
- `docs/audits/2026-10-10-four-dimension-app-audit.md` — the whole-app review. Its
  thirteen closed recommendations are in the table above, its one open one was the
  notices question, settled on 16 October 2026 by the source-credit reading and
  check, and its browser-suite coverage figures are in
  `docs/build-performance-findings.md`. Removed on 14 October 2026.
- `docs/audits/2026-10-12-build-cost-and-data-architecture.md` — the build-cost and
  data-architecture review. Its twelve tasks are in the table above, its figures
  are in `docs/build-performance-findings.md`, its two rejected designs are above,
  and the three findings it opened are the open findings at the top of this file.
  Removed on 14 October 2026.
- `docs/audits/comment-audit-2026-10-14.md` — the comment audit. Both findings and
  the suppression census are in the closed entry above, its rejected ideas are
  above, and no `# noqa` in the tree is left with a cause the audit could not name.
  Removed on 14 October 2026.
- `docs/audits/2026-10-09-impeccable-route-audit.md` — the non-dev route audit. Its
  twenty-two items settle in the tables above, the last two ([20] and [21]) closing
  with the source-credit reading, and its detector's one finding is a rejected
  design above. Removed on 16 October 2026.
- `docs/audits/2026-10-14-impeccable-clarify.md` — the clarity reading of every
  route. Its fifty findings settle in the entry above: the applied ones are held
  by the commits that carry them, item 8 was read and left as it was, item 3 was
  settled by measurement, item 17 is a rejection with its reason, and items 23, 42
  and 44 landed on their own. Removed on 18 October 2026.
- `docs/audits/2026-10-18-agent-friendliness-plan.md` — the plan to
  rearchitect the code for agents rather than patch it. Its eight items settle
  in the entry above, with the premise it started from (a check that cannot fail
  is worse than none) and the measurements that found it. Removed on 18 October
  2026, in `fe71c1d`.
