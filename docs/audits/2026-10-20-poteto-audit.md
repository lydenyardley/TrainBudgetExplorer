# Poteto-mode audit: the app in ten dimensions

**Date:** 20 October 2026
**Reviewed:** `f042fbb` plus the worktree's uncommitted 19 October critique work
and its twelve-shard workflow change. Nothing in this pass was built from the
licensed feeds.
**Mode:** read-only. No source file, template, stylesheet or test was changed by
this audit. One command was run to rebuild and re-drive the demo and shape pages,
and one measurement walked the CIF already in `feeds/timetable-nwr`.
**Method:** file inventory and churn from `git log`, targeted reads, the
repository's own recorded figures where they are dated, and the measurements
taken for this pass and marked as such. Every claim below carries `measured`,
`recorded` (a figure the repository states with its date) or `inferred`, in the
sentence that makes it.
**Artifact:** `_demo_site`, `_shape_site/one-page/from/nottingham` and
`_shape_site/prices-only/from/grantham`, built 20 October 2026, driven at 390,
320 and 1366 CSS pixels through `tests/browser_test.cjs`.

## The numbers this reading was taken from

| Thing | Size | How it was counted |
|---|---|---|
| Application Python, top level | 32 files, 22,317 lines | `measured`, largest is `atoc_fare_declarations.py` at 2,631 |
| The page's script | 19 files, 3,984 lines | `measured`, `page/**/*.js`, the station route is 17 of them |
| The page's stylesheets | 4 files, 1,035 lines | `measured` |
| Unit tests | 35 modules, 912 test methods, 17,677 lines | `measured`, so test code is 0.79x the application's |
| Browser checks | 429 `check(` sites producing 1,011 checks over 5 pages in 47.2 s | `measured` today, `python -m tools.verify --browser`, exit 0 |
| Operator tools | 45 files, 11,376 lines | `measured` |
| Decisions | 73 ADRs, 7,838 lines | `measured` |
| Reviews | 4 files in `docs/audits`, 4,847 lines of `docs/**` | `measured` |
| Fast loop | 1,137 tests in 21 minutes, 15 October 2026 | `recorded`, re-measured in `docs/build-performance-findings.md` after three earlier claims were wrong |
| Full loop | every unit test, the type check, the JavaScript parsed, 35 minutes | `recorded`, same source |
| Site budget | 800 MB against GitHub's 1 GB | `recorded`, `tools/page_bytes.SITE_BUDGET_MB` |
| The over-budget release | 2,444 MB | `recorded`, ADR-0069, run 38353105980, before that ADR's fix |
| Shard 1 after ADR-0069 | 90.8 MB for 458 pages, about 536 MB for the network | `recorded`, ADR-0069; an extrapolation from one shard |
| The release's timetable | 488,796 passenger schedules, 7,373,060 calling points in 99,816,417 bytes | `measured` today, counted through the loader's own filter |

## The ten dimensions, and what each one says

| Dimension | Verdict | Where it is answered |
|---|---|---|
| Product and scope | The question is the product and the page answers it. The release's byte figure is stale in one document and projected in the other | A2 |
| Release pipeline | It cannot finish inside its own bound, and the replacement bound is arithmetic | A1 |
| Build architecture | Seven build modules, one constant for the opening budget, no duplicated helpers found | Working, A8 |
| Page architecture | State and render are separated and `render()` reads the state, but the route's script is never parsed as one artifact | A4, A6 |
| Front-end layout | Two-line rows at desktop widths, one viewport measured 16 px wider than a real browser at the same width | A3 |
| Accessibility | Both palettes, three widths, computed contrast, and `not exercised` instead of false passes | Working |
| Testing | 1,011 browser checks that caught five real defects in one afternoon, and 912 unit tests of which 104 observe source text | A6 |
| Developer loop | 21 minutes for the fast command, which is not a loop a change can be checked with | A5 |
| CI and operability | Twelve shares, credentials per feed, a clearance gate that refuses a public build | A1, A7, A8 |
| Documentation and decision trail | 73 ADRs and a settled record with an enforcer per row | Working |

## Findings

Severity: P1 breaks a release or a reader now, P2 costs real work or hides a
defect, P3 is polish with a named check behind it.

### A1 [P1] The release pipeline cannot finish inside its own bound, and the bound's replacement is arithmetic

