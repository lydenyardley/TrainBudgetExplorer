# Non-dev route audit — the chooser, the station page, the privacy page

⚠️ DEGRADED: single-context (no sub-agent tool is exposed in this session, so
Assessments A and B ran sequentially in one context rather than as two isolated
sub-agents; the detector's output was therefore in context before the design
judgement was finalised. One judgement — the `.origin-slot-wrap` warning below —
was re-checked against the stylesheet for this reason.)

**Date:** 9 October 2026
**Commit reviewed:** `339abf7` on `main`, with the working tree's uncommitted
edits present: `README.md`, `retailer.py`, `adr/ADR-0017-…`, `adr/ADR-0066-…`,
`tools/check_slice_equivalence.py` and its test. None of them is a route template
or a page asset, so nothing in this audit is a reading of an in-flight edit.
**Routes audited:** the three routes a release serves, plus the one-station
variant of the root.
**Not audited:** the dev-only builds (`_shape_site/one-row/`, `_demo_site/` as
fixtures in their own right). They exist to make the shipped shapes reachable and
are not published.
**No code was changed by the audit.** This file was the whole deliverable.
**Pruned 10 October 2026:** of the twenty-two numbered items this audit left,
twelve were implemented that day — 1, 2, 5, 7, 8, 9, 11, 12, 13, 14, 17 and 19 —
and are removed from this file. Their record is not restated here: each closure
is held by the commit that carries it, whose message names the item and a command
that reproduces its proof (`git log --grep="audit item"`), and the mapping of
groups to commits is in this file's own commit, `1ecd719`.
**Pruned again 11 October 2026:** seven more were implemented with the whole-app
pass — 3, 4, 6, 10, 16, 18 and 22 — and their record is in
`docs/audits/2026-10-10-four-dimension-app-audit.md`'s settled table. The three
still open keep the numbers they were given (15, 20 and 21), so a gap in the
sequence is deliberate. What is below is the whole of what this audit asks for:
the heuristic tables, strengths and persona notes were the pass's judgement of the
9 October state and are not carried with it.

## The non-dev routes

A release is the set of routes its manifest names (`adr/ADR-0034`), and the
build writes exactly three templates:

| Route | Template | What it is |
|---|---|---|
| `/` | `CHOOSER_TEMPLATE` | the root. A directory of every station this build priced, with one search field in the heading. When the build priced exactly one station the same template states that station instead of asking for it (the "release root"). |
| `/from/<slug>/` | `TEMPLATE` | the product: every destination inside the budget, as a table. |
| `/privacy/` | `_PRIVACY_TEMPLATE` | the notice, written from what the build ships. |

The station page is also the root of a one-station build by URL convention only;
a release always writes the chooser at `/` and the station under `from/`, so the
"release root" is a state of the chooser, not a fourth template.

## How this was produced

**Method.** Impeccable `critique`: one design review per route (specificity,
Nielsen heuristics, cognitive load, personas), plus the bundled detector over the
built HTML, then synthesis.

**Evidence, dated 9 October 2026.** Figures in the items below are from these
builds on this machine, read in headless Chromium (the Playwright already in
`node_modules`):

- `_site/` — the real-feed build in the working tree (prices-only station page,
  chooser, privacy).
- `_demo_site/` — the synthetic build the browser suite drives, with a timetable
  and three priced origins (`python build_demo_page.py --feed _demo_feed --timetable
  _demo_feed --knowledgebase _demo_kb --all-origins --out _demo_site/index.html`).
- `_shape_site/prices-only/` — a one-station build, made for this audit with
  `python make_synthetic_feed.py _shape_feed --unserved-station` then
  `python build_demo_page.py --feed _shape_feed --origin GRN --out
  _shape_site/prices-only/index.html`.

Viewports: 1440×900, 1366×768, 1280×800, 390×844; light and dark where the theme
matters. Text content, element geometry, computed styles, tab order and console
errors were read from the running pages. Build-cost figures are not repeated
here; `docs/build-performance-findings.md` owns those.

**One honesty note about the fixture.** `_site/` is a working-tree artefact whose
`stations.js` came from a full-network run while its manifest names one station.
Content read from it is valid; route-contract numbers read from it (2,703 picker
options, 2,704 chooser rows) describe the deploy's `--all-origins` shape rather
than a one-station release, and are labelled that way below.

**What was seen, and what was only measured.** The chooser was inspected as
pixels at 1440×900: dark, in the directory state, the completion state and the
no-match state; light, with the dropdown open under the field. The Preview
compositor then stopped producing frames partway through the session, so the
station page and the privacy page were assessed from their stylesheets, their
DOM, computed styles and measured geometry rather than from a screenshot.
Nothing below claims a visual judgement about those two routes that geometry and
the stylesheet cannot support.

**Detector result.** `impeccable detect --json` on each built route: one finding,
`cramped-padding` on `.origin-slot-wrap` (children flush against a
`border-bottom`), on the station page only. **False positive**: that border is
the dashed underline that is the station slot's entire affordance, chosen in
`page/shared.css` precisely because a text field's underline is the one shape a
reader already reads as "this part of the sentence is yours". The chooser and the
privacy page scanned clean.

