"""A workflow's run block is shell, and a backtick in it is not punctuation.

It also holds the browser's version to the one file that names it. CI pinned
1.63.0 while a local run took whatever `npx --package playwright` resolved to,
so a green run on a developer's machine was a different browser from the
release's (A7 of the 20 October 2026 poteto audit). The pin lives in
`tests/browser/playwright-version`, both paths read it, and this fails when a
workflow names a version that file does not.

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


#: The one file that names the browser, read by CI and by `tools/verify.py`.
PLAYWRIGHT_VERSION = ROOT / "tests" / "browser" / "playwright-version"
PLAYWRIGHT_PIN = re.compile(r"playwright@([^\s\"']+)")

#: The record of what a share costs and what it is allowed to cost. It states
#: the three numbers the shard job runs on, and the checks below hold the
#: workflow to them (A8 of the 20 October 2026 poteto audit).
PERFORMANCE = ROOT / "docs" / "build-performance-findings.md"


def stated(label: str) -> int:
    """The value the performance record's bound table gives one of its rows."""
    text = PERFORMANCE.read_text(encoding="utf-8")
    match = re.search(rf"^\|\s*{re.escape(label)}\s*\|\s*\**\s*([\d,]+)", text, re.M)
    if match is None:
        raise AssertionError(
            f"docs/build-performance-findings.md states no '{label}' row, so the "
            "check below has nothing to hold the workflow to"
        )
    return int(match.group(1).replace(",", ""))


def shard_job() -> str:
    """The shard job's own text, so a number elsewhere in the file cannot answer."""
    deploy = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
    start = deploy.index("\n  shard:")
    end = deploy.index("\n  assemble:")
    return deploy[start:end]


class BuildBoundTest(unittest.TestCase):
    def test_the_timeout_is_the_one_the_record_states(self) -> None:
        stated_minutes = stated("the shard step's timeout-minutes")
        found = re.findall(r"^\s*timeout-minutes:\s*(\d+)", shard_job(), re.M)
        self.assertEqual(
            found,
            [str(stated_minutes)],
            f"the shard job sets timeout-minutes to {found}, and "
            f"docs/build-performance-findings.md states {stated_minutes}: change "
            "one of them together with the figure that justifies it",
        )

    def test_the_matrix_runs_the_number_of_shares_the_record_states(self) -> None:
        stated_shares = stated("the shard matrix's shares")
        matrix = re.search(r"shard:\s*\[([^\]]+)\]", shard_job())
        self.assertIsNotNone(matrix, "the shard job has no matrix list to count")
        shares = [part.strip() for part in matrix.group(1).split(",") if part.strip()]
        self.assertEqual(
            len(shares),
            stated_shares,
            f"the matrix runs {len(shares)} shares, and "
            f"docs/build-performance-findings.md states {stated_shares}",
        )
        # The build is told the denominator separately, and a share of 1/11 in a
        # twelve-share matrix silently overlaps or skips a slice.
        denominator = re.search(r"SHARD:\s*\$\{\{\s*matrix\.shard\s*\}\}/(\d+)", shard_job())
        self.assertIsNotNone(denominator, "the shard job does not tell the build its share count")
        self.assertEqual(int(denominator.group(1)), stated_shares)

    def test_the_nearing_minute_is_the_one_the_record_states(self) -> None:
        stated_minutes = stated("the minute a share counts as nearing its bound")
        found = re.search(r"NEARING_MINUTES:\s*(\d+)", shard_job())
        self.assertIsNotNone(
            found, "the shard job no longer reports the minute a share counts as nearing its bound"
        )
        self.assertEqual(
            int(found.group(1)),
            stated_minutes,
            f"the workflow warns at {found.group(1)} minutes and "
            f"docs/build-performance-findings.md states {stated_minutes}",
        )


class PlaywrightVersionTest(unittest.TestCase):
    def test_the_file_names_a_version(self) -> None:
        # A file of prose, or an empty one, would let every check below agree
        # on nothing.
        self.assertRegex(
            PLAYWRIGHT_VERSION.read_text(encoding="utf-8").strip(),
            r"^\d+\.\d+\.\d+$",
        )

    def test_the_workflow_reads_the_file(self) -> None:
        # The pin is only one fact if CI reads it: a literal here and a literal
        # in the file are two places, which is what this finding was about.
        deploy = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn(
            'PLAYWRIGHT_VERSION="$(cat tests/browser/playwright-version)"',
            deploy,
            "the browser step does not read tests/browser/playwright-version, so "
            "the version CI installs is a second copy of the pin",
        )

    def test_no_workflow_names_a_version_the_file_does_not(self) -> None:
        version = PLAYWRIGHT_VERSION.read_text(encoding="utf-8").strip()
        disagreeing = [
            f"{path.name}:{number}: playwright@{token}"
            for path in sorted(WORKFLOWS.glob("*.yml"))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            for token in PLAYWRIGHT_PIN.findall(line)
            if token not in (version, "$PLAYWRIGHT_VERSION")
        ]
        self.assertEqual(
            disagreeing,
            [],
            f"tests/browser/playwright-version names {version}, and these name "
            "another browser: "
            + "; ".join(disagreeing),
        )


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


class ServiceDayTest(unittest.TestCase):
    """A share is built for the one day the build job named, never undated.

    The release dropped its --date on 16 October 2026, in the commit that
    published the times from the Open Government Licence timetable, so
    every share's pages had no day to walk their week from: each page indexed
    the feed's whole schedule window (7x the work) and shipped with no day
    control at all. Share 3 of run 39618401726 wrote 78 pages in 139 minutes
    that way, where six shares wrote 458 pages in 108 minutes on 13 October
    with a day. These checks are the reason a flag nobody misses cannot go
    missing again.
    """

    def deploy(self) -> str:
        return (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")

    def test_the_build_job_names_one_day_for_the_whole_run(self) -> None:
        deploy = self.deploy()
        self.assertIn(
            "service_date: ${{ steps.service_day.outputs.value }}",
            deploy,
            "the build job publishes no service_date, so a share has no day to "
            "read and would have to call date itself (and two shares either side "
            "of midnight would claim two days, which the merge refuses)",
        )
        self.assertIn(
            'echo "value=$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"',
            deploy,
            "the build job's service day step does not write a YYYY-MM-DD value, "
            "and a build given any other shape of date refuses to start",
        )

    def test_each_share_is_built_for_that_day(self) -> None:
        job = shard_job()
        self.assertIn(
            "SERVICE_DATE: ${{ needs.build.outputs.service_date }}",
            job,
            "the shard job does not take the day from the build job's output",
        )
        self.assertIn(
            '--date "$SERVICE_DATE"',
            job,
            "the share builds without --date, so every page indexes the feed's "
            "whole schedule window and carries no day control "
            "(docs/build-performance-findings.md, 21 October 2026)",
        )

    def test_a_share_with_no_day_stops_instead_of_indexing_the_feed(self) -> None:
        job = shard_job()
        guard = re.search(r'if \[ -z "\$SERVICE_DATE" \]; then(.*?)\bfi\b', job, re.S)
        self.assertIsNotNone(
            guard, "the share no longer checks that it has a day before building"
        )
        self.assertIn(
            "exit 1",
            guard.group(1),
            "the guard names a missing day and then builds anyway, which is the "
            "run that timed out on 21 October 2026",
        )


if __name__ == "__main__":
    unittest.main()
