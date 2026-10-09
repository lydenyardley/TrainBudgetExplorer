# ADR-0068: The contact route is the issue tracker

**Status:** Accepted
**Date:** 9 October 2026
**Relates to:** ADR-0032 (a public build needs a privacy contact), the release gate in `tools/check_release_clearance.py`

## Context

A real-feed page has to name somebody a reader can tell about a problem with
the site. The build used to print an email address for that. An address on a
public page is a published mailbox: it can be copied out of the HTML, and the
project had not confirmed that anyone reads it.

The repository has a public issue tracker. That is a route a reader can open
without the page carrying an email address.

## Decision

1. **Every build names the issue tracker.** `DEFAULT_PRIVACY_CONTACT` in
   `build_demo_page.py` is the same sentence for a synthetic demo and a
   real-feed build, and it includes
   `https://github.com/lydenyardley/TrainBudgetExplorer/issues`. The page
   prints that route and no email address. `PRIVACY_CONTACT` and
   `--privacy-contact` still override it.

2. **The clearance stays open.** `licences/release-clearance.md` keeps
   `privacy contact` at `excluded`. Clearing it means a person has confirmed
   they monitor issue notifications, with the date and who confirmed it.
   Choosing the route is not that confirmation.

## Consequences

The live page does not contain the project's email address. A reader who
wants to write still has a working URL. Publication remains blocked until
the checklist item "A monitored contact route exists" is ticked and the
clearance section is updated to match.
