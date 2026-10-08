# ADR-0066: The equivalence sweep is proven in shards over disjoint origin sets

**Status:** Accepted
**Date:** 8 October 2026
**Relates to:** ADR-0032 (a measurement plan before a figure), ADR-0005 (the feed cannot be checked in), ADR-0061 (every leg a page shows is part of the question)

## Context

The slice's claim is about a page's questions, and the tool that checks it,
`tools/check_slice_equivalence.py`, asks the whole database and the slice the same
question for every origin and every day of the service week: **3,767 origins by
seven days is 26,369 origin-days at about 2.4-2.5 s each, or about 17-18 hours**
(re-measured 8 October 2026 below). One process, one checkpoint, resumable. After
a day of runs the seven-day sample was complete and the first day was a third
done, and the rest of the request was argued in a document rather than proven --
which is the one thing a proof may not be.

The work is embarrassingly parallel: an origin-day is compared against the feed
and nothing else, and no pair's answer depends on another pair. What the sweep
does hold, per process, is the feed's own index: **1.87 GB** on the national
download, which is a cost of running it at all, not of the comparison.

## Decision

1. **The shards are disjoint by construction.** `--shard N/M` compares origins N,
   N+M, N+2M ... of the request's origin list -- the feed's own sorted list unless
   `--origins` named an order. The M shares cover that list exactly once, so the
   union of the shards' origin-days is the request and no pair is compared twice.

2. **Each shard owns a checkpoint, named for it.** `--shard N/M` writes
   `<base>.shard-N-of-M.json` beside the base file, so M processes share no bytes
   on disk: no lock, no queue, no ordering, and a shard that finishes early does
   not touch another's work or its resume.

3. **A shard records the request it was given.** Its checkpoint carries the
   origins it holds, the request they are a share of, the days, `max_legs` and
   the feed, so `--merge M` can check the partition instead of trusting it. It
   refuses, rather than concludes, when a shard file is missing, when a shard was
   made against another request, when two shards' origins overlap, when a request
   origin is in no shard, or when a pair sits outside the origin-days its own
   file records. A refusal is exit 2, the same code a run uses for "still to
   compare".

4. **One verdict serves a run and a merge.** Both answer the same question --
   every origin-day asked for agreed, one did not or raised, or some are still to
   compare -- through one function, so the exit-code contract cannot come out two
   ways depending on how the pairs were produced.

5. **Memory is the constraint, and the tool says so.** Each shard parses the feed
   and holds its own index (1.87 GB, measured), so the count that fits is a memory
   question before it is a CPU one. A sharded run prints the index its M shards
   hold against the free memory this machine has. The tool does not spawn the
   shards: the operator runs M commands, which is the shape `run.py` and
   `build_stations.py` already have here.

## Consequences

Re-measured on the national download, 8 October 2026: the feed loads in **58.0 s**
(419,589 schedules, 7,700,987 calling points), a probe of eight origins on
2026-10-07 gives **2.45 s per origin-day** (0.29-9.32 s; the first origin of a day
carries that day's index build), so the full request is **about 18 hours** in one
process, **about 4.5 hours over 4 shards** and **about 2.2 hours over 8** -- at the
memory those shards want, 8 x 1.87 GB of index against the **4.7 GB** that was
free on this machine, so 4 is the number this machine can hold and 8 is the number
a 16 GB runner could.

A merged verdict is only as good as its partition, and the merge refuses anything
that is not the request, so a green merge cannot be greener than its parts. What
sharding does not do: it does not make a shard's rate faster, it does not reduce
the memory the sweep needs, and an incomplete set of shards is not a verdict but
the count of what is left.

Read by running:

```bash
python tools/check_slice_equivalence.py --timetable feeds/timetable --date 2026-10-07 \
    --days 7 --progress _cache/slice-equivalence.json --shard 1/4
python tools/check_slice_equivalence.py --timetable feeds/timetable --date 2026-10-07 \
    --days 7 --progress _cache/slice-equivalence.json --merge 4
python -m unittest tools.test_check_slice_equivalence
```
