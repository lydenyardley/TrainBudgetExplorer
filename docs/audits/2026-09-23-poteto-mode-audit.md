# Poteto-mode audit — 23 September 2026

Scope: the whole repository as it stands after commit `4e4991f` — performance,
code quality, structure. 232 Python tests and the browser suite pass at the
time of the audit; the findings below are what a fresh reading and a live
trace found anyway. **No code was changed for this report.** Findings are
numbered for reference; each names the evidence and the principle that shapes
the recommendation.

---

## A. Correctness (fix before the real feed arrives)

**A1. Single-origin builds embed the wrong picker slugs.**
*Evidence:* `main()` in `build_demo_page.py` builds the picker's `stations`
list inline and calls `station_slug(location.name, crs, set())` — the empty
`taken` set means every station's slug is computed *independently*. Slugs are
deduplicated by adding distinguishing suffixes when two stations share a name,
so the `set()` form can only ever produce collisions-free slugs for a *single*
station, not a consistent set. In `--all-origins` builds the slugs come from
`build_station_index`, which passes the shared `taken` set — so the two modes
can disagree. Concretely: with two stations both named "Ashford" (ASH, AFS-style
suffixes in the real feed), the all-origins build writes `ashford/` and
`ashford-2/` (first-claimed wins by station-count order), while a single-origin
build's picker links one of them to `ashford-2/` with no guarantee that is the
folder the other build created. The link 404s.
*Impact:* broken picker links on the real network wherever station names
collide — and UK names collide constantly (Ashford ×2, Newport ×2, Rainford/
Rainhill-class near-names). The synthetic feed never trips it, which is why
tests pass.
*Fix:* one slug authority. Compute the index once (even for single-origin
builds) or share the `taken` set through a helper; `principle-encode-lessons-
in-structure`: the rule "slugs are consistent across a build" should be
unrepresentable to violate, not remembered in two places.

**A2. `_build_page_job` silently substitutes the wrong timetable for worker
builds when `--timetable` is omitted.**
*Evidence:* `_build_page_job` fetches the timetable with
`job.get("timetable", _WORKER.get("timetable"))`. In single-process mode the
parent stuffs `job["fares"] = fares; job["timetable"] = timetable` into every
job. In worker mode jobs carry *no* `timetable` key, so `job.get` falls to
`_WORKER["timetable"]` — correct. But nothing forces the two shapes to stay
aligned: a future edit that stops injecting `fares` in-process would also
silently switch to `job.get("fares") or _WORKER[...]` (already written that
way), where a falsy database would fall through to a worker that never got an
initializer run (`_WORKER` empty → `KeyError: 'fares'` with no explanation).
The dual-shape job dict is exactly the "state to hold in the reader's head"
that `principle-minimize-reader-load` bans.
*Fix:* one job shape. Jobs always carry config only; the caller builds pages
through the same worker function with a `_WORKER` populated by either an
initializer (pool) or a direct call (in-process).

**A3. `price_source_from_metadata` accepts a metadata file missing either key
and the build publishes with no provenance.**
*Evidence:* `read_feed_metadata` returns the first *parseable* dict; if
`metadata.json` exists but holds only `{"source": "RSP fares feed"}` (no
`downloaded`), `price_source_from_metadata` returns `None`, `main()` falls back
to `DEFAULT_PRICE_SOURCE`, and a **real-data page ships saying "the synthetic
demo feed"** — the false-attribution failure the feature was built to prevent,
arriving through the half-filled-in metadata case.
*Impact:* provenance lies silently in the exact scenario (operator fills the
template partially) most likely to occur.
*Fix:* if any `metadata.json` exists, its content is authoritative: fail the
build (or warn loudly and require `--price-source`) rather than falling back.
`principle-boundary-discipline`: parse the boundary, don't half-trust it.

---

## B. Performance (measured, not speculative)

**B1. The remaining journey-search cost is the per-candidate linear walk, and
the honest ceiling is a rewrite.**
*Evidence:* profile at 2,500 stations after the committed fixes:
`_one_change_journey` tottime ~5.9 s of one origin's ~9.5 minutes; candidate
triple count scales with stations × schedules and each candidate walks its
remaining stops. ADR-0024 accepts this. Nothing here contradicts that
decision — but the accepted-cost has no *tripwire*. The README says "time one
origin before committing to the full set," which is manual.
*Recommendation:* encode the tripwire (ADR-0024 already calls for this): a
`--max-origin-seconds` flag, or a check in `benchmark.py`'s test suite that
fails if the measured per-origin time at a fixed shape exceeds the recorded
bound. `principle-encode-lessons-in-structure`.

