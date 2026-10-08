"""The verify entry point keeps its two promises: what --fast leaves out, and a
report that does not let a step which could not run read as one that passed.
"""

from __future__ import annotations

import unittest

from tools import verify


class SlowListTest(unittest.TestCase):
    def test_every_excluded_test_is_one_that_exists(self) -> None:
        # An exclusion that names a test nobody has holds the fast path to a
        # test that was renamed, so the list has to keep pointing at real tests.
        discovered = {test.id() for test in _flatten(verify._discover("tests"))}
        for test_id in verify.FEED_SCALE:
            with self.subTest(test_id=test_id):
                self.assertIn(test_id, discovered)

    def test_the_fast_suite_leaves_the_feed_scale_tests_out(self) -> None:
        suite = verify.without(verify._discover("tools"), frozenset(verify.FEED_SCALE))
        ids = {test.id() for test in _flatten(suite)}
        self.assertNotIn(verify.FEED_SCALE[0], ids)
        self.assertGreater(len(ids), 100, "the tools suite discovered almost nothing")


class WithoutTest(unittest.TestCase):
    def test_it_drops_only_the_named_tests(self) -> None:
        class Named(unittest.TestCase):
            def test_one(self) -> None:  # noqa: D102 - a name to drop, not a behaviour
                pass

            def test_two(self) -> None:  # noqa: D102
                pass

        one, two = Named("test_one"), Named("test_two")
        suite = unittest.TestSuite([unittest.TestSuite([one]), two])
        kept = [test.id() for test in _flatten(verify.without(suite, frozenset({one.id()})))]
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0].endswith("test_two"))


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
        # empty set that would pass.
        self.assertEqual(verify.JAVASCRIPT, "page/*.js")


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
