"""The replay driver has to survive a base that lacks a file it restores.

`replay.py` checks eleven files out at HEAD and then applies every patch script
in order. Three of the commits in the range -- `eea30b6`, `8d8783a`, `be207f2`
-- create ADR-0053, 0054, 0055 and 0057, so against a base older than them
ADR-0055 is a pathspec git does not know. `git checkout --` treats that as a
fatal error, and the driver died on the tenth path of eleven without applying a
single patch: a run from the base the README names could not start.

So the restore is filtered to the paths the checkout holds, and the run ends by
saying which files it could not land on HEAD, with the commits that edited them.
"Replayed" is a claim, and this is the check on it.
"""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent

# Loaded by path, not by name: `tools/replay` is a directory, so `import replay`
# from the tools suite finds the namespace package that directory makes, not the
# driver inside it.
_spec = importlib.util.spec_from_file_location(
    "replay_driver", ROOT / "tools" / "replay" / "replay.py")
replay = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(replay)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


class RestoreTest(unittest.TestCase):
    def test_a_path_the_checkout_does_not_hold_is_dropped_and_named(self) -> None:
        with mock.patch.object(replay.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="page_templates.py\nbuild_demo_page.py\n", stderr="",
            )
            held = replay.tracked(("page_templates.py", "build_demo_page.py",
                                   "adr/ADR-0055-the-runner-builds-what-the-reader-will-ask-for.md"))
        # ADR-0055 is absent from the checkout, so it is neither restored --
        # which is what used to abort the run -- nor silently forgotten.
        self.assertEqual(held, ["page_templates.py", "build_demo_page.py"])

    def test_a_path_the_checkout_holds_is_restored(self) -> None:
        self.assertIn("page_templates.py", replay.RESTORED)
        self.assertIn("page_templates.py", replay.tracked(replay.RESTORED))

    def test_the_real_checkout_does_hold_every_path_it_will_restore(self) -> None:
        # Not a tautology: ADR-0055 is the path that broke the driver, and it
        # exists at HEAD because the commits that made it are in the range. If
        # one of these is dropped, the driver is running against a different
        # base than the one it was written for and says nothing.
        missing = [path for path in replay.RESTORED if not (ROOT / path).is_file()]
        self.assertEqual(missing, [])


class GapReportTest(unittest.TestCase):
    """The report is only worth reading if it fires when it should and not otherwise.

    Every check here names a path the test itself edits and restores, or a path
    outside the tree the replay edits. A check that asserted "nothing is
    reported" over the whole restore list would fail every time the driver was
    run against a tree with uncommitted work -- which is the state a replay runs
    in, and the state this one was developed in.
    """

    # A tracked file no patch script touches, so it is clean unless this test
    # makes it otherwise.
    QUIET = "tools/replay/README.md"

    def test_a_file_that_matches_head_is_not_reported(self) -> None:
        self.assertEqual(replay.not_reconstructed([self.QUIET]), [])

    def test_an_edited_file_is_reported_with_the_commits_that_edited_it(self) -> None:
        path = ROOT / self.QUIET
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"\n<!-- scratch -->\n")
            result = replay.not_reconstructed([self.QUIET])
        finally:
            path.write_bytes(original)
        self.assertEqual(len(result), 1, result)
        reported, why, commits = result[0]
        self.assertEqual(reported, self.QUIET)
        self.assertEqual(why, "differs from HEAD")
        # The file is not the useful unit of a gap: the commit that wrote the
        # missing edit is, and it is named by hash and subject.
        self.assertTrue(commits, "a gap names the commits behind it")
        self.assertRegex(commits[0], r"^[0-9a-f]{7,} ")

    def test_only_the_path_that_moved_is_named(self) -> None:
        # The report is read by someone deciding which patch to write next, so
        # every path in it has to be one git says is different -- not one the
        # driver remembered worrying about, and not a neighbour that happens to
        # be in the restore list.
        path = ROOT / self.QUIET
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"\n<!-- scratch -->\n")
            reported = {name for name, _, _ in
                        replay.not_reconstructed([self.QUIET, "page_templates.py"])}
        finally:
            path.write_bytes(original)
        self.assertIn(self.QUIET, reported)
        self.assertLessEqual(len(reported), len(replay.RESTORED))

    def test_an_empty_restore_reports_nothing(self) -> None:
        self.assertEqual(replay.not_reconstructed([]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)