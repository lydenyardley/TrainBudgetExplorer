"""The suite's own shape, because a dead test looks exactly like a passing one.

Python resolves a method name once per class: define ``test_foo`` twice and
the first definition is gone, silently, while the file still reads as two
tests and the run reports one fewer test than a reader counts. This file was
found that way -- ``test_a_destination_type_with_no_matches_gets_no_chip`` was
defined twice in ``DemoPageTest``, differing only in the string it split the
page on, and the first had been dead for most of a release.

A check that only runs when someone remembers to look is how the same defect
comes back, so it is a test. It parses the test files rather than importing
them, so it sees what is written in the file and not what a module happens to
expose: an import-time conditional that drops a class would hide the class
from an import-based check, and a class is not dead by being unreachable --
it is dead by being unreachable.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Directories that hold a copy of something rather than the thing itself, or
# nothing this project maintains: _cache is this repository's own scratch
# space (.gitignore) and has held a copy of the suite in it before.
SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "feeds",
    "node_modules",
    "reference-data",
    "_cache",
}


def test_files() -> list[Path]:
    return sorted(
        path
        for path in REPO.rglob("test_*.py")
        if not SKIP_PARTS.intersection(path.relative_to(REPO).parts)
    )


class NoShadowedTestNameTest(unittest.TestCase):
    """No class defines a test method twice."""

    def test_no_test_method_is_defined_twice_in_one_class(self) -> None:
        shadowed: list[str] = []
        for path in test_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                seen: set[str] = set()
                for child in node.body:
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if not child.name.startswith("test"):
                        continue
                    if child.name in seen:
                        shadowed.append(
                            f"{path.relative_to(REPO)}:{child.lineno} "
                            f"{node.name}.{child.name} is defined more than once, "
                            "so the earlier one never runs"
                        )
                    seen.add(child.name)
        self.assertEqual(shadowed, [], "\n".join(shadowed))

    def test_the_files_this_check_reads_are_the_files_the_suite_runs(self) -> None:
        # A checker that reads nothing is a checker that passes. The suite is
        # discovered in tests/ and tools/, so those are the directories it has
        # to be looking at.
        found = {path.relative_to(REPO).parts[0] for path in test_files()}
        self.assertEqual(found, {"tests", "tools"})
        self.assertGreater(len(test_files()), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
