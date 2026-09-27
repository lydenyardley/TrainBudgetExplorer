# Train Budget Explorer

**Status:** Stage 1 in progress. Both parser layers are built, hardened against
damaged input, date-aware when asked, and covered by automated tests. The journey
search is measured rather than tuned by feel, the demo page runs on the
synthetic feeds, and the count that decides go/no-go now comes with a report
that questions it. DTD download and audit tooling is now available; real fares
and timetable access still depends on the separate DTD subscription entitlement.
**Created:** 21 September 2026

## What this is

From any UK station, find every destination reachable for under a set budget
(e.g. "≤£20 return from Grantham"), with the journey time and the number of
changes. Prices are standard-class return fares; the page also shows a Two Together price
where the current DTD railcard restriction records permit that fare.

## Destination types

Destination metadata has one primary settlement class per station from ONS
Census 2021 built-up-area size bands, and any number of independent facets. A
city can also be coastal, a university town or an island without either value
replacing the other.

The primary class is the settlement's population band, and the labels say what
the bands are: `city` (100,000 and over, and 25,000–99,999), `town`
(10,000–24,999), `small_town` (5,000–9,999), `village` (under 5,000) and
`other` for a station whose settlement the workbook does not name at all.
Folding the two smallest bands into one "town" is what left villages filed as
"other"; Ancaster and Bottesford are both `village` now. `other` is still the
payload value for an unnamed settlement, but it is no longer a filter chip:
**No settlement band** read as unfinished work rather than a choice. A
reviewed list covers the places a page prices, so Newcastle is a city, an
airport station is an airport, and Attenborough is a village.

Every facet is one entry in `DESTINATION_FACET_SOURCES` in `atoc_fares.py`:
the label, the dataset it comes from, where that dataset lives, what geography
it covers, and the reader that turns it into settlement names. The filter chips,
the page payload, the generated cache's provenance and the checked-in reference
data are all derived from that list, so adding a sourced type does not mean
finding a second place to remember. The current facets:

| Facet | Source | Coverage |
| --- | --- | --- |
| `seaside` | ONS Census 2021 coastal communities built-up areas | England and Wales |
| `university` | UK Learning Providers, universities keyed by UKPRN and HESA provider id | United Kingdom |
| `heritage` | UNESCO World Heritage List, UK properties, with a reviewed list of the stations they are reached from | United Kingdom |
| `island` | reviewed station list (see below) | England, Wales and Scotland, as the DTD feed covers them |
| `airport` | reviewed list of rail stations serving a UK airport | United Kingdom, as the DTD feed covers them |
| `nature` | reviewed list of stations reaching The Wildlife Trusts' reserve sites and the WWT wetland centres, from the station each reserve or trust page names | United Kingdom, as the DTD feed covers them |
| `transport` | reviewed coach, tram, metro, stadium, and parkway or park-and-ride locations, matched from the feed's own station names | United Kingdom, as the DTD feed covers them |

`reference-data/destination-facets.json` is the checked-in, source-backed
mapping, and `tools/regenerate_destination_facets.py` rebuilds it from those
sources against a real fares download. A facet whose source is temporarily
unreachable can be carried forward with `--keep-unavailable`, which prints what
it could not read rather than writing a file that quietly lost it.


The `nature` list is a floor, and the tool that keeps it honest is
`tools/propose_nature_stations.py`. Given reserve pages it reads the station
each one names, matches it against the codes the feed carries, and prints every
proposal **with the sentence it came from**. It writes nothing: a proposal is not
a reviewed list, and only a person can say a reserve is worth a destination
category.

```
python tools/propose_nature_stations.py   --url https://www.wildlifetrusts.org/nature-reserves   --allow-host essexwt.org.uk --allow-host ywt.org.uk
```


## Fare-construction points are not places

The feed prices fares *through* things that are not stations. `BOUNDARY ZONE 4`
is where a fare changes from an inner to an outer London zone; `BRIGHTON
UNIZONE` and `METRO T&W ZONE A` are the same idea; `KINGS LYNN COACH` and
`DEREHAM (COACH)` are a coach stop standing in for the town it serves. No
train calls at any of them, so the page must not offer one as a destination to
be priced to or an origin to depart from, and the coverage report must not let
them top the "most reached" table.

