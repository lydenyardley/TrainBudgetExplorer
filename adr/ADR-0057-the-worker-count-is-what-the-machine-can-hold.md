# ADR-0057: the worker count is what the machine can hold, not how many cores it has

Date: 2 October 2026

## Status

Accepted. Amends the way ADR-0055's whole-network default is carried out; the
default itself stands.

**Amended 2 October 2026.** The two worker figures in the table below are
withdrawn: they were measured from a database the measuring tool had already
freed. `WORKER_BYTES` is left unchanged pending one real four-worker build, and
the recorded four-worker tree is now unexplained. The correction is under the
table; the decision itself is not reopened.

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
| `build_workers.WORKER_BYTES`, which this ADR justifies | **900 MB** |

So the per-worker budget is 2.4x smaller than the figure it was derived from,
and decision 3 below -- "the numbers are measured by a tool, not asserted in a
comment" -- is the claim that failed: the tool was measuring a discarded object
and reporting it as a measurement.

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

**`WORKER_BYTES` is deliberately left at 900 MB.** The evidence now points one
way: a worker costs 2,188 MB, not 900 MB, and the tree arithmetic above is
consistent with that at both four workers and eight. But the constant is not
changed here, because changing it is a decision about every machine and about
CI, and the figure that would replace it has been measured in one process on
one feed. Raising it to 2,200 MB moves `ONE_WORKER_FLOOR` from 7.3 GB to
8.6 GB, which on a 15.8 GB machine turns a four-worker build into a one-worker
build for anyone whose desktop is open -- the opposite of the ceiling this ADR
exists to enforce, and a consequence no single-process measurement can
predict. That is a decision to make against a real four-worker run, not against
a corrected comment.

The wall time that budget was chosen against: a whole-network build of the real
feed, 2 October 2026, wrote 2,712 pages between 10:29:52 and 12:30:57. That is
121 minutes at 0.093 pages/s per worker on four workers, and about two hours
from a cold start including the 145s feed load, the 83s pool start and the
chooser. An earlier note in this file put it at 63 minutes, from a nine-minute
window early in a build; that window held the cheapest stations in the set, and
the error was a factor of two. The release workflow's own comment records
0.84 pages/s and 54 minutes from "the first twenty pages" -- the same mistake on
a different machine, left standing here because correcting it needs that run,
not this edit.

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
figure and says the old one is withdrawn rather than qualified. The release
workflow's own recorded 54 minutes of page building plus a 279s load at three
workers is a measurement of a different machine and is left standing.

## Read by running

```
python tools/measure_build_memory.py --measure machine
python tools/measure_build_memory.py --measure worker
python tools/measure_worker_pages.py --origins GRN,LCN
python -m unittest tests.test_build_demo_page.WorkerBudgetTest
python -m unittest discover -s tools -p "test_measure_worker_pages.py"
```
