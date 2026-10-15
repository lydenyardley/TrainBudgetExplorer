# ADR-0047 — The station route fetches one hashed stylesheet

**Date:** 1 October 2026
**Status:** accepted; amended 12 October 2026 (see below)

## Context

The 30 September amendment to ADR-0033 measured the network and left the
stylesheet where it was, on the strength of a projection: 119.3 KB identical on
every page, ~309 MB of a projected ~1.6 GB, against a target of 800 MB. The
projection was the picker's station list, which has since moved into
`stations.js`, so the first question had to be asked again against a build that
exists rather than an extrapolation.

It was asked against the whole network. `python build_demo_page.py --feed
feeds/fares --fast-all-origins --notices nre,rdg,ogl,accuracy --out
_cache/site_measure/index.html` wrote all 2,712 station pages plus the chooser
and the privacy page in six minutes on eight workers, and
`python -m tools.page_bytes --site _cache/site_measure` reports **583 MB of the
800 MB budget**. The target is met with 217 MB to spare, so nothing *has* to
move. What is left is a judgement about the shape of that headroom:

- The bytes identical on every page are **126.2 KB** — the same 34.6 KB of CSS
  and the same 91.6 KB of script — which is **58.9% of a mean 214 KB page**.
- The stylesheet is 92.6 MB of the 583; the script is 242.4 MB.
- A mean page is 219,234 bytes; the smallest is 152,679 (SWR Origin, one row)
  and the largest 519 KB (Stratford International, 1,678 rows).

So the decision is not "does the release fit" — it does — but "is 92.6 MB of
one file, repeated 2,712 times, the right way to hold 16% of the site".

## Decision

1. **The station route's stylesheet becomes one hashed asset beside the pages.**
   The build writes it once, next to the picker's asset, and every station page
   names it with a render-blocking `<link>`. Its bytes are
   `page_templates.STATION_STYLESHEET`: the shared block, then this route's own
   rules, which is exactly what the inline `<style>` element held. ADR-0033's
   single-source rule is untouched — the block is still written once, and a
   route's own rules still live in the route.

2. **The name is a digest of the stylesheet's own bytes:**
   `station-<12 hex of sha256>.css`. A changed stylesheet is therefore a new
   file, so a cached copy can never be served beside a page built from another
   revision of the CSS, and no build step has to be told to rename anything or
   to be invalidated by hand.

3. **A `<link>`, not a script that injects a `<style>` element.** The page is
   styled before it is painted, so there is no flash of plain text, and a reader
   with no JavaScript still gets the layout and the dark palette.

4. **The chooser and the privacy page keep inlining their blocks.** Two pages,
   34 KB between them, and their CSS is not byte-identical to the station
   route's; fetching a file to save 34 KB once is a worse trade than the request.

5. **The script stays inline, and this is the interesting half.** The shared
   document that *would* save 242.4 MB is the page's own script — but that
   script is what draws the page's own inline payload. A request that did not
   arrive would leave a page with an empty table, a count line that never fills
   and controls that do nothing: not an unstyled page, a shell. ADR-0033's
   requirement is that a route whose shared document does not arrive stays
   readable and truthful, and on this document that cannot be met without paying
   the bytes straight back in a second renderer that draws the rows without the
   script. So the document that moves is the one whose absence costs a reader
   nothing but appearance.

6. **The failure mode is the picker's, one route down.** The stylesheet sets
   `--tbe-stylesheet: 1`; the page reads that token, so the answer is the
   browser's own rather than a guess about whether a request is still in flight.
   If the token is absent when the body exists, the page **removes** the theme
   switch rather than leaving a control that rewrites an attribute no rule reads,
   and shows one sentence saying its styling did not load and that every price,
   time and restriction is still there. The check is made again on `load`,
   because a stylesheet still arriving when the body exists has not failed yet.
   `tests/browser_test.cjs` withholds the document on a second page in the same
   context and asserts all three: the rows are still listed, the switch is gone,
   and the page says why.

## Consequences

