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
**Implemented since:** items 1, 2, 5, 7, 8, 9, 11, 12, 13, 14, 17 and 19 were
implemented on 10 October 2026 and are listed under "Closed since this audit" at
the end. The route sections below are the state as found on 9 October; the
collated list now holds only what is still open.
**Reference numbers.** Every task this audit leaves has one number, [1] to
[22]: the route sections print it beside their findings, and the collated list at
the end is the complete numbered set. A task can be asked for by number alone.

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
built HTML, then synthesis. Scores are out of the applicable maximum and say
which heuristics were scored `n/a`.

**Evidence, dated 9 October 2026.** Figures below are from these builds on this
machine, read in headless Chromium (the Playwright already in `node_modules`):

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
compositor then stopped producing frames
partway through the session, so the station page and the privacy page were
assessed from their stylesheets, their DOM, computed styles and measured
geometry rather than from a screenshot. Nothing below claims a visual judgement
about those two routes that geometry and the stylesheet cannot support.

**Detector result.** `impeccable detect --json` on each built route: one finding,
`cramped-padding` on `.origin-slot-wrap` (children flush against a
`border-bottom`), on the station page only. **False positive**: that border is the
dashed underline that is the station slot's entire affordance, chosen in
`page/shared.css` precisely because a text field's underline is the one shape a
reader already reads as "this part of the sentence is yours". The chooser and the
privacy page scanned clean.

## Route 1 — the chooser (`/`)

**Verdict.** The strongest visual idea on the site: the two gaps in the sentence
`Train fares up to £___ from ___` are the whole interface, and the ordering note
tells the truth about an order a competitor would hide. It is also the route where
the interface most often answers a question the reader did not ask. Measured on a
full-network build: **2,704 stations, 51,770px of page at 1440px and 153,923px at
390px** when the list is in the flow, or a **522px-tall fixed panel holding
153,537px of content** while the field is in use.

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | `#pickStatus` announces "N stations listed"; the ordering note is honest. But the list silently becomes one row when a completion lands, and the directory state gives no sense of position in 2,704 rows. |
| 2 | Match system / real world | 2 | Ranking by "851 destinations" is a feed metric, not a traveller's. 36 of 2,704 names are feed-internal (`LONDON INTL(CIV)`, `HEATHROW UNDERGD`, `XC ORIGIN`). |
| 3 | User control and freedom | 3 | Escape returns focus to the field, a click outside dismisses, the field clears. The completion still rewrites what the reader typed on every keystroke. |
| 4 | Consistency and standards | 2 | The same list is a fixed dropdown when the field is in use and a 51,770px in-flow directory when it is not, with no transition between the two. The middot separators retired on the station page survive here. |
| 5 | Error prevention | 1 | Typing "gran" completes to GRANGETOWN CRDIF (121 destinations) over GRANTHAM (50); Tab or Enter accepts it. Nothing disambiguates two real stations. |
| 6 | Recognition rather than recall | 2 | The reader must know a name or a code. There is no geography, no region, no recent station, and the directory is too long to browse. |
| 7 | Flexibility and efficiency | 2 | Arrow keys walk the list and Tab accepts the completion; there is no second path for a reader who does not know what to type. |
| 8 | Aesthetic and minimalist design | 2 | Type, spacing and contrast are excellent; a 153,923px phone page and an overlay that covers the page's own explanation are not minimal. |
| 9 | Error recovery | 3 | A no-match names the three-letter-code route and says what was searched. Nothing catches a near-miss, which is the failure mode this route actually has. |
| 10 | Help and documentation | 2 | The ordering sentence is the best help on the site; nothing explains what the completion is doing or what "destinations" counts. |
| **Total** | | **22/40** | **Acceptable — significant improvements needed before this route is doing its job** |

**Strengths.** (1) The heading-as-input is the product's own idea, not a template:
both editable gaps wear one treatment across routes (`page/shared.css`). (2) The
ordering note says what the order is *not*, which is rarer than saying what it is.
(3) The no-match copy quotes the reader back at themselves and names the code
route — the failure mode is handled in the page's own voice.

