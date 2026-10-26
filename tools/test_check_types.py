"""Tests for the type-check ratchet.

What matters is the shape of the verdict: an error in a file on the clean list
fails, the same error in a file that is not on it does not, and a mypy that is
not installed reports that it could not run rather than passing. The tests drive
the tool with a mypy report built here, so they hold whether or not mypy is
installed on the machine reading them.
"""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

from tools import check_types


def report(*lines: str) -> tuple[int, str]:
    return 1, "\n".join(lines) + "\n"


SUM_REPORT = report(
    "atoc_fares_loader.py:84: error: \"FaresLoader\" has no attribute \"location_type_sources\"  [attr-defined]",
    "build_payload.py:371: error: Argument 1 has incompatible type \"int\"  [arg-type]",
    "tools/check_types.py:1: error: Name \"nope\" is not defined  [name-defined]",
)


class ErrorsInTest(unittest.TestCase):
    def test_each_error_is_keyed_by_the_file_it_is_in(self) -> None:
        found = check_types.errors_in(SUM_REPORT[1])
        self.assertEqual(
            sorted(found),
            ["atoc_fares_loader.py", "build_payload.py", "tools/check_types.py"],
        )
        self.assertEqual(len(found["build_payload.py"]), 1)

    def test_a_windows_path_is_read_as_the_file_inside_the_tree(self) -> None:
        # mypy reports the path it was given, and a checkout on Windows spells it
        # with a backslash: a key the clean list cannot match is an error nobody
        # would ever be told about.
        found = check_types.errors_in("tools\\check_fare_rate.py:42: error: broken  [misc]")
        self.assertIn("tools/check_fare_rate.py", found)

    def test_a_note_is_not_an_error(self) -> None:
        found = check_types.errors_in(
            "build_pool.py:1164: note: \"dict\" is invariant\nbuild_pool.py:1165: error: real  [misc]\n"
        )
        self.assertEqual(len(found["build_pool.py"]), 1)


class VerdictTest(unittest.TestCase):
    def check(self, result: tuple[int, str] | None, argv: list[str] | None = None) -> tuple[int, str]:
        # Standard error as well as standard output: a check that could not run
        # says why on the error stream, which is where a reader looks for it.
        buffer = io.StringIO()
        with mock.patch.object(check_types, "run_mypy", return_value=result):
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                code = check_types.check(Path("."), bool(argv))
        return code, buffer.getvalue()

    def test_an_error_in_a_listed_file_fails(self) -> None:
        code, said = self.check(
            report("trainbudget/build/build_demo_page.py:1: error: nope  [misc]")
        )
        self.assertEqual(code, 1)
        self.assertIn("trainbudget/build/build_demo_page.py", said)

    def test_an_error_in_a_file_that_is_not_listed_does_not_fail(self) -> None:
        # atoc_fares_loader has 108 errors of its own today and is not on the
        # list: a check that failed on it would be red before it was written.
        self.assertNotIn("trainbudget/fares/atoc_fares_loader.py", check_types.CLEAN)
        code, said = self.check(
            report("trainbudget/fares/atoc_fares_loader.py:84: error: nope  [attr-defined]")
        )
        self.assertEqual(code, 0)
        self.assertIn("no type error", said)

    def test_a_mypy_that_is_not_installed_says_so(self) -> None:
        code, said = self.check(None)
        self.assertEqual(code, 2)
        self.assertIn("mypy is not installed", said)

    def test_a_mypy_that_reported_nothing_is_not_a_pass(self) -> None:
        code, said = self.check((0, "Success: no issues found\n"))
        self.assertEqual(code, 2)
        self.assertIn("read nothing", said)

    def test_the_census_prints_and_does_not_fail(self) -> None:
        code, said = self.check(
            report("trainbudget/fares/atoc_fares_loader.py:1: error: nope  [misc]"),
            argv=["--all"],
        )
        self.assertEqual(code, 0)
        self.assertIn("1 file(s) with errors of their own", said)


class CleanListTest(unittest.TestCase):
    def test_every_file_on_the_clean_list_is_there(self) -> None:
        # A renamed module would leave the list pointing at nothing, and the
        # check would report a mypy it never asked to read a file.
        missing = [name for name in check_types.CLEAN if not (check_types.ROOT / name).is_file()]
        self.assertEqual(missing, [])

    def test_the_list_is_a_subset_of_the_files_the_check_reads(self) -> None:
        listed = set(check_types.sources(check_types.ROOT))
        self.assertTrue(set(check_types.CLEAN) <= listed)

    def test_no_generated_directory_is_read(self) -> None:
        for name in check_types.sources(check_types.ROOT):
            self.assertFalse(
                any(part in check_types.GENERATED for part in Path(name).parts), name
            )


if __name__ == "__main__":
    unittest.main()
