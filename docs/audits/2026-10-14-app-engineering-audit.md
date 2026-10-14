# Whole-app engineering audit: performance, modernity, future-proofing

**Date:** 14 October 2026
**Scope:** every module at the repository root, `page/`, `tools/`, `tests/`, both
workflows. Graded on the four dimensions, then given as numbered
opportunities — the audit changes nothing.
**Method:** `python tools/verify.py --fast` (1,120 tests), the two feed-scale
tests, a fresh real-feed single-origin build (`feeds/fares` +
`feeds/timetable`, notices `nre,rdg,ogl,accuracy`) served at
`127.0.0.1:8899` and driven in Chromium, `tools/page_bytes.py`, plus the
measurements below. This pass shares its date with
[the impeccable critique](2026-10-14-impeccable-critique.md); that document owns
the UX and copy findings, this one owns structure and cost. Neither repeats the
other's items.

## Scores

| Dimension | Score | The gap that costs the most |
|---|---|---|
| SPEC | 7 | The product promise in `PRODUCT.md` is delivered and exercised end to end. Two visible gaps are wording rather than capability: the chooser's duplicated download date and the 50-versus-53 destination counts (critique items 1 and 2). |
| DESIGN | 5 | `build_demo_page.py` is 5,639 lines with **120** top-level defs and classes, and it owns feed loading, page rendering, release gating, provenance, the worker pool and the shard merge at once. Careful, but not a structure a maintainer would praise. |
| CORRECTNESS | 6 | Exercised, not asserted: a real-feed build writes a page that renders with no console or network errors. Real defects remain: a cache identity a build can invalidate by writing a classification file after computing it, and one test that failed once in four runs of the same tree. |
| QUALITY | 5 | 20,471 lines of Python at the root, one 604-line function, 40 `# noqa`, 16 `# type: ignore`, no type checker, and a supported Python version that is declared nowhere. |

## Numbered recommendations

1. **[P1] Split `build_demo_page.py`.** 5,639 lines, 120 top-level definitions,
   `build_payload` alone 604 lines, `_build_all_origins` 431, `read_provenance`
   213, `parse_args` 198. The seams are already visible in the file and in the
   tests: feed provenance and metadata (~300 lines), the release gates and
   notices (~400), the page contexts and rendering (~1,200), the worker pool and
   shard merge (~700), and the resumable build state (~300). Split along those
   seams one at a time, each behind its existing tests; the page's own
   `page/station/*` split (F1) is the model that worked.
2. **[P1] Write the classification cache before the cache identity that names
   it.** `fares_cache_identity` hashes the bytes of every classification file
   beside the feed (`location_lookup_candidates`), and the ONS/classification
   pass writes `fares.location-types.json` beside that same feed. A build that
   writes it *after* the identity was computed leaves a cache pair that no later
   build can ever name, so the next build re-parses the feed (measured elsewhere
   in this repository at 55.6s against 2.6s restored). Measured and proven: the
   identity changes the moment those bytes change.
3. **[P1] Then de-flake `test_the_caches_of_older_feeds_are_tidied_and_this_one_is_kept`.**
   It failed once in a full `--fast` run and passed in three other runs of the
   same tree, and the mechanism is legible in a diagnostic: when a cache
   directory holds three digest pairs, `prune_fare_index_caches` (keep=2,
   one protected) deletes two revision pairs — four files, where the test asserts
   two. Recommendation 2 is one source of a second pair. The other is that this
   test runs the real `main()`, so it makes live HTTP requests: the suite prints
   `ResourceWarning: <HTTPError 304>` from the feed/ONS fetches. Mock the fetch
   in this test, or assert on the pairs it created rather than on a count.
4. **[P2] Add a type checker to CI.** Every module is annotated and there are 16
   `# type: ignore` comments, but nothing reads them. `mypy --strict` on the
   root modules first, then `page`-facing code; it is a CI dependency, which this
   repository has so far refused, so it belongs in a decision record with the
   cost measured (`mypy` over 20,471 lines) rather than slipped into a workflow.
