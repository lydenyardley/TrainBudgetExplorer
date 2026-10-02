# ADR-0052: A railcard is one of a collection the reader picks from

**Date:** 1 October 2026
**Status:** Accepted
**Question:** How does the page offer a railcard now that Two Together is one of
several rather than the only one?

## Context

`atoc_fares.py` models a railcard as a product with the codes the feed carries
for it, and `REVIEWED_PUBLIC_RAILCARDS` reviews six of them. Nothing consumed
that yet. The page priced one card, Two Together, through a checkbox that was
ticked or not, and a row carried that one card's whole answer.

The owner's answer to question 2 in `docs/open-work.md` was that Two Together is
one of the entire collection of available railcards, that the default is no
railcard selected, and that the browser remembers the choice once one is added.

That is a control, a default and a memory. It is also a payload shape, and the
shape is what this record is about.

## The shape, measured rather than argued

A row's single railcard entry cost 433 bytes on the real Grantham page. It carried the price,
minimum, state, a key into the shared rule map, and a sentence explaining the
DTD decision. Six of those is 2,598 bytes a row on a page that already carries
411KB, across 190 rows and 2,718 pages, against a site budget of 800MB.

Four candidate shapes were measured on that page.

| Shape | Bytes a row | Page total |
|---|---|---|
| One object per card, keys spelled out | 287 | 54,530 |
| One array per card | 139 | 26,410 |
| Prices and drawer facts split | 197 | 37,430 |
| What varies per row only | 98 | 18,620 |
| Today, for one card | 433 | 82,270 |

The last row is the one that decides it. The straightforward six-of-the-same
shape is a 6x regression against a shape that is already too heavy.

Three measurements explain the cheap shape:

* the 190 rows share one RR rule record, so rules already deduplicate;
* the minimum fare is a function of (card, ticket code) and there are 16
  distinct ticket codes on the page, so it is not a per-destination fact;
* the discounted price is the only per-row, per-card fact that cannot be looked
  up from something else.

So the row keeps a price and a rule key per card, the rule records stay hoisted
into one shared map as audit B3 paid 388KB to establish, and the drawer's
sentences are composed by the page from the facts. Measured on the built page:
the payload went from 411,583 to 421,124 bytes, +2.3%, and now carries six cards
where it carried one.

## The decision

**Facts ship, sentences are written by the page.** The build carries the numbers
and the DTD rule records, which are facts about the feed. The drawer composes
its own prose from them. Six cards of build-written sentences per row is a cost
the site budget cannot carry.

**A select, not six checkboxes.** One control whose first option is "No
railcard". The default needs no separate control and cannot be left on by a
reader who meant standard fares.

**Nothing is selected by default.** The prices on load are standard fares, and
the page says so in the sentence under the control rather than leaving the reader
to infer it from an unticked box.

**The browser remembers the choice**, under `tbe.railcard.<origin CRS>`, keyed
per origin because a reader from one station is answering the same question as a
reader from another and a stored card must not travel to a page whose feed priced
nothing for it. The address carries `card=<code>` as well, so a shared link is
the same search.

**A card that cannot cover the party on screen cannot be chosen**, rather than
left there to be picked and then ignored. The bounds are the feed's own records
for that card. Two Together is two adults, the 16-25 is one to eight, the
Student card is one.

*Amended 2 October 2026.* This originally read "is removed from the list", and
removal turned out to cost more than it bought. Two Together's bounds are 2 to
2 and the default page shows one adult, so it was the one card the selector
lost on every page a reader opened by default, and its absence read as "this
page does not price Two Together" rather than "not for the party you have on
screen". Every card the build prices is now listed, and one that cannot cover
the party on screen is struck out of choosing with the reason in its own label.

The guarantee this record was protecting is unchanged and, if anything,
tighter. Removal existed so the page would never show a price nobody could
buy, and a disabled `<option>` prevents that at least as strictly as removing
the option does: a disabled option cannot hold a value, so `priceOf` and
`cardFor` cannot read one. What removal also did, and was never asked to do,
was hide a card the feed prices.

**A card code this page does not price is ignored**, rather than read as a card
the reader holds. A link can arrive from a station whose feed carries a card this
one does not.

## What this rejected

**Shipping the sentences.** It is the honest division of labour in the other
direction, and it was measured at 2,598 bytes a row. Rejected on the byte budget,
not on taste.

**The build picking a default card.** "No railcard" is the only default that
cannot overstate what the page knows.

**A per-card party model.** The page's party control is one adult or two, which
is a product decision already taken (ADR-0019). What changed is that the party
rule is now evaluated per card against the feed's own bounds rather than hardcoded
to Two Together's two adults.

## Consequences

* The payload keys `hasTwoTogether`, `railcardInFeed`, `railcardEligibleCount`,
  `railcardAvailable` and `railcardParty` are gone, and a row's `railcardPence`
  and `railcard` are replaced by one `railcards` map. Both were read by the
  browser suite, which had to change with them.
* The synthetic feed's rules and minimum fare moved onto the reviewed code. They
  had hung off a code the project does not review, so the reviewed card matched
  no rule at all and the page never saw a card refused. It now refuses one fare,
  conditions the rest, and has a minimum that raises a third fare above its
  standard price, which is all three cases the page has to get right.
* The drawer names the card it is about. Six cards behind one drawer that said
  "the railcard" would answer a question nobody asked.
* Two browser checks record themselves as unexercised on the synthetic feed,
  which carries only the 16-25 and so cannot price a party of two. The real feed
  carries Two Together, and the checks name that in their reason.

## Follow-on

A card whose own record covers one adult but which in practice is also held by a
companion travelling at the standard fare is not modelled. The feed's own record
is what the page uses, and where the feed does not distinguish the cardholder
from the party the page does not either.

Verified by:

    python -m unittest tests.test_atoc_fares
    python -m unittest tests.test_build_demo_page
    npx --yes --package playwright node tests/browser_test.cjs _demo_site/index.html _demo_site/from/grantham/index.html