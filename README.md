# Train Budget Explorer

**Status:** Stage 1 in progress. Both parser layers are built, hardened against
damaged input, date-aware when asked, and covered by 130 tests. The journey
search is measured rather than tuned by feel, the demo page runs on the
synthetic feeds, and the count that decides go/no-go now comes with a report
that questions it. The feed download clears when the Marketplace account is
approved (21 September 2026).
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
  the CIF timetable feed. `grantham_sweep.py` joins them, `feed_audit.py`
  reports what a feed actually contained, `sanity_report.py` questions the count
  it produced, `benchmark.py` measures the journey search, `damage_feed.py`
  makes feeds go wrong on purpose, and `build_demo_page.py` writes the browsable
  page. 115 tests pass.
- **Blocked:** the feeds need a Marketplace account and a licence accepted in the
  owner's name. Nothing about them is anonymously readable.
- **Not yet answered:** the real count of Grantham destinations under £20, and
  the licence terms for commercial use.
- **Details and evidence:** `stage-1-results.md`, `adr/ADR-0005-data-access-and-blocker.md`.

## What the journey times mean

A journey time is the fastest service in the feed, with one change allowed by
default. Pass `--date YYYY-MM-DD` and the search honours each schedule's service
days, its date range, and its STP indicator, so an overlay replaces the train it
covers and a cancellation removes it. Without a date the search reads every
schedule, which suits the Stage 1 coverage count and is wrong for a specific
Saturday. Bank holidays are not interpreted yet, so a schedule that skips them
will appear on one. `adr/ADR-0006-timetable-layer.md` and
`adr/ADR-0008-date-aware-services.md` list every approximation and what removes
it.

## Why the onward search stops at 200 departures

A one-change journey is found by looking for an onward train at every place the
origin can reach. The search considers the 200 earliest departures at each
interchange. That number was measured, not guessed: on a hub-and-spoke network,
where every journey past the hub needs a change, capping at 60 dropped ten of
thirty journeys while saving under a millisecond, and capping at 200 dropped
none. Measurements for both feed shapes are in
`adr/ADR-0009-onward-departure-cap.md`, and `test_benchmark.py` fails if the
value changes without the argument changing with it.

## Files

| File | Purpose |
|---|---|
| `atoc_fares.py` | Fares feed parser and the budget query |
| `atoc_timetable.py` | CIF timetable parser, journey and reachability queries |
| `grantham_sweep.py` | CLI: every destination in a budget, with journeys |
| `feed_audit.py` | CLI: what each feed contained and where they disagree |
| `sanity_report.py` | CLI: whether a budget count can be believed |
| `damage_feed.py` | Writes deliberately damaged copies of a feed |
| `retailer.py` | Builds the outbound ticket links, with tracking off by default |
| `parse_report.py` | Shared parse counters and the streaming line reader |
| `make_synthetic_feed.py` | Builds invented fares and timetable feed folders |
| `benchmark.py` | Measures the onward departure cap against an uncapped search |
| `build_demo_page.py` | Writes the self-contained demo page from the feeds |
| `check_commit_message.py` | Checks a commit message against the convention |
| `test_atoc_fares.py` | Ten tests against the synthetic fares feed |
| `test_atoc_timetable.py` | Thirteen tests against the synthetic timetable |
| `test_grantham_sweep.py` | Two tests for the fare and service merge |
| `test_feed_audit.py` | Nine tests for the audit and for damaged input |
| `test_benchmark.py` | Ten tests for the feed shapes and the cap measurement |
| `test_build_demo_page.py` | Nine tests for the page payload and template |
| `test_fare_shapes.py` | Sixteen tests for route codes, shared station codes, and the skip tally |
| `test_damaged_feed.py` | Twenty tests for damaged input |
| `test_sanity_report.py` | Fourteen tests for the count report |
| `test_retailer.py` | Fifteen tests for the ticket links |
| `test_commit_message.py` | Eleven tests for the message checker |
| `stage-1-results.md` | Stage 1 findings, evidence, and residual risks |
| `glossary.md` | Domain terms |
| `CONTRIBUTING.md` | Commit convention and how to run the tests |
| `adr/` | Decisions, numbered, newest last |

## When the account clears

1. Put the fares feed in `feeds/fares` and the timetable feed in
   `feeds/timetable`. Both accept a folder or a zip, and a folder holding the
   zip.
2. Run `python feed_audit.py --feed feeds/fares --timetable feeds/timetable`
   and read the rejected count and the unopened files before any total. A feed
   that did not load looks exactly like a feed that is empty.
3. Run `python sanity_report.py --feed feeds/fares --timetable feeds/timetable
   --origin GRN --budget 20` and read what the count left out.
4. Check the licence text for commercial use, which decides whether ADR-0003
   can proceed.
5. Run the sweep for the Stage 1 count that decides go/no-go.

The four readings in the sanity report are not four answers to one question.
They are one question asked in four ways, and the gap between them is the part
worth reading.

## Commit convention

Commits follow Conventional Commits 1.0.0. `CONTRIBUTING.md` holds the rules,
and `check_commit_message.py` checks a message against them.

```
git log -1 --format=%B | python check_commit_message.py
```

## The demo page

`build_demo_page.py` writes one self-contained HTML file: every priced
destination from an origin, with a budget slider, a city or town filter, and a
choice of whether the budget covers one adult or two on a Two Together Railcard.
The page is generated from a feed rather than hand-written, so the real feeds
replace the synthetic ones with no change to the page.

```
python make_synthetic_feed.py _demo_feed --unserved-station
python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRN --out demo.html
```

Each destination carries a link to a ticket seller and an expander listing the
next few journeys. The link sends the origin, the destination, the date if the
page was built with one, and the party size. It does not send a railcard, because
no seller documents a parameter for one, and it does not send a chosen train,
because the fare is a walk-up fare valid on any of them. The page says both
these things rather than leaving the reader to find out.

Affiliate tracking is **off by default**, and turning it on wraps the link in a
network redirect rather than changing the search:

```
python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN --provider trainline
python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN \
  --provider trainline --affiliate-network partnerize --advertiser-id <id> --publisher-id <id>
```

The page is not deployed. `adr/ADR-0010-demo-page-before-the-gate.md` records why
it exists before the go/no-go gate opens, and `adr/ADR-0014-ticket-links.md`
records which seller is the default, what a link may carry, and why the tracked
version must not be published until the licence text is read.

## Run it

```
python make_synthetic_feed.py _demo_feed --unserved-station
python -m unittest discover -p "test_*.py"
python feed_audit.py --feed _demo_feed --timetable _demo_feed
python grantham_sweep.py --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20 --adults 2 --railcard "Two Together"
python grantham_sweep.py --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20 --date 2026-09-27
```

To measure the journey search, build an invented feed of the shape you want,
replace it with the downloaded feeds once they land, and name a real origin:

```
python benchmark.py --shape hub_spoke --stations 300 --schedules 8000 --caps 0,60,200 --transfer-only
python benchmark.py --feed feeds/fares --origin GRN --queries 40 --caps 0,60,200 --transfer-only
```

To question a count, and to break a feed on purpose:

```
python sanity_report.py --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20
python damage_feed.py --list
python damage_feed.py _demo_feed _damaged crlf
python damage_feed.py _demo_feed _damaged truncated_record --target ffl
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
