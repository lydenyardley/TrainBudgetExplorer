# Building the site: the demo page and the real release

The two builds: the browsable demo page, and the whole-network release the
deploy workflow publishes.

## The demo page

`trainbudget/build/build_demo_page.py` writes one self-contained HTML file: every priced destination
from an origin, with a budget slider, a settlement and character destination-type filter,
and a choice of whether the budget covers one adult or two. The page is generated
from a feed rather than hand-written, so the real feeds replace the synthetic ones
with no change to the page. The page opens on **the cheapest fare of any ticket
type** to each destination, composed in the page from the three sets it already
carries rather than chosen by the build, so the list answers the budget question
the reader arrived with; the builder still refuses to run without a clean `.RST`
file, and the reviewed Anytime Day Return selector, the broader "any return" set
the feed prices (restricted off-peak fares included) and outbound singles are the
three filters beside it. Whichever set is open, a line above the table says what
that set contains, because a restricted fare is not interchangeable with an
unrestricted one; and a row in the opening list names the ticket it is priced as,
which is what the count line's mix is counting.

```
python -m trainbudget.feeds.make_synthetic_feed _demo_feed --unserved-station --third-origin --return-network --long-list
python -m trainbudget.build.build_demo_page --feed _demo_feed --timetable _demo_feed --all-origins --out _demo_site/index.html
python -m trainbudget.build.build_demo_page --feed feeds/fares --timetable feeds/timetable --origin GRA --out demo.html
```

`--long-list` prices Grantham to more than twenty destinations, because the
table shows twenty rows before it offers a pager: without it no demo page has a
second page, and the pager's keys have nothing to turn.

Each destination carries a link to a ticket seller and one expander per row, holding
the next few journeys with the fare in words, the condition it carries, the
validity the feed states for it and the feed's own record. What is on the row
itself is the fare's code plus one word when the fare is one a reader should
open — `advance` or `restricted` — because the column that sentence used to
occupy said the same thing on all twenty rows (ADR-0040). **By default that link is the seller's own search page**, with
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

Because the default link carries nothing, each row's own details offer a **Copy**
control that puts the four things a seller asks for — from, to, date, and party
size — on the reader's clipboard, saying that the railcard discount is not included
and to tick the card on the seller's site. If the browser refuses
clipboard access, which it does for a page opened straight from disk, the text
appears under that button and the button says so instead of the page claiming a
copy that did not happen.

### One page per station

The origin is the artifact's identity (ADR-0019): each page is *about* one station,
and choosing a different one is navigation, not a filter. The heading is the page's
own sentence — *Train fares · up to £20 · from GRANTHAM* — and the station in it is
the control: the name wears the same accent and dashed underline as the budget
beside it, a drawn chevron says a list is behind it, and opening it searches the
other priced stations by name or three-letter code. On a build with one origin the
name stands as plain text instead, because a control that opens nothing is a
control that lies. The chooser is the same heading with the name replaced by a
field holding the word *station*, so the two routes read as one page
(`adr/ADR-0038-the-heading-names-the-mode.md` for the wording,
`adr/ADR-0039-the-chooser-and-a-station-page-are-one-page.md` for the rest). Each
option links to that station's own page at a readable address
(`/from/nottingham/`). The root address of a full build is the chooser itself,
ranked by how many destinations each station's build
actually priced. Nothing is stored: the URL is the only memory, which also makes it
the shareable address a community post can carry.

```
python -m trainbudget.build.build_demo_page --feed _demo_feed --timetable _demo_feed --origin GRN --out _site/index.html --all-origins
```

writes one page per priceable station under `_site/from/<slug>/` plus the chooser
at `_site/index.html`, and one `stations.js` beside them for the station picker:
the same list on every page, so it is one file rather than 2,712 copies. Each
page still carries its own destinations inline, and a page whose copy of the
list does not arrive states its station as text instead of offering a control
that opens nothing. For a real DTD fares feed, the faster publication mode is:

