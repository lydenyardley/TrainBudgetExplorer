# ADR-0073: The publishable timetable is a whole CIF from a URL

**Status:** Accepted
**Date:** 16 October 2026
**Relates to:** ADR-0005 (a licensed feed is never checked in), ADR-0024 (memory
per worker), ADR-0032 (a measurement plan before a figure), ADR-0047 (the
release is what the clearance record allows), ADR-0050 (the release is the whole
network), ADR-0067 (a Rail Data Marketplace licence is filed like any other),
question 11 of `docs/open-work.md`, `docs/dtd-licensing-and-data-access.md`

## Context

The Darwin Timetable Files product is marked OGL3 and its Schedule 1 §5 allows
internal business purposes only, so the 16 October release published prices and
no journey times. Network Rail's **NWR Schedule** product carries the same CIF
under the Open Government Licence v3, whose §5 permits raw redistribution, and
its licence was filed on 16 October 2026.

Two things stand between that licence and a page with times on it, and only one
of them is about code.

**The file has to arrive.** The Rail Data Marketplace's file products have no
pull API: the platform's own guide offers the dashboard's Download button and a
*file transfer* it pushes to a destination the consumer owns (S3, Google Cloud
Storage, Azure Blob, SFTP), and its wiki entry for File Source feeds is "cannot
be easily used in software". Driving the dashboard from a script means a bearer
token from the browser login flow, whose client secret is AES-CBC encrypted and
whose account may carry a second factor -- and the public scraper's own author,
"following constructive dialogue with Rail Delivery Group", recommends the
official transfer tooling instead. Network Rail's own feed at
`publicdatafeeds.networkrail.co.uk/ntrod/CifFileAuthenticate?type=CIF_ALL_FULL_DAILY&day=toc-full.CIF.gz`
answers HTTP Basic and redirects to a signed S3 URL: the simplest code of the
three, the same CIF, the same licence -- and admission capped at 1,000 accounts,
reported full in the community in January 2026. The owner has no cloud
destination to push to.

**The file is a different shape from the one the loader was written for.** The
DTD product ships a folder of record-type files with a `.msn` station names file
beside them, filtered to passenger services before publication. Network Rail's
CIF is one gzipped file, unfiltered, with no station names at all. Three silent
failures live in that difference, and each was reachable before this decision:
a `.gz` reaching `read_feed_files` as a text file of unknown kind; a freight path
or an empty-stock move offered as a journey; and -- worst -- a focus derived from
a station names file that does not exist, which drops every schedule one at a
time and answers "nowhere" for every station while reading the whole file to do
it.

## Decision

The timetable a release publishes comes from Network Rail's CIF under the Open
Government Licence, fetched by `schedule_download.py` from **a URL with an
optional Basic credential**. Which URL is the owner's and the code does not know
the difference: Network Rail's own feed if an account is granted, a copy that
arrives by hand at any address otherwise. Scripting the marketplace dashboard is
not the plan, and would need the platform agreement read before it was.

Four rules make it safe to run unattended.

