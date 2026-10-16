# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: a UK rail traveller with a price ceiling and no chosen destination.**
They want a day out and have a number in mind — "somewhere I can get to for under
£20 return". They are not researching a specific town; the price is the starting
point and the destination is the answer. They arrive from a community post rather
than a search engine (ADR-0003: r/uktrains, local Facebook groups, Hacker News
only if worthy), so they are reading a stranger's recommendation in a thread and
deciding in seconds whether this is worth a click.

**Travelling as a pair is a first-class case, not a variant.** A large share of
readers are two people asking what the trip costs *them*. A railcard is one card
chosen from a collection rather than a single card (ADR-0052): the page offers
every card this feed prices, nothing is selected by default, and the choice is
remembered in the browser instead of being typed again on every page. A chosen
card's discount is priced per fare (ADR-0025): it lowers the fare wherever the
feed's current `RR` rules permit and widens the list the budget reaches, and each
row's own details name the minimum fare in force and the rule behind the answer. A
row the feed prices in two tickets carries a card price of its own as well, the
two card fares added together and the minimum applied to each ticket (ADR-0061).
The undiscounted figure stays the default party total and the budget ceiling,
because the page cannot know who is reading and a ceiling must not move when a
card is named.

**The operator is the owner**, acting part-time. The staged plan bounds the whole
experiment at roughly four weeks part-time, with a hard build stop and a written
review (ADR-0004).

## Product Purpose

Turn a price into a shortlist of places. Given an origin station and a budget, the
page lists **every** destination reachable by train inside that budget, with the
fastest journey time, the number of changes, the cheapest fare of any ticket type
the feed prices to that place for one adult, and the total for two adults on that
same fare (ADR-0025, ADR-0044). A place the feed prices in two published fares is
one row priced at the sum of the two fares the journey itself uses, naming both
tickets and the station the split sits at (ADR-0061). The ticket a row is priced
as is named on the row, and the count line names the mix of ticket types the list
is showing.

It exists as a demand experiment whose commercial shape, if it survives, is
affiliate lead generation (ADR-0003). Success for v1 is therefore a **signal, not
revenue**: clicks from the named community venues, comments, and repeat usage,
weighed at the written review on **21 October 2026** — with the default outcome, if
unsure, being to park the project rather than continue it (ADR-0004).

## Positioning

**It inverts the search.** Every journey planner and fare-enquiry tool this
neighbourhood already has is destination-first: you name where you are going and it
tells you the price. This is price-first: you name the price and it tells you where
you can go. The glossary calls the shape a **"fare-ochrone"** — reachable within a
*price* limit rather than a time limit.

What a neighbouring product could not truthfully copy is the second half of that:
this one publishes its own limits as content. It promises reviewed Anytime Day
**Returns** and says out loud that Advance singles can undercut them; it refuses
not only a chosen train but an unrunnable assumption: the railcard is priced only
where the reader says they hold one and the feed's own current rules allow it, and
it never sends a railcard or a chosen train to a seller; and when no ticket link
could be verified, it was the link —
not the claim — that changed (ADR-0017, ADR-0018). A competitor optimising for
conversion would not make those moves.

## Operating Context

- **The page is generated, not written.** `build_demo_page.py` reads a fares feed
  and a timetable feed and writes one self-contained HTML file. The design source
  of truth is the `TEMPLATE` string in that Python file, not the `demo*.html`
  output, which is derived and gitignored. Regenerating overwrites hand edits.
- **The data is licensed and refreshes on the provider's schedule.** The DTD fares
  feed updates weekly and the public timetable daily; both arrive through the
  National Rail Data Portal account and are pulled by `dtd_download.py`, which
  needs no credentials stored in the repository (environment only). The refreshed
  ZIP replaces the previous one, and the audit and page build read whatever ZIP is
  current, so a rebuild is the update (ADR-0025, `docs/dtd-licensing-and-data-access.md`).
- **How the page is used:** arrive on your own town's page, drag the budget,
  optionally filter to a city or town, switch whether the budget covers one adult
  or the two of them, expand a row for the next few departures, follow the ticket
  link to buy. If you arrived on the wrong town, you change station from the header
  and are taken to that station's page — choosing is navigation, not a filter
  (ADR-0019).
