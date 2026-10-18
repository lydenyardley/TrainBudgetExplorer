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

### P1 — a whole-network release is over its byte budget, and the pair rules are why

**Severity:** P1 for a published release, and now measured rather than
projected. **Route:** `build_demo_page.py`'s payload encoding, the deploy
workflow's release build, `tools/page_bytes.py`'s budget gate.
**Raised:** 12 October 2026, from the build-cost audit's own projection.

**Evidence, measured 12 October 2026** (24 September 2026 DTD download,
`--date`, `--notices nre,rdg,ogl,accuracy`, in `docs/build-performance-findings.md`).
24 major stations average **2,734,828 bytes** a page, median 2,493,992, and a
10-page alphabetical stride sample averages **806,367 bytes**, median 712,627,
from 72,065 to 2,495,286. At 2,712 priced stations the with-week shape projects
to roughly **2.2 GB** against the **800 MB** budget the gate holds the site to,
with wide error bars at n=10 — so the direction is measured and the size is an
estimate until the next real release runs the gate.

**Where the bytes are.** Birmingham New Street's 1,626,528-byte payload breaks
down as **1,050,373 railcardRules**, 220,029 destinations, 188,527 single
destinations, 73,593 anytime destinations, 56,454 pool, 30,756 serviceWeek. The
2,372 railcard rules are almost all two-ticket pair records (one per
permitted ticket × route × location combination, ADR-0061), and all but 18 are
referenced by a row, so the bulk is combinatorial rather than a leak: a hub that
prices 288 destinations across three modes with many permitted pair splits
produces thousands of distinct pairs. The audit asked the build to search the
service week once for the network; what this shows is that the *payload* is now
the expensive half, not the search.

**What was tried, and did not help.** The service week is 30,756 bytes and the
destinations 220 KB: neither is the problem. The 1 October T1/T10 work removed
the route's script from every page exactly (148,477 bytes a page on the same
station, same shape), which is about 385 MB across the network — and the release
is still projected over budget, which is why this is a P1 rather than a footnote.

**Added 16 October 2026: the release's own shape is once again the with-timetable
one.** The times came back from Network Rail's CIF under the Open Government
Licence, so the next scheduled run builds every station page with a timetable and
`tools/page_bytes.py` reads that number. Whether it refuses is the measurement
this entry has been asking for since 12 October, and a refusal stops publication
rather than publishing a site over budget.

**What would close it.** One of three, in an order a reader of the numbers would
take. First, measure first: run a whole-network build in the release's own shape
and let `python -m tools.page_bytes --site _site --budget-mb 800` refuse it, so
the projection is replaced by a figure. Second, the pair rules: they are a code
plus a price, and the pair's own minimum-fare behaviour is derivable from the
rule's components rather than carried as a record per pair — an encoding change
behind the payload's shape, so the browser suite's fare-panel checks hold it
honest. Third, shard the build so a release that does not fit in one runner's
wall clock can still be published (T4 landed the shards and the merge; nothing
yet shards the release build).

### The pair-rule encoding is the release's own cost, and it is measurable

Raised by the same measurement, as its own finding because it is separable from
the budget question above. `railcardRules` is the largest block on a real page
and it grows combinatorially with the permitted pair splits, so the release's
byte cost is now a function of how many two-ticket combinations the feed allows
rather than of how many destinations it prices. Until the encoding changes, the
whole-network byte figure cannot be reasoned about, only measured — which is the
state the audit's projection came from.

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

### The critique's small remaining asks: the chip arrangement, the fare vocabulary, and an accelerator

**Severity:** P2 for the first, P3 for the other two. **Route:** the station
page.
**Raised:** the 14 October 2026 critique, recommendations 3's second half, 7 and
8. That file is `docs/audits/2026-10-14-impeccable-critique.md`, pruned to those
three. Its recommendation 5 — the licence notices on the routes that show no
fare — was settled on 16 October 2026 by the reading in
`licences/release-clearance.md` and `tools/check_source_credit.py`, which closed
the route audit's items [20] and [21] with it. Its other five recommendations
landed on 15 October 2026, held by the tests named in that file's own table.

- **The chip arrangement (3, second half).** The three chips that could only ever
  select an empty list are no longer offered, so the dead ends are gone; what is
  left is that `All` plus fourteen chips sit at one decision point. What would
  close it: the four settlement bands ahead of the ten thematic facets, behind one
  "More types" disclosure.
