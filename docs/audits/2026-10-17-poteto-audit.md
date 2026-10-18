# Engineering audit: what to improve, and the instrument that would prove it

**Date:** 17 October 2026
**Reviewed:** `main` with that day's uncommitted work. The three published routes,
the build that writes them, the tools that measure them, and the checks that hold
them.
**What it is:** a read-only audit. No file in the repository was changed in
producing it. Every finding is a numbered recommendation with the evidence that
produced it; nothing here has been implemented.
**Method:** built `_demo_site` from `_demo_feed` and `_demo_kb` at service date
5 October 2026 and served it; ran `python -m tools.page_bytes` on the result; ran
the impeccable detector over the three routes; measured the page in Chromium with
Playwright at nine widths and four heights, including the geometry of the stacked
table and the state changes across a budget edit; read the modules named in each
finding. A **measured** label means a command or a browser produced the number.
A **read** label means the claim comes from the source. A **inferred** label means
arithmetic from one of those. There is no real-feed build in this pass, so no
figure here describes the 2,712-page release unless it says so. Nothing here is a
build-runtime figure, so nothing here belongs in
`docs/build-performance-findings.md`; every number below is a page measurement or
a command output, dated by this document.
**Overlap:** where this audit met the same subject as
[the critique](2026-10-17-impeccable-critique.md) or
[the distill](2026-10-17-impeccable-distill.md), the reader-facing half stayed
with those documents and only the mechanism and the check remained here. The
section "Pruned for overlap" lists what left this document and where it went.

## Principles applied, and what each one changed

I read `model-the-domain`, `minimize-reader-load` and `encode-lessons-in-structure`
this session. Each of the three changed a recommendation rather than decorating
one:

- **Model the domain** turned "the page state is spread across the DOM" from an
  observation into a concrete recommendation: one view object derived once per
  render, rather than four independent readers of the same radio group (E9). It
  also fixed the shape of E10: one owner for one sentence, because two modules
  composing the same string is a missing structure, not a copy bug.
- **Minimize reader load** is why E12 is filed against panel ownership rather than
  against file count. Sixteen files are not the problem; `#summary` being declared
  in `service-day.js` and written by `table.js` is, because a reader answering
  "what writes this element" has to open three files.
- **Encode lessons in structure** is the reason the two test findings (E13, E14)
  do not say "be careful with the stacked table". They name the assertion and the
  place it belongs, because the repository already writes the analogous check for
  every other cell.

## Findings

Severity is about cost to the product, not effort: **high** means a reader or a
release decision is being misled now, **medium** means a maintainer pays on every
change, **low** is housekeeping.

### The instrument that is supposed to measure the page

**E1 [high] The page-size tool reports zero payload and zero rows for every
station page, and the suite cannot see it.** `tools/page_bytes.py:51` splits the
inline data with `INLINE_JSON_MARKERS = ("const DATA = ", "const STATIONS = ")`.
No page has written either string since the data moved onto `window.TBE_*`
(`page_templates.py:364`, `:410`, `build_assets.py:291`). Measured on this build:

```
_demo_site/from/grantham/index.html: 38 KB total, 0 KB css, 22 KB script, 0 KB payload, 0 rows
_demo_site/index.html:               28 KB total, 22 KB css, 3 KB script, 0 KB payload, 0 rows
identical on all 2 measured pages: 0 KB, 0% of the largest page
```

The station page's inline data is counted as script, so its own payload and row
count are both 0, and because the payload is then part of "code", `identical_bytes`
returns 0 for two pages whose only difference *is* the payload. The budget gate
still passes because `--site` sums file sizes, which is why nothing has failed.
`tools/test_page_bytes.py` feeds the tool `const DATA = ` fixtures by hand
(`:34, :59, :66`), so the tests agree with the tool and not with a page.
Recommend: build the marker list from the thing that writes the page
(`page_templates`/`build_assets`), and add one test that measures a page
`render_page` actually produced. This is the single highest-value fix in the
document: the open decision about the 354 KB page (14 October engineering audit,
recommendation 6) cannot be re-measured while the instrument returns 0.

