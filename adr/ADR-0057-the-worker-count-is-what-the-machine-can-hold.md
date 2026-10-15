# ADR-0057: the worker count is what the machine can hold, not how many cores it has

Date: 2 October 2026

## Status

Accepted. Amends the way ADR-0055's whole-network default is carried out; the
default itself stands.

**Amended 2 and 3 October 2026.** The two worker figures in the table below
were withdrawn on the 2nd: they were measured from a database the measuring tool
had already freed. On the 3rd the recorded four-worker tree was explained -- it
was sampled while the pool was still parsing -- and `WORKER_BYTES` was set to
the measured 2,200 MB once the parent stopped holding its databases across the
pool. The four-worker ceiling now needs about 32 GB of hardware to confirm;
that is recorded in the decision, not hidden by it.

**Amended 3 October 2026, later.** The whole-network run this file had been
waiting on happened, so the release workflow's own timing comment is corrected
rather than left standing, and its bound moved from 150 to 300 minutes because a
private repository's runner is half the size of a public one's. The same day
brought the first measured prices-only whole-network build -- 2,712 pages in
23 min 38 s on one worker -- which is what `run.bat` actually does. Both are in
the decision below.

## Context

ADR-0055 made `python run.py` build the whole network, and the runner chose its
worker count as `min(8, os.cpu_count())`. On this machine that is eight.

Every pool worker is handed the whole national timetable, not a slice of it.
The fares feed was given that treatment deliberately — `write_fare_indexes`
persists shared metadata and one index per origin so a worker restores its own
slice instead of re-parsing 8.5M flow lines — and the timetable was not.

Eight workers therefore mean eight simultaneous parses of a feed with 419,589
schedules and 7,700,987 calling points. The build died with a `MemoryError`
inside the pool initialiser after five minutes, having written no pages. It
reproduced. Four workers completed.

What made this a decision rather than a bug report is that the number it asked
for was presented as a core count. Cores answer how much work a machine can do.
They say nothing about how much of that work can be held at once, and on this
workload the two are not close.

## Decision

**1. `build_workers.worker_budget()` is the only thing that decides how many
workers a whole-network build uses.** Both the runner and the release workflow
call it. Neither counts cores for itself.

Three ceilings, narrowest first: the cores present, whether the machine can hold
the parent and one worker and itself at the same time, and the largest count
measured to finish. It is never zero — a build that cannot have a pool still
builds, one page at a time, and a slow build beats no build.

**2. The ceiling is the largest count measured to finish, not a division.** The
measurements do not support a formula:

| | |
|---|---|
| the parent, parsing both feeds, pricing 3,424 origins, writing an index each | peaks at **4,110 MB** |
| one worker's initialiser | ~~**325 MB**~~ — **withdrawn, see below** |
| the largest worker sampled while assembling pages | ~~**852 MB**~~ — **withdrawn, see below** |
| a four-worker tree, sampled mid-build | **2.9 GB** total, parent down to 120 MB |

### Correction, 2 October 2026: the two worker figures were measured from a freed object

The parent's 4,110 MB stands. The two worker figures do not, and the reason is
a bug in the tool this ADR names as its own re-derivation.

`measure_worker` loaded the national timetable as a statement with no assignment:

    TimetableDb().load_feed(args.timetable)

The load completed, the object had no referrers, CPython freed it, and the
sample taken immediately afterwards read the arenas Python had not returned to
the operating system. The figure it printed -- 325 MB, later 338 MB -- was
memory the process had already given back, not memory it held. A worker keeps
that timetable for every page it builds, so neither number was ever a figure
about a worker.

Measured on the real feed, holding the reference against dropping it:

| | private |
|---|---|
| `db = TimetableDb().load_feed(feed)` | **1,918 MB** |
| `TimetableDb().load_feed(feed)` | 316 MB |

Corrected, through the pool's own `init_worker` and `build_page_job`:

| | |
|---|---|
| one worker, after `init_worker` | **2,100 MB** |
| one worker, assembling pages | **2,188 MB** |
| `build_workers.WORKER_BYTES`, which this ADR justified at the time | **900 MB** |

So the per-worker budget was 2.4x smaller than the figure it was derived from,
and decision 3 below -- "the numbers are measured by a tool, not asserted in a
comment" -- was the claim that failed: the tool was measuring a discarded object
and reporting it as a measurement. The constant is now 2,200 MB; what still had
to give before it could be is the decision beneath this correction.

**The four-worker tree is explained, and it was never a contradiction.** The
2.9 GB sample and the 2,188 MB worker are two readings of the same build at two
different moments, and the arithmetic separates them without another run.

The sample that produced 2.9 GB also recorded its own largest process at
1.2 GB. One worker holds 2,188 MB from the moment `init_worker` returns until it
answers its last job, so a process at 1.2 GB is a worker partway through
`TimetableDb().load_feed` -- the parse that takes 79 seconds and ends at 2,100
MB. Four workers at that instant hold about 4 x 1.2 = 4.8 GB, and a tree of
4.9 GB against a machine of 15.8 GB is a build with room, not a build in
trouble. The sample was taken while the pool was still initialising, which is
the one moment the tree is at its cheapest and the one moment a sampler is most
likely to catch, because it is the moment the operator is watching for progress.

