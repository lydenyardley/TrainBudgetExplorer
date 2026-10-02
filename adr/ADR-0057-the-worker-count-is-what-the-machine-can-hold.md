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

**`WORKER_BYTES` is deliberately left at 900 MB.** The corrected figures say the
four-worker budget does not hold; the recorded four-worker tree above says four
workers fitted in 2.9 GB with the parent down to 120 MB, which cannot be true if
one worker holds 2.1 GB. Both cannot be right, and one of them has now been
shown to be a measurement error, so the honest position is that this ADR holds
one good measurement, one bad one withdrawn, and one unexplained. Changing the
constant would change the worker count on every machine and in CI on the strength
of a contradiction rather than a measurement.

Settling it needs one run this machine could not do: a real four-worker
build, which needs about 10 GB free. Two things are already true and do not wait
for it. `tools/measure_build_memory.py` now holds its subject, and
`tools/measure_worker_pages.py` measures a worker's real peak without needing
four workers -- it calls `init_worker` and `build_page_job` in one process
rather than re-implementing them.

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
