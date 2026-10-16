# ADR-0050: The release is the whole network, and it is affordable

**Status:** Accepted; amended 12 October 2026 and 16 October 2026 (see below)
**Date:** 1 October 2026
**Relates to:** ADR-0019 (one page per station), ADR-0024 (scaling and the batch
build, re-measured the same day), ADR-0046 (a row list ships as a table and a
pool), ADR-0047 (the station route fetches one hashed stylesheet)
Answers question 1 of `docs/open-work.md`.

## Context

The deploy workflow published one station. `--origin GRA` put Grantham's page
at `/from/grantham/` beside a chooser offering exactly one origin, so a reader
who arrived at a product whose premise is "where can we go from anywhere" met a
single destination. The route contract was already right and the coverage was
not, which made this a coverage decision rather than a structural one.

The obvious objection was cost. ADR-0024 had projected that a whole-network
build with journey times is **about two days**, from a measurement on an invented
uniform feed in which every one of 2,500 stations priced about 2,500
destinations. A workflow with `timeout-minutes: 10` could not host that, and
publishing the network without times would contradict the workflow's own
journeys gate.

That projection was measuring a network this project does not have, and it was
the whole of the argument against doing it.

## What was measured

Against the real feed, with the national timetable loaded:

| | measured |
|---|---|
| priced origins | **2,718** |
| origin-destination pairs | 316,315 |
| destinations per origin | median **91**, mean **116**, max 851 |
| fares and schedules loaded | 7,818,772 fares, 419,589 schedules |
| load before the first page | 279s |
| first twenty pages (workers reading their fare indexes) | 79s |
| steady state, 3 workers on a 12-CPU machine | **0.84 pages/s** |

Per-origin cost turned out not to track destination count at all on the real
feed: HPE, which prices 851 destinations, took 110s in isolation, and ALG, which
prices one, took 99s, with a median origin between them at 94s. The cost is the
fixed timetable load, and ADR-0024's superquadratic curve was a property of the
invented feed's uniform shape.

Extrapolating the steady state: about 54 minutes of page building plus the 279s
load on this machine, and about 81 minutes plus the load on GitHub's 2-vCPU
standard runner with two workers. Not two days.

## Decision

1. **The deploy workflow builds `--all-origins`.** Every priced station, with
   the national timetable, on the schedule and on any feed change. The route
   contract does not change: the root is the chooser and a station is at
   `/from/<slug>/`.
2. **`timeout-minutes` is 150.** The measured extrapolation on a 2-core runner
   is about 86 minutes including the load. Nearly double is enough for a busier
   day and little enough that a stalled build fails rather than occupying a
   runner until the job limit kills it.
3. **The worker count is read from the runner.** The work is CPU-bound, so the
   useful worker count is the core count, and the number in the file was a
   machine this repository happens to have.
4. **A byte-budget gate is added, because nothing else in the workflow reads
   the bytes.** The manifest check counts routes, the journey check counts
   fields, and every one of them is satisfied by a release twice the size. The
   measured release is 498 MB against a target of 800 MB, and
   `tools/page_bytes.py --site _site` is what holds that.
5. **The browser sweep is bounded, and the bound is a spread rather than a
   prefix.** A whole-network sweep is 2,718 pages; `--max 24` drives 24 of them.
   The first 24 pages in name order are the stations whose slugs start with A
   and B, and a sample confined to one end of the alphabet cannot find a bug
   that only the far end has. The suite takes every `--max`-th page, which is
   deterministic and needs no seed.
6. **The build stays a scheduled batch, not a per-push job.** The workflow
   already skips the build entirely when the feed fingerprint is unchanged, so
   a push that touches no feed costs nothing, and the RSP fares feed updates
   weekly. The hourly cost is paid when there is something to publish.

## Consequences

- The product's premise is now the release. A reader arriving from any of 2,718
  stations finds a page, and the chooser at the root ranks all of them.
- The release is about 498 MB of pages across 2,714 routes. That is inside the
  800 MB target with room, and the step that proves it is a step that can fail.
- A whole-network build takes about an hour and a half on a 2-core runner, so
  the day's build is not interactive. The gates that read it (manifest, byte
  budget, journeys, browser sweep) add their own time on top.
- The browser sweep is a sample, and it says so on stderr with the names of the
  pages it drove. A gate reporting on a sample and calling it the site is worse
  than no gate, so the reporting is part of the change rather than a footnote.
- `run.py --all-origins` gains a worker count from the core count, and its
  refusal now quotes the measured figure. The flag still exists; the sentence
  it used to print ("a batch job measured in days") was a projection from a
  feed shape the project does not have.

Read by running:

```bash
python _cache/origin_spread.py feeds/fares
python run.py --all-origins
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable \
  --all-origins --workers 3 --out _cache/net_probe/index.html --notices nre,rdg,ogl,accuracy
python -m tools.page_bytes --site _cache/net_probe
```

## Amendment — 12 October 2026: the 498 MB figure is prices-only, and the build shards

Decision 4's "measured release is 498 MB" was a prices-only build
(`--fast-all-origins`): it never priced the service week, the two-ticket
pairs or the departures the release ships, so it is not the release decision
1 publishes. Measured 12 October 2026 in the release's own shape
(`docs/build-performance-findings.md`): 24 major stations average 2.73 MB a
page, a 10-page stride sample 806 KB, driven by two-ticket pair records in
`railcardRules` (~1 MB on the heaviest hubs) rather than by anything the
1 October work moved. The with-week shape projects to roughly 2.2 GB against
the 800 MB budget — over, with wide error bars at n=10. The gate in decision
4 is what settles it: it refuses on its own, and until the next real release
runs it the projection stands as the estimate. `docs/open-work.md` carries
the pair-rule encoding this measurement points at.

What decision 1 publishes is unchanged: one page per priced station, chooser
at the root. How it is built may now be sharded: `--shard N/M` over the
origin list with a `--merge` that proves the partition, for the runners the
single-build wall clock does not fit. A shard is a share of the same release,
not a release of its own, and the merge writes the chooser, the station list
and the manifest once from the union. Decisions 2, 3, 5 and 6 stand.

## Amendment — 16 October 2026: the bound is the sweep, and the shape pages get driven

Decision 5 said the spread "always includes the first and last" page of the
list. It does not, and never did for any list longer than `--max`: the last
index a spread of `MAX_PAGES` reaches is `floor((MAX_PAGES-1) * length /
MAX_PAGES)`, which on a 2,700-page network is most of a sample short of the
end. The claim had a cost. The deploy workflow names two pages on the command
line -- a prices-only page and a one-page page, the two shapes a sweep cannot
otherwise meet -- and because the bound was applied to the whole list rather
than to the swept directory, a spread that took every 24th page of 2,700 could
and did leave them out of every run. Measured in run 38888953205: 24 pages
driven, all of them station pages, neither shape among them.

`--max` now bounds the pages of the swept directory. A page named on the
command line is driven whatever the bound is, because a page is named for a
reason, and the reasons are the shapes the spread cannot be relied on to
reach.

Decision 5's spread is unchanged and still right for the sweep itself: 24
pages of a whole network, evenly spread rather than the A's and the B's.

The same run is what made the skip budget a per-shape figure; see the
amendment to ADR-0027 for that half.
