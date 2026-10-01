# ADR-0049: The feed-change report refuses nothing on its own

**Status:** Accepted
**Date:** 1 October 2026
**Relates to:** ADR-0035 (what a page may claim about the reference feed)
Settles S34 in `docs/audits/2026-09-27-reenvision.md`.

## Context

Every gate in this project asks whether a release is *internally* sound. The
link crawl asks whether every internal link resolves; the release-clearance
check asks whether the licence record permits publishing; the byte budget asks
whether the site fits. All three are the right questions and none of them can
answer the one an operator has before replacing a feed: **what changed?**

A fare moving is not a defect, so no gate should refuse it. But a new download
arrives on a schedule, replaces the one the published pages were built from, and
goes out with a green build — so a feed that quietly lost a station, or moved a
fare by a third, or changed a restriction at an unchanged price, is invisible.
The restriction case is the sharpest: the price column on the page looks
identical, and what the fare permits is different.

## Decision

`tools/feed_change_report.py` compares two snapshots and prints the difference.
Three choices in it are decisions rather than implementation.

**A fare is identified by what it is, not by the feed's record key.** The key is
the pair of location codes, the route code and the ticket code — not the flow id.
A flow id is the feed's own key and a publisher may renumber it between
downloads; keyed on it, a renumbering reads as the entire catalogue removed and
re-added. There is a test that renumbers the flow id and asserts nothing moved.

**A move must clear two bars, not one.** A fare counts as moved when it moved at
least `--material-pct` of its old price **and** at least `--material-pence` in
absolute terms. Either bar alone is wrong in a way that matters: fifty percent is
arithmetic on a fifty-pence fare, and five percent is thirty pence on a
five-pound one. Both thresholds are flags, because the right numbers are the
operator's judgement and not the tool's.

**The tool refuses nothing by default.** `--fail-on-material` exists and exits 1
when any fare cleared both bars. It is off unless asked for. This is the part
worth arguing about: every other refusal in this project is on by default,
because the project's stance is that a thing it cannot vouch for should not
publish. But that stance is about *claims the site makes* — a link that might
land on a retailer's error page, a price the feed cannot attribute to a fare.
A price that moved is not a claim the site got wrong. A tool that refused on its
own authority would be inventing a policy, and a policy nobody chose is one
nobody can argue with.

Two smaller decisions follow from the same reasoning. A fare whose flow record
the feed does not carry is **counted and named** rather than dropped, because
dropped it would appear as a removal that never happened. And a figure that did
not move is reported as having **held** rather than "moved from £1.00 to £1.00",
because a report whose sentences say a change happened when none did teaches
its reader to stop believing it.

## Consequences

- A scheduled publication can carry a reviewable reason for its prices. The
  report is Markdown, so it pastes into a release note; `--json` writes the same
  content for a machine.
- The comparison covers the whole feed rather than the pages a build would
  publish, so it includes fares no page shows. That is deliberate: a change in
  what the feed *carries* is what a coverage decision is made on.
- Nothing in the release path depends on this tool. It is not wired into the
  deploy workflow, because a gate that fires on ordinary fare movement would be
  switched off within a month, and a switched-off gate is worse than none.
- The tool reads two folders the operator names. It does not fetch, store or
  retain snapshots, so keeping a previous feed to compare against is still the
  operator's business.

Read by running:

```bash
python tools/feed_change_report.py --previous-feed feeds/previous --feed feeds/fares
python -m unittest tools.test_feed_change_report -v
```
