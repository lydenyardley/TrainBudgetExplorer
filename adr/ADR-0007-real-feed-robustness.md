# ADR-0007: Survive damaged input, and report what was read

**Status:** Accepted
**Date:** 21 September 2026

## Context

The first run against the real feeds happens once, and it will be the first time
these parsers meet a file they did not generate. The earlier loaders read a whole
file into memory, assumed UTF-8, and accepted any record they could slice, so a
truncated record became a stop with a blank name rather than an error.

An audit over a single folder holding both feeds showed how quiet a wrong answer
can be. The timetable loader classified the fares files as station records,
because a fares record also begins with an update marker. It reported sixteen
stations, five of which did not exist.

## Decision

1. **Stream line by line from a binary handle.** Decode each line as UTF-8, fall
   back to latin-1 for that line only, and count the fallbacks. One bad byte
   costs one line, and a multi-gigabyte feed never lands in memory.
2. **Count everything, on both parsers.** `ParseReport` records the files read,
   the lines read, the records handled, the records rejected, and the encoding
   fallbacks. The numbers are the evidence for every later claim about a feed.
3. **Refuse to guess at a damaged record.** A record whose required field is
   truncated raises, is counted as rejected, and keeps up to five examples with
   the file name and the offending line. A schedule left with fewer than two
   stops is dropped rather than published.
4. **Classify files strictly.** The extension decides when it is known. For an
   extensionless file, a fares record and a station name record are told apart by
   the four spaces that follow a station name record type, and anything ambiguous
   is skipped.
5. **Audit before analysing.** `feed_audit.py` prints what each feed contained and
   where the two disagree: stations with a fare and no train, trains with no fare,
   unresolved TIPLOC codes, the service day patterns, and the STP mix.

## Consequences

- The first real run produces a report, so a wrong answer can be traced to a file,
  a line, or an encoding rather than guessed at.
- Coverage gaps between the two feeds are expected rather than suspicious. A
  station can hold a through fare with no direct train, and a small station can
  hold a train and no through fare.
- The date fields are captured now and interpreted later. Service day filtering
  and STP precedence are the next unit, and the counters make their effect on the
  schedule count visible.
- Rejected records cost a schedule, not a run. A feed that half parses is worse
  than one that fails loudly, so the audit prints the rejected examples first.
