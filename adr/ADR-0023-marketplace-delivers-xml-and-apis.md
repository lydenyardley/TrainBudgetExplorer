# ADR-0023: The marketplace delivers XML and APIs; the parsers read fixed-width files

**Status:** Accepted
**Date:** 22 September 2026

## Context

Three products were subscribed to and delivered, and what arrived does not match what
the parsers read:

- **Fare Locations Reference Data v1.3** arrived as a **2.1 MB XML file**
  (`feeds/FareLocationsRefData_v1.3.xml`) holding 7,489 `<FareLocation>` records. Each
  carries an `Nlc`, a `Name`, display names and four flags (`OJPEnabled`, `AttendedTIS`,
  `UnattendedTIS`, `UsedByWct`). **No CRS code. No price.**
- **Knowledgebase Ticket Types** and **Knowledgebase Ticket Restrictions** arrived as
  **API credentials** — a consumer key and secret each — not as files.

The parsers were built in ADR-0005's spirit: layouts taken from the open-source
`pashri/atoc` parser, reading the legacy fixed-width records `ffl`, `loc`, `tty`, `rlc`,
`rcm`. `FaresDb._load_lines` dispatches on the file extension and drops anything it does
not recognise.

## Decision

1. **Record the gap rather than paper over it.** The Rail Data Marketplace's modern
   products are delivered as **XML files and REST APIs**; this project's readers are
   **fixed-width line parsers**. The two do not meet, and nothing about subscribing to
   more of the former will change that.

2. **Do not write new readers speculatively.** The XML cannot substitute for the `loc`
   file, because the join it exists to provide is **NLC → CRS** — fare flows are keyed by
   location code and the page's destinations are keyed by station code — and the XML
   carries no CRS. It also holds no fares. Reading it would add a parser that unblocks
   nothing.

3. **The RSP Data Licence route delivers the format already supported**, which is a
   further argument for it beyond licence terms: its schedule names "**Fares Data**
   comprising of RSP fares files as specified by RSP from time to time in document
   **RSPS5045**", and RSPS5045 is the fixed-width specification the parser was built
   against (ADR-0022). The shortest path to real data is the one that needs no new code.

4. **Credentials belong in the environment, never in the repository.** `.gitignore` now
   carries `.env`, `.env.*` and `*.secret`. No client is written yet, so nothing consumes
   them.

5. **A defect in `feed_audit.py` is reported, not fixed here.** Pointed at a folder whose
   only file is unrecognised, the audit prints `files 0: none` and says nothing about the
   2.1 MB file it ignored — while its own closing line advises reading the unopened files
   first. An operator could read "files 0" as "the download was empty" rather than "no
   reader for this format", which is precisely the failure ADR-0005 warned about when it
   insisted a missing feed must say so. Out of scope for this change.

## Consequences

- **Nothing is unblocked by the three new subscriptions.** They supply names and rules,
  not prices, and not in a shape the code reads. The fares feed under an RSP Data Licence
  remains the only route to the data the page displays.
- **No code was written, and none should be until a real feed arrives.** The parser is
  verified against fixtures in the real record layouts, so the day RSPS5045-format files
  land is a data question rather than a coding one — the property ADR-0005 aimed for and
  has now held twice.
- **The audit's silence is a known weakness** to fix before the next download is judged
  by it.
