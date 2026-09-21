# ADR-0012: Damaged input is reported or refused, never guessed at

**Status:** Accepted
**Date:** 21 September 2026

## Context

The real feeds arrive once. Whatever is wrong with them will be discovered on
that day unless it is discovered before, and the failures that matter are not
crashes. A crash is a good day. The failures that matter are the ones that
produce a plausible number: a fare read as zero, a flow keyed on nothing, an
empty database answering every question with "nowhere".

`damage_feed.py` writes deliberately damaged copies of a feed. Each damage is
something a real download does, and each one is asserted against one of two
rules:

- **cosmetic damage changes no answer at all**, and is not reported as a problem
- **structural damage is reported, never guessed at, and never raises**

Fifteen damages: Windows line endings, trailing spaces, blank lines, no final
newline, an accented station name, a byte order mark, lowercase record types,
repeated records, a lowercase file extension, the archive sitting inside its own
folder, half a record removed, a record stubbed to four characters, an empty
file, a stray file, and an archive inside the archive.

## Finding 1: a path that does not exist loaded as an empty feed

`FaresDb().load_feed("feeds/typo")` returned a database with zero stations, zero
flows, and no complaint. The lines are read lazily, and a file whose extension is
not a feed extension is ignored without ever being opened, so nothing looked at
the path at all.

The consequence was narrower than it first looked, and worse for being narrower:
the sweep refuses a missing origin, so it caught the typo. **The audit did not.**
`feed_audit.py` printed `files 0, stations 0, flows 0, rejected 0` — a clean bill
of health for a feed that was never there. The audit is the tool run first on the
day the feeds land, so it was the one tool that could confirm a download that had
not happened.

**Decision.** A path that does not exist raises `FileNotFoundError`. Not because
an error message is nicer, but because an empty feed is a plausible answer and a
missing file is not a question.

## Finding 2: a truncated fares record invented values

Slicing a fixed-width string shorter than the field asking for it returns an
empty string, not an error. A fare record cut before its price read as
`fare_text = ""`, which is not a digit and was rejected — but a record cut mid
price would read a shorter number and be accepted, and a flow record cut before
its id was keyed on `""`.

**Decision.** A fares record shorter than the fields it needs is refused, with
the length and the requirement named. The timetable parser already worked this
way (`_require`), so this brings the two to the same standard rather than
inventing a new one. The check is on the width of the fields actually read, not
the width of the whole published layout, because a real record may be padded or
trimmed beyond what is read.

## What was already sound, and is now pinned

- The CIF reader refuses a record too short for the field it needs, so a four
  character record is rejected rather than read as a location of `WK`.
- Half a CIF record is harmless: the fields that carry a journey sit early in the
  record, so half of one is all padding. A test asserts the journeys are
  unchanged, which is the honest claim, rather than asserting a rejection the
  parser should not make.
- Both parsers now share one reader walk, so they cannot disagree about what a
  feed folder is. A folder holding the downloaded archive now loads, an archive
  inside an archive is named and skipped, and a byte order mark is stripped
  instead of riding into the first field of the first record.

## Consequences

- The stubbed CIF record takes its schedule with it, because a train with one
  stop is not a journey. That is the honest outcome and it is counted, but it
  means one damaged record can remove a whole train: the audit's rejected count
  is the only thing that says so.
- The damage list is fixed, not a fuzzer. A real feed will do something not on
  it. The claim is that the cheap, common shapes are covered, not that the
  parsers are certified against input.
- `feed_audit.py` should be run before anything is believed about a new feed, and
  the rejected count and the skipped files read before the totals. That
  instruction is now in the README's first-run list.
