# Working in this repository

A static site that answers "where can I go from this station for under £X",
built from two licensed National Rail feeds. Python 3 standard library only, no
`requirements.txt`, no `pyproject.toml`. Tests are `unittest`; one Playwright
suite is Node.

## Run this first

```
python tools/verify.py --fast      # the unit suites minus the feed-scale tests, and the page's JavaScript parsed
python tools/verify.py --full      # every unit test, the same suite the deploy workflow runs
python tools/verify.py --browser   # the demo and shape builds, then tests/browser_test.cjs
```

`--fast` is about three minutes; `--full` about fifteen. A step that could not run
(node missing, a build that wrote no page) reports `not run` and exits 2 rather
than passing quietly. One module while you work on it:
`python -m unittest tests.test_build_demo_page`.

## The map

| Area | Files |
|---|---|
| Fares | `atoc_fares.py` (the parser and the loaded database), `atoc_restrictions.py`, `parse_report.py`, `destination_coverage.py`, `retailer.py` |
| Timetable | `atoc_timetable.py` (the database, `focused()` and the slice index), `atoc_knowledgebase.py` |
| The build | `build_demo_page.py` (writes a page), `build_workers.py` (the pool and its memory floor), `build_stations.py` (the command), `page_templates.py` (the templates and one reader for `page/`) |
| The page | `page/station.js`, `page/station.css`, `page/chooser.js`, `page/chooser.css`, `page/theme.js`, `page/shared.css`, `page/privacy.css`, inlined into each route by `page_templates.py` |
| The runner | `run.py` (`build` and `serve`) |
| Feeds | `dtd_download.py`, `feeds_cli.py`, `make_synthetic_feed.py` (the fixture every test builds on), `feed_audit.py`, `dtd_audit.py`, `damage_feed.py`, `fuzz_feed.py` |
| Measurements | `benchmark.py`, `grantham_sweep.py`, `sanity_report.py` |
| Operator tools | `tools/verify.py`, `tools/build_inputs.py`, `tools/build_timetable_index.py`, `tools/page_bytes.py`, `tools/check_slice_equivalence.py`, `tools/check_facet_reference.py`, `tools/check_commit_message.py`, `tools/check_fare_rate.py`, `tools/check_links.py`, `tools/check_release_clearance.py`, `tools/feed_change_report.py`, `tools/measure_build_memory.py`, `tools/measure_worker_pages.py`, `tools/regenerate_destination_facets.py`, `tools/easy_fares_check.py`, `tools/inspect_knowledgebase.py`, `tools/propose_fare_construction_stations.py`, `tools/propose_nature_stations.py`, `tools/propose_reviewed_settlements.py` |
| Tests | `tests/` (28 modules, one per area); the page suite's shared fixture is `tests/page_harness.py`, and the browser suite is `tests/browser_test.cjs` |
| Decisions | `adr/` (67 ADRs, each with a Status line), `docs/open-work.md` (what is still open and why), `docs/build-performance-findings.md` (every measured figure) |
| Data | `reference-data/destination-facets.json`, checked against the registry in CI |
| Release | `.github/workflows/deploy.yml`, `licences/release-clearance.md` (a person's decision, and it gates publishing) |

## The rules, and what enforces them

| Rule | Enforcer |
|---|---|
| Conventional Commits, subject under 80 characters | `tools/check_commit_message.py`, in CI over the commits a push adds |
| A built page stays inside its byte budget | `tools/page_bytes.py --site _site` in CI |
| The facet reference data matches the registry | `tools/check_facet_reference.py` in CI |
| Rebuild when any build input changed | `tools/build_inputs.py` in both workflow steps, held by `tools/test_build_inputs.py` |
| The page's JavaScript parses | `tools/verify.py --fast` (`node --check` on `page/*.js`) |
| Every module is on the map above | `tests/test_agents_map.py` |
| A page's claims that only browser JS can prove | the Playwright suite, `tools/verify.py --browser` |
| Measured figures live in one place | `docs/build-performance-findings.md`; other docs link to it |

## Habits this repository asked for

- A real-feed defect gets the smallest synthetic record that reproduces it,
  added to `make_synthetic_feed.py` with a comment naming the commit that fixed
  it. A licensed feed cannot be checked in (ADR-0005), so the fixture is the only
  regression test there is (F7 of the 8 October 2026 agent-efficiency audit).
- A measurement plan is written before a figure is quoted and the figure is
  dated (ADR-0032).
- Comments say why, not what. A comment that restates the line is noise.
- Commit messages say why the change is needed and what it costs, and name a
  command whose output a reviewer can reproduce.
