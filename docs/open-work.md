# Open work

**Opened:** 1 October 2026
**Scope:** every item the project's own audits left open, in one place, so that
nothing is open only because it lives in a file nobody has re-read.

This file replaces three audit documents that sat in `docs/audits/`. Two of them
are closed — every finding in each is fixed, and the record of the fix is the
ADR that carries it, not a restatement here. One had a single open finding. What
is left is what is below, and the closed work is listed at the foot so that a
reader looking for "was this ever looked at" finds the answer without reading
three files of prose first.

An item leaves this file when it is done, and it leaves by naming the commit and
the test that hold it, or by naming the ADR where it was a decision rather than a
fix. Nothing leaves on the strength of having been discussed.

---

## The one open finding

### C27 — the chooser requires a known station name or a code prefix

**Severity:** P2. **Route:** the full-build root chooser.
**Raised:** 27 September 2026, re-verified the same day, still open.

**Evidence.** Matching is by name substring or three-letter code prefix, and the
first forty matches are ranked by how many destinations the download prices from
that station. `PRODUCT.md` records correctly that the fares location records
carry no coordinates and no region. The chooser now says what its order is and
is not — "Ordered by how many destinations this download prices from each
station — not by how busy it is, and not by how near it is" — and a no-match
names the three-letter code route, so a reader is no longer left guessing what a
code is for.

**Why it is still open.** The limitation is now stated on the page; the
capability gap is unchanged. A traveller who knows the town they live in but not
the official station name or its code still has no natural way to choose an
origin, and a high destination count is not a "near me" signal.

**What it is not.** "Nearest station" is not derivable from this feed, and no
amount of work on the chooser will produce it. An earlier attempt to derive a
geography from the fares location records was the wrong answer to a real
question.

**What would close it.** An opt-in geographic lookup backed by a **named,
reviewed** station-coordinate source, with manual search kept as the default and
the location permission explained in full before it is asked for — and a source
whose licence and provenance are recorded alongside the station index. That is a
decision with a data question inside it, which is why it is here and not in the
code.

---

## Suggestions not yet taken up

From the re-envision pass of 27 September 2026. Each carries the benefit it was
argued for, because a suggestion without one is a wish.

### Needs a data source or a licence answer

| | Suggestion | What it is for |
|---|---|---|
| **S08** | An opt-in "find my station" path, backed by a reviewed coordinate source, keeping manual name/code search as the default and explaining exactly what the permission does before asking | A traveller who knows their town but not the station's CRS code can still start, without silently collecting location data |
| **S09** | Region, town or rail-network grouping, once a trustworthy geography source is chosen, with that source's provenance and coverage kept beside the station index | The origin directory stays navigable when a reader cannot use nearest-station lookup or cannot spell the station |
| **S24** | Date-specific schedules as an explicit product mode: build or select a timetable snapshot for the named date, label its service date beside the times, and keep undated aggregate schedules visibly indicative | A journey time is tied to the day the reader cares about rather than to a mixed schedule set |
| **S25** | Calendar handling, but only where the source supports it: bank holidays and service exceptions as first-class inputs, with a clear fallback where they are not | Fewer "typical" schedules are mistaken for holiday-specific service |
| **S27** | A few evidence-backed discovery entry points — "cities under £20", "seaside under £20" — generated only from currently priceable destinations | A reader with a broad idea and no exact town gets a useful first click without editorial claims about popularity |
| **S31** | Deep links verified per seller, date and party before they are enabled, with a working fallback and the destination's link mode stated; never infer success from a URL that merely has query parameters | The handoff is the shortest one known to work, rather than the shortest one that looks right |

### Needs a product decision, not a source

| | Suggestion | What it is for |
|---|---|---|
| **S35** | Provenance and approximation as compact confidence signals: distinguish a reviewed fare, a conditional fare, missing service data, classification coverage and seller-link confidence, without inventing a numeric score | A reader can assess the exact uncertainty instead of reading one generic disclaimer as applying to every row equally |
| **S40** | Decide the public name before designing any identity assets; until then do not present "Rail Budget" as a settled brand | The site looks authored without committing to an unapproved name or to generic SaaS decoration |

### Needs people, not code

| | Suggestion | What it is for |
|---|---|---|
| **S43** | Short, task-focused sessions with the intended traveller: someone with a price ceiling and no destination has to find a usable day out, then explain the fare and time they chose | The next changes address real interpretation failures rather than adding features because they are technically possible |
| **S44** | Instrument the existing tripwire before investing in a redesign — venue-level visits, comments and return signal only under an approved privacy approach | Effort stays bounded by the experiment, and a polished interface is not mistaken for demonstrated demand |
| **S46** | Lightweight task telemetry without personal tracking, and only if it is necessary and permitted: a static "Was this shortlist useful?" or an optional feedback route | Qualitative signal without recording a reader's budget or filter state, and without turning a static experiment into a tracking product |

---

## Questions a future design pass still has to answer

1. **Is the release meant to expose the whole station network now, or
   intentionally just Grantham?** The route contract no longer depends on the
   answer — the deployment publishes a one-station chooser whose contract is the
   same as a full build's, every internal link resolves, and the release
   manifest is proved against the files on disk. What is open is the *coverage*
   decision: a one-station release is coherent, but a reader arriving at a "where
   can we go from anywhere" product meets exactly one origin. This is the only
   question in the 27 September critique that its own re-verification could not
   close, and it is a decision rather than a defect.
2. **Is the Two Together enforcement the answer the brief wanted?** The solo case
   is now refused rather than shown, which the enforcement test holds. Whether
   the brief wanted that, or wanted an explicitly conditional per-person
   comparison instead, was never put to it.
