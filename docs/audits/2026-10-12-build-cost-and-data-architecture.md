# Build cost and data architecture: what is still open

**Date:** 12 October 2026
**Commit reviewed:** `e56a071` on `main`
**Scope:** the whole build path (`run.py`, `build_stations.py`,
`build_demo_page.py`, `build_workers.py`, `page_templates.py`,
`atoc_timetable.py`, `atoc_fares.py`), the release workflow's build step, and the
freshness path from download to publish.
**Method:** read-only, on the licensed feeds in `feeds/` (419,589 schedules,
3,436 priced stations) and on a 24-page real-feed build of this tree, so the page
and per-origin figures are real-feed figures rather than synthetic ones.
**Pruned:** 14 October 2026. The twelve tasks this audit set landed, and each is
held by an artifact and by a command a reviewer can re-run; that table is now in
`docs/open-work.md` under "The 12 October 2026 build-cost audit". Its figures,
including the per-origin distribution and the byte measurements, are in
`docs/build-performance-findings.md`. What is below is the whole of what it still
asks for.

## Still open

- **A whole-network release is over its byte budget, and the pair rules are why.**
  `docs/open-work.md` holds the entry, the measurements and the three ways it
  would close. Short version: `railcardRules` is the largest block on a real page
  (1.05 MB of Birmingham New Street's 1.63 MB), it grows combinatorially with the
  permitted two-ticket splits, and the release projects to roughly 2.2 GB against
  the 800 MB budget, with the error bars named.
- **The real release's byte total** is still a projection until a whole-network
  build in the release's own shape runs the gate. That is the first of the three
  ways the finding above closes.
- **A sharded release build.** T4 landed the shards and the merge; nothing yet
  shards the deploy workflow's own build, which is where its timeout is spent.

## Decided against, and why

Kept for the same reason the 8 October 2026 audit keeps its rejections: they are
what a later reader would otherwise re-derive.

- **The national single-pass search (T2 as written).** One national day index per
day of the week, held for the whole build, is the shape the 8 October 2026 work
removed. It was not built, because the per-origin facts layer delivers the same
payoff without holding the network, and because sharding (T4) is what would make
such a pass affordable rather than a reason to build one.
- **A database, or any store.** No store was prototyped, and the recommendation
against one is reasoning rather than measurement: a store removes the page write,
which measures 1.5 ms for a page as built and 10.9 ms for the largest page this
audit saw -- 0.014% to 0.10% of the 10.75 s a page takes to compute (measured
14 October 2026, `docs/build-performance-findings.md`) -- and none of the work
itself, because the facts still have to be computed somewhere. The reasoning and
the public record it was weighed against are in ADR-0019's 14 October 2026
amendment.

## Not measured, and why

The published build itself: the 130-minute figure is quoted from the workflow's
own comment, and this audit did not run a whole-network build. The real release's
byte total was measured in a 34-page sample of the release's own shape, which
projects to ~2.2 GB with wide error bars. The fares half of a page was not loaded
into these measurements; `docs/build-performance-findings.md` measures a
prices-only page at 0.39 to 0.47 s, which is the part that is not the timetable.