They are a reviewed list, `FARE_CONSTRUCTION_CRS`, keyed by the feed's own CRS
rather than matched on the station name. A substring test over names looks
equivalent and is not: it would drop a real station the day anyone called one
Coach House, and it would stop catching a zone the day the feed renamed it. The
CRS is the feed's identity for a station, so a rename shows up as a dead code
instead.

The evidence that the list is current comes from
`tools/propose_fare_construction_stations.py`, which applies the name markers to
the feed's station records and prints every match with its code, marking which
are already reviewed and which are not. It writes nothing, for the same reason
the nature proposer does: a proposal is not a reviewed list. On the 24 September
2026 download it matched the twelve reviewed codes and nothing else — eight
zones, four coach stops — and it also reports the other direction, a reviewed
code that no longer matches any name, which is what a withdrawn zone looks like.

```
python tools/propose_fare_construction_stations.py --feed feeds/fares
```


Four limits worth stating plainly. `island` is a reviewed list, not an
official one: no UK open dataset names island *settlements* at a size this page
cares about, so the entry says so in its own `source` text. `transport` and
`nature` are reviewed too, and say so the same way: the coach, tram, metro and
parkway tags come from the feed's own station names, with a small list of
settlements the markers catch wrongly (Bushey, BUSBY, CAMBUSLANG and Shepherd's
Bush are places, not interchanges), and the nature tag only credits reserves a
Wildlife Trust or the WWT actually manages. `heritage` has a
reviewed settlement side for the same reason — UNESCO names whole properties,
not the towns inside them — but its site ids are checked against UNESCO's live
list on every build, so a delisted site stops tagging destinations and a
curated station name that no longer exists is reported rather than ignored.
The primary settlement classes come from ONS built-up-area population bands,
not from a general gazetteer: a real village or hamlet can therefore have no
band. Rather than showing **No settlement band**, the page keeps the `other`
value in the payload for auditing and covers the places it prices with a
reviewed list; a station-to-settlement or station-to-LSOA crosswalk is still
the honest way to close the remaining gap. TfL is not a source for any of this — its data covers Greater
London only, so it can describe London stations and nothing else in the
network. A page only offers the types its own destinations carry, because a
chip that can only ever return nothing reads as a broken control.

## Decided summary

- **What:** Grantham-only demo. Every destination reachable from Grantham under
  a budget (cheapest reviewed Anytime Day Return per adult), a destination-type filter,
  and a party total for two adults. Static data, honest disclaimers.
- **Hypothesis:** affiliate lead-gen asset (Trainline, applied post-launch).
- **Discovery:** communities first (r/uktrains, local FB groups, HN); SEO only
  after a community signal.
- **Scope:** Two Together is the only railcard in v1. Its one-third discount and
  feed minimum fare are shown only when the current DTD RR rules permit the
  fare's ticket, route, and endpoint locations.
- **Plan:** Stage 1 licence and data verification, then go/no-go, then a
  one-week build hard-stopped at 30 September, launch w/c 5 October, written
  review **21 October** with park-by-default if unsure.
- **Accepted tension:** this runs before Missing Music and The Family Apothecary
  are published. The owner chose that knowingly. Recorded in ADR-0004.

## Stage 1 status

- **Built:** `atoc_fares.py` answers budget queries from the fares feed, and
  `publishable_destinations_within` narrows a public price to reviewed exact
  ANYTIME DAY R tickets with blank restriction codes. `atoc_restrictions.py`
  parses the `.RST` restriction file behind that gate. `atoc_timetable.py`
  answers journey time, change count, and reachability from the CIF timetable
  feed. `grantham_sweep.py` joins them, `feed_audit.py`
  reports what a feed actually contained, `sanity_report.py` questions the count
  it produced, `benchmark.py` measures the journey search, `damage_feed.py`
  makes feeds go wrong on purpose, and `build_demo_page.py` writes the browsable
  page. The automated suite covers the parsers, audit, downloads, and page.
- **Data access:** `dtd_download.py` authenticates with environment-only
  credentials, validates each response, and writes atomic ZIPs under `feeds/`.
  The supplied Knowledgebase URLs are reference feeds; they do not establish
  access to the DTD fares/timetable subscription.
- **Blocked:** real fares and timetables still need the account's separate
  **Fares, Routeing Guide and Timetable data** entitlement. A missing entitlement
  is reported explicitly; it is never treated as an empty feed.
