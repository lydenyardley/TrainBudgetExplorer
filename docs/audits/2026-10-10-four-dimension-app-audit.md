# Whole-app audit — the four dimensions

**Date:** 10 October 2026. **Pruned 11 October 2026:** thirteen of its fourteen
recommendations have been implemented and the one that remains is a person's
decision, rewritten in plain words below. The scores and the findings are the
audit's own reading of the 10 October state and are kept as the record of what
was found; the settled table near the end is what the fixes are held by.
**Fixtures widened 12 October 2026.** The skip figure this audit recorded — 69 of
815 checks (8.5%), over the suite's own 5% budget — was a property of its fixtures
rather than of the suite: the shape feed priced each secondary origin to a single
station, and neither fixture build carried a service date, so the checks about the
day the table reports and about a page's own controls had nothing to read. The feed
now takes the demo feed's `--third-origin --return-network`, both dated builds
report Monday 5 October 2026 (`tools/verify.py`'s `SERVICE_DATE`, which the workflow
reads rather than naming a second date), and the shape route is `one-page`, because
what fits on one page is a list rather than a row. Re-measured on the same five
pages on 12 October 2026: **830/830 checks passed, 25 of 824 skipped (3.0%), the run
exits 0** — demo station 257/257 (3 skipped), chooser 71/71 (1), privacy 31/31,
one-page station 254/254 (5), prices-only 217/217 (16). The 16 are the journey and
day checks a build with no timetable cannot run.
**Commit reviewed:** `1ecd719` on `main`, with the working tree's uncommitted edits
present: `README.md` and the pruned `docs/audits/2026-10-09-impeccable-route-audit.md`.
**Scope:** the whole app — the build (`build_demo_page.py`, `build_workers.py`,
`page_templates.py`, `page/`), the feed layer (`atoc_fares.py`, `atoc_timetable.py`,
`atoc_restrictions.py`, `atoc_knowledgebase.py`), the runner and operator tools,
the tests, and the three generated routes.
**Method:** the `/audit` four dimensions — SPEC, DESIGN, CORRECTNESS, QUALITY —
with CORRECTNESS graded from behaviour actually exercised (the repo's own
Playwright suite plus a hand-driven pass over the built pages), not from re-reading
claims. **No code was changed by this audit.** This file was the deliverable.

## Scores

| Dimension | Score | One line |
|---|---:|---|
| **SPEC** | **7/10** | The contract in `PRODUCT.md` is implemented and exercisable end to end on the synthetic feeds. The entry route is missing the provenance line the product principles promise, its first screen can cover or swallow the page's own prose, and the privacy notice carries one sentence that points at the wrong direction. |
| **DESIGN** | **5/10** | Real seams exist (parsers, page assets, worker plumbing, tests by feature), but four units a change lands in are monoliths: `main()` 1,001 lines, `FaresDb` 2,401, `page/station.js` 2,737, `tests/browser_test.cjs` 7,163. |
| **CORRECTNESS** | **7/10** | The browser suite passed **777/777 checks on 5 pages**, 0 failures, and the main flows were driven by hand. One real defect was reproduced (the chooser's open list swallows a click meant for the page's intro and opens a station), one copy defect was found, and 8.5% of the suite's checks could not run — the run exits 1 on its own skip budget by design. |
| **QUALITY** | **6/10** | The release-writing block is written twice, `matches()` is duplicated between two assets, and the largest functions cannot be read in parts. Directly removable lines are modest (≈40–60); the real cost is structure, not length. |

## What was exercised

- **The repo's own browser suite**, run over five freshly built pages (the demo
  station page, chooser and privacy page, the one-row shape's station page and
  the prices-only page): **777 checks passed, 0 failed, 5 of 5 pages checked**;
  69 of 815 checks (8.5%) were not exercised by these pages, over the suite's own
  5% budget, so the run exits 1. Per page: demo station 245/245 (13 skipped),
  chooser 72/72 (1), privacy 31/31, one-row station 213/213 (39), prices-only
  216/216 (16).
- **A hand-driven pass** over `_demo_site` and `_shape_site` served over HTTP:
  the chooser's completion (typing `gran` completes `GRANTHAM`, one match shown),
  the click-through defect below, a station page fetched exactly its two shared
  documents (`station-<digest>.css`, `stations.js`) with no console errors, the
  one-station release root, the prices-only opening sentence and stood-down Time
  and Changes columns, the privacy page, and the stylesheet-missing fallback
  (plain text, no theme switch, every price still listed).
