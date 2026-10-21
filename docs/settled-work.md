# Settled work, and where the record is

**Opened:** 18 October 2026, by moving the closed record out of
`docs/open-work.md` (E19 of the 17 October 2026 poteto audit).

Every item below is closed. None of it is restated here beyond the pointer,
because a reader checking a closure wants the ADR and the test. The file exists
because that record was the largest part of the file whose purpose is to say what
is *open*, and a reader answering "what is open" was reading two thirds of a
closed history first. The numbers cited in code comments as "audit item N" are in
here, under the audit that filed them.

## The record

Every item below is closed. None of it is restated here beyond the pointer,
because a reader checking a closure wants the ADR and the test.

| Item | Closed by | Held by |
|---|---|---|
| S17's first half — one inclusive "up to £X" resolver feeding the heading, the control, the count line and the URL | ADR-0019, in place before this pass | the budget contract tests in `tests/test_build_demo_page.py` |
| S16 — the list is ordered by the price on screen | no code change needed; `render()` already sorted by `priceOf()` | the railcard reading in `tests/browser_test.cjs`, added and recorded as a guard rather than a gate — see ADR-0048 |
| S17's second half — the page says where the budget stops, and the figure is the stop | ADR-0048 | `test_the_page_says_where_the_slider_stops_and_the_figure_is_the_stop`, the tamper that hardcoded £500.00, and the browser suite's two readings |
| S34 — a human-readable feed-change report for the operator | ADR-0049 | `tools/test_feed_change_report.py` |
| C27's sibling findings, C01–C31 | five passes, 27–28 September 2026 | the commits that carried each change; the finding ids that survive as reasons in the code (`C14` in `SHARED_CSS`) |
| Question 1, the release coverage, settled by building every priced station rather than Grantham alone | ADR-0050 | `timeout-minutes: 150` against the measured extrapolation, and `tools/page_bytes.py --site _site` as the only step that reads the release's bytes |
| A railcard is a product with the feed's codes for it, not a code | landed ahead of the page that consumes it, so each unit builds and verifies | `ReviewedRailcardTest` in `tests/test_atoc_fares.py`, six tests over families, aliases, bounds and the absent-code report |
| Question 2, the railcards, with the page offering the reviewed collection, none selected by default, and the browser remembering the choice | ADR-0052 | `RailcardAdultBoundsTest`, and the browser suite's six collection checks, which are the menu, the default, the memory, the address, an unpriced code, and the party rule |
| Question 3, the runner, with the build and the serve as separate commands | ADR-0051, amended by ADR-0055 | `RunnerBuildOrServeTest`, five tests over a site existing, not existing, a flag asking for a rebuild, and sources newer than the build |
| The row names its fare in a word; the feed's code waits in the row's disclosure | ADR-0053, superseding decision 2 of ADR-0040 | `test_result_changes_and_mobile_cells_are_accessible` and `test_table_headers_name_their_columns_and_scope`, and the browser suite's fare-type and Feed-record readings |
| The shortlist is one select and one strip above the table, not a button on every row | ADR-0054 | the browser suite's five shortlist checks, and the select's change listener's tests in `tests/test_build_demo_page.py` |
| The station name in the heading is the field you type into | ADR-0056 | the heading-picker checks, including Escape pressed in the field rather than in the panel |
| The licence notices on the routes that show no fare (route audit items [20] and [21]) — whether the chooser and the privacy notice have to carry the NRE credit | recorded rather than assumed: the credit travels with the page that shows a fare, the chooser's station index and the privacy notice show none, and the alternative reading (render it on every route) is named with the reading | the section "Which pages carry the acknowledgement" in `licences/release-clearance.md`, and `tools/check_source_credit.py` — held by `tools/test_check_source_credit.py`, run over the built site by the assemble job |

### The 8 October 2026 agent-efficiency audit

The audit file was removed on 14 October 2026, when its last finding landed. Its
eight findings are settled here with the artifact that holds each one, and its
four rejected designs are under "Rejected designs, with the reason" at the foot of
this file.

| Finding | Closed by | Held by |
|---|---|---|
| F1, the station page was one 2,938-line string, so no linter or `rg --type js` could see it and half of all fixes landed in it | the page's CSS and JavaScript are real files now, inlined by `page_templates.py` at import time | `page/*.js` and `page/*.css`, `tests/test_page_assets.py` for the seam, and `node --check page/*.js` in `tools/verify.py --fast` |
| F2, there was no agent entry point and the README's file table had drifted to omit 26 tracked files | `AGENTS.md` is the entry point: the map, both verify commands, and a rule table naming each rule's enforcer | `tests/test_agents_map.py` checks the map in both directions, so a module, page asset or operator tool that is not on it fails the suite |
| F3, `tools/replay/` was 7,492 lines of stale page copies that supplied 40% of the hits for `priceOf` and `shortlist` | deleted in `ffad8b3` (8 October 2026) | `git checkout ffad8b3^ -- tools/replay` reads it back. Nothing in the build, the tests or the release referenced it, and `tools/test_replay_driver.py` went with it |
| F4, the CI rebuild fingerprint was a hand-kept three-file list, written twice, and eight of the last 150 commits had changed only unlisted inputs | one script hashes every build input and both workflow steps call it | `tools/build_inputs.py`, held by `tools/test_build_inputs.py`, which fails on a transitively imported module that is not covered |
| F5, there was no single verify command, and the browser suite existed only as 115 lines of bash inside the workflow | `tools/verify.py` with `--fast`, `--full`, `--browser` and `--all`, written in Python so a Windows checkout runs it, called from CI before the feeds are downloaded | `tools/verify.py` itself; `--full` adds the two feed-scale tests its docstring names (and, since 15 October 2026, the type check), and `tests/test_atoc_fares.py` shares its fixture through `setUpClass` |
| F6, the two hot test files were the biggest in the repository | the Python half moved out by feature seam over the fixture in `tests/page_harness.py`, and the JavaScript half was split on 11 October 2026 | `tests/test_page_runner.py`, `tests/test_page_caches.py`, `tests/test_page_output.py` and `tests/test_page_gates.py`; and the browser suite is one module per route and section under `tests/browser/`, with `tests/browser_test.cjs` as the entry point. **Landed 14 October 2026:** those 163 methods are one class per subject over `PageTestCase` in `tests/page_harness.py` -- `DemoPageTest` keeps 52, and `tests/test_build_fares.py` (43), `tests/test_build_provenance.py` (33), `tests/test_build_chooser.py` (19) and `tests/test_build_links.py` (16) took the rest -- the same 180 tests with 179 of their 180 names unchanged (the contact test is rewritten, because route audit item [15] landed in the same pass), and `python -m unittest tests.test_build_demo_page tests.test_build_fares tests.test_build_provenance tests.test_build_chooser tests.test_build_links` green on the 180 in 28 s (14 October 2026) |
| F7, fixture-versus-real-feed gaps recurred | the rule is in `AGENTS.md`: a real-feed defect fix adds the minimal synthetic record with the fixing commit named | the passing-stop record in `make_synthetic_feed.py`, held by a test in `tests/test_atoc_timetable.py` |
| F8, measured figures lived in the README and were withdrawn rather than corrected | the README's measured section is a summary that links | `docs/build-performance-findings.md`, which holds "The whole network, measured" behind the README's link |

### The 10 October 2026 test-suite audit

`docs/audits/2026-10-10-test-suite-audit.md` was removed once its twelve
recommendations landed; the commit that removed it is named at the foot of this
file. Each finding is settled by the artifact that holds it, and the one that
keeps the others done is named last.

| Finding | Closed by | Held by |
|---|---|---|
| F1, the page's JavaScript was proved by quoting it: 154 statement needles over 52 methods, and a one-space edit inside a statement failed the Python suite while the browser suite passed 839/839 over the same page | the needles are gone. A statement the browser suite drives was deleted and left to that suite; one that stood for a fact no browser check drives was rewritten as the fact — an attribute, a rendered string, a payload key | the browser suite's own labels (the address, the fold, the budget, the shortlist, the ticket modes, the picker), which ran 839/839 over five pages |
| F2, `fuzz_feed.check_timetable` had no caller and one of its two tests asserted the opposite of its name | the invariants are wired into `one_round()`, so a schedule that is not a journey fails the round that damaged it | `tests/test_fuzzed_feed.py`: the clean timetable passes, a one-stop schedule is a violation, and a round reports what the check finds |
| F3, two tests asserted the slug rule audit finding A1 replaced, keeping a production function alive that only tests called | `station_slug` and both tests are deleted | the live rule at the boundary that owns it, `tests/test_page_output.py`'s slug-and-folder agreement |
| F4, tests for a download path the command does not take | `download_specs`, `download_dtd` and `download_knowledgebase` are deleted; the one rule they alone carried — each feed is offered its own previous record — moved to a `--dtd all` case on the command itself | `CommandLineTest.test_each_feed_is_offered_its_own_previous_record` |
| F5, a gate that failed on a correct checkout, because `page/*` was CRLF here and LF in CI | `.gitattributes` pins the page assets to LF and the working tree agrees with the blob | `tests/test_page_assets.py` all four, green on Windows |
| F6, dead constants, one of them copied: `atoc_knowledgebase._normalise`, `tools/check_release_clearance.PRODUCT_ID`, `atoc_fares.DESTINATION_FACETS_BY_KEY` | `_normalise` and `BY_KEY` are deleted (the tests index the registry); `PRODUCT_ID` is now enforced by the tool that declares it | `tools/check_release_clearance.py` refuses a manifest row whose product id is not the declared format, and `tests/test_licences.py` imports that one definition |
| F7, `test_atoc_fares.py` reached into load steps: 55 tests called a private method and 53 never loaded a feed | one coherent pass: 17 hand-built equivalents replaced by 19 feed-level cases over `load_feed()`, with the pure functions kept | `FeedBoundaryClassificationTest` in `tests/test_atoc_fares.py` |
| F10, one JS fragment asserted in two files | the picker's shared-field wiring is asserted once, in `tests/test_page_output.py`; the completion itself is the browser suite's | the chooser's completion checks in `tests/browser/chooser.cjs` |
| R11, encode the lesson rather than the list | the rule is a test, and it asks what a needle *is* rather than which punctuation it holds: a needle the page's script only holds inside a string, a template or a comment is copy, a bare name or dotted path is a payload key or a hook, and a needle with letters and real syntax that appears as code is the statement being quoted | `tests/test_test_suite_shape.py`'s `NoPageStatementNeedleTest`; over the committed `tests/test_build_demo_page.py` it reports 268, over the current one none |
| R12, keep the browser suite as the owner of page behaviour and in the release gate | nothing to change: the suite is what the deploy workflow runs over five pages, and the coverage floor is the second net | `.github/workflows/deploy.yml` |

