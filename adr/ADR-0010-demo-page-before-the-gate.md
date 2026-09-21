# ADR-0010: The demo page is built before the gate opens, but stays local

**Status:** Accepted
**Date:** 21 September 2026
**Relates to:** ADR-0001 (licences), ADR-0003 (discovery and monetisation),
ADR-0004 (staged plan and stop rules)

## Context

ADR-0004 kept the demo UI unbuilt until the real feeds produced the Grantham
count, on the grounds that building a page which might say "nowhere" repeats the
spreadsheet mistake: time spent on presentation before demand is verified.

The owner has since asked for the page, to run against the synthetic feeds until
the real ones land. That is a deliberate change to a written decision, so it is
recorded here rather than left as an undocumented drift.

Two risks were weighed:

1. **Sunk effort before validation.** Real, but small: `build_demo_page.py` is
   about 300 lines of generator and template, writes a single static file, and
   adds no data pipeline. The Stage 1 gate still decides whether anything is
   published, and the page is what makes that decision inspectable.
2. **Publishing on unverified licences.** Serious, and avoidable. A page carrying
   prices from a feed whose commercial terms are unconfirmed, with affiliate
   links attached, is the version of this product that could get someone into
   trouble. So the page ships with no affiliate links at all and is not served
   publicly.

## Decision

Build `build_demo_page.py`. It reads the same feeds as the sweep, embeds the
priced destinations as one JSON payload, and writes a self-contained HTML file
with a budget slider, a city or town filter, and a party mode. No server, no
build step, no external assets.

Constraints, each deliberate:

- **Local only.** The file is generated, opened, and read. Nothing is deployed,
  and `demo*.html` is not committed, because it is derived from feeds that are
  not in the repository.
- **No affiliate links yet.** ADR-0003's monetisation plan waits for the licence
  text. Adding links before that is the one thing here that cannot be undone by
  regenerating a file.
- **Every approximation stays on the page.** The footer states that fares are
  cheapest Anytime or Off-Peak returns, that Advance singles can undercut them,
  and the provenance line states whether services are date-specific, whether a
  timetable was loaded at all, and whether a Two Together railcard was found. A
  page that hides those is worse than no page.
- **Both party prices are carried.** The reader chooses whether the budget covers
  one adult or the two of them, because ADR-0002 makes party pricing a property
  of the fare maths rather than a display option.

## Consequences

- The Grantham question becomes inspectable: raise the slider and watch the list
  empty out, which is the same information the go/no-go count carries, in a form
  the owner and anyone else can read without running a command.
- The page is a second consumer of the parser layer, so it exercises the fare,
  railcard, and journey paths together rather than one at a time. Two of its
  tests exist because writing it surfaced wrong expectations about the data, not
  wrong code.
- A real feed replaces `--feed` and `--timetable` and the page regenerates
  unchanged. Three feed releases a year means three regenerations, or none until
  the numbers move enough to matter.
- The Stage 1 gate is unchanged, and so is the 21 October review. What changed is
  that the gate now has a screen attached to its answer.
- If the licence text forbids commercial use, the page survives as a demo or a
  portfolio piece and the affiliate plan in ADR-0003 dies instead. That
  separation is the reason this ADR keeps the two apart.
