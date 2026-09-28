"""Tests for the Knowledgebase reference check on restriction wording.

The check exists to answer one question a fares feed cannot answer alone: is
the condition printed beside this price still the condition the reference feed
publishes? So the tests are about the *answers* rather than the parse, and each
one pins down a way the answer could be a lie:

* a feed that agrees with itself proves the comparison ran, not that it works;
* a feed this reader does not understand must not be read as agreement;
* zero codes compared is not agreement, however complete the feed looked.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import atoc_knowledgebase as kb
from atoc_knowledgebase import (
    ABSENT,
    CHECKED,
    DISAGREES,
    UNKNOWN,
    Knowledgebase,
    KnowledgebaseRestriction,
    RestrictionCheck,
    check_restrictions,
    load_ticket_restrictions,
)
from build_demo_page import _iso_day, describe_restriction_check, knowledgebase_dates
from make_synthetic_feed import build_synthetic_knowledgebase


class _Header:
    """Stands in for the ``.RST`` RestrictionHeader the fares feed produces."""

    def __init__(self, description: str = "PEAK", outward: str = "OUT", return_text: str = "RTN"):
        self.description = description
        self.outward_text = outward
        self.return_text = return_text


def _xml(records: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<Knowledgebase>{records}</Knowledgebase>\n'


def _write(payload: str, tmp: str) -> Path:
    folder = Path(tmp) / "kb"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ticket-restrictions.xml").write_text(payload, encoding="utf-8")
    return folder


class ReaderTest(unittest.TestCase):
    def test_a_recognised_record_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            feed = _write(
                _xml(
                    "<TicketRestrictions><Restriction>"
                    "<RestrictionCode>B3</RestrictionCode>"
                    "<Description>EARLY</Description>"
                    "<DescOut>NOT VALID BEFORE 0859</DescOut>"
                    "<DescRtn>NOT VALID AT ANY TIME</DescRtn>"
                    "</Restriction></TicketRestrictions>"
                ),
                tmp,
            )
            loaded = load_ticket_restrictions(feed)
            self.assertTrue(loaded.loaded)
            self.assertTrue(loaded.usable)
            record = loaded.restrictions["B3"]
            self.assertEqual(record.description, "EARLY")
            self.assertEqual(record.outward_text, "NOT VALID BEFORE 0859")
            self.assertEqual(record.return_text, "NOT VALID AT ANY TIME")

    def test_a_feed_this_reader_does_not_understand_is_not_a_feed_that_agrees(self) -> None:
        # The whole reason this reader reports its own uncertainty. A document
        # it cannot recognise must produce no records, and therefore no claim.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _write(_xml("<SomethingElse><Row a='1'/></SomethingElse>"), tmp)
            loaded = load_ticket_restrictions(feed)
            self.assertTrue(loaded.loaded)
            self.assertFalse(loaded.usable)
            self.assertEqual(loaded.records_understood, 0)
            self.assertFalse(load_ticket_restrictions(feed).restrictions)

    def test_a_description_is_never_mistaken_for_a_code(self) -> None:
        # A two-letter rule is a code; a sentence is not. Without the shape
        # check, an element named generically enough to match DESCRIPTION_NAMES
        # could be read as the code and every condition would key on the wrong
        # thing.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _write(
                _xml(
                    "<R><Restriction><Description>PEAK</Description>"
                    "<RestrictionCode>1A</RestrictionCode></Restriction></R>"
                ),
                tmp,
            )
            self.assertEqual(sorted(load_ticket_restrictions(feed).restrictions), ["1A"])

    def test_broken_xml_and_an_absent_folder_are_named_not_guessed_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = _write("<?xml version='1.0'?><Knowledgebase><unclosed>", tmp)
            loaded = load_ticket_restrictions(broken)
            self.assertFalse(loaded.usable)
            self.assertIn("XML", loaded.problem or "")

            missing = load_ticket_restrictions(Path(tmp) / "no-such-folder")
            self.assertFalse(missing.loaded)
            self.assertIn("no Knowledgebase restriction feed", missing.problem or "")


    def test_a_partly_understood_feed_does_not_read_as_agreeing(self) -> None:
        # The dangerous shape. Three records understood out of hundreds looks
        # exactly like a feed that confirms those three and says nothing about
        # the rest, so every record-shaped element that yielded no code has to
        # be counted -- otherwise a wrong guess at the schema is laundered into
        # a claim of agreement.
        with tempfile.TemporaryDirectory() as tmp:
            rows = "".join(
                f"<RestrictionRow><n>{i}</n></RestrictionRow>" for i in range(40)
            )
            feed = _write(
                _xml(
                    "<TicketRestrictions>"
                    "<Restriction><RestrictionCode>1A</RestrictionCode>"
                    "<Description>PEAK</Description></Restriction>"
                    + rows
                    + "</TicketRestrictions>"
                ),
                tmp,
            )
            loaded = load_ticket_restrictions(feed)
            self.assertEqual(loaded.records_understood, 1)
            self.assertFalse(loaded.usable)
            self.assertEqual(sum(loaded.unrecognised.values()), 40)
            check = check_restrictions({"1A": _Header("PEAK")}, loaded)
            self.assertEqual(check.status, UNKNOWN)
            self.assertFalse(check.verified)

    def test_a_container_is_not_mistaken_for_an_unreadable_record(self) -> None:
        # The other half of the same rule: <TicketRestrictions> holds the
        # records, and counting it would disqualify every well-formed feed.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _write(
                _xml(
                    "<TicketRestrictions><Restriction>"
                    "<RestrictionCode>1A</RestrictionCode>"
                    "<Description>PEAK</Description>"
                    "</Restriction></TicketRestrictions>"
                ),
                tmp,
            )
            loaded = load_ticket_restrictions(feed)
            self.assertTrue(loaded.usable, loaded.summary())
            self.assertEqual(dict(loaded.unrecognised), {})

    def test_a_feed_of_codes_and_no_wording_is_not_usable(self) -> None:
        # The case the inspector found: a feed in a vocabulary this reader
        # half-understands. The codes come out, so a parse succeeded, and
        # "usable" would have been true -- while the page would go on to have
        # nothing to compare. A feed that parses is not a feed that confirms.
        with tempfile.TemporaryDirectory() as tmp:
            feed = _write(
                _xml(
                    "<FareRestriction><RestrictionCode>B3</RestrictionCode>"
                    "<RestrictionOutwardDescription>VALID AFTER 0859</RestrictionOutwardDescription>"
                    "</FareRestriction>"
                ),
                tmp,
            )
            loaded = load_ticket_restrictions(feed)
            self.assertEqual(sorted(loaded.restrictions), ["B3"])
            self.assertEqual(loaded.records_understood, 1)
            self.assertFalse(loaded.usable)
            check = check_restrictions({"B3": _Header("EARLY", "OUT", "RTN")}, loaded)
            self.assertEqual(check.status, UNKNOWN)
            # And the reason names what was found, so a reader is not sent to
            # look for records the tool has already read.
            self.assertIn("none carried a description", check.note)

    def test_a_reference_record_with_no_wording_cannot_be_a_disagreement(self) -> None:
        # If the real feed nests its text one element deeper than this reader
        # looks, every record would come back empty. Reading that as "the
        # reference feed disagrees" would tell readers the portal had retired
        # conditions it had said nothing about -- the worst failure this
        # feature has.
        check = check_restrictions(
            {"1A": _Header("PEAK", "OUT 1A", "RTN 1A")},
            self_kb_with_empty_record(),
        )
        self.assertNotEqual(check.status, DISAGREES)
        self.assertFalse(check.verified)
        self.assertEqual(check.compared, 0)

    def test_a_zip_member_larger_than_the_cap_is_refused_not_read(self) -> None:
        import zipfile

        import atoc_knowledgebase as kbmod

        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "kb" / "ticket-restrictions.zip"
            archive_path.parent.mkdir(parents=True)
            # The cap is lowered rather than the payload grown: a member past
            # the limit has to be refused on the size the central directory
            # declares, and 256 MB of zeros is a slow way to prove it.
            original = kbmod._MAX_BYTES
            kbmod._MAX_BYTES = 64
            self.addCleanup(setattr, kbmod, "_MAX_BYTES", original)
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("big.xml", b"<Knowledgebase/>" * 10)
            loaded = load_ticket_restrictions(archive_path.parent)
            self.assertFalse(loaded.usable)
            self.assertIn("larger than this reader will parse", loaded.problem or "")
            self.assertNotIn("not readable XML", loaded.problem or "")


def self_kb_with_empty_record() -> Knowledgebase:
    loaded = Knowledgebase(files_read=["x.xml"])
    loaded.restrictions["1A"] = KnowledgebaseRestriction("1A", "", "", "")
    loaded.records_seen = loaded.records_understood = 1
    return loaded


class CheckTest(unittest.TestCase):
    def _headers(self) -> dict[str, _Header]:
        return {"1A": _Header("PEAK", "OUT 1A", "RTN 1A"), "R1": _Header("OTHER", "OUT R1", "RTN R1")}

    def _kb(self, *pairs: tuple[str, str, str, str]) -> Knowledgebase:
        loaded = Knowledgebase(files_read=["x.xml"])
        for code, description, outward, back in pairs:
            loaded.restrictions[code] = KnowledgebaseRestriction(code, description, outward, back)
        loaded.records_seen = len(pairs)
        loaded.records_understood = len(pairs)
        return loaded

    def test_matching_wording_is_reported_as_checked_with_a_count(self) -> None:
        check = check_restrictions(
            self._headers(),
            self._kb(("1A", "PEAK", "OUT 1A", "RTN 1A"), ("R1", "OTHER", "OUT R1", "RTN R1")),
        )
        self.assertEqual(check.status, CHECKED)
        self.assertEqual((check.compared, check.agree, check.disagree), (2, 2, 0))
        self.assertTrue(check.verified)

    def test_a_disagreement_is_reported_and_the_code_is_named(self) -> None:
        # The case the page exists for: the reference feed has retired a
        # condition the fares file still prints. The reader must be told which.
        check = check_restrictions(
            self._headers(),
            self._kb(("1A", "PEAK", "NOT VALID AT ANY TIME", "RTN 1A"), ("R1", "OTHER", "OUT R1", "RTN R1")),
        )
        self.assertEqual(check.status, DISAGREES)
        self.assertEqual((check.compared, check.agree, check.disagree), (2, 1, 1))
        self.assertEqual([code for code, _ in check.differing], ["1A"])
        self.assertFalse(check.verified)

    def test_a_reflowed_sentence_is_not_a_disagreement(self) -> None:
        # Crying wolf is how a warning stops being read. Case and internal
        # whitespace are not differences in meaning.
        check = check_restrictions(
            {"1A": _Header("peak", "OUT 1A", "RTN 1A")},
            self._kb(("1A", "PEAK", "  out 1a  ", "RTN 1A")),
        )
        self.assertEqual(check.status, CHECKED)
        self.assertEqual(check.disagree, 0)

    def test_no_reference_feed_is_absent_not_agreement(self) -> None:
        check = check_restrictions(self._headers(), None)
        self.assertEqual(check.status, ABSENT)
        self.assertFalse(check.verified)

    def test_an_unusable_reference_feed_is_unknown_not_agreement(self) -> None:
        loaded = Knowledgebase(files_read=["x.xml"])
        loaded.unrecognised["somethingelse"] += 3
        check = check_restrictions(self._headers(), loaded)
        self.assertEqual(check.status, UNKNOWN)
        self.assertFalse(check.verified)
        self.assertIn("not understood", check.note)

    def test_zero_codes_compared_is_unknown_however_complete_the_feed(self) -> None:
        # The dangerous one. A reference feed with 400 restrictions and none of
        # them on this page has not confirmed anything about this page.
        check = check_restrictions(
            {"1A": _Header()}, self._kb(("ZZ", "SOMETHING ELSE", "OUT", "RTN"))
        )
        self.assertEqual(check.status, UNKNOWN)
        self.assertFalse(check.verified)
        self.assertEqual(check.compared, 0)

    def test_a_code_the_reference_feed_lacks_is_skipped_not_counted_as_conflict(self) -> None:
        check = check_restrictions(
            self._headers(),
            self._kb(("R1", "OTHER", "OUT R1", "RTN R1")),
        )
        self.assertEqual(check.status, CHECKED)
        self.assertEqual(check.compared, 1)


class WordingTest(unittest.TestCase):
    """The four answers are worded once; these hold that wording to its facts."""

    def _describe(self, **kwargs) -> str:
        return describe_restriction_check(kb.RestrictionCheck(**kwargs))

    def test_agreement_names_how_many_were_compared(self) -> None:
        said = self._describe(
            status=CHECKED, compared=7, agree=7, published="2026-09-26T04:15:00Z"
        )
        self.assertIn("agrees on all 7", said)
        self.assertIn("published 2026-09-26", said)
        # And without a date the wording is still a complete sentence, rather
        # than one with a hole where a claim should be.
        self.assertNotIn("None", self._describe(status=CHECKED, compared=7, agree=7))

    def test_disagreement_names_the_codes(self) -> None:
        said = self._describe(
            status=DISAGREES, compared=7, agree=6, disagree=1, differing=(("B3", "x"),)
        )
        self.assertIn("disagrees on 1 of 7", said)
        self.assertIn("B3", said)

    def test_absent_and_unknown_say_so_rather_than_being_silent(self) -> None:
        self.assertIn("not checked", self._describe(status=ABSENT, note="nothing named"))
        unknown = self._describe(status=UNKNOWN, note="3 records were not understood")
        self.assertIn("could not be checked", unknown)
        self.assertIn("3 records were not understood", unknown)


class ManifestDateTest(unittest.TestCase):
    def test_the_portals_own_publication_date_is_read_not_todays(self) -> None:
        # A freshness claim about someone else's data has to rest on their date
        # for it. Reading the build's clock would make the claim true today and
        # quietly false tomorrow, and a page sits on a server for a long time.
        manifest = {
            "downloads": [
                {
                    "name": "ticket-restrictions",
                    "last_modified": "Fri, 26 Sep 2026 04:15:00 GMT",
                    "downloaded_at": "2026-09-27T03:20:00Z",
                    "checked_at": "2026-09-28T03:18:00Z",
                }
            ]
        }
        published, checked = knowledgebase_dates(manifest)
        # Normalised to YYYY-MM-DD. Left as the raw HTTP-date it was, the page
        # sliced the first ten characters -- "Fri, 26 Se" -- and shipped
        # "published undefined undefined NaN" to a real reader.
        self.assertEqual(published, "2026-09-26")
        self.assertEqual(checked, "2026-09-28")

    def test_a_date_in_either_shape_normalises_and_anything_else_becomes_nothing(self) -> None:
        self.assertEqual(_iso_day("2026-09-26T04:15:00Z"), "2026-09-26")
        self.assertEqual(_iso_day("Fri, 26 Sep 2026 04:15:00 GMT"), "2026-09-26")
        self.assertEqual(_iso_day("Friday, 26-Sep-26 04:15:00 GMT"), "2026-09-26")
        # An unreadable date is left out of the page, not printed as whatever
        # the formatter makes of it.
        for value in ("", "   ", "not a date", None, 17, "2026/09/26", "2026-13-45"):
            self.assertEqual(_iso_day(value), "", value)
        # And a manifest carrying one leaves the whole claim unsaid, not wrong.
        self.assertEqual(
            knowledgebase_dates({"downloads": [{"name": "ticket-restrictions", "last_modified": "?"}]}),
            ("", ""),
        )

    def test_an_absent_or_unusable_manifest_yields_no_dates_rather_than_guesses(self) -> None:
        self.assertEqual(knowledgebase_dates(None), ("", ""))
        self.assertEqual(knowledgebase_dates({}), ("", ""))
        self.assertEqual(
            knowledgebase_dates({"downloads": [{"name": "fares", "downloaded_at": "x"}]}),
            ("", ""),
        )
        # A manifest with no validator recorded is a first run, not a feed
        # published at the epoch.
        self.assertEqual(
            knowledgebase_dates({"downloads": [{"name": "ticket-restrictions"}]}), ("", "")
        )


class ParallelPathTest(unittest.TestCase):
    """One check for a whole build, not one per page.

    The --all-origins build renders up to 2,700 pages. The reference check is a
    single comparison against a single document, so it is made once in the
    parent and handed down; the bug this covers is the alternative, where the
    worker path silently fell back to "not checked" and a multi-page site
    contradicted a single-page build of the same feed.
    """

    def test_the_worker_path_receives_the_parents_check(self) -> None:
        import build_workers

        source = Path(build_workers.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "restriction_reference=_WORKER.get(\"restriction_reference\")", source
        )

    def test_the_resumable_signature_distinguishes_two_different_answers(self) -> None:
        # Otherwise a resumed build could keep pages built against a reference
        # feed that has since disagreed, mixing two answers inside one release.
        import build_demo_page as bdp

        shared = {
            "max_changes": 1, "note": "", "attribution": None, "price_source": "x",
            "feed_date": None, "base_path": "", "provider": "p", "link_mode": "fallback",
            "adults": 2, "network": None, "advertiser_id": None, "publisher_id": "",
            "departures": 5, "index": [], "feed": "f", "timetable": None, "analytics": None,
        }
        absent = dict(shared, restriction_reference=RestrictionCheck(status=ABSENT))
        differs = dict(
            shared,
            restriction_reference=RestrictionCheck(
                status=DISAGREES, compared=3, agree=2, disagree=1
            ),
        )
        again = dict(shared, restriction_reference=RestrictionCheck(status=ABSENT))
        self.assertNotEqual(
            bdp.resumable_signature(absent, []), bdp.resumable_signature(differs, [])
        )
        # And the same answer twice is the same build, or nothing would resume.
        self.assertEqual(
            bdp.resumable_signature(absent, []), bdp.resumable_signature(again, [])
        )


class FixtureTest(unittest.TestCase):
    def test_the_fixture_agrees_and_can_be_made_to_disagree(self) -> None:
        # The fixture derives its wording from the same RH records the fares
        # feed carries, so "agrees" here is a fact about the comparison rather
        # than about two hand-kept copies of a sentence.
        from make_synthetic_feed import _restriction_lines
        from atoc_restrictions import RESTRICTION_OFFSETS

        headers = {}
        for line in _restriction_lines():
            if line[1:3] != "RH":
                continue
            offsets = RESTRICTION_OFFSETS["RH"]
            field = lambda name: line[offsets[name][0]:offsets[name][1]].strip()  # noqa: E731
            if field("restriction_code"):
                headers[field("restriction_code")] = _Header(
                    field("description"), field("desc_out"), field("desc_rtn")
                )
        self.assertTrue(headers, "the fixture has restriction headers to compare")

        with tempfile.TemporaryDirectory() as tmp:
            agreeing = load_ticket_restrictions(
                build_synthetic_knowledgebase(Path(tmp) / "a", disagree_on=None)
            )
            self.assertEqual(check_restrictions(headers, agreeing).status, CHECKED)

            disagreeing = load_ticket_restrictions(
                build_synthetic_knowledgebase(Path(tmp) / "b", disagree_on="1A")
            )
            check = check_restrictions(headers, disagreeing)
            self.assertEqual(check.status, DISAGREES)
            self.assertIn("1A", [code for code, _ in check.differing])


if __name__ == "__main__":
    unittest.main(verbosity=2)