```
python -m trainbudget.build.build_demo_page --feed feeds/fares --fast-all-origins --out _site/index.html
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

Build caches live in `_cache/` (git-ignored): the shared feed metadata and one
per-origin fare index per station page, which every build writes and restores its
pages from, single-worker builds included -- that is what lets a whole fares feed
be released before the first page is rendered -- and the timetable pickles a
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
python -m trainbudget.build.build_demo_page --feed _demo_feed --timetable _demo_feed --all-origins --out _site/index.html
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

A row carries three controls and no more: the Tickets link, the departures
expander, and the shortlist toggle. The two actions that answer a question a reader
asks once they have decided — the railcard's Card details, and the Copy that
produces the handoff text — are inside the row's own details, beside the fare's
condition (ADR-0043); five controls a row, a hundred targets on page one, put the
price a reader came to compare in a cluster of buttons. What stays on the row keeps
a small visible mark and reaches the 44px touch guideline through invisible
hit-area padding around it.

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
python -m trainbudget.build.build_demo_page --feed _demo_feed --timetable _demo_feed --origin GRN --provider trainline
python -m trainbudget.build.build_demo_page --feed _demo_feed --timetable _demo_feed --origin GRN \
  --provider trainline --affiliate-network partnerize --advertiser-id <id> --publisher-id <id>
```

The page is not deployed. `adr/ADR-0010-demo-page-before-the-gate.md` records why
it exists before the go/no-go gate opens, and `adr/ADR-0014-ticket-links.md`
records which seller is the default, what a link may carry, and why the tracked
version must not be published until the licence text is read.

Three further switches exist for when the terms are read:

```
python -m trainbudget.build.build_demo_page --feed feeds/fares --timetable feeds/timetable --origin GRA \
  --attribution "Contains data licensed from Rail Delivery Group"   # the licence wording
python -m trainbudget.build.build_demo_page --feed feeds/fares --timetable feeds/timetable --origin GRA \
  --link-mode deep                                                  # opt in once a link is verified
python -m trainbudget.build.build_demo_page --feed feeds/fares --timetable feeds/timetable --origin GRA \
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
python -m tools.check_links --origin GRA --destination NOT
python -m tools.check_links --provider trainline --mode fallback
```

The checker can prove a link is broken and cannot prove one works, so a `blocked`
or `inconclusive` verdict still needs a person to open it.
`adr/ADR-0017-what-the-live-link-check-found.md` records what it found.

The page is the whole product, and none of the Python tests opens a browser, so
one test drives it in a real one:

```
npx --yes --package "playwright@$(cat tests/browser/playwright-version)" \
    node tests/browser_test.cjs
```

`tests/browser/playwright-version` is the one file that names the browser; CI
installs the version it names, and a run that floats is a different browser from
the release's.

It drags the budget slider to the floor, filters to a town, follows a ticket link
(to a stub, so nothing depends on a seller being up), and reads back what the
**Copy** control puts on the clipboard. It exits 2 and says SKIPPED when playwright
is missing rather than passing quietly. It earned its place immediately: the copy
control shipped with a newline inside a JavaScript string literal, which took the
whole page down while every Python test still passed. It is also the only cover
for what the generated JavaScript *does* — `trainbudget/build/page_templates.py` deliberately has
no unit tests of its own, a decision recorded in
`adr/ADR-0027-browser-suite-covers-the-template.md`.

A check the page has nothing to exercise is a skip rather than a failure, in
every mode: no UNESCO destination, one option in the picker, one station to
change to. A small station is not failed for being small, and neither is the
published one-origin page, which has no second station and no destination
without a journey. Reporting skips is not enough on its own — a fixture can get
small enough that the suite tests almost nothing and the run still reads as a
pass — so the run also **fails when more than 5% of the checks on the station
and chooser pages were skipped**, and names the pages that skipped. A green run
is a claim that the suite exercised the page, not just that nothing it did
exercise broke. `--sweep` is still accepted and still means "this is a station
set"; it no longer changes the standard, because one standard is the point.

One check the demo run still cannot reach is **a feed with a download date says
how old its prices are**. The synthetic feed carries no download, because a feed
nobody downloaded has no date to claim and the page is right to print no age for
it, so the check is not run at all until a real build. That is where it was
found: failing on a real page whose sentence was perfectly correct, because the
regex lived inside a `page.evaluate` and was therefore parsed twice — once by
node, and again in the page from the serialised source, where a doubled escape
arrives as a literal backslash and matches nothing. The age on the page is now
compared rather than looked for, to the day, against the build's own `feedDate`;
and `tests/test_build_demo_page.py` refuses a doubled escape inside any page
callback, which is the shape that made the check unfalsifiable.

