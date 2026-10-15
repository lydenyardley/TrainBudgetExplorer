# Clarity audit: the language of every user-facing view

**Date:** 14 October 2026
**Command:** `impeccable clarify`, run over every route rather than one target
**Commit reviewed:** `a6c809c` on `main`
**Status:** findings only. No code and no page copy was changed in this pass, and
nothing below has been applied. The numbering is one sequence across the whole
document; the groups are screens and routes, not priority bands.

## What was read, and how

Clarity is a property of what is on screen, so the audit read built pages, not
the templates: the three routes the release serves, plus the fares-only build
shape, each served over HTTP so the route's own script ran and every string the
reader sees was present.

| Route | Artifact | Build |
|---|---|---|
| `/` | `_demo_site/index.html`, served on `127.0.0.1:8902` | synthetic feed, 3 origins, 5 October 2026 |
| `/from/grantham/` | `_demo_site/from/grantham/index.html`, same server | as above, with a timetable |
| `/` and `/from/grantham/` | served on `127.0.0.1:8899` | the **real** feed, single origin, built 14 October 2026 (`Site built 2026-10-14 20:51:40 UTC · source 109ca0ab7fd21e44`) |
| `/privacy/` | both builds above | synthetic and real |
| `run.py --feed feeds/fares` shape | `_shape_site/prices-only/from/grantham/index.html`, served on `127.0.0.1:8903` | synthetic feed, no timetable |

Every quote below is either the rendered text of one of those pages (read from
the live DOM, so it is what the reader sees after the script has run) or a string
literal in the module named beside it. Where a finding is a reading of what a
sentence *means* to someone who does not work here, it is marked as needing a
person rather than a rewrite.

The strings were collected with a throwaway `html.parser` walk of each page
(visible text plus `aria-label`, `placeholder`, `title`, `alt`) and a literal
scan of `page/chooser.js` and the fifteen files under `page/station/`. The
interactive states — an empty table, a chosen railcard, an open row, a
shortlisted place, a picker with a query typed into it — were driven in the
browser and read from the DOM, not inferred.

## The chooser (`/`)

1. **[P1] The provenance sentence prints the download date twice.** Rendered on
   the release chooser: *"Prices from the National Rail Data Portal DTD fares
   feed, downloaded 24 September 2026 downloaded 24 September 2026."* Both
   producers of that string already end in the date — `price_source_from_manifest`
   returns `"the National Rail Data Portal DTD fares feed, downloaded 24
   September 2026"` and `price_source_from_metadata` returns
   `"the ATOC/RDG DTD fares feed (24 September 2026), downloaded 24 September
   2026"` — and `render_chooser` then appends `"downloaded " + human_date(feed_date)`
   again (`build_demo_page.py` around the `provenance_parts` list). Reproduced by
   calling `render_chooser` with that string, so it is the code, not one stale
   file. One place should own the date: either the sources stop naming it, or the
   chooser appends only when the source string carries no date of its own.

2. **[P1] The ordering note answers a question the reader has not asked, in build
   words.** *"Ordered by how many destinations this download prices from each
   station — not by how busy it is, and not by how near it is."* "This download"
   and "prices from" are the build's vocabulary; the sentence also spends its
   whole length on a sort order before the page has said what the list is.
   Recommendation: what the list is, then how it is ordered, in the reader's
   words ("every station this page prices journeys from, most first"), keeping
   the honest "not by how busy it is" half.

