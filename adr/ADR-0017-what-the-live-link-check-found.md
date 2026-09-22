# ADR-0017: What opening the ticket links on the live sites found

**Status:** Accepted
**Date:** 22 September 2026
**Relates to:** ADR-0014 (the links and what they carry), ADR-0016 (the seller and
the network, whose second precondition this set out to answer)

## Context

ADR-0016 made two things preconditions of publishing a tracked link: the licence
read, and the Trainline search URL verified against the live site. This ADR is the
second one being attempted, and it is written up because the check failed in a way
worth keeping: one link cannot be checked at all, and the other is the *default*
link, which does not work.

## What was checked

Both links exactly as `retailer.py` builds them, opened in a real browser. Only
the provider's own parameters were varied, and every variant is listed so the
negative result can be reproduced rather than taken on trust.

| National Rail variant opened | outcome |
|---|---|
| `?type=single&origin=GRN&destination=NOT&leavingType=departAfter&leavingDate=20261014` | no matching journeys |
| `?type=single&origin=GRN&destination=NOT&leavingType=departAfter&leavingDate=14/10/2026` | no matching journeys |
| `?origin=GRN&destination=NOT` | no matching journeys |
| `?type=single&origin=Grantham&destination=Nottingham&leavingType=departAfter&leavingDate=20261014` (names, not codes) | no matching journeys |
| `?type=single&origin=GRA&destination=NOT&leavingType=departAfter&leavingDate=2026-10-14&adults=1` | no matching journeys |
| `?type=single&origin=KGX&destination=EDB&leavingType=departAfter` | no matching journeys |

## Finding 1: the default provider's link does not search

Every variant reaches the same place: the results view renders — "Outward results,
step 1 of 2" — and then states *"Error: No matching journeys found. Please re-plan
your journey below."*

The date format is not the cause, because date-less links fail the same way.
Station codes are not the cause, because station names fail the same way. Grantham
is not the cause, because **King's Cross to Edinburgh** — a route with trains every
half hour — fails the same way. What fails is the mechanism: this planner does not
run a search from query parameters. It renders a results page, so the parameters
are being read, and then it searches for nothing.

This is worth stating plainly because ADR-0014 recorded the opposite. It said this
seller's URL "takes CRS station codes directly, which is exactly what this tool
holds". Both halves of that sentence are true about the **URL**, and neither makes
the **link** work. A reader who clicks the default link today is told there are no
journeys from Grantham to Nottingham, which is the worst outcome available: not a
dead link, a confident wrong answer.

**Confirmed without a browser.** `check_links.py` was written to catch this
without a person, and a plain HTTP request — no browser, no JavaScript, no session
— comes back with the same "No matching journeys found" in the page text. Two
independent paths agree: one driven like a person, one a bare request. That closes
the explanation that could not be ruled out by hand, because it is the one that
would have made this finding wrong. This is **not** the seller refusing an
automated visitor; that is what Trainline did, and it looks nothing like this. The
server is answering "no journeys" to the link the page builds.

## Finding 2: Trainline refused to be checked

The Trainline link opened and was answered with a bot check: the page rendered
"Access is temporarily restricted — we have checks to prevent misuse by automated
bots", `POST /api/journey-search/` returned **403**, and a DataDome captcha
interstitial loaded. The search never ran.

One signal came through before the block, and it is recorded as a hypothesis, not a
finding: the results page's own header read **Tue 22 Sept 2026** — today — while
the URL asked for 14 October. That is the exact failure ADR-0014 predicted for a
missing date ("the reader lands on today and the price they read is for another
day"), and it is consistent with `outwardDate` wanting a time component rather than
the bare ISO date this module sends. **No parameter was changed on this evidence.**
A block is not a result, and guessing a format to fix a link nobody has seen work
would be exactly the kind of tidy invention the rest of this project refuses.

## Finding 3: Grantham's station code is GRA, not GRN

Found while driving the planner's own form. Its station autocomplete offers
**"Grantham (GRA)"** and writes `GRA` into its hidden field, and the station's code
is GRA in public listings. The glossary asserted "such as GRN for Grantham", and
`GRN` is the code the synthetic feed invents for its invented Grantham.

So the two things were never the same, and no real feed will contain `GRN`. The
documented real-feed commands would have searched for a station that does not
exist and reported an empty budget honestly, which is the failure this project
keeps trying to make impossible. Corrected in the glossary, in the CLI help, and
in the README's real-feed commands; the synthetic commands keep `GRN`, because the
synthetic feed is where `GRN` lives.

## Decision

1. **A link check is recorded beside the parameters.** `Provider` gains a
   `verified` field, carried into `provider_table()`, and a test fails if a
   provider has no recorded check. "This page declares these parameters" and "this
   link was opened and worked" are different claims, and the code now holds both.
2. **No parameter is changed on this evidence.** Trainline's parameters were never
   exercised. National Rail's are wrong at a level no parameter edit reaches.
3. **Nothing is published and National Rail stays the default**, as ADR-0010 and
   ADR-0016 already required. The page remains local and tracking remains off, so
   the broken link has no reader to mislead yet.
4. **The repo stops claiming the links work**, in the glossary, the CLI help, the
   comments in `retailer.py`, and the README's real-feed commands.
5. **The check is a tool rather than a hand ritual.** `check_links.py` builds the
   link the page would build, opens it once, and reports what the response proves:
   `no_journeys`, `http_error`, `blocked`, or `inconclusive`. It has no verdict that
   means "works", because it has never seen a working seller page and a marker
   invented for one would make it lie in the direction that matters. It exits
   non-zero on a proven failure, so a future check can gate on it.
6. **The fallback link is built, not applied.** `--link-mode fallback` sends the
   reader to the seller's own search page with no parameters, and it stays off
   until someone reads the two sections above and chooses it.

## Consequences

- **The page has a launch blocker that is not the licence.** Even with the licence
  read and cleared, a reader clicking the default link is told there are no
  journeys from Grantham. That is now the second thing standing between this build
  and a public page, and the cheaper of the two to close.
- **What would close it is now a flag, not a rewrite.** Either someone finds the
  URL shape that does drive the search, or the page switches to
  `--link-mode fallback` and sends the reader to the planner to fill in — a worse
  link that works, rather than a good link that lies. For the default seller the
  evidence is already enough to act on; what is left is deciding, and that belongs
  with the seller decision rather than being made here.
- **The hand-check that is still owed is Trainline's.** A refusal leaves everything
  unproven, including the date-format hypothesis, and no amount of tooling on this
  side can open a page that declines to be opened. One minute in a normal browser
  settles both ADR-0016's second precondition and this one.
- **Both of ADR-0016's preconditions are still open**, so the seller and network it
  records remain a target rather than a plan: the licence is unread, and the URL
  cannot be verified from here because the seller refuses automated visitors. The
  owner can check the Trainline link in the time it takes to click it.
- **The Trainline date format is the leading hypothesis** for why that link's date
  may not be honoured, and it is testable in one browser session. It is written
  down so the next session tests it instead of rediscovering the 403.
- A real feed now has a documented code for its origin station, so the first run
  after the account clears does not spend an afternoon on a station code.
