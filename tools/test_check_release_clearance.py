"""Tests for the release clearance gate.

The gate's whole job is to refuse, so the tests are about refusal. The one
that matters most is the shipped record: `licences/release-clearance.md` is
written today with no licence cleared, and a test that let it drift into a pass
would turn a documented refusal into a silent one -- which is the exact shape of
the finding this gate closes. The record does clear one product, the privacy
contact, and that one is not a licence: the tests below hold that clearing it
did not clear a release.

The other tests are the ways a clearance might be faked, each asked of the same
function: an answer that is not a yes, a clearance that has expired, one dated in
the future, one inherited from a licence file that has since been replaced, a
product nobody answered, and a release asking for a shape that does not exist.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tools.check_release_clearance import (
    DTD,
    MANIFEST_NAME,
    PRIVACY,
    clearance_problems,
    digest,
    file_sha256,
    main,
    manifest_sha,
    parse_sections,
    product_digests,
    products,
    products_needed,
    template,
)

ROOT = Path(__file__).parent.parent
RECORD = ROOT / "licences" / "release-clearance.md"
#: The day the shipped record is read. It is frozen rather than `date.today()`, so
#: a run six months from now does not read a record whose clearances have quietly
#: expired, and it has to be at or after every date the record itself carries or
#: the record's own clearance reads as future-dated. The privacy contact's
#: confirmation is dated this day.
TODAY = date(2026, 10, 14)
DARWIN = "P-9ca6bc7e-62e1-44d6-b93a-1616f7d2caf8"


def cleared(block: str, **fields: str) -> str:
    """A record holding one product's block, in the shape the gate reads."""
    lines = ["- state: cleared", f"- answer: {'yes'}", "- approved by: a person"]
    lines += [f"- {name}: {value}" for name, value in fields.items()]
    return f"# a record\n\n## {block}\n\n" + "\n".join(lines) + "\n"


class ShippedRecordTest(unittest.TestCase):
    """The record as committed, which is the project's actual licence position."""

    def setUp(self) -> None:
        self.text = RECORD.read_text(encoding="utf-8")

    def test_the_shipped_record_still_refuses_both_build_shapes(self) -> None:
        # No licence is cleared, and the publish checklist is explicit that the
        # DTD route is unresolved, so a release that publishes fares is refused
        # whichever shape it asks for. The one product the record does clear is
        # the privacy contact, which is a promise a person keeps rather than a
        # licence anyone read, and clearing it must not be enough.
        for release in (["fares"], ["fares", "timetable"]):
            with self.subTest(release=release):
                problems = clearance_problems(self.text, releasing=release, today=TODAY)
                self.assertTrue(problems)
                self.assertTrue(any(DTD in problem for problem in problems), problems)

    def test_the_report_only_mode_needs_nothing_cleared(self) -> None:
        # The shape of the question matters: a run that publishes nothing is
        # asking what the record says, not for permission to publish.
        self.assertEqual(clearance_problems(self.text, releasing=[], today=TODAY), [])

    def test_every_product_the_tool_knows_has_a_section(self) -> None:
        # A licence PDF can be filed without a decision if this ever slips, and
        # then a later build would publish it by default.
        sections = parse_sections(self.text)
        for product in products():
            with self.subTest(product=product):
                self.assertTrue(
                    any(product.lower() in heading.lower() for heading in sections),
                    f"{product} is a known product with no section in the record",
                )

    def test_every_product_has_a_decision_and_every_exclusion_a_reason(self) -> None:
        # Every product is either cleared or excluded, and an exclusion has to
        # say why: excluding is the safe direction, so it may not need an
        # approval, but it may not be silent either.
        sections = parse_sections(self.text)
        for product in products():
            fields = next(f for h, f in sections.items() if product.lower() in h.lower())
            with self.subTest(product=product):
                state = fields.get("state")
                self.assertIn(state, ("cleared", "excluded"), f"{product} has no decision")
                if state == "excluded":
                    self.assertTrue(
                        fields.get("reason", "").strip(), f"{product} is excluded with no reason"
                    )


class ParseTest(unittest.TestCase):
    def test_fields_are_read_from_their_own_section_only(self) -> None:
        sections = parse_sections("# top\n\n- answer: yes\n\n## one\n\n- state: cleared\n\n## two\n\n- state: excluded\n")
        self.assertEqual(sections["one"], {"state": "cleared"})
        self.assertEqual(sections["two"], {"state": "excluded"})

    def test_prose_above_the_first_section_is_not_a_field(self) -> None:
        # The record explains itself in prose. That prose must not be able to
        # answer a question by accident.
        sections = parse_sections("# why\n\n- answer: yes\n\n## one\n\n- state: cleared\n")
        self.assertNotIn("answer", sections["one"])


