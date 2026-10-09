# Release clearance

**Nothing here is cleared, and the deploy workflow is gated on that.** This file
is the record the gate reads, and it is edited in a pull request by a person who
has read the actual terms — which is the point, because no tool here can read a
licence and decide whether it permits publication. What the tool can do is make
that decision binding, dated, scoped to the release it was made for, and tied to
the exact licence file it was read from.

`tools/check_release_clearance.py` fails the publish path unless every product a
release publishes is `cleared` below. Local builds do not read this file at all:
`build_demo_page.py` and `run.py` are ungated, so a contributor can build, test
and open a real-feed page with no licence clearance in sight. The gate applies to
publication, and only to publication.

The product list is read from `licence-manifest.json` in this folder (each
file's name, SHA-256 and product id), plus the two questions that are not a
filed PDF — the DTD portal route and the privacy contact. The PDFs are kept
locally and are not in git (ADR-0067). A PDF on disk that the manifest does
not name, or whose bytes no longer match it, cannot be filed and forgotten:
it needs a decision before it can be published. That is the same failure
`tests/test_licences.py` prevents on the register side. CI has no PDFs, so it
checks the clearance digest against the manifest.

## How to clear a product

1. Read the actual current terms. For a marketplace product that is the filed
   PDF; for the DTD route it is the account subscription and the current DTD/NRE
   terms, neither of which is a file in this folder.
2. Work through `docs/publish-checklist.md` §1 and record the answers here.
3. `python tools/check_release_clearance.py --print` prints a block per product
   with the licence digest already filled in. Paste it, change `state` from
   `excluded` to `cleared`, and answer `answer`, `read on`, `approved by`,
   `approved on` and `expires`.
4. Open a pull request. The review of that pull request *is* the approval; there
   is nowhere else for it to happen.
5. Configure **required reviewers** on the `github-pages` environment
   (Settings → Environments). That is the platform's own second half of the gate,
   and this file cannot supply it, because a workflow cannot require a person.

`answer` is `yes` or it is nothing. `unknown`, `probably`, a blank and a
paragraph of reasoning are all the same thing to the gate, which is deliberate:
this project's own register records that the only honest answer to the DTD
public-use question is still outstanding, and a gate that accepted prose would
have passed the same build the audit found.

A clearance is **scoped to a product**, and a release declares what it publishes
(`--release fares`, `--release fares,timetable`). The fares build in
`.github/workflows/deploy.yml` reads only the fares feed, so a fares-only
clearance is enough to publish it. Adding `--timetable` to that build demands a
timetable clearance this project has not got — which is how the "internal
business purposes only" reading stays binding instead of being a note somebody
skips.

Two things a clearance is not, and the tool is built so it cannot be fooled by
either:

- **Not the attribution wording.** The page can carry every required credit and
  still be a page nobody has cleared. Crediting a publisher is a different
  question from being permitted to publish.
- **Not permanent.** `expires` is enforced, and `licence digest` is checked
  against `licence-manifest.json` (and against the PDF when you have it), so a
  licence replaced under a standing clearance does not inherit it.

## dtd

- state: excluded
- reason: permission is not the open question — the current terms grant publication and commercial exploitation, and the fee is nil by a published charging document — but two of the terms' requirements are unanswered, and neither is a footer

The terms were read on 28 September 2026, from the copy filed in this folder,
whose footer is dated 24/09/2026 and names `opendata.nationalrail.co.uk/terms`.
They are not ambiguous about permission: "You are free to: copy, publish,
distribute and transmit the Information", and to "exploit the Information
commercially ... by including it in Your own product or application ("End User
Product")". The account holds the entitlement the build needs: the fares and
timetable were downloaded from `opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares`
and `.../3.0/timetable` on 24 September 2026, and those endpoints are gated on
the Fares, Routeing Guide and Timetable selection
(`feeds/download-manifest.json`). The Knowledgebase feeds the user downloaded on
28 September are a separate entitlement and are not evidence of this one.

What is open is compliance, and none of it can be written in a footer. One of
the three requirements is met — the acknowledgement, by `--notices nre` — and the
other two are not:

- The terms require the publisher to "acknowledge NRE as the source of
  Information in accordance with this agreement and the Developer Guidelines".
  The URL the terms give for those guidelines 404s, but the document is
  published from `nationalrail.co.uk/developers/` and was read on 28 September
  2026. It requires "a link to the NRE website for more information and ...
  displaying the 'Powered by National Rail Enquiries' logo", placed
  "directly alongside, above or underneath the Information derived from the
  feed" where that feed is the product's predominant information. `--notices
  nre` carries the acknowledgement, the logo and the link, and the page's
  placement is underneath the results. Nothing here is invented.
- The terms require that "all forecasted arrival and departure times, provided by
  Your End User Product(s), are consistent with Darwin forecasts". The page
  computes its times from the static timetable download, not from Darwin. Whether
  a published static time is a "forecasted" time in the terms' sense is the
  question, and it is the one that decides whether times may go out at all.
- The terms require that "all Time-Bound Data, used in Your End User Product(s),
  are displayed as directed in the Information, as per the Developer Guidelines",
  and the guidelines are the same unpublished document.
- Charges arise only above NRE's High Volume Usage threshold, and the Usage
  Charging Document (v06-01, read 28 September 2026) confines that model to the
  Darwin **Webservice** feeds: 5 million enquiries per user per 28-day railway
  period at 0.042p each, with Darwin **Push** feeds `N/A` throughout. This build
  downloads two static ZIPs a day and makes no Webservice enquiry, so no fee
  applies to it. That is a published document rather than a conclusion from
  volume, and it is the one requirement of these terms this release answers
  outright.

The registration is in scope too. The portal asks what the data is for and where
it will be used, and the terms require that information to be true: if the
registered purpose does not name a public page carrying an affiliate link, that
is a defect in the account rather than in this build.

This is the source the published build actually reads, and it is the one the
audit found the workflow downloading with no licence decision anywhere near it.
It is a portal subscription rather than a marketplace product schedule, so it
has no PDF in this folder and no product id — which is precisely why it needed a
section of its own.

## the NRE mark is reversed

- state: open question, not a product decision
- reason: NRE's brand pack ships no reversed asset, so the mark on every page is a rendering they have not approved

The Developer Brand Guidelines (September 2026, filed in this folder, read 28
September 2026) require the logo to be "legible to viewers". The mark is
`#2E2D7F`, which is invisible on this page's dark palette, so the page reverses
it: a light rendering of NRE's blue on a dark plate of the same blue. The file
in `assets/powered-by-national-rail.svg` is NRE's, byte for byte, and the page
inlines it unchanged; the reversal is applied by the page's own stylesheet at
paint time (ADR-0036).

Nothing in the pack permits or forbids it. The ZIP holds one #2E2D7F `Powered by
National Rail.svg` and one #2e2d7f wordmark, and no reversed variant of either,
so a dark page has two options: this, or a logo the guidelines say is not
legible. The developer page says brand materials are subject to NRE's
permission, and the guidelines name the address to ask
(`NationalRailDatafeeds@raildeliverygroup.com`) for an exemption.

Asking is one email, and the answer is one of two: a reversed asset, which
replaces the stylesheet rule with a file; or written permission for the
reversed rendering, which turns this paragraph into a decision. Until one
arrives the page carries an edited logo, and this is where that is recorded.
It is deliberately not a gated pseudo-product like `privacy contact`: the credit
itself is required and satisfied, the question is about the rendering, and
making it block publication would gate the whole site on an unanswered email.
Turn it into one by adding it to `products_needed()` in
`tools/check_release_clearance.py`.

## privacy contact

- state: excluded
- reason: the address the build uses by default has not been confirmed as monitored, so the promise every route makes to its reader is unbacked

Every generated route carries a contact, and the privacy page tells a reader
that somebody is at the end of it. `PROJECT_PRIVACY_CONTACT` in
`build_demo_page.py` holds the project's own address so that a real-feed build
works locally without an operator having to supply one, and it was chosen for a
local build. Nothing has confirmed that anybody reads it, that it is an address
appropriate to publish, or that it will outlast the project.

Clearing this means: the address to publish, the date it was confirmed, and who
confirmed it. An operator who has a monitored address should override it on the
build — `PRIVACY_CONTACT`, or `--privacy-contact` — rather than publish the
default, and record that override here.

The register records a documented zero-cost working conclusion from the public
charging material, not a signed entitlement, and the letter to RDG is drafted at
`docs/rdg-licence-enquiry.md` and unanswered.

## P-9ca6bc7e-62e1-44d6-b93a-1616f7d2caf8

- state: excluded
- reason: Schedule 1 §5 permits internal business purposes only, so the timetable cannot be published at all until RDG answers in writing

Darwin Timetable Files, read 22 September 2026. The OGL v3.0 head permits
commercial use and Schedule 1 §5 does not; ADR-0020 keeps the strict reading, and
ADR-0021 records that the restrictive wording is a per-product choice rather than
boilerplate, because the neighbouring products say the opposite. This exclusion
is the reason the fares-only build exists, and the reason the page has a
prices-only mode that says so.

## P-51e17973-7327-4735-a7ca-d2a484a56065

- state: excluded
- reason: the build does not read this product, and the Rail Delivery Group credit its §8 leaves as a condition is unconfirmed against the page as built

Knowledgebase Ticket Types data feed. §5 permits distribution, and its §8 lists
no attribution statement — which does not mean none is required, because the Data
Sharing Agreement cl. 3.3.1 still requires crediting the data publisher.
`docs/publish-checklist.md` §2b has not confirmed that credit is visible without
a click on the generated page.

## P-2d177d2e-dcb8-43dc-ac4d-3a967dd35c5e

- state: excluded
- reason: the build does not read this product, and the Rail Delivery Group credit its §8 leaves as a condition is unconfirmed against the page as built

Knowledgebase Ticket Restrictions data feed, on the same terms as the ticket types
feed. The build does read a restriction file, but the one in use comes from the
DTD download rather than from this product.

## P-4f4a90ff-d4e2-442e-93b3-07121430f303

- state: excluded
- reason: the Rail Delivery Group credit its §8 leaves as a condition is unconfirmed against the page as built

Fare Locations Reference Data v1.3. Unlike the two feeds above, this one is in the
shape the build already reads: `FaresDb` takes location names from a feed of this
form. If the build is ever to run on the marketplace feeds rather than DTD, this
is the first section to clear.

## P-37faed36-518a-4870-b1bd-b675461fb72e

- state: excluded
- reason: a product decision, not a licence one: the demo tier is a sanity check and is not intended to sit under a published page

Easy Fares API (Demo Version). §5 does permit sale for commercial gain, so this
exclusion is a choice rather than a restriction. ADR-0022 records it: a
station-pair query API with a paid usage schedule past 100 hits, and the wrong
shape for a bulk feed that ranks every destination from an origin.
