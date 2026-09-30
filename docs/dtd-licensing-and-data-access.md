# DTD licensing and data-access research

**Research date:** 24 September 2026  
**Status:** implementation guidance, not a legal opinion or a written RDG entitlement confirmation

## Executive conclusion

The intended zero-cost route is a periodic, authenticated download from the
National Rail Data Portal (NRDP), historically called the National Rail / DTD
data service. Both halves of that are now answered from published documents
rather than assumed, and both were re-read on 28 September 2026:

- **Permission.** The portal terms grant copying, publishing, distributing,
  transmitting and commercial exploitation of the Information in an End User
  Product. Publication is inside the grant; see "The portal terms" below.
- **Fee.** The Usage Charging Document confines charges to high-volume use of
  the Darwin **Webservice** feeds, above 5 million enquiries per user per
  28-day period. This build makes no Webservice enquiries, so the DTD
  subscription is **£0 for this project on a published document**, not on a
  working assumption.

What is still open is compliance with the terms' three requirements, and none of
it is a question a footer can answer. Before a public page goes live:

1. [x] the account holds the separate **Fares, Routeing Guide and Timetable
   data** selection — evidenced by the two static-feed downloads recorded in
   `feeds/download-manifest.json`, not by the Knowledgebase feeds;
2. [x] the current DTD/NRE terms have been read; the Developer Guidelines and
   brand pack they name return 404, so the mandated wording and logo treatment
   are unverified;
3. [ ] whether a **static computed time** is a "forecasted" time the terms
   require to stay consistent with Darwin, and how Time-Bound Data must be
   displayed — both are answered by the unpublished guidelines;
4. [x] the National Rail Enquiries source acknowledgement is on every page
   (`--notices nre`), and the Knowledgebase data is credited to the Rail
   Delivery Group (`--notices rdg`) — a third credit, not a replacement;
5. [ ] obtain written clarification from RDG on anything the guidelines or the
   account screen says differently. The letter to send is drafted in
   `docs/rdg-licence-enquiry.md`.

The project will not use Easy Fares, an RSP Data Licence fee, or any other paid
API as its production data source.

## The two NRDP subscriptions

The URLs supplied for this project are the **Knowledgebase (KB) API** feeds.
They provide reference and service information, including station and ticket
metadata. They do not, by themselves, provide the bulk fares or timetable
files.

| Access | Endpoints/format | What it supplies |
|---|---|---|
| DTD | `POST /authenticate`, then `GET /api/staticfeeds/2.0/fares` and `/api/staticfeeds/3.0/timetable`; ZIP responses | RSPS5045 fares and the public passenger timetable |
| Knowledgebase | the seven URLs recorded below; XML responses | service indicators, incidents, TOCs, ticket restrictions/types, promotions, and stations |

The Knowledgebase URLs supplied for this project are:

- National Service Indicators — <https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/serviceIndicators>
- Incidents — <https://opendata.nationalrail.co.uk/api/staticfeeds/5.0/incidents>
- TOCs — <https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/tocs>
- Ticket Restrictions — <https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/ticket-restrictions>
- Ticket Types — <https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/ticket-types>
- Public Promotions — <https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/promotions-publics>
- Stations — <https://opendata.nationalrail.co.uk/api/staticfeeds/4.0/stations>
- Documentation — <https://wiki.openraildata.com/index.php/KnowledgeBase>

The DTD registration page currently lists **Fares, Routeing Guide and Timetable
data** as a separate subscription. A successful token proves that the account
authenticated; it does not prove that a particular feed is entitled. A 401 or
403 from a DTD endpoint is therefore reported as a possible missing
subscription, not treated as an empty feed.

## Sources examined

The conclusions above were checked against these public sources (all links
were consulted on 24 September 2026 unless a source is explicitly a historical
or supporting document):