- The site measures **498 MB of the 800 MB budget** over 2,714 pages, down from
  583 MB. Both numbers come from `tools/page_bytes.py` over a full-network
  build, before and after. The stylesheet accounts for 92.6 MB of it
  (36,283 bytes × 2,712, the byte count of the file as written on Windows);
  the remaining ~7 MB is this change's own addition to the shared script, which
  every page carries.
- A mean station page is **192,167 bytes**, down from 219,234; the median is
  189,579, the smallest 122,172 (SWR Origin, one row) and the largest 511,561
  (Stratford International, 1,678 rows). A page's payload is unchanged at a mean
  of 69,936 bytes, which is now 37% of the page rather than 32%.
- `tools/page_bytes.py` no longer finds CSS in a station page, because there is
  none to find. Its "identical on all measured pages" figure is now the script
  alone, which is the point: the number was always meant to be the ceiling on
  what a shared document could save, and the stylesheet is no longer inside it.
- A station page is one HTML file plus one cached stylesheet. It is still one
  file to publish, one file to lint and one file to read, and the site is still
  static files with no server of its own — but it is no longer true that a page
  renders from its own bytes alone in the unstyled case, and
  `PRODUCT.md`'s "one self-contained HTML file: no external assets" now reads
  with the two named exceptions below rather than without any.
- The link crawl reads `src` as well as `href`, and every written file counts as
  a route. A page could previously have asked — in a `<script src>`, which the
  crawl never looked at — for a file the build did not write, and the run would
  have said every internal link resolves.
- The browser suite serves the page's stylesheet from beside the page on disk,
  the way it already served the picker's asset, and serves it as `text/css`: a
  stylesheet served as anything else is not applied at all, and the suite would
  otherwise have been measuring an unstyled page while reporting the checks an
  unstyled page fails.
- The test that asserted every route inlines the shared block now asserts what
  the decision left standing: one source, two routes inlining it, one route
  fetching it, and the link resolving to a file whose name is a digest of the
  bytes it serves.

## Alternatives rejected

- **Both documents in one asset, fetched by script.** The user's first framing,
  and the one this record answers rather than adopts: one request instead of
  two, at the price of a stylesheet a browser cannot apply before it runs the
  script — an unstyled page with JavaScript off, and a flash of plain text on
  every page view for everyone else.
- **Both as two assets.** The honest full move, and it fails the same place for
  the same reason: the script's absence is a shell page, and the fix is a second
  renderer rather than a failure branch.
- **Neither: keep 583 MB and the literal promise.** Defensible — the target is
  met with 217 MB to spare, and a release that is inside its budget does not
  need a second document. Rejected because the 92.6 MB is a fifth of what the
  project holds itself to, in a form that never grows: the picker's list was
  bigger and was moved for the same reason, and a station page that renders from
  its own bytes is a page that cannot be served from a cache at all.

## Amendment — 12 October 2026: decision 5 is superseded, the script moves

Decision 5 above kept the script inline because its absence is a shell page
and the boundary could not absorb that without a second renderer. The 12
October build-cost audit re-asked it against a measurement — 149,377 bytes
byte-identical on every one of 24 sampled pages, an 827 MB whole-release
projection against the 800 MB budget — and the answer changed without the
reason being wrong: the absence is still a shell page, and there is still no
second renderer. What changed is that the shell now says so. The script tag's
`onerror` reveals the page's own missing-script note and the table stays
empty rather than filling with nothing, which is the picker's failure mode
one route down rather than a renderer. The browser suite withholds the asset
and asserts both, the way it withholds the stylesheet.

The chooser's script moves with it (T10): one `chooser-<digest>.js` beside
the release rather than a copy inside the one page that carries it, because
both routes' scripts come out of the same machinery and the two should move
or stay together rather than by halves. A rebuild removes the hashed files
no file in the folder names (T11): a changed asset is a new name, so five
stylesheets had accumulated in `_site/` beside the one the pages named. A page
the build left alone -- an earlier build's station, named rather than deleted --
keeps the asset it requests, and a page is rewritten whenever its markup would
change, not only its payload, so no page the build kept names a pruned file.

The decision that stands unchanged: a changed stylesheet is a new file, the
`<link>` rather than an injected element, and the failure mode above — which
the script now shares rather than being exempt from.