What the sample cannot be is a ceiling for a steady-state worker, and this ADR
previously used it as one. The committed four-worker log settles what a finished
worker costs: it loaded 419,589 schedules and 7,700,987 calling points, wrote
2,712 pages and exited cleanly. At the measured 2,188 MB that is 4 x 2,188 =
8,748 MB of workers, plus the parent's 4,110 MB peak, and the sum -- 12,858 MB
-- fits inside 15.8 GB with room to spare. Four workers were never the problem
on this machine. Eight were, and the same arithmetic says why with nothing left
over: 8 x 2,188 + 4,110 = 21,596 MB against 15,800 MB. The `MemoryError` in
`_cache/w8b.log` is not a transient nobody can account for. It is this sum.

The parent's own share is not released while the pool runs. `build_demo_page.py`
holds `fares` and `timetable` in locals across the `ProcessPoolExecutor` branch
and never drops them -- there is no `del` and no `gc.collect` before the workers
start -- so the pool begins while the parent is still committed. That is why
`PARENT_BYTES` is counted, and it is the premise decision 2's single-step
ceiling relies on when it declines to divide free memory by a per-worker cost.

### Decision, 3 October 2026: the parent stops holding its databases

The constant was left at 900 MB pending a four-worker run this machine could
not do. It is now the measured figure instead, because the thing standing in
the way of a four-worker run was not the cost of measuring it -- it was that
the parent never gave its memory back.

`build_demo_page.py` held `fares` and `timetable` in locals across the
`ProcessPoolExecutor` branch, so the parent was still holding 4.1 GB while
every worker held its own 2,188 MB. The two were concurrent, and 4 x 2,188 +
4,110 = 12,858 MB is a figure no 16 GB machine can satisfy. The parent now
releases both before the pool starts, which is free: the fare indexes the
workers restore are already on disk, and each worker parses the timetable
itself. Measured on the real feed, the release sheds 4,000 MB of the 4,017 MB
held and leaves the parent 36 MB. That measurement also reproduced the parent's
peak independently -- 4,017 MB against the 4,110 MB recorded above -- so
`PARENT_BYTES` stands on a second reading rather than on one old sample.

The release is in the pool branch only. With one worker the build renders in
this process and puts both objects into `_WORKER`, so releasing them there
would delete the databases the build is about to use.

Three things follow, and they are the decision:

- **`WORKER_BYTES` is 2,200 MB**, from the measured 2,188. It was 900 MB while a
  worker held 2,188, which is how a constant could be 2.4x wrong for so long.
- **`worker_budget` divides free memory by it**, which it refused to do while
  the divisor was wrong. A division by a measurement is a division.
- **`ONE_WORKER_FLOOR` is 6.4 GB**, the larger of the two phases plus the
  reserve, rather than their sum. The parent runs first and the workers second,
  so a machine needs room for the bigger one, not for both at once.

Four workers now cost 8,800 MB, which is why a 16 GB machine -- this one, and
GitHub's `ubuntu-latest -- correctly gets fewer than the ceiling of four. A
release build on that hardware drops from about 54 minutes to most of a day,
and that is the honest cost of the corrected constant rather than a reason to
leave it wrong.

**What this decision has not been checked against.** A four-worker tree cannot
be run on 16 GB: it needs 8,800 MB of workers plus the 2,000 MB reserve, before
the parent has parsed anything. Confirming the ceiling needs roughly 32 GB of
RAM -- about 11 GB free, which is 16 GB of hardware with nothing else running,
so in practice a larger machine. Until that run happens, the four-worker arm of
the ceiling is inherited from `MAX_WORKERS` rather than re-measured, and
`tools/measure_worker_pages.py` is what re-derives the per-worker figure. Every
number in the decision above is measured in one process on one feed; the only
unmeasured claim left is that four of them coexist, and it is the one that was
already believed before this correction.

The wall time that budget was chosen against: a whole-network build of the real
feed, 2 October 2026, wrote 2,712 pages between 10:29:52 and 12:30:57. That is
121 minutes at 0.093 pages/s per worker on four workers, and about two hours
from a cold start including the 145s feed load, the 83s pool start and the
chooser. An earlier note in this file put it at 63 minutes, from a nine-minute
window early in a build; that window held the cheapest stations in the set, and
the error was a factor of two. The release workflow's own comment recorded
0.84 pages/s and 54 minutes from "the first twenty pages" -- the same mistake on
a different machine -- and was left standing here pending that run.

### 3 October 2026: the workflow's figures, and what a prices-only build costs

The run this file was waiting on has happened, so the release workflow's own
comment is corrected rather than left standing: it now carries the
whole-network figures above -- 121 minutes at 0.093 pages/s per worker on four
workers -- and withdraws its own 0.84 pages/s and 54 minutes as the
first-twenty-pages measurement they were.