The first version of R11's rule listed fourteen punctuation shapes that make a
needle an implementation quote, and it reported 114 over that same file. The
shape list was the defect: shortening a needle until the punctuation was gone
was enough to pass it -- `var dark = true;` became `dark = true` -- and the
audit's own work had already done that four times without noticing. The rule
now reads the script's structure instead, which is what makes a hole like that
impossible to open, and it finds 268 where the list found 114. Every one of
the 154 the list missed was retired: replaced by a payload fact, a markup fact
or the whole sentence a reader sees, or deleted where the browser suite already
owns the claim, or moved into the browser suite where only a rendered page can
answer it (`tests/browser/station-rows.cjs` reads the opened panel's `colSpan`
against the table's own heading count).

### The 10 October 2026 whole-app audit

The audit file was removed on 14 October 2026. Its thirteen closed
recommendations landed on 11 October 2026; each is held by an artifact, and the
two audits agree: the route audit's items [3], [4], [6], [10], [16], [18] and
[22] are closed by them. Its one open recommendation was the notices question,
settled on 16 October 2026 as the source-credit reading and check in the settled
table above, together with the route audit's items [20] and [21]. Its
browser-suite coverage figures are in `docs/build-performance-findings.md`.

| Recommendation | Closed by | Held by |
|---|---|---|
| R1, the chooser opened its list over its own explanation and could navigate on a click meant for prose | the shared field block takes an `anchor` and an `openOn`: the chooser opens on typing and draws the panel over the list's own place, never over the intro | `page_templates.py`'s `STATION_FIELD_JS`, and the browser suite's "a click on the prose leaves the page alone while a completion is in the field" |
| R2, an empty chooser field rendered every station (51,770px) | the directory is capped and says so: a stated top 40 of the true count, the field still the primary path | `page/chooser.js`'s `render()`, the browser suite's "the field opens on a stated top-N of stations rather than the whole directory" |
| R3, the entry route carried no provenance | `render_chooser` takes the build's `price_source` and `feed_date` and prints the station page's own sentence | `build_demo_page.render_chooser`, `tests/test_build_chooser.py`'s entry-provenance test |
| R4, the picker capped silently and station search was two behaviours | one `stationMatches` and one `STATION_LIST_CAP` serve both routes, and the picker states its cap in the same sentence the chooser uses | `page_templates.py`'s `STATION_MATCH_JS`, `page/station/picker.js`, the browser suite's picker-cap check |
| R5, the privacy "below" pointed at a section above it | the summary now precedes the deep dive, and a test asserts the order so the sentence cannot drift again | `page_templates.py`'s privacy template, `tests/test_build_provenance.py`'s order assertions |
| R6, no build date and the deep dive read first | "What this site does" reads first and one dated line under the title dates the build-dependent promises from `builtAt` | `render_privacy`'s `built_at`, the privacy template's `#builtLine` |
| R8, the release was written twice, with two writers and two clocks | one `write_release()` for both shapes, `write_page_atomic` everywhere and one `builtAt` | `build_demo_page.write_release` |
| R9, `main()` was 1,001 lines holding two build scripts | `main()` is 41 lines over five named phases, and the two shapes are `_build_all_origins` and `_build_single_origin` | `build_demo_page.load_inputs` … `release_gates`, and the two `_build_*` functions |
| R10, `build_payload()`'s eight nested closures | a `PageContext` NamedTuple carries the per-page configuration and a `RulePool` owns the rule numbering; every builder is a module-level function | `build_demo_page.PageContext`, `RulePool`, `railcard_detail_for`, `destination_row`, `day_answer` |
| R11, `page/station.js` (2,737 lines) and `tests/browser_test.cjs` (7,163 lines) were monoliths | the station route's script is one file per panel under `page/station/`, concatenated in a named order; the browser suite is one module per route and section under `tests/browser/` | `page_templates.STATION_SCRIPT_PARTS`, `tests/browser/`, and the pages built from this tree passing every check they can run |
| R12, `matches()` was copied in two route scripts | it is `stationMatches`, in the shared `STATION_MATCH_JS` block | `page_templates.STATION_MATCH_JS` |
| R13, `FaresDb` held its loader and its queries in one 2,401-line class | the loader is a `FaresLoader` mixin in `atoc_fares_loader.py`; `FaresDb` owns the state and the queries unchanged | `atoc_fares_loader.FaresLoader`, `atoc_fares.FaresDb(FaresLoader)` |
| R14, a Windows build emitted CRLF pages while CI emitted LF | every write passes `newline="\n"`, and `.gitattributes` pins `page/*` to LF so the working tree agrees with the blob | `write_page_atomic`, `write_resume_state`, `.gitattributes`, and `tests/test_page_output.py`'s byte test |

The structure work is worth naming here because it is what a later change lands
in. `build_demo_page.main()` is 41 lines over five named phases
(`load_inputs`, `_load_timetable`, `read_provenance`, `price_one_payload`,
`release_gates`) with the two build shapes as `_build_all_origins` and
`_build_single_origin`, and both shapes end in one `write_release()`.
`build_payload()`'s builders are module-level functions over a `PageContext` and
a `RulePool`. `page/station.js` became one file per panel under `page/station/`,
and `tests/browser_test.cjs` became one module per route and section under
`tests/browser/`. `FaresDb` keeps its state and its queries, and the loader it
used to hold beside them is `atoc_fares_loader.FaresLoader`, mixed in.

### The 9 October 2026 non-dev route audit

The audit file was removed on 16 October 2026, when its last two items were
settled: [20] and [21], the notices on the routes that show no fare and the build
check for them, are the settled-table entry above. Twenty of its twenty-two items
are implemented, each held by the commit that carries it
(`git log --grep="audit item"`); the group-to-commit mapping is in `ff84c8b`
(10 October 2026, `docs/audits/2026-10-09-impeccable-route-audit.md`), which
names a commit beside twelve of its items, and its items [3], [4], [6], [10],
[16], [18] and [22] are also closed by the 10 October 2026 work above. Its detector's one finding,
`cramped-padding` on the station slot, is under "Rejected designs, with the
reason".

### The 12 October 2026 build-cost audit

The audit file was removed on 14 October 2026. Its twelve tasks landed, each held
by an artifact and by a command a reviewer can re-run; its figures are in
`docs/build-performance-findings.md`, its two rejected designs are under "Rejected
designs, with the reason" at the foot of this file, and the decisions it amends are
named in its own T12 row. What it left open was three findings: the byte budget,
which is open work O1 in `docs/open-work.md`, and the pair-rule encoding (ADR-0069)
and the sharded release build (the twelve shares of 20 October 2026), which landed.

| Task | What it asked | What landed | Command whose output a reviewer can reproduce |
|---|---|---|---|
| T1 | the station script out of every page | `station-<digest>.js` beside the stylesheet; each page inlines only its own `DATA` | `python -m tools.page_bytes --site _bytes_site` on a controlled two-build comparison; 261,362 → 112,885 bytes on one station |
| T2 | search the service week once for the network, write the facts | the facts store exists and is keyed per origin; the *national* single-pass search was not built, because it would hold the national timetable for the whole build | `python -m unittest tests.test_page_caches.PageFactsTest` |
| T3 | a rebuild keyed per origin | one origin's priced counts and journey weeks keyed by feed; a masked payload comparison skips unchanged writes | `python -m unittest tests.test_page_runner.AllOriginsCliTest` |
| T4 | build in shards and merge | `--shard N/M` and `--merge`, with a merge that proves the partition | the same `AllOriginsCliTest` module's shard cases |
| T5 | measure the release against its budget | measured in the release's own shape: 24 major stations average 2.73 MB a page, a stride sample 806 KB; the with-week shape projects to ~2.2 GB against 800 MB, which is the P1 finding above | `python -m tools.page_bytes --site _stride_site` |
| T6 | fold the pricing pre-pass into the facts pass | the pre-pass replays the counts it already priced; the station index is built from the facts | `python -m unittest tests.test_destination_coverage.ReportTest` |
| T7 | decide what the local default build is | the default is the fast single-origin page again; `--all-origins` requires its acknowledgement | `python -m unittest tests.test_page_runner.RunnerBuildOrServeTest` |
| T8 | publish the per-origin cost distribution | `tools/measure_origin_costs.py`: mean 19.37 s against median 4.74 s, max 105.17 s | `python -m tools.measure_origin_costs --origins AAT,ABA,AAP` |
| T9 | reuse the timetable-derived facts across releases | a fares-only refresh of the network build reuses every journey fact; the store is keyed by feed content, and a single-origin build neither reads nor writes it | the sweep-reuse case in `PageFactsTest` |
| T10 | the same shared-asset treatment for the chooser | `chooser-<digest>.js` beside the release | `python -m unittest tests.test_page_output.SharedStationAssetTest` |
| T11 | check whether hashed assets accumulate | a rebuild removes the hashed files no file in the folder names | `...SharedStationAssetTest.test_a_rebuild_removes_the_hashed_assets_no_page_names` |
| T12 | record what this changes in the registers | ADR-0033, ADR-0047, ADR-0019, ADR-0024, ADR-0050, ADR-0055 and ADR-0032 amended; the findings hold the measurements | `python -m unittest tests.test_agents_map` |

### The 14 October 2026 clarity audit

The audit file was removed on 18 October 2026, when its last finding left the
tree, and its fifty findings are settled here. Forty-four landed on 15 October
2026 in one commit, because the payload keys and the page's reads had to move
together and the templates and their tests carry items from more than one route;
item 1 had already landed in `4234294` with the rest of that day's critiques, and
`git log --grep="audit item"` reads any of them back. Item 8 read a sentence that
was worth leaving as it was, and item 5 offered a warm and a blunt wording, so
this pass chose one (warm) rather than splitting the difference. What was left
after that pass went on 18 October 2026: item 23 landed on its own, item 3 was
settled by measurement rather than by a person, item 17 was read and rejected
with its reason, and items 42 and 44 were answered (below).

Two of the findings were the same fault twice, and they are the ones worth
remembering: a paragraph written from build-time constants while the rows beside
it are written from the state on screen (items 20 and 24), so a railcard holder
was told "No railcard is selected" while every row showed a card price.

Item 3's data half turned out not to be a question about the index at all. One
real build, read on 16 October 2026:

    python build_demo_page.py --feed feeds/fares --timetable feeds/timetable-nwr \
      --origin GRA --notices nre,rdg,ogl,accuracy --out <site>/index.html

gives a chooser row reading *"GRANTHAM GRA 331 destinations this feed prices"*
over a page that says **331 destinations for up to £181.00 per adult** at the top
of its own budget and **53** at the default £20.00, from 324 rows in the cheapest
list, 331 in the single list and 135 in the anytime list. The chooser's number is
the page's own payload — the distinct places those lists carry, counted once
each — so the two are the same number whenever the budget excludes nothing, and
that is why the number moved from the 50 the audit read to the 331 the page
holds: the index pass's `_priced_destinations` (what the chooser used to print,
and what still decides the write set, ADR-0019 decision 3) is not the page's own
count. The 50 against 53 was a count of places at any budget (50) beside a count
of rows inside £20.00 on a page carrying 331 of them (53).

