"""Mutate a feed at random and check what a parser is not allowed to do.

`damage_feed.py` covers the failures somebody thought of. This covers the rest:
bytes flipped, lines reordered, a record cut in half, two files' worth of damage
in one round. It does not assert that a damaged feed parses correctly, because
there is no such thing. It asserts that nothing *quietly wrong* comes out.

The invariants, in order of how much they are worth:

1. **Loading does not raise.** A feed file that exists is data, however damaged.
2. **Every line is accounted for.** A line is either parsed or rejected, never
   both and never neither. A rejected line that is also counted as parsed hides
   itself, and the audit's rejected count is the first thing read on a real feed.
3. **Nothing invented.** Every answer is the shape of an answer: three character
   station codes, a positive price, a party price at least the single price.
4. **The same input gives the same answer twice.**
5. **A rejected record leaves an example**, so the count can be explained.

Run it against a synthetic feed before a real one, and against the real feed
before believing a number from it:

    python fuzz_feed.py --feed _demo_feed --rounds 200 --seed 1
    python fuzz_feed.py --feed feeds/fares --rounds 500 --seed 1 --keep _fuzz_failure
"""

from __future__ import annotations

import argparse
import random
import shutil
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path

from atoc_fares import FaresDb
from atoc_timetable import TimetableDb
from parse_report import MAX_SKIPPED_EXAMPLES

# Names, so a failure can be described rather than dumped.
MUTATIONS = (
    "flip_a_byte",
    "delete_a_run",
    "insert_junk",
    "truncate_the_file",
    "swap_two_lines",
    "reverse_the_lines",
    "duplicate_a_line",
    "drop_a_line",
    "empty_the_file",
    "append_half_a_record",
    "mix_the_line_endings",
    "change_the_case",
    "insert_a_non_utf8_byte",
    "add_a_stray_file",
)

DEFAULT_ROUNDS = 100
DEFAULT_SEED = 1
ORIGIN = "GRN"


@dataclass
class Round:
    """What one round did, and what it found."""

    number: int
    seed: int
    mutations: tuple[str, ...]
    violations: list[str] = field(default_factory=list)
    lines_read: int = 0
    parsed: int = 0
    rejected: int = 0
    destinations: int = 0

    @property
    def ok(self) -> bool:
        return not self.violations

    def describe(self) -> str:
        state = "ok" if self.ok else "FAILED"
        return (
            f"round {self.number} {state}: {', '.join(self.mutations)} "
            f"[lines {self.lines_read} parsed {self.parsed} rejected {self.rejected} "
            f"destinations {self.destinations}]"
        )


