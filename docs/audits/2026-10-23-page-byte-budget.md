# The release's bytes: a cluster-priced page, profiled, cut and measured

**Date:** 23 October 2026, updated 24 October 2026
**Raised by:** the release report, which projected **1,940 MB** for 12 shards against
`SITE_BUDGET_MB = 800` and GitHub Pages' 1 GB limit, after `.FSC` cluster flows
(ADR-0075) roughly tripled each page's destination rows.
**Route:** O1 of `docs/open-work.md`, `tools/page_bytes.py`, `build_payload.encode_payload`.

## What was measured

The release's own feed is not on this machine, so pages were built from the local
downloaded feeds, which is the same bracket O1 already quotes. Nothing in the local
build is synthetic: the fares feed is the DTD one with its `.FSC` file, and the
timetable is the DTD feed's 329,008 schedules. The first page was built from
`HEAD` as it stood, every later one from this tree, into a scratch directory that
is not committed.

```
python build_demo_page.py --feed feeds/fares --timetable feeds/timetable \
    --origin GRA --date 2026-10-05 --notices nre,rdg,ogl,accuracy \
    --out _scratch/before/index.html --workers 1
python -m tools.page_bytes _scratch/before/from/grantham/index.html
```

Every `SITE_BUDGET_MB` figure below is the release's own gate, run by
`tools/page_bytes.py`; the gzip figures are over the same file, at `gzip -9`,
which is the compression the host applies.

**The page, before any change.** `tools/page_bytes` reports **1,336 KB total,
1,302 KB payload, 4,690 rows**. The raw file is 1,368,721 bytes; the 35 KB that is
not payload is markup.

**Why the page is this size.** `.FSC` cluster flows price a fare from Grantham to
**2,752 destinations** -- nearly every station the feed knows -- in three fare
lists: 1,666 standard returns, 2,752 outbound singles, 272 Anytime Day Returns.
The places table is therefore almost the whole network on *every* page, and it,
not the rows, is what the site's size was made of.

| part of the payload | bytes before | after the wire pass |
|---|---:|---:|
| `places` (2,752 destinations) | 806,498 | 274,496 |
| fare rows (4,690) | 354,914 | 235,078 |
| `serviceWeek` (8 days) | 105,169 | 70,552 |
| page pool | 42,137 | 50,805 |
| railcard rules, codec, validity | 19,445 | 19,488 |
| everything else | 5,258 | 5,258 |
| **payload** | **1,333,421** | **655,677** |

The largest single item was not data a reader pays for twice. It was **the same
`link` object on 2,752 places, 272,448 bytes** of a 1.3 MB page, because the
page-level pool (ADR-0046) only ever saw the row tables.

## What has been done

### 23 October: the wire form (ADR-0069 amendment)

Each is a wire-format change. Each round-trips through `decode_payload` to the
object the build wrote, field for field and in order, and the page hydrates it in
`page/station/payload.js`.

1. **A place's cells join the page pool**: the same `link` on 2,752 places went
   from 272,448 bytes to 8,256.
2. **A departure option is three values, not three keys**: 189,089 -> 56,726.
3. **A column of repeating words is sent as indices** (`table.dicts`): the route
   code, ticket code, restriction code and wording, `quality`, `isAdvance`,
   `offPeak`, `journeyState` and `destinationType` were worth 162,000 bytes
   between them on that page.
4. **The party price is derived**, not sent: 26,769 -> 0.
5. **The service week is transposed** to one entry per station: 105,169 -> 70,552.
6. **A pooled value has to be worth pooling**: pooling everything that repeated
   *grew* `places`, because an empty list is two bytes and a reference into a
   754-entry pool is four.

**Result: 1,368,721 -> 690,977 bytes, 49.5% off, the same 4,690 rows.** The page
gzips 139,782 -> 128,201, **8.3%**, because the repetition removed was what
deflate was already removing.

### 24 October: what the page carries (ADR-0076, ADR-0069 amendment)

The wire had stopped being the problem. The page was listing 2,752 places of
which the timetable reached 1,027, and carrying each station's own facts
2,930 times over.

1. **A page lists only what a journey reaches** (ADR-0076). Places reachable on
   no day of the eight the page carries are dropped, together with their rows.
   Grantham: **2,752 -> 1,027 places, 4,690 -> 2,092 rows**. The payload carries
   `unreachableDestinationCount` and `maxChanges`, and the page says how many
   places it left out and by which journey limit, so the count above the table
   cannot read as coverage.
2. **The station's own facts travel in the shared station list** (ADR-0069
   amendment). `destinationType`, `destinationTypes` and the six named-site
   lists are on every page that lists the place; they are now
   `window.TBE_STATION_FACTS` in `stations.js`, joined to each row by CRS. That
   document is 124,286 bytes for the feed's 3,436 stations, served once.
3. **A day that repeats the day before travels as `true`**: 4,870 of the
   Grantham page's 8,216 day answers were their predecessor's, and the week went
   from 70,552 to 57,443 bytes.

**Grantham, same feed and day: 690,977 -> 373,396 bytes, 46% off**, gzip
127,158 -> 82,961 (35%). Unlike the wire pass, this one removes content a reader
was being sent: the compressed size falls with the raw one.

## Where a page is now

Twelve stations were built in the release's own shape on 24 October 2026,
`--all-origins --only-stations LIN,IPS,NOR,CBG,KGX,GRA,OXF,PLY,NOT,SHF,NCL,MAN
--date 2026-10-05`, so each page fetches the shared station list and carries no
station facts. Places and rows are read out of each page's own payload.

