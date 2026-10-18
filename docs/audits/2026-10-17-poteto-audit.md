# Engineering audit: what to improve, and the instrument that would prove it

**Date:** 17 October 2026
**Reviewed:** `main` with that day's uncommitted work. The three published routes,
the build that writes them, the tools that measure them, and the checks that hold
them.
**What it is:** a read-only audit. No file in the repository was changed in
producing it. Every finding is a numbered recommendation with the evidence that
produced it. All nineteen were answered on 18 October 2026; "Answered since this
was written" records what closed each one and which check holds it, and the
finding text above it stays as it was filed so the recommendation that changed
can be read beside the reason it changed.
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
- **Encode lessons in structure** is the reason the test findings (E13, E14, E15;
  all three answered on 18 October 2026, in the table below) do not say "be
  careful with the stacked table". They name the assertion and the place it belongs,
  because the repository already writes the analogous check for every other cell.

## Findings

Severity is about cost to the product, not effort: **high** means a reader or a
release decision is being misled now, **medium** means a maintainer pays on every
change, **low** is housekeeping.

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

### How the page holds its state

**E9 [high] An open row still closes on every render.** The state half landed
(R4 of the 18 October 2026 plan): `page/station/state.js` is the one object,
`unit()` and `ticketMode()` read it, and the sort comparator no longer queries
anything. What did not land is the open CRS. `rowPanel` is a `WeakMap` keyed on
the row element (`page/station/fare-panel.js:160`) and `rows.replaceChildren()`
(`page/station/table.js:156`) replaces those elements, so a reader who opens a
row and types a new budget gets the row closed and the detail gone. Measured
before the state half: `aria-expanded` goes from `true` to `false` and the detail
rows go to zero. Recommend: keep the open CRS in `STATE` beside the rest of the
search and re-open that row after the list is rebuilt. This is the same defect
as the critique's C8, filed here for its cause; the reader-facing half stays
there.

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

## Answered since this was written

All nineteen findings are closed and pruned, all on 18 October 2026: the eight of
the first pass, the phone-table group, the state and ownership ones, and the last
two of the build group. Each row names the check that would fail if the defect
came back, because the check is the part that keeps it closed.

| | What proves it |
|---|---|
| **E1** — the page-size tool reported 0 payload and 0 rows for every station page | `python -m tools.page_bytes _demo_site/from/grantham/index.html` reports 39 KB total, 19 KB payload and 16 rows. R1–R3 of the 18 October 2026 plan built the markers from `page_templates`, made the tool exit 2 on a payload it did not parse, and its test measures a page `render_page` wrote. |
| **E2** — every station page blocked parsing on the network's station list | `build_assets.station_asset_tag` writes `defer`, and `tests/test_build_demo_page.py` reads the tag out of a rendered page. |
| **E3** — 42 substitutions, two of them asserted | `build_render.refuse_unfilled` sweeps the whole document on all three routes; its tests render each route, assert no placeholder survives, and assert that a note naming one is refused. |
| **E8** — the privacy contact was the one unescaped substitution | `render_privacy` escapes it, and the provenance tests read an address carrying `<` and `&`. |
| **E9** — an open row closed on every render | `STATE.openCrs` holds the row a reader opened and `reopenOpenRow` puts it back after the rows are rebuilt, so the panel and the fare inside it survive a budget move. `tests/browser/station-rows.cjs` drives it as a reader does — open a row, then type a budget — and reported `stillOpen: false` with the state half removed. |
| **E13** — order-dependent top-level statements | `DEFAULT_MODE` is `STATE.mode` and the comment names the ordering as the invariant it depends on; the browser suite loads the built asset on every page it drives. |
| **E17** — a chip's count leaked into the sentence that named it | `typeLabel()` reads the label span, and the browser suite checks the sentence for every chip it presses. With the old read put back it reported `in cities (1)`. |
| **E18** — three housekeeping items | `tests/test_page_assets.py` holds all three: no local declaration shadows a shared function, no top-level constant only renames another, and every option the shared station field reads is passed by a caller. The last check found a second unread option (`onUse`) and the shadow check found a second shadow (`unit` in `url-state.js`); both were removed with these. |
| **E10** — one sentence, two owners | `emptyListSentence(cap, what)` is the one composition, called by the count line and by the empty state. `tests/browser/station-filters.cjs` asserts the two are the same sentence character for character on a page with an empty list, and reported two different ones when the empty state added a clause of its own. |
| **E11** — the railcard list rebuilt at the budget's drag frequency | `writeRailcardOptions` runs only when the party changes, so a budget keystroke leaves the list alone. The browser suite marks the list and types a budget; with the guard removed it reported `kept: false`. |
| **E12** — page-level elements owned by the wrong panel | `#summary`, `#empty`, `#more`, `#pagination`, `#pageStatus` and the two pager buttons are read in `page/station/payload.js`, the one place the page's elements are read; `filters.js` and `service-day.js` keep only what they write. |
| **E14** — the phone table was exercised for overflow, never for where text landed | `tests/browser/station-layout.cjs` measures every cell of every row at 390px: two tracks, every painted line of the value starting in the value track, nothing painting outside its cell, and the numbers and the ticket link one line each. With the station cell's wrapper removed it reported `worst: -89px`; with the last cell's `width: auto` removed, a 1px Tickets cell painting 88px outside itself. |
| **E15** — the wrap detector existed with the two broken cells excluded | The detector in `tests/browser/station-render.cjs` now measures every run of every cell, prose runs (a site proof, an interchange, a split note) excluded by class, and the station and tickets cells are in the set. A 3rem `.station-value` at desktop reports `{"cell":"Station","lines":3}`. |
| **E16** — the mobile layout's rules were asserted as text, and the text passed | `tests/test_build_demo_page.py` keeps the media query and the markup-is-a-table claim; everything else it asserted is now geometry in `station-layout.cjs` at 390px. |
| **E4** — the resume key was weaker than the cache key | `resumable_signature` and the shard agreement are keyed on `feed_content_digest`, not on names, sizes and mtimes; `tests/test_atoc_knowledgebase.py` gives two feeds of equal size and the same mtime different bytes and gets different keys. |
| **E19** — `docs/open-work.md` carried two thirds of a closed record | The settled record moved to `docs/settled-work.md` on 18 October 2026, with the audit-item numbers code comments cite; `open-work.md` is 825 lines from 1,133 and holds open work only. |
| **E7** — the opening budget was a literal in five places | `build_release.OPENING_BUDGET_POUNDS` is the one constant, the shard manifest carries it in `release`, and the merge opens at the shard's figure. `tests/test_page_runner.py` refuses a `budget_pounds=<number>` literal and reads the manifest. |
| **E5** — tidying the release read the whole release | `prune_shared_assets` is given the pages this build wrote and does not read them, because a page it rendered requests its own names and nothing else; only a page an earlier build wrote can name an older asset. `tests/test_page_output.py` records every `read_text` the prune makes and asserts the station page it wrote is not among them, and a leftover page that names a stale asset still protects it. The recommendation as filed, to take the answer from the manifest, cannot answer the question: the names that must be kept belong to pages the manifest does not describe, so the fix is which pages are read rather than where the names come from. |
| **E6** — the shard merge parsed the whole fares feed to answer a set question | `FaresDb.load_feed(..., locations_only=True)` reads the `.loc` file through the same `read_feed_files` dispatch, and `merge_shards` asks only the locations question. `tests/test_atoc_fares.py` proves the cheap load returns the map the full one returns and reads only `rjfaf.loc`; on the real feed the load went **37.7 s → 0.3 s**, the same 3,436 stations, measured 18 October 2026 in `docs/build-performance-findings.md`. |

