# ADR-0077: A page lists the places it prices most cheaply

**Status:** Accepted
**Date:** 24 October 2026
**Relates to:** ADR-0076 (a page lists the places a journey reaches), ADR-0069 (the wire form), ADR-0046 (a row list ships as a table and a pool), `docs/audits/2026-10-23-page-byte-budget.md`

## Context

ADR-0069 and ADR-0076 took a release-shaped Grantham page from 1,368,721 to
373,396 bytes. Twelve release-shaped pages measured on 24 October 2026 still
average **407,289 bytes**, so 2,930 of them are **1,138 MiB** of HTML against the
800 MiB gate `tools/page_bytes.py` holds the site to and the host's 1 GiB.

The three fare lists are **36% of the largest page**. They are three different
fares to the same place, so no encoding removes them: merging them into one row
per place serves the same filters and saves only the repeated place key, **2.9%**
(`docs/build-performance-findings.md`). The one version of that saving that keeps
every ticket-mode filter is fewer places.

## Decision

A page lists **at most 600 places**, ranked by the cheapest standard adult fare
it prices, and says where it stops.

Seven rules hold the decision together:

1. **A place, not a fare.** Every fare list is cut to the same places, so a place
   keeps every fare it has. A single, an Anytime return and a return are still
   three rows for a place that has all three, and each mode still means "every
   fare of this kind to a place this page lists".
2. **Ranked by the fare the page opens on.** The ranking is the cheapest standard
   adult fare, which is the fare the opening mode picks with. Every fare below
   the stop is therefore unchanged, and the page answers every budget up to its
   stop exactly as it did before the cap. Ties go to the station code, so two
   builds of one feed put a place on the same page.
3. **A railcard cannot move it.** The ranking is the build's standard fare, not a
   reader's card price, so the page a reader arrives at does not depend on which
   card they hold. The cost is that a place a card would make cheaper than a
   listed row stays off the page.
4. **The service week narrows with the rows.** The build already cut an answer for
   a place the page no longer lists; a capped page pays nothing for the places it
   stops listing, which is where the saving comes from.
5. **The page says where it stops.** The payload carries
   `cappedDestinationCount`, counted apart from `unreachableDestinationCount`
   because "no journey reaches it" and "it is dearer than the last place this page
   lists" are different reasons. The coverage line names the count and the rule.
6. **The budget ceiling is the stop.** The ceiling is composed from the rows, so it
   falls to the dearest listed fare and a reader cannot ask for a fare the page
   has stopped listing. No second number is carried for a range the page cannot
   show.
7. **A build flag, set by the release.** `--max-places N`; `tools/release/share.py`
   passes `PLACE_CAP = 600`, and the synthetic fixture and the unit builds pass
   nothing, so their pages hold every place the feed prices.

## Evidence

Measured on the twelve release-shaped pages of the 23 October 2026 audit, built
24 October 2026, `python -m tools.measure_place_cap --site _scratch`. At no cap
the tool reproduces each page byte for byte, which is the check that it measures
the page it replaces.

| Places a page lists | Mean page | Mean gzip | 2,930 pages | Of the 800 MiB budget |
|---|---:|---:|---:|---:|
| no cap | 407,289 | 87,144 | 1,138 MiB | 142% |
| 700 | 289,101 | 63,598 | 808 MiB | 101% |
| **600** | **265,946** | **58,713** | **743 MiB** | **93%** |
| 500 | 236,344 | 52,696 | 660 MiB | 83% |
| 400 | 207,034 | 46,860 | 579 MiB | 72% |

- **600 lands the sample 7% inside the budget**, and 700 is its edge (808 MiB
  against 800), so a whole-network run could justify about 650 and no more on this
  mean.
- **The twelve pages list 6,647 of the 12,579 places they price and reach** --
  53%. From Manchester Piccadilly the page stops at **£47.40** where the feed
  prices £186.30, from Sheffield £54.50, from Grantham £72.40, from Plymouth
  £138.90; Ipswich (380 places) and Linlithgow (267) are untouched.
- **The hand-checked fares stay inside it.** Grantham's four `tests/known_fares.toml`
  rows are to Nottingham and Skegness, which rank **19th and 100th** of its 1,027
  places, so `tools/check_known_fares.py` reads the same pages it always did.

## Consequences

- **A page no longer answers a long journey.** That is the product cost: from a
  big station the cap bites hardest, and everything above the stop is off the
  page rather than priced and unreachable. The picker still reaches every station
  page, so what is lost is discovery from this page, not the network.
- **The page no longer states the station's range of fares.** It says where it
  stops instead; the budget control's ceiling is that stop.
- **The chooser's number follows the page, so it reads 600.** The all-origins
  build already replaced each index entry's planned count with
  `places_in_payload` (ADR-0076 rule 5), so a release's station list counts
  what its pages list. A reader choosing Manchester Piccadilly now sees the
  number of places its page carries rather than everything the feed prices from
  there, which is the same claim the page makes.
- **A browser shape test found a stale-page hole.** The reviewed-name shape page
  prices from an origin whose every place was unreachable after ADR-0076, so the
  shape build wrote no page and `tools/verify.py --browser` drove the page an
  earlier run had left behind, with a script this tree no longer writes. The
  fixture now gives that origin its trains, `tools/verify.py` clears its fixture
  sites before building, and the suite's page list fails rather than passing on a
  page no build wrote.
- **The number is the sample's, not the network's.** `python -m tools.page_bytes
  --site _site` on a whole-network run still decides whether 600 is enough; the twelve
  pages are a spread of small, medium and large stations rather than a random
  draw.
