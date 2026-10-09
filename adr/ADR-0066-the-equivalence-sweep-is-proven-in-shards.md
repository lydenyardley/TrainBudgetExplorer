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
   compare". **The request is read from the shards**, not recomputed from the
   feed: they agree about it or there is no verdict, and a merge that parsed the
   feed would spend a minute and hold an index to relearn what the files say.

4. **One verdict serves a run and a merge.** Both answer the same question --
   every origin-day asked for agreed, one did not or raised, or some are still to
   compare -- through one function, so the exit-code contract cannot come out two
   ways depending on how the pairs were produced.

5. **Memory is the constraint, and the tool says so.** Each shard parses the feed
   and holds its own index (1.87 GB, measured), so the count that fits is a memory
   question before it is a CPU one. A sharded run prints the index its M shards
   hold against the free memory this machine has, and `--shards auto` picks the
   count from exactly that division, narrowed by the cores, never below one: a
   machine that cannot hold two still sweeps, one share at a time.

6. **A sharded run is one invocation, and it loses no work.** `--shards M` starts
   the M children itself, streams their output prefixed with the shard number,
   draining every child at once -- an OS pipe holds about 4 KB, so a launcher
   that read its children in turn would stall each one in `write()` behind the
   ones ahead of it, and a stalled child is a shard that is not comparing --
   then merges them; `--shards auto` is the same with the count this machine can
   hold. A shard starts from the base checkpoint's answers about its own share
   when that checkpoint was asked the same question, so a sharded run of a
   request an earlier unsharded sweep has partly compared does not compare it
   again, and a merge keeps the base's pairs that its own request was not about.

## Consequences

Re-measured on the national download, 8 October 2026: the feed loads in **58.0 s**
(419,589 schedules, 7,700,987 calling points), a probe of eight origins on
2026-10-07 gives **2.45 s per origin-day** (0.29-9.32 s; the first origin of a day
carries that day's index build), and the same sweep through `--shards auto` over
the first twelve origins and all seven days -- 84 origin-days, 18 of them carried
over from the base checkpoint -- **finished in 4 min 53 s, exit 0, 84 of 84 agreed,
2,065 pairs of the base's other request kept**, at a rate of 3.3 s per origin-day
on a machine that had 2.4 GB free rather than the 4.7 GB of the probe.

The full request is **about 18 hours** in one process, **about 4.5 hours over 4
shards** and **about 2.2 hours over 8** -- at the memory those shards want, 8 x
1.87 GB of index. That is the whole point of `auto`: on the day this was written
this machine had **3.1 GB** free, so it chose **one shard**, and 4 was not a number
it could hold without paging. Freeing the machine, or a 16 GB runner, was the
expectation for what buys 4 or 8.

Run anyway on **9 October 2026** with `--shards 4` -- 4.1 GB free against the
9.5 GB four shards want, so the sweep sat at 0.1-0.2 GB free -- and the four
shards finished the request's remaining origin-days at **41 pairs/min against
one process's 26.5, 1.6x and not 4x**: paging priced the parallelism rather
than erasing it, which corrects the expectation above. The same morning the
launcher's own streaming was found to be the other cost -- measured 4 KB of pipe
-- and draining every child at once (decision 6) is what the run then used.
The merged verdict: **26,369 of 26,369 origin-days, 0 differing, exit 0**, with
the full figures in `docs/build-performance-findings.md`.

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