class ClearanceTest(unittest.TestCase):
    """A clearance that is real passes. Each way of faking one does not."""

    def _record(self, **fields: str) -> str:
        base = dict(
            **{
                "read on": "2026-09-20",
                "approved on": "2026-09-21",
                "expires": "2027-03-21",
            }
        )
        base.update(fields)
        # A release that publishes anything needs the privacy contact as well as
        # the licences, so a record under test clears it too. Every other
        # product is excluded, so the check under test is the only one with
        # anything to say.
        text = cleared(DTD, **base) + "\n" + cleared(PRIVACY, **base)
        for product in products():
            if product not in (DTD, PRIVACY):
                text += f"\n## {product}\n\n- state: excluded\n- reason: not used by this build\n"
        return text

    def test_a_real_clearance_passes(self) -> None:
        self.assertEqual(clearance_problems(self._record(), releasing=["fares"], today=TODAY), [])

    def test_an_answer_that_is_not_yes_is_a_refusal(self) -> None:
        # "unknown", "probably" and a blank are the same to this gate, which is
        # the point: a licence nobody has read cannot be cleared by saying so.
        for answer in ("unknown", "probably", "I think so", "", "yes-ish"):
            with self.subTest(answer=answer):
                text = self._record().replace("- answer: yes", f"- answer: {answer}")
                problems = clearance_problems(text, releasing=["fares"], today=TODAY)
                self.assertTrue(problems, f"{answer!r} cleared a release")
                self.assertTrue(any("answer" in p for p in problems))

    def test_an_expired_clearance_is_a_refusal(self) -> None:
        problems = clearance_problems(
            self._record(expires="2026-09-27"), releasing=["fares"], today=TODAY
        )
        self.assertTrue(any("expired" in p for p in problems))

    def test_a_clearance_dated_in_the_future_is_a_refusal(self) -> None:
        # A decision that has not happened yet is not a decision.
        problems = clearance_problems(
            self._record(**{"approved on": "2026-10-15"}), releasing=["fares"], today=TODAY
        )
        self.assertTrue(any("future" in p for p in problems))

    def test_a_clearance_with_no_approver_is_a_refusal(self) -> None:
        problems = clearance_problems(
            self._record().replace("- approved by: a person\n", ""), releasing=["fares"], today=TODAY
        )
        self.assertTrue(any("approved by" in p for p in problems))

    def test_a_missing_expiry_is_a_refusal(self) -> None:
        problems = clearance_problems(
            self._record().replace("- expires: 2027-03-21\n", ""), releasing=["fares"], today=TODAY
        )
        self.assertTrue(any("expires" in p for p in problems))

    def test_a_record_with_no_privacy_contact_section_is_a_refusal(self) -> None:
        # A contact nobody wrote about is the filed-and-forgotten case for a
        # promise rather than for a licence, and it has to be refused the same
        # way: an absent section is not a cleared one.
        text = self._record().replace(f"## {PRIVACY}\n", "## an unrelated heading\n")
        problems = clearance_problems(text, releasing=["fares"], today=TODAY)
        self.assertTrue(
            any(PRIVACY in problem for problem in problems),
            f"a record with no {PRIVACY} section published without a complaint: {problems}",
        )


