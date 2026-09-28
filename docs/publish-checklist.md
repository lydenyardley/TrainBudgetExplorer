# Pre-publish checklist: before a tracked ticket link goes live

One page, to be worked top to bottom. It exists because a published page carrying
prices from licensed data and a monetised link is the one artefact in this project
that cannot be undone by regenerating a file.

Nothing here is a formality. Every box is something a person has to look at and
answer, and "I think that's fine" is not an answer.

## 0. The gate that enforces this page

**`licences/release-clearance.md` is the machine-checked form of §1 and §6**, and
the deploy workflow refuses to publish anything it does not clear. Run

```
python tools/check_release_clearance.py --release fares,timetable
```

to see where the project stands today. It currently fails, which is correct: §1
below is unfinished, and the shape the workflow now publishes is `fares,timetable`
because the daily build loads the national timetable to show times and changes.
Two things are therefore not cleared — the DTD fares product, and the Darwin
timetable product schedule, which this project reads as internal business
purposes only. Nothing in `build_demo_page.py` or `run.py` reads the record, so a
contributor can still build, test and open a real-feed page locally with no
clearance in sight.

The shape is not chosen by hand. `tools/check_release_clearance.py` refuses a
`--release` it does not recognise, and a test compares the shape the workflow
declares against the flags the build step actually passes — so a build that
gained `--timetable` without a matching clearance is a red test, not a release
that quietly widened its own permission.

The two halves of the gate, because neither is enough alone:

| | what it is | where it lives |
|---|---|---|
| the record | a written, dated, scoped decision, reviewed like any other change | `licences/release-clearance.md`, changed in a pull request |
| the presence | a person who must click approve before a release | required reviewers on the `github-pages` environment |

The second half is repository settings, not code, and a workflow cannot require a
person. Set it once under **Settings → Environments → github-pages**; until then
the record is the only gate, and the pull-request review is the only approval.

## 1. The licence — this blocks everything else

**Where:** the National Rail Data Portal (NRDP/DTD) account for fares and
timetable access, plus the current NRE developer terms and brand pack. The
supplied Knowledgebase URLs are reference feeds, not the DTD fares/timetable
subscription. The DTD research, source links, zero-cost conclusion, and
escalation route are in `docs/dtd-licensing-and-data-access.md`.

**How to verify DTD access.** The DTD registration/subscription screen is the
place to confirm the separate **Fares, Routeing Guide and Timetable data**
selection. The Knowledgebase URLs in the project are not evidence of that
selection. The endpoint examples and the current terms are recorded in
`docs/dtd-licensing-and-data-access.md`.

- [ ] Confirmed the DTD subscription selection in the account
- [ ] Read the current DTD/NRE terms and brand pack, not only the older marketplace schedules
- [ ] Recorded the answers below, in writing, with the date read
- [x] Re-read the Darwin timetable product — **read 22 September 2026**, see below
- [x] The fares data has a reviewed selector, not the broad query: `publishable_destinations_within`
      keeps only the exact standard-class ANYTIME DAY R ticket codes (`8AE`, `AAB`,
      `E2R`, `HX9`, `SDR`, `XAR`) with a blank restriction code, and refuses to
      run unless the `.RST` restriction file parsed with no rejected records
- [x] The timetable audit separates unresolved TIPLOCs into known locations with
      no CRS and no-record-at-all, and normalises padded keys. The real audit
      reads 4,139 used TIPLOCs, 1,146 unresolved (1,070 known locations, 76 with
      no record), and 1,294 normalised from a padded raw value
- [x] Railcard discounts: the publishable selector evaluates the current `.RST`
      `RR` records against each fare's ticket, route, and endpoint locations;
      blank fields are wildcards, a matching total ban removes the discount, and
      a matching restriction code is retained as the discounted fare's travel
      condition

The first four rows are marketplace products whose §5 fill controls use. The
DTD row is a separate portal subscription and must be checked against the
current NRE/DTD terms; it must not be treated as an OGL or RSP product by
analogy.

| product | agreement | §5 permits publication? | attribution required | licence fee | read |
|---|---|---|---|---|---|
| Darwin Timetable Files | OGL v3.0 | **no** — "internal business purposes only" | OGL fallback wording (§8 gives none) | nil | 22 Sep 2026 |
| Knowledgebase Ticket Types data feed | Data Sharing Agreement | **yes** — "freely available or otherwise distributed to third parties" | credit Rail Delivery Group (cl. 3.3.1) | nil | 22 Sep 2026 |
| Knowledgebase Ticket Restrictions data feed | Data Sharing Agreement | **yes** — same wording | credit Rail Delivery Group (cl. 3.3.1) | nil | 22 Sep 2026 |
| Fare Locations Reference Data v1.3 | Data Sharing Agreement | **yes** — same wording | credit Rail Delivery Group (cl. 3.3.1) | nil | 22 Sep 2026 |
| **NRDP/DTD fares and timetable** (RSPS5045 fares and public timetable ZIPs) | current DTD/NRE terms — confirm in the account | **must be confirmed** | NRE source credit and **Powered by National Rail Enquiries** treatment/logo | working conclusion: nil for static DTD downloads; verify | 24 Sep 2026 |

