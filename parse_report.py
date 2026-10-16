"""Counters and a line reader shared by the two feed parsers.

The first run against a real feed is the only test that matters, and it happens
once. These counters make that run say what it read, so a wrong answer can be
traced to a file, a line, or an encoding instead of guessed at.
"""

from __future__ import annotations

import gzip
import itertools
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Callable, Iterator

MAX_SKIPPED_EXAMPLES = 5
ARCHIVE_SUFFIXES = (".zip",)
GZIP_SUFFIXES = (".gz",)


@dataclass
class ParseReport:
    files_read: list[str] = field(default_factory=list)
    lines_read: int = 0
    records_parsed: int = 0
    records_skipped: int = 0
    encoding_fallback_lines: int = 0
    skipped_examples: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    # A classification source that could not be read: the ONS types workbook or
    # a sourced destination facet. Counted apart from skipped feed files
    # because their loss is silent on the page -- the filters keep working with
    # fewer chips and only the source label hints at it (audit A5).
    # --require-classification turns these into a refusal.
    classification_failures: list[str] = field(default_factory=list)
    # Reviewed settlement-fallback codes the feed does not carry: a list going
    # stale, not a file left unread, so it has its own channel rather than
    # riding in skipped_files where an audit would report it as an unopened
    # source. --require-live-reviewed-codes turns these into a refusal (audit
    # A7), which is the point: a dead code costs nothing at runtime, so
    # nothing else would ever notice one arriving.
    reviewed_codes_absent: list[str] = field(default_factory=list)
    # Reviewed settlement-fallback codes for a station the ONS workbook already
    # names. The code resolves and the class never applies, so nothing looks
    # wrong until the name match misses and the reviewed class lands.
    # --require-live-reviewed-codes turns these into a refusal too.
    reviewed_codes_redundant: list[str] = field(default_factory=list)
    #: Reviewed railcard codes the feed does not carry. Its own channel for
    #: the reason the reviewed station lists have one: the code is intersected
    #: away before it is applied, so a stale entry changes nothing at runtime
    #: and only silence would let the list rot unnoticed.
    reviewed_railcard_codes_absent: list[str] = field(default_factory=list)
    # CIF schedules a whole-CIF feed carries that no passenger can take:
    # freight, trip, bus, ship, empty coaching stock and parcels moves. The DTD
    # timetable product is filtered to passenger services before it is
    # published, so nothing had to count these; Network Rail's own CIF is not
    # filtered, and a schedule the loader drops is one no page can reach a
    # journey through -- the same silence as a feed that never carried it.
    non_passenger_schedules: int = 0

    def skip_file(self, message: str) -> None:
        """Record a whole file the loader chose not to read.

        An archive inside an archive is not a damaged record, so it does not
        belong in the record counters. Saying nothing about it would be worse
        than either: a compressed file decoded as text yields thousands of
        nonsense records that look like data.
        """
        self.skipped_files.append(message)

    def skip_classification(self, message: str) -> None:
        """Record a classification source that could not be read.

        It is still a skipped file, so feed_audit keeps seeing it; the second
        list is what a build reads when it must decide whether the page can
        claim sourced classification.
        """
        self.skipped_files.append(message)
        self.classification_failures.append(message)

    def summary(self) -> dict[str, int]:
        return {
            "files": len(self.files_read),
            "lines": self.lines_read,
            "parsed": self.records_parsed,
            "skipped": self.records_skipped,
            "encoding_fallbacks": self.encoding_fallback_lines,
            "skipped_files": len(self.skipped_files),
            "non_passenger_schedules": self.non_passenger_schedules,
        }


def decode_lines(handle: BinaryIO, report: ParseReport) -> Iterator[str]:
    """Yield decoded lines from a binary handle.

    Decoding happens per line, so one bad byte costs one line rather than a whole
    file, and a multi-gigabyte feed never lands in memory at once.
    """
    for raw in handle:
        try:
            line = raw.decode("utf-8")
        except UnicodeDecodeError:
            report.encoding_fallback_lines += 1
            line = raw.decode("latin-1")
        # A byte order mark is not whitespace to str.strip, so it would ride
        # along in the first field of the first record of the file.
        if line.startswith("\ufeff"):
            line = line[1:]
        yield line.rstrip("\r\n")


