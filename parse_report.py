"""Counters and a line reader shared by the two feed parsers.

The first run against a real feed is the only test that matters, and it happens
once. These counters make that run say what it read, so a wrong answer can be
traced to a file, a line, or an encoding instead of guessed at.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterator

MAX_SKIPPED_EXAMPLES = 5


@dataclass
class ParseReport:
    files_read: list[str] = field(default_factory=list)
    lines_read: int = 0
    records_parsed: int = 0
    records_skipped: int = 0
    encoding_fallback_lines: int = 0
    skipped_examples: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "files": len(self.files_read),
            "lines": self.lines_read,
            "parsed": self.records_parsed,
            "skipped": self.records_skipped,
            "encoding_fallbacks": self.encoding_fallback_lines,
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
        yield line.rstrip("\r\n")


def iter_lines(path: Path, report: ParseReport) -> Iterator[str]:
    with path.open("rb") as handle:
        yield from decode_lines(handle, report)


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

