# Non-dev route audit: the chooser, the station page, the privacy page

**Date:** 9 October 2026
**Commit reviewed:** `339abf7` on `main`
**Routes audited:** the three routes a release serves, plus the one-station
variant of the root. The dev-only builds (`_shape_site/`, `_demo_site/`) were not
audited.
**Method:** Impeccable `critique`, one design review per route, plus the bundled
detector over the built HTML, read in headless Chromium.
**Pruned:** 10, 11 and 14 October 2026. Twenty of this audit's twenty-two numbered
items are implemented: each is held by the commit that carries it
(`git log --grep="audit item"`), and the group-to-commit mapping for the first
twelve is in `1ecd719`. Item [15] was settled on 14 October 2026 by clearing the
privacy contact in `licences/release-clearance.md`, and items [16] and [18] had
already landed with the whole-app pass. The numbers keep their original values,
so a gap in the sequence is deliberate. This file holds the two items that are
still open.

## Still open

Both concern the same question, and both are tracked in `docs/open-work.md`,
which is the register for what is open. A release serves the chooser at `/`, the
station page at `/from/<slug>/` and the privacy notice at `/privacy/`.

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

## The detector's one finding, and why it is not one

`impeccable detect --json` on each built route reported one item, `cramped-padding`
on `.origin-slot-wrap` (children flush against a `border-bottom`), on the station
page only. It is a **false positive**: that border is the dashed underline that is
the station slot's entire affordance, chosen in `page/shared.css` precisely because
a text field's underline is the one shape a reader already reads as "this part of
the sentence is yours". The chooser and the privacy page scanned clean. A later
pass should not re-file it.
