"""Tests for the commit message checker."""

from __future__ import annotations

import unittest

from tools.check_commit_message import MAX_SUBJECT, check


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

    def test_rejects_a_body_that_starts_on_line_two(self) -> None:
        self.assertIn("line 2 must be blank", check("docs: add the runbook\nbecause it helps."))

    def test_rejects_an_overlong_subject(self) -> None:
        problems = check("docs: " + "x" * 80)
        self.assertEqual(problems, ["subject is 86 characters, the limit is 80"])

    def test_a_long_body_line_is_not_a_problem(self) -> None:
        # The subject is the display surface, so it has a cap. The body is
        # prose, and the closing recap paragraph of most of this repository's
        # commits is a single line over 200 characters: capping that rejected
        # all 87 commits in the history, which is how a rule that was never
        # kept came to look like a rule that was being broken.
        recap = "Keep the fares index, and let each worker apply only its own " + "flow " * 40
        message = "docs: add the runbook\n\n" + recap
        self.assertEqual(check(message), [])
        footer = "docs: add the runbook\n\nRefs: adr/" + "a" * 80 + ".md"
        self.assertEqual(check(footer), [])

    def test_the_subject_cap_is_the_longest_this_repository_keeps(self) -> None:
        # 80 is measured, not chosen: the longest subject among the commits
        # that follow the grammar is 77, so the cap catches a run-on without
        # failing the history the tool is supposed to police.
        self.assertEqual(MAX_SUBJECT, 80)
        longest = (
            "fix(types): a fare-construction point is not a station, and is nowhere a page"
        )
        self.assertEqual(check(longest), [])
        self.assertEqual(len(longest), 77)

    def test_rejects_an_empty_message(self) -> None:
        self.assertEqual(check(""), ["the message is empty"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
