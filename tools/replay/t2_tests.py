"""T2: the second pass over the rewritten tests.

Eight assertions were still reading strings the design had already replaced,
and one new assertion concatenated a variable in the test rather than in the
page. Each is corrected against what the page now says.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

patch(
    "tests/test_build_demo_page.py",
    [
        (
            '        self.assertIn(\'cheapest: "The cheapest fare of any ticket type for each destination\', script)',
            '        self.assertIn(\'cheapest: "Each row is the cheapest fare of any ticket type\', script)',
        ),
        (
            '        self.assertIn("this page prices the through fare only", self.html)',
            '        self.assertIn("This page prices the through fare only.", self.html)',
        ),
        (
            '        self.assertIn(\'setShortlistStatus("The shortlist holds " + SHORTLIST_LIMIT + " places.\', self.html)',
            '        # Said on the page as well as to the status region: a control that\n'
            '        # stops responding with no explanation is the one thing a reader\n'
            '        # cannot act on, and the strip is where they are already looking.\n'
            '        self.assertIn(\n'
            '            \'const message = "The shortlist holds " + SHORTLIST_LIMIT + " places. Remove one to add another.";\',\n'
            '            self.html,\n'
            '        )\n'
            '        self.assertIn(\n'
            '            "if (shortlistLimit) shortlistLimit.textContent = message;", self.html\n'
            '        )',
        ),
        (
            '        self.assertIn("Restricted fare — condition below", self.html)',
            '        self.assertIn(\'Restricted fare — the condition is below.\', self.html)',
        ),
        (
            '        self.assertIn("const card = railcards[railcardSelect.value];", self.html)\n'
            '        self.assertIn("note.textContent =\\n      card.label +", self.html)',
            '        # The label is read from the variable, not spelled out, so the test\n'
            '        # reads the variable and the two sentences the note branches into.\n'
            '        self.assertIn("const card = railcards[railcardSelect.value];", self.html)\n'
            '        self.assertIn(\'card.label + " does not reduce this fare. Its own price here is "\', self.html)\n'
            '        self.assertIn(\'card.label + " cannot be applied to this fare.\', self.html)',
        ),
        (
            '        self.assertIn(\n'
            '            "This feed prices no " + card.label + " fare to " + destination.name, self.html\n'
            '        )',
            '        self.assertIn(\n'
            '            \'      "This feed prices no " + card.label + " fare to " + destination.name +\',\n'
            '            self.html,\n'
            '        )',
        ),
        (
            "    def run_main(self, *flags, site_exists=True):",
            "    def run_main(self, *flags, site_exists=True, stale=False):",
        ),
        (
            '            stack.enter_context(mock.patch.object(run, "build", builder))',
            '            stack.enter_context(mock.patch.object(run, "build", builder))\n'
            "            # The freshness check reads this machine's file times, which\n"
            "            # are not what is under test; the decision is.\n"
            '            stack.enter_context(\n'
            '                mock.patch.object(run, "sources_are_newer", lambda: stale)\n'
            "            )",
        ),
        (
            "    def test_rebuild_builds_even_when_a_site_is_already_there(self) -> None:",
            "    def test_a_build_the_sources_have_moved_past_is_rebuilt(self) -> None:\n"
            "        # Nine hours of committed work, a double-clicked runner and a page\n"
            "        # from before it, with nothing on the page saying so. The runner\n"
            "        # rebuilds when what it would serve is out of date, and says why.\n"
            "        _, said, builds, served = self.run_main(\n"
            '            "--origin", "GRA", site_exists=True, stale=True\n'
            "        )\n"
            "        self.assertEqual(builds, 1)\n"
            "        self.assertEqual(len(served), 1)\n"
            '        self.assertIn("newer than _site/", said)\n'
            "\n"
            "    def test_rebuild_builds_even_when_a_site_is_already_there(self) -> None:",
        ),
    ],
)
