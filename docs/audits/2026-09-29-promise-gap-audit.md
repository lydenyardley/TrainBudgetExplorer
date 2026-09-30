# Promise gap audit: any departure station, every destination under a budget

**Date:** 29 September 2026
**Method:** read-only. Code and copy were read, the feeds were measured with the
repository's own tools, and one full-network build was run until it stopped.
Nothing here changes code. The first pass's recommendations were proposals; the
revision records the owner's decisions on the four questions it left open.
**Question:** does the site deliver the promise, and what stands between the
promise and the published artefact?
**Revision, 30 September 2026.** The census has been re-verified and re-measured.
Three of the first pass's numbers were wrong or unverifiable, and two of its
recommendations rested on premises the code and the payload contradict. The four
questions it left open are decided, and the decisions are recorded at the end. The
measurements added here are re-runnable from "How these numbers were measured".

## The promise, in the project's own words

`PRODUCT.md` states it twice:

> Given an origin station and a budget, the page lists **every** destination
> reachable by train inside that budget, with the fastest journey time, the number
> of changes, the fare for one adult, and the total for two adults at two Anytime
> Day Returns.

> If you arrived on the wrong town, you change station from the header and are
> taken to that station's page — choosing is navigation, not a filter.

So the promise has four parts: any departure station, every destination, a price
ceiling, and a change of station without a round trip through the home page. The
request that prompted this audit adds a fifth: destinations that require a change,
including where a split ticket is the cheaper answer.

## What the census measured

| Claim | Measured | Where it came from |
|---|---|---|
| The published site prices one origin | 3 routes: `/`, `/from/grantham/`, `/privacy/` | `_site/release-manifest.json`, built from `deploy.yml`'s `--origin GRA` |
| The network the feed can price | 2,712 priceable origins | build log, `Persisted 2,712 per-origin fare indexes` |
| Cost of publishing all of them | 944 pages in 36 min, then `OSError: [Errno 28] No space left on device` | `--all-origins --workers 8` run, stopped by a full disk with 944 MB free |
| Projected size of the whole network | **1.4 to 1.6 GB for 2,712 pages.** 564 MB for 944 pages (598 KB a page) measured on the stopped run, and 396–861 KB a page (mean 512 KB) over 12 sampled origins | `du` on the run's output and the payload length of the 12 samples, both taken in the first pass. The output folder was deleted after measuring, so these two are recorded rather than re-runnable |
| Bytes identical on every station page | 116.7 KB per page, 33.9 KB of CSS and 82.8 KB of script, which is **~309 MB, 22%** of the projected total. 117 KB after the wire encoding, which added the 0.9 KB hydrator to every page, and **119.3 KB** measured over 963 real network pages after the picker moved out, since that change added its own code to each of them | `tools/page_bytes.py` over `_site/from/grantham/index.html`, the demo station pages, and the 963 pages of the measured network build |
| The picker list on every station page | **111.3 KB a page** in the wire encoding -- 113,983 bytes over 2,712 rows, so **295 MB of the network** -- and identical on every page but the one row each page filters out. As plain objects the same list is 164.2 KB a page, 435 MB over the network, near the 445 MB this audit first estimated from a 63.5-byte row | the real `--all-origins` build's own output, measured 30 September 2026: 2,712 rows, 113,983 bytes encoded a page, 168,467 bytes as one file |
| What one payload row costs, before the wire encoding | 1,023 bytes, of which **361 are JSON key names**; departure options cost 13.8 KB of which 11.1 KB is three key names; railcard prose is 80 KB over 190 rows from **83 distinct reason strings** | `const DATA` decoded from the Grantham page |
| The object repeated on every row | One link, `{"url": "https://www.nationalrail.co.uk/journey-planner/", "label": "National Rail", "rel": "noopener"}`, byte-identical on all 190 rows, **18.6 KB of a 200 KB payload, 9%** | same decode |
| The host's other limits | A deployment times out after 10 minutes; bandwidth is a soft 100 GB a month | GitHub Pages limits, read 30 September 2026 |
| Destinations per origin | 26 to 193, in the same 12 | the 12 sampled payloads, since deleted |
| Destinations that need a change | 62% of Abbey Wood's 117, 66% of Ardrossan's 193, 76% of Durham's 70, 0–76% across the sample | `changes > 0` in the sampled payloads |
| Priced destinations no source can classify | 1,575, worst shares 100% of MYB (10 destinations), 98% of PEE and UIG (45 each) | `python destination_coverage.py --feed feeds/fares` |
| Destination rows that can never be named | 84,544 rows, summed over origins, so one unnamed location is counted once for every origin that prices it | same tool |
| The CI ceiling on that first number | `--unsourced-ceiling 1575`, exactly today's value | `.github/workflows/deploy.yml` |
| Split ticketing | no implementation anywhere in the repository | search for `split` returns only `docs/launch-checklist.md`, a line to disclose it in the launch post |

