# Launch checklist: posting, measuring, and reading the result

The second half of the plan. `publish-checklist.md` decides whether the page *may*
go up; this one decides where it goes, how the result is measured, and what gets
read on 21 October. ADR-0003 committed to measuring clicks, comments, and repeat
usage, and none of it can be measured afterwards if it is not set up now.

## 1. Gates, before anything is posted

- [ ] `publish-checklist.md` is ticked top to bottom
- [ ] `python -m tools.check_links` reports no `no_journeys` and no `http_error`
      (`blocked` and `inconclusive` are **not** a pass — they mean a person has not
      looked yet)
- [ ] The Stage 1 count is in hand. If the honest answer was "Grantham reaches
      almost nowhere under £20", the launch is a **no-go** and the ADR-0004 gate
      says so; a page that answers "nowhere" is the spreadsheet mistake again
- [ ] The date is written down, because it is the baseline for everything below

## 2. Measurement — decided before posting, not after

**Stance: no cookies, no personal data, no cross-site tracking.** Three numbers are
needed and nothing else is worth the reader's privacy: clicks per venue,
unique-ish visitors, and return visits.

- [ ] A counter was chosen, and injected with
      `--analytics-snippet <file>` so it lives in the build rather than in a
      generated file
- [ ] Its snippet sets nothing on the reader's device that would require a consent
      banner — if it does, either drop the counter or accept the banner, and decide
      that **now** rather than discovering it on the day
- [ ] The page still opens and works with the counter blocked or offline. It is a
      static file and must stay one
- [ ] Each venue's post links to the page with a `?ref=` tag of its own, so
      "which community showed up" is a fact and not a guess

**What to read, and where.** Not invented later:

| signal | from | why it counts |
|---|---|---|
| clicks, per venue | the counter, split by the `?ref=` tag | ADR-0003's first measure of whether the audience path exists at all |
| comments, and their tone | the threads themselves | the qualitative signal a counter cannot carry: is anyone asking a follow-up question? |
| repeat usage | returning visitors | the difference between a curiosity and a tool |

No numeric gate was agreed (ADR-0004, risk 2: "judge at the time"), so the review
judges. This page exists so that the evidence to judge *with* exists.

## 3. Where it goes, and what the post says

ADR-0003's order: communities first, and no SEO or content investment until a
community signal appears.

- [ ] r/uktrains — the first venue
- [ ] Relevant local Facebook groups around Grantham
- [ ] Hacker News, only if it is genuinely worthy of the front page, not as a fallback

Things the post must do:

- [ ] Say in the first sentence what the tool does **and what it is not**: the
      cheapest fare of any ticket type from a station, named on the row, not a
      booking engine. Where that fare is an Advance single it is valid on a
      qualifying train only and the page says so; the reviewed Anytime Day Return
      set is one of three filters rather than the list that opens. Railcard
      discounts are priced per fare, and per row, when the reader names a card
      from the collection the page offers; a row the feed prices in two tickets
      prices both of them; and the party quote keeps the undiscounted fare as its
      default
- [ ] Disclose any affiliate link in the post itself. A community that discovers it
      undeclared is a community lost, and that is the whole audience
- [ ] Meet the predictable "split ticketing is cheaper" reply by agreeing with it,
      because it is true: every row whose journey changes names the station it
      changes at and says a two-ticket split may cost less, and where the feed
      itself prices that journey in two published fares the row is already the
      sum of both, naming the station the split sits at (ADR-0061)

## 4. The review, 21 October 2026

- [ ] The three readings from section 2, written down with the numbers
- [ ] The owner's answer to the actual question: is this worth keeping?
- [ ] **Default if unsure: park it.** Docs stay, no further time, and resuming takes
      a new decision (ADR-0004)
- [ ] If the affiliate application was rejected, record it: v1 revenue is £0 by
      design (ADR-0003), the tool continues as a demand experiment, and the second
      seller in ADR-0016 is the next question rather than an emergency
