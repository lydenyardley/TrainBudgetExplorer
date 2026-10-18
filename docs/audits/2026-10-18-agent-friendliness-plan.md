# The repo an agent cannot quietly get wrong

**Status:** partly landed, 18 October 2026. R1, R2 and R3 are implemented and
tested, and "What landed" below records the proof. R4 to R8 are proposals and none
of them is in the tree. Each numbered recommendation names the defect it prevents
and the check that would hold it, and the order to build them in is at the end.

**Raised by:** the operator's request of 18 October 2026, that the code be
rearchitected for agents rather than patched.

**Landed the same day:** R1, R2 and R3, after this file was written. The evidence
in it is what they were implemented from.

## What was asked, and what the record actually holds

The brief was to learn how the operator steers agents, then turn the recurring
corrections into structure. It named three sources. Two do not exist on this
machine, checked rather than assumed.

| Source | State |
|---|---|
| Slack threads and PR review comments | No chat app is connected. The GitHub repo has **0 pull requests and 0 issues**, and the 385 commits on `main` belong to one person under two spellings. There is no review thread to mine. |
| Past agent transcripts | No Cursor or Claude transcript store under `$HOME`. There is nothing for `/recall` to reconstruct. |
| Commit history | 385 commits, 108 of them `fix`. This is the trace, and it is unusually good, because each subject and body says why and what it cost. |

So the operator's steering was read from the repo's own record, which the repo
keeps deliberately. `docs/audits/` holds the dated reviews, `docs/open-work.md` is
1,035 lines and its open findings are the first 477 of them, and the section that
matters most for taste is "Rejected, with the reason" at line 568. `adr/` holds 73
decisions with status lines. Those
rejections are the cheapest source of taste in the tree and this plan is checked
against every one of them.

## The premise this plan is built on

Four rungs of enforcement, strongest first. Make the bad state unrepresentable,
then make it fail a check, then write a canonical helper, then write prose. The
repo is already strong at rung two. It has 34 test modules, a type ratchet, a
`verify.py` that reports `not run` and exits 2 rather than passing, and eight
`tools/check_*` commands, most of them wired into CI.

That strength is exactly where the first defect lives. **A check that cannot fail
is worse than no check, because it spends the trust a real check would have
earned.** The rest of this document is mostly about that one shape, found in four
different places.

## The measured evidence

Every number below was produced this session, and each names the command that
reproduces it.

### E1. The byte gate measures nothing, and passes

`python -m tools.page_bytes _demo_site/index.html _demo_site/from/grantham/index.html _shape_site/prices-only/index.html`

```
_demo_site/index.html: 28 KB total, 22 KB css, 3 KB script, 0 KB payload, 0 rows
_demo_site/from/grantham/index.html: 38 KB total, 0 KB css, 22 KB script, 0 KB payload, 0 rows
identical on all 3 measured pages: 0 KB, 0% of the largest page
exit=0
```

The Grantham page carries `window.TBE_DATA = ` exactly once, and the tool searches
for `const DATA = `. Measured with the marker the renderer actually writes, the
same page reports **19 KB payload and 16 rows, which is 48% of its 39,757 bytes**.

This is not cosmetic. `docs/open-work.md:101` records an open P2, "a station page
is 354 KB, and nobody has decided whether that is the payload", and says what
would close it, "a measurement, then a decision, in that order". The instrument
for that measurement reports zero and CI's only byte gate reads the same zero. The
decision has been waiting on a tool that has been answering 0 for an unknown
number of months.

### E2. The same tool passes over an empty site

`python -m tools.page_bytes --site <empty dir>` prints `site 0 MB of a 800 MB
budget over 0 page(s)` and exits 0. `deploy.yml:729` is that exact invocation and
it is the only byte gate in CI. A build that writes no page passes it.

The repo already knows this is wrong. `tools/verify.py:92` maps `None` to
`not run`, and `tools/verify.py:263` returns 2 with "a step could not run, so
nothing here says the change is good". And sitting at `deploy.yml:797`, ten lines
below the byte gate, `tools/check_source_credit.py` obeys the convention and says
so in a sentence a reader can act on.

Two adjacent steps in one job. One refuses an empty tree. One passes it. That is
what prose does when nothing enforces it.

### E3. One fact, eight owners, one stale

The inline payload's marker is spelled independently in eight places, under two
different names.