5. **[P2] Declare the Python the app runs on.** CI pins 3.12; this machine
   developed on 3.14. Nothing else — no `pyproject.toml`, no `requires-python` —
   states the range, so the only way to learn it is to read the workflow. A
   one-line `.python-version` plus a note in `README.md`, or a `pyproject.toml`
   with `requires-python` and no dependencies, makes the constraint explicit
   without adding a build system.
6. **[P2] Decide whether a 354 KB page is the intended payload.** Measured on the
   fresh real build: the station page is **354 KB raw, 53 KB gzip**, of which the
   route's CSS is 54 KB (17 KB gzip) and its script 149 KB (45 KB gzip); the
   chooser and privacy pages are 28 KB and 26 KB. The site budget (800 MB) is not
   the constraint — per-page parse and paint on a phone is. Before changing
   anything, measure: split the payload per ticket mode and time first paint on a
   4x-throttled connection, then decide whether the split earns its complexity
   (ADR-0032 wants the plan written first).
7. **[P3] Kill the tools' path dance.** 34 of the 40 `# noqa` are the same
   construct: a root-reaching `sys.path` insert in 16 modules under `tools/`,
   because each is run as `python tools/<name>.py`. Running them as
   `python -m tools.<name>` (they already form a package: `tools/__init__.py`
   exists and `tests` import them that way) deletes the insert and its
   suppression together.
8. **[P3] Make the suppression census a check, not a table.**
   `docs/open-work.md` records 40 suppressions and the cause each names, and
   nothing fails when a new `# noqa` arrives without one.
   `tests/test_agents_map.py` is the precedent: a check that reads the tree and
   names what is missing. A rule that every `# noqa` must be preceded by a
   comment naming its cause is a five-line test.
9. **[P3] Correct the documented runtimes.** `AGENTS.md` promises "`--fast` is
   about three minutes; `--full` about fifteen". Measured here, twice:
   **780 seconds** on an otherwise idle machine and **1,017 seconds** while a
   second suite ran alongside — thirteen to seventeen minutes for the same
   1,120 tests in one process. The three-minute figure is off by four whatever
   the load, and `docs/build-performance-findings.md` is where a measured figure
   belongs, dated, with the load it was taken under.
10. **[P3] Keep the one-owner rule for build inputs, now that it exists.** The
    three hand-kept lists this session collapsed into one
    (`build_demo_page.SOURCE_FILES`, derived from the build's own imports, with
    the runner importing it) are the pattern for anything else of that shape:
    `tools/build_inputs.py` remains a glob because CI needs a rule about where
    sources live, and measurement says it is not wasting rebuilds — of the last
    150 commits, 32 touched a `.py` file a build does not read, but **none**
    touched only the six root-level modules CI hashes. Leave it alone.

## What is already right, and should not be traded away

- **The cache keys are content digests, and the reason is written down.** Feed
  bytes, classification sources and the code reading them, all three, in names
  that cannot collide (ADR-0031). The identity work in recommendation 2 is a
  correctness bug in *when* the file is written, not a flaw in the key.
- **The failure modes refuse rather than guess.** A public build with no notices
  stops; a missing brand mark stops; a slice index missing a page names the codes
  before the build starts. For a page whose numbers are the product, that is the
  right default and it is enforced by tests.
- **The page's JavaScript is one file per panel and the test suite knows it.**
  `tests/test_page_assets.py` proves each file lands in the asset the build
  writes, so the split cannot quietly rot.

## The single most valuable next pass

**Split `build_demo_page.py` (recommendation 1), and take recommendation 2 with
it.** The file is 28% of the repository's Python and holds every concern the
product has; the cache-identity bug is a two-line ordering fault in the middle of
it that only a reader who already knows the whole file will find. Splitting first
makes the fix obvious and makes the next ten changes land in one place each.
Everything else on this list is cheap and can follow.
