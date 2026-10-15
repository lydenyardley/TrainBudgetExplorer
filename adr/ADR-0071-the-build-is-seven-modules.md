# ADR-0071: The build is seven modules and a command

**Status:** Accepted
**Date:** 15 October 2026
**Relates to:** ADR-0019 (one page per station), ADR-0031 (the cache keys are
content digests), ADR-0055 (the runner builds what the reader will ask for),
ADR-0070 (the fares declarations are their own module), F1 of the 8 October 2026
agent-efficiency audit (the station route's own split), item 1 of the 14 October
2026 app-engineering audit

## Context

`build_demo_page.py` was 5,799 lines with 120 top-level definitions and held every
concern the product has at once: feed loading, provenance, notices and release
gating, the payload, the markup, the worker pool, the shard merge and the
resumable build state. `build_payload` alone was 591 lines, `_build_all_origins`
442, `read_provenance` 213 and `parse_args` 198. It was 28% of the repository's
Python, and the audit's own summary said it was "not a structure a maintainer
would praise".

Two things made the split a decision rather than a mechanical edit.

- **The module is a patching surface.** Twelve tests and the page harness patch
  `build_demo_page.CACHE_DIR`, and one each patch `FARE_INDEX_CACHE_VERSION`,
  `source_fingerprint` and `NRE_LOGO`. A name that moves takes its patch site
  with it: a test that patches the old module still passes its own setup and
  then quietly exercises the real directory, which is exactly the failure the
  harness comment warns about.
- **Every caller reaches into it by name.** 45 import statements in 41 files
  take names from it, and `SOURCE_FILES` is derived by walking *this module's*
  imports, so the split changes the cache keys of every feed unless the walk
  still starts here.

The station route's split (F1) is the model that worked: one file per panel, a
test that proves each file lands in the asset the build writes, and no change to
what a caller imports.

## Decision

The build is seven modules beside a command.

| Module | Holds | Lines |
|---|---|---|
| `build_state.py` | The caches and the resumable state: cache identities, paths and pruning, the page facts, the service week, the resume file, `SOURCE_FILES` | 803 |
| `build_provenance.py` | Where the numbers came from: feed metadata, the download manifest, the dates, the reference feed, `read_provenance` | 648 |
| `build_release.py` | The notices, the National Rail credit, the privacy route, the release manifest and the gate that refuses a public build | 433 |
| `build_assets.py` | The files a site is made of: the content-digest asset names and writers, the writing of a page, the slug helpers, the offline station asset | 411 |
| `build_payload.py` | The payload: `PageContext`, the pools, destination rows, `build_payload`, and `encode_payload` | 1,691 |
| `build_render.py` | The markup: a payload and a template become the page, the chooser and the privacy route | 524 |
| `build_pool.py` | The build itself: `BuildContext`, the phases, the worker pool and the shard merge | 1,254 |

`build_demo_page.py` keeps the command -- `parse_args` and `main` -- and is 410
lines.

Four rules make the split hold.

- **Imports run one way.** `assets`, `state`, `release`, `provenance`,
  `payload`, `render`, `pool`, then the command: a module imports only from the
  ones before it in that list. A cycle is a broken layering, not something to
  defer with a function-local import. Where the layering forced a name to move,
  it moved:
  `EVERYTHING_PENCE` is now `atoc_fares.EVERYTHING_PENCE`, beside the queries
  asked with it, because the provenance pass and the payload both need it and
  neither may import the other.
- **`build_demo_page` re-exports the names other files reach for.** It is the
  entry point every tool, test and workflow runs, and a caller should not have
  to know which module the split put a name in. The re-export block is generated
  from the call sites in the tree, and a name that stops being re-exported fails
  at import rather than at a call site.
- **A test patches the module whose code reads the name.** `build_state.CACHE_DIR`,
  `build_state.FARE_INDEX_CACHE_VERSION` and `build_release.NRE_LOGO` are read by
  the module that defines them, so that is the patch site; the facade would be a
  copy. Two names showed what the rule has to say next to that. The merge reads
  `source_fingerprint`, imported from `build_state`, so its test patches
  `build_pool.source_fingerprint` -- the module whose code calls it -- because a
  name imported by value is bound in the importer. And the shared assets' names
  are read *through* `build_assets` (`build_assets.station_script_asset_name()`)
  rather than bound by value in the four modules that need one, so a test that
  changes them changes them in one place.
- **`SOURCE_FILES` still starts at `build_demo_page.py`.** The walk follows
  imports, so the seven modules are hashed into every cache key and every
  `tools/build_inputs.py` fingerprint without being named anywhere.

## Evidence

- The partition was made by a generator that cuts top-level blocks with the
  comments above them and computes each module's imports from `symtable`'s scope
  analysis, excluding annotations because `from __future__ import annotations`
  makes them strings. Its own check -- every non-blank line of the original
  outside its header lands in exactly one module -- passes, and a re-run of the
  import analysis reports **nothing missing** in all eight files.
- A second checker walks the tree for `build_demo_page.<name>` and `from
  build_demo_page import ...` and reports nothing missing from the facade.
- `python -c "import build_demo_page"` reaches every module, and
  `SOURCE_FILES` names all seven.
- The suites that hold the moved code pass: `tests/test_page_caches.py` (45
  tests), `tests/test_build_provenance.py`, `tests/test_page_output.py`,
  `tests/test_build_demo_page.py`, `tests/test_page_gates.py`,
  `tests/test_page_runner.py`, `tools/test_measure_origin_costs.py`. Each of the
  three tests whose expectation the split made stale was updated to the fact it
  now holds -- `price_source_from_manifest` and `price_source_from_metadata`
  return the feed's name, and the page carries the download date beside it for
  its own script to compose (`feed_date_from`).

## Consequences

- The audit's item 1 and the cache-identity ordering fix it asked to take with
  it are in different files now. `fares_cache_identity` and the write that has
  to follow it are both in `build_state.py`, in the same 60 lines.
- A new name goes in the module that owns its concern, and is added to the
  facade only if a caller outside the build reaches for it. The generated
  re-export block is the contract; `tests/test_agents_map.py` keeps the seven on
  the `AGENTS.md` map.
- `build_payload.py` at 1,691 lines is the largest of the seven and the one
  closest to the old shape. It stays whole because it is one concern -- the
  page's own content and its wire format -- and `build_payload` (591 lines) is
  the one function still large enough to be worth watching. Splitting it again
  is a change with its own measurement, not a continuation of this one.
- `python -m tools.verify --fast` costs the same after the split: the modules
  are read fewer times, not more, and the split adds no import of a feed.
