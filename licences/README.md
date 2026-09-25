# Licence register

One row per Rail Data Marketplace product this project has taken a licence for.
Each licence was downloaded from the product's licence tab while signed in, which is
the only way to reach it (ADR-0005), and each PDF is kept here, untouched, exactly as
it downloaded: the filename carries the product id the licence refers to in Schedule 1
§3 `LICENCED DATA`, so the file and the entry can always be matched up.

**Read date for every licence below: 22 September 2026.**

Legend for the `§5 permitted purposes` column: `internal only` means the licence
forbids publication; `distribute` means it permits it. That single distinction decides
whether a product can appear on a public page (ADR-0021).

| product | id | agreement | §5 permitted purposes | §8 attribution | fee | update |
|---|---|---|---|---|---|---|
| Darwin Timetable Files | `P-9ca6bc7e-62e1-44d6-b93a-1616f7d2caf8` | OGL v3.0 | **internal only** — "may be copied and used by Data Consumer for internal business purposes only" | list empty, no statement given | nil, `Open (OGL3)` | daily |
| Knowledgebase Ticket Types data feed | `P-51e17973-7327-4735-a7ca-d2a484a56065` | Data Sharing Agreement | **distribute** — "may be made freely available or otherwise distributed to third parties" | list empty; T&Cs cl. 3.3.1 still requires crediting the Data Publisher | nil, `Open` | other or unknown |
| Knowledgebase Ticket Restrictions data feed | `P-2d177d2e-dcb8-43dc-ac4d-3a967dd35c5e` | Data Sharing Agreement | **distribute** — same wording | list empty; same cl. 3.3.1 obligation | nil, `Open` | other or unknown |
| Fare Locations Reference Data v1.3 | `P-4f4a90ff-d4e2-442e-93b3-07121430f303` | Data Sharing Agreement | **distribute** — same wording | list empty; same cl. 3.3.1 obligation | nil, `Open` | daily |
| Easy Fares API (Demo Version) | `P-37faed36-518a-4870-b1bd-b675461fb72e` | Data Sharing Agreement, `Bespoke` | **distribute** — "may be **sold or otherwise distributed to third parties for commercial gain**" | RSP and NRE, per the licensing document (§8 defers to it) | free to **100 hits**, then access ceases | daily |

The first four share a Data Publisher: **Rail Delivery Group** (2nd Floor, 1 Puddledock,
London EC4V 3DS). The Easy Fares demo's publisher is **BR Fares Ltd** (Quadrant House,
20 Broad Street Mall, Reading RG1 7QE), and its §10 adds one special condition: the
information **must not be changed or misrepresented**.

Common to all five: the term is **1 year, renewing automatically**; data received may be
**retained** after the term; the Data Consumer field is blank on every export.

The NRE charging/terms and brand-pack source documents are supporting evidence,
not per-product Marketplace licences, so they do not have a product-id row:
`National Rail Data Portal Terms-and-conditions.pdf` and the charging document
linked from `docs/dtd-licensing-and-data-access.md`. `BR Fares RDM Pricing.pdf`
is likewise a supporting price schedule.

Differences worth knowing:

| | Darwin Timetable Files | the three Data Sharing Agreement feeds |
|---|---|---|
| agreement body | none — OGL head plus Schedules | contractual T&Cs (clauses 1–8) plus Schedules |
| order of precedence | n/a | T&Cs, then Schedule 1 excluding Special Conditions, then Special Conditions (cl. 8.8) |
| territory | Global, with a prohibited-country list | **UK** |
| notice to terminate for convenience | 1 month | 1 week |
| prohibition on publication | cl. none stated, but §5 restricts use to internal business purposes | none — cl. 2.3 forbids publication *except* as the Agreement allows, and §5 allows it |

## What the register is used for

- `publish-checklist.md` §1 — the four licence questions per product.
- ADR-0020 — the Darwin reading, and the conflict inside it.
- ADR-0021 — the finding that §5 varies by product, and what that means for the page.
- `tests/test_licences.py` — asserts every PDF in this folder has a row above and every row
  names a file that exists, so a licence can never be downloaded, filed, and forgotten.

## DTD access (preferred zero-cost route)

The current working route for bulk fares and timetable data is the National Rail
Data Portal (NRDP/DTD), not a per-query fare API. The public NRE charging
material says that most NRE feeds, including feeds used by independent and
commercial developers, are free; the high-volume charge is for Darwin
Webservice feeds rather than scheduled static DTD downloads. This is a
**documented zero-cost working conclusion**, not a written RDG confirmation.
The account must separately subscribe to **Fares, Routeing Guide and Timetable
data**; the Knowledgebase feeds listed in the project research do not establish
that entitlement.

The DTD/NRE terms require acknowledgement of NRE as source, and the current
developer brand pack calls for the official **Powered by National Rail
Enquiries** treatment/logo where the feed is predominant or standalone. The
full source list, caveats, fallback, and escalation contacts are in
`docs/dtd-licensing-and-data-access.md`.

The fares product is not represented by one of the marketplace PDFs in this
folder yet. That is expected: DTD is a portal subscription/download route,
not one of the product schedules already registered above. Do not infer a
price or publication permission for DTD from the absence of a PDF; verify the
account and current terms before launch.

## Considered and not taken for the zero-cost build

The **RSP Data Licence**, from Rail Settlement Plan Limited, remains a
possible alternative route, but its published template contains a licence-fee
field and a possible Datafeeds Charge, with permitted-use and schedule fields
completed per licensee. It is not a documented zero-cost route. If RDG quotes
a non-zero fee, reject it and retain DTD.

The **Easy Fares API** remains a small real-data sanity check only. It is a
station-pair query API with a paid usage schedule after its demo allowance and
is the wrong shape for a locally held bulk feed used to rank every destination
from an origin.

### Paid API detail

The **Easy Fares API** from BR Fares Ltd is published on this marketplace in three volume
tiers — and the volume tier names are a price list, not a service level. Low volume is
£50 per block of 1,000 calls with no recurring fee; medium and high add £500 and £1,000
per 30 days respectively (BR Fares RDM Pricing.pdf, filed here, is the schedule). It is a
paid product, and it is the wrong **shape** as well as the wrong price: it is keyed by
station pair, while this project answers "cheapest return to every destination from this
origin" out of a locally held bulk feed. No client is written for it (ADR-0022). Its
**demo** tier is held, but for a sanity check rather than to sit under the page — legal
though that would be, since its §5 permits sale for commercial gain.
