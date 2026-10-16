# Release clearance

**The DTD fares route is cleared and the Darwin timetable schedule is not, and
the deploy workflow is gated on both.** The privacy contact — a promise a person
keeps rather than a term anyone read — is cleared too, and the [section
below](#privacy-contact) holds the date it was confirmed and by whom. This file
is the record the gate reads, and it is edited in a pull request by a person who
has read the actual terms — which is the point, because no tool here can read a
licence and decide whether it permits publication. What the tool can do is make
that decision binding, dated, scoped to the release it was made for, and tied to
the exact licence file it was read from.

`tools/check_release_clearance.py` is the `clearance` job in the deploy workflow,
and it fails unless every product a release publishes is `cleared` below. A
failure there reddens that one job and skips the deploy; the build, the shards,
the assemble job and their tests are unaffected. Local builds do not read this
file at all: `build_demo_page.py` and `run.py` are ungated, so a contributor can
build, test and open a real-feed page with no licence clearance in sight. The
gate applies to publication, and only to publication.

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
3. `python -m tools.check_release_clearance --print` prints a block per product
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

- state: cleared
- answer: yes
- read on: 2026-10-16
- approved by: Lyden Yardley
- approved on: 2026-10-16
- expires: 2027-10-16

The terms were first read on 28 September 2026 and re-read on 16 October 2026,
from the copy filed in this folder, whose footer is dated 24/09/2026 and names
`opendata.nationalrail.co.uk/terms`.
They are not ambiguous about permission: "You are free to: copy, publish,
distribute and transmit the Information", and to "exploit the Information
commercially ... by including it in Your own product or application ("End User
Product")". The account holds the entitlement the build needs: the fares and
timetable were downloaded from `opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares`
and `.../3.0/timetable` on 24 September 2026, and those endpoints are gated on
the Fares, Routeing Guide and Timetable selection
(`feeds/download-manifest.json`). The Knowledgebase feeds the user downloaded on
28 September are a separate entitlement and are not evidence of this one.

**Why it is cleared.** Publication of fares from the DTD static fares feed, on a
public page whose ticket links may earn affiliate commission, is inside the grant
in the filed terms. The conditions the grant comes with are met or have no subject
on this release, and the fee is nil by a published document:

- **Acknowledgement** — the terms require the publisher to "acknowledge NRE as
  the source of Information in accordance with this agreement and the Developer
  Guidelines". The URL the terms give for those guidelines 404s, but the document
  is published from `nationalrail.co.uk/developers/` and was read on 28 September
  2026. It requires "a link to the NRE website for more information and ...
  displaying the 'Powered by National Rail Enquiries' logo", placed "directly
  alongside, above or underneath the Information derived from the feed" where
  that feed is the product's predominant information. `--notices nre` carries the
  acknowledgement, the logo and the link, and the page's placement is underneath
  the results. The logo is painted white, one of the three colours the guidelines
  permit ("blue, black or white"), so its rendering is one they name rather than
  one awaiting permission.
- **Forecasted times** — the terms require that "all forecasted arrival and
  departure times, provided by Your End User Product(s), are consistent with
  Darwin forecasts". This release is **prices-only** (`--release fares`): the
  build does not load the national timetable, so the pages provide no arrival or
  departure times and the condition has nothing to apply to.
- **Time-Bound Data** — the terms require that "all Time-Bound Data, used in Your
  End User Product(s), are displayed as directed in the Information, as per the
  Developer Guidelines", and the licence **defines** the term: "'Time-Bound Data'
  means any data within the Information that is provided in conjunction with
  instruction for the timeliness of its display; platform numbers for example."
  The static fares feed carries neither platform numbers nor a display-timeliness
  instruction, so a fares page carries none. Earlier readings of this record
  treated this as answered only by the unpublished guidelines; it is the term's
  own definition that decides it, and the trigger is absent.
- **Fee** — charges arise only above NRE's High Volume Usage threshold, and the
  Usage Charging Document (v06-01, read 28 September 2026) confines that model to
  the Darwin **Webservice** feeds: 5 million enquiries per user per 28-day railway
  period at 0.042p each, with Darwin **Push** feeds `N/A` throughout. This build
  downloads two static ZIPs a day and makes no Webservice enquiry, so no fee
  applies. That is a published document rather than a conclusion from volume.

**What this clearance does not cover.** Times. A page that showed arrival or
departure times would raise the "forecasted" question, and whether a static
scheduled time is "forecasted" in the terms' sense is a reading this project has
not taken. The national timetable is not published, and the Darwin timetable
product schedule is excluded below for that reason. Putting the times back means
answering that question, or RDG's §5.

The registration is in scope too, and it is the one thing no document here can
show. The portal asks what the data is for and where it will be used, and the
terms require that information to be true: if the registered purpose does not
name a public page carrying an affiliate link, that is a defect in the account
rather than in this build. Only the account holder can see it.

This is the source the published build actually reads, and it is the one the
audit found the workflow downloading with no licence decision anywhere near it.
It is a portal subscription rather than a marketplace product schedule, so it has
no PDF in this folder and no product id — which is precisely why it needed a
section of its own, and why the gate cannot pin it to a digest.

The register records a documented, dated reading of the published terms and
charging material, not a signed entitlement. The letter to RDG at
`docs/rdg-licence-enquiry.md` is unanswered, and that answer is what would put the
times back rather than what lets the fares out.

## the NRE mark is white

- state: answered by the brand guidelines, not a product decision
- reason: the guidelines permit blue, black or white, so the white mark the page paints is a rendering they name rather than one awaiting permission

The Developer Brand Guidelines (September 2026, filed in this folder, read 28
September 2026) require the logo to be "legible to viewers" and fix its colours:
"The National Rail logo should only be used in blue, black or white", and "our
wordmark can be used both positively (in our brand blue) and negatively (white
out of a colour or image) just make sure it is always legible". The mark is
`#2E2D7F`, invisible on this page's dark palette, so the page paints it white on
a dark plate (`--nre-ink: #ffffff`; ADR-0036, amended a third time). The file in
`assets/powered-by-national-rail.svg` is NRE's, byte for byte, and the page
inlines it unchanged; the colour is applied by the page's own stylesheet at paint
time.

The pale blue this section used to describe (`#cdd6ff`) was none of the three
permitted colours, which is why it stood here as an open question: it was a
rendering NRE had not approved. White is one they name, so the question is settled
by the guidelines rather than by an email, and the file was never edited. It is
deliberately not a gated pseudo-product like `privacy contact`: the credit itself
is required and satisfied, and this was a rendering question rather than a right
to publish. `NationalRailDatafeeds@raildeliverygroup.com` remains the route if a
different rendering is ever wanted — a reversed asset, say, which would replace
the stylesheet rule with a file.

## privacy contact

- state: cleared
- answer: yes
- read on: 2026-10-14
- approved by: Lyden Yardley, the repository owner
- approved on: 2026-10-14
- expires: 2027-10-14

Every generated route carries a contact, and the privacy page tells a reader
that somebody is at the end of it. The build names the public issue tracker
(`https://github.com/lydenyardley/TrainBudgetExplorer/issues`, ADR-0068) and
prints no email address.

**Why it is cleared.** The owner confirmed on 14 October 2026 that the issue
tracker's notifications reach an address they read, so the route every generated
page names is a monitored one. That confirmation is the whole of what this
section claims, and it is the one thing no tool here can check: nothing in this
repository reads a mailbox.

**Why it expires.** The claim is about a person watching an inbox, which is a
circumstance rather than a term, so it is dated for a year and the confirmation
is repeated rather than inherited. Re-clearing is this date changed after a fresh
look at the route.

**What would take it back.** `PRIVACY_CONTACT` or `--privacy-contact` can name a
different route: record that override here and clear the route it names instead.
Anyone who stops reading the tracker sets `state: excluded` again, and the gate
refuses a release on the line, because refusing is the safe direction.

This is one of the two products that are not a filed licence. [`dtd`](#dtd) is
the other, and it is cleared against the filed portal terms — but only for a
prices-only release, so this section and that one together clear `--release
fares` and nothing wider.

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
