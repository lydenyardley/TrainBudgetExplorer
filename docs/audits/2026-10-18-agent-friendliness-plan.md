# The repo an agent cannot quietly get wrong

**Status:** pruned 18 October 2026. R1, R2, R3 and R6 are implemented, and R8 as
far as R1 reaches; "What landed" names what holds each. What is left is the page's
own state (R4, R5), the rule table's third column (R7), and the half of R8 that
waits on R4. The numbers keep their original values, so a gap in the sequence is
deliberate.

**Raised by:** the operator's request of 18 October 2026, that the code be
rearchitected for agents rather than patched.

## The premise

Four rungs of enforcement, strongest first. Make the bad state unrepresentable,
then make it fail a check, then write a canonical helper, then write prose. The
repo is already strong at rung two: it has 34 test modules, a type ratchet, a
`verify.py` that reports `not run` and exits 2 rather than passing, and eight
`tools/check_*` commands, most of them wired into CI.

That strength is where the first defect lived. **A check that cannot fail is worse
than no check, because it spends the trust a real check would have earned.** Three
measurements found it in three places: a byte gate that reported 0 KB of payload
on every page it measured, the same gate passing an empty folder, and one fact
(the payload's marker) spelled independently in eight files, the eighth being the
gate. R1 and R2 closed those; each figure is in the commit that fixed it and in
`docs/build-performance-findings.md`, which is where measured figures live.

The three mistake classes the plan was grouped by are now two landed and one left.

| Class | Closed by | What is left |
|---|---|---|
| A measurement that degrades to zero instead of failing | R2, and the byte gate's own test measuring a page the template wrote (R3) | nothing |
| One fact with several owners | R1, for the payload's marker | the page's state, which is R4 and R5 |
| A claim wider than the data behind it | R6, for the sentence about times | nothing |

## The evidence the remaining work rests on

### E4. The page has no state, so its state is 269 element properties

`grep -cE '\.(value|checked|dataset|textContent|hidden|classList)' page/station/*.js`
sums to **269 accesses across 15 modules**. The count is a size, not a defect
count, and it does not separate reads from writes.

The domain model does exist, in `page/station/url-state.js`. `readState()` returns
a complete typed shape with the clamping and filtering already written as domain
rules. `applyState()` maps it back into the controls. That pair is used on load
and on `popstate` and nowhere else, so during a session the controls are the state
and the state object is a snapshot taken at the page's boundaries.

Six of the 37 `fix(page|station|chooser|routes)` commits are the same shape seen
from six sides, all of them a second writer or reader of a fact that only lives in
an element: `Back and Forward carry the chosen day`, `an arrow key no longer takes
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

Eighteen instrumentation fixes is the number that shaped this plan, and R1 to R3
are the answer to it. The thirty-seven page fixes are what R4 and R5 are for.

## The design, two candidates compared

The question is where the page's state lives, because that is the largest class
and the one with the most repeated fixes.

**Candidate A, the state object becomes the source.** `readState()` names the
shape and it becomes the page's one mutable object. Every control writes into it
through one adapter and every render derives from it. The URL becomes a projection
of the object in both directions, which `writeUrl` and `readState` already are.
`applyState` survives as the only writer into the controls.

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

## Recommendations

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

### R7. The rule table gains a column, and a blank cell is a task

`AGENTS.md`'s table pairs rules with enforcers. It gains "what fails when the rule
is broken", and any row that cannot name a failing command is moved to an open
work item in the same edit. That is `/correct`'s own instruction, applied to the
file that most agents read first.

Holds, nothing mechanical. This is prose, so it is rung four, and it is here
because it is the index to the rest. It is the one recommendation whose own test
is a person, which is why it ranks last.

### R8. Retire the prose the structure replaces

The half that R1 reached landed with it: `check_source_credit.py`'s docstring
imports the marker it used to name in its own words, so a reader of the docstring
and a reader of the template are told the same string. What waits on R4 is the
comments in `url-state.js` that explain why `applyState` must re-read the controls.

Prose that explains a workaround is a marker for the workaround, so the same change
removes it.

## Order, and what each unit proves

1. **R4 on three panels, then R5.** The state object earns its place on
   `service-day.js`, `shortlist.js` and `picker.js` before the rest of the page
   moves, and it is the four defects there that justify it.
2. **R7 alongside whichever lands next.** It is prose, and it costs nothing to
   carry.

## What landed

| | What changed | Held by |
|---|---|---|
| **R1** | `page_templates.py` owns `PAYLOAD_MARKER` and `CHOOSER_MARKER`. `build_state.py`, `tools/page_bytes.py`, `tools/check_source_credit.py`, `tests/page_harness.py` and `tests/test_page_output.py` import them instead of spelling them. | `tests/test_page_assets.py` holds each template to its own marker, and holds the two gating tools to the template's. |
| **R2** | `page_bytes` exits 2 on a page that names a payload it did not parse, and on a `--site` run that finds no page. | `tools/test_page_bytes.py`, two cases, plus a third proving a page that ships nothing still passes. |
| **R3** | The byte measurer's own test measures a page built from `page_templates.TEMPLATE`, not a page the test typed. | `tools/test_page_bytes.py` |
| **R6** | The paragraph about times is the payload's own sentence, chosen once from `hasJourneys`: a prices-only page no longer says "valid on the services listed". | `tests/test_build_demo_page.py`'s `test_the_sentence_about_times_names_only_what_this_build_has`; the words are `build_release.SERVICE_CLAIM` and `SERVICE_CLAIM_WITHOUT_TIMES` |
| **R8** | `check_source_credit.py`'s docstring imports the marker rather than restating it. | the same test as R1 |

Each new check was run against the old behaviour before it was trusted: the byte
tool as it shipped, imported from `git show HEAD:tools/page_bytes.py`, reports
0 bytes and 0 rows on a page carrying a payload, exits 0 on an empty site, and
exits 0 on a payload that did not parse. The C5 sentence was read out of the
prices-only page built before R6 and is the sentence that page no longer carries.

## What this plan deliberately does not propose

Checked against "Rejected, with the reason" in `docs/open-work.md`.

- **No package move.** Rejected 8 October for import and CI churn, and R1 gave the
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

- E5 is a classification by commit prefix, which is the author's label. It locates
  the work. It does not measure it.
- The state object's cost in R4 is estimated from file count and the bug cluster.
  No prototype has run for it, and the four defects it is meant to prevent are
  already fixed at the element level: R4 is prevention, not a repair, so its
  benefit is proved by the cases that keep passing, not by a case that starts
  passing.
- No browser suite run was made for R1 to R3. R6's change was read in the browser
  suite on both page shapes, 482 checks, and in the live page.

## Waiting on a person

1. **Does the 354 KB P2 get decided now that the byte gate measures the payload, or
   does it wait for a throttled first-paint measurement as well?** The instrument
   gives the payload split. It does not give the paint cost, and the open item asks
   for the figure before the change.
2. **R4 lands three panels first or all sixteen at once?** I recommend three, and
   the reason is in the order section, but it is a call about review appetite
   rather than about code.
