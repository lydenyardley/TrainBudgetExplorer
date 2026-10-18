# Impeccable critique: the chooser, the station page, the privacy page

**Date:** 14 October 2026
**Commit reviewed:** the worktree at `9bb8e01` plus that day's uncommitted work (the
derived build-source lists).
**Mode:** Operate. Every route is a tool a reader uses to answer one question, and
the design's job is to get out of the way of the answer.
**Routes criticiqued:** `/` (the chooser), `/from/grantham/` (a station page with
fares), `/privacy/`. A prices-only station page (`_shape_site/prices-only/`) was
built and read for its empty states.
**Method:** ⚠️ DEGRADED: single-context (no sub-agent tool is exposed to this
session, so the design review and the detector evidence were run sequentially
rather than as two isolated assessments). The bundled detector was run over the
built HTML; the live pages were read in Chromium through this thread's preview —
computed styles, geometry, accessible names and console output. **No screenshots:**
the preview webview produced no composited frames in this environment, so every
finding below is measured from the live DOM rather than seen. A visual pass with a
screenshot-capable browser is still owed.
**Pruned:** 15 October 2026, again on 16 October 2026 when item 5 was settled, and
again on 18 October 2026 when item 7 landed. Recommendations 1, 2, 4, 6 and 7 are
implemented, and 3's first half with them; each is held by the test named beside it
in the table below, and the commits that carry them are found with
`git log --grep="critique item"`. The numbers keep their original values, so a gap
in the sequence is deliberate, and what is left is what still asks for something:
3's second half and 8.

## Still open

- **[3, second half] [P2] A 15-option decision point.** The dead ends are gone
  (each of the three chips that selected an empty list is no longer offered), but
  the group is still `All` plus fourteen chips at one decision point, well past
  the four a reader holds at once. What is left of the fix is the arrangement:
  group the four settlement bands ahead of the ten thematic facets behind one
  "More types" disclosure.
- **[8] [P3] No accelerator for the page's one job.** The primary action is
  setting the budget, and it is reachable only by tabbing through the heading
  controls or grabbing the slider. Fix: `/` or `b` to focus the budget field,
  `n`/`p` for the next and previous page, and say so in the folded bar's summary
  line.

## What landed

| Recommendation | Closed by | Held by |
|---|---|---|
| [1] [P1] the chooser printed the download date twice | the provenance is a structured pair — the source names the feed, the date travels beside it, and each route composes one sentence from the two | `tests/test_build_chooser.py`'s entry-provenance test, `build_demo_page.dtd_download_entry`, `page/station/provenance.js` |
| [2] [P1] two counts for one question | the count is the places the page carries, two-ticket rows included: measured on the real feed, Grantham's 50 became 334, and the number a reader arriving from the chooser sees is now the page's own set | `tests/test_build_demo_page.py`'s `test_the_count_is_every_place_this_page_carries`, `tests/test_page_caches.py`'s timetable-key test, `build_demo_page._priced_destinations` |
| [3, first half] [P2] three of fourteen chips could not succeed | a chip is offered only when a destination of its type is inside the budget on screen, which is the same rule the count beside it already stated | `tests/browser/station-filters.cjs`'s chip checks, both directions, `page/station/filters.js`'s `syncDestinationTypeChips` |
| [4] [P2] the empty state named the budget and not the cause | the count line names the active refinement in the same words the paragraph below the table uses, and the empty state's own "Clear the destination type" is one press away | `tests/browser/station-filters.cjs`, `page/station/table.js`'s `render` |
| [6] [P3] the smallest type on the page was 11.52px | `.75rem` is the floor for type on this route, and the letter-spacing carries the small-caps effect | `tests/test_page_assets.py`, `page/station.css` |
| [7] [P3] the fare vocabulary had no home | the words the route quotes are defined once, in a definitions list inside the method disclosure, immediately below the provenance line — which is the "block beside the provenance" this recommendation offered as its first option, drawn as the second (clarity audit item 44 chose the same answer from the other end) | `tests/browser/station-render.cjs`'s "the trade words the page quotes are defined together, in the method disclosure", `page/station/provenance.js` |
| [5] [P2] the routes that show no fares carry no licence notices | settled on 16 October 2026 as a reading, not a change: the credit travels with the page that shows a fare, the chooser's station index and the privacy notice show none, and the alternative reading is named beside it in the record. The build check the same reading asked for landed with it, and it closes route audit items [20] and [21] | the section "Which pages carry the acknowledgement" in `licences/release-clearance.md`, `tools/check_source_credit.py`, `tools/test_check_source_credit.py` |

## The detector's one finding, and why it is not one

`impeccable detect --json` over the built chooser, station page and privacy page
returned one finding, `cramped-padding` on `.origin-slot-wrap` (children flush
against a `border-bottom`). It is a **false positive**: that border is the dashed
underline that is the station slot's whole affordance, chosen in
`page/shared.css` precisely because a text field's underline is the one shape a
reader already reads as "this part of the sentence is yours". The 9 October route
audit recorded the same finding and reached the same verdict, and a later pass
should not re-file it.

## Run notes

Target slugs: the three built routes above. Ignore list: `.impeccable/critique/ignore.md`
does not exist, so nothing was suppressed. Assessment independence: not achieved
(single context, banner above). CLI detector: one finding, false positive, not
re-filed. Browser: Chromium via this thread's preview at `127.0.0.1:8899`; the
server and its preview are left running for the next pass. Screenshots: unavailable
(no composited frames) — DOM, computed style and layout measurements used instead.
Temp files: the diagnostic script used during this session was deleted; the real-feed
build under test lives in the system temp directory, not the repository.