**E2 [high] Every station page blocks parsing on the whole network's station
list.** `build_assets.station_asset_tag` (`build_assets.py:296-306`) emits a plain
`<script src>` with no `defer` and no `async`, and `page_templates.py` places
`__STATIONS_SRC__` immediately before the inline `window.TBE_DATA` block. A classic
script blocks the parser, and the route's own script runs after parsing, so first
paint of the table waits on a file that exists for a control most readers never
open. The list scales with the network (2,712 rows at the last count, each a name,
a CRS and a href; I did not measure its bytes on the real release). Recommend:
`defer` as the one-attribute fix, or fetch it on first interaction with the change
control, which is the shape `ADR-0033`'s fetch boundary already permits.

**E3 [medium] The render path substitutes into its own output and asserts almost
none of it.** `render_page` performs 42 `.replace()` calls on the whole document,
inserting the per-origin JSON at `__DATA__` first, then substituting `__NOTE__`,
`__BASE__`, `__BUDGET__` and the rest across the payload it just embedded. Only two
placeholders are proved absent afterwards (`build_render.py:303`, `:308`). A
placeholder added to the template and forgotten here ships literally into every
page of the release, and a feed-supplied string containing `__BUDGET__` is silently
rewritten. Recommend: one final assertion that `re.search(r"__[A-Z_]+__", page)` is
empty, which is the same guard `page_templates._shared_script` already applies to
its blocks.

**E4 [medium] The resume key is weaker than the cache key, for the exact case the
cache key was written to survive.** `build_state.resumable_signature` (`:160`)
identifies a station build by `feed_fingerprint`, which is name, size and mtime,
while `feed_content_digest`'s own docstring names the case this misses: an archive
extracted with the dates stored in it. A replacement with the same size and
timestamps invalidates the fares cache (content-keyed, so it re-parses) and resumes
every page as complete, leaving a release that quotes the previous download beside
freshly parsed data. Recommend: key the resume signature on content, or state in
the docstring that resume is deliberately cheaper and why the disagreement is
acceptable. Read, not reproduced.

**E5 [medium] Tidying the release reads the whole release.** `build_assets.prune_shared_assets`
globs `*.html` under the output folder and reads every page to collect the asset
names in use, to answer a question about three filenames. On a full-network build
that is reading the whole site (at the last measured 354 KB per station page) at
the tail of a build that already takes hours. Recommend: take the answer from the
release manifest, which the same process just wrote.

**E6 [medium] The shard merge parses the whole fares feed to answer a set
question.** `build_pool.merge_shards` loads the feed and uses only
`locations_by_crs` to check that the shards partition it. That is a full parse in
the process whose entire reason to exist is to be cheap at the end of a
distributed build. Recommend: a locations-only load, or the union the shard
manifests already carry.

**E7 [medium] The opening budget is a literal in five places and absent from the
release.** `budget_pounds=20` appears at `build_pool.py:646`, `:1045`, `:1184`,
`:1205` and `build_workers.py:334`, and there is no `--budget` flag. A merged
release therefore opens at £20 by construction, and the shard manifest's `release`
dict does not carry the figure, so the merge could not learn a different one.
Recommend: one constant in one module, threaded through `shared`/`release`.

**E8 [low] The privacy page's one unescaped substitution.** `render_privacy`
inserts `__CONTACT__` without `html.escape` while every other string on that route
is escaped. The value is operator-supplied, so the blast radius is small; an
address containing `&` still becomes markup on the page whose promise is that it
says exactly what the build does. Recommend: escape it, one line.

### How the page holds its state

**E9 [high] The page's state is the DOM, read by four independent consumers, and
a render is a full teardown.** `unit()` and `ticketMode()` query radio groups,
`chosenCard()` queries the select, `priceOf()` calls `unit()` inside the sort
comparator. Measured consequence: open a row, type a new budget, and the row's
`aria-expanded` goes from `true` to `false` and the detail rows go to zero, because
`rows.replaceChildren()` (`page/station/table.js:153`) rebuilds the list and the
open CRS is not carried. Read consequence in the same shape: the sort comparator
calls two DOM readers per comparison, so a 334-row list does thousands of queries
per render. Recommend: one `view` object derived once per render (`unit`, mode,
card, cap, list of priced rows), passed to the renderers, with the open CRS kept
beside it. This is the same defect as the critique's C8, filed here for its cause;
the reader-facing half stays there.