The licences themselves are in `licences/`, one PDF per product, with the register that
these rows are drawn from and a test that keeps the two in step.

Still to answer for the DTD route: whether the current account/product schedule
expressly permits the intended public display and affiliate-linked use, and
whether any current fee applies. The public charging document supports a
zero-cost static-download conclusion, but it is not a signed entitlement. Do not
publish until the account terms and brand pack have been checked.

- [x] Researched the DTD/NRE route and recorded the source links and caveats in
      `docs/dtd-licensing-and-data-access.md`
- [ ] Confirmed that the account subscription includes **Fares, Routeing Guide and
      Timetable data**, not only the Knowledgebase feeds
- [ ] **The Darwin timetable product schedule is read for the pages that now
      show times.** The daily build loads the national timetable, so this
      project's reading of that schedule as "internal business purposes only" is
      no longer a description of something the site does not publish — it is
      the answer that has to change, or the decision that the published times
      stay switched off. `python tools/check_release_clearance.py --release
      fares,timetable` names it as outstanding.
- [ ] Read the current DTD/NRE terms and recorded the public-use/attribution answer
- [ ] **NRE is acknowledged as source** and the required **Powered by National Rail
      Enquiries** treatment/logo is visible in the generated page
- [ ] **The privacy contact is confirmed for a public service.** The build now
      carries a real address so a real-feed build works locally without an
      operator having to supply one: `lydenyardley+trainbudgetexplorer@example.net`,
      held as `PROJECT_PRIVACY_CONTACT` in `build_demo_page.py`. It was chosen
      for a local build and has **not** been confirmed as monitored, as
      appropriate to publish, or as durable. Read it before the site is public:
      someone has to read it, and the page promises a reader that there is
      somebody. Replace it here and in the build, or set `PRIVACY_CONTACT` or
      `--privacy-contact` to override it.
- [ ] If RDG quotes a non-zero fee, the project rejects it and keeps the zero-cost
      route rather than silently adding a cost

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
- **Schedule 2 sets the fee at nil** — `Open (OGL3)`, no charge. That answer belongs
  to this Darwin product only; it does not decide the DTD subscription or the
  fares publication terms.
- Term is one year, auto-renewing, with one month's notice for convenience; the data
  may be retained after the term; the update frequency is daily.

Nothing here is a formality: §5 may forbid the public page entirely, so it is a
question for RDG in writing before launch, not a reading to be argued in-house. The
letter is drafted in `docs/rdg-licence-enquiry.md`. Three
further products have since been read under the same template, and **their** §5 permits
distribution in terms — so the restrictive wording is a choice, not boilerplate, and the
strict reading of this one is the one to plan around (ADR-0021).

The timetable is also the **degradable** product: `--timetable` is optional and the
builder already renders a prices-only page that says no timetable was loaded. If §5 means
what it says, the journey times go and the product stays. The fares licence is the one
that could end it.

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
- [ ] The **accuracy and liability notices** required of onward distribution are on the
      page: Data Sharing Agreement cl. 3.3.2 requires appropriate accuracy notices plus
      the publisher's liability limitation and exclusion, and cl. 7.2 supplies them —
      the data is "as is", with no representation as to accuracy or fitness for purpose

## 2b. The attribution statement

**There are two, not one**, and both are required (ADR-0021):

- [ ] **Rail Delivery Group credited as the source** for the three Data Sharing Agreement
      feeds — a *condition* of the licence under cl. 3.3.1, in any reasonable manner, and
      never in a way suggesting the publisher endorses the page
- [ ] **The OGL fallback wording** for the Darwin timetable, since its §8 gives no
      statement: `Contains public sector information licensed under the Open Government Licence v3.0.`
- [ ] Neither is read off a blank §8 and treated as "nothing required" — the blank field
      names additional third-party licensors, of which there are none
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

## 7. How a cleared release gets published

1. Work §1–§5 above. Every answer lands in the matching block of
   `licences/release-clearance.md`, with `state: cleared`, `answer: yes`, the
   date the terms were read, who approved it, when, and when it expires.
2. `python tools/check_release_clearance.py --print` prints the blocks with each
   licence PDF's SHA-256 already filled in. The digest is what stops a clearance
   outliving the licence file it was made from: replace the PDF and the standing
   clearance is void until it is made again.
3. Open a pull request. **That review is the approval.** There is nowhere else for
   approval to happen, which is the point.
4. Merge. The next push builds, tests, and passes the clearance gate.
5. Publication stops, rather than the tests going red, if a later release widens
   what it publishes. Adding `--timetable` to the build step changes what
   `--release` is allowed to claim, and the Darwin clearance this project does not
   hold is what stops the times going out under a fares-only decision.

The build is deliberately **fares-only**, and the clearance is scoped to match. If
§5 is ever confirmed to forbid publishing the timetable, the fix is a wider
clearance for the fares route, not a wider build.
