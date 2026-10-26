# ADR-0016: The seller and the network to publish with

**Status:** Accepted, conditional — the seller and the network are recorded; nothing
tracked publishes until the fares licence is read
**Date:** 22 September 2026
**Relates to:** ADR-0001 (data sources and the licence gate), ADR-0003
(monetisation), ADR-0005 (the account blocker), ADR-0010 (the page stays local),
ADR-0014 (which left this open)

## Context

ADR-0014 ended by naming three things still open: the production seller, the
network, and the real rate. The owner asked for the licence side and the
affiliate side to be put next to each other, and for a seller and a network to be
recorded.

The comparison is lopsided, and that is the finding. The affiliate side is
publicly readable. The licence side is not: the terms that decide what may be
published are the ones behind the account in ADR-0005.

## The licence side, and what changed

New evidence, read this session, that sharpens ADR-0005 rather than overturning
it:

- **The contract set is published in the open.** Rail Delivery Group publishes
  the RDM platform agreements, the data sharing agreement template, and an
  adapted Open Government Licence. So the *shape* of the terms is knowable
  without an account even though the operative text is not.
- **Licences are per product, in two shapes.** A product is offered either under
  the adapted **OGL3** (open; reuse encouraged) or under the generic **Data
  Sharing Agreement** with a per-product **Schedule 1**. Products on both sides
  exist in the catalogue today, so "open data" is real but product-specific.
- **The DSA is generic, and Schedule 1 carries the particulars.** It is made
  between the data publisher and the consumer; Rail Delivery Group operates the
  platform, is not a party, and gives no warranty. **`Licence Fees` is a defined
  term**, so a product may be charged for.
- **Darwin is a click-accept, not a plain open licence.** The feeds are enabled
  by subscribing on the Marketplace and accepting terms and conditions there.
