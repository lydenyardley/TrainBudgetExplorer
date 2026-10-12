# Build cost and data architecture: what is still open

**Date:** 12 October 2026
**Commit reviewed:** `e56a071` on `main`, working tree clean except one untracked
screenshot in the root that is not mine.
**Scope:** the whole build path (`run.py`, `build_stations.py`,
`build_demo_page.py`, `build_workers.py`, `page_templates.py`, `atoc_timetable.py`,
`atoc_fares.py`), the release workflow's build step, and the freshness path from
download to publish.
**Method:** read-only. Every figure below was measured on this machine today
unless it is quoted, in which case the source and its own date are named beside
it. The feeds in `feeds/` are the licensed download (419,589 schedules,
3,436 priced stations), and `_site/` is a 24-page real-feed build of this tree,
so the page and per-origin figures are real-feed figures and not synthetic ones.
The 24 pages were written by a build of 10 October 2026, so where the figures
below describe a page's shape they describe that build's shape.
**No code was changed.** This file was the original deliverable; it is now pruned
to what the work left open, per the rule `docs/open-work.md` holds itself to.

## The answer in one paragraph

Building one page per station is not what makes the build slow. A page's own
numbers are computed from the two national feeds inside the build, and that
computation repeats per origin, per day of the service week. On this machine a
single origin's timetable work alone measured 1.2 s, 7.2 s and 28.5 s for three
sampled stations, against a whole-build average of 10.75 s of work per page on one
worker. Moving the pages to a database would remove the last 20 milliseconds of
that (the file write) and keep every second of the rest, because the facts a page
shows would still have to be computed somewhere. What would actually help is on
the table below and in the numbered task list. Two of the tasks are cheap and
large. One shared 149 KB script is copied into every page, which is both a
serving cost and a byte-budget risk. The service week is searched eight times per
origin, and it could be searched once for the whole network.

## What a page is made of, measured

24 real-feed station pages from `_site/from/*/index.html` built by this tree:

| Part | Median bytes | Share of the page |
|---|---|---:|
| The page's own `DATA` object | 110,205 | 45.7% |
| Inline scripts, excluding `DATA` | 149,377 | 46.7% |
| Markup, headings, controls | 24,411 | 7.6% |
| **Page** | **283,908** | **100%** |
| Shared assets, fetched once and cached | `stations.js` 168,141, one hashed stylesheet 40,960-54,694 | not per page |

**The inline script is byte-identical on every page.** Distinct script texts across
the 24 pages, with the `DATA` object removed: **1**. Its size is **149,377 bytes**.
The only per-page differences in the file are the title, the heading, the budget
slider's `max`, the filter chip counts and `DATA` itself.

`stations.js` was externalised on 30 September 2026 for exactly this reason: the
picker list repeated on every page was "445 MB across the network" in
`build_workers.py` and "295 MB of the network in the wire encoding" in
`build_demo_page.py`, each comment measured from that build's own output. The
page's own script is the same mistake, still in place, 149 KB at a time.

**Projection, labelled as one.** The 24-page sample's mean page is 319,891 bytes.
At the workflow's own page count (2,712 priced stations) that is **827 MB of pages
alone**, against the 800 MB budget `tools/page_bytes.py` holds the site to
(`SITE_BUDGET_MB = 800`). Either the published release is over its own budget or
this sample of 24 stations is not representative, and the next real release
settles it with `python tools/page_bytes.py --site _site --budget-mb 800`. Removing
the shared script from each page would take the same projection to **442 MB**, so
this is a budget question rather than a tidiness one.

## What a page costs to compute, measured

Per page, the timetable half only, on the national feed in this workspace
(419,589 schedules, loaded in 57.1 s), dated 2026-10-12, single process:

| Origin (a sample, not the mean) | Slice schedules | Slice cut | Day index, per day | Reachability search, per day | 8-day total |
|---|---:|---:|---:|---:|---:|
| `AAT` | 848 | 1.10 s | 0.00 s | 0.01 s | **1.17 s** |
| `ABA` | 15,431 | 0.24 s | 0.04 s | 0.83 s | **7.20 s** |
| `AAP` | 188,368 | 0.20 s | 0.65 s | 2.88 s | **28.48 s** |