**The figures these ADRs quote, and the command beside each.** A number in a
decision record that nobody can re-derive is a rumour, so the ones that survive
into the ADRs came with their command and keep it:

| Figure | Command |
|---|---|
| a page split into stylesheet, script and inline payload, the bytes every page repeats, a folder totalled against the 800 MB target | `python -m tools.page_bytes --site _site` |
| the whole network, measured against that target: 2,712 pages and 498 MB of 800 MB, or 583 MB before the stylesheet became a shared document | `python -m trainbudget.build.build_demo_page --feed feeds/fares --fast-all-origins --notices nre,rdg,ogl,accuracy --out _cache/site_measure/index.html` then `python -m tools.page_bytes --site _cache/site_measure` |
| unclassified destinations, the worst origins by share, and the rows the feed cannot name at all | `python -m trainbudget.fares.destination_coverage --feed feeds/fares` |
| what a new feed download changed against the one the published pages were built from | `python -m tools.feed_change_report --previous-feed feeds/previous --feed feeds/fares` |
| the browser suite over the published routes, with its not-exercised count | `npx --yes --package "playwright@$(cat tests/browser/playwright-version)" node tests/browser_test.cjs _site/index.html _site/from/grantham/index.html _site/privacy/index.html` |
| which routes this release actually wrote | `_site/release-manifest.json` |
| a station's own rows, its three lists and its prices | the payload in the built page, which the suite reads as `DATA` |

Two figures from the September 2026 audit cannot be re-derived, because the
artefact they were measured from was deleted after measuring: 564 MB for the 944
pages a full-network build had written when the disk filled, and the 396–861 KB
range those pages showed. They are in the audit's history and nowhere else, and
nothing in the current decisions rests on them.

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
python -m trainbudget.feeds.feed_audit --feed feeds/fares --timetable feeds/timetable
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
python -m trainbudget.build.build_demo_page --feed feeds/fares --timetable feeds/timetable \
  --knowledgebase feeds/knowledgebase --date "$(date -u +%Y-%m-%d)" --origin GRA \
  --notices nre,rdg,ogl,accuracy --out demo.html
```

`--notices nre,rdg,ogl,accuracy` composes the four licence obligations into the
footer, and which source each one names matters:

- **nre** — the National Rail Data Portal terms require the publisher to
  "acknowledge NRE as the source of Information", and the Developer Brand
  Guidelines require the **Powered by National Rail Enquiries** logo with a
  link to NRE, placed underneath the information when the feed is the page's
  predominant information. The fares and the timetable come from that portal,
  so the credit is NRE's; the mark is inlined from the file NRE supplies, so
  the self-contained page still shows it.
- **rdg** — the Rail Delivery Group credit required by the Data Sharing
  Agreement (cl. 3.3.1) for the Rail Data Marketplace products: the
  Knowledgebase reference feeds and the fare-locations data. Not the fares.
- **ogl** — the Open Government Licence sentence, the fallback attribution the
  Darwin timetable's own §8 leaves blank.
- **accuracy** — the accuracy and liability notice for onward distribution
  (cl. 3.3.2 with the licence's liability clause). It names NRE alongside the
  Rail Delivery Group, because the fares and the times it covers are NRE's.

They are opt-in because crediting a publisher above synthetic prices would be
false attribution — which is why the demo build carries none. What the NRDP
terms require *besides* the acknowledgement — that published times stay
consistent with Darwin forecasts, and that time-bound data is displayed as the
feed directs — is not something a footer can satisfy, and the first is an open
question in `docs/publish-checklist.md` §1.

**A real-feed build takes the timetable *and* a date.** Those are two decisions,
and the second is the one that decides how long the build runs.

Without `--date` the journey search reads every schedule in the feed rather than
the ones that run on a given day, and the difference is not marginal. On one
machine, with the timetable index already cached, Grantham took **7 minutes 9
seconds** without a date and **48 seconds** with one. The national timetable
holds 1.7 million calling points, so a full-network build at the undated
per-origin cost is a multi-day job — which is what `--max-origin-seconds`
exists to catch, and it fires on the *first* origin, so that is learned in
minutes rather than in days (ADR-0024). The first build on a machine also parses
the timetable feed before any of that, which is the slow part; the index is then
cached in `_cache/` keyed by the feed's own bytes, so later builds skip it.

So `--timetable` on its own is not a long job, and `--date` on its own is not a
journey: the pair is what produces the times and changes the journey columns
show. Leaving the timetable off is still a supported build — it writes prices
without times and says so on the page — but it is not a build the deploy
workflow will publish. The workflow loads both, and its release-manifest check
fails the run if the station pages came out without journeys.

**4. Build the site.**

```
python -m trainbudget.build.build_demo_page --feed feeds/fares --all-origins \
  --notices nre,rdg,ogl,accuracy --workers 8 --out _site/index.html