| Where | What it says |
|---|---|
| `build_state.py:253` | `marker = "window.TBE_DATA = "` |
| `page_templates.py:364` | `window.TBE_DATA = __DATA__;` |
| `page/station/payload.js:19` | `const DATA = window.TBE_DATA;` |
| `page/chooser.js:9` | `const STATIONS = window.TBE_CHOOSER_STATIONS;` |
| `tests/page_harness.py:156` | indexes `"window.TBE_DATA = "` |
| `tests/test_page_output.py:134` | asserts the block starts with it |
| `tools/check_source_credit.py:55` | `FARE_MARK = "window.TBE_DATA"` |
| `tools/page_bytes.py:51` | `("const DATA = ", "const STATIONS = ")` |

Seven agree. The eighth is the one that measures, and it is the one nobody
noticed. No check compares them, because a string constant duplicated is not a
type error and not a test failure.

### E4. The page has no state, so its state is 269 element properties

`grep -cE '\.(value|checked|dataset|textContent|hidden|classList)' page/station/*.js`
sums to **269 accesses across 15 modules**. `provenance.js` has 35, `filters.js`
33, `railcards.js` 29. The count is a size, not a defect count, and it does not
separate reads from writes.

The domain model does exist, in `page/station/url-state.js`. `readState()` returns
a complete typed shape with the clamping and filtering already written as domain
rules. `applyState()` maps it back into the controls. That pair is used on load
and on `popstate` and nowhere else, so during a session the controls are the state
and the state object is a snapshot taken at the page's boundaries.

Six of the 37 `fix(page|station|chooser|routes)` commits are the same shape seen
from six sides, all of them a second writer or reader of a fact that only lives in
an element. `Back and Forward carry the chosen day`, `an arrow key no longer takes
the station away from Tab`, `the tick on a row is the shortlist`, `a card must not
swap the row under a reader's feet`, `the budget floor is zero`, `the field stops
moving the page`.

### E5. The fix record, by the author's own label

A subject prefix is the author's label, not a measured property, so read this as a
map and not as a metric.

| Prefix | Count | Reads as |
|---|---|---|
| `fix` | 108 | |
| of which `fix(tools|tests|ci|verify)` | 18 | the instrument was wrong |
| of which `fix(page|station|chooser|routes)` | 37 | the page said or did the wrong thing |
| of which `fix(fares|timetable|journeys|feeds|reference)` | 17 | a feed fact was read wrong |
| of which `fix(build|release|licences|replay|adr)` | 12 | the build's own plumbing |

Eighteen instrumentation fixes is the number that decides this plan's shape. The
checks are not under-built. They are built from parts that cannot report their own
failure.

## The three mistake classes

Grouped per `/correct`, each with the level chosen and why the level above it did
not work.

### Class 1. A measurement that degrades to zero instead of failing

**Evidence.** E1, E2, and these subjects. `fix(tests): a check must read the rows
the page renders, not the rows it holds`. `fix(tools): the worker measurement was
reading a database it had already freed`. `fix(tools): the sweep estimates what is
left from the request, not from the file`. `fix(feeds): the fuzzer checks the
timetable copy it damaged`. `fix(tools): the link check stops reading the seller's
own error strings`. `fix(ci): compare only the DTD download across the build's jobs`.
Plus `fix(tests): a prices-only page cannot print a service window, so stop asking`.

The shared mechanism is a default that is also a legal answer. `_row_count` returns
0 for a shape it does not recognise. `payload` stays 0 when the marker is absent.
`pages` is 0 for an empty tree. In each case "there is nothing here" and "I cannot
see what is here" produce the same value, so the caller has no way to tell them
apart and neither does the exit code.

**Level chosen.** Architecture, then a check. Not prose, because the convention is
already written in `AGENTS.md` and `verify.py` and was still broken by the very
next tool written beside a tool that obeys it.

**Why not types.** Python's type system cannot express "this integer was measured"
versus "this integer is the default". A `Measured[int]` wrapper would be a new
layer through every print statement, and the Laziness Protocol rejects a layer that
removes no branch.

### Class 2. One fact with several owners

**Evidence.** E3, eight spellings. E4, the state of the page living in 269 element
properties. And these subjects. `fix(page): write the page's claims from the state
on screen`. `fix(build): a page the rebuild keeps never names an asset it pruned`.
`fix(build): a rebuild removes the hashed assets it no longer names`. `fix(adr): the
four-worker tree was a sample taken mid-parse, not a contradiction`. `fix(page):
share a two-ticket row's railcard rule across rows`.