- **The fare vocabulary (7).** "Regular", "Restricted", "Advance", "changes",
  "two tickets" and the minimum-fare note are explained one disclosure at a time,
  inside a row's own panel, so a reader comparing six rows holds words nobody has
  given them. What would close it: one short block beside the provenance, or a
  definitions list the row links to.
- **An accelerator for the page's one job (8).** Setting the budget is reachable
  only by tabbing through the heading controls or grabbing the slider. What would
  close it: `/` or `b` to focus the budget field, `n`/`p` to page, and the folded
  bar saying so.

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
variable `SCHEDULE_URL` and the credential is the `SCHEDULE_USERNAME` and
`SCHEDULE_PASSWORD` secrets; `docs/dtd-licensing-and-data-access.md` holds the
detail and `docs/github-pages-deployment.md` the configuration steps.

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
shape that the P1 byte-budget finding above asks for.

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
what gets built, so each is written as the choice it is. None of them is blocked
on a tool.

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
3. **Which byte-budget path first?** The P1 finding above lists three ways the
   release gets back inside its 800 MB budget: measure the real release first,
   change the pair-rule encoding, or shard the build. The order is a judgement
   about what to spend time on: the first replaces a projection with a figure,
   the second is the one that actually removes the bytes, and the third only makes
   an over-budget release affordable to publish.
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
| The licence notices on the routes that show no fare (route audit items [20] and [21]) — whether the chooser and the privacy notice have to carry the NRE credit | recorded rather than assumed: the credit travels with the page that shows a fare, the chooser's station index and the privacy notice show none, and the alternative reading (render it on every route) is named with the reading | the section "Which pages carry the acknowledgement" in `licences/release-clearance.md`, and `tools/check_source_credit.py` — held by `tools/test_check_source_credit.py`, run over the built site by the assemble job |

### The 8 October 2026 agent-efficiency audit

The audit file was removed on 14 October 2026, when its last finding landed. Its
eight findings are settled here with the artifact that holds each one, and its
four rejected designs are under "Rejected designs, with the reason" above.

| Finding | Closed by | Held by |
|---|---|---|
| F1, the station page was one 2,938-line string, so no linter or `rg --type js` could see it and half of all fixes landed in it | the page's CSS and JavaScript are real files now, inlined by `page_templates.py` at import time | `page/*.js` and `page/*.css`, `tests/test_page_assets.py` for the seam, and `node --check page/*.js` in `tools/verify.py --fast` |
| F2, there was no agent entry point and the README's file table had drifted to omit 26 tracked files | `AGENTS.md` is the entry point: the map, both verify commands, and a rule table naming each rule's enforcer | `tests/test_agents_map.py` checks the map in both directions, so a module, page asset or operator tool that is not on it fails the suite |
| F3, `tools/replay/` was 7,492 lines of stale page copies that supplied 40% of the hits for `priceOf` and `shortlist` | deleted in this pass. Its last commit was `5b50a33` (2 October 2026) | `git checkout 5b50a33 -- tools/replay` reads it back. Nothing in the build, the tests or the release referenced it, and `tools/test_replay_driver.py` went with it |
| F4, the CI rebuild fingerprint was a hand-kept three-file list, written twice, and eight of the last 150 commits had changed only unlisted inputs | one script hashes every build input and both workflow steps call it | `tools/build_inputs.py`, held by `tools/test_build_inputs.py`, which fails on a transitively imported module that is not covered |
| F5, there was no single verify command, and the browser suite existed only as 115 lines of bash inside the workflow | `tools/verify.py` with `--fast`, `--full`, `--browser` and `--all`, written in Python so a Windows checkout runs it, called from CI before the feeds are downloaded | `tools/verify.py` itself; `--full` adds the two feed-scale tests its docstring names (and, since 15 October 2026, the type check), and `tests/test_atoc_fares.py` shares its fixture through `setUpClass` |
| F6, the two hot test files were the biggest in the repository | the Python half moved out by feature seam over the fixture in `tests/page_harness.py`, and the JavaScript half was split on 11 October 2026 | `tests/test_page_runner.py`, `tests/test_page_caches.py`, `tests/test_page_output.py` and `tests/test_page_gates.py`; and the browser suite is one module per route and section under `tests/browser/`, with `tests/browser_test.cjs` as the entry point. **Landed 14 October 2026:** those 163 methods are one class per subject over `PageTestCase` in `tests/page_harness.py` -- `DemoPageTest` keeps 52, and `tests/test_build_fares.py` (43), `tests/test_build_provenance.py` (33), `tests/test_build_chooser.py` (19) and `tests/test_build_links.py` (16) took the rest -- the same 180 tests with 179 of their 180 names unchanged (the contact test is rewritten, because route audit item [15] landed in the same pass), and `python -m unittest tests.test_build_demo_page tests.test_build_fares tests.test_build_provenance tests.test_build_chooser tests.test_build_links` green on the 180 in 28 s (14 October 2026) |
| F7, fixture-versus-real-feed gaps recurred | the rule is in `AGENTS.md`: a real-feed defect fix adds the minimal synthetic record with the fixing commit named | the passing-stop record in `make_synthetic_feed.py`, held by a test in `tests/test_atoc_timetable.py` |
| F8, measured figures lived in the README and were withdrawn rather than corrected | the README's measured section is a summary that links | `docs/build-performance-findings.md`, which holds "The whole network, measured" behind the README's link |

