# Glossary — Train Budget Explorer

Three lists, because they answer three different questions. The first is what a
reader sees on a station page. The second is what a seller or an analyst asks
for. The third is what this codebase calls things, and none of it is ever
printed for a reader.

## The words the page uses

| Term | Meaning |
|---|---|
| **Station page** | The page for one origin station. It answers "where can I go from here, and what will it cost". One page per station (ADR-0019). |
| **Priced place** | A destination the fares feed publishes a fare for from this station, which the page can therefore put a number against. The page's own list is made of these, plus the two-ticket places below (ADR-0061). |
| **Reachable place** | A destination a train can actually get you to, with the connection time the feed states, within one change. Larger than the priced list, and measured to be much larger: from Grantham, 582 stations are reachable within one change on Monday 5 October 2026 and 50 are priced. |
| **Two-ticket place** | A destination the feed prices in two parts: a fare from the origin to a calling point on the journey shown, plus a fare from there to the destination. It becomes one row priced at the sum, naming both tickets and the pricing-split station (ADR-0061). The split need not be where the reader leaves the train, and the row's own railcard price is the two card fares added together, with the feed's minimum fare applied to each ticket. |
| **The build's own day** | The date the page was built for. It is the default the reader sees when they touch nothing, and it is why the page cannot say "today". A build may be days old. |
| **The chosen day** | The date the reader has selected in the day control. It changes the Time and Changes columns and nothing else, not the list, not the prices (ADR-0060). It travels in the address as `day=N`, so a shared link opens on the sender's day. |
| **A day of the week is not a date** | Sunday 4 October 2026 reaches 238 stations from Grantham and Sunday 11 October reaches 416, and 50 of the 220 both reach have a different time. The day control therefore names a date, with the weekday leading. |
| **Fastest time** | The journey in minutes that arrives soonest, and among those the one with the fewest changes. The Time column. It is a property of the chosen day, not of the fare. |
| **Changes** | How many times the reader leaves one train and boards another. Zero reads "Direct". It comes from the timetable, not from the fare, so it moves with the day while the price does not. |
| **Within one change** | The reach the page claims. Measured against the alternative: a two-change search takes 236 seconds per origin-day against 1.0 for one change, and reads 8.6 million onward departures against 38,628, for 23% more stations (ADR-0061). |
| **Split ticket** | Buying a journey as two or more tickets rather than one. The row says where the split would be and what each part costs. Two tickets means two purchases, from two sale points, and the page does not promise they are available together. |
| **Budget** | The price limit the reader sets. It filters rows; it does not change what a fare costs. |
| **The count above the table** | How many places are inside the budget right now, under every filter in force. ADR-0040 controls what may stand between it and the first row. |
| **Feed record** | The disclosure in a row's panel carrying the ticket code, route, quality and restriction validity, for a reader who needs to sell or check rather than travel. ADR-0053 moved the code there from the table. |
| **Destination type** | The chip in the refinement bar: a settlement band (city, town, small town, village) or one sourced facet. A type is offered only where the page can prove it, so the chip comes with named proof under the station's name (ADR-0026, ADR-0064). |
| **Named proof** | The subline a chip carries: the World Heritage property, the reserve, the beach or the gateway that station actually reaches, linked to the source's own page. |
| **Railcard collection** | The cards this feed prices, offered as one control with nothing selected by default. Naming one prices it per fare and per row, and the browser remembers the choice per station (ADR-0052). |

## What a seller asks for