- **Not yet answered:** the real count of Grantham destinations under £20, and
  the final public-use/attribution checks for the DTD terms.
- **Details and evidence:** `docs/dtd-licensing-and-data-access.md`,
  `docs/stage-1-results.md`, and `adr/ADR-0005-data-access-and-blocker.md`.

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

The root holds the executable pipeline and its launchers. Automated tests live in
`tests/`; reader-facing prose lives in `docs/` (checklists, the glossary, the stage
report, the licence enquiry), one-off diagnostics and their tests in `tools/`, and
decisions in `adr/`. The root stays the build, not the filing cabinet.

| File | Purpose |
|---|---|
| `atoc_fares.py` | Fares feed parser, the budget query, and the publishable selector |
| `atoc_restrictions.py` | RSPS5045 `.RST` restriction parser and its publication gate |
| `atoc_timetable.py` | CIF timetable parser, journey and reachability queries |
| `grantham_sweep.py` | CLI: every destination in a budget, with journeys |
| `dtd_download.py` | Credential-safe NRDP/DTD and Knowledgebase downloader |
| `dtd_audit.py` | DTD archive validation plus the real fares/timetable audit |
| `feed_audit.py` | CLI: what each feed contained and where they disagree |
| `sanity_report.py` | CLI: whether a budget count can be believed |
| `damage_feed.py` | Writes deliberately damaged copies of a feed |
| `fuzz_feed.py` | Mutates a feed at random and checks the parser's invariants |
| `retailer.py` | Builds the outbound ticket links, with tracking off by default |
| `tools/check_links.py` | CLI: whether each seller's link lands on a search, proved only where it can be |
| `parse_report.py` | Shared parse counters and the streaming line reader |
| `destination_coverage.py` | Names the priced destinations no source could classify; a build prints the summary, `--fail-on-unsourced` turns it into a refusal, and `--unsourced-ceiling` holds the count |
| `make_synthetic_feed.py` | Builds invented fares and timetable feed folders |
| `benchmark.py` | Measures the onward departure cap against an uncapped search |
| `build_demo_page.py` | Writes the self-contained demo page from the feeds, or the whole per-station set with `--all-origins` |
| `page_templates.py` | The page's HTML/CSS/JS as fill-in templates (station page, chooser, privacy); `SHARED_CSS` is the one stylesheet every route inlines, so the three cannot drift (ADR-0033) |
| `build_workers.py` | The per-process feed cache and job function behind `--workers` |
| `tools/check_commit_message.py` | Checks a commit message against the convention |
| `tools/test_propose_nature_stations.py` | Proposer tests: host guard, name matching, and never writing a file |
| `tools/propose_nature_stations.py` | Reads Wildlife Trust and WWT reserve pages and proposes station codes, with the sentence each came from, for a person to review |
| `tools/propose_fare_construction_stations.py` | Applies the fare-construction name markers to the feed's stations and proposes codes, with the name that caught each, for a person to review |
| `tests/test_atoc_fares.py` | Fares parser and publishable-selector tests |
| `tests/test_atoc_restrictions.py` | `.RST` field offsets, real sample records, and the gate |
| `tests/test_atoc_timetable.py` | Timetable parser, TIPLOC normalisation, and journey tests |
| `tests/test_grantham_sweep.py` | Two tests for the fare and service merge |
| `tests/test_feed_audit.py` | Nine tests for the audit and for damaged input |
| `tests/test_dtd_download.py` | Downloader safety, authentication, validation, and DTD audit tests |
| `tests/test_benchmark.py` | Ten tests for the feed shapes and the cap measurement |
| `tests/test_build_demo_page.py` | Page payload, template, licence slot, copy control, and origin-picker tests |
| `feeds_cli.py` | Shared feed-argument parsing and loading for the CLI tools |
| `tests/browser_test.cjs` | Playwright test: drives the generated page in a real browser |
| `tests/test_fare_shapes.py` | Route codes, shared station codes, and the skip tally |
| `tests/test_damaged_feed.py` | Damaged-input tests |
| `tests/test_sanity_report.py` | Count-report tests |
| `tests/test_retailer.py` | Ticket-link tests |
| `tools/test_check_links.py` | Fourteen tests for the link checker's verdicts |
| `tests/test_fuzzed_feed.py` | Accounting and fuzzer tests |
| `tools/test_commit_message.py` | Commit-message checker tests |
| `tests/test_destination_coverage.py` | Coverage-report tests: dedup, ranking, the summary, and the refusal |
| `docs/dtd-licensing-and-data-access.md` | DTD/KB licensing research, zero-cost conclusion, and entitlement caveats |
| `docs/stage-1-results.md` | Stage 1 findings, evidence, and residual risks |
| `docs/publish-checklist.md` | The licence, attribution, and fee checks that must pass before a tracked link goes live |
| `docs/github-pages-deployment.md` | GitHub Pages setup, safe Actions secrets, scheduled deployment, and troubleshooting |
| `docs/launch-checklist.md` | Where the page goes, how the result is measured, and what the October review reads |
| `docs/glossary.md` | Domain terms |
| `CONTRIBUTING.md` | Commit convention and how to run the tests |
| `adr/` | Decisions, numbered, newest last |