| station | page | places | rows | unreachable |
|---|---:|---:|---:|---:|
| Linlithgow | 159,870 | 267 | 716 | 2,469 |
| Ipswich | 198,313 | 380 | 987 | 2,352 |
| Normanton | 277,041 | 619 | 1,498 | 2,112 |
| Cambridge | 363,518 | 937 | 2,511 | 1,821 |
| London Kings Cross | 371,949 | 658 | 1,255 | 19 |
| Grantham | 373,396 | 1,027 | 2,092 | 1,725 |
| Oxford | 422,228 | 1,122 | 2,705 | 1,632 |
| Plymouth | 426,613 | 1,270 | 2,760 | 1,478 |
| Nottingham | 512,978 | 1,397 | 3,215 | 1,322 |
| Sheffield | 570,314 | 1,691 | 3,821 | 1,037 |
| Newcastle | 573,788 | 1,480 | 3,152 | 1,252 |
| Manchester Piccadilly | 637,545 | 1,731 | 4,119 | 995 |

**The arithmetic for 1 GB.** 2,930 pages inside 1 GB is **366 KB a page** if the
host's gigabyte is 2^30, **341 KB** if it is 10^9; inside the 800 MB budget it is
**273 KB**. This sample's mean is **407,296 bytes** and its median 397,812, so at
this mean the release is **1,193 MB**: 11% over the host's 1 GiB, 19% over it at
10^9, and 49% over the budget. The sample is a spread of big, medium and small
stations rather than a random draw, so it is a bracket and not a projection: only
a whole-network build prints the release's own mean, and O1 asks for that run. Its
gzip mean is 87,146 bytes, so the release's shard zips should come out near 255 MB
against the 343.5 MiB that raised this audit.

**What a page is made of now**, Manchester Piccadilly, the largest measured
(637,545 bytes, 1,731 places, payload 601,746):

| part | bytes | of the page |
|---|---:|---:|
| the three fare lists' rows (4,119 rows) | 228,075 | 36% |
| `places` (1,731 places) | 185,447 | 29% |
| `serviceWeek` (8 days) | 98,439 | 15% |
| page pool (railcard records, links, changes) | 62,295 | 10% |
| markup | ~35,800 | 6% |
| railcard rules, codec, validity, page facts | ~22,800 | 4% |

Inside `places`, the largest column is **`departures`, 103,614 bytes (16% of the
page)**, then `name` 23,003, `legs` 11,162, `changeStations` 8,067 and `link`
5,193.

## What is still open

**O1. Two pages' worth of levers were taken; the total still breaches both the
budget and the host's limit.** The site is about 1.19 GB on this sample's mean --
11% over 1 GiB, 49% over `SITE_BUDGET_MB` -- so a release would be refused by its
own gate. What closes it is a whole-network run that prints the real mean, and
that run will refuse rather than publish if the mean is where this sample's is.
Nothing in this audit can substitute for it.

**O2. The levers left, measured.** Each is real, each costs something, and each
is a product decision rather than an encoding one.

- **The three fare lists are 36% of a page.** They are three different fares to
  the same place, so one row per place cannot serve the mode filters; the only
  version of this lever that works is fewer modes or fewer places per page.
- **`departures` was 16%, and the estimate was wrong by a factor of seven.**
  Built and measured on the twelve pages on 24 October 2026: an option's two
  minutes as indices into one page-level list, ordered by use, saves **1.24%
  of the raw page and costs 1.91% of its gzip** (mean 5,300 bytes off 407,296,
  and 1,656 bytes on 87,146). A page has 400 to 1,040 distinct minutes, so the
  list is 2 to 4 KB of its own and deflate already encodes a repeated clock in
  a few bits. The estimate here was about 29 KB of Manchester Piccadilly's
  103,614; the measurement is 8,362. **Left, not taken:** 15.5 MB off the
  release's 1,193 MB -- 13% of the 119 MB it is over 1 GiB, 4% of the 393 MB it
  is over the 800 MB budget -- while every reader's transfer grows 1.9%. That is
  a trade somebody has to want rather than an encoding win, so it is filed as a
  decision and the code is unchanged. The figures and the method are in
  `docs/build-performance-findings.md` under "A lever measured and refused".
- **`name` is 4% of a page and is already in the shared station list**, for the
  stations that have a page. Moving it is the same rule as D1 and would leave a
  page whose rows have no names if that document did not arrive.
- **`legs` is 2% and nothing reads it**: a row's train UIDs, written since the
  timetable arrived and read by no file under `page/station/`. Removing it is a
  one-line change and a deleted assertion. It is filed rather than done because a
  train UID is the kind of fact a later feature ("which train") would want.
- **The service week is 15%** and answers "when does it run" for every place the
  page lists. It has already had the run-length that removed a third of it.

**Not a lever.** Compressing or splitting the payload does not help the limit.
GitHub Pages counts the files it serves, not the bytes on the wire, and it already
compresses them. A gzipped payload inside the HTML would break reviewability for
bytes nobody pays for (ADR-0046 rejected it once) and would not move the 1 GB.
Splitting the three fare lists across requests was measured on 21 October 2026
and costs about 100 ms to the first fare (`docs/build-performance-findings.md`),
so it is a slower page for a limit it does not fix.
