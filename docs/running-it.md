# Running it: every flag

Every flag the runner and the build accept, and what each one is for.

## Open the app on this machine

**What it runs on:** Python 3, standard library only -- there is no
`requirements.txt` and nothing to install. The version is pinned in
`.python-version` (3.12, what every workflow uses), and the code is written to
3.12: it also runs unchanged on 3.13 and 3.14, which is what a developer machine
here has, but 3.12 is the version a change has to work on.

**To open the app on this machine:** double-click `run.bat` (Windows), or run

```
python run.py
```

That builds one page per priced station from the current feed, serves it at
http://localhost:8741, and opens your browser. The next run serves what the
first one wrote and
starts immediately. The worker count comes from what the machine has free rather
than from how many cores it has, because every worker holds the whole timetable;
a machine short of memory builds on one worker rather than dying (ADR-0057).
The runner also rebuilds when
the builder, the template or the fare maths is newer than the build it would
serve, so a page cannot quietly be yesterday's (ADR-0055). The runner removes any
station page folder a *previous* single-origin build left behind, reading the
release manifest to tell which folders this build wrote. Close the window (or
Ctrl+C) to stop.

### What a whole-network build costs, measured

Every measured figure lives in `docs/build-performance-findings.md`, which is the
one place for them (ADR-0032). The short version: the default run is **prices
only** -- `run.py` reads `feeds/fares` and loads no timetable unless
`--with-timetable` is given -- and it builds **2,712 pages in 23 min 38 s**, 1.91
pages/s, 592 MB of output. Journey times need `--with-timetable`, which loads the
national timetable, and that build is **hours**: 8 h 06 m on one worker, about 2 h
10 m on the four a 16 GB GitHub runner offers. Which is a long time to wait for a
page you are not going to read all of, so for one station, or two, use the script
below instead.

**To build just Grantham and Nottingham, fares *and* timetable, in one command:**

```
double-click build_stations.bat   (Windows), or run
python -m trainbudget.build.build_stations
```

That builds exactly those two stations against the real feeds in `feeds/fares`
and `feeds/timetable`, writes their pages, a two-station chooser and the privacy
page into `_stations/` (which is not what `run.py` serves, so the two never
fight), and serves it at http://localhost:8742. It uses `--workers 1`, because two
timetable-holding workers do not fit in this machine's free memory, and the
script prints a warning if there is not even room for one.

The two-station build's own figures -- five runs, the **6.4 GB** floor they hit,
and the phase split behind them -- are in `docs/build-performance-findings.md`,
next to the whole-network numbers above.

`trainbudget/build/build_stations.py` takes `--timetable`, `--knowledgebase`, `--feed`, `--out`,
`--workers`, `--date`, `--port` and `--no-serve`, and station codes as bare
arguments (`python -m trainbudget.build.build_stations LEI`).

Underneath it is one flag on the builder itself, usable without the script:
`python -m trainbudget.build.build_demo_page --all-origins --only-stations GRA,NOT` builds
exactly those stations, and refuses an unknown code rather than quietly building
all 2,712 of them. Add `--timetable feeds/timetable` for journey times, or leave
it off for prices only.

**To build those pages without reading the national timetable at all**, write the
per-origin slices once and point builds at them:

```
python -m tools.build_timetable_index --timetable feeds/timetable --origins GRA,NOT
python -m trainbudget.build.build_stations GRN --timetable-index _cache/timetable-index
```

The writer parses the feed once and writes one file per station (Grantham's is
157 MB of the feed's 419,589 schedules, Nottingham's 209 MB); every build after
that reads its page's own slice off disk in 4-6 seconds and holds a slice rather
than the 1.87 GB national index (855 MB for Grantham's, 1.13 GB for Nottingham's,
measured as Python heap). `trainbudget/build/build_stations.py` and `build_demo_page.py
--timetable-index` both take the directory, and when the index holds a slice for
every page the build writes, no timetable feed is read at all -- not by the pool
workers either. A station the index has not got is refused before the build starts
rather than published without times. The index is keyed to the feed's bytes and the
source that reads them, so a new download writes a new directory rather than
reusing the old one. Measured on 8 October 2026, the two-station command given the
index **finished, exit 0, in 3 min 44 s** with 4.7 GB free and wrote the same site
as the build from the feed.

Useful variants: `--origin GRA` for the fast single-station page — its root at
`/`, that one station under `/from/<slug>/`, and the privacy page, with a root
that names the station rather than offering a search over a list of one —
`--port 9000`, `--no-build` (serve what's there), `--timetable` with no value for
a prices-only build, and `--feed feeds/fares --timetable feeds/timetable` for
the real licensed feeds. The demo feed is rebuilt first if `_demo_feed/` is
missing: `python -m trainbudget.feeds.make_synthetic_feed _demo_feed --unserved-station
--third-origin --return-network --long-list`.

A real-feed run carries the same licence notices the deploy workflow passes,
without being asked, so the page you preview is the page that ships. `--notices`
narrows that set rather than granting it; the demo feed gets none, because
crediting NRE for invented prices would be false attribution.

The individual commands behind it, if you want them separately:
```
python -m trainbudget.feeds.make_synthetic_feed _demo_feed --unserved-station --third-origin --return-network --long-list
python -m trainbudget.build.build_demo_page --feed _demo_feed --timetable _demo_feed --all-origins --out _demo_site/index.html
python -m http.server 8000 --directory _demo_site   # then open http://localhost:8000/
python -m unittest discover -s tests -p "test_*.py"
python -m trainbudget.feeds.feed_audit --feed _demo_feed --timetable _demo_feed
python -m trainbudget.measure.grantham_sweep --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20 --adults 2 --railcard "Two Together"
python -m trainbudget.measure.grantham_sweep --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20 --date 2026-09-27
```

CI runs the same tests under a coverage floor, and you can run the chain locally:

```
python -m pip install coverage
python -m coverage run -m unittest discover -s tests -p "test_*.py"
python -m coverage run --append -m unittest discover -s tools -p "test_*.py"
python -m coverage report --fail-under=79 --precision=1
```

To measure the journey search, build an invented feed of the shape you want,
replace it with the downloaded feeds once they land, and name a real origin:

```
python -m trainbudget.measure.benchmark --shape hub_spoke --stations 300 --schedules 8000 --caps 0,60,200 --transfer-only
python -m trainbudget.measure.benchmark --feed feeds/fares --origin GRA --queries 40 --caps 0,60,200 --transfer-only
```

To question a count, and to break a feed on purpose:

```
python -m trainbudget.measure.sanity_report --feed _demo_feed --timetable _demo_feed --origin GRN --budget 20
python -m tools.check_slice_equivalence --timetable _demo_feed --days 1 --probe 3
python -m tools.check_slice_equivalence --timetable _demo_feed --days 1 --progress _cache/demo-equivalence.json --shard 1/4   # then --merge 4
python -m trainbudget.feeds.damage_feed --list
python -m trainbudget.feeds.damage_feed _demo_feed _damaged crlf
python -m trainbudget.feeds.damage_feed _demo_feed _damaged truncated_record --target ffl
python -m trainbudget.feeds.fuzz_feed --feed _demo_feed --rounds 200 --seed 1
python -m trainbudget.feeds.fuzz_feed --feed feeds/fares --rounds 500 --seed 1 --keep _fuzz_failure
```

Swap `_demo_feed` for the downloaded feeds to get the real answer. The fares
sweep alone works without `--timetable`, and then shows prices without journeys.