## Refreshing the real feeds

The DTD fares feed updates weekly and the public timetable daily, so "keeping up
with the data" is a repeat of this sequence whenever a new release matters:

```bash
python dtd_download.py
python dtd_audit.py
```

The downloader writes each ZIP atomically and records its non-secret URL, size,
and hash in `feeds/download-manifest.json`; the audit then checks the archive
before the page build reads it. Nothing in the repository schedules this. There is
no server and no cron job: the refresh is a deliberate manual run (or the CI
workflow, which rebuilds from a feed artifact when one is supplied), and a rebuild
is the only step that changes the published pages. The page's own provenance line
comes from the feed's `metadata.json`, so a refreshed build says which download it
was built from.

1. Set `NRDP_USERNAME` and `NRDP_PASSWORD` in the local environment. Do not put
   either value in a command, source file, or chat message. The `.env` pattern is
   ignored by this repository if a local environment file is preferred.
2. Download the DTD fares and timetable ZIPs:

   ```bash
   python dtd_download.py
   ```

   This writes `feeds/fares/dtd-fares.zip` and
   `feeds/timetable/dtd-timetable.zip`. Use `--dtd fares` or
   `--dtd timetable` while confirming entitlement, and `--kb` to download the
   supplied Knowledgebase XML feeds as well. The downloader never replaces an
   existing good archive with an error page, empty ZIP, or non-ZIP response.
3. Validate and audit the real pair:

   ```bash
   python dtd_audit.py
   ```

   This distinguishes missing, empty, invalid, and unrecognized downloads from
   a valid feed whose parser rejected records. It then prints the existing
   `feed_audit.py` report. **Grantham's real station code is `GRA`, not the
   `GRN` the synthetic feed invents.**
4. Run `python fuzz_feed.py --feed feeds/fares --rounds 500` and read anything it
   reports. It is the only thing that will exercise the real feed's encodings and
   record shapes against a parser written without them.
5. Run `python sanity_report.py --feed feeds/fares --timetable feeds/timetable
   --origin GRA --budget 20` and read what the count left out.
6. Check the current DTD/NRE terms, brand treatment, commercial-use permission,
   and affiliate disclosure before publishing. The research and escalation route
   are in `docs/dtd-licensing-and-data-access.md`.
7. Run the sweep for the Stage 1 count that decides go/no-go.

The Knowledgebase URLs can be downloaded independently, but they contain
reference/service information rather than the DTD fares and timetable. A token
for those URLs is not proof of DTD entitlement.

The four readings in the sanity report are not four answers to one question.
They are one question asked in four ways, and the gap between them is the part
worth reading.

## Commit convention

Commits follow Conventional Commits 1.0.0. `CONTRIBUTING.md` holds the rules,
and `tools/check_commit_message.py` checks a message against them.

```
git log -1 --format=%B | python tools/check_commit_message.py
```

## The demo page`build_demo_page.py` writes one self-contained HTML file: every priced destination
from an origin, with a budget slider, a settlement and character destination-type filter,
and a choice of whether the budget covers one adult or two. The page is generated from

a feed rather than hand-written, so the real feeds replace the synthetic ones
with no change to the page. Prices come only from the reviewed Anytime Day
Return selector; the builder refuses to run without a clean `.RST` file.

