# Why a local build is slow, measured

**Written:** 7 October 2026
**For:** the next person who double-clicks `run.bat` and wonders why a two-station
preview is taking most of an hour.

Every number here was measured on this repository's own machine, on 7 and
8 October 2026 against the feeds downloaded 24 September 2026
(`feeds/fares/dtd-fares.zip`, `feeds/timetable/dtd-timetable.zip`), and on the
later dates named by the sections that carry them: 12 October 2026 for the
build-cost audit's figures, 14 October 2026 for the page write, and 15 October
2026 for the verify suite's own runtime and the type-check census.

Each figure is labelled measured or
extrapolated, and the reproduction command is beside it. Where a figure is an
extrapolation from a sample, the sample size is named.

**Revision, 7 October 2026.** The first draft read "5.1 s against did not finish in
8 minutes" as a search-cost finding: 80x the schedules, so about 80x the page.
Measured properly, the searches are **2.3x** slower and the per-day index build is
8 s a week, so what the minutes are is the **1.87 GB footprint** held beside the
fares feed. The headline figures are unchanged -- they are measurements -- and the
explanation of them is corrected below.

**Revision, 7 October 2026 (later the same day).** The fares half of that
footprint is now released before a page renders. The two-station build that had
written no page in 24 minutes **finished, exit 0, in 63 min 38 s**. The timetable
half is untouched, and it is why the first page still takes 35 minutes. The third
row of the two-station table is that measurement, and "What is actually wrong"
now separates the two halves.

**Revision, 8 October 2026.** The timetable half is fixed for a page, and
measured. A page
is now built from **its own origin's slice** of the timetable, cut out of the
database the build already holds (`atoc_timetable.TimetableDb.focused`), and the
same two-station command on the same feeds **finished, exit 0, in 20 min 53 s**:
Grantham at 9.7 minutes, Nottingham at 20.8, on a machine with **2.1 GB free**
against the same 6.4 GB floor. The 63-minute run had 5.1 GB. Both pages are
character-for-character the pages of the previous release apart from `builtAt`
and the source fingerprint, so nothing a reader sees moved. A control run of the
same build with the slice switched off wrote no page in 25 minutes, on **more**
free memory through its page phase than this run had. What the slice does
**not** do is release the index it was cut from: the national timetable is still
held by the process for the whole build, which is where the floor and the
remaining minutes are. "The timetable half, and what it holds" below has the
measurements.

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

`run.bat` calls `python run.py`, and at the time of this measurement `run.py`'s
default was `--all-origins` with `focus_origin=None`, so every worker parsed and
held the whole timetable. Since 12 October 2026 the default is the single-origin
page again and `--all-origins` needs `--i-know-this-is-slow` (T7 of the
12 October 2026 build-cost audit, settled in `docs/open-work.md`). Since
8 October 2026 a page is built from a slice of it cut for its own origin, so the
1.87 GB is no longer what a page holds while it is assembled. The index is still
parsed and held once per process, and that part is unchanged.

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
| `python build_stations.py GRA NOT` | whole fares feed | the whole timetable parsed, a per-origin slice held per page | two | **20 min 53 s** (measured 8 October 2026; no page at all in 24 minutes on 7 October) |
| The deploy workflow | whole fares feed | whole timetable, unfocused, per worker | whole network | ~81 min per README/ADR-0050, from before ADR-0061 and the service week (see caveat) |

Two facts about the default path are easy to miss and are both in `run.py`:

- Until 12 October 2026, `python run.py` with no `--origin` set
  `--all-origins` itself, so the double-click path was a whole-network batch
  job, not a preview. It is now the fast single-origin page (T7), and the
  table above describes the earlier default.
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

## The two-station build, measured five times

| Run | Conditions | Result |
| --- | --- | --- |
| 6 October 2026 | 5.5 GB free, unit suite running alongside | **no page in 23 minutes**, stopped |
| 7 October 2026, before the fares release | 5.1 GB free, machine otherwise idle | **no page in 24 minutes**, stopped by hand |
| 7 October 2026, after the fares release | 5.1 GB free, machine otherwise idle | **finished, exit 0, 63 min 38 s** -- Grantham at 35 min, Nottingham at 63 |
| 8 October 2026, after the timetable slice | **2.1 GB free**, the machine running the operator's own browser again | **finished, exit 0, 20 min 53 s** -- Grantham at 9.7 min, Nottingham at 20.8 |
| 8 October 2026, given the index and no timetable feed read | **4.7 GB free**, machine otherwise idle | **finished, exit 0, 3 min 44 s** -- both pages, the same pages |

The fifth run is not a like-for-like comparison with the fourth: it held no
national index at all, and it had twice the free memory. What it removes is
measurable on its own -- the 56.7 s and 1.87 GB of parsing and holding the
national index, replaced by 4.4-5.9 s and a slice (below) -- and the pages it
wrote were checked against the fourth run's page by page rather than assumed.

Every one printed the same warning before starting: *"x GB of memory is free and
this build wants about 6.4 GB for the two feeds and one page at a time. It will
still run, slowly, by paging."* The 6.4 GB is
`build_workers.ONE_WORKER_FLOOR` (4.4 GB parent + 2.0 GB reserved). The 8 October
row is the only one taken while other programs were using the machine, and it had
**less** free memory than either 7 October run, so its figure is not a machine
that had been tidied up for it.

Reproduction, both idle runs: `python build_stations.py GRA NOT --no-serve --date
2026-10-07`, free memory sampled every 15 s alongside it.

The two idle runs give the phase split, because the script names each one:

