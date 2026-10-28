# ADR-0078: An outbound link carries no referrer

**Status:** Accepted
**Date:** 28 October 2026
**Relates to:** ADR-0017 (what the live link check found), ADR-0018 (the page's default link), ADR-0020 and ADR-0021 (the licence notices), `docs/fares.md`

## Context

A station page keeps the reader's whole search in the address, because the
address is the search (S05): `?budget=20&mode=single&party=2&card=2TR&short=NOT&short=GDN`.
Refreshing, sharing or pressing Back all depend on it, and the privacy notice
names it as one of the two ways the search leaves the device.

Every outbound anchor on that page sent it on as the `Referer` header. The
ticket links carried `noopener` and, when a network was configured,
`nofollow sponsored`, and neither touches the referrer. The footer's two licence
links were the same: `rel="external"`, which is not a referrer policy either.

So a click on a ticket link told a commercial seller the reader's budget,
whether they hold a railcard, and which places they had shortlisted -- the
reader's plan, handed to a party they did not choose to tell. The 28 October 2026
audit measured it on the built page (audit item 9) and the address is the search
that carried it.

Three fixes were available:

1. `rel="noreferrer"` on the anchors.
2. `referrerpolicy="no-referrer"` on the anchors.
3. A site-wide `Referrer-Policy` response header from the host.

## Decision

**Every anchor that leaves this site carries `noreferrer`**, ticket links and the
licence credit alike, and the tokens are built in one place:
`trainbudget/fares/retailer.py` for the rows, `build_release.py` for the footer.

The header was refused because this project does not own its host: a release is
static files uploaded by a workflow, and a promise the page depends on but cannot
make is not a promise this repository can keep. The `referrerpolicy` attribute
was refused because there would then be two places stating the rule -- the
element and the `rel` -- and the payload already carries a `rel` per row for the
page to copy, so one of them would eventually be forgotten.

## Evidence

- `tests/test_retailer.py` holds both rel values, tracked and untracked.
- `tests/test_build_links.py` holds the payload's `rel` for every row and reads
  every outbound anchor in a rendered page, the footer's licence links included.
- `tests/browser/station-rows.cjs` reads the live anchor's `rel` on a built page,
  because the row's link is built by the page's script from the payload rather
  than written into the markup.

## Consequences

- A seller's own analytics no longer receives the search that produced the click.
  Nothing this project measures depended on it: there is no server here to
  receive the referral, and the commission a tracked link earns comes from the
  redirect wrapper and its own identifiers, not from the referrer.
- A reader following a ticket link to a seller lands on the seller's search as
  before. A page that arrived from this site is now indistinguishable, to the
  seller, from one that arrived from a bookmark.
- **A licensed link that must carry a referrer** -- if a future agreement names
  one -- is a change to the `rel` built in two functions, not a change to the
  page, and `tests/browser/station-rows.cjs` fails until both halves move.
