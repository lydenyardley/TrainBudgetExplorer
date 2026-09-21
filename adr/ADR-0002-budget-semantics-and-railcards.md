# ADR-0002: Budget semantics, fare classes, and railcard scope

**Status:** Accepted
**Date:** 21 September 2026

## Context

"What does £20 mean?" is not a UI question — it determines the fare engine.
Fares multiply per passenger; railcards change the maths (Two Together only
exists as a *party* discount); Advance fares are per-train and yield-managed;
each railcard carries restriction codes (minimum fares, time-of-day validity,
excluded flows) that add another dataset and correctness risk.

## Decision

1. **Budget unit (v1):** cheapest scheduled **Anytime/Off-Peak return per adult**.
   The headline question is "what can *each of us* reach for ≤£20 return?".
2. **Two Together Railcard is the only railcard in v1**, shown as a party
   price: both adults' returns at 1/3 off, displayed as a party total and an
   effective per-adult figure. Rationale: it is the owner's real use case, and
   it is the one railcard whose maths forces party pricing — a differentiator
   no mainstream journey planner shows.
3. **All other railcards (16–25, Senior, Family, Disabled, etc.) are out of
   scope until a demand signal justifies them.** Each adds restriction-code
   data and failure modes. Deferred, not forgotten (see ADR-0003 gates).
4. **Advance fares are excluded from v1 prices.** The UI must state honestly:
   "typical walk-up fares — cheapest Advance singles may be lower". This keeps
   the tool inside the no-misleading rule.
5. **Child fares: out of scope in v1.**

## Consequences

- The fare engine needs only: flows (origin→destination pairs), cheapest
  Anytime/Off-Peak return, and the Two Together discount rule.
- Two Together's exact restriction rules (any minimum fares, ticket-type
  exclusions) must be verified from the restriction codes data during the
  build, not assumed.
- If Grantham returns almost nothing at ≤£20/adult, that is a Day-2 finding,
  not a reason to quietly change the question (see ADR-0004 go/no-go).
