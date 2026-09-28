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

The product list is read from the licence PDFs filed in this folder plus the DTD
portal route, so a PDF dropped in here cannot be filed and forgotten — it needs a
decision before it can be published. That is the same failure
`tests/test_licences.py` prevents on the register side.

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
  against the file in this folder, so a licence replaced under a standing
  clearance does not inherit it.

## dtd

- state: excluded
- reason: the account subscription selection, the current DTD/NRE public-use terms and the NRE brand treatment are all unconfirmed, per docs/publish-checklist.md §1

This is the source the published build actually reads, and it is the one the
audit found the workflow downloading with no licence decision anywhere near it.
It is a portal subscription rather than a marketplace product schedule, so it
has no PDF in this folder and no product id — which is precisely why it needed a
section of its own.

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
