# ADR-0033 — One stylesheet source, inlined into every route

**Date:** 27 September 2026
**Status:** accepted; amended 30 September 2026 (see below)

## Context

The site is three routes — the chooser at the root, a station page under
`/from/<slug>/`, and the privacy page — and each one carried its own `<style>`
block. They had grown apart. The chooser had no `--ochre` in its dark palette
and no focus ring; the privacy page had no `--field` and no `[hidden]` rule;
the station page had no `.brand` and restated `input[type=search]`, `.sr-only`,
`footer` and `.footnav` in its own words. A reader who moved from a station page
to the chooser met a different focus ring and different muted text, and nothing
in the build could notice.

The constraint that stops the obvious fix is the site's own: every route is one
self-contained file with no external asset, so there is no stylesheet to link
and nothing a browser could fetch.

## Decision

1. **`page_templates.SHARED_CSS` is the single source** for the tokens and
   components every route uses: the light and dark palettes, the box model,
   body and heading typography, links, the focus ring, the selection colour,
   `.muted`/`.tag`/`.disclosure`, the brand line, the back link, the shared
   input styling, the footer and its nav, and `.sr-only`.
2. **It is inlined at import time.** `with_shared_css()` substitutes the block
   into each template and raises if a template still holds the placeholder, so
   a route cannot ship unstyled text and a forgotten substitution is an error
   rather than a page.
3. **A route states only what is its own.** Where a route genuinely differs it
   sets a token — `--page-max`, `--page-pad`, `--h1` — rather than restating a
   rule. The station page is wide and has a table; the chooser is a single
   column with a small heading; the privacy page takes the defaults.
4. **Unifying does not mean flattening.** A style that only one route uses stays
   in that route's block, and the station page keeps its own rules for the
   table, the drawer, the shortlist and the reflow.

## Consequences

- The chooser, a station page and the privacy page cannot drift: they carry the
  same bytes, and a test asserts that each rendered route contains the shared
  block rather than a lookalike.
- Adding a token is a one-line change that reaches every route, which is what
  the audit's S39 asks for.
- A route's `<style>` block is now short enough to read top to bottom, and what
  is left in it is what is actually specific to that route.
- The site still ships one file per route with no external asset. The cost is
  roughly 3 KB of duplicated CSS in each file, which is the price of the
  self-contained guarantee rather than an accident.

## Alternatives rejected

- **A shared `styles.css` fetched by every page.** Breaks the no-runtime-assets
  promise, adds a request and a failure mode to a page whose whole argument is
  that it works from a file.
- **A build step that concatenates CSS into a cache file.** The build already
  writes one file per route; a second artefact would need its own staleness
  rules for no gain over a Python string substitution.
- **Keep three `<style>` blocks and add a test that they match.** A test can
  catch drift once it is written; a single source cannot drift at all, and the
  test is still worth having to catch someone pasting a rule back into a route.

## Amendment — 30 September 2026: what a route may fetch

The consequence recorded above ("roughly 3 KB of duplicated CSS") is stale, and
the guarantee now has one exception, so both are stated here rather than left
implied. Every figure is measured by `tools/page_bytes.py`, which is the tool the
release argues its byte budget from.

**The price of the guarantee, measured.** `SHARED_CSS` is 15.9 KB, not 3 KB, so
the shared block is about five times what this ADR recorded. The bytes that are
byte-identical on every station page are larger still — **119.3 KB**, measured
over 963 pages of a real network build: this block, the theme block and the theme
control, the chevron, the list-key block, the station page's own stylesheet and
its script, and the picker's handling. Across the projected 2,712-page network
that is ~309 MB of ~1.6 GB, about a fifth.

**The boundary, which is what the one exception needs.** A route carries in its
own file everything that is *its own answer*: the destination rows, the fares,
the provenance and the notices, the destination facets, and everything a reader
needs to read the page. A route may fetch a document that is the same for every
route and is not part of that route's answer. There is exactly one such document
today:

- **`stations.js`, the station picker's options** — the same 2,712 rows on every
  station page but the one row each page filters out, 295 MB of the projected
  network sent 2,712 times over before it moved (audit recommendation 1d).

The stylesheet and the script stay inline until a decision moves them, and if they
move they move under this same boundary. A requirement follows from the boundary
rather than being a separate promise: **a route whose shared document does not
arrive stays readable and truthful.** The picker's failure mode is that rule's
shape — the heading's control is replaced by the station's name as text, the
panel is removed rather than left empty, and the first-use sentence is rewritten
— so no reader meets a heading reading "from" and nothing, or a control that
opens nothing. A build that ships the list inside the page cannot reach that
state at all.

Nothing else changes. The single-source rule above stands, `with_shared()`'s
substitution stands, and the tests that prove each route carries the shared block
rather than a lookalike stand: what this amends is the claim about external
assets, not the claim about where the stylesheet comes from.
