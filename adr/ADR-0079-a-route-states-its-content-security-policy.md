# ADR-0079: A route states its content security policy

**Status:** Accepted
**Date:** 28 October 2026
**Relates to:** ADR-0033 (one stylesheet inlined per route), ADR-0047 (the station route fetches one hashed stylesheet), ADR-0078 (an outbound link carries no referrer)

## Context

A built page loads nothing cross-origin. The station route fetches one hashed
script and one hashed stylesheet that the build wrote; the shared station list is
one more script from the same origin. Everything else the page runs is inline:
the theme switch in the head, the payload, and the first-paint styles that keep a
page from flashing unstyled.

That shape means the two things a policy could have prevented outright are not
available:

- A nonce or a hash would let `script-src` drop `'unsafe-inline'`, and it cannot
  be used here: the inline theme runs before any request could deliver a nonce,
  and ADR-0033 keeps the styles inlined for the same first-paint reason.
- `frame-ancestors` is ignored in a meta tag, so clickjacking is the host's
  header to send and this decision cannot cover it.

The 28 October 2026 audit found no injected script on the page -- every
feed-supplied string reaches markup through `html.escape` and the payload is
embedded with `</` escaped -- and recorded the missing policy as a gap worth
closing anyway (audit item 10).

## Decision

**Each of the three routes carries the same `Content-Security-Policy` in a meta
tag**, built once as `CSP` in `trainbudget/build/page_templates.py` and
interpolated into all three templates:

```
default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';
img-src 'self' data:; connect-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'
```

Three directives carry the weight:

- **`connect-src 'none'`** is the one that makes the policy worth having. A page
  that can fetch nothing cannot become an exfiltration channel for anything that
  reaches the DOM, and no part of this page needs to fetch: its list is in its
  own bytes.
- **`base-uri 'none'`** stops an injected `<base>` from re-pointing every
  relative address on the page, which is the cheapest way to turn markup into a
  redirect.
- **`object-src 'none'`** and **`form-action 'none'`** close the two remaining
  ways to leave the page. The routes have no form, no plugin, no frame and no
  `<base>` to lose -- `grep -n "<form\|<base\|<iframe\|<object\|<embed"` over
  `page_templates.py` matches one comment and no markup -- so the directives cost
  nothing today and refuse the markup that would.

## Evidence

- `tests/test_page_output.py::SharedStationAssetTest::test_every_page_states_what_it_may_load_and_reach`
  builds a whole site and holds every page to `CSP_META`, then holds the constant
  itself to the five directives that make it worth adding -- so a page cannot stop
  carrying the policy and the policy cannot quietly lose `connect-src` in the same
  commit.
- The browser suite runs every route in the accessibility matrix with the policy
  in place, which is what says the inline theme, the payload and the two fetched
  assets still run: `physically-visible-invalid` is not a check, a blank page is.

## Consequences

- `'unsafe-inline'` remains for both script and style. This is a limit, not an
  oversight: the policy here is a floor under an injection, not a solution that
  makes injection impossible, and the escape that matters (`html.escape` at every
  sink) is unchanged by it.
- **The page is not framed-proof and does not claim to be.** `frame-ancestors`
  belongs in a host header; the comment beside `CSP` says so, so a later reader
  does not read the meta tag as covering it.
- A route that ever needs a third-party asset -- an analytics snippet, a font --
  must state it here, and `tests/test_page_output.py` fails the moment a route
  ships without the policy. That is the intended friction: the policy is where
  the exception has to be argued rather than discovered in a console.

## 9 November 2026: the visit count opens `connect-src` and nothing else

The release counts visits with GoatCounter, hosted at
`trainbudgetexplorer.goatcounter.com`. GoatCounter's own CSP note asks for
`script-src https://gc.zgo.at` and `connect-src` to the count endpoint, because
the standard snippet loads `count.js` from `gc.zgo.at` and then calls
`navigator.sendBeacon`.

**`count.js` is vendored** (`page/goatcounter-count.js`, copied once to the
site root) **and `script-src` is unchanged.** Opening `script-src` to
`gc.zgo.at` would let that origin run any script on every page. The count is a
beacon, so the only new capability the page needs is to send it. The policy is
now:

```
default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';
img-src 'self' data:; connect-src https://trainbudgetexplorer.goatcounter.com/count;
form-action 'none'; base-uri 'none'; object-src 'none'
```

`img-src` stays closed. The vendored script falls back to an image when
`sendBeacon` returns false, which is how it recovers from a policy that blocks
the beacon. That fallback stays blocked: a refused count is a lost count. The
same policy is on every route, including a build that does not inject the
snippet, because the policy is one constant. An injection can beacon to that
one host and nowhere else, which is the exception this amendment is willing to
write down.

The privacy page names the counter only when the injected snippet is this one
(ADR-0032). `tests/test_page_output.py` holds the directives, including that
`gc.zgo.at` is not among them.