- **The credential never travels further than the door it opened.** Network Rail
  answers with a 302 to a signed S3 URL, and S3 refuses a request carrying both a
  query signature and an `Authorization` header ("Only one auth mechanism
  allowed"). urllib copies the headers onto the redirect, so the handler drops it
  -- and only HTTPS is accepted as a destination, because the host cannot be
  known in advance and a plain hop on a signed URL costs more than the file.
- **A download is not a feed until it has been read.** The bytes stream to
  `.name.part` beside the destination, the gzip (or the plain text) is read far
  enough to see a CIF record, and only then is the file moved into place. A web
  page answering a bad URL is refused by name rather than published as a
  timetable with no journeys in it. The temporary name is removed on any failure,
  because the loader reads every file in a folder and half a download is a second
  timetable.
- **What a passenger cannot take is filtered by the CIF's own code tables**, not
  by the presence of a public time: freight, trip, bus and ship statuses, and the
  empty-coaching-stock and parcels categories -- an empty-stock move is a
  passenger train (`P`) that carries nobody, which is why the status alone is not
  the test. A blank or unrecognised value is kept, because the DTD feed's own
  files do not fill every field and one blank field must not empty a page.
- **A feed that names no stations is read unfocused, not emptily.** The focus
  decides how much is held, not whether an answer exists.

## Evidence

- `tests/test_schedule_download.py` (17 tests): the query string and any userinfo
  are never printed, the header is dropped across a redirect while the redirect
  itself is followed, a downloaded fixture is readable by `TimetableDb`, a web
  page and an empty body are refused with nothing left on disk, a 403 with a
  credential names `SCHEDULE_USERNAME` and never the password, a 503 is retried,
  a truncated archive is refused by the parser that reads it, and a second feed
  beside the file is named.
- `tests/test_atoc_timetable.py::WholeCifFeedTest` (4 tests): a gzipped whole CIF
  is read under the name it holds, a freight path and an empty-stock move are not
  journeys (and are counted), a feed with no station names is read unfocused and
  says so, and the same feed with station names focuses as usual.
- `make_synthetic_feed.build_synthetic_whole_cif` writes the shape: one gzipped
  file, the freight and empty-stock services in the CIF's own layouts, an `.msn`
  file only when a test asks for one. The empty-stock move carries public times
  on purpose, so the test is the code table and not a missing time.
- The whole timetable suite passes: 55 tests in `tests/test_atoc_timetable.py`,
  and the shared reader's other callers are unaffected
  (`tests/test_atoc_fares.py`, `tests/test_feed_audit.py`, `tests/test_fuzzed_feed.py`,
  `tests/test_dtd_download.py`, `tests/test_feeds_cli.py`, `tests/test_page_caches.py`:
  255 tests).

## Consequences

- Nothing about the release changes yet. `tools/check_release_clearance.py` still
  refuses `--release fares,timetable` on Darwin's exclusion, NWR Schedule's
  section in `licences/release-clearance.md` is `excluded` until the owner signs
  it, and `TIMETABLE_GLOB` still names Darwin's evidence. Wiring the build to a
  timetable is the commit that follows the approval, not this one.
- The fetch is one command an owner can run today:
  `python -m schedule_download --url ... --out feeds/timetable-nwr/nwr-schedule.CIF.gz`,
  then `--timetable feeds/timetable-nwr` on a local build. Local builds are
  ungated; publishing is not.
- A whole CIF is read unfocused once, by the index build, where ADR-0024's memory
  floor already applies; page builds read slices. A page build pointed straight
  at the feed holds all of it and reports the focus it did not apply.
- The passenger filter also runs over the DTD files, where it drops nothing today
  (their status is blank) and counts nothing. That is the intended outcome: the
  same reader serves both sources, and the day the DTD feed fills the field the
  filter is already there.
- `docs/open-work.md` question 11 keeps the delivery route open. The code no
  longer depends on which answer it gets.

**Amended 21 October 2026.** The shard build passes `--date` again, one day named once
by the build job and handed to every share. The 16 October wiring above dropped it with
the CIF switch, and an undated page turned out to have no day control at all and to
index the feed's whole schedule window for every page: share 3 of the 21 October run
wrote 78 pages in 139 minutes and timed out, where a share on 13 October wrote 458 in
108 minutes with a day (`docs/build-performance-findings.md`). Nothing about the licence
changed, and `--release fares,timetable` is what the gate still clears.

**Amended 16 October 2026.** The record and the gate caught up the same day. NWR
Schedule's section in `licences/release-clearance.md` is `cleared` on the owner's
approval, and `TIMETABLE_GLOB` in `tools/check_release_clearance.py` names that
product rather than Darwin's, so `--release fares,timetable` passes the gate
while Darwin's exclusion stays in the record and a release that claims the times
still has to clear the schedule it publishes them from. The OGL line was already
on every page the release serves, so nothing new had to be written for it.
The release was wired to it the same day: every job that holds the feeds fetches
the CIF into `feeds/nwr-schedule/`, the shard build passes `--timetable
feeds/nwr-schedule` and no `--date`, the clearance job declares `--release
fares,timetable`, and the assemble job's journey check refuses a station page with
no journeys instead of one that carries them. What is left is a measurement rather
than a decision: the first real run is the whole-network build in the release's own
shape that the P1 byte-budget finding asks for.