The last one is the clearest. A rule that applies across rows was stored per row,
so two rows could disagree about a fact that has one value. That is not a bug in
either row. It is a bug in where the fact was kept.

**Level chosen.** Architecture. The rule is one value in one place, or it is two
values that will drift.

**Why not a lint first.** A lint that forbids reading `.value` outside one module
is worth having (R5), but it is the guardrail for the fix, not the fix. Shipping
the lint without the state object would just move the reads into an allowlist.

### Class 3. A claim wider than the data behind it

**Evidence.** `fix(page): a row with no service names the day it does run`.
`fix(page): name no interchange under a journey the page does not know`.
`fix(page): a row reads Direct and claims a split ticket somewhere`.
`fix(fares): publish only fares a reader can actually buy`. `fix(fares): a return
called NOT FOR TRAVEL reached a page`. And C5 of the review filed yesterday, P1, a
prices-only page still claiming "valid on the services listed", shipped
unconditionally by `page_templates.py:330`.

The page builds sentences in a template and fills them from a payload that may not
support every clause. When the payload is thinner than the template, the sentence
survives and becomes false.

**Level chosen.** Type at the boundary, then a test. The payload's shape should
make a claim without its support unrepresentable, which is what the packed column
form in `build_payload.py:1610` already does for row fields.

**Why not prose.** This was already prose. The 3 October subject `fix(tests): a
prices-only page cannot print a service window, so stop asking` is the operator
telling the suite to stop asserting something the page cannot have. The words were
right and the shape was wrong, and the page still made the claim fifteen days
later.

## The design, two candidates compared

The question is where the page's state lives, because that is the largest class
and the one with the most repeated fixes.

**Candidate A, the state object becomes the source.** `readState()` names the shape
and it becomes the page's one mutable object. Every control writes into it through
one adapter and every render derives from it. The URL becomes a projection of the
object in both directions, which `writeUrl` and `readState` already are. `applyState`
survives as the only writer into the controls.

**Candidate B, the URL becomes the source.** Every control writes the address, the
address is read back into the controls, and the DOM stays as it is. One owner, no
adapter needed.

**Compared on interface depth.** A adds one object and keeps one adapter per
control family, about six. B adds no object but makes the address part of the
interaction path, so the budget clamps through a string, a keystroke becomes a
history entry or a replace, and the 700 ms timer in `url-state.js` moves from
polishing a URL into the correctness of the state. B is fewer files and a worse
contract, because the encoding leaks into every event handler.

**Synthesis.** A, with B's discipline that the address is always derived and never
read back during a session. That is what the existing `popstate` handler already
assumes.

**What the sketch settles.** `applyState` currently sweeps
`document.querySelectorAll` twice and then walks two selector lists it holds as
module constants, because it has to know every control by its element. Under A it
remains the only place that knows the controls, but it runs from the object rather
than from the address, and the six class-2 page defects become states the object
cannot hold two of.

## What the prototypes showed

All scratch work, in `%TEMP%/pb-proto/`, nothing written to the tree.

| Run | Result |
|---|---|
| Shipped tool on the demo pages | 0 KB payload, 0 rows, 0 markers found, exit 0 |
| Prototype, marker taken from the renderer | 19 KB payload, 16 rows on Grantham. 48 KB over the 5 demo pages |
| Prototype, marker list left as it is today | 0 payload, 0 rows, and **0 markers found**, which is the number that separates "empty" from "blind" |
| Prototype on an empty site | exit 2, "no page was found under ..., so there is nothing to measure" |
| Prototype on a page naming a payload that will not parse | marker named 1, payload 0, and the exit code is non-zero |
| Prototype on the privacy page | 0 payload, 0 markers, exit 0, so the guard does not fire on a page that genuinely ships nothing |

One thing the prototype changed. My first guard was "fail when every measured page
reports 0 payload". Measuring the privacy page alone would trip that falsely, so
the guard became local to the page, "a page that names a payload the tool did not
parse is a failure", which has no false positive and needs no global heuristic.

## Recommendations

Numbered, strongest rung first, each with the check that holds it. Cost is my
estimate from the file sizes, not a measurement.

### R1. One module owns the inline payload's wire form

`build_payload.py` already owns the payload's shape. It gains the marker and the
line the template writes, `MARKER` and `script_line(payload)`, and `page_templates.py`
builds `window.TBE_DATA = __DATA__;` from them. `page_bytes.py`,
`check_source_credit.py`, `tests/page_harness.py` and `tests/test_page_output.py`
import `MARKER`. Eight spellings become one.

