# ADR-0001: Data sources for timetable and fares

**Status:** Proposed — licence terms must be verified from the actual data licence agreements before any public launch
**Date:** 21 September 2026

## Context

The service needs, for any origin station: (a) which other stations are reachable, and (b) what the cheapest realistic fare is.

## Options considered

1. **Darwin / Network Rail timetable open data** — free, national coverage, stable. Gives times and reachability but **no prices**.
2. **Full ATOC/NRE Fares Feed via the Rail Data Marketplace** — complete fare matrix, released three times yearly, legacy format, heavier licence obligations; community parsers exist (librailfare, UK2GTFS).
3. **Marketplace fare APIs (e.g. Easy Fares API demo)** — queryable single/return fares between two points, licences "generally free"; coverage and rate limits unverified.
4. **Scraping retailers or TOC sites** — against primer ethics (no scraping personal data / misleading presentation) and fragile. Rejected.

## Decision (proposed)

- **Timetables:** Darwin open data (free) for reachability and scheduled journey times.
- **Fares:** start from static, scheduled fares only (Anytime/Off-Peak — flat, timetable-independent), sourced via the cheapest lawful route (Marketplace product or Fares Feed download); show an honest disclaimer that cheapest Advance singles may be lower and vary by train.
- Verify licence terms for attribution, commercial use, and redistribution **before** any public launch; prototype only against feeds with confirmed free/licensed access.

## Consequences

- Fast prototype is feasible in days, not months.
- Prices shown are "typical walk-up fares", not the cheapest possible — must be labelled honestly to stay inside the primer's no-misleading rule.
- Licence verification is a hard gate before launch, before the build if possible.
