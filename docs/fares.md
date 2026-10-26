# Fares: what a price is, and what the page may claim about it

How a destination is classified, what a fare row is allowed to claim, and
the conditions the page checks before it prints a price.

## Destination types

Destination metadata has one primary settlement class per station from ONS
Census 2021 built-up-area size bands, and any number of independent facets. A
city can also be coastal, a university town or an island without either value
replacing the other.

The primary class is the settlement's population band, and the labels say what
the bands are: `city` (100,000 and over, and 25,000–99,999), `town`
(10,000–24,999), `small_town` (5,000–9,999), `village` (under 5,000) and
`other` for a station whose settlement the workbook does not name at all.
Folding the two smallest bands into one "town" is what left villages filed as
"other"; Ancaster and Bottesford are both `village` now. `other` is still the
payload value for an unnamed settlement, but it is no longer a filter chip:
**No settlement band** read as unfinished work rather than a choice. A
reviewed list covers the places a page prices, so Newcastle is a city, an
airport station is an airport, and Attenborough is a village.

Every facet is one entry in `DESTINATION_FACET_SOURCES` in `trainbudget/fares/atoc_fare_declarations.py`:
the label, the dataset it comes from, where that dataset lives, what geography
it covers, and the reader that turns it into settlement names. The filter chips,
the page payload, the generated cache's provenance and the checked-in reference
data are all derived from that list, so adding a sourced type does not mean
finding a second place to remember. The current facets:

| Facet | Source | Coverage |
| --- | --- | --- |
| `seaside` | ONS Census 2021 coastal communities built-up areas | England and Wales |
| `university` | UK Learning Providers, universities keyed by UKPRN and HESA provider id | United Kingdom |
| `heritage` | UNESCO World Heritage List, UK properties, with a reviewed list of the stations they are reached from | United Kingdom |
| `island` | reviewed station list (see below) | England, Wales and Scotland, as the DTD feed covers them |
| `airport` | reviewed list of rail stations serving a UK airport | United Kingdom, as the DTD feed covers them |
| `nature` | reviewed list of stations reaching The Wildlife Trusts' reserve sites and the WWT wetland centres, from the station each reserve or trust page names | United Kingdom, as the DTD feed covers them |
| `transport` | reviewed coach, tram, metro, stadium, and parkway or park-and-ride locations, matched from the feed's own station names | United Kingdom, as the DTD feed covers them |
| `rspb` | reviewed list of stations reaching RSPB reserves, linked by the hybrid closest-station prune | United Kingdom, as the DTD feed covers them |
| `national_trust` | reviewed list of stations reaching National Trust visitor properties, linked by the hybrid closest-station prune | England, Wales and Northern Ireland, as the DTD feed covers them |
| `national_park` | reviewed gateway stations for National Parks and National Landscapes (AONBs), linked by the hybrid closest-station prune | England, Wales and Scotland, as the DTD feed covers them |

`reference-data/destination-facets.json` is the checked-in, source-backed
mapping, and `tools/regenerate_destination_facets.py` rebuilds it from those
sources against a real fares download. A facet whose source is temporarily
unreachable can be carried forward with `--keep-unavailable`, which prints what
it could not read rather than writing a file that quietly lost it.

`tools/check_facet_reference.py` is what keeps the checked-in copy honest. It
regenerates the file into a temporary directory and compares the result with the
repository's copy, naming every facet that moved and the station codes it gained
or lost; it exits 1 on a difference, 2 when a facet could not be read or the copy
is missing, and 0 when the two agree. The deploy workflow runs it on every build,
so a source that ships without the file being regenerated fails the run instead
of classifying stations from an older registry.

The three day-out sources ADR-0062 put on the backlog shipped on 7 October
2026, in that ADR's order: 9 RSPB reserves, 9 National Trust visitor properties
and 19 National Park / National Landscape gateways, each one reviewed list on
its own facet, each station linked by the hybrid closest-station prune from
`adr/ADR-0063-hybrid-closest-station-prune.md`. The decision is recorded in
`adr/ADR-0065-three-day-out-sources-ship-on-one-reviewed-list-each.md`, and
ADR-0062's non-goals (no VisitBritain dump, no full NHLE sweep, no raw OSM
tourism tags, no polygon-wide landscape tagging) still hold.