**E10 [medium] One sentence has two owners.** `page/station/table.js:198` and
`page/station/ticket-modes.js:228` compose "No destinations for up to £X …" from
the same inputs, one into `#summary` and one into `#empty`, so an empty list prints
it twice one line apart. Measured. The distill's D2 owns the reader-facing
recommendation; the engineering half is that the sentence needs one function and
two call sites, not two functions.

**E11 [medium] The railcard control is rebuilt on every budget keystroke.**
`syncRailcardParty()` runs from `render()`, and `render()` runs on every `input`
event of the budget slider, so the option list is torn down and rewritten at drag
frequency. Read, plus platform behaviour inferred: an open native `<select>` can be
dismissed by having its options replaced underneath it. Recommend: sync only when
the eligible set changes, which is a comparison the payload can answer cheaply.

**E12 [medium] Page-level elements are owned by the wrong panel.** `#summary` and
`#empty` are declared in `service-day.js` and written by `table.js`; `#more` is
declared in `filters.js` and written by `table.js`; `currentPage` and the pager
handles live in `filters.js`. A maintainer changing the count line has to find
three files before knowing what may write it. Recommend: move the declared
elements to the panel that writes them, or to `payload.js`, which is already the
one place the page's elements are read. No new abstraction: this is a move.

**E13 [medium] Sixteen concatenated panels with order-dependent top-level
statements.** `page_templates.STATION_SCRIPT_PARTS` documents the order and why,
which is good practice for a constraint that should not need to exist.
`page/station/url-state.js:13` takes `DEFAULT_MODE` from the checked radio at parse
time, so it only works because it is concatenated before `wiring.js` applies the
URL. Nothing but the Playwright suite exercises the ordering. This is the price of
the one-file promise and I am not recommending modules; recommend: a check that
loads the built asset and asserts it parses and runs with the panels in the
declared order (the suite already proves this indirectly), plus a comment at
`DEFAULT_MODE` naming the ordering as the invariant it depends on.

### The checks that are supposed to catch this

**E14 [high] The phone table is exercised for overflow, never for where text
landed.** At 390px `tests/browser/station-fares.cjs` asserts three things about the
stacked table: the document does not overflow (`:37`), the last cell's rect is
inside the viewport (`:41`), and each row carries one border. A cell measured at
**1px wide** with its link painting 48px outside it passes all three. Measured:
that is exactly the Tickets cell today, and its label is inline with the link.
Recommend: assert per cell that the number of distinct line-box tops in its own
value is what the design says it is, at 390 as well as at desktop.

**E15 [medium] The wrap detector exists, with the two broken cells excluded.**
`tests/browser/station-render.cjs` already counts line-box tops more than 3px apart
(`lines()`), which is the technique that would report the station cell as three
lines. Its cell list is `thead th` plus `td.num` plus `.fare-type`, which omits
`td[data-label="Station"]` and the last cell. A naive inclusion would also fail on
the deliberate `site-proof` subline, so the assertion has to be per run of inline
text, not per cell. Recommend: extend the detector and run it at 390; the render
section currently runs only at the context's default width.

**E16 [medium] The mobile layout's rules are asserted as text, and the text
passes.** `tests/test_build_demo_page.py` asserts that the media block contains
`grid-template-columns: 5rem minmax(0, 1fr)`, the `::before` label rule and the
border rules. All present, all passing, with both defects in place, because the
failure is the interaction between `td > *` (track two) and a bare text node (no
track). A text assertion cannot see that. Recommend: replace the layout half of
that test with the browser assertions of E14/E15 and leave the Python test
asserting only what it can honestly check (that the media query exists at 44rem).

**E17 [low] A chip's count leaks into the empty-state sentence.**
`page/station/filters.js:69` builds the type label from
`input.parentElement.textContent`, and the label is
`<span>Cities</span> <span class="chipcount">(2)</span>`
(`build_render.py:269`), so a sentence would read "…in cities (2)". Reachable only
when two refinements combine, because a chip is withdrawn before it can empty the
list by itself; I could not construct it in this build. File it as latent rather
than as a reader-visible defect: the fix is to read the label span, which
`chipLabel()` already does elsewhere in the same file.

