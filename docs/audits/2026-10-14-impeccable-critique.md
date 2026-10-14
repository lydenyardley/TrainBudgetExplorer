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

## Design health score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 4 | Count line is `aria-live`, the pager says `1 of 5 pages`, the day is named, the folded bar carries what is currently narrowed. |
| 2 | Match between system and real world | 3 | "53 destinations" is counting fare rows, and the chooser answers the same question with 50 (recommendation 2). |
| 3 | User control and freedom | 4 | Budget, day, ticket type, party, chips, station picker, shortlist clear — every choice is reversible in place. |
| 4 | Consistency and standards | 3 | One shared stylesheet and one component per job, but the station route carries licence notices and the other two carry none (register item [20]). |
| 5 | Error prevention | 4 | The budget clamps, the picker only offers stations the build has pages for, and a build refuses rather than publishing a page without its notices. |
| 6 | Recognition rather than recall | 3 | The destination-type group is 15 options at one decision point, three of them dead ends (recommendation 3). |
| 7 | Flexibility and efficiency | 3 | No keyboard accelerator for the primary action; paging is one page at a time. |
| 8 | Aesthetic and minimalist design | 4 | The refinements fold away by default and the default view is almost entirely the answer. |
| 9 | Error recovery | 3 | The empty state names the budget and not the refinement that emptied it (recommendation 4). |
| 10 | Help and documentation | 3 | The provenance, the address-bar notice and the feed record are excellent; the three fare words are explained only inside a row's panel. |
| **Total** | | **34/40** | Good — 85% of the scale, with the gaps concentrated in wording, not in structure. |

## Design specificity verdict

**Authored for this product, not for the category.** Three things could not be
lifted onto another site unchanged: the heading *is* the query (the budget field
and the station slot are words inside the sentence, with a dashed underline
instead of a label), a row's price is stated with its ticket type and its
condition, and the page refuses to imply a recommendation — no "best" tint, no
sorted-by-our-opinion badge, the order is stated in words in the count line. The
palette and the component vocabulary are quiet and consistent across routes.

**Deterministic scan.** `impeccable detect --json` over the built chooser, station
page and privacy page returns **one** finding: `cramped-padding` on
`.origin-slot-wrap` (children flush against a `border-bottom`). This is the false
positive the 9 October route audit already recorded — that border is the dashed
underline that is the slot's whole affordance — and it should not be re-filed.
Nothing else was detected, including on the real-feed build (354 KB station page).

## What's working

- **The heading as a sentence.** Measured on the real Grantham page, the budget
  field is `2ch` wide with a `1.5rem` floor and the station field is
  content-sized — a word in a sentence, not a form control. This is the page's
  whole idea and it survives contact with real data.
- **Accessibility is measured, not asserted.** Every text element sampled in both
  colour schemes came back at **8.25:1 or better** (body 14.89, muted tag 8.29,
  station code 8.29, interchange 8.29, restricted fare 9.59, footer 8.29), and no
  control among the 34 on the station page fell below 44px in either dimension. At
  390px the table becomes stacked cards and the document does not scroll sideways
  (`scrollWidth` 374 of 390); at 615px it does not either (598 of 615).
- **Nothing hides without saying so.** The refinements fold, and the toggle
  carries a live summary — "Filter this list · Ticket: Cheapest of any type ·
  Travellers: One adult, 0 railcard · Destination: All" — so a folded bar is
  never a hidden filter.

## Numbered recommendations

Deduplicated against the open register. Items [20] and [21] of the 9 October
route audit are *not* repeated here; they are still open and this pass found them
still present (see item 5).

1. **[P1] The chooser prints the download date twice.** Built bytes, real-feed
   build: `Prices from the National Rail Data Portal DTD fares feed, downloaded
   24 September 2026 downloaded 24 September 2026.` The station page prints it
   once. Cause: `render_chooser` appends `downloaded {feed_date}` to a
   `price_source` that already ends in its own download date (both
   `price_source_from_metadata` and `price_source_from_manifest` return the date
   inside the sentence). Fix: give the provenance a *structured* pair — source,
   date — and let each route compose one sentence from it. This is the first
   sentence a reader arriving from a community post sees.
