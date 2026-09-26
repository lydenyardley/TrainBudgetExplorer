# ADR-0029: A reviewed fallback must be a fallback

**Status:** Accepted
**Date:** 26 September 2026
**Relates to:** ADR-0026 (the destination facet registry and the reviewed lists
behind it), ADR-0028 (reviewed lists, the dead-code gate and the proposer)

## Context

`atoc_fares.py` holds three reviewed lists: `LONDON_STATION_CRS`,
`MAJOR_UK_STATION_FALLBACKS` and `REVIEWED_SETTLEMENT_FALLBACKS`. Every entry
is a judgement about one station's settlement class, keyed by the feed's own
CRS. They exist for the stations no source can name: London station names do
not match the ONS workbook's rows, the workbook stops at the Scottish border,
and its coverage is a built-up-area table rather than a gazetteer.

ADR-0028 made these lists reviewed and added a gate for the failure mode that
was easy to see — a code that names no station in the feed, which
`--require-live-reviewed-codes` refuses. **The failure mode that was not easy
to see is the opposite one: a code that names a real station and is filed
under the wrong class.** The code resolves, the page builds, the gate is
silent, and a reader is offered a "city" filter that contains a village.

`PER` is the worked example. The feed's `PER` is Penrhwceiber, a village in the
Rhondda; the list filed it as a city. Nothing in the build could see it.

## The measurement

Every entry in all three lists was measured against the feed's own station name
and the ONS workbook's band for that settlement, on the 24 September 2026
download. 326 entries:

- **11 were inert and contradicting.** The workbook names the station, so the
  reviewed class never applies — and would apply the moment a name match
  missed, which is exactly what a fallback is for. Ascot, Battle, Knighton,
  Windermere, Wickford, Welshpool, Brockenhurst, Bramhall, Bangor, Truro, York.
  Eleven latent wrong answers, of which York was the worst: the workbook says
  city, the list said town.
- **6 were inert and agreeing.** Harmless, and removed anyway for the same
  reason: an entry that covers nothing is still a claim about a station someone
  else classified.
- **309 were live** — no ONS row, so the reviewed class is the answer. These are
  the entries the lists are for. Of those, twelve were filed under a class the
  settlement does not have.

After the corrections and the removals: **308 live, 0 inert.**

## Decision

**A reviewed entry covers a station no source could name. An entry that
duplicates a source is a defect, and it is checked against the source rather
than left to a reader to notice.**

`_load_ons_location_types` records every CRS the workbook names, in
`FaresDb.ons_classified_crs`, which is the only way to tell a *fallback* from an
entry that can never apply. `_apply_major_station_fallbacks` reports the
difference as `ParseReport.reviewed_codes_redundant`, once per parse, in its own
channel beside the dead codes. `feed_audit.py` prints it and
`build_demo_page.py --require-live-reviewed-codes` refuses on it exactly as it
refuses on a dead code: a build must not publish with a reviewed list that
either names nothing or covers something.

Measured after the corrections: **0 dead, 0 redundant, 308 live.**

### What was corrected, and how the intent was recovered

The code was trusted and the class was not, in every case, because the code is
the feed's own identity and a wrong code is a dead code the gate would have
named. The class was recovered from the settlement the feed's station name
denotes, against the ONS bands:

| Code | Station in the feed | Was | Now |
|---|---|---|---|
| `PER` | Penrhwceiber | city | village |
| `HGY` | Harringay | city | village |
| `LDY` | Ladybank | city | village |
| `BNV` | Banavie | city | village |
| `BHC` | Balloch Central | city | village |
| `BHD` | Brithdir | city | village |
| `WRE` | Wrenbury | city | village |
| `CBR` | Cooksbridge | city (London list) | village |
| `CHT` | Chathill | city (London list) | village |
| `TUL` | Tulloch | city (London list) | village |
| `CDD` | Cardenden | city | town |
| `HUL` | Hull | town | city |

`CBR`, `CHT` and `TUL` were in the London list, where they could not be: they
are a hamlet in East Sussex, a village in Northumberland and a Highland village.
Cooksbridge and Chathill were the only two non-London codes in that list, which
is what made the list worth auditing at all.

### What was kept, and why

