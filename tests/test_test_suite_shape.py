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

The second rule here is the one the 10 October 2026 suite audit asked for: a
test that proves the page's JavaScript by quoting a *statement* out of it
cannot detect that the page stopped working, because the string it looks for
is the implementation. Changing one space inside the statement fails the test
while the page behaves identically -- measured: the Playwright suite passed
839/839 over a one-space-patched copy of the page the Python suite failed on.
So the page's statements belong to the browser suite, and this file refuses
them here.
"""

from __future__ import annotations

import ast
import re
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

#: Everything in JavaScript that is not code: a comment, a string, a template
#: literal. A needle that the page's script only ever holds inside one of
#: these is copy, a payload key, an id, a class or a sentence -- the things
#: this suite is entitled to assert. Every one of these alternatives is closed
#: by a delimiter on the same construct, so a quote inside a regular
#: expression or a comment can misjudge one line and cannot run away with the
#: rest of the file.
NOT_CODE = re.compile(
    r"//[^\n]*"
    r"|/\*.*?\*/"
    r"|\"(?:[^\"\\\n]|\\.)*\""
    r"|'(?:[^'\\\n]|\\.)*'"
    r"|`(?:[^`\\]|\\.)*`",
    re.DOTALL,
)
#: A needle that is a name and nothing else: an identifier, or a dotted path
#: of identifiers with the hyphens a class name carries. These name a payload
#: key, a method or a class rather than quoting a statement, and a suite that
#: asserts `DATA["tickets"]` exists is asserting the product. A needle with no
#: word characters at all (`?`, `/`) is a separator rather than code.
BARE_NAME = re.compile(r"^(?:[A-Za-z_$][\w$]*(?:-[\w$]+)*)(?:\.[A-Za-z_$][\w$]*(?:-[\w$]+)*)*$|^\W+$")
#: JavaScript syntax, without which a needle is not code: a fares code, a
#: date, a station name and `1 of 3` are all strings, and the page's script
#: happens to contain the same characters as operands. A needle needs a letter
#: and one of these to be a statement rather than a value.
CODE_SHAPES = ("(", ")", "{", "}", "[", "]", "=", ";", '"', "'", "<", ">", "!", "&", "|", "+", "*", "/", "%")


def page_script_text() -> str:
    """Every byte of the page's JavaScript, so a needle is read against it."""
    return "\n".join(
        path.read_text(encoding="utf-8").replace("\r\n", "\n")
        for path in sorted((REPO / "page").rglob("*.js"))
    )


def _not_code_spans(script: str) -> list[tuple[int, int]]:
    """The ranges of *script* that hold copy rather than code."""
    return [(match.start(), match.end()) for match in NOT_CODE.finditer(script)]


def quotes_a_page_statement(needle: str, script: str) -> bool:
    """Whether *needle* quotes a statement of the page's own JavaScript.

    The rule is structural on purpose. An earlier version listed fourteen
    punctuation shapes that make a needle an implementation quote, and the
    first thing the suite did with it was shorten needles until the
    punctuation was gone -- `var dark = true;` became `dark = true` -- so the
    list grew a hole per shortening. What separates the two kinds of needle
    is not which characters they hold but what the needle *is*:

    * a needle the script only ever holds inside a comment, a string or a
      template is copy, a payload key, an id, a class or a sentence;
    * a bare name or a dotted path (`tickets`, `partyPence`, `mode-chips`)
      is a payload key or a hook name, which is a contract even where the
      script happens to use the same identifier;
    * a needle with no letters in it, or none of the syntax in `CODE_SHAPES`,
      is a value -- `1`, `00000`, `station`, `table` -- and the script's
      operands are not the same thing as a statement;
    * anything else that appears as code carries syntax -- an assignment, a
      comparison, a call, a literal -- and is the implementation.
    """
    if not needle or needle not in script:
        return False
    if BARE_NAME.match(needle):
        return False
    if not re.search(r"[A-Za-z]", needle):
        return False
    if not any(shape in needle for shape in CODE_SHAPES):
        return False
    spans = _not_code_spans(script)
    for start in _occurrences(script, needle):
        if not _within(spans, start, start + len(needle)):
            return True
    return False


def _occurrences(script: str, needle: str) -> list[int]:
    """Every index *needle* starts at in *script*."""
    found: list[int] = []
    at = script.find(needle)
    while at >= 0:
        found.append(at)
        at = script.find(needle, at + 1)
    return found


def _within(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    """Whether ``[start, end)`` sits inside one of *spans*."""
    return any(low <= start and end <= high for low, high in spans)


#: Empty since 18 October 2026. The byte measurer's fixtures were the one entry,
#: because they spelled the payload marker by hand and that is a statement of the
#: page's script. They import it from ``page_templates`` now, so the exemption went
#: with the copy. Kept as a set because the next file that needs one should have to
#: say so here rather than skip the rule quietly.
FIXTURE_FILES: set[str] = set()


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


class NoPageStatementNeedleTest(unittest.TestCase):
    """No test proves the page's JavaScript by quoting a statement of it.

    The browser suite owns what the page does; this suite owns what the page
    says and the payload it carries. A needle holding a statement of
    ``page/*.js`` fails on a whitespace-only edit to that statement while the
    page behaves identically, which is the same cost as a test that cannot
    fail, so it is refused here rather than argued about in review.
    """

    def test_no_test_asserts_a_statement_of_the_pages_javascript(self) -> None:
        script = page_script_text()
        quoted: list[str] = []
        for path in test_files():
            if path.relative_to(REPO).as_posix() in FIXTURE_FILES:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    body = getattr(node, "body", [])
                    if (
                        body
                        and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)
                    ):
                        docstrings.add(id(body[0].value))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                if id(node) in docstrings:
                    continue
                if quotes_a_page_statement(node.value, script):
                    quoted.append(
                        f"{path.relative_to(REPO)}:{node.lineno} quotes "
                        f"{node.value[:60]!r}, which is a statement of the page's "
                        "script; assert the fact it was reaching for, or leave the "
                        "claim to the browser suite"
                    )
        self.assertEqual(quoted, [], "\n".join(quoted))

    def test_the_page_assets_are_there_to_be_read(self) -> None:
        # A rule that reads no script passes whatever is in the tests. Copy
        # rather than a statement, so this probe is not itself the defect it
        # refuses.
        self.assertIn("No railcard selected", page_script_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