Two of these are worth stating plainly.

**The published artefact cannot change station at all.** It has one origin, and
the heading renders the name as text rather than as a control precisely because
there is nowhere to go. The browser suite reports four checks it cannot exercise
across the three published routes, three of them on the chooser and one on the
station page: typing cannot narrow a list of one, and there is no second option
for the arrow keys to reach. That is the suite telling the truth about the
artefact, and it names which page is short.

**Every page is a self-contained file, and the price of that promise is
measurable.** The first pass ran two quantities together and they are separated
here. ADR-0033's own inlined blocks (stylesheet, theme, chevron, list-key block)
total **18.6 KB**, and its recorded cost of "roughly 3 KB of duplicated CSS" is
stale against the 15.9 KB that `SHARED_CSS` has since become, so about 5x. The bytes **byte-identical on every station page** are larger,
**116.7 KB**, because the station page's own stylesheet (18 KB) and its script
(82.8 KB) also come from one template that no page varies. Across the network that
is ~309 MB of the projected 1.4 to 1.6 GB, about 22%. Enough to matter, not enough
to decide the fit alone. The payload is the larger part and about half of it is
recoverable, because rows spend their bytes on things that repeat: 1,023 bytes a
row of which 361 are key names, one identical link object on all 190 rows, and
80 KB of railcard prose the feed expresses as 83 distinct reason strings. At
598 KB a page the network is ~1.6 GB against GitHub Pages' 1 GB per-site limit,
and an operator's build needs that much scratch space besides. The build I ran died
of a full disk, not of a bug.

## Findings, in the order they block the promise

1. **The deploy publishes one station.** Everything the request asks for —
   selecting a departure station, a real selector list, the heading control, arrow
   keys through the list — is implemented and tested, and unreachable in the
   artefact that is published. This is one root cause behind three symptoms.
2. **The artefact does not fit the host as built, and the shared blocks are only
   a fifth of why.** 1.4 to 1.6 GB of pages against a 1 GB limit, of which 309 MB
   is bytes every page repeats while about half of every payload is re-sent names,
   one unchanging link object and repeated prose. ~100 minutes of build (warm
   caches) per publication, against a deployment that has to finish in 10.
   **The largest repeated item is not code at all.** Every station page carries the
   168 KB picker list of every other station, which is 445 MB of the projected
   site and is the same list on all 2,712 pages but for one row.
3. **The party figure is honest; the copy about it is not.** *(Corrected 30
   September 2026.)* This pass repeated PRODUCT.md's claim that the Two Together
   discount is "parsed but not evaluated". The code evaluates it: the one-third
   discount rounded down to 5p, held up to the feed's minimum-fare table, gated by
   the current DTD RR ticket, route, location and total-ban rules — and `priceOf()`
   puts the result into the list filter, the chip counts and the row, so ticking
   the box lowers prices *and* widens the list. Two undiscounted returns is the
   right default for a reader who has not said they hold a card, and the page does
   not claim otherwise. What is wrong is narrower: the RCM minimum-fare record's
   `start_date`/`end_date` are read past, so a minimum outside its window is
   applied as if current, and PRODUCT.md and the launch-post copy still describe
   the discount as unpriced.
