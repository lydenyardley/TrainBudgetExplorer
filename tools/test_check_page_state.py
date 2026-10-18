"""Tests for the page-state read ratchet.

What matters is the verdict: a panel over its number fails, a panel the budget
does not name fails, a panel the budget names that is not there says the check
could not run, and a write is not counted as a read. The tests read sources
written here rather than the page itself, so they hold while the page changes.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import check_page_state


class ReadsTest(unittest.TestCase):
    def test_a_write_is_not_a_read(self) -> None:
        source = "budget.value = String(safe);\ninput.checked = true;\n"
        self.assertEqual(check_page_state.reads(source), 0)

    def test_a_read_is_counted(self) -> None:
        source = "const wanted = Number(budget.value);\nconst on = input.checked;\n"
        self.assertEqual(check_page_state.reads(source), 2)

    def test_a_comparison_is_not_an_assignment(self) -> None:
        # `===` starts with `=`, and a count that read it as an assignment would
        # miss the reads in every chip comparison on the page. The fixture names
        # a `row` rather than the page's own `input` because a test that spells a
        # statement of the page verbatim is exactly what
        # `tests/test_test_suite_shape.py` refuses -- the assertion here is about
        # the counter, not about the page.
        source = "if (row.value === \"all\") continue;\n"
        self.assertEqual(check_page_state.reads(source), 1)

    def test_a_comment_is_not_a_read(self) -> None:
        source = "// budget.value is what the reader typed\n/* input.checked */\nconst x = 1;\n"
        self.assertEqual(check_page_state.reads(source), 0)


def page(root: Path, panels: dict[str, int]) -> None:
    """A `page/station` holding one minimal panel per name and read count."""
    directory = root / check_page_state.PANELS
    directory.mkdir(parents=True)
    for name, count in panels.items():
        (directory / name).write_text("const x = budget.value;\n" * count, encoding="utf-8")


class VerdictTest(unittest.TestCase):
    def check(self, budget: dict[str, int], panels: dict[str, int], census: bool = False) -> tuple[int, str]:
        buffer = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page(root, panels)
            with mock.patch.dict(check_page_state.BUDGET, budget, clear=True):
                with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                    code = check_page_state.check(root, census)
        return code, buffer.getvalue()

    def test_a_panel_at_its_number_passes(self) -> None:
        code, said = self.check({"a.js": 2}, {"a.js": 2})
        self.assertEqual(code, 0)
        self.assertIn("no control read past its budget", said)

    def test_a_panel_over_its_number_fails(self) -> None:
        code, said = self.check({"a.js": 1}, {"a.js": 3})
        self.assertEqual(code, 1)
        self.assertIn("a.js", said)

    def test_a_panel_the_budget_does_not_name_fails(self) -> None:
        # Otherwise a new panel arrives unmeasured and the ratchet is a list of
        # the panels that happened to exist on the day it was written.
        code, said = self.check({}, {"new.js": 1})
        self.assertEqual(code, 1)
        self.assertIn("not in the budget", said)

    def test_a_panel_the_budget_names_that_is_gone_says_it_could_not_run(self) -> None:
        code, said = self.check({"gone.js": 0}, {"a.js": 0})
        self.assertEqual(code, 2)
        self.assertIn("no panel of that name exists", said)

    def test_a_page_with_no_panel_says_it_could_not_run(self) -> None:
        buffer = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / check_page_state.PANELS).mkdir(parents=True)
            with contextlib.redirect_stderr(buffer):
                code = check_page_state.check(root, False)
        self.assertEqual(code, 2)
        self.assertIn("no panel under", buffer.getvalue())

    def test_a_budget_above_the_count_is_a_note(self) -> None:
        code, said = self.check({"a.js": 5}, {"a.js": 2})
        self.assertEqual(code, 0)
        self.assertIn("the budget says 5", said)

    def test_the_census_prints_and_fails_on_nothing(self) -> None:
        code, said = self.check({"a.js": 1}, {"a.js": 3}, census=True)
        self.assertEqual(code, 0)
        self.assertIn("3 read(s)", said)


class PageTest(unittest.TestCase):
    def test_every_panel_of_the_page_is_named_in_the_budget(self) -> None:
        listed = set(check_page_state.panels(check_page_state.ROOT))
        self.assertEqual(listed - set(check_page_state.BUDGET), set())

    def test_the_budget_names_no_panel_that_is_gone(self) -> None:
        listed = set(check_page_state.panels(check_page_state.ROOT))
        self.assertEqual(set(check_page_state.BUDGET) - listed, set())


if __name__ == "__main__":
    unittest.main()
