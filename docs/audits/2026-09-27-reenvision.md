# Re-envision pass — a better fare-first rail explorer

**Date:** 27 September 2026  
**Scope:** The whole app: public route journey, generated pages, data/publishing workflow, and experiment. This is a forward-looking proposal list, not a build plan and not permission to change application code in this task. No application code was changed.

## The weakest subsystem

**The route/publishing contract is the part furthest below the product's promise.** The app has a coherent “tell me the budget, show me places” idea and a substantial honesty layer, but the single-origin build can publish a station page whose Change picker links to pages it did not generate. The current Pages workflow builds one GRA page at the root, while the product's full-network design assigns the root to a chooser and station URLs to `/from/<slug>/`. Until those shapes agree, visual polish or new filters are improvements on a surface whose basic navigation may not exist.

The strongest next rebuild is therefore not a new look: make the generated artifact, its route manifest, its navigation links, and the deployment workflow describe exactly the same site. Then make every subsequent product enhancement preserve the rule that a fare, service, or seller link must never look more certain than its evidence.

## North star

A traveller arrives with a price ceiling and an origin in mind, gets a shortlist they can scan in seconds, understands what each fare and time does—and does not—promise, and can share or hand off the exact shortlist without retyping it. A missing feed fact should become a visible state, not a plausible-looking number. The operator should be able to publish the same route contract reproducibly, prove internal links and disclosures, and stop at the experiment's existing tripwire rather than building ahead of evidence.

## Suggestions

Each item has an explicit expected benefit. They range from small copy/interaction fixes to substantial product and data-platform bets; they are intentionally not implementation commitments.

> **Thirty of these are now built.** The completed items have been
> removed from this list; the record of each is the commit that carries it,
> the `adr/` entry where the change was a decision rather than a fix, and the
> test that holds it in place. The suggestions still listed here are the ones
> the project has not taken up.
>
> Four were removed for the count above by checking the source rather than the
> note: **S18** (per-mode notes above the table name the set and separate
> unrestricted, restricted and Advance-single fares — `MODE_NOTE`,
> `renderModeNote`), **S21** (`moreFiltersToggle`/`moreFiltersPanel`), **S30**
> (`#linkNote` and `#disclosure` sit above the table, not in the method
> accordion), and **S32** (`journeyText` carries origin, destination, ticket
> mode, date, passengers and the railcard caveat, and the copy box survives a
denied clipboard permission). **S17** was checked at the same time and is only
> half built, so it stays below with what remains named.

### Origin discovery and entry points

**S08 — Offer an opt-in “find my station” path backed by a reviewed station-coordinate source.** Keep manual name/code search as the default and explain exactly what location permission does before asking.  
**Expected benefit:** travellers who know their town but not the station's CRS code can still start quickly without silently collecting location data.

**S09 — Add region, town, or rail-network grouping when a trustworthy geography source is selected.** Keep the provenance and coverage of that mapping alongside the station index.  
**Expected benefit:** the origin directory remains navigable when a user cannot use nearest-station lookup or exact station spelling.

### Price-first results and exploration

**S13 — Give each destination a compact, price-led result card on phones and a comparable row on desktop.** Keep station, current price, ticket validity, journey time/changes, and actions in a consistent reading order.  
**Expected benefit:** users can compare destinations without horizontally scanning a dense row of columns or losing field labels on small screens.

**S14 — Show the individual and two-person price together when both are trustworthy.** Make the headline budget unit explicit and keep the railcard scenario separate from the standard party total.  
**Expected benefit:** pairs—the stated first-class use case—can see their actual decision without toggling back and forth or confusing per-person and party totals.

**S16 — Sort and emphasize by the price currently being displayed.** Recompute order and the “best” cue after party-size or railcard changes.  
**Expected benefit:** price-first ranking remains truthful for the selected scenario.

**S17 — Make the budget contract explicit and consistent.** *(half built)*  
The inclusive ceiling is done: one resolver (`resolvedBudget`) feeds the heading, the control, the results count and the URL, and all four say “up to”, so a fare at the boundary is included and the figure cannot drift between them (ADR-0019, C15, C21).  
**What remains:** the second half — *expose how the maximum is determined*. The control's ceiling is a build-substituted value (`__MAXPOUNDS__`) with nothing on the page saying where it comes from, so a reader cannot tell why the slider stops where it does.  
**Expected benefit:** users can predict exactly whether a fare at the boundary is included and why a control stops where it does.