4. **The type facets are missing where the sources are.** 1,575 priced
   destinations carry no settlement class from any source, and on the worst origins
   that is every destination the page has, so those pages offer no facet but
   "All" — and a reader filtering by type is filtering against data the feed never
   classified.
5. **Split ticketing does not exist, in code or in copy.** The page says Advance
   singles can undercut an Anytime Day Return; it says nothing about two tickets
   being cheaper than one, which is the reply the launch checklist already expects.
6. **The list that opens is the narrowest of the three, and the cheapest fare may
   not be a return at all.** *(Corrected 30 September 2026.)* The page opens on
   Anytime Day Return, which is narrower than "any return" and much narrower than
   "single": the Grantham page opens on 42 destinations of the 101 the same budget
   reaches. On 12 sampled origins the single mode carried 904 destinations against
   the return mode's 818, and the gap is not uniform: Durham 118 against 70, Cark &
   Cartmel 42 against 26, Delamere 45 against 32. Of Grantham's 54 single-only
   destinations, only 16 are Advance, so most of that reach is ordinary singles
   rather than quota-priced ones. A reader who leaves the mode on its default is
   not seeing every destination their budget reaches.

## Recommendations, in order

Each names what to change, the evidence behind it, and how a reviewer would know
it worked. The first two are one decision in practice: publishing the network is
only possible once a page is small enough to publish.

### 1. Make a station page publishable at network scale, then publish the network

Two changes, in this order, each measured against the byte budget rather than
assumed.

**First, spend the payload better.** Three changes, each measured on the Grantham
page, together remove about half of a payload:

- **Encode rows positionally.** 361 of a row's 1,023 bytes are key names, and the
  departure options are 13.8 KB of which 11.1 KB is three repeated key names. A
  per-page key list removes most of it.
- **Hoist what never varies.** One link object is byte-identical on all 190 rows
  and costs 18.6 KB, 9% of the payload, to say one thing once per row.
- **Key the prose.** Railcard prose is 80 KB over 190 rows from 83 distinct reason
  strings, so a once-per-page table keyed by rule removes the repetition.

None of the three touches ADR-0033, and each is a change to serialisation rather
than to the promise.

**Then, if the re-measured build still does not fit, move what repeats.** Two
things repeat, and the larger one is data rather than code:

- **The picker list, 445 MB.** Every station page carries every other station's
  name, code and address so the heading can offer them. It is the single largest
  repeated item in the release, more than the code blocks, and one shared file
  fetched once would pay for itself on the second page a reader opens.
- **The stylesheet and script, 309 MB.** Byte-identical on all 2,712 pages.

Moving either one into a hashed asset re-decides ADR-0033, whose guarantee (no
page depends on a second request to be readable) has to be re-scoped to the page's
*own* data rather than quietly dropped: the destination payload stays inline, and
the escape-guard and self-contained tests need a contract that names what must
remain inlined and what may be fetched. A block that fails to arrive must leave
the page readable, not blank.

**Evidence.** 12 sampled pages of 396–861 KB, of which the bytes identical on
every station page are 116.7 KB, measured rather than estimated, beside the same
run's 564 MB for 944 pages. ADR-0033's own inlined blocks are 18.6 KB against the
"roughly 3 KB of duplicated CSS" it records, and neither figure counted the
station page's script, which is 82.8 KB of the 116.7 KB.

**Cost to be measured before committing.** The asset fetch, the cache-busting
hash, and the GitHub Pages limit once both changes are in. On the measured mean
page of 598 KB they work out as follows.

| Change | Projected site | Verdict |
|---|---|---|
| The payload work, landed | ~1.08 GB | still over the limit |
| Plus the picker list as a shared file, landed 30 September 2026 | ~0.79 GB (295 MB saved, 164 KB spent once) | at the 800 MB target |
| Plus the stylesheet and script as one | ~0.49 GB | fits, with room |

