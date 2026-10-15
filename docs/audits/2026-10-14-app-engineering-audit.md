# Whole-app engineering audit: performance, modernity, future-proofing

**Date:** 14 October 2026
**Pruned:** 15 October 2026, to what it still asks for. Nine of its ten
recommendations landed the next day; the table below names what holds each, and
the one still open is recommendation 6, filed in `docs/open-work.md` as "A
station page is 354 KB, and nobody has decided whether that is the payload".
**Scope:** every module at the repository root, `page/`, `tools/`, `tests/`, both
workflows. Graded on the four dimensions, then given as numbered
opportunities — the audit changes nothing.
**Method:** `python -m tools.verify --fast` (1,120 tests), the two feed-scale
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

## What it asked for, and what holds it

| # | Asked | Holds it |
|---|---|---|
| 1 | Split `build_demo_page.py` along its seams | ADR-0071: seven modules and a command, with the facade, the one-way imports and the patch sites named |
| 2 | Write the classification cache before the cache identity that names it | `build_state.load_page_fares` resolves the cache paths from the bytes as they are *after* the classification pass; the ordering and its cost (55.6 s against 2.6 s restored) are in the comment beside it |
| 3 | De-flake `test_the_caches_of_older_feeds_are_tidied_and_this_one_is_kept` | `tests/test_page_caches.FaresCacheTest` refuses the network in `setUp`, so the test no longer depends on the ONS server's answer |
| 4 | Add a type checker to CI | ADR-0072 and `tools/check_types.py`: a ratchet over the 27 files whose own errors are zero, run by `--full` and by the deploy workflow. The census is 350 errors in 29 of 70 files in 7 s |
| 5 | Declare the Python the app runs on | `.python-version` (3.12) and the note under "Run it" in `README.md` |
| 7 | Kill the tools' path dance | Every tool is run as `python -m tools.<name>`: the `sys.path` insert and its 34 `# noqa: E402` are gone from 16 modules, and the commands in `README.md`, `CONTRIBUTING.md`, the ADRs, both workflows and `docs/open-work.md` follow |
| 8 | Make the suppression census a check, not a table | `tests/test_suppressions.py`: a `# noqa` names its cause on its own line or in the comment block above it, and the census prints what it found |
| 9 | Correct the documented runtimes | `AGENTS.md` and `docs/build-performance-findings.md`, dated 15 October 2026 |
| 10 | Keep the one-owner rule for build inputs | Nothing to do: `tools/build_inputs.py` stays a glob, and the measurement that says it is not wasting rebuilds is in the recommendation itself |

## The one it still asks for

6. **[P2] Decide whether a 354 KB page is the intended payload.** Measured on the
   fresh real build: the station page is **354 KB raw, 53 KB gzip**, of which the
   route's CSS is 54 KB (17 KB gzip) and its script 149 KB (45 KB gzip); the
   chooser and privacy pages are 28 KB and 26 KB. The site budget (800 MB) is not
   the constraint — per-page parse and paint on a phone is. Before changing
   anything, measure: split the payload per ticket mode and time first paint on a
   4x-throttled connection, then decide whether the split earns its complexity
   (ADR-0032 wants the plan written first). That measurement is open work now, in
   `docs/open-work.md` with the figure and the decision rule.

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
