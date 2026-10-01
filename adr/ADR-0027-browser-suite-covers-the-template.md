# ADR-0027: The browser suite is `page_templates.py`'s test

**Status:** Accepted
**Date:** 26 September 2026
**Relates to:** ADR-0010 (the demo page before the gate), ADR-0024 (what a
build costs), audit finding C2 of 25 September 2026

## Context

`page_templates.py` is 1,051 lines of the product: the budget field, the
filters, the fare labels, the railcard drawer, the origin picker, the copy
actions. It has no test file of its own. What it has instead is two things
that cover different halves of it:

- `tests/test_build_demo_page.py` asserts strings inside the rendered page —
  that the right HTML and JavaScript reach the output. Those are stills, not
  behaviour: none of them opens a browser.
- The Playwright suite (`tests/browser_test.cjs`, 57 checks, run in the
  deploy workflow) drives the built page in a real browser: it drags the
  budget slider, filters to a town, follows a ticket link to a stub, and
  reads back what **Copy** puts on the clipboard. That is the only cover for
  what the JavaScript *does*.

An audit can read that as a gap — a 1,051-line module with no unit tests —
and the natural response would be to add unit tests that assert template
output harder. The suite already does that, and more string assertions would
not have caught the failure this arrangement actually caught: the copy
control shipped with a newline inside a JavaScript string literal, the whole
page went down, and every Python test still passed.

## Decision

**The browser suite stays the cover for `page_templates.py`, and the module
gets no unit tests of its own.** This is a decision, not a gap to be closed
by a later pass.

The line that matters: Python tests assert what the page *says*; the browser
suite asserts what the page *does*. A new behaviour in the template — a
control, a state, a keyboard path — arrives with a check in
`browser_test.cjs`, because that is where the failure would show. A new
string in the template arrives with the existing render tests.

**Every expectation in the browser suite is read out of the page's own
payload.** The suite used to name Nottingham, Lincoln, Peterborough and the
Tower of London, which made it a test of the synthetic demo feed whatever page
it was pointed at, and the deploy workflow pointed it at a real Grantham page
where none of those is a priced destination: three checks could not pass there
for that reason alone, and a gate that cannot pass is a gate nobody reads. The
facts it wanted were all in the page it was already reading, so a check now
asks the payload — the origin's own name, the cheapest return it can fill a
budget with, the rows a type leaves, the mode that carries a heritage
destination — and judges the page against that, in both directions where a
check has two (a chip must be offered when a destination carries its type, and
not offered when none does).

The page under test in CI is the synthetic demo feed's, built in the workflow
itself. The suite tests the template, not a station, so it holds for any
origin and a day's fares cannot fail it; and because the workflow builds it
there, the step has a page on every run rather than pointing at an artifact
that only exists when the feed changed. A build that produced no page fails the
step with a reason attached.

**The suite takes as many page paths as it is given and reports one result
per page.** Every expectation comes from the page's payload, so the same
checks hold on a real station's page and on the synthetic one — which is what
makes a sweep worth having: pointing the suite at the built station set finds
origin-specific template bugs (a page whose cheapest fare is above the opening
budget, a page carrying no destination of a type the checks expect) in one
run, rather than one page at a time by hand. A path that is a **directory** is
swept: every `index.html` beneath it becomes a page of the run, so a whole
published station set is one command. Each page gets its own browser
context, so the seller's stub route, the clipboard grant, and the budget,
filters and mode a reader left behind are per page rather than carried over.
A path that is not there is a failed page and not a failed run: the other
pages are still driven and still reported, and the summary names the ones
that failed.

**A page that is not a station page is a fourth thing, and it does not fail
the run.** Sweeping a published site found the case: which page sits at the
site root is a fact about the build, not about the file. A single-station
build writes the station page there; a full-network build writes a chooser
there and its station pages under `from/`. CI passes the root path on every
run that built a site, so a rule that fails on a page's shape would have
failed the workflow for something a working build had done. A chooser or a
privacy page is reported as 0/0, named at the end of the run, and skipped —
while a run in which *no* page was a station page has checked nothing and
fails for that reason instead. The rule it replaced was "a page that is not
what this suite tests stops the run and fails it", which was right for a
mistyped path and wrong for a real site: it failed the tool, not the product.

**A check a page has nothing to exercise is a third outcome, and which
outcome it is depends on the run.** Some checks need the page to *contain*
something: a destination carrying a UNESCO property, a small town, two
destination-type chips, more than one option in the picker. On the demo page
— the only page CI builds — a page without those is a failure, because a check
that never ran is the thing this project keeps refusing to let pass quietly.
Sweeping a station set it is a skip: most real stations have no UNESCO
property, and failing them would be failing pages for their own size.
`--sweep` chooses which, and the run always reports how many checks it
skipped, so a sweep cannot pass by exercising nothing. `--max` bounds a sweep
and says on stderr how many pages it left out, for the same reason.

The sweep earned its keep the first time it ran, on a two-station build: it
found a budget bug, not a test artefact. On a page with one destination the
ceiling the page allows is that destination's adult fare while the party fare
is double it, so the "Two adults" control could not show a row at any budget
the page accepted. The suite had been reading the ceiling before selecting
the party unit, reporting the rows as unreachable, and then waiting thirty
seconds for a button that could never appear.

One check drives a state the page's own feed may not contain. Most real
origins price no unrestricted Anytime Day Return at all — King's Cross has
171 returns and none of those — so the check switches to whichever mode the
payload says is empty. When a page prices all three, as the synthetic demo
feed does, it empties one list in the page and switches to it, so the path is
driven on that page too rather than being reported as untestable. The
alternative was worse: a check that could only pass on a page CI never
builds is a check whose failure nobody would read.

## What would change this

The browser suite is skipped with exit 2 when Playwright is missing, so an
environment that never installs it has a real hole in the JS cover. That is
the known cost, recorded here so a later audit measures the hole instead of
re-discovering it: the deploy workflow installs Chromium and runs the suite
(`deploy.yml`, "Test the page in a real browser"), so the shipped path is
covered; a contributor's local run is what goes without.

The suite runs against the published page in the same CI run that publishes
it, so a real station's page is no longer the one nobody opened on the day.
That closes the cost this record used to name, and it closes it because the
suite reads its expectations from the payload rather than from a fixture: the
checks that could not pass on a real page three decisions ago now hold on it,
and the page that ships is one a browser drove. The remaining gap is the
unchanged-feed run, where the site was not rebuilt and there is no published
page to drive; the demo page still runs there, and the next build drives its
own output.

**Amended 28 September 2026.** The paragraph above decides that which outcome a
check the page cannot exercise gets "depends on the run", and that `--sweep`
chooses. That was right for a suite whose only page was a demo page built to be
big, and wrong the moment the suite was pointed at the published site: a
one-origin build has no second station to change to and no destination without
a journey, so five checks it honestly cannot run were five failures and the
page went untested altogether. The teeth were never in the failure — they are
in the skip budget, which is enforced in every mode and names the page. So a
check with nothing to exercise is now a skip in every mode, `--sweep` is
accepted and stripped but decides nothing, and one standard covers a single page
and a station set. The "never ran that assertion" worry this record was written
against is answered by the budget rather than by the exit code, which is the
same worry the budget was added for.
