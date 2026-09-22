# Train Budget Explorer

**Status:** Stage 1 in progress. Both parser layers are built, hardened against
damaged input, date-aware when asked, and covered by 186 tests. The journey
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
| `fuzz_feed.py` | Mutates a feed at random and checks the parser's invariants |
| `retailer.py` | Builds the outbound ticket links, with tracking off by default |
| `check_links.py` | CLI: whether each seller's link lands on a search, proved only where it can be |
| `parse_report.py` | Shared parse counters and the streaming line reader |
| `make_synthetic_feed.py` | Builds invented fares and timetable feed folders |
| `benchmark.py` | Measures the onward departure cap against an uncapped search |
| `build_demo_page.py` | Writes the self-contained demo page from the feeds, or the whole per-station set with `--all-origins` |
| `check_commit_message.py` | Checks a commit message against the convention |
| `test_atoc_fares.py` | Ten tests against the synthetic fares feed |
| `test_atoc_timetable.py` | Thirteen tests against the synthetic timetable |
| `test_grantham_sweep.py` | Two tests for the fare and service merge |
| `test_feed_audit.py` | Nine tests for the audit and for damaged input |
| `test_benchmark.py` | Ten tests for the feed shapes and the cap measurement |
| `test_build_demo_page.py` | Thirty-nine tests for the page payload, template, licence slot, copy control, and the origin picker |
| `browser_test.cjs` | Playwright test: drives the generated page in a real browser |
| `test_fare_shapes.py` | Sixteen tests for route codes, shared station codes, and the skip tally |
| `test_damaged_feed.py` | Twenty tests for damaged input |
| `test_sanity_report.py` | Fourteen tests for the count report |
| `test_retailer.py` | Twenty-one tests for the ticket links |
| `test_check_links.py` | Fourteen tests for the link checker's verdicts |
| `test_fuzzed_feed.py` | Fifteen tests for the accounting and the fuzzer |
| `test_commit_message.py` | Eleven tests for the message checker |
| `stage-1-results.md` | Stage 1 findings, evidence, and residual risks |
| `publish-checklist.md` | The licence, attribution, and fee checks that must pass before a tracked link goes live |
| `launch-checklist.md` | Where the page goes, how the result is measured, and what the October review reads |
| `glossary.md` | Domain terms |
| `CONTRIBUTING.md` | Commit convention and how to run the tests |
| `adr/` | Decisions, numbered, newest last |

## When the account clears

1. Put the fares feed in `feeds/fares` and the timetable feed in
   `feeds/timetable`. Both accept a folder or a zip, and a folder holding the
   zip. **Grantham's real station code is `GRA`, not the `GRN` the synthetic feed
   invents**, so every command below that reads the real feeds uses `GRA`. The
   synthetic commands keep `GRN` because the synthetic feed is the thing that
   has it.
2. Run `python feed_audit.py --feed feeds/fares --timetable feeds/timetable`
   and read the rejected count and the unopened files before any total. A feed
   that did not load looks exactly like a feed that is empty.
3. Run `python fuzz_feed.py --feed feeds/fares --rounds 500` and read anything it
   reports. It is the only thing that will exercise the real feed's encodings and
   record shapes against a parser written without them.
4. Run `python sanity_report.py --feed feeds/fares --timetable feeds/timetable
   --origin GRA --budget 20` and read what the count left out.
5. Check the licence text for commercial use, which decides whether ADR-0003
   can proceed, and whether the tracked links ADR-0014 builds may be published.
