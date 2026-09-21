# Train Budget Explorer

**Status:** Stage 1 in progress. Parser built and verified; the fares download is
blocked on a Marketplace account (21 September 2026).
**Created:** 21 September 2026

## What this is

From any UK station, find every destination reachable for under a set budget
(e.g. "≤£20 return from Grantham"), filterable by city/town, built on official
UK rail open data.

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

- **Built:** `atoc_fares.py` parses the real record layouts and answers budget
  queries. `grantham_sweep.py` is the go/no-go instrument. Ten tests pass.
- **Blocked:** the fares feed needs a Marketplace account and a licence accepted
  in the owner's name. Nothing about it is anonymously readable.
- **Not yet answered:** the real count of Grantham destinations under £20, and
  the licence terms for commercial use.
- **Details and evidence:** `stage-1-results.md`, `adr/ADR-0005-data-access-and-blocker.md`.

## Files

| File | Purpose |
|---|---|
| `atoc_fares.py` | Fares feed parser and the budget query |
| `grantham_sweep.py` | CLI: every destination in a budget from one origin |
| `make_synthetic_feed.py` | Builds an invented feed folder in the real layouts |
| `test_atoc_fares.py` | Ten tests against the synthetic feed |
| `stage-1-results.md` | Stage 1 findings, evidence, and residual risks |
| `glossary.md` | Domain terms |
| `adr/` | Decisions, numbered, newest last |

## Run it

```
python make_synthetic_feed.py _demo_feed
python -m unittest -v test_atoc_fares
python grantham_sweep.py --feed _demo_feed --origin GRN --budget 20 --adults 2 --railcard "Two Together"
```

Swap `_demo_feed` for the downloaded feed folder to get the real answer.

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
