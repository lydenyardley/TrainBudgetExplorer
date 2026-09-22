# Pre-publish checklist: before a tracked ticket link goes live

One page, to be worked top to bottom. It exists because a published page carrying
prices from licensed data and a monetised link is the one artefact in this project
that cannot be undone by regenerating a file.

Nothing here is a formality. Every box is something a person has to look at and
answer, and "I think that's fine" is not an answer.

## 1. The licence — this blocks everything else

**Where:** `raildata.org.uk`, the fares product, its **licence** (`termsAndConditions`)
tab, **while signed in as the account holder**. The Rail Data Marketplace licence is
a generic agreement with a per-product **Schedule 1**, and Schedule 1 is the
operative part. Nothing about it is readable anonymously (ADR-0005), and the
published template is the wrapper, not the terms.

**How to find a product.** Searching the marketplace for `Schedule 1` returns
nothing, because Schedule 1 is a section *inside* the downloaded licence PDF, not a
catalogue field. `RJFAF` returns nothing either: it is the legacy ATOC file prefix
for the fares feed, not the product name. Products are named in words, and the one
the download is for is stated in Schedule 1 §3 as `LICENCED DATA` with its product
id. Search by the words — **Fares**, **Knowledgebase**, **Ticketing fares and
retail** — or browse that category. Each product's licence downloads as a PDF named
`<Product name>-license-P-<product id>.pdf`; keep one per product.

- [ ] Opened the fares product's licence tab while signed in
- [ ] Read **Schedule 1** for the fares product, not only the agreement above it
- [ ] Recorded the four answers below, in writing, with the date read
- [x] Re-read the same for the timetable product — **read 22 September 2026**, see below

| the question | what to find | answer found | where recorded |
|---|---|---|---|
| **commercial use** | may these prices sit on a page that earns commission? | **fares: unread.** timetable: OGL3 permits it, but Schedule 1 §5 restricts the raw data to *internal business purposes only* — see ADR-0020 | ADR-0020 |
| **attribution** | the exact wording, and where it must appear | **fares: unread.** timetable: §8 lists **no organisations** and gives no statement, so the OGL fallback wording applies (below) | ADR-0020 |
| **redistribution** | may the prices be shown to people other than the licensee? | **fares: unread.** timetable: OGL3 permits, §5 restricts — the same conflict | ADR-0020 |
| **licence fee** | is the `Licence Fees` term in Schedule 1 nil, or a number? | **fares: unread.** timetable: **nil** — Schedule 2, `Open (OGL3)`, "without charge" | ADR-0020 |

### What the timetable licence says

The Darwin Timetable Files licence (`Darwin-timetable-license-P-9ca6bc7e-....pdf`,
project root) was read on 22 September 2026. It is two documents in one file, and
they disagree:

- **The head is Open Government Licence v3.0.** It explicitly permits exploiting the
  Information "commercially and non-commercially", including in your own product.
- **Schedule 1 §5 does not.** `PERMITTED PURPOSES`: "The raw data may be copied and
  used by Data Consumer for **internal business purposes only**."
- **Schedule 1 §8 sets no attribution statement.** It says organisations "must be
  attributed if the data is subsequently published", then lists none. Under the OGL
  head, that means the fallback wording is the required one:
  `Contains public sector information licensed under the Open Government Licence v3.0.`
- **Schedule 2 sets the fee at nil** — `Open (OGL3)`, no charge. The fee question is
  answered for this product; it does not transfer to the fares product.
- Term is one year, auto-renewing, with one month's notice for convenience; the data
  may be retained after the term; the update frequency is daily.

Nothing here is a formality: §5 may forbid the public page entirely, so it is a
question for RDG in writing before launch, not a reading to be argued in-house.

## 2. Attribution — the term most likely to be got wrong

- [ ] The required wording is copied **verbatim**, including any capitalisation
- [ ] It fits the page as built: single static file, no server, no request per row
- [ ] It is visible **without a click** — in the footer, not in a comment, a
      collapsed expander, or the generated payload
- [ ] It lives in the **template**, not typed into a generated `demo.html`, so it
      survives the next regeneration
- [ ] If the licence also imposes terms on *downstream* users of the page, that is
      flagged and decided, not accepted silently — this is the kind of clause that
      has been found in rail licences and needed a careful reading

## 2b. The attribution statement

- [ ] The exact statement is the product's own if Schedule 1 §8 gives one, and the OGL
      fallback text otherwise — **the timetable gives none, so the fallback it is**
- [ ] The wording is pinned in one place in the code, not retyped into a build
      command where the next regenerator can drop it

## 3. The fee term

- [x] `Licence Fees` for the timetable: **nil** (Schedule 2, `Open (OGL3)`)
- [ ] `Licence Fees` is either nil or a number, and whichever it is is written down
- [ ] If it is non-zero: it is compared against the affiliate rate — and the rate is
      only visible **after joining** the network, so a fee against an unknown rate
      means the decision is deferred, not guessed

## 4. The seller and the network (ADR-0016)

- [ ] Seller is Trainline and network is Partnerize, with both ids to hand — or a
      written reason the recorded decision changed
- [ ] `pairing_warning` is **silent** for the chosen pair; a seller linked through a
      network that does not run its programme produces a working link that earns
      nothing
- [ ] The rate read inside the network is written into ADR-0016, replacing the
      directory figures that disagree with each other by a factor of seven

## 5. The link itself (ADR-0017)

- [ ] `python check_links.py` reports no `no_journeys` and no `http_error` for the
      chosen seller and mode; it catches a broken link without a person
- [ ] The link was **then** opened by hand in a normal browser. A `blocked` or
      `inconclusive` verdict means the checker learned nothing, and only a person
      can look at a page and see a list of trains
- [ ] The mode is deliberate and written down: `deep` sends the reader's own search,
      `fallback` sends the seller's own search page
- [ ] It lands on a search for the right origin, destination, date and party size
- [ ] The **date on the landing page is the date on the page**, not today
- [ ] The default National Rail link is fixed or removed: it currently reports
      "No matching journeys found" for every route, and it must not sit on a
      published row
- [ ] Tracked and untracked links land on the **same URL** (`test_retailer` asserts
      the wrapper only)
- [ ] The disclosure is visible **above the click**, and the link carries
      `rel="nofollow sponsored"`

## 6. Stop rules

Do not publish if any of these is true. Park the page and say so; do not soften a
term to get past it.

- the licence does not permit commercial use — the page survives as a demo or
  portfolio piece and the affiliate plan dies instead (ADR-0010)
- the attribution requirement cannot be met by the page as built — change the page,
  then come back
- there is a licence fee and no known rate — defer
- the link has not been opened by hand and seen to work — a link that lies is worse
  than no link

Anything left unverified stays recorded as unverified in the ADR. A checklist ticked
on an assumption is worse than no checklist at all.
