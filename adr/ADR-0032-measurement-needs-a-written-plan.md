# ADR-0032 — Measurement needs a written plan before a snippet can ship

**Date:** 27 September 2026
**Status:** accepted

## Context

`build_demo_page.py` can inline an analytics snippet from `--analytics-snippet`.
Nothing in the project has ever turned it on, and the privacy page says so: "No
analytics run. If the operator later adds analytics, this page will name them
here first." That promise was unenforceable. A flag is a familiar thing to
reach for, and a snippet inlined into a page that claims to measure nothing is
exactly the kind of drift the re-envision audit calls out: the notice and the
behaviour would disagree, and nothing would say so.

The audit's S38 asks a question rather than describing a feature: if measurement
is still wanted, compare aggregate referrer counts, short retention, no
persistent identifier and no client-side cookie, and write down the trade-off
before enabling it. S37 asks for the same idea in the build: a release
condition that a flag cannot bypass.

## Decision

1. **No measurement is switched on, and the default stays off.** The project
   does not currently need it: the experiment's tripwire is community
   discussion, not traffic, and inventing a measurement story to justify an
   unused flag is the wrong direction of travel.
2. **A snippet without a plan is refused.** `--analytics-snippet` now requires
   `--measurement-plan`, whose value must name one of the plans in
   `build_demo_page.MEASUREMENT_PLANS`. Today that is exactly one:
   `aggregate-referrer-counts` — counts referrers in aggregate, no persistent
   identifier, no cookie, a short rolling retention window. A second plan is a
   new decision with its own ADR.
3. **The privacy page is generated from the build, not from a checklist.**
   `site_features()` reads the same values the pages are built from, and the
   notice's list of practices is written from them. Analytics on, tracked links
   on or an affiliate network configured each make the page say so; each of
   them without a disclosure is a refusal rather than a published page that
   describes a different site.
4. **The gates apply to the release, not to the operator's memory.** A public
   build (one whose prices come from a real feed rather than the synthetic
   default) additionally needs a licence or attribution notice and a privacy
   contact. A synthetic demo build is exempt from the notice by construction,
   because it publishes no real fares, and gets a stated placeholder contact so
   its page is never blank.

## Consequences

- Turning measurement on is now a deliberate act with a written record: the
  flag, the plan name, and a privacy page that says what the snippet does.
- A public build stops if the privacy contact is blank. The default route is
  the public issue tracker (ADR-0068). A blank `PRIVACY_CONTACT` is still a
  refusal, and the message names the variable to set.
- The plans list is deliberately short. Adding an entry is cheap to do and
  expensive to regret, which is the right asymmetry for a decision about
  somebody else's data.

## Alternatives rejected

- **A boolean `--i-have-thought-about-privacy`.** A flag that can be set without
  saying what was thought about is the same problem with an extra step.
- **A trailing comment in the snippet file.** The snippet is third-party text;
  a decision recorded next to it is not a decision the build can check.
- **Inferring the plan from the snippet's contents.** A snippet that sets a
  cookie cannot be made compliant by describing it accurately afterwards.

## 12 October 2026: an ADR that cites a measurement names the tool and the date

The 12 October build-cost audit amended five decisions from its own figures
and each cites its measurement in the amendment itself: the per-origin spread
from `tools/measure_origin_costs.py` over a twelve-origin stride sample, the
byte delta from a controlled two-build comparison in the release's own shape,
and the whole-network projection from that sample. The measurements live in
`docs/build-performance-findings.md`, which is the one place measured figures
are held (ADR, and the README's summary links there). An ADR that leans on a
figure therefore names the tool, the feed and the date it was taken, because a
number without those cannot be re-derived and cannot be disagreed with.