### The 10 October 2026 test-suite audit

`docs/audits/2026-10-10-test-suite-audit.md` was removed once its twelve
recommendations landed; the commit that removed it is named at the foot of this
file. Each finding is settled by the artifact that holds it, and the one that
keeps the others done is named last.

| Finding | Closed by | Held by |
|---|---|---|
| F1, the page's JavaScript was proved by quoting it: 154 statement needles over 52 methods, and a one-space edit inside a statement failed the Python suite while the browser suite passed 839/839 over the same page | the needles are gone. A statement the browser suite drives was deleted and left to that suite; one that stood for a fact no browser check drives was rewritten as the fact — an attribute, a rendered string, a payload key | the browser suite's own labels (the address, the fold, the budget, the shortlist, the ticket modes, the picker), which ran 839/839 over five pages |
| F2, `fuzz_feed.check_timetable` had no caller and one of its two tests asserted the opposite of its name | the invariants are wired into `one_round()`, so a schedule that is not a journey fails the round that damaged it | `tests/test_fuzzed_feed.py`: the clean timetable passes, a one-stop schedule is a violation, and a round reports what the check finds |
| F3, two tests asserted the slug rule audit finding A1 replaced, keeping a production function alive that only tests called | `station_slug` and both tests are deleted | the live rule at the boundary that owns it, `tests/test_page_output.py`'s slug-and-folder agreement |
| F4, tests for a download path the command does not take | `download_specs`, `download_dtd` and `download_knowledgebase` are deleted; the one rule they alone carried — each feed is offered its own previous record — moved to a `--dtd all` case on the command itself | `CommandLineTest.test_each_feed_is_offered_its_own_previous_record` |
| F5, a gate that failed on a correct checkout, because `page/*` was CRLF here and LF in CI | `.gitattributes` pins the page assets to LF and the working tree agrees with the blob | `tests/test_page_assets.py` all four, green on Windows |
| F6, dead constants, one of them copied: `atoc_knowledgebase._normalise`, `tools/check_release_clearance.PRODUCT_ID`, `atoc_fares.DESTINATION_FACETS_BY_KEY` | `_normalise` and `BY_KEY` are deleted (the tests index the registry); `PRODUCT_ID` is now enforced by the tool that declares it | `tools/check_release_clearance.py` refuses a manifest row whose product id is not the declared format, and `tests/test_licences.py` imports that one definition |
| F7, `test_atoc_fares.py` reached into load steps: 55 tests called a private method and 53 never loaded a feed | one coherent pass: 17 hand-built equivalents replaced by 19 feed-level cases over `load_feed()`, with the pure functions kept | `FeedBoundaryClassificationTest` in `tests/test_atoc_fares.py` |
| F10, one JS fragment asserted in two files | the picker's shared-field wiring is asserted once, in `tests/test_page_output.py`; the completion itself is the browser suite's | the chooser's completion checks in `tests/browser/chooser.cjs` |
| R11, encode the lesson rather than the list | the rule is a test, and it asks what a needle *is* rather than which punctuation it holds: a needle the page's script only holds inside a string, a template or a comment is copy, a bare name or dotted path is a payload key or a hook, and a needle with letters and real syntax that appears as code is the statement being quoted | `tests/test_test_suite_shape.py`'s `NoPageStatementNeedleTest`; over the committed `tests/test_build_demo_page.py` it reports 268, over the current one none |
| R12, keep the browser suite as the owner of page behaviour and in the release gate | nothing to change: the suite is what the deploy workflow runs over five pages, and the coverage floor is the second net | `.github/workflows/deploy.yml` |

