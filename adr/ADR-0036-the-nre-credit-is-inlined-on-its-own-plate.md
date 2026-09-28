# ADR-0036: The NRE credit is the supplied mark, inlined, on its own plate

**Status:** Accepted
**Date:** 28 September 2026
**Relates to:** ADR-0020 (a notice describes the page it is on), ADR-0021 (one
product, one licence, one attribution), ADR-0033 (one self-contained file per
route), ADR-0035 (what a page may claim)

## Context

The National Rail Data Portal terms require the publisher to "acknowledge NRE
as the source of Information in accordance with this agreement and the Developer
Guidelines". The URL the terms name for those guidelines 404s, and the record in
`licences/release-clearance.md` said so, which left the attribution requirement
open and kept the page carrying a plain sentence where the licence asks for a
mark. The guidelines are published — from the developer page rather than from
the terms' own link — and they are specific:

> The user of NRE feeds (You) must acknowledge NRE as the source of
> information, where possible, by providing a link to the NRE website for more
> information and by displaying the "Powered by National Rail Enquiries" logo
> …

> Where an NRE feed is displayed as the predominant or standalone information in
> Your product or service, NRE attribution should be shown directly alongside,
> above or underneath the Information derived from the feed.

This page's fares and times *are* its predominant information, so the second
condition applies and an attribution page would not satisfy it. Three things
follow, and each has a way of being got wrong.

**The mark is a file, and the page is one file.** The ZIP supplies
`Powered by National Rail.svg`: 8.3KB, paths only, no fonts and no external
references, so it inlines cleanly. A linked `<img>` would be simpler and wrong
in the way this project keeps refusing — the page is one self-contained file
(ADR-0033), and an attribution that needs a second request to appear is an
attribution a reader on a train may never see.

**The mark is dark blue on a fixed fill, and the page has a dark palette.** The
brand is #2E2D7F; on this page's dark background it would be invisible, and the
guidelines require the logo to be "legible to viewers". Recolouring the mark to
fit a background is not an option — an edited mark is not the mark that was
licensed — so it is given a white plate to sit on, which is legible in both
palettes and leaves the artwork untouched.

**The mark is paths, so it reads as nothing.** An SVG's paths carry no text, so
a screen reader announcing the image would announce an unlabelled graphic. The
name is written on the wrapper (`role="img"` with the mandated words) and the
`<svg>` itself is hidden from the tree, because a bare `<svg>` inside a named
image is exposed as a second, unnamed image — which is exactly what the
accessibility matrix caught when the first version shipped.

## Decision

**`--notices nre` writes the acknowledgement, the NRE mark and the link to NRE
into the footer's credit block; the mark is inlined, unaltered, on a light
plate, underneath the results.**

- The logo file is committed at `assets/powered-by-national-rail.svg`, byte for
  byte as NRE supplies it, with the source recorded beside it. A build that
  cannot read it stops: this is the one element in the footer the licence names,
  and a page that quietly loses it is worse than a build that fails.
- The credit is written when, and only when, the composed notice list contains
  the NRE acknowledgement — `wants_nre_credit()`, keyed on the notice rather
  than on the flag so the in-process build and the worker pool cannot disagree.
  A build given verbatim `--attribution` text is not second-guessed; the
  operator chose that wording and the licence question behind it is theirs.
- The `Powered by` logo is used, not the National Rail wordmark. The wordmark is
  the brand's own; this page is not National Rail's.

## Consequences

- The credit adds ~8.4KB to every station page. That is the size of the mark,
  and the alternative — a request per page view for a legal notice — is worse.
- Three browser checks hold it: the credit appears exactly when the page
  acknowledges NRE as the source; the mark is present, has the mandated name and
  is drawn; and it is legible, linked to NRE, and underneath the table. Each was
  proved to fail by breaking it — an unnamed image, an 18px pointer target and a
  link that the licence requires and the page did not have were all caught by
  the suite rather than by reading the code.
- The remaining open requirement is not an attribution question. The guidelines
  do not define a "forecasted" time for a licensee, so whether the times this
  page computes from a static schedule are the "forecasted arrival and departure
  times" the terms require to stay consistent with Darwin is still unanswered,
  and is recorded as such in `docs/publish-checklist.md` §1.

**Amended 28 September 2026.** The plate is a token now, `--logo-plate`, rather
than a fixed white, because the page can be told to paint dark (ADR-0037) and a
pure-white chip in a dark footer reads as a hole in the page. The mark's own
colours still never move: the plate is white in the light palette and a
near-white in the dark one. The light case needed a second thing — white on a
white page is not a plate at all, and the plate measured 1.00:1 against the
background, which the new legibility check caught — so it carries a 1px edge.
What the guidelines ask, legible in both palettes, is now measured rather than
argued: 3:1 between the mark's ink and its plate, in each scheme.