- **Unit suites**: `tests.test_build_demo_page`, `tests.test_page_output`,
  `tests.test_page_gates`, `tests.test_service_week`, `tests.test_page_assets`
  and `tests.test_agents_map`: **259 tests in 80.5 s, 1 failure** —
  `tests/test_page_assets.py::test_no_asset_carries_a_carriage_return`, on
  `page/station.js`; see CORRECTNESS gap 3.
- **Rebuilt fixtures** with the exact commands `tools/verify.py --browser` uses,
  from the current tree: the demo feed and site, and both shape builds.

## SPEC — 7/10

The product contract is broad, and nearly all of it is present and working: price
first per station, budget ceiling, filter chips with named proof, party and
railcard pricing, three ticket sets plus the cheapest-of-any-type opening list,
per-row details, shortlist copy/share, date-aware schedules, the prices-only
state, the one-station release root, the privacy notice generated from the build,
and ticket links that are the seller's plain search page. Nothing found here is
built beyond what `PRODUCT.md` and the ADRs record.

Highest-value gaps, in order:

1. **The entry route has no provenance.** A real build passes `note=""`
   (`build_demo_page.py` uses the synthetic note only for the synthetic default),
   so the chooser — the page every community link points at — says what the
   ordering is but not what the site is, whose feed its prices came from, or how
   old that feed is. The station page already has all of it. (Route audit item
   [6], still open.)
2. **The entry route can hide its own explanation and hijack a click.** The field
   is focused on load (`page/chooser.js:161`), so the list opens as a fixed panel
   over the intro and ordering sentences; with a completion in the field,
   clicking the intro paragraph navigates to the completed station's page —
   reproduced by hand at 690×867: a click aimed at prose opened
   `/from/grantham/`. (Route audit item [3]; the unbounded directory state,
   item [4], is 51,770px at 1440px and 153,923px at 390px on a full-network
   build.)
3. **One privacy sentence points the wrong way.** The practices bullet reads
   "what stays in the address bar, below, explains it in full"
   (`build_demo_page.py:3013`), but that section sits above it
   (`page_templates.py:65` before `:72`). The route audit's item [18] would move
   the sections and make the word true; until it lands, the copy is wrong. The
   page also still prints no build date (item [16]).

Not counted against SPEC, because they are recorded decisions or blocked on a
person: the whole-network release cannot publish until the `privacy contact`
product is cleared (`licences/release-clearance.md` holds it `excluded`;
`tools/check_release_clearance.py` refuses), the fares licence's commercial terms
are unread, and the station picker legitimately needs a known name or code
(`docs/open-work.md`, C27).

## DESIGN — 5/10

What is already right: the feed parsers and the page templates are separate
modules; the page's real source is `page/*` files, not Python strings; the worker
pool is split out of the builder; the tests are split by feature seam around a
shared harness; ADRs own the decisions. Those are seams a maintainer would keep.

Highest-value gaps:

1. **`build_demo_page.main()` is 1,001 lines** (`build_demo_page.py:3270–4270`)
   and contains the release write twice: the all-origins path (≈4060–4132) and
   the single-origin path (≈4196–4245) each render the chooser, write the privacy
   page, crawl links and write-and-verify the manifest — with different writers
   (`root.write_text` vs `write_page_atomic`) and different `builtAt` sources.
   One `write_release(out_dir, routes, …)` used by both would delete the
   duplicate and make the two shapes produce one code path.
2. **`FaresDb` is 2,401 lines and 85 methods** (`atoc_fares.py:2636–5036`),
   holding the loaded feed, the loader/fallback machinery, location lookup,
   railcard rules, two-part fares and the destination query in one class. The
   class's own state is fine; its surface is not — a change to any one query
   means opening 2,400 lines.
3. **`page/station.js` is 2,737 lines, 94 named functions and eight module-level
   mutable variables**, with no seam between the filters, the shortlist, the
   railcard pricing and the row rendering. Its only executable decomposition is
   `tests/browser_test.cjs`, which is itself 7,163 lines (the open half of F6 in
   the 8 October 2026 audit). Splitting either is only verifiable once the other
   is splittable; they are one project, not two.

## CORRECTNESS — 7/10

Exercised, not asserted: the suite's 777 checks (real clicks, typing, keyboard
and viewport changes), the hand pass over four route states, and the unit subset
above. The product's hard claims held where probed: exactly two fetched documents
on a station page, none on the chooser or privacy page; ticket links to the
seller's plain search page; the stylesheet-missing fallback keeps every price and
offers no theme switch.

Highest-value gaps:

1. **The chooser list can swallow a click meant for the page.** Reproduced by
   hand: with a completion in the field, a pointer click on the intro paragraph
   moved the panel under the field and the click landed on the completion link,
   navigating to `/from/grantham/`. This is the same defect as SPEC gap 2 seen
   from the user's side — a click on prose must never leave the page.
