"""Tests for the Knowledgebase reference check on restriction conditions.

The check exists to answer one question a fares feed cannot answer alone: does
the portal still publish the conditions printed beside these prices? So the
tests are about the *answers* rather than the parse, and each one pins down a
way the answer could be a lie:

* a feed that lists what this reader lists proves the comparison ran, not that
  it works;
* a feed this reader does not understand must not be read as confirmation;
* zero codes compared is not confirmation, however complete the feed looked.

What is compared is publication, never wording, and one test exists to hold
that: run against the real portal feed, comparing the two texts word for word
reported every one of 628 conditions disagreeing on a feed where none did.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import atoc_knowledgebase as kb
from atoc_knowledgebase import (
    ABSENT,
    CHECKED,
    UNKNOWN,
    UNPUBLISHED,
    Knowledgebase,
    KnowledgebaseRestriction,
    RestrictionCheck,
    check_restrictions,
    load_ticket_restrictions,
)
from build_demo_page import (
    _iso_day,
    describe_restriction_note,
    knowledgebase_dates,
    reference_fingerprint,
    restriction_codes_shown,
)
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
            check = check_restrictions(["1A"], loaded)
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
            check = check_restrictions(["B3"], loaded)
            self.assertEqual(check.status, UNKNOWN)
            # And the reason names what was found, so a reader is not sent to
            # look for records the tool has already read.
            self.assertIn("none carried a description", check.note)

    def test_a_reference_record_with_no_wording_cannot_be_a_missing_condition(self) -> None:
        # If the real feed nests its text one element deeper than this reader
        # looks, every record would come back empty. Reading that as "the
        # portal no longer publishes this" would tell readers the portal had
        # retired conditions it had said nothing about -- the worst failure
        # this feature has. The reader's own gate catches it: a feed whose
        # records carry no wording at all is not known to be a feed of
        # restriction conditions, so the check is unknown and nothing is
        # counted either way.
        check = check_restrictions(
            ["1A"],
            self_kb_with_empty_record(),
        )
        self.assertEqual(check.status, UNKNOWN)
        self.assertNotEqual(check.status, UNPUBLISHED)
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
    def _codes(self) -> list[str]:
        return ["1A", "R1"]

    def _kb(self, *pairs: tuple[str, str, str, str]) -> Knowledgebase:
        loaded = Knowledgebase(files_read=["x.xml"])
        for code, description, outward, back in pairs:
            loaded.restrictions[code] = KnowledgebaseRestriction(code, description, outward, back)
        loaded.records_seen = len(pairs)
        loaded.records_understood = len(pairs)
        return loaded

    def test_every_listed_condition_is_reported_as_checked_with_a_count(self) -> None:
        check = check_restrictions(
            self._codes(),
            self._kb(("1A", "PEAK", "OUT 1A", "RTN 1A"), ("R1", "OTHER", "OUT R1", "RTN R1")),
        )
        self.assertEqual(check.status, CHECKED)
        self.assertEqual((check.compared, check.listed, check.missing), (2, 2, 0))
        self.assertEqual(check.unlisted, ())
        self.assertTrue(check.verified)

    def test_a_condition_the_portal_no_longer_lists_is_reported_and_named(self) -> None:
        # The case the page exists for: this build quotes a condition the
        # portal's own feed does not carry. The reader must be told which.
        check = check_restrictions(
            self._codes(),
            self._kb(("1A", "PEAK", "OUT 1A", "RTN 1A")),
        )
        self.assertEqual(check.status, UNPUBLISHED)
        self.assertEqual((check.compared, check.listed, check.missing), (2, 1, 1))
        self.assertEqual(check.unlisted, ("R1",))
        self.assertFalse(check.verified)

    def test_different_wording_for_the_same_condition_is_not_a_problem(self) -> None:
        # The decision this whole comparison rests on, and the one a future
        # reader is most likely to undo by accident.
        #
        # The portal words a condition in prose and the fares feed compresses
        # it, for the same condition: "VALID ON ANY TRAIN 0930 OR LATER M-F"
        # against "Not valid to depart the origin station shown on the ticket
        # until 09:30". Compare those texts and every condition differs. A
        # page that reported that would be crying wolf, and a reader who saw it
        # once would stop reading the line that tells them the portal still
        # publishes what they are being quoted.
        check = check_restrictions(
            ["3V"],
            self._kb(
                (
                    "3V",
                    "",
                    "Not valid to depart the origin station shown on the ticket until 09:30",
                    "Not valid to depart the origin station shown on the ticket until 09:30",
                )
            ),
        )
        self.assertEqual(check.status, CHECKED)
        self.assertEqual((check.compared, check.listed, check.missing), (1, 1, 0))
        self.assertTrue(check.verified)

    def test_no_reference_feed_is_absent_not_confirmation(self) -> None:
        check = check_restrictions(self._codes(), None)
        self.assertEqual(check.status, ABSENT)
        self.assertFalse(check.verified)

    def test_an_unusable_reference_feed_is_unknown_not_confirmation(self) -> None:
        loaded = Knowledgebase(files_read=["x.xml"])
        loaded.unrecognised["somethingelse"] += 3
        check = check_restrictions(self._codes(), loaded)
        self.assertEqual(check.status, UNKNOWN)
        self.assertFalse(check.verified)
        self.assertIn("not understood", check.note)

    def test_a_condition_neither_feed_knows_is_reported_not_skipped(self) -> None:
        # This one used to assert the opposite, and the change is the whole
        # point of the codes-only design. A missing code used to be skipped,
        # because skipping was the safe thing to do when a "disagreement" meant
        # "these two feeds word the same condition differently" -- and a
        # disagreement nobody could defend was worse than silence. What is
        # compared now is publication, which is a fact about the portal: this
        # build quotes 1A and the portal does not list it, so the reader is
        # told. Silence here would be the lie, because it would read as "the
        # portal publishes everything this build quotes".
        check = check_restrictions(["1A"], self._kb(("ZZ", "SOMETHING ELSE", "OUT", "RTN")))
        self.assertEqual(check.status, UNPUBLISHED)
        self.assertEqual(check.unlisted, ("1A",))
        self.assertEqual((check.compared, check.listed, check.missing), (1, 0, 1))
        self.assertFalse(check.verified)

    def test_a_build_quoting_no_condition_at_all_is_unknown(self) -> None:
        # A page with no restriction codes is not a page the portal has
        # confirmed anything about, and must not print "all zero of them".
        check = check_restrictions([], self._kb(("1A", "PEAK", "OUT", "RTN")))
        self.assertEqual(check.status, UNKNOWN)
        self.assertFalse(check.verified)
        self.assertIn("quotes no restriction condition", check.note)


class WordingTest(unittest.TestCase):
    """The four answers are worded once; these hold that wording to its facts."""

    def _describe(self, **kwargs) -> str:
        # The console sentence reads the note the page carries, so the test
        # carries one too. That is the property being kept: what an operator
        # reads in the terminal and what a reader sees cannot be two different
        # answers about the same conditions.
        note = {
            "status": ABSENT,
            "compared": 0,
            "listed": 0,
            "missing": 0,
            "unlisted": [],
            "note": "",
            "published": "",
            "checkedAt": "",
        }
        note.update(kwargs)
        return describe_restriction_note(note)

    def test_the_confirmed_answer_names_how_many_conditions_it_covered(self) -> None:
        said = self._describe(
            status=CHECKED, compared=7, listed=7, published="2026-09-26T04:15:00Z"
        )
        self.assertIn("still publishes all 7", said)
        self.assertIn("published 2026-09-26", said)
        # And without a date the wording is still a complete sentence, rather
        # than one with a hole where a claim should be. The portal sends no
        # Last-Modified on these feeds, so the absent date is the usual case.
        self.assertNotIn("None", self._describe(status=CHECKED, compared=7, listed=7))

    def test_no_answer_ever_claims_the_two_feeds_agree_about_wording(self) -> None:
        # The portal compresses what the fares feed spells out. Any wording
        # here that says the feeds agree, or disagree, would be saying something
        # the comparison never established.
        for status, kwargs in (
            (CHECKED, {"compared": 7, "listed": 7}),
            (UNPUBLISHED, {"compared": 7, "listed": 6, "missing": 1, "unlisted": ("B3",)}),
        ):
            said = self._describe(status=status, **kwargs)
            self.assertNotIn("agree", said.lower())
            self.assertNotIn("disagree", said.lower())

    def test_a_missing_condition_names_the_codes(self) -> None:
        said = self._describe(
            status=UNPUBLISHED, compared=7, listed=6, missing=1, unlisted=("B3",)
        )
        self.assertIn("no longer publishes 1 of the 7", said)
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

    def test_the_worker_path_receives_the_parents_parsed_feed(self) -> None:
        # The feed is delivered once per process rather than re-read per page,
        # and the answer is worked out inside the worker from the page's own
        # rows -- so the worker needs the feed itself, not a verdict.
        import build_workers

        source = Path(build_workers.__file__).read_text(encoding="utf-8")
        self.assertIn("reference=_WORKER.get(\"reference\")", source)
        self.assertIn('_WORKER["reference"] = reference', source)

    def test_both_ways_into_a_page_are_given_the_same_state(self) -> None:
        # The pool initialiser and the in-process build both have to hand the
        # worker its reference feed. Only the pool path did, so a
        # --workers 1 --all-origins build with --knowledgebase told every page
        # that no reference feed had been named while the same build across
        # several processes checked every one of them. Asserted on the source
        # because the failure is a missing call on one of two paths, which is
        # invisible to any test that builds a page one way.
        import build_pool
        import build_workers

        worker_source = Path(build_workers.__file__).read_text(encoding="utf-8")
        # The two paths into a page are the pool initialiser and the in-process
        # branch of the builder, and the builder's phases live in build_pool.py
        # since the split (ADR-0071).
        build_source = Path(build_pool.__file__).read_text(encoding="utf-8")
        self.assertIn("def configure_worker(shared: dict", worker_source)
        # The initialiser delegates to it rather than duplicating it...
        self.assertIn("configure_worker(shared, reference)", worker_source)
        # ...and so does the in-process branch.
        self.assertIn("configure_worker(shared, reference)", build_source)
        # Neither path may clear and refill the worker state on its own again.
        self.assertNotIn("_WORKER.clear()", build_source)

    def test_the_resumable_signature_distinguishes_two_different_answers(self) -> None:
        # Otherwise a resumed build could keep pages built against a reference
        # feed that has since changed, mixing two answers inside one release.
        import build_state

        shared = {
            "max_changes": 1, "note": "", "attribution": None, "price_source": "x",
            "feed_date": None, "base_path": "", "provider": "p", "link_mode": "fallback",
            "adults": 2, "network": None, "advertiser_id": None, "publisher_id": "",
            "departures": 5, "index": [], "feed": "f", "timetable": None, "analytics": None,
        }
        absent = dict(shared, reference_fingerprint="absent")
        differs = dict(shared, reference_fingerprint="2026-09-26|2026-09-26|abc123")
        again = dict(shared, reference_fingerprint="absent")
        self.assertNotEqual(
            build_state.resumable_signature(absent, []),
            build_state.resumable_signature(differs, []),
        )
        # And the same answer twice is the same build, or nothing would resume.
        self.assertEqual(
            build_state.resumable_signature(absent, []),
            build_state.resumable_signature(again, []),
        )

    def test_the_fingerprint_is_stable_for_one_feed_and_moves_with_it(self) -> None:
        # The signature is JSON-serialised, so the fingerprint has to be a
        # value with a stable serialised form. A parsed feed's repr carries an
        # address: serialising the feed itself would give every run a different
        # signature, and a build that never resumes is a build that rebuilds
        # 2,700 pages for nothing.
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_ticket_restrictions(
                build_synthetic_knowledgebase(Path(tmp) / "a", omit=None)
            )
            dropped = load_ticket_restrictions(
                build_synthetic_knowledgebase(Path(tmp) / "b", omit="1A")
            )
            one = reference_fingerprint(loaded, "2026-09-26", "2026-09-26")
            self.assertEqual(one, reference_fingerprint(loaded, "2026-09-26", "2026-09-26"))
            self.assertNotEqual(one, reference_fingerprint(dropped, "2026-09-26", "2026-09-26"))
            self.assertNotEqual(one, reference_fingerprint(loaded, "2026-09-27", "2026-09-26"))
            self.assertEqual(reference_fingerprint(None, "", ""), "absent")

    def test_the_claim_is_about_the_rows_on_the_page(self) -> None:
        # The check reports on the conditions a reader can find on the page.
        # Asking the feed for every code the origin's flows could carry made a
        # station page report on 32 conditions while showing 4, naming codes a
        # reader could not see anywhere on it.
        rows = [
            {"restrictionCode": "3V"},
            {"restrictionCode": "B3"},
            {"restrictionCode": ""},
            {"restrictionCode": None},
            {"restrictionCode": "3V"},
        ]
        self.assertEqual(restriction_codes_shown(rows), {"3V", "B3"})
        self.assertEqual(restriction_codes_shown([]), set())


class FixtureTest(unittest.TestCase):
    def _fixture_codes(self) -> list[str]:
        from make_synthetic_feed import _restriction_lines
        from atoc_restrictions import RESTRICTION_OFFSETS

        codes: list[str] = []
        for line in _restriction_lines():
            if line[1:3] != "RH":
                continue
            offsets = RESTRICTION_OFFSETS["RH"]
            code = line[offsets["restriction_code"][0] : offsets["restriction_code"][1]].strip()
            if code:
                codes.append(code)
        self.assertTrue(codes, "the fixture has restriction codes to compare")
        return codes

    def test_the_fixture_lists_every_condition_the_fares_feed_quotes(self) -> None:
        # The fixture is built from the same restriction records the fares feed
        # carries, so the codes line up by construction. That is the point: this
        # asserts the comparison ran and matched, not that two hand-kept copies
        # of a list agree.
        codes = self._fixture_codes()
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_ticket_restrictions(
                build_synthetic_knowledgebase(Path(tmp) / "a", omit=None)
            )
            check = check_restrictions(codes, loaded)
            self.assertEqual(check.status, CHECKED)
            self.assertEqual((check.compared, check.listed, check.missing), (len(codes), len(codes), 0))
            self.assertTrue(check.verified)

    def test_a_condition_dropped_from_the_reference_is_reported(self) -> None:
        # The other direction, and the one the page exists for: a condition the
        # fares feed still quotes and the reference feed no longer lists. The
        # fixture omits one code by name, so the case is built rather than
        # happening to occur.
        codes = self._fixture_codes()
        dropped = codes[0]
        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_ticket_restrictions(
                build_synthetic_knowledgebase(Path(tmp) / "a", omit=dropped)
            )
            check = check_restrictions(codes, loaded)
            self.assertEqual(check.status, UNPUBLISHED)
            self.assertEqual(check.unlisted, (dropped,))
            self.assertEqual(check.missing, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