## Route 1 — the chooser (`/`)

**What is still open.**

- None. Items [3], [4] and [6] were implemented on 11 October 2026 as part of the
  whole-app pass (`docs/audits/2026-10-10-four-dimension-app-audit.md`, R1–R3):
  the list opens on typing and is drawn over its own place rather than over the
  intro, the empty-field directory is a stated top 40 of the true count, and the
  entry route now carries the same provenance sentence the station pages do. The
  artifact for each is in that file's settled table. The one open item this audit
  shares with the whole-app one is [20]/[21] below.

## Route 2 — the station page (`/from/<slug>/`)

**What is still open.**

- None. Items [10] and [22] were implemented on 11 October 2026 with R4: one
  matcher and one cap now serve both station fields, and the picker states the
  cap in the same sentence the chooser uses, beside `#originPicks`. The artifact
  is in the whole-app audit's settled table.

## Route 3 — the privacy page (`/privacy/`)

**What is still open.**

- **[15] [P1] Decide the contact before anything publishes.** The build names the
  public issue tracker (`DEFAULT_PRIVACY_CONTACT`, ADR-0068) and prints no email
  address, but nothing has confirmed that its notifications are read:
  `licences/release-clearance.md` holds the `privacy contact` product as
  `state: excluded` for exactly that reason, and `tools/check_release_clearance.py`
  refuses to clear a release that publishes until somebody confirms it. Clearing
  means recording the date it was confirmed and who confirmed it, or naming a
  different route. *(Command: none — this is a person's decision, and the gate
  holds it.)*
- **[16] [P2] No date on a page that makes dated claims.** **Closed 11 October
  2026** (whole-app audit R6): one line under the title dates the notice's
  build-dependent promises from `builtAt`.
- **[18] [P3] Put the summary before the deep dive.** **Closed 11 October 2026**
  (whole-app audit R6): "What this site does" now reads before "What stays in the
  address bar", and the "below" in the practices bullet points at the section that
  now really is below it.

## Cross-route

- **[20] [P2] Every route the release serves should carry the notices the build was
  given.** `--notices nre,rdg,ogl,accuracy` reaches `render_page` only: the built
  chooser and privacy pages contain no licence or attribution wording at all,
  while the station page carries NRE and the Open Government Licence. Two ways to
  close it: render the notices on every template, or record the decision that
  directory routes do not need one. **Open.** This is a person's decision about
  the licence terms, and the whole-app audit's one remaining item; it is written
  out in plain words there. *(Command: `$impeccable harden`, then
  `$impeccable audit` for the wording.)*
- **[21] [P2] Make that invariant a build check, not a template accident.** The link
  crawl already proves every internal link resolves; a sibling check can prove
  every route in the release manifest carries the notices the build passed, and
  name the route that does not. **Open, with [20].** Whichever way [20] is
  decided, this is the tool half of it. *(Command: none — a build/tooling change,
  `$impeccable harden` for the page half.)*
- **[22] [P2] Make "station search" mean one thing.** **Closed 11 October 2026**
  with [10] and the whole-app audit's R4: one matcher, one cap and one sentence
  about it serve both routes, and the browser suite holds the completion on
  each.

## Questions this audit leaves open

- Should the non-fare routes carry licence notices ([20]), or is the recorded
  position "the obligations travel with the pages that show the fares"? This is
  the one question this audit and the whole-app audit still share, and it is a
  person's decision rather than work.

## Run notes

- **Targets:** `_site/index.html`, `_site/from/grantham/index.html`,
  `_site/privacy/index.html`, `_demo_site/from/grantham/index.html`,
  `_shape_site/prices-only/index.html`, `_shape_site/prices-only/privacy/index.html`.
- **Assessment independence:** not achieved — no sub-agent tool in this session,
  so the design review and the detector evidence were produced in one context and
  interleaved rather than sequenced (banner above). The detector's single finding
  was re-checked against `page/shared.css` before being called a false positive —
  the check the sequencing rule exists to force.
- **CLI detector:** ran on all built routes; exit 2 on the two station pages (one
  `cramped-padding` warning), exit 0 on the chooser and privacy pages.
- **Browser evidence:** the native Preview compositor stopped producing frames
  after the first route; the fallback was headless Chromium through the
  repository's own Playwright (`node_modules/playwright`), reading geometry,
  computed styles, text, tab order and console errors, and driving typed input,
  row expansion, the filter panel, the shortlist and the picker. Console errors
  on every route: none.
- **Ignore list:** none (`.impeccable/critique/ignore.md` does not exist).
- **Snapshot:** not written — this run covers several targets and was delivered as
  this file instead of a per-slug snapshot.
- **Servers:** the three static servers used for the audit — `python -m
  http.server` on 8799 (`_site`), 8800 (`_demo_site`) and 8801 (`_shape_site`) —
  were stopped after the last measurement; a `curl` to each port returns 000, and
  the process ids recorded when they were started are gone.