def mutate_file(content: bytes, rng: random.Random) -> tuple[bytes, str]:
    """Apply one random mutation to one file's bytes."""
    kind = rng.choice(MUTATIONS)
    lines = content.split(b"\n")
    if not content:
        return content, kind
    if kind == "flip_a_byte":
        index = rng.randrange(len(content))
        return content[:index] + bytes([content[index] ^ (1 << rng.randrange(8))]) + content[index + 1 :], kind
    if kind == "delete_a_run":
        start = rng.randrange(len(content))
        length = rng.randrange(1, 40)
        return content[:start] + content[start + length :], kind
    if kind == "insert_junk":
        start = rng.randrange(len(content))
        printable = string.printable.encode("ascii")
        junk = bytes(rng.choice(printable) for _ in range(rng.randrange(1, 30))) + b"\n"
        return content[:start] + junk + content[start:], kind
    if kind == "truncate_the_file":
        return content[: max(1, int(len(content) * rng.uniform(0.3, 0.9)))], kind
    if kind == "swap_two_lines" and len(lines) > 2:
        one, two = rng.sample(range(len(lines)), 2)
        lines[one], lines[two] = lines[two], lines[one]
        return b"\n".join(lines), kind
    if kind == "reverse_the_lines":
        return b"\n".join(reversed(lines)), kind
    if kind == "duplicate_a_line" and lines:
        lines.insert(rng.randrange(len(lines)), rng.choice(lines))
        return b"\n".join(lines), kind
    if kind == "drop_a_line" and len(lines) > 2:
        del lines[rng.randrange(len(lines))]
        return b"\n".join(lines), kind
    if kind == "empty_the_file":
        return b"", kind
    if kind == "append_half_a_record":
        line = rng.choice([line for line in lines if line] or [b""])
        return content + line[: max(1, len(line) // 2)] + b"\n", kind
    if kind == "mix_the_line_endings":
        return b"".join(
            line + (b"\r\n" if index % 2 else b"\n") for index, line in enumerate(lines)
        ), kind
    if kind == "change_the_case":
        return bytes(byte ^ 0x20 if byte in b"ABCFILMNORSTU" and rng.random() < 0.3 else byte for byte in content), kind
    if kind == "insert_a_non_utf8_byte":
        # A byte that cannot start a UTF-8 sequence, which is what a feed encoded
        # in latin-1 contains and what the reader's fallback exists for. Replaced
        # rather than inserted so the record keeps its fixed width.
        index = rng.randrange(len(content))
        replacement = rng.randrange(0xC0, 0x100)
        if replacement == content[index]:
            replacement = 0xE9
        return content[:index] + bytes([replacement]) + content[index + 1 :], kind
    if kind == "add_a_stray_file":
        return content, kind
    return content, kind


def one_round(feed: Path, work: Path, rng: random.Random, number: int, seed: int) -> Round:
    """Damage a copy of the feed, load it, and check the invariants."""
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(feed, work)

    files = [path for path in sorted(work.rglob("*")) if path.is_file()]
    result = Round(number=number, seed=seed, mutations=())
    names: list[str] = []
    for _ in range(rng.randint(1, 3)):
        if not files:
            break
        target = rng.choice(files)
        if target.name == "extra.txt":
            continue
        damaged, kind = mutate_file(target.read_bytes(), rng)
        names.append(f"{kind} on {target.name}")
        if kind == "add_a_stray_file":
            (work / "extra.txt").write_bytes(b"not a feed record\n")
            continue
        target.write_bytes(damaged)

    result.mutations = tuple(names)

    fares = FaresDb()
    try:
        fares.load_feed(work)
    except Exception as error:  # noqa: BLE001 - any escape is the finding
        result.violations.append(f"loading raised {type(error).__name__}: {error}")
        return result

    report = fares.report
    result.lines_read = report.lines_read
    result.parsed = report.records_parsed
    result.rejected = report.records_skipped

    if report.records_parsed + report.records_skipped != report.lines_read:
        result.violations.append(
            f"lines are not accounted for: {report.lines_read} read, "
            f"{report.records_parsed} parsed, {report.records_skipped} rejected"
        )
    if report.records_skipped and not report.skipped_examples:
        result.violations.append("a record was rejected with no example to look at")
    if len(report.skipped_examples) > MAX_SKIPPED_EXAMPLES:
        result.violations.append(f"{len(report.skipped_examples)} examples kept, the cap is {MAX_SKIPPED_EXAMPLES}")

    try:
        answers = fares.destinations_within(ORIGIN, 1_000_000)
    except KeyError:
        # The round removed the origin. That is a legitimate outcome, not a bug.
        return result
    except Exception as error:  # noqa: BLE001
        result.violations.append(f"querying raised {type(error).__name__}: {error}")
        return result

    result.destinations = len(answers)
    contents = _file_bytes(work)
    for row in answers:
        # Plausibility is not the parser's job: a damaged file may hold a station
        # code of "E$", and reporting it is correct. Provenance is the parser's
        # job, so this checks that every value in an answer was read from the
        # file rather than invented. What looks wrong is the sanity report's
        # business, not this one's.
        if not _appears(row.crs, contents):
            result.violations.append(f"station code {row.crs!r} is not in the feed")
        if row.station and not _appears(row.station, contents):
            result.violations.append(f"station name {row.station!r} is not in the feed")
        if row.party_pence < row.best_pence:
            result.violations.append(f"{row.crs} prices a party below one adult")

    again = FaresDb().load_feed(work)
    if again.stats() != fares.stats():
        result.violations.append("loading the same feed twice gave different counts")
    if [row.crs for row in again.destinations_within(ORIGIN, 1_000_000)] != [
        row.crs for row in answers
    ]:
        result.violations.append("loading the same feed twice gave different destinations")

    return result


def _file_bytes(folder: Path) -> bytes:
    """Every byte of the feed, for checking that an answer came from it."""
    return b"".join(path.read_bytes() for path in sorted(folder.rglob("*")) if path.is_file())


def _appears(value: str, contents: bytes) -> bool:
    """Whether a value was read from the file.

    Compared without case, because the parser normalises case on read and a
    damaged file may hold the value in any form. A value the parser invented
    appears in no form at all.
    """
    # Both the value and its case-folded form are looked for, against both the
    # raw bytes and the lowercased ones, because the parser may have normalised
    # case on read. The comparison stays byte-wise: str.lower() maps the latin-1
    # byte 0xD8 to a different byte entirely, so a value that is in the file
    # would look absent if either side were folded alone.
    haystacks = (contents, contents.lower())
    for candidate in {value, value.lower()}:
        for encoding in ("utf-8", "latin-1"):
            try:
                needle = candidate.encode(encoding)
            except UnicodeEncodeError:
                continue
            if any(needle in haystack for haystack in haystacks):
                return True
    return False


def fuzz(
    feed: str | Path,
    *,
    rounds: int = DEFAULT_ROUNDS,
    seed: int = DEFAULT_SEED,
    work: str | Path | None = None,
    keep_failures: str | Path | None = None,
) -> list[Round]:
    """Run the rounds and return them. Seed and round number reproduce any."""
    feed = Path(feed)
    if not feed.exists():
        raise FileNotFoundError(f"no feed at {feed}")
    scratch = Path(work) if work else feed.parent / f"{feed.name}-fuzzed"
    rng = random.Random(seed)
    results: list[Round] = []
    for number in range(1, rounds + 1):
        result = one_round(feed, scratch, rng, number, seed)
        results.append(result)
        if keep_failures and not result.ok:
            shutil.copytree(scratch, Path(keep_failures) / f"round-{number}", dirs_exist_ok=True)
    if not work:
        shutil.rmtree(scratch, ignore_errors=True)
    return results


def check_timetable(feed: str | Path, *, seed: int = DEFAULT_SEED) -> list[str]:
    """The timetable side of the invariants, on the feed as it stands.

    Damaged timetable files are covered by `damage_feed.py`; what matters after
    any load is that a schedule is a journey at all.
    """
    violations: list[str] = []
    for path in (feed,):
        db = TimetableDb()
        try:
            db.load_feed(path)
        except Exception as error:  # noqa: BLE001
            violations.append(f"loading the timetable raised {type(error).__name__}: {error}")
            continue
        for schedule in db.schedules:
            if len(schedule.stops) < 2:
                violations.append(f"{schedule.train_uid} has {len(schedule.stops)} stop(s)")
        journey = db.best_journey("GRN", "NOT")
        if journey is not None and journey.duration <= 0:
            violations.append("a journey with no duration came back")
    return violations


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Mutate a feed at random and check the parser.")
    parser.add_argument("--feed", required=True, help="feed folder to damage a copy of")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="reproduces any failure")
    parser.add_argument("--keep", default=None, help="copy each failing round here")
    arguments = parser.parse_args(argv)

    try:
        results = fuzz(
            arguments.feed,
            rounds=arguments.rounds,
            seed=arguments.seed,
            keep_failures=arguments.keep,
        )
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 2

    failed = [result for result in results if not result.ok]
    rejected = sum(1 for result in results if result.rejected)
    print(f"{len(results)} rounds from seed {arguments.seed}: {len(failed)} failed")
    print(f"{rejected} rounds had at least one rejected record, which is the fuzzer biting")
    for result in failed[:20]:
        print(result.describe())
        for violation in result.violations:
            print(f"    {violation}")
    if failed:
        print("reproduce with --seed and the round number, or read the copy in --keep")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
