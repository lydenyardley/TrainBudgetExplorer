"""Check a commit message against the convention in CONTRIBUTING.md.

Usage:
    git log -1 --format=%B | python -m tools.check_commit_message
    python -m tools.check_commit_message <file> [--author "<name> <email>"] ...

Prints one line per problem and exits 1 when any exist. An empty result means
the message passes.

The limits here are measured, not assumed. The subject cap is 80 because the
subject is a display surface: it is what ``git log --oneline`` and a pull
request list show, so a length that buries the description is a real cost. The
longest subject in the history that follows this grammar is 77 characters, and
the mean is 63. There is deliberately no cap on a body line: the closing recap
paragraph of the commits in this repository runs to 209 characters, and a rule
the history breaks on nearly every commit is a rule nobody keeps, which is how
this tool came to reject all 87 of them.

The last rule has no grammar to it. A message may not credit the tool that typed
it, and neither may the author: 310 of the 444 commits this repository had on
21 October 2026 carried ``Generated with Codebuff`` or ``Co-Authored-By: Codebuff``,
and that day's rewrite took them out of the history. A credit is refused rather
than dropped quietly, because leaving one off costs an edit and taking one out
later costs every hash after it. A message that merely mentions a tool is not a
credit: the build's own ``.freebuff/`` note in a commit body is the case this
line test has to let through.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
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

MAX_SUBJECT = 80

SUBJECT = re.compile(
    r"^(?P<type>" + "|".join(TYPES) + r")(\((?P<scope>[a-z0-9-]+)\))?(?P<breaking>!)?: (?P<description>.+)$"
)

#: The tools a commit may not credit. The rule names both because the client
#: and the model behind it write different trailers, and a check that knew only
#: one of them would pass the other.
TOOLS = ("codebuff", "freebuff")

#: The trailer keys that name people, which is the set a credit hides in. The
#: list is closed rather than shaped like `Key: value`, because a body line that
#: opens with a colon -- "Note: the client wrote the trailer" -- is prose and not
#: a footer, and a check that refused it would be saying something it does not
#: mean. A key Git or a generator adds later is one line here.
TRAILER = re.compile(
    r"(?i)^\s*(?P<key>co-authored-by|signed-off-by|authored-by|reviewed-by|"
    r"generated-with|written-with|assisted-by)\s*:\s*(?P<value>.+)$"
)

#: The phrases a generator writes when it is not using a trailer at all.
PHRASE = re.compile(r"(?i)\b(?:generated|written|made|produced|assisted)\s+(?:with|by)\b")

#: A line that opens with the tool's own name is a credit however it continues.
LEADING_NAME = re.compile(r"^\W*(?P<name>" + "|".join(TOOLS) + r")\b", re.IGNORECASE)


def credited_tool(line: str) -> str:
    """The tool a line credits, or an empty string when it credits none.

    Three shapes count, because they are the three a tool has actually written
    here: a trailer whose value names it, a "generated with" phrase, and a line
    that opens with its name. A line that names a tool for any other reason --
    the build output directory, an argument about the client -- is not a credit,
    and refusing it would make the rule say something it was never about.
    """
    lowered = line.lower()
    tool = next((name for name in TOOLS if name in lowered), "")
    if not tool:
        return ""
    trailer = TRAILER.match(line)
    if trailer and any(name in trailer.group("value").lower() for name in TOOLS):
        return tool
    if PHRASE.search(line) or LEADING_NAME.match(line):
        return tool
    return ""


def check(
    message: str, authors: Sequence[str] = (), credits_only: bool = False
) -> list[str]:
    """Return every problem with the message. Empty means it passes.

    `credits_only` is for a push that replaced the history it was based on. Such
    a push makes every commit new to the remote, and the grammar is deliberately
    not retroactive -- 41 commits here predate it -- so a whole-history check
    would fail on the history it is supposed to accept. The credit rule has no
    such history: it was applied backwards on 21 October 2026.
    """
    problems: list[str] = []
    # Git's own cleanup drops the blank lines a message file may open with, so
    # the first *content* line is the subject. Reading line one as the subject
    # instead called such a message empty and stopped there: a message with a
    # fine subject was refused, and the tool said the wrong thing about why.
    lines = message.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    subject = lines[0].strip() if lines else ""

    if not subject and not credits_only:
        return ["the message is empty"]

    # The grammar has an exception for the subjects Git writes; the credit rule
    # does not. A merge commit is still a message a person signs, and returning
    # here would let the one place a trailer is most likely to be pasted through.
    if not credits_only and not subject.startswith(SPECIAL_PREFIXES):
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

        if len(lines) > 1 and lines[1].strip():
            problems.append("line 2 must be blank")

    for number, line in enumerate(lines, 1):
        tool = credited_tool(line)
        if tool:
            problems.append(
                f"line {number} credits {tool.title()}, and a commit's message names "
                "neither the tool that typed it nor a reviewer: keep the why and drop the credit"
            )
    for author in authors:
        tool = next((name for name in TOOLS if name in author.lower()), "")
        if tool:
            problems.append(
                f"the author '{author}' credits {tool.title()}, and a commit's author is a person"
            )

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a commit message against CONTRIBUTING.md.")
    parser.add_argument("message_file", nargs="?", help="the message, or stdin when it is omitted")
    parser.add_argument(
        "--author",
        action="append",
        default=[],
        help="an author or committer identity to check, in the form '<name> <email>'",
    )
    parser.add_argument(
        "--credits-only",
        action="store_true",
        help="check the credit rule and nothing else, for a history a push replaced",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    message = (
        Path(args.message_file).read_text(encoding="utf-8")
        if args.message_file
        else sys.stdin.read()
    )
    problems = check(message, args.author, credits_only=args.credits_only)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
