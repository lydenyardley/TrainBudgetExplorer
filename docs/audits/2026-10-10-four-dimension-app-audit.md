# Whole-app audit: the four dimensions

**Date:** 10 October 2026
**Commit reviewed:** `1ecd719` on `main`
**Scope:** the whole app: the build (`build_demo_page.py`, `build_workers.py`,
`page_templates.py`, `page/`), the feed layer (`atoc_fares.py`,
`atoc_timetable.py`, `atoc_restrictions.py`, `atoc_knowledgebase.py`), the runner
and the operator tools, the tests, and the three generated routes.
**Method:** SPEC, DESIGN, CORRECTNESS and QUALITY, with CORRECTNESS graded from
behaviour actually exercised (the repository's own Playwright suite plus a
hand-driven pass over the built pages) rather than from re-reading claims.
**Pruned:** 11 and 14 October 2026, to the one item that is still open. Thirteen
of the fourteen recommendations landed on 11 October 2026 and each is held by an
artifact; the settled table is now in `docs/open-work.md` under "The 10 October
2026 whole-app audit", because that file is the register and a closure record
belongs with the closures. The scores and the reading of the 10 October state are
not kept: the artifact table is the answer to "was this ever looked at".

## Still open

### Decide or render the non-fare routes' notices

**The question, in plain words.** When a build is given licence and attribution
notices (`--notices nre,rdg,ogl,accuracy`), where do they appear today? Only the
station page (`from/<slug>/`) carries them. The two other routes a release
serves, the chooser at `/` and the notice at `/privacy/`, contain no licence or
attribution wording at all.

**Why it is a question and not a bug.** The station page is the one route that
shows a price. The licences and attributions the operator supplies say who the
fares and times are sourced from, and those words belong beside the numbers.
Whether that obligation must also ride on the chooser and the privacy page is a
judgement about the licence terms themselves, which this project cannot make
alone.

**There are two ways to close it, and both are legitimate.** Record the decision
that the notices travel with the pages that show fares, and add the build check
that proves it, so a future route that shows fares without its notices is caught;
or render the notices on the chooser and the privacy page too, so every route a
release serves carries the attribution.

**What it needs from a person.** A decision about which, made the way the rest of
this project's licence questions have been: a written, dated answer in a pull
request, recorded in `licences/release-clearance.md` alongside the other licence
positions. The tool half, a build check that names a route showing fares without
its notices, can be written either way and should be written once the decision is
made. It is the route audit's items [20] and [21], and it is written out in plain
words, with what each answer changes, under "What is waiting on a person" in
`docs/open-work.md`.

## The browser suite's coverage, measured

Re-measured 12 October 2026 on the five pages the suite drives: **830 checks
passed of 855, none failed, 25 skipped (2.9%), exit 0** -- demo station 257/257
(3 skipped), chooser 71/71 (1), privacy 31/31, one-page station 254/254 (5),
prices-only 217/217 (16), which is where the 830 and the 25 come from. The
skipped checks are the journey and day checks a build with no timetable cannot
run. This audit had recorded 69 of 815 (8.5%,
over the suite's own 5% budget) on the previous fixtures; that was a property of
the fixtures rather than of the suite, because the shape feed priced each
secondary origin to a single station and neither fixture build carried a service
date. `tools/verify.py` now builds both fixtures for `SERVICE_DATE` and passes
`--third-origin --return-network`, and the shape route is `one-page`, because
what fits on one page is a list rather than a row.