6. Run the sweep for the Stage 1 count that decides go/no-go.

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
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRA --out demo.html
```

Each destination carries a link to a ticket seller and an expander listing the
next few journeys. **By default that link is the seller's own search page**, with
no journey on it, because no seller's parameterised link is known to land on a
search (ADR-0017) and a reader sent to "No matching journeys found" does not
conclude that the seller is broken. The page says what the reader has to fill in,
and that the price is the same at any seller, so the cost is stated rather than
discovered.

`--link-mode deep` sends the origin, the destination, the date if the page was
built with one, and the party size, and opting in asserts that somebody has opened
that link and seen a search. What a link never carries, either way: a railcard,
because no seller documents a parameter for one, and a chosen train, because the
fare is a walk-up fare valid on all of them.

Because the default link carries nothing, each row offers a **Copy** control that
puts the four things a seller asks for — from, to, date, and party size — on the
reader's clipboard, naming the Two Together Railcard as something to tick when the
price on screen is the railcard price. If the browser refuses clipboard access,
which it does for a page opened straight from disk, the text appears under the row
and the button says so instead of the page claiming a copy that did not happen.

### One page per station

The origin is the artifact's identity (ADR-0019): each page is *about* one station,
and choosing a different one is navigation, not a filter. Every page carries a
**Change** control beside the heading that opens a search over the other priced
stations — by name or three-letter code — and each option links to that station's
own page at a readable address (`/from/nottingham/`). The root address of a full
build is the chooser itself, ranked by how many destinations each station's build
actually priced. Nothing is stored: the URL is the only memory, which also makes it
the shareable address a community post can carry.

```
python build_demo_page.py --feed _demo_feed --timetable _demo_feed --origin GRN --out _site/index.html --all-origins
```

writes one self-contained page per priceable station under `_site/from/<slug>/`
plus the chooser at `_site/index.html`. The picker's station list is built from the
outputs the build actually wrote, so no option can point at a page that does not
exist, and slug collisions between same-named stations are resolved with the CRS
code at build time. The picker cannot offer "nearest station": the fare feed
records no county, region, or coordinates for a station, only its name and code.

### What leads, and what an unpriced page says

The controls panel states the page's order of decisions. The **budget leads** — the
widest column and the largest type on the page — because the price is the question
the reader arrived with. The party switch and the town filter share one quieter
secondary column: they refine the budget rather than compete with it. On phones the
panel stacks with the budget first.

Row actions (the departures expander, Copy, and the Tickets link) keep small visible
marks so they fit beside each other, and reach the 44px touch guideline through
invisible hit-area padding around each control.

A station the build could not price gets a different page from one whose prices sit
outside the budget: instead of a slider over an empty table, the page says *"We
couldn't price any journeys from X (CODE) in this feed."*, links the chooser when
other priced stations exist, and hides the controls, because a budget is not a
question that can be answered there. The build prints a note in that case, so the
operator sees it too.

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

Three further switches exist for when the terms are read:

```
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRA \
  --attribution "Contains data licensed from Rail Delivery Group"   # the licence wording
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRA \
  --link-mode deep                                                  # opt in once a link is verified
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRA \
  --analytics-snippet counter.html                                  # counting referrers
```

Neither seller's link is currently known to land on a search. To see that stated
rather than claimed:

```
python check_links.py --origin GRA --destination NOT
python check_links.py --provider trainline --mode fallback
```

The checker can prove a link is broken and cannot prove one works, so a `blocked`
or `inconclusive` verdict still needs a person to open it.
`adr/ADR-0017-what-the-live-link-check-found.md` records what it found.

The page is the whole product, and none of the Python tests opens a browser, so
one test drives it in a real one:

```
npx --yes --package playwright node browser_test.cjs
```

It drags the budget slider to the floor, filters to a town, follows a ticket link
(to a stub, so nothing depends on a seller being up), and reads back what the
**Copy** control puts on the clipboard. It exits 2 and says SKIPPED when playwright
is missing rather than passing quietly. It earned its place immediately: the copy
control shipped with a newline inside a JavaScript string literal, which took the
whole page down while every Python test still passed.

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
python benchmark.py --feed feeds/fares --origin GRA --queries 40 --caps 0,60,200 --transfer-only
```

To question a count, and to break a feed on purpose:

```
python sanity_report.py --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20
python damage_feed.py --list
python damage_feed.py _demo_feed _damaged crlf
python damage_feed.py _demo_feed _damaged truncated_record --target ffl
python fuzz_feed.py --feed _demo_feed --rounds 200 --seed 1
python fuzz_feed.py --feed feeds/fares --rounds 500 --seed 1 --keep _fuzz_failure
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
