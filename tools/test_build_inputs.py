"""The build-input fingerprint has to cover what a build actually reads.

The rule is a set of globs, and the point of the tool is that the rule cannot
drift from the build the way the hand-kept list in the workflow did. These tests
hold the rule to the build's own imports and to the two directories it reads.
"""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tools import build_inputs


class CoveredModulesTest(unittest.TestCase):
    def test_every_module_the_build_imports_is_an_input(self) -> None:
        # build_demo_page.py is where a build starts. Every module it reaches,
        # transitively, has to be inside the fingerprint, or a fix to that
        # module does not rebuild the site.
        covered = {path.name for path in build_inputs.build_inputs()}
        seen: set[str] = set()
        pending = ["build_demo_page.py"]
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            self.assertIn(name, covered, f"{name} is imported by the build and is not hashed")
            pending.extend(_imported(build_inputs.ROOT / name))
        self.assertGreater(len(seen), 5, "the build's imports were not followed")

    def test_the_page_and_the_reference_data_are_inputs(self) -> None:
        # None of these is imported, so none would be caught by the test above:
        # the page's CSS and JS are inlined by page_templates, the reference data
        # is read as data, and the brand mark is read and inlined into the footer
        # of every page that carries the NRE credit. Every file under page/ is an
        # input, because the station route's script is one file per panel there.
        names = {path.relative_to(build_inputs.ROOT).as_posix() for path in build_inputs.build_inputs()}
        page = {path.relative_to(build_inputs.ROOT).as_posix() for path in build_inputs.ROOT.glob("page/**/*") if path.is_file()}
        self.assertIn("reference-data/destination-facets.json", names)
        self.assertIn("assets/powered-by-national-rail.svg", names)
        self.assertEqual(page - names, set(), "a file the page ships is not a build input")


class FingerprintTest(unittest.TestCase):
    def _tree(self, folder: Path) -> None:
        (folder / "page" / "station").mkdir(parents=True)
        (folder / "reference-data").mkdir()
        (folder / "tests").mkdir()
        (folder / "tools").mkdir()
        (folder / "build_demo_page.py").write_text("DATA = 1\n", encoding="utf-8")
        (folder / "page" / "station" / "payload.js").write_text("const a = 1;\n", encoding="utf-8")
        (folder / "reference-data" / "destination-facets.json").write_text("{}\n", encoding="utf-8")
        (folder / "tests" / "test_build_demo_page.py").write_text("x = 1\n", encoding="utf-8")
        (folder / "tools" / "page_bytes.py").write_text("x = 1\n", encoding="utf-8")

    def test_a_page_script_is_an_input_and_a_test_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._tree(root)
            before = build_inputs.fingerprint(root)
            self.assertEqual(before, build_inputs.fingerprint(root))
            (root / "tests" / "test_build_demo_page.py").write_text("x = 2\n", encoding="utf-8")
            (root / "tools" / "page_bytes.py").write_text("x = 2\n", encoding="utf-8")
            self.assertEqual(before, build_inputs.fingerprint(root), "a test is not a build input")
            (root / "page" / "station" / "payload.js").write_text("const a = 2;\n", encoding="utf-8")
            self.assertNotEqual(before, build_inputs.fingerprint(root), "the page is a build input")

    def test_touching_a_file_without_changing_it_is_not_a_change(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._tree(root)
            before = build_inputs.fingerprint(root)
            import os
            import time

            later = time.time() + 60
            os.utime(root / "build_demo_page.py", (later, later))
            self.assertEqual(before, build_inputs.fingerprint(root))

    def test_renaming_an_input_changes_the_digest(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._tree(root)
            before = build_inputs.fingerprint(root)
            (root / "build_demo_page.py").rename(root / "build_page.py")
            self.assertNotEqual(before, build_inputs.fingerprint(root))


def _imported(path: Path) -> list[str]:
    """The root-level modules one file imports, by file name."""
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".")[0])
    return [name + ".py" for name in names if (build_inputs.ROOT / f"{name}.py").is_file()]


if __name__ == "__main__":
    unittest.main()