The first version of R11's rule listed fourteen punctuation shapes that make a
needle an implementation quote, and it reported 114 over that same file. The
shape list was the defect: shortening a needle until the punctuation was gone
was enough to pass it -- `var dark = true;` became `dark = true` -- and the
audit's own work had already done that four times without noticing. The rule
now reads the script's structure instead, which is what makes a hole like that
impossible to open, and it finds 268 where the list found 114. Every one of
the 154 the list missed was retired: replaced by a payload fact, a markup fact
or the whole sentence a reader sees, or deleted where the browser suite already
owns the claim, or moved into the browser suite where only a rendered page can
answer it (`tests/browser/station-rows.cjs` reads the opened panel's `colSpan`
against the table's own heading count).

### The 10 October 2026 whole-app audit

The audit file was removed on 14 October 2026. Its thirteen closed
recommendations landed on 11 October 2026; each is held by an artifact, and the
two audits agree: the route audit's items [3], [4], [6], [10], [16], [18] and
[22] are closed by them. Its one open recommendation was the notices question,
settled on 16 October 2026 as the source-credit reading and check in the settled
table above, together with the route audit's items [20] and [21]. Its
browser-suite coverage figures are in `docs/build-performance-findings.md`.

| Recommendation | Closed by | Held by |
|---|---|---|
| R1, the chooser opened its list over its own explanation and could navigate on a click meant for prose | the shared field block takes an `anchor` and an `openOn`: the chooser opens on typing and draws the panel over the list's own place, never over the intro | `page_templates.py`'s `STATION_FIELD_JS`, and the browser suite's "a click on the prose leaves the page alone while a completion is in the field" |
| R2, an empty chooser field rendered every station (51,770px) | the directory is capped and says so: a stated top 40 of the true count, the field still the primary path | `page/chooser.js`'s `render()`, the browser suite's "the field opens on a stated top-N of stations rather than the whole directory" |
| R3, the entry route carried no provenance | `render_chooser` takes the build's `price_source` and `feed_date` and prints the station page's own sentence | `build_demo_page.render_chooser`, `tests/test_build_chooser.py`'s entry-provenance test |
| R4, the picker capped silently and station search was two behaviours | one `stationMatches` and one `STATION_LIST_CAP` serve both routes, and the picker states its cap in the same sentence the chooser uses | `page_templates.py`'s `STATION_MATCH_JS`, `page/station/picker.js`, the browser suite's picker-cap check |
| R5, the privacy "below" pointed at a section above it | the summary now precedes the deep dive, and a test asserts the order so the sentence cannot drift again | `page_templates.py`'s privacy template, `tests/test_build_provenance.py`'s order assertions |
| R6, no build date and the deep dive read first | "What this site does" reads first and one dated line under the title dates the build-dependent promises from `builtAt` | `render_privacy`'s `built_at`, the privacy template's `#builtLine` |
| R8, the release was written twice, with two writers and two clocks | one `write_release()` for both shapes, `write_page_atomic` everywhere and one `builtAt` | `build_demo_page.write_release` |
| R9, `main()` was 1,001 lines holding two build scripts | `main()` is 41 lines over five named phases, and the two shapes are `_build_all_origins` and `_build_single_origin` | `build_demo_page.load_inputs` … `release_gates`, and the two `_build_*` functions |
| R10, `build_payload()`'s eight nested closures | a `PageContext` NamedTuple carries the per-page configuration and a `RulePool` owns the rule numbering; every builder is a module-level function | `build_demo_page.PageContext`, `RulePool`, `railcard_detail_for`, `destination_row`, `day_answer` |
| R11, `page/station.js` (2,737 lines) and `tests/browser_test.cjs` (7,163 lines) were monoliths | the station route's script is one file per panel under `page/station/`, concatenated in a named order; the browser suite is one module per route and section under `tests/browser/` | `page_templates.STATION_SCRIPT_PARTS`, `tests/browser/`, and the pages built from this tree passing every check they can run |
| R12, `matches()` was copied in two route scripts | it is `stationMatches`, in the shared `STATION_MATCH_JS` block | `page_templates.STATION_MATCH_JS` |
| R13, `FaresDb` held its loader and its queries in one 2,401-line class | the loader is a `FaresLoader` mixin in `atoc_fares_loader.py`; `FaresDb` owns the state and the queries unchanged | `atoc_fares_loader.FaresLoader`, `atoc_fares.FaresDb(FaresLoader)` |
| R14, a Windows build emitted CRLF pages while CI emitted LF | every write passes `newline="\n"`, and `.gitattributes` pins `page/*` to LF so the working tree agrees with the blob | `write_page_atomic`, `write_resume_state`, `.gitattributes`, and `tests/test_page_output.py`'s byte test |

The structure work is worth naming here because it is what a later change lands
in. `build_demo_page.main()` is 41 lines over five named phases
(`load_inputs`, `_load_timetable`, `read_provenance`, `price_one_payload`,
`release_gates`) with the two build shapes as `_build_all_origins` and
`_build_single_origin`, and both shapes end in one `write_release()`.
`build_payload()`'s builders are module-level functions over a `PageContext` and
a `RulePool`. `page/station.js` became one file per panel under `page/station/`,
and `tests/browser_test.cjs` became one module per route and section under
`tests/browser/`. `FaresDb` keeps its state and its queries, and the loader it
used to hold beside them is `atoc_fares_loader.FaresLoader`, mixed in.

### The 9 October 2026 non-dev route audit

The audit file was removed on 16 October 2026, when its last two items were
settled: [20] and [21], the notices on the routes that show no fare and the build
check for them, are the settled-table entry above. Twenty of its twenty-two items
are implemented, each held by the commit that carries it
(`git log --grep="audit item"`); the group-to-commit mapping for the first twelve
is in `1ecd719`, and its items [3], [4], [6], [10], [16], [18] and [22] are also
closed by the 10 October 2026 work above. Its detector's one finding,
`cramped-padding` on the station slot, is under "Rejected designs, with the
reason".

### The 12 October 2026 build-cost audit

The audit file was removed on 14 October 2026. Its twelve tasks landed, each held
by an artifact and by a command a reviewer can re-run; its figures are in
`docs/build-performance-findings.md`, its two rejected designs are under "Rejected
designs, with the reason" above, and the decisions it amends are named in its own
T12 row. What it left open is the three open findings above: the byte budget, the
pair-rule encoding and the sharded release build.

| Task | What it asked | What landed | Command whose output a reviewer can reproduce |
|---|---|---|---|
| T1 | the station script out of every page | `station-<digest>.js` beside the stylesheet; each page inlines only its own `DATA` | `python -m tools.page_bytes --site _bytes_site` on a controlled two-build comparison; 261,362 → 112,885 bytes on one station |
| T2 | search the service week once for the network, write the facts | the facts store exists and is keyed per origin; the *national* single-pass search was not built, because it would hold the national timetable for the whole build | `python -m unittest tests.test_page_caches.PageFactsTest` |
| T3 | a rebuild keyed per origin | one origin's priced counts and journey weeks keyed by feed; a masked payload comparison skips unchanged writes | `python -m unittest tests.test_page_runner.AllOriginsCliTest` |
| T4 | build in shards and merge | `--shard N/M` and `--merge`, with a merge that proves the partition | the same `AllOriginsCliTest` module's shard cases |
| T5 | measure the release against its budget | measured in the release's own shape: 24 major stations average 2.73 MB a page, a stride sample 806 KB; the with-week shape projects to ~2.2 GB against 800 MB, which is the P1 finding above | `python -m tools.page_bytes --site _stride_site` |
| T6 | fold the pricing pre-pass into the facts pass | the pre-pass replays the counts it already priced; the station index is built from the facts | `python -m unittest tests.test_destination_coverage.ReportTest` |
| T7 | decide what the local default build is | the default is the fast single-origin page again; `--all-origins` requires its acknowledgement | `python -m unittest tests.test_page_runner.RunnerBuildOrServeTest` |
| T8 | publish the per-origin cost distribution | `tools/measure_origin_costs.py`: mean 19.37 s against median 4.74 s, max 105.17 s | `python -m tools.measure_origin_costs --origins AAT,ABA,AAP` |
| T9 | reuse the timetable-derived facts across releases | a fares-only refresh of the network build reuses every journey fact; the store is keyed by feed content, and a single-origin build neither reads nor writes it | the sweep-reuse case in `PageFactsTest` |
| T10 | the same shared-asset treatment for the chooser | `chooser-<digest>.js` beside the release | `python -m unittest tests.test_page_output.SharedStationAssetTest` |
| T11 | check whether hashed assets accumulate | a rebuild removes the hashed files no file in the folder names | `...SharedStationAssetTest.test_a_rebuild_removes_the_hashed_assets_no_page_names` |
| T12 | record what this changes in the registers | ADR-0033, ADR-0047, ADR-0019, ADR-0024, ADR-0050, ADR-0055 and ADR-0032 amended; the findings hold the measurements | `python -m unittest tests.test_agents_map` |

### The 14 October 2026 clarity audit

The audit file was removed on 18 October 2026, when its last finding left the
tree, and its fifty findings are settled here. Forty-four landed on 15 October
2026 in one commit, because the payload keys and the page's reads had to move
together and the templates and their tests carry items from more than one route;
item 1 had already landed in `e20582d` with the rest of that day's critiques, and
`git log --grep="audit item"` reads any of them back. Item 8 read a sentence that
was worth leaving as it was, and item 5 offered a warm and a blunt wording, so
this pass chose one (warm) rather than splitting the difference. What was left
after that pass went on 18 October 2026: item 23 landed on its own, item 3 was
settled by measurement rather than by a person, item 17 was read and rejected
with its reason, and items 42 and 44 were answered (below).

Two of the findings were the same fault twice, and they are the ones worth
remembering: a paragraph written from build-time constants while the rows beside
it are written from the state on screen (items 20 and 24), so a railcard holder
was told "No railcard is selected" while every row showed a card price.

Item 3's data half turned out not to be a question about the index at all. One
real build, read on 16 October 2026:

    python build_demo_page.py --feed feeds/fares --timetable feeds/timetable-nwr \
      --origin GRA --notices nre,rdg,ogl,accuracy --out <site>/index.html

gives a chooser row reading *"GRANTHAM GRA 331 destinations this feed prices"*
over a page that says **331 destinations for up to £181.00 per adult** at the top
of its own budget and **53** at the default £20.00, from 324 rows in the cheapest
list, 331 in the single list and 135 in the anytime list. The chooser's number is
the page's own payload — the distinct places those lists carry, counted once
each — so the two are the same number whenever the budget excludes nothing, and
that is why the number moved from the 50 the audit read to the 331 the page
holds: the index pass's `_priced_destinations` (what the chooser used to print,
and what still decides the write set, ADR-0019 decision 3) is not the page's own
count. The 50 against 53 was a count of places at any budget (50) beside a count
of rows inside £20.00 on a page carrying 331 of them (53).

