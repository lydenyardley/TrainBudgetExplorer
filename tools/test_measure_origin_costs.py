"""Tests for the per-origin cost distribution tool.

The tool exists so a mean is never quoted where a spread decides the work
(T8 of the 12 October 2026 build-cost audit). What the test holds is the
shape: one timed row per origin through the build's own calls, and a summary
that names the mean, the median, the ninetieth percentile and the maximum --
because a summary that printed only the mean would let the audit's own
mistake back in.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from make_synthetic_feed import build_synthetic_timetable  # noqa: E402
from tools import measure_origin_costs  # noqa: E402


class OriginCostTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.timetable = build_synthetic_timetable(Path(self._tmp.name) / "timetable")

    def run_tool(self, *flags: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = measure_origin_costs.main(["--feed", str(self.timetable), *flags])
        return code, buffer.getvalue()

    def test_each_origin_gets_a_timed_row_and_a_distribution(self) -> None:
        code, said = self.run_tool("--origins", "GRN,NOT", "--date", "2026-10-05")
        self.assertEqual(code, 0)
        self.assertIn("GRN", said)
        self.assertIn("NOT", said)
        for word in ("mean", "median", "p90", "max"):
            self.assertIn(word, said)

    def test_a_missing_feed_is_refused_before_anything_is_timed(self) -> None:
        code, _ = self.run_tool("--feed", str(Path(self._tmp.name) / "absent"))
        self.assertEqual(code, 2)

    def test_naming_no_origin_is_refused(self) -> None:
        code, _ = self.run_tool("--origins", " ,")
        self.assertEqual(code, 2)

    def test_the_distribution_names_the_spread_not_just_the_mean(self) -> None:
        rows = [
            {"origin": "A", "total": 1.0},
            {"origin": "B", "total": 2.0},
            {"origin": "C", "total": 3.0},
            {"origin": "D", "total": 24.0},
        ]
        shape = measure_origin_costs.distribution(rows)
        self.assertEqual(shape["origins"], 4)
        self.assertAlmostEqual(shape["mean"], 7.5)
        self.assertAlmostEqual(shape["median"], 2.5)
        self.assertEqual(shape["p90"], 24.0)
        self.assertEqual(shape["max"], 24.0)


if __name__ == "__main__":
    unittest.main()
