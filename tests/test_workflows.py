"""A workflow's run block is shell, and a backtick in it is not punctuation.

The SCHEDULE_URL gate failed on 19 October 2026 with `--release: command not
found` and a message reading "declare  again". The gate was right to fire -- no
repository variable of that name is set -- but the sentence meant to say so
named `--release fares` in backticks inside a double-quoted `echo`, so bash ran
the flag as a command and printed the empty substitution in its place. Every line
of shell in a `run:` block here is held to carrying no backtick: `$(...)` is the
same substitution written where it cannot be mistaken for punctuation, and the
message that says what to do about a stopped run is the one thing a reader of
the log has.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# `run:` as a key, with or without the `- ` a list item puts in front of it,
# with any amount of space after the dash, and with the key quoted. YAML allows
# all three spellings and the scan has to read what a workflow may write. The
# value is everything after the colon; a block scalar's value is `|` or `>` with
# an optional chomping or indentation indicator. Flow mappings (`{ run: ... }`)
# are out of scope, because no workflow here writes one and pretending to parse
# YAML is how a scan starts missing lines it thinks it read.
RUN_KEY = re.compile(r"""^(\s*)(?:-\s+)?["']?run["']?\s*:\s*(.*)$""")

SAMPLE = """\
jobs:
  build:
    steps:
      # Outside a run block a backtick is prose, like this `--release fares`.
      - name: gate
        run: |
          # Inside one it is prose on a comment line, like this `--release fares`.
          if [ -z "$SCHEDULE_URL" ]; then
            echo "declare `--release fares` again"
            exit 1
          fi
      - name: tidy
        run: python -m tools.verify --fast
      - run: echo "`whoami`"
      - name: spaced key
        run : |
          echo "no backtick here"
      -  run: echo "`pwd`"
      - "run": echo "`date`"
"""


def shell_lines(text: str) -> list[tuple[int, str]]:
    """Every line of shell a document's `run:` keys hold, with its line number.

    A `run:` whose value is a block scalar holds the lines indented past it; any
    other `run:` is one line of shell. What comes back is what the file says,
    comments and all, because which of it is shell is the caller's question.
    """
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = RUN_KEY.match(lines[index])
        if not match:
            index += 1
            continue
        indent, value = len(match.group(1)), match.group(2)
        if not value.startswith(("|", ">")):
            found.append((index + 1, value))
            index += 1
            continue
        index += 1
        while index < len(lines):
            line = lines[index]
            if line.strip() and len(line) - len(line.lstrip()) <= indent:
                break
            if line.strip():
                found.append((index + 1, line))
            index += 1
    return found


def backticks_in(text: str) -> list[str]:
    """`<line>: <the line>` for each line of shell that carries a backtick.

    A comment line is prose and may carry them; a line of shell may not.
    """
    offenders = []
    for number, line in shell_lines(text):
        if line.lstrip().startswith("#"):
            continue
        if "`" in line:
            offenders.append(f"{number}: {line.strip()}")
    return offenders


class WorkflowShellTest(unittest.TestCase):
    def test_the_scan_reads_a_block_a_one_liner_and_their_comments(self) -> None:
        # The scan is the whole check below, so it is held on a document whose
        # answer is known: two block scalars, one written with a space before
        # its colon, three one-liners, and the three comments a backtick is
        # allowed to sit in.
        self.assertEqual(
            [number for number, _line in shell_lines(SAMPLE)],
            [7, 8, 9, 10, 11, 13, 14, 17, 18, 19],
        )
        self.assertEqual(
            backticks_in(SAMPLE),
            [
                '9: echo "declare `--release fares` again"',
                '14: echo "`whoami`"',
                '18: echo "`pwd`"',
                '19: echo "`date`"',
            ],
        )

    def test_the_scan_reaches_the_gate_whose_message_the_shell_ate(self) -> None:
        # A scan that reads nothing passes the check below by knowing nothing,
        # and the line it has to reach is the one that went wrong: the SCHEDULE_URL
        # gate's own message.
        deploy = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
        self.assertTrue(
            any(
                "no SCHEDULE_URL repository variable is set" in line
                for _number, line in shell_lines(deploy)
            ),
            "the scan did not reach the gate's message: either the scan stopped "
            "short of it or the message has been reworded, and either way this "
            "test's anchor is the line to fix",
        )

    def test_no_run_block_writes_a_backtick(self) -> None:
        workflows = sorted(WORKFLOWS.glob("*.yml"))
        self.assertTrue(workflows, f"there is no workflow to check under {WORKFLOWS}")
        offences = [
            f"{path.name}:{offence}"
            for path in workflows
            for offence in backticks_in(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(
            offences,
            [],
            "a backtick in a run block is command substitution, not punctuation: "
            "the shell runs what it quotes and prints nothing in its place, so the "
            "line says something other than what it was written to say. Write "
            "$(...) if the substitution is wanted, or drop the backticks.\n  "
            + "\n  ".join(offences),
        )


if __name__ == "__main__":
    unittest.main()
