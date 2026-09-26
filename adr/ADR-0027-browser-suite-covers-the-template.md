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
- The Playwright suite (`tests/browser_test.cjs`, 50 checks, run in the
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

## What would change this

The browser suite is skipped with exit 2 when Playwright is missing, so an
environment that never installs it has a real hole in the JS cover. That is
the known cost, recorded here so a later audit measures the hole instead of
re-discovering it: the deploy workflow installs Chromium and runs the suite
(`deploy.yml`, "Test the page in a browser"), so the shipped path is
covered; a contributor's local run is what goes without.
