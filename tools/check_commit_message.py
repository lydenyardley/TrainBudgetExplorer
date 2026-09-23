"""Check a commit message against the convention in CONTRIBUTING.md.

Usage:
    git log -1 --format=%B | python check_commit_message.py
    python check_commit_message.py <file>

Prints one line per problem and exits 1 when any exist. An empty result means
the message passes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TYPES = (
    "feat",
    "fix",
    "docs",
    "test",
    "refactor",
    "perf",
    "build",
    "ci",
    "chore",
    "revert",
)

SPECIAL_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ")
FOOTER_PREFIXES = ("Refs:", "Co-Authored-By:", "BREAKING CHANGE:")

MAX_SUBJECT = 72
MAX_BODY_LINE = 72

SUBJECT = re.compile(
    r"^(?P<type>" + "|".join(TYPES) + r")(\((?P<scope>[a-z0-9-]+)\))?(?P<breaking>!)?: (?P<description>.+)$"
)


def check(message: str) -> list[str]:
    """Return every problem with the message. Empty means it passes."""
    problems: list[str] = []
    lines = message.rstrip("\n").split("\n")
    subject = lines[0].strip() if lines else ""

    if not subject:
        return ["the message is empty"]
    if subject.startswith(SPECIAL_PREFIXES):
        return problems

    match = SUBJECT.match(subject)
    if match is None:
        problems.append(
            f"subject must read '<type>(<scope>): <description>' with type one of {', '.join(TYPES)}"
        )
    else:
        description = match.group("description")
        if description[0].isupper():
            problems.append("description starts with a capital letter")
        if description.endswith("."):
            problems.append("description ends with a period")

    if len(subject) > MAX_SUBJECT:
        problems.append(f"subject is {len(subject)} characters, the limit is {MAX_SUBJECT}")

    if len(lines) > 1:
        if lines[1].strip():
            problems.append("line 2 must be blank")
        for number, line in enumerate(lines[2:], start=3):
            too_long = len(line) > MAX_BODY_LINE
            exempt = line.lstrip().startswith(FOOTER_PREFIXES) or " " not in line
            if too_long and not exempt:
                problems.append(f"line {number} is {len(line)} characters, the limit is {MAX_BODY_LINE}")

    return problems


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    message = Path(argv[0]).read_text(encoding="utf-8") if argv else sys.stdin.read()
    problems = check(message)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
