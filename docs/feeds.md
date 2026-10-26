# The licensed feeds, and how to refresh them

Two licensed National Rail feeds, an entitlement that decides whether they
can be downloaded at all, and the commands that keep up with them.

## Refreshing the real feeds

The DTD fares feed updates weekly and the public timetable daily, so "keeping up
with the data" is a repeat of this sequence whenever a new release matters:

```bash
python -m trainbudget.feeds.dtd_download
python -m trainbudget.feeds.dtd_audit
```

The downloader writes each ZIP atomically and records its non-secret URL, size,
and hash in `feeds/download-manifest.json`; the audit then checks the archive
before the page build reads it. The deploy workflow runs this on a daily
schedule (`17 3 * * *` UTC) as well as on every push, so the published pages
follow the feed without anyone running anything. A rebuild is the only step that
changes the published pages. The page's own provenance line comes from the feed's
`metadata.json`, so a refreshed build says which download it was built from.

**A daily refresh does not re-fetch 125 MB to be told nothing changed.** A
national fares and timetable pair is large and is re-requested every run whether
or not the portal has published a new one, so the downloader asks conditionally:
when the manifest holds an `ETag` or `Last-Modified` from the last run, and the
file it describes is still on disk, the request carries `If-None-Match` /
`If-Modified-Since` and a `304` keeps the archive. A portal that ignores those
headers answers `200` and the download proceeds exactly as before, so this
cannot break against one that does not support it. A `304` never advances
`downloaded_at` — the page measures the age of its prices against that field,
and a feed the portal last republished a month ago must keep saying so however
many `304`s it has answered since. It records `checked_at` instead, which is
the moment the portal was asked rather than the moment data arrived.

A `304` is believed only if the file on disk still matches the record that
asked the question: its size and its SHA-256 are re-checked first, and a
truncated, replaced or half-written file is fetched in full rather than
carried forward. That turns the manifest's central claim from one this run
inherited into one it verified, and it costs a fraction of a second against the
network transfer it saves. `--no-conditional` skips the question entirely, which
is the escape hatch when a local file has gone bad underneath the downloader.

**A transient failure is retried; a refusal is not.** A timeout, a reset
connection, a `429` or a `5xx` on an unattended daily job used to fail the whole
run for a reason that would be gone in a minute. Those are retried up to
`--retries` times (3 by default) with a pause that doubles and is capped.
A `4xx` is not retried: a portal that has refused the subscription or the
credentials will refuse them again, and asking again only spends the run's
time. A response that is the wrong shape — an HTML error page behind a `200` —
is not retried either, because that is a fault to be read, not weather to wait
out.

**The published build carries journey times, and they come from a second source.**
The deploy workflow loads the DTD fares feed for the prices and Network Rail's own
CIF for the times: the DTD timetable's Schedule 1 §5 permits internal business
purposes only, so the same schedule is published from the Open Government Licence
product instead (ADR-0073). It passes `--date`: the build job names one day once and
every share is built for it, because an undated page has no day to walk a week from.
It carries no day control at all, and every page indexes the feed's whole schedule
window instead of one day's share of it -- 7x the work, measured on 21 October 2026
(`docs/build-performance-findings.md`). The release is the whole network as prices,
conditions and times for that one day, and every page names the day it is for.
Three places state this shape and they have to agree -- the build's `--timetable`,
the clearance job's `--release fares,timetable`, and the journey check that reads
the built pages. A run whose station pages come out carrying no journeys fails
that check rather than publishing a release that does not match what it declares.

That step is measured rather than assumed, and the release is the **whole
network**, so it is measured on the whole network. One origin against the real
feed, on this repository's own machine:

| build | time |
| --- | --- |
| fares only | 2.5 s |
| fares + timetable, cold index | 1 m 36 s |
| fares + timetable, warm index | 11 s |

The whole set is a different shape of work, and it was measured rather than
projected. ADR-0024 had put it at about two days, from an invented uniform feed
in which every station priced about 2,500 destinations. The real feed's origins
are small, and that is the whole difference:

| | measured against the real feed |
| --- | ---: |
| priced origins | 2,718 |
| destinations per origin | median 91, mean 116, max 851 |
| fares and schedules loaded | 7,818,772 and 419,589 |
| load before the first page | 279 s |
| steady state, 3 workers on 12 CPU | 0.84 pages/s |
| whole set at that rate | ~54 min, plus the load |

Per-origin cost does not track destination count here: the origin pricing 851
destinations took 110 s in isolation and the one pricing a single destination
took 99 s. On GitHub's 2-vCPU runner that puts the set at about 81 minutes plus
the load, and the step's `timeout-minutes` is 150. ADR-0024 is amended, and
ADR-0050 is the decision that follows from the measurement.

The warm figure above is still why the workflow caches the timetable index: the
cache file is named after a digest of the feed bytes and the stations it serves,
so a cache from a different timetable is a different filename and is never
opened. A stale restore is a miss, not a wrong answer.

Two gates read the result rather than trusting it. `tools/page_bytes.py --site
_site` holds the release against the 800 MB target (measured: 498 MB over 2,714
routes), because nothing else in the workflow reads the bytes and every other
gate is satisfied by a release twice the size. And the browser sweep drives 24
pages spread evenly across the 2,718 rather than the first 24 in name order,
because a prefix of a whole-network site is the stations whose slugs start with
A and B.

1. Set `NRDP_USERNAME` and `NRDP_PASSWORD` in the local environment. Do not put
   either value in a command, source file, or chat message. The `.env` pattern is
   ignored by this repository if a local environment file is preferred.
2. Download the DTD fares and timetable ZIPs:

   ```bash
   python -m trainbudget.feeds.dtd_download
   ```

   This writes `feeds/fares/dtd-fares.zip` and
   `feeds/timetable/dtd-timetable.zip`. Use `--dtd fares` or
   `--dtd timetable` while confirming entitlement, and `--kb` to download the
   supplied Knowledgebase XML feeds as well. The downloader never replaces an
   existing good archive with an error page, empty ZIP, or non-ZIP response.

   `--print-fingerprint <manifest>` prints a digest of what a manifest says the
   feeds *are* and exits, needing no credentials. Compare that rather than the
   manifest's bytes to decide whether a rebuild is warranted: the manifest also
   records when a download was last *checked*, which moves on a day the portal
   republished nothing, and a byte comparison would read that as a new feed
   every day.
3. Validate and audit the real pair:

   ```bash
   python -m trainbudget.feeds.dtd_audit
   ```

   This distinguishes missing, empty, invalid, and unrecognized downloads from
   a valid feed whose parser rejected records. It then prints the existing
   `trainbudget/feeds/feed_audit.py` report. **Grantham's real station code is `GRA`, not the
   `GRN` the synthetic feed invents.**
4. Run `python -m trainbudget.feeds.fuzz_feed --feed feeds/fares --rounds 500` and read anything it
   reports. It is the only thing that will exercise the real feed's encodings and
   record shapes against a parser written without them.
5. Add the Knowledgebase reference feeds. They are a different subscription from
   the DTD fares and timetable, so the same credentials do not prove entitlement:

   ```bash
   python -m trainbudget.feeds.dtd_download --output-root feeds --kb
   ```

   This writes `feeds/knowledgebase/*.xml`. The build reads the
   `ticket-restrictions` feed as a second opinion on whether the portal still
   publishes the conditions the fares feed quotes; see below for what it does
   and does not claim.
6. Run `python -m trainbudget.measure.sanity_report --feed feeds/fares --timetable feeds/timetable
   --origin GRA --budget 20` and read what the count left out.
7. Check the current DTD/NRE terms, brand treatment, commercial-use permission,
   and affiliate disclosure before publishing. The research and escalation route
   are in `docs/dtd-licensing-and-data-access.md`.
8. Run the sweep for the Stage 1 count that decides go/no-go.

The Knowledgebase URLs can be downloaded independently, but they contain
reference/service information rather than the DTD fares and timetable. A token
for those URLs is not proof of DTD entitlement.

The four readings in the sanity report are not four answers to one question.
They are one question asked in four ways, and the gap between them is the part
worth reading.