```

`--all-origins` writes one page per priceable station plus the chooser; it also
writes the privacy page the footers link to. `--workers 8` builds station pages
in parallel processes (each origin is independent). In `--fast-all-origins`
mode, workers use the persisted per-origin fare indexes described above. On a
host that does not serve the site at its domain root — a GitHub
Pages project site, most shared hosting — add `--base-path <name>` so every
internal link resolves.

**A public build carries a notice and somebody to contact.** A build whose
prices come from a real feed (anything but the synthetic default) needs both a
licence or attribution notice and somebody to contact, and it stops before
writing a page if either is missing. The contact is the project's own, held as
`DEFAULT_PRIVACY_CONTACT` in `trainbudget/build/build_demo_page.py`, so a real-feed build works
locally without an operator having to supply one; it has **not** been confirmed
as monitored or appropriate to publish (see `docs/publish-checklist.md` §1), and
either flag overrides it:

```
PRIVACY_CONTACT=privacy@example.org python -m trainbudget.build.build_demo_page \
  --feed feeds/fares --origin GRA --notices nre,rdg,ogl,accuracy --out _site/index.html
```

The refusal names both conditions and the flag or variable that satisfies each,
because a gate an operator cannot act on is one they route around. A synthetic
demo build is exempt from the notice — it publishes invented fares and credits
nobody — and names the deployment operator's public repository issue tracker as
its contact so its page is never blank. The privacy page's list of what the
site does is generated from the same feature configuration the pages are built
from, so it cannot describe a site this build did not ship
(`adr/ADR-0032`; gates S36–S38 in the re-envision audit).

**Accessibility is a route matrix, not one happy path.** The browser suite
runs an accessibility matrix against every route it is pointed at — the
chooser, a station page, the privacy page — in light and dark, at desktop,
phone and 200% zoom, and measures rather than asserts:

| what | how it is measured |
| --- | --- |
| names | the browser's own accessibility tree (`ariaSnapshot`), so a control named by a label, an `aria-label` or text this suite has never heard of counts, and one with no name fails |
| contrast | the rendered colours composited over whatever is behind them and resolved through a canvas, against WCAG's own split of 4.5:1 and 3:1 |
| targets | the rendered box plus a positioned `::after`'s slop — 24px for any pointer target, 44px for the row actions the project promises, with links inside a sentence counted and reported as exempt rather than quietly ignored |
| zoom | a 320px viewport, which is what 200% zoom leaves of a 640px screen: no sideways scrolling, no text below the base size |
| keyboard | one Tab reaches a control, and the focused element (or its `:focus-within` wrapper) visibly changes |

Writing it found four real defects, all fixed in the page rather than excused
in the check: the dark palette's muted text measured 4.48:1, the synthetic-data
banner's label 4.37:1, the feed record's disclosure and the footer nav's links
were both under 24px. The privacy page used to be reported as `0/0` because it
carries no controls; it is a route every footer on the site links to, and the
deploy workflow now drives it (audit suggestion S41; ADR-0027 for the suite
itself).

**The reader picks the palette, and dark is the default.** The page is read at
night, on a phone, on a train, so it paints dark unless the reader says otherwise,
and the switch in the top right says "Dark theme" with the state a screen reader
reads. The choice is remembered per browser and applied before the first paint,
so no visit flashes the other palette. Each colour token is written once as a
`light-dark()` pair with its plain light value in front of it, which is what an
older browser falls back to; a token cannot be added to one palette and forgotten
in the other. The control ships hidden and the script reveals it, because a
button that cannot work without JavaScript is a control that lies
(`adr/ADR-0037-the-reader-chooses-the-palette.md`).

**The budget never folds; the refinements are the reader's to open.** The budget
slider and its note share a line under the heading whose budget it is, and the
results stay beneath it, so the page's own question is never behind a control.
The three refinements — ticket type, party, destination type — fold behind one
control whose label states what is currently narrowed ("Cheapest available ·
One adult · all types"), so a reader who has not opened it can still see that a
filter is on. The fold is the reader's at *every* width rather than a phone
behaviour: one control, one `data-open`, no media query and no resize listener,
because a fold driven by a viewport width means two things at two widths and a
single rotation can overwrite the choice. The control is a button carrying
`aria-expanded`, the panel's visibility is a stylesheet fact rather than a state
a missed event can strand, and the summary is rewritten from the page's own
controls on every render, so it cannot describe a filter that has since been
cleared (audit suggestion S42, amended by ADR-0039; the checks are in
`tests/browser_test.cjs`).

**A synthetic build says so above the content.** Every generated route -- the
chooser, each station page, the privacy page -- carries a banner naming the
invented data, plus a `data-synthetic` attribute on `<body>` a test or a
screenshot fixture can assert in either direction. It is a banner rather than
a footer paragraph because the footer is what gets cropped out of a screenshot
(ADR-0033's shared `.synthetic-banner` component; audit suggestion S45).

**A build states which routes it serves.** Every build writes
`release-manifest.json` beside the pages: the base path, the price source,
whether the data is synthetic, the build time, and every route in the release —
the chooser, each station page, the privacy page. The build proves it against
the files on disk and refuses rather than reporting success if it names a route
it did not write, and the deploy workflow refuses a folder whose page count and
manifest disagree. The link crawl asks the other question — does every link a
reader can follow resolve? — so the two together are a release that is complete
in both directions. The output folder is not cleared first: `--fast-all-origins`
resumes from it, and the project does not delete a page it did not write (it
names those folders instead), so a local preview can hold an earlier build's
pages that nothing links to. Audit suggestion S07 asked for a staged swap; that
would have broken both, so the manifest is what this build does instead
(`adr/ADR-0034-the-release-is-the-routes-its-manifest-names.md`).

Every build also names the priced destinations no source could classify — the
stations the page's settlement filters therefore cannot return. The list is a
warning, because a full-network build legitimately meets stations nobody has
reviewed; `--fail-on-unsourced` turns it into a refusal for a release build,
checked before anything is written. Run the same check on its own, across the
whole feed, with `python -m trainbudget.fares.destination_coverage --feed feeds/fares`.

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

**Publication is gated on a licence clearance, and the gate is not code alone.**
A separate `clearance` job runs `tools/check_release_clearance.py --release
fares`, and the `deploy` job needs it, so a release the record does not clear is
never published. While a product it publishes is outstanding the run is **red, at
that one job**: `build`, the shard jobs, `assemble` — which runs `tools/verify
--full` and the browser suite — stay green, `deploy` is skipped, and the
`clearance` job's own output names the product that is missing. That is
deliberate, and the confinement is the point: a gate nobody can see is a gate
nobody keeps, but a licence refusal that reddened the build would read as a code
fault. The
decision itself lives in `licences/release-clearance.md`: which licensed products
may be published, each answered `cleared` or `excluded` with a reason, a named
approver, a date and an expiry, changed in a pull request so the review *is* the
approval. The record clears the DTD fares route against the filed
portal terms and clears NWR Schedule, whose §5 permits distribution, as the
timetable a release may publish from. It still excludes the Darwin timetable
schedule: that exclusion is the project's reading of Schedule 1 §5 as
internal-use-only, and it holds whether or not the times go out, because the
times would come from the other product. The shape the workflow declares is
therefore `fares,timetable`: prices from the DTD feed, times from the OGL CIF every
job fetches into `feeds/nwr-schedule/`, and no page that comes out without journeys
may be published under it.

Two things that gate deliberately is not:

- **Not the attribution wording.** The build supplies every required credit, and
  that is a different question from being permitted to publish at all.
- **Not permanent, and not scope-free.** `expires` is enforced, the licence file's
  SHA-256 is recorded with the clearance so a replaced licence voids it, and a
  fares-only clearance does not authorise a build that also loads a national
  timetable: that shape demands the publishable schedule's clearance on top of
  the fares one, so a narrow decision cannot quietly widen the release it covers.

Local builds are untouched by any of this: `trainbudget/build/build_demo_page.py` and `run.py` do
not read the record, so the real-feed path can be built, tested and opened
locally with no clearance in sight.

```
python -m tools.check_release_clearance --release fares   # what may be published
python -m tools.check_release_clearance --print          # blocks to fill in
```