**A station inside a conurbation takes the class of the settlement it belongs
to.** `BMG` is Barming, three miles from Maidstone; `WKF` is Wakefield
Westgate, not Wakefield; `STP` is St Pancras, not London. They are kept as the
conurbation's class for the same reason the London list exists: a station's own
name is a local name and the reader is filtering on where the train goes. That
is a judgement, so it is written down here rather than left to be re-derived.
Maidstone and Wakefield are both towns and cities respectively, so the rule
gives Barming a `town` and Wakefield Westgate a `city` — which is what the
entries now say, having both said the other thing.

`LAR` (Largs) sits within ten people of the town/small-town boundary and is left
as the Scottish `town` it has always been. `LBN`, `NWY` and `PTN` are `town`.
Scotland and Northern Ireland have no equivalent of the ONS built-up-area bands
— the workbook's coverage was checked and it stops at the border — so these
remain reviewed, per ADR-0026.

## The second pass: the list had been grouped by a claim that was not true

A review of the corrections above found that the list's comment groups had
drifted from their contents, and that the drift had been hiding errors of
exactly the kind this ADR is about:

- The **Northern Ireland** group held `LAR` (Largs, in Scotland), `BCH`
  (Birchington, in Kent), `BHD` (Britwhir) and `WRE` (Wrenbury). Birchington had
  acquired a `town` class it is not — a village on the Isle of Thanet. A group
  is a claim about where an entry comes from, and a wrong group hides a wrong
  class: nobody reading a Northern Ireland list looks for a Kentish village in
  it.
- The **Scotland** group held `HUL` (Hull) and `MAN` (Manchester Piccadilly).
- The **Cardiff** group held `FER`, filed as a `city`. Fernhill is a village in
  the Scottish Borders.
- The **small towns** group held `PPL` as a small town; the workbook puts
  Pontypool in a medium band. `BCJ` (Burscough Junction) was a village where the
  workbook says small town. `RMC` (Rotherham Central) was a `city` because it
  sat beside Sheffield in a comment naming Sheffield; Rotherham is a town.
  `NLW` (Newton-le-Willows) was a village. `SIA` (Southend Airport) was a
  `city`; Southend-on-Sea is a town.

All seven are corrected. The groups are now organised by what they are, and the
`LOCATION_CACHE_SCHEMA` moved to 5, because the cache holds the final
classification and a machine holding a schema-4 cache would have kept serving
the classes corrected here for ever.

## What the gate cannot see, and the tool that can

The hard gate compares a reviewed code against the stations the workbook
*names*. It cannot see a station the workbook names under a spelling the lookup
misses: the feed writes `NEWTON LE WILL` and the workbook writes
`Newton-le-Willows`, so the reader misses and the reviewed entry applies. That
is the exact scenario the ADR above describes — the entry applying the day the
match missed — and on this feed **45 of the 306 entries** were in that
position, eight of them disagreeing with the band the workbook would have given.

Prefix matching is the obvious fix and it is unsound: `BATHGATE` is not Bath,
`BRADFORD` is not Bradford-on-Avon, and the existing reader deliberately
matches whole names only. So the near-miss search is **not** wired into the
parser. It is `tools/propose_reviewed_settlements.py`, which prints the feed's
own name for every reviewed code, the reviewed class, and what the workbook
says, split into *to delete*, *to decide* and *in agreement*. It writes nothing,
for the reason every proposal in this project writes nothing.

On the 24 September 2026 download it reports **0 to delete, 4 to decide, 302 in
agreement**. The four are left for a person, and each is a case where the tool is
wrong rather than the list: `BDY` (Bredbury) is a village but the workbook's
built-up area is *Bredbury and Woodley*, two villages; `RDF` (Radcliffe-on-
Trent) and `RMD` (Richmond) match same-named settlements in other counties;
`SIA` (Southend Airport) is a town the built-up-area table does not carry under
that name. The tool's own bounds are tested, because a tool that flags
everything is a tool nobody reads: a shared prefix of at least eight characters,
an extension of at most twelve, and a row settles as agreement as soon as one
plausible reading agrees.

## Two bugs the measurement found