Coastal & seaside follows the chip-implies-named-proof rule in
adr/ADR-0064-seaside-chip-implies-named-coastal-proof.md: ONS stays primary,
a reviewed CRS supplement covers Blackpool / Brighton / Southend / Weston, and
COASTAL_SITE_PROOFS must name a day-out for every seaside-tagged station.

The `nature` list is a floor, and the tool that keeps it honest is
`tools/propose_nature_stations.py`. Given reserve pages it reads the station
each one names, matches it against the codes the feed carries, and prints every
proposal **with the sentence it came from**. It writes nothing: a proposal is not
a reviewed list, and only a person can say a reserve is worth a destination
category.

```
python -m tools.propose_nature_stations   --url https://www.wildlifetrusts.org/nature-reserves   --allow-host essexwt.org.uk --allow-host ywt.org.uk
```

## Fare-construction points are not places

The feed prices fares *through* things that are not stations. `BOUNDARY ZONE 4`
is where a fare changes from an inner to an outer London zone; `BRIGHTON
UNIZONE` and `METRO T&W ZONE A` are the same idea; `KINGS LYNN COACH` and
`DEREHAM (COACH)` are a coach stop standing in for the town it serves. No
train calls at any of them, so the page must not offer one as a destination to
be priced to or an origin to depart from, and the coverage report must not let
them top the "most reached" table.

They are a reviewed list, `FARE_CONSTRUCTION_CRS`, keyed by the feed's own CRS
rather than matched on the station name. A substring test over names looks
equivalent and is not: it would drop a real station the day anyone called one
Coach House, and it would stop catching a zone the day the feed renamed it. The
CRS is the feed's identity for a station, so a rename shows up as a dead code
instead.

The evidence that the list is current comes from
`tools/propose_fare_construction_stations.py`, which applies the name markers to
the feed's station records and prints every match with its code, marking which
are already reviewed and which are not. It writes nothing, for the same reason
the nature proposer does: a proposal is not a reviewed list. On the 24 September
2026 download it matched the twelve reviewed codes and nothing else — eight
zones, four coach stops — and it also reports the other direction, a reviewed
code that no longer matches any name, which is what a withdrawn zone looks like.

```
python -m tools.propose_fare_construction_stations --feed feeds/fares
```


Four limits worth stating plainly. `island` is a reviewed list, not an
official one: no UK open dataset names island *settlements* at a size this page
cares about, so the entry says so in its own `source` text. `transport` and
`nature` are reviewed too, and say so the same way: the coach, tram, metro and
parkway tags come from the feed's own station names, with a small list of
settlements the markers catch wrongly (Bushey, BUSBY, CAMBUSLANG and Shepherd's
Bush are places, not interchanges), and the nature tag only credits reserves a
Wildlife Trust or the WWT actually manages. The three day-out sources ship that
way too: `rspb`, `national_trust` and `national_park` are reviewed lists, and a
station on one of them has been checked against the coordinates in the
Knowledgebase file, so a town that merely shares an attraction's name cannot
claim it. `heritage` has a
reviewed settlement side for the same reason — UNESCO names whole properties,
not the towns inside them — but its site ids are checked against UNESCO's live
list on every build, so a delisted site stops tagging destinations and a
curated station name that no longer exists is reported rather than ignored.
The primary settlement classes come from ONS built-up-area population bands,
not from a general gazetteer: a real village or hamlet can therefore have no
band. Rather than showing **No settlement band**, the page keeps the `other`
value in the payload for auditing and covers the places it prices with a
reviewed list; a station-to-settlement or station-to-LSOA crosswalk is still
the honest way to close the remaining gap. TfL is not a source for any of this — its data covers Greater
London only, so it can describe London stations and nothing else in the
network. A page only offers the types its own destinations carry, because a
chip that can only ever return nothing reads as a broken control.

## What the ticket conditions are, and what checks them

A restricted fare's row carries the feed's own ticket code, and the wording
that code stands for is in that row's own disclosure, beside the times: the
restriction's description, and the outward and return validity it permits
(`VALID AFTER 0859 MON-FRI`, `NOT VALID TO ARR KGX BEFORE 1000`). A single shows
only the outward text — it has no return leg for a return condition to
constrain. The wording is the fares feed's own, because a price and the
condition attached to it must come from the same publication.

