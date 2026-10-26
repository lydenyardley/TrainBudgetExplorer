"""A workflow's run block is shell, and a backtick in it is not punctuation.

It also holds every path the workflows name to the tree that holds it, because a
cached key built on a path that is not there is a key that silently stops telling
two commits apart.

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
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTIONS = ROOT / ".github" / "actions"

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


#: The folders a run writes for itself: build output, the downloaded feeds, the
#: artifact a share hands to the merge, and the review folder the facet workflow
#: uploads. A path under one of these need not be in the tree, because the run
#: that names it is the run that creates it -- and a check that demanded one
#: would be red on a clean clone.
GENERATED_DIRS = (
    "feeds/",
    "_site/",
    "_demo_site/",
    "_demo_feed/",
    "_demo_kb/",
    "_shape_site/",
    "_shape_feed/",
    "_stations/",
    "_cache/",
    ".feed-state/",
    "facet-review/",
    "node_modules/",
)

#: The top-level folders the repository itself supplies. A token that starts with
#: one of these is a claim about this tree.
REPO_DIRS = (
    "trainbudget/",
    "tests/",
    "tools/",
    "page/",
    "docs/",
    "adr/",
    "licences/",
    "reference-data/",
    "assets/",
    ".github/",
    ".githooks/",
)

#: The extensions a path in a workflow ends in when it names a file of this tree.
REPO_SUFFIXES = (
    "py", "md", "json", "cjs", "js", "css", "svg", "toml", "yml", "yaml", "bat", "txt",
)

TOKEN = re.compile(r"[A-Za-z0-9_.\-/]+")
HASHED = re.compile(r"hashFiles\((?P<args>[^)]*)\)", re.S)


def _hashed_claims(text: str) -> list[tuple[int, str]]:
    """Every argument of every `hashFiles` call, which is always a path.

    This is the one place a bare `build_pool.py` is a claim rather than prose: it
    is what the call hashes, and a path that is not there hashes to the empty
    string. Read over the whole document rather than line by line, because the
    arguments may be wrapped and a scan that only read one line would miss the
    ones that are.
    """
    found: list[tuple[int, str]] = []
    for match in HASHED.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        for raw in match.group("args").split(","):
            token = raw.strip().strip("`'\"")
            if not token or "{{" in token or any(character in token for character in "*?$"):
                continue
            found.append((line, token))
    return found


def named_paths(text: str) -> list[tuple[int, str]]:
    """Every repository path a document names, with the line that names it.

    Two readings, because a workflow writes a path in two ways. Inside a
    `hashFiles` call it is always a path, bare or folded. Everywhere else it is a
    token with a folder in it -- `tools/verify.py`, `reference-data/` -- and a
    comment line is prose, which is where the bare `build_pool.py` mentions live.

    What a workflow may not do is name a path the tree does not hold, because
    `hashFiles` answers an empty string for one that is missing and a cache key
    built on it stops telling two commits apart without saying anything.
    """
    found: list[tuple[int, str]] = _hashed_claims(text)
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for raw in TOKEN.findall(line):
            token = raw.strip("`'\"(),:;")
            if "/" not in token or token.startswith(("http", "$", "/", "./", "../", "-")):
                continue
            if any(character in token for character in "*?[]=@:{}"):
                continue
            if not (token.startswith(REPO_DIRS) or token.rsplit(".", 1)[-1] in REPO_SUFFIXES):
                continue
            found.append((number, token))
    # A path inside `hashFiles` is read twice when it also has a folder in it, and
    # a defect reported twice reads as two defects.
    return list(dict.fromkeys(found))


def missing_paths(documents: dict[str, str]) -> list[str]:
    """`<file>:<line>: <the path>` for every path a document names that is not there.

    `documents` maps a name to the document's text rather than a path to its text,
    so a test can hand the rule a workflow it wrote instead of one on disk.
    """
    missing: list[str] = []
    for name, text in documents.items():
        for number, token in named_paths(text):
            if token.startswith(GENERATED_DIRS) or (ROOT / token).exists():
                continue
            missing.append(f"{name}:{number}: {token}")
    return missing


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
        denominator = re.search(r"--shard \"\$\{\{\s*matrix\.shard\s*\}\}/(\d+)\"", shard_job())
        self.assertIsNotNone(denominator, "the shard job does not tell the build its share count")
        self.assertEqual(int(denominator.group(1)), stated_shares)

    def test_the_nearing_minute_is_the_one_the_record_states(self) -> None:
        from tools.release import share

        stated_minutes = stated("the minute a share counts as nearing its bound")
        self.assertEqual(
            share.NEARING_MINUTES,
            stated_minutes,
            f"tools/release/share.py warns at {share.NEARING_MINUTES} minutes and "
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

    def test_the_scan_reaches_a_block_of_the_release_workflow(self) -> None:
        # A scan that reads nothing passes the check below by knowing nothing,
        # so it has to reach a line inside one of deploy.yml's block scalars.
        deploy = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn(
            "python -m tools.verify --fast",
            [line.strip() for _number, line in shell_lines(deploy)],
            "the scan did not reach the verify step's block: either the scan stopped "
            "short of it or the step changed, and either way this anchor is the line to fix",
        )

    def test_no_run_block_writes_a_backtick(self) -> None:
        workflows = sorted(WORKFLOWS.glob("*.yml")) + sorted(ACTIONS.glob("*/action.yml"))
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


class LocalActionTest(unittest.TestCase):
    def test_every_local_action_a_workflow_uses_is_tracked(self) -> None:
        # actionlint skips a local action it cannot find, and .gitignore's
        # feeds/ rule once swallowed one named feeds: the workflow would have
        # failed on its first run with every check here green.
        used = sorted(
            {
                match.group(1)
                for path in WORKFLOWS.glob("*.yml")
                for match in re.finditer(r"uses:\s*\./(\S+)", path.read_text(encoding="utf-8"))
            }
        )
        self.assertTrue(used, "no workflow uses a local action, so this check reads nothing")
        tracked = subprocess.run(
            ["git", "ls-files", "--others", "--cached", "--exclude-standard", ".github/actions"],
            cwd=ROOT, capture_output=True, text=True,
        ).stdout.split()
        for action in used:
            with self.subTest(action=action):
                self.assertIn(f"{action}/action.yml", tracked, f"{action}/action.yml is missing or ignored by git")


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
        from tools.release import share

        self.assertIn(
            '--date "${{ needs.build.outputs.service_date }}"',
            shard_job(),
            "the shard job does not take the day from the build job's output",
        )
        built = share.command("1/12", "2026-10-22", 4)
        self.assertEqual(
            built[built.index("--date") + 1],
            "2026-10-22",
            "the share builds without --date, so every page indexes the feed's "
            "whole schedule window and carries no day control "
            "(docs/build-performance-findings.md, 21 October 2026)",
        )

    def test_a_share_with_no_day_stops_instead_of_indexing_the_feed(self) -> None:
        import contextlib
        import io
        from unittest import mock

        from tools.release import share

        with mock.patch.object(share.subprocess, "run") as build, contextlib.redirect_stdout(io.StringIO()):
            code = share.main(["--shard", "1/12", "--date", ""])
        self.assertEqual(code, 1)
        build.assert_not_called()

class WorkflowPathTest(unittest.TestCase):
    """A path a workflow names is a path this tree has to hold.

    Moving the modules into `trainbudget/` left `deploy.yml`'s feed-cache key
    hashing `build_demo_page.py`, `atoc_fares.py` and `page_templates.py` -- three
    paths that no longer existed. `hashFiles` answers the empty string for a path
    that is not there, so the key was still well formed, every commit hashed the
    same, and nothing said so. A missing script in a `run:` block is at least red
    on the next push; a missing path in a cache key is silent, which is why this
    check exists and why it runs in `--fast`.
    """

    def documents(self) -> dict[str, str]:
        paths = sorted(
            [path for pattern in ("*.yml", "*.yaml") for path in WORKFLOWS.glob(pattern)]
            + [path for pattern in ("*.yml", "*.yaml") for path in ACTIONS.rglob(pattern)]
        )
        return {
            path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
            for path in paths
        }

    def test_every_path_a_workflow_names_is_there(self) -> None:
        missing = missing_paths(self.documents())
        self.assertEqual(
            missing,
            [],
            "these workflows name a path this tree does not hold -- a moved module "
            "leaves `hashFiles` answering an empty string, so the cache key keeps "
            "working and stops meaning anything:\n" + "\n".join(missing),
        )

    def test_the_scan_reads_the_workflows_it_claims_to_read(self) -> None:
        # A scan that found nothing would pass forever. It has to have read every
        # workflow and the action, and to have found the paths they all use.
        documents = self.documents()
        self.assertGreaterEqual(len(documents), 4, f"only {len(documents)} workflow(s) found")
        found = {token for text in documents.values() for _, token in named_paths(text)}
        for path in ("tests/browser/playwright-version", "reference-data/destination-facets.json"):
            with self.subTest(path=path):
                self.assertIn(path, found, f"the scan did not find {path}, so it is not reading what it says")
        # The three paths the feed-cache key hashes: the check's own reason for
        # existing, named here so a second move fails on the path rather than on
        # a cache key nobody reads.
        hashed = {
            token
            for _, token in named_paths(documents[".github/workflows/deploy.yml"])
        }
        for path in (
            "trainbudget/build/build_demo_page.py",
            "trainbudget/fares/atoc_fares.py",
            "trainbudget/build/page_templates.py",
        ):
            with self.subTest(hashed=path):
                self.assertIn(path, hashed, "the feed-cache key no longer hashes this path")

    def test_a_path_that_is_not_there_is_reported(self) -> None:
        # The rule, on the shape of the defect it was written for, and on the two
        # cases it must not fire on: a generated folder, and a glob.
        missing = missing_paths({
            "sample.yml": (
                "      key: cache-${{ hashFiles('trainbudget/build/gone.py') }}\n"
                "      path: _site/\n"
                "      run: python -m unittest discover -s tests -p 'test_*.py'\n"
            )
        })
        self.assertEqual(missing, ["sample.yml:1: trainbudget/build/gone.py"])


class KnowledgebaseFeedTest(unittest.TestCase):
    """The shards that build pages from the Knowledgebase feeds cannot lack them.

    Run 39798397862 (22 October 2026): two shards were refused the feeds,
    warned and built anyway, and the merge refused their pages an hour later.
    """

    def action(self) -> str:
        return (ACTIONS / "licensed-feeds" / "action.yml").read_text(encoding="utf-8")

    def test_every_shard_requires_the_feeds_and_staggers_by_its_number(self) -> None:
        job = shard_job()
        self.assertIn("knowledgebase: required", job)
        self.assertIn("shard: ${{ matrix.shard }}", job)
        self.assertIn("fail-fast: true", job)

    def test_the_required_download_has_no_fallback(self) -> None:
        action = self.action()
        required = action[action.index("required)"):action.index(";;", action.index("required)"))]
        self.assertIn("--kb-only --required", required)
        self.assertNotIn("||", required)

    def test_every_portal_download_is_staggered(self) -> None:
        downloads = [line for line in self.action().splitlines() if "python -m trainbudget.feeds.dtd_download" in line]
        self.assertEqual(len(downloads), 3)
        for line in downloads:
            self.assertIn('--stagger "$SHARD"', line)


if __name__ == "__main__":
    unittest.main()
