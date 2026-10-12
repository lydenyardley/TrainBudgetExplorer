"""Tests for the two memory measurement tools.

`tools/measure_build_memory.py` decides the constants in `build_workers`, so a
number it gets wrong is a number the whole build budget is wrong by. One was,
for a long time, wrong by a factor of six.

`measure_worker` loaded the national timetable and threw the result away. The
statement completed, the object had no referrers, CPython freed it, and the
sample that followed read the arenas Python had not returned to the OS. It
printed "one worker's initialiser peaks at 338 MB" and the truth on the real
feed is 1,918 MB. Every figure derived from it -- `WORKER_BYTES`, the table in
ADR-0057 -- was wrong in the reassuring direction, and the tool that existed to
re-derive them was what made them look measured.

So the test below holds a reference to the same database the tool loads and
requires the tool to report at least that much. A measurement that drops its
subject cannot pass it.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import measure_build_memory, measure_worker_pages  # noqa: E402


class MemoryReadingTest(unittest.TestCase):
    def test_reading_this_process_returns_a_plausible_number(self) -> None:
        # Both tools read memory the same way, and an earlier draft of
        # measure_worker_pages read it through ctypes instead: the win32 counter
        # struct was laid out wrongly, every sample came back 0 MB, and the tool
        # reported a peak of zero with enormous margin against the budget. A
        # reading of zero is a broken instrument, not a small process.
        for module in (measure_build_memory, measure_worker_pages):
            working, private = module.memory_mb()
            self.assertGreater(working, 0, module.__name__)
            self.assertGreater(private, 0, module.__name__)
            self.assertLess(working, 1_000_000, module.__name__)

    def test_the_two_tools_agree_about_this_process(self) -> None:
        # They are separate files reading the same subject. If they disagree by
        # more than a page, one of them is measuring something else.
        self.assertEqual(measure_build_memory.memory_mb(),
                         measure_worker_pages.memory_mb())


class WorkerMeasurementTest(unittest.TestCase):
    """`measure_worker` must hold what it measures."""

    def test_the_initialiser_figure_covers_the_database_it_loaded(self) -> None:
        from atoc_timetable import TimetableDb
        from make_synthetic_feed import build_synthetic_timetable

        from atoc_fares import FaresDb
        from make_synthetic_feed import build_synthetic_feed
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            timetable = build_synthetic_timetable(root / "timetable")
            fares_feed = build_synthetic_feed(root / "fares")

            # The tool reads the shared fare metadata from a cache the parent
            # would have written. Written here from the synthetic feed so the
            # test measures the timetable rather than the fares.
            common = root / "fare-common.pickle"
            index_dir = root / "fare-index"
            index_dir.mkdir()
            FaresDb().load_feed(fares_feed).write_fare_indexes(common, index_dir, ["GRN"])
            args = argparse.Namespace(feed=fares_feed, timetable=timetable)

            # What the database is worth while something still refers to it.
            held = TimetableDb().load_feed(timetable)
            _working, while_held = measure_build_memory.memory_mb()
            schedules = held.stats()["schedules"]
            self.assertGreater(schedules, 0)
            del held

            buffer = io.StringIO()
            with mock.patch.object(measure_build_memory, "fares_index_cache_paths",
                                   return_value=(common, index_dir)):
                with contextlib.redirect_stdout(buffer):
                    measure_build_memory.measure_worker(args)
            report = buffer.getvalue()

        peak = _peak_from(report)
        self.assertIsNotNone(peak, report)
        # Both figures are whole megabytes truncated from kilobytes, so two
        # readings of the same footprint can differ by one. That is the
        # instrument's resolution, not a smaller measurement: on Windows the
        # readings round alike, and on Linux -- where the private figure read
        # 0 until 12 October 2026 and this held trivially -- a freed and
        # reloaded database lands a few hundred kilobytes either side.
        self.assertGreaterEqual(
            peak, while_held - 1,
            "the reported peak must cover a database of this size while it is "
            "held; a smaller figure means the tool measured something other "
            "than what it loaded")


def _peak_from(report: str) -> int | None:
    """The peak the tool printed, in MB."""
    for line in report.splitlines():
        if "initialiser peaks at" in line:
            return int(line.split("peaks at", 1)[1].split("MB", 1)[0].replace(",", ""))
    return None


if __name__ == "__main__":
    unittest.main(verbosity=2)