3. **[P1] The chooser's number and the page's number disagree.** The chooser row
   reads *"GRANTHAM GRA 50 destinations"* and links to `/from/grantham/?budget=20`
   (the chooser's own budget travels in the link), where the count line reads
   *"53 destinations for up to £20.00 each, cheapest first: 47 singles, 6
   returns"*. The synthetic site behaves exactly as the definitions predict —
   chooser "5 destinations", page "4 destinations for up to £20.00 each" — so the
   index is counting every priced destination at any budget
   (`_priced_destinations`, union over the three modes at `EVERYTHING_PENCE`)
   while the page counts what is inside the budget on screen. The release's 50
   against 53 cannot come from that difference alone. **The copy fix does not
   depend on which number is right**: a count with no qualifier, one click from a
   count with one, invites the comparison. Qualify it ("50 places this feed
   prices", against "53 inside your budget"), and put the release's 50-vs-53 in
   front of whoever owns the index as a data question.

4. **[P2] The one-station release explains itself with build words.** *"This site
   was built for one station: open it below for every destination your budget
   reaches from there."* "Was built for" is a fact about the pipeline; "open it
   below" points at nothing in particular when the only thing below is a row
   labelled GRANTHAM. Recommendation: state the coverage ("this site covers
   Grantham only"), and name the link.

5. **[P2] The empty chooser greets a visitor with the pipeline.**
   `page/chooser.js`: *"Nothing is priced from any station in this build, so
   there is nothing to explore yet. When the build prices journeys, this page
   lists every station it can start from."* "Build" twice, and "nothing to
   explore yet" is the worst possible first sentence. Someone arriving at this
   state should be told what to do instead (nothing here, try later, here is what
   this is). *Needs a person:* it can only happen for a build that priced
   nothing, and the operator may prefer it to be blunt rather than warm.

6. **[P2] "We don't have prices from 'zzz'."** (`page/chooser.js`, rendered when
   a query matches nothing.) The sentence is good — it names the input and the
   two ways to succeed — but it promises the wrong thing: a station that has no
   page is absent from the list, and a station with no *fare* may still exist in
   the feed. "We don't have a page for" is the true statement, and it is the one
   a reader can act on. The straight quotes should be the page's own typographic
   ones (it already uses `’` elsewhere).

7. **[P3] The field has three names.** Its placeholder is `station`, its
   accessible name is "The station you are starting from", and the visible
   sentence above it reads "Type the station you are leaving from, then pick it
   from the list." Three phrasings of one job ("starting from", "leaving from",
   `station`). Pick one and use it in all three places.

8. **[P3] The capped list's sentence tells the reader to do what they are
   already doing.** `page/chooser.js` writes *"Showing " + cap + " of " +
   wanted.length + " stations. Type to narrow the list."* — and it appears only
   once the matches exceed the 40-option cap, which on a site this size means the
   reader has typed one or two letters and got 120 matches. So the second clause
   is actionable and correctly placed; the only wrinkle is that they have just
   typed. Worth leaving as it is; the alternative ("Add another letter") is not
   obviously better. Not verified on screen: neither build on disk has enough
   stations to reach the cap, so this was read from the source and its condition.

9. **[P3] The budget field's accessible name is "Budget in pounds" on every
   route, including the chooser, where the heading reads "Train fares up to £
   from"** and the field is the only thing in the sentence that is a control. A
   screen reader meets "Budget in pounds" and then "from" with no object. The
   heading's own name is worth a pass once the copy above it settles (see 13).

## The station page (`/from/<station>/`)

### Heading, intro and the budget control

10. **[P1] Three versions of the page's promise, and the live one reads
    oddly.** With a timetable: *"Every place you can reach from the station
    above, inside the budget, with the fastest time and the fewest changes."*
    The station is in the heading *above this sentence's own line*, so "the
    station above" is true but loose; "the fewest changes" promises a column
    rather than a journey. Without a timetable: *"Every place this feed prices
    from the station above, inside the budget. This build has no timetable, so
    no times are shown."* And the static fallback in `page_templates.py` is a
    third sentence again. Recommendation: one promise, written once, with the
    timetable clause composed onto it.

11. **[P1] A one-station build explains itself in build words.** *"This is the
    only station this build has pages for, so the name above is not a link."*
    (both routes, `ONE_STATION_FIRST_USE`.) "Has pages for" is the site's file
    layout. Recommendation: "This site covers Grantham only, so the name in the
    heading is not a link."

12. **[P1] The budget hint points at a control the reader cannot see, and its
    unit follows the wrong switch.** *"Drag to change the budget in the heading.
    It stops at the highest fare in the ticket type you are looking at —
    £181.00 for one adult."* The ticket-type control is inside "Filter this
    list", which is collapsed on first paint, so "the ticket type you are looking
    at" names nothing on screen; and the closing "for one adult" is the *ceiling's*
    unit, which the party switch changes (`__CEILING_NOTE__` is written for one
    adult at build time). Recommendation: name the mode in the words the control
    uses ("at the highest fare in Cheapest of any type"), and let the party
    switch restate the unit or drop it.

13. **[P2] The `h1` is a sentence with a control inside it.** Rendered, its
    name is *"Train fares up to £ 20 from Change starting station: GRANTHAM"* —
    the budget split from its number by the input's own text, then the control's
    label appended mid-sentence. For a reader with a screen reader this is the
    page's first line. Recommendation: keep the visible sentence, give the
    heading an accessible name that is a sentence ("Train fares up to £20 from
    Grantham") and let the control carry its own name.

14. **[P2] The unit is "each" in half the page and "one adult" in the other
    half.** The count line reads *"53 destinations for up to £20.00 each"*, the
    empty state *"No destinations for up to £1.00 each"*, the control "One
    adult"/"Two adults", the row details "per adult", the shortlist "for the two
    of us". "Each" is never anchored to people, and after the party switch it is
    the only thing on the count line that could carry the party size. It should
    say "per adult" wherever the control says "adult".

### The refinements

15. **[P2] "Cheapest of any type" sits in the same radio group as three ticket
    names.** The legend is "Ticket type" and the options are *Cheapest of any
    type / Anytime Day Return / Any return / Single*: one is a policy, three are
    products. The mode note below the table then says "so this list mixes singles
    and returns", which is the consequence of the first option rather than a
    property of a "type". Recommendation: label the group for what it does
    ("Which fares to list") or label the first option for what it is ("Cheapest
    available").

16. **[P2] "Railcard" is one word for a control that changes every price on the
    page, and its help is written for a reader who has already opened it.** The
    select's first option is "No railcard" and the help reads *"No railcard
    selected, so these are standard fares. Choose the card you hold to price the
    journey with it; this browser will remember your choice."* The second
    sentence is the one that matters (the choice is remembered, nothing is sent)
    and it is last. Also "standard fares" is a claim the method block repeats and
    then contradicts (see 24).

17. **[P2] The destination-type chips are ONS bands wearing everyday words.**
    Rendered: *All / Cities (2) / Small towns (1) / Coastal & seaside (1) /
    University towns (2) / World heritage (1)* — and on the release page
    *Towns / Villages / Islands / Airports / Nature sites / Transport
    interchanges / RSPB reserves / National Trust / National parks and
    landscapes*. "Cities" and "Villages" are Census 2021 built-up-area size
    bands, which is not what a reader means by either word, and the rule line
    below explains counts but not the bands. Recommendation: one line naming the
    source ("size of the place, from the 2021 census"), or rename the four bands
    so they cannot be read as the ordinary words. *Needs a person:* the labels
    are a product decision, and the chips are written from
    `DESTINATION_TYPE_FILTERS` in `atoc_fare_declarations.py`, the same reviewed
    table the payload's types are keyed by, so a rename is one registry edit.

18. **[P3] The chip rule describes plural selection to a reader who picked
    one.** *"More than one type shows destinations of any of them. The count on
    each is how many are inside the budget now."* The first half is about a
    state the reader may not be in; the second half is the useful half and could
    stand alone under the chips.

19. **[P3] "Clear destination types"** appears only once a type is chosen, which
    is right, but the label pluralises a control that may have cleared one, and
    it does not say what the page returns to. "Show all destination types" is the
    same length and states the outcome.

### The count line and the table

20. **[P1] "Shown" means "in the data" in one paragraph and "in the table" in
    the next.** `#feedCoverage` rendered: *"8 destinations are shown, each on the
    cheapest fare of any ticket type the feed prices for it, and all are shown."*
    The table below holds 4. On the release page it reads *"305 destinations are
    shown …"* where the table holds 53. With the budget at £1 the sentence still
    says "8 destinations are shown" while the table is empty. The count line
    (*"4 destinations for up to £20.00 each"*) and this paragraph therefore
    disagree on screen in every state. Recommendation: reserve "shown" for the
    table and use "the feed prices" for the rest; the sentence also needs to say
    what budget it is counting at, because "305" and "53" are both true.

21. **[P2] The same count is stated twice in one screenful, in two vocabularies.**
    *"53 destinations for up to £20.00 each, cheapest first: 47 singles, 6
    returns"* above the table and *"1 of 3 pages · 53 destinations"* below it,
    with `#modeNote` between them saying that the list mixes singles and returns
    again. One of the three is the reader's; the other two are the page thinking
    aloud.

22. **[P2] A sentence lives in the Time column.** Rendered row (synthetic):
    Time *"No service Mon any day this week"*, Changes *"Unknown"*. The column
    holds durations in every other row, so the eye reads a duration and gets a
    clause — and the clause is ungrammatical. The strings in
    `page/station/service-day.js` are assembled per state ("No service " + day +
    " any day this week", "no service on " + day + ", and it runs on …"), which is
    what produces it. Recommendation: a short state in the cell ("No service that
    day") with the day explanation in the row's own details, and the grammar
    fixed either way.

23. **[P2] The price cell packs three facts with no words between them.** With a
    16-25 card chosen: *"£4.65 £7.00 standard"*. Visually this is a price, a
    struck price and a label; in text order it is three numbers and a word. The
    word "standard" is doing the whole job of saying which is which. "£4.65 with
    your card (was £7.00)" is longer but needs no second glance.

24. **[P1] The method block contradicts the row the reader is looking at.** With
    a railcard selected, `#railcardNote` still reads *"No railcard is selected,
    so the prices shown are standard fares. Choose the card you hold and each
    displayed fare is repriced…"* while the rows show card prices and the
    control's help says the card is applied. `railcardNote` is written once, at
    first render, from the payload's build-time constant
    (`page/station/provenance.js` writes it; `build_demo_page.py` composes it),
    and nothing rewrites it on a card change. This is the most damaging item in
    this audit: the page's own explanation of its numbers is false in the state a
    railcard holder is in. Recommendation: write that paragraph from the same
    state the rows read.

### A row and its own details

25. **[P1] The disclosure heading promises a condition the body says the feed
    does not carry.** Rendered: *"Restricted fare — the condition is below."*
    followed immediately by *"This fare carries restriction 00, which this feed
    does not describe, so the condition has to be read from the seller's own
    terms."* The first sentence sends the reader down for something that is not
    there. Recommendation: one sentence, e.g. "Restricted fare — the fare's own
    condition is not in this feed, so check the seller's terms", and no promise.

26. **[P2] "Feed record" is a machine record shown to a reader.** Inside the
    disclosure: summary *"Feed record"*, then *Ticket SDS / Restriction 00 / Route
    00000 / Priced as outbound single*, and, with a card chosen, *"Railcard rule:
    Current RR 0002 for 16-25 Railcard: ticket any, route any, location any; total
    ban no; restriction R9."* Field names, codes and a `RR` record with no gloss
    anywhere on the page. Recommendation: keep the record (it is the page's
    evidence) but label it as technical, or move it into the text the Copy button
    produces so the reader-facing surface states the price and one qualifier.

27. **[P1] The same control has two accessible names and no visible text.** The
    row expanders render as *"Fare details for NOTTINGHAM"* and *"2 times and
    fare details for LINCOLN"* — one names the times, one does not — and each is
    an icon-only button with an empty text node. Two names for one control is a
    screen-reader defect as well as a copy one; pick the shape that is true on
    both rows and keep it.

28. **[P2] "Copy" does not say what is copied.** The row action's visible word is
    "Copy"; the explanation (*"Copy the from, to, date and party size for this
    row"*) lives in a `title` attribute, which a touch reader never sees, and the
    accessible name says "the journey details". Three descriptions of one button,
    only one of them visible. Recommendation: a visible label ("Copy journey") or
    a persistent hint beside it, and one sentence used everywhere.

29. **[P2] The card sentences are the densest copy in the product.** Rendered for
    one row: *"16-25 Railcard is available for this fare, subject to condition
    R9. No matching total ban applies; the restriction is a travel condition
    rather than a card ban. The feed's one-third discount gives £4.65 per adult,
    and no minimum fare is current for this ticket."* The first fact a card
    holder wants (what they pay) is third. Recommendation: price first, one
    qualifier, then the rule; the "total ban" vocabulary belongs in the feed
    record (26).

30. **[P3] "The price above is the railway's own walk-up fare."** The line sits in
    the disclosure above the table; the prices it refers to are below it. Also
    "walk-up fare" is a trade term: for the reader this is "the fare you can buy
    on the day". Recommendation: point at the row ("each row's price is…"), and
    gloss the term.

31. **[P3] "This journey is not priced for two tickets…" / the two-ticket rows.**
    `page/station/row-actions.js` carries four different shapes of the same
    news ("This feed prices no X fare for this two-ticket journey…", "…bans it on
    one of the two tickets…", "Two tickets, and X applies to each one…"). Checked
    only when the feed offers a split, so this audit read the strings rather than
    a rendered instance; they are worth a single pass for one voice, and the
    "stay on the train" parenthetical in `row-cells.js` ("priced via X (stay on
    the train)") is the one a reader will not decode without help.

### The empty states

32. **[P1] The suggestions in the empty state are counts with no verb.** At a £1
    budget: *"No destinations for up to £1.00 each. Try: Show everything up to
    £7.00 | Price it for two adults | Anytime Day Return has 7 | Any return has
    8 | Single has 1"*. The last three are buttons whose labels are fragments;
    "has 7" of what? Recommendation: "Show the 7 Anytime Day Returns", "Show the
    8 returns", "Show the one single", and keep each count as the object of the
    verb.

33. **[P3] "Show everything up to £7.00."** "Everything" claims the page's whole
    list; the button raises the budget to the next fare, which may be one place.
    "Raise the budget to £7.00" says exactly what happens.

34. **[P3] The pagination narrates an empty page.** *"1 of 1 page · 0
    destinations"* below an empty state. One page is not information; the count
    is already in the line above.

### The shortlist dock

35. **[P2] The dock says the same thing twice in two words.** *"Shortlist 1
    place"* in the header and the live region's *"1 shortlisted."* One of the two
    is the announcement; the other is the label. Keep the header's, and let the
    live region say what changed rather than how many there are.

36. **[P2] "Share" hands the reader a URL and a sentence with no warning beside
    it.** Rendered: *"Shortlist of 1 place from GRANTHAM. http://127.0.0.1:8902/
    from/grantham/?budget=20&card=YNG"* — the address carries the budget and the
    railcard, the privacy page says a shared link carries "your budget and party
    size to whoever opens the link", and the two are never in the same place.
    The URL is also not a link and not selectable in one action. Recommendation:
    name what the link carries next to it, and make it a link that can be copied.

37. **[P3] The copied list and the dock's own headings.** The text the Copy
    buttons produce (`page/station/row-actions.js`, read from the source rather
    than from a click: "From: … To: … Ticket: … Date: … Passengers: 2 adults") is
    a run of labels and values, while the dock's table headings read
    Station/Price/Time/Changes and its count says "places" rather than
    "destinations". The same list of the same places uses "place", "destination"
    and "station" within one screen.

## The prices-only build (`run.py --feed feeds/fares`)

38. **[P1] One fact, three times, in one screenful.** Rendered on
    `_shape_site/prices-only`: the intro ends *"This build has no timetable, so
    no times are shown."*, the freshness line reads *"This build prices fares
    only: no timetable was supplied, so no times or changes are shown."*, and the
    provenance line repeats *"no timetable loaded, so no times are shown"*. A
    reader who needs the fact meets it once and then reads it two more times;
    "this build" also appears twice in the intro alone.

39. **[P3] The intro's third sentence is the first-use note, and it changes
    subject mid-paragraph.** *"Every place this feed prices from the station
    above, inside the budget. This build has no timetable, so no times are
    shown. This is the only station this build has pages for, so the name above
    is not a link."* Three sentences about three different things (the list, the
    times, the heading control) in the paragraph a reader meets first. See 11 for
    the sentence itself.

## The privacy notice (`/privacy/`)

40. **[P2] "Contact" is a fragment with a bare URL.** Rendered:
    *"the deployment operator via its public repository issue tracker
    (https://github.com/lydenyardley/TrainBudgetExplorer/issues)"* — no sentence,
    no capital, and the one actionable thing on the page is plain text.
    Recommendation: a sentence naming who to contact and a real link.

41. **[P2] The same claim is made in two sections.** *"No cookies are set by this
    site."* and *"The site code does not intentionally collect visit data."*
    appear as bullets under "What this site does", and the Hosting section ends
    *"The site code itself does not set cookies or intentionally collect visit
    data."* The first bullet also points down at a section that repeats its
    substance. This is the "say each idea once" rule: the bullets are the
    summary, and the Hosting paragraph should not restate them.

42. **[P2] The built-line promises a publication that has not happened.**
    *"This notice describes the build published on 14 October 2026."* Nothing has
    been published — `licences/release-clearance.md` is still open — and "the
    build" is the pipeline's word. Recommendation: "the build dated …", or state
    the date without the verb, and keep the sentence because the analytics bullets
    below it are claims about one build. *Needs a person:* the clearance file is
    a person's decision, so the wording that describes publication should be
    theirs.

43. **[P3] Three conditional promises in three voices.** *"No analytics run. If
    the operator later adds analytics, this page will name them here first."*,
    *"if tracked links are ever switched on, the footer of the fare pages says so
    plainly"*, and *"The site code does not intentionally collect visit data."*
    Each is honest; together they mix "this site", "the operator" and "the site
    code" for the same actor, and "intentionally" appears where the reader wants
    "does not". One actor name, one tense.

## Across every route

44. **[P1] Nothing defines the trade vocabulary the page quotes.** ITX (footer,
    `#feedCoverage`), DTD (provenance, method), RR (the railcard note and rule),
    "feed", "this download", "feed dated", "flow" (`#feedCoverage`: *"140 priced
    flows had no station name in the feed"*), "Priced as", "Feed record",
    "walk-up fare", "NRE". None is glossed on any route, and `docs/glossary.md`
    already holds the reader-facing definitions of several. Recommendation: one
    short glossary inside the method disclosure, and a first-use gloss for the
    two or three that appear above the table. *Needs a person:* which terms the
    audience genuinely knows (the brief says plain language without flattening
    real terminology) is a judgement about rail readers, not a style rule.

45. **[P1] One sentence, two dates, and the second is mislabelled.** Rendered on
    the release page: *"Prices from the National Rail Data Portal DTD fares feed,
    downloaded 24 September 2026, feed dated 14 October 2026."* The second date is
    `DATA.serviceDate` (`page/station/provenance.js`: `parts.push("feed dated " +
    humanDate(DATA.serviceDate))`), the day the build asked about — not a date on
    the feed, which is 20 days older. A reader takes it as "the feed is dated
    today" and stops worrying about the age the freshness line is warning about.
    Recommendation: "…downloaded 24 September 2026; fares and times read for 14
    October 2026."

46. **[P2] The build stamp is internal.** *"Site built 2026-10-14 20:51:40 UTC ·
    source 109ca0ab7fd21e44."* A timestamp to the second and a bare digest are
    evidence for a person debugging the site, not copy for a reader, and the date
    format is the only ISO one on the page. Recommendation: keep it, name it
    ("Site built … from this revision of the code"), or move it into the
    copyable text with the feed record.

47. **[P2] The method paragraph has no subject and starts lowercase.** Rendered:
    *"cheapest displayable standard-class fare found in the feed, in the ticket
    mode the page opens in; each mode names above the table what its fares are,
    with ITX placeholders excluded and Advance singles labelled as
    train-specific. Use the ticket-type control to change which fares are
    listed…"* — the fragment is the payload string
    (`build_demo_page.py`'s `pricingBasis`), appended as-is by
    `page/station/provenance.js`. Recommendation: give it a subject and a
    capital ("Each price is the cheapest displayable standard-class fare in the
    feed, in the ticket mode the page opens in.").

48. **[P2] The provenance line is a machine record.** *"Origin GRANTHAM (GRA) ·
    305 destinations, each on its cheapest fare of any ticket type, in the feed ·
    services on 2026-10-14 · destination types: Office for National Statistics,
    Census 2021 built-up-area size bands and coastal classification + ONS 2021
    geography coverage with reviewed London, Scottish, Welsh, Northern Ireland,
    major-city, and reach-ranked settlement fallbacks"* — a `·`-joined record
    whose last field is a method sentence, with a `+` joining two sources.
    Recommendation: split the reader's facts (origin, what the count is, which
    day the times are for) from the sources, and put the sources in the
    attribution block where the other licence text already lives.

49. **[P3] Three date formats on one page.** "24 September 2026" (provenance),
    "2026-10-14" (`services on`, the build stamp), "Mon, 5 October 2026" (the day
    picker's options). One of them should win for a reader, and it is not the
    ISO one.

50. **[P3] "today" means the build's day.** *"Times are from a timetable covering
    17 May 2026 to 15 May 2027, which includes today."* The page is a file; the
    reader's today is whenever they open it, and by then the sentence is stale in
    a way the page cannot see. Recommendation: "which covers the day these times
    are for" — the same day the day picker names.

## What this audit did not check

- **Narrow widths and 200% zoom.** The clarify method's scanability step is a
  layout reading, and the 14 October critique owns it. This pass read the copy at
  one viewport.
- **Screen-reader announcement order.** Accessible names, roles and live regions
  were read from the DOM; the order and interruption behaviour they produce in a
  reader were not.
- **The merged-network chooser and station pages.** The deploy's release shape is
  built from shards (`build_demo_page.py --merge _shards/shard-*`) and is not on
  disk here, so the multi-origin chooser was read from the synthetic build
  (3 origins) and the release pages from a single-origin build.
- **A real-feed rebuild.** Attempted for this pass and it failed: the machine had
  62 MB free and the fares index cache write returned `OSError: [Errno 28] No
  space left on device`. The real-feed evidence used above is the 14 October
  release build already on disk and served on `127.0.0.1:8899`; its build stamp
  is quoted in the table so a later pass can tell whether it is still current.
- **Localisation.** Every string is English and several are assembled from
  fragments by script; the clarify reference's "complete translatable messages"
  test is not met by the composition in 20, 22, 24 or 30, and reworking it is a
  page-code change rather than a copy one.
- **Two open items this audit deliberately did not restate.** Route audit items
  [20] and [21] (the notices on the chooser and the privacy page, and the build
  check that would hold them) are already open in `docs/open-work.md`; the
  chooser's missing notice is that item, not a new finding.

## What happens next

Nothing was changed. Every item above is a wording change except 1, 20, 24, 45
and 50, which are defects in what the page asserts: two of those (1, 45) are one
sentence each and one place owns each date; 20 and 24 are the same fault twice —
a paragraph written from build-time constants while the rows are written from
the state on screen. If a later pass takes this list, the natural order is the
defects, then the count line's vocabulary (3, 20), then the trade-terms glossary
(44), because those three decide how much of the rest is worth rewording.
