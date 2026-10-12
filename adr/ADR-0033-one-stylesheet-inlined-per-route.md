# ADR-0033 — One stylesheet source, inlined into every route

**Date:** 27 September 2026
**Status:** accepted; amended 30 September, 1 October and 12 October 2026 (see below)

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
byte-identical on every station page are larger still — **126.2 KB**, measured
over 963 pages of a real network build: this block, the theme block and the theme
control, the chevron, the list-key block, the station page's own stylesheet and
its script, and the picker's handling. **This figure is superseded on 1 October
2026; see the second amendment below.**

*(Superseded on 1 October 2026: the 119.3 KB above was measured before the
picker's list moved into `stations.js` and before the payload gained its value
pool, and the ~309 MB of ~1.6 GB was a projection from it. A whole-network build
of all 2,712 pages now measures **583 MB** — the projection was low by nearly a
factor of three, and wrong in the safe direction only by accident. The 126.2 KB
is what the same measurement gives on the current build.)*

**The boundary, which is what the one exception needs.** A route carries in its
own file everything that is *its own answer*: the destination rows, the fares,
the provenance and the notices, the destination facets, and everything a reader
needs to read the page. A route may fetch a document that is the same for every
route and is not part of that route's answer. There is exactly one such document
today:

- **`stations.js`, the station picker's options** — the same 2,712 rows on every
  station page but the one row each page filters out, 295 MB of the projected
  network sent 2,712 times over before it moved (audit recommendation 1d).
- **`station-<digest>.css`, the station route's stylesheet** — the shared block
  and the station route's own rules, byte-identical on all 2,712 station pages
  and 92.6 MB of the network before it moved (ADR-0047, 1 October 2026). Named
  for a digest of its own bytes, so a changed stylesheet is a new file.

The script stays inline until a decision moves it, and if it moves it moves under
this same boundary. A requirement follows from the boundary
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

## Amendment — 1 October 2026: a whole-network build, and the second document

The 30 September amendment was written from 963 pages and a projection. The
projection is retired, because a build of the whole network now exists and
disagrees with it: **583 MB over 2,714 pages against the 800 MB budget**, from

```
python build_demo_page.py --feed feeds/fares --fast-all-origins \
  --notices nre,rdg,ogl,accuracy --out _cache/site_measure/index.html
python tools/page_bytes.py --site _cache/site_measure
```

Six minutes on eight workers, 2,712 station pages, and the tool exits 0. What
the projection had wrong was the picker's list, which is 168 KB once in
`stations.js` rather than 295 MB spread over the network, and the payload
encoding that shrank every page since. Nothing about the boundary above needed
to move for that, but one document has joined it.

**What a station page fetches now.** Two documents, neither of them part of any
page's answer: `stations.js` and the station route's stylesheet. The chooser and
the privacy page fetch neither, because two pages are not worth a request. The
script stays inline, and the reason is the one thing this boundary cannot
absorb: the script draws the page's own payload, so its absence leaves a shell
rather than an unstyled page. ADR-0047 records that measurement and the
alternative considered.

**What the boundary now costs, and what it bought.** The site went from 583 MB
to **498 MB**, and the bytes identical on every station page from 126.2 KB to
**93.9 KB**, which is the script alone. A mean page is 192,167 bytes against a
mean payload of 69,936: the payload is now 37% of a page rather than 32%, and
the page is 12% smaller than it was before any of this.

The claims that stand unchanged: the single source (the block is still written
once, in `page_templates.SHARED_CSS`, and the asset is that block plus the
station route's own rules); `with_shared()`'s substitution, and its refusal; and
the test that each route carries the shared block rather than a lookalike — which
for the station route is now the test that it *links* the one file, whose name is
a digest of the bytes it serves.

## Amendment — 12 October 2026: the script moves under the same boundary

The 1 October amendment left the script inline for the reason ADR-0047 gave:
its absence is a shell page, and the boundary could not absorb that without a
second renderer. The 12 October build-cost audit measured the script at
**149,377 bytes byte-identical on every one of 24 sampled pages** — the whole
of the 93.9 KB above plus eleven days of growth — and a whole-release
projection of 827 MB against the 800 MB budget, so the decision had to be
asked again.

**What moved.** Both routes' scripts ship as one hashed asset each beside the
stylesheet: `station-<digest>.js` for the station route, `chooser-<digest>.js`
for the chooser. Each page inlines only its own answer — the station page its
`DATA`, the chooser its station list — as a small block the asset reads, so
the bytes the browser keeps are the same on every page of the route. The
one-file promise now reads with three named exceptions (`stations.js`, the
stylesheet, the route's script) rather than two, and the boundary above is
unchanged: a route carries its own answer, and fetches what is the same for
every route.

**The failure branch instead of the second renderer.** ADR-0047's reason
against moving the script was that its absence is a shell page. That is still
true, and there is still no second renderer: what the move adds is the failure
branch the stylesheet already had. A page whose script does not arrive reveals
its own missing-script note through the script tag's `onerror` and leaves the
table empty rather than filling it with nothing, and the browser suite
withholds the asset on a second page and asserts both. The requirement stands
as written — a route whose shared document does not arrive stays readable and
truthful — and the script is now held to it rather than exempted from it.

**Measured.** Birmingham New Street, same feed, same prices-only shape:
261,362 bytes on 10 October 2026 → 112,885 bytes, a saving of 148,477 per
page. At 2,712 pages that is about 385 MB the release no longer carries
(`docs/build-performance-findings.md`). The per-page figure leans on the
byte-identity measurement above, per ADR-0032.
