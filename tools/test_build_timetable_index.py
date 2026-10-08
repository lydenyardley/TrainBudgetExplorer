"""Tests for the tool that writes the per-origin timetable slices.

Two things decide whether this tool is useful: it writes slices a build can read
(a property of `SliceIndex`, tested with it), and it refuses the requests that
would fill a disk without saying so. The refusals are what these tests are mostly
about, because an index of a hundred gigabytes is not a mistake a second run
undoes.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from make_synthetic_feed import build_synthetic_timetable
from tools.build_timetable_index import main


class BuildTimetableIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.timetable = build_synthetic_timetable(root / "timetable")
        self.root = root / "index"

    def run_tool(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--timetable", str(self.timetable), "--root", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def index_dirs(self) -> list[Path]:
        return sorted(child for child in self.root.glob("*") if child.is_dir())

    def test_the_named_origins_are_written_and_named(self) -> None:
        code, said, _ = self.run_tool("--origins", "GRN, NOT")
        self.assertEqual(code, 0, said)
        self.assertIn("GRN:", said)
        self.assertIn("NOT:", said)
        directories = self.index_dirs()
        self.assertEqual(len(directories), 1)
        manifest = json.loads((directories[0] / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(manifest["origins"]), ["GRN", "NOT"])
        self.assertTrue((directories[0] / "GRN.pickle").is_file())

    def test_a_second_run_leaves_what_is_already_there(self) -> None:
        self.run_tool("--origins", "GRN")
        before = (self.index_dirs()[0] / "GRN.pickle").stat().st_mtime_ns
        code, said, _ = self.run_tool("--origins", "GRN")
        # Idempotent: the request is served, the file is not touched, and the
        # exit code does not turn a re-run into a failure.
        self.assertEqual(code, 0, said)
        self.assertIn("already here", said)
        self.assertIn("nothing to write", said)
        self.assertEqual((self.index_dirs()[0] / "GRN.pickle").stat().st_mtime_ns, before)

    def test_refresh_rewrites_what_is_already_there(self) -> None:
        self.run_tool("--origins", "GRN")
        code, said, _ = self.run_tool("--origins", "GRN", "--refresh")
        self.assertEqual(code, 0, said)
        self.assertIn("GRN:", said)

    def test_a_code_the_feed_cannot_be_asked_about_is_refused(self) -> None:
        code, _, err = self.run_tool("--origins", "GRN,ZZZ")
        self.assertEqual(code, 2)
        self.assertIn("ZZZ", err)
        self.assertEqual(self.index_dirs(), [], "a refused request writes no index")

    def test_no_origins_named_is_refused(self) -> None:
        code, _, err = self.run_tool()
        self.assertEqual(code, 2)
        self.assertIn("--origins", err)

    def test_all_origins_without_a_budget_is_refused(self) -> None:
        code, _, err = self.run_tool("--all-origins")
        self.assertEqual(code, 2)
        self.assertIn("--max-bytes", err)
        self.assertEqual(self.index_dirs(), [])

    def test_all_origins_stops_at_the_budget_it_was_given(self) -> None:
        code, said, _ = self.run_tool("--all-origins", "--max-bytes", "1")
        self.assertEqual(code, 0, said)
        self.assertIn("stopping", said)
        manifest = json.loads((self.index_dirs()[0] / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["origins"]), 1, "one slice over a one-byte budget")

    def test_a_missing_feed_is_refused(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(
                ["--timetable", str(Path(self._tmp.name) / "absent"), "--root", str(self.root), "--origins", "GRN"]
            )
        self.assertEqual(code, 2)
        self.assertIn("no timetable feed", err.getvalue())


if __name__ == "__main__":
    unittest.main()