Holds, `tests/test_page_output.py` asserts the built page starts with the marker the
module exports, so a template that drifts fails a test that already exists.

Prevents, E3, and the entire class of "a constant that measures the artifact is
copied instead of imported".

Cost, one new constant, five import lines, one template line. **This is the cheapest
change in the document and the only one that unblocks an open decision.**

### R2. A measurement fails when it cannot measure

Two invariants, in `page_bytes.py` first and then everywhere with the same shape.

- **Nothing to measure is not a pass.** A `--site` run that finds no page exits 2
  and says so, the sentence `check_source_credit.py` already writes.
- **A page that names a payload it did not parse is a failure.** Local to the page,
  so a privacy page still passes.

Holds, `tools/test_page_bytes.py` gains an empty-tree case and a
marker-named-but-unparseable case, and the CI step keeps exit 2 as a failure.

Prevents, E2, and by precedent the 18 instrumentation fixes.

Cost, about 15 lines and three tests.

### R3. A check's test measures an artifact the build wrote

`tools/test_page_bytes.py` builds its pages by hand, in the old wire format, so it
proves the parser and cannot prove the tool. This is the general form of
`fix(tests): a check must read the rows the page renders, not the rows it holds`.

The test renders one page through `build_render` into a temporary directory and
asserts a non-zero payload and a row count against a literal. The hand-built cases
stay, because they cover the split.

Holds, the new case fails today, on the shipped tool, which is the proof the fix is
real.

Cost, one test and one import. `tests/page_harness.py` already imports
`build_demo_page` and `build_state`, and already parses the `window.TBE_DATA`
block out of a built page, so the machinery is there and this is a second caller.

### R4. The page gets one state object

`readState()`'s shape becomes `page/station/state.js`, the page's one mutable
object, with `read()` and `write()` for the URL bound around it. Controls write
into it. `render()` reads from it. `applyState` becomes the only writer into the
DOM and the only place that knows a control's identity.

Holds, a browser case per defect already filed, run against the state rather than
the elements. `tests/browser/station-picker.cjs` and `station-filters.cjs` already
drive the controls, so the cases exist and the assertions move.

Prevents, the six class-2 page defects and the page half of E4.

Cost, the largest item here. `page/station/` is 16 files and the change lands one
panel at a time. Start with `service-day.js`, `shortlist.js` and `picker.js`, which
hold four of the six, the day, the tick, the arrow key and the moving field.

### R5. A lint that names the fix, for the reads that remain

No module outside `state.js` may read `.value` or `.checked` except through a
named control adapter, with the adapter list in one place. This is the ratchet
shape `tools/check_types.py` already uses, and it runs in `--full`.

Holds, `tools/check_page_state.py`, plus `tests/test_suppressions.py`'s rule that
any allowlist entry names its cause.

Prevents, R4 regressing file by file as the next panel is written by copying the
last one.

Cost, about 60 lines, plus the allowlist's honest first entry.

### R6. A claim is rendered from the payload, never hardcoded in a template

Any sentence in `page_templates.py` that asserts something about the data carries
a payload flag that produced it, or it is not rendered. C5's "valid on the services
listed" on a prices-only page is the case, and the flag already exists in the
payload because the page already knows which shape it is.

Holds, one assertion per shape in `tests/test_build_demo_page.py`, which already
builds both shapes.

Prevents, class 3.

Cost, small per sentence, and the number of sentences is small.

### R7. The rule table gains a column, and a blank cell is a task

`AGENTS.md`'s table pairs rules with enforcers. It gains "what fails when the rule
is broken", and any row that cannot name a failing command is moved to an open
work item in the same edit. That is `/correct`'s own instruction, applied to the
file that most agents read first.

Holds, nothing mechanical. This is prose, so it is rung four, and it is here because
it is the index to the rest.

### R8. Retire the prose the structure replaces

When R1 lands, the sentence in `check_source_credit.py`'s docstring about
`window.TBE_DATA` becomes an import. When R4 lands, the comments in
`url-state.js` that explain why `applyState` must re-read the controls become
unnecessary. Prose that explains a workaround is a marker for the workaround, so
the same change removes it.

## Order, and what each unit proves

1. **R1, R2, R3 in one change.** It proves the instrument and unblocks the P2
   decision in `docs/open-work.md:101`. Nothing else should be written until the
   tool that measures the release can be trusted, because the 354 KB question is
   the one the next three months of decisions depend on.