The eight days are the service week. `build_demo_page.py:2352` and `:2357` loop
`range(0, SERVICE_WEEK_HORIZON + 1)` and call `journeys_from` once per day, and
`atoc_timetable._ensure_indexes` rebuilds the day's indexes whenever the day
changes. `TimetableDb.focused` (`atoc_timetable.py:547`) builds each slice as a
bare `TimetableDb`, so a slice cut per page does not inherit the parent's day
indexes, which is why the per-day index cost appears above.

The build's own measured average is **10.75 s per page on one worker** and 2.7 s
at four workers (`run.py`, measured 2 October 2026 on 2,712 pages; quoted, with
its own date, from the comment beside it). So the timetable half is a large share
of an average page and can exceed it on a large origin.

## Should the site stop writing a page per station?

The question behind the question is real. Every commercial rail site answers it
per request, from databases and engines rather than from files. The public record
says so without going into the web layer.

| Source | What it says | URL |
|---|---|---|
| National Rail | Knowledgebase is a database of station content for 2,500+ stations, published as feeds; the Online Journey Planner is the engine that plans routes and calculates fares; Darwin supplies live times | https://www.nationalrail.co.uk/developers/knowledgebase-data-feeds/, https://www.nationalrail.co.uk/developers/online-journey-planner-data-feeds/, https://www.nationalrail.co.uk/developers/darwin-data-feeds/ |
| Trainline | Best Fare Finder is built from customers' own journey searches, and a search needs a route, a date and passengers | https://www.thetrainline.com/farefinder |
| LNER | Deal Finder is the browse-under-a-budget flow a reader would compare this site to, described as browsing journeys and dates | https://news.railbusinessdaily.com/lner-launches-new-deal-finder-feature/ |
| CDS (National Rail's supplier) | more than 100 integrated data feeds, 227 million Journey Planner requests handled | https://www.cds.co.uk/our-work/national-rail-enquiries |

No public source describes either company pre-rendering a station page per
station, and none describes the cost of the choice. Treat the architecture
comparison as this project's own reasoning, not as evidence about them.

**What a database would change here, and what it would not.**

| | Static pages today | Pages rendered from a store at request time |
|---|---|---|
| Per-page file write | ~20 ms a page, measured as `write_page_atomic` | none |
| Per-page fare and journey computation | 10.75 s a page on one worker | the same work, at request time, or precomputed into the store |
| Serving | any static host, no runtime, offline-friendly, crawlable, one URL per station | a host with a runtime, plus a store, plus a cold path |
| Release gate | files plus a manifest the gates can read | a live service the gates cannot read |
| Freshness | a rebuild, then a publish | write once to the store |
| Licensing and provenance | the release is an artifact a person clears | data served from a service has to be re-argued |

The static argument wins on every row except the two the user actually feels, and
neither of those is fixed by the database. A store would make the *rebuild*
cheaper only if the store is computed in one pass and the pages are rendered from
it, which is available without a runtime. That is task **T2**.

## What landed, and what its measurements are

| Task | What it asked | What landed | Command whose output a reviewer can reproduce |
|---|---|---|---|
| T1 | the station script out of every page | `station-<digest>.js` beside the stylesheet; each page inlines only its own `DATA` | `python tools/page_bytes.py --site _bytes_site` on a controlled two-build comparison; 261,362 → 112,885 bytes on one station |
| T2 | search the service week once for the network, write the facts | the facts store exists and is keyed per origin; the *national* single-pass search was not built, because it would hold the national timetable for the whole build | `python -m unittest tests.test_page_caches.PageFactsTest` |
| T3 | a rebuild keyed per origin | one origin's priced counts and journey weeks keyed by feed; a masked payload comparison skips unchanged writes | `python -m unittest tests.test_page_runner.AllOriginsCliTest` |
| T4 | build in shards and merge | `--shard N/M` and `--merge`, with a merge that proves the partition | the same `AllOriginsCliTest` module's shard cases |
| T5 | measure the release against its budget | measured in the release's own shape: 24 major stations average 2.73 MB a page, a stride sample 806 KB; the with-week shape projects to ~2.2 GB against 800 MB, which is new open work | `python tools/page_bytes.py --site _stride_site` |
| T6 | fold the pricing pre-pass into the facts pass | the pre-pass replays the counts it already priced; the station index is built from the facts | `python -m unittest tests.test_destination_coverage.ReportTest` |
| T7 | decide what the local default build is | the default is the fast single-origin page again; `--all-origins` requires its acknowledgement | `python -m unittest tests.test_page_runner.RunnerBuildOrServeTest` |
| T8 | publish the per-origin cost distribution | `tools/measure_origin_costs.py`: mean 19.37 s against median 4.74 s, max 105.17 s | `python tools/measure_origin_costs.py --origins AAT,ABA,AAP` |
| T9 | reuse the timetable-derived facts across releases | a fares-only refresh reuses every journey fact; the store is keyed by feed content | the sweep-reuse case in `PageFactsTest` |
| T10 | the same shared-asset treatment for the chooser | `chooser-<digest>.js` beside the release | `python -m unittest tests.test_page_output.SharedStationAssetTest` |
| T11 | check whether hashed assets accumulate | a rebuild removes the hashed files its manifest no longer names | `...SharedStationAssetTest.test_a_rebuild_removes_the_hashed_assets_no_page_names` |
| T12 | record what this changes in the registers | ADR-0033, ADR-0047, ADR-0019, ADR-0024, ADR-0050, ADR-0055 and ADR-0032 amended; the findings hold the measurements | `python -m unittest tests.test_agents_map` |

## What is still open, and where it lives

One finding came out of the work, and the audit's own "what was not measured"
section is now measured:

- **A whole-network release is over its byte budget, and the pair rules are why.**
  `docs/open-work.md` holds the entry, the measurements and the three ways it
  would close. Short version: `railcardRules` is the largest block on a real page
  (1.05 MB of Birmingham New Street's 1.63 MB), it grows combinatorially with
  permitted two-ticket splits, and the release projects to roughly 2.2 GB against
  its 800 MB budget with the error bars named.
- **The real release's byte total** is still a projection until a whole-network
  build in the release's own shape runs the gate. That is the first way the
  finding above closes.
- **The national single-pass search (T2 as written) was not built**, and the
  reason is the whole-timetable hold this audit opened about: one national day
  index per day of the week, held for the whole build, is the shape the
  8 October work removed. The facts layer delivers the payoff without it, and
  the sharding (T4) is what would make the national pass affordable.
- **A sharded release build.** T4 landed the shards and the merge; nothing yet
  shards the deploy workflow's own build, which is where the 300-minute timeout
  is spent.

## What was not measured

- **The published build.** The 130-minute figure is quoted from the workflow's own
  comment (2 October 2026) and this audit did not run a whole-network build. The
  per-origin table is three sampled origins, not a distribution, which is why T8
  exists — and it does now.
- **The real release's byte total.** Measured here in a 34-page sample of the
  release's own shape, which projects to ~2.2 GB with wide error bars; the
  whole-network figure remains to be taken.
- **The fares half of a page.** The local fares feed was not loaded into these
  measurements, so the per-page fare, railcard and two-ticket costs are unmeasured
  here. `docs/build-performance-findings.md` measures a prices-only page at
  0.39-0.47 s, which is the part that is not the timetable.
- **What a database deployment would cost.** No store was prototyped. The
  recommendation against one is reasoning from the measured distribution of the
  build's own cost, labelled as reasoning, and the research above is labelled as
  what the sources do and do not say.
- **Whether a sharded build beats a smarter build.** T2 and T4 are independent, and
  T2's saving is the one that would also help a laptop.
