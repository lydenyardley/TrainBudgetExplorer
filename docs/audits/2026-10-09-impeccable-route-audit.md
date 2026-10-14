# Non-dev route audit: the chooser, the station page, the privacy page

**Date:** 9 October 2026
**Commit reviewed:** `339abf7` on `main`
**Routes audited:** the three routes a release serves, plus the one-station
variant of the root. The dev-only builds (`_shape_site/`, `_demo_site/`) were not
audited.
**Method:** Impeccable `critique`, one design review per route, plus the bundled
detector over the built HTML, read in headless Chromium.
**Pruned:** 10, 11 and 14 October 2026. Twenty of this audit's twenty-two
numbered items are implemented: each is held by the commit that carries it
(`git log --grep="audit item"`), and the group-to-commit mapping for the first
twelve is in `1ecd719`. Item [15] was settled on 14 October 2026 by clearing the
privacy contact in `licences/release-clearance.md`, and items [16] and [18] had
already landed with the whole-app pass. The numbers keep their original values,
so a gap in the sequence is deliberate.

## The routes a release serves

A release is the set of routes its manifest names (ADR-0034), and the build
writes exactly three templates:

| Route | Template | What it is |
|---|---|---|
| `/` | `CHOOSER_TEMPLATE` | the root. A directory of every station this build priced, with one search field in the heading. When the build priced exactly one station the same template states that station instead of asking for it (the "release root"). |
| `/from/<slug>/` | `TEMPLATE` | the product: every destination inside the budget, as a table. |
| `/privacy/` | `_PRIVACY_TEMPLATE` | the notice, written from what the build ships. |

The station page is also the root of a one-station build by URL convention only.
A release always writes the chooser at `/` and the station under `from/`, so the
"release root" is a state of the chooser rather than a fourth template.

## Still open

- **[20] [P2] Every route the release serves should carry the notices the build
  was given.** `--notices nre,rdg,ogl,accuracy` reaches `render_page` only: the
  built chooser and the privacy page contain no licence or attribution wording at
  all, while the station page carries NRE and the Open Government Licence. There
  are two legitimate ways to close it, and they are written out in plain words
  under "What is waiting on a person" in `docs/open-work.md`, because choosing
  between them is a reading of the licence terms rather than a code decision.
- **[21] [P2] Make that invariant a build check, not a template accident.** The
  link crawl already proves every internal link resolves; a sibling check can
  prove every route in the release manifest carries the notices the build passed,
  and name the route that does not. **Open with [20]**, because the check's shape
  is the decision: record the position and the check refuses a route that shows a
  fare without its notices; render them everywhere and the check refuses any route
  without them.

Both are tracked in `docs/open-work.md`, which is the register for what is open.

## The detector's one finding, and why it is not one

`impeccable detect --json` on each built route reported one item, `cramped-padding`
on `.origin-slot-wrap` (children flush against a `border-bottom`), on the station
page only. It is a **false positive**: that border is the dashed underline that is
the station slot's entire affordance, chosen in `page/shared.css` precisely because
a text field's underline is the one shape a reader already reads as "this part of
the sentence is yours". The chooser and the privacy page scanned clean. A later
pass should not re-file it.