| Item | What it asked | What landed | Held by |
|---|---|---|---|
| 1 | the chooser printed the feed's download date twice | one date, composed once | `4234294`; `tests/test_build_chooser.py` |
| 2, 3, 4, 5, 6, 7 | the chooser's words: what the list is before how it is ordered, a count that names its scope, an intro that says what the site covers, an empty state that helps, "a page for", one "starting from" | all seven | `tests/test_build_chooser.py`; `tests/browser/chooser.cjs`, "the chooser says what its order is, and what it is not" |
| 9, 10, 11, 13, 38, 39 | the station page's opening: the heading's own name, one promise, the first-use note, the no-timetable fact stated once | the heading's accessible name is the whole sentence, written from the tab title on every render; one promise with the timetable clause composed onto it; the note names the station; "no timetable was supplied" said once | `tests/browser/station-render.cjs`, "the heading's own name is the whole sentence, and the same one as the tab title" and "the times columns exist exactly when the sentence promises times"; `tests/test_build_demo_page.py` |
| 12, 14, 15, 18, 19, 32 | the controls' own words: the budget hint, the unit, the mode's name, the chip rule, the clear control, the empty-state buttons | the hint names the mode it clamps in; "per adult"; "Cheapest available"; the chip rule says only what a count is; "Show all destination types"; "Show the 7 Anytime Day Returns" and "Raise the budget to £7.00" | `tests/test_build_fares.py`; `tests/browser/station-fares.cjs`, "the chips say what the count beside each one is"; `tests/browser/station-picker.cjs` |
| 16, 24, 26, 29, 31 | the railcard and the fare's own panel: the help, the method note, the card sentences, the feed's ban vocabulary, one voice | the help says where the choice travels; the note is written from the card the rows read and claims the card only where it lowers the fare; the sentences are one voice; the ban vocabulary sits in the feed record | `tests/browser/station-fares.cjs` (the railcard help); `tests/test_build_fares.py`; `tests/browser/station-rows.cjs` |
| 20, 21, 22, 33, 34 | the count, the day and the pagination | "shown" is reserved for the table, so the cover line counts what the feed prices at any budget; the count line states the breakdown once; an absence in the Time cell is a short state and the row's own details name the day; an empty list carries no page number | `tests/browser/station-fares.cjs`, "and the status re-announces the page, without repeating the count"; `tests/browser/station-shortlist.cjs`, "and every absence on every day names the day it is about" |
| 25, 27, 28, 30 | a row and its own details | the restricted-fare sentence promises a condition only when the feed describes the code, from a payload fact rather than from reading the fallback text; one shape of disclosure name; "Copy journey"; the walk-up fare glossed where it is met | `restrictionDescribed` in `build_payload.destination_row`; `tests/test_build_fares.py`; `tests/browser/station-rows.cjs` |
| 35, 36, 37 | the shortlist dock | the live region says what changed rather than the count; the share line names what the link carries beside a real link; the list noun is "destination" | `tests/browser/station-shortlist.cjs`, "and the change to the list is announced, not just drawn" and "and the shared link names exactly the places the list holds" |
| 40, 41, 43 | the privacy page | the contact is a sentence with a real link; the hosting paragraph no longer restates the bullets above it; one actor name and one tense across the conditional promises | `tests/test_build_provenance.py` (the contact and its issue tracker); `DEFAULT_PRIVACY_CONTACT` in `build_release.py` |
| 45, 46, 47, 48, 49, 50 | the provenance block | the price line tells the two dates apart ("downloaded", "fares and times read for"); the build stamp is named and dated in the page's own words; each method sentence has a subject; the destination-type source sits with the attribution; the timetable verdict names the day the times are for | `tests/test_build_provenance.py` (the two clauses, the type source's place); `tests/browser/station-fares.cjs`, "and judges that window against the reader's today" |
| 23 | the price cell's three facts with no words between them | the note reads "with your card (was £7.00)", so the words say which number is the card's | `page/station/railcards.js`; `tests/browser/station-fares.cjs`, "a discounted row shows the card price and the standard fare it was discounted from" |
| 3 (the data half) | the chooser's number and the page's number disagree | the chooser names the page's own places, so at the top of the budget the two are the same number | `places_in_payload` in `build_payload.py`; the build and its readings are below |
| 17 | the destination-type chips are census bands wearing everyday words | read and rejected by the owner: the words stay | the entry under "Rejected designs, with the reason"; no code changed |
| 42 | the built line promised a publication that had not happened | the line dates the build ("This notice describes the build dated ..."), so it is true of a build nobody deployed and of a deployed one | `build_render.py`; `tests/test_build_provenance.py`, which holds the line to the date and to no claim of publication |
| 44 | nothing defined the trade vocabulary the page quotes | one glossary inside the method disclosure, written from the route's shared script and not per page, and no gloss where the words are met | `page/station/provenance.js`; the placeholder in `page_templates.py`; `tests/browser/station-render.cjs`, "the trade words the page quotes are defined together, in the method disclosure" |

### The 14 October 2026 impeccable critique

`docs/audits/2026-10-14-impeccable-critique.md` was removed on 19 October 2026,
when its last recommendation landed. Its eight recommendations are settled here,
and the commits that carry them are `4234294` (1, 2, 3's first half, 4 and 6, in
one pass), `6e83318` with `ba9cd45` (7), `92ae476` (8) and `3b48bc5` (3's second
half). Recommendation 5 was settled as a reading rather than a change, so it has
its paper in `licences/release-clearance.md` instead of a commit. The pass was
run degraded and said so: no sub-agent was exposed to that session, so the design
review and the detector evidence were not independent, and no screenshot was
available, so every finding was measured from the live DOM rather than seen. Its
detector's one finding, `cramped-padding` on `.origin-slot-wrap`, was a false
positive — that border is the station slot's own dashed underline — and the 9
October route audit recorded the same finding and the same verdict, so a later
pass should not re-file it.

