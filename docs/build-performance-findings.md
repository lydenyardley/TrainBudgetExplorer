# Why a local build is slow, measured

**Written:** 7 October 2026
**For:** the next person who double-clicks `run.bat` and wonders why a two-station
preview is taking most of an hour.

Every number here was measured on this repository's own machine on 7 October
2026 against the feeds downloaded 24 September 2026 (`feeds/fares/dtd-fares.zip`,
`feeds/timetable/dtd-timetable.zip`). Each figure is labelled measured or
extrapolated, and the reproduction command is beside it. Where a figure is an
extrapolation from a sample, the sample size is named.

**Revision, 7 October 2026.** The first draft read "5.1 s against did not finish in
8 minutes" as a search-cost finding: 80x the schedules, so about 80x the page.
Measured properly, the searches are **2.3x** slower and the per-day index build is
8 s a week, so what the minutes are is the **1.87 GB footprint** held beside the
fares feed. The headline figures are unchanged -- they are measurements -- and the
explanation of them is corrected below.

## The one-line answer

**The cost is not the number of stations.** It is the **national timetable**, and
the reason is its size in memory rather than the work it does per search. A page
whose journey search runs against an index scoped to its own origin's
destinations holds about **50 MB** of timetable and answers 30 journey searches
in **0.14 s**; the same page against the whole national index holds **1.87 GB**
and answers the same 30 searches in **0.31 s**. The searches are 2.3x slower, not
80x. What the 1.87 GB does is sit beside the 2.1 GB fares feed on a machine with
about 5 GB free, and a build that pages spends its minutes there.

Same page, same fully-loaded fares feed: **5.1 s** with a focused timetable,
and **not finished in 17 minutes** (stopped) with the unfocused one, measured
while the machine had 2.84 GB free. The second figure is a paging figure, and
that is the point.

`run.bat` calls `python run.py`, and `run.py`'s default is `--all-origins` with
`focus_origin=None`, so every worker parses and holds the whole timetable for
every page.

## What this means if you just double-click `run.bat`

You asked for a page about a station, and the build starts by preparing the whole
country. Three things follow from that, and none of them needs a code change to
act on today:

1. **You are running a batch job, not a preview.** The double-click default builds
a page for every station the feed prices, 3,424 of them on this feed. If you want
to look at one station, say so: `python run.py --origin GRA` is **44 seconds**, and
the station page it writes is the same one the long run would have written.
2. **Journey times are the expensive part, so ask for them deliberately.** Without
`--with-timetable` the build reads no timetable at all and writes prices only.
With it, every page searches a timetable index, and that search is where the
minutes go.
3. **Free memory decides how many pages are built at once.** Below 6.4 GB free the
builder runs a single worker and tells you it will page. That is deliberate, and
it is also the slowest version of the build.

What you cannot get by choosing a flag is a whole-network build that is fast,
because the cost is inside the build rather than in how it is invoked. That is
strategy 7 below, in plain words.

## What each entry point actually does

| Command | Feed loading | Timetable | Pages | Measured end to end |
| --- | --- | --- | --- | --- |
| `run.bat` (double-click) | whole fares feed | **none** (opt-in flag) | every priced station (3,424 on this feed) | tens of minutes; not fully run (see below) |
| `python run.py --origin GRA` | the origin's fare slice | none | one | **44 s** (measured) |
| `python run.py --origin GRA --with-timetable` | the origin's fare slice | focused on that origin's destinations | one | **2 m 57 s** cold, **2 m 03 s** warm (measured) |
| `python build_stations.py GRA NOT` | whole fares feed | **whole national timetable, unfocused, per page** | two | **no page written after 24 min**, stopped (measured twice) |
| The deploy workflow | whole fares feed | whole timetable, unfocused, per worker | whole network | ~81 min per README/ADR-0050, from before ADR-0061 and the service week (see caveat) |

Two facts about the default path are easy to miss and are both in `run.py`:

- `python run.py` with no `--origin` sets `--all-origins` itself. The
  double-click path is a whole-network batch job, not a preview.
- The national timetable is **not** loaded unless `--with-timetable` is passed.
  The double-click default is a prices-only build.

## The per-phase measurements

Reproduction: each figure is from a one-off script that loads the feed and
stops; the exact script is quoted under the table.