class DigestTest(unittest.TestCase):
    """A clearance is made from a licence file, and does not outlive it."""

    def test_a_marketplace_clearance_must_name_the_licence_it_read(self) -> None:
        pdf = product_digests()[DARWIN]
        text = (
            f"## {DARWIN}\n\n- state: cleared\n- answer: yes\n- read on: 2026-09-20\n"
            "- approved by: a person\n- approved on: 2026-09-21\n- expires: 2027-03-21\n"
        )
        for product in products():
            if product != DARWIN:
                text += f"\n## {product}\n\n- state: excluded\n- reason: not used\n"
        self.assertTrue(clearance_problems(text, releasing=["fares", "timetable"], today=TODAY))

        # With the digest added to that same block, and the DTD route and the
        # privacy contact cleared as well, the release passes. The digest is the
        # whole difference.
        text = text.replace(
            f"\n## {DTD}\n\n- state: excluded\n- reason: not used\n",
            f"\n## {DTD}\n\n- state: cleared\n- answer: yes\n- read on: 2026-09-20\n"
            "- approved by: a person\n- approved on: 2026-09-21\n- expires: 2027-03-21\n",
        )
        text = text.replace(
            f"\n## {PRIVACY}\n\n- state: excluded\n- reason: not used\n",
            f"\n## {PRIVACY}\n\n- state: cleared\n- answer: yes\n- read on: 2026-09-20\n"
            "- approved by: a person\n- approved on: 2026-09-21\n- expires: 2027-03-21\n",
        )
        text = text.replace(
            "- approved on: 2026-09-21\n- expires: 2027-03-21\n",
            f"- approved on: 2026-09-21\n- expires: 2027-03-21\n- licence digest: {digest(pdf)}\n",
            1,
        )
        self.assertEqual(
            clearance_problems(text, releasing=["fares", "timetable"], today=TODAY), []
        )

    def test_a_replaced_licence_does_not_inherit_the_clearance(self) -> None:
        # Same record, different file: the words on the page are unchanged and
        # the clearance is void, which is the only way this check can be right
        # without reading the licence itself. The PDFs are stand-ins named as
        # the committed manifest names them: the licences are not in a clean
        # checkout, and what is under test is the digest, not their wording.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for pdf_path in product_digests().values():
                (folder / pdf_path.name).write_bytes(
                    b"%PDF-1.4 stand-in for " + pdf_path.name.encode("utf-8")
                )
            _write_manifest(folder)
            pdf = folder / product_digests()[DARWIN].name
            text = (
                f"## {DARWIN}\n\n- state: cleared\n- answer: yes\n- read on: 2026-09-20\n"
                "- approved by: a person\n- approved on: 2026-09-21\n- expires: 2027-03-21\n"
                f"- licence digest: {digest(pdf)}\n"
            )
            for product in products():
                if product != DARWIN:
                    text += f"\n## {product}\n\n- state: excluded\n- reason: not used\n"
            self.assertFalse(
                any("licence file has changed" in p for p in clearance_problems(
                    text, releasing=["fares", "timetable"], today=TODAY, folder=folder
                )),
                "the unreplaced stand-in matches its own digest",
            )
            (folder / "Darwin-timetable-license-P-9ca6bc7e-62e1-44d6-b93a-1616f7d2caf8.pdf").write_bytes(
                b"%PDF-1.4 a different licence entirely"
            )
            problems = clearance_problems(
                text, releasing=["fares", "timetable"], today=TODAY, folder=folder
            )
        self.assertTrue(any("licence file has changed" in p for p in problems))

    @unittest.skipUnless(
        product_digests()[DARWIN].is_file(),
        "the Darwin licence PDF is licensed material and is not committed "
        "(ADR-0067); this checks the local copy against the committed manifest",
    )
    def test_the_local_licence_matches_the_committed_manifest(self) -> None:
        # Where the PDF is present, the manifest must name its exact bytes, or
        # the gate in CI is judging a licence nobody holds.
        pdf = product_digests()[DARWIN]
        self.assertEqual(manifest_sha(pdf.name), file_sha256(pdf))

    def test_a_missing_pdf_is_judged_against_the_manifest(self) -> None:
        # CI has the manifest and not the PDFs. A clearance whose digest does
        # not match that manifest still fails, and one that matches can pass
        # without the file being in the checkout.
        pdf = product_digests()[DARWIN]
        committed = manifest_sha(pdf.name)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / MANIFEST_NAME).write_text(
                (ROOT / "licences" / MANIFEST_NAME).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.assertFalse((folder / pdf.name).exists())
            text = (
                f"## {DARWIN}\n\n- state: cleared\n- answer: yes\n- read on: 2026-09-20\n"
                "- approved by: a person\n- approved on: 2026-09-21\n- expires: 2027-03-21\n"
                f"- licence digest: {'0' * 64}\n"
            )
            for product, path in products(folder).items():
                if product != DARWIN:
                    text += f"\n## {product}\n\n- state: excluded\n- reason: not used\n"
            problems = clearance_problems(
                text, releasing=["fares", "timetable"], today=TODAY, folder=folder
            )
            self.assertTrue(any("does not match" in p for p in problems))
            text = text.replace("0" * 64, committed)
            # DTD and the privacy contact are still excluded, and this release
            # publishes both, so the digest match is not by itself a pass.
            # What it must not do is complain about a PDF that is not in the checkout.
            problems = clearance_problems(
                text, releasing=["fares", "timetable"], today=TODAY, folder=folder
            )
        self.assertFalse(any(pdf.name in p and "changed" in p for p in problems))
        self.assertTrue(any("excluded from publication" in p for p in problems))


class ScopeTest(unittest.TestCase):
    """The mapping from a build shape to the licences it publishes."""

    def test_a_fares_only_release_needs_the_dtd_route(self) -> None:
        needed, problems = products_needed(["fares"])
        self.assertEqual(problems, [])
        self.assertEqual(needed, [DTD, PRIVACY])

    def test_a_release_with_the_timetable_needs_the_darwin_licence_too(self) -> None:
        # This is the check that stops a fares-only decision being read as
        # permission to publish the times as well.
        needed, problems = products_needed(["fares", "timetable"])
        self.assertEqual(problems, [])
        self.assertEqual(sorted(needed), sorted([DTD, DARWIN, PRIVACY]))

    def test_every_release_that_publishes_anything_needs_the_privacy_contact(self) -> None:
        # Every route promises its reader that somebody is at the end of the
        # contact address, so an address nobody has confirmed cannot be
        # published. It is not a licence and it has no filed PDF, and the gate
        # asks about it in exactly the same shape.
        for shape in (["fares"], ["fares", "timetable"]):
            with self.subTest(shape=shape):
                needed, problems = products_needed(shape)
                self.assertEqual(problems, [])
                self.assertIn(PRIVACY, needed)

    def test_a_release_that_publishes_nothing_needs_no_contact(self) -> None:
        # The report-only shape asks what the record says, not for permission,
        # and a contact nobody is publishing is nobody's business.
        self.assertEqual(products_needed([]), ([], []))
    def test_a_mistyped_shape_is_a_refusal_not_an_empty_scope(self) -> None:
        # An unrecognised shape must not resolve to "no products", which would
        # clear everything by publishing nothing.
        for shape in (["fare"], ["timetable"], ["fares", "fares"], ["everything"]):
            with self.subTest(shape=shape):
                _, problems = products_needed(shape)
                self.assertTrue(problems, f"{shape} was accepted as a build shape")


class RecordShapeTest(unittest.TestCase):
    def test_a_missing_record_is_a_refusal_not_a_pass(self) -> None:
        # The dangerous failure is a file that is absent, because "no record"
        # reads most like "nothing to object to".
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--record", str(Path(tmp) / "nope.md"), "--release", "fares"]), 1)

    def test_the_shipped_record_fails_the_publish_gate(self) -> None:
        self.assertEqual(main(["--record", str(RECORD), "--release", "fares"]), 1)

    def test_a_missing_release_shape_does_not_clear_anything(self) -> None:
        # The dangerous flag is the absent one. An empty scope requires nothing
        # to be cleared, so a dropped --release would turn the gate into a no-op
        # and a red run into a green one.
        for argv in ([], ["--release", ""]):
            with self.subTest(argv=argv):
                self.assertEqual(main(["--record", str(RECORD), *argv]), 1)

    def test_report_only_reads_the_record_without_gating(self) -> None:
        # Useful for a person, and deliberately spelled differently so it can
        # never be reached by forgetting an argument.
        self.assertEqual(main(["--record", str(RECORD), "--report-only"]), 0)

    def test_report_only_names_what_the_record_leaves_outstanding(self) -> None:
        # The mode exists to read the record, and it used to answer "cleared
        # for the record as it stands" over a record that excludes every
        # product in it: the empty shape requires nothing, so nothing was
        # wrong and the sentence claimed everything was fine. The shipped
        # record is the case, because it is the record this project publishes
        # against.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--record", str(RECORD), "--report-only"]), 0)
        said = out.getvalue()
        self.assertIn("outstanding", said)
        self.assertIn(DTD, said)
        # The privacy contact is the one product this record clears, so it is no
        # longer outstanding; every licence product still is.
        self.assertNotIn(PRIVACY, said)
        self.assertNotIn("cleared for the record as it stands", said)
        # A product with no section at all is outstanding too: unrecorded is
        # not the same as cleared, and the filed-and-forgotten case is exactly
        # a heading that never got written.
        with tempfile.TemporaryDirectory() as tmp:
            thin = Path(tmp) / "thin.md"
            blocks = []
            for name, path in products().items():
                fields = {
                    "read on": "2026-09-20",
                    "approved on": "2026-09-21",
                    "expires": "2027-03-21",
                }
                if path is not None:
                    fields["licence digest"] = digest(path)
                blocks.append(cleared(name, **fields))
            thin.write_text("".join(blocks), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["--record", str(thin), "--report-only"]), 0)
            self.assertIn("every one of", out.getvalue())

    def test_a_product_answered_twice_is_a_refusal(self) -> None:
        # Two headings naming the same product are two answers to one question,
        # and taking the first would let a cleared block be shadowed by an
        # excluded one or the other way round, depending on the order.
        text = (
            f"## {DTD}\n\n- state: cleared\n- answer: yes\n- approved by: x\n"
            f"- read on: 2026-09-20\n- approved on: 2026-09-21\n- expires: 2027-03-21\n\n"
            f"## National Rail Data Portal ({DTD})\n\n- state: excluded\n- reason: b\n"
        )
        problems = clearance_problems(text, releasing=["fares"], today=TODAY)
        self.assertTrue(any("answered twice" in p for p in problems))

    def test_a_product_nobody_answered_is_a_refusal(self) -> None:
        problems = clearance_problems("# empty\n", releasing=[], today=TODAY)
        self.assertTrue(any("no clearance section" in p for p in problems))
        self.assertEqual(len(problems), len(products()))

    def test_an_unknown_state_is_a_refusal_rather_than_a_guess(self) -> None:
        # A typo in `state` must not fall through to either answer.
        text = f"## {DTD}\n\n- state: clear\n- answer: yes\n- approved by: x\n"
        problems = clearance_problems(text, releasing=[], today=TODAY)
        self.assertTrue(any("'state'" in p for p in problems))

    def test_the_template_names_every_product_with_its_digest(self) -> None:
        printed = template()
        for product, pdf in products().items():
            with self.subTest(product=product):
                self.assertIn(f"## {product}", printed)
                if pdf is not None:
                    self.assertIn(digest(pdf), printed)
        # The portal route has no file, so it must not be given a digest to
        # copy: a digest it cannot have is a digest nobody can get right.
        self.assertNotIn(f"## {DTD}\n\n- state: excluded\n- reason: \n- licence digest", printed)