- [NRDP registration](https://opendata.nationalrail.co.uk/registration) — account
  registration and feed-subscription selection.
- [NRDP terms](https://opendata.nationalrail.co.uk/terms) — current portal terms.
- [NRE developer page](https://www.nationalrail.co.uk/developers/) — developer
  access and current brand-pack link.
- [NRE Knowledgebase feeds](https://www.nationalrail.co.uk/developers/knowledgebase-data-feeds/)
  — description of the KB XML feeds.
- [NRE Usage Charging Document v06-01](https://assets.nationalrail.co.uk/e8xgegruud3g/1FMZaTCkitl5TXLHyEAEvw/a493521c9d9a4e90c012bfce5b16363a/Usage_Charging_Document_v06-01.pdf)
  — free-feed and high-volume charging distinction.
- [Open Rail Data Wiki: National Rail Data Portal](https://wiki.openraildata.com/index.php/National_Rail_Data_Portal)
  and [DTD](https://wiki.openraildata.com/index.php/DTD) — endpoint and
  authentication examples.
- [UK2GTFS ATOC documentation](https://itsleeds.github.io/UK2GTFS/articles/ATOC.html)
  — DTD ZIP contents (`.MCA`, `.MSN`, and ancillary files) and fares format.
- [NWR Schedule product](https://raildata.org.uk/dataProduct/P-dbd92416-2f09-4f72-ad42-d53bbfec50f3/termsAndConditions)
  — free OGL3 fallback, daily update, and UK territory.
- [Darwin Timetable Files product](https://raildata.org.uk/dataProduct/P-9ca6bc7e-62e1-44d6-b93a-1616f7d2caf8/termsAndConditions)
  — the product-specific internal-use restriction discussed below.
- [RSP Data Licence template v07-00](https://raildata.org.uk/dataProduct/P-37faed36-518a-4870-b1bd-b675461fb72e/termsAndConditions)
  and the BR Fares licensing information — the paid/negotiated alternative,
  retained only as a documented comparison.

## DTD technical and operational contract

The downloader uses the following protocol:

```text
POST https://opendata.nationalrail.co.uk/authenticate
Content-Type: application/x-www-form-urlencoded
username=...&password=...
        -> JSON object containing "token"

GET https://opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares
X-Auth-Token: <token>

GET https://opendata.nationalrail.co.uk/api/staticfeeds/3.0/timetable
X-Auth-Token: <token>
```

The implementation deliberately reads credentials only from
`NRDP_USERNAME` and `NRDP_PASSWORD` (lowercase `NRDP_username` and
`NRDP_password` are also accepted for compatibility with UK2GTFS). It does not
accept a password on the
command line, put credentials in a URL, or write them to a manifest. Downloads
go through a temporary file, are checked for the expected format and required
members, and are atomically moved into the ignored `feeds/` tree. A failed or
unrecognised response cannot overwrite a previously good archive.

Default output layout:

```text
feeds/
  fares/dtd-fares.zip
  timetable/dtd-timetable.zip
  knowledgebase/*.xml       # when --kb or --kb-only is used
  download-manifest.json    # non-secret hashes, sizes, URLs, and timestamps
```

The manifest is optional (`--no-manifest`) and is itself inside the ignored
feed directory. It is a provenance aid, not a credential store.

## Feed formats and audit expectations

### Fares

The DTD fares response is a ZIP containing the RSPS5045 fixed-width files,
including the `FFL` flow/fare records and the location/ticket/railcard files
used by `atoc_fares.py`, plus the `RST` restriction file. The downloader requires
an `.FFL` member; the parser then reports all files it did or did not recognize.

`atoc_restrictions.py` reads the `RST` records: `RH` headers, `HD`/`TD` date
bands, `TR` time rules, `TT` TOC rules, `RR` railcard restrictions, and the
`SD`/`SQ`/`SR`/`CA`/`EC`/`RD` records the real feed carries. The real DTD file
holds 468,516 records across 12 types; the parser keeps counts, headers, and
samples rather than claiming to evaluate every rule.

### Timetable

The DTD timetable response is a ZIP containing the public passenger timetable,
normally including `.MCA` and `.MSN` files. Ancillary files such as `.FLF`,
`.ALF`, `.TSI`, `.SET`, `.DAT`, `.ZTR`, or rejected-data files may be present.
The downloader requires `.MCA` and `.MSN`; the parser audit reports ancillary
files separately. The current project does not yet interpret every CIF
restriction/public-service field, so a successful parse is not yet a licence to
publish every parsed schedule.

### Knowledgebase

The supplied KB endpoints are expected to return XML and are validated as
well-formed XML rather than as HTML login/error pages. They are reference
feeds, not substitutes for DTD fares or timetables.

Run:

```bash
python dtd_audit.py
```

The command validates the archives first, then runs the existing
`feed_audit.py` report. It distinguishes missing, empty, non-ZIP, invalid,
unrecognized, mixed, multiple-archive, and parser-rejected data. A valid but
empty result is never silently treated as proof that a feed is current. Keep
one current ZIP in each default feed directory; do not mix it with loose files
or an older archive.

### How a refresh works

The DTD fares ZIP is republished weekly and the public timetable ZIP daily. A
refresh is `python dtd_download.py` followed by `python dtd_audit.py` and a page
rebuild: the downloader writes the new archive atomically and records its
non-secret URL, size, and SHA-256 in `feeds/download-manifest.json`, and the
build reads whatever ZIP is current. There is no scheduled job or server in the
repository, so the cadence the project actually runs at is the cadence of that
manual command (or the CI workflow's feed artifact). The page's provenance line
comes from the feed's `metadata.json`, which is why a refresh does not require
retyping where the numbers came from.

The fares side of the audit now reports the restriction file separately:
``restrictions: files 1, records 468516, codes 841, railcard codes 331,
rejected 0``. A non-zero ``rejected`` count here is a publication blocker,
because the reviewed selector depends on the whole restriction file.

The timetable side separates the unresolved TIPLOCs into categories. On the
real DTD file that is 1,146 unresolved: 1,070 are known CIF locations with a
blank CRS (operational or non-passenger places, not missing records), and 76
have no record at all. The audit also reports the 1,294 TIPLOCs whose raw
seven-character value needed normalisation, which is how a padded location
field such as ``ABHLJN 2`` stopped acquiring a second key.

## The portal terms, read 28 September 2026

Read from the copy filed in `licences/`, whose footer is dated 24/09/2026 and
which is the document served from `opendata.nationalrail.co.uk/terms`.

**Permission is granted, and it is explicit.** The licensee is free to "copy,
publish, distribute and transmit the Information", to "adapt the format", and to
"exploit the Information commercially … by including it in Your own product or
application ("End User Product")". The build's route — a static HTML page
carrying fares and times, published publicly, with ticket links that may be
affiliate-linked — is inside that grant. The terms also bar any use that
suggests official status or NRE endorsement, which the page's wording avoids.

**Three requirements come with it**, and they are compliance, not permission:

1. Registration information must be true and accurate. The portal asks what the
   data is for and where it will be used, so an account registered without a
   public page in mind is a defect in the account, not in this build.
2. The licensee must "acknowledge NRE as the source of Information in
   accordance with this agreement and the Developer Guidelines". The
   acknowledgement is now carried by `--notices nre`; the Guidelines that would
   fix the wording are the 404 above.
3. "All forecasted arrival and departure times, provided by Your End User
   Product(s), are consistent with Darwin forecasts", and "all Time-Bound Data
   … are displayed as directed in the Information, as per the Developer
   Guidelines". This build computes its times from the static timetable
   download rather than from Darwin, so whether a static computed time is a
   "forecasted" time in the terms' sense is the question that decides whether
   times may be published at all. It is not a footer question, and no footer
   can answer it.

The warranty position is as expected and is what the accuracy notice says: the
Information is provided as is, with no representation or warranty and no
liability; the governing law is England and Wales.

**The entitlement is evidenced, not assumed.** `feeds/download-manifest.json`
records the fares feed (48.5 MB, 24 members) and the timetable feed (76.2 MB, 9
members) downloaded on 24 September 2026 from
`opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares` and `.../3.0/timetable`.
Those endpoints are the Fares, Routeing Guide and Timetable selection, and they
returned their files, so the account holds it. The Knowledgebase feeds, a
separate entitlement, were downloaded on 28 September 2026 and are **not** the
evidence for this one.

## The Developer Brand Guidelines, read 28 September 2026

The terms name `nationalrail.co.uk/static/documents/Developer_Guidelines.pdf`,
which returns 404. The document they mean is published from
<https://www.nationalrail.co.uk/developers/>, which links a **Developer Brand
Guidelines** PDF inside a ZIP with the logos — "Use of these logos and brand
materials are subject to permission from National Rail" refers to the other
brand materials, not to this attribution, which the guidelines themselves
instruct. Both were downloaded on 28 September 2026:

- `DEVELOPERS_BRAND_GUIDELINES_AND_LOGOS_SEPTEMBER_2026.zip` → "FB-6184
  Developer Brand Guidelines - National Rail .pdf" and
  `National Rail Logos/Powered by National Rail.svg` (8.3KB, paths only, no
  fonts or external references).
- `NRE_Feeds_Developer_Pack_v.01-05.pdf` — a technical description of the feeds,
  last updated 11 October 2019. It carries no attribution requirement, so it is
  not the document the terms name.

**Licence condition, verbatim:** "You must acknowledge National Rail as the
source of Information in accordance with this document, including Developer
brand Guidelines".

**Attribution, verbatim:** "The user of NRE feeds (You) must acknowledge NRE as
the source of information, where possible, by providing a link to the NRE
website for more information and by displaying the 'Powered by National Rail
Enquiries' logo in accordance with the Brand Guidelines and the following
conditions", followed by:

- "Where an NRE feed is displayed as the predominant or standalone information
  in Your product or service, NRE attribution should be shown directly
  alongside, above or underneath the Information derived from the feed";
- "Where an NRE feed is combined with other data feeds and/or is not the primary
  information being displayed, NRE branding may be shown on an attribution page";
- "Where NRE feeds are displayed on a dot matrix screen, the words 'Powered by
  National Rail Enquiries' should be used as static or scrolling text";
- "The logo must be sized appropriately to the screen displaying information and
  must be legible to viewers";
- an exemption route: where the recommendations cannot be followed, or would
  harm the end user's experience, contact
  `NationalRailDatafeeds@raildeliverygroup.com` to discuss alternatives or an
  exemption.

This page's fares and times *are* the predominant information, so the first
condition applies and an attribution page would not do: the mark sits in the
footer, directly underneath the results, with the link to NRE beside it. The
`Powered by` mark is used, not the National Rail wordmark, because the
wordmark is the brand's own and this page is not National Rail's.

Two things the guidelines do not answer, and which no attribution can: whether
a static computed time is a "forecasted" time under the terms, and how
Time-Bound Data must be displayed. The Developer Pack is evidence on the first
— it describes the Darwin Timetable feed as republished schedules that "do not
include any information about live train movements or delays", and separately
describes Darwin as *forecasting* the remainder of each schedule from matched
external forecasts — which is an argument, not an answer.

## The charging document, read 28 September 2026

The Usage Charging Document v06-01 recorded in the sources list above is
retrievable (HTTP 200) and answers the fee question outright:

- "In most cases the feeds are free to use whether you (the licensee 'You') are
  a commercial entity, a public sector organisation or a small independent
  developer."
- The only charging model in the document is high-volume use of **chargeable
  Darwin feeds**: the threshold is **5 million enquiries per user per 28-day
  railway reporting period**, and enquiries above it cost **0.042 pence** each.
- "The high-volume usage threshold applies only to Darwin Webservice feeds" —
  the public and staff versions. Every charging row for **Darwin Push Feeds** is
  `N/A`, and "Push feeds, such as Darwin Push Port, are not subject to
  high-volume usage charges."

This build makes no Darwin Webservice enquiries at all: it downloads two static
ZIPs a day and renders them. It is therefore not a user the threshold can apply
to, and the fee term is **nil, from a published document** rather than from a
working conclusion drawn from volume. The Darwin product schedule's own
`Open (OGL3)` nil fee is a separate answer for that product and does not decide
this one.

## Licensing decisions

### DTD/NRE: preferred route, conditional publication permission

The charging document is the basis for the zero-cost conclusion, and it now
answers the question rather than leaving it open: see "The charging document,
read 28 September 2026" below. The current NRE developer terms also require
acknowledgement of NRE as the source, and the Developer Brand Guidelines that
the terms point to are published — not at the URL the terms name, which 404s,
but from the developer page. What they require is set out verbatim in "The
Developer Brand Guidelines" below, and the page now carries it.

The broad OGL wording in a Darwin document does not override a product-specific
schedule. This is why the implementation treats the DTD terms and current
account schedule as the publication gate.

### Darwin: not a public-output source

The Darwin Timetable Files product is marked OGL3, but Schedule 1 §5 says raw
data may be copied and used for **internal business purposes only**. The project
will not publish Darwin-derived output without written permission or a suitable
variation. The OGL3 head is not being used as a shortcut around that fill.

### NWR Schedule: free fallback, not first choice

The NWR Schedule product is documented as free, daily, OGL3, with no fair-use
limit and permission for raw data to be distributed. It is a useful fallback if
DTD access is unavailable, but it is a single gzip CIF rather than the DTD ZIP
shape, has UK rather than worldwide territory, and can contain freight,
empty-stock, and non-public calls. The current parser is not yet a drop-in
replacement. If used, the page should carry the exact fallback attribution:

> Contains public sector information licensed under the Open Government Licence v3.0.

Filtering and parser work would be required before using NWR output publicly.

### RSP Data Licence and Easy Fares: rejected for the zero-cost build

The published RSP template contains a licence-fee field and a possible
Datafeeds Charge, with permitted-use and schedule fields completed per
licensee. It is not a documented zero-cost route. If RDG quotes a non-zero fee,
reject it and retain DTD rather than silently changing the product's cost
model.

Easy Fares is a station-pair query API with a paid usage schedule after its demo
allowance. It is useful for a small reality check, but it is the wrong shape for
this static site, which needs a local bulk feed to rank every destination from an
origin. It is not wired into the page.

If an RSP licence is ever used, its ultimate-source notice and any additional
branding conditions must be reviewed separately; they must not be copied into a
DTD-only page without the corresponding licence basis.

## Attribution and publication checklist

Before a real-data page is published:

- [x] DTD fares and timetable downloads both succeed with the same account —
      `feeds/download-manifest.json`, 24 September 2026.
- [x] The current DTD/NRE terms have been reread, **28 September 2026**, and the
      Developer Brand Guidelines they point to have been found and read — they
      are published from `nationalrail.co.uk/developers/` rather than from the
      URL the terms name, which 404s.
- [x] The page visibly acknowledges NRE as source — `--notices nre`, in the
      footer of every generated route, unprompted and without a click.
- [x] The **Powered by National Rail Enquiries** logo is in the page, inlined
      from the file NRE supplies, linked to NRE's site, placed underneath the
      information the feed supplied, and legible in both palettes.
- [x] KB-derived station/ticket-reference data is credited to **Rail Delivery
      Group, via Rail Data Marketplace** — `--notices rdg`, worded to the
      Knowledgebase and fare-locations products it actually covers.
- [ ] No RSP ultimate-source notice is added unless an RSP licence is actually
      the source.
- [ ] Darwin is not used as a substitute public timetable source.
- [x] The reviewed `publishable_destinations_within` selector exists: it keeps
      only the exact standard-class ANYTIME DAY R ticket codes and blank
      restriction codes, and it refuses to run unless the `.RST` file parsed
      cleanly. Railcard prices are evaluated against the current `RR` rows in the
      same feed, with the `.RCM` minimum fare in force on the day. The broad
      `destinations_within` query remains for analysis only.
- [ ] The timetable audit's rejected records, unopened files, date range, STP
      mix, TIPLOC normalisation, and the unresolved TIPLOC categories (known
      location vs no record) have been read.
- [ ] Affiliate disclosure is present if commission is enabled.

## Known gaps and escalation

The DTD zero-cost conclusion is based on current public terms and charging
material, not a written response to the earlier general enquiry. If the account
screen, a product schedule, or RDG requires clarification, contact:

- `NationalRailDatafeeds@raildeliverygroup.com` — the focused NRE data-feed
  address found in the current developer/charging material; and
- [Rail Data Marketplace support](https://raildata.org.uk/helpAndInformation/contactSupport)
  — choose **Ask a question** → **Consuming data**.

Ask specifically whether the account's DTD subscription includes static fares,
routeing guide, and timetable downloads; whether the intended periodic static
use (including a public page and affiliate links) is permitted; what attribution
and brand treatment applies; and whether any fee is due. Keep the answer with
this document and update the relevant ADR/checklist.

The immediate implementation can proceed without asking the user to disclose a
password in chat. Set `NRDP_USERNAME` and `NRDP_PASSWORD` in the local shell or
an ignored `.env` file, then run `python dtd_download.py`. A missing DTD
subscription is expected to produce an explicit entitlement error, not a false
empty feed.
