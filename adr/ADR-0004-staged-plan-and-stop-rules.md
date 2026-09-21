# ADR-0004: Staged plan, go/no-go criteria, and stop rules

**Status:** Accepted
**Date:** 21 September 2026

## Context

The primer's post-mortem rule: no build without pre-verified demand signals.
The owner declined pre-agreed numeric demand gates ("judge at the time") but
accepted one written tripwire (a date, not numbers). The owner also chose to
run the full staged plan **now**, before publishing Missing Music and The
Family Apothecary — explicitly pushing back the stated priorities.

## Decision — the staged plan

| Stage | When | What | Gate |
|---|---|---|---|
| 1. Verify | 22–23 Sep | Register on raildata.org.uk; confirm licence text for timetable + fares products; download samples; parse a fares sample; compute the real count of Grantham destinations ≤£20 Anytime/Off-Peak return per adult | **Go/no-go, 23 Sep.** No-go if licences block commercial use, or the data can't be parsed in the 2 days, or Grantham genuinely has ~nothing ≤£20 (the demo would answer "nowhere") |
| 2. Build | ≤1 week, to 30 Sep | Grantham-only demo: static fares + scheduled times, budget slider, city/town filter, Two Together party price, honest Advance disclaimer, free hosting | Hard stop at 30 Sep — any unfinished feature is cut, not delayed |
| 3. Launch + listen | w/c 5 Oct | Community posts (ADR-0003), referrer tracking, affiliate application | — |
| 4. Review (tripwire) | **21 October 2026** | Written review: community traction? owner still thinks it's worth keeping? | Default outcome if unsure: **park it** — docs stay, no further time. Resuming later requires a new decision |

## Risk register

1. **Sequencing tension (accepted by owner):** this runs before Missing Music
   and The Family Apothecary are published, contradicting the paused money
   plan's ordering. Time-box caps the damage: Stage 1 is 2 days, Stage 2 is
   hard-stopped at 1 week.
2. **"Judge at the time" without numbers:** mitigated only by the dated
   tripwire and the park-by-default rule.
3. **Affiliate rejection:** v1 revenue £0 regardless; accepted (ADR-0003).

## Consequences

- The idea cannot silently consume the runway: two hard dates (30 Sep build
  stop, 21 Oct review) bound the whole experiment at ~4 weeks part-time.
- All numeric analysis (the Grantham ≤£20 count) happens in Stage 1, before
  any build decision.