- **The National Rail portal's own terms open with the open-data framing**
  ("encouraged to use and re-use the Information ... freely and flexibly, with
  only a few conditions"), which is the timetable side's most likely licence
  shape — read from an indexed snippet, because the page body is behind the same
  JavaScript shell as the rest of the portal.

| question | fares feed (RJFAF, Marketplace product) | timetable (Darwin / CIF) |
|---|---|---|
| licence shape | OGL3 **or** DSA + Schedule 1, per product | click-accept terms on subscription |
| commercial use | **unread** | **unread** |
| attribution | **unread** | **unread** |
| redistribution | **unread** | **unread** |
| licence fee | `Licence Fees` is a defined term; **unread** | **unread** |
| readable without an account | no | a single opening line only |

Every unread cell is unread for one reason, and it is the same reason: the
Schedule 1 that fills the template in is on the product's licence tab, which
needs the session.

## The affiliate side

| programme | network | rate claimed | source and quality |
|---|---|---|---|
| Trainline | **Partnerize** | "Partnerize network rates and terms", no number published | Trainline's own partnerships page, corroborated by a Partnerize signup page for the programme |
| Trainline | — | 3% per sale; separately 20%; separately 4–5.5% | three affiliate directories, mutually inconsistent, none authoritative |
| TransPennine Express | Awin | 4% on Advance purchase | Awin merchant listing (ADR-0014) |
| **TrainPal** (Trip.com's UK rail brand) | **CJ (Commission Junction)** | 2% per sale | a branded CJ publisher signup page in TrainPal's own name, plus directory listings |
| TrainPal | Indoleads, Involve Asia, MyLead (regional) | "share 60% of commission" style reshares | network offer pages; none authoritative |
| Trip.com UK (TrainPal's parent) | Awin | Train 2%, among other category rates | Awin merchant listing 22405 |
| National Rail | none found | — | no programme surfaced in any search this session |

Two networks are implemented, `awin` and `partnerize`, and the rate is set inside
the network: joining is the only way to see it. A 3% figure and a 20% figure for
the same programme cannot both be the published rate, which is the reason this
ADR chooses on a known pairing rather than on a claimed rate, exactly as
ADR-0014 did.

### TrainPal, considered and not chosen

TrainPal is a real second seller with a real programme, and it has one advantage
over the chosen pairing: **a number**. Its 2% train rate is listed, where
Trainline publishes none and where two directories disagree by a factor of seven.
A rate you can read is worth more than a rate you can only discover after joining.

It is still not the seller, for three reasons.

1. **Its programme is on CJ, which this project does not implement.** Adding it is
   a third `AffiliateNetwork` entry, not the data-only edit ADR-0014 promised —
   and the redirect wrapper would be written without a live programme to test it
   against, which is the same unverified-URL problem in a new place.
2. **It is not the biggest retailer**, and the audience is a reader who wants to
   buy a ticket, not to compare apps. Coverage and link fidelity were the criteria
   ADR-0014 set, and they still point the same way.
3. **Credibility at the launch venue.** ADR-0003 launches to r/uktrains, where
   TrainPal's parent is discussed with suspicion. Recorded fairly: the ASA has
   upheld complaints against **both** candidates — Trainline in August 2025 over
   "you won't find cheaper tickets anywhere else", and Trip.com in November 2025
   over railcard adverts — so an advertising-standards ruling does not separate
   them, and this is a reason to stay neutral about the claim rather than a reason
   for Trainline.

What would change this: TrainPal becoming the choice would need a verified search
URL and a deliberate move to CJ. The comparison above is the starting point for
that decision, not a prohibition on it.

## The side by side that decides it

| seller | link fidelity | programme known to run | can earn |
|---|---|---|---|
| **National Rail** | verified: takes CRS station codes directly, which is what this tool holds | none found | no |
| **Trainline** | unverified: its URL parameters have not been checked against the live site | yes, on Partnerize | yes, at an unknown rate |

A seller with no programme cannot fund an affiliate hypothesis at all. A seller
whose link might land on an empty search can lose the click it is paid on. Both
runner-up weaknesses point the same way here, and one of them is cheap to close:
the Trainline URL is verifiable **without** the account, by opening a link that
`build_demo_page.py` already writes.

## Decision

1. **Publish with Trainline, through Partnerize.** It is the only pairing on the
   table where a programme is known to exist, and a lead-gen asset pointed at a
   seller that pays nothing is not the asset ADR-0003 chose. National Rail keeps
   its place as the *default link*; it does not become the publishing seller.
2. **National Rail remains the untracked default**, because its links are the
   ones whose parameters this tool has actually verified. The two roles are
   different and both are needed.
3. **Two preconditions, neither met today.** The tracked variant does not enter
   the page until both hold:
   - the fares product's Schedule 1 permits commercial use and the intended
     presentation and attribution, which is the licence read ADR-0001 has been
     waiting on;
   - the Trainline search URL is verified against the live site, so the first
     reader to click it lands on a real search rather than an empty one. Attempted
     and refused: `adr/ADR-0017-what-the-live-link-check-found.md` records the bot
     check, the 403, and the fact that the same check found the *default* link
     broken too.
4. **The application still happens after the demo has traffic** (ADR-0003), and
   a low-traffic application may still be rejected. Nothing here changes that
   risk, and nothing here relaxes ADR-0010: the page stays local until the
   licence is read.

## Consequences

- `retailer.py` already declares `usual_network="partnerize"` for Trainline, so
  the recorded pairing is the one `pairing_warning` stays quiet about. The code
  and the record now agree instead of the record being silent.
- The build command for the recorded pairing is:
  `python -m trainbudget.build.build_demo_page --feed <feeds> --timetable <feeds> --origin GRN
  --provider trainline --affiliate-network partnerize --advertiser-id <id>
  --publisher-id <id>`
- Because tracking is a redirect wrapper (ADR-0014), changing the seller later
  does not change where a reader lands. This decision is therefore reversible at
  the price of editing a URL and a test — the irreversible part is the licence,
  not the seller. That is deliberate.
- If the Schedule 1 forbids commercial use, this decision dies rather than the
  project: the page survives as a demo or portfolio piece and the affiliate plan
  in ADR-0003 dies instead (ADR-0010). The comparison above is still what the
  next seller decision starts from.
- **Still open:** the real rate, every unread cell in the licence table above,
  and both preconditions in item 3. Recording the seller and the network does not
  close the gate; it names what is waiting behind it.
- **Added later the same day:** the live check in `adr/ADR-0017-what-the-live-link-check-found.md`
  found that neither link can currently be trusted to land on a search, which is a
  second launch blocker beside the licence and does not change this decision. The
  page's answer to it — defaulting to the seller's own search page rather than a
  parameterised search — is `adr/ADR-0018-the-pages-default-link.md`.