3. **Does the local preview keep its own build step, or does the runner become a
   server for a folder the builder produces?** The concrete cost of the split has
   been fixed, so the question is open again rather than answered by a defect:
   the runner still shells out to the builder, which works, and no finding says
   it should not.

---

## Settled in this pass, and where the record is

Every item below is closed. None of it is restated here beyond the pointer,
because a reader checking a closure wants the ADR and the test.

| Item | Closed by | Held by |
|---|---|---|
| S17's first half — one inclusive "up to £X" resolver feeding the heading, the control, the count line and the URL | ADR-0019, in place before this pass | the budget contract tests in `tests/test_build_demo_page.py` |
| S16 — the list is ordered by the price on screen | no code change needed; `render()` already sorted by `priceOf()` | the railcard reading in `tests/browser_test.cjs`, added and recorded as a guard rather than a gate — see ADR-0048 |
| S17's second half — the page says where the budget stops, and the figure is the stop | ADR-0048 | `test_the_page_says_where_the_slider_stops_and_the_figure_is_the_stop`, the tamper that hardcoded £500.00, and the browser suite's two readings |
| S34 — a human-readable feed-change report for the operator | ADR-0049 | `tools/test_feed_change_report.py` |
| C27's sibling findings, C01–C31 | five passes, 27–28 September 2026 | the commits that carried each change; the finding ids that survive as reasons in the code (`C14` in `SHARED_CSS`) |

### The measurements three ADRs lean on

ADR-0040, ADR-0041 and ADR-0043 were settled from a rendered-page audit of the
published Grantham page on 29 September 2026. Their evidence is kept here rather
than in a file that would otherwise have been deleted, because an ADR that cites
a measurement needs the measurement to still exist.

**Finding 1 — the price column was 56px wide, so the price wrapped** (settled by
ADR-0040 §1). Seven columns measured station 176px, price 56px, time 62px,
changes 72px, fare 225px, conditions 234px, tickets 352px. Thirteen of the first
twenty prices painted as two lines: `£10.10` rendered as `£10.1` over `0`, and
the same for £12.60, £13.30, £13.70, £14.10, £14.40, £14.70 and £15.40.
`CHANGES` wrapped mid-word in its 72px column. Nothing in `SHARED_CSS` refused a
wrap on `th` or on `td.num`, so each column took its width from the widest thing
in it that could not break — and for a two-word header that is the header.

| Tamper | Check result |
|---|---|
| price column forced to 56px, `white-space: normal`, CHANGES-only | **FAIL** — `{"text":"Changes","lines":2,"width":56}` |
| price column forced to 40px, same | **FAIL** — `£8.70` in 2 lines, `50m` in 2 lines, `CHANGES` in 3 |
| as shipped | **ok** — 18 cells measured, price column 78–81px |

**Finding 2 — forty cells restated the mode the reader had already chosen**
(settled by ADR-0040 §2). All twenty rows read `Unrestricted Anytime Day Return`
in FARE and `No travel conditions on this fare in the feed.` in CONDITIONS — two
sentences about the *mode*, printed twenty times. Each row measured 81px, of
which those two columns were the greater part; twenty rows occupied 1620px,
about two laptop screens. With the fare's own code and a differing-condition
word in their place, rows measure **49px** and twenty occupy 980px. The
condition stayed reachable one disclosure away, so C07's pointer survives with
its wording made true.

**Finding 3 — the count line was 205px from its table** (settled by ADR-0040 §3).
At 1440×900 the count line sat at y=654 and the table began at y=859, with six
paragraphs between them, and the first fare began at y=914 — fourteen pixels
below a 900px laptop's fold. At 390×844 the same block measured 455px. After the
change: **8px**, nothing between them; the first fare at y=867, thirty-three
pixels above the fold; no sideways scroll at 321/705/760/1024/1280/1440px.

**Finding 4 — five controls on every row** (settled by ADR-0043). The Tickets
cell carried `Tickets`, `5 times`, `Card details`, `Copy` and `Shortlist` — a
hundred pointer targets on page one, inside one cell 352px wide at 1440px and
240px at 705px. Recorded rather than fixed at the time, because the decision
changes what the row promises at a glance; ADR-0043 is that decision.

**Finding 5 — the cheapest row was tinted with no legend** (settled by ADR-0041).
`tr.best` set a background wash on the cheapest row and nothing on the page said
so, on a page that names no "best", no "recommended" and no star. Recorded
rather than fixed at the time, because the tint was also the only visual
grouping of the sort order; ADR-0041 is that decision, and the order is now
stated in words in the count line instead.

**Not a design fix.** The deploy workflow publishes a single origin
(`--origin GRA`), so the published artefact has one station page, no Change
chevron in the heading and only Privacy in the footer. That is a coverage fact
about the release command — see question 1 above — and it is measured so the
next reader does not file it as a defect.

---

## Where this came from

- `docs/audits/2026-09-27-impeccable-critique.md` — the public route audit.
  Thirty-one findings, thirty closed across five passes, C27 open.
- `docs/audits/2026-09-27-reenvision.md` — the re-envision pass. Thirty of its
  suggestions built; the rest are above, with the three this pass closed marked
  in the settled table.
- `docs/audits/2026-09-29-real-grantham-page.md` — the rendered-page audit of
  the published Grantham page. Five findings, all settled; its measurements are
  above because three ADRs cite them.
- `docs/audits/2026-09-29-promise-gap-audit.md` — filed away in `d33b762` after
  the gap it found was closed, and deliberately not reopened here.
