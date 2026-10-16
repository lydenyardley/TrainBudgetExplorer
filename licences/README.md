# Licence register

One row per Rail Data Marketplace product this project has taken a licence for.
Each licence was downloaded from the product's licence tab while signed in, which is
the only way to reach it (ADR-0005). The PDFs are kept in this folder on a machine
that holds them, and they are not in git (ADR-0067). `licence-manifest.json` is the
tracked shelf: filename, SHA-256, and the product id the filename carries from
Schedule 1 §3 `LICENCED DATA`, so the file and the entry can always be matched up.
A local copy that does not match the manifest fails `tests/test_licences.py` and
the release gate.

**Read date: 22 September 2026 for every licence below except NWR Schedule, read on
16 October 2026.**

Legend for the `§5 permitted purposes` column: `internal only` means the licence
forbids publication; `distribute` means it permits it. That single distinction decides
whether a product can appear on a public page (ADR-0021).

| product | id | agreement | §5 permitted purposes | §8 attribution | fee | update |
|---|---|---|---|---|---|---|
| Darwin Timetable Files | `P-9ca6bc7e-62e1-44d6-b93a-1616f7d2caf8` | OGL v3.0 | **internal only** — "may be copied and used by Data Consumer for internal business purposes only" | list empty, no statement given | nil, `Open (OGL3)` | daily |
| NWR Schedule | `P-dbd92416-2f09-4f72-ad42-d53bbfec50f3` | OGL v3.0 | **distribute** — "The raw data may be made freely available or otherwise distributed to third parties" | list empty, no statement given, so the OGL fallback wording applies | nil, `Open (OGL3)` | daily |
| Knowledgebase Ticket Types data feed | `P-51e17973-7327-4735-a7ca-d2a484a56065` | Data Sharing Agreement | **distribute** — "may be made freely available or otherwise distributed to third parties" | list empty; T&Cs cl. 3.3.1 still requires crediting the Data Publisher | nil, `Open` | other or unknown |
| Knowledgebase Ticket Restrictions data feed | `P-2d177d2e-dcb8-43dc-ac4d-3a967dd35c5e` | Data Sharing Agreement | **distribute** — same wording | list empty; same cl. 3.3.1 obligation | nil, `Open` | other or unknown |
| Fare Locations Reference Data v1.3 | `P-4f4a90ff-d4e2-442e-93b3-07121430f303` | Data Sharing Agreement | **distribute** — same wording | list empty; same cl. 3.3.1 obligation | nil, `Open` | daily |
| Easy Fares API (Demo Version) | `P-37faed36-518a-4870-b1bd-b675461fb72e` | Data Sharing Agreement, `Bespoke` | **distribute** — "may be **sold or otherwise distributed to third parties for commercial gain**" | RSP and NRE, per the licensing document (§8 defers to it) | free to **100 hits**, then access ceases | daily |

The Darwin product, the three Data Sharing Agreement feeds and the Easy Fares demo share
a Data Publisher: **Rail Delivery Group** (2nd Floor, 1 Puddledock, London EC4V 3DS).
The Easy Fares demo's publisher is **BR Fares Ltd** (Quadrant House, 20 Broad Street
Mall, Reading RG1 7QE), and its §10 adds one special condition: the information **must
not be changed or misrepresented**. **NWR Schedule's is Network Rail** (The Quadrant,
Elder Gate, Milton Keynes MK9 1EN), and its §7 is the one territorial restriction in the
table: exercise of the licensed rights is permitted in the **UK** only.

Common to all six: the term is **1 year, renewing automatically**; data received may be
**retained** after the term; the Data Consumer field is blank on every export.
NWR Schedule also reports its permitted recipients as "All registered users", and its
Schedule 2 states no fair-usage policy and no non-chargeable limit — the two fields
where a licence would impose a volume ceiling are the ones it leaves blank.

The NRE terms, brand guidelines, developer pack and charging document are
supporting evidence, not per-product Marketplace licences, so they do not have a
product-id row: `National Rail Data Portal Terms-and-conditions.pdf`,
`NRE Developer Brand Guidelines September 2026.pdf` and
`NRE Feeds Developer Pack v.01-05.pdf`, all filed here untouched, plus the
charging document linked from `docs/dtd-licensing-and-data-access.md`.
`BR Fares RDM Pricing.pdf` is likewise a supporting price schedule.

| document | issued by | what it decides here | read |
|---|---|---|---|
| National Rail Data Portal Terms-and-conditions | NRE | permission to copy, publish and commercially exploit the Information, on three requirements | 28 Sep 2026 |
| NRE Developer Brand Guidelines | NRE | the source acknowledgement: a link to NRE plus the "Powered by National Rail Enquiries" logo, placed alongside, above or underneath the information the feed supplied | 28 Sep 2026 |
| NRE Feeds Developer Pack v.01-05 | RDG / NRE | a technical description of the feeds, including that the static Darwin Timetable feed carries no live movements. Carries no attribution requirement, so it is not the document the terms name | 28 Sep 2026 |
| NRE Usage Charging Document v06-01 | NRE | the fee: charges apply only above 5 million enquiries per user per 28 days, and only to the Darwin Webservice feeds | 28 Sep 2026 |

The terms name
`nationalrail.co.uk/static/documents/Developer_Guidelines.pdf`, which returns
404. The brand guidelines above are the document that requirement points at, and
the file that the ZIP carried it in — `assets/powered-by-national-rail.svg` — is
the mark the page inlines, byte for byte.

Differences worth knowing:

| | Darwin Timetable Files | NWR Schedule | the three Data Sharing Agreement feeds |
|---|---|---|---|
| agreement body | none — OGL head plus Schedules | none — OGL head plus Schedules, on the same form | contractual T&Cs (clauses 1–8) plus Schedules |
| order of precedence | n/a | n/a | T&Cs, then Schedule 1 excluding Special Conditions, then Special Conditions (cl. 8.8) |
| territory | Global, with a prohibited-country list | **UK**, and no prohibited-country list | **UK** |
| notice to terminate for convenience | 1 month | 1 month | 1 week |
| prohibition on publication | cl. none stated, but §5 restricts use to internal business purposes | none — §5 permits it outright, and §8 names no attribution statement | none — cl. 2.3 forbids publication *except* as the Agreement allows, and §5 allows it |

The two OGL products are the same document with one field changed, and that field is the
whole difference between a timetable this project may publish and one it may not. Both
heads grant use "worldwide, royalty-free, perpetual, non-exclusive"; Darwin's §7 then
lists prohibited countries, and NWR Schedule's permits exercise **within the UK**. That
is the one condition on the publishable timetable that is not a formality, so it is
recorded rather than assumed away (ADR-0021).

## What the register is used for

- `publish-checklist.md` §1 — the four licence questions per product.
- ADR-0020 — the Darwin reading, and the conflict inside it.
- ADR-0021 — the finding that §5 varies by product, and what that means for the page.
- `tests/test_licences.py` — asserts every product on `licence-manifest.json` has a row
  above and every row names a product on the manifest. When the PDFs are on disk, each
  hash has to match. A licence can never be downloaded, filed, and forgotten.

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

The DTD/NRE terms require acknowledgement of NRE as source, and the Developer
Brand Guidelines (filed above) require a link to NRE's site and the official
**Powered by National Rail Enquiries** logo where the feed is predominant or
standalone. The page carries both. The full source list, caveats, fallback, and
escalation contacts are in `docs/dtd-licensing-and-data-access.md`.

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