These are extrapolations, labelled as such: the payload cut is measured on one
page (64% off, Grantham, 190 rows) and applied to the 598 KB mean page the
944-page run produced. The second row's figure is no longer an extrapolation. The
picker list was measured at 113,983 bytes a page over 2,712 pages, 295 MB, against
164 KB for the one file that replaces all of them -- which is why the shared file
that pays first is data rather than code.

The target to write into the build's own check should be **800 MB**, not "inside
1 GB". A hard limit reached with nothing to spare is reached again by the next
feed revision. If both changes still do not fit, the release splits into shards (a
page per origin plus an index per region), which changes the route layout and the
chooser's list.

**Sequence, because three decisions share one code path.** The positional
encoding, the change-station field (Q2) and the cheapest-of-everything list (Q4)
all read the same payload in the same pass, so they are one change to the builder
and one to the page's reader rather than three. Fields that Q2 and Q4 add have to
be paid for out of the payload savings, not on top of them, or the fit is lost
again by the changes that were meant to be free.

**How a reviewer knows.** `find _site -name index.html | wc -l` equals the
priceable origins; `du -sh _site` is under 800 MB; a page renders its table with
the shared asset blocked; and the browser suite's chooser checks (typing narrows
the list, the arrow keys reach the second option) stop reporting as not exercised
on the published site.

### 2. Make the one-origin artefact stop looking like a chooser

