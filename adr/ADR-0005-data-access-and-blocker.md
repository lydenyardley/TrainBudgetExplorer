# ADR-0005: Data access requires an account, so the parser was built first

**Status:** Accepted
**Date:** 21 September 2026

## Context

Stage 1 assumed a fares sample could be obtained quickly. Testing that
assumption showed otherwise. The historic `data.atoc.org` host no longer
responds, and both live portals (`opendata.nationalrail.co.uk`, `raildata.org.uk`)
are JavaScript applications whose data API did not connect from this machine.
Licence text sits behind a session. Nothing about the fares feed is anonymously
readable, and scraping a retailer stays rejected under ADR-0001.

A second fact changed the plan for the better. The fares feed's record layouts are
documented in open-source parsers, so the parsing work does not depend on holding
the data.

## Decision

1. **Build the parser now** against synthetic fixtures that use the real record
   layouts, and verify it with literal-value tests. The lever exists before the
   data arrives, so the day the feed lands is a data question, not a coding
   question.
2. **Data comes from the Marketplace account**, created by the owner, with the
   licence accepted in their name. No anonymous or scraped substitute.
3. **The railcard discount is a documented assumption** ("1/3 off", which is the
   published rule for Two Together), with the feed's `dis` and `frr` files named
   as the upgrade path. Minimum fares come from `rcm`, which is real data.
4. **Stage 2 does not start until the sweep has run on real fares.** The Grantham
   count is the go/no-go input, and a demo that answers "nowhere" must be caught
   before any UI work.

## Consequences

- Four days of Stage 1's budget were not needed. The parse-and-query layer is
  done, and only the download remains.
- The owner holds a two-minute task that cannot be delegated. It is the single
  item on the critical path.
- Licence terms remain unread. Commercial use, attribution, and redistribution
  are still unverified, so the affiliate and public-launch decisions in ADR-0003
  stay provisional until the licence text is read on signup.
- If the licence forbids the intended use, the work to date is not wasted: the
  same parser answers personal budget questions, and ADR-0004's tripwire still
  bounds the project.
