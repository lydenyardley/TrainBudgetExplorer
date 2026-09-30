# Glossary — Train Budget Explorer

| Term | Meaning |
|---|---|
| **Anytime fare** | Walk-up fare valid on (almost) any train; flat price, timetable-independent. The safest fare class for a static budget tool. |
| **Off-Peak fare** | Cheaper walk-up fare, valid outside defined peak restrictions; flat price but validity varies by flow/day. |
| **Advance fare** | Cheap per-train fare, yield-managed, sold out per service. Cannot be promised by a static tool. |
| **Fares flow** | A priced origin→destination pair in the fares data (the unit of the Fares Feed). |
| **Ticket restriction code** | The two-character code on a fare that selects its validity rules (`B1`, `C4`, `Y2`, …). A blank code is how the DTD feed marks a fare with no restriction of its own. |
| **Restriction file (`.RST`)** | The RSPS5045 file holding the restriction rules the codes point at. `atoc_restrictions.py` reads it, and `publishable_destinations_within` refuses to publish unless it parsed cleanly. |
| **Publishable selector** | `publishable_destinations_within`: the reviewed query that keeps only exact standard-class ANYTIME DAY R tickets with a blank restriction code. A railcard price is evaluated against the current `RR` rows in the same feed: a matching total ban removes the discount, and a matching restriction code supplies the travel condition (ADR-0025). |
| **Fares Feed** | The ATOC/NRE master file of all fares between all flows, released ~3×/year; legacy format. |
| **Darwin** | NRE's real-time engine; its timetable/schedule feeds give the national train schedule (open data). |
| **Rail Data Marketplace** | raildata.org.uk — the portal through which NRE/industry data products (including fares) are licensed. |
| **Isochrone** | Map of places reachable within a time limit from a point. This project is a "fare-ochrone": reachable within a *price* limit. |
| **Origin station** | The user's starting station (e.g. Grantham). |
| **Budget** | The user's maximum spend; must be defined per passenger or per party (open question). |
| **Return / single** | Round-trip vs one-way ticket. Most day trips price as a return; the tool's default unit is a return. |
| **Party** | The travelling group (couple, family). Fares multiply per adult/child — a core correctness trap. |
| **MTD** | Making Tax Digital — appears in this workspace's other project docs, unrelated here. |
| **CIF** | Common Interface Format, the fixed-width timetable record format used by the timetable feed. |
| **TIPLOC** | The seven character code that identifies a location in the timetable feed, such as GRNT. One station can hold several. A CIF location field is eight characters wide; the eighth is a flag, so the parser takes the first seven before stripping and reports how many keys that changed. |
| **CRS code** | The three letter station code passengers see, such as GRA for Grantham. Note that the synthetic feed in this project invents `GRN` for Grantham, and no real feed contains it. |
| **Calling point** | One stop on a schedule, with its arrival and departure times. A schedule is an ordered list of them. |
| **Station names file** | The MSN feed that maps each TIPLOC to a station code, a name, and a minimum interchange time. |
| **STP indicator** | Whether a schedule is permanent (`P`), an overlay (`O`), new (`N`), or a cancellation (`C`) of a permanent schedule. |
| **Service days** | The seven character Monday to Sunday pattern saying which days a schedule runs on. |
| **Schedule** | One train's plan for one period: an identity, a date range, service days, and its calling points. |
| **Overlay** | A schedule that replaces the permanent schedule of the same train identity for its date range. |
| **Onward departure cap** | How many of the earliest departures at an interchange the one-change search will consider. Currently 200, chosen by measurement. |
| **Transfer-only pair** | An origin and destination whose only route needs a change. The set where a departure cap can lose a journey. |
| **Hub-and-spoke feed** | An invented feed where one hub is the only place two routes meet, so every journey past it needs a change. |