| Recommendation | What it asked | What landed | Held by |
|---|---|---|---|
| 1 | the chooser printed the download date twice | the provenance is a structured pair — the source names the feed, the date travels beside it, and each route composes one sentence from the two | `tests/test_build_chooser.py`'s entry-provenance test, `build_provenance.dtd_download_entry`, `page/station/provenance.js` |
| 2 | two counts for one question | the count is the places the page carries, two-ticket rows included: measured on the real feed, Grantham's 50 became 334, and the number a reader arriving from the chooser sees is the page's own set | `tests/test_build_demo_page.py`'s `test_the_page_carries_more_places_than_the_selectors_price`, `tests/test_page_caches.py`'s timetable-key test, `build_demo_page._priced_destinations` |
| 3 (first half) | three of fourteen chips could not succeed | a chip is offered only when a destination of its type is inside the budget on screen, which is the same rule the count beside it already stated | `tests/browser/station-filters.cjs`'s chip checks, both directions, `page/station/filters.js`'s `syncDestinationTypeChips` |
| 3 (second half) | the group was `All` plus fourteen chips at one decision point, well past the four a reader holds at once | the four settlement bands stay in the row and the ten thematic facets are one press away, behind the chip that row ends with — the arrangement chosen on 19 October 2026 from four mocked up in the page's own stylesheet, a throwaway that is not in the tree | `tests/test_build_fares.py`'s `test_the_settlement_bands_stay_in_the_row_and_the_facets_go_behind_it`, `tests/browser/station-filters.cjs`'s five disclosure checks, `build_render.destination_type_chip`, `page/station/filters.js`'s `syncDestinationTypeChips` |
| 4 | the empty state named the budget and not the cause | the count line names the active refinement in the same words the paragraph below the table uses, and the empty state's own "Clear the destination type" is one press away | `tests/browser/station-filters.cjs`, `page/station/table.js`'s `render` |
| 5 | the routes that show no fares carry no licence notices | settled on 16 October 2026 as a reading, not a change: the credit travels with the page that shows a fare, the chooser's station index and the privacy notice show none, and the alternative reading is named beside it in the record. The build check the same reading asked for landed with it, and it closes route audit items [20] and [21] | the section "Which pages carry the acknowledgement" in `licences/release-clearance.md`, `tools/check_source_credit.py`, `tools/test_check_source_credit.py` |
| 6 | the smallest type on the page was 11.52px | `.75rem` is the floor for type on this route, and the letter-spacing carries the small-caps effect | `tests/test_page_assets.py`, `page/station.css` |
| 7 | the fare vocabulary had no home | the words the route quotes are defined once, in a definitions list inside the method disclosure, immediately below the provenance line — which is the "block beside the provenance" this recommendation offered as its first option, drawn as the second (clarity audit item 44 chose the same answer from the other end) | `tests/browser/station-render.cjs`'s "the trade words the page quotes are defined together, in the method disclosure", `page/station/provenance.js` |
| 8 | no accelerator for the page's one job | `/` or `b` focuses the budget field, `n` and `p` press the pager's own buttons rather than repeating what they do, and one line on the always-visible strip names both — with the paging half promised only while a pager is on the page, because a hint for a key that does nothing is the failure the format's own counts are held to | `tests/browser/station-filters.cjs`'s accelerator checks, `page/station/wiring.js`'s keydown listener, `page/station/filters.js`'s `renderKeyHints`, `page/station/table.js`'s two calls to it |

### The 17 October 2026 impeccable review

`docs/audits/2026-10-17-impeccable-review.md` was removed on 20 October 2026,
when C21 landed and the review named no open item. Twenty of its thirty findings
landed on 19 October 2026, C21 landed the next day, and two were answered rather
than changed: C9 / D5, argued in ADR-0048, and C18, rejected by the owner on
19 October 2026. The rows below name the tests once, so a reader of this file does
not have to open the audit to know what holds the pass.

The pass also re-measured the two figures it changed rather than quoting the
17 October ones: at 1366×768 a whole destination row now sits above the fold, and
a 390px row is 111px over two lines rather than 275px over six.

| Findings | What landed | Held by |
|---|---|---|
| C3, C4, C6, C7, C13 / D8 | a fold that holds a row, a footer at the body's measure, one drawn mark on all three disclosures, the ticket link as the bordered control and the expander bare, and the two-line phone row | `tests/browser/station-layout.cjs`, whose section names are the findings: "at 1366x768 one whole destination row is above the fold", "the footer is held to a readable measure rather than the whole page", "both disclosures wear the page's drawn mark", "the ticket link is the bordered control and the expander the bare mark", "at 390px the typical row is two lines rather than six" |
| C10, D1 | the click sentence is the first-use note beside the heading and the intro paragraph that carried the rest is gone | `tests/browser/station-picker.cjs` for `#firstUse`, `tests/test_build_demo_page.py` for the note's wording |
| D3 | a restricted fare is explained once, in a sentence composed by `build_payload.describe_restriction` and carrying the code | `tests/test_build_fares.py`, "a restriction the feed cannot describe says so plainly" |
| D4, D7 | the day help is one clause and the coverage window is with the other dates; the trade words end the method disclosure | `tests/browser/station-shortlist.cjs`, `tests/browser/station-fares.cjs`, `tests/browser/station-render.cjs` |
| D6 | a page with no feed note writes no note paragraph | `tests/test_build_chooser.py`, "a route without a note ships no empty paragraph" |
| C11, C12 / D10, C14 / D11 | the chooser's panel opens under the field, the phrase is the list's heading, and the empty field says "your station" | `tests/browser/chooser.cjs`, three checks that read the panel's position, a row's bare count and the placeholder |
| C15, D9 | the instruction paragraph is gone and "Most first." is the list's subtitle, with the denial of busyness and nearness deleted | `tests/test_build_chooser.py`, "the chooser is the index and carries no fares" and "the chooser says what its order is and is not" |
| C17 / D12, C19, C20 / D14, D13 | two bullets rather than three, the back link and theme switch in one row of chrome, "Last updated" in place of the maintainer's sentence, and the address parameters as one line of short names | `tests/test_build_provenance.py`, which reads the privacy page's bullets, the chrome row's order, the date sentence and the parameter line |
| C21 [P2] the ticket set is chosen above the table and defined below it | the sentence that says what the open set contains sits under the options that choose it, one sentence per set shortened to the difference between them; the old paragraph below the table is gone rather than moved twice | `tests/browser/station-shortlist.cjs`, "what the ticket set contains is said under the options that choose it"; `tests/test_build_demo_page.py`, `test_the_ticket_set_is_defined_where_it_is_chosen`; `tests/test_build_fares.py`, `test_the_page_opens_on_the_cheapest_fare_of_any_type` |
| C18 [P3] the privacy page's title is a single word | rejected by the owner on 19 October 2026, so `<title>Privacy</title>` stands. The review's suggestion ("Privacy · Train fares", or the release's own name once one exists) is not built, and a later pass should not re-file it | nothing, deliberately: the finding was argued against rather than fixed |

### The 19 October 2026 impeccable distill and delight passes

`docs/audits/2026-10-19-impeccable-distill.md` was removed on 19 October 2026,
when all seven of its suggestions landed. The delight and overdrive audits went on
21 October 2026, merged into `docs/audits/2026-10-21-audit-asks.md`: DL3 is open
work O3, DL6 and OV1 are O5, OV5 is O4, OV7 is O6 and OV3 is O8 (OV5 and OV3
were both measured on 21 October 2026; their decisions are still open).

The passes were read on `_demo_site`, built 19 October 2026 for service date
5 October 2026: 17 destinations, a 23-row page of two ticket types, both
palettes, 1366, 390 and 320px. What the new checks measured afterwards is in
`docs/build-performance-findings.md`; the figures this section states are the
ones a check now holds.

| Item | What it asked | What landed | Held by |
|---|---|---|---|
| DS1 | an empty list said its sentence twice, around seven column names over no rows | the count line is the live region and owns the sentence; the table and its head stand down with the list, and the block below carries only the way out | `tests/browser/station-filters.cjs`, "and the sentence is said once, in the count line rather than twice" and "and no table or column headings are left over an empty list"; `tests/test_build_demo_page.py`, the `for up to ` count |
| DS2 | the budget hint spent 41 characters saying where the control was | "Drag to set the budget. Stops at £X for one adult.", with the ticket mode named only when it is not the default | `test_the_page_says_where_the_slider_stops_and_the_figure_is_the_stop`; the browser suite's stated-stop checks |
| DS3 | two keys were named to every device, including phones | one key, and the line is shown only to `(pointer: fine), (any-pointer: fine)`; `b` still works but is not advertised | the browser suite's "the strip that stays on screen names the budget key", and the media query in `page/station.css` |
| DS4 | the folded summary repeated the controls while the panel was open | hidden while open, in the toggle's `aria-label` for exactly that time; the folded line returns on close | `tests/browser/station-filters.cjs`, "and the open panel does not repeat the state beside the controls that show it" and "and the folded plate shows it again rather than leaving it in a label" |
| DS5 | the Advance limitation was two paragraphs, twenty pixels apart, each with a clause the other lacked | one paragraph: the excluded ITX fares, then the payload's own sentence, which now carries the cheapest-single rule and the price-change caveat | `test_the_sentence_about_times_names_only_what_this_build_has`, which also counts the visible copy of "qualifying train" once; `test_the_ticket_mix_is_stated_once` |
| DS6 | eight type sizes, six of them between 11.5 and 18.4px | five: 12 for labels and records, 14 for secondary prose and controls, 16 for body and cells, 18 for section headings, and the display heading | the browser suite's "and the page keeps five type sizes below the display heading", a census of every rendered text node with a row open, so a sixth size fails the check rather than a stylesheet assertion |
| DS7 | five copies of one uppercase label, already disagreeing on letter-spacing | one `.eyebrow` rule, worn by the legends, both tables' headings, the shortlist label and the picker's label | `test_table_headers_name_their_columns_and_scope`, the hold-column assertion in `test_build_demo_page.py` |
| DL1 / OV2 / OV3 | the drag answered in numbers, not places, and re-rendered every row on every input event | the line under the count names the next fare and the place it adds ("£6.40 adds SLEAFORD."), the release says what the budget gained, and the render is coalesced to one per frame | `tests/browser/station-filters.cjs`, "a drag names the next fare and the place it adds" and "and on release it says what the new budget gained"; `queueBudgetFrame` in `page/station/budget.js` |
| DL2 | the £0 door said "Raise the budget to £7.00" and asked the reader to trust it | "£7.00 reaches SLEAFORD." above the same button, with a count when the cheapest fare is tied | the browser suite's "and the door names the place the raised budget reaches" |
| DL4 | the dock's Copy was silent to the eye while the row's said "Copied" | the same two-second word, "Select below" on a refused clipboard, and the timer cleared with the list | the browser suite's "the dock's Copy acknowledges the copy to the eye as well as the region"; `test_a_failed_copy_is_never_reported_as_a_copy` |
| DL5 | a row's panel and the shortlist dock appeared with no transition | one 120ms opacity-and-4px reveal, on the panel the reader opened and on the dock's contents rather than its fixed box, with no motion under `prefers-reduced-motion` | the browser suite's "and with motion allowed the panel arrives in one reveal" and "a reader who asked for less motion gets no reveal" |
| OV6 | moving between stations painted a blank frame | `@view-transition { navigation: auto; }` at the chevron's .18s, none under reduced motion, ignored by a browser without the API; the shared-station morph (OV7) is not shipped | `test_the_route_asks_for_a_cross_fade_and_can_turn_it_off`; the suite navigates every route and the accessibility matrix runs after each navigation |
| OV8 | the budget's re-render had no budget | a reading on every station page, named with its row count: input handler, render and forced layout under 50ms | the browser suite's "a budget change re-renders this page inside the input-to-paint budget" |
| OV4 | at row 40 the budget is two screens back | a 56px rail at the top of the viewport, shown only while the page's own slider is out of view (the owner's condition, 20 October 2026), carrying one value in two views and the sticky headings' offset | the browser suite's four rail checks in `station-filters.cjs`; `test_the_budget_is_kept_in_reach_once_its_control_scrolls_away` |
| OV9 | each fallback was a paragraph rather than a test | no script: the existing `checkWithoutTheScript`; reduced motion: the reveal check above; no canvas: not applicable, because OV1 did not ship; no view transitions: the at-rule is ignored, and every route still navigates | `tests/browser/station-assets.cjs`, `station-layout.cjs` |

