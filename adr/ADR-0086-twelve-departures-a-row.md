# ADR-0086: Twelve departures a row

**Status:** Accepted
**Date:** 7 November 2026
**Relates to:** ADR-0084 (a row's panel is the trains and the fare), O43 (the time control that is still refused)

## Context

A row's panel listed the first five trains of the service day. The 4 November
2026 review asked for a time control beside the day control, and the record
refused it on bytes and on the payload's shape: the page holds no per-train
windows, so a control could only slice the five already sent. The 7 November
2026 review asked the narrower question, what eight and twelve departures cost,
and to ship twelve if it was cheap.

## Decision

`DEPARTURE_LIMIT` is **12** in `build_payload.py`. The panel draws them as a
four-column table (departs, arrives, journey, changes) rather than one sentence
per train, so the twelve rows are compared down columns.

## Evidence

The Grindleford page, real feeds, 2026-10-05:

| Build | Page bytes | Delta |
|---|---:|---:|
| 5 | 268,604 | -- |
| 8 | 283,113 | +14,509 (+5.4%) |
| 12 | 300,463 | +31,859 (+11.9%) |

The release measured 370 MB of its 800 MB budget over 2,838 pages on 26
October 2026. Twelve percent on every page would be 414 MB, with 386 MB spare.
The figures and the plan are in `docs/build-performance-findings.md`.

## Consequences

- **A timed page is about 12% larger**, and a page whose destinations carry no
  times is unchanged. The site gate still measures the release, not this
  estimate.
- **The time control is still refused.** Twelve rows are still the first twelve
  of the day; a reader at four in the afternoon sees the morning unless the
  payload learns to slice by time. O43 records that, unchanged.
- **The panel is a table.** Four short headings and one row per train replace
  the sentence whose words moved from line to line.
