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
python -m tools.check_release_clearance --release fares,timetable
```

to see where the project stands today. The shape the workflow publishes is
**`fares,timetable`**: prices from the DTD fares feed and times from Network Rail's
CIF under the Open Government Licence (ADR-0073). Darwin's timetable product
schedule — which this project reads as internal business purposes only — stays
**excluded**, and that holds whether or not the times go out, because the times come
from the other product. `--timetable` on the build step without the matching
`--release` is a red test rather than a quiet widening, and so is a run whose
station pages come out carrying no journeys (ADR-0020, ADR-0021, ADR-0073).

The **DTD fares route is cleared** in the record against the filed portal terms
(§1 below), and the privacy contact on the same shape **was cleared on 14
October 2026** when the owner confirmed that the issue tracker's notifications
reach an address they read; the record dates it and expires it a year later.
Nothing in `build_demo_page.py` or `run.py` reads the record, so a contributor
can still build, test and open a real-feed page locally with no clearance in
sight.

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

- [x] Confirmed the DTD subscription selection in the account — evidenced by the
      fares and timetable static-feed downloads in `feeds/download-manifest.json`
      (24 September 2026), which are the Fares, Routeing Guide and Timetable
      selection and are **not** the Knowledgebase feeds
- [x] Read the current DTD/NRE terms, not only the older marketplace schedules —
      **28 September 2026**, from the copy in `licences/` (footer dated
      24/09/2026). They grant publication and commercial exploitation outright
- [x] Read the **Developer Guidelines / brand pack** the terms name. The URL
      they give (`nationalrail.co.uk/static/documents/Developer_Guidelines.pdf`)
      returns 404, but the document is published: the developer page links the
      **Developer Brand Guidelines** PDF inside a ZIP with the logos, and it
      was read on 28 September 2026. What it requires is quoted verbatim in
      `docs/dtd-licensing-and-data-access.md`
- [x] Recorded the answers below, in writing, with the date read
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

The marketplace rows are products whose §5 fill controls use. The two timetable
rows are the same form with that fill set opposite ways, which is the whole
reason one of them may be published from and one may not. The DTD row is a
separate portal subscription and must be checked against the current NRE/DTD
terms; it must not be treated as an OGL or RSP product by analogy.

| product | agreement | §5 permits publication? | attribution required | licence fee | read |
|---|---|---|---|---|---|
| Darwin Timetable Files | OGL v3.0 | **no** — "internal business purposes only" | OGL fallback wording (§8 gives none) | nil | 22 Sep 2026 |
| NWR Schedule | OGL v3.0 | **yes** — "The raw data may be made freely available or otherwise distributed to third parties" | OGL fallback wording (§8 names none) | nil, `Open (OGL3)` | 16 Oct 2026 |
| Knowledgebase Ticket Types data feed | Data Sharing Agreement | **yes** — "freely available or otherwise distributed to third parties" | credit Rail Delivery Group (cl. 3.3.1) | nil | 22 Sep 2026 |
| Knowledgebase Ticket Restrictions data feed | Data Sharing Agreement | **yes** — same wording | credit Rail Delivery Group (cl. 3.3.1) | nil | 22 Sep 2026 |
| Fare Locations Reference Data v1.3 | Data Sharing Agreement | **yes** — same wording | credit Rail Delivery Group (cl. 3.3.1) | nil | 22 Sep 2026 |
| **NRDP/DTD fares and timetable** (RSPS5045 fares and public timetable ZIPs) | NRDP terms, read from the filed copy | **yes** — "copy, publish, distribute and transmit", and commercial exploitation in an End User Product | NRE source credit, the **Powered by National Rail Enquiries** logo and a link to NRE (both done, `--notices nre`) | **nil** — the charging document confines charges to Darwin Webservice feeds, which this build never calls | 28 Sep 2026 |

The licences themselves are in `licences/`, one PDF per product, with the register that
these rows are drawn from and a test that keeps the two in step.

The requirements the permission comes with, and how the release meets them: the
acknowledgement is done (`--notices nre`, a link and the mark); the fee is nil on
a published document; and the two time conditions have no subject in this feed's
own data, because the fares it supplies carry no time and no platform number.
**Time-Bound Data** is defined by the licence — "any data … provided in
conjunction with instruction for the timeliness of its display; platform numbers
for example" — so the display requirement has nothing to bite on. The **static
computed time** question would decide a page that shows this feed's times, and
the release does not: every time a station page prints is NWR Schedule's, cleared
on 16 October 2026 in `licences/release-clearance.md`. The reading is therefore
owed by that product's section and not by this one.
One thing no document can answer: the portal registration must be true, and only
the account holder can see the registered purpose.

- [x] Researched the DTD/NRE route and recorded the source links and caveats in
      `docs/dtd-licensing-and-data-access.md`
- [ ] Confirmed that the account subscription includes **Fares, Routeing Guide and
      Timetable data**, not only the Knowledgebase feeds
- [x] **The Darwin timetable product schedule is read, and the pages do not show
      times.** The daily build no longer loads the national timetable, so the
      published pages carry prices only and Schedule 1 §5's "internal business
      purposes only" reading is never exercised. `licences/release-clearance.md`
      excludes the product with that reason rather than clearing it. The times
      went back by the second route rather than by answering §5: Network Rail's
      own CIF schedule is published under the Open Government Licence, and that
      path — the licence, the whole-CIF reader, and the glob the gate reads — is
      in `docs/dtd-licensing-and-data-access.md` ("NWR Schedule and the Network
      Rail open data feeds"), ADR-0073 and `docs/open-work.md`.
- [x] **The publishable timetable's licence is cleared — 16 October 2026.**
      NWR Schedule, Network Rail, OGL v3.0, §5 permitting distribution and §7
      confining exercise to the UK; the PDF is in `licences/`, the row is in
      `licences/README.md` and the cleared section is in
      `licences/release-clearance.md`. Darwin's version of the same document stays
      excluded with its §5 reason. The **delivery route** is settled too: the
      workflow reads `SCHEDULE_URL` and a credential for it
      (`SCHEDULE_USERNAME`/`SCHEDULE_PASSWORD`, falling back to the fares pair),
      probes the address for two bytes before any feed is downloaded, fetches the
      CIF with `schedule_download.py`, and builds the network with `--timetable`.
      `docs/github-pages-deployment.md` holds the configuration steps.
- [x] Read the current DTD/NRE terms and recorded the public-use/attribution
      answer — publication and commercial exploitation are permitted; see
      `docs/dtd-licensing-and-data-access.md`
- [x] **NRE is acknowledged as source** in the footer of every route that shows a
      fare, in the terms' own words (`--notices nre`), in the template so no
      regeneration can drop it. The station route is that page; the chooser
      shows the feed's station index and the privacy notice shows no fare, and
      the reading that neither needs the credit is recorded in
      `licences/release-clearance.md` and enforced by
      `tools/check_source_credit.py`, which fails a release route showing a fare
      without the mark and the words
- [x] The required **Powered by National Rail Enquiries** treatment/logo is
      visible in the generated page. The Developer Guidelines are published
      from `nationalrail.co.uk/developers/` — not from the URL the terms name,
      which 404s — and were read on 28 September 2026. The mark is the file they
      supply, inlined so the self-contained page still shows it, linked to
      NRE's site, and placed underneath the information, which is what they
      require where the feed is the page's predominant information. The mark is
      painted white — one of the three colours the guidelines permit ("blue,
      black or white") — so the rendering is theirs rather than a reversal
      awaiting permission; the pale blue it replaced was none of the three
- [x] The **Darwin-consistency** requirement has no subject in this feed:
      no arrival or departure time on a page is derived from it, so nothing from
      it has to stay consistent with Darwin forecasts. The times a page shows are
      NWR Schedule's, cleared on 16 October 2026 against its own terms, and
      whether a static scheduled time is a "forecasted" one in these terms' sense
      stays unread because no time on the page is theirs to ask about
- [x] **A monitored contact route exists.** The privacy page names the public
      issue tracker (`https://github.com/lydenyardley/TrainBudgetExplorer/issues`,
      `DEFAULT_PRIVACY_CONTACT` in `build_demo_page.py`, ADR-0068) and prints no
      email address. The owner confirmed on **14 October 2026** that its
      notifications reach an address they read, which is what the page promises
      a reader. `licences/release-clearance.md` holds that decision under
      `privacy contact`, dated and expiring a year later, and
      `tools/check_release_clearance.py` stops treating it as outstanding. It is
      a circumstance rather than a term, so the confirmation is repeated when
      the record expires rather than inherited. `PRIVACY_CONTACT` or
      `--privacy-contact` can name a different route: record the override there
      and clear the route it names instead.
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

