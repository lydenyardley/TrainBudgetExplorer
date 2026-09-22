# ADR-0014: Ticket links, what they carry, and where they sit on the page

**Status:** Accepted
**Date:** 21 September 2026
**Relates to:** ADR-0001 (licences), ADR-0003 (monetisation), ADR-0010 (the page
stays local), ADR-0013 (reading the count)

## Context

The owner asked for a link from each destination to a page where the tickets can
be bought, and asked three questions: which seller, what the link carries, and
whether the journeys belong in an expander on the row or on a page of their own.

ADR-0010 said the generated page carries **no affiliate links** until the
licence text for commercial use is read. This ADR does not overturn that. It
builds the link, and makes monetisation a switch that is off by default.

## Which seller, and the commission question

The honest answer to "best affiliate commissions" is that **the headline rate is
not publicly verifiable**, and the figures in circulation cannot all be true:

| source | claim |
|---|---|
| Trainline's own partnerships page | commission follows "Partnerize network rates and terms", no number given |
| Awin merchant listing | TransPennine Express, 4% on advance purchase tickets |
| two affiliate directories | 3% per sale, and separately 20% per sale, for Trainline |

A 3% and a 20% figure for the same programme means at least one is marketing.
The rate is set inside the network and is visible only after joining it.

**Decision.** Choose on coverage and link fidelity, not on a rate. Two sellers
are built:

- **National Rail's journey planner is the default.** It is the industry's own
  and its URL takes CRS station codes directly, which is exactly what this tool
  holds. Whether an affiliate programme runs on it is unverified, and the module
  says so rather than claiming one.
- **Trainline is available behind a flag.** It is the largest retailer and the
  one whose programme is best documented, but its URL parameters are unverified
  against the live site, so it is not the default.

The provider is a configuration value with a declared parameter list, so adding
or changing a seller is a data edit with tests, not a rewrite.

## What the link carries

| sent | why |
|---|---|
| origin code, destination code | the search the reader was already reading |
| the date, when the page was built with one | otherwise the reader lands on today and the price they read is for another day |
| number of adults | so the party size matches the party price on the page |

| not sent | why |
|---|---|
| **railcard** | no seller documents a parameter for it, and a wrong railcard silently changes the price the reader sees, which is worse than no prefill. The page says "tick the railcard box on their site" instead. |
| **a departure or a train** | the fare this tool reports is an Anytime or Off-Peak walk-up fare that exists on every train that day. Choosing one for the reader would turn a price list into a booking suggestion the data cannot support. |
| anything about the traveller | there is nothing of the sort to send, and no reason to start |

A provider is never sent a parameter its URL does not declare, which is what
stops an unsupported parameter reaching a search page and emptying it.

## Where the link sits

**Decision: one ticket link on every row, and the journeys behind an expander on
the same row.**

- Buying is the action. Putting the link behind a click loses the click for no
  gain, so the row carries it directly.
- The expander answers the question the price raises next — *is this actually a
  day out?* — without navigating away, so the budget slider and the comparison
  survive. That is the whole value of the page: a reader at £20 wants to know
  they can reach three places, not to lose that context on the first click.
- The content is generated at build time and revealed with a few lines of
  script, so there is no server and no request per row.

Rejected: **a click-through page per destination.** It would be better for
search — one page per town, in the pattern these tools grow with — but it is
precisely the indexed, published artefact that ADR-0010 keeps behind the licence
gate, and 139 thin pages per origin is as much an SEO liability as an asset. The
expander delivers the same information inside the page that already exists.

## Consequences

- Affiliate tracking is implemented as a redirect wrapper (Awin's `cread.php`,
  Partnerize's `prf.hn/click`) rather than a tracking parameter, so turning it on
  cannot change where a reader lands, and a test asserts the wrapped link lands on
  the same URL as the plain one.
- Tracked links carry `rel="nofollow sponsored"` and a visible disclosure above
  the click, because a commercial link that does not say so breaks both UK
  advertising rules and the reader's trust.
- A seller linked through a network that does not run its programme is warned
  about at build time: that mistake produces a working link that earns nothing.
- The page's journeys are read through the same date rules as everything else, so
  without a date a train whose plan has changed appears twice. The page says so
  in the footer rather than hiding it.
- **Unchanged:** the page stays local, and the tracked variant must not be
  published before the licence text in ADR-0001 is read. The switch exists so that
  decision stays with the owner rather than being made by a default.
- **Open:** the real rate. The production seller and the network are recorded in
  `adr/ADR-0016-publishing-seller-and-network.md` as a decision that does not
  take effect until the licence is read; the rate still needs an application
  made, and that stays open.
