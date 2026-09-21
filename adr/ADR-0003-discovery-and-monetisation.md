# ADR-0003: Discovery and monetisation

**Status:** Accepted
**Date:** 21 September 2026

## Context

The spreadsheet post-mortem concluded the Etsy products died of *discovery*
(15 views in 30 days), not product quality. Any new build must name its
audience path before code is written. Separately, the owner deferred Upwork
specifically because an empty profile is a weak position; the Trainline
affiliate programme has the same shape.

## Decision

1. **Discovery: communities first, then decide.** The Grantham demo launches
   to r/uktrains, relevant local Facebook groups, and (if worthy) Hacker News.
   Measured: clicks, comments, repeat usage. SEO/content investment happens
   **only if** a community signal appears. No fresh-domain SEO bet.
2. **Monetisation: affiliate lead-gen asset** (owner-selected hypothesis).
   Trainline affiliate via Partnerize/Awin, applied for **after** the demo
   exists and has some traffic — accepting the known risk that a low-traffic
   application may be rejected, and that a rejected/absent affiliate link
   makes v1 revenue exactly £0. No other monetisation in v1.
3. **The honest comparison on record:** this repeats the "build first, apply
   later" pattern that Upwork deferral avoided. Accepted because the demo's
   primary purpose is a demand experiment, not immediate cash — and because
   the staged time-box (ADR-0004) caps the exposure.

## Consequences

- Launch plan must include a community-posting checklist and measurement
  (referrer tracking on the demo).
- If affiliate application is rejected, the tool continues as a demand
  experiment; monetisation revisits only if traffic appears.
- SEO/content work is explicitly gated behind community evidence.