**B2. `destinations_within` scans every flow in the database per call, per
origin.**
*Evidence:* `atoc_fares.py` line ~460: `for flow in self.flows.values(): if
flow.origin_nlc not in origin_nlcs`. Called 2,500 times per full build (once
per origin, plus twice for the single/pair query) against ~1M+ flows. An
`origin_nlc → flows` index built once at load time makes each call
O(origin's flows) instead of O(all flows). This is likely a linear-to-flat
improvement on the whole build, independent of the timetable cost ADR-0024
accepts — the fares side has no excuse to be superquadratic.
*Recommendation:* build the index in `load_feed`. Measure before and after
with `benchmark.py --stations 400` (the shape where the timetable cost doesn't
drown it).
*This is the single highest-leverage change in the report.*

**B3. The privacy page and chooser are re-rendered per build for zero reason.**
*Evidence:* negligible cost today; listed only to record that the
`--workers` pool serialises the index through each job's `others` list — at
2,500 stations that is ~2,500 × 2,500 ≈ 6M dict entries pickled across the
process boundary in total (the earlier `TimetableDb` pickling lesson, in
miniature). `chunksize=1` makes it worse.
*Recommendation:* pass workers the index once via the initializer (or a
shared memory / temp-file path), and raise `chunksize` to ~8 — at network
scale the pickle traffic is real minutes. Measure with the existing bench
shape before/after.

**B4. `run.py` uses single-threaded `TCPServer`.**
*Evidence:* fine for one reader; but a page with an un-cached sub-resource or
two browser tabs stalls silently. One-word fix (`ThreadingTCPServer`) with no
behavioral downside for a local preview tool.

---

## C. Code quality and structure

**C1. `build_demo_page.py` is a 1,477-line module doing five jobs.**
*Evidence:* it contains the feed-metadata boundary (lines 86–124), the notice
wordings, the worker/executor plumbing, ~520 lines of embedded HTML/CSS/JS
templates (519–1067, 1135–1239), payload assembly, and the CLI. Every new
feature (provenance, base-path, notices, workers) grew *this file*.
*Recommendation:* two splits, no more (Laziness Protocol — not a package,
not layers): templates out (`page_templates.py`, pure strings), and the
worker/job plumbing out (`build_workers.py`) — leaving the module as CLI +
payload + render. Reader load drops because the question "where does the page
come from?" then has a one-file answer.

**C2. The templates are filled by `str.replace("__DATA__", …)` with JS
holding the render logic — the largest untested surface in the repo.**
*Evidence:* `render_page` swaps a token into `TEMPLATE`; the browser JS
(parsing, filtering, keyboard, copy) has ~120 lines with no unit tests; the
`browser_test.cjs` suite (38 checks) is the only cover, and it runs only when
someone remembers to run it. The Notice presets, provenance, and prices-only
column-drop are all exercised *through it* — the A3 class of bugs (page claims
something wrong) lives here and only surfaces in a browser.
*Recommendation:* add the browser suite to the deploy workflow (it already
runs tests; `browser_test.cjs` needs Node, which the ubuntu runner has) so the
claims the page makes are checked on every push, not on demand.

**C3. Six CLI tools independently re-implement "load the feed, then…"
plumbing.**
*Evidence:* `grantham_sweep.py`, `sanity_report.py`, `feed_audit.py`,
`benchmark.py`, `fuzz_feed.py`, `damage_feed.py` each own argument parsing for
`--feed/--timetable/--origin` and their own load-and-check preamble. This is
the "repeated shape assumption across files" `principle-model-the-domain`
names.
*Recommendation:* one `feeds_cli.py` with a shared `add_feed_args(parser)`
and a `load_pair(args)` helper — a consolidation, not an abstraction; do it
the next time a seventh tool appears, not before.

**C4. `easy_fares_check.py` writes credentials' *responses* (with journey
data, harmless) into `_ef_cache/` but its README says credentials come from
environment only — the cache path is committed nowhere and git-ignored,
correct; the gap is that the cache has no expiry, so a "reality check" run
tomorrow silently reports last week's prices as current.**
*Recommendation:* embed the fetch date in the cache filename (it already has
the route) or print the cache age in the report line. Small, and it protects
the honesty of the finding the page now quotes.

---

## D. Product/structure notes (no code)

**D1.** The launcher (`run.py`) defaults to rebuilding every start. Once the
real feed lands, that default becomes "wait minutes before seeing anything"
(ADR-0024's per-origin cost applies to the *demo* feed only in miniature —
but `--all-origins` through `run.py` would rebuild hours on start). The
`--no-build` escape exists; consider making `run.py` refuse `--all-origins`
without an explicit `--i-know-this-is-slow`, or simply print the ADR-0024
warning and require a flag.

**D2.** `docs/` now exists (this report). The README's tool table is the
index of scripts; as the tool count grows, the docs/ folder should own the
"how do I run/verify/release" prose and README should shrink to the quick
start — otherwise README follows `build_demo_page.py`'s growth path.

**D3.** Test count is 232 across 14 files with no coverage report. The
untested surfaces this audit found (A1's slug path from *outside*
`build_station_index`, A3's partial-metadata branch) are both reachable by
cheap unit tests — worth adding alongside the fixes.

---

## Priority order

1. **B2** — the flows index; highest leverage, low risk, measurable.
2. **A1, A3** — correctness of what the page claims and links; both cheap.
3. **C2** — browser suite in CI; converts the page's honesty claims into
   regression-checked ones.
4. **A2, B3, B4, C1, C3** — quality batch.
5. **D1–D3, C4** — when convenient.

*Method: read the actual source (build_demo_page.py, atoc_fares.py,
atoc_timetable.py, run.py, easy_fares_check.py), traced the two build modes
end to end, ran the full suite (232 OK), cross-checked the slug and
metadata paths against ADR-0019/0024's decisions. Principles applied:
Laziness Protocol, Minimize Reader Load, Model the Domain, Boundary
Discipline, Encode Lessons in Structure, Prove It Works — leaf SKILL.md
files read this session.*