**The workflow's bound moved from 150 minutes to 300, and the reason is this
ADR.** The worker count is read from the runner, and GitHub's standard Linux
runners are not one machine: `ubuntu-latest` is 4 vCPU / 16 GB for a public
repository and 2 vCPU / 8 GB for a private one (docs.github.com, "GitHub-hosted
runners reference"). The same workflow is therefore a four-worker build in one
case and a two-worker build in the other, and 150 minutes covered only the
first. At the measured per-worker rate:

| workers | page building | from a cold start |
|---|---|---|
| 4 (a 16 GB runner) | 121 min | ~130 min |
| 3 | 162 min | ~170 min |
| 2 (an 8 GB runner) | 243 min | ~255 min |
| 1 | 8 h 06 m | longer than any bound GitHub sets |

300 minutes is the slowest runner that can still finish. It costs nothing when
the build is fast, because a hosted job is billed for the minutes it actually
runs; 150 was not a cheaper build, it was a build that failed on a private
repository and published nothing. Raising it again needs this table re-measured.

**A prices-only whole-network build, measured for the first time.** Every wall
time above is a build that loaded the national timetable, and `run.bat` does not:
the runner's default build omits the timetable, so the double-click path is a
different shape of work and had no measured rate at all. Measured on the real
feed on this machine, 3 October 2026, one worker, prices only:

| | |
|---|---|
| station pages | **2,712 in 1,418s -- 23 min 38 s, at 1.91 pages/s** |
| fares feed load | about 30s, from the pickle the earlier builds left |
| output | 592 MB of pages |
| memory | 1.4 GB free at launch, down to 0.08 GB while the feeds loaded |

It is not comparable with the table above, and that is the point: a worker that
never holds the timetable assembles a page for about a tenth of the price, so
`run.bat` on this machine is a 25-minute build and not the 8 hours the
with-timetable figures imply. Two numbers for one project is not a
contradiction; they are two different builds, and the flag between them is
`--with-timetable`.

A four-worker build asks for 4.1 GB plus four workers and finishes; eight asks
for 4.1 GB plus eight and dies, with 8 GB free at the time. The arithmetic does
not explain the failure, and something transient during eight simultaneous
parses of the same zip is the likelier cause than steady-state capacity. This
ADR does not claim to have measured it. The ceiling is therefore the observed
one, and the arithmetic has one job only: catching a machine too small for the
smallest parallel build, which is a floor of 7.3 GB free below which the answer
is one worker.

**3. The numbers are measured by a tool, not asserted in a comment.**
`tools/measure_build_memory.py` re-derives the parent's peak and a worker's
initialiser cost by doing the build's own work, and prints the machine's free
memory against the budget. Constants that go stale are a maintenance cost; a
tool that re-derives them is not.

This held for the parent and not for the worker, and the reason is worth keeping
as the rule the tool now follows: **a measurement must hold what it measures.**
A load with no reference to its result measures the allocator, not the load, and
it reported a number six times smaller than the truth in the reassuring
direction. `tools/test_measure_worker_pages.py` now holds a reference to the
same database the tool loads and requires the reported peak to cover it.

**4. The runner says which count it chose and how much memory was free.** "1
worker" alone does not distinguish the ceiling from a shortage, and those are
different problems for whoever is waiting for the build.

## Consequences

- A machine with room to spare builds the network in about two hours; one
  without builds it on a single worker in most of a day, and says so.
- The release workflow can no longer ask a twelve-core runner for twelve
  workers. It called `max(2, os.cpu_count())`, which had the same exposure in
  the other direction.
- `MAX_WORKERS = 4` is the thing most likely to become wrong as machines grow.
  Raising it needs a measurement, not a hunch, and the tool that makes the
  measurement is the one to run.

## What was withdrawn

ADR-0024's and ADR-0055's "about 20 minutes on eight cores, 81 on two". That
figure was measured without the national timetable, and the eight-worker build
it assumed does not complete. ADR-0055's decision 1 now carries the re-measured
figure and says the old one is withdrawn rather than qualified.

The release workflow's recorded 54 minutes of page building plus a 279s load at
three workers was left standing for one day after this file said it would be,
and is withdrawn now: it was the first twenty pages, and the whole-network run
on the same feed is 121 minutes at four times the worker count. Its 81-minute
figure for a two-vCPU runner goes with it, because `ubuntu-latest` is 4 vCPU /
16 GB for a public repository and 2 vCPU / 8 GB for a private one -- so the
runner is either twice the machine that comment assumed or the same size with
half the memory, and neither case is 81 minutes.

## Read by running

```
python -m tools.measure_build_memory --measure machine
python -m tools.measure_build_memory --measure worker
python -m tools.measure_worker_pages --origins GRN,LCN
python -m unittest tests.test_page_runner.WorkerBudgetTest
python -m unittest discover -s tools -p "test_measure_worker_pages.py"
```

Confirming the four-worker ceiling needs roughly 32 GB of RAM: about 11 GB free,
so a 16 GB machine with nothing else running is not enough. On this project's
own hardware, what re-derives without that is the per-worker figure.
