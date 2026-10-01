# Name ideas

**Date:** 1 October 2026
**Answers:** S40 in `docs/open-work.md`, which asked for the public name to be
decided before any identity assets are designed, and for help deciding it.

## The brief the name has to meet

The name is not decoration here. It is the first claim the site makes about
itself, and three things about it are load-bearing:

1. **It must say what the tool is.** Someone seeing the name in a community post
   has to know it is about rail fares before they click. A name that could be a
   bank, a game or a timetable app costs the click.
2. **It must not promise what the page cannot deliver.** The site's own rule is
   that nothing on a page claims more than the evidence behind it. A name that
   says *cheapest*, *best* or *smart* is a recommendation the page deliberately
   refuses to make anywhere.
3. **It must not be another rail company's word.** "Rail Budget" currently
   appears nowhere in the code as a settled brand, and that is deliberate.
   It reads as the name of a product a national operator might launch. The site is
   unaffiliated, and the name should not create doubt about that.

Two things the name is **not** for, which is worth saying before any list:

- It is not a claim about coverage. The site publishes 2,718 stations now, but a
  name like "Every Station" would be a promise the next feed could break.
- It is not a mechanism name. Nobody reads "destination graph" and thinks of a
  day out.

## Shortlist

These are deliberately plain. The page's whole voice is plain sentences and
exact numbers, and a clever name sets a different expectation.

### Strong

| Name | Why it fits | What to check |
|---|---|---|
| **Farefield** | Puts the two things the site is about, a fare and a field of choices, in one word. Reads as a place rather than a tool, which suits a site whose output is a list of places. | A quick search for existing use. "Farefield" is also a place-name shape, which may read as a single station rather than a network. |
| **What's the Fare** | A question, so it invites a reader who has exactly that question. Matches the page's opening sentence shape. | Too long for a tab title and for a card in a community post without context. |
| **Up To** | The product's own inclusive budget wording, lifted from the page's four places that say it. A name that cannot be misread as "under". | Abstract on its own. Needs the descriptor everywhere it appears. |
| **Platform Fare** | "Platform" is a rail word without being a company word, and "fare" says what the number is. | "Platform" is crowded in UK software naming. |

### Usable, with a caveat

| Name | Why it fits | The caveat |
|---|---|---|
| **Pencewise** | British, exact, and about money rather than sentiment. | Reads as a budgeting app, which is a different and larger category. |
| **Rail & Fare** | Almost impossible to mistake for an operator. | Bland, and the ampersand is a nuisance in a domain name and a URL. |
| **Outbound** | A rail word, one syllable, and it points away from the origin, which is what the page is for. | Very common name. Also reads as marketing for a travel product. |
| **The 20** | Concrete, memorable, and it names the budget-first idea. | Ties the product to one number that the reader changes on every page. |

### I'd avoid

- Anything with **Smart**, **Auto**, **AI** or **Compare**: it claims a mechanism
  and a quality judgement. The page's whole editorial position is that it does
  not rank.
- Anything with **Cheapest**, **Best**, **Deals** or **Savings**: a
  recommendation. The page sorts cheapest-first and says so in words, and the
  tint that implied a winner was removed for exactly this reason
  ([ADR-0041](../adr/ADR-0041-no-row-is-tinted-as-the-best-fare.md)).
- **Rail Budget** as a settled brand. It reads as an NRE product line. Fine as a
  working description, wrong as a name.
- A person's name. Nothing on this page is attributable to a person, and a name
  that implies one is a claim the site cannot support.

## The test I would apply

Say the name out loud in the sentence a community post would use:

> *I built [NAME]. You give it a budget and a station and it tells you where you
> can get to for that.*

If the sentence reads as something the page actually does, the name works. If it
needs a second sentence to explain, the name is wrong and the descriptor is
carrying it, which means it should be replaced by a better name plus the same
descriptor.

Three of the four strong candidates survive that sentence unchanged.

## What is still undecided

- **The owner picks one.** This file does not choose for them, and nothing in
  the code, the pages or the metadata changes until they do.
- **Domain and handle availability** for every candidate is unchecked. That is a
  lookup, not a judgement, and it should happen before the shortlist is narrowed.
- **Whether a descriptor is needed** at all. "Farefield" and "Pencewise" work
  bare; "Up To" does not.

Once one is chosen, the remaining work is small and separate. It is the page title, the
privacy page's own name, the footer credit, and any identity asset. S40's second
half, which was to avoid designing assets before the name exists, is the reason
that order matters.