**Priority issues.**
**Closed since:** [1], [2], [5], [7], [8], [9] — implemented 10 October 2026
(see "Closed since this audit" at the end).
- **[1] [P1] The completion can land on the wrong station.** The field completes
  to the *first station in list order* whose name starts with the typed text
  (`page/chooser.js`, `complete()`), and list order is destination count. Typed
  one letter at a time, `grantham` produced: `g`→GWERSYLLT, `r`→GREENFAULDS,
  `a`→GRAVELLY HILL, `n`→GRANGETOWN CRDIF, `t`→GRANTHAM. The browser suite
  asserts this behaviour deliberately (`browser_test.cjs`, "typing … completes
  the station's name"), which is why the fix has to change the check with it.
- **[2] [P1] The dropdown shows one row, so the alternatives never appear.**
  Because the completion is written *into* the field and the list is filtered by
  the field's value, the dropdown shows exactly one row at every step: when the
  field reads GRANGETOWN CRDIF, GRANTHAM is not on screen to choose.
- **[3] [P1] The dropdown covers the page's own explanation on load.** The script
  focuses the field, so the list opens as a `position: fixed` panel from the
  field's bottom (y≈306) to y≈828 at 1440×900 — over the intro sentence and the
  ordering note. A test click on `main p.sub` was intercepted by
  `#picks.under-field`; on a phone the panel covers ~58vh from y≈110.
- **[4] [P2] One empty field is a 51,770px page (153,923px on a phone).** The state a
  reader lands in after dismissing the field renders every station at once. Both
  states are directories nobody can scan.
- **[5] [P2] Feed names leak into a reader-facing list.** A pattern over the
  chooser's own list matches **36 entries that read as feed-internal rather than as
  places**, among them `LONDON INTL(CIV)` (667 destinations), `HEATHROW UNDERGD`
  (539), `LIVERPOOL S PWAY`, `LIVERPOOL ARPRT`, `GLASGOW AIR XBUS`, `EFFINGHAM
  JN`, `WARRINGTON BK QY`, `MANCHESTER O RD`, and `XC ORIGIN` (QXO, one
  destination — the name a reader gets for typing "x"). The pattern is a proxy
  for the count; each name above was checked in the list itself.
- **[6] [P2] The route says nothing about what the site is, or how old its prices
  are.** On a real build `render_chooser` writes `<p class="tag">` with an empty
  note, so the entry route's only prose is "Type the station you are leaving from"
  and the ordering note; the licence line, the feed's name and its download date
  appear on the station page only.
- **[7] [P3] The middot separators still run on the chooser.** The station page
  retired its two `.heading-sep` middots for the "from" line by decision
  (`page/shared.css`); the chooser still renders them, and the second one ends the
  first line at display size.
- **[8] [P3] Empty note paragraphs ship anyway.** `render_chooser` and
  `render_privacy` write their note paragraph whatever the note is; a real build
  passes `""`, leaving an empty `<p class="tag">` (2rem of dead space) on the
  chooser and an empty `<p class="muted">` in the privacy footer. The synthetic
  banner already writes nothing instead.
- **[9] [P3] The 40-match cap message is nearly unreachable.** It fires only when
  the typed text is a substring no station name *starts* with ("x" → "XC
  ORIGIN"), because any prefix match completes and collapses the list to one row.

**Persona red flags.** *Jordan (first-timer):* the field is a grey word inside a
100px heading; nothing says "search". The first thing on screen is a list of
counts ("851 destinations") whose meaning is explained below the fold in the
overlay state. *Sam (keyboard/AT):* the field is focused on load, so a screen
reader's first announcement is a search box followed by a status of "2704
stations listed" — accurate, and impossible to act on. Arrow keys and Escape do
work. *Casey (phone, one-handed):* the completion is a 2rem-tall target above the
fold with the thumb zone empty; dismissing the overlay needs a tap outside a
522px panel.

**Cognitive load.** 2 of 8 checklist items fail (single focus is broken on load by
the overlay; minimal choices is broken by 2,704 visible options in the directory
state). Moderate. The decision points that matter are inside the field's own
behaviour rather than on screen.

## Route 2 — the station page (`/from/<slug>/`)

**Verdict.** This route has been through four measured passes and it shows: the
count line sits 8px above its table, the first fare is in the fold at every size
measured (y=718 at 1440×900, 682 at 1366×768, 664 at 1280×800, and 705 of a
844px-tall phone on the prices-only build), the table stacks into labelled rows below 44rem
rather than scrolling sideways, and the states that could lie (`prices-only`,
`unpriced`, stale feed, restricted fare, no timetable) all say so on the page.
The remaining findings are vocabulary and small print, not structure.

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 4 | Count line, live region, the filter toggle carrying the current narrowing, the freshness line, the dock's own count. |
| 2 | Match system / real world | 3 | "Cheapest first", "Direct", "Regular / Restricted / Advance". The shortlist column is still headed `LIST`. |
| 3 | User control and freedom | 4 | Clear types, clear shortlist, one change-station control, disclosures that close, browser Back intact. |
| 4 | Consistency and standards | 3 | One vocabulary for 95% of the page; the shortlist column is the exception, and the ticket-mix rule is stated three times. |
| 5 | Error prevention | 3 | The slider stops at the fare ceiling and says so; no journey is ever chosen; the ticket link cannot land on a broken search. |
| 6 | Recognition rather than recall | 3 | Everything is labelled; the fare's condition is one click in, which is the recorded trade-off rather than an oversight. |
| 7 | Flexibility and efficiency | 3 | Keyboard reach for every control, paging, shortlist copy/share, remembered railcard; no sorting or export. |
| 8 | Aesthetic and minimalist design | 3 | Dense by intent and honest; the footer is a long small-print stack and one rule is stated three times. |
| 9 | Error recovery | 3 | A missing timetable, an unpriced origin and a stale feed each get their own sentence in the page's voice. |
| 10 | Help and documentation | 4 | "Where these prices come from" and the link terms are the best help surface on the site: concrete, in the page, and read from the build. |
| **Total** | | **33/40** | **Good — solid foundation, address the weak areas** |

**Strengths.** (1) The provenance fold states the origin, the count, whether times
are loaded, the destination-type source, the feed's date and the restriction
reference — all from the page's own data. (2) The 44px floor with hit-slop is real:
the ticket link the eye sees is 48×22, and its out-set (11px top and bottom, 4px
sides) makes the target 56×44; the shortlist box is an 18px mark inside a 44px
label. (3) The mobile stacked row keeps label
and value in two fixed columns, so a stacked table still reads as a table.

**Priority issues.**
**Closed since:** [11], [12], [13], [14] — implemented 10 October 2026
(see "Closed since this audit" at the end).
- **[10] [P2] The change-station picker truncates silently for sighted readers.** It
  draws `wanted.slice(0, 40)` rows and puts "2703 stations listed" in an
  `sr-only` status (`page/station.js`, `renderPicks`). Measured: 40 rows, 539px
  client height against 2,022px of content, no visible cap note — the chooser
  solves the same problem with `#capMessage`.
- **[11] [P3] Nothing on the row says the ticket link opens a new tab.** The row link
  is `target="_blank" rel="noopener"` with the visible text "Tickets" and the
  accessible name "Tickets for ANCASTER"; the handoff sentence in the row's panel
  explains what to fill in and never mentions where it opens.
- **[12] [P3] "Page 1 of 2 of 30 results"** reads as a stutter. The page status and the
  result count are two facts in one sentence with one "of".
- **[13] [P3] Two words for one thing.** The column is headed `LIST`, its checkbox is
  named "List ANCASTER in the shortlist", and the dock, its count and its clear
  button all say "Shortlist".
- **[14] [P3] The ticket-mix rule is stated three times** above and below the table:
  the count line ("cheapest first: 28 singles, 2 returns"), `#modeNote` ("Each row
  is the cheapest fare of any ticket type, so this list mixes singles and
  returns"), and the footer paragraph.

**Persona red flags.** *Alex (power user):* no sorting, no column toggles, no
export; the shortlist's Copy does exist and is the one accelerator. *Riley (stress
tester):* the unnamed-`LIST` column and the unstated new tab are the two things
that read as bugs when probed. *Sam:* the shortlist checkbox's 18px mark inside a
44px label, the sticky header with its own background, one `main`, one `h1`, and
`role="status"` on the count line are all correct — the suite holds these already.

## Route 3 — the privacy page (`/privacy/`)

**Verdict.** A genuinely good notice: it names the two ways a search leaves the
device, what the host's logs contain, what happens after the ticket link, and
whether analytics run — all read from `site_features()`, so the page cannot
describe a build it is not. It is a document rather than a product page, which is
the right call (`page/privacy.css` sizes the title at 2rem for exactly that
reason). Its weaknesses are governance and ordering, not craft.

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | `data-synthetic` and the banner carry build provenance; there is no "last updated" for a page whose sentences are build-dependent. |
| 2 | Match system / real world | 4 | Plain language throughout, including "the host serving these static files sees the full address". |
| 3 | User control and freedom | 3 | A back link and a footer nav; nothing to escape. |
| 4 | Consistency and standards | 3 | Same chrome and type scale; no attribution or provenance, unlike the station page. |
| 5 | Error prevention | n/a | No input on this route. |
| 6 | Recognition rather than recall | 3 | Each heading names the question; the list points at its own section. |
| 7 | Flexibility and efficiency | n/a | A document, not a tool. |
| 8 | Aesthetic and minimalist design | 3 | 42rem measure, no eyebrow, no decoration; one bullet repeats the section beneath it. |
| 9 | Error recovery | n/a | Nothing can fail here. |
| 10 | Help and documentation | 4 | It is the help surface, and it is specific about mechanisms and the seller handoff. |
| **Total** | | **23/28** | **Good — 82% of the applicable maximum** |

**Priority issues.**
**Closed since:** [17], [19] — implemented 10 October 2026 (see "Closed since
this audit" at the end).
- **[15] [P1] The published contact is a personal mailbox and the README says it is
  unconfirmed.** The build in the working tree renders
  `the old email address` in the Contact section, while the
  uncommitted `README.md` edit records that `PROJECT_PRIVACY_CONTACT` "has **not**
  been confirmed as monitored or appropriate to publish". Every generated route
  promises a monitored contact, and `tools/check_release_clearance.py` is the gate
  that holds this — this is a state-of-the-tree finding, not a defect in the
  template.
- **[16] [P2] No date on a page that makes dated claims.** "No analytics run. If the
  operator later adds analytics, this page will name them here first" is a promise
  about a build; the build knows its `builtAt` and the page does not print it.
- **[17] [P3] The practices list restates the section it points at.** The bullet "Your
  search is kept in the page's web address … What stays in the address bar, below,
  explains this in full" duplicates the paragraph and the two bullets in that
  section, and appears before them.
- **[18] [P3] Section order buries the summary.** "What stays in the address bar" (the
  deep dive) precedes "What this site does" (the list a reader scans first).
- **[19] [P3] "Back to the station chooser" is wrong on a one-station release.** The
  release root for a single priced station says "This site was built for one
  station"; the privacy page still calls it a chooser and the footer still says
  "All stations".

## Collated suggestions

One list, organised by page, ordered by severity within each page. These numbers
are the document's reference numbers, matching the findings in the route sections
above. P0 = blocking, P1 = major, P2 = minor, P3 = polish. Each item names the
command/skill that could take it. The twelve items implemented on 10 October 2026
are under "Closed since this audit" at the end; the numbers of the open items are
unchanged.

### The chooser (`/`)

- **[3] [P1] Do not open the overlay over the page's own explanation.** Either open
   the list on the first keystroke or an explicit click rather than on load, or
   place the intro and ordering sentences above the overlay, or cap the panel's
   height until the reader types. Today a 522px panel covers both sentences on a
   fresh load. *(Command: `$impeccable layout`.)*
- **[4] [P2] Bound the directory state.** 2,704 rows make a 51,770px page at 1440px
   and a 153,923px page at 390px. Group by initial letter, page it, or show a
   stated top-N with the true count, keeping the field as the primary path.
   *(Command: `$impeccable distill`, then `$impeccable optimize` for the
   render cost.)*
- **[6] [P2] Say what the site is, and how old its prices are, on the entry
  route.** A real build passes no note, so the entry route carries no provenance
  line at all (the empty `<p class="tag">` item 8 removed was where one would
  sit): add one promise sentence and the feed's name and download date — the data
  the station page already has. *(Command: `$impeccable clarify`.)*

### The station page (`/from/<slug>/`)

- **[10] [P2] Show the picker's truncation to sighted readers.** Draw a visible
    "showing 40 of 2,703 — type to narrow" line beside `#originPicks`, as the
    chooser does, instead of leaving the fact in an `sr-only` status.
    *(Command: `$impeccable clarify`.)*

### The privacy page (`/privacy/`)

- **[15] [P1] Decide the contact before anything publishes.** The rendered page
    carries a personal-looking mailbox; the release gate exists for exactly this,
    and the uncommitted README edit says it is unconfirmed. Decide monitored
    address or issue tracker, then update `PROJECT_PRIVACY_CONTACT` and the
    clearance record together. *(Command: none — this is a person's decision,
    `tools/check_release_clearance.py` holds it.)*
- **[16] [P2] Print the build date.** One line under the title, from the `builtAt`
    the build already stamps, so the notice's build-dependent sentences are
    dated. *(Command: `$impeccable clarify`.)*
- **[18] [P3] Put the summary before the deep dive.** "What this site does" reads
    first; "What stays in the address bar" explains it. *(Command: `$impeccable
    layout`.)*

### Cross-route

- **[20] [P2] Every route the release serves should carry the notices the build was
    given.** `--notices nre,rdg,ogl,accuracy` reaches `render_page` only: the
    built chooser and privacy pages contain no licence or attribution wording at
    all, while the station page carries NRE and the Open Government Licence. Two
    ways to close it: render the notices on every template, or record the decision
    that directory routes do not need one. *(Command: `$impeccable harden`, then
    `$impeccable audit` for the wording.)*
- **[21] [P2] Make that invariant a build check, not a template accident.** The link
    crawl already proves every internal link resolves; a sibling check can prove
    every route in the release manifest carries the notices the build passed, and
    name the route that does not. This is the repo's own habit — a rule with an
    enforcer beside it. *(Command: none — a build/tooling change, `$impeccable
    harden` for the page half.)*
- **[22] [P2] Make "station search" mean one thing.** The chooser's field completes
    and shows counts; the station page's picker filters, has no completion, shows
    no counts and caps at 40 without saying so. One behaviour, one cap, one
    sentence about it, wherever a reader types a station name. *(Command:
    `$impeccable layout` after items 1, 2 and 10.)*

## Closed since this audit

Implemented on 10 October 2026 by the commits named beside each item. The route
sections above are the state as found on 9 October and were not rewritten.

- **[1]**, **[2]** and **[9]** — the field completes the exact match or the
  shortest prefix rather than the first name in count order, and the list shows
  every match with the completion first, which makes the forty-match cap message
  a normal result state. `fix(chooser): rank completions by relevance and show
  the matches`
- **[5]** — reviewed station display names, keyed by CRS, applied wherever a
  station is shown and nowhere a slug is derived. `fix(build): show a reviewed
  name for the stations the feed compresses`
- **[7]** and **[8]** — the chooser's two `.heading-sep` middots are gone and its
  heading is the station page's own sentence; no route writes a note paragraph
  when the build gave it no note. `fix(routes): one heading, no empty note
  paragraphs`
- **[11]**, **[12]**, **[13]** and **[14]** — the ticket link's accessible name,
  tooltip and handoff sentence say it opens a new tab; the page status reads
  "1 of 2 pages · 30 destinations"; the column, the dock and the stacked label
  say Shortlist; the footer keeps the limitations and leaves the mix to the count
  line and `#modeNote`. `fix(station): say where the link opens and state the mix
  once`
- **[17]** and **[19]** — the practices bullet is one sentence pointing at its
  own section; the back link and both footer links say "Station list" (the
  privacy footer's link travelled with [7] and [8], in that commit's file).
  `fix(privacy): cut the repeated practice bullet, say station list`

## Questions this audit leaves open

- The destination count as a *recommendation*: answered on 10 October 2026 — it
  is a sorting convenience, and the item-1 fix stopped the completion using it as
  a signal. Whether the directory should still be ordered by it is item 4's
  question rather than this one.
- Does the project want the chooser to be a directory at all? The 51,770px state
  is defensible as "a directory of every station", and indefensible as a first
  paint — which of those is the intent decides item 4.
- Should the non-fare routes carry licence notices (20), or is the recorded
  position "the obligations travel with the pages that show the fares"?

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