Five of the six shard jobs reported `the action 'Build the site from audited
fares and the publishable timetable' has timed out after 150 minutes` on
20 October 2026, in a matrix that runs six shares of the whole network. That is
`measured` in the sense that the failure is the run's own message. There is no
per-share figure for it, so nobody knows whether a share was 151 minutes or 300.

The bound was set from run 38353105980 on 13 October 2026, where six shares of
about 450 pages took 114, 111, 106, 87, 95 and 103 minutes (`recorded`, in the
workflow's comment). Thirty-six minutes of headroom is now spent. The worktree
already answers with twelve shares of about 226 pages and the same bound, and
the reasoning is stated in `docs/build-performance-findings.md` as the day's
entry. That is `inferred` arithmetic, not a measurement. Halving the page count
halves the part of a share that scales, and every share still loads the whole
fares feed and the whole national timetable for itself.

What is ruled out, by a measurement taken today. The suspicion that the switch
to Network Rail's whole CIF (ADR-0073) made the index much bigger is false. The
CIF holds 488,796 passenger schedules and 7,373,060 calling points after the
loader's own filter, against the DTD feed's 419,589 schedules and 7,700,987
calling points. That is 17% more schedules and 4% fewer calling points, so the
new source is not a doubling of what a worker holds.

What the twelve shares do not establish. Which part of a share the extra minutes
went to. A per-page regression between 13 and 20 October would look exactly like
this, and the repository's own instrument for it exists and was not run:
`python -m tools.measure_origin_costs` times the slice cut, the day index and
the search per origin on the real feed. The one figure the twelve-share run
should produce is a per-share wall clock, and its place is the day's entry in
`docs/build-performance-findings.md`.

Nothing holds it today. The workflow comment states the rule ("a share that nears
it is the signal to split further rather than to raise it") and nothing compares
the run's shares against it.

### A2 [P2] The byte budget's open P1 is superseded, and its replacement is an extrapolation

`docs/open-work.md` opens with a P1: a whole-network release projects to about
**2.2 GB** against the **800 MB** budget, from a 24-station sample measured on
12 October 2026. ADR-0069, accepted on 13 October 2026, changed the payload's
encoding and measured the result on the same shard: **90.8 MB for 458 real
pages**, in place of 429 MB, which is **about 536 MB** for 2,707 pages. The
open P1 does not mention the ADR, and the ADR does not close the P1.

Neither figure is a whole-network build. 536 MB is an extrapolation from one
shard, and it predates the 16 October switch to Network Rail's CIF, which added
schedules and therefore possible departures to every row. The gate exists and
runs in CI (`tools/page_bytes.py --site _site`), so the release cannot publish
over budget; what no check does is notice that the document describing the
budget contradicts the decision that fixed it. `measured` in both directions,
`inferred` on the release's actual size.

This matters less for the release than for the next reader. `docs/open-work.md`
is the file that says what is open, and an owner reading it would reasonably
re-open a decision ADR-0069 already made. The measurement that settles it is the
next release run, which prints the assembled site's bytes whether it passes or
refuses; until then the honest line is that the release is probably inside its
budget and nobody has proved it.

The check that would hold this is not a new one: `tools/page_bytes.py` already
fails on an overage. What it has no opinion about is the sentence in
`docs/open-work.md`, and nothing in the tree compares that file against the ADRs
it outlived.

### A3 [P2] The phone layout is proven in a viewport with no scrollbar

`tests/browser/station-layout.cjs` drives a Playwright viewport of 390 by 844 and
320 by 640 CSS pixels. Playwright's Chromium lays that out with no scrollbar, so
the results table is 366 px wide. A real Chromium window at the same 390 px
renders `document.documentElement.clientWidth` of 374, a row of 350 px, and the
absence text over four lines. `measured` both ways today, on the same page and
the same build.

| Where it was measured | Row width | Time cell | Row height |
|---|---|---|---|
| Playwright viewport, 390 | 366 px | 72 px | 112 px |
| Registered preview, 390, real scrollbar | 350 px | 55 px | 160 px |

Why it costs something. The audits name the 320 px case as the 200% zoom case,
and zoom happens in a desktop window, which has a scrollbar. So one of the two
widths the suite claims to model is a desktop browser measured as if it were a
phone, and on this page the difference is a two-line row becoming a four-line
one. A phone with overlay scrollbars really is 390 px wide, so the demo case is
sound and the zoom case is not.

What to do. Give the layout module a viewport whose content width is asserted
(take 375 for a 390 phone, 304 for 320, and read `clientWidth` back), and hold
the row to three lines at both. The suite's own `notExercised` idiom covers a
page that cannot reach a row.

The row-height check holds it today, and it passes at a width a zoomed desktop
browser does not offer.

### A4 [P2] The page's script is never parsed as the artifact it ships

The station route is one `<script src>` built from 19 files concatenated in the
order `page_templates.py` names. `tools/verify.py` runs `node --check` once per
file (`files = sorted(Path(ROOT).glob(JAVASCRIPT))`, `measured`). Nothing parses
the concatenation, so a duplicate top-level declaration is legal per file,
silently shadows the earlier one in the artifact, and stays invisible until a
reader meets it. One duplicate exists today. `function render` is declared in
`page/chooser.js` and in `page/station/table.js` (`measured`). Different routes
mean it is harmless now. Nothing says it must stay that way, and the route split
is a decision, not a fence.

What to do. Build each route's script from the same list the page builds it
from, and `node --check` that string. One check, in the step that already exists,
and it fails naming the file that clashed.

Only per-file syntax is checked today.

### A5 [P2] The fast loop is twenty-one minutes

`python -m tools.verify --fast` is 1,137 tests in 21 minutes, re-measured on
15 October 2026 (`recorded`, `AGENTS.md` carries the figure and its date, and the
"three minutes" it replaced was wrong by four). A loop that long is not a loop a
change like this session's can be checked with while it is being written. Today's
work was checked with `python -m unittest tests.test_build_chooser
tests.test_build_fares` at 11 s and four page modules at 69 s (`measured`), which
is the shape the fast command should have.

What to do. Make `--fast` the page, payload and chooser modules, with a stated
ceiling of five minutes, and leave the feed-scale modules to `--full`. The
work that lands in this repository is overwhelmingly page work, and the fast
command should be the one that proves it.

The figure is held by a document, and no check reads it.

### A6 [P2] A hundred unit assertions read the page's script source instead of its behaviour

104 of the 131 uses of `page_script(...)` sit inside an assertion about the
script's text (`measured`). `self.assertIn("one ticket to the station above",
page_script(self.html))` passes when the sentence is in a function that never
runs, and fails when the sentence moves to a template. The browser suite holds
the rendered form of the same copy, so the pins duplicate a proof that is
strictly better.

Not all of them are the same. `assertNotIn("aliases", ...)` is a decision
("the page does not search aliases") and cannot be observed another way. A copy
sentence can.

What to do. Keep the pins that hold a decision, delete the ones that restate copy
the browser suite already proves, and where a unit test must hold copy, assert on
the rendered body of a built fixture page rather than on the script's source.

Nothing holds it, and `tests/test_suppressions.py` has no bearing on it.

### A7 [P3] The browser dependency is pinned in CI and floating everywhere else

CI pins `PLAYWRIGHT_VERSION: 1.63.0` and installs it with `npm install --no-save`
(`measured`). `tests/browser_test.cjs` documents `npx --yes --package playwright
node browser_test.cjs` for local runs, which takes whatever is current
(`measured`), and no `package.json` or lockfile is tracked at all (`measured`).
A green run locally is therefore not the same command as a green run in CI, and
`--no-save` leaves the transitive tree unpinned even in CI.

What to do. One file names the version, both paths read it, and
`tests/test_workflows.py` fails when the two disagree. It is the same shape as
the commit-message check.

### A8 [P3] The build's bound is justified by a table no check reads

The shard step's 150 minutes is defended in a comment by a table of measured
share times, and `docs/open-work.md` already carries the note that
`docs/build-performance-findings.md` "is a rule with no enforcer". `recorded`,
by the repository's own open work. Today's failure is what that costs, because a
bound drifting away from its measurement is exactly what happened.

What to do. One check compares the workflow's `timeout-minutes` and shard count
against a stated table in the performance document, and fails naming both
numbers when they disagree. The document stays the record. The check makes it a
rule.

## What is working, and should not be traded away

- **The rule table in `AGENTS.md` names an enforcer for every rule, and says
  what fails.** Twelve rows, each with the command and the message (`measured`,
  the file). Reviews that cannot name an enforcer are moved to open work instead,
  which is what keeps the table honest.
- **Reviews are pruned to what they still ask for.** The 19 October critique
  keeps one open finding and its closed ones are rows in
  `docs/settled-work.md` with the check that holds each (`measured`, this
  session's edit). A review with nothing open is deleted.
- **The browser suite is the strongest part of the tree.** 1,011 checks over
  five pages in 48 s, with a per-shape skip budget so a page that cannot exercise
  a check reports `not exercised` rather than passing (`measured`). In this
  session it caught five real defects in one afternoon's diff, including two the
  author had already reasoned past.
- **The release is driven in a browser, not just inspected.** The assemble job
  drives the real `_site` through `--sweep --max 24`, with a named spread rather
  than a prefix, and refuses to run when the site wrote no page (`measured`, the
  workflow's own steps). A static byte gate plus a real browser on the shipped
  artifact is more than most static sites do.
- **Cost claims are dated and reproduced.** Every figure in
  `docs/build-performance-findings.md` carries a date, a method and a
  reproduction command, and the file records the figures that were withdrawn
  (`measured`). The 150-minute bound was set from one, which is why A1 is a
  drift rather than a guess.
- **Accessibility is measured rather than asserted.** The matrix drives both
  palettes at desktop, phone and 200% zoom, with contrast computed over the
  composited background (`measured`, `tests/browser/a11y-matrix.cjs`).
- **The domain is modelled, not branched.** `atoc_fare_declarations.py` holds
  the record layouts and the reviewed tables, the loader mixes in the readers,
  and the build is seven modules with one place that names them (`measured`).
  The 19 October finding this session fixed was a fact copied per fare list, and
  the fix was to give the fact one owner (ADR-0069's principle, applied to
  departures).
- **Memory is a measured budget, not a guess.** `build_workers` divides free
  memory by a measured 2.2 GB per worker and caps at the largest count measured
  to finish, with the figures and the two wrong ones it replaced in the file
  (`measured`).
- **Boundaries are guarded where they are crossed.** Three independent search
  passes over the tree looked for the usual leaks and found none: every
  `localStorage` read and write is wrapped (the theme's and the railcard's, each
  with a comment saying what happens when storage is blocked), no `assert`
  survives in application code, and the opening budget is one constant read by
  the shards and the merge rather than five literals (`measured`, the three
  passes and `tests/test_page_runner.py`).
- **A rule that was written twice became a constant.** The opening budget was a
  literal in five places until E7 of the 17 October audit, and now a test
  refuses a numeric literal on that path (`recorded`, `docs/settled-work.md`).
  It is the repository's own example of the pattern the remaining findings
  recommend.

## Questions for the owner

1. Is `docs/open-work.md`'s byte P1 void against ADR-0069's 536 MB, and should
   it be closed rather than re-opened? A2, and only the next release run can
   replace the extrapolation with a figure.
2. What is the phone's fold budget, in numbers? S5 of the 19 October critique
   stands on this, and the laptop has a budget with a check while the phone has
   neither.
3. Is a release allowed to cost twelve runners times two hours? If not, the
   answer is less work per page, which the next run's per-share figure would
   have to support.

## Out of scope for this pass, and worth a separate one

- Which of the twelve-share minutes is the timetable, which is the fares slice,
  and which is the walk. `tools/measure_origin_costs` exists and settles it.
- Whether `build_payload.py` at 1,760 lines should split. It is the hottest
  module and the one every audit touches (`measured`, churn below), and it has
  no failing behaviour to justify the move today.
- Whether the pair-rule encoding can be halved. ADR-0069's own numbers say the
  railcard columns are 629 KB of a page, and the open work names it as the
  release's cost.

## Run notes

- **Churn since 21 September 2026** (`measured`, `git log --name-only`):
  `page_templates.py` 104 commits, `build_demo_page.py` 98, `atoc_fares.py` 38,
  `build_workers.py` 20, `make_synthetic_feed.py` and `atoc_timetable.py` 18
  each. The two most edited files are the template strings and the build's CLI,
  which is where the page's copy and its flags are proved.
- **App code hygiene** (`measured`): no `TODO`/`FIXME` in application code (one
  in `make_synthetic_feed.py`), no bare `except`, three `except Exception` and
  three `noqa` in `fuzz_feed.py` only, five `type: ignore` across the build.
- **The worktree this was read in** carries the 19 October critique work, the
  twelve-shard workflow change and its performance entry, all uncommitted.
  Nothing was committed or reverted for this audit.
- **Screenshots and probes** were taken through Playwright and the preview pane
  during this session and were working files, not part of this record. The
  screenshot folder is not tracked and has been removed.
