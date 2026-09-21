"""Tests for the commit message checker."""

from __future__ import annotations

import unittest

from check_commit_message import check


class CommitMessageTest(unittest.TestCase):
    def test_accepts_a_subject_only_message(self) -> None:
        self.assertEqual(check("fix(fares): reject a fare with no digits"), [])

    def test_accepts_a_body_and_footers(self) -> None:
        message = (
            "feat(timetable): allow one change when planning a journey\n"
            "\n"
            "The onward search is capped so that a query stays cheap.\n"
            "\n"
            "Refs: adr/ADR-0006-timetable-layer.md\n"
        )
        self.assertEqual(check(message), [])

    def test_accepts_a_breaking_change_marker(self) -> None:
        self.assertEqual(check("refactor(sweep)!: drop the positional feed argument"), [])

    def test_accepts_git_generated_prefixes(self) -> None:
        self.assertEqual(check("Merge branch 'main' into work"), [])
        self.assertEqual(check("fixup! feat(sweep): add the audit command"), [])

    def test_rejects_a_missing_type(self) -> None:
        problems = check("Add the audit command")
        self.assertEqual(len(problems), 1)
        self.assertIn("subject must read", problems[0])

    def test_rejects_an_unknown_type(self) -> None:
        self.assertTrue(check("feature(sweep): add the audit command"))

    def test_rejects_a_capitalised_or_punctuated_description(self) -> None:
        self.assertIn("description starts with a capital letter", check("docs: Add the runbook"))
        self.assertIn("description ends with a period", check("docs: add the runbook."))

    def test_rejects_an_overlong_subject(self) -> None:
        problems = check("docs: " + "x" * 80)
        self.assertEqual(problems, ["subject is 86 characters, the limit is 72"])

    def test_rejects_a_body_that_starts_on_line_two(self) -> None:
        self.assertIn("line 2 must be blank", check("docs: add the runbook\nbecause it helps."))

    def test_rejects_an_overlong_body_line_but_allows_a_footer_or_a_url(self) -> None:
        long_prose = "docs: add the runbook\n\n" + "word " * 20
        self.assertTrue(check(long_prose))
        footer = "docs: add the runbook\n\nRefs: adr/" + "a" * 80 + ".md"
        self.assertEqual(check(footer), [])

    def test_rejects_an_empty_message(self) -> None:
        self.assertEqual(check(""), ["the message is empty"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
