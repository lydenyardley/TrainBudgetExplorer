"""Tests for the commit message checker."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.check_commit_message import MAX_SUBJECT, check, main


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
        self.assertEqual(check("\n\n   \n"), ["the message is empty"])

    def test_rejects_a_generated_with_trailer(self) -> None:
        # The two spellings this repository's history carried, in the two places
        # the emoji sat: a check that read only one of them would have passed the
        # other, and the rewrite of 21 October 2026 had 273 of these to remove.
        for credit in ("\U0001f916 Generated with Codebuff", "Generated with Codebuff \U0001f916"):
            with self.subTest(credit=credit):
                problems = check(f"docs: add the runbook\n\nThe gate now names the flag.\n\n{credit}")
                self.assertTrue(
                    any("credits Codebuff" in problem for problem in problems),
                    f"{credit!r} was accepted: {problems}",
                )

    def test_rejects_a_tool_in_a_co_author_trailer(self) -> None:
        problems = check(
            "docs: add the runbook\n\nThe gate now names the flag.\n\n"
            "Co-Authored-By: Codebuff <noreply@codebuff.com>"
        )
        self.assertTrue(any("credits Codebuff" in problem for problem in problems), problems)

    def test_rejects_the_other_tool_and_a_line_that_opens_with_its_name(self) -> None:
        problems = check(
            "docs: add the runbook\n\nThe gate now names the flag.\n\n"
            "Freebuff <noreply@freebuff.com>\n"
        )
        self.assertTrue(any("credits Freebuff" in problem for problem in problems), problems)

    def test_a_credit_is_refused_on_a_merge_commit_too(self) -> None:
        # The grammar has an exception for the subjects Git writes; the credit
        # rule does not. A merge is where a pasted trailer is likeliest.
        problems = check("Merge branch 'main' into work\n\nCo-Authored-By: Codebuff <noreply@codebuff.com>")
        self.assertTrue(any("credits Codebuff" in problem for problem in problems), problems)

    def test_a_body_line_that_opens_with_a_colon_is_not_a_trailer(self) -> None:
        # Prose in the body is not a footer. A colon in the *last* block is read
        # as a trailer on purpose: `Tool:` and `Generated-by:` are credits, and
        # the cost of that reading is one reworded sentence rather than a rule
        # with a key list the next generator is missing from.
        message = (
            "docs: say where the client is discussed\n\n"
            "Note: Freebuff wrote the two trailers.\n\n"
            "The rule is in CONTRIBUTING.md.\n"
        )
        self.assertEqual(check(message), [])

    def test_a_trailer_under_any_key_is_refused(self) -> None:
        # The shape is the rule, not a list of keys: `Tool:` and `Generated-by:`
        # are the same credit as `Co-Authored-By:`, and the key a generator picks
        # next is not one this file has seen.
        for footer in ("Tool: Codebuff", "Generated-by: Freebuff <noreply@freebuff.com>"):
            with self.subTest(footer=footer):
                problems = check(f"docs: add the runbook\n\nThe gate names the flag.\n\n{footer}")
                self.assertTrue(
                    any("credits" in problem and "line 5" in problem for problem in problems),
                    f"{footer!r} was accepted: {problems}",
                )

    def test_accepts_a_person_as_co_author(self) -> None:
        message = (
            "docs: add the runbook\n\nThe gate now names the flag.\n\n"
            "Co-Authored-By: A Person <person@example.net>"
        )
        self.assertEqual(check(message), [])

    def test_a_message_that_merely_mentions_a_tool_is_not_a_credit(self) -> None:
        # The history has a commit whose body names the client's own directory.
        # Refusing it would make the rule say something it was never about, and
        # the first thing an author does with a checker that refuses a true line
        # is delete the line.
        message = (
            "chore: ignore the build output\n\n"
            "_site/ is the --all-origins build output (ADR-0019); .freebuff/ and\n"
            "_demo_site/ are ignored with it.\n"
        )
        self.assertEqual(check(message), [])

    def test_rejects_an_author_identity_that_names_a_tool(self) -> None:
        problems = check(
            "docs: add the runbook",
            ["Codebuff <noreply@codebuff.com>", "Lyden <lydenyardley+github@example.net>"],
        )
        self.assertTrue(any("credits Codebuff" in problem for problem in problems), problems)
        self.assertEqual(problems[0].count("credits"), 1)

    def test_the_command_line_checks_a_file_and_its_author(self) -> None:
        # The deploy workflow calls the tool this way, so the two arguments it
        # passes are held here rather than only in the workflow's own text.
        with tempfile.TemporaryDirectory() as scratch:
            message = Path(scratch, "message.txt")
            message.write_text(
                "docs: add the runbook\n\nCo-Authored-By: Codebuff <noreply@codebuff.com>\n",
                encoding="utf-8",
            )
            self.assertEqual(main([str(message)]), 1)
            message.write_text("docs: add the runbook\n", encoding="utf-8")
            self.assertEqual(main([str(message), "--author", "A Person <person@example.net>"]), 0)
            self.assertEqual(main([str(message), "--author", "Freebuff <noreply@freebuff.com>"]), 1)

    def test_credits_only_leaves_the_grammar_alone(self) -> None:
        # The deploy workflow checks every commit a force-push carries with this
        # flag: 41 commits here predate the grammar, so applying it backwards
        # would fail the history the rule deliberately accepts.
        self.assertEqual(check("Add the audit command", credits_only=True), [])
        self.assertEqual(check("", credits_only=True), [])
        problems = check(
            "Add the audit command\n\nCo-Authored-By: Codebuff <noreply@codebuff.com>",
            credits_only=True,
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("credits Codebuff", problems[0])
        self.assertEqual(
            check("docs: add the runbook", ["Codebuff <noreply@codebuff.com>"], credits_only=True),
            [
                "the author 'Codebuff <noreply@codebuff.com>' credits Codebuff, and a "
                "commit's author is a person"
            ],
        )

    def test_reads_a_message_that_opens_with_a_blank_line(self) -> None:
        # Git strips the blank lines a message file may begin with, so the first
        # content line is the subject. Reading line one as the subject called
        # such a message empty, and a checker that refuses a good message for an
        # invented reason sends its author to edit the wrong thing.
        self.assertEqual(check("\nfix(sweep): name the feed that refused\n"), [])
        self.assertEqual(check("\n\nfix(sweep): name the feed that refused\n\nBody.\n"), [])
        # The blank line after the subject is still the subject's own, not the
        # file's leading one: a body that starts on line two is still a problem.
        self.assertIn(
            "line 2 must be blank",
            check("\ndocs: add the runbook\nbecause it helps.\n"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