2. **R4 on three panels, then R5.** The state object earns its place on
   `service-day.js`, `shortlist.js` and `picker.js` before the rest of the page
   moves, and it is the four defects there that justify it.
3. **R6.** Independent of the page state.
4. **R7 and R8 alongside whichever lands first.**

## What landed, and how it was proved

Landed 18 October 2026, in one change.

| | What changed | Held by |
|---|---|---|
| **R1** | `page_templates.py` owns `PAYLOAD_MARKER` and `CHOOSER_MARKER`. `build_state.py`, `tools/page_bytes.py`, `tools/check_source_credit.py`, `tests/page_harness.py` and `tests/test_page_output.py` import them instead of spelling them. | `tests/test_page_assets.py` holds each template to its own marker, and holds the two gating tools to the template's. |
| **R2** | `page_bytes` exits 2 on a page that names a payload it did not parse, and on a `--site` run that finds no page. | `tools/test_page_bytes.py`, two cases, plus a third proving a page that ships nothing still passes. |
| **R3** | The byte measurer's own test measures a page built from `page_templates.TEMPLATE`, not a page the test typed. | `tools/test_page_bytes.py` |

**The proof that each new check fails on the old behaviour.** The tool as it
shipped was imported from `git show HEAD:tools/page_bytes.py` and run against the
same four cases.

| Case | Shipped tool | The test wants |
|---|---|---|
| a page carrying a payload | 0 bytes, 0 rows | more than 0 and 2 rows |
| an empty site | exit 0 | exit 2 |
| a payload that did not parse | exit 0 | exit 2 |
| a page the template wrote | 0 bytes | more than 0 |

Repaired, the same page reports 19 KB of payload and 16 rows. The figures are in
`docs/build-performance-findings.md`, dated, with the command beside them.

**Suites run and green.** `tools.test_page_bytes` 20, `tools.test_check_source_credit`,
`tests.test_page_assets` 39 together, `tests.test_page_output` 45,
`tests.test_page_caches` 45. The full suite and the browser suite did not run.

**What did not land.** R4 to R8. The page-state object is the next unit and it is
the only one of them that needs a prototype first.

## What this plan deliberately does not propose

Checked against "Rejected, with the reason" in `docs/open-work.md:568`.

- **No package move.** Rejected 8 October for import and CI churn, and R1 gives the
  same orientation benefit through one module.
- **No type checker for page defects.** Rejected 8 October because the defects are
  in JavaScript. R5 is a lint over JavaScript instead.
- **No split for length.** No file in this plan moves because it is long.
- **No schema for the classification tables, no template helpers, no parametrized
  test ids.** Each was rejected for the same reason, they would trade a written
  reason for a mechanism that cannot carry it.
- **No new abstraction over the checks.** R2 is one function and one exit code, not
  a runner. `verify.py` is already the runner and does not need a competitor.

## Limits of this document

- No real-feed build this pass. Every figure describes the demo and shape builds
  already on disk, which were built before the nine files currently modified. The
  demo Grantham page holds 16 destinations and the real one holds 334, so the
  48% payload share must not be projected onto the 354 KB figure.
- No full suite run and no browser suite run, then or since. The modules that
  consume the changed imports were run and are listed under "What landed".
  `mypy` is not installed on this machine, so `--full` could not pass here even
  if run.
- E5 is a classification by commit prefix, which is the author's label. It locates
  the work. It does not measure it.
- The state object's cost in R4 is estimated from file count and the bug cluster.
  No prototype ran for it. The prototype in this document settles the measurement
  question only.

## A question this file decides rather than defers

**The demo build is a fair stand-in for repairing the byte gate.** The tool's
contract is that it reads the payload a page ships, and that contract does not
change with the number of destinations. The demo pages carry the same marker the
release writes, so a tool proved against them is proved. The 48% share is a demo
figure and stays labelled as one. A real-feed build is a build, not a change, and
it belongs to the P2 below rather than to R1.

## Waiting on a person

1. **Does the 354 KB P2 get decided after R1, or does it wait for a throttled
   first-paint measurement as well?** R1 gives the payload split. It does not give
   the paint cost, and the open item asks for the figure before the change.
2. **R4 lands three panels first or all sixteen at once?** I recommend three, and
   the reason is in the order section, but it is a call about review appetite
   rather than about code.