2. **The privacy bullet's positional word is false** (SPEC gap 3) — small, but it
   is on the page that promises to say unflattering things plainly.
3. **Two evidence limits are real and should not read as passes.**
   `tests/test_page_assets.py::test_no_asset_carries_a_carriage_return` **fails on
   this Windows checkout**: the working-tree `page/station.js` has 2,737 CRLF line
   endings while its `HEAD` blob is LF (`core.autocrlf=true` hides the difference
   from `git status`). The build normalises assets (`_page_file` reads LF, proven
   by the passing sibling test), so releases are unaffected — but the documented
   `python -m unittest` does not pass on a Windows checkout. Separately, the
   browser suite could not exercise 69 of its 815 checks on these fixtures
   (8.5%, over its own 5% budget), which is why the run exits 1; the pages under
   test have too few destinations to reach those checks.

## QUALITY — 6/10

Concision, graded against the smallest version of the same behaviour:

1. **The release-writing block is duplicated** (≈70 lines: chooser render, privacy
   render, link crawl, manifest write, manifest verify, report line) with two
   different writers and two different clock sources for `builtAt` — the
   duplication is both the largest removable block and a place where the two
   build shapes can drift.
2. **`matches(station, needle)` is duplicated verbatim** at `page/chooser.js:26`
   and `page/station.js:202`. The fix location already exists: the shared JS
   blocks (`LIST_KEYS_JS`, `STATION_FIELD_JS`) in `page_templates.py`.
3. **Long stretches of `main()` are report-only print blocks** repeated between
   branches, and one call is not even indented consistently
   (`render_chooser(` at ≈4196), a sign that no unit of the function is read as a
   unit. Directly removable lines are ≈40–60; the larger win is that a reader of
   any one phase no longer has to hold the whole function.

The comment style is not counted against QUALITY: this repo asks comments to say
why, and they do.

## Recommendations

**Pruned 11 October 2026.** Thirteen of this audit's fourteen recommendations
have been implemented and each closure is held by an artifact, listed in the
settled table below. One is a person's decision rather than work, and it is
rewritten here in plain words. This is the whole of what the audit still asks
for.

### The one open item: decide or render the non-fare routes' notices

**The question, in plain words.** When a build is given licence and attribution
notices (`--notices nre,rdg,ogl,accuracy`), where do they appear today? Only the
station page (`from/<slug>/`) carries them. The two other routes a release
serves — the chooser at `/` and the notice at `/privacy/` — contain no licence or
attribution wording at all.

**Why it is a question and not a bug.** The station page is the one route that
shows a price. The licences and attributions the operator supplies say who the
fares and times are sourced from, and those words belong beside the numbers.
Whether that obligation must also ride on the chooser and the privacy page is a
judgement about the licence terms themselves, which this project cannot make
alone.

**There are two ways to close it, and both are legitimate.**

1. *Record the decision* that the notices travel with the pages that show fares,
   and add the build check that proves it — so a future route added to a release
   is caught if it shows fares without carrying the notices (route audit [21]).
2. *Render the notices* on the chooser and the privacy page too, so every route a
   release serves carries the attribution (route audit [20]).

**What it needs from a person.** A decision about which, made the way the rest of
this project's licence questions have been: a written, dated answer in a pull
request, recorded in `licences/release-clearance.md` alongside the other licence
positions. The tool half — a build check that names a route showing fares without
its notices — can be written either way and should be written once the decision
is made.

**The route-audit items are [20] and [21].** This file adds the whole-app view;
the route audit's list remains the register for the route-level findings.

## Settled here, and the artifact that holds each one

