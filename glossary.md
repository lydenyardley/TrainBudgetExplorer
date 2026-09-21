# Glossary — Train Budget Explorer

| Term | Meaning |
|---|---|
| **Anytime fare** | Walk-up fare valid on (almost) any train; flat price, timetable-independent. The safest fare class for a static budget tool. |
| **Off-Peak fare** | Cheaper walk-up fare, valid outside defined peak restrictions; flat price but validity varies by flow/day. |
| **Advance fare** | Cheap per-train fare, yield-managed, sold out per service. Cannot be promised by a static tool. |
| **Fares flow** | A priced origin→destination pair in the fares data (the unit of the Fares Feed). |
| **Fares Feed** | The ATOC/NRE master file of all fares between all flows, released ~3×/year; legacy format. |
| **Darwin** | NRE's real-time engine; its timetable/schedule feeds give the national train schedule (open data). |
| **Rail Data Marketplace** | raildata.org.uk — the portal through which NRE/industry data products (including fares) are licensed. |
| **Isochrone** | Map of places reachable within a time limit from a point. This project is a "fare-ochrone": reachable within a *price* limit. |
| **Origin station** | The user's starting station (e.g. Grantham). |
| **Budget** | The user's maximum spend; must be defined per passenger or per party (open question). |
| **Return / single** | Round-trip vs one-way ticket. Most day trips price as a return; the tool's default unit is a return. |
| **Party** | The travelling group (couple, family). Fares multiply per adult/child — a core correctness trap. |
| **MTD** | Making Tax Digital — appears in this workspace's other project docs, unrelated here. |