```
python make_synthetic_feed.py _demo_feed --unserved-station --third-origin
python build_demo_page.py --feed _demo_feed --timetable _demo_feed --all-origins --out _demo_site/index.html
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
reader's clipboard, saying that the railcard discount is not included and to tick
the Two Together box on the seller's site. If the browser refuses clipboard access,
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
plus the chooser at `_site/index.html`. For a real DTD fares feed, the faster
publication mode is:

```
python build_demo_page.py --feed feeds/fares --fast-all-origins --out _site/index.html
```

`--fast-all-origins` is deliberately prices-only (it ignores `--timetable`),
uses parallel workers by default, reports station discovery and page progress,
and writes each page atomically. It keeps `.trainbudget-build.json` beside the
output; rerunning the same command resumes from that checkpoint, while a feed,
configuration, or station-index change starts a new build. The chooser's starting
budget is carried into station-page URLs, so the page and its title use the same
initial amount. The fast build also persists feed-fingerprinted per-origin fare
indexes in `_cache/`: workers load the shared location/ticket/restriction
metadata once and apply only the fares relevant to each page, rather than
reparsing the complete DTD feed in every worker. The picker's station
list is built from the outputs the build actually wrote, so no option can point
at a page that does not exist, and slug collisions between same-named stations
are resolved with the CRS code at build time. The picker cannot offer "nearest
station": the fare feed records no county, region, or coordinates for a station,
only its name and code.

Build caches live in `_cache/` (git-ignored): the shared feed metadata and
per-origin fare indexes the workers restore, and the timetable pickles a
single-origin build keys by the feed's bytes and its focus stations. Every
build that reads or writes a timetable pickle then keeps the newest two per
origin — the caches it just used are protected — and deletes the older
digests, so a feed refresh no longer strands the previous 100MB file for
someone to remove by hand.

### Opening the pages yourself

There is no `index.html` in the repository on purpose. The pages are build output:
`.gitignore` excludes `_site/`, `demo*.html`, and the generated feeds, because a
committed copy would drift from the builder the first time the feed changed and
would read as a source of truth it is not. Build it, then serve it:

```
python build_demo_page.py --feed _demo_feed --timetable _demo_feed --all-origins --out _site/index.html
python -m http.server 8000 --directory _site
# then open http://localhost:8000/
```

Serve it rather than double-clicking the file. Station links are root-absolute
(`/from/grantham/`), which is what a real host needs and what the file system
cannot resolve; the build prints that reminder when it finishes. The server also
serves a build you already have — `_site/` may hold pages from an earlier run, and
the build names any it did not rewrite instead of deleting them for you.

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
couldn't price any journeys from X (CODE) in this feed."*, follows it with why —
the feed reaches a number of standard-return destinations but the cheapest fare to
every one of them is an ITX placeholder, or flows exist but none prices a
publishable fare, naming the top rejection reasons — links the chooser when other
priced stations exist, and hides the controls, because a budget is not a question
that can be answered there. The footer only suggests raising the budget when there
are destinations to raise it toward. The build prints a note in that case, so the
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
  --analytics-snippet counter.html \
  --measurement-plan aggregate-referrer-counts                       # opt in to measurement
```

A snippet is refused without `--measurement-plan`: the plan names what the
snippet measures, what it keeps, and for how long, and the privacy page prints
that sentence. There is one plan today and nothing is measured — turning
measurement on is a decision, recorded in
`adr/ADR-0032-measurement-needs-a-written-plan.md`, not a flag somebody reaches
for.

Neither seller's link is currently known to land on a search. To see that stated
rather than claimed:

```
python tools/check_links.py --origin GRA --destination NOT
python tools/check_links.py --provider trainline --mode fallback
```

The checker can prove a link is broken and cannot prove one works, so a `blocked`
or `inconclusive` verdict still needs a person to open it.
`adr/ADR-0017-what-the-live-link-check-found.md` records what it found.

The page is the whole product, and none of the Python tests opens a browser, so
one test drives it in a real one:

```
npx --yes --package playwright node tests/browser_test.cjs
```

It drags the budget slider to the floor, filters to a town, follows a ticket link
(to a stub, so nothing depends on a seller being up), and reads back what the
**Copy** control puts on the clipboard. It exits 2 and says SKIPPED when playwright
is missing rather than passing quietly. It earned its place immediately: the copy
control shipped with a newline inside a JavaScript string literal, which took the
whole page down while every Python test still passed. It is also the only cover
for what the generated JavaScript *does* — `page_templates.py` deliberately has
no unit tests of its own, a decision recorded in
`adr/ADR-0027-browser-suite-covers-the-template.md`.

