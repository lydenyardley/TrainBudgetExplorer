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

Common to all four: Data Publisher is **Rail Delivery Group** (2nd Floor, 1 Puddledock,
London EC4V 3DS); the term is **1 year, renewing automatically**; data received may be
**retained** after the term; the Data Consumer field is blank on every export.

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
- `test_licences.py` — asserts every PDF in this folder has a row above and every row
  names a file that exists, so a licence can never be downloaded, filed, and forgotten.

## Not yet held

The **fares product itself** — the one carrying the flows and fares records (`ffl`) and
the railcard minimum fares (`rcm`), and a railcards feed (`rlc`). Everything above is
reference and rules data: names, codes, ticket types, restrictions. None of it contains
a price. Until that licence is read, the question that decides this project is open.

Two leads on where it comes from, both recorded in ADR-0022:

- **The RSP Data Licence**, held from Rail Settlement Plan Limited and obtained by
  contacting Rail Delivery Group. BR Fares Ltd's own licensing page describes it as
  governing the fares data, requiring that RSP be named as the ultimate source where the
  data is shown publicly, and states that RSP Data Licences are **"generally free of
  charge"**. This is the licence to ask RDG for.
- **A free demo**, if a real-data sanity check is wanted before the bulk feed arrives:
  the Easy Fares API demo allows 100 calls per 30 days at no charge.

## Considered and not taken

The **Easy Fares API** from BR Fares Ltd is published on this marketplace in three volume
tiers — and the volume tier names are a price list, not a service level. Low volume is
£50 per block of 1,000 calls with no recurring fee; medium and high add £500 and £1,000
per 30 days respectively. It is a paid product, and it is the wrong **shape** as well as
the wrong price: it is keyed by station pair, while this project answers "cheapest return
to every destination from this origin" out of a locally held bulk feed. No client is
written for it (ADR-0022).
