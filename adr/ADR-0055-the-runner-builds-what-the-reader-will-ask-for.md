# ADR-0055: The runner builds what the reader will ask for, and never serves a stale one

**Status:** Accepted; amended 12 October 2026 and 14 October 2026 (see below)
**Date:** 1 October 2026
**Relates to:** ADR-0019 (one page per station), ADR-0024 (the release is
published under the repository's own path), ADR-0050 (the release is the whole
network), ADR-0051 (the runner serves and the build builds).
**Amends ADR-0051**: the separation it decided is kept, and the default it
decided is reversed.

## Context

ADR-0051 separated the build from the serve so that "the page I am looking at is
the page I built" could be asked and answered. It decided that `python run.py`
serves `_site/` as it is, and that `--all-origins` — the whole network, 2,718
pages on the real feed — had to be asked for by name and refused otherwise.

Two things made that decision wrong in practice, and both were found by using the
runner rather than by reading it.

**The default built a page the page itself said was a subset.** ADR-0050 decided
that a release is the whole network. `python run.py` with no flags built one
station, so the page a contributor opened had a station name in its heading that
was plain text rather than a control: a single-origin build honestly refuses to
render a picker with nowhere to go. The first thing the runner did by default was
produce a page that could not do the one thing the heading offers.

**The separation had no way to notice staleness.** A build written before the
last commit is a page from before the last commit, and nothing on the page says
so. The separation made the stale answer *knowable* — you could ask the runner
which it did — and that was worth having. It did not make the page correct. The
review that follows such a build is a review of yesterday's fares, and a railcard
fix appears not to work.

## Decision

**1. The default build is the whole network, and it says what that costs before it
starts.** `python run.py` builds one page per priced station, prints the measured
cost, and says that the next run will serve what this writes. The cost was
originally recorded here as about 20 minutes on eight cores, 81 on two. That was
measured without the national timetable, and the eight-worker build it assumed
dies with a MemoryError (ADR-0057). Re-measured with the timetable on a 15.8 GB
machine, 2 October 2026: 0.093 pages/s per worker, so about two hours on the
four workers that machine can hold and most of a working day on one. The figure
in this decision is withdrawn rather than qualified, and so is the 63 minutes
that replaced it here an hour earlier: that came from the first nine minutes of
a build, which are the cheapest stations in the set, and a rate taken from the
first tenth of the work is not a rate for the work. The
`--i-know-this-is-slow` guard is gone, because the default no longer needs
consent: the question ADR-0051's guard asked — *are you sure you want an hour?* —
is answered in the first line of output instead of by a refusal.

**2. `--origin GRA` remains the fast path.** A build of one station is the right
tool for working on one station and the wrong thing to double-click, so the
single-origin build is still one flag away and the notice names it.

**3. A build older than its sources is rebuilt, and the runner says why.**
`sources_are_newer()` compares the mtimes of the builder, the template and the
modules they import against `_site/release-manifest.json` — the manifest, because
it is written last and is therefore the build's own completion stamp. A manifest
that is missing or unreadable answers *no*: an unreadable answer must never be the
one that starts an hour-long build, and `--rebuild` is always there.

**4. The separation is kept.** `--no-build` still never builds and still fails
when there is nothing to serve. `--rebuild` still builds over an existing site.
The runner still says which of the three things it did.

## Consequences

- **"The page I am looking at is the page I built" is now true by default**,
  which is the whole of what ADR-0051 was for. The mechanism changed; the
  question it made askable is answered without asking.
- **A contributor on a clean checkout still needs one command**, and a
  contributor with a nine-hour-old `_site/` and a changed fare maths gets a
  rebuild instead of a confident wrong answer.
- **The first run on a real feed is now the slow one by default.** That is the
  cost, it is printed before it starts, and `--origin` is one flag away. A
  double-click of `run.bat` on a fresh clone builds the network, which is what a
  release is.
- **The freshness check is a decision under test, not an accident.** The runner's
  tests patch `sources_are_newer` and assert the decision — rebuild, or serve —
  so the check reads the decision under test rather than this machine's file
  times.
- **ADR-0051 is left as the record of the decision it was.** Its separation is
  kept; only its default is reversed, and the reason is written down here rather
  than in a comment.

## Amendment — 12 October 2026: the default is the fast page again (T7)

Decision 1 above made the double-click path a whole-network batch job, and a
first run never finished: about four hours on this machine's free memory
against the two hours the decision quoted from a larger one. The default is
the fast single-origin page again, which is what this runner's own docstring
already promised — the code contradicted it, and the contradiction is what
this amends. A single-origin page stands as text where a network page offers
the station control, so there is nowhere to change to and the name is not a
control that opens nothing; the heading objection that moved the default to
the network in the first place does not survive that reading.

The whole-network build is still one flag away, and the flag now requires
its acknowledgement: `--all-origins` without `--i-know-this-is-slow` is
refused before it starts, with the measured cost named, rather than after it
has finished. Decisions 2, 3 and 4 stand unchanged.

## Amendment — 14 October 2026: the source list is read from the build's imports

Decision 3's `sources_are_newer()` walked a tuple written out in the runner, and
`build_demo_page.SOURCE_FILES` was a second tuple kept by hand for the same
purpose. Both had drifted from the build they describe: every build imports
`atoc_fares_loader`, `atoc_knowledgebase` and `destination_coverage`, and neither
list named one of them, so a fix to any of the three left this runner serving the
pages from before it while saying nothing. `tools/build_inputs.py` replaced the
workflow's hand-kept list with a rule for the same reason (F4 of the 8 October
2026 agent-efficiency audit); the two local lists are now read the same way.

`build_demo_page.module_sources()` walks the build's own imports, transitively,
and `SOURCE_FILES` is that walk plus the data a build reads rather than imports:
the `reference-data/*.json` the facet reader globs, because a regenerated facet
file changes what a page calls its destinations, and the mark in `assets/` that
`nre_attribution` inlines into every page carrying the NRE credit. Neither
directory was on either list before, so replacing the brand mark left every
built page showing the old one. The runner imports these names instead of
keeping a second list, so there is one owner and no copy to forget; a module
moved into a new file is on the list the moment the build imports it.

Two costs, both measured on this machine. The walk parses the 13 modules the
build reaches and is **259 ms** of `build_demo_page`'s 584 ms import, once per
process. And the set hashed by `source_fingerprint()` changed, so every cache
keyed on it (ADR-0031) is invalidated once: the next build re-parses the feed,
55.6s on the real timetable against 2.6s restored, and an interrupted build
does not resume. CI's own fingerprint needed one edit rather than a rework:
`tools/build_inputs.py` is a rule about where sources live, and it now names
`assets/*` beside `reference-data/*`.
