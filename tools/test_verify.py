"""The verify entry point keeps its two promises: what --fast leaves out, and a
report that does not let a step which could not run read as one that passed.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import verify


class FastListTest(unittest.TestCase):
    def test_every_fast_module_holds_tests(self) -> None:
        # A module name that loads nothing is a fast loop that passes by
        # running less: a package move or a rename would leave the line here
        # and the tests behind.
        for name in verify.FAST_MODULES:
            with self.subTest(module=name):
                loaded = unittest.TestLoader().loadTestsFromNames([name])
                self.assertGreater(len(_flatten(loaded)), 0, f"{name} holds no tests")

    def test_the_list_leaves_the_feed_scale_modules_out(self) -> None:
        # The whole point of the list: a module that parses the licensed
        # national download is --full's work, not every edit's.
        self.assertNotIn("tests.test_atoc_fares", verify.FAST_MODULES)
        self.assertNotIn("tests.test_atoc_timetable", verify.FAST_MODULES)

    def test_the_ceiling_is_the_five_minutes_the_audit_asked_for(self) -> None:
        self.assertLessEqual(verify.FAST_CEILING, 300.0)


class ArtifactCheckTest(unittest.TestCase):
    def test_it_names_the_part_whose_addition_breaks_the_concatenation(self) -> None:
        # Two panels may each declare `const total`: legal per file, a
        # SyntaxError in the one script the route ships. The check has to say
        # which panel, because "the script does not parse" is a search of
        # seventeen files rather than a fix.
        texts = {
            "a.js": "const total = 1;\n",
            "b.js": "const total = 2;\n",
            "c.js": "const other = 3;\n",
        }

        def build(parts: tuple[str, ...]) -> str:
            return "".join(texts[part] for part in parts)

        def parses(source: str) -> bool:
            return source.count("const total") < 2

        self.assertEqual(verify.first_unparsed(tuple(texts), build, parses), "b.js")

    def test_it_says_nothing_when_every_prefix_parses(self) -> None:
        def build(parts: tuple[str, ...]) -> str:
            return "".join(f"const {part.replace('.', '_')} = 1;\n" for part in parts)

        self.assertEqual(verify.first_unparsed(("a.js", "b.js"), build, lambda _text: True), "")


class PlaywrightPinTest(unittest.TestCase):
    def test_the_browser_it_asks_npx_for_is_the_one_file_that_names_it(self) -> None:
        # The audit that found CI pinned 1.63.0 while a local run floated also
        # found this command asking for an unpinned playwright. It reads the
        # same file the workflow reads, so the two commands launch one browser.
        version = (verify.ROOT / verify.PLAYWRIGHT_VERSION).read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(verify.playwright_package(), f"playwright@{version}")


class StepReportTest(unittest.TestCase):
    def test_a_step_that_could_not_run_does_not_read_as_a_pass(self) -> None:
        passed = verify.Step("something").done(True, "1 test").line()
        failed = verify.Step("something").done(False, "1 test").line()
        not_run = verify.Step("something").done(None, "no node").line()
        self.assertIn("ok", passed)
        self.assertIn("FAILED", failed)
        self.assertIn("not run", not_run)
        self.assertNotIn("ok", not_run)

    def test_the_page_javascript_is_where_the_javascript_check_looks(self) -> None:
        # F1 moved the blocks into files; this is the pattern that proves the
        # move happened and keeps the check pointed at them rather than at an
        # empty set that would pass. It reaches below the first level, because
        # the station route's script is one file per panel under a
        # subdirectory and a pattern that stopped there would check none of
        # them.
        self.assertEqual(verify.JAVASCRIPT, "page/**/*.js")


class WorkflowLintTest(unittest.TestCase):
    def test_no_actionlint_is_not_run_rather_than_a_pass(self) -> None:
        with mock.patch.object(verify.shutil, "which", return_value=None):
            step = verify.workflows()
        self.assertIsNone(step.ok)
        self.assertIn("actionlint-py", step.detail)

    @unittest.skipUnless(shutil.which("actionlint"), "actionlint is not on PATH")
    def test_a_broken_workflow_fails_the_step(self) -> None:
        # The lint has to read the files it is pointed at, or a clean report
        # means nothing: a job that needs a job nobody defined is an error.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "broken.yml").write_text(
                "on: push\njobs:\n  a:\n    needs: nowhere\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: echo hi\n",
                encoding="utf-8",
            )
            with mock.patch.object(verify, "ROOT", root):
                step = verify.workflows()
        self.assertIs(step.ok, False)

    @unittest.skipUnless(shutil.which("actionlint"), "actionlint is not on PATH")
    def test_this_repository_s_workflows_pass(self) -> None:
        self.assertIs(verify.workflows().ok, True)


def _flatten(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    tests: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            tests.extend(_flatten(item))
        else:
            tests.append(item)
    return tests


if __name__ == "__main__":
    unittest.main()


class BrowserVerdictTest(unittest.TestCase):
    """The step reports the suite's own page counts, not its argument count."""

    RUN_39772120392 = [
        "  swept _site/from/abbey-wood/index.html\n",
        "321/322 browser checks passed against _site/from/abbey-wood/index.html\n",
        "\n",
        "1 of 31 page(s) failed: 8841/8842 checks passed (_site/from/abbey-wood/index.html), "
        "147 check(s) not exercised by the pages swept\n",
    ]

    def test_a_failed_run_names_the_pages_that_failed_of_the_pages_driven(self) -> None:
        # Eight targets (five built pages, the site's two and its from/
        # directory), 31 pages driven, one failed. The step said 8.
        verdict = verify.suite_verdict(False, self.RUN_39772120392, targets=8)
        self.assertEqual(verdict, "the browser suite failed on 1 of 31 page(s)")

    def test_a_passing_run_counts_the_pages_the_suite_drove(self) -> None:
        lines = ["5 of 5 page(s) checked, 1030/1030 browser checks passed\n"]
        self.assertEqual(verify.suite_verdict(True, lines, targets=5), "5 page(s)")
        swept = ["31 of 31 page(s) checked, 8842/8842 browser checks passed\n"]
        self.assertEqual(verify.suite_verdict(True, swept, targets=8), "31 page(s)")

    def test_a_suite_that_died_before_its_summary_does_not_claim_a_count(self) -> None:
        verdict = verify.suite_verdict(False, ["TypeError: x is undefined\n"], targets=8)
        self.assertNotIn("failed on", verdict)
        self.assertIn("before it summarised", verdict)
