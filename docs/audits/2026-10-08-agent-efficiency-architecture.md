# Agent-efficiency architecture review

**Date:** 8 October 2026
**Commit reviewed:** `81ea448` on `main`
**Reviewer:** Grok Bot, first pass on this repository.
**Question:** how cheaply and safely can a coding agent make a correct change
here? The agent sees only the files it opens, copies the nearest example, and
takes the shortest path that compiles.
**Pruned:** 10 October 2026, then 14 October 2026 to what this review still asks
for, which is nothing.

## Still open

- **None.** Findings F1 to F8 are settled, and the last of them landed on
  14 October 2026: F6's remainder, `DemoPageTest` -- 3,010 lines and 159 test
  methods at the commit reviewed here, 3,156 and 163 by the time it moved -- whose
  methods were one class. They are now one module per subject over
  `PageTestCase` in `tests/page_harness.py`: the same 180 tests, and 179 of their
  180 names unchanged. The one rewritten is the contact test, because route
  audit item [15] landed in the same pass and the old name asserted the opposite
  of what is now true.

## Where the record is

Each finding, the commit that closed it and the artifact that holds it are in
`docs/open-work.md` under "The 8 October 2026 agent-efficiency audit". The
scorecard and the reading of the 8 October state it was written from are not kept
here: the finding table is the answer to "was this ever looked at", and a second
copy of it would be a second thing to keep true.

The rule F7 left behind is in `AGENTS.md` and holds for every later audit: a
real-feed defect gets the smallest synthetic record that reproduces it, added to
`make_synthetic_feed.py` with a comment naming the commit that fixed it.

## Not worth doing, and why

Four structural ideas were weighed and rejected in the same pass. They are the
part of this review that would otherwise be re-derived, so they are kept.

- **Moving the root Python modules into a package.** High import and CI churn,
  and the `AGENTS.md` map gets most of the orientation benefit.
- **Adding a Python type checker for page defects.** The defects live in
  JavaScript files, which Python types do not reach; `node --check` catches the
  syntax half of it.
- **Splitting `atoc_fares.py`.** It is 4,740 lines but changed 19 times in 150
  commits, a third of the page's rate. Length alone was not the cost F1 and F6
  were about.
- **Checking in real feed samples as fixtures.** The data is licensed (ADR-0005),
  so the synthetic fixture is the only regression test there is.