| Recommendation | Closed by | Held by |
|---|---|---|
| R1, the chooser opened its list over its own explanation and could navigate on a click meant for prose | the shared field block takes an `anchor` and an `openOn`: the chooser opens on typing and draws the panel over the list's own place, never over the intro | `page_templates.py`'s `STATION_FIELD_JS`, and the browser suite's "a click on the prose leaves the page alone while a completion is in the field" |
| R2, an empty chooser field rendered every station (51,770px) | the directory is capped and says so: a stated top 40 of the true count, the field still the primary path | `page/chooser.js`'s `render()`, the browser suite's "the field opens on a stated top-N of stations rather than the whole directory" |
| R3, the entry route carried no provenance | `render_chooser` takes the build's `price_source` and `feed_date` and prints the station page's own sentence | `build_demo_page.render_chooser`, `tests/test_build_demo_page.py`'s chooser-provenance test |
| R4, the picker capped silently and station search was two behaviours | one `stationMatches` and one `STATION_LIST_CAP` serve both routes, and the picker states its cap in the same sentence the chooser uses | `page_templates.py`'s `STATION_MATCH_JS`, `page/station/picker.js`, the browser suite's picker-cap check |
| R5, the privacy "below" pointed at a section above it | the summary now precedes the deep dive, and a test asserts the order so the sentence cannot drift again | `page_templates.py`'s privacy template, `tests/test_build_demo_page.py`'s order assertions |
| R6, no build date and the deep dive read first | "What this site does" reads first and one dated line under the title dates the build-dependent promises from `builtAt` | `render_privacy`'s `built_at`, the privacy template's `#builtLine` |
| R8, the release was written twice, with two writers and two clocks | one `write_release()` for both shapes, `write_page_atomic` everywhere and one `builtAt` | `build_demo_page.write_release` |
| R9, `main()` was 1,001 lines holding two build scripts | `main()` is 41 lines over five named phases, and the two shapes are `_build_all_origins` and `_build_single_origin` | `build_demo_page.load_inputs` … `release_gates`, and the two `_build_*` functions |
| R10, `build_payload()`'s eight nested closures | a `PageContext` NamedTuple carries the per-page configuration and a `RulePool` owns the rule numbering; every builder is a module-level function | `build_demo_page.PageContext`, `RulePool`, `railcard_detail_for`, `destination_row`, `day_answer` |
| R11, `page/station.js` (2,737 lines) and `tests/browser_test.cjs` (7,163 lines) were monoliths | the station route's script is one file per panel under `page/station/`, concatenated in a named order; the browser suite is one module per route and section under `tests/browser/` | `page_templates.STATION_SCRIPT_PARTS`, `tests/browser/`, and the pages built from this tree passing every check they can run (demo station page 247/247, chooser 71/71, privacy 31/31, one-row 214/214, prices-only 217/217) |
| R12, `matches()` was copied in two route scripts | it is `stationMatches`, in the shared `STATION_MATCH_JS` block | `page_templates.STATION_MATCH_JS` |
| R13, `FaresDb` held its loader and its queries in one 2,401-line class | the loader is a `FaresLoader` mixin in `atoc_fares_loader.py`; `FaresDb` owns the state and the queries unchanged | `atoc_fares_loader.FaresLoader`, `atoc_fares.FaresDb(FaresLoader)` |
| R14, a Windows build emitted CRLF pages while CI emitted LF | every write passes `newline="\n"`, and `.gitattributes` pins `page/*` to LF so the working tree agrees with the blob | `write_page_atomic`, `write_resume_state`, `.gitattributes`, and `tests/test_page_output.py`'s byte test |

## What was measured, and how it was verified

Every closure above was verified against the repository's own commands, re-run
on 11 October 2026: the Python suites through `python tools/verify.py --fast`
(1,079 tests, green, and the page's 18 JavaScript files parsed) and the page
behaviour through the Playwright suite over pages built from this tree — the
demo station page 247/247 (13 checks its fixture cannot reach), the chooser
71/71 (1), the privacy page 31/31, the one-row station page 214/214 (40) and
the prices-only page 217/217 (16), with 0 failures. The one-row page and the
prices-only page exit 1 on the suite's own 5% skip budget by design, which is
the suite refusing to read a small fixture as a whole-site pass.

One thing on this machine is not a closure and is not a regression: a `_site/`
left by a real-feed build of 10 October 2026 fails three of the new checks and
stops early on two more, because it was built before the split — its chooser
has no `STATION_LIST_CAP` and its station pages carry the old script. That is
the previous release driven by the new suite; the pages built from this tree in
the same run pass every check they can run. The figures are this audit's own,
from the tree it was written against.

## Not exercised here, and why

- **The licensed real feeds end to end.** The audit ran on the synthetic fixtures
  the repo's own tests use; the real-feed release build is a whole-network CI job
  (recorded at ~2 hours in `docs/build-performance-findings.md`). No figure above
  is a real-fare claim.
- **The browser checks these fixtures cannot reach** (14 across the three demo
  routes, 16 on the prices-only page, 40 on the one-row page) — the fixtures are
  intentionally small; the suite reports them rather than passing quietly, and
  exits 1 when the tally is over its own 5% budget.
- **Assistive technology and real devices.** Widths and 200% zoom were exercised
  by the suite's matrix; no screen reader or physical phone was.
- **Earlier audits' open items are not re-litigated here.** The route audit's
  list (pruned to the ten open items on 10 October 2026) remains the register for
  the route-level findings; this file adds the whole-app view.