## Pruned for overlap

These subjects appear in more than one document from this pass. The duplicate was
deleted from the audit where it was least useful, not merged into both.

| Subject | Kept in | Dropped here |
|---|---|---|
| The phone table's stacked row, as a reader experiences it | critique C1, C2, C13; distill D8 | The recommendation to rebuild the row; this document kept only the check that would catch it (E14, E15), which landed on 18 October 2026. |
| The empty state's repeated sentence | distill D2 | The wording recommendation; this document keeps only the ownership fault (E10). |
| The 354 KB page and what it costs to parse | 14 October engineering audit, recommendation 6 | Not re-filed. The instrument that could not measure it has been repaired (E1, answered), but this pass did not re-measure the release. |
| The chooser's dropdown placement | critique C11 | No engineering finding: the mechanism is working as its comment intends, and the disagreement is a design call. |
| The closing of an open row when the budget changes | critique C8 | The reader-facing description; this document keeps the state model behind it (E9). |
| The prices-only page's timetable sentence | critique C5 | No second filing: the layout-test question E16 raised was about the phone table, and C5's own check is in `tests/test_build_demo_page.py`. |

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
  measures the 2,712-page release. The instrument E1 was filed against now reports
  a payload, so that question can be measured again, but this pass did not.
- E4 (resume identity) was read from the code when this audit was written. It
  is now held by a unit test over two files of equal size and the same mtime,
  which is the part of the crafted feed that mattered; the end-to-end case -- a
  resumed build that must not skip -- still has no fixture, and the key is what
  the unit test pins.
- E11's platform behaviour (an open select being dismissed when its options are
  replaced) is inferred from how native selects behave, not observed: this session
  drove headless Chromium, whose select popup is not the platform's.
- No real phone. 390px in Chromium is a viewport, not a device; the row heights and
  the fragment positions are exact for that viewport and should be re-measured on
  hardware before anyone quotes them as a device figure.

## If someone picks this up

Nothing is left. Every finding this audit filed is closed, each with the check
that would fail if it came back, and the two that were argued before they were
fixed carry the reason the recommendation changed: E5's manifest idea could not
answer the question, and E6's second dispatch was one keyword on the existing one.

The pass that closed the last two made no page change. E5 removes a read and E6
replaces one; neither moves a byte a reader receives, which is why the browser
suite is not part of their evidence.