Until 1 lands, the published site should not carry a heading slot and a list that
cannot select anything. Today the page is honest in words ("the only one this site
was built for") and looks like a search box in shape. Either publish more than one
origin or state the choice in the shape as well as the sentence.

**Evidence.** The suite cannot exercise four of its checks across the three
published routes, three on the chooser and one on the station page, and the
chooser renders one row out of a list whose cap is forty.

**How a reviewer knows.** No page presents a field that can only ever confirm a
single answer, and the not-exercised count on the published artefact drops.

### 3. Price the Two Together discount — decided: keep the default, close two gaps

The undiscounted total stays the default party figure, and the one the budget
ceiling is built from, because the page cannot know who is reading and a ceiling
must not move the moment a box is ticked. The discount itself is already priced
per fare and already drives the filter, the counts and the row. Two gaps close:
the minimum-fare lookup starts honouring the record's `start_date` and `end_date`,
and a row with the card ticked shows the card price **and** the standard fare it
came from, so a discounted number never stands alone in the cell. The stale claims
in PRODUCT.md and the launch-post copy are corrected rather than left describing a
build that no longer exists.

**How a reviewer knows.** A minimum whose window has passed does not raise a fare;
a ticked row shows two prices and an unticked row shows one; and no document in the
repository says the discount is unevaluated.

### 4. Close the classification gap, worst origin first

Work the settlement classes from the origin end: MYB, PEE and UIG lose their type
facets entirely today, and across the feed 1,575 priced destinations are
unclassified while 84,544 rows can never be named at all. The second number is the
one to take apart first, because it is the larger and it is a product claim about
what the feed can express.

**Evidence.** `destination_coverage.py` output above, and the CI ceiling of 1,575,
which is exactly the current count and therefore cannot absorb one more. Any
origin that gains a priced-but-unclassified destination fails the gate until this
number falls, so the ceiling is both today's count and today's blocker.

**Sequence against 1.** Naming those destinations puts rows on pages, so this work
**adds** payload bytes at the same time as 1 removes them. Ordered the other way
round it grows the site exactly as the fit is being fixed. Do it after the payload
encoding, and count the added rows against the same 800 MB target.

**How a reviewer knows.** The ceiling falls, and the page's facet chips appear on
the origins that had none.

### 5. Decide what split ticketing is — decided: signal only

The row's details panel gains one line for a journey with a change, naming the
change station as where a two-ticket split may undercut the through fare. It sits
where the fare's condition already sits (`fareDetails`), so it needs no new column
and no new row control, and it states a possibility rather than a price.

"Price the splits" was rejected: it doubles the fare lookups per row, and the feed
prices flows rather than itineraries, so a row would stop meaning one fare. "Leave
it out, say so" was rejected as the weaker answer once the station turned out to
be nameable from data the build already holds — rows carry `changes` and `legs`,
and a `Leg` has `origin_crs`/`destination_crs` — so the cost is one payload field
on the changed rows, which can ride along with Q1's row encoding.

### 6. Make the headline list the cheapest way to get there — decided: cheapest of everything, named

The list that opens is the cheapest fare of any ticket type to each destination,
with the three mode lists kept as filters for a reader who wants one ticket type.
It can be composed in the page rather than in the build, so it costs no payload
bytes.

Two consequences are accepted rather than avoided, and the page has to carry
them:

- **The headline is a one-way price list in practice.** Measured on the Grantham
  page, every one of the 101 destinations is cheapest on a single, because a
  one-way fare is cheaper than a return to the same place. The return therefore
  stops being what the page opens with, and PRODUCT.md's "the total for two adults
  at two Anytime Day Returns" becomes the cheapest ticket that reaches the place.
- **The party figure changes meaning per row.** Two adults with the card are still
  two of the fare the row names, but on a single row that is two singles, not two
  returns. The count line and the column's own words have to say which, or a £30
  ceiling reads as two returns when it is two singles.

**How a reviewer knows.** A page's first row is the cheapest of the fares it can
show; the fare code beside it says which one that is; the count line names the mix
of ticket types it is showing; and PRODUCT.md's promise names the same basis the
page displays.

## What is already right, so the next pass does not redo it

- **Destinations that require a change are in the list.** Measured as a majority of
  destinations on the busier origins (62%, 66%), with the change count in its own
  column.
- **The price columns are readable.** No price or header wraps, enforced by a check
  that counts painted line boxes rather than reading CSS.
- **The count line sits on its table**, the order is stated in words, and no row is
  tinted as a recommendation.
- **Provenance and licence gates hold.** The freshness threshold, the restriction
  reference check, the reviewed-code gate and the release-clearance gate all fire
  before a page is written.

## How these numbers were measured

Every figure in the census can be re-derived by the command beside it. The two
marked **recorded** cannot, because the artefact they were measured from was
deleted after measuring.

| Figure | Command |
|---|---|
| 1,575 unclassified, the worst shares, 84,544 unnameable rows | `python destination_coverage.py --feed feeds/fares` |
| 2,712 priceable origins | `grep -m1 "priceable origins" _cache/all_build.log` |
| 944 pages written before the disk filled | `grep -c "^wrote " _cache/all_build.log` |
| 564 MB for 944 pages | **recorded**. `du` on `_cache/site_all`, since deleted |
| 396–861 KB a page over 12 origins | **recorded**. Measured on 12 sampled pages, since deleted |
| 247/247 with 4 not exercised, 3 of them on the chooser and 1 on the station page | `npx --yes --package playwright node tests/browser_test.cjs _site/index.html _site/from/grantham/index.html _site/privacy/index.html` |
| 3 published routes | `_site/release-manifest.json` |
| the chooser's list of one, against a cap of forty | `const STATIONS = [{"name":"GRANTHAM","crs":"GRA","href":"/from/grantham/","destinations":101}]` in `_site/index.html`, against `const CHOOSER_LIMIT = 40` in `page_templates.py` |

The page-byte figures come from `tools/page_bytes.py`, which splits a page into
stylesheet, script and inline payload and reports the bytes every measured page
repeats word for word. It was written for this section after the first pass's
hand measurements disagreed with each other, and its console output floors to
whole KB, so 116 KB printed is the 116.7 KB quoted below.

```
$ python tools/page_bytes.py _demo_site/from/grantham/index.html       _demo_site/from/lincoln/index.html _demo_site/from/nottingham/index.html       _site/from/grantham/index.html
_demo_siterom\grantham\index.html: 142 KB total, 33 KB css, 82 KB script, 14 KB payload, 11 rows
_demo_siterom\lincoln\index.html: 140 KB total, 33 KB css, 82 KB script, 12 KB payload, 9 rows
_demo_siterom
ottingham\index.html: 140 KB total, 33 KB css, 82 KB script, 12 KB payload, 9 rows
_siterom\grantham\index.html: 336 KB total, 33 KB css, 82 KB script, 200 KB payload, 190 rows
identical on all 4 measured pages: 116 KB, 34% of the largest page
```

It counts a part as shared only when every measured page carries it word for
word, which is why the same command over the three published routes reports 0 KB.

## Decisions taken

**Q1 — is a shared asset file acceptable, or is the one-file route a promise
worth paying 1.4 GB for?** *Decided 30 September 2026: both levers, in this
order.* Keep the promise for what is the page's own — the destination payload
stays in the file, so a page is still one request for its own data — and spend it
better first, by encoding rows positionally and holding repeated prose once per
page. Then, only if the re-measured build is still over the host's limit, move the
bytes that are identical on every page (116.7 KB of CSS and script) into one
hashed asset, and re-decide ADR-0033 with a contract that says what stays inline.
The host does not change and the network is not thinned: all 2,712 origins are to
be published. The reason is the measurement — the promise costs 309 MB, not
1.4 GB, and about half of the payload is recoverable on its own, so giving up the
guarantee before trying that would pay the larger price for the smaller saving.

**Amendment, 30 September 2026.** The picker list changes what the second lever
should carry. At 445 MB it is the largest repeated item in the release, so the
first thing to move out of a page is the station list, not the stylesheet. The
order stays as decided: encode first, fetch only if the re-measured build is still
over the 800 MB target.

**Q2 — is split ticketing in this product, or is it a limitation the page
states?** *Decided 30 September 2026: a signal the page states, priced nowhere.*
A journey with a change gets one line in the row's details naming the change
station as where a two-ticket split may undercut the through fare. The page makes
no price claim, the build adds one field to the changed rows, and any "two tickets
can be cheaper" reply is met by the page the reader is already on rather than by
the launch post alone.

**Q3 — does the party price wait for the railcard rule?** *Decided 30 September
2026: it does not have to, because the rule is already applied.* The two
undiscounted returns stay the default party figure and the basis of the ceiling;
filtering and the counts already use the price that applies to the reader, and
ticking the card widens the list as well as lowering the numbers. A row with the
card ticked shows the card price and the standard fare beside it. The minimum-fare
lookup starts honouring the record's validity dates, and PRODUCT.md and the launch
post are corrected.

**Q4 — is the headline ticket type "the return" or "the cheapest"?** *Decided 30
September 2026: the cheapest of everything, with the ticket named on every row.*
The page opens on the cheapest fare of any ticket type to each destination, and
the three existing mode lists survive as filters. Two costs are accepted knowingly
and have to be carried in the copy: the headline is a one-way price list in
practice, because a single is always cheaper than a return to the same place, and
the party figure is two of whatever fare the row names — two singles on most rows.
The count line and the column's wording therefore have to name the mix and the
basis, and PRODUCT.md's "two Anytime Day Returns" becomes the cheapest ticket that
reaches the destination.

## Progress against these recommendations

The trail lives here rather than in a separate file, because this document is
already the record the next reader opens. Each entry names the command that
re-checks it.

### 1a. The byte measurer, landed 30 September 2026

`tools/page_bytes.py` splits a built page into stylesheet, script and inline
payload, reports the bytes every measured page repeats word for word, and totals a
built folder against a budget of 800 MB. `tools/test_page_bytes.py` holds fifteen
tests. The tool reproduces the figure this document argues from, which is the
point of building it: 117 KB identical across the demo station pages, 83% of the
largest.

Command: `python tools/page_bytes.py --site _site`.

### 1b. The payload wire encoding, landed 30 September 2026

Each row list now ships as a column list and a table of cells, and the page
hydrates it as it loads, so no other line of the script changed. Measured on the
real Grantham page from the same feed, before and after:

| | before | after |
|---|---|---|
| page | 336 KB | 286 KB |
| payload | 200 KB | 149 KB |
| rows | 190 | 190 |

That is 15% off the page and 25.5% off the payload, not the 35% the key count
predicted. A table has to carry a cell where the old object simply left the key
out, so the sparse destination rows give about 15 KB of their 66 KB of key names
back. The picker rows are dense and keep all of it: 63.5 bytes a row as objects,
43.5 as a table, 32% off, which is 168 KB a page down to 115 KB, or 445 MB of the
projected site down to 305 MB.

Verification: 567 tests in `tests/` and 15 in `tools/` pass at 84.3% coverage, the
browser suite is 595/595 over the five demo routes and 247/247 over the three
published ones, and the journey gate exits 0.

Commands: `python tools/page_bytes.py _site/from/grantham/index.html` and `npx
--yes --package playwright node tests/browser_test.cjs _site/index.html
_site/from/grantham/index.html _site/privacy/index.html`.

### 1c. The pool of repeated values, landed 30 September 2026

The same encoder now counts the values that repeat inside a row list and sends
one copy of each in a page-level pool, with the cells that use it carrying a
negative index. The length floor is what stops a pool costing more than it
saves: only objects, arrays and strings of twelve bytes or more are pooled,
because for anything shorter a reference is no smaller than the value, and
booleans and numbers are never pooled for the same reason.

Measured on the same Grantham page, three builds of the same feed:

| | before | 1b, the encoding | 1c, the pool |
|---|---|---|---|
| page | 336 KB | 286 KB | 209 KB |
| payload | 200 KB | 149 KB | 72 KB |
| rows | 190 | 190 | 190 |

The payload is 64% smaller than it was this morning and the page 38% smaller. The
pool is the larger half of the saving, because what repeats on a real page is not
only the key names: it is one ticket link on all 190 rows and one railcard record
per rule rather than per row. The picker list gains nothing from it, since its
three fields are unique per row, which is the one reason the picker is still worth
moving out of the page.

Verification: the browser suite is unchanged at 247/247 over the published routes
and 595/595 over the demo routes, so the page still renders the same table from a
payload that is 64% smaller.

### 1d. The picker list as one shared file, landed 30 September 2026

The station list every page's picker offers was the release's largest repeated
item. It is now written once, as `stations.js` beside the pages, and each station
page names it with a plain `<script src>`. The list is the same bytes on all 2,712
pages but the one row each page filters out, so 2,712 copies bought nothing.

**The contract that replaces ADR-0033 where it applies.** A page still carries its
own data inline -- the destination rows, the fares, the provenance -- so a page is
still one request for everything that is about itself. What a page may now fetch is
the list of *other stations*, which is one document for the whole site and is not
part of this page's answer. Two behaviours are part of that contract rather than
incidental:

- **A page whose copy did not arrive still names its station.** The heading's
  control is replaced with the station's name as text, the picker's panel is
  removed rather than left empty, and the first-use sentence is rewritten from the
  same constant the build ships. A reader never gets a heading reading "from" and
  nothing, and never gets a control that opens nothing -- the defect the browser
  suite exists to catch.
- **The picker is the only thing that degrades.** The table, the filters, the
  budget and the ticket links are all in the page, so a failed fetch costs the way
  to another station by header and leaves the "All stations" link in the footer.

A one-station site writes no asset and requests none, so the published
single-origin artefact is unchanged but for the picker code every page now carries.

**Measured on the real network, not extrapolated.** The `--all-origins` build over
`feeds/fares` wrote its own list to `_cache/site_measure/stations.js`:

| | bytes | over 2,712 pages |
|---|---|---|
| the list inside each page, wire-encoded | 113,983 a page | 295 MB |
| the list as one file | 168,467 once | 0.16 MB |

So the move saves about **295 MB** of the projected network and spends one request
and 164 KB. A second measurement from the same run, over the 963 pages it had
written when it was stopped by a timeout: mean page 209 KB, smallest 143 KB,
largest 420 KB, 119.3 KB identical on all of them. The same pages carrying the list
would have averaged 320 KB, so on a prices-only network the picker was a third of
every page: 848 MB across 2,712 pages against 553 MB now.

Verification: 577 tests in `tests/` and 143 in `tools/` pass at 84.5% coverage, the
browser suite is 595/595 over the five demo routes and 247/247 over the three
published ones, and the journey gate exits 0. The suite now serves the asset a page
names and stops the run if a page asks for one it cannot find; a page with its
asset reference removed was driven on its own and passed 153/153, with the heading
naming the station as text and no control.

Commands: `python build_demo_page.py --feed feeds/fares --fast-all-origins
--notices nre,rdg,ogl,accuracy --out _cache/site_measure/index.html` writes the
asset, and `python tools/page_bytes.py --site _cache/site_measure` totals the site.

### 2. The one-station root states the choice, landed 30 September 2026

The published artefact offered exactly one station and asked the reader to type
it. The field could only ever confirm the station the build already knew, so the
root now names that station in the heading instead: a release that priced one
station writes no search slot, no ordering note (nothing is ordered over one row)
and no station field, and its single row is the page to open, carrying that
station's own destination count. A root that offers more than one station is
unchanged.

The suite drives it as what it is. It used to drive the same page as a chooser —
where four checks could not be exercised across the published routes, three of
them for the same reason: a list of one cannot be narrowed — and this
recommendation's own measure is that count falling. On the same three published
routes:

| | before | after |
|---|---|---|
| checks passed | 247/247 | 234/234 |
| not exercised | 4 (3 on the root, 1 on the station page) | 1 (the station page) |

The check total falls by thirteen because a page with no search has no search to
test. The root is driven by its own fifteen assertions: the heading names the
station, no field asks for it, no ranking is claimed over one row, the one row is
a link to that station's page carrying the reader's budget, the option carries the
station's name, code and count, the tab title names the station, and a shared link
opens at the budget it carries. What it does not have is the field, the
placeholder, the caret, the narrowing and the arrow keys that the chooser's checks
exercise, because the page does not have them. The demo site is unchanged at
595/595, since it prices three stations and is a chooser.

The shape is also what the page is: a release that already chose does not ask the
reader to confirm the choice. A station name is not lost by this -- the heading
still names it, and the one link still opens its page.

**How a reviewer knows.** Build the published site and drive it:
`python build_demo_page.py --feed feeds/fares --timetable feeds/timetable
--knowledgebase feeds/knowledgebase --origin GRA --out _site/index.html ...`, then
`npx --yes --package playwright node tests/browser_test.cjs _site/index.html
_site/from/grantham/index.html _site/privacy/index.html`. No page presents a field
that can only confirm a single answer, and the not-exercised count is one.

## Where the four decisions leave the work

All four questions the first pass left open are decided. What remains is work
rather than judgement: the byte budget (Q1), the split-ticket line in the row's
details (Q2), the minimum-fare validity window and the two stale documents (Q3),
and the cheapest-of-everything list with the copy that has to carry it (Q4).

The byte budget's second lever has begun and its largest item is done: the picker
list is one shared file (1d). What is left of recommendation 1 is the stylesheet
and script, 119.3 KB identical on every page, which is the same boundary and the
same hashed asset the picker's move needed. Recommendation 2 is done (2), and the
ADR carries both: ADR-0033 now records what a route must keep inlined, what it may
fetch, and what a route does when that fetch fails.

## What this pass corrected

Three of this document's own figures were wrong and are corrected above rather
than left standing. The first pass treated the shared blocks as the network's
fixed cost without measuring them, and the measured price of the promise is
116.7 KB a page, 309 MB of the total, not the 3 KB ADR-0033 records. The revision
of 30 September then compared two different quantities, and the comparison is now
split: ADR-0033's duplicated CSS is 15.9 KB against its recorded 3 KB, about 5x,
while the 116.7 KB also counts the station page's own stylesheet and script.
Recommendation 6 proposed a cheapest-of-both union without measuring it, and the
union collapses into the single list. Recommendation 3 repeated PRODUCT.md's claim
that the Two Together discount is unevaluated, and the code evaluates it.
