# ADR-0057: the worker count is what the machine can hold, not how many cores it has

Date: 2 October 2026

## Status

Accepted. Amends the way ADR-0055's whole-network default is carried out; the
default itself stands.

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
| one worker's initialiser | **325 MB** |
| the largest worker sampled while assembling pages | **852 MB** |
| a four-worker tree, sampled mid-build | **2.9 GB** total, parent down to 120 MB |

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

**4. The runner says which count it chose and how much memory was free.** "1
worker" alone does not distinguish the ceiling from a shortage, and those are
different problems for whoever is waiting for the build.

## Consequences

- A machine with room to spare builds the network in about 63 minutes; one
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
python -m unittest tests.test_build_demo_page.WorkerBudgetTest
```
