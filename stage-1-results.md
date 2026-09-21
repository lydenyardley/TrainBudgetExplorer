# Stage 1 results: data access and a working fares parser

**Date:** 21 September 2026
**Gate from ADR-0004:** verify licences, get a fares sample, and compute the real
count of Grantham destinations under £20 return per adult. Go/no-go follows.

## Outcome in one line

The parser is built and verified. The data download is blocked on an account
only the owner can create. No anonymous, lawful route to the fares feed exists.

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
| `test_atoc_fares.py` | Ten tests, every assertion a literal value. |

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

## The single blocking action

The owner needs to create an account on `raildata.org.uk`, accept the licence for
the fares feed (and the timetable feed for Stage 2), download the current `RJFAF`
release, and drop the folder into the project. Then:

```
python grantham_sweep.py --feed <downloaded folder> --origin GRN --budget 20 --adults 2 --railcard "Two Together"
```

The count it prints is the Stage 1 go/no-go input. Everything else is ready.
