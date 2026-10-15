"""Every suppression in the tree says what it is suppressing, and why.

`# noqa` is a decision to silence a check, and a silenced check with no reason
written beside it is indistinguishable from a mistake nobody noticed. The 14
October 2026 comment audit counted them and wrote the count, and the cause of
each, into `docs/open-work.md` as a table: 40 of them then, all but six the
`# noqa: E402` that the tools' `sys.path` insert forced on every import after it.
A table is a fact about one afternoon; when the inserts were deleted the count
went stale within the hour. This is the rule instead.

The rule is the one the surviving suppressions already follow: a `# noqa` names
its cause on its own line after a dash, or in the comment block directly above
it. A suppression of a broad check (`BLE001`, a bare `except Exception`) is the
one that needs its reason most, because it is the one a reader cannot reconstruct
from the code around it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Directories written by a build, a probe or a test run. Nothing in them is
#: source, and a check that read them would report the pages a test wrote.
GENERATED = ("_site", "_demo_site", "_shape_site", "_cache", "_probe_feed", "_zz_feed",
             "_demo_feed", "_demo_kb", "_shape_feed", "_stations")

NOQA = re.compile(r"#\s*noqa(?::\s*(?P<codes>[A-Z0-9, ]+))?\s*(?P<reason>-\s*\S.*)?$")

#: How many comment lines directly above a suppression may carry its reason. Three
#: is a sentence: an explanation that needs a fourth line is a note the reader
#: will not connect to the suppression anyway.
REASON_LINES = 3


def python_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.py")
        if not any(part in GENERATED or part == "__pycache__" for part in path.parts)
    )


def where(path: Path) -> str:
    """A path a report can be read without the directory the tree happens to sit in."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def causes(path: Path) -> tuple[list[str], list[str]]:
    """The lines that name a cause, and the lines that suppress without one."""
    lines = path.read_text(encoding="utf-8").splitlines()
    named: list[str] = []
    silent: list[str] = []
    for number, line in enumerate(lines):
        match = NOQA.search(line)
        if match is None:
            continue
        if match.group("reason"):
            named.append(f"{where(path)}:{number + 1}")
            continue
        # A reason on the lines above, reaching back over the code the comment
        # block is attached to and no further.
        above = lines[max(0, number - REASON_LINES):number]
        if any(entry.lstrip().startswith("#") and entry.strip("# ").strip() for entry in above):
            named.append(f"{where(path)}:{number + 1}")
            continue
        silent.append(f"{where(path)}:{number + 1}  {line.strip()}")
    return named, silent


class SuppressionCensusTest(unittest.TestCase):
    def test_every_noqa_names_its_cause(self) -> None:
        silent: list[str] = []
        named = 0
        for path in python_files():
            held, quiet = causes(path)
            named += len(held)
            silent.extend(quiet)
        self.assertEqual(
            silent, [], "these suppressions say nothing about why they are here:\n"
            + "\n".join(silent),
        )
        # The census is printed rather than asserted: how many there are is a
        # fact about the tree, and the number that matters is the count of silent
        # ones, which is zero above.
        print(f"{named} suppression(s) in the tree, each naming its cause")

    def test_the_census_reads_the_tree_it_claims_to_read(self) -> None:
        # A check that found no files would pass forever. This is the count of
        # files and of the suppression the rule was written for: if the walk
        # stops finding either, the check above has stopped checking anything.
        files = python_files()
        self.assertGreater(len(files), 50, f"only {len(files)} Python file(s) found")
        self.assertIn(ROOT / "fuzz_feed.py", files)
        found = [entry for path in files for entry in causes(path)[0]]
        self.assertGreater(len(found), 3, "the walk found almost no suppressions")

    def test_a_suppression_on_its_own_with_no_reason_is_reported(self) -> None:
        # The rule itself, on a case it has to catch and a case it must not:
        # a bare `# noqa` is silent, and one with a dash and a sentence is not.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text(
                "try:\n    pass\nexcept Exception:  # noqa: BLE001\n    pass\n",
                encoding="utf-8",
            )
            named, silent = causes(path)
            self.assertEqual((named, len(silent)), ([], 1))
            path.write_text(
                "try:\n    pass\nexcept Exception:  # noqa: BLE001 - a probe reports\n    pass\n",
                encoding="utf-8",
            )
            named, silent = causes(path)
            self.assertEqual(len(named), 1)
            self.assertEqual(silent, [])
            path.write_text(
                "# The parser's own escape hatch: a damaged file is the input here.\ntry:\n    pass\nexcept Exception:  # noqa: BLE001\n    pass\n",
                encoding="utf-8",
            )
            named, silent = causes(path)
            self.assertEqual(len(named), 1, "a reason in the comment above counts")
            self.assertEqual(silent, [])


if __name__ == "__main__":
    unittest.main()
