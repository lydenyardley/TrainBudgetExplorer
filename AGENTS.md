# Working in this repository

A static site that answers "where can I go from this station for under £X",
built from two licensed National Rail feeds. Python 3 standard library only, no
`requirements.txt`, no `pyproject.toml`. Tests are `unittest`; one Playwright
suite is Node.

## Run this first

```
python -m tools.verify --fast      # the page, payload and chooser modules, under a five-minute ceiling
python -m tools.verify --full      # every unit test, the type check, and the page's JavaScript parsed
python -m tools.verify --browser   # the demo and shape builds, then tests/browser_test.cjs
```

`--fast` is the page's own modules and the checks that speak for the release --
**328 tests, 70-182 s** measured 24-25 and 28 October 2026 and re-measured
11 and 12 November 2026, the spread being the fare gate's three builds and the
machine -- and it fails when its unit step
passes the five-minute ceiling, so a module added to the list is a decision rather than a
drift. `--full` is every
module including the feed-scale ones, **35 min** measured 15 October 2026. Both
figures are dated and reproducible in `docs/build-performance-findings.md`. A step
that could not run (node missing, mypy missing, actionlint missing, a build that
wrote no page) reports `not run` and exits 2 rather than passing quietly -- which
is why both want `python -m pip install actionlint-py` (it lints
`.github/`) and only `--full` wants `mypy`. A `pip install` that cannot write the machine's site-packages lands `actionlint` in the user Scripts directory (`~/.local/bin` on Linux, `%APPDATA%\Python\Python314\Scripts` here), so that directory has to be on PATH, or the step reports `not run` with the package already installed. One module while you work on it:
`python -m unittest tests.test_build_demo_page`.