| Phase | Measured | Memory (free before -> after) |
| --- | --- | --- |
| Whole fares feed load (`FaresDb().load_feed("feeds/fares")`) | **37.6 s** | 5.96 -> 3.83 GB |
| Whole timetable load, no focus (`TimetableDb().load_feed("feeds/timetable")`) | **55.6 s** | 6.03 -> 4.21 GB |
| Focused timetable load (`focus_origin="GRA"`) | **50.6 s** | 4.96 -> 4.91 GB, index 5,262 schedules of 419,589 |
| Pricing pre-pass, one origin, fares only | **0.01-0.09 s** | - |
| `build_payload("GRA")`, prices only | **0.39-0.47 s** | - |
| `build_payload("GRA")`, **focused** timetable | **5.1 s** | - |
| `build_payload("GRA")`, **unfocused** national timetable | **> 480 s** (killed) | 3.61 -> 3.57 GB before the call |

The last three rows are the finding. They use the **same** fully-loaded fares
feed; only the timetable differs. The focused index holds 5,262 schedules and
224,045 calling points; the unfocused one holds 419,589 schedules and 7,700,987
calling points. That is 80x the schedules for the same page, and 1.87 GB against
50 MB to hold -- which is the part that costs the minutes, as the next section
measures.

```python
# the focused / unfocused comparison, from the session that produced the table
from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
import build_demo_page as b
fares = FaresDb().load_feed("feeds/fares")                      # 37.6 s
tt = TimetableDb().load_feed("feeds/timetable", focus_origin="GRA")  # 51.0 s, 5,262 schedules
b.build_payload(fares, tt, "GRA", day=date(2026, 10, 7))        # 5.1 s
```

### Where the unfocused seconds actually go, measured

The 5.1 s against "not finished in 8 minutes" invited the wrong explanation, so
this was measured separately, on an idle machine, in three steps:

| Measurement | National index | Focused (`focus_origin="GRA"`) |
| --- | --- | --- |
| `load_feed` | **56.1 s**, 419,589 schedules, 7,700,987 calling points | **50.6 s**, 5,262 schedules, 224,045 calling points |
| held afterwards | 4.92 -> 3.05 GB free (**1.87 GB**) | 4.96 -> 4.91 GB free (**50 MB**) |
| `_ensure_indexes(day)`, seven days | **1.1-2.3 s each**, 8.2 s for the week | **0.0 s each** |
| 30 `best_journey` searches | **0.31 s** (10 ms each) | **0.14 s** (5 ms each) |
| `departures()`, five destinations | 0.01 s | not separately measured |

The loader is parse-bound: focusing drops the index to 1.3% of the schedules and
saves 5 s of a 56 s read, because the loader still has to see every record to know
it can drop it. The per-day index build that a service week repeats costs 8.2 s
over seven days even nationally. The search itself is 2.3x slower nationally.

So the schedule count is not what makes an unfocused page take minutes. Its
**footprint** is: 1.87 GB against 50 MB, on a machine whose whole free margin is
about 5 GB while the fares feed is loaded.

**Extrapolation, labelled.** The all-origins pricing pre-pass samples at
0.01-0.09 s per origin (ten origins measured), so pricing all 3,424 origins
fares-only is about **2 minutes** single-threaded. Rendering is not the problem
either: at 0.39-0.47 s a page, 2,718 prices-only pages are roughly 18-21 minutes
of single-threaded work, or a handful of minutes across four workers. Neither
figure explains a two-station build that has not written a page in 23 minutes.
The unfocused timetable does.

## The two-station build, measured twice

| Run | Conditions | Result |
| --- | --- | --- |
| 6 October 2026 | 5.5 GB free, unit suite running alongside | **no page in 23 minutes**, stopped |
| 7 October 2026 | 5.1 GB free, machine otherwise idle | **no page in 24 minutes**, stopped by hand |

Both runs printed the same warning before starting: *"5.1 GB of memory is free and
this build wants about 6.4 GB for the two feeds and one page at a time. It will
still run, slowly, by paging."* The 6.4 GB is
`build_workers.ONE_WORKER_FLOOR` (4.4 GB parent + 2.0 GB reserved).

The idle run also gives the phase split, because the script names each one:

- fares feed + national timetable load: **11 minutes** (the log's last write before
  rendering began), where the same two loads measured **93 s** -- 37 s + 56 s --
  when the machine had room. That 7x is paging, and it happens before a single
  page is built.