| Item | What it asked | What landed | Held by |
|---|---|---|---|
| 1 | the chooser printed the feed's download date twice | one date, composed once | `e20582d`; `tests/test_build_chooser.py` |
| 2, 3, 4, 5, 6, 7 | the chooser's words: what the list is before how it is ordered, a count that names its scope, an intro that says what the site covers, an empty state that helps, "a page for", one "starting from" | all seven | `tests/test_build_chooser.py`; `tests/browser/chooser.cjs`, "the chooser says what its order is, and what it is not" |
| 9, 10, 11, 13, 38, 39 | the station page's opening: the heading's own name, one promise, the first-use note, the no-timetable fact stated once | the heading's accessible name is the whole sentence, written from the tab title on every render; one promise with the timetable clause composed onto it; the note names the station; "no timetable was supplied" said once | `tests/browser/station-render.cjs`, "the heading's own name is the whole sentence, and the same one as the tab title" and "the times columns exist exactly when the sentence promises times"; `tests/test_build_demo_page.py` |
| 12, 14, 15, 18, 19, 32 | the controls' own words: the budget hint, the unit, the mode's name, the chip rule, the clear control, the empty-state buttons | the hint names the mode it clamps in; "per adult"; "Cheapest available"; the chip rule says only what a count is; "Show all destination types"; "Show the 7 Anytime Day Returns" and "Raise the budget to £7.00" | `tests/test_build_fares.py`; `tests/browser/station-fares.cjs`, "the chips say what the count beside each one is"; `tests/browser/station-picker.cjs` |
| 16, 24, 26, 29, 31 | the railcard and the fare's own panel: the help, the method note, the card sentences, the feed's ban vocabulary, one voice | the help says where the choice travels; the note is written from the card the rows read and claims the card only where it lowers the fare; the sentences are one voice; the ban vocabulary sits in the feed record | `tests/browser/station-fares.cjs` (the railcard help); `tests/test_build_fares.py`; `tests/browser/station-rows.cjs` |
| 20, 21, 22, 33, 34 | the count, the day and the pagination | "shown" is reserved for the table, so the cover line counts what the feed prices at any budget; the count line states the breakdown once; an absence in the Time cell is a short state and the row's own details name the day; an empty list carries no page number | `tests/browser/station-fares.cjs`, "and the status re-announces the page, without repeating the count"; `tests/browser/station-shortlist.cjs`, "and every absence on every day names the day it is about" |
| 25, 27, 28, 30 | a row and its own details | the restricted-fare sentence promises a condition only when the feed describes the code, from a payload fact rather than from reading the fallback text; one shape of disclosure name; "Copy journey"; the walk-up fare glossed where it is met | `restrictionDescribed` in `build_payload.destination_row`; `tests/test_build_fares.py`; `tests/browser/station-rows.cjs` |
| 35, 36, 37 | the shortlist dock | the live region says what changed rather than the count; the share line names what the link carries beside a real link; the list noun is "destination" | `tests/browser/station-shortlist.cjs`, "and the change to the list is announced, not just drawn" and "and the shared link names exactly the places the list holds" |
| 40, 41, 43 | the privacy page | the contact is a sentence with a real link; the hosting paragraph no longer restates the bullets above it; one actor name and one tense across the conditional promises | `tests/test_build_provenance.py` (the contact and its issue tracker); `DEFAULT_PRIVACY_CONTACT` in `build_release.py` |
| 45, 46, 47, 48, 49, 50 | the provenance block | the price line tells the two dates apart ("downloaded", "fares and times read for"); the build stamp is named and dated in the page's own words; each method sentence has a subject; the destination-type source sits with the attribution; the timetable verdict names the day the times are for | `tests/test_build_provenance.py` (the two clauses, the type source's place); `tests/browser/station-fares.cjs`, "and judges that window against the reader's today" |
| 23 | the price cell's three facts with no words between them | the note reads "with your card (was £7.00)", so the words say which number is the card's | `page/station/railcards.js`; `tests/browser/station-fares.cjs`, "a discounted row shows the card price and the standard fare it was discounted from" |
| 3 (the data half) | the chooser's number and the page's number disagree | the chooser names the page's own places, so at the top of the budget the two are the same number | `places_in_payload` in `build_payload.py`; the build and its readings are below |
| 17 | the destination-type chips are census bands wearing everyday words | read and rejected by the owner: the words stay | the entry under "Rejected designs, with the reason"; no code changed |
| 42 | the built line promised a publication that had not happened | the line dates the build ("This notice describes the build dated ..."), so it is true of a build nobody deployed and of a deployed one | `build_render.py`; `tests/test_build_provenance.py`, which holds the line to the date and to no claim of publication |
| 44 | nothing defined the trade vocabulary the page quotes | one glossary inside the method disclosure, written from the route's shared script and not per page, and no gloss where the words are met | `page/station/provenance.js`; the placeholder in `page_templates.py`; `tests/browser/station-render.cjs`, "the trade words the page quotes are defined together, in the method disclosure" |

