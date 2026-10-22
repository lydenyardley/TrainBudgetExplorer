"""The commit-msg hook refuses what CI would refuse, before the commit exists."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".githooks"


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class CommitHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def commit(self, message: str, author: str = "A Person <person@example.net>") -> subprocess.CompletedProcess[str]:
        name, email = author[: author.index(" <")], author[author.index("<") + 1 : -1]
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": "A Person",
            "GIT_COMMITTER_EMAIL": "person@example.net",
        }
        return subprocess.run(
            ["git", "-c", f"core.hooksPath={HOOKS.as_posix()}", "commit", "-q", "--allow-empty", "-m", message],
            cwd=self.repo,
            env=env,
            capture_output=True,
            text=True,
        )

    def commits(self) -> int:
        found = subprocess.run(
            ["git", "rev-list", "--all", "--count"], cwd=self.repo, capture_output=True, text=True
        )
        return int(found.stdout.strip() or 0)

    def test_a_conventional_message_is_committed(self) -> None:
        done = self.commit("docs: say how to enable the hook")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.commits(), 1)

    def test_a_credit_in_a_trailer_leaves_no_commit(self) -> None:
        done = self.commit("docs: add the runbook\n\nWhy.\n\nCo-Authored-By: Codebuff <noreply@codebuff.com>")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("credits Codebuff", done.stdout + done.stderr)
        self.assertEqual(self.commits(), 0)

    def test_a_credited_author_leaves_no_commit(self) -> None:
        done = self.commit("docs: add the runbook", author="Freebuff <noreply@freebuff.com>")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("credits Freebuff", done.stdout + done.stderr)
        self.assertEqual(self.commits(), 0)

    def test_a_subject_outside_the_grammar_leaves_no_commit(self) -> None:
        done = self.commit("Added the runbook.")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.commits(), 0)


if __name__ == "__main__":
    unittest.main()