**A cache that discarded its own classes still claimed to have supplied them.**
Bumping `LOCATION_CACHE_SCHEMA` to 4 drops the primary classes from an older
cache and says so. It did not drop the cache's `source` label, which then told
the classification pass that the ONS workbook had already been applied, so the
pass returned without reading it and every station the cache had classified
fell through to the reviewed fallbacks. On the 24 September 2026 download that
was **3,119 of 3,436 stations** losing their class in a build whose whole point
was to fix classes. The loader now clears the label, and because the loader
reads the label back out of the same discarded data, the pass clears it again
on the flag — for the candidate that discarded, and only for that one. A flag
that is consulted for every later candidate erases the label of a file that had
just classified the feed properly, which leaves the build claiming no source at
all, or claiming the reviewed fallbacks did the work a source did.

**The writer named its own schema as a literal.** `_write_location_cache`
wrote `"schema": 3` while the reader had moved to 4, so every build wrote a
cache the next build was required to discard and re-derive from the workbook:
a cache that never once did its job, and a discard note on every run. It is now
`LOCATION_CACHE_SCHEMA`, and a test writes a cache and reads it back, which is
the only check that catches a constant copied into two places.

## The gate that could pass without checking anything

The commit-message checker was in no hook and no workflow, which is how a tool
could reject all 87 commits in the repository without anyone noticing. The step
added to `deploy.yml` walks the commits a push adds — and its first version had
the same defect one layer down. A force-push drops the old tip from the remote,
so a full-history checkout does not have the base commit, `git rev-list` fails,
the loop iterates nothing, and the step **reports success having checked no
commit at all**. A gate that evaluates nothing must not report success, so the
step now refuses when the base commit is unresolvable, refuses when the range is
empty, and prints how many messages it actually checked.

## The commit convention was checked by a tool that rejected the whole history

`tools/check_commit_message.py` capped the subject and every body line at 72
characters. Measured over all 87 commits: **all 87 were rejected.** 41 predate
the Conventional Commits grammar and fail it, which is honest. The other 46
follow the grammar and failed only on length — 45 of them. The longest subject
among the 46 is 77 characters and the mean is 63; the closing recap paragraph of
those commits runs to 209 characters on a single line.

A rule the whole history breaks is not a rule being broken, it is a rule that
was never kept, and an unenforced rule in `CONTRIBUTING.md` is worse than none:
it reads as a standard and fails everything, so it teaches a reader to ignore
it. **The subject is capped at 80 and the body is not capped at all**, because
the subject is a display surface — `git log --oneline`, a pull request list —
and the body is prose.

The grammar itself is kept exactly, because it is the part the project does
keep: 46 of 46 since it was adopted. The 41 older commits still fail and are
left failing, because rewriting published history to satisfy a linter is a
worse trade than a linter the older history is honestly outside of.

A message file may open with a blank line: git's own cleanup strips those when
it creates the commit, but the checker reads the file it is given. `check` read
line one as the subject, called such a message empty and stopped there, so a
message with a fine subject was refused for a reason that was not about it. It
now skips the leading blank lines, as git's cleanup does, and the empty-message
test covers a truly empty message, a line of spaces, and a message whose subject
follows the blanks without its line-two rule being lost.

The tool was in no hook and no workflow, which is how a tool could disagree
with every commit in the repository for as long as it existed. It is now a step
in `deploy.yml` that walks the commits the push added and fails the build on
one, and a scheduled run says it has nothing to check rather than passing
silently.

## Verified

The 24 September 2026 download: 3,436 stations with a CRS, 1,210 classified and
2,226 not, 0 reviewed codes absent, 0 redundant, 0 classification failures. A
second load of the same feed takes no workbook read, emits no schema note, and
reports the same classes — the cache now survives its own round trip.

`build_demo_page.py --feed feeds/fares --origin KGX --require-live-reviewed-codes`
publishes. The corrected classes are what the page gets: Penrhwceiber, Harringay,
Ladybank, Banavie, Balloch Central, Brithdir, Wrenbury, Birchington and Fernhill
are villages; Cardenden, Rotherham Central, Newton-le-Willows, Southend Airport
and Barming are towns; Wakefield Westgate and Hull are cities.

`tools/propose_reviewed_settlements.py --feed feeds/fares` reports 0 to delete,
4 to decide, 302 in agreement, and the four are the ones a person has to judge.
`tools/test_commit_message.py` passes 12 tests, and every commit in the history
that follows the grammar passes the checker that CI now runs.