### The 18 October 2026 agent-friendliness plan

`docs/audits/2026-10-18-agent-friendliness-plan.md` was removed on 18 October
2026, when R4, R5, R7 and the rest of R8 landed; the commit that removed it is
named at the foot of this file. The question it answered was the operator's, of
18 October 2026: the code should be rearchitected for agents rather than patched.

Its premise is worth keeping because it is the reason the next such plan should
start the same way. There are four rungs of enforcement, strongest first: make the
bad state unrepresentable, make it fail a check, write a canonical helper, write
prose. This repository was already strong at the second rung, and that strength is
where the first defect lived: **a check that cannot fail is worse than no check,
because it spends the trust a real check would have earned.** Three measurements
found it in three places that day: a byte gate that reported 0 KB of payload on
every page it measured, the same gate passing an empty folder, and one fact (the
payload's marker) spelled independently in eight files, the eighth being the gate.

| Item | What changed | Held by |
|---|---|---|
| **R1** | `page_templates.py` owns `PAYLOAD_MARKER` and `CHOOSER_MARKER`; five modules import them instead of spelling them, `tools/check_source_credit.py`'s docstring included | `tests/test_page_assets.py` holds each template to its own marker, and the two gating tools to the template's |
| **R2** | `page_bytes` exits 2 on a page that names a payload it did not parse, and on a `--site` run that finds no page | `tools/test_page_bytes.py`, two cases, plus a third proving a page that ships nothing still passes |
| **R3** | the byte measurer's own test measures a page built from `page_templates.TEMPLATE`, not a page the test typed | `tools/test_page_bytes.py` |
| **R4** | `page/station/state.js` is the page's one mutable object: `seedState()`, then one gesture per control family (`chooseBudget`, `chooseUnit`, `chooseMode`, `chooseCard`, `chooseTypes`, `chooseServiceDay`). Every listener is one line calling one of them, every render derives from the state, and `applyState` is the one place a control is written from it — it no longer reads a control back | the browser suite, 844/844 over five pages on 18 October 2026, with the setups that used to assign `.checked` on a control now driving a gesture or `applyState` |
| **R5** | `tools/check_page_state.py`: a ratchet over control reads per panel, in the shape `tools/check_types.py` uses, run by `python -m tools.verify --full` | `tools/test_check_page_state.py`, thirteen cases over the verdict, including that a panel the budget does not name fails and that a write is not counted as a read. It fails on the tab title's old `budgetNumber.value` read, which is the defect it was written from |
| **R6** | the paragraph about times is the payload's own sentence, chosen once from `hasJourneys`: a prices-only page no longer says "valid on the services listed" | `tests/test_build_demo_page.py`'s `test_the_sentence_about_times_names_only_what_this_build_has`; the words are `build_release.SERVICE_CLAIM` and `SERVICE_CLAIM_WITHOUT_TIMES` |
| **R7** | `AGENTS.md`'s rule table gained the third column, "what fails, and what it says", and lost the one row that could not name a failure | the row below, which is that row's new home: "docs/build-performance-findings.md is a rule with no enforcer" |
| **R8** | the prose the structure replaced is gone: `check_source_credit.py`'s docstring imports the marker it used to spell, and `url-state.js`'s `applyState` no longer explains why it must re-read the controls, because it does not | the same tests as R1 and R4 |

**The evidence, kept because the numbers are the argument.** `grep -cE
'\.(value|checked|dataset|textContent|hidden|classList)' page/station/*.js` summed
to **269 accesses across 15 modules** before R4. It is a size, not a defect count,
and it does not separate reads from writes; after R4 the reads alone, which is what
the ratchet counts, sum to **34** across the page's 17 panels (measured 18 October
2026). Six of the 37 `fix(page|station|chooser|routes)` commits were the same shape
from six sides, all of them a second writer or reader of a fact that only lived in
an element: `Back and Forward carry the chosen day`, `an arrow key no longer takes
the station away from Tab`, `the tick on a row is the shortlist`, `a card must not
swap the row under a reader's feet`, `the budget floor is zero`, `the field stops
moving the page`. Eighteen of the 108 `fix` commits were `fix(tools|tests|ci|verify)`
-- the instrument was wrong -- and that is what R1 to R3 answered.

