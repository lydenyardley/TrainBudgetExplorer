# ADR-0051: The runner serves, and the build builds

**Status:** Accepted
**Date:** 1 October 2026
**Relates to:** ADR-0010 (the demo page before the gate), ADR-0019 (one page per
station)
Answers question 3 of `docs/open-work.md`.

## Context

`run.py` did both jobs. It shelled out to `build_demo_page.py`, tidied the
folders the build did not write, then served the result and opened a browser.

The cost is not that shelling out is inelegant. The cost is that the server
cannot say what it is serving. "The page I am looking at is the page I built" is
the question every review of a generated page rests on, and a command that
rebuilds on every start makes it unaskable: the artifact under the browser is a
product of the last start, and whether the feed moved between the build you ran
by hand and this one is unknowable from the page. The stale answer to that
question is how fares get reviewed against yesterday's download.

## Decision

**The build and the serve are separate decisions, and the runner states which
one it took.**

- `python run.py` **serves `_site/` as it is** and says so on stdout.
- On a clean checkout there is nothing to serve, so it **builds once first**.
  The double-click path a contributor starts from still works.
- `--rebuild` builds again before serving, which is what you want after the
  feed moved.
- `--no-build` never builds and **fails** if there is nothing to serve, rather
  than quietly building what it was told not to.

The build remains `python build_demo_page.py` with its own flags, which is what
the deploy workflow already calls directly and what every "build one origin and
read the page" instruction in the README already tells a reader to type. Nothing
about building a page changed; what changed is that the runner stopped being the
thing that does it by default.

`run.py` also keeps the flags that make a local build match a published one,
because those are about the build and not about serving: a real feed takes every
licence notice without being asked, `--all-origins` builds the whole network, and
`--with-timetable` opts into the national timetable. The `--all-origins` refusal
stays too, and now quotes the measured cost.

## Consequences

- A reviewer can serve `_site/` and be certain it is the artifact under review.
  If they want a fresh one they ask for it by name, and the runner says which
  happened.
- A contributor on a clean checkout still needs one command, not two.
- Nothing is installed and nothing outside this folder is touched, as before.
- The four behaviours are tests rather than prose: a clean checkout builds, a
  second run serves without building, `--rebuild` builds over an existing site,
  and `--no-build` refuses rather than building. The first and last are the two
  a reader would get wrong silently.

Read by running:

```bash
python run.py --help
python -m unittest tests.test_page_runner.RunnerBuildOrServeTest -v
```
