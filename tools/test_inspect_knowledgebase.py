"""Tests for the Knowledgebase inspector.

The tool exists so a guessed element name can be checked against a real feed and
corrected. Two things make that worth trusting, and both are tested here: it
reports the real feed's vocabulary rather than a template, and it never reports
the reader as working when the reader is not.

The reader's own verdict is quoted rather than reimplemented, so a test that
passes here and a page that says something different would both be defects --
and this is the one that would catch it.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from make_synthetic_feed import build_synthetic_knowledgebase
from tools import inspect_knowledgebase as inspector


def _feed(folder: Path, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "ticket-restrictions.xml"
    target.write_text(body, encoding="utf-8")
    return target


# A feed in a vocabulary the reader does not know, and a person writing it would
# plainly mean: a restriction code, an outward condition and a return one.
FOREIGN = """<?xml version="1.0"?>
<KnowledgeBase>
  <FareRestriction>
    <RestrictionCode>B3</RestrictionCode>
    <RestrictionOutwardDescription>VALID AFTER 0859 MON-FRI</RestrictionOutwardDescription>
    <RestrictionReturnDescription>NOT VALID AT ANY TIME</RestrictionReturnDescription>
  </FareRestriction>
</KnowledgeBase>
"""


class ElementSummaryTest(unittest.TestCase):
    def test_every_name_is_reported_with_its_depth_and_where_it_appears(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed(Path(tmp), FOREIGN)
            elements, problem = inspector.summarise(feed.read_bytes())
        self.assertIsNone(problem)
        self.assertEqual(
            sorted(elements), ["farerestriction", "knowledgebase", "restrictioncode",
                               "restrictionoutwarddescription", "restrictionreturndescription"]
        )
        # Depth is what tells a record from a field, and a default of zero
        # would have pinned every name to the root.
        self.assertEqual(elements["knowledgebase"].depth, 0)
        self.assertEqual(elements["farerestriction"].depth, 1)
        self.assertEqual(elements["restrictioncode"].depth, 2)
        self.assertEqual(elements["restrictioncode"].parents, {"farerestriction"})

    def test_a_name_used_at_two_depths_reports_the_shallower(self) -> None:
        # A name that is a record in one place and a field in another is being
        # used for two things, and reporting only the deepest hides that.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed(
                Path(tmp),
                '<?xml version="1.0"?><r><Code>A</Code>'
                "<w><Code>B</Code></w></r>",
            )
            elements, _ = inspector.summarise(feed.read_bytes())
        self.assertEqual(elements["code"].depth, 1)
        self.assertEqual(elements["code"].count, 2)
        self.assertEqual(elements["code"].parents, {"r", "w"})

    def test_broken_xml_is_named_rather_than_reported_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed(Path(tmp), "<Knowledgebase><unclosed>")
            elements, problem = inspector.summarise(feed.read_bytes())
        self.assertEqual(elements, {})
        self.assertIn("not readable XML", problem or "")


class MatchingTest(unittest.TestCase):
    def test_names_are_assigned_to_the_field_the_reader_uses(self) -> None:
        matched = inspector.classify(
            {"restrictioncode", "description", "descout", "descrtn", "somethingelse"}
        )
        self.assertEqual(matched["code"], ["restrictioncode"])
        self.assertEqual(matched["description"], ["description"])
        self.assertEqual(matched["outward"], ["descout"])
        self.assertEqual(matched["return"], ["descrtn"])
        self.assertNotIn("somethingelse", [n for names in matched.values() for n in names])

    def test_a_near_miss_names_one_field_and_not_a_coincidence(self) -> None:
        # `restrictionoutwarddescription` contains three of the reader's words.
        # Listing all three said it looked like a CODE field, which is a
        # coincidence of spelling; the longest match is the specific one.
        lines = inspector.suggestions({"restrictionoutwarddescription"})
        self.assertEqual(len(lines), 1)
        self.assertIn("outward", lines[0])
        self.assertNotIn("code field", lines[0])

    def test_an_unknown_name_with_no_anchor_produces_no_suggestion(self) -> None:
        self.assertEqual(inspector.suggestions({"thing"}), [])
        # A name already matched is not a near miss; it is a match.
        self.assertEqual(inspector.suggestions({"descout"}), [])


class ReportTest(unittest.TestCase):
    def test_a_feed_the_reader_can_use_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = build_synthetic_knowledgebase(Path(tmp) / "kb")
            report = inspector.inspect_file(folder / "ticket-restrictions.xml")
        self.assertTrue(report["reader"]["usable"])
        self.assertEqual(report["reader"]["codesWithWording"], ["1A", "AS", "R1"])
        self.assertEqual(report["suggestions"], [])

    def test_a_feed_the_reader_cannot_use_is_reported_with_the_readers_own_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            feed = _feed(Path(tmp) / "kb", FOREIGN)
            report = inspector.inspect_file(feed)
        reader = report["reader"]
        # The codes ARE found. What is missing is the wording, and a tool that
        # said "no records recognised" here would send a person to look in the
        # wrong place entirely.
        self.assertEqual(reader["codes"], ["B3"])
        self.assertEqual(reader["codesWithWording"], [])
        self.assertFalse(reader["usable"])
        self.assertEqual(reader["verdict"], "unknown")
        self.assertIn("none carried a description", reader["note"])
        self.assertEqual(
            sorted(report["unmatchedNames"]),
            ["restrictionoutwarddescription", "restrictionreturndescription"],
        )

    def test_a_folder_with_no_feed_says_so_instead_of_reporting_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            reports = inspector.inspect(empty)
        self.assertEqual(len(reports), 1)
        self.assertIn("no XML or ZIP feed", reports[0]["problem"])

    def test_a_zip_is_read_and_the_member_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "kb" / "ticket-restrictions.zip"
            archive.parent.mkdir(parents=True)
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("inner/ticket-restrictions.xml", FOREIGN)
            report = inspector.inspect_file(archive)
        self.assertEqual(report["member"], "inner/ticket-restrictions.xml")
        self.assertIn("restrictioncode", [e["name"] for e in report["elements"]])

    def test_an_archive_with_no_xml_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "kb" / "ticket-restrictions.zip"
            archive.parent.mkdir(parents=True)
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("readme.txt", b"nothing here")
            report = inspector.inspect_file(archive)
        self.assertIn("no XML member", report["problem"])


class CommandLineTest(unittest.TestCase):
    def test_json_output_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_synthetic_knowledgebase(Path(tmp) / "kb")
            printed = io.StringIO()
            with redirect_stdout(printed):
                code = inspector.main([str(Path(tmp) / "kb"), "--json"])
            payload = json.loads(printed.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(payload), 1)
        self.assertTrue(payload[0]["reader"]["usable"])

    def test_a_missing_folder_explains_how_to_get_the_feed(self) -> None:
        # The most likely reason to run this tool is that the feed was never
        # downloaded, and "not there" alone would not tell the reader that.
        with tempfile.TemporaryDirectory() as tmp:
            printed, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(printed), redirect_stderr(errors):
                code = inspector.main([str(Path(tmp) / "absent")])
        self.assertEqual(code, 2)
        self.assertIn("--kb-only", errors.getvalue())

    def test_a_feed_the_reader_misses_still_exits_zero(self) -> None:
        # The report is the deliverable. A feed the reader cannot use is the
        # exact situation the tool exists for, so it must not exit non-zero.
        with tempfile.TemporaryDirectory() as tmp:
            _feed(Path(tmp) / "kb", FOREIGN)
            printed = io.StringIO()
            with redirect_stdout(printed):
                code = inspector.main([str(Path(tmp) / "kb")])
        self.assertEqual(code, 0)
        self.assertIn("possible near misses", printed.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