**What it does not establish.** The commit-prefix census is the author's label, not
a measured property: it locates the work and does not measure it. R4's benefit is
prevention rather than repair, because the six defects it is meant to prevent were
already fixed at the element level, so it is proved by the cases that keep passing
rather than by a case that starts passing. And the ratchet counts reads without
judging them: a read inside a gesture and a read compared against a chip's markup
look the same to it, which is why the reason for a particular read belongs in the
comment beside it.

**Not proposed, and why.** No package move (rejected 8 October for import and CI
churn, and R1 gave the same orientation benefit through one module). No type
checker for page defects (they are in JavaScript; R5 is a lint over JavaScript
instead). No split for length, no schema for the classification tables, no new
abstraction over the checks: each would trade a written reason for a mechanism
that cannot carry it, and `verify.py` is already the runner.

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

**Not a design fix.** The page measured above was the single origin the deploy
workflow then published (`--origin GRA`): one station page, no Change chevron in
the heading and only Privacy in the footer. That is a coverage fact about the
release command of the time rather than a defect in it, and the release has since
become the whole network — the settled entry "Question 1, the release coverage"
above (ADR-0050).

---

## Where this came from

All twelve files below are gone from the working tree; each was removed by the
commit named with it, and the findings they held are either fixed or restated
above. `git show <commit>` reads one back. Most were removed on 14 October 2026,
in the commit that settled their findings here; the route audit below was removed
on 16 October 2026, with the reading that closed its last two items. Their
rejections are under "Rejected designs, with the reason" and their figures are in
`docs/build-performance-findings.md`.

Two reviews from 14 October are still in `docs/audits/`, each pruned to what it
still asks for. `2026-10-14-impeccable-critique.md` is recommendations 3's second
half and 8, which are the entry above; its item 7 is answered by the trade words
that are now defined once. The app-engineering audit of the same
date is its recommendation 6, the entry above. The reviews filed on 17 October and
the plan filed on 18 October sit beside them. A review with nothing open does not
keep a file.

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