**E18 [low] Three housekeeping items in the page's script.** `clock` is shadowed at
`page/station/provenance.js:333` over `format.js:8`'s formatter, so any future call
inside that function throws. `attachStationField`'s `cap` option has no caller and
its return object is read by nobody (`page_templates.py:498`), so both are surface
without a use. `const shortlist = shortlistDock` in `shortlist.js` is an alias from
the removed in-page section. Each is a deletion.

### The one file a person reads to decide what to do next

**E19 [medium] `docs/open-work.md` is 1,035 lines, most of it a record of work that
is finished.** It carries the settled history of every audit, including the fifty
findings of the 14 October clarity audit, and the code cites 45 "audit item N"
locations whose numbers live in that file. Answering "what is open" means reading
two thirds of a closed record first, which is reader load paid by the one person
the file exists for. Recommend: the file holds open work only; settled items move
to the audit document they came from (or to one archive file), and code comments
cite the ADR or the test that holds a decision rather than a number in a moving
document. This is not a documentation style preference: 45 comments now depend on a
file whose purpose is to shrink.

## Pruned for overlap

These subjects appear in more than one document from this pass. The duplicate was
deleted from the audit where it was least useful, not merged into both.

| Subject | Kept in | Dropped here |
|---|---|---|
| The phone table's stacked row, as a reader experiences it | critique C1, C2, C13; distill D8 | The recommendation to rebuild the row; this document keeps only the check that would catch it (E14, E15). |
| The empty state's repeated sentence | distill D2 | The wording recommendation; this document keeps only the ownership fault (E10). |
| The 354 KB page and what it costs to parse | 14 October engineering audit, recommendation 6 | Not re-filed. E1 explains why that open decision currently cannot be measured. |
| The chooser's dropdown placement | critique C11 | No engineering finding: the mechanism is working as its comment intends, and the disagreement is a design call. |
| The closing of an open row when the budget changes | critique C8 | The reader-facing description; this document keeps the state model behind it (E9). |
| The prices-only page's timetable sentence | critique C5 | No second filing. E16 covers the missing check for it only as part of the layout-test question. |

## What is already right, and would be a mistake to trade away

- **Failure modes refuse rather than guess.** A public build with no notices stops;
  a missing brand mark stops; a slice index with a gap names the codes before the
  build starts. For a page whose numbers are the product, that default is the
  product.
- **The cache identities are content digests with the reason written down**
  (ADR-0031). E4 is a mismatch between two identities, not a flaw in either.
- **`page_is_current` compares the markup around the payload byte for byte, and the
  asset names are part of the resume signature**, so a template or `page/*` change
  already cannot be resumed past. The stale-markup case is closed; do not reopen
  it while fixing E4.
- **The browser suite's skip budget** is the right shape for a project whose pages
  differ enormously in what they can exercise: a check a page cannot exercise is a
  skip, and the budget stops skipping from reading as a pass.

## What I could not establish

- No real-feed build. Every figure is of a 3-station demo page; nothing here
  measures the 2,712-page release, and E1 is why the obvious instrument would not
  have answered it anyway.
- E4 (resume identity) is read from the code, not reproduced with a crafted feed.
  Reproducing it needs two ZIPs of equal size and timestamps, which is a fixture
  question for `make_synthetic_feed.py`.
- E11's platform behaviour (an open select being dismissed when its options are
  replaced) is inferred from how native selects behave, not observed: this session
  drove headless Chromium, whose select popup is not the platform's.
- No real phone. 390px in Chromium is a viewport, not a device; the row heights and
  the fragment positions are exact for that viewport and should be re-measured on
  hardware before anyone quotes them as a device figure.

## If someone picks this up

Three units, each ending in a check, in this order:

1. **Make the instrument honest (E1).** One marker list, one test that measures a
   page the renderer wrote. Nothing else in this document can be verified until the
   tool reports a payload again.
2. **Fix the two defects a reader sees (critique C1, C2 via distill D8), and hold
   them with E14/E15.** The check comes with the fix, so the regression is closed
   the same day the row is rebuilt.
3. **Then the state model (E9, E10, E12).** It is the largest change and the one
   with the least visible payoff, which is exactly why it should follow the two
   that a reader can see.

The rest (E2 to E8, E11, E16 to E19) is independent and can be taken in any order;
E2 is one attribute, E8 is one call, and E19 is a file move.