- **Terminology is load-bearing** and collected in `docs/glossary.md`: budget (per adult
  or per party), return (the tool's default unit), flow, CRS code, TIPLOC, overlay,
  fare-ochrone. Note that Grantham's real CRS code is `GRA`; the synthetic feed
  invents `GRN`.
- **Venues and cadence:** community posts at launch (w/c 5 October), referrer
  measurement, an affiliate application only once the licence is read and there is
  traffic, and the 21 October review tripwire.
- **Hosting is chosen but not switched on.** The deploy workflow targets GitHub
  Pages, builds the whole network from the licensed fares feed as a prices-only
  release, and is cleared to publish that shape by `licences/release-clearance.md`
  — which clears `fares` against the filed portal terms and excludes the Darwin
  timetable schedule — so nothing has been served publicly yet
  (`docs/github-pages-deployment.md`, ADR-0010).

## Capabilities and Constraints

**Confirmed functionality.** Station picker (search by name or three-letter code,
resolving to the station's page); budget slider; destination filter by name or code;
destination-type chips, which are the settlement bands plus one chip per sourced
facet in `DESTINATION_FACET_SOURCES` (coastal and seaside, universities, World
Heritage, islands, airports, nature sites, transport interchanges, RSPB reserves,
National Trust properties, and National Park and National Landscape gateways);
party switch (one adult, or two adults on the fare the row names); a railcard
control offering every card this feed prices, with nothing selected by default; a
ticket type
control that opens on the cheapest fare of any type and filters the list to one
of the three named sets; per
destination a price, the fastest journey time, the number of changes, the station
a journey changes at when it changes (where a two-ticket split may be cheaper,
stated without a price), the fare type code, the travel condition the feed states
for a restricted fare, an expander
holding the next few departures, and one ticket link on the row; date-aware
schedules when the page is built with a date, and an explicit note that every
schedule was read when it is not. A build with no timetable says so in its opening
sentence and stands the times columns down rather than describing them. Above the
results — not in a closed disclosure — the page states what the ticket link costs
the reader, and, where links are tracked, what it earns the site.

**A destination-type chip carries named proof behind it.** A chip is only honest
if the row can name the place that earned it, so a tagged row shows a proof
subline under its name: the World Heritage property, the reserve, the beach, the
castle or the reserve the station actually reaches. A source is added as one
registry entry and one reviewed list, never as a second place to remember, so the
chips, the payload and the checked-in reference data all follow from the same
list (ADR-0026, ADR-0064, ADR-0065).

**Hard constraints.**

- **One self-contained HTML file: no server, no build step, no external assets**
  (ADR-0010). No webfonts, no CDN imagery, no framework, nothing fetched at
  runtime. There are currently **no images, logos, icons, or font files in the
  repository at all**, and designing one in means inlining it. A station page
  fetches exactly two documents, and both are the same for every page of the
  route: the picker's station list (`stations.js`) and this route's stylesheet
  (`station-<digest>.css`). Neither is part of any page's own answer — the
  destinations, fares, notices and provenance are all in the page's own bytes
  (ADR-0033's fetch boundary, ADR-0047). The rule that comes with them: a page
  whose shared document does not arrive stays readable and truthful, taking away
  a control it cannot deliver rather than leaving it inert. The chooser and the
  privacy page fetch neither.
- **The reader picks the ticket, from three named sets.** The page opens on the
  cheapest fare of any ticket type to each destination, because the question a
  reader arrived with is a budget and not a ticket type (ADR-0044). The three
  sets stay as filters: the **reviewed unrestricted Anytime Day Returns** — exact
  standard-class ANYTIME DAY R ticket codes with a blank restriction code, and
  the build still refuses to run without a clean `.RST` file (ADR-0025) — the
  **any return** set (every standard-class return the feed prices, restricted
  off-peak and advance included, because a restricted off-peak fare is a real
  price a reader can buy), and **outbound singles**. Whichever set is open, the
  page states above the table what that set contains, and a fare that is only
  valid on a particular train says so where it is shown rather than in a
  footnote. On the real Grantham feed the opening list is all 101 destinations
  and every one of them is cheapest on a single, which is the accepted cost of
  the decision: the headline is a one-way price list, and the party figure is
  two of the fare the row names.
- **The railcard is one card chosen from a collection.** The page offers every
  card this feed prices and prices the reader's choice on the page: the one-third
  discount rounded down to 5p, held up by the `.RCM` minimum fare in force on the
  day -- each record's own `start_date` and `end_date` are honoured -- and gated by
  the current `.RST` `RR` ticket, route, location and total-ban rules. A card that
  does not cover the party is marked and cannot be chosen, the choice is remembered
  per station rather than sent anywhere, and a row the card cannot lower says so
  instead of quoting a number nobody could buy (ADR-0025, ADR-0052). The
  undiscounted figure stays the default party total and the budget ceiling. The
  railcard is never sent to a seller; the page tells the reader to name it here
  instead (ADR-0014).
- **No train is ever chosen for the reader.** A departure or a journey identifier
  in a link would turn a price list into a booking suggestion the data cannot
  support.
- **The default ticket link is the seller's own search page**, with no journey on
  it, because no seller's parameterised link is known to land on a search. The page
  must state what the reader has to fill in and that the price is the same at any
  seller (ADR-0017, ADR-0018).
- **No affiliate tracking of any kind until the fares licence's terms for
  commercial use are read** (ADR-0001, ADR-0010, ADR-0016). This is the hard gate
  on publishing anything that earns.
- **Known approximations that stay visible:** bank holidays are not interpreted, so
  a schedule that skips them appears on one; journey times allow one change by
  default; the onward search considers the 200 earliest departures at each
  interchange, a figure chosen by measurement (ADR-0009).

**Decided: the origin is the artifact's identity.** The interview confirmed the
design must work for any origin, and the owner then chose to launch with every
priceable station rather than one. ADR-0004's Grantham-only scope is replaced for
the artifact by ADR-0019: **one self-contained page per priceable station**, with a
station index inside every page so that choosing a station is navigation between
files rather than a filter inside one. The reason is delivery, not data — the feed
already answers every origin, but ~2,500 origins in a single file is roughly 890 MB.

ADR-0004's dates and park-by-default tripwire are unchanged; only the scope of what
gets built is.

**Decided: the origin is a property of the file; choosing one is navigation.** The
station index that drives the picker ships inside every page, a station page's
address is a readable slug (`/from/grantham`) with the chooser at the root, the
picker is a search field over real links rather than a custom listbox, and nothing
is stored — the URL is the only memory. Thepicker cannot offer a "nearest station": the fares feed's location records carry no
county, region, or coordinates, so the page's own data holds no geography. The
Knowledgebase stations file it reads for the attraction prune does carry
coordinates (2,613 CRS on the 24 September 2026 download), and ranking a reader's
nearby stations with them is open work rather than a capability
(`docs/open-work.md`, C27). Destination rows do not become entrances to other
origins in v1.

**Explicitly undecided, not to be invented:**

- the public product name (see Brand Commitments);
- the fares licence terms for commercial use, and therefore whether monetisation
  happens at all;
- how long the published whole-network build may take. It is bounded rather than
  decided (`timeout-minutes: 300` in the deploy workflow, sized from the slowest
  runner the workflow can land on), and `docs/build-performance-findings.md`
  measures the cost the bound stands on.

## Brand Commitments

**The public name is undecided.** "Train Budget Explorer" is the current README
heading and a working title only; a public name is still to be chosen. No
commitment was made to a tone, mark, or wordmark beyond that.

**No identity assets exist.** There is no logo, no icon, no favicon, no
illustration, and no typeface in the repository. Any future work that shows one
either creates it deliberately or is inventing evidence.

## Evidence on Hand

**The tests run on invented data; the licensed feeds are also on disk, and the two
are never blended.** Every test, demo page and browser check runs on synthetic
feeds whose stations, fares and times are invented (`make_synthetic_feed.py`,
`_demo_feed`), and the generated `demo*.html` files derived from that are
gitignored: they are a pipeline exercise, not a fare quote. Separately, the real
licensed downloads are present (`feeds/fares/dtd-fares.zip`, 47 MB, and
`feeds/timetable/dtd-timetable.zip`, 73 MB, both of 24 September 2026), which is
what a real-feed build, `dtd_audit.py` and the deploy workflow read. A figure
quoted from the real feed is a figure from the feed named beside it.

**There are no users yet.** No testimonials, no customers, no benchmark, no press,
no traffic figures, and no user research of any kind. The 21 October review is the
point at which the first real evidence will exist.

**What genuinely exists as evidence:**

- the test suite, including literal-value assertions on parsing, damage and
  fuzzing: **740 tests, OK**, measured on 7 October 2026 with
  `python -m unittest discover -s tests -p "test_*.py"`, plus a browser suite that
  drives the generated page at three widths in light and dark;
- a measured onward-departure cap (200) with the measurement recorded (ADR-0009);
- a first-run runbook for the real feeds, which have now landed and been
  downloaded (`README.md`, "When the account clears");
- an ADR set that records what is unverified rather than only what is decided, plus
  two publish checklists and one living file of open work (`docs/open-work.md`);
- one fact verified from outside the repository: Grantham's CRS code is `GRA`, and
  the National Rail journey-planner deep link returns "No matching journeys found"
  for every route tried, including King's Cross to Edinburgh.

## Product Principles

1. **Never let an approximation pass for a quote.** Every figure carries its fare
   class, its date basis, and what it excludes. If the tool did not read a
   timetable, the page says so before the reader asks.
2. **Say the unflattering thing on the page.** A stated limitation buys more trust
   than a feature implied. The footer's caveats are content, not boilerplate, and
   burying them is a design defect rather than a tidiness choice.
3. **The link is part of the promise.** A reader sent to a page that says "no
   journeys" has been misled by omission. Links are verified, or they are the plain
   ones, and the reader is told which.
4. **Evidence before effort.** No feature is built on a demand signal that has not
   appeared. The dated tripwire and park-by-default rule bound the work, and the
   design is not exempt from them.
5. **Nothing publishes before the licence is read.** The data's terms for
   commercial use are the gate, and no design decision gets to route around it.

## Accessibility & Inclusion

**WCAG 2.2 AA is the standard this page must meet** (confirmed during init; it was
not previously recorded anywhere in the project).

No accessibility research or user testing has been done, so no disability-specific
need beyond the standard is established. Two facts of the operating context are
relevant to it: the page is reached from a community thread, which makes phone use
the likely first encounter, and the party switch changes the meaning of every price
on the page rather than merely filtering it.

The station picker is deliberately built from anchors rather than a custom listbox
(ADR-0019), so keyboard handling and accessible naming are the browser's, and the
one control that moves the reader to another page is a link that assistive
technology already announces as one.