## The real-data build, end to end

When the licensed feeds land, this is the whole path from download to site. Each
step exists because skipping it has a specific failure mode.

**1. Put the feeds in place, and record where they came from.** The fares feed,
the timetable feed, and licence PDFs go in `feeds/` (git-ignored: it is licensed
data with unread redistribution terms). Beside them, one `metadata.json` records
provenance once, so every build reads it and no operator retypes it:

```json
{"source": "RSP fares feed", "downloaded": "3 October 2026"}
```

That file supplies the price line the page shows beside its prices ("Prices from
the RSP feeds, downloaded 3 October 2026."). `--price-source` overrides it;
`--feed-metadata <dir>` points at it when the file is not beside the feed.
Without either, the build reads the downloader's own `download-manifest.json` --
including one that sits two levels above a zipped feed, which is the real
`feeds/fares/dtd-fares.zip` layout. A build that finds neither, but can see the
feed is a DTD download (a manifest nearby, or `RJFAF*` members in the zip),
**refuses** rather than falling back to the synthetic default: calling real
fares "the synthetic demo feed" is the one claim this machinery exists to
prevent. A synthetic feed still gets the synthetic line, with a warning.

**2. Audit before trusting any number.**

```
python feed_audit.py --feed feeds/fares --timetable feeds/timetable
```

Read the rejected count and the `Files not opened` list first: a record that
never loaded is a destination that never appears, and an unrecognised format is
named there rather than silently counted as an empty download. Also check the
codes: the real CRS for Grantham is `GRA`, not the synthetic feed's `GRN`, and
the Easy Fares demo confirmed `GRN` resolves to Grindleford in the real database.

Two newer lines matter for a public price. `restrictions: files 1, records
468516, codes 841, railcard codes 331, rejected 0` must show a clean `.RST`
file; `publishable_destinations_within` refuses to run without one. And the
unresolved TIPLOCs are split into `location_record_without_crs` (1,070 real
operational locations on the current feed) and `no_record` (76), so the second
number is the one to investigate.

**3. Build one origin, and read the page as a reader would.**

```
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable --origin GRA \
  --notices rdg,ogl,accuracy --out demo.html
```

`--notices rdg,ogl,accuracy` composes the three licence obligations into the
footer: the Rail Delivery Group publisher credit (Data Sharing Agreement cl.
3.3.1), the Open Government Licence sentence (the timetable's licence), and the
accuracy-and-liability notice (cl. 3.3.2 with the licence's liability clause).
They are opt-in because crediting RDG above synthetic prices would be false
attribution — which is why the demo build carries none.

**4. Build the site.**

```
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable \
  --all-origins --notices rdg,ogl,accuracy --workers 8 --out _site/index.html
```

`--all-origins` writes one page per priceable station plus the chooser; it also
writes the privacy page the footers link to. `--workers 8` builds station pages
in parallel processes (each origin is independent). In `--fast-all-origins`
mode, workers use the persisted per-origin fare indexes described above. On a
host that does not serve the site at its domain root — a GitHub
Pages project site, most shared hosting — add `--base-path <name>` so every
internal link resolves.

**A public build is refused until it can answer for itself.** A build whose
prices come from a real feed (anything but the synthetic default) needs both a
licence or attribution notice and somebody to contact, and it stops before
writing a page if either is missing:

```
PRIVACY_CONTACT=privacy@example.org python build_demo_page.py \
  --feed feeds/fares --origin GRA --notices rdg,ogl,accuracy --out _site/index.html
```

The refusal names both conditions and the flag or variable that satisfies each,
because a gate an operator cannot act on is one they route around. A synthetic
demo build is exempt from the notice — it publishes invented fares and credits
nobody — and names the deployment operator's public repository issue tracker as
its contact so its page is never blank. The privacy page's list of what the
site does is generated from the same feature configuration the pages are built
from, so it cannot describe a site this build did not ship
(`adr/ADR-0032`; gates S36–S38 in the re-envision audit).

Every build also names the priced destinations no source could classify — the
stations the page's settlement filters therefore cannot return. The list is a
warning, because a full-network build legitimately meets stations nobody has
reviewed; `--fail-on-unsourced` turns it into a refusal for a release build,
checked before anything is written. Run the same check on its own, across the
whole feed, with `python destination_coverage.py --feed feeds/fares`.

Beside it the report names the rows that can never become a destination at all:
flows to an NLC the feed never locates, to a location with no station code, or
to a fare-construction point. No reviewed list closes that gap, because a flow
runs to an NLC the feed does not describe, so it is a fact about the feed
rather than a defect in the registry — but it is counted, so the two halves of
the coverage gap are never read as one.

**Two reviewed lists can go stale, and the build says so.** A classification
source that could not be read leaves the page with fewer filter chips than it
claims: `--require-classification` refuses to publish rather than shipping
them. A reviewed settlement-fallback code the feed does not carry is silent by
construction — the code is intersected away before it is applied, so the page
looks exactly as it did — which is why `--require-live-reviewed-codes` exists
and why the deploy workflow passes it. Neither flag is on by default: a
fuzzed, damaged or synthetic feed is *supposed* to be missing most of the
network, and refusing to build one would make the tools untestable. Both print
what they found either way.

**What the page must never claim without the things behind it:** a publisher
credit without `--notices` (or a custom `--attribution`) naming the licence
actually held; a price line without the feed's metadata or `--price-source`
saying where it came from; `--link-mode deep` without a verified link
(ADR-0017); an analytics snippet without a written measurement plan (ADR-0032);
or a public build without its licence notice and a privacy contact, which stops
the build rather than waiting to be noticed. A public price also needs the
reviewed selector, and the builder is wired to it now: every price in a page comes from
`publishable_destinations_within`, and the build refuses to write anything at all
when the fares feed carries no readable `.RST` restriction file (ADR-0025). Each
claim has a switch, and the page states what it
can back up and stays silent about the rest.

**Scale, re-measured on an invented feed shaped like the network (2,500
stations, 9,000 schedules) after the fares index landed (ADR-0024):** the
fares side is free — all 2,500 origins' prices resolve in 0.06s, and a
prices-only origin payload costs 0.03s, so a prices-only network republishes
in under two minutes. The journey search is the entire remaining cost: one
origin with journeys is ~9 minutes, making the full with-times build roughly
a two-day batch across 8 workers on this shape. The station chooser is not
the bottleneck: with all 2,500 stations embedded it renders in 0.01s (207 KB)
and filters in about 2ms in a real browser. Time one origin with `--origin
GRA` before committing to the full set, and treat the first real with-times
build as an overnight-plus batch job.

The site deploys through `.github/workflows/deploy.yml`: it builds the site,
runs the tests, and publishes to GitHub Pages, with the deploy step isolated so
any other host can consume the same artifact. It builds from the licensed feeds
only if they are supplied as a repository artifact (`FEEDS_ARTIFACT`); otherwise
it ships the demo feed, and the pages say so.

## Run it

**To open the app on this machine:** double-click `run.bat` (Windows), or run

```
python run.py
```

That builds the site from the current feed, serves it at
http://localhost:8741, and opens your browser. Close the window (or Ctrl+C) to
stop. Useful variants: `--port 9000`, `--no-build` (serve what's there),
`--timetable` with no value for a prices-only build, `--feed feeds/fares
--timetable feeds/timetable` for the real licensed feeds, and `--all-origins`
for every priced station (slow at network scale — ADR-0024). The demo feed is
rebuilt first if `_demo_feed/` is missing: `python make_synthetic_feed.py
_demo_feed --unserved-station --third-origin`.

The individual commands behind it, if you want them separately:
```
python make_synthetic_feed.py _demo_feed --unserved-station --third-origin
python build_demo_page.py --feed _demo_feed --timetable _demo_feed --all-origins --out _demo_site/index.html
python -m http.server 8000 --directory _demo_site   # then open http://localhost:8000/
python -m unittest discover -s tests -p "test_*.py"
python feed_audit.py --feed _demo_feed --timetable _demo_feed
python grantham_sweep.py --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20 --adults 2 --railcard "Two Together"
python grantham_sweep.py --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20 --date 2026-09-27
```

CI runs the same tests under a coverage floor, and you can run the chain locally:

```
python -m pip install coverage
python -m coverage run -m unittest discover -s tests -p "test_*.py"
python -m coverage run --append -m unittest discover -s tools -p "test_*.py"
python -m coverage report --fail-under=79 --precision=1
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
