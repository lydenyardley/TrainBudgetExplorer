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
- The Playwright suite (`tests/browser_test.cjs`, 52 checks, run in the
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

## What would change this

The browser suite is skipped with exit 2 when Playwright is missing, so an
environment that never installs it has a real hole in the JS cover. That is
the known cost, recorded here so a later audit measures the hole instead of
re-discovering it: the deploy workflow installs Chromium and runs the suite
(`deploy.yml`, "Test the page in a real browser"), so the shipped path is
covered; a contributor's local run is what goes without.

A second cost is that CI runs the suite against the synthetic page, so a real
station's page is not driven in a browser before it is published. The suite is
written to be run against any page (`node tests/browser_test.cjs <page>`) and
passes against real Grantham and King's Cross pages, so the gap is one command
rather than a rewrite — but it is a gap, and the page that ships is the one
nobody has opened in a browser on the day.
