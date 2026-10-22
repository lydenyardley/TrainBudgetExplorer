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

`--fast` is the page's own modules -- 228 tests, **about 50 s** measured 21
October 2026 -- and it fails when its unit step passes the five-minute ceiling,
so a module added to the list is a decision rather than a drift. `--full` is every
module including the feed-scale ones, **35 min** measured 15 October 2026. Both
figures are dated and reproducible in `docs/build-performance-findings.md`. A step
that could not run (node missing, mypy missing, actionlint missing, a build that
wrote no page) reports `not run` and exits 2 rather than passing quietly -- which
is why both want `python -m pip install actionlint-py` (it lints
`.github/`) and only `--full` wants `mypy`. One module while you work on it:
`python -m unittest tests.test_build_demo_page`.

Once per clone, `git config core.hooksPath .githooks`, so a message the
commit checker refuses never becomes a commit.

## The map

| Area | Files |
|---|---|
| Fares | `atoc_fares.py` (the loaded database and the queries asked of it), `atoc_fares_loader.py` (the feed readers and the classification sources, mixed into `FaresDb`), `atoc_fare_declarations.py` (the record layouts, row types and reviewed tables both readers work on), `atoc_restrictions.py`, `parse_report.py`, `destination_coverage.py`, `retailer.py` |
| Timetable | `atoc_timetable.py` (the database, `focused()` and the slice index), `atoc_knowledgebase.py` |
| The build | `build_demo_page.py` (the command, and the one place the build's modules are named together), `build_state.py` (the caches and the resumable state, and `SOURCE_FILES`), `build_provenance.py` (where the numbers came from), `build_release.py` (the notices, the credit and the gate that refuses a public build), `build_assets.py` (the files a site is made of and the addresses that reach them), `build_payload.py` (every destination a page lists, and the payload's wire format), `build_render.py` (a payload and a template become the page), `build_pool.py` (the phases, the worker pool and the shard merge), `build_workers.py` (the pool and its memory floor), `build_stations.py` (the command), `page_templates.py` (the templates and one reader for `page/`) |
| The page | `page/station/` (the station route's script, one file per panel, concatenated in the order `page_templates.py` names): `page/station/state.js` (the page's one mutable object and the gestures every listener calls), `page/station/payload.js` (the payload and the shared element reads), `page/station/railcards.js` (the party, the card and the price), `page/station/budget.js` (the budget field and its clamp), `page/station/service-day.js` (the day the table reports), `page/station/filters.js` (the refinements and the destination-type chips), `page/station/ticket-modes.js` (which fares the list shows, and the empty states), `page/station/format.js` (money, durations and dates), `page/station/table.js` (the results table and its render), `page/station/row-cells.js` (a row's cells), `page/station/fare-panel.js` (a row's own disclosure), `page/station/row-actions.js` (the ticket link and the copy handoff), `page/station/provenance.js` (where the numbers came from and how old they are), `page/station/picker.js` (the change-station block), `page/station/shortlist.js` (the shortlist and the dock), `page/station/url-state.js` (the address as the search), `page/station/wiring.js` (the listeners and the first render), `page/station.css`, `page/chooser.js`, `page/chooser.css`, `page/theme.js`, `page/shared.css`, `page/privacy.css`, inlined into each route by `page_templates.py` |
| The runner | `run.py` (`build` and `serve`) |
| Feeds | `dtd_download.py`, `schedule_download.py` (Network Rail's own CIF under the Open Government Licence: a URL, optionally with a credential, and a refusal when what arrives is not a schedule), `feeds_cli.py`, `make_synthetic_feed.py` (the fixture every test builds on), `feed_audit.py`, `dtd_audit.py`, `damage_feed.py`, `fuzz_feed.py` |
| Measurements | `benchmark.py`, `grantham_sweep.py`, `sanity_report.py`, `measure_station_defer.cjs` (what `defer` on the shared station list buys a reader, in `docs/build-performance-findings.md`), `tools/measure_locations_load.py` (what the shard merge's locations-only load saves, and that it reads the same stations), `tools/measure_link_crawl.py` (what the release's link crawl costs and what a cheaper one would), `tools/measure_station_paint.cjs` (when a real station page paints its first row on the slow-mobile profile), `tools/measure_station_phone.cjs` (the two pinned surfaces and the budget re-render at a phone's width, and under a slowed CPU) |
| Operator tools | `tools/verify.py` (with actionlint over the workflows: `python -m pip install actionlint-py`), `tools/check_types.py` (the type ratchet, item 4 of the 14 October 2026 audit), `tools/build_inputs.py`, `tools/build_timetable_index.py`, `tools/page_bytes.py`, `tools/check_slice_equivalence.py`, `tools/check_facet_reference.py`, `tools/check_commit_message.py`, `tools/check_fare_rate.py`, `tools/check_links.py`, `tools/check_release_clearance.py`, `tools/check_source_credit.py`, `tools/check_known_fares.py` (the built pages against `tests/known_fares.toml`, the fares checked by hand), `tools/feed_change_report.py`, `tools/check_page_state.py`, `tools/measure_build_memory.py`, `tools/measure_worker_pages.py`, `tools/measure_origin_costs.py`, `tools/regenerate_destination_facets.py`, `tools/easy_fares_check.py`, `tools/inspect_knowledgebase.py`, `tools/propose_fare_construction_stations.py`, `tools/propose_nature_stations.py`, `tools/propose_reviewed_settlements.py` |
| Tests | `tests/` (35 modules, one per area, including `tests/test_suppressions.py`: every suppression names its cause); `tests/test_workflows.py` holds a workflow's `run:` blocks to shell that says what it was written to say; what the page says is one module per subject -- `tests/test_build_demo_page.py`, `tests/test_build_fares.py`, `tests/test_build_provenance.py`, `tests/test_build_chooser.py`, `tests/test_build_links.py` -- over the fixture in `tests/page_harness.py`; the browser suite is `tests/browser_test.cjs` -- the entry point the tools and CI invoke -- over `tests/browser/`: `tests/browser/harness.cjs` (the page list, the server, the money and date helpers, and the report), `tests/browser/chooser.cjs`, `tests/browser/release-root.cjs`, `tests/browser/a11y-matrix.cjs`, `tests/browser/station.cjs` (the station page's driver and the state every section reads), and one module per section of checks: `tests/browser/station-render.cjs`, `tests/browser/station-filters.cjs`, `tests/browser/station-rows.cjs`, `tests/browser/station-fares.cjs`, `tests/browser/station-shortlist.cjs`, `tests/browser/station-layout.cjs`, `tests/browser/station-picker.cjs`, `tests/browser/station-assets.cjs`, and `tests/browser/playwright-version` (the one file that names the browser CI and a local run both launch) |
| Decisions | `adr/` (73 ADRs, each with a Status line), `docs/audits/2026-10-21-audit-asks.md` (every audit ask still open, merged, numbered and mapped to the open-work item that tracks it; a review with nothing open is deleted, its asks moving here and its findings into the record), `docs/open-work.md` (what is still open, numbered, and why, including the questions waiting on a person), `docs/settled-work.md` (every closed item, with the check that holds it, and the rejected designs), `docs/build-performance-findings.md` (every measured figure) |
| Data | `reference-data/destination-facets.json`, checked against the registry in CI |
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
| A fare checked by hand against National Rail is the fare the page shows | `tools/check_known_fares.py --site _site` in the assemble job, over `tests/known_fares.toml` | exits 1 naming the row, the page's price and the one National Rail sold, or the page, destination or card the page lacks; warns on a row checked more than 90 days ago; exits 2 when the table or the site could not be read |
| A page that shows a fare carries the National Rail credit | `tools/check_source_credit.py --site _site` in the assemble job | exits 1 naming the page that carries a fare and no credit; exits 2 when it could not read the page it was given |
| The facet reference data matches the registry | `tools/check_facet_reference.py` in CI | exits 1 naming the facet and the two values that differ; exits 2 when either side could not be read |
| Rebuild when any build input changed | `tools/build_inputs.py` in both workflow steps, held by `tools/test_build_inputs.py` | exits 1 in the step that would publish a stale site; `tools/test_build_inputs.py` fails naming the input the list forgot |
| The shard bound and share count are the ones the performance record states | `tests/test_workflows.py`, against the bound table in `docs/build-performance-findings.md` | fails naming the workflow's `timeout-minutes`, share count or nearing minute beside the document's, so a bound cannot drift from the figure that justifies it |
| The page's JavaScript parses, as every file and as each route's concatenated script | `python -m tools.verify --fast` (`node --check` on every page script, then on each route's concatenated script as `page_templates` builds it) | exits 1 with the syntax error, and on a concatenation names the panel whose addition broke it; with no node on PATH the step reports `not run` and the run exits 2 |
| The browser is one version everywhere | `tests/test_workflows.py` and `tools/test_verify.py` | fail naming the workflow or the command and the version each names, against `tests/browser/playwright-version` |
| A render reads the state, not the controls | `tools/check_page_state.py`, run by `python -m tools.verify --full` | exits 1 naming the panel and its read count; `tools/test_check_page_state.py` holds the verdict, including that a panel the budget does not name fails |
| Every module is on the map above | `tests/test_agents_map.py` | fails naming the module, page asset or operator tool that `AGENTS.md` does not name, and the map entry with no file behind it |
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
