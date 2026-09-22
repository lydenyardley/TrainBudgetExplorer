# ADR-0019: One page per station, and the origin as the artifact's identity

**Status:** Accepted
**Date:** 22 September 2026
**Relates to:** ADR-0001 (data sources), ADR-0003 (discovery and the SEO gate),
ADR-0004 (the staged plan and its Grantham-only scope), ADR-0005 (the account
blocker), ADR-0010 (one self-contained page, no server), ADR-0014 (per-destination
pages rejected), ADR-0018 (the page's default link)

## Context

ADR-0004 scoped v1 as a Grantham-only demo, with the Grantham sweep as the go/no-go
instrument. The origin scope was reopened during shaping and the owner has chosen
the other way: the tool must work from **any** UK station, and v1 should launch with
all of them rather than one.

**The data is not the constraint.** The fares feed already holds every flow, so the
same feed answers every origin; `destinations_within()` already takes any origin
code. What breaks is *delivery*: the artifact is one self-contained HTML file, and
it has held exactly one origin until now.

Measured from the page's own payload: **~357 bytes per priced destination.**

| approach | arithmetic | verdict |
|---|---|---|
| every origin in one file | ~2,500 origins × ~1,000 priced pairs × 357 B ≈ **~890 MB**, before journey times | not a page |
| the same reduced to bare integers | ~5 MB for prices alone | loses names, fare codes, and every journey time, and times are a second matrix of the same size — it stops being this product |
| **one page per station, plus a station index in each** | ~110–420 KB per page, ~60–100 KB of it the index | **the answer** |

## Decision

1. **One self-contained HTML page per priceable station.** The origin is the
   artifact's identity, not a filter inside it.
2. **The picker is driven by a station index** — name, code, and the address to
   follow, measured at 19–32 bytes per station, so roughly 60 KB for the whole
   network as bare pairs and roughly 100 KB once each entry carries its readable
   path. **Choosing a station is navigation**: a link to the neighbouring file.
3. **The index contains only stations the build could price**, so no option is ever
   selectable-and-empty. A station with no priced flows is absent rather than
   offered and then refused.
4. **The root address shows the chooser itself.**
5. **v1 launches with all priceable stations.** This replaces ADR-0004's
   Grantham-only scope *for the artifact*. ADR-0004's staged plan, its two dates,
   and its park-by-default tripwire are unchanged.
6. **This is an extension, not a new visual world.** The existing tokens, table,
   controls, and honesty notes are inherited; there is no identity exercise here and
   DESIGN.md is not rewritten for it.

### The origin-selection flow (shaped and confirmed, 22 September 2026)

7. **The origin is a property of the file; the picker is a control that produces
   navigation, and holds no state.** Which origin the page is about is fixed in the
   `<h1>`, the payload, and the address. Choosing one *leaves* the page, so the
   reader's undo is the back button and there is never an origin on screen that
   contradicts the file it came from.
8. **The destination filter stays in-page state.** One control changes the page you
   are on and the other leaves it; that asymmetry is the flow's largest
   comprehension risk and is separated by position and grammar, not by relabelling:
   the origin sits **above** the controls as page identity ("Where can we go from
   Grantham?" plus a quiet *Change*), while the destination filter stays **inside**
   them ("Prefer a city or town?").
9. **The picker is a search field over real links** — a filtered `<ul>` of anchors,
   not a custom listbox — so arrow keys and Enter are the browser's own and `<a>`
   carries the accessible name. A `<select>` is refused: 2,500 options cannot be
   searched. No match states what was tried and suggests a name or a three-letter
   code; duplicate station names are shown with their codes, because the feed's
   location records carry no county to disambiguate with.
10. **The station index ships in every page**, confirmed over the cheaper
    root-only variant: the commonest reason to use the picker is landing on the
    wrong town, and making that reader take a round trip to fix it is the worse
    cost.
11. **A station page's address is a readable slug: `/from/grantham`**, with the root
    address holding the chooser. Slugs are generated from the feed's station names
    and disambiguated with the CRS code on collision. This is chosen over
    code-only paths knowing it costs roughly 40 KB of extra index on every page,
    because a link pasted into a community thread should be readable.
12. **Nothing is remembered.** No cookie, no `localStorage`: the chosen origin
    lives in the URL, which is also the shareable address.
13. **Destination rows do not become entrances to other origins in v1.** The row
    already carries a price, time, changes, a ticket link, an expander and a Copy
    control, and it already overflows a phone. The chooser covers the need.
14. **The index lists only stations whose pages the build actually wrote** — built
    from the outputs, not from the feed, so no option is ever offered and then
    missing.

## Consequences

- **ADR-0014's rejection of per-destination pages is not overturned.** Those were 139
  thin doorway pages per origin, built for search. A per-origin page is the whole
  tool for that station — the budget list, the journeys, the ticket links, the
  caveats — and it is what a town's community post would link to. The two look
  similar in shape and are opposite in intent.
- **ADR-0010's constraints hold unchanged.** Each page is still one self-contained
  file with no server, no build step, and no external assets. The *set* of files is
  a build output, not a service, and nothing is fetched at runtime.
- **Per-station addresses are the growth mechanism.** A post for Grantham links the
  Grantham page; a post for Leicester links the Leicester page. The shareable
  address is the loop that makes any-origin useful to a community rather than a
  generic tool.
- **The go/no-go instrument changes shape.** The Grantham sweep becomes one of ~2,500
  outputs, so "Grantham reaches almost nowhere under £20" no longer decides the whole
  project on its own. The dated tripwire still decides it, and the honest reading of
  a weak Grantham count is now "one station is weak", not "the tool is".
- **The build cost is bounded by timetable enrichment, not by the fare query.** The
  fare query is cheap; the per-destination journey search is the expensive part, so a
  full build may run to hours and may need a cap or a faster path. **This cannot be
  measured until the feed lands**, which is still blocked (ADR-0005), so the page
  count is a parameter of the build rather than a fixed number.
- **The index costs more than the first estimate, and the slug is why.** A bare
  `["NAME","CRS"]` pair measures 19–32 bytes, so ~2,500 stations is roughly 60 KB;
  carrying a readable path per station brings it to roughly 100 KB on *every* page.
  HTML compresses well, so the wire cost is far lower than the file size, but the
  build must therefore measure a real page before the full set is generated.
- **The picker cannot say "nearest station".** The fare-feed location records carry
  only `crs` and a name — no county, region, or coordinates. A map, a region
  grouping, or a "nearest to you" list would all be invented evidence, so the
  reader is expected to know their station's name or code. This is a real
  limitation of the flow and is stated rather than worked around.
- **The root page is the chooser and holds no fares**, so it is cheap to build and
  cheap to serve, and it is the only page whose subject is the picker itself.
- **Slug collisions are a build-time concern**, not a runtime one. Two stations can
  share a name; the code is the disambiguator, and a collision that reaches the
  page as two identical links is a defect rather than an ambiguity to handle in the
  UI.
- **Undecided and not to be invented:** the hosting or deploy target. The *path*
  scheme is now decided (`/from/<slug>`, root at `/`), but which host serves it, and
  therefore the full address a community post would carry, is still unchosen.
- **ADR-0003's SEO gate is unchanged.** 2,500 pages are a tool set, not a content
  strategy; generating them is not a licence to chase search traffic, and the
  community signal still gates any content investment.
- **One thing to fix first.** The page already overflows horizontally at 390 px with
  the ticket action off-screen, so the picker must not be added until that is fixed.
  The flow above resolves the *content* hazard (origin as identity above the
  controls, destination filter inside them) but not the *width* one: the picker is a
  second place-shaped thing on a screen that is already 73 px too wide. The picker
  opens as a full-width list beneath the field, with no modal to trap focus.
