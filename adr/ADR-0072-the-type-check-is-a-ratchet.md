# ADR-0072: The type check is a ratchet, not a cleanup

**Status:** Accepted
**Date:** 15 October 2026
**Relates to:** ADR-0031 (the cache keys are content digests), item 4 of the
14 October 2026 app-engineering audit, `tools/check_types.py`,
`tests/test_suppressions.py`

## Context

Every module in this repository is annotated and nothing read the annotations.
The 14 October 2026 engineering audit counted 20,471 lines of Python, 40
suppressions and 16 `# type: ignore` comments, and made the point that a
suppression nobody checks is a comment rather than a decision. Its item 4 asked
for a type checker in CI, and — because this repository has refused CI
dependencies so far — for the decision to be written down with its cost measured
rather than slipped into a workflow.

The cost, measured on 15 October 2026 with mypy 2.4.0:

| Command | Result |
|---|---|
| `python -m mypy --no-incremental $(every root module and tool)` | **350 errors in 29 of 70 files, in 7 seconds** |
| the same, `--strict`, over the build's own ten modules | **132 errors in those modules**, 287 in the 17 files that check pulled in |

The errors are not 350 separate mistakes. `atoc_fares_loader.FaresLoader` sets the
attributes its subclass `atoc_fares.FaresDb` reads, which is a mixin the checker
cannot see through, and that one pattern is **108** of them. `feed_audit`'s 42 and
`sanity_report`'s 23 are two more files' worth of untyped dictionaries. So
`--strict` over the tree is a typing project: it would touch the fares loader's
shape, the three report modules and the tools' argument plumbing, and it is a
change with its own measurement rather than a workflow step.

## Decision

The check is a ratchet. `tools/check_types.py` holds a list of the 27 files whose
own errors are already zero, runs mypy over exactly those files, and fails on any
error in one of them.

- **A file joins the list when its own errors are gone.** Growth is the direction;
  the list never shrinks without a reason written in the same commit.
- **A file that is not on the list is not checked.** A file with pre-existing
  errors is not made worse by being read, and failing on it would mean the check
  cannot land until the typing project does — which is how the annotations stayed
  unread.
- **`--all` prints the census and fails on nothing.** It is how the list grows and
  how the figure in `docs/build-performance-findings.md` is reproduced.
- **A check that could not run says so.** No mypy, or a mypy that reported nothing
  at all about files known to have been checked, exits 2 rather than 0.
- **It runs with `--full`, not with `--fast`.** The fast loop is what a developer
  runs while editing and it must not need a dependency they have not installed;
  `python -m tools.verify --full` and the deploy workflow's test job run it, and
  the workflow installs mypy for that reason.

## Consequences

- **CI gains its first test dependency.** `mypy` joins `coverage` in the workflow's
  test job and in nothing else. A release cannot publish on a type error in one of
  the 27 files; it can publish with the 350 that are still there, which is the
  point of a ratchet.
- **`# type: ignore` is now read.** The 16 in the tree are no longer decoration: a
  change that makes one of them unnecessary shows up as an `unused-ignore`
  complaint on a file that is on the list, and a change that needs a new one must
  say why in the same commit as the suppression it is (`tests/test_suppressions.py`
  holds that half for `# noqa`, and a `# type: ignore` sits in the same review).
- **The ratchet does not cover `page/`.** The page's JavaScript has no type
  checker here and this ADR does not add one; the browser suite is what holds that
  half.
- **The remaining 350 are someone's next pass, and they are measurable.** The
  census is one command and 7 seconds, so the question "is it worth typing the
  fares loader" can be answered against a figure rather than a feeling.
  `build_state.py`'s one error and `build_assets.py`'s three are the cheapest
  entries to take, and they are not taken here: adding a file to the list is a
  separate change with its own diff.
