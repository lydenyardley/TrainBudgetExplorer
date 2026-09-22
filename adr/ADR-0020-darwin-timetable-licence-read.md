# ADR-0020: The Darwin timetable licence is OGL3 in the head and restrictive in Schedule 1

**Status:** Accepted
**Date:** 22 September 2026

## Context

Every licence question in this project has until now been unread. ADR-0005 recorded
that the terms sit behind a session; ADR-0016 recorded four `unread` cells for each
of the two products and named the reason as one and the same: the Schedule 1 that
fills the template in is only reachable while signed in.

The account exists now, and the first licence text has been obtained. It is the
**Darwin Timetable Files** licence, saved as
`Darwin-timetable-license-P-9ca6bc7e-62e1-44d6-b93a-1616f7d2caf8.pdf` and read on
22 September 2026. The filename encodes the product id, which is the id Schedule 1
§3 refers to as the `LICENCED DATA`.

Two search directions failed first, and both failures are worth recording because
they are the obvious next move for anyone returning to this:

- Searching the marketplace for **`Schedule 1`** returns nothing. Schedule 1 is a
  section *inside* the downloaded PDF, not a catalogue field.
- Searching for **`RJFAF`** returns nothing. It is the legacy ATOC file prefix for
  the fares feed, not a product name. Marketplace products are named in words
  ("Darwin Timetable Files", "Knowledgebase Ticket Types data feed", "Fare Locations
  Reference Data"), and their category is the axis that works:
  **Ticketing fares and retail (Fares)**.

## Decision

1. **Record what the timetable licence actually says**, which is two documents in
   one file that do not agree:

   | part | what it says |
   |---|---|
   | head | **Open Government Licence v3.0** — grants a worldwide, royalty-free, perpetual, non-exclusive licence; you are free to copy, publish, distribute, adapt, and "exploit the Information commercially and non-commercially ... or by including it in your own product or application" |
   | Schedule 1 §5, `PERMITTED PURPOSES` | "The raw data may be copied and used by Data Consumer for **internal business purposes only**" |
   | Schedule 1 §8, `ATTRIBUTION` | organisations "must be attributed if the data is subsequently published" — **and then lists none** |
   | Schedule 2, `LICENCE FEE TYPE` | **`Open (OGL3)`** — "The Data Consumer can access the Licensed Data without charge" |
   | §6 term | 1 year, renewing automatically on the anniversary, 1 month notice for convenience |
   | §9 retention | the data may be retained after the term |
   | Schedule 2, `UPDATE FREQUENCY` | Daily |

2. **The head and Schedule 1 conflict, and this project already decided which
   governs.** ADR-0016 established the reading that the DSA is generic and Schedule 1
   carries the particulars. Applied here, §5's "internal business purposes only"
   restricts the OGL head's commercial and publication freedoms, and a public page
   showing journey times may therefore be outside the permitted purposes.

3. **Do not resolve the conflict by argument. Put it to the Data Publisher in
   writing.** Two readings are available and the difference decides the product:

   - **Strict:** §5 limits *use* to internal business purposes, so publishing is out.
   - **Permissive:** §5 restricts copying and use of the **raw data**, while the OGL
     head permits the derived product; §8's "if the data is subsequently published"
     reads as contemplating publication, and §5's wording looks like DSA boilerplate
     carried into a template.

   A question to RDG costs one message. Guessing costs the project its premise.

4. **The attribution requirement is the OGL fallback, and the timetable gives no
   statement of its own.** §8 names no organisations and supplies no wording. The OGL
   head covers that case explicitly: where the Data Publisher does not provide a
   specific attribution statement, you must use
   `Contains public sector information licensed under the Open Government Licence v3.0.`

5. **The timetable licence fee is nil.** Schedule 2 says `Open (OGL3)` and no charge.
   This is the first licence-fee answer this project has, and it does not transfer to
   the fares product — the two products are licensed separately.

## Consequences

- **The fares licence is still unread, and it is the one that matters most.** Prices
  are the product; journey times are secondary. The fares product must be found by
  name (see the search note above), its licence PDF downloaded the same way, and its
  Schedule 1 read before anything is published.
- **A restrictive §5 on the fares product, matching the timetable's, would end the
  public-page plan rather than the project.** ADR-0004's tripwire and ADR-0005's
  fallback already stand: the same parser answers personal budget questions, and the
  affiliate plan dies instead of the work (ADR-0010).
- **Two `unread` cells in ADR-0016 narrow but do not close.** The timetable side is
  now read for attribution and fees; commercial use and redistribution remain legally
  unresolved — not unread, but in conflict.
- **The attribution statement needs one home in the code.** The page takes its
  wording from an `--attribution` build flag today, which means the statement can be
  dropped by the next person to run a build. The checklist now requires it pinned in
  one place.
- The licence PDFs are the evidence for all of the above and should be kept, one per
  product, in the repository rather than in a downloads folder.
