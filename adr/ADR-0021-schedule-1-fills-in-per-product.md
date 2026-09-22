# ADR-0021: Schedule 1 fills in per product, and §5 decides publication

**Status:** Accepted
**Date:** 22 September 2026

## Context

ADR-0020 recorded the first licence this project had ever read, the Darwin Timetable
Files, and found a conflict inside it: the Open Government Licence head permits
commercial publication, while Schedule 1 §5 permits use "for internal business purposes
only". It left that open, to be put to the publisher rather than argued in-house.

Three more licences have since been taken out and read — Knowledgebase Ticket Types,
Knowledgebase Ticket Restrictions, and Fare Locations Reference Data v1.3 — all filed in
`licences/` with a register beside them. They are the same publisher (Rail Delivery
Group), the same marketplace, and the same Schedule 1 template as Darwin. Their §5 says
the opposite of Darwin's.

## Decision

1. **`§5 PERMITTED PURPOSES` is filled in per product and takes materially different
   values.** Two have now been observed:

   | product | §5 permitted purposes |
   |---|---|
   | Darwin Timetable Files | "The raw data may be copied and used by Data Consumer for **internal business purposes only**" |
   | Ticket Types, Ticket Restrictions, Fare Locations | "The raw data may be **made freely available or otherwise distributed to third parties**" |

   The permissive wording is available in the template and was chosen for three
   products. That makes Darwin's restriction a **deliberate choice rather than
   boilerplate**, which weakens the permissive reading of the ADR-0020 conflict. The
   strict reading — that §5 restricts publication of journey times — is now the one to
   plan around until the publisher says otherwise.

2. **The three new products are not OGL.** They are governed by a **Data Sharing
   Agreement** with contractual terms and conditions, and their clause 2.3 states the
   rule that turns §5 into the deciding field: "Any copying, storage, transmission,
   **publication**, or use, other than as set out in this Agreement is not permitted."
   Permission for a public page therefore lives entirely in §5, and for these three it
   is granted in terms.

3. **Clause 8.8 refines ADR-0016's reading of precedence.** Where ADR-0016 said Schedule 1
   is the operative part, the Data Sharing Agreement ranks the **terms and conditions
   first**, then Schedule 1 excluding Special Conditions, then Special Conditions.
   Schedule 1 is where permission is *granted*; the T&Cs outrank it when they touch the
   same ground. Schedule 1 remains the operative part for the question that matters here,
   because the T&Cs contain no permissions of their own.

4. **A blank §8 `ATTRIBUTION` does not mean no attribution is required.** This is the
   correction that ADR-0020 could not make from its single sample. For the Data Sharing
   Agreement products, clause 3.3.1 makes it a **condition of exercising the licence**
   that the Data Consumer "give an appropriate credit to the Data Publisher by
   identifying the Data Publisher ... as the source of the Licensed Data", in any
   reasonable manner, and not in a way suggesting endorsement. §8's list is where
   *additional* third-party licensors would be named, and there are none. So:

   - the three Data Sharing Agreement feeds require a **credit to Rail Delivery Group**;
   - the Darwin timetable, being OGL with no statement given in §8, requires the OGL
     fallback wording instead. Both attributions are required; they are not alternatives.

5. **Clause 3.3.2 adds an obligation the page does not yet meet.** Where the licence
   permits distribution, the Data Consumer must "ensure that any onward distribution of
   the Licensed Data is accompanied by appropriate notices relating to accuracy of the
   Data together with any relevant limitation or exclusion of liability provisions that
   the Data Publisher requires". Clause 7.2 supplies the substance: the data is "as is",
   with no representation as to accuracy or fitness for purpose, and clause 6.2 excludes
   liability for loss of revenue or profits. A published page carrying this data needs
   those notices in the template, not only the synthetic-data note it has today.

6. **Keep the register honest with a test.** `test_licences.py` asserts every filed PDF
   has a registered row, that every row's product id is backed by a filed licence, that
   every row states whether §5 permits publication, and that no row claims a fee it does
   not name. A licence that is downloaded, filed and forgotten is the failure this
   guards against.

## Consequences

- **The fares product is still the gap, and it is still the decision.** Everything held
  so far is reference and rules data — names, codes, ticket types, restrictions. None of
  it contains a price. The licence that decides this project is the one for the flows and
  fares records, and it has not been found yet by name. The legacy `RJFAF` prefix is not
  the product name (ADR-0020).
- **The timetable is degradable, so its restriction is a feature loss, not a fatal one.**
  `build_demo_page.py` already takes `--timetable` as optional and renders a prices-only
  page that says no timetable was loaded. If §5 means what it says, dropping the journey
  times preserves the product; the fares licence is what would end it.
- **Two attributions and an accuracy notice now have to be implemented.** The page takes
  its wording from an `--attribution` build flag, which means a build can drop it, and
  there is no liability or accuracy notice beyond the synthetic-data line.
- **The register is the artefact to grow.** Each further subscription should be filed,
  read, and given a row before any code depends on it.