- [x] **Rail Delivery Group credited as the source** for the three Data Sharing Agreement
      feeds — a *condition* of the licence under cl. 3.3.1, in any reasonable manner, and
      never in a way suggesting the publisher endorses the page. `--notices rdg`
      does it, worded to the Knowledgebase and fare-locations products it
      actually covers; it used to claim the fares as well, which credited the
      wrong licensor for data that came from NRE
- [x] **National Rail Enquiries credited as the source** of the fares and the
      timetable, which the RDG credit is not — `--notices nre`, the third
      attribution this page needs and the one the portal terms require
- [x] **The OGL fallback wording** for each OGL timetable, since their §8 gives no
      statement — Darwin's and NWR Schedule's alike, and it is only NWR
      Schedule's that is published from: `Contains public sector information licensed under the Open Government Licence v3.0.`
- [x] Neither is read off a blank §8 and treated as "nothing required" — the blank field
      names additional third-party licensors, of which there are none
- [x] The wording is pinned in one place in the code, not retyped into a build
      command where the next regenerator can drop it — `NOTICES` in
      `build_demo_page.py`, with the workflow passing the four names

## 3. The fee term

- [x] `Licence Fees` for the timetable: **nil** (Schedule 2, `Open (OGL3)`)
- [x] The DTD/NRE fee term: **nil, from the published charging document**
      (v06-01, read 28 September 2026). Charges apply only to the Darwin
      **Webservice** feeds, above 5 million enquiries per user per 28-day
      railway period at 0.042p each; Darwin **Push** feeds are `N/A`
      throughout, and static downloads make no enquiries at all. This is a
      document, not a working conclusion
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
2. `python -m tools.check_release_clearance --print` prints the blocks with each
   licence's SHA-256 already filled in, from the PDF when it is on disk and
   from `licences/licence-manifest.json` otherwise (ADR-0067). The digest is
   what stops a clearance outliving the licence it was made from: change the
   manifest, or the local PDF so it no longer matches the manifest, and the
   standing clearance is void until it is made again.
3. Open a pull request. **That review is the approval.** There is nowhere else for
   approval to happen, which is the point.
4. Merge. The next push builds, tests, and passes the clearance gate.
5. Publication stops, rather than the tests going red, if a later release widens
   what it publishes. Adding `--timetable` to the build step changes what
   `--release` is allowed to claim, and the timetable clearance the gate demands
   is what has to be filed before the times can go out at all.

The shape the workflow publishes is `fares,timetable`. The fares-only choice was
the one §5 of the Darwin schedule left open, and the times came back through a
different licence rather than a different reading: `licences/release-clearance.md`
clears NWR Schedule for them and `tools/check_release_clearance.py` maps
`--release fares,timetable` to that product rather than to Darwin's. The RDG letter
at `docs/rdg-licence-enquiry.md` is no longer what the times wait on, and putting
the release back to prices-only means removing the timetable from the build as
well as from `--release`.
