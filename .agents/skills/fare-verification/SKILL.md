---
name: fare-verification
description: Check a built station page's fares against the National Rail journey planner, and turn every mismatch into a tests/known_fares.toml row and an F7 synthetic record. Use when asked to check, verify or spot-check fares or prices against National Rail, after a change to fare selection, railcards or two-ticket rows, or when a tests/known_fares.toml row warns that it is more than 90 days old.
---

# Fare verification

The release's gates catch an implausible fare. They do not catch a plausible
wrong one: #149, #179 and #421 were each found by a person comparing a page
with nationalrail.co.uk. This is that comparison as a routine, and every run
leaves a test behind.

## 1. Build one origin's page

A real-feed page comes from the licensed feeds, so it stays on the machine
that built it. Never commit it, attach it, or upload it.

- On a desktop with the feeds: `python run.py --feed feeds/fares --timetable feeds/timetable-nwr --origin GRA --date <YYYY-MM-DD> --rebuild`.
  It serves `_site/` on http://localhost:8741.
- A whole-network build does not fit a 16 GB desktop. If even one origin with
  the national timetable runs out of memory, run the `build named origins`
  workflow (`.github/workflows/build-origins.yml`) with the CRS codes, and
  delete its artifact as soon as it is downloaded.

Pick the date you will search National Rail for, a weekday at least a day
ahead. The page's prices do not depend on the time of day; National Rail's do.

## 2. Open it at both widths

Open `/from/<slug>/` at 390 px and at 1280 px wide. Note any row that reads
differently between the two, because a reader on a phone sees the narrow one.

## 3. Choose three destinations

Cover different fare logic, not three similar stations:

1. The cheapest row on the default view.
2. A row with a change, which may be priced as two tickets (ADR-0061).
3. A row priced with a railcard: set the card in the page's control, and for
   Two Together set the party to two.

For each, write down the page's mode (cheapest, single, return or anytime),
party (one adult or two), card and price. The address carries all of them
(`?mode=single&party=2&card=2TR`), so copy it.

## 4. Search National Rail for the same journey

Use the journey planner with the same origin, destination, date, party and
card:

```
https://www.nationalrail.co.uk/journey-planner/?type=single&origin=GRA&destination=SKG&leavingType=departing&leavingDate=061026&leavingHour=09&leavingMin=15&adults=2&railcards=2TR%7C1&extraTime=0#O
```

`type` is `single` or `return`, `leavingDate` is DDMMYY, and `railcards` is
the card code, `%7C`, then the number of cards.

Compare like with like. These are the rules #181 argued over:

- An Advance fare is a real fare, but it is valid on one named train, and the
  page does not publish Advance fares (`page_single_destinations_within`). If
  National Rail's cheapest is an Advance, compare against its cheapest fare
  that is not one.
- The page's return mode is the cheapest standard return. Compare it against
  an off-peak departure's cheapest return. Anytime mode is the Anytime Day
  Return, at any time.
- Cheapest mode is the lowest of the three lists for the party and card on
  screen.
- A railcard price is per person, rounded down to 5p, then multiplied by the
  party (#149). Two Together needs exactly two adults.
- A difference that comes from National Rail offering a fare the page
  deliberately excludes is not a mismatch. Write it down in the reply instead.

## 5. Record what you found

For each mismatch:

1. Add a row to `tests/known_fares.toml` with the price National Rail sold,
   the date you checked, the search link and where it was reported. The
   field list is at the top of that file.
2. Prove the row reaches the page: `python -m tools.check_known_fares --site _site`
   must fail on it, naming both prices. A row that warns instead, naming the
   reachability rule (ADR-0076) or the place cap (ADR-0077) and its count, is
   for a place the page does not list on purpose: pick a destination the page
   lists from that origin, because there is no price there to hold.
3. Find and fix the cause. Then add the smallest synthetic record that
   reproduces it to `make_synthetic_feed.py`, with a comment naming the
   commit that fixed it (F7, AGENTS.md).

For each fare that matched and already has a row, update its `seen_on`.

## 6. Reply

List the three destinations with the page's price, National Rail's price and
the link for each. Name every row you added or updated, and every difference
you judged not to be a mismatch, with the rule above that decided it.