class WorkflowTest(unittest.TestCase):
    """The workflow's declared shape and the shape it actually builds must agree.

    The clearance is a statement about what a build publishes, and the workflow
    states it in two places: the build step's own flags, and the `--release` the
    clearance job passes. Nothing makes those two agree at run time, so if
    somebody adds the national timetable to the build and forgets the
    declaration, the gate would clear a fares-only decision over a release that
    publishes a licence this project has not cleared.

    Parsed as text rather than YAML: the project declares no dependencies, and a
    gate that only runs where PyYAML happens to be installed is not a gate.
    """

    def setUp(self) -> None:
        self.workflow = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")

    def test_the_clearance_job_gates_the_deploy(self) -> None:
        self.assertIn("clearance:", self.workflow)
        # The deploy job, and only it, must wait on the clearance; the jobs it
        # also needs (the gates, the assembled site) may grow.
        deploy = self.workflow.split("\n  deploy:\n", 1)[1]
        self.assertRegex(deploy.split("\n", 1)[0], r"^    needs: \[[^\]]*\bclearance\]")

    def test_the_declared_shape_matches_the_flags_the_build_passes(self) -> None:
        build = self.workflow.split("Build the site from audited fares", 1)[1]
        run = build.split("\n      - name:", 1)[0]
        # The national timetable is the only flag that widens what is
        # published, and it is the one this project's licence reading refuses.
        with_timetable = "--timetable" in run
        declared = re.search(r"check_release_clearance\.py --release ([\w,]+)", self.workflow)
        self.assertIsNotNone(declared, "the clearance step passes no --release")
        self.assertEqual(
            "timetable" in declared.group(1),
            with_timetable,
            "the build step and the --release the gate is given disagree about the "
            "national timetable; the clearance would clear a release it does not describe",
        )


def _write_manifest(folder: Path) -> None:
    """A manifest of whatever PDFs are in ``folder``, as the gate will read it."""
    product_id = re.compile(r"P-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    files = []
    for pdf in sorted(folder.glob("*.pdf")):
        found = product_id.search(pdf.name)
        files.append(
            {
                "filename": pdf.name,
                "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "product_id": found.group(0) if found else None,
            }
        )
    (folder / MANIFEST_NAME).write_text(
        json.dumps({"files": files}, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