def iter_lines(path: Path, report: ParseReport) -> Iterator[str]:
    with path.open("rb") as handle:
        yield from decode_lines(handle, report)


def read_feed_files(
    path: str | Path,
    report: ParseReport,
    consume: Callable[[str, Iterator[str]], None],
) -> None:
    """Hand every feed file to consume, whether it arrived as a folder or a zip.

    A real download is often a folder holding the archive, and occasionally an
    archive holding another one. Both are handled here so the two parsers cannot
    disagree about what a feed folder is.

    ``consume`` is called while the file is still open, because the lines are
    streamed rather than collected: a feed file can be tens of megabytes, and
    holding one in memory is what this design exists to avoid.
    """
    path = Path(path)
    if not path.exists():
        # A path that is not there must say so. An empty feed answers every
        # question with "nowhere" and looks exactly like a real answer.
        raise FileNotFoundError(f"no feed at {path}")
    if path.is_dir():
        for child in sorted(path.iterdir()):
            if not child.is_file():
                continue
            if child.suffix.lower() in ARCHIVE_SUFFIXES:
                _read_archive(child, report, consume)
                continue
            if child.suffix.lower() in GZIP_SUFFIXES:
                _read_gzip(child, report, consume)
                continue
            consume(child.name, iter_lines(child, report))
        return
    if path.suffix.lower() in ARCHIVE_SUFFIXES:
        _read_archive(path, report, consume)
        return
    if path.suffix.lower() in GZIP_SUFFIXES:
        _read_gzip(path, report, consume)
        return
    consume(path.name, iter_lines(path, report))


def _read_archive(
    path: Path,
    report: ParseReport,
    consume: Callable[[str, Iterator[str]], None],
) -> None:
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if name.endswith("/"):
                continue
            if Path(name).suffix.lower() in ARCHIVE_SUFFIXES:
                report.skip_file(f"{path.name}: {name} is an archive inside an archive, not opened")
                continue
            with archive.open(name) as handle:
                if Path(name).suffix.lower() in GZIP_SUFFIXES:
                    _gzip_feed(handle, name, report, consume)
                    continue
                consume(name, decode_lines(handle, report))


def _without_gzip(name: str) -> str:
    """The name a feed file would have if it were not compressed.

    The name is what the loader classifies a file by, and a whole-CIF feed
    arrives as ``...toc-full.CIF.gz``: the suffix saying what it holds sits
    under the one saying how it was compressed, so a name that keeps both
    reaches the loader as a file of unknown kind.
    """
    lowered = name.lower()
    for suffix in GZIP_SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _read_gzip(
    path: Path,
    report: ParseReport,
    consume: Callable[[str, Iterator[str]], None],
) -> None:
    with path.open("rb") as handle:
        _gzip_feed(handle, path.name, report, consume)


def _gzip_feed(
    handle: BinaryIO,
    name: str,
    report: ParseReport,
    consume: Callable[[str, Iterator[str]], None],
) -> None:
    """Stream a compressed feed file as if it had not been compressed.

    Damage is raised, not skipped. A gzip that cannot be read is a download
    that failed, and a skipped download answers every question the feed is
    asked with the answer an empty one gives -- which is how a page comes to
    say "nowhere" with confidence.
    """
    try:
        with gzip.GzipFile(fileobj=handle) as stream:
            consume(_without_gzip(name), decode_lines(stream, report))
    except (OSError, EOFError) as error:
        raise ValueError(f"{name} is not readable as gzip ({type(error).__name__}: {error})") from error


def peek(lines: Iterator[str]) -> tuple[str | None, Iterator[str]]:
    """Return the first non-blank line and an iterator that still starts with it."""
    for line in lines:
        if line.strip():
            return line, itertools.chain([line], lines)
    return None, iter(())


def count(
    lines: Iterator[str],
    handler,
    report: ParseReport,
    name: str,
    *,
    finish=None,
) -> None:
    """Run a per-line handler, counting lines and surviving malformed records."""
    for line in lines:
        if not line.strip():
            continue
        report.lines_read += 1
        try:
            handler(line)
            report.records_parsed += 1
        except (ValueError, IndexError) as error:
            report.records_skipped += 1
            if len(report.skipped_examples) < MAX_SKIPPED_EXAMPLES:
                report.skipped_examples.append(f"{name}: {line[:40]!r} ({error})")
    if finish is not None:
        finish()

