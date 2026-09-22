# ADR-0022: The BR Fares APIs are not the fares source, and the bulk feed is

**Status:** Accepted
**Date:** 22 September 2026

## Context

The fares product that this project needs — the one carrying the flows and fares
records (`ffl`) and the railcard minimum fares (`rcm`) — has not been found by name on
the Rail Data Marketplace. ADR-0020 recorded that the legacy `RJFAF` prefix is not a
product name, and ADR-0021 recorded the four licences since taken out, none of which
contains a price.

The Rail Data Marketplace's own assistant pointed at the **Easy Fares API**, from
**BR Fares Ltd**, in three tiers: high, medium and low volume. The question asked of it
was whether "pricing model" means a fee. It does, and the numbers are published.

## Decision

1. **The API is paid, in tiers, at a rate that does not fit this product.** From the
   BR Fares price schedule effective 1 July 2025:

   | tier | recurring cost per 30 days | included calls per £50 block | cost per call |
   |---|---|---|---|
   | demo | none — **100 calls per 30-day period** | — | free |
   | low volume | none; £50 per block used | 1,000 (Easy Fares) | ~5p |
   | medium volume | £500 | 5,000 | ~1p |
   | high volume | £1,000 | 20,000 | ~0.25p |

   One call is one request — "a query for all fares between two stations". Billing is per
   whole £50 block, minimum contract 30 days, and **nothing is charged in a month with no
   calls** at the low tier.

2. **Reject it on shape, not only on cost.** This is the more decisive reason. The page
   is generated at build time into a single static file with no server and no request per
   row (ADR-0004, ADR-0005); the parser answers "cheapest return to every destination from
   this origin" by querying a **locally held bulk feed** as often as it likes. An API keyed
   by station pair inverts that: one origin's page would need roughly one call per
   destination — a few thousand calls for a full rebuild of one origin, and the sweep
   queries many origins. Rebuilding it monthly as fares change multiplies that again. The
   bulk feed costs one download and unbounded local queries.

   The demo is worth knowing about and is **free at 100 calls per 30 days**, which is
   enough to see what real fare records actually look like — a legitimate use, and useful
   for checking this project's modelling assumptions against real data without paying.

3. **The API's own licensing page names the licence this project actually needs.** BR
   Fares holds an **RSP Data Licence** from Rail Settlement Plan Limited and an **NRE
   Service Licence** from Train Information Services Limited, and states that:

   - the **RSP Data Licence** governs the fares data, and where information is displayed
     publicly "the end user must be made aware that **RSP is the ultimate source** of the
     data ... however in this case there is no requirement to display any particular
     branding";
   - the **NRE Service Licence** governs only the `restriction.details` objects, and where
     those are displayed publicly the **"Powered by National Rail Enquiries" logo** must
     appear;
   - an API user may in certain circumstances need **its own RSP Data Licence**, obtained
     by contacting Rail Delivery Group, and that **"RSP Data Licences are generally free of
     charge"**.

   So the target is the **bulk fares feed under an RSP Data Licence**, and the licence is
   named, is held by others for exactly this kind of public-facing fares service, and is
   normally free. That is a request to put to Rail Delivery Group, not a fee to budget for.

4. **Do not display restriction details.** They are the one part carrying the NRE branding
   obligation. The page shows a fare code and a price, not restriction text, which keeps
   the requirement out of scope by design rather than by accident. If restriction text is
   ever added, the logo comes with it.

5. **Ask Rail Delivery Group once, for both things.** The Darwin timetable's §5
   restriction (ADR-0020, ADR-0021) and the bulk fares feed under an RSP Data Licence are
   the same conversation with the same publisher and should travel in one message.

## Consequences

- **The fares question is now a permission question, not a purchase question.** Nothing
  here needs a budget line; it needs an answer from RDG and a product to download.
- **A free demo is available as a reality check.** 100 calls per 30 days would let the
  project compare this parser's answers against the National Rail fares database for a
  handful of routes — the first real-data check of the pricing model, and it costs
  nothing but the subscription.
- **No new code is implied.** The API is rejected, so no client is written for it, no
  key is stored, and the static-page architecture is untouched.
- **The attribution list grows again.** Beyond ADR-0021's two attributions, an RSP Data
  Licence would add a third: RSP named as the ultimate source. The register and
  `publish-checklist.md` should carry it once the licence is actually held, not before.
- **This is the second option rejected on licence and shape grounds**, after TrainPal
  (ADR-0016) and scraping (ADR-0001). The pattern is holding: the project accepts a
  constrained or missing data source rather than an unlicensed or uneconomic route.