2. **[P1] Two counts, one question.** The chooser says `50 destinations` for
   Grantham; its own station page says `53 destinations for up to £20.00 each,
   cheapest first: 47 singles, 6 returns`. They are computed by different paths
   (`build_station_index` over `priced_destinations_within(…, EVERYTHING_PENCE)`
   against the page's own rows), and the split suggests the page is counting
   *fare rows* under the word "destinations". For a product whose promise is a
   number, a reader who notices has lost the number. Fix: either make them the
   same count, or word them as what they are — "50 places this site prices" and
   "53 fares under £20" — and let the count line's own split match its noun.
3. **[P2] A 15-option decision point, three options of which cannot succeed.**
   The open destination-type group is `All` plus 14 chips; on this origin
   `Coastal & seaside (0)`, `Islands (0)` and `National parks and landscapes (0)`
   select an empty list. Fifteen visible options is well past the four a reader
   holds at once. Fix, cheapest first: the count is already in the label, so hide
   (or disable) chips with no matches for this origin; group the four settlement
   bands ahead of the ten thematic facets behind one "More types" disclosure.
4. **[P2] The empty state names the budget and not the cause.** After choosing
   `Coastal & seaside (0)` the line reads `No destinations for up to £20.00
   each`, the pager reads `1 of 1 page · 0 destinations`, and the control that
   would recover it (`Clear destination types`) is back inside the folded panel.
   Fix: name the active refinement in the empty state ("No coastal & seaside
   destinations from Grantham within £20") and put the clearing action in it.
5. **[P2] Still open from the register, verified live.** The station page carries
   the NRE credit, the Open Government Licence and the Knowledgebase credit; the
   chooser and the privacy page carry none — the privacy page's footer is a
   single "Station list" link. This is items [20] and [21] of
   `docs/audits/2026-10-09-impeccable-route-audit.md`, held open in
   `docs/open-work.md` pending a reading of the licence terms. No new item.
6. **[P3] The smallest type on the page is 11.52px.** The uppercase filter-group
   labels (`0.72rem` with `.08em` letter-spacing) are the hardest text to read on
   a page whose body is 16px. Fix: raise the floor to `0.75rem` and let the
   letter-spacing carry the small-caps effect.
7. **[P3] The fare vocabulary has no home.** "Regular", "Restricted", "Advance",
   "changes", "two tickets" and the minimum-fare note are explained inside a
   row's own panel, one disclosure at a time. A reader comparing six rows is
   holding words they have not been given. Fix: one short "what these words mean"
   block beside the provenance, or a definitions list the row links to.
8. **[P3] No accelerator for the page's one job.** The primary action is setting
   the budget, and it is reachable only by tabbing through the heading controls or
   grabbing the slider. Fix: `/` or `b` to focus the budget field, `n`/`p` for the
   next and previous page, and say so in the folded bar's summary line.

## Persona red flags

**Jordan (first-timer)**: the three words that decide which rows are cheap —
"Regular", "Restricted", "Advance" — appear in a column with no definition above
them (recommendation 7); the chooser sentence that should orient them repeats
itself (recommendation 1).

**Sam (accessibility-dependent)**: the sampled contrast and the 44px floors are
genuinely good, and the count line is announced politely. The gap is the chips: 15
choices in one fieldset with the dead ends offering a result the page cannot
produce (recommendation 3).

**Riley (stress tester)**: a chip with `(0)` is the visible edge case, and choosing
it yields a correct but unhelpful state (recommendation 4). The 50-versus-53
disagreement between two routes is the hidden one (recommendation 2).

## Minor observations

- The station page's own lede honestly states a single-origin build ("This is the
  only station this build has pages for, so the name above is not a link") — good,
  and the same honesty is why the counts in recommendation 2 stand out.
- The day control offers two days from the timetable window; the label row reads
  "Times for", which is the right register for a table whose times are one day's.
- The privacy page is 402 words across five headings and states the build date it
  describes — unusually good for the genre.

## Run notes

Target slugs: the three built routes above. Ignore list: `.impeccable/critique/ignore.md`
does not exist, so nothing was suppressed. Assessment independence: not achieved
(single context, banner above). CLI detector: one finding, false positive, not
re-filed. Browser: Chromium via this thread's preview at `127.0.0.1:8899`; the
server and its preview are left running for the next pass. Screenshots: unavailable
(no composited frames) — DOM, computed style and layout measurements used instead.
Temp files: the diagnostic script used during this session was deleted; the real-feed
build under test lives in the system temp directory, not the repository.