| Term | Meaning |
|---|---|
| **Anytime fare** | Walk-up fare valid on (almost) any train; flat price, timetable-independent. The safest fare class for a static budget tool. |
| **Off-Peak fare** | Cheaper walk-up fare, valid outside defined peak restrictions; flat price but validity varies by flow and day. |
| **Advance fare** | Cheap per-train fare, yield-managed, sold out per service. Cannot be promised by a static tool, and is not the default on a row. |
| **Fares flow** | A priced origin→destination pair in the fares data. It is the unit the page's price query walks. The flow set follows the industry's published fare routes, not the journeys passengers buy, which is why Grantham→Aberdeen arrives as two flows and not one. |
| **Ticket restriction code** | The two-character code on a fare that selects its validity rules (`B1`, `C4`, `Y2`, …). A blank code is how the DTD feed marks a fare with no restriction of its own. |
| **Restriction file (`.RST`)** | The RSPS5045 file holding the restriction rules the codes point at. `atoc_restrictions.py` reads it, and `publishable_destinations_within` refuses to publish unless it parsed cleanly. |
| **Publishable selector** | `publishable_destinations_within`: the reviewed query that keeps only exact standard-class ANYTIME DAY R tickets with a blank restriction code. A railcard price is evaluated against the current `RR` rows in the same feed: a matching total ban removes the discount, and a matching restriction code supplies the travel condition (ADR-0025). |
| **Fares Feed** | The ATOC/NRE master file of all fares between all flows, released ~3×/year; legacy format. |
| **Darwin** | NRE's real-time engine; its timetable/schedule feeds give the national train schedule (open data). |
| **Rail Data Marketplace** | raildata.org.uk — the portal through which NRE/industry data products (including fares) are licensed. |
| **Isochrone** | Map of places reachable within a time limit from a point. This project is a "fare-ochrone": reachable within a *price* limit. |
| **Origin station** | The user's starting station (e.g. Grantham). |
| **Return / single** | Round-trip vs one-way ticket. Most day trips price as a return; the tool's default unit is a return. |
| **Party** | The travelling group (couple, family). Fares multiply per adult/child — a core correctness trap. |

## Feed shorthand, never shown to a reader

| Term | Meaning |
|---|---|
| **CIF** | Common Interface Format, the fixed-width timetable record format used by the timetable feed. Every record in the reference feed is exactly 80 characters wide, so a probe built on any other width silently reads nothing. |
| **TIPLOC** | The seven character code that identifies a location in the timetable feed, such as GRNT. One station can hold several. A CIF location field is eight characters wide; the eighth is a flag, so the parser takes the first seven before stripping and reports how many keys that changed. |
| **CRS code** | The three letter station code passengers see, such as GRA for Grantham. Note that the synthetic feed in this project invents `GRN` for Grantham, and no real feed contains it. |
| **NLC** | The four character National Location Code the fares feed joins on, against the timetable's seven character TIPLOC. The two are not the same code and the feed carries no table mapping one to the other. |
| **Calling point** | One stop on a schedule, with its arrival and departure times. A schedule is an ordered list of them. |
| **Station names file** | The MSN feed that maps each TIPLOC to a station code, a name, and a minimum interchange time. |
| **STP indicator** | Whether a schedule is permanent (`P`), an overlay (`O`), new (`N`), or a cancellation (`C`) of a permanent schedule. Over the reference feed's 497,121 active schedules: `O` 146,695, `N` 137,018, `P` 129,838, `C` 83,570. |
| **Service days** | The seven character Monday to Sunday pattern saying which days a schedule runs on. |
| **Schedule** | One train's plan for one period: an identity, a date range, service days, and its calling points. |
| **Overlay** | A schedule that replaces the permanent schedule of the same train identity for its date range. |
| **Record type** | In a fares flow record it is the *second* character; the first is the update marker. A reader that filters on the first character reads zero records out of 727,315 and reports an empty feed as a finding. |
| **Onward departure cap** | How many of the earliest departures at an interchange the one-change search will consider. Currently 200, chosen by measurement (ADR-0009). |
| **Transfer-only pair** | An origin and destination whose only route needs a change. The set where a departure cap can lose a journey. |
| **Reviewed list** | A list a person has read and stands behind, rather than a dataset read off a download: RSPB reserves, National Trust properties, park and landscape gateways, islands, airports, coach and parkway interchanges, and the coastal supplement. The reviewed facets say `reviewed` in their own source text, so a page cannot read as though an official list produced them (ADR-0026). |
| **Hybrid closest-station prune** | How a named attraction earns a station: the curated candidate is kept unless the coordinates put it more than 15 km from the attraction, the nearest station per component point is kept plus a soft twin inside 2 km, and a candidate the coordinate file does not locate is kept, because distance cannot judge it (ADR-0063). |
| **Hub-and-spoke feed** | An invented feed where one hub is the only place two routes meet, so every journey past it needs a change. |