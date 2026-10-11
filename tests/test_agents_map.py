"""AGENTS.md is the map an agent reads first, and a map with missing roads is
worse than none: the README's file table had drifted to omit 26 tracked files by
the time this was written (F2 of the 8 October 2026 agent-efficiency audit). This
test keeps the map pointing at files that exist, and keeps the files on the map.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def mapped(path: Path) -> bool:
    return path.relative_to(ROOT).as_posix() in MAP


class AgentsMapTest(unittest.TestCase):
    def test_every_module_the_site_is_made_of_is_on_the_map(self) -> None:
        for path in sorted(ROOT.glob("*.py")):
            with self.subTest(module=path.name):
                self.assertTrue(mapped(path), f"{path.name} is not named in AGENTS.md")

    def test_every_page_asset_is_on_the_map(self) -> None:
        # A route's script is one file per panel under a subdirectory, so the
        # walk goes below the first level: a check that read only the files
        # beside it would not notice a panel the map forgot.
        for path in sorted(p for p in (ROOT / "page").rglob("*") if p.is_file()):
            with self.subTest(asset=path.name):
                self.assertTrue(mapped(path), f"page/{path.name} is not named in AGENTS.md")

    def test_every_operator_tool_is_on_the_map(self) -> None:
        # scripts under tools/ are the commands an operator or an agent runs, and
        # they are the ones a reader could not previously find: the README's table
        # named four of them.
        for path in sorted((ROOT / "tools").glob("*.py")):
            if path.name.startswith("test_") or path.name == "__init__.py":
                continue
            with self.subTest(tool=path.name):
                self.assertTrue(mapped(path), f"tools/{path.name} is not named in AGENTS.md")

    def test_every_file_the_map_names_is_there(self) -> None:
        # The other direction: a map that names a file somebody deleted sends the
        # next reader to a path that does not exist.
        named = [
            token.strip("`,")
            for line in MAP.splitlines()
            if line.startswith("|")
            for token in line.replace("|", " ").split()
        ]
        for token in named:
            if not token.endswith((".py", ".js", ".css", ".cjs", ".json", ".md", ".yml")):
                continue
            with self.subTest(named=token):
                self.assertTrue((ROOT / token).exists(), f"AGENTS.md names {token}, which is not there")


if __name__ == "__main__":
    unittest.main()
