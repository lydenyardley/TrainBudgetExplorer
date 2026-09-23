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

**Travelling as a pair is a first-class case, not a variant.** Two adults on a Two
Together Railcard is the only railcard in v1 and party pricing is core maths rather
than a display option (ADR-0002), so a large share of readers are two people
asking what the trip costs *them*.

**The operator is the owner**, acting part-time. The staged plan bounds the whole
experiment at roughly four weeks part-time, with a hard build stop and a written
review (ADR-0004).

## Product Purpose

Turn a price into a shortlist of places. Given an origin station and a budget, the
page lists **every** destination reachable by train inside that budget, with the
fastest journey time, the number of changes, the fare for one adult, and the total
for two adults on a Two Together Railcard.

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
this one publishes its own limits as content. It promises scheduled walk-up
Anytime/Off-Peak **returns** and says out loud that Advance singles can undercut
them; it refuses to send a railcard or a chosen train to a seller because it cannot
honestly know either; and when no ticket link could be verified, it was the link —
not the claim — that changed (ADR-0017, ADR-0018). A competitor optimising for
conversion would not make those moves.

## Operating Context

- **The page is generated, not written.** `build_demo_page.py` reads a fares feed
  and a timetable feed and writes one self-contained HTML file. The design source
  of truth is the `TEMPLATE` string in that Python file, not the `demo*.html`
  output, which is derived and gitignored. Regenerating overwrites hand edits.
- **The data is licensed and roughly triennial.** The fares feed is released about
  three times a year through the Rail Data Marketplace (`raildata.org.uk`), which
  needs an account and an accepted licence held in the owner's name. Nothing about
  the feeds is anonymously readable, and the download is currently blocked on that
  account (ADR-0005, `docs/stage-1-results.md`).
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
- **Hosting is undecided.** The page has never been served publicly (ADR-0010);
  ADR-0004's Stage 2 mentions free hosting without choosing one.

## Capabilities and Constraints

**Confirmed functionality.** Station picker (search by name or three-letter code,
resolving to the station's page); budget slider; destination filter by name or code;
party switch (one adult standard fare, or two adults on a Two Together Railcard); per
destination a price, the fastest journey time, the number of changes, the fare type
code, an expander holding the next few departures, and one ticket link on the row;
date-aware schedules when the page is built with a date, and an explicit note that
every schedule was read when it is not.

**Hard constraints.**

- **One self-contained HTML file: no server, no build step, no external assets**
  (ADR-0010). No webfonts, no CDN imagery, no framework, nothing fetched at
  runtime. There are currently **no images, logos, icons, or font files in the
  repository at all**, and designing one in means inlining it.
- **Fares are scheduled walk-up Anytime/Off-Peak returns.** Advance fares can be
  cheaper and the page must never imply them. A return is assumed.
- **Two Together is the only railcard in v1**, and the railcard is never sent to a
  seller; the page tells the reader to tick the box instead (ADR-0014).
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
is stored — the URL is the only memory. The picker cannot offer a "nearest
station" because the fare feed's location records carry no county, region, or
coordinates, and destination rows do not become entrances to other origins in v1.

**Explicitly undecided, not to be invented:**

- the public product name (see Brand Commitments);
- the fares licence terms for commercial use, and therefore whether monetisation
  happens at all;
- the hosting or deploy target for the set of station pages (ADR-0019) — the path
  scheme is settled, the host is not;
- how much of the network a build can afford to price, which depends on the
timetable enrichment cost and cannot be measured until the feed lands.

## Brand Commitments

**The public name is undecided.** "Train Budget Explorer" is the current README
heading and a working title only; a public name is still to be chosen. No
commitment was made to a tone, mark, or wordmark beyond that.

**No identity assets exist.** There is no logo, no icon, no favicon, no
illustration, and no typeface in the repository. Any future work that shows one
either creates it deliberately or is inventing evidence.

## Evidence on Hand

**There is no real data in this repository, and nothing may be presented as if
there were.** `feeds/fares` and `feeds/timetable` do not exist. Every test, demo,
and screenshot runs on synthetic feeds whose stations, fares, and times are
invented (`make_synthetic_feed.py`, `_demo_feed`). The generated `demo*.html` files
are derived from that synthetic data and are gitignored; they are a pipeline
exercise, not a fare quote.

**There are no users yet.** No testimonials, no customers, no benchmark, no press,
no traffic figures, and no user research of any kind. The 21 October review is the
point at which the first real evidence will exist.

**What genuinely exists as evidence:**

- 179 tests, including literal-value assertions on parsing, damage, and fuzzing;
- a measured onward-departure cap (200) with the measurement recorded (ADR-0009);
- a first-run runbook for when the real feeds land (`README.md`, "When the account
  clears");
- an ADR set that records what is unverified rather than only what is decided, plus
  two publish checklists;
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
