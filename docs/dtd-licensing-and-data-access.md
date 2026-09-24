# DTD licensing and data-access research

**Research date:** 24 September 2026  
**Status:** implementation guidance, not a legal opinion or a written RDG entitlement confirmation

## Executive conclusion

The intended zero-cost route is a periodic, authenticated download from the
National Rail Data Portal (NRDP), historically called the National Rail / DTD
data service. The public charging material says that most NRE data feeds,
including feeds used by independent and commercial developers, are free; the
high-volume charge described there applies to Darwin Webservice feeds, not to
scheduled static DTD downloads. On that evidence, the DTD subscription is a
**documented working assumption of £0 for this project**, subject to the
account's current terms and any product-specific schedule.

That conclusion is not the same as a signed permission to publish. Before a
public page goes live:

1. confirm that the account has the separate **Fares, Routeing Guide and
   Timetable data** subscription;
2. read the current DTD/NRE terms and developer brand pack again;
3. keep the National Rail Enquiries attribution/branding requirement visible;
4. do not treat a Knowledgebase subscription as evidence of DTD entitlement; and
5. obtain written clarification from RDG if the portal or a schedule says that
   a fee or additional permission applies. The letter to send is drafted in
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

## Licensing decisions

### DTD/NRE: preferred route, conditional publication permission

The charging document is the basis for the zero-cost working conclusion. The
current NRE developer terms also require acknowledgement of NRE as the source.
Where an NRE feed is the predominant or standalone data source, the September
2026 developer brand pack calls for the official:

> Powered by National Rail Enquiries

The logo must be included with the static HTML output (inlined or otherwise
included in the self-contained page), alongside, above, or below the relevant
information as the pack requires. Do not imply that RDG/NRE endorses the page.
If commission is enabled, the page must also disclose the affiliate relationship.

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

- [ ] DTD fares and timetable downloads both succeed with the same account.
- [ ] The current DTD/NRE terms and brand pack have been reread.
- [ ] The page visibly acknowledges NRE as source and includes the required
      **Powered by National Rail Enquiries** treatment/logo.
- [ ] KB-derived station/ticket-reference data is credited to **Rail Delivery
      Group, via Rail Data Marketplace**, where those products are used.
- [ ] No RSP ultimate-source notice is added unless an RSP licence is actually
      the source.
- [ ] Darwin is not used as a substitute public timetable source.
- [x] The reviewed `publishable_destinations_within` selector exists: it keeps
      only the exact standard-class ANYTIME DAY R ticket codes and blank
      restriction codes, and it refuses to run unless the `.RST` file parsed
      cleanly. It still refuses railcard discounts, because the `.RST` railcard
      records are parsed but not evaluated. The broad `destinations_within` query
      remains for analysis only.
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
