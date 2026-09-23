# ADR-0024: The full-network build is a batch, and prices-only is the fresh tier

**Status:** Accepted
**Date:** 23 September 2026
**Relates to:** ADR-0019 (one page per station — this sizes its `--all-origins`
mode), ADR-0005 (data access), ADR-0009 (onward departure cap), the README's
measured-scale note (the numbers this decision formalises)

## Context

ADR-0019 chose one page per station; nothing had measured what that costs at
network scale. A benchmark against an invented feed shaped like the real
network (2,500 stations, 9,000 schedules) produced three findings:

1. **Journey search dominates, and grows superquadratically.** One origin's
   payload costs ~9 s at 400 stations and **over 9.5 minutes at 2,500** —
   roughly 6× per doubling of network size. A full 2,500-origin build is a
   batch job of hours even across 8 workers, not a refresh.
2. **The cost is almost entirely the timetable.** A prices-only build (no
   `--timetable`) is effectively free at any scale — seconds for the whole
   network.
3. **The reader-facing side is fine.** The chooser with all 2,500 stations
   embedded renders in 0.01 s (207 KB) and filters in ~2 ms; the per-station
   pages are unchanged in shape.

Profiling traced the search's cost to three compounding factors, two of which
were fixed outright (per-schedule CRS resolution, bisected destination lookup,
a precomputed connection-minutes map — together ~2.4×; a `DEFAULT_CONNECTION_
MINUTES` constant that a refactor had silently dropped from the module was
restored before it could ever fire). What remains is the irreducible inner
loop of `_one_change_journey`: candidate one-change journeys grow with
stations × schedules, and each candidate walks its remaining stops. Shrinking
the cap (ADR-0009) helps linearly; eliminating the loop means a different
search algorithm (indexed reachability or a precomputed transfer graph), which
is a rewrite of the module's core, not a patch.

## Decision

1. **The full build is a scheduled batch, run overnight.** `--all-origins
   --workers 8` is the production path; a full-network rebuild happens on a
   schedule (weekly at first, since the RSP fares feed updates weekly), not on
   demand. The README already instructs timing one origin (`--origin GRA`)
   before committing to the full set; that gate stays.
2. **Prices-only pages are the fresh tier.** Because they are free at scale,
   any fares-data change can be re-published as prices-only pages the same day
   (the columns-drop behaviour for a timetable-less build is already built and
   tested). They carry the provenance line saying exactly what they are — the
   page's honesty machinery makes a degraded tier legible instead of a lie.
3. **Incremental per-origin rebuilds are rejected.** A timetable change
   touches every origin at once (services are network-wide), so increments
   would only help for fares-only deltas — which decision 2 already covers
   more simply. Incremental builds would also make provenance heterogeneous:
   pages from the same site dated differently, with no honest sentence to
   explain it. Not worth it.
4. **The remaining search cost is accepted, not rewritten,** until the real
   feed proves otherwise. The superquadratic curve is measured on an invented
   shape; the real network's schedule distribution may be kinder. If the
   overnight batch becomes unacceptable, the fix is an indexed search rewrite
   — a new ADR, not a tweak here.

## Re-measured after the flows index (23 September 2026)

The audit's finding B2 (every flow scanned per origin) was fixed with an
origin-NLC flow index. Re-measured on the same 2,500-station shape:

| measurement | before | after |
|---|---|---|
| all 2,500 origins, fares only | 2.07 s | **0.06 s** |
| one origin, prices only | ~free | 0.03 s |
| one origin, with journeys | >9.5 min | **543 s (~9.1 min)** |

The fares side of the build is now free, as predicted — and the journey search
is confirmed as the entire remaining cost, untouched by the index. The honest
arithmetic for the full network is therefore **2,500 × 9.1 min ÷ 8 workers ≈
2 days**, not "hours": the uniform synthetic shape gives every origin ~2,500
priced destinations and no fast paths, which is close to the worst case a real
network could present. Decisions 1–4 stand; what changes is the emphasis:

5. **Prices-only is the launch tier, not merely the fresh tier.** At 0.03 s
   per origin the whole network republishes in under two minutes, so the
   first publication should ship prices-only and add the overnight timetable
   batch when it has run once on the real feed. The three optimisations
   already in (index, bisect, connection map) are the cheap ones; the
   remaining 9 minutes are the algorithmic rewrite decision 4 defers.
- **One origin ≈ minutes** becomes the planning unit: 2,500 origins ÷ 8
  workers × minutes each ≈ hours; budget accordingly and never promise a
  same-day timetable refresh.
- The invented-feed benchmark stays the instrument: rerun it whenever the
  search changes, and treat any superquadratic worsening as a stop signal.
