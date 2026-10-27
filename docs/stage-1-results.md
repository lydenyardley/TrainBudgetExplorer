# Stage 1 results: data access and a working fares parser

**Date:** 21 September 2026
**Gate from ADR-0004:** verify licences, get a fares sample, and compute the real
count of Grantham destinations under £20 return per adult. Go/no-go follows.

## Outcome in one line

The parser is built and verified. On 21 September the account was registered
but its DTD fares/timetable selection was not yet confirmed, because the
Knowledgebase URLs supplied for the project are a different subscription. That
gate has since closed; see "Data access, confirmed" below. The zero-cost DTD
route and its caveats are recorded in `docs/dtd-licensing-and-data-access.md`.

> **Status, 27 October 2026:** the account holds the **Fares, Routeing Guide and
> Timetable data** entitlement, and the Grantham under-£20 count is unblocked.
> Nothing in this document is waiting on data access.

## What is reachable without an account

| Source | Result | Evidence |
|---|---|---|
| `data.atoc.org` (historic fares host) | Dead, no response | `curl -sIL https://data.atoc.org/` returned nothing, twice |
| `opendata.nationalrail.co.uk` | Live, JavaScript app, National Rail Data Portal | HTTP 200, HTML shell, title "National Rail Data Portal" |
| `raildata.org.uk` (Rail Data Marketplace) | Live, JavaScript app | HTTP 200, HTML shell referencing `index-0f64132b.js` |
| `api.raildata.org.uk` (its data API) | Unreachable from this machine | `curl` exit with HTTP code 000 on four paths |
| Marketplace licence text | Not readable without a session | Every path returns the same HTML shell |

**Inferred, not observed:** the fares and timetable products are only available
after signup and licence acceptance, so the licence question stays open until
the owner signs in. Search results describe marketplace licences as "generally
free of charge", which is second-hand and not a substitute for the licence text.

## What was built

The fares feed format is documented well enough to parse without the data. Field
layouts came from the open-source `pashri/atoc` parser (a Python port of James
Smith's PHP feed parser), read this session from `raw.githubusercontent.com`.

| File | Purpose |
|---|---|
| `atoc_fares.py` | Fixed-width parser plus the budget query. Reads `ffl` (flows and fares), `loc` (stations), `tty` (ticket types), `rlc` (railcards), `rcm` (railcard minimum fares). Handles folders and zips, and honours `A`/`U`/`D` update markers. |
| `grantham_sweep.py` | The go/no-go instrument. One origin, one budget, prints and optionally writes every destination inside it. |
| `make_synthetic_feed.py` | Writes an invented feed folder in the real record layouts. |
| `tests/test_atoc_fares.py` | Fares parser tests, every assertion a literal value. |

Modelling choices worth knowing:

- Cheapest standard-class **return** per destination. First class and singles are
  filtered out, not merely outscored.
- The railcard price is compared against the standard price and the cheaper wins,
  because a cardholder can always decline the discount. A minimum-fare floor can
  make the railcard price *worse* than the standard fare, and the code reports
  both rather than hiding that.
- The "1/3 off" rule is hardcoded as a documented assumption with the feed's own
  `dis` and `frr` files named as the accuracy upgrade path.

## Evidence

```
=== TESTS ===
Ran 10 tests in 0.043s
OK

=== DEMO SWEEP (synthetic data) ===
feed: 6 stations, 6 flows, 9 fares
origin: GRN GRANTHAM
budget: £20.00 per adult, 2 adult(s), railcard: Two Together
destinations under budget: 3

CRS station                per adult    party  ticket
NOT NOTTINGHAM                 £7.75   £15.50  CDR off-peak
LCN LINCOLN                    £8.70   £17.40  SDR
PBO PETERBOROUGH              £14.95   £29.90  SDR
```

Those stations and prices are invented. The output proves the pipeline runs from
feed files to a ranked list. It proves nothing about real Grantham fares.

## Residual risks

1. **Real-file quirks.** Line endings, padding, and header records are handled by
   construction, not by observation. First run against the real feed is the test.
2. **Local fares and route variants.** A destination can hold several flows with
   different route codes. The query takes the cheapest, which slightly
   under-states the price for a specific permitted route.
3. **`rcm` does not mark deletions.** The file carries no update marker, so an
   incremental update cannot retract a minimum fare. Full feeds are unaffected.

## Later the same day: hardening for the first real run

Both parsers were rebuilt to stream their input, decode each line as UTF-8 with a
latin-1 fallback, and count what they handled and rejected. `feed_audit.py`
prints that report alongside the coverage gaps between the two feeds. The suite
went from 21 tests to 41.

Running the audit against a folder holding both feeds found a real defect. The
timetable loader was reading the fares files as station records, because a fares
record also begins with an update marker, and it reported sixteen stations when
five existed. File classification now requires the four spaces that follow a
station name record type, and a test covers the combined folder.

## Data access, confirmed

This section once named the remaining data action: confirm that the account
holding the Knowledgebase subscriptions also includes **Fares, Routeing Guide
and Timetable data**. It does, and the evidence is observed rather than
inferred:

- `feeds/download-manifest.json` records the fares and timetable static feeds
  downloaded from the DTD endpoints on 24 September 2026, which only that
  selection serves.
- Every "build and publish" run downloads both DTD feeds with the repository's
  `NRDP_USERNAME` and `NRDP_PASSWORD` secrets, in the build job and in every
  shard, and audits them before anything reads them; a shard without them
  stops. [Run 40477635371](https://github.com/lydenyardley/TrainBudgetExplorer/actions/runs/40477635371) (commit `1fdd15c`, 27 October 2026)
  did that, passed the release-clearance check and published, as the runs of
  25 and 26 October did before it.

The Grantham count needs no further access. With `NRDP_USERNAME` and
`NRDP_PASSWORD` in the local environment, run:

```bash
python -m trainbudget.feeds.dtd_download
python -m trainbudget.feeds.dtd_audit
python -m trainbudget.measure.grantham_sweep --feed feeds/fares --origin GRA --budget 20 --adults 2 --railcard "Two Together"
```

The real Grantham code is `GRA`; `GRN` belongs only to the synthetic fixture.
The count printed by the sweep is the Stage 1 go/no-go input. The caveat still
holds for anyone repeating this on another account: a Knowledgebase download
alone neither proves the DTD entitlement nor can produce this count.