- free memory once both feeds were held and the first page began: **0.88 GB**.
- the two station pages: not written inside the remaining 13 minutes.

An earlier run of the same command, on a machine with the memory the floor asks
for, came in **under five minutes**. The reconciliation is the floor, not the
station count: the in-process build holds ~4.2 GB before the first page and
renders with ~0.8 GB left. That is why the flagged strategies below are ordered by
memory first.

## What is actually wrong

**`--all-origins` gives every process the whole country's timetable.** In
`build_demo_page.main`, the single-origin path computes a `focus_destinations`
set and passes a per-origin `cache_path`; the all-origins path passes
`focus_origin=None` and no cache, and `build_workers.init_worker` then does
`TimetableDb().load_feed(timetable)` per worker with no focus. A page only ever
asks about its own origin's destinations, so holding the other 3,300 stations'
schedules buys nothing and holds 1.87 GB the page never reads.

This is a code-level cause and a memory-level one at the same time, and which one
bites depends on the machine. The measured facts above say the search is 2.3x
slower and the index build is 8 s a week, so on a machine with room to spare the
unfocused build is slower but not the 23 minutes reported. On this machine, which
has about 5 GB free, the 1.87 GB is what fails.

**The prescribed fix does not work as written.** "Give every origin its own
focused index and its own cache" cannot be done by parsing per origin: a focused
parse still costs 50.6 s, so 3,424 of them is two days of CPU, and one pickle per
origin for the whole network is gigabytes of disk. A focus has to be derived **in
memory from a single parse**, which is cheap per origin but only pays off if the
national schedule list is not also retained -- and today it is, because a worker
holds one database for every page it builds. That trade is the real design
question, and it is written up in `docs/open-work.md`.

## Strategies, cheapest first

1. **Preview one station, not the network.** `python run.py --origin GRA`
   (or `python run.py --origin GRA --with-timetable`). Measured 44 s and
   ~3 min. This is the direct fix for "I only wanted to look at one station".
2. **Serve what is already built.** `python run.py --no-build`, or just leave
   the previous run's server up. No rebuild at all.
3. **Do not reach for `build_stations.py` to save time.** It is the *documented*
   two-station path and it is the *slowest* one, because it builds through
   `--all-origins`. Use it only when you need one shared chooser over a small
   set; otherwise `run.py --origin` is minutes rather than tens of minutes.
4. **Keep the timetable opt-in.** The default `run.bat` path is prices-only and
   therefore much cheaper. Only pass `--with-timetable` when the times matter.
5. **Free memory first.** Below 6.4 GB free the build pages and the worker
   budget drops to one. Close the browser and the editor before a whole-network
   build; a preview does not need the headroom.
6. **Repeat builds are warmer, not free.** The focused timetable cache takes the
   single-origin build from 2 m 57 s to 2 m 03 s (54 s saved). It does not help
   the unfocused all-origins path, which writes no such cache.
7. **Fix the footprint for real.** Give each page a timetable scoped to that
   origin's destinations, as the single-origin path already does, and stop
   holding the national index while a page is built.

   **In plain words:** right now, when the build writes the page for one town, it
   first loads every train in the country and keeps that in memory while it
   writes the page. It should hold only the trains the page can reach, because a
   page never asks about anywhere else. Nothing about the page a reader sees
   changes. The searches get 2.3x faster and, more importantly, the build stops
   needing 1.87 GB it does not read.

   The one-station path (`run.py --origin GRA`) already works this way, which is
   why it is fast; the whole-network path never got the same treatment. This is
   the change worth making, and it is not yet made.

## A side note: stale servers on the machine

Two `build_stations.py` processes were found still listening on
`127.0.0.1:8742` when this was written, one started 6 October 18:50 and one
7 October 14:16. They are servers left behind by earlier runs (the script builds
and then serves until Ctrl+C), not stuck builds. They hold a little memory and
will make a third `build_stations.py` fight for the port. Close the black window
when done with it.

## What this does not cover

- The deploy workflow's own timings. The README's whole-network figures
  (~54-81 min) predate ADR-0061's two-ticket pricing and the service-week sweep,
  and both add per-page work. Whether the published build is still inside its
  `timeout-minutes: 150` should be **re-measured before the next release**, not
  assumed from the older table.
- A network-wide re-measurement of the focused-index fix. The 5.1 s figure is
  one page on one feed; the shape transfers, the per-origin spread does not.