`--browser` also drives the site at `_site` when one is on disk, which is what CI
has just built and what a checkout has not: a page names the sources it was
built from, so a `_site` from another tree is left out of the drive and the step
says which file differs, rather than reporting this tree's pages as a
regression. `--require-site` (the release's own step) fails instead, because a
site that run did not write cannot certify it.

Once per clone, `git config core.hooksPath .githooks`, so a message the
commit checker refuses never becomes a commit.

## The map

The code is one package, `trainbudget/`, in the four areas the problem has: what
a fare is, what a timetable says, how a page is built from both, and the tools
that fetch and measure the feeds. Each module keeps the name it has always had,
so a reader who knows `build_pool.py` finds `trainbudget/build/build_pool.py`.
The root holds `run.py` and the two launchers, which is all a newcomer needs.

| Area | Files |
|---|---|
<!-- module-map:start -->
| Fares | `trainbudget/fares/atoc_fare_declarations.py` (The fares feed's shape, and every table a reader of it needs.), `trainbudget/fares/atoc_fares.py` (The loaded fares database and the queries asked of it.), `trainbudget/fares/atoc_fares_loader.py` (Read a feed and its classification sources into the state a query reads.), `trainbudget/fares/atoc_restrictions.py` (Read the RSPS5045 ticket restriction file (``.RST``) from the fares feed.), `trainbudget/fares/destination_coverage.py` (Name the priced destinations no source could classify.), `trainbudget/fares/ons_boundaries.py` (Find the settlement a station stands in, from the published area boundaries.), `trainbudget/fares/parse_report.py` (Counters and a line reader shared by the two feed parsers.), `trainbudget/fares/retailer.py` (Build outbound ticket links without pretending to know a journey.) |
| Timetable | `trainbudget/timetable/atoc_knowledgebase.py` (Read the National Rail Enquiries Knowledgebase reference feeds.), `trainbudget/timetable/atoc_timetable.py` (Read the CIF timetable feed and answer journey questions.) |
| The build | `trainbudget/build/build_assets.py` (The files a site is made of and the addresses that reach them.), `trainbudget/build/build_demo_page.py` (Write a self-contained page listing every destination inside a budget.), `trainbudget/build/build_payload.py` (The payload: every destination a page lists, and its own wire format.), `trainbudget/build/build_pool.py` (The build itself: the phases, the worker pool, and the merge that joins the shards.), `trainbudget/build/build_provenance.py` (Where the numbers came from: the feed metadata, the download manifest and the dates.), `trainbudget/build/build_release.py` (The notices, the credit and the gate that decides whether a site may be published.), `trainbudget/build/build_render.py` (The markup: a payload and a template become the HTML a reader gets.), `trainbudget/build/build_state.py` (What a build keeps between runs, and the names it keeps it under.), `trainbudget/build/build_stations.py` (Build a short list of stations, fully, and serve them.), `trainbudget/build/build_workers.py` (The worker plumbing for the --all-origins parallel build.), `trainbudget/build/page_templates.py` (The page's HTML, CSS, and JavaScript, as fill-in templates.) |
| Feeds | `trainbudget/feeds/damage_feed.py` (Damage a copy of a feed on purpose, so the parsers meet bad input here first.), `trainbudget/feeds/dtd_audit.py` (Audit downloaded DTD fares and timetable feeds before using their totals.), `trainbudget/feeds/dtd_download.py` (Download National Rail Data Portal (NRDP/DTD) static feeds safely.), `trainbudget/feeds/feed_audit.py` (Report what the parsers actually read, so the first real run is diagnosable.), `trainbudget/feeds/feeds_cli.py` (Shared plumbing for the feed-driven CLI tools.), `trainbudget/feeds/fuzz_feed.py` (Mutate a feed at random and check what a parser is not allowed to do.), `trainbudget/feeds/make_synthetic_feed.py` (Write small synthetic feeds so the parsers can be exercised without a licence.), `trainbudget/feeds/schedule_download.py` (Fetch Network Rail's own CIF schedule from a URL, and refuse anything else.) |
| Measurements | `tools/measure_station_defer.cjs` (What `defer` on the shared station list's tag buys a reader, measured.), `tools/measure_station_paint.cjs` (When a station page paints its first row on a slow phone, measured.), `tools/measure_station_phone.cjs` (The station page at a phone's width: the two pinned surfaces, and what a), `tools/measure_station_render.cjs` (What one render of a built station page costs, and how much of that is the), `trainbudget/measure/benchmark.py` (Measure the journey search on a large invented feed.), `trainbudget/measure/grantham_sweep.py` (Answer the Stage 1 question for one origin: how many destinations fall under a budget?), `trainbudget/measure/sanity_report.py` (Question a budget count before believing it.) |
| Operator tools | `tools/agents_map.py` (Write the module rows of AGENTS.md from each module's own docstring.), `tools/build_inputs.py` (One fingerprint for every source a built site is made of.), `tools/build_timetable_index.py` (Write the per-origin timetable slices a build can be built from.), `tools/check_commit_message.py` (Check a commit message against the convention in CONTRIBUTING.md.), `tools/check_facet_reference.py` (Refuse a release whose checked-in facet reference data has drifted from the registry.), `tools/check_fare_rate.py` (Refuse a published fare whose price per minute of journey is not plausible.), `tools/check_known_fares.py` (Refuse a release whose page disagrees with a fare a person checked by hand.), `tools/check_links.py` (Check whether a seller's ticket link lands on a search the reader can use.), `tools/check_page_state.py` (Hold the station page's controls to being drawn from the state, not read back.), `tools/check_release_clearance.py` (Refuse a public release that no licence clearance covers.), `tools/check_slice_equivalence.py` (Check that a slice answers every page question the whole feed does.), `tools/check_source_credit.py` (The acknowledgement travels with the pages that show a fare.), `tools/check_types.py` (Run mypy over the tree and fail on a type error in a file that is clean today.), `tools/easy_fares_check.py` (Reality-check the budget model against the real fares database.), `tools/feed_change_report.py` (Compare two feed snapshots and say what changed, for the operator.), `tools/inspect_knowledgebase.py` (Show what a Knowledgebase reference feed actually contains.), `tools/measure_build_memory.py` (Measure what a build holds in memory, so the worker budget can be re-derived.), `tools/measure_link_crawl.py` (What the release build's link crawl costs, and what a cheaper one would.), `tools/measure_locations_load.py` (What the shard merge stops paying for, measured on the real feed.), `tools/measure_origin_costs.py` (Time the per-origin phases of a page build, and print the distribution.), `tools/measure_place_cap.py` (What a cap on the places a station page lists would save, measured.), `tools/measure_worker_pages.py` (Measure the peak of one pool worker while it is assembling pages.), `tools/page_bytes.py` (Measure what a built page costs, in the bytes a host counts.), `tools/propose_fare_construction_stations.py` (Propose station codes for the reviewed fare-construction list, from names.), `tools/propose_nature_stations.py` (Propose station codes for the reviewed nature-sites list, from trust pages.), `tools/propose_reviewed_settlements.py` (Propose the settlement class of every reviewed station fallback, from evidence.), `tools/regenerate_destination_facets.py` (Rebuild ``reference-data/destination-facets.json`` from its named sources.), `tools/verify.py` (The checks a change has to pass, in one command, on any platform.) |
<!-- module-map:end -->
| The page | `page/station/` (the station route's script, one file per panel, concatenated in the order `trainbudget/build/page_templates.py` names): `page/station/state.js` (the page's one mutable object and the gestures every listener calls), `page/station/payload.js` (the payload and the shared element reads), `page/station/railcards.js` (the party, the card and the price), `page/station/budget.js` (the budget field and its clamp), `page/station/service-day.js` (the day the table reports), `page/station/filters.js` (the refinements and the destination-type chips), `page/station/ticket-modes.js` (which fares the list shows, and the empty states), `page/station/format.js` (money, durations and dates), `page/station/table.js` (the results table and its render), `page/station/row-cells.js` (a row's cells), `page/station/fare-panel.js` (a row's own disclosure), `page/station/row-actions.js` (the ticket link and the row's railcard note), `page/station/provenance.js` (where the numbers came from and how old they are), `page/station/picker.js` (the change-station block), `page/station/shortlist.js` (the shortlist and the dock), `page/station/url-state.js` (the address as the search), `page/station/wiring.js` (the listeners and the first render), `page/station.css`, `page/chooser.js`, `page/chooser.css`, `page/theme.js`, `page/shared.css`, `page/privacy.css`, inlined into each route by `trainbudget/build/page_templates.py`, `page/goatcounter-count.js` (GoatCounter's count script, vendored, copied to the site root when the release injects the counter), `page/goatcounter.html` (the snippet the release passes to `--analytics-snippet`) |
| The runner | `run.py` (`build` and `serve`, the one script at the root; the launchers beside it are `run.bat` and `build_stations.bat`) |
| Tests | `tests/` (35 modules, one per area, including `tests/test_suppressions.py`: every suppression names its cause); `tests/test_workflows.py` holds a workflow's `run:` blocks to shell that says what it was written to say; what the page says is one module per subject -- `tests/test_build_demo_page.py`, `tests/test_build_fares.py`, `tests/test_build_provenance.py`, `tests/test_build_chooser.py`, `tests/test_build_links.py` -- over the fixture in `tests/page_harness.py`; the browser suite is `tests/browser_test.cjs` -- the entry point the tools and CI invoke -- over `tests/browser/`: `tests/browser/harness.cjs` (the page list, the server, the money and date helpers, and the report), `tests/browser/chooser.cjs`, `tests/browser/release-root.cjs`, `tests/browser/a11y-matrix.cjs`, `tests/browser/station.cjs` (the station page's driver and the state every section reads), and one module per section of checks: `tests/browser/station-render.cjs`, `tests/browser/station-filters.cjs`, `tests/browser/station-rows.cjs`, `tests/browser/station-fares.cjs`, `tests/browser/station-shortlist.cjs`, `tests/browser/station-layout.cjs`, `tests/browser/station-picker.cjs`, `tests/browser/station-assets.cjs`, `tests/browser/counter.cjs` (the visit counter, with its script blocked and with its count blocked), and `tests/browser/playwright-version` (the one file that names the browser CI and a local run both launch) |
| Decisions | `adr/` (86 ADRs, each with a Status line), `docs/audits/` (empty on 26 October 2026, and the rule that keeps it that way: a review lives here only while it has an ask `docs/open-work.md` has not numbered, and a review with nothing open is deleted, its asks becoming items there and its findings rows in `docs/settled-work.md`), `docs/open-work.md` (what is still open, numbered, and why, including the questions waiting on a person), `docs/settled-work.md` (every closed item, with the check that holds it, and the rejected designs), `docs/build-performance-findings.md` (every measured figure), and the five subject documents the README opens onto: `docs/fares.md`, `docs/timetables.md`, `docs/feeds.md`, `docs/builds.md`, `docs/running-it.md` |
| Data | `reference-data/destination-facets.json`, checked against the registry in CI |
| Skills | `.agents/skills/fare-verification/SKILL.md` (a page's fares against the National Rail journey planner, each mismatch becoming a `tests/known_fares.toml` row) |
| Release | `.github/workflows/deploy.yml` (the jobs, the matrices, the secrets and the calls), `.github/actions/licensed-feeds/action.yml` (the licensed downloads every job makes), `tools/release/` (every step that is more than one call, as `python -m tools.release.<step>`, held by `tools/test_release.py`): `tools/release/__init__.py` (`RELEASE`, the shape the release publishes), `tools/release/commits.py`, `tools/release/schedule.py`, `tools/release/feed_state.py`, `tools/release/feed_identity.py`, `tools/release/facets.py`, `tools/release/share.py`, `tools/release/manifest.py`, `.github/workflows/regenerate-facets.yml` (manual: the facet reference regenerated from CI's download, as an artifact), `licences/release-clearance.md` (a person's decision, and it gates publishing) |

## The rules, and what enforces them

The third column is the half that makes the other two true: the exact thing that
fails, and what it says when it does. A row that cannot name one is not a rule
here but a wish, so it belongs in `docs/open-work.md` instead (R7 of the 18
October 2026 plan).

| Rule | Enforcer | What fails, and what it says |
|---|---|---|
| Conventional Commits, subject under 80 characters | `tools/check_commit_message.py`, run by `.githooks/commit-msg` before the commit exists, and in CI over the commits a push adds | exits 1 and prints one line per offending commit, naming the subject and the character count |
| No commit credits Codebuff or Freebuff, in the author or in a trailer | `tools/check_commit_message.py`, run by `.githooks/commit-msg` before the commit exists, and in CI over the commits a push adds | exits 1 naming the tool the message credits and the line it sits on, or the author identity that credits it, and says to keep the why and drop the credit |
| A line of shell in a workflow's `run:` block carries no backtick, so the shell cannot run a message instead of printing it | `tests/test_workflows.py`, in both unit runs | fails naming the workflow, the line and the shell line it read; a scan that did not reach the verify step's block fails too |
| A built page stays inside its byte budget | `tools/page_bytes.py --site _site` in CI | exits 1 naming the route and its overage; exits 2 rather than passing on a page whose payload it did not parse, or on a site with no page |
| A fare checked by hand against National Rail is the fare the page shows | `tools/check_known_fares.py --site _site` in the assemble job, over `tests/known_fares.toml` | exits 1 naming the row, the page's price and the one National Rail sold, or the page, destination or card the page lacks, unless the page says it left that destination out by the reachability rule (ADR-0076) or the place cap (ADR-0077), which warns naming the rule and its count; warns on a row checked more than 90 days ago; exits 2 when the table or the site could not be read |
| A page that shows a fare carries the National Rail credit | `tools/check_source_credit.py --site _site` in the assemble job | exits 1 naming the page that carries a fare and no credit; exits 2 when it could not read the page it was given |
| The facet reference data matches the registry | `tools/check_facet_reference.py` in CI | exits 1 naming the facet and the two values that differ; exits 2 when either side could not be read |
| Rebuild when any build input changed | `tools/build_inputs.py` in both workflow steps, held by `tools/test_build_inputs.py` | exits 1 in the step that would publish a stale site; `tools/test_build_inputs.py` fails naming the input the list forgot |
| The shard bound and share count are the ones the performance record states | `tests/test_workflows.py`, against the bound table in `docs/build-performance-findings.md` | fails naming the workflow's `timeout-minutes`, share count or nearing minute beside the document's, so a bound cannot drift from the figure that justifies it |
| A path a workflow names is a path this tree holds | `tests/test_workflows.py`, in both unit runs | fails naming the workflow, the line and every missing path, because `hashFiles` answers the empty string for a path that is not there: the key stays well formed, every commit hashes the same, and nothing says so |
| The page's JavaScript parses, as every file and as each route's concatenated script | `python -m tools.verify --fast` (`node --check` on every page script, then on each route's concatenated script as `page_templates` builds it) | exits 1 with the syntax error, and on a concatenation names the panel whose addition broke it; with no node on PATH the step reports `not run` and the run exits 2 |
| The browser is one version everywhere | `tests/test_workflows.py` and `tools/test_verify.py` | fail naming the workflow or the command and the version each names, against `tests/browser/playwright-version` |
| A render reads the state, not the controls | `tools/check_page_state.py`, run by `python -m tools.verify --full` | exits 1 naming the panel and its read count; `tools/test_check_page_state.py` holds the verdict, including that a panel the budget does not name fails |
| Every module is on the map above | `tests/test_agents_map.py`, against `python -m tools.agents_map --check` | fails naming the module, page asset or operator tool that `AGENTS.md` does not name, the map entry with no file behind it, or the generated block a docstring change left stale |
| A module that is type-clean stays type-clean | `tools/check_types.py`, run by `python -m tools.verify --full` and in CI | exits 1 and prints every mypy error in a file on the clean list; exits 2 when mypy is missing or reported nothing at all |
| Every suppression names its cause | `tests/test_suppressions.py` | fails naming the file and line whose `noqa` carries no reason |
| A sentence is proved on the rendered page, not in the script that prints it | `tests/test_test_suite_shape.py`, `CopyPinRatchetTest` | fails naming the module, its count and the sentences when a module adds a copy pin against `page_script(...)`, or goes above the count in `COPY_PINS` |
| A page's claims that only browser JS can prove | the Playwright suite, `tools/verify.py --browser` | prints `FAIL` with the check's own message and the run exits 1; a check the page could not exercise is reported `not exercised`, never passed |

## Habits this repository asked for

- A real-feed defect gets the smallest synthetic record that reproduces it,
  added to `make_synthetic_feed.py` with a comment naming the commit that fixed
  it. A wrong price found against National Rail also gets a row in
  `tests/known_fares.toml`, with the date it was checked, so the real page is
  held to it on every release. A licensed feed cannot be checked in (ADR-0005), so the fixture is the only
  regression test there is (F7 of the 8 October 2026 agent-efficiency audit).
- A measurement plan is written before a figure is quoted and the figure is
  dated (ADR-0032).
- Comments say why, not what. A comment that restates the line is noise.
- Commit messages say why the change is needed and what it costs, and name a
  command whose output a reviewer can reproduce.
