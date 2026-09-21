# ADR-0015: Randomised input, judged on invariants rather than plausibility

**Status:** Accepted
**Date:** 21 September 2026
**Relates to:** ADR-0012 (the fixed damage list), ADR-0013 (the sanity report)

## Context

ADR-0012 tested a fixed list of fifteen damages and said so as its own limit: a
real feed will do something not on the list. `fuzz_feed.py` closes that limit by
mutating a copy of a feed at random — bytes flipped, records reordered, a file
truncated, line endings mixed, a non-UTF-8 byte dropped into a fixed-width record
— and checking what the parser is allowed to do.

A fuzzer is only as good as its invariants, and choosing them is the decision
here. The invariant that matters most is not "the answer is right", because a
damaged feed has no right answer. It is "nothing quietly wrong came out".

## The invariants

1. **Loading does not raise.** A feed file that exists is data, however damaged.
2. **Every line is accounted for.** `parsed + rejected == lines read`. This is
   the most valuable of the five, and it is the one that found a bug.
3. **Nothing invented.** Every value in an answer was read from the file.
4. **The same input gives the same answer twice.**
5. **A rejected record leaves an example**, and the example list respects its cap.

## Finding 1: a rejected record counted as both parsed and rejected

A fare record whose price field was not a number incremented the rejected counter
inside the record handler, and then the line counter counted the line as parsed
because the handler returned normally:

```
lines_read: 29 parsed: 29 skipped: 1
parsed + skipped = 30 vs lines_read 29
skipped examples: []
```

Two things were wrong with that. The totals did not add up, which is exactly what
the audit's headlines are made of. And because the rejection was recorded without
an example, `feed_audit.py` would print "rejected 1" with nothing to look at —
in the tool that is read first on a real feed, and where ADR-0012 says to read the
rejected count *before* the totals.

**Decision.** The handler raises, and the line counter classifies the line once:

```
lines 29 parsed 28 skipped 1
accounted for: True
example: ["bad.ffl: 'AT0000001SDRabc       ' (fare 'abc' is not a number)"]
```

## Finding 2: the fuzzer was asserting plausibility, not honesty

Early rounds failed with `an answer has a station code of 'E$'`. That is not a
parser bug. A damaged file can really contain `E$` in a station code field, and
reporting it is the correct behaviour — inventing a tidier value would be worse.

**Decision.** The fuzzer asserts **provenance**: every station code and station
name in an answer must appear in the feed's bytes. Whether a value is *plausible*
is the sanity report's question (ADR-0013), not the parser's, and a fuzzer that
demands plausible output from deliberately implausible input is testing the wrong
program.

## Finding 3: the provenance check was wrong before the parser was

A round failed with `station name 'PETERØOROUGH' is not in the feed`. It was in
the feed. `str.lower()` maps the latin-1 byte `0xD8` (`Ø`) to `0xF8` (`ø`), so
lowercasing the value and then looking for its bytes missed the bytes that were
actually there. The check now looks for the value and its folded form, in raw and
folded bytes, so a value is never reported absent on account of its case.

## Finding 4: a mutation that mostly did nothing

`insert_an_accent` replaced `NOTTINGHAM`, so on the rounds where the randomly
chosen file was not the one containing it, the mutation changed nothing and the
round tested the clean feed over and over. A test now asserts that every named
mutation alters the bytes, and the mutation became
`insert_a_non_utf8_byte`, which drops a byte into any record and therefore
exercises the encoding fallback on every round it is chosen.

## Consequences

- 900 rounds across six seeds pass on the synthetic feeds, and 13 to 19 rounds in
  every 200 reject at least one record, which is the fuzzer biting rather than
  passing trivially.
- A failure names the seed, the round, and the mutations, and `--keep` writes the
  damaged feed, so a finding is reproducible rather than a story.
- **Scope, honestly:** the byte-level rounds fuzz the fares feed. The timetable's
  invariants are that a schedule has two or more stops and a journey has a
  duration, applied to whatever loaded; record-level timetable damage stays with
  ADR-0012's stubbed and truncated cases.
- The first-run list gains one more command: `fuzz_feed.py --feed feeds/fares
  --rounds 500`. It is cheap, and it is the only thing that will exercise the real
  feed's encoding and record shapes against a parser written without them.
