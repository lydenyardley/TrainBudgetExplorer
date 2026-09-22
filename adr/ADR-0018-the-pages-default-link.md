# ADR-0018: The page's default link is the seller's own search page

**Status:** Accepted
**Date:** 22 September 2026
**Relates to:** ADR-0014 (what a link carries), ADR-0016 (the seller and the
network), ADR-0017 (what the live check found), ADR-0010 (the page stays local)

## Context

ADR-0014 built the ticket link to send the reader's own search — origin,
destination, date, party size — on the reasoning that a reader who lands on today
instead of their date "reads a price for another day". That reasoning has not
changed. What changed is that the link does not work: ADR-0017 found the default
seller's parameterised link answers *"No matching journeys found"* for every route
tried, from a browser and from a bare HTTP request.

So the page has to send something, and the choice is between a link that carries
the search and a link that carries nothing. The question this ADR answers is which
of those a reader gets without asking.

## Decision

**The page's default is the seller's own search page** — `--link-mode fallback` in
`build_demo_page.py`. Opting in to `--link-mode deep` is a statement that somebody
has opened that link and seen a search, and it is the only thing that authorises
it. Nothing detects a working URL; a person does.

**`ticket_link` keeps `deep` as its own default, deliberately.** It is a builder
whose arguments *are* the search, and a builder that silently discards the origin
and destination it was handed is a worse tool than one whose caller decides. The
page is where a reader's experience is decided, so the page is where the default
changed. The function's docstring says so, because otherwise the two defaults look
like an oversight rather than a decision.

## What it costs the reader

Written out, because a fallback whose cost is only discovered on someone else's
site is worse than no fallback at all.

1. **The journey is not carried.** The reader types the origin, the destination,
   the date, and how many are travelling. Four fields, about ten seconds.
2. **The page stops being able to say "this is the search you were reading".** It
   says what the link actually is instead.
3. **The link becomes the same for every row.** This is the real loss. A
   per-destination link was doing a small piece of remembering on the reader's
   behalf; now the reader carries the destination across themselves, and a reader
   who clicks the wrong row lands somewhere wrong with no signal that they did.
   (Partly answered the same day, without a working URL — see the addendum.)
4. **What does not change: the price.** The fare is the railway's own walk-up
   fare, valid at any seller, so the reader is not being sent to a different
   number. This is the reason the fallback is acceptable at all rather than merely
   honest, and it is stated on the page.
5. **Monetisation is unaffected.** Tracking is a redirect wrapper around a
   finished URL (ADR-0014), so the tracked variant wraps the fallback just as
   happily and the disclosure still applies.

## Why not the deep link with a warning beside it

Because a warning the reader is meant to read before clicking is not a fix for a
link that lies. The failure here is not mild inconvenience — it is a reader being
told there are no trains from Grantham to Nottingham, concluding the tool is
broken, and leaving. A disclosure cannot repair that, and the reader's trust is the
thing this project is actually building.

## Consequences

- **The page is less useful and more honest, and it says which.** The loss is
  printed on the page rather than discovered.
- **This sidesteps ADR-0016's precondition rather than closing it.** The licence is
  still unread and Trainline's link is still unverified. What changed is that
  neither is now a reason a reader can be misled, so the remaining blockers are
  about permission rather than about accuracy.
- **Both sellers get the fallback, which is correct:** Trainline's link was never
  verified either, so opting into `deep` for it would be opting into an unverified
  URL. A verified URL at one seller makes `deep` defensible for that seller alone,
  and the check is recorded per provider for exactly that reason.
- **Switching back is a flag, and switching back quietly is not possible.** The
  test that fails when the default moves is the one asserting that the default is
  the seller's own page, so this decision cannot be undone by an unnoticed edit.
- **`check_links.py` keeps `deep` as its default**, because checking the
  parameterised link is the point of the check. Its help text says so, so that the
  two defaults read as intentional.
- **ADR-0014's per-row link weakens into a per-page link.** Its argument that
  buying is the action still holds and the link still sits on the row, but the row
  no longer carries *which* search. That is the price of the fallback, and it is
  the first thing a working URL would buy back.

## Addendum, the same day: the memory, restored by hand

Item 3 above is the cost that matters, and it has been reduced without a working
URL. Every row now carries a **Copy** control that puts the four things a seller
asks for on the reader's clipboard:

```
From: GRANTHAM (GRN)
To: NOTTINGHAM (NOT)
Date: 27 September 2026
Passengers: 1 adult
```

Three decisions inside that, each consistent with what is already recorded here:

- **The railcard is named as something to tick, and only when the party price is
  the one on screen.** Nothing is sent anywhere, so ADR-0014's rule holds, and the
  reader who was shown the railcard price is exactly the reader who needs the
  reminder. The party size follows the price on screen rather than the party size
  configured for the link.
- **The date is formatted from the ISO string by hand, not through `Date`.**
  `new Date("2026-10-05")` is parsed as UTC midnight and prints as the 4th for any
  reader behind UTC, and a copied date that is off by a day is worse than no date.
- **A refused clipboard is reported as refused.** Clipboard access is withheld
  when the page is opened from a file rather than served, so the text is shown
  under the row and the button says so — the page never claims a copy that did not
  happen, which is the same rule as the link itself.

What it does **not** fix: the link is still identical on every row, so a reader who
clicks the wrong row is still sent somewhere wrong. Copying removes the retyping; it
does not do the remembering. That remains ADR-0014's per-row link to buy back.
