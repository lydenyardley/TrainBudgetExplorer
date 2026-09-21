# Train Budget Explorer

**Status:** Stage 1 in progress. Both parser layers are built, hardened against
damaged input, and covered by 41 tests. The feed download clears when the
Marketplace account is approved (21 September 2026).
**Created:** 21 September 2026

## What this is

From any UK station, find every destination reachable for under a set budget
(e.g. "≤£20 return from Grantham"), with the journey time, the number of
changes, and a two-adult party price for Two Together railcard holders.

## Decided summary

- **What:** Grantham-only demo. Every destination reachable from Grantham under
  a budget (cheapest Anytime/Off-Peak return per adult), a city/town filter, and
  a Two Together party price. Static data, honest disclaimers.
- **Hypothesis:** affiliate lead-gen asset (Trainline, applied post-launch).
- **Discovery:** communities first (r/uktrains, local FB groups, HN); SEO only
  after a community signal.
- **Scope:** Two Together is the only railcard in v1. Party pricing is core
  maths, not a UI option, because the card only discounts when both travel.
- **Plan:** Stage 1 licence and data verification, then go/no-go, then a
  one-week build hard-stopped at 30 September, launch w/c 5 October, written
  review **21 October** with park-by-default if unsure.
- **Accepted tension:** this runs before Missing Music and The Family Apothecary
  are published. The owner chose that knowingly. Recorded in ADR-0004.

## Stage 1 status

- **Built:** `atoc_fares.py` answers budget queries from the fares feed.
  `atoc_timetable.py` answers journey time, change count, and reachability from
  the CIF timetable feed. `grantham_sweep.py` joins them, and `feed_audit.py`
  reports what a feed actually contained. 41 tests pass.
- **Blocked:** the feeds need a Marketplace account and a licence accepted in the
  owner's name. Nothing about them is anonymously readable.
- **Not yet answered:** the real count of Grantham destinations under £20, and
  the licence terms for commercial use.
- **Details and evidence:** `stage-1-results.md`, `adr/ADR-0005-data-access-and-blocker.md`.

## What the journey times mean

A journey time is the fastest service in the feed, with one change allowed by
default. Service days and schedule overlays are not honoured yet, so read the
times as typical rather than date-specific. `adr/ADR-0006-timetable-layer.md`
lists every approximation and what would remove it.

## Files

| File | Purpose |
|---|---|
| `atoc_fares.py` | Fares feed parser and the budget query |
| `atoc_timetable.py` | CIF timetable parser, journey and reachability queries |
| `grantham_sweep.py` | CLI: every destination in a budget, with journeys |
| `feed_audit.py` | CLI: what each feed contained and where they disagree |
| `parse_report.py` | Shared parse counters and the streaming line reader |
| `make_synthetic_feed.py` | Builds invented fares and timetable feed folders |
| `check_commit_message.py` | Checks a commit message against the convention |
| `test_atoc_fares.py` | Ten tests against the synthetic fares feed |
| `test_atoc_timetable.py` | Nine tests against the synthetic timetable |
| `test_grantham_sweep.py` | Two tests for the fare and service merge |
| `test_feed_audit.py` | Nine tests for the audit and for damaged input |
| `test_commit_message.py` | Eleven tests for the message checker |
| `stage-1-results.md` | Stage 1 findings, evidence, and residual risks |
| `glossary.md` | Domain terms |
| `CONTRIBUTING.md` | Commit convention and how to run the tests |
| `adr/` | Decisions, numbered, newest last |

## When the account clears

1. Put the fares feed in `feeds/fares` and the timetable feed in
   `feeds/timetable`.
2. Run `python feed_audit.py --feed feeds/fares --timetable feeds/timetable`
   and read every rejected record before trusting a number.
3. Check the licence text for commercial use, which decides whether ADR-0003
   can proceed.
4. Run the sweep for the Stage 1 count that decides go/no-go.

## Commit convention

Commits follow Conventional Commits 1.0.0. `CONTRIBUTING.md` holds the rules,
and `check_commit_message.py` checks a message against them.

```
git log -1 --format=%B | python check_commit_message.py
```

## Run it

```
python make_synthetic_feed.py _demo_feed --unserved-station
python -m unittest discover -p "test_*.py"
python feed_audit.py --feed _demo_feed --timetable _demo_feed
python grantham_sweep.py --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20 --adults 2 --railcard "Two Together"
```

Swap `_demo_feed` for the downloaded feeds to get the real answer. The fares
sweep alone works without `--timetable`, and then shows prices without journeys.

## Why docs exist here

This project uses the **grill-with-docs** method. While the plan was being
challenged, every decision got an ADR and every term a glossary entry, so future
sessions inherit the reasoning rather than just the conclusions.

## Open questions

Answered during the grill on 21 September, and now recorded in the ADRs: the
real user (affiliate lead-gen), the budget unit (return per adult, party maths
for Two Together), and the validation gate (communities first, dated tripwire).
Still open: the licence terms for commercial use, and the Grantham count that
decides go/no-go.
