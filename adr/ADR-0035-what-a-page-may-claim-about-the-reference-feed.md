# ADR-0035: A page reports on the reference conditions it shows, and only that

**Status:** Accepted
**Date:** 28 September 2026
**Relates to:** ADR-0020 (notices describe the page they are on), ADR-0021
(one product, one licence, one attribution), the ticket-restriction reference
check added in the 2026-09 release work

## Context

Every station page prints the travel condition attached to each fare it quotes,
in the wording the feed carries. Those words come from the Rail Data Marketplace
restriction feed, which is a separate product from the fares, with its own
licence, and which the page is entitled to redistribute.

The page also has to say something about where that wording came from, and here
the question is what it is allowed to claim. The obvious, wrong answer is that
the page should report on the reference feed as a whole: it can list every
condition code the feed carries in a single pass — 644 in the 28 September 2026
download — and "the portal publishes all 644" is a sentence a build can produce
for free. The other wrong answer is nearly as cheap: the origin's *flows* carry
a wider set still (32 codes for Grantham, when that was measured), so "all 32
are still published" needs only the fares database.

Both are wrong in the same way, and the error is not in the arithmetic. A page
is evidence for the claims it makes, and these two claims have no evidence on
the page. The 644 include codes no row shows, and reporting on them makes the
page's claim change on every feed refresh that happened anywhere on the
network — a reader watching one station's page would see it disagree with a
neighbour for reasons that have nothing to do with either station. The 32 are
codes the origin's *flows* carry, most of which sit on rows the page filtered
out: unpriceable destinations, tickets outside the published selector, rows
the quality rules dropped. A page naming `2H` and `HR` as retired while showing
neither is not making a weaker claim than the first version; it is making a
claim no reader can check, on a page whose entire value is that its claims are
checkable.

The real Grantham page of 28 September 2026 shows **10** distinct codes across
its 190 destination rows. Both larger numbers are right, and neither is what the
page can stand behind.

There is a second half to the question, which is about wording rather than
scope. The reference feed is published text: RDG's words, describing RDG's
conditions. What this project can check is a fact about the *feed* — does the
portal still publish this condition — and a fact about *its own page* — here
are the conditions on it. What it cannot check, and must not imply, is that the
text on the page is the current text, correctly rendered, for a journey on a
particular date. Restating the condition in the page's own words would convert
RDG's published text into this project's statement, which is a different claim
with no evidence behind it at all.

## Decision

**A page may claim that the portal still publishes the conditions that page
shows — a claim about publication, scoped to the codes the page's own rows
carry, made in the feed's own words.**

1. **The claim is about publication, not wording.** The page states whether the
   reference feed still lists each condition it shows. It does not paraphrase,
   summarise or re-word the condition, and it does not claim the wording is
   current for any date. The text stays as the feed published it; the page's own
   sentence is a statement about the feed.
2. **The scope is the rows on the page.** `restriction_codes_shown()` reads the
   `restrictionCode` off the destination, single and anytime rows the payload
   actually carries, and that set *is* the claim. The build asks the reference
   feed about those codes and nothing else. `atoc_fares.restriction_codes()`
   — the query that returned every code the origin's flows carried — is
   deleted rather than left unused, because the next reader would otherwise
   reach for it.
3. **The number is always stated.** "all" without a count is not a check, so
   every wording of the answer carries it: *the portal still publishes all 10
   condition(s) this page shows*, or *the portal no longer publishes 2 of the
   10 condition(s) this page shows (XY, ZW)*. The count travels as data on the
   note, so the page and the console cannot disagree about it.
4. **The page does not answer for a page it is not.** A build with no reference
   feed, one that could not be parsed, or one whose answer is unknown says so
   in as many words. `UNKNOWN` and `ABSENT` are separate statuses on purpose: a
   feed that failed to load is not evidence that the portal stopped publishing.

## Consequences

- The build reads the reference feed **once** per run (`reference_feed()`), not
  once per page. A `--all-origins` build renders up to 2,700 pages, and each
  page's answer is a set difference against the codes that page shows. The
  in-process `--workers 1` path and the pool initialiser both go through
  `build_workers.configure_worker()` for this, because the first version had the
  single-worker path skip the feed entirely and quietly print pages with no
  reference answer — the same build, two different pages, depending on a
  performance flag.
- `reference_fingerprint()` keys the resume signature on a digest of the codes
  the feed lists and their dates, not on the parsed object. A parsed feed has no
  stable serialised form — its `repr` carries an address — so a resumed build
  would conclude it was a different run every time and resume nothing.
- The sentence is written in one place, `describe_restriction_note()`, from the
  note the page itself carries, so the console line and the page cannot describe
  different checks. The first version printed the date as a clause after the
  count and produced "all 10 condition(s) this page shows, published on this
  page, a splice no reader should have to parse" — visible on the real page
  whenever the feed carried no publication date.
- Three browser checks hold the decision in place, and each was proved to fail
  when the thing it checks is broken: the count in the sentence equals the
  number of distinct codes on the page; every code named as no longer published
  appears in the page's own reference list; and the sentence has no splice.
- What the page still does not claim, and what no footer can supply: that the
  conditions are the operative ones for a particular journey on a particular
  date. That remains the reader's check against the seller, which is what
  `PRICING_NOTE` says next to the times.