- **Before the fares release.** fares feed + national timetable load: **11
  minutes** (the log's last write before rendering began), where the same two
  loads measured **93 s** -- 37 s + 56 s -- when the machine had room. That 7x is
  paging, and it happens before a single page is built. Free memory once both
  feeds were held and the first page began: **0.88 GB**. The two station pages:
  not written inside the remaining 13 minutes.
- **After the fares release.** The same paged 11-minute load, bottoming at **0.39
  GB** free while both feeds were held. Free memory was back to **2.6-3.0 GB** as
  soon as the fares feed was released, and stayed above 1.5 GB through both page
  writes. Both pages landed and the process exited 0.
- **After the timetable slice.** The two loads took about **4 minutes** together
  (fares first, then the timetable) and the two feeds bottomed at **0.94 GB** free
  while both were held. Free memory was **3.1-3.3 GB** through the whole of
  Grantham's page, which is the phase that used to hold the national index's own
  per-day indexes as well, and the run's lowest point was **0.37 GB** at 13.7
  minutes -- inside Nottingham's page, the same place the old run's 0.88 GB was.
  Grantham was written at 9.7 minutes and the process exited 0 at 20 min 53 s.

  The one figure in that run that does not match the earlier ones is the load:
  4 minutes against 11, on a machine with less memory free than the 11-minute run
  had. Nothing in this change touches how a feed is loaded, so that difference is
  the machine rather than the code, and it is the reason the timing claim here is
  about the pages: **9.7 minutes to the first page against 35**, on the same feeds
  with the same page built from them.

**What the release is.** Every build now writes the shared fare metadata and one
index per origin before it renders, and `build_workers.restore_worker_fares`
gives the one-worker path the same per-origin slice a pool worker takes. The 2.1
GB national fare feed is therefore released before the first page, and a page
holds only its own origin's fares while it renders. The **6.4 GB floor does not
move**: the preparation peak is the two whole feeds plus the index write, which is
what `PARENT_BYTES` covers, and the timetable half of it is untouched. What moved
is the render phase, which used to hold a whole fares feed it never read.

Reconciling the earlier figure. An earlier run of the same command, on a machine
with the memory the floor asks for, came in **under five minutes**. The
reconciliation is the floor, not the station count, and it still is: 93 s of feed
loading with room against 11 minutes without, and the render then had a page's
worth of fares rather than the country's. That is why the flagged strategies below
are ordered by memory first.

## The timetable half, and what it holds

**A page is built from a slice of the timetable, cut for its origin.**
`TimetableDb.focused(origin)` returns a database holding exactly the schedules a
page at that origin can use, and `build_payload` asks for it before it touches
the timetable at all, so the in-process build and every pool worker build their
pages from one. The slice shares the source's schedule objects rather than
copying them, and inherits its service window and its counts: the dates and the
figures a page carries are claims about the feed behind it, and a reader cannot
tell which part of a feed the page needed.

**Which schedules a page can use is two sets, and both come from the feed.** The
first is the schedules that call the origin, because a journey starts there. The
second is the schedules that call a station the first set calls, because a
one-change journey boards its onward service at an interchange on the first
train's own stop chain. Neither is read from the fares feed. That matters more
than it sounds: the single-origin path's focus *is* built from the three
destination lists its fares feed prices, so it can only keep services for places
the feed priced -- and ADR-0061 exists precisely because a page can also show a
row for a place with no flow at all, priced from two tickets that meet on a
journey the page already times. A slice cut from the fare lists would drop the
services those rows are timed from.

**Measured on the real feed** (24 September 2026 downloads, measured 8 October
2026):

| Measurement | Figure |
| --- | --- |
| The first cut for an origin (it builds the TIPLOC index) | **1.66 s** |
| A later cut, same database, another origin | **0.248 s** |
| Grantham's slice | **114,244** of 419,589 schedules, 2,747,086 of 7,700,987 calling points |
| The database it was cut from, for comparison | 419,589 schedules, 1.87 GB held |

**Why the slice is a quarter of the feed and not 1.3%.** The single-origin
path's fare-based focus holds 5,262 schedules of 419,589 for Grantham. This slice
holds 114,244, because its second set is "every service that calls anywhere a
Grantham train calls": an East Coast Main Line train's stop chain covers a lot of
the country, and everything calling at any of it comes along. Narrowing it to the
priced destinations would be the 1.3% and would lose the ADR-0061 rows above,
which is the trade the fare-based focus makes and this one does not. What the page
gains is what it *indexes*: `_ensure_indexes` builds its per-day index over the
schedules one page can use rather than over the network, and that allocation ran
while 1.87 GB of index sat beside a 2.1 GB fares feed.

**The pages did not move.** Both pages this run wrote are character-for-character
the pages of the 7 October release, apart from `builtAt` (the build's own
timestamp) and `sourceFingerprint` (a hash of the source files, which this change
is). Two measurements say so: a diff of the written HTML against a copy of the
previous release's, and a `build_payload` byte-diff in
`tests/test_build_demo_page.py`. The slice answering every page question the same
way as the whole feed is held by seven tests in `tests/test_atoc_timetable.py`,
over a fixture of two corridors with nothing between them, which is the only shape
where a slice is a strict subset.

**The control, run the same day.** `TimetableDb.focused` was replaced with one
that hands back the database it is called on, so the run has the fares release and
nothing else -- the same feeds, the same date, `--workers 1`, Grantham alone,
same in-process path. It was **killed at its own 25-minute cap having written no
page**, with **3.2-3.35 GB free** through the last five minutes of its page phase.
That is *more* room than the sliced run had while it wrote Grantham's page in 4.5
minutes. Its page phase starts at the last write before rendering (the CSS, the
picker file and the per-origin fare index, at 11 minutes in) and had 14 minutes at
that free memory without finishing. The one thing its run is not controlling for
is the load: it bottomed at **0.23 GB** free where the sliced run bottomed at
0.94 GB, because the un-sliced process is a different shape from the first second.
The page phase's free memory is the like-for-like part, and there the control is
better off and still slower by more than 3x.

**What it did not do at first, and now does.** For the first cut, the database a
slice was cut from still had to be there: the one-worker path kept the parent's
for the whole build, and a pool worker parsed its own in `init_worker`. The slices
are written to disk instead now, so a build given an index never parses the
timetable at all -- see the next section. What has not moved is
`build_workers.ONE_WORKER_FLOOR` (6.4 GB), because every build without an index
still pays for the parse, and the whole-network build is not re-measured here.

## The per-origin index on disk

**A slice can be written once and read by every build after it.**
`atoc_timetable.SliceIndex` is a directory of per-origin pickles, named for the
feed's bytes, the parser's source fingerprint and the layout version
(`SLICE_INDEX_SCHEMA`), so an index cut from another download or written by
another version of this code is a different directory rather than a wrong answer.
`tools/build_timetable_index.py` writes them from one parse of the feed, and
`build_demo_page.py --timetable-index` builds pages from them. When the index
holds a slice for every page the build writes, the feed is not read at all: not in
the parent, and not in the pool workers, which are handed no timetable to parse.

**Measured on the real feed** (24 September 2026 downloads, measured 8 October
2026):

| Measurement | Figure |
| --- | --- |
| Writing the index for GRA and NOT, one parse of the feed included | **88 s**, of which **53.9 s** is the parse |
| GRA.pickle | **157.0 MB**, 114,244 of 419,589 schedules, 2,747,086 calling points |
| NOT.pickle | **208.8 MB**, 143,560 of 419,589 schedules, 3,728,248 calling points |
| Reading GRA's slice back, no feed in the process | **4.4-5.2 s**, and **855 MB** of Python heap for the 157 MB file |
| Reading NOT's slice back | **5.5-5.9 s**, and **1,133 MB** for the 209 MB file |
| Parsing the national index instead | **56.7 s**, **1.87 GB** held |

The held figures are `tracemalloc` heap growth around the load, not a system free
memory delta: the free memory of the machine moves for reasons that have nothing
to do with the file being read, and reading the same slice twice in one process
was measured at 0.36 GB and at 1.67 GB that way. A slice costs more than its file
because it carries the whole station map and the long-distance services have more
calling points each than the feed's average.

**What it costs to keep.** One file per origin, and a slice is a quarter of the
feed for a main-line station, so an index is for the origins a build actually
writes: the two above are 365.8 MB together. `--all-origins` is refused by the
writer without `--max-bytes`, because indexing all 3,436 priced stations is
writing the network out 3,436 times.

**The write is checked, not assumed.** `SliceIndex.save` re-reads every file it
writes, requires it to come back as that origin's slice of that many schedules,
and raises if it does not. A slice that cannot be restored fails at the tool that
wrote it, with the feed that produced it still in hand, rather than at a build
that finds a miss on every page.

**The question a page asks is one lookup now, not a scan.** `intermediate_crs`
(the ADR-0061 question: which stations a journey's train calls at between two
ends) scanned every schedule in the day for the train's identity -- measured at
**0.6 s a call**, which is minutes inside one page, because a page asks it once per
leg it shows. `_ensure_indexes` now builds `_schedules_by_uid` beside the rest of
the day's indexes and the call is a dict lookup, which is what makes a sweep over
the whole feed affordable at all.

**The build that reads it.** Given the index for Grantham and Nottingham and the
same two feeds on the command line, the two-station build **finished, exit 0, in
3 min 44 s** with 4.7 GB free, printed *"the index holds all 2 station(s) this
build will write; the timetable feed is not read"*, and wrote the same site: both
station pages, the chooser, `stations.js`, the privacy page and the release
manifest. The station pages were compared line by line against the pages the slice
build wrote: all 3,279 lines that are not the page's `DATA` object are
byte-identical once `builtAt` and `sourceFingerprint` are masked, and the `DATA`
object is equal as a value once one thing is normalised, below.

**What that normalisation is.** The 329 destinations on a day are the same 329
with the same durations and change counts, in a different order: `journeys_from`
fills its result by iterating `_reachable(origin)`, which is a set, so the key
order of anything written from that dict -- `serviceWeek` among them -- follows the
process's `PYTHONHASHSEED`. It is not the index and not the slice: in one process
the whole feed, the cut slice and the slice read back from disk return the
identical order, and two processes with different seeds return different orders for
all three. The "character-for-character" claims above are therefore byte claims
about two runs of the same command on the same machine, and a page's key order is
not reproducible across runs. Fixing it is a line at the call site and a
page-wide byte change; it is pre-existing and not this change.

### Every origin, every day

**What the slice claims is about a page's questions, so it is checked against
them.** `tools/check_slice_equivalence.py` walks the feed's origins and the seven
days of the service week, asks the whole database and the slice the same
questions, and compares the answers destination by destination: the departure, the
arrival, the change count, every leg's train, ends and times, every leg's
in-between calling points (ADR-0061, once per leg a page shows), the service window
and the counts the page reports. It checkpoints every 25 pairs and resumes,
because it is hours of CPU on the national download.

**What it costs, measured.** For one origin-day the whole database's search is
0.03-3.8 s, the cut is 0.22-1.3 s, the slice's own search and day index is
0.05-5.2 s, and every leg's `intermediate_crs` together is **under 0.02 s** --
2,027 of them for Grantham -- which is the `_schedules_by_uid` lookup above. Over
3,767 origins and seven days that is 26,369 origin-days at **about 2.4 s each**, or
**about 17 hours**: the question is complete there and it is not a turn's work,
which is why the tool resumes rather than being trimmed.

**The result, measured (8 October 2026, 14:50).** Everything compared agrees:
**0 differing, 0 errors**, and the checkpoint records two runs.

- **The seven-day sample is complete.** Every 30th code of the feed's own sorted
  origin list -- 126 origins, so the sample spreads across the alphabet rather
  than being picked -- asked all seven questions: **882 of 882 origin-days,
  every one agreed**, exit 0.
- **The exhaustive sweep of the first day is a third done and running.** It ran
  command by command with the checkpoint as the handover, reaching **1,277 of
  the 3,767 origins of 2026-10-07** by the time this was written; the checkpoint
  holds **2,033 origin-days, all of them `ok`** -- those origins plus the six
  later days of the sample's 126.

Every one of those pairs asked the complete question -- every leg of every journey
the page would show. The whole request is 3,767 origins by seven days, 26,369
origin-days at about 2.4-3.1 s each, which is **about 17-18 hours**: the complete
sweep is not a turn's work, which is why the tool stops and resumes instead of
being trimmed to a question it could finish:

```
python -m tools.check_slice_equivalence --timetable feeds/timetable \
    --date 2026-10-07 --days 7 --progress _cache/slice-equivalence.json
```

Run that again and it continues from the checkpoint. A pair that differs is named,
counted, and kept with its differences, so the sweep's verdict is about the request
rather than about the run: exit 0 every requested origin-day agreed, 1 one did not
or could not be compared, 2 some are still to compare. The 150 pairs an earlier
sampled run left in the checkpoint -- `--max-legs 25` -- were **not** carried over
when the complete question was asked, which is the guard the tool now enforces.

**The same request in shards, 8 October 2026 (ADR-0066).** An origin-day is
compared against the feed and nothing else, so the request is embarrassingly
parallel and the tool now takes a share of it: `--shard N/M` compares origins N,
N+M, N+2M ... of the request's origin list, checkpoints to a file of its own beside the
base one, and `--merge M` reads those files back into the one verdict a single run
would have printed. The shares are disjoint by construction, and the merge checks
that partition rather than trusting it -- a missing shard, a shard asked a
different request, two shards that overlap, an origin in no shard, or a pair
outside the origin-days its own file records are all exit 2 rather than a verdict.

**Re-measured the same day, and the rates still hold.** The feed loads in **58.0 s**
(419,589 schedules, 7,700,987 calling points) and a probe of eight origins on
2026-10-07 gives **2.45 s per origin-day** (0.29-9.32 s; the first origin of a day
carries that day's index build), against 2.4-3.1 s when the figure was first taken,
so the projections are:

| Shards | Wall clock for 26,369 origin-days | Index they hold |
| --- | --- | --- |
| 1 | about 18 hours | 1.87 GB |
| 4 | about 4.5 hours | 7.5 GB |
| 8 | about 2.2 hours | 15.0 GB |

```
# shard i of 4, in four shells, then one verdict over all of them
python -m tools.check_slice_equivalence --timetable feeds/timetable --date 2026-10-07 \
    --days 7 --progress _cache/slice-equivalence.json --shard 1/4
python -m tools.check_slice_equivalence --timetable feeds/timetable --date 2026-10-07 \
    --days 7 --progress _cache/slice-equivalence.json --merge 4
```

The number that fits is a memory question first: the wall clock divides by the
shard count, the index does not, and **4.7 GB** was free on this machine while the
8-shard row wants 15.0 GB. A sharded run prints both counts against that free
memory before it starts, which is the same warning shape `build_workers` prints
before a build.

**The four-shard proof, 9 October 2026 (ADR-0066).** One invocation,
`--shards 4`, carried the request to the end and merged to **26,369 of 26,369
origin-days compared, 3,767 of 3,767 origins complete, 0 differing, exit 0**;
`--merge 4` reproduces that verdict from the four shard checkpoints without
reading the feed. Nothing compared has ever differed, and no origin-day of the
request is left uncompared.

The conditions were not the conditions the projection assumed, so they are part
of the figure. An overnight single process had compared **19,525** origin-days
at **26.5 pairs/min** (2.26 s each, 22:02 8 October to 10:17 9 October) before it
was retired and its checkpoint handed to the shards as the base, so the shards
inherited rather than re-compared. The machine had **4.1 GB** free against the
**9.5 GB** four shards want and was run anyway: free memory sat at **0.1-0.2 GB**
through the sweep, each shard holding its 1.87 GB index against the page file
rather than against RAM. The successful invocation compared the **6,119**
origin-days the base did not hold in **2 h 28 m** (10:23 to 12:51) -- **41
pairs/min, 1.6x the single process, not 4x**: under four-way contention and
paging each shard ran at 5.8 s per origin-day where one process ran at 2.26, so
paging priced the parallelism rather than erasing it. The invocation before it
(10:02 to 10:17, 725 pairs) was stopped for the defect below; those pairs
stayed in the shard checkpoints and count toward the verdict, which is the
no-work-lost half of ADR-0066's item 6 witnessed at scale.

**The launcher's own pipe, measured 9 October 2026.** That first invocation
streamed its children one at a time, and an OS pipe holds about **4 KB** -- a
writer with no reader blocked after three 1 KB writes -- while a shard writes
about 9 KB of progress long before it finishes: every child not yet reached
would block in `write()` and stop comparing, and M parallel shares would have
become their sum. The launcher now drains every child at once, one prefixed
line at a time (`_stream`), and `test_no_child_stalls_on_a_pipe_another_ones_output_is_using`
holds the regression. The 4 KB is why the drain cannot be sequential; the
table above is why the shards must run at all.

## The whole network, measured

The whole-network figures, kept here rather than in `README.md` so that measured
numbers live in one file (F8 of the 8 October 2026 agent-efficiency audit). They
were taken before the per-origin fare index and the timetable slice, so they
describe the cost those two fixes were aimed at.

**Prices only.** `run.py` reads `feeds/fares` and loads no timetable unless
`--with-timetable` is given: **2,712 pages in 23 min 38 s, 1.91 pages/s**, 592 MB
of output, about 30 s of which is loading fares. Free memory moved between 0.1 GB
and 4.5 GB over the run, so `worker_budget` returned 1.

**With journey times.** The build the rest of this document describes:

| Workers | Whole network, fares and timetable |
| --- | --- |
| 1 | 8 h 06 m |
| 2 | ~4 h 15 m |
| 3 | ~2 h 50 m |
| 4 (16 GB GitHub runner) | ~2 h 10 m |

## What is actually wrong

**`--all-origins` gave every page the whole country's timetable.** In
`build_demo_page.main`, the single-origin path computed a `focus_destinations` set
and passed a per-origin `cache_path`; the all-origins path passed
`focus_origin=None` and no cache, so the first page's journey search ran with the
1.87 GB index beside the fares feed and rebuilt the network's per-day index on
every day of the service week. **Fixed 8 October 2026:** a page is now built from
`TimetableDb.focused(origin)`, the slice of the index that page can use, so both
the search and the index it builds are over one origin's reach. The index itself
is still parsed and held by the process, which is the half that remains -- see
"What it does not do" above.

This was a code-level cause and a memory-level one at the same time, and which one
bites depends on the machine. The measured facts above say the search is 2.3x
slower and the index build is 8.2 s a week even nationally, so on a machine with
room to spare the unfocused page is slower but not the 23 minutes reported. On
this machine, which has about 5 GB free, the 1.87 GB is what failed.

**The fix that could not work, and the one that did.** "Give every origin its own
focused index and its own cache" cannot be done by parsing per origin: a focused
parse still costs 50.6 s, so 3,424 of them is two days of CPU, and one pickle per
origin for the whole network is gigabytes of disk. A focus has to be derived in
memory from a single parse, which is what `TimetableDb.focused` does: one 1.66 s
pass builds a TIPLOC-to-schedules index, and each slice after it is cut out in
0.25 s. It pays off where it is used because the process that needs a page already
holds the feed. It does not reduce what that process holds, which is what an
on-disk timetable index would, and that is the work left in `docs/open-work.md`.

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
   build; a preview does not need the headroom. Below the floor a two-station
   build now finishes rather than stopping at no page, but it takes about 21
   minutes instead of five, because the two feeds page their way in -- the
   8 October run above is that case, at 2.1 GB free.
6. **Repeat builds are warmer, not free.** The focused timetable cache takes the
   single-origin build from 2 m 57 s to 2 m 03 s (54 s saved). It does not help
   the unfocused all-origins path, which writes no such cache.
7. **Fixed, 8 October 2026: each page is a slice of the timetable.** The fares
   feed is released before the first page (7 October) and each page is built from
   its own origin's slice of the timetable (8 October). What is left is the
   whole-network build, which has not been re-measured against the workflow's
   `timeout-minutes: 150`, and indexing a whole network, which is 3,767 files of
   a quarter of the feed each and is refused without a byte budget.

   **In plain words:** the build used to load every train in the country and keep
   that in memory while it wrote the page for one town. It now holds only the
   trains that page can reach, because a page never asks about anywhere else.
   Nothing a reader sees changed -- the same destinations with the same times and
   change counts -- and the two-station build went from no page in 24 minutes to
   20 min 53 s for both, on a machine with less memory free than the run that had
   not finished.

   The one-station path (`run.py --origin GRA`) worked this way all along, which
   is why it was fast; the whole-network path now does too.
8. **Fixed, 8 October 2026, and the cheapest thing to do next: write the slices
   down.** `python -m tools.build_timetable_index --timetable feeds/timetable
   --origins GRA,NOT` cuts those slices once and leaves them on disk, and a build
   given `--timetable-index` reads its page's own slice in 4-6 s instead of
   parsing the national index in 56 s and holding 1.87 GB of it. When the index
   holds every page the build writes, the feed is not read at all -- in the parent
   or in a pool worker -- and the two-station build above finished in **3 min
   44 s** that way. The whole network is not indexed: that is 3,767 files, and the
   writer refuses it without a byte budget.

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
- The undated build. The seven-day request itself is complete as of 9 October
  2026 -- **26,369 of 26,369 origin-days, every one agreed** ("The four-shard
  proof" above) -- but the sweep asks the dated service week: `day=None`, the
  undated question, is still unasked, and so are stations the feed itself
  cannot be asked about.
- A whole-network build from an index, and an index for a whole network. The first
  is unmeasured and the second is refused without a byte budget, because it is
  3,767 files of a quarter of the feed each.

## The 12 October 2026 build-cost audit: the per-origin spread, and the bytes

Measured 12 October 2026 on this machine, on the 24 September 2026 DTD
download (419,589 schedules, 7,818,772 fares). The audit's own task list is
settled in `docs/open-work.md` under "The 12 October 2026 build-cost audit";
what landed is in the ADRs it names, and this section holds only the figures.

**The spread, not the mean (T8).** `python -m tools.measure_origin_costs`
times the slice cut, the day index and the reachability search per origin
through the functions the build calls. The audit's three sampled origins
reproduce on this machine (1.43 s, 8.66 s, 41.76 s against its 1.17 s,
7.20 s, 28.48 s for the timetable half alone). A twelve-origin alphabetical
stride sample, same feed, same day:

| Origin | Slice schedules | Cut | Index/day | Search/day | 8-day total |
|---|---|---|---|---|---|
| AAP | 188,368 | 2.75 s | 2.08 s | 10.72 s | 105.17 s |
| BKL | 90,265 | 0.67 s | 0.41 s | 7.18 s | 61.40 s |
| CHD | 172,358 | 0.21 s | 0.78 s | 2.14 s | 23.58 s |
| DOW | 21,088 | 0.24 s | 0.07 s | 0.36 s | 3.65 s |
| GNB | 11,993 | 0.24 s | 0.04 s | 0.01 s | 0.64 s |
| IGD | 811 | 1.69 s | 0.00 s | 0.02 s | 1.85 s |
| LTV | 155,810 | 0.20 s | 0.57 s | 1.50 s | 16.70 s |
| OCM | 0 | 0.28 s | 0.00 s | 0.00 s | 0.28 s |
| RDW | 160,607 | 0.23 s | 0.70 s | 0.45 s | 9.47 s |
| SOS | 0 | 0.27 s | 0.00 s | 0.00 s | 0.27 s |
| WDL | 10,355 | 0.26 s | 0.05 s | 0.42 s | 3.99 s |
| YVP | 113,248 | 0.20 s | 0.46 s | 0.20 s | 5.49 s |

Mean 19.37 s against median 4.74 s, p90 61.40 s, maximum 105.17 s: the tail
dominates, so the mean is 4x the median and the most expensive origin costs
5.4x the mean. Task ordering for the facts pass and the sharding follows the
tail, not the middle. OCM and SOS price fares but call at no timetable
station, so their slice is empty and their pages are fares-only.

**The bytes, measured against the 800 MB budget (T5).** The audit projected
827 MB from a 24-page sample and could not say whether the sample or the
budget was wrong. Both halves are now measured, same feed, same flags as the
release (`--date`, `--notices nre,rdg,ogl,accuracy`):

- Controlled T1 delta, same station, same shape, same feed, prices-only:
  Birmingham New Street 261,362 bytes on 10 October 2026 → **112,885 bytes**
  on 12 October 2026, a saving of 148,477 bytes, which is the 149,377-byte
  script minus the small inline handoff. Per page the saving is exact,
  because the bytes that moved are byte-identical on every page.
- With timetable and service week, current code: 24 major stations average
  **2,734,828 bytes** a page (median 2,493,992, smallest 1,116,077,
  largest 6,831,298); a 10-page alphabetical stride sample averages
  **806,367 bytes** (median 712,627, 72,065 to 2,495,286).
- Where the megabytes live, Birmingham New Street's 1,626,528-byte DATA:
  **1,050,373 railcardRules**, 220,029 destinations, 188,527 single
  destinations, 73,593 anytime destinations, 56,454 pool, 30,756 serviceWeek.
  The 2,372 railcard rules are nearly all two-ticket pair records, and all
  but 18 are referenced by a row: the bulk is combinatorial, not a leak
  (see `docs/open-work.md`, pair-rule encoding).

The 498 MB whole-network figure of 1 October 2026 was a prices-only build
(`--fast-all-origins`), so it never priced the week, the pairs or the
departures the release ships. Against the 800 MB budget the release is held
to, the with-week shape projects to roughly **2.2 GB** (10-page stride mean
× 2,712, with wide error bars at n=10) — over budget, and driven by the
pair-rule encoding rather than by the script T1 removed (2,712 × 149 KB ≈
385 MB saved, the remainder still over). The next real release settles it
with `python -m tools.page_bytes --site _site --budget-mb 800`, which refuses
on its own; until then the projection above is the standing estimate.

**The page write, measured (14 October 2026).** The audit's argument against a
store turned on what a store would remove, and the one figure it carried for
that -- "~20 ms a page, measured as `write_page_atomic`" -- was never
transcribed anywhere, so it is measured here instead. 200 writes of three
payload sizes, through `build_demo_page.write_page_atomic` as the build calls
it:

| Payload | Written | First write | Median | p90 | Share of a page's 10.75 s |
|---|---|---|---|---|---|
| Birmingham New Street as built | 258,021 B | 1.73 ms | **1.51 ms** | 1.97 ms | 0.014% |
| the audit's mean page | 2,734,888 B | 5.05 ms | **5.32 ms** | 6.99 ms | 0.049% |
| the largest page the audit measured | 6,831,358 B | 11.54 ms | **10.90 ms** | 12.01 ms | 0.10% |

The second and third rows write the first row's bytes padded to that size, so
they measure the write and not the content. What limits the figure is the OS
page cache: every write after the first is a cached write, which is the best
case for the write and the worst case for the store's argument. It does not
matter which way that cuts, because the whole write is 0.014% to 0.10% of what
a page costs to compute -- the audit's ~20 ms is 4x the mean page's real
figure, and its conclusion survives the correction: a store removes the write,
and the write was never the cost.

```python
# the three payload sizes, 200 writes each, warm cache (14 October 2026)
from pathlib import Path
import statistics, tempfile, time
import build_demo_page as b
raw = Path("_site/from/birmingham-n-st/index.html").read_bytes().replace(b"\r\n", b"\n").decode()
for target in (len(raw), 2_734_828, 6_831_298):
    out = Path(tempfile.mkdtemp()) / "page.html"
    times = []
    for _ in range(200):
        start = time.perf_counter()
        b.write_page_atomic(out, raw + " " * (target - len(raw)))
        times.append((time.perf_counter() - start) * 1000)
    print(f"{target:,} B median {statistics.median(times):.2f} ms")
```

## The page suite's coverage, measured

Measured 12 October 2026 over the five pages `tools/verify.py --browser` drives:
**830 checks passed of 855, none failed, 25 skipped (2.9%), exit 0** -- demo
station 257/257 (3 skipped), chooser 71/71 (1), privacy 31/31, one-page station
254/254 (5), prices-only 217/217 (16). The skipped checks are the journey and day
checks a build with no timetable cannot run.

The whole-app audit of 10 October 2026 had recorded 69 of 815 skipped (8.5%, over
the suite's own 5% budget) on the previous fixtures. That was a property of the
fixtures rather than of the suite, because the shape feed priced each secondary
origin to a single station and neither fixture build carried a service date.
`tools/verify.py` now builds both fixtures for `SERVICE_DATE` and passes
`--third-origin --return-network`, and the shape route is `one-page`, because what
fits on one page is a list rather than a row.

Measured again 15 October 2026, after the clarity pass changed the copy the
checks read and added a heading-name check to each route: **841 checks passed of
841, none failed, 26 skipped (3.1%), exit 0** -- demo station 260/260 (3
skipped), chooser 74/74 (1), privacy 31/31, one-page station 256/256 (6),
prices-only 220/220 (16). The checks the pass added are the heading's own name --
one on the chooser, one on every station page -- and the four it renamed (the
chip rule, the pager, the shortlist announcement and the no-service row) ran
under their new names.

Measured 19 October 2026, after the thematic facets moved behind the chip row's
disclosure, the tab order through that fold became a check of its own, and the
demo feed gained `--long-list`: **937 checks passed of 937, none failed, 26
skipped (2.8%), exit 0** -- demo station 291/291 (3 skipped), chooser 77/77
(1), privacy 33/33, one-page station 285/285 (6), prices-only 251/251 (16).
Three things moved the count. The tab order is walked on every station page: the
disclosure is a stop with the facets folded, a folded chip is not, and pressing
it is what puts the first chip next. A page whose script does not arrive is now
asked the same question on every route that fetches one, because a fold the
script owns must arrive closed and out of the tab order, which is what "no worse
off without the script" means measured rather than argued. And the paging checks
are no longer skipped: `--long-list` prices Grantham to twenty-two destinations,
so the pager has a second page and `n`/`p` are read turning it, which needed the
block to raise the budget to every row first -- the opening budget is this
mode's cheapest price, so it left even a two-page list one page long. The one
check removed is the not-exercised stand-in for a page whose list fits one page:
the branch that reads "one page" now has no fixture behind it, and what it would
have said is the check above it, that the unpromised key leaves the list where
it is.

The fixture's own cost is 14 records: `--long-list` is off by default, because
every parser test counts records in the base feed, and only the demo feed the
browser suite drives passes it (`tools/verify.py` and the deploy workflow's
browser job).

## The verify suite's own runtime, measured

The figures in `AGENTS.md` and `README.md` said `--fast` was "about three
minutes" and `--full` "about fifteen". Both were wrong by a wide margin, and a
figure nobody dated is how they stayed wrong: the three-minute claim was written
when the suite was a third of its size and nothing measured the command again.

Measured 14 October 2026, twice, on this machine by the whole-app audit:
**780 seconds** for the `--fast` suite on an otherwise idle machine and **1,017
seconds** while a second suite ran alongside, for the same 1,120 tests in one
process. That is thirteen minutes idle and seventeen under load, and the load was
worth naming: the difference is the whole margin, so a figure quoted without it is
half a figure.

Measured again 15 October 2026, dated here rather than in a document that
promises it, because item 9 of that audit is the correction:

| Command | Wall clock | Load |
|---|---|---|
| `python -m tools.verify --fast` (1,137 tests) | **1,275 s** (21 min 15 s) | this machine, one suite at a time |
| `python -m tools.verify --full` (1,139 tests, the type check and the JavaScript parse) | **2,118 s** (35 min 18 s) | the same |

The `--full` figure breaks down as 2,116.1 s for the unit tests, 12.3 s for the
JavaScript parse and 9.8 s for the type check. So this machine is slower than the
machine the audit measured on -- 1,275 s against its 780 s for the same suite two
days earlier -- and neither figure is a property of the tests. The `--fast` run
above was taken while it was still red, reporting 11 failures that the same pass
fixed;failing tests do not shorten a run, so the figure stands, and the later green run
of the same command is what a reader should time their own against. That run was
measured on 15 October 2026 as well: **`--fast`, 1,140 tests in 1,624 s** (27 min
4 s) on this machine, one suite at a time. Its three extra tests are the ones the
same pass added, so the two rows above carry the earlier revision's count while
these are the figures that describe the green tree.

The suite is I/O- and CPU-bound in turn -- the feed-scale tests parse both
licensed feeds and the page tests write pages -- so these are wall-clock figures
for one machine and not a benchmark of the tests. What they are good for is the
question a reader actually has: whether to run the whole thing or one module.
Run one module.

### The fast loop is the page's own modules, 21 October 2026

**What changed.** `--fast` ran every test in the tree except two, so it cost 21
minutes and nobody used it while writing a page change (A5 of the 20 October 2026
poteto audit). It now runs `FAST_MODULES` in `tools/verify.py`: the page, the
payload it is built from, the chooser, and the checks that hold the build's own
documents and this suite's shape -- 228 tests. `--full` still runs every module,
including the feed-scale ones that parse the licensed downloads.

**Measured 21 October 2026**, `python -m tools.verify --fast` on this machine,
twice: **42.3 s** and **53.2 s** for the 228 unit tests, plus 2 s for the
JavaScript parse -- **about a minute** for the command, against the five-minute
ceiling the command now holds itself to (`FAST_CEILING`). The spread is the
machine, not the suite: the same 228 tests both times. The figure is the green
tree's own, not a run with failures in it.

**Where it is held.** The ceiling is a check rather than a sentence: a fast run
whose unit step passes `FAST_CEILING` fails naming the seconds and the two ways
out. `tools/test_verify.py` holds that every module the list names still holds
tests and that the feed-scale modules are not in it, so a rename cannot turn the
loop into one that passes by running less.

**What it does not establish.** A module left out of the list can break without
the fast loop noticing. That is the trade the audit asked for -- the release
still runs `--full` before publishing -- and the ceiling is what makes the trade
visible rather than silent.

**Measured again 24 October 2026, because the paragraph above came true.**
`tools/test_check_known_fares` was one of the modules left out, and it went red
when ADR-0076 stopped listing a place no journey reaches: four of its rows
priced Sleaford's fare, which the fixture's page now drops. Nothing ran it until
the release's own assemble job did, two days later. It is on the list now, and
`python -m tools.verify --fast` on this machine took **52.7 s** for the 293 unit
tests and 54.8 s for the command; 3 s of that is the fare gate's own synthetic
site, which is the whole price of noticing next time.

**Measured 24 and 25 October 2026, at 300 tests**, because the gate now answers
one more question. What a page leaves out decides what a row's absence means, so
the module builds its site three ways -- with the timetable, with the place cap
at two, and fares only -- and it costs **25-32 s** where the one build cost 3 s.
Seventeen of those seconds are the three builds of one three-origin fixture, one
per rule the gate has to tell apart; the rest is the module's own tests reading
the pages it just built.

**The ceiling still fits, and the margin is thinner than the figure implied.**
Before the gate grew, four runs of the same 300 tests took **72.6 s, 80.2 s and
93.9 s** for the unit step on 24 October, with **201 s** while four site builds
held the CPU. After it, four runs took **137 s, 158 s, 180 s and 182 s** on
25 October. The gate's three builds and seven extra tests are about 25 s of that
difference; subtracting them, the same work still took **1.5-1.7x** as long,
which is this desktop rather than the suite. So the figure to plan against is
the slowest run, and against the five minutes the audit asked for it leaves
about 120 s -- one more fixture-building module and no more. CI's own rate from
the 25 October release run (1,376 tests in 731 s) puts the same 300 tests near
160 s there, the same margin against a slower machine.

The decision is to keep `FAST_CEILING` at 300 s. The audit asked for five
minutes, `tools/test_verify.py` holds the number there, and a run that trips it
with no module added says the machine is slower than the figure was taken on,
which is a reason to measure again rather than to raise it.

## The type-check census, measured

Measured 15 October 2026 with mypy 2.4.0, on this machine, `--no-incremental`, one
process. The command is the census `tools/check_types.py --all` prints:

| Command | Result | Wall clock |
|---|---|---|
| `python -m mypy --no-incremental` over every root module and tool | **350 errors in 29 of the 70 files** | **7 seconds** |
| the same, `--strict`, over the build's own ten modules | **132 errors in those ten** (287 in the 17 files the check pulled in) | **4 seconds** |

The cost of the check that landed is the second row's shape over the 27 files
their own errors are zero in: **7 seconds**, which is why it runs with `--full`
and not with `--fast`. `atoc_fares_loader.py` alone is **108** of the 350 -- the
`FaresLoader` mixin sets attributes its subclass reads -- and `feed_audit.py`
(42) and `sanity_report.py` (23) are the next two. Nothing smaller than those
three is worth a pass of its own, which is what ADR-0072's ratchet is for.

## The page-byte split, measured after the marker was repaired

Measured 18 October 2026 on this machine, over the demo and shape builds already
on disk, with the command CI runs.

```
python -m tools.page_bytes --site _demo_site
python -m tools.page_bytes _demo_site/index.html _demo_site/from/grantham/index.html
```

| Page | Total | CSS | Script | Payload | Rows |
|---|---|---|---|---|---|
| the chooser | 28 KB | 22 KB | 3 KB | 0 KB | 3 |
| `/from/grantham/` | 38 KB | 0 KB | 3 KB | **19 KB** | 16 |
| `/from/lincoln/` | 35 KB | 0 KB | 3 KB | **15 KB** | 11 |

The payload is **48%** of the Grantham page's 39,757 bytes. Its CSS reads 0 KB
because the station route's stylesheet is a separate hashed asset, and this tool
measures a stylesheet only where the page inlines one. The demo site totals 0 MB
of the 800 MB budget over its 5 pages.

Before this date the same command reported **0 KB payload and 0 rows on every
page**, and exited 0. The tool searched for `const DATA = ` while the renderer
wrote `window.TBE_DATA = `, and a marker it could not find was indistinguishable
from a page that ships nothing. `python -m tools.page_bytes --site <an empty
folder>` also exited 0, printing `over 0 page(s)`, and that is the invocation
`deploy.yml` runs. Both are failures now.

These are the first figures this tool has produced that describe a page, and they
describe a demo page. The Grantham page here holds 16 destinations where the
real-feed page holds 335, so this is not that page's figure; the real-feed page
was measured on 21 October 2026, further down this file, at 397 KB.

## The shared station list, deferred: the plan

**Written:** 18 October 2026, before the runs below. The figures are in the
section after this one, dated the same day.

**Question.** Every station page carries `<script src="/stations.js" defer>` for
the picker's station list, and `defer` on that tag is new: it was a classic tag,
which is a parse barrier, until E2 of the 17 October 2026 audit. On a page that
already holds its own answer in inline script, what does the attribute buy a
reader's first paint?

**The change under test is one attribute.** Two copies of the same built page,
`_demo_site/from/nottingham/index.html`, differing only in whether the station
list's tag carries `defer`. The route's own script is deferred in both, so the
only difference is when the shared list stops blocking the parser.

**Why the size of the list decides the answer.** The demo build's own list is
459 bytes for its 3 stations, and 459 bytes that never arrive can delay nothing
measurably. A release writes the list for every station it wrote a page for --
the writer's own docstring names 2,712 -- so the list is served at two sizes: the
demo build's 459 bytes, and **162 KB**, the size of the file the same writer
(`build_assets.render_station_asset` over `station_asset_rows`) produces for the
2,613 stations in `feeds/knowledgebase/stations.xml`. The second is the size a
release's reader downloads; the first is the control that says the method can
see a difference at all.

| Served list | Bytes | Stations |
|---|---|---|
| the demo build's own | 459 | 3 |
| the reference station file's | 165,934 | 2,613 |

**What is measured, and why those three.** First Contentful Paint: it is the
thing a parse barrier moves, and nothing paints while the parser waits. Time to
the first results row on screen: the answer the page exists to give, measured by
a `requestAnimationFrame` loop installed before any page script runs, so it is
the row's own paint and not a load event. And DOMContentLoaded, as the check that
the barrier is what the tag claims it is rather than a measurement artefact.

**How.** Chromium through Playwright, one fresh browser context per run so no run
sees a cached list, alternating A and B within each repetition to cancel a drift
in the machine, network throttled through CDP to 150 ms latency, 1.6 Mbps down
and 750 Kbps up (a slow phone), no CPU throttle. 7 runs per variant, reported as
median with min and max, at each of the two list sizes, plus one unthrottled pass
as a control on the throttle itself. The page is served from the project's own
shape: a static server over loopback.

**What would make this untrustworthy, and is stated with the figure.** Loopback
has no TLS handshake and no network jitter, so the RTT component is 150 ms and
nothing else. The page under test is the synthetic demo build, whose banner the
real page does not carry and whose payload is 16 rows against Grantham's 334. The
figure is about a *release-sized station list on a throttled connection*, and it
is not the figure for a fast connection or for a smaller release. Nothing here
measures whether the picker still works after the deferral; the browser suite's
picker checks are what hold that (`tests/browser/station-picker.cjs`), and the
list must still arrive before the reader opens the control rather than before
first paint.

## The deferred station list, measured: it buys a serialization no reader sees

Measured 18 October 2026 on this machine, by `node measure_station_defer.cjs`,
following the plan above. 7 runs per variant per size, alternating within each
repetition, each in a fresh browser context so no run sees a cached list. All
figures are milliseconds from navigation start. The row below is one sweep; how
the three numbers behaved across four sweeps is stated underneath it, because one
sweep cannot tell a difference from a drift.

| Release-sized list, 150 ms / 1.6 Mbps | Payload script ran at | FCP | First row | DCL |
|---|---|---|---|---|
| a classic tag | 2,212 | 1,112 [1,028–1,208] | 2,337 [2,313–2,411] | 2,300 |
| `defer` | 1,016 | 1,032 [1,012–1,116] | 2,334 [2,298–2,361] | 2,290 |

**The barrier is real, and it is 1.2 s wide.** The list's tag sits in the body
before the inline payload, so a classic tag stops the parser until the list has
arrived: 166 KB over a 1.6 Mbps link, which ends at 2,199 ms and takes the
payload's own script with it. Deferred, the payload runs at **1,016 ms**, as soon
as the parser reaches it. Across the four sweeps run here the payload was
**1,161, 1,187, 1,196 and 1,161 ms** earlier behind a deferred tag. That is the
one figure the attribute moves, and it moved every time.

**Nothing a reader sees moved.** Across the same four sweeps the FCP difference
(block minus defer) was −40, +80, −8 and −40 ms, with the two spreads overlapping
in every sweep; the first results row differed by −40, +3, −4 and 0 ms. At this
run count neither direction is measurable, and that is the finding rather than a
failure of the harness: the row is built by the route's own script, which is
174 KB, arrives at 2,278 ms and 2,267 ms and runs the moment it lands. The 166 KB
list is already there by then whichever way its tag was written, so a barrier that
ends at 2,212 ms ends before the byte that matters.

The two controls agree. With the demo build's own 459-byte list the payload runs
at 824 ms against 813 ms and the first row at 1,547 ms against 1,547 ms. With the
release-sized list and no throttling (3 runs), FCP 68 against 64 and the first row
98 against 95. The list's delivery is independent of the attribute in both: all
2,613 stations arrive and the picker shows its 40 options in every run of every
variant, which is the one thing the deferral must not break.

**What this costs the comment that made the claim.** `build_assets.station_asset_tag`
said deferring stops "first paint of the table" waiting on the network's station
list. On the page shape measured it does not, and the docstring now says what was
measured instead: a serialization of the payload's execution, 1.2 s at a
release-sized list, which the route's own script hides from the reader. The
attribute stays -- it costs nothing and it is the difference whenever a page's own
script is not the last byte on the wire -- but it is not the paint win it was
described as, and no figure should be quoted as one.

**The cost that did not move, and is larger than the win.** Every station page
still downloads the whole list: **165,934 bytes** at a release-sized release, for
a control most readers never open, beside a 33 KB payload and a 174 KB route
script. Deferring changes when those bytes are *used*, not whether they are
fetched. Whether the picker should fetch the list when it opens instead is a
separate question, and this is the number that one starts from.

**Reproduce.** The demo build from the plan above, then
`node measure_station_defer.cjs` in the repository root. It writes the
release-sized list itself, through `build_assets.render_station_asset` over
`feeds/knowledgebase/stations.xml`, and refuses rather than guessing if the built
page no longer carries the tag it rewrites.

## The shard merge's feed load: the plan

**Written 18 October 2026, before the figure below was taken.** Finding E6 of the
17 October 2026 audit: `build_pool.merge_shards` loaded the whole fares feed and
used one field of it, `locations_by_crs`, to check that the shards partition the
feed. `FaresDb.load_feed(..., locations_only=True)` now reads the `.loc` file and
nothing else. The question this measures is what the merge stops paying for.

**Method.** One fresh process per load, because a heap warmed by a full parse
would pay for the next one. Each process is timed from just before
`FaresDb()` to just after `load_feed` returns, on the real feed
(`feeds/fares/dtd-fares.zip`, the 24 September 2026 download), three runs each,
on this machine. Correctness is measured first: the two loads' location maps are
compared by CRS to `(nlc, name, group_nlc)`, because a cheaper reader that
disagreed would refuse a correct split and no timing would show it.

**What it does not cover.** The merge command end to end, which also copies the
shards' pages, writes the chooser, the station list and the manifest, and crawls
the result. Nor the timetable. The figure below is the feed load only.

## The locations-only load, measured: the merge stops parsing the feed

**Measured 18 October 2026 on this machine, three runs each, one process per
load**, by the method in the plan above. Real feed: `feeds/fares/dtd-fares.zip`,
the 24 September 2026 download, 48,525,887 bytes.

| Measurement | Full load | Locations only |
| --- | --- | --- |
| Best of three, `FaresDb().load_feed` | **37.7 s** (42.7, 37.7, 39.4) | **0.3 s** (0.3, 0.3, 0.4) |
| Stations kept | 3,436 | 3,436, same map |

The two maps are equal as values, CRS by CRS to `(nlc, name, group_nlc)`, which
is the part that matters: the merge refuses a shard set that does not partition
this list, so a cheaper reader that saw a different list would refuse a correct
split and no timing would show it. **The merge stops paying 37.4 s of its feed
load, about 125x, and reads about 37 s less of the file's records.**

**What this does not say.** It is the feed load, not the merge. A merge also
copies the shards' pages, writes the chooser, the station list and the manifest,
and crawls the result, and none of that is in this figure. It is also one
machine on one download: the ratio is a property of how much of the archive is
not the location file, and the seconds are not a promise for other hardware.

**Reproduce.** `python -m tools.measure_locations_load`, or with
`--runs` and `--feed` to name another download. It spawns one process per load
and refuses when the two maps disagree rather than printing a ratio over them.

## The release link crawl: the plan

**Written 18 October 2026, before the figure below was taken.** The prune stopped
reading the pages it wrote (E5), so `build_release.crawl_internal_links` is now
the one place a build reads the whole release again: every page and every shared
asset, to prove each internal link names a written file. The question is what
that read costs, and whether the same check has a cheaper shape.

**Method.** A corpus shaped like the release, measured directly rather than
extrapolated: one real station page, copied to 2,712 routes (the priced stations
the 12 October 2026 audit counts) and padded to 354 KB (the page size that same
audit measured), with the padding a payload of thousands of station links so the
scan meets the match count a release page's destination rows carry. Three crawls
run interleaved over the same corpus, five times each, best of the five reported:
the crawl as it shipped until 18 October 2026 (the tree walked twice), the same
with the tree walked once, and the same scanning bytes with no decode. Every
variant must report the same broken links, or it is a different check rather than
a faster one. The cost is then broken into its parts
on the same corpus: walking the tree, reading and decoding, scanning, resolving.

**What it does not cover.** A real release: the corpus's pages are one page
repeated, so its link graph is far simpler than a release's even though its byte
count and match count are not. The machine's disk is 98% full and its page cache
holds what it can, and the build runs in CI on other hardware, so the seconds are
this machine's and the shares are the portable part. It also does not cover the
build end to end; the crawl's share of that is the build's own measured hours.

## The release link crawl, measured: six seconds, and the cheaper shape that is not worth it

**Measured 18 October 2026 on this machine**, five runs each, interleaved, best of
the five reported with the range. Corpus: 2,712 pages of 362,523 bytes, 2,719
files, 0.98 GB, built by the method in the plan above. Five internal links a page,
which is what a real station page carries: the payload is column-encoded and the
route's script builds the destination links, so 32 KB of real page holds five.

| Crawl | Best of five | Range |
| --- | --- | --- |
| Two walks of the tree, decode each page | **6.95 s** | 6.95-11.56 |
| One walk, decode each page (shipped from 18 October 2026) | **6.46 s** | 6.46-13.51 |
| Two walks, scan bytes, no decode | **2.66 s** | 2.66-5.56 |

Every variant reported the same two broken links on the same corpus, checked
before the timing: the cheaper shape is the same check or it is not a saving.

**What the 6.46 s is made of**, each measured on the same corpus: walking the tree
once **0.44 s** (0.83 s twice), reading and decoding 2,719 files **3.07 s**,
scanning them for links **2.75 s**, resolving the 13,573 links against 2,719
written files **0.00 s**. The scan and the decode are the cost; there is nothing
to make cheaper about the resolution, because a station page has five links and
not five thousand.

**What bounds it.** Single-core work over 0.98 GB, read from the page cache at
about 150-370 MB/s. The five runs spread by up to 2x in this machine's noise
(which is why the best is quoted beside the range), so a difference under about
half a second is not measurable here.

**Verdict. The same check can be done in 2.66 s rather than 6.46 s**, by scanning
the page's bytes and never decoding them. It is not worth taking. The crawl runs
once per build, and the release build is measured in hours (the workflow's own
150-minute timeout); 3.8 s is under 0.1% of it, and the second parser would be a
second set of regexes to keep in step with the first, on the code path whose job
is to catch a link the renderer got wrong. The walk was taken because it also
removes a second snapshot of the same tree: one walk, one list of files, one
answer. Nothing else here earns its place.

**Reproduce.** `python -m tools.measure_link_crawl`. It writes the release-shaped
corpus, checks that every variant reports the same broken links, then times them
interleaved. `--runs` and `--pages` change the sample; the default is five runs at
the release's 2,712 pages.

## The budget's re-render while dragging, 19 October 2026

**Plan, written before the figure.** A budget change is the page's hot path: a
range input can fire several `input` events between two paints. Measure the
synchronous cost of one `render()` followed by a forced layout read, on the demo
page at a budget that reaches its rows, with the payload grown to 101
destinations -- one page of 20 rows, because the table paginates at `PAGE_SIZE`
rather than painting every destination. State the row count with the figure,
because the list's length and the painted rows are two different numbers. The
budget is 50ms (OV8 of the 19 October 2026 overdrive pass).

**Figure.** `_demo_site/from/grantham`, Chromium 1366x768, this machine,
19 October 2026: **7.4 ms**, twice over, with 101 destinations in the payload and
20 rows painted. The same page's 17-destination render measured 6.3-14.3ms in the
19 October audit's probe, which timed an input event to a forced layout rather
than `render()` alone; that figure is not re-measured here.

**Method.** The payload's own destinations were cloned to 101 with distinct CRSs,
`render()` was called, and `document.getElementById("summary").getBoundingClientRect()`
was read to force layout, all inside one `page.evaluate`. The clones reuse each
row's journey facts, so the figure costs the DOM and the sort, not a second
timetable lookup; `render()` reads no timetable.

**Where it is held.** `tests/browser/station-layout.cjs` measures the same
statements on every station page the suite drives and fails above 50ms, naming
the figure and the row count. `python -m tools.verify --browser` is the command.

**What it does not establish.** The licensed Grantham page's own figure: the
gate will take it the first time the release suite runs, and the 101-destination
probe above is the demo's rows repeated, not the real feed's. It also does not
time the paint itself, only the statements plus the layout they force, so a
compositor cost on a slow device is outside it.

## The shard build against its 150-minute bound, 20 October 2026

**What happened.** Every share of the six-shard release build ran into the
shard step's `timeout-minutes: 150` and published no page, in the run of
20 October 2026. The only earlier figure is run 38353105980 (13 October 2026):
six shares of about 450 pages at 114, 111, 106, 87, 95 and 103 minutes, with the
bound set 36 minutes above the slowest of them. That headroom is spent.

**What the failure is and is not.** It is a bound, not a measurement: the run
says every share passed 150 minutes and not by how much, so nothing here knows
whether a share was 151 minutes or 300. No per-share figure is quoted, and none
should be read into the change below.

**What changed, and the arithmetic behind it.** Six shares became twelve of
about 226 pages each, in `.github/workflows/deploy.yml`, with the bound left
where it is. A share's cost has two parts and only one of them shrinks with the
share: the pages, which scale, and the whole fares feed plus the whole national
timetable every share loads for itself, which does not. Halving the pages
therefore halves the larger part and leaves the fixed part paid twice over --
minutes, against the hours the pages take.

**The bound, as a table a check reads.** The release's three numbers are stated
here, and `tests/test_workflows.py` fails naming the value the workflow (or
`tools/release/share.py`, for the nearing minute) holds and this table's when
they disagree. The document stays the record; the check makes it a
rule (A8 of the same audit), because a bound drifting away from its measurement
is exactly what the 20 October failure cost.

| What the workflow states | Value |
|---|---|
| the shard step's timeout-minutes | 150 |
| the minute a share counts as nearing its bound | 100 |
| the shard matrix's shares | 12 |

**What is ruled out by measurement.** The release's timetable became Network
Rail's whole CIF on 16 October 2026 (ADR-0073), so the obvious suspect was that
the CIF is a much bigger index than the DTD feed the earlier figures were taken
on. It is not: the CIF in `feeds/timetable-nwr` (99,816,417 bytes) holds
**488,796 passenger schedules and 7,373,060 calling points** after the loader's
own filter, against the DTD feed's **419,589 schedules and 7,700,987 calling
points** -- 17% more schedules and 4% fewer calling points. That is not a
doubling of what a worker holds, so the switch is not the 150-minute story on
its own.

**What this does not establish.** Which part of a share the extra minutes went
to. Twelve shares is the workflow's own rule for a share that nears its bound
(the rule its comment states), not a diagnosis of a regression: a code change
between 13 and 20 October that costs per page would show up exactly this way,
and the figure that would separate "more work per page" from "the same work,
slower hardware" is a per-share timing from a successful run. The first
twelve-share run is that measurement, and it belongs in this section.

**Reproduce the CIF count** (no build, no credentials; the file is the release's
own download):

```python
import gzip
import atoc_timetable as t

def field(line, layout, name):
    pos = 0
    for key, width in layout:
        if key == name:
            return line[pos:pos + width]
        pos += width

kept = calls = 0
with gzip.open("feeds/timetable-nwr/nwr-schedule.CIF.gz", "rt", encoding="latin-1", newline="") as feed:
    keep = False
    for line in feed:
        if line[:2] == "BS":
            keep = t.is_passenger_service(
                field(line, t.CIF_SCHEDULE, "status").strip().upper(),
                field(line, t.CIF_SCHEDULE, "category"),
            )
            kept += keep
        elif line[:2] in ("LO", "LI") and keep:
            calls += 1
print(kept, calls)
```

## A real-feed station page's bytes, 21 October 2026

**Why this was taken.** O2, closed the same day, held a **354 KB** figure from
14 October 2026, and no page had been re-measured since the route's CSS and
script became hashed shared assets, while the release itself moved to Network
Rail's CIF (ADR-0073). O1 needs the same page to reason about the site's bytes.
This is one page's full split, with three more origins measured beside it below.

**Command.** Built on this machine on 21 October 2026 from the feeds downloaded
on 24 September 2026, service date 2026-10-05.

```
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable \
    --origin GRA --date 2026-10-05 --notices nre,rdg,ogl,accuracy \
    --out _real_site/index.html --workers 1
python -m tools.page_bytes _real_site/from/grantham/index.html
```

**Figure.** `tools/page_bytes` reports **397 KB total, 0 KB CSS, 3 KB script,
362 KB payload, 800 rows**. The CSS reads 0 KB because the station route's
stylesheet is a separate hashed file, which that tool measures only where a page
inlines one. Measured again with gzip at level 9, which is what GitHub Pages
sends:

| Part | Raw | Gzip |
| --- | --- | --- |
| the page's HTML, payload included | **406,943 B (397 KB)** | **57,637 B (56 KB)** |
| the route's stylesheet, one copy for every station page | 68,383 B (67 KB) | 21,251 B (21 KB) |
| the route's script, one copy for every station page | 200,934 B (196 KB) | 61,226 B (60 KB) |
| the payload inside the HTML | 371,643 B (363 KB) | 45,524 B (44 KB) |
| the payload's `places` list, shared by every ticket mode | 146,401 B (143 KB) | 14,566 B (14 KB) |

The payload holds **800 fare rows**: 328 returns, 335 singles and 137 anytime
returns, plus one `places` row for each of 335 destinations. A reader's cold
visit to this page therefore transfers **about 660 KB raw, 137 KB gzip**, and a
visit to any second station page re-uses the two hashed assets and transfers the
HTML alone.

**Which timetable these pages carry.** They were built from the DTD timetable on
this machine (`feeds/timetable`, downloaded 24 September 2026), not from the NWR
CIF the release reads. An attempt to build one from
`feeds/timetable-nwr/nwr-schedule.CIF.gz` was killed while loading on this
machine, before it wrote a page. The two feeds are close but not the same: the
CIF carries **488,796 passenger schedules** against the DTD feed's **419,589**,
17% more, and 4% fewer calling points (the counts are in "The shard build
against its 150-minute bound" above). So this is the best local bracket, not the
release's own feed, and the figure O1 waits for is still the assembled site's.

**Three more origins, same command, same day.** The same build was run for
Nottingham, Linlithgow and Ashwell & Morden (the command above with `--origin
NOT`, `LIN` and `AWM`, each `--out` naming its own folder), and all four pages
measured with the same tool and the same gzip:

| Origin | HTML raw | HTML gzip | Payload | Fare rows |
| --- | --- | --- | --- | --- |
| Grantham | 397 KB | 56 KB | 362 KB | 800 |
| Nottingham | 449 KB | 63 KB | 414 KB | 949 |
| Linlithgow | 283 KB | 41 KB | 249 KB | 942 |
| Ashwell & Morden | 345 KB | 51 KB | 311 KB | 790 |

**What it does not settle, and what it now suggests.** The site's total, which O1
is about. Four pages are not the network, but they are a worse bracket than the
one O1 was written on. The shard-1 average of **198 KB a page** behind the 536 MB
projection was measured on 12 October 2026, before times returned to the page on
16 October 2026; these four pages carry times, and they average **369 KB**, from
283 to 449. At that average 2,707 pages are **975 MB against the 800 MB budget**,
and the budget would hold only if the network's average page is under **302 KB**.
Ashwell & Morden is a small station and is still 345 KB, so the small end of the
network is not small enough for the average to be waved away. A 4-origin spread build
(`build_stations.py GRA NOT LIN EDB`) was also attempted on this machine and was
killed while building its pages, after the log had warned that **5.8 GB was free
against the 6.4 GB the two feeds want**; it wrote its shared assets and no page.
The figure that settles this is the assemble job's own `python -m
tools.page_bytes --site _site`, and it may refuse the release rather than
describe it.

## A station page's first paint on a slow phone, 21 October 2026

**Why this was taken.** The same O2 asked for a first paint on a throttled
connection before anyone decided whether the payload is the thing to split.

**Method.** `node tools/measure_station_paint.cjs _real_site`, which serves the
built page gzipped the way GitHub Pages does, in a 390x844 mobile context, and
loads it five times with Lighthouse's mobile profile: **1.6 Mbps down, 750 kbps
up, 150 ms RTT and a 4x CPU slowdown**. The unthrottled control is three runs of
the same page. The first row is recorded by polling for a row with a height, not
by a load event.

**Figure.** Three runs of the same command on the same afternoon, each the median
of five loads: **FCP 864, 748 and 724 ms**, first row **1,374, 1,253 and
1,249 ms**. The honest shape of the figure is therefore **720 to 865 ms to first
paint and 1.25 to 1.37 s to a fare on screen**, and the spread is the machine's
own load rather than a property of the page. The unthrottled control is 88 to
116 ms and a first row at 123 to 161 ms, which is how much of the figure is the
connection rather than the page.

**The split, costed with measured bytes.** The payload's three fare lists are
62,631 B (7,506 B gzip) of returns, 64,444 B (7,916 B) of singles and 22,826 B
(3,209 B) of anytime returns; the 146,401 B of places is shared by all three and
cannot move with a mode. Dropping the single and anytime lists from the first
response saves **10,415 B gzip, 52 ms at 1.6 Mbps**. Fetching either list needs
**at least one round trip, 150 ms**, and the page's default view -- the cheapest
fare of any ticket type -- is composed from all three lists, so the first paint
would need all three either way. The split is therefore **about 100 ms slower to
the first fare than the page it replaces**, before counting a fourth
precomputed list if the default view is to avoid the waterfall. That is what
decided O2: the payload is the page's own data, and the ticket-mode split is not
worth building.

## The two pinned surfaces at the last row, 21 October 2026

**Plan.** O4 asked how much of the screen the budget rail and the shortlist dock
take when both are pinned, and whether the dock's own Copy can be reached
without covering the row above it. Measured rather than reasoned, because the
dock's height is whatever its rows need and the rail's offset moved on
20 October 2026.

**Method.** `node tools/measure_station_phone.cjs _real_site`, at 390x844 on the
real page, two and then four places held, with the page scrolled until the last
row sits just clear of the dock -- the state in which both strips matter. The
rail is shown by an IntersectionObserver, so the run waits for it rather than
reading `hidden` on the next statement; the first version of this tool did the
latter and reported a rail that was already up as hidden.

**Figure.**

| Places held | Rail bottom | Dock top, height | Between them | Rows fully visible | Last row | Copy |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | 56 px | 703 px, 141 px tall | **647 px** | **4** | 592-703 px, clears the dock | 712 px, 44 px tall, topmost at its centre |
| 4 | 56 px | 627 px, 217 px tall | **571 px** | **4** | 516-627 px, clears the dock | 636 px, 44 px tall, topmost at its centre |

**What it means.** Both strips can be pinned at once without hiding a row or a
control: the last row ends exactly where the dock begins, the page's own body
padding is what buys that, and the dock's Copy sits inside the 844 px viewport
with 44 px of target. The cost is the middle of the screen -- 647 px, four rows
-- and it is a cost a reader pays only while they have places held and are deep
in the list. Whether four rows is enough to compare against is the product
decision O4 still holds.

## The budget re-render on a phone's CPU, 21 October 2026

**Plan.** O8 asked for the drag's cost with the CPU a phone's, against the 7.4 ms
desktop figure and the 50 ms gate `tests/browser/station-layout.cjs` holds.

**Method.** `node tools/measure_station_phone.cjs _real_site`, at 390x844, the
same probe the gate uses: `render()` followed by a forced layout read, seven
times per run, on the page's own list and on the audit's 101-destination probe.
The CPU is slowed through CDP at 4x and 6x; **neither is a handset**, and ADR-0032
wants that said beside the figure.

**Figure.** Three full runs of the tool on the same afternoon, each the median of
seven:

| CPU | The page's own 328 destinations | The 101-destination probe |
| --- | --- | --- |
| no throttle | 8.3 to 9.6 ms | 6.6 to 9.6 ms |
| 4x slowdown | **46.4, 79.0, 56.6 ms** | 44.0, 85.9, 52.1 ms |
| 6x slowdown | **84.3, 142.0, 93.9 ms** | 96.9, 128.7, 85.0 ms |

**What it means.** The phone figure straddles the gate rather than sitting on
one side of it: at 4x the same probe is sometimes inside 50 ms and usually over,
and at 6x it is over by a wide margin. The run-to-run spread is the machine's own
load, not a property of the page, which is why the three figures are all here
rather than the middle one. The first fix O8 named -- one render per frame
instead of one per input event -- is already shipped (`queueBudgetFrame`,
19 October 2026), so what is left is the cost of that one render. A decision is
owed on whether the 50 ms gate is a phone gate or a desktop one; O8 now holds
that decision and this figure.

## The release had lost its service day, 21 October 2026

**Plan.** The twelve-share release run of 21 October timed out with none of its
shares finished. Two candidate causes were in the log and neither had been timed:
the OGL timetable's size, and the release building with no `--date`. This measures
both, on the real feed, and the second one is the answer.

**Method.** The run's own log, whose lines carry a timestamp per line: share 3 of
run 39618401726 (`shard (3)`, 14:44:49 to 17:15:24 on 21 October 2026), against
a share of the six on 13 October (run 38353105980, job 115152941550).
The per-page figures come
from `python build_demo_page.py`'s own `build_payload` on the real feeds at this
checkout, once with `day=date(2026, 10, 21)` and once with `day=None`, on the same
loaded databases and the same fare slices, so the only difference is the day.

**Figure.** The two release shapes, page for page and share for share:

| Shape | One Linlithgow page | One Nottingham page | A share's pages |
| --- | --- | --- | --- |
| Dated (`--date 2026-10-21`) | **2.4 s** | **49.1 s** | 458 pages in **108.3 min** (13 Oct, 6 shares, median gap 9.2 s) |
| Undated (no `--date`) | **16.7 s** | **not finished in ten minutes** (stopped there) | 78 pages in **139 min** (21 Oct, 12 shares, median gap 58.4 s) |

```python
# the two shapes, on one loaded database and one fare slice
from datetime import date

import build_demo_page as b
from atoc_timetable import TimetableDb
fares = b.load_page_fares("feeds/fares", "LIN").fares
timetable = TimetableDb().load_feed("feeds/timetable-nwr")
for day in (date(2026, 10, 21), None):
    b.build_payload(fares, timetable, "LIN", day=day)      # 2.4 s, then 16.7 s
```

The same page's timetable half, measured through a worker
(`python -m tools.measure_worker_pages --timetable feeds/timetable-nwr --origins
NOT,EDB --pages 2`), is **31.8 s** for Nottingham and **132.6 s** for Edinburgh
against **2,204 MB** of private memory, so a page on this timetable costs what it
cost on the DTD one (33.6 s and 119.6 s on the same probe): the CIF switch is not
what happened.

**What it means.** Without a date there is no day for the page to walk a week
from, so `TimetableDb._ensure_indexes(None)` indexes every schedule in the feed's
window instead of the one day's share of them, for every page: 7x the index work
on the smallest page here, and on Nottingham a page that does not finish in the
minutes one dated page takes seconds. `journeys_from` is then asked with no day
as well. The page also carries no day control at all, which
`tests/test_service_week.py` states as the intended shape of an undated build, so
the workflow's comment about "aggregate schedules and the day control filters
them" described a page that was never built. On 21 October 78 pages took 139
minutes where 458 had taken 108 on 13 October. A share in the twelve-way split
writes about 217 pages, so at that share's 58.4 s median gap it is **3 h 31 min**
against the step's 150-minute bound, and at 13 October's 14.2 s a page it is
**51 min**.

**What was done.** The build job now names one day for the run and every share is
built for it, with a guard that stops a share which has no day, and
`tests/test_workflows.py` holds the flag to the build job's output. The release is
therefore dated, as the 13 October one was: the page names its day and its day
control moves the table across the service week. S24 in `docs/open-work.md` is
still the decision that would make an aggregate, undated shape a mode of its own.

The first dated twelve-share run then measured it, 21 October 2026 (run
39667902022): share 6 wrote **221 pages in 20 min 49 s** (20:14:55 to 20:35:44
UTC, 287 origins), and its `shard.json` carries `2026-10-21` in the inputs the
merge compares, against the 139 minutes 78 pages took undated that morning. The
51-minute projection above was conservative; a dated share costs about four and
a half seconds a page on a hosted runner.

## What the real page did not settle, 21 October 2026

O1's own closing figure is the assembled release's bytes, and no run has reached
the assemble job since 19 October 2026: one push stopped on a missing
`SCHEDULE_URL` and the next answered HTTP 401 from the CIF endpoint. Nothing in
this section changes that. What it adds is the page the budget is per, measured
rather than extrapolated, and the bracket the open item now states.

## A .FSC-priced page's bytes, 23 October 2026

**Why this was taken.** O1's bracket was four pages of 283 to 449 KB, measured on
21 October 2026 before `.FSC` cluster flows priced nearly the whole network from
every origin. The release report then projected 1,940 MB for 12 shards and asked
for the page to be profiled rather than projected. The plan was to build one
heavy page and one small one from the local feeds, split each into stylesheet,
script, payload and markup with `tools/page_bytes.py`, compress the same file at
`gzip -9` the way the host does, and cost every payload key separately. The
figures below are all from that plan; nothing here was estimated before it was
measured.

```
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable \
    --origin GRA --date 2026-10-05 --notices nre,rdg,ogl,accuracy \
    --out _scratch/before/index.html --workers 1
python -m tools.page_bytes _scratch/before/from/grantham/index.html
```

**The page shape.** Grantham prices **2,752 destinations** in three fare lists
(1,666 returns, 2,752 singles, 272 Anytime Day Returns): **4,690 rows** and
2,752 places, 8 days of service week. **1,730 of the places carry
`journeyState: no_service`** on every day the page walks, so 2,584 of the rows are
a price for a place the timetable does not reach within one change. Ashwell &
Morden, a small station, has 6,056 rows and 2,756 places, which is the same shape.

| origin | before | after | gzip before | gzip after | payload before | payload after |
| --- | --- | --- | --- | --- | --- | --- |
| Grantham | 1,368,721 B | 690,977 B | 139,782 B | 128,201 B | 1,333,421 B | 655,677 B |
| Ashwell & Morden | 1,301,965 B* | 657,135 B | not kept | 114,176 B | 1,266,617 B | 621,787 B |

\* Ashwell & Morden's before page was not built: that figure is the old encoder
run over the page's own decoded payload (1,266,617 B) plus the 35,348 bytes of
markup the page carries. Every other figure in the table is a measured file.

**The raw page halves and the compressed page barely moves.** Grantham is 49.5%
smaller on disk and **8.3% smaller over the wire** (139,782 -> 128,201), because
the redundancy the wire carried -- one ticket link on 2,752 places, the same
column names on every row -- is exactly what deflate was already removing. Raw is
what the 1 GB published-site limit counts and what `page_bytes.py` gates, so the
change is real for the release; a reader's transfer is not what it buys.

**Why the projection was low.** The release report took 343.5 MiB of compressed
shard zips and divided by 5.65:1. These pages compress at **9.8:1 before** the
change (1,368,721 -> 139,782) and **5.4:1 after**, so 343.5 MiB is about **3.4 GB**
of HTML, not 1.94 GB. 120 KB gzipped a page divided by 9.8 is 1.18 MB a page,
which is where the two measured origins sit.

**Where the payload went, before and after.** `places` 806,498 -> 274,496, the
fare rows 354,914 -> 235,078, `serviceWeek` 105,169 -> 70,552, page pool
42,137 -> 50,805, payload 1,333,421 -> 655,677. The largest single item was the
same `link` object on all 2,752 places, 272,448 bytes, because the page-level pool
(ADR-0046) only ever saw the row tables; the second was a departure option
spelled as an object (189,089 bytes). The per-column table and the six changes
were in `docs/audits/2026-10-23-page-byte-budget.md`, removed on 26 October 2026
once its last question was measured; the two decisions it raised are ADR-0076 and
ADR-0077, and the figures still in use are the two rows above.

**What it does not settle.** These pages come from the DTD timetable on this
machine, not from the Network Rail CIF the release reads, and two origins are not
the network. The assembled site's `python -m tools.page_bytes --site _site` was
the figure that decided O1, and it is the last section of this file; 1 GB over
2,930 pages was 366 KB a page (341 KB if a gigabyte is 10^9 bytes) against the
674,056 bytes the two measured pages average.

## Twelve release-shaped pages, 24 October 2026

**Why this was taken.** The 23 October section above halved the raw page and
left the site about 1.19 GB by projection. Two changes to what a page carries
were costed there and not measured: dropping the places no journey reaches
(ADR-0076) and moving the station's own facts into the shared list (ADR-0069
amendment). The plan was to build twelve stations in the release's own shape --
`--all-origins --only-stations`, so each page fetches the station list and
carries no facts -- from the same feeds and one service date, then read each
page's bytes, its gzip size, its payload, its places and its rows out of the
page itself. Twelve rather than one because a cluster-priced page's size tracks
how much of the network it reaches, and one origin would be a socket for the
network's average.

```
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable \
    --all-origins --only-stations LIN,IPS,NOR,CBG,KGX,GRA,OXF,PLY,NOT,SHF,NCL,MAN \
    --date 2026-10-05 --notices nre,rdg,ogl,accuracy \
    --out _scratch/sample2/index.html --workers 2
```

| station | page | gzip | payload | places | rows | unreachable |
|---|---:|---:|---:|---:|---:|---:|
| Linlithgow | 159,870 | 37,981 | 124,456 | 267 | 716 | 2,469 |
| Ipswich | 198,313 | 45,401 | 162,730 | 380 | 987 | 2,352 |
| Normanton | 277,041 | 62,655 | 241,278 | 619 | 1,498 | 2,112 |
| Cambridge | 363,518 | 79,055 | 327,755 | 937 | 2,511 | 1,821 |
| London Kings Cross | 371,949 | 74,361 | 336,333 | 658 | 1,255 | 19 |
| Grantham | 373,396 | 82,961 | 337,636 | 1,027 | 2,092 | 1,725 |
| Oxford | 422,228 | 93,758 | 386,474 | 1,122 | 2,705 | 1,632 |
| Plymouth | 426,613 | 87,774 | 390,853 | 1,270 | 2,760 | 1,478 |
| Nottingham | 512,978 | 109,013 | 477,212 | 1,397 | 3,215 | 1,322 |
| Sheffield | 570,314 | 121,449 | 534,551 | 1,691 | 3,821 | 1,037 |
| Newcastle | 573,788 | 117,267 | 538,025 | 1,480 | 3,152 | 1,252 |
| Manchester Piccadilly | 637,545 | 134,076 | 601,746 | 1,731 | 4,119 | 995 |

**What the twelve say.** Mean **407,296 bytes**, median 397,812, gzip mean
87,146. At that mean 2,930 pages are **1,193 MB** of HTML: 11% over 1 GiB, 19%
over 10^9, and 49% over `SITE_BUDGET_MB`. The gzip mean projects the release's
shard zips near 255 MB, against the 343.5 MiB that raised the audit.

**What each change was worth, on Grantham, one at a time.**

| state | page | gzip |
|---|---:|---:|
| after the wire pass (23 October) | 690,977 | 127,158 |
| + a page lists only what a journey reaches (ADR-0076) | 426,972 | 90,017 |
| + the station's facts in the shared list (ADR-0069 amendment) | 386,505 | 83,626 |
| + a day that repeats the day before travels as `true` | 373,396 | 82,961 |

The contents changes take **46%** off the raw page and **35%** off its gzip,
unlike the wire pass: a place nobody can reach and a fact repeated on every page
are bytes a reader was actually being sent.

**What it does not settle.** These pages come from the DTD timetable on this
machine, not from the Network Rail CIF the release reads, and twelve stations are
a spread rather than a random sample. The assembled site's
`python -m tools.page_bytes --site _site` was the figure that decided O1, and the
26 October section below is it.

## A lever measured and refused: the clock times as one list, 24 October 2026

**Why this was taken.** The twelve-page section above leaves the site 1,193 MB
against a 1 GB limit, and named `departures` as the second largest column of a
page -- 103,614 bytes of Manchester Piccadilly's 637,545 -- with an estimate of
about 29 KB recoverable by sending each clock time once and each option as an
index into that list. The estimate was not measured, so it was built.

**The plan.** Rebuild the same twelve pages on the same day and date with one
change: a departure option travels as `[departureIndex, arrivalIndex, changes]`,
`rowCodec.departureTimes` holds each distinct minute once, and the list is
ordered by how often a time is used so the commonest clock is a single
character. The encoder sends the list only when every time on the page is a
minute and the rewrite is smaller, so a page of a handful of trains keeps its
times. The round trip through `decode_payload` was byte-identical, and the built
page's `DATA.destinations[0].departures` read back as
`{depart: 341, arrive: 523, changes: 1}` -- minutes, not indices.

| | before | after | change |
|---|---:|---:|---:|
| mean page, raw | 407,296 | 401,996 | **-1.24%** |
| mean page, gzip -9 | 87,146 | 88,802 | **+1.91%** |
| Grantham, raw | 373,396 | 369,315 | -4,081 |
| Grantham, gzip | 82,961 | 84,531 | +1,570 |
| Manchester Piccadilly, raw | 637,545 | 629,183 | -8,362 |
| Manchester Piccadilly, gzip | 134,076 | 136,465 | +2,389 |

**What it does not buy, and why the estimate was wrong.** A page names between
400 and 1,040 distinct minutes -- each destination's next few departures are its
own, not its line's -- so the list is 2 to 4 KB of the page on its own, and
deflate already spends a few bits on a repeated three- or four-digit clock. The
raw page falls 1.2%, which is 15.5 MB off the release's 1,193 MB -- 13% of the
119 MB it is over 1 GiB, 4% of the 393 MB it is over the 800 MB budget -- while
every reader's transfer grows 1.9%. The change was reverted rather than shipped:
the estimate in the audit is corrected, and the trade is recorded there as a
decision rather than taken as an encoding win.

## A cap on the places a page lists, 24 October 2026

**Plan.** The 23 October audit left the three fare lists as the largest lever it
had measured and not taken: they are 36% of its largest page, and the rows are
three different fares to the same place, so one fare per place cannot serve the
ticket-mode filters. The version that keeps every filter is a cap on the places
themselves -- every list cut to the same places, so a mode still means "every
fare of this kind to a place this page lists". This costs that cap, and says what
a reader loses. Written before the figures were taken.

**Method.** `python -m tools.measure_place_cap --site _scratch --census grantham`
over the same twelve release-shaped pages the audit measured (`--all-origins
--only-stations LIN,IPS,NOR,CBG,KGX,GRA,OXF,PLY,NOT,SHF,NCL,MAN --date
2026-10-05`, built 24 October 2026). For each cap the tool decodes a page's
payload, cuts the three fare lists to the cheapest N places by standard adult
fare, prunes the service week the way the build already prunes it after a row
filter, re-encodes, rebuilds the page around the new payload, and measures the
rebuilt page and its `gzip -9`. **The check that it is measuring the page it
replaces:** at no cap the rebuilt page is the built page byte for byte, 12 of 12.
The release figure is the twelve's mean times the 2,930 pages the release writes,
against the 800 MiB budget `tools/page_bytes.py` holds the site to. **Units:**
every figure in this section is MiB or a raw byte count, because that is what the
gate counts; the audit's 1,193 MB is the same release in decimal megabytes.

**Figure.**

| Places a page lists | Mean page | Mean gzip | 2,930 pages | Of the 800 MiB budget |
|---|---:|---:|---:|---:|
| no cap | 407,289 | 87,144 | 1,138 MiB | 142% |
| 700 | 289,101 | 63,598 | 808 MiB | 101% |
| 600 | 265,946 | 58,713 | **743 MiB** | **93%** |
| 500 | 236,344 | 52,696 | 660 MiB | 83% |
| 400 | 207,034 | 46,860 | 579 MiB | 72% |

**What a reader loses at 600 places.** The twelve pages price and reach 12,579
places between them and would list 6,647. The cap is a price, not a cut: every
fare below the stop is unchanged, so the page answers every budget up to it
exactly as it does now, and the two small stations are untouched.

| Station | Places listed | Dearest fare listed | Dearest fare the feed prices |
|---|---:|---:|---:|
| Manchester Piccadilly | 600 of 1,731 | £47.40 | £186.30 |
| Sheffield | 600 of 1,691 | £54.50 | £235.00 |
| Newcastle | 600 of 1,480 | £55.00 | £316.90 |
| Nottingham | 600 of 1,397 | £63.00 | £254.80 |
| Plymouth | 600 of 1,270 | £138.90 | £328.20 |
| Oxford | 600 of 1,122 | £80.00 | £242.30 |
| Grantham | 600 of 1,027 | £72.40 | £206.30 |
| Cambridge | 600 of 937 | £60.90 | £261.80 |
| London Kings Cross | 600 of 658 | £88.00 | £268.30 |
| Normanton | 600 of 619 | £192.60 | £243.60 |
| Ipswich | 380 of 380 | £111.70 | £272.80 |
| Linlithgow | 267 of 267 | £255.90 | £328.20 |

**The design, in three places.** The rule goes in `build_payload` beside the
reachability cut (ADR-0076), the one place every fare list is already narrowed:
rank the places by their cheapest standard adult fare, ties by CRS, keep the
first N, and let the service week narrow with the rows as it already does. The
payload carries the count the rule left out, beside `unreachableDestinationCount`,
and `table.js` writes one sentence from it beside `unreachableNote()`. Nothing
else changes: the budget ceiling, the mode counts, the empty-state doors and the
shortlist all read the rows, so they agree with the cap by construction. It is a
build flag (off for the synthetic fixture) rather than a page-side rule, because
which places a page carries is the build's answer to the same question D2 was.
One check had to follow it: `tools/check_known_fares.py` holds a page to fares
checked by hand, and a row for a place beyond a page's stop would report as a
fare the page lacks. It does not bite: Grantham's four rows are to Nottingham and
Skegness, which rank 19th and 100th of its 1,027 places, so the table reads the
same pages it always did at 600. A cap low enough to exclude a hand-checked fare
would have to be 19 or less at this station, and the check's own message names
the destination it could not find, which is what sent a reader to this ranking
rather than to the tool.

**Why merging the fare lists is not this lever.** A merged row per place, holding
that place's fares, serves the same filters and saves only what the three lists
repeat: Grantham's place key is 4,030 + 5,135 + 1,295 bytes across its three
lists, and across the twelve pages the keys are 144,155 bytes of their 4,887,468
-- 2.9%, and about 1.7% once each place keeps one. The cells that make a fare a
fare are per fare: on Grantham's page the ticket records are 28,017 bytes and the
railcard decisions 22,473, and both are the fare's own, not the station's. The
lever is how many places a page lists, not how the lists are shaped.

**What it means.** At 600 a page lists 53% of the places it reaches, stops between
£47.40 and £255.90 depending on the station, and lands 7% inside the budget --
93% of it against 142% now, and 27% inside the host's 1 GiB where the page shape
was 11% over. **700 is the edge**: 808 MiB against the 800 budget, so the most a
whole-network run could justify is about 650. Two costs come with it. The ranking
is the build's standard adult fare, so a railcard cannot move the cap: a place a
card would make cheaper than a listed row stays off the page. And the page stops
saying the station's range of fares -- it says where it stops, which is the one
sentence the design owes a reader. The picker still reaches every station, so the
loss is what this page can discover, not what the network holds.

## The release's own bytes, 26 October 2026

**Why this was taken.** Every figure above is a sample: two origins, twelve
origins, one shard. O1 asked for one release run that reached the assemble job,
because the `python -m tools.page_bytes --site _site` step there is the only
measurement of the site the host serves. The 25 October run reached the browser
step and failed on one page defect; the 26 October run finished, published, and is
this section.

**What it printed.** Run 40295899061, head `82fd095`, all sixteen jobs succeeded:

```
site 370 MB of a 800 MB budget over 2838 page(s)
the manifest names 2838 route(s) and the folder holds 2838 page(s)
all 4 known fare(s) agree with the pages
32 of 32 page(s) checked, 8980/8980 browser checks passed, 156 check(s) not
  exercised by the pages swept (121 of 8527 with a timetable, 19 of 466 without one)
  ok  browser suite (274.6s): 32 page(s)
```

**The figure.** 370 MB is the gate's own unit: 387,973,120 bytes over **2,838
pages**, so the mean page is **136,705 bytes**. Against the 800 MB budget that is
**46%**, with 430 MB spare. The twelve-page sample predicted 407,296 bytes a page
and 1,193 MB for the release; the release is **3.0x smaller** than that per page
and 3.1x smaller in total (370 MiB against the sample's 1,138). The sample was
chosen as a spread and included the network's largest stations -- Manchester
Piccadilly, Sheffield, Newcastle, Nottingham -- and the whole-network mean is
three times smaller, which is what that sample's own caveat predicted. The release
also writes 2,838 pages, not the 2,930 every projection assumed.

**Why the third decimal is not quoted.** The gate prints whole MB, so the mean
carries about 150 bytes of rounding either way. The number that decides the
budget is 370 of 800, and it is the gate's own.

**The twelve shares.** Each shard prints its wall clock, and the first whole-network
release to finish spent:

| Share | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Minutes | 34 | 27 | 33 | 20 | 30 | 20 | 39 | 25 | 33 | 18 | 33 | 34 |

Mean **28.8 minutes**, slowest **39**, against the step's **150-minute** bound and
its **100-minute** nearing warning. 346 runner-minutes for the whole release. The
20 October audit's A1 owed this figure because the run it measured spent the whole
bound on every share and wrote no page; the figure replaces that with a bound four
times the slowest share.

**What it settles.** O1, and with it the 1.94 GB projection, the 1,193 MB sample
mean and the 366 KB a page arithmetic. The cap at 600 places and the two contents
changes were enough, and the margin is not close: 430 MB.

**What it leaves unnecessary.** The 23 October audit named the columns still worth
weighing -- the three fare lists (taken, as the cap), `departures` (measured: 1.24%
of the raw page for 1.91% *more* gzip, refused), `name` (4%, already in the shared
list for stations that have a page), `legs` (2%, read by no file) and the service
week (15%). None is needed for the budget now. Each remains a product question
about what a page carries rather than a byte lever, and none is worth its trade at
370 of 800.

**What it does not settle.** One run, one feed, one service date. A page's bytes
also move with how much of the network its origin reaches, so the mean is this
network's on that day; a later release that changes the cap or the day will print
its own. And bytes are not paint: the reader's first row on a throttled connection
is measured separately, under "A real-feed station page's bytes".