**S24 — Offer date-specific schedules as an explicit product mode.** Build or select a timetable snapshot for the named date, label its service date beside times, and keep undated aggregate schedules visibly indicative.  
**Expected benefit:** a journey-time suggestion is tied to the travel day the user cares about rather than a mixed schedule set.

**S25 — Extend calendar handling only when the source can support it.** Treat bank holidays and service exceptions as first-class inputs, and show a clear fallback where that data is unavailable.  
**Expected benefit:** fewer “typical” schedules are mistaken for holiday-specific service.

**S27 — Create a few evidence-backed discovery entry points.** Examples could be “cities under £20,” “seaside under £20,” or a route from a community post, generated only from current priceable destinations.  
**Expected benefit:** a traveller with a broad idea but no exact town gets a useful first click without editorial claims about popularity.

### Ticket handoff and confidence

**S31 — Verify deep links per seller, date, and party before enabling them.** Keep a working fallback and make the destination's link mode explicit; never infer success from a URL that merely has query parameters.  
**Expected benefit:** users receive the shortest handoff that is actually known to work.

**S34 — Add a human-readable feed-change report for the operator.** Compare each new feed with the previous one, highlighting material price changes, removed fares, changed station coverage, and timetable freshness.  
**Expected benefit:** scheduled publication has a reviewable reason to change and suspicious jumps are easier to catch.

**S35 — Make provenance and approximation visible as compact “confidence” signals.** Distinguish reviewed fare, conditional fare, missing service data, classification coverage, and seller-link confidence without inventing a numeric confidence score.  
**Expected benefit:** readers can assess the exact uncertainty rather than interpreting one generic disclaimer as applying to every row equally.

### Privacy, accessibility, and design system

**S40 — Decide the public name before designing identity assets.** Once chosen, create a restrained rail-specific visual cue that supports the price-first premise; until then, avoid presenting “Rail Budget” as a settled brand.  
**Expected benefit:** the site feels intentionally authored without committing to an unapproved name or generic SaaS decoration.

### Validation and experiment discipline

**S43 — Use short, task-focused sessions with the intended traveller before broadening the feature set.** Ask someone who has a price ceiling but no destination to find a usable day out, then ask them to explain the fare and time they selected.  
**Expected benefit:** the next changes address real interpretation failures rather than adding features because they are technically possible.

**S44 — Instrument the existing tripwire before investing in a large redesign.** Record venue-level visits/comments/return signal only under an approved privacy approach, then compare evidence with the dated park-or-continue decision.  
**Expected benefit:** effort stays bounded by the experiment and the project does not mistake a polished interface for demonstrated demand.

**S46 — Add lightweight task telemetry without personal tracking only if it is necessary and permitted.** A static “Was this shortlist useful?” prompt or an optional feedback route can gather qualitative signal without recording the user's budget/filter state.  
**Expected benefit:** the owner gets actionable feedback from the communities that matter without turning a static experiment into a tracking product.

## Adversarial pass

I challenged the suggestions against the brief and the checked implementation rather than treating every possible feature as free:

- The route rebuild is the single weakest subsystem; it should come before visual rebranding or additional facets.
- “Nearest station” is not derivable from the current station feed. S08/S09 require a named, reviewed geography source and must retain a manual-search fallback; no location permission is assumed.
- Date-specific fares, a chosen train, or a verified deep link must not be implied unless the source data and seller destination actually support it. S24/S31 preserve that boundary.
- Two Together is not modeled as a solo discount. S15 explicitly makes the party condition part of the price state.
- Analytics, affiliate tracking, and public data use remain gated by the licence and privacy decisions; suggestions do not authorize enabling them.
- A future redesign should still respect the current “no external runtime assets” constraint unless the product deliberately changes that architecture.
- This task only records recommendations. No implementation was attempted; the user's two-audit-only boundary is preserved.
