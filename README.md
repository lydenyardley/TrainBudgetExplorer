# Train Budget Explorer

Ask what a station can reach for a budget, and get a page: every destination
within the money, the fastest journey to each, the changes it takes, and the fare
a reader would pay.

**Status:** the whole-network release builds from the licensed National Rail feeds
and publishes as a static site on GitHub Pages — 2,838 pages on 26 October 2026 —
behind a licence clearance a person signs off. The fares and the times are
indicative: the seller's own conditions decide what a ticket actually costs.

## What it does

From one station, the site answers "where can I go for under £X?":

- **Every destination a budget reaches**, priced from the fares feed, with the
  ticket each row names — and what that ticket allows — shown on the row itself.
- **The fastest journey to each**, and how many changes it takes, from the CIF
  timetable. A dated build honours service days, date ranges and overrides.
- **A railcard price**, for a reader who holds one of the reviewed cards, where
  the feed's own railcard restrictions permit the fare.
- **Refinements and a shortlist** — destination type, ticket mode, a party of
  adults and children, and a dock that holds the journeys a reader is weighing.
- **Where the numbers came from**, how old the prices are, and what the page's
  approximations are, on the page rather than in a footnote.

Everything is static. There is no account, no tracking script and no server: a
page is a file the browser opens, and it works from GitHub Pages or from a
`python -m http.server` on a laptop.

## What it is not

It is not a retailer, and it does not sell anything. A row's ticket link opens the
seller's own search with tracking off by default, and the page says so where the
handoff happens. It is not a substitute for the operator's conditions either: a
price is what the feed says the fare is, and a journey time is the fastest service
in the timetable, not a promise about the day a reader travels.

## Run it

Python 3.12, standard library only — there is no `requirements.txt` and nothing to
install. The version is pinned in `.python-version`, which is what every workflow
uses.

```bash
python -m trainbudget.feeds.make_synthetic_feed _demo_feed   # once, so there is a feed to read
python run.py                    # build one page per priced station, serve it on :8741, open it
python -m tools.verify --fast    # the checks a change has to pass, about a minute
python -m unittest tests.test_build_demo_page    # one module, while you work on it
```

That builds from the synthetic feed the tests use, so it needs no credentials. A
real build wants the DTD entitlement the feeds sit behind (this project's account
holds it; every CI build downloads and audits both feeds with it), and then a run
with no `--feed` picks the downloaded one up by itself:

```bash
python -m trainbudget.feeds.dtd_download    # credentials from the environment
python -m trainbudget.feeds.dtd_audit       # what arrived, before anything reads it
python run.py --feed feeds/fares --with-timetable --origin GRA
```

The downloader writes atomically and refuses a response that is not a schedule, so
a missing entitlement is reported as itself rather than landing as an empty feed.
Every flag, and what a whole-network build costs on a real machine, is in
[docs/running-it.md](docs/running-it.md).

## How the repository is laid out

| Path | What is in it |
|---|---|
| `trainbudget/fares/` | The loaded fares database, the feed readers behind it, the restriction parser, the seller links |
| `trainbudget/timetable/` | The CIF timetable, the Knowledgebase, and the per-origin slice a page is cut from |
| `trainbudget/build/` | The build command, its phases, the payload, the templates, the release record |
| `trainbudget/feeds/` | The licensed downloaders, the feed audits, the damaged-input tools, the fixture builder |
| `trainbudget/measure/` | The commands that measure a number rather than assert one |
| `page/` | The site's CSS and JavaScript, one file per panel, inlined into each route |
| `tests/` | The unit suite, and the Playwright suite in `tests/browser/` |
| `tools/` | The operator commands: the verifier, the gates, the measurements |
| `docs/` | The subjects below, the measured figures, the open work |
| `adr/` | The decisions, numbered, each with the reasoning that produced it |
| `licences/` | The release clearance the publication gate reads |

`run.py` and the two `.bat` launchers are the only code at the root. [AGENTS.md](AGENTS.md)
is the maintained map — every module, every page asset, every tool, and each rule
with the thing that enforces it — and `tests/test_agents_map.py` fails when it
drifts.

## Where the detail lives

| Document | What it answers |
|---|---|
| [docs/fares.md](docs/fares.md) | How a destination is classified, what a row may claim, and the conditions behind a price |
| [docs/timetables.md](docs/timetables.md) | What a journey time means, and where the onward search stops |
| [docs/feeds.md](docs/feeds.md) | The two licensed feeds, the entitlement, and how to keep up with them |
| [docs/builds.md](docs/builds.md) | The demo page and the whole-network release, end to end |
| [docs/running-it.md](docs/running-it.md) | Every flag, and what a build costs |
| [docs/open-work.md](docs/open-work.md) | Everything still open, numbered, and why |
| [docs/settled-work.md](docs/settled-work.md) | Every closed item with the check that holds it, and the designs that were refused |
| [docs/build-performance-findings.md](docs/build-performance-findings.md) | Every measured figure, with the date it was measured |
| [docs/glossary.md](docs/glossary.md) | The terms this project uses, and what they mean here |
| [docs/dtd-licensing-and-data-access.md](docs/dtd-licensing-and-data-access.md) | The licence research, the entitlement, and what may be published |
| [CONTRIBUTING.md](CONTRIBUTING.md) | The commit convention, and how to run the tests |

## The data, and what may be shown

The fares and the timetable are licensed National Rail data, downloaded under an
entitlement that is not this repository's to grant: the feeds themselves are never
committed (ADR-0005), and the checked-in fixture is invented. What a release may
publish, and under which terms, is a person's dated decision recorded in
[licences/release-clearance.md](licences/release-clearance.md), which the deploy
workflow refuses to publish without.

A page that shows a fare carries the National Rail credit; that is a rule with a
checker, not a convention. Where the site's own prose describes a licence, it says
what the clearance file says.

## Contributing

One logical change per commit, Conventional Commits, and a command whose output a
reviewer can reproduce in the body. [CONTRIBUTING.md](CONTRIBUTING.md) has the
grammar and the checker; `git config core.hooksPath .githooks` once per clone makes
the hook enforce it before a bad message becomes a commit.