Because that feed is a snapshot, the page also says what the **portal's own
restriction feed** was asked and answers it above the table, where a reader
comparing two prices will read it. The Knowledgebase `ticket-restrictions` feed
is published on its own schedule, and comparing the two answers a question the
fares file cannot answer alone: does the portal still publish the conditions
printed beside these prices?

**What is compared is publication, never wording.** That is not a simplification
— it is the only thing the feed can honestly be asked, and it was found by
running the comparison against the real download. The two feeds describe the
same conditions in different vocabularies:

| code | fares feed | portal's own record |
|---|---|---|
| `3V` | `VALID ON ANY TRAIN 0930 OR LATER M-F` | "Not valid to depart the origin station shown on the ticket until 09:30" |
| `B3` | `VALID AFTER 0859 MON-FRI` | "Not valid on trains timed to depart after 04:29 and before 09:00." |

The same condition, once compressed into the `.RST` field and once written out in
prose, because the fares text is per-journey and the portal's is per-ticket-type.
Compare the two texts and every condition differs: word for word, the real feed
reported **628 of 628 conditions disagreeing** on a feed where nothing at all
did. A page saying that is crying wolf, and a reader who sees it once stops
reading the line that tells them what is actually true.

The four answers, and none of them is a fifth:

- **still publishes all of them**, with the number of conditions covered and the
  date the reference feed was published;
- **no longer lists some**, naming the codes — the wording shown stays the
  fares feed's, because that is the publication the prices come from;
- **could not be checked**, with the reason;
- **not checked**, when no reference feed was named.

The count is the conditions **the page's own rows carry**, gathered from those
rows rather than from the feed's header list or from the origin's flows. All
three have been the wrong answer at some point, and the real feed shows why: it
holds 841 headers, Grantham's flows carry 32 codes between them, and the page's
rows show 10. A check built from the feed's list claimed to have covered 628
conditions on a page that shows 10; a check built from the flows named `2H` and
`HR` as retired while the page displayed neither. The count spans the ticket
modes the page offers, because all of them are on it: on Grantham's page four
codes sit in the all-returns mode and eight in the singles mode, and the
reviewed Anytime Day Return set carries none at all — which is what that set is
for, and why it is a filter beside the opening list rather than the list itself.

**The check reports its own uncertainty, and that is the design.** The
Knowledgebase feeds' exact element names are not published in a form this
project can verify, so the reader recognises records by local name from a set of
plausible spellings and counts what it did not recognise. An unrecognised
record, a missing feed, or **zero conditions to check** all resolve to "could
not be checked" — never to "still publishes all of them". A record whose wording
the reader could not find is also not a missing condition: a reader that looked
in the wrong place must not tell a reader the portal retired something it never
looked at.

The publication date comes from the downloader's recorded `Last-Modified`, not
from the build's clock. A claim about someone else's data has to rest on their
date for it; "built today" is a fact about the build, and a page sits on a
server long enough for that to quietly become false. The portal sends no
`Last-Modified` on these feeds, so in practice the page says when *we* last
asked and not when the portal last published — which is the honest half of the
claim, and all this feed offers.

The fares feed stays the authority. A condition the portal no longer lists is
reported to the reader, never resolved in either direction.

**Checking the guess.** The reader matches element names from a set of plausible
spellings, and that set was a guess until it was checked against a real
download. `tools/inspect_knowledgebase.py` is how you check it:

```
python -m trainbudget.feeds.dtd_download --output-root feeds --kb-only   # needs NRDP credentials
python -m tools.inspect_knowledgebase feeds/knowledgebase
```

It prints every element name in the feed with its count, depth and a sample of
its text; which of the four fields the reader currently matches each to; the
names carrying text that it matches to nothing; and the specific line to add
when a name is a near miss. It then reports what a page built on that feed would
say, in the reader's own words — so the tool cannot describe the reader
differently from how the build behaves. `--json` for the same report
machine-readably.

It reads the local file and never writes to the reader, so running it against
the real feed is safe precisely when the reader is wrong. A feed the reader
cannot use exits zero: the report is the deliverable, and a non-comparable feed
is the situation the tool exists for.
