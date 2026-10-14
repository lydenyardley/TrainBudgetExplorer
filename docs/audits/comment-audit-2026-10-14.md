# Comment audit

**Date:** 14 October 2026
**Scope:** the whole default branch: `git grep` over the tracked `.py`, `.js`,
`.css`, `.cjs` and `.html` files, plus spot reads of the blocks the counts
pointed at. Report-only when it was written.
**Pruned:** 14 October 2026, to what it asked for. The two findings that held up
were implemented the same day; the three that did not are kept below with the
reason, so a later reader does not re-derive them. The sizes and bucket splits
the report opened with are not kept: they were read off pattern heuristics
rather than counted comment blocks, so they said where to look rather than what
was there.

## What it asked for, and what landed

- **Encode the London code rule instead of narrating it.**
  `atoc_fares.py`'s `LONDON_STATION_CRS` carried a paragraph about the seven
  Underground, DLR and Overground codes that had lost their leading `Z`, and a
  second about seventeen entries later removed for naming stations the ONS
  workbook already classifies. Both rules are held by code, and the constant now
  names the checks instead of the incidents: `tests/test_atoc_fares.py`'s
  `test_every_london_code_is_one_the_feed_carries` pins the seven codes that
  carry the `Z` and the seven bare forms that must not be in the list,
  `test_a_reviewed_code_the_feed_does_not_carry_is_named` holds the dead-code
  record, and `tests/test_page_gates.py` holds that
  `--require-live-reviewed-codes` refuses a dead code and a redundant one. The
  validation the finding asked for already existed, so what landed was the
  deletion half.
- **Stop making a production import exist for a test's patch path.**
  `atoc_fares.py` held `import urllib.request  # noqa: F401` with a comment
  explaining that the tests stub the ONS, UNESCO and UKPRN readers by patching
  `atoc_fares.urllib.request`. Those readers live in `atoc_fares_loader.py`,
  which imports `urllib.request` for itself, so `mock.patch.object(urllib.request,
  "urlopen", ...)` is the seam the loader already calls: the tests patch that now,
  and the import, its `noqa` and its comment are gone. The injected-fetcher seam
  the finding proposed was not added: it would thread a parameter through four
  fetch sites to arrive in the same place.

## Decided against, and why

- **Extract the classification tables to data files with schema checks**
  (`MAJOR_UK_STATION_FALLBACKS`, `LONDON_STATION_CRS`,
  `REVIEWED_SETTLEMENT_FALLBACKS`, `REVIEWED_ATTRACTIONS_BY_FACET`). They are
  reviewed judgements with the reason written beside each group, and they are
  checked harder than a schema already: a code the feed does not carry and a
  code the workbook already classifies are both recorded, and
  `--require-live-reviewed-codes` refuses either. A file plus a schema would
  replace type-checked literals with file I/O and a second definition of the
  shape, for a list a person reads and reviews rather than a machine consumes.
- **`page_templates.py` is "templates explained in prose; use named template
  helpers."** The templates are literal HTML whose comments say why a shape is
  what it is -- why the station slot is a field, why the footnote sits where it
  does. A helper per fragment would separate the markup from its reason and make
  the bytes a reader has to trust harder to follow, and those bytes are what the
  page tests, the byte budget and the browser suite read.
- **Turn `tests/test_atoc_fares.py`'s long test preambles into test names or
  parametrized ids.** Those comments are the "why" this repository asks for, and
  a parametrized id cannot carry the paragraph that says which real-feed shape a
  case came from. Nothing in the audit named one that failed to earn its place.

## What it got wrong

The report said the tree holds no suppressions. It holds 54 `# noqa` comments and
16 `# type: ignore` comments. `atoc_fares.py`'s was worth removing because it
existed for a test rather than for a tool, which is a reason about that import
and not about suppressions in general.