**What the pass did not do.** OV1 (the canvas fare horizon) and DL6 (the tick at
the cheapest fare) are one visual direction the owner has not chosen, and the
mockups of 20 October 2026 are evidence against the first form of it: on a £126
ceiling the ticks bunch into the left fifth of the track. It is open work O5. OV4
(the sticky budget rail) landed on 20 October 2026, after the owner saw it mocked
up, on the condition that it appears only while the page's own slider is out of
view. What is left of that pair is OV5, the dock under the rail, which is O4, and
DL3, the shortlist total, which is O3.

**What the numbers were.** On the demo, the next fare above £20 was £22.40 to
PETERBOROUGH, which is the sentence the browser check reads; at £0 the door
reaches SLEAFORD for £7.00 and the list shows two places at £7.00. A render
with 101 destinations in the payload and one page of 20 rows measured 7.4ms in
Chromium on this machine (19 October 2026), against the 50ms gate; that is a
probe of the demo's own rows, not of the licensed Grantham page, and the gate
will report the licensed page's own figure the first time the release suite
runs it.

### The 19 October 2026 impeccable critique

`docs/audits/2026-10-19-impeccable-critique.md` was removed on 21 October 2026,
merged into `docs/audits/2026-10-21-audit-asks.md`. It went on one finding, S5, the
phone's fold budget, which has to be given a stated budget in numbers before it can
be implemented, and that is an owner's decision rather than an edit; it is open
work O7. Two more of its observations are O9 (the refinements panel's 160px void)
and O10 (the heading's budget field against the 44px promise). Eleven of its twelve
findings are settled here. S8 is C21 of the 17 October review above and S12 is that
review's rejected C18, so both already have their rows. S6, S9 and S10 landed on
19 October 2026 with DS1, DL4 and DS3 of the distill and delight passes and share
their checks. S1, S2, S3, S4, S7 and S11 landed on 20 October 2026.

The six that landed on 20 October changed one thing the pass could only see from
the outside: a fact that belonged to the journey was being copied out of one fare
record instead of read once. The departures are the clearest case, and the payload
now shares one list per journey across the fare lists that price it (S1).

| Finding | What it asked | What landed | Held by |
|---|---|---|---|
| S1 [P1] | the cheapest row opened a panel with no times and said nothing about it | the departures belong to the journey: one list per destination, read once from the timetable the row's journey came from and shared by every fare set that prices it; a fare set that still has none says so in the panel, beside the duration it explains | `tests/test_build_fares.py`, `test_the_journey_is_the_same_fact_in_all_three_fare_lists`; `tests/browser/station-fares.cjs`, "every row the build timed opens onto its departures, or says it has none" and "and a fare set with no times says so, beside the duration it explains" |
| S2 [P1] | the chooser's station field looked like the end of a title | "Type your station's name, or pick one below." under the heading and above the list, on the route that has a field to point at; a release that priced one station keeps its own sentence | `tests/test_build_chooser.py`, `test_the_chooser_says_what_to_do_with_the_field_it_offers`; `tests/browser/chooser.cjs`, "the chooser says what its field is for, under the heading and above the list" |
| S3 [P2] | three of the four £0 doors led to another empty list | each set door sets the budget to that set's cheapest fare and switches the mode in one gesture, so the list it promises is the list it opens; it is not offered when the set has nothing the type chips can show, and its label names the floor and scopes the count ("Show returns, from £6.40 (22 in the feed)") | `tests/browser/station-filters.cjs`, "and every ticket-set door lands on the set it names, at the price it names"; `page/station/state.js`, `chooseModeAt` |
| S4 [P2] | "Restricted" lost the column that explained it on a phone | the cell carries its noun -- "Restricted fare", "Regular fare", "Advance fare" -- so the row reads as a fare type without the clipped heading, and "Two tickets" already carried one | `tests/browser/station-layout.cjs`, "at the phone's content width the fare cell says what kind of thing it names"; `tests/browser/station-fares.cjs`, "and the row names the fare in a phrase while the feed's code stays folded" |
| S7 [P2] | clearing the shortlist dropped focus to `<body>` | the clear announces "Shortlist cleared." and moves focus out of the dock before the dock goes -- to the first row's checkbox, or to the count line when the list has no rows; the live region now sits outside the dock, because a region inside a hidden subtree is announced to nobody | `tests/browser/station-shortlist.cjs`, "and clearing it from the keyboard leaves the focus on the page"; `page_templates.py`, the count line's `tabindex` and the status region's place |
| S11 [P3] | the chooser's destination count was a bare number | one column line above the list, "Station · Code · Destinations", written once rather than in every row; it is for the eye, because each row's accessible name already says what the count counts | `tests/test_build_chooser.py`, `test_the_chooser_names_the_three_columns_its_rows_carry`; `tests/browser/chooser.cjs`, "the chooser's destination count is named by a column line above the list" |
| S6 [P1] | the empty list said its sentence twice, over an empty table head | landed on 19 October 2026 with DS1: the count line owns the sentence and the table stands down with the list | the two DS1 checks in `tests/browser/station-filters.cjs` |
| S9 [P2] | the shortlist's copy confirmation was invisible | landed on 19 October 2026 with DL4: the dock's Copy says "Copied" for two seconds, and "Select below" when the clipboard refuses | `tests/browser/station-shortlist.cjs`, "the dock's Copy acknowledges the copy to the eye as well as the region" |
| S10 [P2] | a keyboard hint was shown to a phone, naming two keys | landed on 19 October 2026 with DS3: one key, and the line only on a fine pointer | `tests/browser/station-filters.cjs`, "the strip that stays on screen names the budget key" |

### The 20 October 2026 poteto audit

`docs/audits/2026-10-20-poteto-audit.md` was removed on 21 October 2026, after
all eight of its findings landed and none of them named an open item. Its three
questions for the owner went to `docs/open-work.md`; question 1 is the byte entry
there, now a P2 resting on ADR-0069's measurement rather than a P1 resting on a
superseded projection, and question 2 is S5 of the 19 October critique above.

The audit's own figures are kept where a later reader will need them. A3 measured
the same page twice, and the difference is the finding: Playwright's 390px
viewport has no scrollbar, so it laid the table out 366px wide with a 72px time
cell and a 112px row, while a real Chromium window at 390 gives 374px of content,
a 350px row and a 160px row height. At the corrected 375px of content the demo
page's median row is **138px** with a 159px tallest, and it is the same at 304px
of content, which is what 200% zoom leaves of a 640px screen. A1's count is that
the network's CIF holds **488,796 passenger schedules and 7,373,060 calling
points** after the loader's filter, against the DTD feed's 419,589 and 7,700,987,
so the 16 October source switch is not a doubling of what a worker holds. A5's
fast loop is **228 tests, 42.3 s and 53.2 s on two runs** plus 2 s for the
JavaScript parse, and A2's figure is ADR-0069's 90.8 MB for 458 real pages, about 536 MB for the network.

| Finding | What it asked | What landed | Held by |
|---|---|---|---|
| A1 [P1] | a release cannot finish inside its own bound, and nobody knows what a share costs | the shard step times itself, prints every share's wall clock, and warns at the stated nearing minute; the workflow's bound, share count and nearing minute are the ones the performance record states | `.github/workflows/deploy.yml`, the shard step's `SPENT_MINUTES`; `tests/test_workflows.py`, `BuildBoundTest`. **Still owed:** the first twelve-share run's per-share figure, which belongs in `docs/build-performance-findings.md` |
| A2 [P2] | the byte budget's open P1 contradicted the ADR that fixed it | the P1 is restated as the P2 it is: ADR-0069's 90.8 MB for 458 pages, about 536 MB against 800 MB, and the next release run prints the number that replaces the extrapolation | `docs/open-work.md`, the byte entry; `tools/page_bytes.py` still refuses an overage |
| A3 [P2] | the phone and zoom layouts were measured in a viewport no reader has | the layout is measured at 375px of content (a 390px window less its scrollbar) and the zoom case at 304px, both read back as `clientWidth`, with the row held to three lines at each | `tests/browser/station-layout.cjs` and `tests/browser/a11y-matrix.cjs`, each with a check that the content width is the one claimed |
| A4 [P2] | the route's script was only ever parsed one file at a time | `tools/verify.py` parses `page_templates.STATION_SCRIPT` and `CHOOSER_SCRIPT` as one string each, and names the panel whose addition stops the concatenation parsing | `tools/verify.py`, `first_unparsed`; `tools/test_verify.py` holds the attribution, and a duplicate top-level `const` in the artifact fails the run |
| A5 [P2] | the fast loop was 21 minutes, so nobody used it while writing | `--fast` is `FAST_MODULES`: the page, payload and chooser modules plus the checks that speak for the build, 228 tests in about a minute, and it fails past its 300-second ceiling; `--full` still runs every module | `tools/verify.py`, `FAST_MODULES` and `FAST_CEILING`; `tools/test_verify.py` holds that every listed module holds tests and that the feed-scale ones stay out |
| A6 [P2] | a hundred assertions read the page's script source instead of its behaviour | fifteen sentences the browser suite already proves are deleted; the 58 still held only by a source pin are behind a ratchet that no module may add to. The audit's count of 104 assertions included identifiers and decisions -- `DATA.dateNote` is a hook, not copy -- so 72 of them were sentences, and this is what is left of those | `tests/test_test_suite_shape.py`, `COPY_PINS`; measured 21 October 2026, and a module outside the table or above its count fails with the sentences named |
| A7 [P3] | the browser was pinned in CI and floating everywhere else | one file names it: `tests/browser/playwright-version` (1.63.0), which CI reads, which `tools/verify.py` asks npx for, and which the documented local command reads | `tests/test_workflows.py`, `PlaywrightVersionTest`; `tools/test_verify.py`, `PlaywrightPinTest` |
| A8 [P3] | the bound was justified by a table no check read | the performance record states the bound, the nearing minute and the share count in a table, and the workflow is held to it | `docs/build-performance-findings.md`, the 20 October entry; `tests/test_workflows.py`, `BuildBoundTest` |

### The 17 October 2026 poteto audit

`docs/audits/2026-10-17-poteto-audit.md` was removed on 19 October 2026, after
its last two findings landed on 18 October 2026 and it named no open item. All
nineteen are settled here,
each with the check that would fail if it came back, because the check is the part
that keeps a closure closed. Two were argued before they were fixed, and the
argument is in their rows: E5's recommendation, to take the keep-list from the
release manifest, cannot answer the question, because the names that must survive
belong to pages this build did not write; and E6's second dispatch is one keyword
on the load dispatch that already existed.

| Finding | Closed by | Held by |
|---|---|---|
| E1, the page-size tool reported 0 payload and 0 rows for every station page | the templates own the payload markers and the two gating tools are held to them, and `page_bytes` exits 2 on a page that names a payload it did not parse | `python -m tools.page_bytes _demo_site/from/grantham/index.html` reports 39 KB total, 19 KB payload and 16 rows; `tools/test_page_bytes.py` measures a page `render_page` wrote |
| E2, every station page blocked parsing on the network's station list | `build_assets.station_asset_tag` writes `defer` | `tests/test_build_demo_page.py` reads the tag out of a rendered page |
| E3, 42 substitutions, two of them asserted | `build_render.refuse_unfilled` sweeps the whole document on all three routes | its tests render each route, assert no placeholder survives, and assert that a note naming one is refused |
| E4, the resume key was weaker than the cache key | `build_state.resumable_signature` and the shard agreement key on `feed_content_digest`, not on names, sizes and mtimes | `tests/test_atoc_knowledgebase.py` gives two feeds of equal size and the same mtime different bytes and gets different keys |
| E5, tidying the release read the whole release | `prune_shared_assets` is given the pages this build wrote and does not read them, because a page it rendered requests its own names and nothing else; only a page an earlier build wrote can name an older asset | `tests/test_page_output.py` records every `read_text` the prune makes, asserts the station page it wrote is not among them, and holds that a leftover page naming a stale asset still protects it |
| E6, the shard merge parsed the whole fares feed to answer a set question | `FaresDb.load_feed(..., locations_only=True)` reads the `.loc` file through the same `read_feed_files` dispatch, and `merge_shards` asks only the locations question | `tests/test_atoc_fares.py` proves the cheap load returns the map the full one returns and reads only `rjfaf.loc`; on the real feed the load went 37.7 s to 0.3 s over the same 3,436 stations (measured 18 October 2026) |
| E7, the opening budget was a literal in five places | `build_release.OPENING_BUDGET_POUNDS` is the one constant, the shard manifest carries it in `release`, and the merge opens at the shard's figure | `tests/test_page_runner.py` refuses a `budget_pounds=<number>` literal and reads the manifest |
| E8, the privacy contact was the one unescaped substitution | `render_privacy` escapes it | the provenance tests read an address carrying `<` and `&` |
| E9, an open row closed on every render | `STATE.openCrs` holds the row a reader opened and `reopenOpenRow` puts it back after the rows are rebuilt, so the panel and the fare inside it survive a budget move | `tests/browser/station-rows.cjs` opens a row and then types a budget; with the state half removed it reported `stillOpen: false` |
| E10, one sentence had two owners | `emptyListSentence(cap, what)` is the one composition, called by the count line and by the empty state | `tests/browser/station-filters.cjs` asserts the two are the same sentence character for character on a page with an empty list |
| E11, the railcard list was rebuilt at the budget's drag frequency | `writeRailcardOptions` runs only when the party changes, because nothing in the list depends on the budget | the browser suite marks the list and types a budget; with the guard removed it reported `kept: false` |
| E12, page-level elements were owned by the wrong panel | `#summary`, `#empty`, `#more`, `#pagination`, `#pageStatus` and the two pager buttons are read in `page/station/payload.js`, the one place the page's elements are read | `filters.js` and `service-day.js` keep only what they write, and `tools/check_page_state.py` counts what each panel reads |
| E13, order-dependent top-level statements | `DEFAULT_MODE` is `STATE.mode` and the comment names the ordering as the invariant it depends on | the browser suite loads the built asset on every page it drives |
| E14, the phone table was exercised for overflow and never for where text landed | the stacked row's two tracks | `tests/browser/station-layout.cjs` measures every cell of every row at 390px; with the station cell's wrapper removed it reported `worst: -89px` |
| E15, the wrap detector existed with the two broken cells excluded | the detector measures every run of every cell, prose runs excluded by class, and the station and tickets cells are in the set | `tests/browser/station-render.cjs`; a 3rem `.station-value` at desktop reports `{"cell":"Station","lines":3}` |
| E16, the mobile layout's rules were asserted as text | `tests/test_build_demo_page.py` keeps the media query and the markup-is-a-table claim; everything else it asserted is now geometry | `tests/browser/station-layout.cjs` at 390px |
| E17, a chip's count leaked into the sentence that named it | `typeLabel()` reads the label span | the browser suite checks the sentence for every chip it presses; with the old read put back it reported `in cities (1)` |
| E18, three housekeeping faults in one shared namespace | no local declaration shadows a shared function, no top-level constant only renames another, and every option the shared station field reads is passed by a caller | `tests/test_page_assets.py`; the last check found a second unread option (`onUse`) and the shadow check a second shadow (`unit` in `url-state.js`) |
| E19, `docs/open-work.md` carried two thirds of a closed record | the settled record moved to this file on 18 October 2026, with the audit-item numbers code comments cite | `docs/open-work.md` is open work only, and this file is the closed record |

**What the pass said is worth keeping.** Failure modes refuse rather than guess: a
public build with no notices stops, a missing brand mark stops, a slice index with
a gap names the codes before the build starts, and for a page whose numbers are
the product that default is the product. The cache identities are content digests
with the reason written down (ADR-0031); E4 was a mismatch between two identities,
not a flaw in either. `page_is_current` compares the markup around the payload
byte for byte and the asset names are part of the resume signature, so a template
or `page/*` change already cannot be resumed past. The browser suite's skip budget
is the right shape for pages that differ enormously in what they can exercise: a
check a page cannot exercise is a skip, and the budget stops skipping from reading
as a pass.

**What the pass could not establish.** No real-feed build, so every figure was of
a 3-station demo page and nothing measured the 2,712-page release. E4's key is
pinned by a unit test over two files of equal size and the same mtime, and the
end-to-end case, a resumed build that must not skip, still has no fixture. E11's
platform behaviour, an open native select dismissed when its options are replaced,
is inferred rather than observed, because the session drove headless Chromium,
whose select popup is not the platform's. And 390px in Chromium is a viewport
rather than a device, so the row heights and fragment positions are exact for that
viewport and should be re-measured on hardware before anyone quotes them as a
device figure.

### The 18 October 2026 agent-friendliness plan

`docs/audits/2026-10-18-agent-friendliness-plan.md` was removed on 18 October
2026, when R4, R5, R7 and the rest of R8 landed; the commit that removed it is
named at the foot of this file. The question it answered was the operator's, of
18 October 2026: the code should be rearchitected for agents rather than patched.

Its premise is worth keeping because it is the reason the next such plan should
start the same way. There are four rungs of enforcement, strongest first: make the
bad state unrepresentable, make it fail a check, write a canonical helper, write
prose. This repository was already strong at the second rung, and that strength is
where the first defect lived: **a check that cannot fail is worse than no check,
because it spends the trust a real check would have earned.** Three measurements
found it in three places that day: a byte gate that reported 0 KB of payload on
every page it measured, the same gate passing an empty folder, and one fact (the
payload's marker) spelled independently in eight files, the eighth being the gate.

| Item | What changed | Held by |
|---|---|---|
| **R1** | `page_templates.py` owns `PAYLOAD_MARKER` and `CHOOSER_MARKER`; five modules import them instead of spelling them, `tools/check_source_credit.py`'s docstring included | `tests/test_page_assets.py` holds each template to its own marker, and the two gating tools to the template's |
| **R2** | `page_bytes` exits 2 on a page that names a payload it did not parse, and on a `--site` run that finds no page | `tools/test_page_bytes.py`, two cases, plus a third proving a page that ships nothing still passes |
| **R3** | the byte measurer's own test measures a page built from `page_templates.TEMPLATE`, not a page the test typed | `tools/test_page_bytes.py` |
| **R4** | `page/station/state.js` is the page's one mutable object: `seedState()`, then one gesture per control family (`chooseBudget`, `chooseUnit`, `chooseMode`, `chooseCard`, `chooseTypes`, `chooseServiceDay`). Every listener is one line calling one of them, every render derives from the state, and `applyState` is the one place a control is written from it — it no longer reads a control back | the browser suite, 844/844 over five pages on 18 October 2026, with the setups that used to assign `.checked` on a control now driving a gesture or `applyState` |
| **R5** | `tools/check_page_state.py`: a ratchet over control reads per panel, in the shape `tools/check_types.py` uses, run by `python -m tools.verify --full` | `tools/test_check_page_state.py`, thirteen cases over the verdict, including that a panel the budget does not name fails and that a write is not counted as a read. It fails on the tab title's old `budgetNumber.value` read, which is the defect it was written from |
| **R6** | the paragraph about times is the payload's own sentence, chosen once from `hasJourneys`: a prices-only page no longer says "valid on the services listed" | `tests/test_build_demo_page.py`'s `test_the_sentence_about_times_names_only_what_this_build_has`; the words are `build_release.SERVICE_CLAIM` and `SERVICE_CLAIM_WITHOUT_TIMES` |
| **R7** | `AGENTS.md`'s rule table gained the third column, "what fails, and what it says", and lost the one row that could not name a failure | the row below, which is that row's new home: "docs/build-performance-findings.md is a rule with no enforcer" |
| **R8** | the prose the structure replaced is gone: `check_source_credit.py`'s docstring imports the marker it used to spell, and `url-state.js`'s `applyState` no longer explains why it must re-read the controls, because it does not | the same tests as R1 and R4 |

**The evidence, kept because the numbers are the argument.** `grep -cE
'\.(value|checked|dataset|textContent|hidden|classList)' page/station/*.js` summed
to **269 accesses across 15 modules** before R4. It is a size, not a defect count,
and it does not separate reads from writes; after R4 the reads alone, which is what
the ratchet counts, sum to **34** across the page's 17 panels (measured 18 October
2026). Six of the 37 `fix(page|station|chooser|routes)` commits were the same shape
from six sides, all of them a second writer or reader of a fact that only lived in
an element: `Back and Forward carry the chosen day`, `an arrow key no longer takes
the station away from Tab`, `the tick on a row is the shortlist`, `a card must not
swap the row under a reader's feet`, `the budget floor is zero`, `the field stops
moving the page`. Eighteen of the 108 `fix` commits were `fix(tools|tests|ci|verify)`
-- the instrument was wrong -- and that is what R1 to R3 answered.

**What it does not establish.** The commit-prefix census is the author's label, not
a measured property: it locates the work and does not measure it. R4's benefit is
prevention rather than repair, because the six defects it is meant to prevent were
already fixed at the element level, so it is proved by the cases that keep passing
rather than by a case that starts passing. And the ratchet counts reads without
judging them: a read inside a gesture and a read compared against a chip's markup
look the same to it, which is why the reason for a particular read belongs in the
comment beside it.

**Not proposed, and why.** No package move (rejected 8 October for import and CI
churn, and R1 gave the same orientation benefit through one module). No type
checker for page defects (they are in JavaScript; R5 is a lint over JavaScript
instead). No split for length, no schema for the classification tables, no new
abstraction over the checks: each would trade a written reason for a mechanism
that cannot carry it, and `verify.py` is already the runner.

### The measurements three ADRs lean on

ADR-0040, ADR-0041 and ADR-0043 were settled from a rendered-page audit of the
published Grantham page on 29 September 2026. Their evidence is kept here rather
than in a file that would otherwise have been deleted, because an ADR that cites
a measurement needs the measurement to still exist.

**Finding 1 — the price column was 56px wide, so the price wrapped** (settled by
ADR-0040 §1). Seven columns measured station 176px, price 56px, time 62px,
changes 72px, fare 225px, conditions 234px, tickets 352px. Thirteen of the first
twenty prices painted as two lines: `£10.10` rendered as `£10.1` over `0`, and
the same for £12.60, £13.30, £13.70, £14.10, £14.40, £14.70 and £15.40.
`CHANGES` wrapped mid-word in its 72px column. Nothing in `SHARED_CSS` refused a
wrap on `th` or on `td.num`, so each column took its width from the widest thing
in it that could not break — and for a two-word header that is the header.

| Tamper | Check result |
|---|---|
| price column forced to 56px, `white-space: normal`, CHANGES-only | **FAIL** — `{"text":"Changes","lines":2,"width":56}` |
| price column forced to 40px, same | **FAIL** — `£8.70` in 2 lines, `50m` in 2 lines, `CHANGES` in 3 |
| as shipped | **ok** — 18 cells measured, price column 78–81px |

**Finding 2 — forty cells restated the mode the reader had already chosen**
(settled by ADR-0040 §2). All twenty rows read `Unrestricted Anytime Day Return`
in FARE and `No travel conditions on this fare in the feed.` in CONDITIONS — two
sentences about the *mode*, printed twenty times. Each row measured 81px, of
which those two columns were the greater part; twenty rows occupied 1620px,
about two laptop screens. With the fare's own code and a differing-condition
word in their place, rows measure **49px** and twenty occupy 980px. The
condition stayed reachable one disclosure away, so C07's pointer survives with
its wording made true.

**Finding 3 — the count line was 205px from its table** (settled by ADR-0040 §3).
At 1440×900 the count line sat at y=654 and the table began at y=859, with six
paragraphs between them, and the first fare began at y=914 — fourteen pixels
below a 900px laptop's fold. At 390×844 the same block measured 455px. After the
change: **8px**, nothing between them; the first fare at y=867, thirty-three
pixels above the fold; no sideways scroll at 321/705/760/1024/1280/1440px.

**Finding 4 — five controls on every row** (settled by ADR-0043). The Tickets
cell carried `Tickets`, `5 times`, `Card details`, `Copy` and `Shortlist` — a
hundred pointer targets on page one, inside one cell 352px wide at 1440px and
240px at 705px. Recorded rather than fixed at the time, because the decision
changes what the row promises at a glance; ADR-0043 is that decision.

**Finding 5 — the cheapest row was tinted with no legend** (settled by ADR-0041).
`tr.best` set a background wash on the cheapest row and nothing on the page said
so, on a page that names no "best", no "recommended" and no star. Recorded
rather than fixed at the time, because the tint was also the only visual
grouping of the sort order; ADR-0041 is that decision, and the order is now
stated in words in the count line instead.

**Not a design fix.** The page measured above was the single origin the deploy
workflow then published (`--origin GRA`): one station page, no Change chevron in
the heading and only Privacy in the footer. That is a coverage fact about the
release command of the time rather than a defect in it, and the release has since
become the whole network — the settled entry "Question 1, the release coverage"
above (ADR-0050).
### Closed out of `docs/open-work.md` on 21 October 2026

Seven entries left that file that day, none of them open. Each is here with what
closed it and what holds it. The measurements they carried are in
`docs/build-performance-findings.md` or in the ADR named, because a figure belongs
in the file that measured it and not in a second retelling.

| Item | Closed by | Held by |
|---|---|---|
| The day-out decisions: ADR-0062's reserve, National Trust and landscape backlog, ADR-0063's closest-station prune, ADR-0064's seaside proof, ADR-0065's three registry facets | ADR-0063, ADR-0064 and ADR-0065 | `reference-data/destination-facets.json` carries them (rspb 9, national_trust 9, national_park 19), and `tools/check_facet_reference.py` fails when the file and the registry disagree |
| The slice equivalence sweep, P2 | ADR-0066 and the four-shard run of 9 October 2026: 26,369 of 26,369 origin-days compared, 3,767 of 3,767 origins complete, 0 differing | `python -m tools.check_slice_equivalence --merge 4` reproduces the verdict reading no feed |
| The checked-in facet reference data lagging the registry, P3 | one `tools/regenerate_destination_facets.py` run, and the check that now runs it whenever the registry moves | `tools/check_facet_reference.py` in CI, and 16 tests in `tests/test_check_facet_reference.py` |
| A whole-network build holding the national timetable for its whole life, P1, superseded 12 October 2026 | `TimetableDb.focused`, the on-disk `SliceIndex` and `--timetable-index`: 3 min 44 s for a two-station build, against the 24 minutes that wrote no page | the figures are in `docs/build-performance-findings.md`; `tools/build_timetable_index.py --all-origins` refuses without `--max-bytes` |
| The fares declaration cycle forcing two late imports, P3 | ADR-0070: 103 declarations moved to `atoc_fare_declarations.py`, and both `# noqa: E402` deleted rather than moved | `python -c "import atoc_fares, atoc_fares_loader, atoc_fare_declarations"` and the three fares suites |
| The comment audit's two findings and its suppression census | the checks that replaced the count: `tests/test_suppressions.py` and `tools/check_types.py` (ADR-0072) | six suppressions remain, each naming its cause on its own line or above it; 16 `# type: ignore` comments are held by the type ratchet |
| The journey times dropped from the release, and the source that brings them back | ADR-0073 and the wiring of 16 October 2026: `schedule_download.py`, the clearance gate's `TIMETABLE_GLOB`, and a fetch in `build`, `shard` and `assemble` | the first real run is open work O1; the stale licence reading it left behind was O17, corrected on 21 October 2026 against the clearance the owner gave on 16 October 2026 |

### What the 21 October 2026 pass closed

| Item | Closed by | Held by |
|---|---|---|
| **O2**, a station page's 354 KB had never been re-measured, and nobody had decided whether the payload was the thing to split | a real Grantham page built from the local feeds: **397 KB of HTML, 56 KB of it gzip**, 800 fare rows; the ticket-mode split costed at **10 KB gzip saved** against a **150 ms** round trip, with the default view still needing all three lists | `node tools/measure_station_paint.cjs _real_site` and "A real-feed station page's bytes" in `docs/build-performance-findings.md`; the default view's dependence on the three lists is `page/station/ticket-modes.js` |
| **O17**, six licence sentences still described a prices-only release | the owner's cleared reading of 16 October 2026 (`licences/release-clearance.md`, NWR Schedule), which the six sentences were corrected against in `docs/publish-checklist.md` and `docs/dtd-licensing-and-data-access.md` | `tools/check_release_clearance.py` for the clearance; the prose is held by `grep prices-only docs`, whose two remaining hits describe a capability (the builder's prices-only page) and a hypothetical (reverting the release) |
| **O18**, `docs/build-performance-findings.md` was a rule with no enforcer | read, prototyped and refused, with the census and the prototype's failure under "Structural ideas the reviews weighed and refused" | nothing shipped, deliberately |

## Rejected designs, with the reason

Moved here from `docs/open-work.md` on 21 October 2026, because a rejection is a
decision already made and that file is what is *not* decided. Kept rather than
deleted, because a rejected idea with its reason stops the next person from
re-deriving it.

### Suggestions the owner rejected

| | Suggestion | Why it is not worth doing |
|---|---|---|
| **S09** | Region, town or rail-network grouping once a geography source is chosen | The chooser already ranks all 2,718 priced stations and filters by name or code across them. Grouping adds a second way to browse a list nobody needs a second way to browse, and it needs the same geography source as S08 and C27 for no extra reach. |
| **S27** | Discovery entry points such as "cities under £20" or "seaside under £20" | It is a curated editorial list dressed as a derived one. The project's rule is that a page says what the feed says and nothing more, and a landing page that decides which towns are worth a click is that page making a claim it has no evidence for. |
| **S46** | A "Was this shortlist useful?" prompt or an optional feedback route | It is a tracker with a small payload, and it collects exactly the thing the page is careful not to collect. The same question is answered better by the S43 sessions, which are observed rather than recorded. |

### Structural ideas the reviews weighed and refused

- **Renaming the destination-type chips, or naming the census bands under them**
  (clarity audit item 17, 16 October 2026). "Cities" and "Villages" are Census
  2021 built-up-area size bands, so a reader may bring the ordinary word's meaning
  to a chip that means the band. Read and rejected by the owner: the words stay,
  because the chip is the page's own grouping of a place rather than a claim about
  it, the sourced facets worth naming already carry their named proof, and a
  rename would trade a word every reader knows for a longer one meaning the same.
- **Moving the root Python modules into a package** (8 October 2026). High import
  and CI churn, and the `AGENTS.md` map gets most of the orientation benefit.
- **Adding a Python type checker for page defects** (8 October 2026). The defects
  live in JavaScript files, which Python types do not reach; `node --check`
  catches the syntax half of it.
- **Splitting `atoc_fares.py` for its length** (8 October 2026). Length alone was
  not the cost F1 and F6 were about, and the file changed 19 times in 150 commits,
  a third of the page's rate. **Superseded 14 October 2026** by ADR-0070, which
  split it for a different reason: the declaration cycle it forced, not its size.
- **Checking in real feed samples as fixtures** (8 October 2026). The data is
  licensed (ADR-0005), so the synthetic fixture is the only regression test there
  is.
- **The national single-pass search, T2 as written** (12 October 2026). One
  national day index per day of the week, held for the whole build, is the shape
  the 8 October 2026 work removed. The per-origin facts layer delivers the same
  payoff without holding the network, and sharding is what would make such a pass
  affordable rather than a reason to build one.
- **A database, or any store** (12 October 2026). A store removes the page write,
  which measures 1.5 ms for a page as built and 10.9 ms for the largest page that
  audit saw, and none of the work itself, because the facts still have to be
  computed somewhere. ADR-0019's 14 October 2026 amendment holds the reasoning.
- **Extracting the classification tables to data files with schema checks**
  (14 October 2026). They are reviewed judgements with the reason written beside
  each group, and they are checked harder than a schema already: a code the feed
  does not carry and a code the workbook already classifies are both refused by
  `--require-live-reviewed-codes`.
- **`page_templates.py`'s templates rewritten as named template helpers**
  (14 October 2026). The templates are literal HTML whose comments say why a
  shape is what it is; a helper per fragment would separate the markup from its
  reason, and those bytes are what the page tests, the byte budget and the browser
  suite read.
- **Turning the long test preambles into test names or parametrized ids**
  (14 October 2026). Those comments are the "why" this repository asks for, and a
  parametrized id cannot carry the paragraph that names the real-feed shape a
  case came from.
- **A check that holds every documented figure to the one place it was measured**
  (O18, 21 October 2026). The cheapest enforceable rule was prototyped, and it
  is the one an ADR would have to state: a paragraph in a living document under
  `docs/` that carries a number with a unit must also carry a date or a citation
  of `docs/build-performance-findings.md`. Run over those documents it failed
  **21 of the 44 paragraphs** that carry a figure, and the failures are not
  mistakes: the **800 MB** budget is a setting, a withdrawn **2.2 GB**
  projection is a record, and a settled finding's **205px** gap is a measurement
  whose date sits in the section around it. Making those pass needs a list of exceptions on the day it lands, which is the
  gate this item was filed to avoid. It would be worth building once the figures
  are structured, meaning a registry the prose cites by name and a marker on each
  quote, and even then it sees only the quotes somebody marked. Re-open it if a
  figure drifts a third time, or if the prose is ever generated from a source.

### What the delight and overdrive passes refused

- **A celebration when a place is shortlisted.** It is a two-second decision, not a
  milestone.
- **A "best value" badge, or any ranking beyond cheapest-first.** The page refuses
  to recommend, and the data cannot support a score.
- **A weather, sunset, or "things to do" line for the destination.** Nothing in the
  feed carries it, and inventing it is the failure `PRODUCT.md` forbids.
- **A total that calls itself a day out or a plan.** The fares are a sum; the day is
  the reader's.
- **Particles, confetti, a mascot, or a WebGL map.** The fares feed carries no
  coordinates, so a map would invent geography the page's data does not have.
- **A loading skeleton.** The page is static and answers in milliseconds; a skeleton
  would fake work.
- **Sound or haptics on the drag.** The context is a train and a phone; silence is
  the feature.
- **A virtualised table before it is needed.** The station page's opening list is
  101 rows; virtualisation would buy complexity the page cannot spend. Measure the
  ceiling build first if that changes.

### A false positive, kept so a later pass does not re-file it

- **`cramped-padding` on `.origin-slot-wrap`, as `impeccable detect` reads it**
  (9 October 2026, and again on 19 October 2026). The border it flags is the dashed
  underline that is the station slot's whole affordance, chosen in `page/shared.css`
  because a text field's underline is the shape a reader already reads as "this part
  of the sentence is yours". The detector reported it on the station route only; the
  chooser and the privacy page scanned clean.

### Comments an audit saw and deliberately kept

Each for the same reason: two places, two facts.

- The two `_add_station` helpers in `tests/test_atoc_timetable.py` carry the same
  comment about appending a station record rather than rewriting the file. They
  are two fixtures with two signatures, and the comment sits on the byte handling
  each one does.
- `atoc_fares.py`'s `location_type_sources` field and the property below it open
  with the same sentence. One is the docstring a caller reads, the other carries
  the incident that shaped the field.
- "One manifest of the routes a release actually serves" in `build_demo_page.py`
  and the class docstring in `tests/test_page_output.py`. One is the build's
  contract, the other says which contract the class tests.
- The tram-stop note in `atoc_fare_declarations.py` appears in the reviewed
  settlement fallback table and in `TRANSPORT_STATION_CRS`. Two tables, two facts:
  one is a settlement class, the other a facet tag.
- The duplicated `try: ... except OSError: continue` in the two prunes in
  `build_demo_page.py`. The five lines of loop are two different rankings (one
  keys by path, one takes the newest stamp per digest, and only the first honours
  `protected` per file), so a shared helper would carry a flag rather than remove
  a branch.
