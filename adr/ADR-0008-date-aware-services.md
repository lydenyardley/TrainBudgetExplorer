# ADR-0008: A journey time belongs to a date

**Status:** Accepted
**Date:** 21 September 2026

## Context

The first journey implementation read every schedule in the feed. That is wrong
in two directions at once. A Sunday-only train appeared on a Tuesday, and a
cancelled train still ran. It also ignored the fact that a feed covers a date
range, so schedules for a period that has ended looked current.

The timetable feed carries the three fields needed to fix this: a Monday to
Sunday service day pattern, a date range, and an STP indicator.

## Decision

1. **A schedule answers its own question.** `Schedule.runs_on(day)` checks the
   date range and the service day pattern, and nothing else.
2. **Cancellations remove, overlays replace.** A cancellation entry removes the
   permanent schedule of the same train identity for its date range. An overlay
   replaces it. An overlay wins over a cancellation that covers the same date,
   because the overlay is the more specific instruction.
3. **A date is optional and its absence is meaningful.** Without a date the
   search reads every schedule, which keeps the Stage 1 coverage question
   answerable before the question "which Tuesday" exists. With a date, only
   schedules running that day are indexed.
4. **Indexes are cached per service date.** The station indexes rebuild when the
   date changes, so repeated queries for one date cost one build.

## Consequences

- `--date YYYY-MM-DD` turns a typical journey time into a date-specific one, and
  the CLI prints which date it used. A destination with no train that day shows
  as no service rather than silently disappearing.
- Two dates need two runs. A week view would need a loop over dates, which the
  index cache already makes cheap.
- Bank holidays are still not interpreted. The feed carries a bank holiday
  marker, and a schedule that skips them will appear on one until that marker is
  read.
- The Stage 1 count stays undated on purpose. Its question is whether enough
  destinations exist near Grantham, not whether they exist on a chosen day.
