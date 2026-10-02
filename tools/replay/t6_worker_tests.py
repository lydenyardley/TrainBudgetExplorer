"""T6: the tests for the worker budget, in the class that owns the runner.

The budget is the one thing standing between a whole-network build and a
MemoryError five minutes in, so the tests are about the answers rather than
about the arithmetic: which machine gets which count, and what the runner does
with the answer.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

TARGET = "tests/test_build_demo_page.py"

NEW_CLASS = '''class WorkerBudgetTest(unittest.TestCase):
    """How many build workers this machine can hold.

    `min(8, cpu_count())` was a core count wearing a memory claim. On a
    twelve-core machine with 15.8 GB it asked for eight, every worker was
    handed the whole national timetable, and the build died with a
    MemoryError in the pool initialiser after five minutes having written no
    pages -- reproducibly, twice. These hold the budget to the answers that
    matter rather than to the arithmetic behind them.
    """

    GB = 10 ** 9

    def test_a_machine_with_room_gets_the_measured_ceiling(self) -> None:
        # Twelve cores and plenty of memory is the case the ceiling exists
        # for: it is the machine the old core count got wrong.
        self.assertEqual(worker_budget(cores=12, free_bytes=16 * self.GB), 4)

    def test_the_ceiling_is_not_the_core_count(self) -> None:
        # The whole point: cores are not the question. Sixty-four cores with
        # room to spare still gets four, because four is the largest count
        # measured to finish a whole-network build.
        self.assertEqual(worker_budget(cores=64, free_bytes=64 * self.GB), 4)
        self.assertLess(worker_budget(cores=64, free_bytes=64 * self.GB), 64)

    def test_a_machine_without_room_gets_one_worker_and_still_builds(self) -> None:
        # Never zero. A build that cannot have a pool still builds, one page
        # at a time; refusing to build would be a worse answer than a slow one.
        for free in (0, 2 * self.GB, 6 * self.GB):
            with self.subTest(free=free):
                self.assertEqual(worker_budget(cores=12, free_bytes=free), 1)

    def test_the_floor_sits_below_the_one_parallel_build_that_has_worked(self) -> None:
        # The one parallel build with a measured outcome was four workers with
        # 8 GB free. A floor above that would turn away the only configuration
        # this project knows to work, which is how a measured ceiling stops
        # being a ceiling and becomes a superstition.
        self.assertLess(8 * self.GB, ONE_WORKER_FLOOR + self.GB)
        self.assertGreater(8 * self.GB, ONE_WORKER_FLOOR)

    def test_the_core_count_still_bounds_it_from_below(self) -> None:
        # A two-core runner cannot use four workers whatever it has free.
        self.assertEqual(worker_budget(cores=2, free_bytes=16 * self.GB), 2)
        self.assertEqual(worker_budget(cores=1, free_bytes=16 * self.GB), 1)

    def test_a_platform_that_will_not_say_falls_back_on_the_ceiling(self) -> None:
        # None is not zero. A machine that will not report its memory gets the
        # measured count rather than the one-worker answer a zero would give.
        with mock.patch.object(build_workers, "free_memory_bytes", lambda: None):
            self.assertEqual(worker_budget(cores=12), 4)
        with mock.patch.object(build_workers, "free_memory_bytes", lambda: 0):
            self.assertEqual(worker_budget(cores=12), 1)

    def test_passing_none_means_ask_the_machine_not_trust_the_ceiling(self) -> None:
        # free_bytes=None is "I have not read it yet", which is not the same
        # answer as "the machine could not tell me". Conflating them would let
        # a caller who meant one get the other.
        with mock.patch.object(build_workers, "free_memory_bytes",
                               return_value=4 * self.GB),                 mock.patch.object(build_workers.os, "cpu_count", return_value=12):
            self.assertEqual(worker_budget(cores=12, free_bytes=None), 1)

    def test_the_budget_reads_the_machine_when_it_is_not_told(self) -> None:
        # The no-argument path is the one the runner and the workflow use, so
        # it has to consult the platform rather than answer from a constant.
        with mock.patch.object(build_workers, "free_memory_bytes",
                               return_value=16 * self.GB):
            with mock.patch.object(build_workers.os, "cpu_count", return_value=12):
                self.assertEqual(worker_budget(), 4)

    def test_free_memory_is_a_number_or_nothing_at_all(self) -> None:
        free = free_memory_bytes()
        self.assertTrue(free is None or (isinstance(free, int) and free > 0))

    def test_the_figures_the_budget_is_built_from_are_the_measured_ones(self) -> None:
        # The parent was measured at 4,110 MB and the largest worker sampled
        # mid-build at 852 MB. The constants are rounded up from those, so a
        # future edit that lowers them below the measurement is caught here
        # rather than by a MemoryError.
        self.assertGreaterEqual(PARENT_BYTES, 4_110 * 10 ** 6)
        self.assertGreaterEqual(WORKER_BYTES, 852 * 10 ** 6)


class RunnerWorkerCountTest(unittest.TestCase):
    """That `python run.py` asks the budget rather than counting cores.

    It carries its own harness rather than borrowing the passthrough test's,
    because that one redirects stdout internally and the notice this is about
    is printed. A harness that swallowed the line under test could not assert
    on it.
    """

    GB = 10 ** 9

    def setUp(self) -> None:
        self.saved = (run.worker_budget, run.free_memory_bytes)
        self.addCleanup(setattr, run, "worker_budget", self.saved[0])
        self.addCleanup(setattr, run, "free_memory_bytes", self.saved[1])

    def _build(self, workers: int, free: int | None) -> tuple[list[str], str]:
        run.worker_budget = lambda free_bytes=None: workers
        run.free_memory_bytes = lambda: free

        captured: list[str] = []

        class _Result:
            returncode = 0

        def fake_run(cmd, cwd=None):
            captured.extend(cmd)
            return _Result()

        args = argparse.Namespace(
            feed=Path("feeds/fares"), origin=None, timetable=None,
            with_single_timetable=False, date="2026-10-02", all_origins=True,
            base_path=None, notices=None, privacy_contact=None,
        )
        out = io.StringIO()
        with mock.patch.object(run, "ROOT", Path(__file__).parent.parent),                 mock.patch.object(run, "_feed_exists", return_value=True),                 mock.patch.object(run.subprocess, "run", fake_run),                 contextlib.redirect_stdout(out):
            run.build(args)
        return captured, out.getvalue()

    def test_the_runner_passes_the_budget_to_the_builder(self) -> None:
        command, _ = self._build(3, 16 * self.GB)
        self.assertIn("--all-origins", command)
        self.assertEqual(command[command.index("--workers") + 1], "3")

    def test_the_runner_says_which_count_it_chose_and_what_it_had_to_work_with(self) -> None:
        # "1 worker" on its own does not say whether that was the ceiling or a
        # shortage of memory, and those are different problems for whoever has
        # to wait for the build.
        _, said = self._build(1, 4 * self.GB)
        self.assertIn("1 worker(s)", said)
        self.assertIn("4.0 GB free", said)

    def test_a_platform_that_cannot_report_memory_is_not_reported_as_having_none(self) -> None:
        _, said = self._build(4, None)
        self.assertIn("4 worker(s)", said)
        self.assertNotIn("GB free", said)

    def test_the_runner_no_longer_asks_for_the_core_count(self) -> None:
        source = Path(run.__file__).read_text(encoding="utf-8")
        self.assertNotIn("min(8, os.cpu_count()", source)
        self.assertIn("worker_budget(", source)
'''


OLD_WORKER_TEST = '''    def test_a_whole_network_run_asks_the_builder_for_this_machine_cores(self) -> None:
        # Left at the builder's default of one worker, the 2,718-page set
        # took over two and a half hours on this machine: each origin's page
        # is independent and the work is CPU-bound, so one worker leaves
        # every other core idle. The cap is eight because that is the
        # builder's own default for --fast-all-origins, and nothing here has
        # been measured past it.
        command = self._command(all_origins=True)
        self.assertIn("--workers", command)
        workers = int(command[command.index("--workers") + 1])
        self.assertEqual(workers, min(8, os.cpu_count() or 1))
        # A single-origin run has one page to build, so a worker count says
        # nothing there and passing one would only misreport the shape of the
        # work.
        self.assertNotIn("--workers", self._command(all_origins=False))
'''

NEW_WORKER_TEST = '''    def test_a_whole_network_run_asks_the_builder_for_what_this_machine_can_hold(self) -> None:
        # Left at the builder's default of one worker, the 2,712-page set
        # takes most of a working day: each origin's page is independent and
        # the work is CPU-bound, so one worker leaves every other core idle.
        # Cores were the wrong ceiling -- eight workers on this machine die
        # with a MemoryError having written no pages -- so the count is the
        # measured budget, and this holds the runner to passing it through
        # rather than recomputing it.
        command = self._command(all_origins=True)
        self.assertIn("--workers", command)
        workers = int(command[command.index("--workers") + 1])
        self.assertEqual(workers, worker_budget())
        self.assertGreaterEqual(workers, 1)
        self.assertLessEqual(workers, build_workers.MAX_WORKERS)
        # A single-origin run has one page to build, so a worker count says
        # nothing there and passing one would only misreport the shape of the
        # work.
        self.assertNotIn("--workers", self._command(all_origins=False))

'''

IMPORT_OLD = "import build_demo_page\n"
IMPORT_NEW = "import build_demo_page\nimport build_workers\n"

IMPORT_FROM_OLD = "from build_demo_page import ("
IMPORT_FROM_NEW = """from build_workers import (  # noqa: E402
    ONE_WORKER_FLOOR,
    PARENT_BYTES,
    WORKER_BYTES,
    free_memory_bytes,
    worker_budget,
)
from build_demo_page import ("""

ANCHOR = "class SingleOriginRunnerTidyTest(unittest.TestCase):"

patch(
    TARGET,
    [
        (IMPORT_OLD, IMPORT_NEW),
        (IMPORT_FROM_OLD, IMPORT_FROM_NEW),
        (OLD_WORKER_TEST, NEW_WORKER_TEST),
        (ANCHOR, NEW_CLASS + ANCHOR),
    ],
)
